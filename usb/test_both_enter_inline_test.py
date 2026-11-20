"""Enter-only bench regression tests: fake serial, clock and operator only."""
import contextlib
import io
import unittest
from pathlib import Path

from test_both_inline_test import FakeHub


INLINE = Path(__file__).with_name("test_both_enter_inline.txt").read_text()
SOURCE = INLINE.split("-c '\n", 1)[1].rsplit("'", 1)[0]
NAMESPACE = {"__name__": "both_enter_fake"}
exec(compile(SOURCE, "both_enter_inline", "exec"), NAMESPACE)
MAIN = NAMESPACE["main"]


class BothEnterTests(unittest.TestCase):
    def setUp(self):
        self.hub = FakeHub()
        self.answers = ["", "", ""]
        self.prompts = []
        self.output = io.StringIO()

    def pulses(self):
        return [event for event in self.hub.events
                if event[0] == "write" and event[2].startswith(b"PULSE")]

    def ask(self, prompt):
        self.prompts.append(prompt)
        stage = len(self.prompts)
        if stage == 1:
            self.assertEqual(self.hub.ports, [])
        elif stage == 2:
            self.assertEqual(self.pulses(), [])
            self.assertEqual(len(self.hub.ports), 2)
            for port in self.hub.ports:
                self.assertEqual(port.writes, [b"ID\n", b"STOP\n"])
        elif stage == 3:
            self.assertIn("ENTRAMBE", prompt)
            for port in self.hub.ports:
                self.assertEqual(port.writes[-1], b"STOP\n")
                self.assertFalse(port.closed)
        else:
            self.fail("Unexpected operator prompt")
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def invoke(self):
        with contextlib.redirect_stdout(self.output):
            MAIN(factory=self.hub.factory, ask=self.ask,
                 now=self.hub.now, sleep=self.hub.sleep)

    def aborted(self, exception=RuntimeError):
        with self.assertRaises(exception):
            self.invoke()
        self.assertNotIn("TEST A+B COMPLETATO", self.output.getvalue())
        self.assertTrue(all(port.closed for port in self.hub.ports))

    def test_empty_enter_at_all_three_stages_runs_one_episode_per_node(self):
        self.invoke()
        self.assertEqual(len(self.prompts), 3)
        self.assertEqual(self.answers, [])
        self.assertNotIn("PROVA", "\n".join(self.prompts))
        self.assertEqual([(event[1], event[2]) for event in self.pulses()],
                         [("A", b"PULSE 15 250\n"), ("B", b"PULSE 15 250\n")])
        self.assertTrue(all(port.closed for port in self.hub.ports))
        self.assertIn("TEST A+B COMPLETATO", self.output.getvalue())

    def test_old_typed_PROVA_at_first_prompt_no_longer_cancels(self):
        self.answers[0] = "PROVA"
        self.invoke()
        self.assertEqual(len(self.prompts), 3)
        self.assertEqual(len(self.pulses()), 2)
        self.assertIn("TEST A+B COMPLETATO", self.output.getvalue())

    def test_eof_at_first_pause_opens_no_ports_and_sends_no_pulse(self):
        self.answers[0] = EOFError()
        self.aborted(EOFError)
        self.assertEqual(self.hub.ports, [])
        self.assertEqual(self.pulses(), [])

    def test_eof_before_second_input_returns_prevents_activation(self):
        self.answers[1] = EOFError()
        self.aborted(EOFError)
        self.assertEqual(self.pulses(), [])
        self.assertTrue(all(port.writes[-1] == b"STOP\n" for port in self.hub.ports))

    def test_keyboard_interrupt_at_either_pause_prevents_activation(self):
        for stage in (0, 1):
            with self.subTest(stage=stage):
                self.setUp()
                self.answers[stage] = KeyboardInterrupt()
                self.aborted(KeyboardInterrupt)
                self.assertEqual(self.pulses(), [])

    def test_wrong_identity_on_either_node_never_reaches_battery_prompt(self):
        for unit in ("A", "B"):
            with self.subTest(unit=unit):
                self.setUp()
                self.hub.bad_id = unit
                self.aborted()
                self.assertEqual(self.pulses(), [])
                self.assertEqual(len(self.prompts), 1)

    def test_failed_initial_stop_on_either_node_prevents_activation(self):
        for unit in ("A", "B"):
            with self.subTest(unit=unit):
                self.setUp()
                self.hub.stop_error = unit
                self.aborted()
                self.assertEqual(self.pulses(), [])
                self.assertEqual(len(self.prompts), 1)

    def test_both_complete_pulses_are_sent_before_any_pulse_ack_read(self):
        self.invoke()
        events = self.hub.events
        first, second = [events.index(event) for event in self.pulses()]
        self.assertFalse(any(event[0] == "read" for event in events[first + 1:second]))
        self.assertEqual(self.pulses()[0][3], self.pulses()[1][3])
        for pulse in self.pulses():
            stops = [event for event in events[:events.index(pulse)]
                     if event[0] == "write" and event[1] == pulse[1] and event[2] == b"STOP\n"]
            self.assertGreaterEqual(pulse[3] - stops[-1][3], 0.25)

    def test_partial_pending_ack_on_either_node_is_drained_during_cleanup(self):
        for unit in ("A", "B"):
            with self.subTest(unit=unit):
                self.setUp()
                self.hub.interrupt_ack = unit
                self.aborted(KeyboardInterrupt)
                self.assertEqual(len(self.pulses()), 2)
                self.assertNotIn("STOP non confermato", self.output.getvalue())
                self.assertTrue(all(port.writes[-1] == b"STOP\n" for port in self.hub.ports))

    def test_second_pulse_write_error_sends_all_stops_before_reading(self):
        self.hub.pulse_write_failure = "B"
        self.aborted(OSError)
        self.assertEqual(len(self.pulses()), 2)
        events = self.hub.events
        last_pulse = events.index(self.pulses()[-1])
        later = events[last_pulse + 1:]
        first_read = next(index for index, event in enumerate(later) if event[0] == "read")
        writes = [event for event in later[:first_read] if event[0] == "write"]
        self.assertEqual([(event[1], event[2]) for event in writes],
                         [("A", b"STOP\n"), ("B", b"STOP\n")])

    def test_first_close_error_does_not_skip_second_port_close(self):
        self.hub.close_failure = "A"
        self.aborted()
        self.assertEqual(len(self.pulses()), 2)


if __name__ == "__main__":
    unittest.main()
