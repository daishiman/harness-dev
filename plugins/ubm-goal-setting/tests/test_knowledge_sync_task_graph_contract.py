from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = PLUGIN_ROOT / "skills/run-ubm-knowledge-sync"
SKILL = SKILL_DIR / "SKILL.md"
MANIFEST = SKILL_DIR / "workflow-manifest.json"
TEMPLATE_SCRIPTS = (
    REPO_ROOT
    / "plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts"
)
ENGINE_ASSETS = (
    "extract-ready-set-from-checklist.py",
    "build-self-reflection-entry.py",
    "extract-capability-dependency-graph.py",
    "build-capability-graph-knowledge-entry.py",
)
TRACE_VALIDATOR = SKILL_DIR / "scripts/validate-knowledge-sync-task-graph.py"
GOAL = "UBM knowledge sync を依存順に完了する"


def _goal_seek_block(text: str) -> str:
    match = re.search(r"^goal_seek:\n(?P<body>(?:^  .*\n)+)", text, re.MULTILINE)
    assert match is not None
    return match.group("body")


def test_knowledge_sync_uses_safe_task_graph_profile() -> None:
    text = SKILL.read_text(encoding="utf-8")
    goal_seek = _goal_seek_block(text)
    assert "  engine: task-graph\n" in goal_seek
    assert "  engine_profile: checklist-graph\n" in goal_seek
    assert "  full_task_spec_graph: false\n" in goal_seek
    assert "  fork: inline\n" in goal_seek
    assert "ready_set" in text and "selected_item" in text
    assert "self-reflect 完了 gate" in text
    assert "preview 後の exact reply は親が受け" in text
    assert '"$PROJECT_ROOT/eval-log/' in text
    assert 'skills/run-ubm-knowledge-sync/scripts/extract-ready-set-from-checklist.py' in text
    assert '../../scripts/validate-inline-goal-seek-anchor.py' in text
    assert 'scripts/validate-knowledge-sync-task-graph.py' in text
    assert "`--dry-run` では extract 結果を eval-log 内でのみ consult" in text
    assert "record と plugin `knowledge/` write を no-op trace" in text


def test_manifest_serializes_corpus_writers_before_graph_reader() -> None:
    phases = json.loads(MANIFEST.read_text(encoding="utf-8"))["phases"]
    assert [phase["id"] for phase in phases] == [
        "phase1-detect",
        "phase2-extract",
        "phase3-split-check",
        "phase5-graph-sync",
        "phase4-report",
    ]
    assert {phase["id"]: phase.get("dependsOn", []) for phase in phases} == {
        "phase1-detect": [],
        "phase2-extract": ["phase1-detect"],
        "phase3-split-check": ["phase2-extract"],
        "phase5-graph-sync": ["phase3-split-check"],
        "phase4-report": ["phase5-graph-sync"],
    }
    assert all(phase["parallel"] is False for phase in phases)


def test_task_graph_engine_assets_match_harness_creator_template() -> None:
    for name in ENGINE_ASSETS:
        assert (SKILL_DIR / "scripts" / name).read_bytes() == (
            TEMPLATE_SCRIPTS / name
        ).read_bytes()


def test_subagent_references_have_task_runtime_and_real_agents() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert re.search(r"^  - Task$", text, re.MULTILINE)
    for name in ("knowledge-extractor", "knowledge-relation-extractor"):
        assert (PLUGIN_ROOT / "agents" / f"{name}.md").is_file()


def test_sync_recovery_and_external_io_boundary_are_explicit() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    extractor = (PLUGIN_ROOT / "agents/knowledge-extractor.md").read_text(encoding="utf-8")
    assert "registry の `(file_path,file_hash,status=processed)` を唯一の commit point" in skill
    assert "1トランザクション扱い" not in skill
    assert "idempotency_key = sha256" in extractor
    assert "source の最終 commit point として最後に" in extractor
    assert "vault source は常に read-only" in extractor
    assert "write target が symlink" in extractor


def _item(item_id: str, *, depends_on: list[str] | None = None, status: str = "done") -> dict:
    item = {"id": item_id, "text": item_id, "status": status}
    if depends_on:
        item["depends_on"] = depends_on
    return item


def _row(iteration: int, ready: list[str], selected: str | None) -> dict:
    return {
        "iteration": iteration,
        "original_goal": GOAL,
        "current_goal_snapshot": GOAL,
        "delta_from_original": "",
        "merged_directive_for_next": "next",
        "drift_signal": "aligned",
        "ready_set": ready,
        "selected_item": selected,
    }


