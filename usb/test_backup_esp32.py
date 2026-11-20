"""Prove offline del backup: un eseguibile finto sostituisce sempre esptool.

La porta /dev/null soddisfa il controllo di dispositivo a caratteri, ma non
viene aperta dal fake. Nessun test usa hardware, rete o pacchetti aggiuntivi.
"""

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("backup_esp32.sh")
FLASH_BYTES = 4 * 1024 * 1024
FLASH_CONTENT = bytes(range(256)) * (FLASH_BYTES // 256)

FAKE_PROGRAM = r'''
import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
if arguments[:2] != ["-m", "esptool"]:
    os.execv(ACTUAL_PYTHON, [ACTUAL_PYTHON, *arguments])

arguments = arguments[2:]
commands = ("get-security-info", "flash-id", "read-flash")
command = next((arg for arg in arguments if arg in commands), None)
with Path(os.environ["HAMDA_ESP32_TEST_LOG"]).open("a", encoding="utf-8") as log:
    premature_marker = (
        (Path(arguments[-1]).parent / "VERIFIED.txt").exists()
        if command == "read-flash" else False
    )
    log.write(json.dumps({"command": command, "args": arguments, "premature_marker": premature_marker}) + "\n")

mode = os.environ.get("HAMDA_ESP32_TEST_MODE", "success")
if command == "get-security-info":
    print("esptool v5.6.0")
    print("Connected to ESP32-C3 on /dev/null:")
    if mode != "unknown_flags":
        print("Flags: 0x00000001" if mode == "nonzero_flags" else "Flags: 0x00000000")
    if mode == "duplicate_flags":
        print("Flags: 0x00000000")
    print("Secure Boot: Enabled" if mode == "secure_boot" else "Secure Boot: Disabled")
    if mode != "unknown_encryption":
        print("Flash Encryption: Enabled" if mode == "encrypted" else "Flash Encryption: Disabled")
    print("Staying in bootloader.")
    raise SystemExit(9 if mode == "security_fail" else 0)

if command == "flash-id":
    print("Manufacturer: c8")
    print("Device: 4016")
    print("Detected flash size: 4MB")
    print("Staying in bootloader.")
    raise SystemExit(8 if mode == "flash_id_fail" else 0)

if command == "read-flash":
    output = Path(arguments[-1])
    content = bytes(range(256)) * (4 * 1024 * 1024 // 256)
    second = output.name == "firmware_B.bin"
    if mode == "read_fail" and second:
        output.write_bytes(content[:1024])
        print("Simulated read failure", file=sys.stderr)
        raise SystemExit(7)
    if mode == "mismatch" and second:
        content = content[:-1] + bytes([content[-1] ^ 1])
    if mode == "short" and second:
        content = content[:-1]
    if mode == "oversized" and second:
        content += b"x"
    output.write_bytes(content)
    print(f"Read {len(content)} bytes into {output.name}")
    print("Staying in bootloader.")
    raise SystemExit(0)

print("Forbidden or unexpected esptool command", file=sys.stderr)
raise SystemExit(77)
'''


class BackupScriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hamda_backup_test_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.parent = self.root / "backups"
        self.parent.mkdir()
        self.log = self.root / "fake_calls.jsonl"
        self.fake_python = self.root / "fake_python"
        source = (
            f"#!{sys.executable}\n"
            f"ACTUAL_PYTHON = {sys.executable!r}\n"
            + FAKE_PROGRAM
        )
        self.fake_python.write_text(source, encoding="utf-8")
        self.fake_python.chmod(0o700)

    def run_backup(self, mode="success"):
        environment = os.environ.copy()
        environment.update({
            "HAMDA_ESP32_PYTHON": str(self.fake_python),
            "HAMDA_ESP32_PORT": "/dev/null",
            "HAMDA_ESP32_BACKUP_PARENT": str(self.parent),
            "HAMDA_ESP32_TEST_LOG": str(self.log),
            "HAMDA_ESP32_TEST_MODE": mode,
        })
        return subprocess.run(
            ["bash", str(SCRIPT)],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def backup_directories(self):
        return sorted(self.parent.glob("HAMDA_backup_ESP32_*"))

    def assert_no_verified_marker(self):
        directories = self.backup_directories()
        self.assertTrue(directories, "Il tentativo deve conservare la propria cartella")
        self.assertTrue(all(not (directory / "VERIFIED.txt").exists() for directory in directories))

    def assert_nonzero(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_success_verifies_two_identical_complete_reads_and_relative_hashes(self):
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        directories = self.backup_directories()
        self.assertEqual(len(directories), 1)
        directory = directories[0]
        self.assertRegex(directory.name, r"^HAMDA_backup_ESP32_[A-Za-z0-9]{8}$")
        for name in ("firmware_A.bin", "firmware_B.bin"):
            self.assertEqual((directory / name).stat().st_size, FLASH_BYTES)
            self.assertEqual((directory / name).read_bytes(), FLASH_CONTENT)
        expected_digest = hashlib.sha256(FLASH_CONTENT).hexdigest()
        hashes = {}
        for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, filename = line.split(maxsplit=1)
            filename = filename.lstrip("*")
            self.assertFalse(Path(filename).is_absolute())
            self.assertEqual(Path(filename).name, filename)
            hashes[filename] = digest
        self.assertEqual(hashes, {"firmware_A.bin": expected_digest, "firmware_B.bin": expected_digest})
        self.assertTrue((directory / "VERIFIED.txt").is_file())

    def test_backup_folder_and_all_result_files_are_private(self):
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        directory = self.backup_directories()[0]
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        for path in directory.rglob("*"):
            with self.subTest(path=path.name):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)

    def test_success_commands_are_read_only_in_order_and_do_not_reset(self):
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls()
        self.assertEqual(
            [call["command"] for call in calls],
            ["get-security-info", "flash-id", "read-flash", "read-flash"],
        )
        for call in calls:
            arguments = call["args"]
            self.assertFalse(call["premature_marker"], "VERIFIED non può esistere durante le letture")
            for option, expected in (
                ("--chip", "esp32c3"),
                ("--port", "/dev/null"),
                ("--baud", "115200"),
                ("--before", "no-reset"),
                ("--after", "no-reset"),
            ):
                with self.subTest(command=call["command"], option=option):
                    self.assertEqual(arguments[arguments.index(option) + 1], expected)
            self.assertIn("--no-stub", arguments)
            forbidden = {"write-flash", "erase-flash", "erase-region", "burn-efuse", "burn-key"}
            self.assertFalse(forbidden.intersection(arguments))
        for call, expected_name in zip(calls[2:], ("firmware_A.bin", "firmware_B.bin")):
            arguments = call["args"]
            offset = arguments.index("read-flash") + 1
            self.assertEqual(int(arguments[offset], 0), 0)
            self.assertEqual(arguments[offset + 1].upper(), "ALL")
            self.assertEqual(Path(arguments[offset + 2]).name, expected_name)

    def test_security_protection_and_unknown_information_stop_before_flash_access(self):
        for mode in ("secure_boot", "encrypted", "nonzero_flags", "unknown_flags", "unknown_encryption", "duplicate_flags"):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                result = self.run_backup(mode)
                self.assert_nonzero(result)
                self.assertEqual([call["command"] for call in self.calls()], ["get-security-info"])
                self.assert_no_verified_marker()
                for directory in self.backup_directories():
                    self.assertFalse((directory / "firmware_A.bin").exists())

    def test_failed_security_command_is_not_hidden_by_successful_tee(self):
        result = self.run_backup("security_fail")
        self.assert_nonzero(result)
        self.assertEqual([call["command"] for call in self.calls()], ["get-security-info"])
        self.assert_no_verified_marker()

    def test_failed_flash_metadata_command_is_not_hidden_by_successful_tee(self):
        result = self.run_backup("flash_id_fail")
        self.assert_nonzero(result)
        self.assertEqual([call["command"] for call in self.calls()], ["get-security-info", "flash-id"])
        self.assert_no_verified_marker()

    def test_failed_read_preserves_partial_files_without_verified_marker(self):
        result = self.run_backup("read_fail")
        self.assert_nonzero(result)
        self.assert_no_verified_marker()
        directory = self.backup_directories()[0]
        self.assertEqual((directory / "firmware_A.bin").stat().st_size, FLASH_BYTES)
        self.assertEqual((directory / "firmware_B.bin").stat().st_size, 1024)

    def test_different_second_read_is_rejected_even_with_expected_size(self):
        result = self.run_backup("mismatch")
        self.assert_nonzero(result)
        self.assert_no_verified_marker()
        directory = self.backup_directories()[0]
        first = (directory / "firmware_A.bin").read_bytes()
        second = (directory / "firmware_B.bin").read_bytes()
        self.assertEqual(len(first), FLASH_BYTES)
        self.assertEqual(len(second), FLASH_BYTES)
        self.assertNotEqual(first, second)

    def test_wrong_size_read_is_rejected(self):
        for mode, expected_size in (("short", FLASH_BYTES - 1), ("oversized", FLASH_BYTES + 1)):
            with self.subTest(mode=mode):
                before = set(self.backup_directories())
                result = self.run_backup(mode)
                self.assert_nonzero(result)
                self.assert_no_verified_marker()
                directory, = set(self.backup_directories()) - before
                self.assertEqual((directory / "firmware_B.bin").stat().st_size, expected_size)

    def test_repeated_runs_create_new_directories_and_preserve_previous_backup(self):
        first = self.run_backup()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        original = self.backup_directories()[0]
        before = {path.name: path.read_bytes() for path in original.iterdir() if path.is_file()}
        second = self.run_backup()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        directories = self.backup_directories()
        self.assertEqual(len(directories), 2)
        self.assertNotEqual(directories[0], directories[1])
        self.assertEqual(before, {path.name: path.read_bytes() for path in original.iterdir() if path.is_file()})
        self.assertTrue(all((directory / "VERIFIED.txt").is_file() for directory in directories))

    def test_success_does_not_claim_a_guaranteed_restore(self):
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = (result.stdout + result.stderr).lower()
        self.assertRegex(output, r"(?:non|not|no).*(?:ripristin|restor)")


if __name__ == "__main__":
    unittest.main()
