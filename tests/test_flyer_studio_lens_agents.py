"""flyer-studio の専門レンズ 3 体の frontmatter と呼出契約を検証する。

stage-common の「専門レンズの共通規則」は、レンズがコマンドを実行せず、さらに SubAgent を起動せず、
受け取った画像・資料の所見だけを返すことを定める。本 test は各レンズを名前で列挙し、
name↔ファイル名一致・kind=agent・description (R4 280字/R5 末尾規約)・tools が読み取りだけであること・
共通規則との相互リンクを実検証する。名前の列挙は harness-coverage (agents/mechanical) の tests 被覆源にもなる。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "flyer-studio"
AGENTS_DIR = PLUGIN / "agents"
STAGE_COMMON = PLUGIN / "references" / "stage-common.md"

# 構図・文字・色の専門レンズ。名前をここに列挙することで tests 被覆源にもなる。
LENS_AGENTS = [
    "flyer-composition-reviewer",
    "flyer-typography-reviewer",
    "flyer-color-reviewer",
]

# コマンド実行 (Bash)・成果物の編集 (Write/Edit)・SubAgent 起動 (Agent/Task) を持たせない。
READ_ONLY_TOOLS = {"Read", "Glob", "Grep"}
ALLOWED_TAIL = ("使う。", "読む。", "起動する。")
COMMON_RULE_LINK = "../references/stage-common.md#専門レンズの共通規則"


def _split(name: str) -> tuple[dict, str]:
    src = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    assert src.startswith("---"), f"{name}: frontmatter 開始 --- がない"
    _, fm, body = src.split("---", 2)
    data = yaml.safe_load(fm)
    assert isinstance(data, dict), f"{name}: frontmatter が dict でない"
    return data, body


def test_all_lens_agents_present():
    found = sorted(p.stem for p in AGENTS_DIR.glob("*.md"))
    assert found == sorted(LENS_AGENTS), f"plugin 直下 agent の集合が乖離: {found}"


@pytest.mark.parametrize("name", LENS_AGENTS)
def test_lens_agent_frontmatter(name):
    fm, _ = _split(name)
    assert fm.get("name") == name, f"{name}: frontmatter name 不一致 ({fm.get('name')})"
    assert fm.get("kind") == "agent", f"{name}: kind != agent ({fm.get('kind')})"
    desc = str(fm.get("description", ""))
    assert desc, f"{name}: description 空"
    assert len(desc) <= 280, f"{name}: description {len(desc)} > 280 (R4)"
    assert desc.rstrip().endswith(ALLOWED_TAIL), f"{name}: description 末尾が {ALLOWED_TAIL} でない (R5)"


@pytest.mark.parametrize("name", LENS_AGENTS)
def test_lens_agent_tools_are_read_only(name):
    fm, _ = _split(name)
    tools = {t.strip() for t in str(fm.get("tools", "")).split(",") if t.strip()}
    assert tools, f"{name}: tools 未宣言"
    extra = tools - READ_ONLY_TOOLS
    assert not extra, f"{name}: 専門レンズの共通規則に反する tools {sorted(extra)}"


@pytest.mark.parametrize("name", LENS_AGENTS)
def test_lens_agent_links_common_rule_both_ways(name):
    _, body = _split(name)
    assert COMMON_RULE_LINK in body, f"{name}: 本文が専門レンズの共通規則を指していない"
    common = STAGE_COMMON.read_text(encoding="utf-8")
    assert f"../agents/{name}.md" in common, f"stage-common が {name} を指していない"
