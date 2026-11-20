import contextlib
import fcntl
import importlib.util
import io
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "tools/hamda_banco.py"
SPEC = importlib.util.spec_from_file_location("hamda_banco", SOURCE)
banco = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(banco)


class Bus:
    def __init__(self):
        self.registers = {0: 1, 1: 4}
        for channel in (0, 1, 2):
            self.registers[0x07 + 4 * channel] = 0x10
            self.registers[0x09 + 4 * channel] = 0
        self.pointer = 0
        self.fail_activation = None
        self.activation_failed = False
        self.fail_stop_zero = False
        self.ignore_stop_one = False
        self.reconfigured_while_on = False
        self.writes = []

    def high(self, channel):
        return bool(self.registers.get(0x07 + 4 * channel, 0) & 0x10) and not bool(
            self.registers.get(0x09 + 4 * channel, 0) & 0x10
        )

    def levels(self):
        return tuple(self.high(channel) for channel in (0, 1, 2))

    def write(self, data):
        self.pointer = data[0]
        if len(data) == 2:
            register, value = data
            self.writes.append((register, value))
            if register in (0, 1) and any(self.levels()):
                self.reconfigured_while_on = True
            if self.fail_stop_zero and register == 0x09 and value == 0x10:
                raise OSError("stop write failed")
            if self.ignore_stop_one and register == 0x0D and value == 0x10:
                return len(data)
            self.registers[register] = value
            if (self.fail_activation is not None
                    and register == 0x09 + 4 * self.fail_activation and value == 0
                    and not self.activation_failed):
                self.activation_failed = True
                raise OSError("activation acknowledgement lost")
        return len(data)

    def read(self, length):
        return bytes((self.registers.get(self.pointer, 0),))


class BancoTest(unittest.TestCase):
    def test_off_clears_stale_outputs_before_reconfiguration(self):
        bus = Bus()
        with patch.object(banco.time, "sleep"):
            banco.operate(bus, "off")
        self.assertEqual(bus.levels(), (False, False, False))
        self.assertFalse(bus.reconfigured_while_on)

    def test_commands_select_only_the_expected_motors_and_finish_off(self):
        for command, expected in (("primo", (True, False, False)),
                                  ("secondo", (False, True, False)),
                                  ("insieme", (True, True, False))):
            with self.subTest(command=command):
                bus = Bus()
                waits = []

                def sleep(seconds):
                    waits.append((seconds, bus.levels()))

                with patch.object(banco.time, "sleep", side_effect=sleep):
                    banco.operate(bus, command)
                self.assertEqual(waits, [(0.005, (False, False, False)),
                                         (0.25, expected)])
                self.assertEqual(bus.levels(), (False, False, False))

    def test_interruption_stops_both_and_restores_signal_mask(self):
        bus = Bus()
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())

        def sleep(seconds):
            if seconds == banco.PULSE_SECONDS:
                raise KeyboardInterrupt

        with patch.object(banco.time, "sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt):
                banco.operate(bus, "insieme")
        self.assertEqual(bus.levels(), (False, False, False))
        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous_mask)

    def test_lost_ack_after_either_activation_stops_both(self):
        for channel in (0, 1):
            with self.subTest(channel=channel):
                bus = Bus()
                bus.fail_activation = channel
                with patch.object(banco.time, "sleep"):
                    with self.assertRaisesRegex(OSError, "acknowledgement lost"):
                        banco.operate(bus, "insieme")
                self.assertTrue(bus.activation_failed)
                self.assertEqual(bus.levels(), (False, False, False))

    def test_failure_to_stop_zero_does_not_skip_stop_of_one(self):
        bus = Bus()

        def sleep(seconds):
            if seconds == banco.PULSE_SECONDS:
                bus.fail_stop_zero = True
                bus.writes.clear()

        with patch.object(banco.time, "sleep", side_effect=sleep):
            with self.assertRaisesRegex(OSError, "Spegnimento non confermato"):
                banco.operate(bus, "insieme")
        self.assertEqual(bus.levels(), (True, False, False))
        self.assertIn((0x0D, 0x10), bus.writes)

    def test_acknowledged_but_ignored_stop_is_detected_by_readback(self):
        bus = Bus()

        def sleep(seconds):
            if seconds == banco.PULSE_SECONDS:
                bus.ignore_stop_one = True

        with patch.object(banco.time, "sleep", side_effect=sleep):
            with self.assertRaisesRegex(OSError, "verifica uscita 1"):
                banco.operate(bus, "secondo")
        self.assertEqual(bus.levels(), (False, True, False))

    def test_external_clock_is_rejected_after_forcing_off(self):
        bus = Bus()
        bus.registers[0] = 0x41
        with patch.object(banco.time, "sleep"):
            with self.assertRaisesRegex(OSError, "Clock esterno"):
                banco.operate(bus, "primo")
        self.assertEqual(bus.levels(), (False, False, False))

    def test_busy_lock_blocks_bus_access_and_restores_signal_handlers(self):
        handlers = {sig: signal.getsignal(sig) for sig in banco.STOP_SIGNALS}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with (path / banco.LOCK_NAME).open("a") as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(banco.Path, "home", return_value=path), \
                     patch.object(banco, "open", create=True) as bus_open, \
                     contextlib.redirect_stderr(io.StringIO()) as output:
                    self.assertEqual(banco.main(["primo"]), 1)
                    bus_open.assert_not_called()
                    self.assertIn("Scollega il powerbank", output.getvalue())
            self.assertEqual({sig: signal.getsignal(sig) for sig in banco.STOP_SIGNALS},
                             handlers)


if __name__ == "__main__":
    unittest.main()
