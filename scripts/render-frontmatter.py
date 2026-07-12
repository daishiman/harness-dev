#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""render-frontmatter.py: brief JSON を読み込み SKILL.md を生成する。

Usage:
  render-frontmatter.py brief.json [--output SKILL.md]

brief JSON の必須キー:
  name        (str)  skill name (kebab-case)
  description (str)  description フィールド
  body        (str)  SKILL.md 本文（frontmatter 以降）

オプションキー:
  cross_platform      (bool)  true のとき OS プリアンブルを本文先頭に挿入
  os_preamble_required (bool) cross_platform の代替名。どちらかが true で挿入
  kind / effect / allowed_tools / disable_model_invocation / user_invocable 等:
    frontmatter に追記される任意フィールド

挿入される OS プリアンブル (14章「共通プリアンブル1行」準拠):
  !`uname -s 2>/dev/null || ver`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OS_PREAMBLE = "!`uname -s 2>/dev/null || ver`\n"

# frontmatter に書き出す任意フィールドのマッピング (brief key -> frontmatter key)
OPTIONAL_FM_FIELDS: dict[str, str] = {
    "when_to_use": "when_to_use",
    "argument_hint": "argument-hint",
    "arguments": "arguments",
    "disable_model_invocation": "disable-model-invocation",
    "user_invocable": "user-invocable",
    "allowed_tools": "allowed-tools",
    "model": "model",
    "effort": "effort",
    "context": "context",
    "agent": "agent",
    "paths": "paths",
    "shell": "shell",
    "cross_platform": "cross_platform",
    "os_preamble_required": "os_preamble_required",
    "kind": "kind",
    "effect": "effect",
    "merge_strategy": "merge_strategy",
    "conflict_policy": "conflict_policy",
    "rubric_refs": "rubric_refs",
    "reference_refs": "reference_refs",
    "script_refs": "script_refs",
    "base": "base",
    "pair": "pair",
}


def needs_os_preamble(brief: dict) -> bool:
    """cross_platform または os_preamble_required が true の場合 True を返す。"""
    cp = brief.get("cross_platform", False)
    opr = brief.get("os_preamble_required", False)
    # str "true" も許容
    def _is_true(v: object) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() == "true"
    return _is_true(cp) or _is_true(opr)


def render(brief: dict) -> str:
    name = brief.get("name", "")
    description = brief.get("description", "")
    body: str = brief.get("body", "")

    lines: list[str] = ["---\n"]
    if name:
        lines.append(f"name: {name}\n")
    if description:
        lines.append(f"description: {description}\n")

    for brief_key, fm_key in OPTIONAL_FM_FIELDS.items():
        val = brief.get(brief_key)
        if val is None:
            continue
        if isinstance(val, list):
            lines.append(f"{fm_key}:\n")
            for item in val:
                lines.append(f"  - {item}\n")
        else:
            lines.append(f"{fm_key}: {val}\n")

    lines.append("---\n\n")

    # OS プリアンブル自動挿入 (B-1: cross_platform/os_preamble_required が true の場合)
    if needs_os_preamble(brief):
        lines.append(OS_PREAMBLE)
        lines.append("\n")

    lines.append(body)
    if body and not body.endswith("\n"):
        lines.append("\n")

    return "".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: render-frontmatter.py brief.json [--output SKILL.md]", file=sys.stderr)
        return 2

    brief_path = Path(args[0])
    if not brief_path.exists():
        print(f"not found: {brief_path}", file=sys.stderr)
        return 2

    output_path: Path | None = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 >= len(args):
            print("--output requires a path argument", file=sys.stderr)
            return 2
        output_path = Path(args[idx + 1])

    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return 1

    content = render(brief)

    if output_path:
        output_path.write_text(content, encoding="utf-8")
        print(f"ok: wrote {output_path}")
    else:
        sys.stdout.write(content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
