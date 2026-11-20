#!/usr/bin/env python3
"""Bench test: one DRV8833 motor on PCA9685 channel 0, motor supply 3 V.

Standard library only. Commands: off (default), pulse (250 ms, full output).
This is an attended bench test, not the full HAMDA controller. PCA9685 outputs
can persist after a bus failure or an uncatchable process termination; retain
a physical means of disconnecting the motor powerbank.
"""

import argparse
import fcntl
import signal
import sys
import time
from pathlib import Path

ADDRESS = 0x40
BUS_PATH = "/dev/i2c-1"
PULSE_SECONDS = 0.25
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


class PCA9685:
    def __init__(self, bus):
        self.bus = bus

    def write(self, register, value):
        if self.bus.write(bytes((register, value))) != 2:
            raise OSError("Scrittura I2C incompleta")

    def read(self, register):
        if self.bus.write(bytes((register,))) != 1:
            raise OSError("Selezione registro I2C incompleta")
        value = self.bus.read(1)
        if len(value) != 1:
            raise OSError("Lettura I2C incompleta")
        return value[0]

    def off(self):
        # FULL_OFF overrides FULL_ON. Stop channel 0 first, then all others.
        for channel in range(16):
            self.write(0x09 + 4 * channel, 0x10)
        if not self.read(0x09) & 0x10:
            raise OSError("Spegnimento del canale 0 non confermato")

    def prepare(self):
        self.off()
        self.write(0x01, 0x04)  # MODE2: non-inverted, totem-pole output.
        mode = self.read(0x00)
        if mode & 0x40:
            raise OSError("Clock esterno attivo: controllare la PCA prima del test")
        self.write(0x00, mode & ~0xB0)  # Clear SLEEP, AI and RESTART.
        time.sleep(0.005)  # Oscillator startup; no PWM frequency change needed.

    def on(self):
        self.write(0x07, 0x10)  # FULL_ON, still held off by FULL_OFF.
        self.write(0x09, 0x00)  # Release FULL_OFF: channel 0 is now high.


def operate(bus, command):
    pca = PCA9685(bus)
    try:
        pca.prepare()
        if command == "pulse":
            pca.on()
            time.sleep(PULSE_SECONDS)
    finally:
        # Do not let a second catchable signal interrupt the stop sequence.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, STOP_SIGNALS)
        try:
            pca.off()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description="HAMDA: prova del primo motore")
    parser.add_argument("command", choices=("off", "pulse"), nargs="?", default="off")
    command = parser.parse_args(argv).command
    old_handlers = {sig: signal.getsignal(sig) for sig in STOP_SIGNALS}
    try:
        for sig in STOP_SIGNALS:
            signal.signal(sig, interrupted)
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
    print("PCA: tutte le uscite impostate spente.")
    if command == "pulse":
        print("Impulso di 0,25 secondi completato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
