"""In-memory PWM outputs: no GPIO, I²C, electrical or perceptual simulation."""

import threading

from hamda.config import finite_number


class SimulatedBackend:
    def __init__(self) -> None:
        self._outputs = {channel: 0.0 for channel in range(16)}
        self._closed = False
        self._lock = threading.Lock()

    @property
    def outputs(self) -> dict[int, float]:
        """Return a copy so callers cannot modify the backend's output state."""
        with self._lock:
            return dict(self._outputs)

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def set_output(self, channel: int, duty_cycle: float) -> None:
        if type(channel) is not int or not 0 <= channel <= 15:
            raise ValueError("Canale fuori intervallo: usare un intero tra 0 e 15.")
        duty = finite_number(duty_cycle, "duty_cycle")
        if not 0 <= duty <= 1:
            raise ValueError("duty_cycle deve essere tra 0 e 1.")
        with self._lock:
            if self._closed:
                raise RuntimeError("Backend simulato già chiuso.")
            self._outputs[channel] = duty

    def close(self) -> None:
        with self._lock:
            self._outputs = dict.fromkeys(range(16), 0.0)
            self._closed = True
