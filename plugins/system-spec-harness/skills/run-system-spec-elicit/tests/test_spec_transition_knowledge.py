#!/usr/bin/env python3
"""Knowledge-candidate transition acceptance tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from spec_transition_support import (
    record_foundation_sources,
    valid_foundation as _valid_foundation,
)

SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
TAXONOMY = (
    PLUGIN_ROOT
    / "skills"
    / "ref-system-design-knowledge"
    / "references"
    / "system-category-taxonomy.json"
)


def _load_mod():
    path = SKILL_DIR / "scripts" / "apply-spec-transition.py"
    spec = importlib.util.spec_from_file_location("apply_spec_transition", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_mod()


def _taxonomy() -> dict:
    return json.loads(TAXONOMY.read_text(encoding="utf-8"))


def _set_confirmed_foundation(state) -> None:
    record_foundation_sources(mod, state)
    mod.set_foundation(state, _valid_foundation())


def _knowledge_source() -> dict:
    return {
        "url": "https://www.rfc-editor.org/rfc/rfc6902",
        "official_or_primary": True,
        "checked_at": "2026-07-11T00:00:00Z",
    }


def _deep_knowledge_card() -> dict:
    return {
        "purpose": "オフライン更新競合を利用者の意図を失わず解決する",
        "background": "複数端末が切断中に同じ業務データを変更するため競合が起きる",
        "problems": ["単純な最終書込優先では利用者の更新を失う"],
        "core_concepts": ["因果順序を保持する", "競合を明示的に解決する"],
        "applies_when": ["複数端末がオフラインで同じデータを変更する"],
        "does_not_apply_when": ["常時オンラインで単一writerが保証される"],
        "tradeoffs": ["競合メタデータと同期処理の複雑性が増える"],
        "failure_modes": ["競合を黙って上書きし利用者の更新を失う"],
        "goal_contribution": ["G1のオフライン継続利用とデータ保全に寄与する"],
        "primary_sources": [
            {
                "title": "JSON Patch",
                "publisher_or_author": "IETF",
                "locator": "https://www.rfc-editor.org/rfc/rfc6902",
            }
        ],
        "freshness": {
            "class": "standard-tracked",
            "last_checked": "2026-07-11",
            "review_by": "2027-01-11",
            "triggers": ["標準改訂"],
        },
    }


def _knowledge_candidate(status: str) -> dict:
    candidate = {
        "id": "offline-first-conflict-resolution",
        "topic": "offline-first conflict resolution",
        "status": status,
        "problem": "複数端末のオフライン更新競合を解決する必要がある",
        "serves_goals": ["G1"],
        "source_refs": [],
    }
    if status in {"qualified", "deepened", "promoted"}:
        candidate["source_refs"] = [_knowledge_source()]
    if status in {"deepened", "promoted"}:
        candidate["card"] = _deep_knowledge_card()
    if status == "promoted":
        candidate["curation_ref"] = "ref-system-design-knowledge/references/offline-first.md"
    return candidate


def test_unknown_seed_candidate_discover_qualify_deepen_integration():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    assert state["knowledge_candidates"] == []
    for status in ("discovered", "qualified", "deepened"):
        mod.set_knowledge_candidate(state, _knowledge_candidate(status))
        assert state["knowledge_candidates"][0]["status"] == status
    assert state["knowledge_candidates"][0]["card"]["does_not_apply_when"]
    assert state["knowledge_candidates"][0]["card"]["goal_contribution"]


def test_knowledge_candidate_qualified_requires_official_https_and_checked_at():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    mod.set_knowledge_candidate(state, _knowledge_candidate("discovered"))
    bad = _knowledge_candidate("qualified")
    bad["source_refs"][0]["url"] = "http://example.invalid/blog"
    bad["source_refs"][0]["official_or_primary"] = False
    with pytest.raises(mod.TransitionError, match="HTTPS"):
        mod.set_knowledge_candidate(state, bad)


def test_knowledge_candidate_deepened_requires_complete_card():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    mod.set_knowledge_candidate(state, _knowledge_candidate("discovered"))
    mod.set_knowledge_candidate(state, _knowledge_candidate("qualified"))
    bad = _knowledge_candidate("deepened")
    del bad["card"]["does_not_apply_when"]
    with pytest.raises(mod.TransitionError, match="card.does_not_apply_when"):
        mod.set_knowledge_candidate(state, bad)


def test_knowledge_candidate_rejects_skip_rollback_topic_change_and_dangling_goal():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    with pytest.raises(mod.TransitionError, match="discovered"):
        mod.set_knowledge_candidate(state, _knowledge_candidate("qualified"))
    mod.set_knowledge_candidate(state, _knowledge_candidate("discovered"))
    with pytest.raises(mod.TransitionError, match="1段階前進"):
        mod.set_knowledge_candidate(state, _knowledge_candidate("deepened"))
    changed = _knowledge_candidate("discovered")
    changed["topic"] = "changed topic"
    with pytest.raises(mod.TransitionError, match="stable topic"):
        mod.set_knowledge_candidate(state, changed)
    dangling = _knowledge_candidate("discovered")
    dangling["id"] = "another-candidate"
    dangling["serves_goals"] = ["G999"]
    with pytest.raises(mod.TransitionError, match="実在 goal"):
        mod.set_knowledge_candidate(state, dangling)


def test_knowledge_candidate_promoted_requires_curation_ref():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    for status in ("discovered", "qualified", "deepened"):
        mod.set_knowledge_candidate(state, _knowledge_candidate(status))
    promoted = _knowledge_candidate("promoted")
    del promoted["curation_ref"]
    with pytest.raises(mod.TransitionError, match="curation_ref"):
        mod.set_knowledge_candidate(state, promoted)


def test_cli_set_knowledge_candidate(tmp_path):
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    state_path = tmp_path / "spec-state.json"
    state_path.write_text(mod.dump_state(state), encoding="utf-8")
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(
        json.dumps(_knowledge_candidate("discovered"), ensure_ascii=False), encoding="utf-8"
    )
    assert mod.main(
        [
            "set-knowledge-candidate",
            "--state",
            str(state_path),
            "--candidate",
            str(candidate_path),
        ]
    ) == 0
    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert written["knowledge_candidates"][0]["status"] == "discovered"
