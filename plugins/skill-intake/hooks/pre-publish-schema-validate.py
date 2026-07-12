#!/usr/bin/env python3
"""pre-publish-schema-validate.py

PreToolUse Bash hook: intake_publish_pipeline.py / publish_notion_page.py / render_notion_page.py
の起動コマンドから intake.json を抽出し、intake.schema.json で検証する。

設計方針 (LS-01/LS-10/MD-01/SS-03 対応):
  - Python stdlib のみ。schema 検証は scripts/_jsonschema_compat.py 経由で行い、bash 委譲しない (.sh 廃止)。
  - exit code を契約違反 (1) と環境不備 (3) と pass-through (0) で厳密に分離。
  - regex は --intake / --intake-file / absolute path / output/<hint>/ を網羅。

Hook input (stdin): {"tool_input": {"command": "..."}, "cwd": "..."}
Exit codes:
  0  pass-through (検証対象外 or PASS)
  1  contract violation (schema FAIL) → PreToolUse は 2 へ昇格させる
  2  block publish (用途別 BLOCK; 本 hook では Wrapper 役)
  3  environment error (validator / schema 不在)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate_intake_schema.py"

TARGET_COMMANDS = (
    "intake_publish_pipeline.py",
    "publish_notion_page.py",
    "render_notion_page.py",
)

INTAKE_PATH_PATTERNS = (
    re.compile(r"--intake(?:-file)?[= ]([^\s]+intake\.json)"),
    re.compile(r"(/[^\s]+intake\.json)"),
    re.compile(r"(output/[^\s]+/intake\.json)"),
    re.compile(r"(fixtures/[^\s]+/intake\.json)"),
)


def _extract_intake_path(command: str) -> str | None:
    for pat in INTAKE_PATH_PATTERNS:
        m = pat.search(command)
        if m:
            return m.group(1)
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # 不明 payload は pass-through (hook 自体の故障防止)

    command = payload.get("tool_input", {}).get("command", "")
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    if not any(t in command for t in TARGET_COMMANDS):
        return 0

    # publish 経路の本体 (publish_notion_page.py / pipeline) は intake.json を --intake で必須に取る。
    # render_notion_page.py は --ctx で context を取り intake.json 検証対象でないため、
    # --intake フラグの有無で「検証対象か」を判別する (無関係な Bash を巻き込まない配慮)。
    declares_intake = re.search(r"--intake(?:-file)?[= ]", command) is not None

    intake_path_str = _extract_intake_path(command)
    if not intake_path_str:
        if declares_intake:
            # 検証対象 (--intake 宣言あり) なのにパスを抽出できない = fail-open 化を防ぐため block。
            print(
                "BLOCK: --intake declared but intake.json path not extractable; "
                "schema validation cannot be skipped silently.",
                file=sys.stderr,
            )
            return 2
        return 0  # --intake を取らない経路 (render --ctx 等) は検証対象外で pass-through

    intake_path = Path(intake_path_str)
    if not intake_path.is_absolute():
        intake_path = (cwd / intake_path).resolve()

    if not intake_path.exists():
        # 検証対象として明示されたファイルが存在しない = 素通りさせず block (fail-closed)。
        print(f"BLOCK: intake.json declared for publish but not found at {intake_path}",
              file=sys.stderr)
        return 2

    if not VALIDATOR.exists():
        print(f"ERROR: validator missing at {VALIDATOR}", file=sys.stderr)
        return 3

    import subprocess

    rc = subprocess.call(
        [sys.executable, str(VALIDATOR), str(intake_path)],
        stdout=sys.stderr,  # PASS/FAIL ログは stderr へ寄せて Claude Code の表示と整合
        stderr=sys.stderr,
    )

    if rc == 0:
        return 0
    if rc == 3:
        print(f"ENV: schema validator environment error rc={rc}", file=sys.stderr)
        return 3
    print(f"BLOCK: intake.schema.json validation failed for {intake_path}", file=sys.stderr)
    return 2  # PreToolUse の block 用 exit code


if __name__ == "__main__":
    sys.exit(main())
