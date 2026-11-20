"""Controlli funzionali su stato, temporizzazione, STOP e guasti simulati."""

from dataclasses import replace
from pathlib import Path
import threading
import unittest

from hamda.config import load_config
from hamda.controller import MotorController
from hamda.hardware.simulated import SimulatedBackend


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "hardware.json"


class FailingBackend(SimulatedBackend):
    """Permette di guastare una scrittura dopo l'avvio del controller."""

    def __init__(self):
        super().__init__()
        self.fail_channel = None
        self.attempts = []

    def set_output(self, channel, duty_cycle):
        self.attempts.append((channel, duty_cycle))
        if channel == self.fail_channel:
            raise OSError("Guasto di comunicazione simulato")
        super().set_output(channel, duty_cycle)


class MotorControllerTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG_PATH)
        self.backend = SimulatedBackend()
        self.controller = MotorController(self.config, self.backend)
        self.addCleanup(self.controller.close)

    def states(self):
        return {state.motor_id: state for state in self.controller.snapshot()}

    def test_startup_has_sixteen_outputs_all_off(self):
        self.assertEqual(set(self.backend.outputs), set(range(16)))
        self.assertTrue(all(value == 0 for value in self.backend.outputs.values()))
        self.assertEqual(len(self.states()), 16)
        self.assertTrue(all(state.intensity == 0 for state in self.states().values()))

    def test_each_motor_controls_its_own_channel(self):
        for motor in self.config.motors:
            with self.subTest(motor=motor.motor_id):
                self.controller.activate(motor.motor_id, 37.5, 1000)
                active = {channel for channel, value in self.backend.outputs.items() if value}
                self.assertEqual(active, {motor.channel})
                self.assertAlmostEqual(self.backend.outputs[motor.channel], 0.375)
                self.controller.deactivate(motor.motor_id)

    def test_two_motors_have_independent_intensities(self):
        self.controller.activate("L1", 20, 1000)
        self.controller.activate("R8", 75, 1000)
        self.assertAlmostEqual(self.backend.outputs[0], 0.2)
        self.assertAlmostEqual(self.backend.outputs[15], 0.75)
        self.controller.deactivate("L1")
        self.assertEqual(self.states()["L1"].intensity, 0)
        self.assertEqual(self.states()["R8"].intensity, 75)

    def test_group_activation_can_control_all_sixteen_motors(self):
        self.controller.activate_many([motor.motor_id for motor in self.config.motors], 30, 1000)
        self.assertTrue(all(value == 0.3 for value in self.backend.outputs.values()))

    def test_group_validation_does_not_partially_activate(self):
        with self.assertRaises(ValueError):
            self.controller.activate_many(["L1", "not-a-motor"], 50, 1000)
        self.assertTrue(all(value == 0 for value in self.backend.outputs.values()))

    def test_invalid_intensity_does_not_change_running_motor(self):
        self.controller.activate("L1", 20, 1000)
        for invalid in (-1, 101, True, "50", None, float("nan"), float("inf")):
            with self.subTest(intensity=invalid):
                with self.assertRaises(ValueError):
                    self.controller.activate("L1", invalid, 1000)
                self.assertEqual(self.states()["L1"].intensity, 20)

    def test_invalid_duration_does_not_activate(self):
        for invalid in (-1, 0, self.config.max_duration_ms + 1, True, "500", None, float("nan"), float("inf")):
            with self.subTest(duration=invalid):
                with self.assertRaises(ValueError):
                    self.controller.activate("L1", 50, invalid)
                self.assertEqual(self.backend.outputs[0], 0)

    def test_unknown_motor_is_rejected(self):
        for operation in (
            lambda: self.controller.activate("L9", 50, 100),
            lambda: self.controller.deactivate("L9"),
            lambda: self.controller.set_intensity("L9", 50),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    operation()

    def test_zero_intensity_turns_motor_off(self):
        self.controller.activate("L1", 50, 1000)
        self.controller.activate("L1", 0, 1000)
        self.assertEqual(self.backend.outputs[0], 0)
        self.assertTrue(self.controller.wait_until_idle(timeout=0.1))

    def test_timed_activation_expires_automatically(self):
        self.controller.activate("L1", 50, 40)
        self.assertTrue(self.controller.wait_until_idle(timeout=1))
        self.assertEqual(self.backend.outputs[0], 0)
        self.assertEqual(self.states()["L1"].remaining_ms, 0)

    def test_wait_timeout_reports_still_active(self):
        self.controller.activate("L1", 50, 1000)
        self.assertFalse(self.controller.wait_until_idle(timeout=0.01))
        self.assertEqual(self.states()["L1"].intensity, 50)

    def test_new_activation_replaces_old_deadline(self):
        self.controller.activate("L1", 20, 40)
        self.controller.activate("L1", 70, 500)
        threading.Event().wait(0.1)
        self.assertEqual(self.states()["L1"].intensity, 70)
        self.assertTrue(self.controller.wait_until_idle(timeout=1))

    def test_changing_intensity_preserves_original_deadline(self):
        self.controller.activate("L1", 20, 1000)
        threading.Event().wait(0.05)
        before = self.states()["L1"].remaining_ms
        self.controller.set_intensity("L1", 80)
        state = self.states()["L1"]
        self.assertEqual(state.intensity, 80)
        self.assertLessEqual(state.remaining_ms, before + 5)
        self.assertAlmostEqual(self.backend.outputs[0], 0.8)

    def test_setting_positive_intensity_on_inactive_motor_is_rejected(self):
        with self.assertRaises(ValueError):
            self.controller.set_intensity("L1", 50)
        self.assertEqual(self.backend.outputs[0], 0)

    def test_setting_zero_intensity_stops_motor(self):
        self.controller.activate("L1", 50, 1000)
        self.controller.set_intensity("L1", 0)
        self.assertTrue(self.controller.wait_until_idle(timeout=0.1))
        self.assertEqual(self.backend.outputs[0], 0)

    def test_stop_clears_every_motor_and_pending_deadline(self):
        self.controller.activate_many([motor.motor_id for motor in self.config.motors], 70, 1000)
        self.controller.stop_all()
        self.assertTrue(all(value == 0 for value in self.backend.outputs.values()))
        self.assertTrue(all(state.remaining_ms == 0 for state in self.states().values()))
        self.assertTrue(self.controller.wait_until_idle(timeout=0.1))

    def test_old_timer_after_stop_does_not_stop_new_activation(self):
        self.controller.activate("L1", 20, 40)
        self.controller.stop_all()
        self.controller.activate("L1", 80, 500)
        threading.Event().wait(0.1)
        self.assertEqual(self.states()["L1"].intensity, 80)

    def test_close_turns_off_all_outputs_and_is_idempotent(self):
        self.controller.activate("L1", 80, 1000)
        self.controller.close()
        self.controller.close()
        self.assertTrue(self.backend.closed)
        self.assertTrue(all(value == 0 for value in self.backend.outputs.values()))
        with self.assertRaises(RuntimeError):
            self.controller.activate("L1", 20, 1000)

    def test_context_manager_closes_on_application_exception(self):
        backend = SimulatedBackend()
        with self.assertRaisesRegex(RuntimeError, "errore applicativo"):
            with MotorController(self.config, backend) as controller:
                controller.activate("R1", 40, 1000)
                raise RuntimeError("errore applicativo")
        self.assertTrue(backend.closed)
        self.assertTrue(all(value == 0 for value in backend.outputs.values()))

    def test_configured_channel_mapping_and_intensity_cap_are_used(self):
        motors = list(self.config.motors)
        motors[0] = replace(motors[0], channel=15, max_intensity=35)
        motors[-1] = replace(motors[-1], channel=0)
        backend = SimulatedBackend()
        with MotorController(replace(self.config, motors=tuple(motors)), backend) as controller:
            controller.activate("L1", 35, 1000)
            self.assertAlmostEqual(backend.outputs[15], 0.35)
            self.assertEqual(backend.outputs[0], 0)
            with self.assertRaises(ValueError):
                controller.activate("L1", 36, 1000)

    def test_group_validates_every_motor_limit_before_writing(self):
        motors = list(self.config.motors)
        motors[0] = replace(motors[0], max_intensity=35)
        backend = SimulatedBackend()
        with MotorController(replace(self.config, motors=tuple(motors)), backend) as controller:
            controller.activate("R8", 60, 1000)
            before = backend.outputs
            with self.assertRaises(ValueError):
                controller.activate_many(["R1", "L1"], 50, 1000)
            self.assertEqual(backend.outputs, before)


class BackendFailureTests(unittest.TestCase):
    def test_startup_failure_attempts_all_outputs_and_closes_backend(self):
        config = load_config(CONFIG_PATH)
        backend = FailingBackend()
        backend.fail_channel = 0
        with self.assertRaises(RuntimeError):
            MotorController(config, backend)
        self.assertTrue(backend.closed)
        attempted_off = {channel for channel, duty in backend.attempts if duty == 0}
        self.assertEqual(attempted_off, set(range(16)))

    def test_background_expiration_failure_is_reported_to_waiter(self):
        config = load_config(CONFIG_PATH)
        backend = FailingBackend()
        controller = MotorController(config, backend)
        try:
            controller.activate("L1", 50, 40)
            controller.activate("R8", 60, 1000)
            backend.fail_channel = 0
            with self.assertRaises(RuntimeError):
                controller.wait_until_idle(timeout=1)
            self.assertTrue(controller.faulted)
            self.assertEqual(backend.outputs[15], 0)
        finally:
            backend.fail_channel = None
            controller.close()

    def test_write_failure_stops_other_outputs_and_attempts_every_channel(self):
        config = load_config(CONFIG_PATH)
        backend = FailingBackend()
        controller = MotorController(config, backend)
        try:
            controller.activate("R8", 60, 1000)
            backend.fail_channel = 0
            backend.attempts.clear()
            with self.assertRaises(RuntimeError):
                controller.activate("L1", 50, 1000)
            self.assertTrue(controller.faulted)
            attempted_off = {channel for channel, duty in backend.attempts if duty == 0}
            self.assertEqual(attempted_off, set(range(16)))
            self.assertEqual(backend.outputs[15], 0)
            with self.assertRaises(RuntimeError):
                controller.activate("R1", 50, 1000)
        finally:
            backend.fail_channel = None
            controller.close()

    def test_shutdown_failure_still_closes_backend(self):
        config = load_config(CONFIG_PATH)
        backend = FailingBackend()
        controller = MotorController(config, backend)
        controller.activate("L1", 60, 1000)
        backend.fail_channel = 0
        backend.attempts.clear()
        with self.assertRaises(RuntimeError):
            controller.close()
        self.assertTrue(backend.closed)
        attempted_off = {channel for channel, duty in backend.attempts if duty == 0}
        self.assertEqual(attempted_off, set(range(16)))
        controller.close()

    def test_shutdown_failure_does_not_hide_original_application_error(self):
        config = load_config(CONFIG_PATH)
        backend = FailingBackend()
        with self.assertRaisesRegex(ValueError, "errore originale"):
            with MotorController(config, backend) as controller:
                controller.activate("L1", 50, 1000)
                backend.fail_channel = 0
                raise ValueError("errore originale")
        self.assertTrue(backend.closed)


if __name__ == "__main__":
    unittest.main()
