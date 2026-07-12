#!/usr/bin/env python3
# /// script
# name: test-spec-transition
# version: 0.1.0
# purpose: run-system-spec-elicit の受入テスト。IN1(validate-coverage-matrix.py が fixture spec-state に exit0)/OUT1(最終 spec-state が未収集0で --require-complete exit0)/5周目 resume の状態保存/単一 transition writer の確定巻き戻し拒否を検証する。
# inputs:
#   - argv: pytest 収集 (引数なし)
# outputs:
#   - pytest 結果
#   - exit: 0=PASS / 非0=FAIL
# contexts: [C, E]
# network: false
# write-scope: none (tmp_path のみ)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""run-system-spec-elicit acceptance tests (IN1 / OUT1 / resume / single-writer)。"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-coverage-matrix.py"
TAXONOMY = (
    PLUGIN_ROOT
    / "skills"
    / "ref-system-design-knowledge"
    / "references"
    / "system-category-taxonomy.json"
)
FIXTURES = SKILL_DIR / "fixtures"
TURNS = FIXTURES / "hearing-turns.json"
GOLDEN_RESUME = FIXTURES / "expected-resume-spec-state.json"
GOLDEN_FINAL = FIXTURES / "expected-final-spec-state.json"


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


def _turns() -> list:
    return json.loads(TURNS.read_text(encoding="utf-8"))


def _run_validator(matrix: Path, require_complete: bool = False, require_foundation: bool = False) -> int:
    argv = [sys.executable, str(VALIDATOR), "--matrix", str(matrix)]
    if require_complete:
        argv.append("--require-complete")
    if require_foundation:
        argv.append("--require-foundation")
    return subprocess.run(argv, capture_output=True, text=True).returncode


# --------------------------------------------------------------------------- #
# IN1: validate-coverage-matrix.py が fixture spec-state に exit0 (loop)       #
# --------------------------------------------------------------------------- #
def test_IN1_validator_exit0_on_resume_fixture():
    assert GOLDEN_RESUME.is_file()
    assert _run_validator(GOLDEN_RESUME) == 0


def test_IN1_validator_exit0_on_final_fixture_loop():
    assert _run_validator(GOLDEN_FINAL) == 0


# --------------------------------------------------------------------------- #
# OUT1: 最終 spec-state が未収集0で --require-complete exit0                    #
# --------------------------------------------------------------------------- #
def test_OUT1_final_require_complete_exit0():
    assert _run_validator(GOLDEN_FINAL, require_complete=True) == 0


def test_resume_require_complete_fails():
    # 未収集残の resume 状態は最終ゲート (require-complete) で必ず落ちる
    assert _run_validator(GOLDEN_RESUME, require_complete=True) == 1


# --------------------------------------------------------------------------- #
# 5周目 resume: 状態保存の決定論部分                                           #
# --------------------------------------------------------------------------- #
def test_five_loop_resume_persists_state():
    state = mod.init_state(_taxonomy())
    processed = mod.run_chunk(state, _turns(), max_loops=5)
    assert processed == 5
    hp = state["hearing_progress"]
    assert hp["loop_count"] == 5
    assert hp["complete"] is False  # 未収集を完了扱いしない
    assert hp["next_question"]  # 非 null (resumable)
    assert mod.count_unresolved(state) == 4
    # golden resume と一致 (決定論)
    assert state == json.loads(GOLDEN_RESUME.read_text(encoding="utf-8"))


def test_resume_then_finish_reaches_complete():
    turns = _turns()
    state = mod.init_state(_taxonomy())
    mod.run_chunk(state, turns, max_loops=5)  # invocation 1
    assert state["hearing_progress"]["complete"] is False
    mod.run_chunk(state, turns[5:], max_loops=5)  # invocation 2 (resume)
    hp = state["hearing_progress"]
    assert hp["complete"] is True
    assert hp["next_question"] is None
    assert mod.count_unresolved(state) == 0
    # C9: 上位概念を確定し全確定セルを serves_goals で anchor する。canonical 最終状態は
    # C7 (マトリクス網羅) と C9 (上位概念トレース) の両方を満たすべき (上位概念なき仕様=drift)。
    mod.set_foundation(state, _valid_foundation())
    for cat, row in state["matrix"].items():
        for pf, cell in row.items():
            if isinstance(cell, dict) and cell.get("state") == "確定":
                mod.apply_cell_op(
                    state,
                    {"action": "set-serves", "category": cat, "platform": pf, "serves_goals": ["G1"]},
                )
    assert state == json.loads(GOLDEN_FINAL.read_text(encoding="utf-8"))
    # canonical 最終状態が anti-drift ゲート (--require-foundation) も通る (C9 end-to-end)
    assert _run_validator(GOLDEN_FINAL, require_foundation=True) == 0


