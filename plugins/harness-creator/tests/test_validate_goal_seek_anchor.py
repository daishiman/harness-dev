from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    ROOT
    / "plugins/harness-creator/skills/run-build-skill/templates/goal-seek-runtime/scripts"
    / "validate-inline-goal-seek-anchor.py"
)
SPEC = importlib.util.spec_from_file_location("validate_goal_seek_anchor", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    goal = "初回のゴール"
    progress = tmp_path / "progress.json"
    intermediate = tmp_path / "intermediate.jsonl"
    progress.write_text(
        json.dumps({"original_goal_hash": hashlib.sha256(goal.encode()).hexdigest()}),
        encoding="utf-8",
    )
    row = {
        "iteration": 0,
        "original_goal": goal,
        "current_goal_snapshot": goal,
        "delta_from_original": "",
        "merged_directive_for_next": goal,
        "drift_signal": "initial",
    }
    intermediate.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return progress, intermediate, goal


def test_valid_anchor_passes(tmp_path: Path) -> None:
    progress, intermediate, _goal = _fixture(tmp_path)
    code, message = MODULE.validate(progress, intermediate)
    assert code == 0
    assert "PASS" in message


def test_missing_hash_fails_closed(tmp_path: Path) -> None:
    progress, intermediate, _goal = _fixture(tmp_path)
    progress.write_text("{}", encoding="utf-8")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "missing/drift" in message


def test_drift_and_missing_trace_fail_closed(tmp_path: Path) -> None:
    progress, intermediate, goal = _fixture(tmp_path)
    row = {
        "iteration": 1,
        "original_goal": goal + " drift",
        "current_goal_snapshot": "",
        "delta_from_original": "",
        "merged_directive_for_next": "",
        "drift_signal": "widening",
    }
    with intermediate.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    assert MODULE.validate(progress, intermediate)[0] == 1
    assert MODULE.validate(progress, tmp_path / "missing.jsonl")[0] == 1
