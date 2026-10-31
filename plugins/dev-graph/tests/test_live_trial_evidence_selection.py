"""lib/live_trial_evidence_selection.py (latest_task_path を含む) の単体検証。

live-trial 証跡は run-id の辞書順だけで選ぶと、時計ずれで将来日付を持つ古い run が
fresh PASS に勝つ。criteria receipt (criteria-test/scenario-verdict.json) が採用した
PASS verdict を優先し、receipt が存在するのに壊れている・曖昧・live-trial 外を指す・
PASS でない場合は、呼出側が fail-closed にできるよう選択エラーを返すことを固定する。
receipt が無いときだけ従来の辞書順 fallback へ後退する。

root の lint-live-trial-verdict.py が証跡選択をこの module へ寄せるときに備え、
``verdict_selection_from_criteria_receipt`` の名前・引数・戻り値の形
((Path | None, str | None)) も固定する。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from live_trial_evidence_selection import (
    latest_task_path,
    task_path_from_criteria_receipt,
    verdict_path_from_criteria_receipt,
    verdict_selection_from_criteria_receipt,
)

PLUGIN = "dev-graph"
SKILL = "run-dev-graph-system-spec"


def _skill_dir(root: Path) -> Path:
    return root / "eval-log" / PLUGIN / SKILL


def _run(root: Path, run_id: str, *, verdict: str | None = "PASS", task: bool = True) -> Path:
    run = _skill_dir(root) / "live-trial" / run_id
    run.mkdir(parents=True)
    if task:
        (run / "task.md").write_text(f"# {run_id}\n", encoding="utf-8")
    if verdict is not None:
        (run / "verdict.json").write_text(
            json.dumps({"overall": {"verdict": verdict}}), encoding="utf-8"
        )
    return run


def _receipt(root: Path, criteria_results: object) -> Path:
    path = _skill_dir(root) / "criteria-test" / "scenario-verdict.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"criteria_results": criteria_results}), encoding="utf-8")
    return path


def _ref(run_id: str) -> str:
    return f"eval-log/{PLUGIN}/{SKILL}/live-trial/{run_id}/verdict.json"


def test_receipt_absent_returns_no_selection_and_no_error(tmp_path: Path) -> None:
    _run(tmp_path, "20260801T000000-a")
    assert verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL) == (None, None)


def test_receipt_selects_referenced_pass_over_newer_run_id(tmp_path: Path) -> None:
    fresh = _run(tmp_path, "20260801T000000-fresh")
    # 時計ずれで将来日付を持つ古い証跡。辞書順だけなら勝ってしまう。
    _run(tmp_path, "20991231T000000-skewed")
    _receipt(tmp_path, {"OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": _ref(fresh.name)}})

    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert error is None
    assert selected == (fresh / "verdict.json").resolve()
    assert verdict_path_from_criteria_receipt(tmp_path, PLUGIN, SKILL) == selected
    assert task_path_from_criteria_receipt(tmp_path, SKILL) == selected.parent / "task.md"
    assert latest_task_path(tmp_path, SKILL) == selected.parent / "task.md"


def test_receipt_without_live_trial_criteria_is_not_an_error(tmp_path: Path) -> None:
    _receipt(tmp_path, {"IN1": {"verify_by": "fixture"}})
    assert verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL) == (None, None)


def test_invalid_receipt_json_is_reported(tmp_path: Path) -> None:
    path = _skill_dir(tmp_path) / "criteria-test" / "scenario-verdict.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert selected is None
    assert error is not None and error.startswith("criteria-receipt-invalid-json")


def test_non_object_criteria_results_is_reported(tmp_path: Path) -> None:
    _receipt(tmp_path, [])
    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert selected is None
    assert error is not None and error.startswith("criteria-receipt-invalid:")


def test_empty_live_trial_ref_is_reported(tmp_path: Path) -> None:
    _receipt(tmp_path, {"OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": ""}})
    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert selected is None
    assert error is not None and "live_trial_verdict_ref" in error


def test_ambiguous_refs_are_reported(tmp_path: Path) -> None:
    first = _run(tmp_path, "20260801T000000-a")
    second = _run(tmp_path, "20260802T000000-b")
    _receipt(
        tmp_path,
        {
            "OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": _ref(first.name)},
            "OUT2": {"verify_by": "live-trial", "live_trial_verdict_ref": _ref(second.name)},
        },
    )
    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert selected is None
    assert error is not None and error.startswith("criteria-receipt-ambiguous")


def test_ref_outside_live_trial_dir_is_reported(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "verdict.json"
    outside.parent.mkdir()
    outside.write_text(json.dumps({"overall": {"verdict": "PASS"}}), encoding="utf-8")
    _receipt(tmp_path, {"OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": "elsewhere/verdict.json"}})
    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert selected is None
    assert error is not None and error.startswith("criteria-receipt-outside-live-trial")


def test_ref_not_named_verdict_json_is_reported(tmp_path: Path) -> None:
    run = _run(tmp_path, "20260801T000000-a")
    ref = _ref(run.name).replace("verdict.json", "task.md")
    _receipt(tmp_path, {"OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": ref}})
    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert selected is None
    assert error is not None and error.startswith("criteria-receipt-invalid-ref")


def test_non_pass_verdict_is_reported(tmp_path: Path) -> None:
    run = _run(tmp_path, "20260801T000000-a", verdict="FAIL")
    _receipt(tmp_path, {"OUT1": {"verify_by": "live-trial", "live_trial_verdict_ref": _ref(run.name)}})
    selected, error = verdict_selection_from_criteria_receipt(tmp_path, PLUGIN, SKILL)
    assert selected is None
    assert error is not None and error.startswith("criteria-receipt-invalid-verdict")
    # 互換 API は error を捨てて None を返し、latest_task_path は辞書順 fallback へ後退する。
    assert task_path_from_criteria_receipt(tmp_path, SKILL) is None
    assert latest_task_path(tmp_path, SKILL) == run / "task.md"


def test_latest_task_falls_back_to_latest_completed_run_without_receipt(tmp_path: Path) -> None:
    """receipt 不在時は verdict 保有 run の辞書順最大へ後退し、中断 run は無視する。"""
    _run(tmp_path, "20260801T000000-old")
    newest = _run(tmp_path, "20260802T000000-new")
    _run(tmp_path, "20260803T000000-interrupted", verdict=None)

    assert latest_task_path(tmp_path, SKILL) == newest / "task.md"


def test_latest_task_is_none_without_live_trial_dir(tmp_path: Path) -> None:
    assert latest_task_path(tmp_path, SKILL) is None
