"""check-requirements-coverage.py (SDD RTM ゲート) の機能テスト。

goal-spec.checklist の各要件 id が index の 完了チェックリスト/受入確認 で引用される
(要件 orphan=silent drop 防止)。id 照合は境界安全 (C1 が C01/C11 に誤マッチしない)。
"""
from __future__ import annotations

import json


def _index_text(done_body: str = "- [ ] 要件なし", accept_body: str = "確認なし") -> str:
    return (
        "# index\n\n"
        f"## 完了チェックリスト\n{done_body}\n\n"
        f"## 受入確認\n{accept_body}\n"
    )


def _goal_spec(ids: list[str]) -> dict:
    return {"checklist": [{"id": i, "criterion": "x", "done": False} for i in ids]}


# ─────────────────── 純関数: 境界安全な id 照合 ───────────────────
def test_id_pattern_word_boundary(requirements_coverage):
    pat = requirements_coverage._id_pattern("C1")
    assert pat.search("要件 C1 を満たす")          # スペース区切り
    assert pat.search("要件C1が満たされる")         # 日本語直結も許容
    assert pat.search("(C1)")
    assert not pat.search("C11 を満たす")           # C11 に誤マッチしない
    assert not pat.search("C01 を満たす")           # component id に誤マッチしない
    assert not pat.search("ABC1 を満たす")          # 英字前置に誤マッチしない


def test_uncovered_all_ids_found(requirements_coverage):
    gs = _goal_spec(["C1", "C2"])
    idx = _index_text("- [ ] 要件 C1: inventory 記録", "要件C2の routes 確認")
    errors, uncovered = requirements_coverage.uncovered_requirements(gs, idx)
    assert errors == [] and uncovered == []


def test_uncovered_detects_silent_drop(requirements_coverage):
    gs = _goal_spec(["C1", "C2", "C3"])
    idx = _index_text("- [ ] 要件 C1 のみ")
    errors, uncovered = requirements_coverage.uncovered_requirements(gs, idx)
    assert errors == [] and uncovered == ["C2", "C3"]


def test_uncovered_c1_not_satisfied_by_c11(requirements_coverage):
    # C11 (component id) の出現では要件 C1 の被覆にならない
    gs = _goal_spec(["C1"])
    idx = _index_text("- [ ] guard hook (C11) が阻む")
    errors, uncovered = requirements_coverage.uncovered_requirements(gs, idx)
    assert errors == [] and uncovered == ["C1"]


def test_uncovered_fails_closed_on_missing_section(requirements_coverage):
    gs = _goal_spec(["C1"])
    idx = "# index\n\n## 完了チェックリスト\n- [ ] C1\n"  # 受入確認 節が無い
    errors, _ = requirements_coverage.uncovered_requirements(gs, idx)
    assert any("受入確認" in e for e in errors)


def test_uncovered_fails_closed_on_empty_checklist(requirements_coverage):
    errors, _ = requirements_coverage.uncovered_requirements({"checklist": []}, _index_text())
    assert any("checklist" in e for e in errors)


def test_uncovered_fails_closed_on_missing_id(requirements_coverage):
    gs = {"checklist": [{"criterion": "id なし", "done": False}]}
    errors, _ = requirements_coverage.uncovered_requirements(gs, _index_text())
    assert any("id が無い" in e for e in errors)


# ─────────────────── run / main (ファイル IO と exit code) ───────────────────
def _write_plan(tmp_path, goal_spec: dict | str, index: str):
    if isinstance(goal_spec, dict):
        goal_spec = json.dumps(goal_spec, ensure_ascii=False)
    (tmp_path / "goal-spec.json").write_text(goal_spec, encoding="utf-8")
    (tmp_path / "index.md").write_text(index, encoding="utf-8")


def test_run_pass(requirements_coverage, tmp_path):
    _write_plan(tmp_path, _goal_spec(["C1"]), _index_text("- [ ] 要件 C1 被覆"))
    code, errors = requirements_coverage.run(tmp_path)
    assert (code, errors) == (0, [])


def test_run_fail_on_uncovered(requirements_coverage, tmp_path):
    _write_plan(tmp_path, _goal_spec(["C1", "C9"]), _index_text("- [ ] 要件 C1 被覆"))
    code, errors = requirements_coverage.run(tmp_path)
    assert code == 1
    assert any("C9" in e and "未被覆要件" in e for e in errors)


def test_run_fail_closed_on_missing_goal_spec(requirements_coverage, tmp_path):
    (tmp_path / "index.md").write_text(_index_text(), encoding="utf-8")
    code, errors = requirements_coverage.run(tmp_path)
    assert code == 1 and any("goal-spec.json" in e for e in errors)


def test_run_fail_closed_on_broken_json(requirements_coverage, tmp_path):
    _write_plan(tmp_path, "{broken", _index_text())
    code, errors = requirements_coverage.run(tmp_path)
    assert code == 1 and any("parse error" in e for e in errors)


def test_main_exit_codes(requirements_coverage, tmp_path, capsys):
    _write_plan(tmp_path, _goal_spec(["C1"]), _index_text("- [ ] C1"))
    assert requirements_coverage.main([str(tmp_path)]) == 0
    assert requirements_coverage.main([]) == 2                       # usage
    assert requirements_coverage.main([str(tmp_path / "nai")]) == 2  # not a dir
    capsys.readouterr()


def test_golden_sample_plan_passes(requirements_coverage):
    """golden (examples/sample-plan) が RTM を満たす回帰固定。"""
    from pathlib import Path
    sample = Path(__file__).resolve().parents[1] / "examples" / "sample-plan"
    code, errors = requirements_coverage.run(sample)
    assert (code, errors) == (0, [])


def test_gate_scripts_contains_requirements_coverage(specfm_mod):
    """specfm.GATE_SCRIPTS (機械正本) に本ゲートが登録されている (配線の回帰固定)。"""
    names = {name for name, _args in specfm_mod.GATE_SCRIPTS["extended"]}
    assert "check-requirements-coverage.py" in names
