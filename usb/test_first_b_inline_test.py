"""Fakes only: no serial import, device, pulse, battery or subprocess."""
import ast
import contextlib
import io
import unittest
from pathlib import Path

INLINE = Path(__file__).with_name("test_first_b_inline.txt").read_text()
SOURCE = INLINE.split("-c '\n", 1)[1].rsplit("'", 1)[0]
NAMESPACE = {"__name__": "first_b_fake"}
exec(compile(SOURCE, "first_b_inline", "exec"), NAMESPACE)
MAIN = NAMESPACE["main"]
IDENTITY = "ID HAMDA_USB 1 B 10:00:3b:cc:1c:78"
PORT = "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_10:00:3B:CC:1C:78-if00"


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeSerial:
    def __init__(self, test, clock):
        self.test = test
        self.clock = clock
        self.port = self.dtr = self.rts = None
        self.is_open = False
        self.closed = False
        self.writes = []
        self.write_times = []
        self.rx = bytearray()
        self.identity = IDENTITY + "\n"
        self.stop_responses = []
        self.pulse_response = "OK PULSE 1 250\n"
        self.interrupt_pulse_after = None
        self.pulse_read_count = 0
        self.pulse_attempted = False
        self.short_pulse_write = False
        self.fail_cleanup_write = False
        self.clears = 0

    def factory(self, **options):
        self.test.assertEqual(options, dict(port=None, baudrate=115200, timeout=0.05,
                                            write_timeout=1, exclusive=True))
        return self

    def open(self):
        self.test.assertFalse(self.dtr)
        self.test.assertFalse(self.rts)
        self.test.assertEqual(self.port, PORT)
        self.is_open = True

    def reset_input_buffer(self):
        self.test.assertEqual(self.writes, [])
        self.clears += 1
        self.rx.clear()

    def write(self, data):
        self.test.assertTrue(self.is_open)
        self.writes.append(data)
        self.write_times.append(self.clock.now())
        if data == b"ID\n":
            response = self.identity
        elif data == b"STOP\n":
            if self.fail_cleanup_write and self.pulse_attempted:
                raise OSError("USB disconnected")
            response = self.stop_responses.pop(0) if self.stop_responses else "OK STOP\n"
        elif data == b"PULSE 1 250\n":
            self.pulse_attempted = True
            if self.short_pulse_write:
                return len(data) - 1
            response = self.pulse_response
        else:
            raise AssertionError("Unexpected command: " + repr(data))
        self.rx.extend(response.encode("ascii"))
        return len(data)

    def read(self, count):
        self.test.assertEqual(count, 1)
        self.clock.sleep(0.01)
        if self.pulse_attempted and self.interrupt_pulse_after is not None:
            if self.pulse_read_count == self.interrupt_pulse_after:
                self.interrupt_pulse_after = None
                raise KeyboardInterrupt()
            self.pulse_read_count += 1
        if not self.rx:
            return b""
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def close(self):
        self.closed = True
        self.is_open = False


class FirstBTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.serial = FakeSerial(self, self.clock)
        self.output = io.StringIO()
        self.answers = ["PROVA", ""]
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            self.assertEqual(self.serial.writes, [b"ID\n", b"STOP\n"])
            self.assertIn("SOLO batteria B", prompt)
            self.assertIn("DEVONO restare fermi", prompt)
            self.assertIn("scollega subito", prompt)
        else:
            self.assertEqual(self.serial.writes[-1], b"STOP\n")
            self.assertIn("Scollega batteria B", prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def invoke(self):
        with contextlib.redirect_stdout(self.output):
            MAIN(factory=self.serial.factory, ask=self.ask,
                 now=self.clock.now, sleep=self.clock.sleep)

    def assert_no_pulse(self):
        self.assertFalse(any(data.startswith(b"PULSE") for data in self.serial.writes))
        self.assertTrue(self.serial.closed)
        self.assertNotIn("PROVA B COMPLETATA", self.output.getvalue())

    def test_inline_plain_python_c_is_bounded(self):
        self.assertLess(len(INLINE.encode()), 4096)
        self.assertNotIn("'", SOURCE)
        ast.parse(SOURCE)
        self.assertNotIn("PULSE 2", SOURCE)
        self.assertNotIn("PULSE 15", SOURCE)
        self.assertNotIn("reset_output_buffer", SOURCE)

    def test_normal_one_pulse_only_after_manual_gate_and_cooldown(self):
        self.invoke()
        self.assertEqual(self.serial.writes, [b"ID\n", b"STOP\n", b"STOP\n",
                                              b"PULSE 1 250\n", b"STOP\n"])
        self.assertGreaterEqual(self.serial.write_times[3] - self.serial.write_times[2], 0.25)
        self.assertEqual(len(self.prompts), 2)
        self.assertEqual(self.serial.clears, 1)
        self.assertTrue(self.serial.closed)
        self.assertIn("PROVA B COMPLETATA", self.output.getvalue())

    def test_bad_identity_no_activation_or_battery_prompt(self):
        self.serial.identity = "ID HAMDA_USB 1 A 10:00:3b:cc:97:d8\n"
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.prompts, [])
        self.assertEqual(self.serial.writes, [b"ID\n"])
        self.assert_no_pulse()

    def test_id_timeout_no_activation(self):
        self.serial.identity = ""
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.prompts, [])
        self.assert_no_pulse()

    def test_wrong_initial_stop_no_activation(self):
        self.serial.stop_responses = ["ERR GPIO\n"]
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.prompts, [])
        self.assertEqual(self.serial.writes[-1], b"STOP\n")
        self.assert_no_pulse()

    def test_initial_stop_timeout_no_activation(self):
        self.serial.stop_responses = [""]
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.prompts, [])
        self.assert_no_pulse()

    def test_enter_alone_cannot_trigger_pulse(self):
        self.answers = [""]
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assert_no_pulse()

    def test_wrong_confirmation_cannot_trigger_pulse(self):
        self.answers = ["prova"]
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assert_no_pulse()

    def test_eof_during_manual_gate_stops_and_closes(self):
        self.answers = [EOFError()]
        with self.assertRaises(EOFError):
            self.invoke()
        self.assert_no_pulse()
        self.assertEqual(self.serial.writes[-1], b"STOP\n")

    def test_keyboard_interrupt_during_manual_gate_stops_and_closes(self):
        self.answers = [KeyboardInterrupt()]
        with self.assertRaises(KeyboardInterrupt):
            self.invoke()
        self.assert_no_pulse()

    def test_second_stop_failure_prevents_pulse(self):
        self.serial.stop_responses = ["OK STOP\n", "ERR GPIO\n"]
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assert_no_pulse()

    def test_interrupted_partial_pulse_ack_is_preserved_for_cleanup(self):
        self.serial.interrupt_pulse_after = 4
        with self.assertRaises(KeyboardInterrupt):
            self.invoke()
        self.assertEqual(self.serial.writes.count(b"PULSE 1 250\n"), 1)
        self.assertEqual(self.serial.writes[-1], b"STOP\n")
        self.assertIn("STOP cleanup confermato", self.output.getvalue())
        self.assertNotIn("STOP NON CONFERMATO", self.output.getvalue())
        self.assertNotIn("PROVA B COMPLETATA", self.output.getvalue())
        self.assertTrue(self.serial.closed)

    def test_pulse_timeout_has_no_retry_and_cleanup_stop_is_confirmed(self):
        self.serial.pulse_response = ""
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.serial.writes.count(b"PULSE 1 250\n"), 1)
        self.assertIn("STOP cleanup confermato", self.output.getvalue())
        self.assertNotIn("PROVA B COMPLETATA", self.output.getvalue())

    def test_short_pulse_write_aborts_without_retry(self):
        self.serial.short_pulse_write = True
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.serial.writes.count(b"PULSE 1 250\n"), 1)
        self.assertTrue(self.serial.closed)
        self.assertNotIn("PROVA B COMPLETATA", self.output.getvalue())

    def test_cleanup_failure_never_claims_stop_or_success(self):
        self.serial.interrupt_pulse_after = 4
        self.serial.fail_cleanup_write = True
        with self.assertRaises(KeyboardInterrupt):
            self.invoke()
        self.assertIn("STOP NON CONFERMATO", self.output.getvalue())
        self.assertNotIn("PROVA B COMPLETATA", self.output.getvalue())
        self.assertTrue(self.serial.closed)

    def test_eof_at_battery_disconnection_prompt_repeats_stop_only(self):
        self.answers = ["PROVA", EOFError()]
        with self.assertRaises(EOFError):
            self.invoke()
        self.assertEqual(self.serial.writes.count(b"PULSE 1 250\n"), 1)
        self.assertEqual(self.serial.writes[-1], b"STOP\n")
        self.assertTrue(self.serial.closed)
        self.assertNotIn("PROVA B COMPLETATA", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
