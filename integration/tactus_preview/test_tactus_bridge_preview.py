"""Contratti offline della preview TACTUS: nessun hardware o broker necessario."""

import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("tactus_bridge_preview.py")
SPEC = importlib.util.spec_from_file_location("tactus_bridge_preview", MODULE_PATH)
bridge = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bridge
SPEC.loader.exec_module(bridge)


def mixed_config():
    """Esempio indipendente dal modulo sotto test."""
    return {
        "local_units": {"1": {"front": 0, "right": 1, "back": 2, "left": 3}},
        "remote_units": {
            "2": {
                "topic_prefix": "hap_02",
                "pins": {"front": 0, "right": 1, "back": 2, "left": 3},
            }
        },
    }


class PlanTests(unittest.TestCase):
    def test_full_mixed_frame_produces_exact_local_and_mqtt_commands(self):
        frame = {
            "1": {"front": True, "right": False, "back": " TRUE ", "left": " false "},
            "2": {"front": "False", "right": "true", "back": False, "left": True},
        }
        self.assertEqual(
            bridge.build_plan(frame, mixed_config()),
            {
                "local": {0: 255, 1: 0, 2: 255, 3: 0},
                "mqtt": [
                    {"topic": "hap_02/pin/0", "payload": "0"},
                    {"topic": "hap_02/pin/1", "payload": "255"},
                    {"topic": "hap_02/pin/2", "payload": "0"},
                    {"topic": "hap_02/pin/3", "payload": "255"},
                ],
            },
        )

    def test_false_string_does_not_become_truthy(self):
        result = bridge.build_plan({"1": {"front": " false "}}, mixed_config())
        self.assertEqual(result["local"], {0: 0, 1: 0, 2: 0, 3: 0})

    def test_missing_positions_are_off_full_state(self):
        result = bridge.build_plan({"1": {"front": True}}, mixed_config())
        self.assertEqual(result["local"], {0: 255, 1: 0, 2: 0, 3: 0})
        self.assertEqual([command["payload"] for command in result["mqtt"]], ["0"] * 4)

    def test_missing_units_and_valid_unknown_units_produce_all_off(self):
        for frame in ({}, {"99": {"front": True, "left": "true"}}):
            with self.subTest(frame=frame):
                self.assertEqual(
                    bridge.build_plan(frame, mixed_config()),
                    {
                        "local": {0: 0, 1: 0, 2: 0, 3: 0},
                        "mqtt": [
                            {"topic": "hap_02/pin/0", "payload": "0"},
                            {"topic": "hap_02/pin/1", "payload": "0"},
                            {"topic": "hap_02/pin/2", "payload": "0"},
                            {"topic": "hap_02/pin/3", "payload": "0"},
                        ],
                    },
                )

    def test_position_subset_targets_only_explicitly_configured_channels(self):
        config = {"local_units": {"1": {"left": 3}}, "remote_units": {}}
        self.assertEqual(
            bridge.build_plan({"1": {"front": True, "left": True}}, config),
            {"local": {3: 255}, "mqtt": []},
        )

    def test_unit_one_exceptional_remote_pins_follow_explicit_mapping(self):
        config = {
            "local_units": {},
            "remote_units": {
                "1": {
                    "topic_prefix": "hap_01",
                    "pins": {"front": 0, "right": 1, "back": 3, "left": 4},
                }
            },
        }
        self.assertEqual(
            bridge.build_plan({"1": {"front": True, "back": True}}, config),
            {
                "local": {},
                "mqtt": [
                    {"topic": "hap_01/pin/0", "payload": "255"},
                    {"topic": "hap_01/pin/1", "payload": "0"},
                    {"topic": "hap_01/pin/3", "payload": "255"},
                    {"topic": "hap_01/pin/4", "payload": "0"},
                ],
            },
        )

    def test_unit_one_does_not_implicitly_replace_explicit_pins(self):
        config = mixed_config()
        config["local_units"] = {}
        config["remote_units"] = {
            "1": {"topic_prefix": "custom", "pins": {"back": 2, "left": 3}}
        }
        self.assertEqual(
            bridge.build_plan({"1": {"back": True, "left": True}}, config)["mqtt"],
            [
                {"topic": "custom/pin/2", "payload": "255"},
                {"topic": "custom/pin/3", "payload": "255"},
            ],
        )

    def test_one_unit_can_mirror_to_local_and_remote_routes(self):
        config = mixed_config()
        config["remote_units"] = {
            "1": {"topic_prefix": "mirror", "pins": {"front": 15}}
        }
        result = bridge.build_plan({"1": {"front": True}}, config)
        self.assertEqual(result["local"], {0: 255, 1: 0, 2: 0, 3: 0})
        self.assertEqual(result["mqtt"], [{"topic": "mirror/pin/15", "payload": "255"}])

    def test_unit_ids_are_normalized_in_config_and_frame(self):
        config = {"local_units": {"001": {"front": 2}}, "remote_units": {}}
        for unit_id in ("1", "01", "001"):
            with self.subTest(unit_id=unit_id):
                self.assertEqual(
                    bridge.build_plan({unit_id: {"front": True}}, config),
                    {"local": {2: 255}, "mqtt": []},
                )

    def test_command_order_does_not_depend_on_input_dictionary_order(self):
        config = {
            "local_units": {},
            "remote_units": {
                "10": {"topic_prefix": "ten", "pins": {"left": 9, "front": 6}},
                "2": {"topic_prefix": "two", "pins": {"left": 4, "back": 3, "right": 1, "front": 0}},
            },
        }
        result = bridge.build_plan({}, config)
        self.assertEqual(
            [command["topic"] for command in result["mqtt"]],
            ["two/pin/0", "two/pin/1", "two/pin/3", "two/pin/4", "ten/pin/6", "ten/pin/9"],
        )

    def test_inputs_are_not_modified(self):
        config = mixed_config()
        frame = {"01": {"front": " TrUe "}, "2": {"right": False}}
        original_config = copy.deepcopy(config)
        original_frame = copy.deepcopy(frame)
        bridge.build_plan(frame, config)
        self.assertEqual(config, original_config)
        self.assertEqual(frame, original_frame)

    def test_planning_does_not_require_network_or_file_writes(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), patch(
            "builtins.open", side_effect=AssertionError("file access forbidden")
        ):
            result = bridge.build_plan({"1": {"front": True}}, mixed_config())
        self.assertEqual(result["local"][0], 255)