# --------------------------------------------------------------------------- #
# 単一 transition writer: 確定巻き戻し拒否 / reopen 経由のみ確定変更           #
# --------------------------------------------------------------------------- #
def _confirmed_state():
    state = mod.init_state(_taxonomy())
    mod.apply_turn(
        state,
        {"qa_id": "qa-001", "question": "q", "answer": "a",
         "ops": [{"action": "confirm", "category": "database", "platform": "web"}]},
    )
    assert state["matrix"]["database"]["web"]["state"] == "確定"
    return state


def test_confirm_then_exclude_rollback_rejected():
    state = _confirmed_state()
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "exclude", "category": "database", "platform": "web", "reason": "x"}
        )


def test_confirm_then_reconfirm_rejected():
    state = _confirmed_state()
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-999"}
        )


def test_reopen_only_from_confirmed():
    state = mod.init_state(_taxonomy())  # 未収集
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "reopen", "category": "database", "platform": "web", "reason": "x"}
        )


def test_reopen_requires_reason():
    state = _confirmed_state()
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "reopen", "category": "database", "platform": "web"}
        )


def test_reopen_then_reconfirm_allowed():
    state = _confirmed_state()
    mod.apply_cell_op(
        state, {"action": "reopen", "category": "database", "platform": "web", "reason": "追加要件が判明"}
    )
    assert state["matrix"]["database"]["web"]["state"] == "未収集"
    assert state["reopen_log"][-1]["reason"] == "追加要件が判明"
    # reopen 後は confirm へ再遷移できる
    mod.apply_cell_op(
        state, {"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-002"}
    )
    assert state["matrix"]["database"]["web"] == {"state": "確定", "qa_ref": "qa-002"}


def test_confirm_requires_qa_ref():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "confirm", "category": "database", "platform": "web"}
        )


def test_exclude_requires_reason_or_approval():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "exclude", "category": "database", "platform": "mobile"}
        )


def test_unknown_action_and_unknown_cell():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(state, {"action": "frobnicate", "category": "database", "platform": "web"})
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(state, {"action": "confirm", "category": "nope", "platform": "web", "qa_ref": "q"})
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(state, {"action": "confirm", "category": "database", "platform": "nope", "qa_ref": "q"})


# --------------------------------------------------------------------------- #
# 集約 (真理値表) / 初期化                                                     #
# --------------------------------------------------------------------------- #
def test_derive_aggregate_truth_table():
    assert mod.derive_aggregate([]) == "未着手"
    assert mod.derive_aggregate(["未収集", "未収集"]) == "未着手"
    assert mod.derive_aggregate(["対象外", "対象外"]) == "対象外"
    assert mod.derive_aggregate(["確定", "未収集"]) == "収集中"
    assert mod.derive_aggregate(["確定", "対象外"]) == "確定"


def test_init_state_all_uncollected():
    state = mod.init_state(_taxonomy())
    assert state["platforms"] == list(mod.CANONICAL_PLATFORMS)
    for row in state["matrix"].values():
        assert set(row.keys()) == set(mod.CANONICAL_PLATFORMS)
        assert all(c["state"] == "未収集" for c in row.values())
    assert set(state["category_aggregate"].values()) == {"未着手"}
    assert state["hearing_progress"]["next_question"]


def test_init_state_missing_platform_rejected():
    tax = copy.deepcopy(_taxonomy())
    tax["platforms"] = [p for p in tax["platforms"] if p["id"] != "tablet"]
    with pytest.raises(mod.TransitionError):
        mod.init_state(tax)


# --------------------------------------------------------------------------- #
# targets (取得対象一覧) の単一 writer 経路 (set-targets)                       #
# --------------------------------------------------------------------------- #
def test_set_targets_normalizes_dicts_and_strings():
    state = mod.init_state(_taxonomy())
    assert state["targets"] == []
    mod.set_targets(
        state,
        [{"target_id": "react", "category": "frontend"}, "postgres"],
    )
    assert state["targets"] == [
        {"target_id": "react", "category": "frontend"},
        {"target_id": "postgres"},
    ]


def test_set_targets_replaces_previous():
    state = mod.init_state(_taxonomy())
    mod.set_targets(state, [{"target_id": "a"}])
    mod.set_targets(state, [{"target_id": "b", "category": "backend"}])
    assert state["targets"] == [{"target_id": "b", "category": "backend"}]


