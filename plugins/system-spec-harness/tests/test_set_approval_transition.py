# /// script
# name: test-set-approval-transition
# version: 0.1.0
# purpose: 確定セルへ承認記録を紐づける set-approval op (単一 writer) と、承認主張×承認記録の突合検査 (validate-coverage-matrix.py) を、正例・負例・確定巻き戻し拒否の不変性で固定する pytest。
# inputs:
#   - argv: pytest 経由 (直接 argv は取らない)
# outputs:
#   - stdout: pytest 結果
#   - exit: 0=all pass / 1=failure
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""set-approval op と承認トレース検査を固定する。

背景 (F-0025): `exclude` は `approval_ref` を cell へ持てるのに `confirm` は持てず、
「回答本文は承認を主張しているが、確定セルから承認記録へ機械追跡できない」非対称が
あった。`confirm` の action 定義を変えると確定条件そのものへ触れるため、確定セル限定の
後付け annotation である `set-serves` と同型の `set-approval` を新設して対称化した。

本テストが固定するのは 3 点:
(a) set-approval は確定セル限定・approval_log 実在必須で、それ以外は TransitionError
(b) 単一 writer の中核不変則 (確定セルの直接変更拒否) が新 action で壊れていない
(c) validator が「qa 本文は appr-NNN を引用しているのにセルに approval_ref が無い」を検出し、
    set-approval 適用後は消える (検査が生きていることを実測で示す)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ELICIT_SCRIPTS = (
    Path(__file__).resolve().parent.parent
    / "skills/run-system-spec-elicit/scripts"
)
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"



def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stm = _load("apply_spec_transition_approval", ELICIT_SCRIPTS / "apply-spec-transition.py")
TransitionError = stm.TransitionError
c12 = _load("vcm_approval", SCRIPTS / "validate-coverage-matrix.py")

PLATFORMS = list(stm.CANONICAL_PLATFORMS)


def _state() -> dict:
    """auth/web だけ確定、他は未収集の最小 state。"""
    state = stm.bootstrap_state()
    state["categories"] = [{"id": "auth", "label": "認証"}]
    state["matrix"] = {"auth": {pf: {"state": "未収集"} for pf in PLATFORMS}}
    state["matrix"]["auth"]["web"] = {"state": "確定", "qa_ref": "qa-001"}
    state["qa_log"] = [{"id": "qa-001", "question": "認証方式は?", "answer": "appr-010 で承認済みの OIDC"}]
    state["approval_log"] = [{"id": "appr-010", "note": "認証方式の承認"}]
    stm.recompute_aggregates(state)
    return state


def _op(**kwargs) -> dict:
    return {"action": "set-approval", "category": "auth", "platform": "web", **kwargs}


# ── writer: set-approval ───────────────────────────────────────────────────
def test_set_approval_attaches_ref_to_confirmed_cell():
    state = _state()
    stm.apply_cell_op(state, _op(approval_ref="appr-010"))
    cell = state["matrix"]["auth"]["web"]
    assert cell["approval_ref"] == "appr-010"
    # 既存の確定情報を壊さない (annotation であって遷移ではない)
    assert cell["state"] == "確定" and cell["qa_ref"] == "qa-001"


def test_set_approval_rejects_non_confirmed_cell():
    state = _state()
    with pytest.raises(TransitionError, match="確定セルのみ"):
        stm.apply_cell_op(state, _op(platform="mobile", approval_ref="appr-010"))


def test_set_approval_rejects_dangling_approval_ref():
    """approval_log に無い id を許すと、トレース先が存在しない偽の承認記録ができる。"""
    state = _state()
    with pytest.raises(TransitionError, match="approval_log に存在しない"):
        stm.apply_cell_op(state, _op(approval_ref="appr-999"))
    assert "approval_ref" not in state["matrix"]["auth"]["web"]


@pytest.mark.parametrize("bad", [None, "", "   "])
def test_set_approval_requires_non_empty_ref(bad):
    state = _state()
    op = _op() if bad is None else _op(approval_ref=bad)
    with pytest.raises(TransitionError, match="非空 approval_ref"):
        stm.apply_cell_op(state, op)


def test_apply_turn_fills_approval_ref_from_turn():
    """confirm と同 turn で承認を得た場合、turn の approval_id を確定セルへ紐づける。

    turn 境界は state に永続化されないため、この場でしか対応を残せない。
    """
    state = _state()
    stm.apply_turn(
        state,
        {
            "approval_id": "appr-020",
            "approval_note": "同 turn 承認",
            "ops": [{"action": "set-approval", "category": "auth", "platform": "web"}],
        },
    )
    assert state["matrix"]["auth"]["web"]["approval_ref"] == "appr-020"


def test_confirmed_cell_direct_change_still_rejected():
    """新 action 追加で単一 writer の中核不変則が緩んでいないことを確認する。"""
    state = _state()
    for action in ("confirm", "exclude"):
        with pytest.raises(TransitionError, match="確定セルの直接変更は拒否"):
            stm.apply_cell_op(
                state,
                {"action": action, "category": "auth", "platform": "web", "qa_ref": "qa-001", "reason": "x"},
            )


# ── validator: 承認主張 × 承認記録の突合 ───────────────────────────────────
def _approval_findings(state: dict) -> list[str]:
    return [f for f in c12.validate(state) if "approval" in f or "承認" in f]


def test_validator_flags_claimed_approval_without_ref():
    """qa 本文が appr-010 を引用しているのにセルに approval_ref が無い状態を検出する。"""
    findings = _approval_findings(_state())
    assert any("承認 ['appr-010'] を引用しているが" in f for f in findings), findings


def test_validator_clears_after_set_approval():
    """set-approval を通せば検出が消える = 検査が実際に対象を見ている証拠。"""
    state = _state()
    stm.apply_cell_op(state, _op(approval_ref="appr-010"))
    assert _approval_findings(state) == []


def test_validator_ignores_unknown_approval_id_citation():
    """approval_log に無い id の言及は誤検出しない (本文の言い回しでゲートを鳴らさない)。"""
    state = _state()
    state["qa_log"][0]["answer"] = "appr-777 で承認したと聞いている"
    assert _approval_findings(state) == []


def test_validator_flags_dangling_cell_approval_ref():
    """セル側の approval_ref が approval_log に無ければ、追跡不能として検出する。"""
    state = _state()
    state["matrix"]["auth"]["web"]["approval_ref"] = "appr-999"
    findings = _approval_findings(state)
    assert any("approval_log に不在" in f for f in findings), findings


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