class FrameValidationTests(unittest.TestCase):
    def assert_frame_error(self, frame):
        with self.assertRaises(bridge.FrameError):
            bridge.build_plan(frame, mixed_config())

    def test_parse_valid_json_then_build_plan(self):
        frame = bridge.parse_frame('{"1":{"front":"TRUE","left":false}}')
        self.assertEqual(bridge.build_plan(frame, mixed_config())["local"], {0: 255, 1: 0, 2: 0, 3: 0})

    def test_duplicate_json_unit_keys_are_rejected(self):
        with self.assertRaises(bridge.FrameError):
            bridge.parse_frame('{"1":{"front":true},"1":{"front":false}}')

    def test_duplicate_json_position_keys_are_rejected(self):
        with self.assertRaises(bridge.FrameError):
            bridge.parse_frame('{"1":{"front":true,"front":false}}')

    def test_duplicate_normalized_unit_aliases_are_rejected(self):
        self.assert_frame_error({"1": {"front": True}, "01": {"front": False}})

    def test_root_and_unit_states_must_be_objects(self):
        for frame in (None, [], "text", True, 1, {"1": None}, {"1": []}, {"1": True}):
            with self.subTest(frame=frame):
                self.assert_frame_error(frame)

    def test_boolean_values_and_explicit_boolean_strings_only(self):
        for value in (0, 1, -1, 0.0, 255, None, [], {}, "yes", "on", "1", "", "truth"):
            with self.subTest(value=value):
                self.assert_frame_error({"1": {"front": value}})

    def test_invalid_values_are_rejected_even_for_unknown_units(self):
        for state in ({"front": 1}, {"front": None}, {"front": {}}, {"front": "yes"}):
            with self.subTest(state=state):
                self.assert_frame_error({"999": state})

    def test_unknown_or_malformed_positions_are_rejected_even_for_unknown_units(self):
        for unit_id in ("1", "999"):
            for position in ("up", "Front", " front ", "", 1):
                with self.subTest(unit_id=unit_id, position=position):
                    self.assert_frame_error({unit_id: {position: True}})

    def test_unit_ids_must_be_positive_ascii_numeric_strings(self):
        for unit_id in ("0", "000", "-1", "1.0", "unit1", "", "١", 1, True):
            with self.subTest(unit_id=unit_id):
                self.assert_frame_error({unit_id: {"front": True}})

    def test_invalid_json_is_rejected(self):
        for text in ("", "{", '{"1": {"front": true,}}', '{"1": {"front": NaN}}'):
            with self.subTest(text=text):
                with self.assertRaises(bridge.FrameError):
                    bridge.parse_frame(text)

    def test_invalid_whole_frame_cannot_return_partial_commands(self):
        frame = {"1": {"front": True}, "2": {"right": "invalid"}}
        original = copy.deepcopy(frame)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), patch(
            "builtins.open", side_effect=AssertionError("file access forbidden")
        ):
            self.assert_frame_error(frame)
        self.assertEqual(frame, original)


