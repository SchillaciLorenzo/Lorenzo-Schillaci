import importlib.util
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "tools/configura_usb_mac.py"
SPEC = importlib.util.spec_from_file_location("configura_usb_mac", SOURCE)
usb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(usb)


class BootConfigTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.boot = Path(self.folder.name)
        self.originals = {
            "config.txt": b"arm_64bit=1\n[cm5]\ndtoverlay=dwc2,dr_mode=host\n[all]\n",
            "cmdline.txt": (
                b"console=tty1 root=PARTUUID=9586d7bf-02 rootfstype=ext4 "
                b"rootwait ds=nocloud;i=rpi-imager-1793895500719\n"
            ),
            "network-config": b"version: 2\nethernets: {}\n",
            "user-data": b"#cloud-config\n# credential sentinel: leave untouched\n",
            "meta-data": b"instance-id: installation-sentinel\n",
        }
        for name, data in self.originals.items():
            (self.boot / name).write_bytes(data)

    def assert_unchanged(self):
        for name, data in self.originals.items():
            self.assertEqual((self.boot / name).read_bytes(), data)
        self.assertFalse((self.boot / "hamda-before-usb").exists())

    def test_preserves_image_identity_credentials_and_original_backups(self):
        backup = usb.prepare_boot(self.boot)
        line = (self.boot / "cmdline.txt").read_text()
        self.assertEqual(len(line.splitlines()), 1)
        self.assertIn("root=PARTUUID=9586d7bf-02", line.split())
        self.assertIn("ds=nocloud;i=rpi-imager-1793895500719", line.split())
        self.assertIn("modules-load=dwc2,g_ether", line.split())
        self.assertIn("g_ether.dev_addr=" + usb.DEV_MAC, line.split())
        self.assertIn("g_ether.host_addr=" + usb.HOST_MAC, line.split())
        for name in ("user-data", "meta-data"):
            self.assertEqual((self.boot / name).read_bytes(), self.originals[name])
        self.assertEqual(set(path.name for path in backup.iterdir()),
                         {"config.txt", "cmdline.txt", "network-config"})
        for path in backup.iterdir():
            self.assertEqual(path.read_bytes(), self.originals[path.name])
        config = (self.boot / "config.txt").read_text()
        self.assertTrue(config.endswith(usb.USB_BLOCK))
        self.assertIn("[cm5]\ndtoverlay=dwc2,dr_mode=host", config)
        network = (self.boot / "network-config").read_text()
        self.assertIn('macaddress: "' + usb.DEV_MAC + '"', network)
        self.assertIn("10.55.0.2/24", network)

    def test_repetition_is_idempotent_and_keeps_original_backup(self):
        backup = usb.prepare_boot(self.boot)
        once = {name: (self.boot / name).read_bytes() for name in self.originals}
        usb.prepare_boot(self.boot)
        for name, data in once.items():
            self.assertEqual((self.boot / name).read_bytes(), data)
        for path in backup.iterdir():
            self.assertEqual(path.read_bytes(), self.originals[path.name])

    def test_missing_cloud_init_file_stops_before_any_write(self):
        (self.boot / "meta-data").unlink()
        with self.assertRaisesRegex(ValueError, "File mancanti"):
            usb.prepare_boot(self.boot)
        self.assertFalse((self.boot / "hamda-before-usb").exists())
        for name in ("config.txt", "cmdline.txt", "network-config", "user-data"):
            self.assertEqual((self.boot / name).read_bytes(), self.originals[name])

    def test_multiline_or_missing_root_is_rejected_without_modification(self):
        for invalid in (b"console=tty1\nroot=PARTUUID=x\n", b"console=tty1\n"):
            with self.subTest(invalid=invalid):
                self.originals["cmdline.txt"] = invalid
                (self.boot / "cmdline.txt").write_bytes(invalid)
                with self.assertRaisesRegex(ValueError, "una sola riga"):
                    usb.prepare_boot(self.boot)
                self.assert_unchanged()

    def test_keeps_other_modules_and_rejects_conflicting_gadget(self):
        original = self.originals["cmdline.txt"].rstrip(b"\n")
        (self.boot / "cmdline.txt").write_bytes(original + b" modules-load=i2c-dev\n")
        usb.prepare_boot(self.boot)
        self.assertIn("modules-load=i2c-dev,dwc2,g_ether",
                      (self.boot / "cmdline.txt").read_text().split())
        with tempfile.TemporaryDirectory() as other:
            boot = Path(other)
            for name, data in self.originals.items():
                (boot / name).write_bytes(data)
            conflicting = original + b" modules-load=dwc2,g_multi\n"
            (boot / "cmdline.txt").write_bytes(conflicting)
            with self.assertRaisesRegex(ValueError, "altro modulo gadget"):
                usb.prepare_boot(boot)
            self.assertEqual((boot / "cmdline.txt").read_bytes(), conflicting)
            self.assertEqual((boot / "config.txt").read_bytes(), self.originals["config.txt"])
            self.assertFalse((boot / "hamda-before-usb").exists())


if __name__ == "__main__":
    unittest.main()
