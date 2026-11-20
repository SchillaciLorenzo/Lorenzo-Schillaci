"""Focused A-only tests. Every serial operation is fake."""
import contextlib
import hashlib
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
INLINE = (ROOT / "test_all_a_inline.txt").read_text()
SOURCE = INLINE.split("-c '\n", 1)[1].rsplit("'", 1)[0]
NAMESPACE = {"__name__": "all_a_fake"}
exec(compile(SOURCE, "all_a_inline", "exec"), NAMESPACE)
MAIN = NAMESPACE["main"]
ID_A = "ID HAMDA_USB 1 A 10:00:3b:cc:97:d8"
PORT_A = "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_10:00:3B:CC:97:D8-if00"


class FakeSerial:
    def __init__(self):
        self.time = 0.0
        self.dtr = self.rts = self.port = None
        self.closed = False
        self.writes = []
        self.times = []
        self.rx = bytearray()
        self.identity = ID_A
        self.stop_reply = "OK STOP"
        self.pulse_reply = "OK PULSE 15 250"
        self.pulse_sent = False
        self.interrupt_after = None
        self.pulse_reads = 0

    def factory(self, **kwargs):
        assert kwargs == dict(port=None, baudrate=115200, timeout=0.05,
                              write_timeout=1, exclusive=True)
        return self

    def now(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds

    def open(self):
        assert self.dtr is False and self.rts is False and self.port == PORT_A

    def reset_input_buffer(self):
        assert not self.writes
        self.rx.clear()

    def write(self, data):
        self.writes.append(data)
        self.times.append(self.time)
        if data == b"ID\n":
            reply = self.identity
        elif data == b"STOP\n":
            reply = self.stop_reply
        elif data == b"PULSE 15 250\n":
            self.pulse_sent = True
            reply = self.pulse_reply
        else:
            raise AssertionError("Wrong command: " + repr(data))
        if reply:
            self.rx.extend((reply + "\n").encode("ascii"))
        return len(data)

    def read(self, count):
        self.time += 0.01
        if self.pulse_sent and self.interrupt_after is not None:
            if self.pulse_reads == self.interrupt_after:
                self.interrupt_after = None
                raise KeyboardInterrupt()
            self.pulse_reads += 1
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def close(self):
        self.closed = True


class AllATests(unittest.TestCase):
    def setUp(self):
        self.serial = FakeSerial()
        self.answers = ["PROVA", ""]
        self.prompts = []
        self.output = io.StringIO()

    def ask(self, prompt):
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            self.assertEqual(self.serial.writes, [b"ID\n", b"STOP\n"])
            self.assertIn("SOLO batteria A", prompt)
            self.assertIn("quattro motori A", prompt)
        else:
            self.assertIn("Scollega batteria A", prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def invoke(self):
        with contextlib.redirect_stdout(self.output):
            MAIN(factory=self.serial.factory, ask=self.ask,
                 now=self.serial.now, sleep=self.serial.sleep)

    def aborted(self, exception=RuntimeError, pulse_count=0):
        with self.assertRaises(exception):
            self.invoke()
        self.assertEqual(self.serial.writes.count(b"PULSE 15 250\n"), pulse_count)
        self.assertNotIn("PROVA TUTTI A COMPLETATA", self.output.getvalue())
        self.assertTrue(self.serial.closed)

    def test_A_accepted_only_one_mask15_pulse_after_PROVA_and_cooldown(self):
        self.invoke()
        self.assertEqual(self.serial.writes, [b"ID\n", b"STOP\n", b"STOP\n",
                                              b"PULSE 15 250\n", b"STOP\n"])
        self.assertGreaterEqual(self.serial.times[3] - self.serial.times[2], 0.25)
        self.assertEqual(len(self.prompts), 2)
        self.assertTrue(self.serial.closed)
        self.assertIn("PROVA TUTTI A COMPLETATA", self.output.getvalue())

    def test_B_identity_rejected_before_battery_prompt(self):
        self.serial.identity = "ID HAMDA_USB 1 B 10:00:3b:cc:1c:78"
        self.aborted()
        self.assertEqual(self.prompts, [])

    def test_unknown_identity_rejected(self):
        self.serial.identity = "ID HAMDA_USB 1 UNKNOWN 10:00:3b:cc:97:d8"
        self.aborted()
        self.assertEqual(self.prompts, [])

    def test_initial_stop_failure_no_pulse(self):
        self.serial.stop_reply = "ERR GPIO"
        self.aborted()
        self.assertEqual(self.prompts, [])

    def test_empty_or_wrong_case_gate_no_pulse(self):
        for gate in ("", "prova"):
            with self.subTest(gate=gate):
                self.setUp()
                self.answers = [gate]
                self.aborted()

    def test_gate_keyboard_interrupt_no_pulse(self):
        self.answers = [KeyboardInterrupt()]
        self.aborted(KeyboardInterrupt)
        self.assertEqual(self.serial.writes[-1], b"STOP\n")

    def test_pending_partial_mask15_ack_is_drained_on_cleanup(self):
        self.serial.interrupt_after = 4
        self.aborted(KeyboardInterrupt, pulse_count=1)
        self.assertIn("STOP cleanup confermato", self.output.getvalue())
        self.assertNotIn("STOP NON CONFERMATO", self.output.getvalue())

    def test_pulse_ack_timeout_no_retry_cleanup_stop(self):
        self.serial.pulse_reply = ""
        self.aborted(pulse_count=1)
        self.assertIn("STOP cleanup confermato", self.output.getvalue())

    def test_frozen_B_template_unchanged_and_no_B_target_in_A(self):
        self.assertEqual(hashlib.sha256((ROOT / "test_all_b_inline.txt").read_bytes()).hexdigest(),
                         "0c05ef5e813e66db0743577865d82804ec46b49d7cb891d90c34329cb262a636")
        self.assertNotIn("1C:78", SOURCE)
        self.assertNotIn("1c:78", SOURCE)
        self.assertNotIn("batteria B", SOURCE)
        self.assertNotIn("PULSE 1 250", SOURCE)
        self.assertLess(len(INLINE.encode()), 4096)
        self.assertNotIn("'", SOURCE)


if __name__ == "__main__":
    unittest.main()
