#!/usr/bin/env python3
# /// script
# name: validate-system-blueprint
# purpose: doc-emit の blueprint.json を system-blueprint.schema.json 正本へ検証する。
# inputs:
#   - argv: --blueprint <json> [--schema <json>] | --self-test
# outputs:
#   - stdout: validation summary JSON
#   - stderr: schema violations
#   - exit: 0=valid, 1=invalid, 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [jsonschema optional; top-level fail-closed fallback]
# requires-python: ">=3.10"
# ///
"""Validate emitted blueprints against the canonical JSON Schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path


SCHEMA = Path(__file__).with_name("system-blueprint.schema.json")
CONFIDENCE_SCHEMA = Path(__file__).with_name("fact-inference-confidence.schema.json")


def _load_unique(path: Path) -> dict:
    def no_duplicates(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out

    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def validate(blueprint: dict, schema: dict) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        required = set(schema.get("required") or [])
        allowed = set((schema.get("properties") or {}).keys())
        errors = [f"required property missing: {key}" for key in sorted(required - blueprint.keys())]
        if schema.get("additionalProperties") is False:
            errors += [f"additional property not allowed: {key}" for key in sorted(blueprint.keys() - allowed)]
        return errors
    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    confidence = _load_unique(CONFIDENCE_SCHEMA)
    base_id = str(schema.get("$id") or "")
    confidence_id = str(confidence.get("$id") or "")
    resolved_relative = base_id.rsplit("/", 1)[0] + "/fact-inference-confidence.schema.json"
    resolver = jsonschema.RefResolver.from_schema(
        schema,
        store={confidence_id: confidence, resolved_relative: confidence},
    )
    return [
        f"{'.'.join(str(x) for x in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(
            validator(schema, resolver=resolver).iter_errors(blueprint),
            key=lambda e: list(e.absolute_path),
        )
    ]


def self_test() -> int:
    schema = _load_unique(SCHEMA)
    errors = validate({}, schema)
    if not any("metadata" in error for error in errors):
        print("self-test failed: required property was not rejected", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as td:
        duplicate = Path(td) / "duplicate.json"
        duplicate.write_text('{"x":1,"x":2}\n', encoding="utf-8")
        try:
            _load_unique(duplicate)
        except ValueError:
            pass
        else:
            print("self-test failed: duplicate JSON key was accepted", file=sys.stderr)
            return 1
    digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    print(json.dumps({"valid": True, "self_test": "PASS", "schema_sha256": digest}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint")
    parser.add_argument("--schema", default=str(SCHEMA))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.blueprint:
        parser.error("--blueprint is required unless --self-test is used")
    try:
        schema = _load_unique(Path(args.schema))
        blueprint = _load_unique(Path(args.blueprint))
        errors = validate(blueprint, schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"validation input error: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(json.dumps({"valid": False, "errors": len(errors)}))
        return 1
    print(json.dumps({"valid": True, "errors": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
