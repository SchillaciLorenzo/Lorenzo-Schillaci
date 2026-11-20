import importlib.util
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "tools/prepara_console_usb_mac.py"
SPEC = importlib.util.spec_from_file_location("console_usb", SOURCE)
console = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(console)


class ConsoleTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.boot = Path(folder.name)
        self.original = (
            b"console=serial0,115200 console=tty1 root=PARTUUID=9586d7bf-02 "
            b"rootwait ds=nocloud;i=rpi-imager-1793895500719 "
            b"modules-load=dwc2,g_ether g_ether.dev_addr=02:48:41:4d:44:01 "
            b"g_ether.host_addr=02:48:41:4d:44:02\n"
        )
        self.others = {
            "config.txt": b"[all]\ndtoverlay=dwc2,dr_mode=peripheral\n",
            "user-data": b"#cloud-config\n# private credential sentinel\n",
            "meta-data": b"instance-id: unchanged\n",
            "network-config": b"version: 2\nethernets: {}\n",
        }
        (self.boot / "cmdline.txt").write_bytes(self.original)
        for name, data in self.others.items():
            (self.boot / name).write_bytes(data)

    def test_preserves_identity_and_credentials_and_adds_authenticated_console(self):
        backup = console.prepare_console(self.boot)
        self.assertEqual(backup.read_bytes(), self.original)
        data = (self.boot / "cmdline.txt").read_text()
        self.assertEqual(len(data.splitlines()), 1)
        args = data.split()
        for argument in ("root=PARTUUID=9586d7bf-02",
                         "ds=nocloud;i=rpi-imager-1793895500719",
                         "modules-load=dwc2,g_serial", "g_serial.use_acm=1",
                         "network-config=disabled", console.GETTY):
            self.assertIn(argument, args)
        self.assertFalse(any(word.startswith("g_ether.") for word in args))
        for name, original in self.others.items():
            self.assertEqual((self.boot / name).read_bytes(), original)

    def test_repetition_keeps_original_and_restore_is_exact(self):
        console.prepare_console(self.boot)
        once = (self.boot / "cmdline.txt").read_bytes()
        console.prepare_console(self.boot)
        self.assertEqual((self.boot / "cmdline.txt").read_bytes(), once)
        self.assertEqual((self.boot / console.BACKUP).read_bytes(), self.original)
        console.restore_ethernet(self.boot)
        self.assertEqual((self.boot / "cmdline.txt").read_bytes(), self.original)

    def test_can_prepare_an_already_booted_image_without_seed_files(self):
        for name in ("user-data", "meta-data"):
            (self.boot / name).unlink()
        console.prepare_console(self.boot)
        self.assertIn(console.GETTY, (self.boot / "cmdline.txt").read_text().split())
        self.assertEqual((self.boot / console.BACKUP).read_bytes(), self.original)
        self.assertFalse((self.boot / "user-data").exists())
        self.assertFalse((self.boot / "meta-data").exists())

    def test_conflicting_gadget_is_rejected_before_backup_or_changes(self):
        original = self.original.replace(b"dwc2,g_ether", b"dwc2,g_multi")
        (self.boot / "cmdline.txt").write_bytes(original)
        with self.assertRaisesRegex(ValueError, "Modulo gadget inatteso"):
            console.prepare_console(self.boot)
        self.assertEqual((self.boot / "cmdline.txt").read_bytes(), original)
        self.assertFalse((self.boot / console.BACKUP).exists())

    def test_invalid_boot_line_and_missing_setup_are_rejected(self):
        for original in (b"console=tty1\n", b"console=tty1\nroot=PARTUUID=x\n"):
            with self.subTest(original=original):
                (self.boot / "cmdline.txt").write_bytes(original)
                with self.assertRaisesRegex(ValueError, "cmdline.txt non valido"):
                    console.prepare_console(self.boot)
                self.assertEqual((self.boot / "cmdline.txt").read_bytes(), original)
                self.assertFalse((self.boot / console.BACKUP).exists())
        (self.boot / "cmdline.txt").write_bytes(self.original)
        (self.boot / "config.txt").write_text("[all]\n")
        with self.assertRaisesRegex(ValueError, "dwc2 peripheral"):
            console.prepare_console(self.boot)
        self.assertEqual((self.boot / "cmdline.txt").read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
