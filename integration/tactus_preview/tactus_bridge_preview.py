"""Offline preview of explicit TACTUS routes into local and MQTT commands.

SIMULATION ONLY: this module never imports a hardware or network driver and
never sends commands.  A planned value is not evidence that an output changed.

The accompanying demo is fictional.  In particular, its remote pin mapping is
an explicit example, not a correction or discovery of any live TACTUS device.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


POSITIONS = ("front", "right", "back", "left")
MAX_INPUT_BYTES = 64 * 1024
_UNIT_ID = re.compile(r"[0-9]+", re.ASCII)
_TOPIC_PREFIX = re.compile(r"[A-Za-z0-9_-]+", re.ASCII)


class FrameError(ValueError):
    """A frame or routing configuration cannot be interpreted unambiguously."""


def _object(value: object, location: str) -> dict:
    if not isinstance(value, dict):
        raise FrameError(f"{location} must be a JSON object.")
    return value


def _unit_id(value: object, location: str) -> str:
    if not isinstance(value, str) or _UNIT_ID.fullmatch(value) is None:
        raise FrameError(f"{location}: unit IDs must be positive numeric strings.")
    # Avoid converting to int: an otherwise valid ID need not fit a machine
    # integer or Python's configurable decimal-conversion limit.
    canonical = value.lstrip("0")
    if not canonical:
        raise FrameError(f"{location}: unit ID zero is not valid.")
    return canonical


def _unit_order(unit_id: str) -> tuple[int, str]:
    """Numeric ordering of canonical decimal strings, without integer parsing."""
    return len(unit_id), unit_id


def _units(value: object, location: str) -> dict[str, tuple[str, object]]:
    result: dict[str, tuple[str, object]] = {}
    for raw_id, entry in _object(value, location).items():
        unit_id = _unit_id(raw_id, location)
        if unit_id in result:
            raise FrameError(f"{location}: duplicate aliases for unit {unit_id}.")
        result[unit_id] = raw_id, entry
    return {unit_id: result[unit_id] for unit_id in sorted(result, key=_unit_order)}


def _positions(value: object, location: str) -> dict:
    result = _object(value, location)
    if any(position not in POSITIONS for position in result):
        raise FrameError(f"{location}: positions must be front, right, back or left.")
    return result


def _integer(value: object, maximum: int, location: str) -> int:
    # bool subclasses int, but a boolean is not an explicit channel/pin number.
    if type(value) is not int or not 0 <= value <= maximum:
        raise FrameError(f"{location} must be an integer from 0 to {maximum}.")
    return value


def validate_config(config: object) -> dict:
    """Return a new canonical route map, rejecting ambiguous output ownership.

    Every route is explicit. A unit can intentionally mirror to local and
    remote outputs, but alternate spellings of its ID must not create an
    accidental mirror. Empty groups and subsets of positions are permitted.
    """
    config = _object(config, "config")
    if set(config) != {"local_units", "remote_units"}:
        raise FrameError("config requires exactly local_units and remote_units.")
    local = _units(config["local_units"], "local_units")
    remote = _units(config["remote_units"], "remote_units")
    for unit_id in local.keys() & remote.keys():
        if local[unit_id][0] != remote[unit_id][0]:
            raise FrameError(f"config: duplicate aliases for unit {unit_id} across route groups.")

    canonical: dict = {"local_units": {}, "remote_units": {}}
    local_channels: set[int] = set()
    for unit_id, (_, raw_positions) in local.items():
        positions = _positions(raw_positions, f"local unit {unit_id}")
        routes = {}
        for position in POSITIONS:
            if position not in positions:
                continue
            channel = _integer(positions[position], 3, f"local {unit_id}/{position}")
            if channel in local_channels:
                raise FrameError(f"local channel {channel} has more than one route.")
            local_channels.add(channel)
            routes[position] = channel
        canonical["local_units"][unit_id] = routes

    mqtt_topics: set[str] = set()
    for unit_id, (_, raw_entry) in remote.items():
        entry = _object(raw_entry, f"remote unit {unit_id}")
        if set(entry) != {"topic_prefix", "pins"}:
            raise FrameError(f"remote unit {unit_id} requires exactly topic_prefix and pins.")
        prefix = entry["topic_prefix"]
        if not isinstance(prefix, str) or _TOPIC_PREFIX.fullmatch(prefix) is None:
            raise FrameError(f"remote unit {unit_id}: topic_prefix must be a single explicit MQTT level.")
        positions = _positions(entry["pins"], f"remote pins {unit_id}")
        pins = {}
        used_pins: set[int] = set()
        for position in POSITIONS:
            if position not in positions:
                continue
            pin = _integer(positions[position], 255, f"remote {unit_id}/{position}")
            if pin in used_pins:
                raise FrameError(f"remote unit {unit_id}: pin {pin} has more than one position.")
            used_pins.add(pin)
            topic = f"{prefix}/pin/{pin}"
            if topic in mqtt_topics:
                raise FrameError(f"MQTT topic {topic!r} has more than one route.")
            mqtt_topics.add(topic)
            pins[position] = pin
        canonical["remote_units"][unit_id] = {"topic_prefix": prefix, "pins": pins}
    return canonical


def _switch(value: object, location: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise FrameError(f"{location} must be a JSON boolean or a true/false string.")


def _validate_frame(frame: object) -> dict[str, dict[str, bool]]:
    result = {}
    for unit_id, (_, raw_positions) in _units(frame, "frame").items():
        positions = _positions(raw_positions, f"frame unit {unit_id}")
        # Validate every input unit, including units with no configured route.
        result[unit_id] = {
            position: _switch(positions[position], f"frame {unit_id}/{position}")
            for position in POSITIONS
            if position in positions
        }
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise FrameError(f"Duplicate JSON key: {key!r}.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise FrameError(f"Invalid JSON constant: {value}.")


def _decode_json(text: str) -> object:
    if not isinstance(text, str):
        raise FrameError("JSON input must be text.")
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except FrameError:
        raise
    except (ValueError, RecursionError) as error:
        raise FrameError(f"Invalid JSON: {error}") from error


def parse_frame(text: str) -> dict:
    """Parse and validate one complete frame; reject duplicate JSON keys."""
    return _validate_frame(_decode_json(text))


def build_plan(frame: object, config: object) -> dict:
    """Build a full-state plan. Missing configured positions are always OFF.

    All inputs are validated before producing a result. Valid but unmapped
    units have no effect. This function never applies the generated plan.
    """
    routes = validate_config(config)
    state = _validate_frame(frame)
    local = {}
    mqtt = []
    for unit_id, positions in routes["local_units"].items():
        unit_state = state.get(unit_id, {})
        for position, channel in positions.items():
            local[channel] = 255 if unit_state.get(position, False) else 0
    for unit_id, entry in routes["remote_units"].items():
        unit_state = state.get(unit_id, {})
        for position, pin in entry["pins"].items():
            mqtt.append({
                "topic": f"{entry['topic_prefix']}/pin/{pin}",
                "payload": "255" if unit_state.get(position, False) else "0",
            })
    return {"local": local, "mqtt": mqtt}


def _read_text(source: str) -> str:
    """Bound file/stdin reads before decoding JSON (64 KiB per input)."""
    if source == "-":
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        content = stream.read(MAX_INPUT_BYTES + 1)
    else:
        with Path(source).open("rb") as stream:
            content = stream.read(MAX_INPUT_BYTES + 1)
    if isinstance(content, str):
        content = content.encode("utf-8")
    if len(content) > MAX_INPUT_BYTES:
        raise FrameError("Each JSON input is limited to 64 KiB.")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FrameError("JSON input must be UTF-8 text.") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SIMULATION ONLY: preview local/MQTT commands offline; nothing is sent.",
        epilog="Missing units/positions mean OFF. No hardware or network connection is made.",
    )
    parser.add_argument("--demo", action="store_true", help="use the fictional demo (default with no arguments)")
    parser.add_argument("--config", metavar="PATH", help="explicit routing JSON file")
    parser.add_argument("--frame", metavar="PATH", help="frame JSON file, or '-' for stdin (default with --config)")
    args = parser.parse_args(argv)
    if args.demo and (args.config is not None or args.frame is not None):
        parser.error("--demo cannot be combined with --config or --frame")
    if args.frame is not None and args.config is None:
        parser.error("--frame requires an explicit --config")
    demo = args.config is None
    print("SIMULATION ONLY: offline command plan; nothing is sent to hardware or MQTT.", file=sys.stderr)
    try:
        if demo:
            print("FICTIONAL DEMO: routes and pin numbers are unconfirmed examples, not live device settings.", file=sys.stderr)
            config = _decode_json(_read_text(str(Path(__file__).with_name("demo_routes.json"))))
            frame = {"1": {"front": "true", "right": "false", "back": "false", "left": "true"}}
        else:
            config = _decode_json(_read_text(args.config))
            frame = parse_frame(_read_text(args.frame or "-"))
        print(json.dumps(build_plan(frame, config), indent=2))
        return 0
    except (FrameError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
