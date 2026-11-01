#!/usr/bin/env python3
"""Foundation, traceability, and decision transition acceptance tests."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from spec_transition_support import (
    effective_source_refs,
    foundation_source_turns,
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
REQUIRED_INFO = SKILL_DIR / "references" / "required-info-catalog.json"


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


def _design_applications() -> list[dict]:
    return [{
        "knowledge_ref": "ddd.md#Bounded Context",
        "principle": "Bounded Context",
        "applicability": "applied",
        "rationale": "テスト対象を単一境界として扱う",
        "tradeoffs": ["境界分割時は再評価する"],
    }]


def _confirmed_state():
    state = mod.init_state(_taxonomy())
    mod.apply_turn(
        state,
        {"qa_id": "qa-001", "question": "q", "answer": "a",
         "design_applications": _design_applications(),
         "ops": [{"action": "confirm", "category": "database", "platform": "web"}]},
    )
    assert state["matrix"]["database"]["web"]["state"] == "確定"
    return state


def _set_confirmed_foundation(state, foundation: dict | None = None) -> None:
    """Record primary sources through chunk before the writer confirms U1--U9."""
    record_foundation_sources(mod, state)
    mod.set_foundation(state, foundation or _valid_foundation())


# --------------------------------------------------------------------------- #
# requirements_foundation (上位概念・要件 C9) の set-foundation op              #
# --------------------------------------------------------------------------- #
def test_init_state_has_empty_foundation():
    state = mod.init_state(_taxonomy())
    rf = state["requirements_foundation"]
    assert rf == mod.empty_foundation()
    assert rf["confirmed"] is False
    assert rf["goals"] == [] and rf["essential_purpose"] == ""
    assert rf["scope"] == {"in": [], "out": []}


def test_set_foundation_confirmed_ok():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    rf = state["requirements_foundation"]
    assert rf["confirmed"] is True
    assert [g["id"] for g in rf["goals"]] == ["G1", "G2"]


def test_current_confirmed_foundation_requires_all_effective_source_refs():
    # 1.1 は opt-in。1.0 の既定 state は qa-foundation-u1..u9 の正規 index へ fallback できる。
    state = mod.init_state(_taxonomy(), schema_version="1.1")
    record_foundation_sources(mod, state)
    foundation = _valid_foundation()
    foundation.pop("effective_source_refs")
    with pytest.raises(mod.TransitionError, match="effective_source_refs"):
        mod.set_foundation(state, foundation)


def test_set_foundation_persists_effective_sources_without_mutating_history():
    state = mod.init_state(_taxonomy())
    record_foundation_sources(mod, state)
    historical = copy.deepcopy(state["qa_log"])
    foundation = _valid_foundation()
    mod.set_foundation(state, foundation)

    assert state["requirements_foundation"]["effective_source_refs"] == effective_source_refs()
    assert state["qa_log"] == historical


def test_confirmed_foundation_value_change_requires_fresh_qa_and_approval_binding():
    """確定値だけを変え、旧QA/承認を新値の根拠として再利用できない。"""
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)

    with pytest.raises(mod.TransitionError, match="U1.*qa_ref.*approval_ref"):
        mod.set_foundation(
            state,
            {"essential_purpose": "利用者入力なしで置換した本質的目的"},
        )


def test_confirmed_foundation_value_change_accepts_fresh_qa_and_approval_binding():
    """新しい利用者QAと承認へ対象Uを付け替えた更新は受理する。"""
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    previous_history = copy.deepcopy(state["qa_log"])
    mod.run_chunk(
        state,
        [
            {
                "qa_id": "qa-foundation-u1-revision",
                "question": "利用者との再確認で U1 は何か",
                "answer": "事業展開を本質的目的として再承認する",
                "source": {"kind": "user-dialogue"},
                "approval_id": "appr-foundation-revision",
                "approval_note": "U1 の変更を利用者が承認した",
                "ops": [],
            }
        ],
        max_loops=5,
    )
    revised = copy.deepcopy(state["requirements_foundation"])
    revised["essential_purpose"] = "事業展開を本質的目的とする"
    revised["approval_ref"] = "appr-foundation-revision"
    revised["effective_source_refs"]["U1"] = {
        "qa_ref": "qa-foundation-u1-revision",
        "approval_ref": "appr-foundation-revision",
    }

    mod.set_foundation(state, revised)

    assert state["requirements_foundation"]["essential_purpose"] == revised["essential_purpose"]
    assert state["requirements_foundation"]["effective_source_refs"]["U1"] == revised[
        "effective_source_refs"
    ]["U1"]
    assert state["qa_log"][: len(previous_history)] == previous_history


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda refs: refs.pop("U9"), "U1-U9"),
        (lambda refs: refs.__setitem__("U10", refs["U9"]), "U1-U9"),
        (lambda refs: refs.__setitem__("U1", "qa-foundation-u1"), "object"),
        (lambda refs: refs["U1"].__setitem__("qa_ref", "qa-missing"), "qa_log に不在"),
        (lambda refs: refs["U1"].__setitem__("approval_ref", "appr-missing"), "approval_log に不在"),
    ],
)
def test_set_foundation_rejects_invalid_effective_source_bindings(mutate, expected):
    state = mod.init_state(_taxonomy())
    record_foundation_sources(mod, state)
    foundation = _valid_foundation()
    refs = effective_source_refs()
    mutate(refs)
    foundation["effective_source_refs"] = refs

    with pytest.raises(mod.TransitionError, match=expected):
        mod.set_foundation(state, foundation)


def test_set_foundation_rejects_non_primary_effective_qa_source():
    state = mod.init_state(_taxonomy())
    record_foundation_sources(mod, state)
    state["qa_log"][0]["source"] = {
        "kind": "harness-remediation",
        "trigger": "review",
    }
    foundation = _valid_foundation()
    with pytest.raises(mod.TransitionError, match="source.kind"):
        mod.set_foundation(state, foundation)


def test_set_foundation_rejects_duplicate_effective_qa_ids():
    state = mod.init_state(_taxonomy())
    record_foundation_sources(mod, state)
    state["qa_log"].append(copy.deepcopy(state["qa_log"][0]))

    with pytest.raises(mod.TransitionError, match="重複"):
        mod.set_foundation(state, _valid_foundation())


def test_set_foundation_rejects_effective_qa_bound_to_the_wrong_u():
    """実在する1件のQAを全Uへ使い回してlineageを偽装できない。"""
    state = mod.init_state(_taxonomy())
    record_foundation_sources(mod, state)
    foundation = _valid_foundation()
    u1_binding = copy.deepcopy(foundation["effective_source_refs"]["U1"])
    foundation["effective_source_refs"] = {
        label: copy.deepcopy(u1_binding)
        for label in (f"U{number}" for number in range(1, 10))
    }

    with pytest.raises(mod.TransitionError, match="U2.*示す"):
        mod.set_foundation(state, foundation)


def _record_shared_u3_u4(state, *, question: str, answer: str) -> dict:
    record_foundation_sources(mod, state)
    mod.run_chunk(
        state,
        [
            {
                "qa_id": "qa-shared-u3-u4",
                "question": question,
                "answer": answer,
                "source": {"kind": "user-dialogue"},
                "ops": [],
            }
        ],
        max_loops=5,
    )
    foundation = _valid_foundation()
    evidence = {
        "U3": "U3 はデータ統合をゴールとする",
        "U4": "U4 は請求漏れ月0件を目標とする",
    }
    for label in ("U3", "U4"):
        foundation["effective_source_refs"][label] = {
            "qa_ref": "qa-shared-u3-u4",
            "approval_ref": "appr-foundation",
            "evidence_quote": evidence[label],
            "evidence_sha256": hashlib.sha256(evidence[label].encode("utf-8")).hexdigest(),
        }
    return foundation


def test_set_foundation_accepts_explicit_shared_qa_with_consumer_evidence():
    state = mod.init_state(_taxonomy())
    foundation = _record_shared_u3_u4(
        state,
        question="利用者との対話で U3 と U4 を共有確認する",
        answer="U3 はデータ統合をゴールとする。U4 は請求漏れ月0件を目標とする。",
    )

    mod.set_foundation(state, foundation)


def test_set_foundation_rejects_shared_qa_when_answer_replaces_bound_evidence():
    state = mod.init_state(_taxonomy())
    foundation = _record_shared_u3_u4(
        state,
        question="利用者との対話で U3 と U4 を共有確認する",
        answer="AI が上位概念をひとつに要約した。",
    )

    with pytest.raises(mod.TransitionError, match="shared qa_ref.*evidence_quote"):
        mod.set_foundation(state, foundation)


def test_set_foundation_rejects_out_of_scope_u_marker_in_shared_question():
    state = mod.init_state(_taxonomy())
    foundation = _record_shared_u3_u4(
        state,
        question="利用者との対話で U3 / U4 / U5 を共有確認する",
        answer="U3 はデータ統合をゴールとする。U4 は請求漏れ月0件を目標とする。",
    )

    with pytest.raises(mod.TransitionError, match="shared qa_ref.*question"):
        mod.set_foundation(state, foundation)


def test_set_foundation_rejects_mixed_approvals_for_one_shared_qa():
    state = mod.init_state(_taxonomy())
    foundation = _record_shared_u3_u4(
        state,
        question="利用者との対話で U3 と U4 を共有確認する",
        answer="U3 はデータ統合をゴールとする。U4 は請求漏れ月0件を目標とする。",
    )
    mod.run_chunk(
        state,
        [
            {
                "qa_id": "qa-other-approval",
                "question": "別の承認が必要か",
                "answer": "別の承認とする",
                "source": {"kind": "user-dialogue"},
                "approval_id": "appr-other",
                "approval_note": "別の承認",
                "ops": [],
            }
        ],
        max_loops=5,
    )
    foundation["effective_source_refs"]["U4"]["approval_ref"] = "appr-other"

    with pytest.raises(mod.TransitionError, match="shared qa_ref.*approval_ref"):
        mod.set_foundation(state, foundation)


def test_set_foundation_rejects_reused_shared_evidence_quote():
    state = mod.init_state(_taxonomy())
    foundation = _record_shared_u3_u4(
        state,
        question="利用者との対話で U3 と U4 を共有確認する",
        answer="U3 はデータ統合をゴールとする。U4 は請求漏れ月0件を目標とする。",
    )
    u3 = foundation["effective_source_refs"]["U3"]
    u4 = foundation["effective_source_refs"]["U4"]
    u4["evidence_quote"] = u3["evidence_quote"]
    u4["evidence_sha256"] = u3["evidence_sha256"]

    with pytest.raises(mod.TransitionError, match="consumer ごとに独立"):
        mod.set_foundation(state, foundation)


def test_set_foundation_rejects_duplicate_effective_approval_ids():
    state = mod.init_state(_taxonomy())
    record_foundation_sources(mod, state)
    duplicate = {"id": "appr-foundation", "note": "重複した承認"}
    state["approval_log"] = [copy.deepcopy(duplicate), copy.deepcopy(duplicate)]

    with pytest.raises(mod.TransitionError, match="重複"):
        mod.set_foundation(state, _valid_foundation())


def test_set_foundation_requires_current_approval_in_effective_bindings():
    state = mod.init_state(_taxonomy())
    record_foundation_sources(mod, state)
    state["approval_log"].append({"id": "appr-older", "note": "旧承認"})
    foundation = _valid_foundation()
    foundation["effective_source_refs"] = effective_source_refs(
        approval_ids=("appr-older",) * 9
    )

    with pytest.raises(mod.TransitionError, match="現行 approval_ref"):
        mod.set_foundation(state, foundation)


def test_written_foundation_source_indexes_are_append_only_and_preserve_matrix():
    """書面要件を1論点の qa_log 索引として残しても matrix を変更しない。"""
    state = mod.init_state(_taxonomy())
    matrix_before = copy.deepcopy(state["matrix"])
    source_indexes = foundation_source_turns(written=True)

    # chunk は上限5なので、書面索引も通常の resume 契約で 2 回に分けて記録する。
    assert mod.run_chunk(state, source_indexes, max_loops=5) == 5
    assert mod.run_chunk(state, source_indexes[5:], max_loops=5) == 4
    assert state["matrix"] == matrix_before
    assert [entry["id"] for entry in state["qa_log"]] == [
        f"qa-foundation-u{number}" for number in range(1, 10)
    ]

    # 同じ入力を再適用しても既存entryを上書き・重複しない (append-only/idempotent)。
    mod.run_chunk(state, source_indexes, max_loops=9)
    assert len(state["qa_log"]) == 9
    mod.set_foundation(state, _valid_foundation())
    assert state["requirements_foundation"]["confirmed"] is True


def test_set_foundation_confirm_rejects_missing_source_index():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError, match="source-index"):
        mod.set_foundation(state, _valid_foundation())


def test_written_source_hash_mismatch_is_rejected_at_record_time():
    # 記録時点で落とす。以前は chunk が source を逐語コピーしていたため digest 不一致の
    # entry が保存でき、confirm まで進んで初めて露見していた。
    state = mod.init_state(_taxonomy())
    written_turns = foundation_source_turns(written=True)
    written_turns[0]["source"]["sha256"] = "0" * 64
    with pytest.raises(mod.TransitionError, match="sha256 が answer 原文と不一致"):
        mod.run_chunk(state, written_turns[:5], max_loops=5)
    assert not state["qa_log"], "拒否した turn の entry を残さない"


def test_set_foundation_confirm_rejects_written_source_hash_mismatch():
    # 記録経路の検査を通過した後に digest が壊れた state (別 writer の退行・手編集の混入) でも、
    # confirm は「利用者原文を索引した」という主張を受理しない。多層で同じ不変則を守る。
    state = mod.init_state(_taxonomy())
    written_turns = foundation_source_turns(written=True)
    assert mod.run_chunk(state, written_turns[:5], max_loops=5) == 5
    assert mod.run_chunk(state, written_turns[5:], max_loops=5) == 4
    state["qa_log"][0]["source"]["sha256"] = "0" * 64
    with pytest.raises(mod.TransitionError, match="sha256 が answer 原文と不一致"):
        mod.set_foundation(state, _valid_foundation())


def test_set_foundation_confirm_requires_essential_purpose():
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    f["essential_purpose"] = "   "
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, f)


def test_set_foundation_confirm_requires_background():
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    f["background"] = ""
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, f)


def test_set_foundation_confirm_requires_goals():
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    f["goals"] = []
    f["concrete_intents"] = []  # G1 参照が dangling にならないよう除去
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, f)


@pytest.mark.parametrize(
    "field,empty",
    [
        ("objectives", []),
        ("success_criteria", []),
        ("stakeholders", []),
        ("scope", {"in": [], "out": []}),
        ("constraints", []),
        ("concrete_intents", []),
    ],
)
def test_set_foundation_confirm_requires_all_u1_u9(field, empty):
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    f[field] = empty
    with pytest.raises(mod.TransitionError, match=field):
        mod.set_foundation(state, f)


def test_set_foundation_accepts_explicit_na_with_reason():
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    f["constraints"] = {"status": "not_applicable", "reason": "制約なしをユーザー確認済み"}
    _set_confirmed_foundation(state, f)
    assert state["requirements_foundation"]["confirmed"] is True


# F1: confirmed はユーザー合意の approval_ref (approval_log 実在) を機械証跡として要求する
def test_set_foundation_confirm_requires_approval_ref():
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    del f["approval_ref"]
    del f["approval_note"]
    with pytest.raises(mod.TransitionError, match="approval_ref"):
        mod.set_foundation(state, f)


def test_set_foundation_confirm_rejects_dangling_approval_ref():
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    del f["approval_note"]  # 自動登録させない → approval_log に実在しない参照
    f["approval_ref"] = "appr-nonexistent"
    with pytest.raises(mod.TransitionError, match="approval_log に不在"):
        mod.set_foundation(state, f)


def test_set_foundation_registers_approval_from_note():
    state = mod.init_state(_taxonomy())
    assert state["approval_log"] == []
    _set_confirmed_foundation(state)
    assert mod._has_entry(state["approval_log"], "appr-foundation")
    rf = state["requirements_foundation"]
    assert rf["approval_ref"] == "appr-foundation"
    assert "approval_note" not in rf  # 承認本文は approval_log が持つ (foundation へは保存しない)


# F2: U1-U3 (essential_purpose/background/goals) は N/A 不可 (値必須)。"目的が N/A" を弾く
@pytest.mark.parametrize("field", ["essential_purpose", "background", "goals"])
def test_set_foundation_confirm_rejects_na_for_u1_u3(field):
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    f[field] = {"status": "not_applicable", "reason": "N/A にはできないはず"}
    if field == "goals":
        f["concrete_intents"] = []  # goals 消滅で intent.serves が dangling にならないよう除去
    with pytest.raises(mod.TransitionError, match=field):
        mod.set_foundation(state, f)


def test_bootstrap_then_foundation_then_init_preserves_foundation_and_decisions():
    state = mod.bootstrap_state()
    _set_confirmed_foundation(state)
    state["decisions"] = [{"id": "D-bootstrap"}]
    initialized = mod.init_state(_taxonomy(), state)
    assert initialized["requirements_foundation"] == state["requirements_foundation"]
    assert initialized["decisions"] == [{"id": "D-bootstrap"}]
    assert initialized["matrix"]["database"]["web"]["state"] == "未収集"


def test_set_foundation_unconfirmed_allows_empty():
    # confirmed=False なら未完成 (空) の上位概念でも保存できる (途中保存)
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, {"essential_purpose": "検討中"})
    rf = state["requirements_foundation"]
    assert rf["confirmed"] is False
    assert rf["essential_purpose"] == "検討中"


def test_set_foundation_rejects_unknown_key():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, {"nonsense": 1})


def test_set_foundation_rejects_goal_without_id_and_dupe():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, {"goals": [{"text": "id 無し"}]})
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, {"goals": [{"id": "G1", "text": "a"}, {"id": "G1", "text": "b"}]})


def test_set_foundation_rejects_dangling_intent_serves():
    state = mod.init_state(_taxonomy())
    f = _valid_foundation()
    f["concrete_intents"] = [{"id": "I1", "text": "x", "serves": ["G9"]}]  # G9 不在
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, f)


def test_set_foundation_partial_merge_preserves_prior():
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, {"essential_purpose": "目的A"})
    mod.set_foundation(state, {"background": "背景B"})
    rf = state["requirements_foundation"]
    assert rf["essential_purpose"] == "目的A"  # 先の設定が保持される
    assert rf["background"] == "背景B"


def test_set_foundation_rejects_non_object():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.set_foundation(state, [1, 2])


# --------------------------------------------------------------------------- #
# serves_goals トレース (confirm 付随 / set-serves op)                          #
# --------------------------------------------------------------------------- #
def test_confirm_with_serves_goals():
    state = mod.init_state(_taxonomy())
    mod.apply_turn(state, {"qa_id": "qa-001", "question": "q", "answer": "a"})
    mod.apply_cell_op(
        state,
        {"action": "confirm", "category": "database", "platform": "web",
         "qa_ref": "qa-001", "serves_goals": ["G1", "G1", "G2"]},
    )
    assert state["matrix"]["database"]["web"] == {
        "state": "確定", "qa_ref": "qa-001", "serves_goals": ["G1", "G2"],
    }


def test_set_serves_on_confirmed_cell():
    state = _confirmed_state()  # database.web = 確定 (serves_goals 無し)
    mod.apply_cell_op(
        state, {"action": "set-serves", "category": "database", "platform": "web", "serves_goals": ["G1"]}
    )
    cell = state["matrix"]["database"]["web"]
    assert cell["state"] == "確定"  # state は 確定 のまま (rollback でない)
    assert cell["serves_goals"] == ["G1"]


def test_set_serves_requires_confirmed_cell():
    state = mod.init_state(_taxonomy())  # 未収集
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "set-serves", "category": "database", "platform": "web", "serves_goals": ["G1"]}
        )


def test_set_serves_requires_nonempty_and_valid():
    state = _confirmed_state()
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(state, {"action": "set-serves", "category": "database", "platform": "web", "serves_goals": []})
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(state, {"action": "set-serves", "category": "database", "platform": "web", "serves_goals": [""]})
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(state, {"action": "confirm", "category": "auth", "platform": "web", "qa_ref": "q", "serves_goals": "G1"})


def test_cli_set_foundation_string_and_file(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    record_foundation_sources(mod, state)
    state_path.write_text(mod.dump_state(state), encoding="utf-8")
    inline = json.dumps(_valid_foundation())
    assert mod.main(["set-foundation", "--state", str(state_path), "--foundation", inline]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["requirements_foundation"]["confirmed"] is True
    # ファイル入力経路
    ffile = tmp_path / "foundation.json"
    # file path の読込だけを検証する。確定値の変更は別テストで新QA/承認を伴わせる。
    ffile.write_text(json.dumps({"stakeholders": ["経理チーム"]}), encoding="utf-8")
    assert mod.main(["set-foundation", "--state", str(state_path), "--foundation", str(ffile)]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["requirements_foundation"]["stakeholders"] == ["経理チーム"]


def _valid_decision(status="recommended_pending_confirmation") -> dict:
    options = [
        {
            "id": "free-managed", "label": "managed無料枠",
            "cost_model": {
                "category": "free", "amount": 0, "currency": "JPY",
                "billing_period": "month", "tco": "無料枠内は月額0円、超過後は従量課金",
            },
            "free_tier_limits": "1万MAU", "goal_fit": "短期導入に適合", "pros": ["運用容易"],
            "security_fit": "managed更新とMFAで要件を満たす",
            "cons": ["上限後課金"], "risks": ["価格改定"], "lock_in": "中",
            "ops_burden": "低", "evidence_refs": ["https://vendor.example/pricing"],
        },
        {
            "id": "oss", "label": "OSS",
            "cost_model": {
                "category": "low-cost", "amount": 1000, "currency": "JPY",
                "billing_period": "month", "tco": "月額基盤費に保守工数を加算",
            },
            "free_tier_limits": "制限なし", "goal_fit": "内製運用時に適合", "pros": ["自由度"],
            "security_fit": "内製で脆弱性更新を期限内に適用する場合に適合",
            "cons": ["保守必要"], "risks": ["更新遅延"], "lock_in": "低",
            "ops_burden": "高", "evidence_refs": ["https://project.example/docs"],
        },
    ]
    return {
        "id": "D1", "question": "認証基盤をどれにするか", "status": status,
        "options": options,
        "recommendation": {
            "option_id": "free-managed", "rationale": "無料枠内で運用負荷が低い",
            "caveats": ["上限監視"], "confidence": "medium",
            "latest_checked_at": "2026-07-11T00:00:00Z",
            "comparison_basis": {
                "goal_fit": "短期導入目標に最も適合", "tco": "無料枠内の総費用が最小",
                "security": "managed更新とMFAを利用可能", "operations": "保守負荷が低い",
                "lock_in": "中程度の移行費を許容できる",
            },
        },
        "serves_goals": ["G1"], "user_decision": None,
    }


def test_set_decision_recommendation_stays_pending_until_user_confirmation():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    decision = _valid_decision()
    mod.set_decision(state, decision)
    assert state["decisions"][0]["status"] == "recommended_pending_confirmation"
    assert state["decisions"][0]["user_decision"] is None


def test_set_decision_confirmed_requires_user_decision():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    decision = _valid_decision("confirmed")
    with pytest.raises(mod.TransitionError, match="user_decision"):
        mod.set_decision(state, decision)
    decision["user_decision"] = {
        "option_id": "free-managed", "confirmed_at": "2026-07-11T01:00:00Z"
    }
    mod.set_decision(state, decision)
    assert state["decisions"][0]["status"] == "confirmed"


def test_set_decision_rejects_too_few_options_and_dangling_goal():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    decision = _valid_decision()
    decision["options"] = decision["options"][:1]
    with pytest.raises(mod.TransitionError, match="2-3"):
        mod.set_decision(state, decision)
    decision = _valid_decision()
    decision["serves_goals"] = ["G9"]
    with pytest.raises(mod.TransitionError, match="実在 goal"):
        mod.set_decision(state, decision)


def test_set_decision_rejects_all_paid_options():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    decision = _valid_decision()
    for option in decision["options"]:
        option["cost_model"]["category"] = "paid"
        option["cost_model"]["amount"] = 5000
    with pytest.raises(mod.TransitionError, match="free または low-cost"):
        mod.set_decision(state, decision)


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda d: d["options"][0].update(evidence_refs=["http://vendor.example/pricing"]), "https URL"),
        (lambda d: d["recommendation"].update(latest_checked_at="not-a-date"), "RFC3339"),
        (lambda d: d["recommendation"]["comparison_basis"].pop("security"), "comparison_basis.security"),
    ],
)
def test_set_decision_rejects_invalid_evidence_date_and_comparison_axis(mutate, match):
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    decision = _valid_decision()
    mutate(decision)
    with pytest.raises(mod.TransitionError, match=match):
        mod.set_decision(state, decision)


def test_set_decision_confirmed_rejects_non_rfc3339_confirmation_time():
    state = mod.init_state(_taxonomy())
    _set_confirmed_foundation(state)
    decision = _valid_decision("confirmed")
    decision["user_decision"] = {"option_id": "free-managed", "confirmed_at": "2026-07-11"}
    with pytest.raises(mod.TransitionError, match="confirmed_at は RFC3339"):
        mod.set_decision(state, decision)


def test_cli_bootstrap_init_preserves_foundation(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["bootstrap", "--out", str(state_path)]) == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    record_foundation_sources(mod, state)
    state_path.write_text(mod.dump_state(state), encoding="utf-8")
    assert mod.main([
        "set-foundation", "--state", str(state_path),
        "--foundation", json.dumps(_valid_foundation()),
    ]) == 0
    assert mod.main([
        "init", "--taxonomy", str(TAXONOMY), "--state", str(state_path), "--out", str(state_path)
    ]) == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["requirements_foundation"]["confirmed"] is True


def test_cli_set_foundation_confirm_gate_returns_1(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    bad = json.dumps({"confirmed": True})  # essential_purpose 等が空
    assert mod.main(["set-foundation", "--state", str(state_path), "--foundation", bad]) == 1


def test_cli_apply_set_serves(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    catalog = json.loads(REQUIRED_INFO.read_text(encoding="utf-8"))
    state["qa_log"].append({
        "id": "qa-001",
        "question": "q",
        "answer": "a",
        "design_applications": _design_applications(),
        # confirm は --required-info の block 項目が確定へ接地していることを求める。
        "required_info_items": sorted(
            it["item_id"] for it in catalog["items"] if it["missing_effect"] == "block"
        ),
    })
    state_path.write_text(mod.dump_state(state), encoding="utf-8")
    confirm = json.dumps({"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-001"})
    assert mod.main(["apply", "--state", str(state_path), "--op", confirm, "--required-info", str(REQUIRED_INFO)]) == 0
    serves = json.dumps({"action": "set-serves", "category": "database", "platform": "web", "serves_goals": ["G1"]})
    assert mod.main(["apply", "--state", str(state_path), "--op", serves]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["matrix"]["database"]["web"]["serves_goals"] == ["G1"]