def test_set_targets_rejects_missing_id_and_duplicates():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.set_targets(state, [{"category": "frontend"}])  # target_id 欠落
    with pytest.raises(mod.TransitionError):
        mod.set_targets(state, ["react", "react"])  # 重複
    with pytest.raises(mod.TransitionError):
        mod.set_targets(state, [123])  # str でも dict でもない


def test_cli_set_targets_string_and_file(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    # JSON 配列文字列
    inline = json.dumps([{"target_id": "react", "category": "frontend"}])
    assert mod.main(["set-targets", "--state", str(state_path), "--targets", inline]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["targets"] == [{"target_id": "react", "category": "frontend"}]
    # {"targets": [...]} を含むファイル
    tfile = tmp_path / "targets.json"
    tfile.write_text(json.dumps({"targets": ["postgres"]}), encoding="utf-8")
    assert mod.main(["set-targets", "--state", str(state_path), "--targets", str(tfile)]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["targets"] == [{"target_id": "postgres"}]


def test_cli_set_targets_bad_id_returns_1(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    bad = json.dumps([{"category": "frontend"}])  # target_id 欠落
    assert mod.main(["set-targets", "--state", str(state_path), "--targets", bad]) == 1


# --------------------------------------------------------------------------- #
# CLI (main) の網羅                                                            #
# --------------------------------------------------------------------------- #
def test_cli_init_chunk_apply_aggregate(tmp_path):
    state_path = tmp_path / "spec-state.json"
    turns_path = tmp_path / "turns.json"
    turns_path.write_text(TURNS.read_text(encoding="utf-8"), encoding="utf-8")

    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    # chunk invocation1
    assert mod.main(["chunk", "--state", str(state_path), "--turns", str(turns_path),
                     "--max-loops", "5"]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["hearing_progress"]["complete"] is False
    # apply 単一 op: reopen 確定セル → 未収集
    reopen = json.dumps({"action": "reopen", "category": "database", "platform": "web", "reason": "再確認"})
    assert mod.main(["apply", "--state", str(state_path), "--op", reopen]) == 0
    # aggregate 再計算
    assert mod.main(["aggregate", "--state", str(state_path)]) == 0


def test_cli_apply_rollback_returns_1(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    confirm = json.dumps({"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-001"})
    assert mod.main(["apply", "--state", str(state_path), "--op", confirm]) == 0
    # 確定セルを exclude で直接巻き戻し → CLI も拒否 (exit 1)
    bad = json.dumps({"action": "exclude", "category": "database", "platform": "web", "reason": "x"})
    assert mod.main(["apply", "--state", str(state_path), "--op", bad]) == 1


def test_cli_bad_taxonomy_returns_1(tmp_path):
    missing = tmp_path / "nope.json"
    assert mod.main(["init", "--taxonomy", str(missing), "--out", str(tmp_path / "o.json")]) == 1


def test_cli_stdout_emit(capsys, tmp_path):
    assert mod.main(["init", "--taxonomy", str(TAXONOMY)]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["schema_version"] == "1.0"


# --------------------------------------------------------------------------- #
# requirements_foundation (上位概念・要件 C9) の set-foundation op              #
# --------------------------------------------------------------------------- #
def _valid_foundation() -> dict:
    return {
        "essential_purpose": "請求と監査を単一 Web システムへ統合し二重管理をなくす",
        "background": "表計算と個別ツールが乱立し請求漏れと監査コストが慢性化している",
        "goals": [
            {"id": "G1", "text": "請求・監査データを単一の信頼できる情報源へ統合する"},
            {"id": "G2", "text": "主要業務動線を Web だけで完結できるようにする"},
        ],
        "objectives": [{"id": "O1", "text": "請求漏れ検知を自動化", "measure": "月次0件"}],
        "success_criteria": ["請求漏れ0件が3ヶ月継続"],
        "stakeholders": ["経理チーム"],
        "scope": {"in": ["請求管理"], "out": ["給与計算"]},
        "constraints": ["社内 k8s 上で稼働"],
        "concrete_intents": [{"id": "I1", "text": "日次バックアップ", "serves": ["G1"]}],
        "confirmed": True,
        # 確定にはユーザー合意の approval が必須。approval_note で approval_log へ idempotent 登録される。
        "approval_ref": "appr-foundation",
        "approval_note": "上位概念 U1-U9 をユーザーと確認し合意した",
    }


def test_init_state_has_empty_foundation():
    state = mod.init_state(_taxonomy())
    rf = state["requirements_foundation"]
    assert rf == mod.empty_foundation()
    assert rf["confirmed"] is False
    assert rf["goals"] == [] and rf["essential_purpose"] == ""
    assert rf["scope"] == {"in": [], "out": []}


def test_set_foundation_confirmed_ok():
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, _valid_foundation())
    rf = state["requirements_foundation"]
    assert rf["confirmed"] is True
    assert [g["id"] for g in rf["goals"]] == ["G1", "G2"]


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
    mod.set_foundation(state, f)
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
    mod.set_foundation(state, _valid_foundation())
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
    mod.set_foundation(state, _valid_foundation())
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
    inline = json.dumps(_valid_foundation())
    assert mod.main(["set-foundation", "--state", str(state_path), "--foundation", inline]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["requirements_foundation"]["confirmed"] is True
    # ファイル入力経路
    ffile = tmp_path / "foundation.json"
    ffile.write_text(json.dumps({"stakeholders": ["A"]}), encoding="utf-8")
    assert mod.main(["set-foundation", "--state", str(state_path), "--foundation", str(ffile)]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["requirements_foundation"]["stakeholders"] == ["A"]


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
    mod.set_foundation(state, _valid_foundation())
    decision = _valid_decision()
    mod.set_decision(state, decision)
    assert state["decisions"][0]["status"] == "recommended_pending_confirmation"
    assert state["decisions"][0]["user_decision"] is None


def test_set_decision_confirmed_requires_user_decision():
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, _valid_foundation())
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
    mod.set_foundation(state, _valid_foundation())
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
    mod.set_foundation(state, _valid_foundation())
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
    mod.set_foundation(state, _valid_foundation())
    decision = _valid_decision()
    mutate(decision)
    with pytest.raises(mod.TransitionError, match=match):
        mod.set_decision(state, decision)


def test_set_decision_confirmed_rejects_non_rfc3339_confirmation_time():
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, _valid_foundation())
    decision = _valid_decision("confirmed")
    decision["user_decision"] = {"option_id": "free-managed", "confirmed_at": "2026-07-11"}
    with pytest.raises(mod.TransitionError, match="confirmed_at は RFC3339"):
        mod.set_decision(state, decision)


def test_cli_bootstrap_init_preserves_foundation(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["bootstrap", "--out", str(state_path)]) == 0
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
    confirm = json.dumps({"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-001"})
    assert mod.main(["apply", "--state", str(state_path), "--op", confirm]) == 0
    serves = json.dumps({"action": "set-serves", "category": "database", "platform": "web", "serves_goals": ["G1"]})
    assert mod.main(["apply", "--state", str(state_path), "--op", serves]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["matrix"]["database"]["web"]["serves_goals"] == ["G1"]


# --------------------------------------------------------------------------- #
# KNOWLEDGE_CANDIDATES_EXTENSION_C                                             #
# --------------------------------------------------------------------------- #
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
    mod.set_foundation(state, _valid_foundation())
    assert state["knowledge_candidates"] == []
    for status in ("discovered", "qualified", "deepened"):
        mod.set_knowledge_candidate(state, _knowledge_candidate(status))
        assert state["knowledge_candidates"][0]["status"] == status
    assert state["knowledge_candidates"][0]["card"]["does_not_apply_when"]
    assert state["knowledge_candidates"][0]["card"]["goal_contribution"]


def test_knowledge_candidate_qualified_requires_official_https_and_checked_at():
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, _valid_foundation())
    mod.set_knowledge_candidate(state, _knowledge_candidate("discovered"))
    bad = _knowledge_candidate("qualified")
    bad["source_refs"][0]["url"] = "http://example.invalid/blog"
    bad["source_refs"][0]["official_or_primary"] = False
    with pytest.raises(mod.TransitionError, match="HTTPS"):
        mod.set_knowledge_candidate(state, bad)


def test_knowledge_candidate_deepened_requires_complete_card():
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, _valid_foundation())
    mod.set_knowledge_candidate(state, _knowledge_candidate("discovered"))
    mod.set_knowledge_candidate(state, _knowledge_candidate("qualified"))
    bad = _knowledge_candidate("deepened")
    del bad["card"]["does_not_apply_when"]
    with pytest.raises(mod.TransitionError, match="card.does_not_apply_when"):
        mod.set_knowledge_candidate(state, bad)


def test_knowledge_candidate_rejects_skip_rollback_topic_change_and_dangling_goal():
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, _valid_foundation())
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
    mod.set_foundation(state, _valid_foundation())
    for status in ("discovered", "qualified", "deepened"):
        mod.set_knowledge_candidate(state, _knowledge_candidate(status))
    promoted = _knowledge_candidate("promoted")
    del promoted["curation_ref"]
    with pytest.raises(mod.TransitionError, match="curation_ref"):
        mod.set_knowledge_candidate(state, promoted)


def test_cli_set_knowledge_candidate(tmp_path):
    state = mod.init_state(_taxonomy())
    mod.set_foundation(state, _valid_foundation())
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
