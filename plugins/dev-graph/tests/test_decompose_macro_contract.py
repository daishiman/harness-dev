from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml


PLUGIN = Path(__file__).resolve().parents[1]
DECOMPOSE = PLUGIN / "skills" / "run-dev-graph-decompose" / "SKILL.md"
NODE = PLUGIN / "skills" / "run-dev-graph-node" / "SKILL.md"
GOAL_VALIDATOR = PLUGIN / "scripts" / "validate-goal-seek-runtime.py"
COMPOSITION = PLUGIN / "plugin-composition.yaml"


def _frontmatter(text: str) -> dict:
    return yaml.safe_load(text.split("\n---\n", 1)[0][4:])


def test_decompose_and_node_expose_one_c02_macro_contract() -> None:
    decompose = DECOMPOSE.read_text(encoding="utf-8")
    node = NODE.read_text(encoding="utf-8")
    frontmatter = _frontmatter(decompose)

    assert "../../scripts/register-package.py" in frontmatter["script_refs"]
    assert "../../scripts/validate-goal-seek-runtime.py" in frontmatter["script_refs"]
    assert "../../schemas/macro-intent.schema.json" in frontmatter["schema_refs"]
    assert "../../schemas/macro-registration-receipt.schema.json" in frontmatter["schema_refs"]
    for text in (decompose, node):
        assert "preview-macro" in text
        assert "apply-macro" in text
        assert "--expected-candidate-digest" in text
        assert "C11/validate-graph-schema.py" in text
    assert "`architecture_refs` は入力せず" in decompose
    assert "C02が唯一のtop-level architectureから全featureへ導出" in decompose


def test_decompose_runtime_dependencies_are_declared_once() -> None:
    composition = yaml.safe_load(COMPOSITION.read_text(encoding="utf-8"))
    edges = {
        (edge["from"], edge["to"], edge["type"])
        for edge in composition["dependencies"]
    }
    assert (
        "skills/run-dev-graph-decompose", "scripts/register-package.py", "calls"
    ) in edges
    assert (
        "skills/run-dev-graph-decompose", "scripts/validate-goal-seek-runtime.py", "calls"
    ) in edges
    support = {
        row["ref"]: row for row in composition["internal_support"]
    }
    assert "C14" in support["scripts/validate-goal-seek-runtime.py"]["owners"]


def test_dry_run_goal_validation_uses_memory_and_writes_nothing(tmp_path: Path) -> None:
    original = "macro goal"
    digest = hashlib.sha256(original.encode()).hexdigest()
    goal = {"original_goal": original, "original_goal_hash": digest}
    progress = {"original_goal_hash": digest, "checklist": {"macro": {"status": "pending"}}}
    row = {
        "iteration": 1,
        "original_goal": original,
        "original_goal_hash": digest,
        "current_goal_snapshot": original,
        "delta_from_original": [],
        "merged_directive_for_next": original,
        "drift_signal": False,
    }
    before = list(tmp_path.rglob("*"))
    valid = subprocess.run(
        [
            sys.executable, str(GOAL_VALIDATOR),
            "--goal-spec-json", json.dumps(goal),
            "--progress-json", json.dumps(progress),
            "--intermediate-jsonl", json.dumps(row),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert list(tmp_path.rglob("*")) == before

    row["original_goal_hash"] = "0" * 64
    invalid = subprocess.run(
        [
            sys.executable, str(GOAL_VALIDATOR),
            "--goal-spec-json", json.dumps(goal),
            "--progress-json", json.dumps(progress),
            "--intermediate-jsonl", json.dumps(row),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert invalid.returncode != 0
    assert list(tmp_path.rglob("*")) == before
