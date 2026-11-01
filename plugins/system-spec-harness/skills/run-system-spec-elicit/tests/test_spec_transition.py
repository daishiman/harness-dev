#!/usr/bin/env python3
# /// script
# name: test-spec-transition
# version: 0.2.1
# purpose: run-system-spec-elicit の受入テスト。IN1(validate-coverage-matrix.py が fixture spec-state に exit0)/OUT1(最終 spec-state が未収集0で --require-complete exit0)/5周目 resume の状態保存/単一 transition writer の確定巻き戻し拒否/根拠参照の実在/required-info catalog 不正の exit2/confirm に --required-info が無いときの exit2/state・turns・taxonomy の形の崩れの exit1/書込の原子性を検証する。
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
"""run-system-spec-elicit acceptance tests (IN1 / OUT1 / resume / single-writer)。

foundation・decision・knowledge の遷移は test_spec_transition_{foundation,knowledge}.py に分けた。
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from spec_transition_support import (
    record_foundation_sources,
    valid_foundation as _valid_foundation,
)

SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-coverage-matrix.py"
KNOWLEDGE_VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-knowledge-graph.py"
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
REQUIRED_INFO = SKILL_DIR / "references" / "required-info-catalog.json"


def _taxonomy() -> dict:
    return json.loads(TAXONOMY.read_text(encoding="utf-8"))


def _turns() -> list:
    return json.loads(TURNS.read_text(encoding="utf-8"))


def _block_answer_turn(qa_id="qa-block", *, complete=True, answered_at="2026-01-01T00:00:00Z"):
    catalog = json.loads(REQUIRED_INFO.read_text(encoding="utf-8"))
    block_items = [it["item_id"] for it in catalog["items"] if it["missing_effect"] == "block"]
    return {
        "qa_id": qa_id, "question": "必須論点の確認", "answer": "利用者の確認済み回答",
        "basis": "user-decision", "answered_at": answered_at,
        "required_info_items": block_items if complete else block_items[:-1],
        "ops": [{"action": "confirm", "category": "backend", "platform": "web"}],
    }


@pytest.mark.parametrize("command", ["apply", "chunk"])
def test_first_confirm_validates_candidate_before_publishing(tmp_path, command):
    """対象外セルも確定セルも無い初回stateで、揃った回答の候補confirmは循環せず公開できる。"""
    state = mod.init_state(_taxonomy())
    turn = _block_answer_turn()
    state_path = tmp_path / "state.json"
    if command == "apply":
        mod.apply_turn(state, {**turn, "ops": []})  # 回答を先に集め、確定はまだ行わない。
        args = ["apply", "--op", json.dumps({**turn["ops"][0], "qa_ref": turn["qa_id"]})]
    else:
        turns_path = tmp_path / "turns.json"
        turns_path.write_text(json.dumps([turn], ensure_ascii=False))
        args = ["chunk", "--turns", str(turns_path)]
    state_path.write_text(json.dumps(state, ensure_ascii=False))
    assert mod.main(args + ["--state", str(state_path), "--required-info", str(REQUIRED_INFO)]) == 0
    actual = json.loads(state_path.read_text())
    assert actual["matrix"]["backend"]["web"]["state"] == "確定"
    proc = subprocess.run([sys.executable, str(KNOWLEDGE_VALIDATOR), "--profile", "required-info", "--input", str(REQUIRED_INFO), "--state", str(state_path)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("separate_output", [False, True])
def test_missing_block_answer_rejects_without_changing_any_file(tmp_path, separate_output):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(mod.init_state(_taxonomy()), ensure_ascii=False))
    before = state_path.read_bytes()
    turns_path = tmp_path / "turns.json"
    turns_path.write_text(json.dumps([_block_answer_turn(complete=False)], ensure_ascii=False))
    output = tmp_path / "candidate.json"
    output.write_text("pre-existing output")
    args = ["chunk", "--state", str(state_path), "--turns", str(turns_path), "--required-info", str(REQUIRED_INFO)]
    if separate_output:
        args.extend(["--out", str(output)])
    assert mod.main(args) == 1
    assert state_path.read_bytes() == before
    assert output.read_text() == "pre-existing output"


def test_reopen_then_reconfirm_uses_new_candidate_grounding(tmp_path):
    state = mod.init_state(_taxonomy())
    mod.apply_turn(state, _block_answer_turn())
    mod.apply_turn(state, {"ops": [{"action": "reopen", "category": "backend", "platform": "web", "reason": "新しい判断を取り直す", "reopened_at": "2026-01-02T00:00:00Z"}]})
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False))
    turns_path = tmp_path / "turns.json"
    turns_path.write_text(json.dumps([_block_answer_turn("qa-new", answered_at="2026-01-03T00:00:00Z")], ensure_ascii=False))
    assert mod.main(["chunk", "--state", str(state_path), "--turns", str(turns_path), "--required-info", str(REQUIRED_INFO)]) == 0
    actual = json.loads(state_path.read_text())
    assert actual["matrix"]["backend"]["web"]["qa_ref"] == "qa-new"
    assert actual["reopen_log"][0]["reason"] == "新しい判断を取り直す"


def _run_validator(
    matrix: Path,
    require_complete: bool = False,
    require_foundation: bool = False,
    require_basis: bool = False,
) -> int:
    argv = [sys.executable, str(VALIDATOR), "--matrix", str(matrix)]
    if require_complete:
        argv.append("--require-complete")
    if require_foundation:
        argv.append("--require-foundation")
    if require_basis:
        argv.append("--require-basis")
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


def test_OUT1_final_full_completion_condition_exit0():
    # SKILL.md / feedback_contract OUT1 が宣言する最終条件そのものを施行する。
    # 未収集0 (require-complete) だけでは「根拠の性質が不明な確定」と「どのゴールにも
    # 資さない確定」を素通しできるため、宣言に合わせて basis と foundation も課す。
    assert (
        _run_validator(
            GOLDEN_FINAL,
            require_complete=True,
            require_basis=True,
            require_foundation=True,
        )
        == 0
    )


def test_OUT1_final_grounds_all_blocking_required_info():
    # 収集ゲート (C16): block 指定の必須情報が決着済みセル -> qa_ref/qa_refs ->
    # qa_log.required_info_items の鎖で実際に接地していることを最終状態で確認する。
    proc = subprocess.run(
        [
            sys.executable,
            str(KNOWLEDGE_VALIDATOR),
            "--profile",
            "required-info",
            "--input",
            str(SKILL_DIR / "references" / "required-info-catalog.json"),
            "--state",
            str(GOLDEN_FINAL),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    cert = json.loads(proc.stdout)["coverage_certificate"]
    assert cert["ungrounded_blocking_items"] == []
    assert set(cert["grounded_blocking_items"]) == set(cert["blocking_items"])


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
    record_foundation_sources(mod, state)
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
            state, {"action": "reopen", "category": "database", "platform": "web", "reason": "x",
                    "reopened_at": "2020-01-01T00:00:00Z"}
        )


def test_reopen_requires_reason():
    state = _confirmed_state()
    with pytest.raises(mod.TransitionError):
        mod.apply_cell_op(
            state, {"action": "reopen", "category": "database", "platform": "web",
             "reopened_at": "2020-01-01T00:00:00Z"}
        )


def test_reopen_then_reconfirm_allowed():
    state = _confirmed_state()
    mod.apply_cell_op(
        state, {"action": "reopen", "category": "database", "platform": "web", "reason": "追加要件が判明",
         "reopened_at": "2020-01-01T00:00:00Z"}
    )
    assert state["matrix"]["database"]["web"]["state"] == "未収集"
    assert state["reopen_log"][-1]["reason"] == "追加要件が判明"
    # reopen 後は confirm へ再遷移できる (取り直した回答を qa_log に載せてから確定する)
    mod.apply_turn(state, {"qa_id": "qa-002", "question": "q2", "answer": "a2"})
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


def test_set_targets_keeps_also_categories():
    """主たる章 (category) に加えて出典を載せる章 (also_categories) を保つ。

    0.1.15 までは target の未知キーを黙って捨てていたため、宣言しても章割当に届かなかった。
    """
    state = mod.init_state(_taxonomy())
    mod.set_targets(
        state,
        [
            {
                "target_id": "cloudflare-d1",
                "category": "database",
                "also_categories": ["backend", "infrastructure"],
            },
            {"target_id": "react", "category": "frontend"},
        ],
    )
    assert state["targets"] == [
        {
            "target_id": "cloudflare-d1",
            "category": "database",
            "also_categories": ["backend", "infrastructure"],
        },
        {"target_id": "react", "category": "frontend"},
    ]


def test_set_targets_rejects_also_categories_without_category():
    # 主従を残すため、主たる章 (category) を持たない target には指定できない。
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError, match="category"):
        mod.set_targets(state, [{"target_id": "d1", "also_categories": ["backend"]}])
    assert state["targets"] == []


def test_set_targets_rejects_duplicate_also_categories():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError, match="重複"):
        mod.set_targets(
            state,
            [{"target_id": "d1", "category": "database", "also_categories": ["backend", "backend"]}],
        )


def test_set_targets_rejects_also_categories_equal_to_category():
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError, match="主たる章"):
        mod.set_targets(
            state,
            [{"target_id": "d1", "category": "database", "also_categories": ["database"]}],
        )
    # 空配列・非文字列の要素も宣言として成り立たないので拒否する。
    for bad in ([], [""], [1], "backend"):
        with pytest.raises(mod.TransitionError):
            mod.set_targets(
                state, [{"target_id": "d1", "category": "database", "also_categories": bad}]
            )


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
    # block の必須情報を先に接地する (confirm を含む chunk は候補 state の接地検証を通ってから書く)
    grounding_path = tmp_path / "grounding.json"
    grounding_path.write_text(json.dumps([_block_answer_turn()], ensure_ascii=False), encoding="utf-8")
    assert mod.main(["chunk", "--state", str(state_path), "--turns", str(grounding_path),
                     "--required-info", str(REQUIRED_INFO)]) == 0
    # chunk invocation1
    assert mod.main(["chunk", "--state", str(state_path), "--turns", str(turns_path),
                     "--max-loops", "5", "--required-info", str(REQUIRED_INFO)]) == 0
    st = json.loads(state_path.read_text(encoding="utf-8"))
    assert st["hearing_progress"]["complete"] is False
    # apply 単一 op: reopen 確定セル → 未収集
    reopen = json.dumps({"action": "reopen", "category": "database", "platform": "web", "reason": "再確認",
                        "reopened_at": "2020-01-01T00:00:00Z"})
    assert mod.main(["apply", "--state", str(state_path), "--op", reopen]) == 0
    # aggregate 再計算
    assert mod.main(["aggregate", "--state", str(state_path)]) == 0


def _cli_register_qa(tmp_path, state_path, qa_id="qa-001") -> None:
    """CLI の apply は op だけを受けるので、確定の根拠になる回答は先に chunk で qa_log へ載せる。

    confirm には --required-info が要るので、block の必須情報を満たす回答を載せる (confirm はしない)。
    """
    turns_path = tmp_path / f"turns-{qa_id}.json"
    turns_path.write_text(json.dumps([{**_block_answer_turn(qa_id), "ops": []}], ensure_ascii=False))
    assert mod.main(["chunk", "--state", str(state_path), "--turns", str(turns_path)]) == 0


def test_cli_apply_rollback_returns_1(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    _cli_register_qa(tmp_path, state_path)
    confirm = json.dumps({"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-001"})
    assert mod.main(["apply", "--state", str(state_path), "--op", confirm, "--required-info", str(REQUIRED_INFO)]) == 0
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
# 根拠参照の実在・required-info catalog の不正・書込の原子性                    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "op",
    [
        {"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-missing"},
        {"action": "confirm", "category": "database", "platform": "web", "qa_ref": ["qa-001"]},
        {"action": "exclude", "category": "database", "platform": "web", "reason": "x", "qa_ref": "qa-missing"},
        {"action": "exclude", "category": "database", "platform": "web", "approval_ref": "appr-missing"},
    ],
)
def test_cell_op_rejects_dangling_reference(op):
    """validate-coverage-matrix が落とす宙に浮いた参照を、writer が書く前に拒否する。"""
    state = mod.init_state(_taxonomy())
    mod.apply_turn(state, {"qa_id": "qa-001", "question": "q", "answer": "a"})
    before = copy.deepcopy(state)
    with pytest.raises(mod.TransitionError, match="存在しない|非空文字列でない"):
        mod.apply_cell_op(state, op)
    assert state == before


def test_confirm_may_cite_approval_log_entry():
    """validate-coverage-matrix は確定 qa_ref を qa_log ∪ approval_log に照合する。writer も同じ範囲を認める。"""
    state = mod.init_state(_taxonomy())
    mod.apply_turn(state, {"approval_id": "appr-1", "approval_note": "利用者が承認"})
    mod.apply_cell_op(state, {"action": "confirm", "category": "database", "platform": "web", "qa_ref": "appr-1"})
    mod.apply_cell_op(state, {"action": "exclude", "category": "database", "platform": "mobile", "approval_ref": "appr-1"})
    assert state["matrix"]["database"]["web"] == {"state": "確定", "qa_ref": "appr-1"}
    assert state["matrix"]["database"]["mobile"] == {"state": "対象外", "approval_ref": "appr-1"}


def test_cli_apply_dangling_qa_ref_keeps_state_file(tmp_path):
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    before = state_path.read_bytes()
    confirm = json.dumps({"action": "confirm", "category": "database", "platform": "web", "qa_ref": "qa-001"})
    assert mod.main(["apply", "--state", str(state_path), "--op", confirm, "--required-info", str(REQUIRED_INFO)]) == 1
    assert state_path.read_bytes() == before


def _broken_catalogs() -> dict:
    base = json.loads(REQUIRED_INFO.read_text(encoding="utf-8"))
    in_scope_obj = copy.deepcopy(base)
    in_scope_obj["in_scope_domains"] = [{"x": 1}]
    domain_list = copy.deepcopy(base)
    domain_list["items"][0]["domain"] = [domain_list["items"][0]["domain"]]
    depends_obj = copy.deepcopy(base)
    depends_obj["items"][1]["depends_on"] = [{"item_id": "product-goal"}]
    na_list = copy.deepcopy(base)
    na_list["na_domains"] = [{"domain": ["ui-ux"], "approval_state": "approved", "reason": "x"}]
    return {
        "list-root": [],
        "empty-items": {"items": []},
        "in-scope-object": in_scope_obj,
        "domain-list": domain_list,
        "depends-on-object": depends_obj,
        "na-domain-list": na_list,
    }


@pytest.mark.parametrize("name", sorted(_broken_catalogs()))
def test_broken_required_info_catalog_is_usage_error_not_traceback(tmp_path, capsys, name):
    """catalog 自体の不正は rc 2。候補 state の接地不足 (rc 1) と区別し、state も書かない。"""
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(_broken_catalogs()[name], ensure_ascii=False), encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(mod.init_state(_taxonomy()), ensure_ascii=False))
    before = state_path.read_bytes()
    turns_path = tmp_path / "turns.json"
    turns_path.write_text(json.dumps([_block_answer_turn()], ensure_ascii=False))
    rc = mod.main(["chunk", "--state", str(state_path), "--turns", str(turns_path), "--required-info", str(catalog_path)])
    assert rc == 2
    assert capsys.readouterr().err.startswith("CatalogError: ")
    assert state_path.read_bytes() == before


def test_write_failure_keeps_previous_state_file(tmp_path):
    """書込の途中で落ちても前の spec-state.json が残り、一時ファイルも残らない。

    JSON の `\\ud800` は読めるが UTF-8 へは書けない (lone surrogate)。従来の write_text は
    先にファイルを切り詰めてから失敗したため、正本の spec-state.json が空になっていた。
    """
    state_path = tmp_path / "spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    before = state_path.read_bytes()
    op = '{"action": "exclude", "category": "database", "platform": "web", "reason": "\\ud800"}'
    assert mod.main(["apply", "--state", str(state_path), "--op", op]) == 1
    assert state_path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["spec-state.json"]


def test_write_keeps_mode_and_follows_symlink(tmp_path):
    real = tmp_path / "real-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(real)]) == 0
    real.chmod(0o640)
    link = tmp_path / "spec-state.json"
    link.symlink_to(real)
    reason = json.dumps({"action": "exclude", "category": "database", "platform": "web", "reason": "対象外"})
    assert mod.main(["apply", "--state", str(link), "--op", reason]) == 0
    assert link.is_symlink()
    assert (real.stat().st_mode & 0o777) == 0o640
    assert json.loads(real.read_text(encoding="utf-8"))["matrix"]["database"]["web"]["state"] == "対象外"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["real-state.json", "spec-state.json"]


def test_bootstrap_creates_missing_parent_directory(tmp_path):
    """対象 repo に system-spec/ がまだ無い状態からでも bootstrap が通る (SKILL.md の手順 1)。"""
    state_path = tmp_path / "project" / "system-spec" / "spec-state.json"
    assert not state_path.parent.exists()
    assert mod.main(["bootstrap", "--out", str(state_path)]) == 0
    assert json.loads(state_path.read_text(encoding="utf-8")) == mod.bootstrap_state()
    assert [p.name for p in state_path.parent.iterdir()] == ["spec-state.json"]


def test_frontmatter_declares_required_info_validator_dependency():
    """--required-info は plugin の scripts/validate-knowledge-graph.py を読み込むので dependencies に載せる。"""
    script = SKILL_DIR / "scripts" / "apply-spec-transition.py"
    header = script.read_text(encoding="utf-8").split("# ///", 2)[1]
    line = next(row for row in header.splitlines() if row.startswith("# dependencies:"))
    deps = [d.strip() for d in line.split(":", 1)[1].strip().strip("[]").split(",") if d.strip()]
    assert "scripts/validate-knowledge-graph.py" in deps
    assert all((PLUGIN_ROOT / dep).is_file() for dep in deps)


# --------------------------------------------------------------------------- #
# 入力の形の崩れ (traceback ではなく exit 1) と confirm の収集ゲート (exit 2)      #
# --------------------------------------------------------------------------- #
_STATE_COMMANDS = {
    "apply": ["--op", json.dumps({"action": "reopen", "category": "database", "platform": "web",
                                  "reason": "r", "reopened_at": "2026-01-01T00:00:00Z"})],
    "chunk": ["--turns", None],
    "aggregate": [],
    "set-targets": ["--targets", "[]"],
    "set-foundation": ["--foundation", "{}"],
    "set-decision": ["--decision", "{}"],
    "set-knowledge-candidate": ["--candidate", "{}"],
}
_MALFORMED_STATES = {
    "list": "[]",
    "string": '"x"',
    "number": "3",
    "empty-object": "{}",
    "categories-object": json.dumps({"categories": {}, "matrix": {}, "qa_log": [], "approval_log": [],
                                     "hearing_progress": {}}),
}


@pytest.mark.parametrize("shape", sorted(_MALFORMED_STATES))
@pytest.mark.parametrize("command", sorted(_STATE_COMMANDS))
def test_malformed_state_is_transition_error_not_traceback(tmp_path, capsys, command, shape):
    """state が [] などのとき、どのサブコマンドも traceback ではなく exit 1 で止まり、state を書かない。"""
    body = _MALFORMED_STATES[shape]
    state_path = tmp_path / "state.json"
    state_path.write_text(body, encoding="utf-8")
    turns_path = tmp_path / "turns.json"
    turns_path.write_text("[]", encoding="utf-8")
    extra = [str(turns_path) if arg is None else arg for arg in _STATE_COMMANDS[command]]
    assert mod.main([command, "--state", str(state_path), *extra]) == 1
    assert capsys.readouterr().err.startswith("TransitionError: spec-state ")
    assert state_path.read_text(encoding="utf-8") == body


def test_optional_envelope_key_of_wrong_type_is_rejected(tmp_path, capsys):
    state = mod.init_state(_taxonomy())
    state["decisions"] = {}
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    assert mod.main(["aggregate", "--state", str(state_path)]) == 1
    assert "decisions (list 必須)" in capsys.readouterr().err


def test_state_without_optional_envelope_keys_is_still_accepted(tmp_path):
    """古い state に無い knowledge_candidates などは、writer が補うので必須にしない。"""
    state = mod.init_state(_taxonomy())
    for key in ("reopen_log", "decisions", "knowledge_candidates", "design_applications"):
        del state[key]
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    assert mod.main(["aggregate", "--state", str(state_path)]) == 0


@pytest.mark.parametrize(
    "taxonomy",
    [
        [],
        "x",
        {},
        {"platforms": "web", "categories": []},
        {"platforms": [{"id": pf} for pf in mod.CANONICAL_PLATFORMS], "categories": [{"id": "db"}]},
    ],
)
def test_init_malformed_taxonomy_is_transition_error(tmp_path, capsys, taxonomy):
    tax_path = tmp_path / "taxonomy.json"
    tax_path.write_text(json.dumps(taxonomy), encoding="utf-8")
    out = tmp_path / "state.json"
    assert mod.main(["init", "--taxonomy", str(tax_path), "--out", str(out)]) == 1
    assert capsys.readouterr().err.startswith("TransitionError: taxonomy")
    assert not out.exists()


def test_init_rejects_non_object_existing_state(tmp_path, capsys):
    """object でない --state を空として扱うと、bootstrap 済みの foundation を黙って捨ててしまう。"""
    state_path = tmp_path / "state.json"
    state_path.write_text("[]", encoding="utf-8")
    out = tmp_path / "out.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--state", str(state_path), "--out", str(out)]) == 1
    assert capsys.readouterr().err.startswith("TransitionError: spec-state ")
    assert not out.exists()


@pytest.mark.parametrize("turns", [{}, [1], [{"ops": "confirm"}], [{"ops": [1]}]])
def test_chunk_malformed_turns_is_transition_error(tmp_path, capsys, turns):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(mod.init_state(_taxonomy()), ensure_ascii=False), encoding="utf-8")
    before = state_path.read_bytes()
    turns_path = tmp_path / "turns.json"
    turns_path.write_text(json.dumps(turns), encoding="utf-8")
    assert mod.main(["chunk", "--state", str(state_path), "--turns", str(turns_path)]) == 1
    assert capsys.readouterr().err.startswith("TransitionError: turns")
    assert state_path.read_bytes() == before


@pytest.mark.parametrize("op", ["[]", '"confirm"', "3"])
def test_apply_non_object_op_is_transition_error(tmp_path, capsys, op):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(mod.init_state(_taxonomy()), ensure_ascii=False), encoding="utf-8")
    before = state_path.read_bytes()
    assert mod.main(["apply", "--state", str(state_path), "--op", op]) == 1
    assert capsys.readouterr().err.startswith("TransitionError: --op は object 必須")
    assert state_path.read_bytes() == before


@pytest.mark.parametrize("command", ["apply", "chunk"])
def test_confirm_without_required_info_is_usage_error(tmp_path, capsys, command):
    """SKILL.md の収集ゲート: confirm を含む apply / chunk は --required-info を必ず付ける。

    接地済みの回答があっても、catalog が無ければ候補 state を検証できないので書かない。
    """
    state = mod.init_state(_taxonomy())
    turn = _block_answer_turn()
    if command == "apply":
        mod.apply_turn(state, {**turn, "ops": []})
        args = ["apply", "--op", json.dumps({**turn["ops"][0], "qa_ref": turn["qa_id"]})]
    else:
        turns_path = tmp_path / "turns.json"
        turns_path.write_text(json.dumps([turn], ensure_ascii=False), encoding="utf-8")
        args = ["chunk", "--turns", str(turns_path)]
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    before = state_path.read_bytes()
    assert mod.main(args + ["--state", str(state_path)]) == 2
    assert capsys.readouterr().err.startswith("usage error: confirm を含む apply / chunk は --required-info")
    assert state_path.read_bytes() == before


def test_chunk_without_applied_confirm_needs_no_required_info(tmp_path):
    """回答の蓄積は --required-info なしで通る。--max-loops の外にあって適用しない confirm は数えない。"""
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(mod.init_state(_taxonomy()), ensure_ascii=False), encoding="utf-8")
    turns_path = tmp_path / "turns.json"
    turns_path.write_text(
        json.dumps([{**_block_answer_turn(), "ops": []}, _block_answer_turn("qa-later")], ensure_ascii=False),
        encoding="utf-8",
    )
    assert mod.main(["chunk", "--state", str(state_path), "--turns", str(turns_path), "--max-loops", "1"]) == 0
    actual = json.loads(state_path.read_text(encoding="utf-8"))
    assert [entry["id"] for entry in actual["qa_log"]] == ["qa-block"]
    assert actual["matrix"]["backend"]["web"]["state"] == "未収集"


# --------------------------------------------------------------------------- #
# add-category: 確定セルを触らずに行を足す                                       #
# --------------------------------------------------------------------------- #
def test_add_category_appends_row_without_touching_confirmed():
    state = _confirmed_state()
    before = copy.deepcopy(state["matrix"])
    mod.add_category(state, {"id": "dev-workflow", "label": "開発フロー"})
    for category, row in before.items():
        assert state["matrix"][category] == row
    assert set(state["matrix"]["dev-workflow"]) == set(mod.CANONICAL_PLATFORMS)
    assert all(cell["state"] == "未収集" for cell in state["matrix"]["dev-workflow"].values())
    assert state["category_aggregate"]["dev-workflow"] == "未着手"
    assert {"id": "dev-workflow", "label": "開発フロー"} in state["categories"]


def test_add_category_existing_id_rejected_no_rollback():
    state = _confirmed_state()
    with pytest.raises(mod.TransitionError):
        mod.add_category(state, {"id": "database", "label": "上書き試行"})
    assert state["matrix"]["database"]["web"]["state"] == "確定"


@pytest.mark.parametrize(
    "category",
    [
        {"id": "Dev_Workflow", "label": "開発フロー"}, {"id": "dev-workflow"},
        {"id": "", "label": "開発フロー"}, {"id": "dev-workflow", "label": "  "}, ["dev-workflow"],
    ],
)
def test_add_category_invalid_input_rejected(category):
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError):
        mod.add_category(state, category)


def test_add_category_state_passes_validator_loop(tmp_path):
    state = mod.init_state(_taxonomy())
    mod.add_category(state, {"id": "dev-workflow", "label": "開発フロー"})
    out = tmp_path / "spec-state.json"
    out.write_text(mod.dump_state(state), encoding="utf-8")
    assert _run_validator(out) == 0


# --------------------------------------------------------------------------- #
# qa の design_applications (回答とは別の設計解釈) と schema 1.1 opt-in           #
# --------------------------------------------------------------------------- #
def test_apply_turn_preserves_valid_design_application_as_separate_interpretation():
    state = mod.init_state(_taxonomy(), schema_version="1.1")
    assert state["design_application_contract_version"] == "1.0"
    mod.apply_turn(
        state,
        {
            "qa_id": "qa-design-001",
            "question": "永続化方式は?",
            "answer": "SQLite 単一ファイル",
            "design_applications": [
                {
                    "knowledge_ref": "ddd.md#Bounded Context / Context Map",
                    "principle": "Bounded Context / Context Map",
                    "applicability": "not_applicable",
                    "rationale": "単一利用者の単純 CRUD で文脈間翻訳が無い",
                    "tradeoffs": ["複数業務語彙が生じたら再評価する"],
                }
            ],
            "ops": [{"action": "confirm", "category": "database", "platform": "web"}],
        },
    )
    qa = state["qa_log"][0]
    assert qa["answer"] == "SQLite 単一ファイル"
    assert qa["design_applications"][0]["applicability"] == "not_applicable"
    assert qa["design_applications"][0]["rationale"] == "単一利用者の単純 CRUD で文脈間翻訳が無い"


@pytest.mark.parametrize("schema_version", ["1.0", "1.1"])
@pytest.mark.parametrize(
    "application",
    [
        {},
        {"knowledge_ref": "ddd.md", "principle": "DDD", "applicability": "maybe", "rationale": "x", "tradeoffs": ["x"]},
        {"knowledge_ref": "ddd.md", "principle": "DDD", "applicability": "applied", "rationale": "x", "tradeoffs": []},
    ],
)
def test_apply_turn_rejects_malformed_design_application(application, schema_version):
    # 形の検査は版に依らない。1.0 でも渡された design_applications は黙って保存しない。
    state = mod.init_state(_taxonomy(), schema_version=schema_version)
    with pytest.raises(mod.TransitionError):
        mod.apply_turn(
            state,
            {
                "qa_id": "qa-design-bad",
                "question": "q",
                "answer": "a",
                "design_applications": [application],
                "ops": [{"action": "confirm", "category": "database", "platform": "web"}],
            },
        )
    assert state["qa_log"] == []


def test_writer_rejects_confirm_without_design_applications_only_under_1_1():
    current = mod.init_state(_taxonomy(), schema_version="1.1")
    turn = {
        "qa_id": "qa-no-design",
        "question": "q",
        "answer": "a",
        "ops": [{"action": "confirm", "category": "database", "platform": "web"}],
    }
    with pytest.raises(mod.TransitionError, match="design_applications は非空配列必須"):
        mod.apply_turn(current, copy.deepcopy(turn))
    assert not mod._has_entry(current["qa_log"], "qa-no-design")

    # 既定の 1.0 は design application 契約を持たないので、従来どおり確定できる。
    legacy = mod.init_state(_taxonomy())
    mod.apply_turn(legacy, copy.deepcopy(turn))
    assert legacy["matrix"]["database"]["web"]["state"] == "確定"


@pytest.mark.parametrize(
    "broken",
    [
        {},
        {"schema_version": "1.1"},
        {"schema_version": "1.1", "design_application_contract_version": "2.0"},
        {"schema_version": "1.0", "design_application_contract_version": "1.0"},
        {"schema_version": "2.0"},
    ],
)
def test_init_rejects_noncanonical_existing_state_instead_of_repairing(broken):
    with pytest.raises(mod.TransitionError):
        mod.init_state(_taxonomy(), broken)


def test_cli_legacy_state_stays_writable_and_init_opts_in_to_1_1(tmp_path):
    legacy_path = tmp_path / "legacy-spec-state.json"
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(legacy_path)]) == 0
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    assert legacy["schema_version"] == "1.0"
    assert "design_application_contract_version" not in legacy
    assert mod.main(["aggregate", "--state", str(legacy_path)]) == 0

    migrated_path = tmp_path / "migrated-spec-state.json"
    assert mod.main([
        "init", "--taxonomy", str(TAXONOMY), "--state", str(legacy_path),
        "--schema-version", "1.1", "--out", str(migrated_path),
    ]) == 0
    migrated = json.loads(migrated_path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == "1.1"
    assert migrated["design_application_contract_version"] == "1.0"
    assert mod.main(["aggregate", "--state", str(migrated_path)]) == 0

    # 1.1 から 1.0 への降格は、契約 marker を黙って外すことになるので拒否する。
    assert mod.main([
        "init", "--taxonomy", str(TAXONOMY), "--state", str(migrated_path),
        "--schema-version", "1.0", "--out", str(tmp_path / "downgraded.json"),
    ]) == 1


# --------------------------------------------------------------------------- #
# chunk の未消化 turn を黙って捨てない                                          #
# --------------------------------------------------------------------------- #
def test_run_chunk_warns_on_unprocessed_turns(capsys):
    """max_loops を超えた turn を黙って捨てず、未消化件数を stderr へ出す。

    hearing_progress.complete は未収集セル 0 を意味するだけで turn 消化の証跡にならない。
    未消化が可視化されないと、投入した turn の一部だけが適用された state を完了扱いできてしまう。
    """
    turns = _turns()
    state = mod.init_state(_taxonomy())
    processed = mod.run_chunk(state, turns, max_loops=5)
    assert processed == 5
    err = capsys.readouterr().err
    assert "未消化" in err
    assert f"投入 {len(turns)} turn" in err and "5 turn を適用" in err
    assert f"{len(turns) - 5} turn が未消化" in err


def test_run_chunk_require_all_raises_on_unprocessed_turns():
    turns = _turns()
    state = mod.init_state(_taxonomy())
    with pytest.raises(mod.TransitionError) as excinfo:
        mod.run_chunk(state, turns, max_loops=5, require_all=True)
    assert f"{len(turns) - 5} turn が未消化" in str(excinfo.value)


def test_run_chunk_require_all_passes_when_all_consumed(capsys):
    state = mod.init_state(_taxonomy())
    turns = _turns()
    assert mod.run_chunk(state, turns, max_loops=len(turns), require_all=True) == len(turns)
    assert "未消化" not in capsys.readouterr().err


def test_cli_chunk_require_all_returns_1_on_unprocessed(tmp_path):
    state_path = tmp_path / "spec-state.json"
    turns_path = tmp_path / "turns.json"
    turns_path.write_text(TURNS.read_text(encoding="utf-8"), encoding="utf-8")
    assert mod.main(["init", "--taxonomy", str(TAXONOMY), "--out", str(state_path)]) == 0
    before = state_path.read_text(encoding="utf-8")
    assert mod.main([
        "chunk", "--state", str(state_path), "--turns", str(turns_path),
        "--max-loops", "5", "--require-all", "--required-info", str(REQUIRED_INFO),
    ]) == 1
    # fail-closed: 停止時に部分適用を書き戻さない。
    assert state_path.read_text(encoding="utf-8") == before
