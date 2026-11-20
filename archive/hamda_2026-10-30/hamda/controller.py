"""Independent, time-limited motor commands with one monotonic scheduler.

The backend only receives channel/duty-cycle commands. No electronic details
or Raspberry Pi libraries belong here. All state mutations share one condition
lock, so STOP and reactivation cannot race with an obsolete timer callback.
"""

from collections.abc import Iterable
from dataclasses import dataclass
import threading
import time
from types import TracebackType

from hamda.config import SimulationConfig, finite_number
from hamda.hardware.base import OutputBackend


@dataclass(frozen=True)
class MotorState:
    """A snapshot of commanded state, never a measurement of physical motion."""

    motor_id: str
    channel: int
    intensity: float
    duty_cycle: float
    remaining_ms: float


class MotorController:
    def __init__(self, config: SimulationConfig, backend: OutputBackend) -> None:
        if not isinstance(config, SimulationConfig):
            raise ValueError("Serve una SimulationConfig validata.")
        self._config = config
        self._backend = backend
        self._motors = {motor.motor_id: motor for motor in config.motors}
        self._intensities = dict.fromkeys(self._motors, 0.0)
        self._deadlines: dict[str, float] = {}
        self._condition = threading.Condition()
        self._closed = False
        self._faulted = False
        self._fault_reason: Exception | None = None
        self._worker = threading.Thread(
            target=self._run_scheduler, name="hamda-expiration", daemon=True
        )
        # Explicitly initialize every output, even if a backend was reused.
        with self._condition:
            errors = self._all_off_locked()
            if errors:
                self._faulted = self._closed = True
                try:
                    backend.close()
                except Exception:
                    pass
                raise RuntimeError("Avvio fallito: impossibile azzerare tutte le uscite.") from errors[0]
        try:
            self._worker.start()
        except BaseException:
            with self._condition:
                self._closed = True
                self._all_off_locked()
                backend.close()
            raise

    @property
    def faulted(self) -> bool:
        """True means outputs could not be confirmed; no new activation is allowed."""
        with self._condition:
            return self._faulted

    def _ensure_operational_locked(self) -> None:
        if self._closed:
            raise RuntimeError("Controller già chiuso.")
        if self._faulted:
            raise RuntimeError(
                "Controller in stato di guasto; spegnimento tentato, uscite non confermate."
            ) from self._fault_reason

    def _motor_locked(self, motor_id: str):
        if not isinstance(motor_id, str) or motor_id not in self._motors:
            raise ValueError(f"Motore sconosciuto: {motor_id!r}. Usare L1–L8 o R1–R8.")
        return self._motors[motor_id]

    def _intensity_locked(self, motor_id: str, intensity: float) -> float:
        motor = self._motor_locked(motor_id)
        value = finite_number(intensity, "intensity")
        if not 0 <= value <= motor.max_intensity:
            raise ValueError(
                f"Intensità per {motor_id}: valore tra 0 e {motor.max_intensity:g}."
            )
        return value

    def _all_off_locked(self) -> list[Exception]:
        """Attempt ALL channels even when a write fails; clear commanded state.

        A zero logical state after a failure is not evidence of physical shutdown.
        The caller must also check faulted / handle the reported exception.
        """
        errors: list[Exception] = []
        self._deadlines.clear()
        for motor_id, motor in self._motors.items():
            self._intensities[motor_id] = 0.0
            try:
                self._backend.set_output(motor.channel, 0.0)
            except Exception as exc:
                errors.append(exc)
        self._condition.notify_all()
        return errors

    def _fault_locked(self, cause: Exception) -> None:
        self._faulted = True
        self._fault_reason = cause
        self._all_off_locked()

    def _write_locked(self, motor_id: str, intensity: float) -> None:
        try:
            # This linear mapping is only a simulation convention, not a model
            # of perceived intensity or a physical motor calibration.
            self._backend.set_output(self._motors[motor_id].channel, intensity / 100)
        except Exception as exc:
            self._fault_locked(exc)
            raise RuntimeError(
                "Errore del backend: spegnimento globale tentato; uscite non confermate."
            ) from exc

    def activate(self, motor_id: str, intensity: float, duration_ms: float) -> None:
        self.activate_many((motor_id,), intensity, duration_ms)

    def activate_many(
        self, motor_ids: Iterable[str], intensity: float, duration_ms: float
    ) -> None:
        """Start a group with one deadline, validating every input before writing.

        Reissuing a command for an active motor replaces its intensity and
        deadline. Other motors keep their own settings and expiration times.
        """
        if isinstance(motor_ids, (str, bytes)):
            raise ValueError("motor_ids deve essere una sequenza di ID, non una stringa.")
        try:
            selected = tuple(motor_ids)
        except TypeError as exc:
            raise ValueError("motor_ids deve essere una sequenza di ID.") from exc
        if not selected:
            raise ValueError("Selezionare almeno un motore.")
        with self._condition:
            self._ensure_operational_locked()
            # Validate IDs before checking uniqueness: lists and other invalid
            # unhashable values should be input errors, not raw TypeErrors.
            values = [self._intensity_locked(motor_id, intensity) for motor_id in selected]
            if len(set(selected)) != len(selected):
                raise ValueError("Gli ID dei motori non devono essere duplicati.")
            duration = finite_number(duration_ms, "duration_ms")
            if not 0 < duration <= self._config.max_duration_ms:
                raise ValueError(
                    f"Durata: valore maggiore di 0 e al massimo {self._config.max_duration_ms:g} ms."
                )
            deadline = time.monotonic() + duration / 1000
            for motor_id, value in zip(selected, values):
                self._write_locked(motor_id, value)
                self._intensities[motor_id] = value
                if value == 0:
                    self._deadlines.pop(motor_id, None)
                else:
                    self._deadlines[motor_id] = deadline
            self._condition.notify_all()

    def deactivate(self, motor_id: str) -> None:
        with self._condition:
            self._ensure_operational_locked()
            self._motor_locked(motor_id)
            self._write_locked(motor_id, 0.0)
            self._intensities[motor_id] = 0.0
            self._deadlines.pop(motor_id, None)
            self._condition.notify_all()

    def set_intensity(self, motor_id: str, intensity: float) -> None:
        """Change an active output without extending its original deadline."""
        with self._condition:
            self._ensure_operational_locked()
            value = self._intensity_locked(motor_id, intensity)
            if value == 0:
                self.deactivate(motor_id)
                return
            deadline = self._deadlines.get(motor_id)
            if deadline is None or deadline <= time.monotonic():
                if deadline is not None:
                    self.deactivate(motor_id)
                raise ValueError(f"{motor_id} è spento: usare prima on con una durata.")
            self._write_locked(motor_id, value)
            self._intensities[motor_id] = value

    def stop_all(self) -> None:
        """Cancel every deadline and attempt to turn off every output."""
        with self._condition:
            if self._closed:
                raise RuntimeError("Controller già chiuso.")
            errors = self._all_off_locked()
            if errors:
                self._faulted = True
                self._fault_reason = errors[0]
                raise RuntimeError(
                    "STOP incompleto: tentate tutte le uscite; controller in stato di guasto."
                ) from errors[0]

    def snapshot(self) -> tuple[MotorState, ...]:
        with self._condition:
            now = time.monotonic()
            return tuple(
                MotorState(
                    motor_id=motor_id,
                    channel=motor.channel,
                    intensity=self._intensities[motor_id],
                    duty_cycle=self._intensities[motor_id] / 100,
                    remaining_ms=max(0.0, (self._deadlines.get(motor_id, now) - now) * 1000),
                )
                for motor_id, motor in self._motors.items()
            )

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        """Wait for all activations to end. Timeout is in seconds; faults raise."""
        if timeout is not None:
            timeout = finite_number(timeout, "timeout")
            if not 0 <= timeout <= threading.TIMEOUT_MAX:
                raise ValueError("timeout deve essere non negativo ed entro il limite di sistema.")
        limit = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while True:
                self._ensure_operational_locked()
                if not self._deadlines:
                    return True
                remaining = None if limit is None else limit - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return False
                self._condition.wait(remaining)

    def _run_scheduler(self) -> None:
        with self._condition:
            while not self._closed and not self._faulted:
                if not self._deadlines:
                    self._condition.wait()
                    continue
                now = time.monotonic()
                remaining = min(self._deadlines.values()) - now
                if remaining > 0:
                    self._condition.wait(min(remaining, threading.TIMEOUT_MAX))
                    continue
                expired = [key for key, deadline in self._deadlines.items() if deadline <= now]
                for motor_id in expired:
                    try:
                        self._write_locked(motor_id, 0.0)
                    except RuntimeError:
                        # The fault is retained and surfaced to waiters / the
                        # next command; exceptions in a worker must not vanish.
                        return
                    self._intensities[motor_id] = 0.0
                    self._deadlines.pop(motor_id, None)
                self._condition.notify_all()

    def close(self) -> None:
        """Idempotent shutdown, reporting failures after all cleanup attempts."""
        with self._condition:
            if self._closed:
                return
            self._closed = True
            errors = self._all_off_locked()
            try:
                self._backend.close()
            except Exception as exc:
                errors.append(exc)
            if errors:
                self._faulted = True
                self._fault_reason = errors[0]
            self._condition.notify_all()
        self._worker.join()
        if errors:
            raise RuntimeError("Errore durante la chiusura: spegnimento non confermato.") from errors[0]

    def __enter__(self) -> "MotorController":
        with self._condition:
            self._ensure_operational_locked()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except Exception as close_error:
            if exc is None:
                raise
            # Preserve the original failure rather than hiding it with cleanup.
            if hasattr(exc, "add_note"):
                exc.add_note(f"Anche la chiusura del controller è fallita: {close_error}")
