"""Contratti host con seriali/orologio finti, senza dispositivi o pyserial."""

from dataclasses import replace
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).with_name("hamda_usb_bench.py")
SPEC = importlib.util.spec_from_file_location("hamda_usb_bench", SOURCE)
bench = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bench
SPEC.loader.exec_module(bench)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


class FakeSerial:
    def __init__(self, owner, options):
        self.owner = owner
        self.options = options
        self.port = options["port"]
        self.dtr = None
        self.rts = None
        self.closed = False
        self.opened = False
        self.unit = None
        self.replies = []
        self.stop_count = 0

    def open(self):
        self.unit = next(unit for unit, spec in bench.KNOWN_NODES.items() if spec.port == self.port)
        self.owner.openings.append((self.unit, self.dtr, self.rts, self.options.copy()))
        if self.unit in self.owner.open_fail:
            raise OSError("Dispositivo non presente")
        self.opened = True
        if self.unit in self.owner.port_mismatch:
            self.port = "/dev/ttyACM999"

    def write(self, data):
        self.owner.writes.append((self.unit, data, self.owner.clock.now))
        command = data.decode("ascii").removesuffix("\n")
        self.owner.events.append(("write", self.unit, command, self.owner.clock.now))
        if (self.unit, command) in self.owner.write_fail:
            raise OSError("Disconnessione simulata")
        if (self.unit, command) in self.owner.partial_write:
            return len(data) - 1
        response = None
        delay = 0.0
        if command == "ID":
            spec = bench.KNOWN_NODES[self.unit]
            response = self.owner.identities.get(self.unit, f"ID HAMDA_USB 1 {self.unit} {spec.mac}")
        elif command == "STOP":
            self.stop_count += 1
            response = self.owner.stop_responses.get((self.unit, self.stop_count), "OK STOP")
        elif command == "PING":
            response = self.owner.ping_responses.get(self.unit, "OK PING")
        elif command.startswith("PULSE "):
            response = self.owner.pulse_responses.get(self.unit, f"OK {command}")
            delay = int(command.split()[2]) / 1000
        if (self.unit, command) in self.owner.timeouts:
            response = None
        if response is not None:
            payload = response if isinstance(response, bytes) else (response + "\r\n").encode("ascii")
            self.replies.append([self.owner.clock.now + delay, bytearray(payload), command])
        return len(data)

    def read(self, size):
        if not self.replies or self.owner.clock.now < self.replies[0][0]:
            self.owner.clock.sleep(bench.READ_POLL_SECONDS)
            return b""
        reply = self.replies[0]
        result = bytes(reply[1][:size])
        del reply[1][:size]
        if not reply[1]:
            self.replies.pop(0)
            self.owner.events.append(("read_complete", self.unit, reply[2], self.owner.clock.now))
        return result

    def close(self):
        self.closed = True


class FakeFactory:
    def __init__(self, clock):
        self.clock = clock
        self.connections = []
        self.writes = []
        self.events = []
        self.openings = []
        self.identities = {}
        self.stop_responses = {}
        self.ping_responses = {}
        self.pulse_responses = {}
        self.timeouts = set()
        self.write_fail = set()
        self.partial_write = set()
        self.open_fail = set()
        self.port_mismatch = set()

    def __call__(self, **options):
        connection = FakeSerial(self, options)
        self.connections.append(connection)
        return connection

    def commands(self, unit=None):
        return [data.decode("ascii").strip() for u, data, _ in self.writes if unit is None or u == unit]


class HostBenchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hamda_host_test_")
        self.addCleanup(self.temporary.cleanup)
        self.lock_directory = Path(self.temporary.name) / "locks"
        self.clock = FakeClock()
        self.factory = FakeFactory(self.clock)

    def session(self, selection="B"):
        return bench.BenchSession(
            bench.select_nodes(selection), serial_factory=self.factory,
            lock_directory=self.lock_directory,
            clock=self.clock.monotonic, sleep=self.clock.sleep,
        )

    def test_no_default_cli_action_and_help_work_without_site_packages(self):
        for arguments, status in ((["--help"], 0), ([], 2)):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-I", "-S", str(SOURCE), *arguments],
                    text=True, capture_output=True, timeout=5, check=False,
                )
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_import_and_construction_open_nothing(self):
        session = self.session()
        self.assertEqual(self.factory.connections, [])
        self.assertFalse(self.lock_directory.exists())
        session.close()

    def test_endpoints_are_stable_and_do_not_depend_on_tty_number(self):
        self.assertTrue(bench.KNOWN_NODES["A"].port.endswith("10:00:3B:CC:97:D8-if00"))
        self.assertTrue(bench.KNOWN_NODES["B"].port.endswith("10:00:3B:CC:1C:78-if00"))
        self.assertEqual(bench.KNOWN_NODES["A"].mac, "10:00:3b:cc:97:d8")
        self.assertEqual(bench.KNOWN_NODES["B"].mac, "10:00:3b:cc:1c:78")
        for spec in bench.KNOWN_NODES.values():
            self.assertIn("/dev/serial/by-id/", spec.port)

    def test_spec_with_wrong_port_or_mac_is_rejected_before_open(self):
        for spec in (
            replace(bench.KNOWN_NODES["B"], port=bench.KNOWN_NODES["A"].port),
            replace(bench.KNOWN_NODES["B"], mac=bench.KNOWN_NODES["A"].mac),
        ):
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError):
                    bench.BenchSession([spec], serial_factory=self.factory, lock_directory=self.lock_directory)
        self.assertEqual(self.factory.connections, [])

    def test_default_b_pulse_checks_id_stops_waits_and_closes(self):
        with self.session() as session:
            session.prepare()
            session.pulse(1)
        self.assertEqual(self.factory.commands(), ["ID", "STOP", "PULSE 1 250", "STOP"])
        pulse_time = next(t for _, data, t in self.factory.writes if data.startswith(b"PULSE"))
        self.assertGreaterEqual(pulse_time, bench.COOLDOWN_SECONDS)
        self.assertEqual(session.stop_results, {"B": True})
        self.assertTrue(all(connection.closed for connection in self.factory.connections))

    def test_dtr_rts_false_before_open_and_exclusive_bounded_serial(self):
        with self.session() as session:
            session.prepare()
        unit, dtr, rts, options = self.factory.openings[0]
        self.assertEqual(unit, "B")
        self.assertIs(dtr, False)
        self.assertIs(rts, False)
        self.assertIs(options["exclusive"], True)
        self.assertIsNone(options["port"])
        self.assertEqual(options["baudrate"], 115200)
        self.assertGreater(options["timeout"], 0)
        self.assertGreater(options["write_timeout"], 0)

    def test_eight_logical_outputs_and_all_masks(self):
        for unit in ("A", "B"):
            for action, expected_mask in (("primo", 1), ("secondo", 2), ("terzo", 4), ("quarto", 8), ("tutti", 15)):
                with self.subTest(unit=unit, action=action):
                    self.assertEqual(bench.MASKS[action], expected_mask)
                    with self.session(unit) as session:
                        session.prepare()
                        session.pulse(bench.MASKS[action], 1)
                    self.assertIn(f"PULSE {expected_mask} 1", self.factory.commands(unit))

    def test_both_units_complete_preflight_before_first_pulse(self):
        with self.session("entrambe") as session:
            session.prepare()
            session.pulse(15)
        sequence = [(unit, data.decode().strip()) for unit, data, _ in self.factory.writes]
        self.assertEqual(sequence[:4], [("A", "ID"), ("A", "STOP"), ("B", "ID"), ("B", "STOP")])
        self.assertEqual(sequence[4:6], [("A", "PULSE 15 250"), ("B", "PULSE 15 250")])
        self.assertEqual(sequence[-2:], [("A", "STOP"), ("B", "STOP")])
        self.assertEqual(session.stop_results, {"A": True, "B": True})

    def test_both_pulses_are_written_before_reading_first_pulse_ack(self):
        with self.session("entrambe") as session:
            session.prepare()
            session.pulse(15)
        events = [(kind, unit, command) for kind, unit, command, _ in self.factory.events]
        write_a = events.index(("write", "A", "PULSE 15 250"))
        write_b = events.index(("write", "B", "PULSE 15 250"))
        read_a = events.index(("read_complete", "A", "PULSE 15 250"))
        self.assertLess(write_a, write_b)
        self.assertLess(write_b, read_a)

    def test_off_only_sends_stop_to_verified_nodes(self):
        with self.session("entrambe") as session:
            session.prepare()
        self.assertFalse(any(command.startswith("PULSE") for command in self.factory.commands()))
        for unit in ("A", "B"):
            self.assertEqual(self.factory.commands(unit), ["ID", "STOP", "STOP"])

    def test_wrong_unknown_or_malformed_identity_prevents_pulse_and_stop_to_unverified(self):
        for identity in (
            "ID HAMDA_USB 1 UNKNOWN 10:00:3b:cc:1c:78",
            "ID HAMDA_USB 1 B 10:00:3b:cc:97:d8",
            "ID HAMDA_USB 1 A 10:00:3b:cc:1c:78",
            "ID HAMDA_USB 2 B 10:00:3b:cc:1c:78",
            "ID HAMDA_USB 1 B 10:00:3B:CC:1C:78",
            "TACTUS MQTT original firmware",
        ):
            with self.subTest(identity=identity):
                self.factory.writes.clear()
                self.factory.identities["B"] = identity
                with self.assertRaises(bench.BenchError):
                    with self.session() as session:
                        session.prepare()
                        session.pulse(1)
                self.assertEqual(self.factory.commands(), ["ID"])
                self.assertTrue(self.factory.connections[-1].closed)

    def test_port_changed_during_open_aborts_before_id(self):
        self.factory.port_mismatch.add("B")
        with self.assertRaises(bench.BenchError):
            with self.session() as session:
                session.prepare()
        self.assertEqual(self.factory.commands(), [])
        self.assertTrue(self.factory.connections[0].closed)

    def test_second_unit_wrong_id_stops_first_and_never_pulses(self):
        self.factory.identities["B"] = "ID HAMDA_USB 1 UNKNOWN 10:00:3b:cc:1c:78"
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(1)
        self.assertEqual(self.factory.commands("A"), ["ID", "STOP", "STOP"])
        self.assertEqual(self.factory.commands("B"), ["ID"])

    def test_second_port_open_failure_stops_verified_first(self):
        self.factory.open_fail.add("B")
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
        self.assertEqual(self.factory.commands("A"), ["ID", "STOP", "STOP"])
        self.assertTrue(all(connection.closed for connection in self.factory.connections))

    def test_initial_stop_error_prevents_all_pulses(self):
        self.factory.stop_responses[("B", 1)] = "ERR INPUT"
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(1)
        self.assertFalse(any(command.startswith("PULSE") for command in self.factory.commands()))
        self.assertEqual(session.stop_results, {"A": True, "B": True})

    def test_first_pulse_ack_error_stops_both_after_both_pulse_writes(self):
        self.factory.pulse_responses["A"] = "ERR ACTIVE"
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(1)
        self.assertIn("PULSE 1 250", self.factory.commands("B"))
        self.assertEqual(session.stop_results, {"A": True, "B": True})

    def test_first_pulse_write_failure_prevents_write_to_second(self):
        self.factory.write_fail.add(("A", "PULSE 1 250"))
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(1)
        self.assertNotIn("PULSE 1 250", self.factory.commands("B"))
        self.assertEqual(session.stop_results, {"A": True, "B": True})

    def test_second_pulse_failure_still_attempts_final_stop_on_both(self):
        self.factory.write_fail.add(("B", "PULSE 8 250"))
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(8)
        self.assertEqual(session.stop_results, {"A": True, "B": True})
        self.assertEqual(self.factory.commands("A")[-1], "STOP")
        self.assertEqual(self.factory.commands("B")[-1], "STOP")

    def test_wrong_first_ack_aborts_after_both_writes_and_stops_both(self):
        self.factory.pulse_responses["A"] = "OK PULSE 2 250"
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(1)
        self.assertIn("PULSE 1 250", self.factory.commands("B"))
        self.assertEqual(session.stop_results, {"A": True, "B": True})

    def test_first_ack_timeout_occurs_after_both_writes_and_stops_both(self):
        self.factory.timeouts.add(("A", "PULSE 15 250"))
        with self.assertRaisesRegex(bench.BenchError, "timeout"):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(15)
        for unit in ("A", "B"):
            self.assertIn("PULSE 15 250", self.factory.commands(unit))
            self.assertEqual(self.factory.commands(unit)[-1], "STOP")
        self.assertEqual(session.stop_results, {"A": True, "B": True})
        self.assertLess(self.clock.now, 2.0)

    def test_second_ack_error_still_stops_both(self):
        self.factory.pulse_responses["B"] = "ERR INPUT"
        with self.assertRaises(bench.BenchError):
            with self.session("entrambe") as session:
                session.prepare()
                session.pulse(15)
        self.assertEqual(session.stop_results, {"A": True, "B": True})

    def test_response_timeout_is_finite_and_cleanup_stops_verified_nodes(self):
        self.factory.timeouts.add(("B", "PULSE 1 250"))
        with self.assertRaisesRegex(bench.BenchError, "timeout"):
            with self.session() as session:
                session.prepare()
                session.pulse(1)
        self.assertLess(self.clock.now, 2.0)
        self.assertEqual(session.stop_results, {"B": True})

    def test_no_id_response_never_sends_stop_or_pulse(self):
        self.factory.timeouts.add(("B", "ID"))
        with self.assertRaises(bench.BenchError):
            with self.session() as session:
                session.prepare()
        self.assertEqual(self.factory.commands(), ["ID"])
        self.assertLess(self.clock.now, 1.6)

    def test_response_overflow_and_non_ascii_fail_closed(self):
        for response in (b"X" * (bench.MAX_LINE_BYTES + 1), b"\xff\n"):
            with self.subTest(response=response[:8]):
                self.factory.identities["B"] = response
                with self.assertRaises(bench.BenchError):
                    with self.session() as session:
                        session.prepare()
                self.assertTrue(self.factory.connections[-1].closed)

    def test_partial_write_aborts_and_never_retries_pulse(self):
        self.factory.partial_write.add(("B", "PULSE 1 250"))
        with self.assertRaisesRegex(bench.BenchError, "parzialmente"):
            with self.session() as session:
                session.prepare()
                session.pulse(1)
        self.assertEqual(self.factory.commands().count("PULSE 1 250"), 1)
        self.assertEqual(session.stop_results, {"B": True})

    def test_cleanup_failure_on_a_does_not_skip_stop_b(self):
        self.factory.stop_responses[("A", 2)] = "ERR INPUT"
        with self.assertRaisesRegex(bench.BenchError, "STOP non confermato"):
            with self.session("entrambe") as session:
                session.prepare()
        self.assertEqual(session.stop_results, {"A": False, "B": True})
        self.assertTrue(all(connection.closed for connection in self.factory.connections))

    def test_cleanup_writes_both_stops_before_waiting_for_first_stop_ack(self):
        with self.session("entrambe") as session:
            session.prepare()
            self.factory.events.clear()
        events = [(kind, unit, command) for kind, unit, command, _ in self.factory.events]
        self.assertEqual(events[:2], [("write", "A", "STOP"), ("write", "B", "STOP")])
        self.assertEqual(events[2], ("read_complete", "A", "STOP"))

    def test_keyboard_interrupt_runs_cleanup_on_both_verified_nodes(self):
        with self.assertRaises(KeyboardInterrupt):
            with self.session("entrambe") as session:
                session.prepare()
                raise KeyboardInterrupt()
        self.assertEqual(session.stop_results, {"A": True, "B": True})

    def test_cooperative_lock_blocks_second_session_before_open(self):
        with self.session() as first:
            first.prepare()
            opened = len(self.factory.connections)
            with self.assertRaises(bench.BenchError):
                with self.session() as second:
                    second.prepare()
            self.assertEqual(len(self.factory.connections), opened)
        with self.session() as third:
            third.prepare()

    def test_masks_durations_and_prepare_required(self):
        with self.session() as session:
            with self.assertRaises(bench.BenchError):
                session.pulse(1)
            session.prepare()
            for mask, duration in ((0, 250), (16, 250), (True, 250), (1, 0), (1, 251), (1, True), (1, 1.5)):
                with self.subTest(mask=mask, duration=duration):
                    with self.assertRaises(ValueError):
                        session.pulse(mask, duration)
        self.assertFalse(any(command.startswith("PULSE") for command in self.factory.commands()))

    def test_only_one_episode_per_session_and_close_is_idempotent(self):
        with self.session() as session:
            session.prepare()
            session.pulse(1)
            with self.assertRaises(bench.BenchError):
                session.pulse(1)
        before = list(self.factory.writes)
        session.close()
        self.assertEqual(self.factory.writes, before)

    def test_ping_and_error_latch_prevent_future_pulse(self):
        self.factory.ping_responses["B"] = "ERR INPUT"
        with self.session() as session:
            session.prepare()
            with self.assertRaises(bench.BenchError):
                session.ping()
            with self.assertRaises(bench.BenchError):
                session.pulse(1)
        self.assertFalse(any(command.startswith("PULSE") for command in self.factory.commands()))


if __name__ == "__main__":
    unittest.main()
