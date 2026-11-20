"""Focused fakes for B2/B3/B4. No serial import, hardware or subprocess."""
import contextlib
import io
import unittest
from pathlib import Path

INLINE = Path(__file__).with_name("test_remaining_b_inline.txt").read_text()
SOURCE = INLINE.split("-c '\n", 1)[1].rsplit("'", 1)[0]
NAMESPACE = {"__name__": "remaining_b_fake"}
exec(compile(SOURCE, "remaining_b_inline", "exec"), NAMESPACE)
MAIN = NAMESPACE["main"]
IDENTITY = "ID HAMDA_USB 1 B 10:00:3b:cc:1c:78"


class FakeSerial:
    def __init__(self):
        self.time = 0.0
        self.port = self.dtr = self.rts = None
        self.closed = False
        self.writes = []
        self.times = []
        self.rx = bytearray()
        self.identity = IDENTITY
        self.interrupt_mask = None
        self.current_mask = None
        self.pulse_reads = 0
        self.bad_ack_mask = None
        self.fail_stop_after_mask = None

    def now(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds

    def factory(self, **options):
        assert options == dict(port=None, baudrate=115200, timeout=0.05,
                               write_timeout=1, exclusive=True)
        return self

    def open(self):
        assert self.dtr is False and self.rts is False
        assert self.port.endswith("10:00:3B:CC:1C:78-if00")

    def reset_input_buffer(self):
        assert not self.writes
        self.rx.clear()

    def write(self, data):
        self.writes.append(data)
        self.times.append(self.time)
        if data == b"ID\n":
            response = self.identity
        elif data == b"STOP\n":
            response = "ERR GPIO" if self.current_mask == self.fail_stop_after_mask and self.current_mask is not None else "OK STOP"
        else:
            assert data in (b"PULSE 2 250\n", b"PULSE 4 250\n", b"PULSE 8 250\n")
            self.current_mask = int(data.split()[1])
            self.pulse_reads = 0
            response = "OK " + data.decode().strip()
            if self.current_mask == self.bad_ack_mask:
                response = "ERR INPUT"
        self.rx.extend((response + "\n").encode("ascii"))
        return len(data)

    def read(self, count):
        self.time += 0.01
        if self.current_mask == self.interrupt_mask and self.current_mask is not None:
            if self.pulse_reads == 3:
                self.interrupt_mask = None
                raise KeyboardInterrupt()
            self.pulse_reads += 1
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def close(self):
        self.closed = True


class RemainingBTests(unittest.TestCase):
    def setUp(self):
        self.serial = FakeSerial()
        self.output = io.StringIO()
        self.answers = ["", "PROVA", "SI", "PROVA", "SI", "PROVA", "SI", ""]
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            self.assertEqual(self.serial.writes, [b"ID\n", b"STOP\n"])
            self.assertIn("SOLO batteria B", prompt)
            self.assertIn("DEVONO restare fermi", prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def invoke(self):
        with contextlib.redirect_stdout(self.output):
            MAIN(factory=self.serial.factory, ask=self.ask,
                 now=self.serial.now, sleep=self.serial.sleep)

    def pulses(self):
        return [data for data in self.serial.writes if data.startswith(b"PULSE")]

    def assert_aborted(self):
        self.assertTrue(self.serial.closed)
        self.assertNotIn("PROVE B2/B3/B4 COMPLETATE", self.output.getvalue())

    def test_normal_exact_order_masks_gates_observations_and_cooldown(self):
        self.invoke()
        self.assertLess(len(INLINE.encode()), 4096)
        self.assertNotIn("'", SOURCE)
        self.assertEqual(self.pulses(), [b"PULSE 2 250\n", b"PULSE 4 250\n", b"PULSE 8 250\n"])
        self.assertEqual(len(self.prompts), 8)
        for mask, color, gate, observation in ((2, "verde scuro", 1, 2), (4, "giallo", 3, 4), (8, "blu", 5, 6)):
            self.assertIn(color, self.prompts[gate])
            self.assertIn("PROVA", self.prompts[gate])
            self.assertIn(color, self.prompts[observation])
            self.assertIn("SOLO", self.prompts[observation])
            self.assertIn("fermato da solo", self.prompts[observation])
            index = self.serial.writes.index(("PULSE " + str(mask) + " 250\n").encode())
            self.assertEqual(self.serial.writes[index - 1], b"STOP\n")
            self.assertGreaterEqual(self.serial.times[index] - self.serial.times[index - 1], 0.25)
            self.assertEqual(self.serial.writes[index + 1], b"STOP\n")
        self.assertIn("Scollega batteria B", self.prompts[-1])
        self.assertIn("PROVE B2/B3/B4 COMPLETATE", self.output.getvalue())
        self.assertTrue(self.serial.closed)

    def test_bad_identity_prevents_battery_gate_and_any_pulse(self):
        self.serial.identity = "ID HAMDA_USB 1 A 10:00:3b:cc:97:d8"
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.prompts, [])
        self.assertEqual(self.pulses(), [])
        self.assert_aborted()

    def test_battery_gate_refusal_no_pulse(self):
        self.answers = ["NO"]
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.pulses(), [])
        self.assert_aborted()

    def test_each_prova_gate_is_exact_and_no_later_pulse(self):
        for gate, expected in ((1, []), (3, [2]), (5, [2, 4])):
            with self.subTest(gate=gate):
                self.setUp()
                self.answers[gate] = ""
                with self.assertRaises(RuntimeError):
                    self.invoke()
                self.assertEqual([int(data.split()[1]) for data in self.pulses()], expected)
                self.assert_aborted()

    def test_each_si_required_before_advancing(self):
        for observation, expected in ((2, [2]), (4, [2, 4]), (6, [2, 4, 8])):
            with self.subTest(observation=observation):
                self.setUp()
                self.answers[observation] = "NO"
                with self.assertRaises(RuntimeError):
                    self.invoke()
                self.assertEqual([int(data.split()[1]) for data in self.pulses()], expected)
                self.assert_aborted()

    def test_dynamic_partial_pending_ack_cleanup_for_every_mask(self):
        for mask, expected in ((2, [2]), (4, [2, 4]), (8, [2, 4, 8])):
            with self.subTest(mask=mask):
                self.setUp()
                self.serial.interrupt_mask = mask
                with self.assertRaises(KeyboardInterrupt):
                    self.invoke()
                self.assertEqual([int(data.split()[1]) for data in self.pulses()], expected)
                self.assertEqual(self.serial.writes[-1], b"STOP\n")
                self.assertIn("STOP cleanup confermato", self.output.getvalue())
                self.assertNotIn("STOP NON CONFERMATO", self.output.getvalue())
                self.assert_aborted()

    def test_bad_ack_on_second_motor_aborts_without_mask8(self):
        self.serial.bad_ack_mask = 4
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.pulses(), [b"PULSE 2 250\n", b"PULSE 4 250\n"])
        self.assert_aborted()

    def test_stop_failure_aborts_without_later_masks(self):
        self.serial.fail_stop_after_mask = 2
        with self.assertRaises(RuntimeError):
            self.invoke()
        self.assertEqual(self.pulses(), [b"PULSE 2 250\n"])
        self.assertIn("STOP NON CONFERMATO", self.output.getvalue())
        self.assert_aborted()

    def test_keyboard_interrupt_observation_does_not_advance(self):
        self.answers[2] = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.invoke()
        self.assertEqual(self.pulses(), [b"PULSE 2 250\n"])
        self.assertEqual(self.serial.writes[-1], b"STOP\n")
        self.assert_aborted()


if __name__ == "__main__":
    unittest.main()