class ConfigurationValidationTests(unittest.TestCase):
    def assert_config_error(self, config):
        with self.assertRaises(bridge.FrameError):
            bridge.validate_config(config)

    def test_normalization_is_canonical_and_preserves_input(self):
        config = {"local_units": {"001": {"front": 2}}, "remote_units": {}}
        original = copy.deepcopy(config)
        result = bridge.validate_config(config)
        self.assertEqual(result, {"local_units": {"1": {"front": 2}}, "remote_units": {}})
        self.assertEqual(config, original)

    def test_empty_routes_are_allowed(self):
        self.assertEqual(
            bridge.build_plan({}, {"local_units": {}, "remote_units": {}}),
            {"local": {}, "mqtt": []},
        )

    def test_duplicate_local_channels_across_units_are_rejected(self):
        self.assert_config_error({"local_units": {"1": {"front": 0}, "2": {"right": 0}}, "remote_units": {}})

    def test_duplicate_local_channels_within_unit_are_rejected(self):
        self.assert_config_error({"local_units": {"1": {"front": 0, "right": 0}}, "remote_units": {}})

    def test_invalid_local_channels_are_rejected(self):
        for channel in (-1, 4, True, 1.0, "1", None):
            with self.subTest(channel=channel):
                self.assert_config_error({"local_units": {"1": {"front": channel}}, "remote_units": {}})

    def test_remote_pin_type_range_and_uniqueness_are_validated(self):
        for pins in ({"front": True}, {"front": -1}, {"front": 256}, {"front": 1.0}, {"front": "1"}, {"front": None}, {"front": 0, "back": 0}):
            with self.subTest(pins=pins):
                self.assert_config_error({"local_units": {}, "remote_units": {"2": {"topic_prefix": "hap_02", "pins": pins}}})

    def test_remote_pin_endpoints_are_accepted(self):
        config = {"local_units": {}, "remote_units": {"2": {"topic_prefix": "hap_02", "pins": {"front": 0, "back": 255}}}}
        self.assertEqual(
            bridge.build_plan({"2": {"back": True}}, config)["mqtt"],
            [{"topic": "hap_02/pin/0", "payload": "0"}, {"topic": "hap_02/pin/255", "payload": "255"}],
        )

    def test_mqtt_prefix_must_be_explicit_and_single_level(self):
        for prefix in ("", "hap/#", "hap+", "#", "+", "hap/02", "hap\x00", "has space", "é", None, 2):
            with self.subTest(prefix=prefix):
                self.assert_config_error({"local_units": {}, "remote_units": {"2": {"topic_prefix": prefix, "pins": {"front": 0}}}})
        self.assert_config_error({"local_units": {}, "remote_units": {"2": {"pins": {"front": 0}}}})

    def test_duplicate_final_mqtt_topics_across_units_are_rejected(self):
        config = {
            "local_units": {},
            "remote_units": {
                "2": {"topic_prefix": "shared", "pins": {"front": 0}},
                "3": {"topic_prefix": "shared", "pins": {"back": 0}},
            },
        }
        self.assert_config_error(config)

    def test_shared_prefix_is_valid_when_final_topics_are_distinct(self):
        config = {
            "local_units": {},
            "remote_units": {
                "2": {"topic_prefix": "shared", "pins": {"front": 0}},
                "3": {"topic_prefix": "shared", "pins": {"back": 1}},
            },
        }
        self.assertEqual(len(bridge.build_plan({}, config)["mqtt"]), 2)

    def test_duplicate_config_unit_aliases_are_rejected(self):
        self.assert_config_error({"local_units": {"1": {"front": 0}, "01": {"back": 1}}, "remote_units": {}})
        self.assert_config_error({"local_units": {}, "remote_units": {"2": {"topic_prefix": "a", "pins": {"front": 0}}, "02": {"topic_prefix": "b", "pins": {"back": 1}}}})

    def test_invalid_config_shapes_and_positions_are_rejected(self):
        for config in (
            None,
            [],
            {},
            {"local_units": [], "remote_units": {}},
            {"local_units": {}, "remote_units": []},
            {"local_units": {"1": []}, "remote_units": {}},
            {"local_units": {"1": {"up": 0}}, "remote_units": {}},
            {"local_units": {}, "remote_units": {"2": {"topic_prefix": "ok", "pins": {"up": 0}}}},
        ):
            with self.subTest(config=config):
                self.assert_config_error(config)


class OfflineCliTests(unittest.TestCase):
    def test_demo_runs_with_standard_library_only_and_no_site_packages(self):
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(MODULE_PATH), "--demo"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), "La demo deve mostrare il piano offline")
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
