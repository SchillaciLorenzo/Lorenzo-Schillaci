#!/usr/bin/env bash
# Installa solo strumenti di compilazione, mai firmware o driver di sistema.
set -euo pipefail
umask 077

CLI_VERSION='1.6.0'
CORE_VERSION='3.3.13'
CLI_SHA256='2ed4e1436bb3be1265966af8eba95dd25e28f3a9f92d0a58d371ed14dbaf550f'
CLI_ARCHIVE="arduino-cli_${CLI_VERSION}_Linux_ARM64.tar.gz"
CLI_URL="https://github.com/arduino/arduino-cli/releases/download/v${CLI_VERSION}/${CLI_ARCHIVE}"
INDEX_URL='https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json'
FQBN='esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M'
MIN_FREE_KIB=8388608
BUILD_ROOT="${HAMDA_USB_BUILD_ROOT:-$HOME/hamda_usb_build}"
STEP='controlli iniziali'
LOG_FILE=''
WORK_DIR=''

usage() {
    printf '%s\n' \
        'Uso: bash install_arduino.sh --cli-only | --core' \
        '--cli-only  scarica e verifica Arduino CLI 1.6.0, senza installare il core.' \
        '--core      usa il CLI verificato e installa il core ESP32 3.3.13.' \
        'Default: $HOME/hamda_usb_build; nessuna porta seriale viene aperta.' \
        'HAMDA_USB_BUILD_ROOT permette una cartella dedicata alternativa.'
}

fail() {
    printf 'ERRORE: %s\n' "$*" >&2
    return 1
}

failed() {
    local status="$1"
    trap - ERR INT TERM
    printf '\nINSTALLAZIONE NON COMPLETATA: %s (codice %s).\n' "$STEP" "$status" >&2
    if [[ -n "$LOG_FILE" ]]; then
        printf 'Log della fase: %s\n' "$LOG_FILE" >&2
    fi
    printf 'Cache conservata: ripetere la stessa fase dopo aver risolto la causa.\n' >&2
    exit "$status"
}

cleanup() {
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf -- "$WORK_DIR"
    fi
}

trap 'failed "$?"' ERR
trap 'failed 130' INT
trap 'failed 143' TERM
trap cleanup EXIT

if [[ $# -ne 1 ]]; then
    usage >&2
    exit 2
fi
case "$1" in
    --cli-only) PHASE='cli-only' ;;
    --core) PHASE='core' ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

for tool in uname df python3 curl sha256sum tar mkdir mktemp mv rm tee cat cmp env flock; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        fail "Strumento essenziale assente: $tool"
    fi
done
if [[ "$(uname -m)" != 'aarch64' ]]; then
    fail 'Questa procedura richiede Linux aarch64 (Raspberry Pi OS 64 bit).'
fi
if [[ "$(uname -s)" != 'Linux' ]]; then
    fail 'L’archivio fissato è per Linux ARM64.'
fi
python3 - "$BUILD_ROOT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
if not path.is_absolute():
    raise SystemExit("La cartella dedicata deve essere un percorso assoluto.")
if any(character in str(path) for character in ("\n", "\r")):
    raise SystemExit("La cartella dedicata non deve contenere ritorni a capo.")
if path == Path("/") or path == Path.home():
    raise SystemExit("Usare una sottocartella dedicata, non / o la home intera.")
PY

mkdir -p -- "$BUILD_ROOT"
if [[ ! -w "$BUILD_ROOT" ]]; then
    fail "Cartella non scrivibile: $BUILD_ROOT"
fi
FREE_KIB="$(df -Pk -- "$BUILD_ROOT" | python3 -c '
import sys
rows = sys.stdin.read().splitlines()
if len(rows) != 2:
    raise SystemExit("Formato df non riconosciuto.")
columns = rows[1].split()
if len(columns) < 6 or not columns[3].isdigit():
    raise SystemExit("Spazio disponibile non leggibile da df.")
print(columns[3])
')"
if (( FREE_KIB < MIN_FREE_KIB )); then
    fail "Servono almeno 8 GiB liberi; disponibili $FREE_KIB KiB."
fi

mkdir -p -- "$BUILD_ROOT/tools" "$BUILD_ROOT/data" \
    "$BUILD_ROOT/downloads" "$BUILD_ROOT/user" "$BUILD_ROOT/logs" "$BUILD_ROOT/tmp"
