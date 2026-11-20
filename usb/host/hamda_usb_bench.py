"""Banco USB esplicito A/B: preparazione sorgenti, nessuna porta aperta all'import.

Il protocollo conferma comandi logici, non misura il movimento dei motori.
pyserial viene importato solo quando una sessione richiesta apre le porte.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import signal
import sys
import time
from typing import Callable, Sequence


MAX_PULSE_MS = 250
COOLDOWN_SECONDS = 0.250
RESPONSE_TIMEOUT = 1.5
READ_POLL_SECONDS = 0.050
MAX_LINE_BYTES = 128
MASKS = {"primo": 1, "secondo": 2, "terzo": 4, "quarto": 8, "tutti": 15}


class BenchError(RuntimeError):
    """Identità, trasporto o conferma non consentono di proseguire il banco."""


@dataclass(frozen=True)
class NodeSpec:
    unit: str
    mac: str
    port: str


KNOWN_NODES = {
    "A": NodeSpec(
        "A", "10:00:3b:cc:97:d8",
        "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_10:00:3B:CC:97:D8-if00",
    ),
    "B": NodeSpec(
        "B", "10:00:3b:cc:1c:78",
        "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_10:00:3B:CC:1C:78-if00",
    ),
}
_IDENTITY = re.compile(r"ID HAMDA_USB 1 (A|B|UNKNOWN) ([0-9a-f]{2}(?::[0-9a-f]{2}){5})")


def select_nodes(selection: str) -> tuple[NodeSpec, ...]:
    if selection == "entrambe":
        return KNOWN_NODES["A"], KNOWN_NODES["B"]
    if selection not in KNOWN_NODES:
        raise ValueError("Selezionare A, B oppure entrambe.")
    return (KNOWN_NODES[selection],)


def _serial_factory(**options):
    # Il venv del Pi contiene già pyserial; non installiamo niente all'avvio.
    try:
        import serial
    except ImportError as error:
        raise BenchError(
            "pyserial non disponibile: usare il Python del venv hamda_esp32_tools del Pi."
        ) from error
    return serial.Serial(**options)


class DeviceLock:
    """Lock cooperativo Linux per utente e identità, oltre a exclusive=True."""

    def __init__(self, directory: Path, spec: NodeSpec):
        self.path = directory / f"{spec.unit}_{spec.mac.replace(':', '')}.lock"
        self._descriptor: int | None = None

    def acquire(self) -> None:
        import fcntl

        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        options = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0)
        options |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, options, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(descriptor)
            raise BenchError(f"Unità già in uso: {self.path.name}.") from error
        self._descriptor = descriptor

    def release(self) -> None:
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None


@dataclass
class _Node:
    spec: NodeSpec
    serial: object
    verified: bool = False
    pending_pulse_ack: str | None = None


class BenchSession:
    """Una sessione chiusa da context manager, con STOP best effort alla fine.

    Tutte le identità e tutti gli STOP iniziali devono essere confermati prima
    di qualunque impulso. Nessun fallback da una porta o identità sbagliata.
    """

    def __init__(
        self,
        specs: Sequence[NodeSpec],
        *,
        serial_factory: Callable | None = None,
        lock_directory: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.specs = tuple(specs)
        if not self.specs or len({spec.unit for spec in self.specs}) != len(self.specs):
            raise ValueError("Selezionare una o due unità distinte.")
        for spec in self.specs:
            if spec.unit not in KNOWN_NODES or spec != KNOWN_NODES[spec.unit]:
                raise ValueError("MAC e porta by-id devono corrispondere all'unità selezionata.")
        self._factory = serial_factory or _serial_factory
        self._lock_directory = (
            Path(lock_directory) if lock_directory is not None
            else Path.home() / ".cache" / "hamda_usb_bench" / "locks"
        )
        self._clock = clock
        self._sleep = sleep
        self._locks: list[DeviceLock] = []
        self._nodes: list[_Node] = []
        self._prepared = False
        self._closed = False
        self._pulse_used = False
        self._failed = False
        self.stop_results: dict[str, bool] = {}

    def _read_line(self, node: _Node, deadline: float | None = None) -> str:
        if deadline is None:
            deadline = self._clock() + RESPONSE_TIMEOUT
        buffer = bytearray()
        while self._clock() < deadline:
            chunk = node.serial.read(1)
            if not isinstance(chunk, bytes):
                raise BenchError(f"{node.spec.unit}: risposta seriale non valida.")
            if not chunk:
                continue
            buffer.extend(chunk)
            if len(buffer) > MAX_LINE_BYTES:
                raise BenchError(f"{node.spec.unit}: risposta oltre {MAX_LINE_BYTES} byte.")
            if chunk.endswith(b"\n"):
                try:
                    return bytes(buffer).removesuffix(b"\n").removesuffix(b"\r").decode("ascii")
                except UnicodeDecodeError as error:
                    raise BenchError(f"{node.spec.unit}: risposta non ASCII.") from error
        raise BenchError(f"{node.spec.unit}: timeout della risposta USB.")

    def _send(self, node: _Node, command: str) -> None:
        try:
            payload = (command + "\n").encode("ascii")
            if node.serial.write(payload) != len(payload):
                raise BenchError(f"{node.spec.unit}: comando scritto solo parzialmente.")
        except BenchError:
            raise
        except (OSError, ValueError) as error:
            raise BenchError(f"{node.spec.unit}: errore USB durante {command.split()[0]}.") from error

    def _receive(self, node: _Node, expected: str | None = None) -> str:
        try:
            response = self._read_line(node)
        except (OSError, ValueError) as error:
            raise BenchError(f"{node.spec.unit}: errore durante la lettura USB.") from error
        if response.startswith("ERR"):
            raise BenchError(f"{node.spec.unit}: firmware ha rifiutato il comando: {response}.")
        if expected is not None and response != expected:
            raise BenchError(f"{node.spec.unit}: risposta inattesa {response!r}; attesa {expected!r}.")
        return response

    def _request(self, node: _Node, command: str, expected: str | None = None) -> str:
        self._send(node, command)
        return self._receive(node, expected)

    def _confirm_stop(self, node: _Node) -> None:
        """Conferma lo STOP inviato, leggendo un eventuale ACK PULSE precedente.

        Saltiamo soltanto quell'unica risposta nota. Non ignoriamo errori o
        risposte arbitrarie e non estendiamo la deadline mentre leggiamo.
        """
        deadline = self._clock() + RESPONSE_TIMEOUT
        pending = node.pending_pulse_ack
        while True:
            response = self._read_line(node, deadline)
            if response == "OK STOP":
                node.pending_pulse_ack = None
                return
            if pending is not None and response == pending:
                pending = None
                node.pending_pulse_ack = None
                continue
            raise BenchError(f"{node.spec.unit}: STOP non confermato, risposta {response!r}.")

    def prepare(self) -> None:
        if self._closed or self._prepared or self._locks or self._nodes:
            raise BenchError("Sessione già usata: crearne una nuova.")
        # Blocchiamo tutte le unità prima di aprire la prima porta.
        for spec in self.specs:
            lock = DeviceLock(self._lock_directory, spec)
            lock.acquire()
            self._locks.append(lock)
        for spec in self.specs:
            try:
                connection = self._factory(
                    port=None, baudrate=115200, timeout=READ_POLL_SECONDS,
                    write_timeout=0.250, exclusive=True,
                )
                node = _Node(spec, connection)
                self._nodes.append(node)
                connection.dtr = False
                connection.rts = False
                connection.port = spec.port
                connection.open()
                if connection.port != spec.port:
                    raise BenchError(f"{spec.unit}: la porta aperta non corrisponde alla porta by-id.")
                identity = self._request(node, "ID")
                match = _IDENTITY.fullmatch(identity)
                if match is None or match.group(1) != spec.unit or match.group(2) != spec.mac:
                    raise BenchError(f"{spec.unit}: identità HAMDA_USB/MAC non confermata.")
                node.verified = True
                self._request(node, "STOP", "OK STOP")
            except BenchError:
                raise
            except (OSError, ValueError) as error:
                raise BenchError(f"{spec.unit}: impossibile aprire o preparare USB.") from error
        # Il firmware misura un cooldown OFF di almeno 250 ms. La pausa host
        # parte dopo l'ultimo ACK STOP, quindi non anticipa quel limite.
        self._sleep(COOLDOWN_SECONDS)
        self._prepared = True

    def pulse(self, mask: int, duration_ms: int = MAX_PULSE_MS) -> None:
        if type(mask) is not int or not 1 <= mask <= 15:
            raise ValueError("La maschera deve essere un intero da 1 a 15.")
        if type(duration_ms) is not int or not 1 <= duration_ms <= MAX_PULSE_MS:
            raise ValueError("La durata deve essere un intero da 1 a 250 ms.")
        if not self._prepared or self._closed or self._failed or self._pulse_used:
            raise BenchError("Preparare e verificare tutte le unità prima dell'impulso.")
        self._pulse_used = True
        # Inviamo entrambi i comandi prima di attendere il primo ACK, per
        # consentire finestre sovrapposte senza promettere sincronismo USB.
        command = f"PULSE {mask} {duration_ms}"
        try:
            for node in self._nodes:
                self._send(node, command)
                node.pending_pulse_ack = f"OK {command}"
            for node in self._nodes:
                self._receive(node, f"OK {command}")
                node.pending_pulse_ack = None
        except Exception:
            self._failed = True
            raise

    def ping(self) -> None:
        if not self._prepared or self._closed or self._failed:
            raise BenchError("Sessione non pronta.")
        try:
            for node in self._nodes:
                self._request(node, "PING", "OK PING")
        except Exception:
            self._failed = True
            raise

    def close(self) -> list[str]:
        if self._closed:
            return []
        self._closed = True
        errors = []
        awaiting = []
        # Inviamo STOP a tutti prima di leggere gli ACK: una risposta assente
        # da A non deve ritardare il tentativo di arresto su B.
        for node in self._nodes:
            if not node.verified:
                continue
            try:
                self._send(node, "STOP")
                awaiting.append(node)
            except Exception as error:
                self.stop_results[node.spec.unit] = False
                errors.append(f"{node.spec.unit}: STOP non inviato ({error})")
        for node in awaiting:
            try:
                self._confirm_stop(node)
                self.stop_results[node.spec.unit] = True
            except Exception as error:
                self.stop_results[node.spec.unit] = False
                errors.append(f"{node.spec.unit}: STOP non confermato ({error})")
        for node in self._nodes:
            try:
                node.serial.close()
            except Exception as error:
                errors.append(f"{node.spec.unit}: chiusura USB fallita ({error})")
        for lock in reversed(self._locks):
            try:
                lock.release()
            except OSError as error:
                errors.append(f"Rilascio lock fallito ({error})")
        return errors

    def __enter__(self) -> "BenchSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        errors = self.close()
        if errors:
            message = "; ".join(errors)
            if exc is None:
                raise BenchError(message)
            if hasattr(exc, "add_note"):
                exc.add_note(message)
            print(f"Chiusura: {message}", file=sys.stderr)


def _interrupt(signum, frame):
    raise KeyboardInterrupt(f"Segnale {signum}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Banco USB HAMDA: selezione esplicita e impulso finito, senza Wi-Fi/MQTT.",
        epilog=(
            "Richiede il NUOVO firmware HAMDA_USB. ACK = stato comandato, non sensori. "
            "Tenere batteria OFF durante collegamento/reset; stato prove in docs/STATO_2026-11-20.md."
        ),
    )
    parser.add_argument("--unit", required=True, choices=("A", "B", "entrambe"))
    parser.add_argument("action", choices=("off", *MASKS))
    parser.add_argument("--ms", type=int, default=MAX_PULSE_MS, help="durata da 1 a 250 ms (default: 250)")
    args = parser.parse_args(argv)
    if not 1 <= args.ms <= MAX_PULSE_MS:
        parser.error("--ms deve essere compreso tra 1 e 250")
    previous_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for sig in previous_handlers:
            signal.signal(sig, _interrupt)
        with BenchSession(select_nodes(args.unit)) as session:
            session.prepare()
            print("ID e STOP confermati: " + ", ".join(spec.unit for spec in session.specs))
            if args.action != "off":
                mask = MASKS[args.action]
                session.pulse(mask, args.ms)
                print(f"ACK impulso logico: mask {mask}, {args.ms} ms; nessun feedback fisico.")
        print("STOP finale confermato per tutte le unità selezionate.")
        return 0
    except KeyboardInterrupt:
        print("Interruzione: STOP tentato sulle sole unità con identità verificata.", file=sys.stderr)
        return 130
    except (BenchError, OSError, ValueError) as error:
        print(f"Banco interrotto: {error}", file=sys.stderr)
        return 1
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
