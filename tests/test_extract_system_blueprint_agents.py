"""extract-system-blueprint の分析 sub-agent 5 体の frontmatter 契約を検証する。

harness-coverage (agents/mechanical) は agent 名が tests/ 配下で参照されるか coverage レコードで
被覆されるかを見る。本 test は各 esb agent を名前で列挙し、name↔ファイル名一致・kind=agent・
description (skill-description lint と同じ R4 280字/R5 末尾規約)・tools/owner_skill/responsibility_id
の必須契約を実検証することで、agent が harness の一級 artifact として test 被覆される状態を担保する。
"""
from __future__ import annotations

from pathlib import Path

import yaml

AGENTS_DIR = Path(__file__).resolve().parents[1] / "plugins" / "extract-system-blueprint" / "agents"

# esb の分析 sub-agent (C03/C04/C05/C13/C06)。名前をここに列挙することで tests 被覆源にもなる。
ESB_AGENTS = [
    "frontend-surface-analyzer",
    "backend-inference-analyzer",
    "uiux-rationale-analyzer",
    "content-intent-analyzer",
    "architecture-essence-synthesizer",
]

ALLOWED_TAIL = ("使う。", "読む。", "起動する。")


def _frontmatter(name: str) -> dict:
    src = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    assert src.startswith("---"), f"{name}: frontmatter 開始 --- がない"
    _, fm, _body = src.split("---", 2)
    data = yaml.safe_load(fm)
    assert isinstance(data, dict), f"{name}: frontmatter が dict でない"
    return data


def test_all_esb_agents_present():
    found = sorted(p.stem for p in AGENTS_DIR.glob("*.md"))
    assert found == sorted(ESB_AGENTS), f"agent ファイル集合の乖離: {found}"


import pytest


@pytest.mark.parametrize("name", ESB_AGENTS)
def test_esb_agent_contract(name):
    fm = _frontmatter(name)
    assert fm.get("name") == name, f"{name}: frontmatter name 不一致 ({fm.get('name')})"
    assert fm.get("kind") == "agent", f"{name}: kind != agent ({fm.get('kind')})"
    desc = str(fm.get("description", ""))
    assert desc, f"{name}: description 空"
    assert len(desc) <= 280, f"{name}: description {len(desc)} > 280 (R4)"
    assert desc.rstrip().endswith(ALLOWED_TAIL), f"{name}: description 末尾が {ALLOWED_TAIL} でない (R5)"
    assert str(fm.get("tools", "")).strip(), f"{name}: tools 未宣言"
    assert str(fm.get("owner_skill", "")).strip(), f"{name}: owner_skill 未宣言"
    assert str(fm.get("responsibility_id", "")).strip(), f"{name}: responsibility_id 未宣言"
