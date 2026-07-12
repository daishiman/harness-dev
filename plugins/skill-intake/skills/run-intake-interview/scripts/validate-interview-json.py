#!/usr/bin/env python3
"""Validate run-intake-interview interview.json against its schema and stop gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path


USAGE = "usage: validate-interview-json.py <interview.json>"
SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCRIPT_DIR.parent / "schemas" / "output.schema.json"
PLUGIN_SCRIPTS = SCRIPT_DIR.parents[2] / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))

try:
    import _jsonschema_compat as jsonschema
except Exception as exc:  # pragma: no cover - import failure is environmental
    print(f"FAIL jsonschema validator unavailable: {exc}", file=sys.stderr)
    sys.exit(2)

AXES = ["出力先", "情報源", "共有相手", "真の課題", "ナレッジ資産"]
INTENT_SLOTS = [
    "input_spec.sources",
    "input_spec.trigger",
    "input_spec.frequency",
    "input_spec.raw_materials",
    "output_spec.sink",
    "output_spec.format",
    "output_spec.granularity",
    "output_spec.audience",
    "output_spec.cadence",
]
PII_HINTS = ("株式会社", "有限会社", "合同会社", " Inc", " LLC", "さん", "様")


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)


def _contains_unmasked_pii(value: str) -> bool:
    if "{{var_" in value:
        return False
    return any(hint in value for hint in PII_HINTS)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"FAIL file not found: {path}", file=sys.stderr)
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    except Exception as exc:
        print(f"FAIL invalid json/schema: {exc}", file=sys.stderr)
        return 2

    if errors:
        for err in errors:
            loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
            print(f"FAIL schema {loc}: {err.message}", file=sys.stderr)
        return 1

    if data.get("five_axes_complete") is not True:
        print("FAIL five_axes_complete must be true", file=sys.stderr)
        return 1
    if data.get("unresolved"):
        print(f"FAIL unresolved must be empty: {data['unresolved']}", file=sys.stderr)
        return 1
    if data.get("filled_ratio") != 1:
        print("FAIL filled_ratio must be 1 when interview is complete", file=sys.stderr)
        return 1
    if bool(data.get("abstract_answers")) != bool(data.get("needs_excavation")):
        print("FAIL needs_excavation must match abstract_answers presence", file=sys.stderr)
        return 1

    row_names = [row.get("name") for row in data.get("five_axes", {}).get("rows", [])]
    if row_names != AXES:
        print(f"FAIL five_axes.rows order must be {AXES}: {row_names}", file=sys.stderr)
        return 1

    intent = data.get("intent_contract", {})
    status = intent.get("slot_status", {}) if isinstance(intent, dict) else {}
    missing = [slot for slot in INTENT_SLOTS if slot not in status]
    unfilled = [
        slot
        for slot in INTENT_SLOTS
        if not isinstance(status.get(slot), dict) or status.get(slot, {}).get("filled") is not True
    ]
    if missing:
        print(f"FAIL intent_contract.slot_status missing slots: {missing}", file=sys.stderr)
        return 1
    if unfilled:
        print(f"FAIL intent_contract has unfilled slots: {unfilled}", file=sys.stderr)
        return 1
    if data.get("pending_probes"):
        print(f"FAIL pending_probes must be empty: {data['pending_probes']}", file=sys.stderr)
        return 1

    rows_by_name = {row.get("name"): row.get("content", "") for row in data.get("five_axes", {}).get("rows", [])}
    output_sink = intent.get("output_spec", {}).get("sink", "")
    input_sources = intent.get("input_spec", {}).get("sources", [])
    if output_sink and rows_by_name.get("出力先") != output_sink:
        print("FAIL five_axes 出力先 must derive from intent_contract.output_spec.sink", file=sys.stderr)
        return 1
    if input_sources and rows_by_name.get("情報源") != " / ".join(input_sources):
        print("FAIL five_axes 情報源 must derive from intent_contract.input_spec.sources joined by ' / '", file=sys.stderr)
        return 1

    leaking = [s for s in _walk_strings(data) if _contains_unmasked_pii(s)]
    if leaking:
        print("FAIL possible unmasked company/person text; replace with {{var_*}}", file=sys.stderr)
        for item in leaking[:5]:
            print(f"  - {item[:120]}", file=sys.stderr)
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
