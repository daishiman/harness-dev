from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins" / "dev-graph"
INVENTORY = ROOT / "plugin-plans" / "dev-graph" / "component-inventory.json"
COMPONENT_IDS = {"C01", "C02", "C03", "C04", "C05", "C14", "C15", "C18", "C19"}
WIRING_TOKENS = {
    "intermediate.jsonl",
    "original_goal",
    "original_goal_hash",
    "merged_directive_for_next",
    "required_keys",
    "hashlib.sha256",
}


def _components() -> list[dict]:
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return [item for item in data["components"] if item["id"] in COMPONENT_IDS]


def _skill_text(component: dict) -> str:
    return (PLUGIN / "skills" / component["name"] / "SKILL.md").read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n")
    return yaml.safe_load(text.split("\n---\n", 1)[0][4:])


@pytest.mark.parametrize("component", _components(), ids=lambda item: item["id"])
def test_run_skill_frontmatter_is_inventory_exact(component: dict) -> None:
    text = _skill_text(component)
    fm = _frontmatter(text)

    assert fm["combinators"] == component["combinators"]
    assert fm["goal_seek"] == component["goal_seek"]
    assert fm["feedback_contract"] == {
        "max_iterations": 3,
        "criteria": component["feedback_contract"]["criteria"],
    }
    assert [item["id"] for item in fm["responsibilities"]] == [
        item["id"] for item in component["responsibilities"]
    ]
    for actual, expected in zip(fm["responsibilities"], component["responsibilities"], strict=True):
        assert actual["prompt_required"] is expected["prompt_required"]
        assert actual["summary"] == expected["summary"]

    required = [item for item in component["responsibilities"] if item["prompt_required"]]
    expected_refs = [f"prompts/{item['id']}.md" for item in required]
    assert fm["responsibility_refs"] == expected_refs
    assert {"Skill", "Agent", "AskUserQuestion"} <= set(fm["allowed-tools"])
    assert any(
        item["loop_scope"] == "outer" and item["verify_by"] == "live-trial"
        for item in fm["feedback_contract"]["criteria"]
    )


@pytest.mark.parametrize("component", _components(), ids=lambda item: item["id"])
def test_run_skill_has_executable_goal_seek_wiring(component: dict) -> None:
    text = _skill_text(component)
    assert "## ゴールシーク実行" in text
    assert "### 完了チェックリスト" in text
    assert "### ゴールシーク配線" in text
    assert "### ゴールシーク検証" in text
    assert len(re.findall(r"^- \[ \] ", text, flags=re.MULTILINE)) >= 4
    assert WIRING_TOKENS <= {token for token in WIRING_TOKENS if token in text}


@pytest.mark.parametrize("component", _components(), ids=lambda item: item["id"])
def test_required_responsibility_prompts_are_concrete_and_one_to_one(component: dict) -> None:
    skill_dir = PLUGIN / "skills" / component["name"]
    fm = _frontmatter(_skill_text(component))
    prompt_paths = [skill_dir / ref for ref in fm["responsibility_refs"]]
    assert set(prompt_paths) == set((skill_dir / "prompts").glob("*.md"))

    layer2_contracts: set[str] = set()
    required = [item for item in component["responsibilities"] if item["prompt_required"]]
    for responsibility, path in zip(required, prompt_paths, strict=True):
        body = path.read_text(encoding="utf-8")
        assert responsibility["id"] in body
        assert responsibility["summary"] in body
        for layer in range(1, 8):
            assert re.search(rf"^## Layer {layer}:", body, flags=re.MULTILINE)
        for heading in ("入力契約", "出力契約", "責務境界", "受入条件"):
            assert f"### {heading}" in body
        match = re.search(r"^## Layer 2:.*?(?=^## Layer 3:)", body, flags=re.MULTILINE | re.DOTALL)
        assert match
        assert match.group(0) not in layer2_contracts
        layer2_contracts.add(match.group(0))
