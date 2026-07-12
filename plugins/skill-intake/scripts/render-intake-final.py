#!/usr/bin/env python3
"""Render intake-final.md from per-phase JSON outputs.

Usage:
    python3 render-intake-final.py <output_dir>

output_dir 直下に context.json があればそれを正本として使う。
無ければ kickoff.json / assumption.json / profile.json / purpose.json /
options.json / figures.json / sheet.json / next-action.json / self-update.json
/ summary.json を読んで context にマージする（キー名はそのままトップレベルに置く）。

検証:
  1. intake-final-schema.json による JSON Schema 検証
  2. options.groups[].options[] で adopted:true が各グループ厳密に1件であることを追加検証

出力: <output_dir>/intake-final.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from _vendor import activate as _activate_vendor
_activate_vendor()
import _jsonschema_compat as jsonschema
try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except Exception as exc:
    Environment = FileSystemLoader = StrictUndefined = None
    _JINJA_IMPORT_ERROR = exc
else:
    _JINJA_IMPORT_ERROR = None

REFERENCES = (
    Path(__file__).resolve().parent.parent
    / "references"
)
TEMPLATE_NAME = "intake-final-template.md.tmpl"
SCHEMA_NAME = "intake-final-schema.json"

AUTO_MERGE_KEYS = [
    "meta",
    "executive_summary",
    "assumption",
    "profile",
    "purpose",
    "options",
    "figures",
    "five_axes",
    "design_decisions",
    "open_questions",
    "handoff",
    "self_update",
    "artifacts",
]


def load_context(output_dir: Path) -> dict:
    ctx_path = output_dir / "context.json"
    if ctx_path.exists():
        return json.loads(ctx_path.read_text(encoding="utf-8"))

    merged: dict = {}
    for json_file in sorted(output_dir.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if key in AUTO_MERGE_KEYS and key not in merged:
                merged[key] = value
    return merged


def validate_adopted_uniqueness(context: dict) -> list[str]:
    errors: list[str] = []
    groups = context.get("options", {}).get("groups", [])
    for group in groups:
        adopted_count = sum(1 for opt in group.get("options", []) if opt.get("adopted"))
        if adopted_count != 1:
            errors.append(
                f"options group '{group.get('title')}' has {adopted_count} adopted items (expected 1)"
            )
    return errors


def render(output_dir: Path) -> Path:
    schema = json.loads((REFERENCES / SCHEMA_NAME).read_text(encoding="utf-8"))
    context = load_context(output_dir)

    jsonschema.validate(instance=context, schema=schema)
    extra_errors = validate_adopted_uniqueness(context)
    if extra_errors:
        raise ValueError("adopted uniqueness check failed:\n  - " + "\n  - ".join(extra_errors))

    if Environment is None:
        raise RuntimeError(f"bundled jinja2 unavailable: {_JINJA_IMPORT_ERROR}")
    env = Environment(
        loader=FileSystemLoader(str(REFERENCES)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["json_dumps"] = lambda value: json.dumps(
        value, ensure_ascii=False, sort_keys=True, indent=2
    )
    template = env.get_template(TEMPLATE_NAME)
    rendered = template.render(**context)

    out_path = output_dir / "intake-final.md"
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render-intake-final.py <output_dir>", file=sys.stderr)
        return 2
    output_dir = Path(sys.argv[1]).resolve()
    if not output_dir.is_dir():
        print(f"not a directory: {output_dir}", file=sys.stderr)
        return 2
    out_path = render(output_dir)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
