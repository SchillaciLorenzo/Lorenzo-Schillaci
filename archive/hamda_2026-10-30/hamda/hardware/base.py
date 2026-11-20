"""Small output contract: application code never imports Raspberry Pi libraries."""

from typing import Protocol


class OutputBackend(Protocol):
    def set_output(self, channel: int, duty_cycle: float) -> None:
        """Command a normalized duty cycle, from 0.0 (off) to 1.0."""
        ...

    def close(self) -> None:
        """Release resources, attempting to turn off all outputs first."""
        ...
