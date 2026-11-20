#!/usr/bin/env python3
"""Prepara USB Ethernet su una nuova SD Raspberry Pi OS con cloud-init."""

import os
from pathlib import Path
import re
import sys

DEV_MAC = "02:48:41:4d:44:01"
HOST_MAC = "02:48:41:4d:44:02"
USB_BLOCK = (
    "# HAMDA USB INIZIO\n[all]\n"
    "dtoverlay=dwc2,dr_mode=peripheral\n# HAMDA USB FINE\n"
)
NETWORK = """version: 2
ethernets:
  eth0:
    dhcp4: true
    dhcp6: true
    optional: true
  usb0:
    match:
      macaddress: "02:48:41:4d:44:01"
    set-name: usb0
    dhcp4: false
    dhcp6: false
    addresses:
      - 10.55.0.2/24
    link-local: [ipv6]
    optional: true
"""


def prepare_boot(boot_dir):
    required = ("config.txt", "cmdline.txt", "network-config", "user-data", "meta-data")
    missing = [name for name in required if not (boot_dir / name).is_file()]
    if missing:
        raise ValueError("File mancanti sulla SD: " + ", ".join(missing))
    names = ("config.txt", "cmdline.txt", "network-config")
    originals = {name: (boot_dir / name).read_bytes() for name in names}
    lines = originals["cmdline.txt"].decode("utf-8").splitlines()
    if len(lines) != 1 or not any(word.startswith("root=") for word in lines[0].split()):
        raise ValueError("cmdline.txt deve avere una sola riga con root=; nessuna modifica")
    words = lines[0].split()
    modules = []
    for word in words:
        if word.startswith("modules-load="):
            modules.extend(item for item in word.split("=", 1)[1].split(",") if item)
    if any(item.startswith("g_") and item != "g_ether" for item in modules):
        raise ValueError("Un altro modulo gadget e' configurato; nessuna modifica")
    modules = list(dict.fromkeys(modules + ["dwc2", "g_ether"]))
    prefixes = ("modules-load=", "g_ether.dev_addr=", "g_ether.host_addr=")
    words = [word for word in words if not word.startswith(prefixes)]
    words.extend(("modules-load=" + ",".join(modules),
                  "g_ether.dev_addr=" + DEV_MAC, "g_ether.host_addr=" + HOST_MAC))
    config = originals["config.txt"].decode("utf-8")
    config = re.sub(r"(?s)# HAMDA USB INIZIO\n.*?# HAMDA USB FINE\n?", "", config)
    updates = {"config.txt": config.rstrip() + "\n\n" + USB_BLOCK,
               "cmdline.txt": " ".join(words) + "\n", "network-config": NETWORK}
    backup = boot_dir / "hamda-before-usb"
    backup.mkdir(exist_ok=True)
    for name, data in originals.items():
        if not (backup / name).exists():
            (backup / name).write_bytes(data)
    for name, contents in updates.items():
        temporary = boot_dir / (name + ".hamda-tmp")
        with temporary.open("wb") as stream:
            stream.write(contents.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(boot_dir / name)
    return backup


def main():
    if sys.platform != "darwin":
        print("Esegui questo blocco nel Terminale del Mac, con la SD inserita.")
        return 1
    try:
        backup = prepare_boot(Path("/Volumes/bootfs"))
    except (OSError, ValueError) as error:
        print("ERRORE:", error)
        return 1
    print("SD preparata per USB. File originali conservati in:", backup)
    print("Utente e password di Imager conservati.")
    print("IP previsto Raspberry: 10.55.0.2; IP previsto Mac: 10.55.0.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
