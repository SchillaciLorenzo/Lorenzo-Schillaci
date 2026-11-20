"""Dual-node fakes only; never imports serial or opens hardware."""
import contextlib
import io
import unittest
from pathlib import Path

INLINE = Path(__file__).with_name("test_both_inline.txt").read_text()
SOURCE = INLINE.split("-c '\n", 1)[1].rsplit("'", 1)[0]
NAMESPACE = {"__name__": "both_fake"}
exec(compile(SOURCE, "both_inline", "exec"), NAMESPACE)
MAIN = NAMESPACE["main"]
MACS = {"A": "10:00:3b:cc:97:d8", "B": "10:00:3b:cc:1c:78"}


class FakeHub:
    def __init__(self):
        self.time = 0.0
        self.events = []
        self.ports = []
        self.bad_id = None
        self.open_failure = None
        self.pulse_write_failure = None
        self.interrupt_ack = None
        self.no_pulse_ack = None
        self.close_failure = None
        self.stop_error = None

    def now(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds

    def factory(self, **options):
        assert options == dict(port=None, baudrate=115200, timeout=0.05,
                               write_timeout=1, exclusive=True)
        unit = ("A", "B")[len(self.ports)]
        port = FakePort(self, unit)
        self.ports.append(port)
        return port


class FakePort:
    def __init__(self, hub, unit):
        self.hub, self.unit = hub, unit
        self.port = self.dtr = self.rts = None
        self.rx = bytearray()
        self.writes = []
        self.closed = False
        self.pulse_sent = False
        self.pulse_reads = 0

    def open(self):
        assert self.dtr is False and self.rts is False
        assert self.port == "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_" + MACS[self.unit].upper() + "-if00"
        self.hub.events.append(("open", self.unit))
        if self.hub.open_failure == self.unit:
            raise OSError("open failed")

    def reset_input_buffer(self):
        assert not self.writes
        self.rx.clear()

    def write(self, data):
        self.hub.events.append(("write", self.unit, data, self.hub.time))
        self.writes.append(data)
        if data == b"ID\n":
            response = "ID HAMDA_USB 1 " + self.unit + " " + MACS[self.unit]
            if self.hub.bad_id == self.unit:
                response = "ID HAMDA_USB 1 UNKNOWN " + MACS[self.unit]
        elif data == b"STOP\n":
            response = "ERR GPIO" if self.hub.stop_error == self.unit else "OK STOP"
        elif data == b"PULSE 15 250\n":
            self.pulse_sent = True
            if self.hub.pulse_write_failure == self.unit:
                raise OSError("pulse write failed")
            response = "" if self.hub.no_pulse_ack == self.unit else "OK PULSE 15 250"
        else:
            raise AssertionError("Unexpected command: " + repr(data))
        if response:
            self.rx.extend((response + "\n").encode("ascii"))
        return len(data)

    def read(self, count):
        self.hub.time += 0.01
        self.hub.events.append(("read", self.unit))
        if self.pulse_sent and self.hub.interrupt_ack == self.unit:
            if self.pulse_reads == 4:
                self.hub.interrupt_ack = None
                raise KeyboardInterrupt()
            self.pulse_reads += 1
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def close(self):
        self.closed = True
        self.hub.events.append(("close", self.unit))
        if self.hub.close_failure == self.unit:
            raise OSError("close failed")


class BothTests(unittest.TestCase):
    def setUp(self):
        self.hub = FakeHub()
        self.output = io.StringIO()
        self.answers = ["", "PROVA", ""]
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            self.assertEqual(self.hub.ports, [])
            self.assertIn("OFF", prompt)
        elif len(self.prompts) == 2:
            self.assertEqual(len(self.hub.ports), 2)
            for port in self.hub.ports:
                self.assertEqual(port.writes, [b"ID\n", b"STOP\n"])
            self.assertIn("DUE batterie", prompt)
            self.assertIn("DEVONO restare fermi", prompt)
        else:
            self.assertIn("ENTRAMBE", prompt)
            for port in self.hub.ports:
                self.assertEqual(port.writes[-1], b"STOP\n")
                self.assertFalse(port.closed)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def invoke(self):
        with contextlib.redirect_stdout(self.output):
            MAIN(factory=self.hub.factory, ask=self.ask,
                 now=self.hub.now, sleep=self.hub.sleep)

    def pulses(self):
        return [event for event in self.hub.events if event[0] == "write" and event[2].startswith(b"PULSE")]

    def aborted(self, exception=RuntimeError):
        with self.assertRaises(exception):
            self.invoke()
        self.assertNotIn("PROVA A+B COMPLETATA", self.output.getvalue())
        self.assertTrue(all(port.closed for port in self.hub.ports))

    def assert_cleanup_sends_both_stops_before_any_read(self):
        events = self.hub.events
        last_pulse = max(i for i, event in enumerate(events) if event[0] == "write" and event[2].startswith(b"PULSE"))
        later = events[last_pulse + 1:]
        writes = [event for event in later if event[0] == "write"]
        self.assertEqual([(event[1], event[2]) for event in writes[:2]], [("A", b"STOP\n"), ("B", b"STOP\n")])
        first_read = next(i for i, event in enumerate(later) if event[0] == "read")
        self.assertEqual(len([event for event in later[:first_read] if event[0] == "write"]), 2)

    def test_normal_two_pulses_sent_before_first_pulse_ack_read(self):
        self.invoke()
        self.assertLessEqual(len(INLINE.encode()), 4500)
        self.assertNotIn("'", SOURCE)
        self.assertEqual([(event[1], event[2]) for event in self.pulses()], [("A", b"PULSE 15 250\n"), ("B", b"PULSE 15 250\n")])
        events = self.hub.events
        first = events.index(self.pulses()[0])
        second = events.index(self.pulses()[1])
        self.assertFalse(any(event[0] == "read" for event in events[first + 1:second]))
        self.assertEqual(self.pulses()[0][3], self.pulses()[1][3])
        for pulse in self.pulses():
            stops = [event for event in events[:events.index(pulse)] if event[0] == "write" and event[1] == pulse[1] and event[2] == b"STOP\n"]
            self.assertGreaterEqual(pulse[3] - stops[-1][3], 0.25)
        self.assertTrue(all(port.closed for port in self.hub.ports))
        self.assertEqual(len(self.prompts), 3)
        self.assertIn("PROVA A+B COMPLETATA", self.output.getvalue())

    def test_second_port_open_failure_closes_partial_and_first_port(self):
        self.hub.open_failure = "B"
        self.aborted(OSError)
        self.assertEqual(self.pulses(), [])
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(self.hub.ports[0].writes[-1], b"STOP\n")
        self.assertEqual(self.hub.ports[1].writes, [])

    def test_wrong_A_or_B_ID_never_reaches_battery_gate(self):
        for unit in ("A", "B"):
            with self.subTest(unit=unit):
                self.setUp()
                self.hub.bad_id = unit
                self.aborted()
                self.assertEqual(self.pulses(), [])
                self.assertEqual(len(self.prompts), 1)

    def test_wrong_stop_on_either_node_no_pulses(self):
        for unit in ("A", "B"):
            with self.subTest(unit=unit):
                self.setUp()
                self.hub.stop_error = unit
                self.aborted()
                self.assertEqual(self.pulses(), [])
                self.assertEqual(len(self.prompts), 1)

    def test_exact_PROVA_required_after_both_guards(self):
        for answer in ("", "prova", EOFError(), KeyboardInterrupt()):
            with self.subTest(answer=repr(answer)):
                self.setUp()
                self.answers[1] = answer
                self.aborted(type(answer) if isinstance(answer, BaseException) else RuntimeError)
                self.assertEqual(self.pulses(), [])
                self.assertTrue(all(port.writes[-1] == b"STOP\n" for port in self.hub.ports))

    def test_second_pulse_send_failure_stops_both_before_reading(self):
        self.hub.pulse_write_failure = "B"
        self.aborted(OSError)
        self.assertEqual(len(self.pulses()), 2)
        self.assert_cleanup_sends_both_stops_before_any_read()
        self.assertNotIn("STOP non confermato", self.output.getvalue())

    def test_first_pulse_send_failure_never_sends_second_pulse(self):
        self.hub.pulse_write_failure = "A"
        self.aborted(OSError)
        self.assertEqual([(event[1], event[2]) for event in self.pulses()], [("A", b"PULSE 15 250\n")])
        self.assert_cleanup_sends_both_stops_before_any_read()

    def test_interrupt_on_either_pending_ack_preserves_per_node_buffers(self):
        for unit in ("A", "B"):
            with self.subTest(unit=unit):
                self.setUp()
                self.hub.interrupt_ack = unit
                self.aborted(KeyboardInterrupt)
                self.assertEqual(len(self.pulses()), 2)
                self.assertNotIn("STOP non confermato", self.output.getvalue())
                self.assertTrue(all(port.writes[-1] == b"STOP\n" for port in self.hub.ports))

    def test_missing_second_ack_never_retries_and_closes_both(self):
        self.hub.no_pulse_ack = "B"
        self.aborted()
        self.assertEqual(len(self.pulses()), 2)
        self.assertNotIn("STOP non confermato", self.output.getvalue())

    def test_close_failure_on_first_does_not_skip_second_close(self):
        self.hub.close_failure = "A"
        self.aborted()
        self.assertEqual(len(self.pulses()), 2)


if __name__ == "__main__":
    unittest.main()
