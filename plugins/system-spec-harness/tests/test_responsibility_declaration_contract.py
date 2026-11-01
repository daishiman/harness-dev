"""SKILL.md の責務宣言が、参照先 prompt が名乗る責務 id と一致することを固定する。

宣言 (SKILL.md frontmatter の `responsibilities`) と参照 (`responsibility_refs`) と
本文 (prompt の `| responsibility | <id> ...`) の三者がずれると、責務集合と anchor 集合を
機械的に突き合わせられなくなる。実際に 3 種のずれが同時に存在していた:

- `run-system-spec-elicit`: R6/R7 が responsibility_refs にだけ在り、責務として名乗っていない
- `run-system-spec-compile`: frontmatter だけ短縮形 (R1) で、prompt 本文は R1-assemble
- `prompts/R7-audit-matrix.md`: responsibility 欄が散文で始まり id を名乗っていない

id とファイル名の stem は原理的に別物なので (`| responsibility |` 欄が散文で始まる
ref kind の prompt のように、stem からは id を復元できない書き方が実在する)、
突き合わせるのは必ず prompt 本文の宣言側にする。ここを stem で照合すると、
命名規約に沿っていても本文の名乗りが違う skill を検出できず、逆に stem と id を
意図的に変えている skill を誤って赤くする。

なお `assign-system-spec-completeness-evaluator` は 2026-08-16 に id を R1/R2 から
R1-score/R2-delegate へ改めた。rubric PG-001/PG-002 が「宣言 id に対応する
prompts/<id>.md が実在すること」と「responsibility_refs との集合一致」を要求するため、
id と stem を揃えるのが両規約の両立解になる。本テストはその揃え方を強制するのではなく、
frontmatter を動かしたときに prompt 本文の名乗りが取り残されないことだけを固定する。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SKILLS = Path(__file__).resolve().parents[1] / "skills"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
DECLARED_ID = re.compile(r"^\|\s*responsibility\s*\|\s*([A-Za-z0-9][A-Za-z0-9\-]*)", re.M)
# harness-creator を正本に実体コピーで配備される skill。参照は repo root 起点で、
# 正本との byte 一致は scripts/lint-vendored-ssot.py、参照経路は scripts/lint-feedback-protocol.py が見る。
VENDORED_SKILLS = frozenset({"run-skill-feedback"})


def _skill_dirs() -> list[Path]:
    return sorted(
        d for d in SKILLS.iterdir() if (d / "SKILL.md").is_file() and d.name not in VENDORED_SKILLS
    )


def _frontmatter(skill: Path) -> dict:
    match = FRONTMATTER.match((skill / "SKILL.md").read_text(encoding="utf-8"))
    assert match, f"{skill.name}: SKILL.md に frontmatter が無い"
    return yaml.safe_load(match.group(1)) or {}


@pytest.mark.parametrize("skill", _skill_dirs(), ids=lambda p: p.name)
def test_responsibility_refs_exist(skill: Path) -> None:
    for ref in _frontmatter(skill).get("responsibility_refs") or []:
        assert (skill / ref).is_file(), f"{skill.name}: 参照先が不在 {ref}"


@pytest.mark.parametrize("skill", _skill_dirs(), ids=lambda p: p.name)
def test_declared_responsibilities_match_prompt_anchors(skill: Path) -> None:
    fm = _frontmatter(skill)
    declared = sorted(r["id"] for r in (fm.get("responsibilities") or []))
    if not declared:
        # ref/assign kind は責務宣言を持たない (N/A escape)。宣言が無いこと自体は違反ではない。
        return
    anchored = []
    for ref in fm.get("responsibility_refs") or []:
        path = skill / ref
        if not path.is_file():
            continue
        match = DECLARED_ID.search(path.read_text(encoding="utf-8"))
        assert match, f"{skill.name}/{ref}: `| responsibility |` 欄が責務 id を名乗っていない"
        anchored.append(match.group(1))
    assert sorted(anchored) == declared, (
        f"{skill.name}: 責務宣言と prompt の名乗りが不一致 "
        f"(宣言のみ={sorted(set(declared) - set(anchored))} / prompt のみ={sorted(set(anchored) - set(declared))})"
    )
