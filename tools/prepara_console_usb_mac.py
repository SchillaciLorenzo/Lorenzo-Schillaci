#!/usr/bin/env python3
"""Console USB temporanea per diagnosticare il Raspberry senza rete."""

import os
from pathlib import Path
import sys

BACKUP = "cmdline.txt.hamda-ethernet"
GETTY = "systemd.wants=serial-getty@ttyGS0.service"


def atomic_write(path, data):
    temporary = path.with_name(path.name + ".hamda-tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def prepare_console(boot):
    for name in ("cmdline.txt", "config.txt"):
        if not (boot / name).is_file():
            raise ValueError("File mancante: " + name)
    config = (boot / "config.txt").read_text()
    if "dtoverlay=dwc2,dr_mode=peripheral" not in config.splitlines():
        raise ValueError("Configurazione dwc2 peripheral non trovata")
    path = boot / "cmdline.txt"
    original = path.read_bytes()
    lines = original.decode("utf-8").splitlines()
    if len(lines) != 1 or not any(word.startswith("root=") for word in lines[0].split()):
        raise ValueError("cmdline.txt non valido; nessuna modifica")
    words = lines[0].split()
    modules = []
    for word in words:
        if word.startswith("modules-load="):
            modules.extend(item for item in word.split("=", 1)[1].split(",") if item)
    gadgets = [name for name in modules if name.startswith("g_")]
    if not gadgets or any(name not in ("g_ether", "g_serial") for name in gadgets):
        raise ValueError("Modulo gadget inatteso; nessuna modifica")
    modules = list(dict.fromkeys([name for name in modules if name not in gadgets]
                                + ["dwc2", "g_serial"]))
    prefixes = ("modules-load=", "g_ether.", "g_serial.", "network-config=")
    words = [word for word in words if not word.startswith(prefixes) and word != GETTY]
    words.extend(("modules-load=" + ",".join(modules), "g_serial.use_acm=1",
                  "network-config=disabled", GETTY))
    backup = boot / BACKUP
    if not backup.exists():
        atomic_write(backup, original)
    atomic_write(path, (" ".join(words) + "\n").encode("utf-8"))
    return backup


def restore_ethernet(boot):
    backup = boot / BACKUP
    data = backup.read_bytes()
    lines = data.decode("utf-8").splitlines()
    if len(lines) != 1 or not any(word.startswith("root=") for word in lines[0].split()):
        raise ValueError("Backup di avvio non valido; nessuna modifica")
    atomic_write(boot / "cmdline.txt", data)


def main():
    if sys.platform != "darwin":
        print("Esegui questo blocco sul Mac con la SD inserita.")
        return 1
    boot = Path("/Volumes/bootfs")
    mode = sys.argv[1] if len(sys.argv) == 2 else "prepare"
    try:
        if mode == "restore":
            restore_ethernet(boot)
            print("Configurazione di avvio Ethernet ripristinata.")
        elif mode == "prepare":
            backup = prepare_console(boot)
            print("Avvio per console USB preparato. Backup:", backup)
            print("Al prossimo avvio cercheremo una porta seriale USB sul Mac.")
        else:
            raise ValueError("Modalita' non riconosciuta")
    except (OSError, ValueError) as error:
        print("ERRORE:", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
