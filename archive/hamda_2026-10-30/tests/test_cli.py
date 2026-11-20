"""Prove della CLI reale, incluse sessioni interattive con stato persistente."""

from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import re
import subprocess
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent


def run_cli(*arguments: str, commands: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "hamda", *arguments],
        cwd=ROOT,
        input=commands,
        capture_output=True,
        text=True,
        timeout=8,
    )


class CliTests(unittest.TestCase):
    def test_status_reports_all_16_virtual_motors(self):
        result = run_cli("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = re.findall(r"^([LR][1-8])\s+\d+\s+0\.0\s+0\.0%", result.stdout, re.MULTILINE)
        self.assertEqual(len(rows), 16)
        self.assertIn("Nessun motore fisico", result.stdout)

    def test_standalone_activation_completes(self):
        result = run_cli("on", "L1,R1", "50", "30")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("L1, R1", result.stdout)
        self.assertIn("tutte le uscite virtuali sono spente", result.stdout)

    def test_shell_preserves_activation_then_stop_clears_all_outputs(self):
        result = run_cli(commands="on all 50 5000\nstatus\nstop\nstatus\nquit\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(re.findall(r"^[LR][1-8]\s+\d+\s+50\.0", result.stdout, re.MULTILINE)), 16)
        self.assertEqual(len(re.findall(r"^[LR][1-8]\s+\d+\s+0\.0", result.stdout, re.MULTILINE)), 16)
        self.assertIn("STOP", result.stdout)

    def test_shell_can_change_intensity_and_deactivate(self):
        result = run_cli(commands="on L1 50 5000\nset L1 20\nstatus\noff L1\nstatus\nquit\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"L1\s+0\s+20\.0\s+20\.0%")
        self.assertIn("Motori virtuali spenti: L1", result.stdout)

    def test_bad_command_does_not_end_shell(self):
        result = run_cli(commands="on UNKNOWN 50 100\non L1 25 5000\nstatus\nquit\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ID motore sconosciuto", result.stderr)
        self.assertRegex(result.stdout, r"L1\s+0\s+25\.0")
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_standalone_command_returns_failure(self):
        result = run_cli("on", "L1", "101", "30")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Errore:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_eof_closes_shell_with_active_motor(self):
        result = run_cli(commands="on L1 25 5000\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Chiusura", result.stdout)

    def test_ctrl_c_turns_off_outputs_and_closes_backend(self):
        from hamda.cli import main
        from hamda.hardware.simulated import SimulatedBackend

        backend = SimulatedBackend()
        with patch("hamda.cli.SimulatedBackend", return_value=backend):
            with patch("builtins.input", side_effect=["on L1 50 5000", KeyboardInterrupt]):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    result = main(["shell"])
        self.assertEqual(result, 130)
        self.assertTrue(backend.closed)
        self.assertTrue(all(value == 0 for value in backend.outputs.values()))

    def test_missing_config_is_a_readable_error(self):
        result = run_cli("--config", "/nonexistent/hamda-hardware.json", "status")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Errore:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_diagnostic_verifies_all_channels(self):
        result = run_cli("test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("16 canali verificati", result.stdout)
        self.assertIn("non verifica motori", result.stdout)

    def test_faulted_status_distinguishes_logical_zero_from_backend_outputs(self):
        from hamda.cli import DEFAULT_CONFIG, _show_status
        from hamda.config import load_config
        from hamda.controller import MotorController
        from hamda.hardware.simulated import SimulatedBackend

        class FailingBackend(SimulatedBackend):
            fail_writes = False

            def set_output(self, channel, duty_cycle):
                if self.fail_writes:
                    raise OSError("simulated connection failure")
                super().set_output(channel, duty_cycle)

        backend = FailingBackend()
        with MotorController(load_config(DEFAULT_CONFIG), backend) as controller:
            controller.activate("L1", 50, 5000)
            backend.fail_writes = True
            try:
                with self.assertRaises(RuntimeError):
                    controller.stop_all()
                self.assertTrue(controller.faulted)
                self.assertEqual(backend.outputs[0], 0.5)
                output = StringIO()
                with redirect_stdout(output):
                    _show_status(controller)
                self.assertIn("GUASTO", output.getvalue())
                self.assertIn("stato comandato azzerato", output.getvalue())
                self.assertIn("uscite del backend non confermate", output.getvalue())
            finally:
                backend.fail_writes = False

    def test_diagnostic_fails_when_activation_expires_before_observation(self):
        from hamda.cli import DEFAULT_CONFIG, main
        from hamda.config import load_config
        from hamda.controller import MotorController
        from hamda.hardware.simulated import SimulatedBackend

        config = load_config(DEFAULT_CONFIG)
        with MotorController(config, SimulatedBackend()) as controller:
            original_snapshot = controller.snapshot

            def delayed_snapshot():
                # Riproduce una lettura ritardata, quando l'impulso è già finito.
                self.assertTrue(controller.wait_until_idle(timeout=1))
                return original_snapshot()

            output, errors = StringIO(), StringIO()
            with patch("hamda.cli.MotorController", return_value=controller):
                with patch.object(controller, "snapshot", side_effect=delayed_snapshot):
                    with redirect_stdout(output), redirect_stderr(errors):
                        result = main(["test"])
        self.assertNotEqual(result, 0)
        self.assertIn("attivazione troppo breve o non osservata", errors.getvalue())
        self.assertIn("diagnostico incompleto", errors.getvalue())
        self.assertNotIn("16 canali verificati", output.getvalue())


if __name__ == "__main__":
    unittest.main()
