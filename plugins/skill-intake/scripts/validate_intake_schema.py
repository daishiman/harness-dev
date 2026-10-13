#!/usr/bin/env python3
"""intake.json を intake.schema.json (Draft 2020-12) で検証する pre-publish hook.

Usage:
  python3 validate_intake_schema.py <intake.json path>
  echo '{"intake_json": "..."}' | python3 validate_intake_schema.py  # hook stdin mode

Exit codes:
  0  PASS
  1  schema validation error
  2  file not found / IO error
  3  schema file missing
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import _jsonschema_compat as jsonschema

# 単独 install でも解決できるよう plugin-root 起点で算出する ($CLAUDE_PLUGIN_ROOT 優先、
# 無ければ本ファイルの parents[1] = plugins/skill-intake/)。hook pre-publish-schema-validate.py
# と同一の root 解決規約に統一し、repo-root レイアウト (parents[3]) への依存を撤去。
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
SCHEMA_PATH = PLUGIN_ROOT / "references" / "intake.schema.json"


def _resolve_dotted(obj, dotted: str):
    """sections.0_executive_summary.handoff_mode のようなドット式で nested 値を取得。"""
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


_MISSING = object()


def _read_sibling_value(target: Path, rule: dict):
    """intake.json と同じディレクトリの sibling_file から sibling_path の値を読む。読めなければ _MISSING。"""
    sibling = target.parent / rule["sibling_file"]
    try:
        data = json.loads(sibling.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _MISSING
    cur = data
    for part in rule["sibling_path"].split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _check_cross_field_rules(schema: dict, instance: dict, target: Path | None = None) -> list[str]:
    """T6: x-cross-field-rules で宣言した equals / sibling_equals ルールを強制。

    sibling_equals は target (intake.json のパス) の隣のファイルを読む。target が無ければ読めない扱い。
    """
    errors: list[str] = []
    for rule in schema.get("x-cross-field-rules", []):
        operator = rule.get("operator")
        left = _resolve_dotted(instance, rule["left"])
        if operator == "equals":
            right = _resolve_dotted(instance, rule["right"])
            if left is None and right is None:
                continue  # 両方欠落は cross-field エラーではない (schema 側 required で別途検出)
            if left != right:
                errors.append(
                    f"[{rule['id']}] {rule['left']}={left!r} != {rule['right']}={right!r}"
                )
        elif operator == "sibling_equals":
            # left が when_equals のときだけ、隣の sibling_file の値が right と一致することを要求する。
            if left != rule["when_equals"]:
                continue
            actual = _MISSING if target is None else _read_sibling_value(target, rule)
            where = f"{rule['sibling_file']}:{rule['sibling_path']}"
            if actual is _MISSING:
                errors.append(f"[{rule['id']}] {rule['left']}={left!r} だが {where} を読めない (fail-closed)")
            elif type(actual) is not type(rule["right"]) or actual != rule["right"]:
                errors.append(f"[{rule['id']}] {rule['left']}={left!r} だが {where}={actual!r} (期待値 {rule['right']!r})")
    return errors


def _read_target_path(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1]).resolve()
    # hook stdin: {"tool_input": {"file_path": "..."}} or {"intake_json": "..."}
    payload = json.load(sys.stdin)
    candidate = (
        payload.get("intake_json")
        or payload.get("tool_input", {}).get("file_path")
        or payload.get("path")
    )
    if not candidate:
        print("ERROR: target path not provided (argv or stdin)", file=sys.stderr)
        sys.exit(2)
    return Path(candidate).resolve()


def main(argv: list[str]) -> int:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 3

    try:
        target = _read_target_path(argv)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid stdin payload: {exc}", file=sys.stderr)
        return 2

    if not target.exists():
        print(f"ERROR: intake.json not found: {target}", file=sys.stderr)
        return 2

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    instance = json.loads(target.read_text(encoding="utf-8"))

    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))

    cross_errors = _check_cross_field_rules(schema, instance, target)
    if not errors and not cross_errors:
        print(f"PASS: {target} conforms to intake.schema.json (incl. cross-field rules)", file=sys.stderr)
        return 0
    if cross_errors and not errors:
        print(f"FAIL: {target} has {len(cross_errors)} cross-field violations", file=sys.stderr)
        for ce in cross_errors:
            print(f"  - {ce}", file=sys.stderr)
        return 1

    print(f"FAIL: {target} has {len(errors)} schema violations", file=sys.stderr)
    for err in errors[:20]:
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        print(f"  - [{loc}] {err.message}", file=sys.stderr)
    if len(errors) > 20:
        print(f"  ... and {len(errors) - 20} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