def _run_trace(
    tmp_path: Path,
    checklist: list[dict],
    rows: list[dict],
    *,
    status: str = "completed",
    max_loops: int = 9,
) -> subprocess.CompletedProcess[str]:
    progress = {
        "engine": "task-graph",
        "iteration": len(rows) - 1,
        "max_loops": max_loops,
        "status": status,
        "original_goal_hash": hashlib.sha256(GOAL.encode()).hexdigest(),
        "checklist": checklist,
    }
    progress_path = tmp_path / "progress.json"
    trace_path = tmp_path / "intermediate.jsonl"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    trace_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            str(TRACE_VALIDATOR),
            str(progress_path),
            str(trace_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def _core_chain() -> list[dict]:
    return [
        _item("C1"),
        _item("C2", depends_on=["C1"]),
        _item("C3", depends_on=["C2"]),
        _item("C4", depends_on=["C3"]),
        _item("C5", depends_on=["C4"]),
        _item("C6", depends_on=["C5"]),
    ]


def test_task_graph_trace_recomputes_exact_ready_set(tmp_path: Path) -> None:
    checklist = _core_chain()
    rows = [_row(i, [f"C{i + 1}"], f"C{i + 1}") for i in range(6)]
    result = _run_trace(tmp_path, checklist, rows)
    assert result.returncode == 0, result.stderr
    assert "knowledge-sync task-graph PASS" in result.stdout

    rows[0]["ready_set"] = []
    result = _run_trace(tmp_path, checklist, rows)
    assert result.returncode == 1
    assert "ready_set 不整合" in result.stderr


def test_task_graph_trace_rejects_chain_drift_and_cycle(tmp_path: Path) -> None:
    checklist = _core_chain()
    checklist[2]["depends_on"] = ["C1"]
    result = _run_trace(tmp_path, checklist, [_row(0, ["C1"], "C1")], status="in_progress")
    assert result.returncode == 1
    assert "required chain drift" in result.stderr

    cycle_dir = tmp_path / "cycle"
    cycle_dir.mkdir()
    checklist = _core_chain()
    checklist[0]["depends_on"] = ["C6"]
    result = _run_trace(cycle_dir, checklist, [_row(0, [], None)], status="in_progress")
    assert result.returncode == 1
    assert "depends_on cycle" in result.stderr


def test_task_graph_trace_includes_reflected_item_and_completion_gate(tmp_path: Path) -> None:
    checklist = _core_chain()
    checklist.append(
        {
            "id": "C7",
            "text": "reflected",
            "status": "done",
            "depends_on": ["C5"],
            "created_iteration": 4,
            "available_from_iteration": 5,
        }
    )
    rows = [_row(i, [f"C{i + 1}"], f"C{i + 1}") for i in range(5)]
    rows.append(_row(5, ["C7"], "C7"))
    rows.append(_row(6, ["C6"], "C6"))
    result = _run_trace(tmp_path, checklist, rows)
    assert result.returncode == 0, result.stderr

    early_gate = list(rows)
    early_gate[5] = _row(5, ["C6", "C7"], "C6")
    result = _run_trace(tmp_path, checklist, early_gate)
    assert result.returncode == 1
    assert "ready_set 不整合" in result.stderr

    checklist[-1]["status"] = "pending"
    result = _run_trace(tmp_path, checklist, rows)
    assert result.returncode == 1
    assert "doneでない" in result.stderr


def test_task_graph_trace_rejects_missing_done_trace_and_short_bound(tmp_path: Path) -> None:
    checklist = _core_chain()
    result = _run_trace(tmp_path, checklist, [_row(0, ["C1"], "C1")])
    assert result.returncode == 1
    assert "done だが selected_item 証跡なし" in result.stderr

    bound_dir = tmp_path / "bound"
    bound_dir.mkdir()
    result = _run_trace(
        bound_dir,
        checklist,
        [_row(0, ["C1"], "C1")],
        status="in_progress",
        max_loops=5,
    )
    assert result.returncode == 1
    assert "bound 不足" in result.stderr


def test_completion_gate_waits_for_future_available_reflected_item(tmp_path: Path) -> None:
    checklist = _core_chain()
    checklist.append(
        {
            "id": "C7",
            "text": "reflected next iteration",
            "status": "done",
            "depends_on": ["C5"],
            "created_iteration": 5,
            "available_from_iteration": 6,
        }
    )
    rows = [_row(i, [f"C{i + 1}"], f"C{i + 1}") for i in range(5)]
    rows.extend(
        [
            _row(5, [], None),
            _row(6, ["C7"], "C7"),
            _row(7, ["C6"], "C6"),
        ]
    )
    result = _run_trace(tmp_path, checklist, rows)
    assert result.returncode == 0, result.stderr
