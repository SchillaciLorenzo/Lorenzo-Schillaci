"""Interfaccia a riga di comando del prototipo HAMDA simulato.

La shell mantiene lo stesso controller tra un comando e il successivo.
Ogni invocazione separata del programma crea invece una nuova simulazione.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import sys
from typing import Sequence

from hamda.config import SimulationConfig, load_config
from hamda.controller import MotorController
from hamda.hardware.simulated import SimulatedBackend


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "hardware.json"
PROCESS_NOTE = (
    "Ogni processo ha una simulazione indipendente. Per comandare e fermare "
    "le stesse attivazioni, usa la shell nello stesso processo."
)


class CommandParser(argparse.ArgumentParser):
    """Gli errori di sintassi non devono terminare la shell interattiva."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def build_parser(*, shell: bool = False) -> argparse.ArgumentParser:
    """Crea la stessa grammatica per il terminale e per la shell."""
    parser = CommandParser(
        prog="hamda",
        description="HAMDA: controllo di 16 motori virtuali, senza hardware.",
        epilog=PROCESS_NOTE,
    )
    if not shell:
        parser.add_argument(
            "--config",
            type=Path,
            default=DEFAULT_CONFIG,
            help="file JSON di configurazione (default: config/hardware.json del progetto)",
        )
    commands = parser.add_subparsers(dest="command", metavar="COMANDO")
    commands.add_parser("status", help="mostra lo stato logico dei motori virtuali")

    activate = commands.add_parser("on", help="attiva uno o più motori per una durata")
    activate.add_argument("motors", metavar="MOTORI", help="es. L1, L1,R2 oppure all")
    activate.add_argument("intensity", type=float, metavar="INTENSITÀ")
    activate.add_argument("duration_ms", type=float, metavar="DURATA_MS")

    deactivate = commands.add_parser("off", help="spegne i motori selezionati")
    deactivate.add_argument("motors", metavar="MOTORI", help="es. L1, L1,R2 oppure all")

    intensity = commands.add_parser("set", help="modifica l'intensità di un motore attivo")
    intensity.add_argument("motor", metavar="MOTORE")
    intensity.add_argument("intensity", type=float, metavar="INTENSITÀ")

    commands.add_parser("stop", help="spegne tutti i motori di questo processo")
    commands.add_parser("test", help="esegue il diagnostico dei soli motori virtuali")
    if shell:
        commands.add_parser("help", help="mostra i comandi disponibili")
        commands.add_parser("quit", aliases=["exit"], help="spegne tutti i motori ed esce")
    else:
        commands.add_parser("shell", help="avvia la shell interattiva (comportamento predefinito)")
    return parser


def _motor_ids(selection: str, controller: MotorController) -> list[str]:
    """Valida l'intero gruppo prima di modificare qualsiasi motore."""
    known = [state.motor_id for state in controller.snapshot()]
    if selection.lower() == "all":
        return known
    requested = [part.strip() for part in selection.split(",")]
    if not all(requested):
        raise ValueError("specifica almeno un ID motore; evita elementi vuoti")
    if len(requested) != len(set(requested)):
        raise ValueError("lo stesso motore non può comparire più volte")
    unknown = [motor_id for motor_id in requested if motor_id not in known]
    if unknown:
        raise ValueError("ID motore sconosciuto: " + ", ".join(unknown))
    return requested


def _show_status(controller: MotorController) -> None:
    states = controller.snapshot()
    if controller.faulted:
        # Dopo un errore lo zero logico indica la richiesta di spegnimento,
        # non la riuscita delle scritture verso il backend.
        states = controller.snapshot()
        print("GUASTO: stato comandato azzerato; uscite del backend non confermate.")
        print("I valori seguenti non confermano lo spegnimento delle uscite.")
    print("Stato logico virtuale (nessun feedback fisico):")
    print(f"{'Motore':<8} {'Canale':>6} {'Intensità':>10} {'Duty':>8} {'Residuo ms':>12}")
    for state in states:
        remaining = "-" if state.remaining_ms is None else f"{state.remaining_ms:.0f}"
        print(
            f"{state.motor_id:<8} {state.channel:>6} {state.intensity:>10.1f} "
            f"{state.duty_cycle:>7.1%} {remaining:>12}"
        )