exec 9>"$BUILD_ROOT/.setup.lock"
if ! flock -n 9; then
    fail 'Un’altra fase di installazione usa già questa cartella.'
fi
LOG_FILE="$(mktemp "$BUILD_ROOT/logs/${PHASE}.XXXXXXXX")"
WORK_DIR="$(mktemp -d "$BUILD_ROOT/tmp/setup.XXXXXXXX")"
CONFIG_FILE="$BUILD_ROOT/arduino-cli.yaml"
CLI_BIN="$BUILD_ROOT/tools/arduino-cli"
printf 'Fase: %s\nCartella dedicata: %s\nLog: %s\n' "$PHASE" "$BUILD_ROOT" "$LOG_FILE"

run_logged() {
    "$@" 2>&1 | tee -a "$LOG_FILE"
}

capture_json() {
    local output="$1"
    shift
    local status=0
    "$@" >"$output" 2>"${output}.stderr" || status=$?
    if (( status != 0 )); then
        if ! cat "$output" "${output}.stderr" | tee -a "$LOG_FILE" >&2; then
            printf 'Log incompleto; il codice del comando fallito resta %s.\n' "$status" >&2
        fi
        return "$status"
    fi
    cat "$output" "${output}.stderr" | tee -a "$LOG_FILE"
}

STEP='configurazione isolata Arduino CLI'
run_logged python3 - "$BUILD_ROOT" "$CONFIG_FILE" "$INDEX_URL" <<'PY'
import json
from pathlib import Path
import sys

