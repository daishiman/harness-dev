#!/usr/bin/env python3
# /// script
# name: build_criteria_roster
# purpose: feedback_contract.criteria を持つ全実体 skill を plugins/ から動的探索し、
#          criteria_roster.py (llm-coverage 静的走査用の機械生成名簿) を再生成する。
# inputs:
#   - argv: --write (再生成) / なし (差分表示のみ)
# outputs:
#   - tests/criteria/criteria_roster.py
# contexts: [C, E]
# network: false
# write-scope: tests/criteria/criteria_roster.py
# dependencies: []
# requires-python: ">=3.10"
# ///
"""criteria 検証対象の動的探索と名簿の再生成。

旧 test_all_skills_criteria.py はハードコード32本で、量産された新 skill
(company-master / notion-gmail-send / plugin-dev-planner 等 9本) が検証の
死角に落ちていた。本スクリプトの discover() が唯一の探索正本:

  - plugins/*/skills/*/SKILL.md の実体 (symlink 除外)
  - frontmatter feedback_contract.criteria 非空 (kind 不問。loop-kind に加え
    criteria を持つ assign 評価系も対象)

criteria_roster.py は validate-llm-coverage.py の in_repo 判定
(tests/**/*.py に skill 名が静的出現すること) を満たすための機械生成物。
手編集禁止。discovery と名簿の乖離は test_roster_matches_discovery が
fail-closed に検出する。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROSTER_PATH = Path(__file__).resolve().parent / "criteria_roster.py"

sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402

HEADER = '''"""criteria 検証対象の機械生成名簿 (手編集禁止)。

生成器: tests/criteria/build_criteria_roster.py --write (探索正本は同 discover())。
役割: validate-llm-coverage.py の被覆判定は「criterion id と skill 名が
tests/**/*.py に静的出現するか」を見るため、動的探索だけでは新 skill の被覆が
計測されない。本ファイルが全対象 (plugin, skill, criterion id 集合) を静的
テキストとして固定する。各 id の genuine 検証実体は
test_all_skills_criteria.py::test_criterion_is_genuinely_verified の
parametrized 実行 (inner=決定論 lint exit0 / outer=verdict PASS)。
discovery との乖離は test_roster_matches_discovery が検出し再生成を要求する。
"""

ROSTER: list[tuple[str, str, tuple[str, ...]]] = [
'''


def discover() -> list[tuple[str, str, tuple[str, ...]]]:
    """feedback_contract.criteria を持つ全実体 skill を (plugin, skill, ids) で返す。"""
    found: list[tuple[str, str, tuple[str, ...]]] = []
    for md in sorted((ROOT / "plugins").glob("*/skills/*/SKILL.md")):
        skill_dir = md.parent
        if skill_dir.is_symlink() or md.is_symlink():
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        fc = FC.extract_frontmatter_feedback_contract(text)
        if isinstance(fc, dict) and fc.get("criteria"):
            ids = tuple(
                cid for c in fc["criteria"]
                if (cid := str(c.get("id", "")).strip())
            )
            found.append((skill_dir.parts[-3], skill_dir.name, ids))
    return found


def render(entries: list[tuple[str, str, tuple[str, ...]]]) -> str:
    lines = [HEADER]
    for plugin, skill, ids in entries:
        ids_lit = "(" + ", ".join(f'"{i}"' for i in ids) + ("," if len(ids) == 1 else "") + ")"
        lines.append(f'    ("{plugin}", "{skill}", {ids_lit}),\n')
    lines.append("]\n")
    return "".join(lines)


def main(argv: list[str]) -> int:
    entries = discover()
    content = render(entries)
    if "--write" in argv:
        ROSTER_PATH.write_text(content, encoding="utf-8")
        print(f"OK: {ROSTER_PATH.name} を再生成 ({len(entries)} skills)")
        return 0
    current = ROSTER_PATH.read_text(encoding="utf-8") if ROSTER_PATH.exists() else ""
    if current == content:
        print(f"OK: roster は discovery と一致 ({len(entries)} skills)")
        return 0
    print(
        "STALE: criteria_roster.py が discovery と乖離。"
        "python3 tests/criteria/build_criteria_roster.py --write で再生成してください。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
