#!/usr/bin/env python3
"""Attended bench test: PCA channels 0/1 and the two DRV8833 bridges.

Keep hamda_primo_motore.py in the same directory. The first working test
is reused without changing it. Each command starts and finishes with all
outputs off; this is not a continuous or fault-independent controller.
"""

import argparse
import fcntl
import signal
import sys
import time
from pathlib import Path

from hamda_primo_motore import (
    ADDRESS,
    BUS_PATH,
    PCA9685,
    PULSE_SECONDS,
    STOP_SIGNALS,
    interrupted,
)

COMMAND_CHANNELS = {
    "off": (),
    "primo": (0,),
    "secondo": (1,),
    "insieme": (0, 1),
}


class TwoMotorPCA(PCA9685):
    def off(self):
        super().off()
        if not self.read(0x0D) & 0x10:
            raise OSError("Spegnimento del secondo motore non confermato")

    def on_channels(self, channels):
        selected = tuple(channels)
        if (
            not selected
            or any(channel not in (0, 1) for channel in selected)
            or len(set(selected)) != len(selected)
        ):
            raise ValueError("Questa prova ammette solo i due motori 0 e 1")
        # Arm both outputs while FULL_OFF still overrides FULL_ON.
        for channel in selected:
            self.write(0x07 + 4 * channel, 0x10)
        for channel in selected:
            self.write(0x09 + 4 * channel, 0x00)


def operate(bus, command):
    channels = COMMAND_CHANNELS[command]
    pca = TwoMotorPCA(bus)
    try:
        pca.prepare()
        if channels:
            pca.on_channels(channels)
            time.sleep(PULSE_SECONDS)
    finally:
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, STOP_SIGNALS)
        try:
            pca.off()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def main(argv=None):
    parser = argparse.ArgumentParser(description="HAMDA: prova di due motori")
    parser.add_argument(
        "command", choices=tuple(COMMAND_CHANNELS), nargs="?", default="off"
    )
    command = parser.parse_args(argv).command
    old_handlers = {sig: signal.getsignal(sig) for sig in STOP_SIGNALS}
    try:
        for sig in STOP_SIGNALS:
            signal.signal(sig, interrupted)
        # Same lock as the first program: never run the two tests concurrently.
        with (Path.home() / ".hamda-pca40.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with open(BUS_PATH, "r+b", buffering=0) as bus:
                fcntl.ioctl(bus, 0x0703, ADDRESS)
                operate(bus, command)
    except KeyboardInterrupt:
        print("Test interrotto. Scollega il powerbank del motore.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as error:
        print(f"ERRORE: {error}. Scollega il powerbank del motore.", file=sys.stderr)
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    print("PCA: le uscite dei due motori sono impostate spente.")
    if command != "off":
        print(f"Prova '{command}' completata: impulso impostato a 0,25 secondi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
