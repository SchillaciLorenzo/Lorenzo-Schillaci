import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "tools" / "hamda_primo_motore.py"
spec = importlib.util.spec_from_file_location("hamda_primo_motore", MODULE)
motor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motor)


class FakeBus:
    def __init__(self):
        # Simulate a stale ON command from an earlier program.
        self.registers = {0x00: 0x01, 0x01: 0x04, 0x07: 0x10, 0x09: 0x00}
        self.pointer = 0
        self.failed_after_start = False
        self.fail_once_after_start = False
        self.fail_stop = False
        self.clock_changed_while_on = False

    @property
    def high(self):
        return bool(self.registers.get(0x07, 0) & 0x10) and not bool(
            self.registers.get(0x09, 0) & 0x10
        )

    def write(self, data):
        self.pointer = data[0]
        if len(data) == 2:
            register, value = data
            if register in (0x00, 0x01) and self.high:
                self.clock_changed_while_on = True
            if self.fail_stop and register == 0x09 and value & 0x10:
                raise OSError("stop failed")
            self.registers[register] = value
            if (
                self.fail_once_after_start
                and register == 0x09
                and value == 0
                and not self.failed_after_start
            ):
                self.failed_after_start = True
                raise OSError("write completed but acknowledgement lost")
        return len(data)

    def read(self, length):
        return bytes((self.registers.get(self.pointer, 0),))


class MotorTest(unittest.TestCase):
    def test_off_clears_stale_output_before_reconfiguration(self):
        bus = FakeBus()
        with patch.object(motor.time, "sleep"):
            motor.operate(bus, "off")
        self.assertFalse(bus.high)
        self.assertFalse(bus.clock_changed_while_on)
        self.assertTrue(all(bus.registers[0x09 + 4 * ch] & 0x10 for ch in range(16)))

    def test_one_bounded_pulse_then_off(self):
        bus = FakeBus()
        waits = []

        def sleep(seconds):
            waits.append((seconds, bus.high))

        with patch.object(motor.time, "sleep", side_effect=sleep):
            motor.operate(bus, "pulse")
        self.assertEqual(waits, [(0.005, False), (0.25, True)])
        self.assertFalse(bus.high)

    def test_interruption_during_pulse_stops_output(self):
        bus = FakeBus()

        def sleep(seconds):
            if seconds == motor.PULSE_SECONDS:
                self.assertTrue(bus.high)
                raise KeyboardInterrupt

        with patch.object(motor.time, "sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt):
                motor.operate(bus, "pulse")
        self.assertFalse(bus.high)

    def test_ambiguous_start_failure_still_stops_output(self):
        bus = FakeBus()
        bus.fail_once_after_start = True
        with patch.object(motor.time, "sleep"):
            with self.assertRaisesRegex(OSError, "acknowledgement lost"):
                motor.operate(bus, "pulse")
        self.assertTrue(bus.failed_after_start)
        self.assertFalse(bus.high)

    def test_external_clock_is_rejected_after_forcing_off(self):
        bus = FakeBus()
        bus.registers[0x00] |= 0x40
        with self.assertRaisesRegex(OSError, "Clock esterno"):
            motor.operate(bus, "pulse")
        self.assertFalse(bus.high)

    def test_failed_stop_is_not_reported_as_success(self):
        bus = FakeBus()

        def sleep(seconds):
            if seconds == motor.PULSE_SECONDS:
                bus.fail_stop = True

        with patch.object(motor.time, "sleep", side_effect=sleep):
            with self.assertRaisesRegex(OSError, "stop failed"):
                motor.operate(bus, "pulse")
        self.assertTrue(bus.high)


if __name__ == "__main__":
    unittest.main()