def _diagnostic(controller: MotorController, config: SimulationConfig) -> None:
    """Esercita i canali virtuali senza fare affermazioni sull'hardware."""
    controller.stop_all()
    motors = config.motors
    if len(motors) != 16 or len({motor.channel for motor in motors}) != 16:
        raise RuntimeError("il diagnostico richiede 16 motori su 16 canali distinti")
    duration = min(20.0, config.max_duration_ms)
    for motor in motors:
        intensity = min(10.0, motor.max_intensity)
        controller.activate(motor.motor_id, intensity, duration)
        active = next(state for state in controller.snapshot() if state.motor_id == motor.motor_id)
        if active.intensity == 0:
            raise RuntimeError(
                f"{motor.motor_id}: attivazione troppo breve o non osservata; "
                "diagnostico incompleto, riprovare."
            )
        if active.intensity != intensity:
            raise RuntimeError(f"stato virtuale inatteso per {motor.motor_id}")
        if not controller.wait_until_idle(timeout=2.0):
            raise RuntimeError(f"mancato spegnimento temporizzato di {motor.motor_id}")
        if any(state.intensity != 0 for state in controller.snapshot()):
            raise RuntimeError("il diagnostico ha rilevato uscite virtuali ancora attive")
    print("Diagnostico simulato completato: 16 canali verificati, tutte le uscite spente.")
    print("Questa prova non verifica motori, circuiti o parametri elettrici reali.")


def _execute(args: argparse.Namespace, controller: MotorController, config: SimulationConfig) -> None:
    if args.command == "status":
        _show_status(controller)
    elif args.command == "on":
        motors = _motor_ids(args.motors, controller)
        controller.activate_many(motors, args.intensity, args.duration_ms)
        print(f"Attivazione virtuale: {', '.join(motors)}, {args.intensity:g}%, {args.duration_ms:g} ms.")
    elif args.command == "off":
        motors = _motor_ids(args.motors, controller)
        for motor_id in motors:
            controller.deactivate(motor_id)
        print(f"Motori virtuali spenti: {', '.join(motors)}.")
    elif args.command == "set":
        motors = _motor_ids(args.motor, controller)
        if len(motors) != 1:
            raise ValueError("set richiede un solo motore")
        controller.set_intensity(motors[0], args.intensity)
        print(f"Intensità virtuale di {motors[0]} aggiornata a {args.intensity:g}%.")
    elif args.command == "stop":
        controller.stop_all()
        print("STOP: tutte le uscite virtuali di questo processo sono spente.")
    elif args.command == "test":
        _diagnostic(controller, config)


def _shell(controller: MotorController, config: SimulationConfig) -> int:
    parser = build_parser(shell=True)
    print("Comandi: on L1 50 1000 | on L1,R1 40 500 | set L1 30 | off L1 | status | stop | test | help | quit")
    while True:
        try:
            line = input("hamda> ")
        except EOFError:
            print("\nChiusura: tutte le uscite virtuali vengono spente.")
            return 0
        try:
            words = shlex.split(line)
            if not words:
                continue
            args = parser.parse_args(words)
            if args.command in {"quit", "exit"}:
                print("Chiusura: tutte le uscite virtuali vengono spente.")
                return 0
            if args.command == "help":
                parser.print_help()
            else:
                _execute(args, controller, config)
        except ValueError as error:
            print(f"Errore: {error}", file=sys.stderr)
        except SystemExit as error:
            # argparse usa SystemExit anche per --help: la sessione resta aperta.
            if error.code:
                print("Comando non valido. Usa help per vedere la sintassi.", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    """Restituisce un codice di uscita utilizzabile anche da test e script."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except ValueError as error:
        parser.print_usage(sys.stderr)
        print(f"Errore: {error}", file=sys.stderr)
        return 2
    try:
        config = load_config(args.config)
        with MotorController(config, SimulatedBackend()) as controller:
            print("HAMDA — modalità simulata. Nessun motore fisico viene comandato.")
            print(PROCESS_NOTE)
            if args.command in {None, "shell"}:
                return _shell(controller, config)
            _execute(args, controller, config)
            if args.command == "on":
                print("Attesa dello spegnimento temporizzato; Ctrl-C esegue STOP ed esce.")
                if not controller.wait_until_idle():
                    raise RuntimeError("attivazione non terminata correttamente")
                print("Attivazione terminata: tutte le uscite virtuali sono spente.")
        return 0
    except KeyboardInterrupt:
        print("\nInterruzione: chiusura del controller e STOP delle uscite virtuali.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
