#!/usr/bin/env python3
# /// script
# name: ubm-write-path-guard
# version: 0.2.0
# purpose: UBM_VAULT_ROOT 配下への Write|Edit|MultiEdit を PreToolUse で検査し、目標設定/
#          保存・Templates/Daily.md の embed 更新・各 vault が自身の scope-protection.md 等で
#          明示的に書込許可している領域(05_Project/ 全体・.claude/skills 等の開発領域)以外の
#          vault 書込を fail-closed(exit2)で阻む。読み取り専用ソースとして保護すべきなのは
#          01_Notes/・02_Configs/(Daily.md除く)・03_Sources/・logs/・.obsidian/ 等、
#          移植元由来のノート/設定領域に限る。vault 外(plugin 同梱 knowledge/*.json 等)への
#          書込は検査対象外で素通しする。
# inputs:
#   - stdin: PreToolUse hook JSON ({tool_name, tool_input.file_path})
#   - env: UBM_VAULT_ROOT (未設定時は保護対象 vault なしとして全許可)
# outputs:
#   - exit: 0=許可 / 2=ブロック(stderr に理由)。stdin 解釈不能・対象 tool の
#           file_path 欠落も fail-closed で 2 (計画 C04 exit_semantics=fail-closed-exit2)。
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""PreToolUse(Write|Edit|MultiEdit) 動的ガード — 移植元 vault の破壊的書込を防ぐ。

guard は UBM_VAULT_ROOT 配下への Write|Edit|MultiEdit のみを検査対象とする。vault 内では
  - 05_Project/  (UBM目標設定に限らず、各種プロジェクト成果物の出力先全般)
  - .claude/skills/ .claude/agents/ .claude/commands/ .claude/rules/ .claude/prompts/
    (スキル・エージェント・コマンド等の開発領域)
  - 02_Configs/Templates/Daily.md  (embed 参照更新)
のみ許可し、それ以外の vault パス（01_Notes/・02_Configs/の他ファイル・03_Sources/・
logs/・.obsidian/ 等、移植元由来のノート/設定領域）への書込を fail-closed で阻む。
plugin 同梱 dir (plugins/ubm-goal-setting/knowledge/*.json 等) への knowledge-extractor
の書込は vault 外ゆえ guard 対象外で妨げない。
"""
from __future__ import annotations

import json
import os
import sys

GUARDED_TOOLS = {"Write", "Edit", "MultiEdit"}
# vault-root 相対で許可するパス
ALLOWED_PREFIXES = (
    "05_Project/",
    ".claude/skills/",
    ".claude/agents/",
    ".claude/commands/",
    ".claude/rules/",
    ".claude/prompts/",
)
ALLOWED_EXACT = ("02_Configs/Templates/Daily.md",)


def _norm(path: str) -> str:
    return os.path.normpath(os.path.abspath(os.path.expanduser(path)))


def _under(child: str, parent: str) -> bool:
    """child が parent 配下 (同一含む) か。"""
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False  # ドライブ違い等


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # fail-closed: 解釈不能な入力を素通しすると検査自体を迂回できてしまう
        # (計画 C04 exit_semantics=fail-closed-exit2 / fail_closed=true)
        sys.stderr.write(
            "ubm-write-path-guard: stdin の hook JSON を解釈できないため fail-closed で阻止しました。\n"
        )
        return 2

    tool = payload.get("tool_name", "")
    if tool not in GUARDED_TOOLS:
        return 0

    ti = payload.get("tool_input") or {}
    file_path = ti.get("file_path") or ti.get("path") or ""
    if not file_path:
        # fail-closed: 対象 tool なのに検査すべきパスが特定できない → 素通しは迂回穴
        sys.stderr.write(
            f"ubm-write-path-guard: {tool} の tool_input に file_path が無く検査不能のため"
            " fail-closed で阻止しました。\n"
        )
        return 2

    vault = os.environ.get("UBM_VAULT_ROOT", "").strip()
    if not vault:
        return 0  # 保護対象 vault が未設定 → 検査しない (guard は vault 配下のみが責務)

    vault_abs = _norm(vault)
    target = _norm(file_path)

    if not _under(target, vault_abs):
        return 0  # vault 外 (plugin 同梱 dir 等) は検査対象外

    rel = os.path.relpath(target, vault_abs).replace(os.sep, "/")
    if any(rel.startswith(p) for p in ALLOWED_PREFIXES):
        return 0
    if rel in ALLOWED_EXACT:
        return 0

    # vault 配下だが許可リスト外 → fail-closed
    sys.stderr.write(
        "ubm-write-path-guard: vault 配下の保護パスへの書込を阻止しました。\n"
        f"  対象: {rel}\n"
        "  許可: 05_Project/ 配下 / .claude/skills|agents|commands|rules|prompts/ 配下"
        " / 02_Configs/Templates/Daily.md のみ。\n"
        "  01_Notes/・02_Configs/(Daily.md除く)・03_Sources/・logs/・.obsidian/ 等、"
        "移植元由来の領域は読み取り専用ソースです (フォーク・複製・改変禁止)。\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
