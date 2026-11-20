from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import sys

os.umask(0o077)
folder = Path(sys.argv[1])
marker = folder / "VERIFIED.txt"
marker.unlink(missing_ok=True)
names = ("firmware_lettura1.bin", "firmware_lettura2.bin")
copies = [(folder / name).read_bytes() for name in names]
if any(len(data) != 4194304 for data in copies):
    raise SystemExit("BACKUP NON VERIFICATO: dimensione diversa da 4194304 byte.")
if copies[0] != copies[1]:
    raise SystemExit("BACKUP NON VERIFICATO: le due copie sono diverse.")
digest = hashlib.sha256(copies[0]).hexdigest()
(folder / "SHA256SUMS").write_text(
    "".join(f"{digest}  {name}\n" for name in names), encoding="utf-8"
)
note = (
    "Modulo B: due letture complete e identiche.\n"
    f"Data UTC: {datetime.now(timezone.utc).isoformat()}\n"
    "Dimensione di ciascuna copia: 4194304 byte\n"
    f"SHA-256: {digest}\n"
    "Copia stabile; ripristino non collaudato.\n"
)
temporary = folder / "VERIFIED.txt.tmp"
temporary.write_text(note, encoding="utf-8")
temporary.replace(marker)
print("Dimensione verificata: 4194304 byte per copia.")
print(f"SHA-256: {digest}")
print(f"BACKUP VERIFICATO: {folder}")
