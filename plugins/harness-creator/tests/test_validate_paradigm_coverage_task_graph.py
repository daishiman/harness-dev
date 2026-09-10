"""run-elegant-review の task-graph trace 検証 mode を固定する。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "skills/run-elegant-review/scripts/validate-paradigm-coverage.py"
)
GOAL = "30 思考法と 4 条件でレビューを完了する"


def _item(
    item_id: str,
    *,
    status: str = "done",
    depends_on: list[str] | None = None,
    created: int = 0,
    available: int | None = None,
) -> dict:
    result = {
        "id": item_id,
        "text": f"{item_id} を完了する",
        "status": status,
        "created_iteration": created,
        "available_from_iteration": created if available is None else available,
    }
    if depends_on:
        result["depends_on"] = depends_on
    return result


def _row(iteration: int, ready: list[str], selected: str | None) -> dict:
    return {
        "iteration": iteration,
        "original_goal": GOAL,
        "current_goal_snapshot": GOAL,
        "delta_from_original": "",
        "merged_directive_for_next": "依存順を保って次の item を実行する",
        "drift_signal": "initial" if iteration == 0 else "aligned",
        "ready_set": ready,
        "selected_item": selected,
    }


def _write_case(tmp_path: Path, progress: dict, rows: list[dict]) -> tuple[Path, Path]:
    progress_path = tmp_path / "progress.json"
    trace_path = tmp_path / "intermediate.jsonl"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    trace_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return progress_path, trace_path


def _progress(checklist: list[dict], *, iteration: int, max_loops: int, status: str) -> dict:
    return {
        "skill": "run-elegant-review",
        "goal": GOAL,
        "engine": "task-graph",
        "iteration": iteration,
        "max_loops": max_loops,
        "checklist": checklist,
        "status": status,
        "original_goal_hash": hashlib.sha256(GOAL.encode()).hexdigest(),
    }


def _run(progress_path: Path, trace_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--task-graph-trace",
            str(progress_path),
            str(trace_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_valid_trace_passes(tmp_path: Path) -> None:
    checklist = [
        _item("C1"),
        _item("C2", depends_on=["C1"]),
        _item("C3"),
    ]
    progress, trace = _write_case(
        tmp_path,
        _progress(checklist, iteration=2, max_loops=4, status="completed"),
        [
            _row(0, ["C1", "C3"], "C1"),
            _row(1, ["C2", "C3"], "C2"),
            _row(2, ["C3"], "C3"),
        ],
    )
    result = _run(progress, trace)
    assert result.returncode == 0, result.stderr
    assert "task-graph trace verified" in result.stdout


def test_absent_trace_fails_closed(tmp_path: Path) -> None:
    result = _run(tmp_path / "missing-progress.json", tmp_path / "missing.jsonl")
    assert result.returncode == 1
    assert "progress.json 不在" in result.stderr


def test_ready_set_must_equal_recomputed_set(tmp_path: Path) -> None:
    progress, trace = _write_case(
        tmp_path,
        _progress([_item("C1"), _item("C2")], iteration=0, max_loops=2, status="in_progress"),
        [_row(0, ["C1"], "C1")],
    )
    result = _run(progress, trace)
    assert result.returncode == 1
    assert "ready_set 不整合" in result.stderr


def test_selected_item_must_be_ready_minimum(tmp_path: Path) -> None:
    progress, trace = _write_case(
        tmp_path,
        _progress([_item("C1"), _item("C2")], iteration=0, max_loops=2, status="in_progress"),
        [_row(0, ["C1", "C2"], "C2")],
    )
    result = _run(progress, trace)
    assert result.returncode == 1
    assert "ready 最小 id C1" in result.stderr


def test_dangling_and_cycle_fail_closed(tmp_path: Path) -> None:
    dangling, trace = _write_case(
        tmp_path,
        _progress([_item("C1", depends_on=["C9"])], iteration=0, max_loops=1, status="in_progress"),
        [_row(0, [], None)],
    )
    result = _run(dangling, trace)
    assert result.returncode == 1
    assert "dangling" in result.stderr

    cycle_dir = tmp_path / "cycle"
    cycle_dir.mkdir()
    cycle, cycle_trace = _write_case(
        cycle_dir,
        _progress(
            [_item("C1", depends_on=["C2"]), _item("C2", depends_on=["C1"])],
            iteration=0,
            max_loops=2,
            status="in_progress",
        ),
        [_row(0, [], None)],
    )
    result = _run(cycle, cycle_trace)
    assert result.returncode == 1
    assert "cycle" in result.stderr


def test_done_requires_selection_trace(tmp_path: Path) -> None:
    progress, trace = _write_case(
        tmp_path,
        _progress(
            [_item("C1"), _item("C2", depends_on=["C1"])],
            iteration=0,
            max_loops=2,
            status="completed",
        ),
        [_row(0, ["C1"], "C1")],
    )
    result = _run(progress, trace)
    assert result.returncode == 1
    assert "done だが selected_item 証跡なし" in result.stderr


def test_completed_rejects_pending_and_bound_shortage(tmp_path: Path) -> None:
    pending, trace = _write_case(
        tmp_path,
        _progress(
            [_item("C1"), _item("C2", status="pending", depends_on=["C1"])],
            iteration=0,
            max_loops=2,
            status="completed",
        ),
        [_row(0, ["C1"], "C1")],
    )
    result = _run(pending, trace)
    assert result.returncode == 1
    assert "completed だが pending/blocked 残" in result.stderr

    bound_dir = tmp_path / "bound"
    bound_dir.mkdir()
    bound, bound_trace = _write_case(
        bound_dir,
        _progress([_item("C1"), _item("C2")], iteration=0, max_loops=1, status="in_progress"),
        [_row(0, ["C1", "C2"], "C1")],
    )
    result = _run(bound, bound_trace)
    assert result.returncode == 1
    assert "bound 不足" in result.stderr


def test_dependency_must_be_past_done(tmp_path: Path) -> None:
    progress, trace = _write_case(
        tmp_path,
        _progress(
            [_item("C1", status="pending"), _item("C2", depends_on=["C1"])],
            iteration=1,
            max_loops=2,
            status="in_progress",
        ),
        [_row(0, ["C1"], "C1"), _row(1, ["C2"], "C2")],
    )
    result = _run(progress, trace)
    assert result.returncode == 1
    assert "過去周回で done でない" in result.stderr
