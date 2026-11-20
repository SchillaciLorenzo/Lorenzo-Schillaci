"""La configurazione deve essere valida prima di comandare qualsiasi uscita."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from hamda.config import load_config


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "hardware.json"


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "hardware.json"

    def load_modified(self, config):
        self.path.write_text(json.dumps(config), encoding="utf-8")
        return load_config(self.path)

    def test_example_identifies_all_sixteen_motors_and_channels(self):
        config = load_config(CONFIG_PATH)
        self.assertEqual(len(config.motors), 16)
        self.assertEqual(
            {motor.motor_id for motor in config.motors},
            {f"{foot}{number}" for foot in "LR" for number in range(1, 9)},
        )
        self.assertEqual({motor.channel for motor in config.motors}, set(range(16)))
        self.assertTrue(all(motor.position is None for motor in config.motors))

    def test_hardware_mode_is_rejected(self):
        self.example["mode"] = "hardware"
        with self.assertRaises(ValueError):
            self.load_modified(self.example)

    def test_missing_motor_is_rejected(self):
        self.example["motors"].pop()
        with self.assertRaises(ValueError):
            self.load_modified(self.example)

    def test_duplicate_logical_id_is_rejected(self):
        self.example["motors"][1]["motor_id"] = self.example["motors"][0]["motor_id"]
        with self.assertRaises(ValueError):
            self.load_modified(self.example)

    def test_unexpected_logical_id_is_rejected(self):
        self.example["motors"][0]["motor_id"] = "L9"
        with self.assertRaises(ValueError):
            self.load_modified(self.example)

    def test_duplicate_channel_is_rejected(self):
        self.example["motors"][1]["channel"] = self.example["motors"][0]["channel"]
        with self.assertRaises(ValueError):
            self.load_modified(self.example)

    def test_channels_must_be_integers_in_range(self):
        for invalid in (-1, 16, 1.5, True, "0", None):
            with self.subTest(channel=invalid):
                example = copy.deepcopy(self.example)
                example["motors"][0]["channel"] = invalid
                with self.assertRaises(ValueError):
                    self.load_modified(example)

    def test_intensity_limits_must_be_positive_finite_percentages(self):
        for invalid in (-1, 0, 101, True, "50", None, float("nan"), float("inf")):
            with self.subTest(limit=invalid):
                example = copy.deepcopy(self.example)
                example["motors"][0]["max_intensity"] = invalid
                with self.assertRaises(ValueError):
                    self.load_modified(example)

    def test_duration_limit_must_be_positive_and_finite(self):
        for invalid in (-1, 0, True, "1000", None, float("nan"), float("inf")):
            with self.subTest(duration=invalid):
                example = copy.deepcopy(self.example)
                example["max_duration_ms"] = invalid
                with self.assertRaises(ValueError):
                    self.load_modified(example)

    def test_mapping_and_anatomical_description_can_be_configured(self):
        motors = self.example["motors"]
        motors[0]["channel"], motors[-1]["channel"] = (
            motors[-1]["channel"], motors[0]["channel"]
        )
        motors[0]["position"] = "Descrizione definita dall'operatore"
        config = self.load_modified(self.example)
        self.assertEqual(config.motors[0].channel, 15)
        self.assertEqual(config.motors[0].position, motors[0]["position"])

    def test_malformed_json_is_rejected(self):
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(self.path)


if __name__ == "__main__":
    unittest.main()
