#!/usr/bin/env python3
"""HAMDA: prova sorvegliata di quattro motori, due DRV8833 a circa 3 V.

PCA9685 0x40, uscite 0, 1, 2 e 3. Solo libreria standard Python.
Comandi: off, primo, secondo, terzo, quarto, insieme, coppia2, tutti.
Insieme mantiene la prova dei primi due; tutti aziona i quattro motori.
Impulso nominale: 0,25 secondi. Verificare i nuovi motori singolarmente
e l'alimentazione sotto carico prima delle prove simultanee.
Mantenere accessibile la disconnessione del powerbank dei motori:
errori I2C, SIGKILL o blocchi del sistema possono impedire l'arresto.
"""

import argparse
import fcntl
from pathlib import Path
import signal
import sys
import time

ADDRESS = 0x40
BUS_PATH = "/dev/i2c-1"
LOCK_NAME = ".hamda-pca40.lock"
PULSE_SECONDS = 0.25
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
CONTROLLED_CHANNELS = (0, 1, 2, 3)
COMMANDS = {
    "off": (),
    "primo": (0,),
    "secondo": (1,),
    "terzo": (2,),
    "quarto": (3,),
    "insieme": (0, 1),
    "coppia2": (2, 3),
    "tutti": CONTROLLED_CHANNELS,
}


class PCA9685:
    def __init__(self, bus):
        self.bus = bus

    def write(self, register, value):
        if self.bus.write(bytes((register, value))) != 2:
            raise OSError("Scrittura I2C incompleta")

    def read(self, register):
        if self.bus.write(bytes((register,))) != 1:
            raise OSError("Selezione registro I2C incompleta")
        data = self.bus.read(1)
        if len(data) != 1:
            raise OSError("Lettura I2C incompleta")
        return data[0]

    def off(self):
        errors = []
        for channel in range(16):
            try:
                self.write(0x09 + 4 * channel, 0x10)
            except OSError:
                errors.append("scrittura uscita " + str(channel))
        for channel in CONTROLLED_CHANNELS:
            try:
                if not self.read(0x09 + 4 * channel) & 0x10:
                    errors.append("verifica uscita " + str(channel))
            except OSError:
                errors.append("lettura uscita " + str(channel))
        if errors:
            raise OSError("Spegnimento non confermato: " + ", ".join(errors))

    def prepare(self):
        self.off()
        mode = self.read(0x00)
        if mode & 0x40:
            raise OSError("Clock esterno attivo: controllare la PCA")
        self.write(0x01, 0x04)
        self.write(0x00, mode & ~0xB0)
        time.sleep(0.005)

    def activate(self, channels):
        channels = tuple(channels)
        if (not channels or any(channel not in CONTROLLED_CHANNELS for channel in channels)
                or len(set(channels)) != len(channels)):
            raise ValueError("Sono ammesse solo le uscite 0, 1, 2 e 3")
        for channel in channels:
            self.write(0x07 + 4 * channel, 0x10)
        for channel in channels:
            self.write(0x09 + 4 * channel, 0x00)


def operate(bus, command):
    channels = COMMANDS[command]
    pca = PCA9685(bus)
    try:
        pca.prepare()
        if channels:
            pca.activate(channels)
            time.sleep(PULSE_SECONDS)
    finally:
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, STOP_SIGNALS)
        try:
            pca.off()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="HAMDA: prova al banco di quattro motori",
        epilog="insieme = primi due; coppia2 = terzo e quarto; tutti = quattro motori. "
               "Provare prima i motori singolarmente e verificare l'alimentazione.",
    )
    parser.add_argument("command", choices=tuple(COMMANDS), nargs="?", default="off")
    command = parser.parse_args(argv).command
    old_handlers = {sig: signal.getsignal(sig) for sig in STOP_SIGNALS}
    try:
        for sig in STOP_SIGNALS:
            signal.signal(sig, interrupted)
        with (Path.home() / LOCK_NAME).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with open(BUS_PATH, "r+b", buffering=0) as bus:
                fcntl.ioctl(bus, 0x0703, ADDRESS)
                operate(bus, command)
    except KeyboardInterrupt:
        print("Prova interrotta. Scollega il powerbank dei motori.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as error:
        print("ERRORE:", error, file=sys.stderr)
        print("Scollega il powerbank dei motori.", file=sys.stderr)
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    print("PCA: uscite impostate spente.")
    if command != "off":
        print("Prova '" + command + "' completata: impulso impostato a 0,25 secondi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
