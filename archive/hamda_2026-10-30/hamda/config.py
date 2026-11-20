"""Load and validate the configuration before any output is activated.

All limits in the supplied file describe the simulation only. They are not
electrical specifications or verified limits for physical motors.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path


MOTOR_IDS = tuple(f"{foot}{index}" for foot in ("L", "R") for index in range(1, 9))


def finite_number(value: object, name: str) -> float:
    """Reject booleans, strings, infinity and NaN rather than coercing them."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: serve un numero finito.")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name}: serve un numero finito.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name}: serve un numero finito.")
    return result


@dataclass(frozen=True)
class MotorConfig:
    motor_id: str
    channel: int
    max_intensity: float = 100.0
    position: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.motor_id, str) or self.motor_id not in MOTOR_IDS:
            raise ValueError("motor_id deve essere uno tra L1–L8 e R1–R8.")
        if type(self.channel) is not int or not 0 <= self.channel <= 15:
            raise ValueError("channel deve essere un intero tra 0 e 15.")
        maximum = finite_number(self.max_intensity, "max_intensity")
        if not 0 < maximum <= 100:
            raise ValueError("max_intensity deve essere maggiore di 0 e al massimo 100.")
        if self.position is not None and (
            not isinstance(self.position, str) or not self.position.strip()
        ):
            raise ValueError("position deve essere null o una descrizione non vuota.")


@dataclass(frozen=True)
class SimulationConfig:
    motors: tuple[MotorConfig, ...]
    max_duration_ms: float = 60_000.0

    def __post_init__(self) -> None:
        if not isinstance(self.motors, tuple) or not all(
            isinstance(motor, MotorConfig) for motor in self.motors
        ):
            raise ValueError("motors deve essere una tupla di MotorConfig.")
        if len(self.motors) != 16 or {m.motor_id for m in self.motors} != set(MOTOR_IDS):
            raise ValueError("Servono esattamente 16 motori unici: L1–L8 e R1–R8.")
        if {m.channel for m in self.motors} != set(range(16)):
            raise ValueError("I 16 canali devono essere unici e coprire l'intervallo 0–15.")
        duration = finite_number(self.max_duration_ms, "max_duration_ms")
        if duration <= 0:
            raise ValueError("max_duration_ms deve essere maggiore di 0.")
        # threading.Condition uses the operating system's timed wait.
        # Keep the configured duration representable by that primitive.
        import threading

        if duration / 1000 > threading.TIMEOUT_MAX:
            raise ValueError("max_duration_ms supera il limite del timer di sistema.")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Chiave JSON duplicata: {key}.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Costante JSON non valida: {value}.")


def load_config(path: str | Path) -> SimulationConfig:
    """Read a complete simulation mapping; unknown options are treated as errors."""
    with Path(path).open(encoding="utf-8") as source:
        data = json.load(
            source, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    if not isinstance(data, dict):
        raise ValueError("La configurazione deve essere un oggetto JSON.")
    expected = {"schema_version", "mode", "max_duration_ms", "motors"}
    if set(data) != expected:
        raise ValueError(f"Campi richiesti nella configurazione: {', '.join(sorted(expected))}.")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("schema_version supportata: 1.")
    if data["mode"] != "simulation":
        raise ValueError("Questo prototipo supporta soltanto mode='simulation'.")
    if not isinstance(data["motors"], list):
        raise ValueError("motors deve essere una lista JSON.")
    motors = []
    for entry in data["motors"]:
        if not isinstance(entry, dict) or set(entry) != {
            "motor_id", "channel", "max_intensity", "position"
        }:
            raise ValueError("Ogni motore richiede motor_id, channel, max_intensity e position.")
        motors.append(MotorConfig(**entry))
    return SimulationConfig(tuple(motors), data["max_duration_ms"])
