"""Offline tests: no real subprocess, port, SDK or firmware operation."""
import contextlib
import hashlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("flash_a_under_test", Path(__file__).with_name("flash_a.py"))
flash = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flash)


class FakeEsptool:
    def __init__(self, rig):
        self.rig = rig
        self.calls = []
        self.replacements = {}
        self.failures = {}
        self.after_security = None

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        self.rig.assertEqual(args[:3], [sys.executable, "-m", "esptool"])
        self.rig.assertEqual(kwargs, dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, check=False))
        if "version" in args:
            phase, output = "version", "esptool v5.6.0\n5.6.0\n"
        elif "image-info" in args:
            phase = "boot" if ".bootloader.bin" in args[-1] else "app"
            digest = "a" * 64 if phase == "boot" else flash.IMAGE_SHA
            output = ("ESP32-C3 Extended Image Header\nChip ID: 5\n"
                      "Flash size: 4MB\nFlash freq: 80m\nFlash mode: DIO\n"
                      "Checksum: 0xa0 (valid)\nValidation hash: " + digest + " (valid)\n")
            if phase == "app":
                output += "ELF file SHA256: " + flash.ELF_SHA + "\n"
        elif "get-security-info" in args:
            phase = "security"
            output = ("Chip type: ESP32-C3 (QFN32) (revision v0.4)\nMAC: " + flash.MAC +
                      "\nFlags: 0x00000000 (0b0)\n  Secure Boot: Disabled\n"
                      "  Flash Encryption: Disabled\n")
            if self.after_security:
                self.after_security()
        elif "write-flash" in args:
            phase, output = "write", "Hash of data verified.\n" * 4
        else:
            raise AssertionError("Unexpected command: " + str(args))
        output = self.replacements.get(phase, output)
        return subprocess.CompletedProcess(args, self.failures.get(phase, 0), output)