root, config_path = Path(sys.argv[1]), Path(sys.argv[2])
config = {
    "directories": {name: str(root / name) for name in ("data", "downloads", "user")},
    "board_manager": {"additional_urls": [sys.argv[3]]},
}
# JSON è anche YAML valido; json.dumps conserva letteralmente spazi, virgolette
# e altri caratteri senza passare da eval o interpolazioni di codice shell.
contents = json.dumps(config, indent=2, ensure_ascii=True) + "\n"
if config_path.exists():
    try:
        existing = json.loads(config_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise SystemExit("Configurazione dedicata esistente non leggibile come JSON/YAML prodotto dal setup: conservata.") from error
    if existing != config:
        raise SystemExit("Configurazione dedicata esistente e diversa: conservata senza sovrascriverla.")
else:
    temporary = config_path.with_suffix(".yaml.tmp")
    temporary.write_text(contents, encoding="utf-8")
    temporary.replace(config_path)
print(f"Configurazione dedicata: {config_path}")
PY

# Gli override valgono solo per questi processi CLI, senza modificare PATH,
# profili o ambiente del chiamante. Evitano che variabili Arduino già presenti
# reindirizzino i pacchetti verso un’installazione globale.
CLI_ENV=(env
    "ARDUINO_DIRECTORIES_DATA=$BUILD_ROOT/data"
    "ARDUINO_DIRECTORIES_DOWNLOADS=$BUILD_ROOT/downloads"
    "ARDUINO_DIRECTORIES_USER=$BUILD_ROOT/user"
    "ARDUINO_BOARD_MANAGER_ADDITIONAL_URLS=$INDEX_URL"
)

verify_archive() {
    (
        cd "$BUILD_ROOT"
        printf '%s  %s\n' "$CLI_SHA256" "$1" | sha256sum --check --strict -
    )
}

if [[ "$PHASE" == 'cli-only' && ! -e "$BUILD_ROOT/$CLI_ARCHIVE" ]]; then
    STEP='download HTTPS Arduino CLI'
    run_logged curl --fail --location --show-error \
        --proto '=https' --proto-redir '=https' \
        --retry 3 --connect-timeout 20 --max-time 300 \
        --output "$BUILD_ROOT/${CLI_ARCHIVE}.tmp" "$CLI_URL"
    STEP='checksum del nuovo archivio, prima di estrazione o esecuzione'
    run_logged verify_archive "${CLI_ARCHIVE}.tmp"
    mv -- "$BUILD_ROOT/${CLI_ARCHIVE}.tmp" "$BUILD_ROOT/$CLI_ARCHIVE"
fi
if [[ ! -f "$BUILD_ROOT/$CLI_ARCHIVE" ]]; then
    fail 'Archivio CLI verificato assente: eseguire prima --cli-only.'
fi
STEP='checksum dell’archivio in cache'
run_logged verify_archive "$CLI_ARCHIVE"
STEP='estrazione del solo eseguibile verificato'
run_logged tar -xzf "$BUILD_ROOT/$CLI_ARCHIVE" -C "$WORK_DIR" arduino-cli
if [[ ! -f "$WORK_DIR/arduino-cli" || ! -x "$WORK_DIR/arduino-cli" ]]; then
    fail 'L’archivio verificato non contiene l’eseguibile atteso.'
fi

if [[ "$PHASE" == 'cli-only' ]]; then
    mv -- "$WORK_DIR/arduino-cli" "$BUILD_ROOT/tools/arduino-cli.tmp"
    mv -- "$BUILD_ROOT/tools/arduino-cli.tmp" "$CLI_BIN"
else
    if [[ ! -x "$CLI_BIN" ]] || ! cmp -s -- "$CLI_BIN" "$WORK_DIR/arduino-cli"; then
        fail 'Il CLI installato non coincide con l’archivio verificato: ripetere --cli-only.'
    fi
fi

STEP='verifica della versione CLI'
capture_json "$WORK_DIR/cli-version.json" \
    "${CLI_ENV[@]}" "$CLI_BIN" --config-file "$CONFIG_FILE" version --format json
run_logged python3 - "$WORK_DIR/cli-version.json" "$CLI_VERSION" <<'PY'
import json
from pathlib import Path
import sys

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(data, dict) or data.get("VersionString") != sys.argv[2]:
    raise SystemExit("Versione CLI non corrispondente o formato JSON non riconosciuto.")
print(f"CLI verificato: {data['VersionString']}")
PY

if [[ "$PHASE" == 'cli-only' ]]; then
    printf '\nCLI-ONLY COMPLETATO: Arduino CLI %s verificato.\n' "$CLI_VERSION"
    printf 'Il core ESP32 non è stato installato da questa fase. Nessuna porta seriale aperta.\n'
    printf 'Passo successivo separato: bash install_arduino.sh --core\n'
    exit 0
fi

printf 'Core %s: circa 1.2 GB compressi, oltre a estrazione e cache.\n' "$CORE_VERSION"
STEP='aggiornamento degli indici ufficiali'
run_logged "${CLI_ENV[@]}" "$CLI_BIN" --config-file "$CONFIG_FILE" core update-index \
    --additional-urls "$INDEX_URL"
STEP='installazione del core ESP32 fissato'
run_logged "${CLI_ENV[@]}" "$CLI_BIN" --config-file "$CONFIG_FILE" core install \
    "esp32:esp32@$CORE_VERSION" --additional-urls "$INDEX_URL" --skip-post-install
STEP='lettura dei core effettivamente installati'
capture_json "$WORK_DIR/core-list.json" \
    "${CLI_ENV[@]}" "$CLI_BIN" --config-file "$CONFIG_FILE" core list --format json
run_logged python3 - "$WORK_DIR/core-list.json" "$CORE_VERSION" <<'PY'
import json
from pathlib import Path
import sys

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
platforms = data.get("platforms") if isinstance(data, dict) else None
if not isinstance(platforms, list):
    raise SystemExit("Elenco dei core installati: formato JSON non riconosciuto.")
matches = [entry for entry in platforms if isinstance(entry, dict) and entry.get("id") == "esp32:esp32"]
if len(matches) != 1:
    raise SystemExit("Il core esp32:esp32 non risulta installato in modo univoco.")
entry = matches[0]
versions = [entry[key] for key in ("installed", "installed_version") if key in entry]
if len(versions) != 1 or versions[0] != sys.argv[2]:
    raise SystemExit("Il core installato non è esattamente la versione fissata 3.3.13.")
print(f"Core installato verificato: esp32:esp32@{sys.argv[2]}")
PY
STEP='verifica del target ESP32-C3 USB'
run_logged "${CLI_ENV[@]}" "$CLI_BIN" --config-file "$CONFIG_FILE" board details --fqbn "$FQBN"
printf '\nCORE COMPLETATO: esp32:esp32@%s, target %s.\n' "$CORE_VERSION" "$FQBN"
printf 'Questa procedura non compila, non carica firmware e non accede alle porte seriali.\n'
