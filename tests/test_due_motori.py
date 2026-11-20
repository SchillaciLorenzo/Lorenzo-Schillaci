import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
try:
    spec = importlib.util.spec_from_file_location(
        "hamda_due_motori", TOOLS / "hamda_due_motori.py"
    )
    pair = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pair)
finally:
    sys.path.pop(0)


class FakePairBus:
    def __init__(self):
        # Both channels start with a stale ON state.
        self.registers = {
            0x00: 0x01,
            0x01: 0x04,
            0x07: 0x10,
            0x09: 0x00,
            0x0B: 0x10,
            0x0D: 0x00,
        }
        self.pointer = 0
        self.activation_failure = None
        self.activation_failed = False
        self.drop_second_stop = False
        self.reconfigured_while_on = False

    def high(self, channel):
        return bool(self.registers.get(0x07 + 4 * channel, 0) & 0x10) and not bool(
            self.registers.get(0x09 + 4 * channel, 0) & 0x10
        )

    def levels(self):
        return self.high(0), self.high(1)

    def write(self, data):
        self.pointer = data[0]
        if len(data) == 2:
            register, value = data
            if register in (0x00, 0x01) and any(self.levels()):
                self.reconfigured_while_on = True
            if self.drop_second_stop and register == 0x0D and value == 0x10:
                return len(data)  # Acknowledge but fail to apply the stop.
            self.registers[register] = value
            if (
                self.activation_failure is not None
                and register == 0x09 + 4 * self.activation_failure
                and value == 0
                and not self.activation_failed
            ):
                self.activation_failed = True
                raise OSError("activation acknowledgement lost")
        return len(data)

    def read(self, length):
        return bytes((self.registers.get(self.pointer, 0),))


class PairTest(unittest.TestCase):
    def test_off_clears_both_stale_channels_before_reconfiguration(self):
        bus = FakePairBus()
        with patch.object(pair.time, "sleep"):
            pair.operate(bus, "off")
        self.assertEqual(bus.levels(), (False, False))
        self.assertFalse(bus.reconfigured_while_on)

    def test_each_selection_is_independent_and_bounded(self):
        for command, expected in (
            ("primo", (True, False)),
            ("secondo", (False, True)),
            ("insieme", (True, True)),
        ):
            with self.subTest(command=command):
                bus = FakePairBus()
                waits = []

                def sleep(seconds):
                    waits.append((seconds, bus.levels()))

                with patch.object(pair.time, "sleep", side_effect=sleep):
                    pair.operate(bus, command)
                self.assertEqual(waits, [(0.005, (False, False)), (0.25, expected)])
                self.assertEqual(bus.levels(), (False, False))

    def test_interrupt_stops_both(self):
        bus = FakePairBus()

        def sleep(seconds):
            if seconds == pair.PULSE_SECONDS:
                self.assertEqual(bus.levels(), (True, True))
                raise KeyboardInterrupt

        with patch.object(pair.time, "sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt):
                pair.operate(bus, "insieme")
        self.assertEqual(bus.levels(), (False, False))

    def test_ambiguous_failure_of_either_activation_stops_both(self):
        for channel in (0, 1):
            with self.subTest(channel=channel):
                bus = FakePairBus()
                bus.activation_failure = channel
                with patch.object(pair.time, "sleep"):
                    with self.assertRaisesRegex(OSError, "acknowledgement lost"):
                        pair.operate(bus, "insieme")
                self.assertTrue(bus.activation_failed)
                self.assertEqual(bus.levels(), (False, False))

    def test_stop_readback_checks_second_channel_too(self):
        bus = FakePairBus()

        def sleep(seconds):
            if seconds == pair.PULSE_SECONDS:
                bus.drop_second_stop = True

        with patch.object(pair.time, "sleep", side_effect=sleep):
            with self.assertRaisesRegex(OSError, "secondo motore non confermato"):
                pair.operate(bus, "secondo")
        self.assertEqual(bus.levels(), (False, True))

    def test_invalid_targets_never_activate_an_output(self):
        for targets in ((), (2,), (0, 2), (1, 1), ("0",)):
            with self.subTest(targets=targets):
                bus = FakePairBus()
                pca = pair.TwoMotorPCA(bus)
                with patch.object(pair.time, "sleep"):
                    pca.prepare()
                with self.assertRaises(ValueError):
                    pca.on_channels(targets)
                self.assertEqual(bus.levels(), (False, False))


if __name__ == "__main__":
    unittest.main()