class FlashATests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hamda-fake-flash-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.backup = self.home / "HAMDA_backup_ESP32_B9nDqzIe"
        self.backup.mkdir()
        backup_data = b"backup-A" * 524288
        self.assertEqual(len(backup_data), 4194304)
        for name in ("firmware_A.bin", "firmware_B.bin"):
            (self.backup / name).write_bytes(backup_data)
        self.build = self.home / "hamda_usb_build/progetti/hamda_usb_manuale_20261119/build"
        self.build.mkdir(parents=True)
        stem = "hamda_usb_bench.ino"
        self.boot = self.build / (stem + ".bootloader.bin")
        self.part = self.build / (stem + ".partitions.bin")
        self.app = self.build / (stem + ".bin")
        self.elf = self.build / (stem + ".elf")
        self.boot_app = self.home / "hamda_usb_build/data/packages/esp32/hardware/esp32/3.3.13/tools/partitions/boot_app0.bin"
        self.boot_app.parent.mkdir(parents=True)
        for path, size in ((self.boot, 19000), (self.part, 3072), (self.app, 300192),
                           (self.elf, 5000), (self.boot_app, 8192)):
            path.write_bytes(b"X" * size)
        for key, value in (("BACKUP_SHA", hashlib.sha256(backup_data).hexdigest()),
                           ("ELF_SHA", hashlib.sha256(self.elf.read_bytes()).hexdigest())):
            patcher = patch.object(flash, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.fake = FakeEsptool(self)
        self.stdout = io.StringIO()

    def invoke(self, **kwargs):
        with contextlib.redirect_stdout(self.stdout):
            flash.main(home=self.home, runner=self.fake, **kwargs)

    def no_write(self):
        self.assertFalse(any("write-flash" in args for args in self.fake.calls))
        self.assertNotIn("SCRITTURA A COMPLETATA", self.stdout.getvalue())

    def fails_before_write(self):
        with self.assertRaises((RuntimeError, OSError)):
            self.invoke(write=True)
        self.no_write()

    def test_explicit_intent_required(self):
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.fake.calls, [])

    def test_normal_order_single_A_four_component_write(self):
        self.invoke(write=True)
        calls = self.fake.calls
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls[0][-1], "version")
        self.assertIn(str(self.boot), calls[1])
        self.assertIn(str(self.app), calls[2])
        self.assertEqual(calls[3][-1], "get-security-info")
        write = calls[4]
        self.assertEqual(write[-8:], ["0x0", str(self.boot), "0x8000", str(self.part),
                                    "0xe000", str(self.boot_app), "0x10000", str(self.app)])
        for call in calls[3:]:
            self.assertEqual(call[call.index("--port") + 1], flash.PORT)
            self.assertIn("--no-stub", call)
            self.assertEqual(call[call.index("--after") + 1], "no-reset")
            self.assertEqual(call[call.index("--baud") + 1], "115200")
        self.assertEqual(calls[3][calls[3].index("--before") + 1], "default-reset")
        self.assertEqual(write[write.index("--before") + 1], "no-reset")
        self.assertIn("-z", write)
        for flag in ("--flash-mode", "--flash-freq", "--flash-size"):
            self.assertEqual(write[write.index(flag) + 1], "keep")
        self.assertFalse(any("merged" in arg for arg in write))
        for forbidden in ("erase-flash", "--force", "--diff-with", "hard-reset", "upload"):
            self.assertNotIn(forbidden, write)
        self.assertIn("SCRITTURA A COMPLETATA", self.stdout.getvalue())
        self.assertEqual(len(list(self.backup.iterdir())), 2)

    def test_bad_backup_hash(self):
        path = self.backup / "firmware_B.bin"
        path.write_bytes(b"Y" * 4194304)
        self.fails_before_write()
        self.assertEqual(self.fake.calls, [])

    def test_bad_backup_size(self):
        (self.backup / "firmware_A.bin").write_bytes(b"short")
        self.fails_before_write()

    def test_no_fallback_to_actual_module_B_backup_directory(self):
        self.backup.rename(self.home / "HAMDA_backup_ESP32_B_MkWPAM1J")
        self.fails_before_write()
        self.assertEqual(self.fake.calls, [])

    def test_both_unit_A_read_names_required_without_old_B_read_names(self):
        (self.backup / "firmware_B.bin").rename(self.backup / "firmware_lettura2.bin")
        self.fails_before_write()
        self.assertEqual(self.fake.calls, [])

    def test_missing_app(self):
        self.app.unlink()
        self.fails_before_write()

    def test_oversized_region(self):
        self.part.write_bytes(b"X" * 4097)
        self.fails_before_write()

    def test_empty_boot_app(self):
        self.boot_app.write_bytes(b"")
        self.fails_before_write()

    def test_elf_mismatch(self):
        self.elf.write_bytes(b"other ELF")
        self.fails_before_write()
        self.assertEqual(self.fake.calls, [])

    def test_wrong_tool_version(self):
        self.fake.replacements["version"] = "5.3.0\n"
        self.fails_before_write()

    def test_bad_app_validation_digest(self):
        self.fake.replacements["app"] = self.fake(
            [sys.executable, "-m", "esptool", "image-info", str(self.app)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False).stdout.replace(
                flash.IMAGE_SHA, "b" * 64)
        self.fake.calls.clear()
        self.fails_before_write()

    def test_bad_boot_checksum(self):
        self.fake.replacements["boot"] = (
            "Chip ID: 5\nFlash size: 4MB\nFlash freq: 80m\nFlash mode: DIO\n"
            "Checksum: 0xa0 (invalid)\nValidation hash: " + "a" * 64 + " (valid)\n")
        self.fails_before_write()

    def test_wrong_boot_mode(self):
        self.fake.replacements["boot"] = (
            "Chip ID: 5\nFlash size: 4MB\nFlash freq: 80m\nFlash mode: QIO\n")
        self.fails_before_write()

    def test_module_B_mac_is_rejected(self):
        self.fake.replacements["security"] = (
            "MAC: 10:00:3b:cc:1c:78\nFlags: 0x00000000 (0b0)\n"
            "Secure Boot: Disabled\nFlash Encryption: Disabled\n")
        self.fails_before_write()

    def test_repeated_mac_field(self):
        self.fake.replacements["security"] = "MAC: " + flash.MAC + "\nMAC: " + flash.MAC + "\n"
        self.fails_before_write()

    def test_security_flags(self):
        self.fake.replacements["security"] = (
            "MAC: " + flash.MAC + "\nFlags: 0x00000001 (0b1)\n"
            "Secure Boot: Disabled\nFlash Encryption: Disabled\n")
        self.fails_before_write()

    def test_secure_boot_enabled(self):
        self.fake.replacements["security"] = (
            "MAC: " + flash.MAC + "\nFlags: 0x00000000 (0b0)\n"
            "Secure Boot: Enabled\nFlash Encryption: Disabled\n")
        self.fails_before_write()

    def test_flash_encryption_enabled(self):
        self.fake.replacements["security"] = (
            "MAC: " + flash.MAC + "\nFlags: 0x00000000 (0b0)\n"
            "Secure Boot: Disabled\nFlash Encryption: Enabled\n")
        self.fails_before_write()

    def test_security_command_error(self):
        self.fake.failures["security"] = 2
        self.fails_before_write()

    def test_artifact_changed_after_security(self):
        self.fake.after_security = lambda: self.app.write_bytes(b"Z" * 300192)
        self.fails_before_write()

    def test_write_error_has_no_success_marker_or_retry(self):
        self.fake.failures["write"] = 2
        with self.assertRaises(RuntimeError):
            self.invoke(write=True)
        self.assertEqual(sum("write-flash" in args for args in self.fake.calls), 1)
        self.assertNotIn("SCRITTURA A COMPLETATA", self.stdout.getvalue())

    def test_missing_write_hash_verification_has_no_success(self):
        self.fake.replacements["write"] = "Hash of data verified.\n" * 3
        with self.assertRaises(RuntimeError):
            self.invoke(write=True)
        self.assertNotIn("SCRITTURA A COMPLETATA", self.stdout.getvalue())




class FlashAConstantsTests(unittest.TestCase):
    def test_unit_A_identity_backup_and_shared_artifacts(self):
        self.assertEqual(flash.MAC, "10:00:3b:cc:97:d8")
        self.assertEqual(flash.PORT, "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_10:00:3B:CC:97:D8-if00")
        self.assertEqual(flash.BACKUP_SHA, "a2d03e2f8db01d62c39952a197f2c4cdd826780980bf9b0dcf1ce50aab61910e")
        self.assertEqual(flash.ELF_SHA, "6ce79c435fcc326bca3475f487f23d66c3fe13e6b637c4e0e3a026985eb1f417")
        self.assertEqual(flash.IMAGE_SHA, "f1d3b1bc169f7a1203b5fdada68e4bfd79ee63a425fce83b5054c8b72bd65137")

    def test_inline_contains_exact_helper_without_executing(self):
        import shlex
        base = Path(__file__).parent
        source = (base / "flash_a.py").read_text()
        tokens = shlex.split((base / "flash_a_inline.txt").read_text())
        self.assertEqual(tokens[:2], ["$HOME/hamda_esp32_tools/bin/python", "-c"])
        self.assertEqual(len(tokens), 3)
        expected = source + '\ntry:\n    main(write=True)\nexcept Exception as error:\n    raise SystemExit("Caricamento interrotto: " + str(error))\n'
        self.assertEqual(tokens[2], expected)
        compile(tokens[2], "flash_a_inline", "exec")


if __name__ == "__main__":
    unittest.main()
