import contextlib
import fcntl
import importlib.util
import io
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "tools/hamda_quattro_motori.py"
SPEC = importlib.util.spec_from_file_location("hamda_quattro_motori", SOURCE)
banco = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(banco)


class Bus:
    def __init__(self):
        self.registers = {0: 1, 1: 4}
        for channel in range(16):
            self.registers[0x07 + 4 * channel] = 0x10
            self.registers[0x09 + 4 * channel] = 0
        self.pointer = 0
        self.fail_activation = None
        self.activation_failed = False
        self.fail_stops = set()
        self.ignore_stops = set()
        self.reconfigured_while_on = False
        self.writes = []

    def levels(self):
        return tuple(
            bool(self.registers[0x07 + 4 * channel] & 0x10)
            and not bool(self.registers[0x09 + 4 * channel] & 0x10)
            for channel in range(16)
        )

    def write(self, data):
        self.pointer = data[0]
        if len(data) == 2:
            register, value = data
            self.writes.append((register, value))
            if register in (0, 1) and any(self.levels()):
                self.reconfigured_while_on = True
            if value == 0x10:
                if any(register == 0x09 + 4 * ch for ch in self.fail_stops):
                    raise OSError("stop write failed")
                if any(register == 0x09 + 4 * ch for ch in self.ignore_stops):
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


class QuattroMotoriTest(unittest.TestCase):
    def test_off_clears_all_stale_outputs_before_reconfiguration(self):
        bus = Bus()
        with patch.object(banco.time, "sleep"):
            banco.operate(bus, "off")
        self.assertEqual(bus.levels(), (False,) * 16)
        self.assertFalse(bus.reconfigured_while_on)

    def test_each_motor_and_combination_selects_only_expected_outputs(self):
        expected_commands = {
            "primo": (0,), "secondo": (1,), "terzo": (2,), "quarto": (3,),
            "insieme": (0, 1), "coppia2": (2, 3), "tutti": (0, 1, 2, 3),
        }
        for command, active in expected_commands.items():
            with self.subTest(command=command):
                bus = Bus()
                observations = []

                def sleep(seconds):
                    observations.append((seconds, bus.levels()))

                with patch.object(banco.time, "sleep", side_effect=sleep):
                    banco.operate(bus, command)
                expected_levels = tuple(ch in active for ch in range(16))
                self.assertEqual(observations, [
                    (0.005, (False,) * 16), (0.25, expected_levels),
                ])
                self.assertEqual(bus.levels(), (False,) * 16)

    def test_interruption_stops_all_four_and_restores_signal_mask(self):
        bus = Bus()
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())

        def sleep(seconds):
            if seconds == banco.PULSE_SECONDS:
                raise KeyboardInterrupt

        with patch.object(banco.time, "sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt):
                banco.operate(bus, "tutti")
        self.assertEqual(bus.levels(), (False,) * 16)
        self.assertEqual(signal.pthread_sigmask(signal.SIG_BLOCK, set()), previous_mask)

    def test_lost_ack_after_any_activation_stops_every_output(self):
        for channel in range(4):
            with self.subTest(channel=channel):
                bus = Bus()
                bus.fail_activation = channel
                with patch.object(banco.time, "sleep"):
                    with self.assertRaisesRegex(OSError, "acknowledgement lost"):
                        banco.operate(bus, "tutti")
                self.assertTrue(bus.activation_failed)
                self.assertEqual(bus.levels(), (False,) * 16)

    def test_any_stop_failure_still_attempts_every_other_stop(self):
        for failed in range(4):
            with self.subTest(channel=failed):
                bus = Bus()

                def sleep(seconds):
                    if seconds == banco.PULSE_SECONDS:
                        bus.fail_stops.add(failed)
                        bus.writes.clear()

                with patch.object(banco.time, "sleep", side_effect=sleep):
                    with self.assertRaisesRegex(OSError, "Spegnimento non confermato"):
                        banco.operate(bus, "tutti")
                self.assertEqual(bus.levels(), tuple(ch == failed for ch in range(16)))
                for channel in range(16):
                    self.assertIn((0x09 + 4 * channel, 0x10), bus.writes)

    def test_ignored_stop_is_detected_on_each_of_four_controlled_outputs(self):
        for ignored in range(4):
            with self.subTest(channel=ignored):
                bus = Bus()

                def sleep(seconds):
                    if seconds == banco.PULSE_SECONDS:
                        bus.ignore_stops.add(ignored)

                with patch.object(banco.time, "sleep", side_effect=sleep):
                    with self.assertRaisesRegex(OSError, "verifica uscita " + str(ignored)):
                        banco.operate(bus, "tutti")
                self.assertEqual(bus.levels(), tuple(ch == ignored for ch in range(16)))

    def test_external_clock_refusal_leaves_every_output_off(self):
        bus = Bus()
        bus.registers[0] = 0x41
        with patch.object(banco.time, "sleep"):
            with self.assertRaisesRegex(OSError, "Clock esterno"):
                banco.operate(bus, "terzo")
        self.assertEqual(bus.levels(), (False,) * 16)

    def test_invalid_selection_cannot_enable_an_output(self):
        for selection in ((), (4,), (2, 2), (0, 16)):
            with self.subTest(selection=selection):
                bus = Bus()
                pca = banco.PCA9685(bus)
                pca.off()
                bus.writes.clear()
                with self.assertRaises(ValueError):
                    pca.activate(selection)
                self.assertEqual(bus.writes, [])
                self.assertEqual(bus.levels(), (False,) * 16)

    def test_shared_lock_prevents_concurrent_controller_bus_access(self):
        handlers = {sig: signal.getsignal(sig) for sig in banco.STOP_SIGNALS}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with (path / ".hamda-pca40.lock").open("a") as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(banco.Path, "home", return_value=path), \
                     patch.object(banco, "open", create=True) as bus_open, \
                     contextlib.redirect_stderr(io.StringIO()) as output:
                    self.assertEqual(banco.main(["terzo"]), 1)
                    bus_open.assert_not_called()
                    self.assertIn("Scollega il powerbank", output.getvalue())
            self.assertEqual({sig: signal.getsignal(sig) for sig in banco.STOP_SIGNALS},
                             handlers)


if __name__ == "__main__":
    unittest.main()
