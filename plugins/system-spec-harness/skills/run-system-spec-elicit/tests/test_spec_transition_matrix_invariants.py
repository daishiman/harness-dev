#!/usr/bin/env python3
"""Matrix/progress invariants that must hold across every writer entry point."""
from __future__ import annotations

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
    spec = importlib.util.spec_from_file_location("apply_spec_transition_invariants", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_mod()


def _taxonomy() -> dict:
    return json.loads(TAXONOMY.read_text(encoding="utf-8"))


def _complete_state() -> dict:
    state = mod.init_state(_taxonomy())
    for category, row in state["matrix"].items():
        for platform in row:
            action = {
                "action": "exclude",
                "category": category,
                "platform": platform,
                "reason": "対象外",
            }
            if (category, platform) == ("database", "web"):
                action = {
                    "action": "confirm",
                    "category": category,
                    "platform": platform,
                    "serves_goals": ["G1"],
                }
                mod.apply_turn(
                    state,
                    {
                        "qa_id": "qa-001",
                        "question": "保存方式を確認します。",
                        "answer": "SQLite を使います。",
                        "design_applications": [
                            {
                                "knowledge_ref": "ddd.md#Aggregate",
                                "principle": "Aggregate",
                                "applicability": "applied",
                                "rationale": "保存境界を単一集約として扱う",
                                "tradeoffs": ["境界分割時は再評価する"],
                            }
                        ],
                        "ops": [action],
                    },
                )
                continue
            mod.apply_turn(state, {"ops": [action]})
    assert state["hearing_progress"]["complete"] is True
    return state


def test_reopen_preserves_discarded_trace_and_resyncs_progress() -> None:
    state = _complete_state()
    mod.apply_turn(
        state,
        {
            "ops": [
                {
                    "action": "reopen",
                    "category": "database",
                    "platform": "web",
                    "reason": "要件を再確認",
                    "reopened_at": "2026-01-02T00:00:00Z",
                }
            ]
        },
    )

    assert state["reopen_log"][-1]["discarded"] == {
        "qa_ref": "qa-001",
        "serves_goals": ["G1"],
    }
    assert state["hearing_progress"]["complete"] is False
    assert state["hearing_progress"]["next_question"]


def test_reopen_preserves_optional_serves_intents_when_present() -> None:
    state = _complete_state()
    state["matrix"]["database"]["web"]["serves_intents"] = ["I1"]
    mod.apply_turn(
        state,
        {
            "ops": [
                {
                    "action": "reopen",
                    "category": "database",
                    "platform": "web",
                    "reason": "intent を再確認",
                    "reopened_at": "2026-01-02T00:00:00Z",
                }
            ]
        },
    )
    assert state["reopen_log"][-1]["discarded"]["serves_intents"] == ["I1"]


def test_reopen_records_the_approval_it_discards() -> None:
    # reopen は確定の取り消しなので approval_ref を次のセルへ引き継がない (別の回答に対して
    # 得た承認を再確定セルが継承してしまう)。ただし discarded に載せずに落とすと、承認が
    # あったこと自体が state から消え、再取得が要ると reopen_log から読み取れなくなる。
    state = _complete_state()
    state["approval_log"].append({"id": "appr-900", "summary": "旧回答への承認"})
    mod.apply_turn(
        state,
        {
            "ops": [
                {
                    "action": "set-approval",
                    "category": "database",
                    "platform": "web",
                    "approval_ref": "appr-900",
                }
            ]
        },
    )
    mod.apply_turn(
        state,
        {"ops": [{
            "action": "reopen", "category": "database", "platform": "web",
            "reason": "再確認", "reopened_at": "2026-01-02T00:00:00Z",
        }]},
    )
    assert state["reopen_log"][-1]["discarded"]["approval_ref"] == "appr-900"
    # 引き継がないことも同時に固定する。片方だけだと「記録はあるが継承もしている」を見逃す。
    assert "approval_ref" not in state["matrix"]["database"]["web"]


def test_add_category_resyncs_complete_state() -> None:
    state = _complete_state()
    mod.add_category(state, {"id": "dev-workflow", "label": "開発フロー"})

    assert state["hearing_progress"]["complete"] is False
    assert "dev-workflow" in state["hearing_progress"]["next_question"]


def test_init_rejects_existing_confirmed_matrix_but_accepts_bootstrap() -> None:
    with pytest.raises(mod.TransitionError, match="bootstrap state 専用"):
        mod.init_state(_taxonomy(), _complete_state())

    state = mod.init_state(_taxonomy(), mod.bootstrap_state())
    assert mod.count_unresolved(state) > 0
    assert state["hearing_progress"]["complete"] is False


def test_run_chunk_persists_actual_max_loops() -> None:
    state = mod.init_state(_taxonomy())
    mod.run_chunk(state, [], max_loops=2)
    assert state["hearing_progress"]["max_loops"] == 2
