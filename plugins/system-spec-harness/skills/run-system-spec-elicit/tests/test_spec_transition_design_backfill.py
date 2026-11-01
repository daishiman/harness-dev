#!/usr/bin/env python3
"""Design-application backfill tests for the spec-state single writer."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

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
    spec = importlib.util.spec_from_file_location("apply_spec_transition_backfill", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_mod()


def _taxonomy() -> dict:
    return json.loads(TAXONOMY.read_text(encoding="utf-8"))


def _design_applications() -> list[dict]:
    return [{
        "knowledge_ref": "ddd.md#Bounded Context",
        "principle": "Bounded Context",
        "applicability": "applied",
        "rationale": "テスト対象を単一境界として扱う",
        "tradeoffs": ["境界分割時は再評価する"],
    }]


def test_backfill_preserves_qa_and_is_idempotent():
    state = mod.init_state(_taxonomy())
    state["qa_log"].append({
        "id": "qa-legacy",
        "question": "元の質問",
        "answer": "元の回答",
        "legacy_exempt": True,
        "legacy_exempt_reason": "旧契約",
    })

    mod.set_qa_design_applications(state, "qa-legacy", _design_applications())

    qa = state["qa_log"][0]
    assert qa["question"] == "元の質問"
    assert qa["answer"] == "元の回答"
    assert qa["design_applications"] == _design_applications()
    assert qa["design_application_provenance"] == {
        "mode": "legacy_backfill",
        "writer": "set-qa-design-applications",
    }
    assert "legacy_exempt" not in qa
    assert "legacy_exempt_reason" not in qa
    mod.set_qa_design_applications(state, "qa-legacy", _design_applications())


def test_backfill_rejects_conflict_and_unknown_qa():
    state = mod.init_state(_taxonomy())
    state["qa_log"].append({
        "id": "qa-legacy",
        "question": "q",
        "answer": "a",
        "legacy_exempt": True,
        "legacy_exempt_reason": "旧契約",
    })
    mod.set_qa_design_applications(state, "qa-legacy", _design_applications())
    conflicting = copy.deepcopy(_design_applications())
    conflicting[0]["rationale"] = "別の解釈"

    with pytest.raises(mod.TransitionError, match="異なる design_applications の再適用は拒否"):
        mod.set_qa_design_applications(state, "qa-legacy", conflicting)
    with pytest.raises(mod.TransitionError, match="存在しない qa_id"):
        mod.set_qa_design_applications(state, "qa-missing", _design_applications())


def test_backfill_rejects_nonlegacy_and_protects_dialogue_interpretation():
    state = mod.init_state(_taxonomy())
    state["qa_log"].append({"id": "qa-current", "question": "q", "answer": "a"})
    with pytest.raises(mod.TransitionError, match="legacy_exempt=true"):
        mod.set_qa_design_applications(state, "qa-current", _design_applications())

    state["qa_log"][0]["design_applications"] = _design_applications()
    with pytest.raises(mod.TransitionError, match="対話経路として保護"):
        mod.set_qa_design_applications(state, "qa-current", _design_applications())


def test_backfill_rejects_schema_valid_incomplete_or_conflicting_replay():
    state = mod.init_state(_taxonomy())
    state["qa_log"].append({
        "id": "qa-legacy",
        "question": "q",
        "answer": "a",
        "design_application_provenance": {
            "mode": "legacy_backfill",
            "writer": "set-qa-design-applications",
        },
    })
    with pytest.raises(mod.TransitionError, match="design_applications 欠落を検出"):
        mod.set_qa_design_applications(state, "qa-legacy", _design_applications())

    conflicting = copy.deepcopy(_design_applications())
    conflicting[0]["rationale"] = "既存の別解釈"
    state["qa_log"][0]["design_applications"] = conflicting
    with pytest.raises(mod.TransitionError, match="異なる design_applications の再適用は拒否"):
        mod.set_qa_design_applications(state, "qa-legacy", _design_applications())


def test_backfill_rejects_invalid_provenance_from_hand_authored_state():
    state = mod.init_state(_taxonomy())
    state["qa_log"].append({
        "id": "qa-legacy",
        "question": "q",
        "answer": "a",
        "design_applications": _design_applications(),
        "design_application_provenance": {"mode": "dialogue", "writer": "chunk"},
    })
    with pytest.raises(mod.TransitionError, match="既存 provenance の上書きは拒否"):
        mod.set_qa_design_applications(state, "qa-legacy", _design_applications())


def test_cli_set_qa_design_applications(tmp_path):
    state_path = tmp_path / "spec-state.json"
    state = mod.init_state(_taxonomy())
    state["qa_log"].append({
        "id": "qa-legacy",
        "question": "q",
        "answer": "a",
        "legacy_exempt": True,
        "legacy_exempt_reason": "旧契約",
    })
    state_path.write_text(mod.dump_state(state), encoding="utf-8")

    assert mod.main([
        "set-qa-design-applications",
        "--state",
        str(state_path),
        "--qa-id",
        "qa-legacy",
        "--applications",
        json.dumps(_design_applications(), ensure_ascii=False),
    ]) == 0
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["qa_log"][0]["design_applications"] == _design_applications()
