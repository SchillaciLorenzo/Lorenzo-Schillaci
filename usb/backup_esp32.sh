#!/usr/bin/env bash
# Backup di sola lettura per l'ESP32-C3 già identificato, lasciato nel bootloader.
# Nessun comando programma la flash, modifica eFuse o avvia il firmware utente.

set -euo pipefail
umask 077

ESP32_PYTHON="${HAMDA_ESP32_PYTHON:-$HOME/hamda_esp32_tools/bin/python}"
ESP32_PORT="${HAMDA_ESP32_PORT:-/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_10:00:3B:CC:97:D8-if00}"
BACKUP_PARENT="${HAMDA_ESP32_BACKUP_PARENT:-$HOME}"
BACKUP_DIR=''
BACKUP_STEP='controlli iniziali'

backup_failed() {
    local status="$1"
    trap - ERR INT TERM
    printf '\nBACKUP NON VERIFICATO: errore durante %s.\n' "$BACKUP_STEP" >&2
    if [[ -n "$BACKUP_DIR" ]]; then
        # Questa directory privata è stata creata da questa esecuzione.
        # I dati parziali restano disponibili, ma non devono sembrare verificati.
        rm -f -- "$BACKUP_DIR/VERIFIED.txt"
        printf 'File parziali conservati in: %s\n' "$BACKUP_DIR" >&2
    fi
    exit "$status"
}

trap 'backup_failed "$?"' ERR
trap 'backup_failed 130' INT
trap 'backup_failed 143' TERM

if [[ ! -f "$ESP32_PYTHON" || ! -x "$ESP32_PYTHON" ]]; then
    printf 'Interprete non trovato o non eseguibile: %s\n' "$ESP32_PYTHON" >&2
    exit 1
fi
if [[ ! -c "$ESP32_PORT" ]]; then
    printf 'La porta indicata non è un dispositivo seriale a caratteri: %s\n' "$ESP32_PORT" >&2
    exit 1
fi
if [[ ! -d "$BACKUP_PARENT" || ! -w "$BACKUP_PARENT" ]]; then
    printf 'La cartella di destinazione non esiste o non è scrivibile: %s\n' "$BACKUP_PARENT" >&2
    exit 1
fi

BACKUP_DIR="$(mktemp -d "$BACKUP_PARENT/HAMDA_backup_ESP32_XXXXXXXX")"
printf 'Backup privato locale: %s\n' "$BACKUP_DIR"
printf 'Solo lettura: il chip resta nel bootloader, senza reset tra le letture.\n'

ESPTOOL=(
    "$ESP32_PYTHON" -m esptool
    --chip esp32c3
    --port "$ESP32_PORT"
    --baud 115200
    --before no-reset
    --after no-reset
    --no-stub
)

BACKUP_STEP='lettura informazioni di sicurezza'
"${ESPTOOL[@]}" get-security-info 2>&1 | tee "$BACKUP_DIR/security-info.txt"

BACKUP_STEP='verifica delle informazioni di sicurezza'
"$ESP32_PYTHON" - "$BACKUP_DIR/security-info.txt" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")


def field(name):
    matching = [
        line.strip()
        for line in text.splitlines()
        if re.match(r"^\s*" + re.escape(name) + r"\s*:", line)
    ]
    if len(matching) != 1:
        raise SystemExit(f"Sicurezza non verificabile: campo {name!r} mancante o duplicato.")
    return matching[0]


flags_line = field("Flags")
flags = re.fullmatch(
    r"Flags\s*:\s*(0[xX][0-9a-fA-F]+)(?:\s+\((0b[01]+)\))?", flags_line
)
if flags is None:
    raise SystemExit("Sicurezza non verificabile: formato Flags sconosciuto.")
value = int(flags.group(1), 16)
if value != 0:
    raise SystemExit("Backup interrotto: Flags diversi da zero; nessuna lettura flash autorizzata.")
if flags.group(2) is not None and int(flags.group(2), 2) != value:
    raise SystemExit("Sicurezza non verificabile: rappresentazioni Flags incoerenti.")
for name in ("Secure Boot", "Flash Encryption"):
    if re.fullmatch(re.escape(name) + r"\s*:\s*Disabled", field(name)) is None:
        raise SystemExit(f"Backup interrotto: {name} non risulta esplicitamente Disabled.")

print("Sicurezza verificata: Flags zero, Secure Boot e Flash Encryption Disabled.")
PY

BACKUP_STEP='identificazione flash'
"${ESPTOOL[@]}" flash-id 2>&1 | tee "$BACKUP_DIR/flash-id.txt"

BACKUP_STEP='prima lettura completa flash'
"${ESPTOOL[@]}" read-flash 0 ALL "$BACKUP_DIR/firmware_A.bin" 2>&1 | tee "$BACKUP_DIR/read_A.txt"

BACKUP_STEP='seconda lettura completa flash'
"${ESPTOOL[@]}" read-flash 0 ALL "$BACKUP_DIR/firmware_B.bin" 2>&1 | tee "$BACKUP_DIR/read_B.txt"

BACKUP_STEP='verifica dimensioni, identità e SHA-256'
"$ESP32_PYTHON" - "$BACKUP_DIR" <<'PY'
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

directory = Path(sys.argv[1])
names = ("firmware_A.bin", "firmware_B.bin")
paths = [directory / name for name in names]
expected_size = 4 * 1024 * 1024  # Dimensione già rilevata sul dispositivo identificato.
for path in paths:
    size = path.stat().st_size
    if size != expected_size:
        raise SystemExit(f"Backup non completo: {path.name} misura {size}, attesi {expected_size} byte.")

hashes = [hashlib.sha256(), hashlib.sha256()]
with paths[0].open("rb") as first, paths[1].open("rb") as second:
    while True:
        chunks = first.read(1024 * 1024), second.read(1024 * 1024)
        if chunks[0] != chunks[1]:
            raise SystemExit("Backup non verificato: le due letture flash sono diverse.")
        if not chunks[0]:
            break
        for digest, chunk in zip(hashes, chunks):
            digest.update(chunk)
digests = [digest.hexdigest() for digest in hashes]
if digests[0] != digests[1]:
    raise SystemExit("Backup non verificato: SHA-256 differenti.")

# Il manifest usa nomi relativi per restare valido se la cartella viene spostata.
(directory / "SHA256SUMS").write_text(
    "".join(f"{digest}  {name}\n" for digest, name in zip(digests, names)), encoding="utf-8"
)
marker = (
    "VERIFIED: due letture complete e identiche della flash ESP32-C3.\n"
    f"Data UTC: {datetime.now(timezone.utc).isoformat()}\n"
    f"Dimensione di ciascuna copia: {expected_size} byte\n"
    f"SHA-256: {digests[0]}\n"
    "Copia stabile: non prova di ripristino, né garanzia di funzionamento del firmware.\n"
    "Dati privati locali: possono contenere credenziali; non caricare i binari in chat o repository.\n"
)
temporary_marker = directory / "VERIFIED.txt.tmp"
temporary_marker.write_text(marker, encoding="utf-8")
temporary_marker.replace(directory / "VERIFIED.txt")
print(f"Dimensione verificata: {expected_size} byte per copia.")
print(f"SHA-256: {digests[0]}")
PY

printf '\nBACKUP VERIFICATO: %s\n' "$BACKUP_DIR"
printf 'Due letture identiche: copia stabile, non prova di ripristino.\n'
printf 'Conserva cartella e binari privatamente sul Pi; non caricarli in chat o repository.\n'
