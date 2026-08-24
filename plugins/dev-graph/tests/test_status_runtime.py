from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
INIT = PLUGIN / "skills" / "run-dev-graph-init" / "scripts" / "build-dev-graph.py"
WRITER = PLUGIN / "scripts" / "register-package.py"
STATUS = PLUGIN / "scripts" / "extract-graph-status.py"
TASK_SECTIONS = json.loads(
    (PLUGIN / "templates" / "template-contract.json").read_text(encoding="utf-8")
)["artifacts"]["task"]["required_sections"]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)


def _task_body(title: str) -> str:
    lines: list[str] = []
    for index, heading in enumerate(TASK_SECTIONS):
        lines.extend([f"{'#' if index == 0 else '##'} {heading}", "", f"{title}: verified {heading}.", ""])
    return "\n".join(lines).rstrip() + "\n"


def _decision(index: int, title: str, *, depends_on: list[str]) -> dict[str, object]:
    return {
        "input_index": index,
        "artifact_kind": "task",
        "artifact_subtypes": [],
        "project_id": "status-runtime",
        "domain": "runtime",
        "owners": ["dev-graph"],
        "tags": ["status-runtime"],
        "priority": None,
        "resource_scope": [f"status-runtime/{index}"],
        "classification_confidence": 0.95,
        "classification_reason": "The input is a bounded execution task with explicit acceptance evidence.",
        "classification_candidates": [{"artifact_kind": "issue", "confidence": 0.05}],
        "decision_source": "automatic",
        "tracker_binding": "none",
        "depends_on_titles": depends_on,
        "related_node_titles": [],
        "architecture_ref_titles": [],
        "rendered_body": _task_body(title),
    }


def _run(*command: str, expected: int = 0) -> dict[str, object]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == expected, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _digests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }


def test_init_node_can_prepare_closed_dependency_and_status_is_exactly_read_only(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-qm", "fixture")

    initialized = _run(
        sys.executable, str(INIT), "--repo-root", str(root), "--hook-source", "plugin",
    )
    assert initialized["owner"] == "C01/run-dev-graph-init"
    assert initialized["readiness"]["graph"]["valid"] is True  # type: ignore[index]

    prerequisite_title = "Prepare status dependency"
    target_title = "Inspect historical closed task"
    input_path = root / "status-runtime-input.json"
    plan_path = root / "status-runtime-plan.json"
    state_path = root / "status-runtime-initial-state.json"
    _write_json(input_path, {
        "batch_id": "STATUS-RUNTIME-001",
        "artifacts": [
            {"title": prerequisite_title, "body": "A prerequisite for the status query."},
            {"title": target_title, "body": "A historical task whose closed state must be queried."},
        ],
    })
    _write_json(plan_path, {
        "schema_version": "1.0.0",
        "observed_at": "2026-08-24T12:00:00Z",
        "decisions": [
            _decision(0, prerequisite_title, depends_on=[]),
            _decision(1, target_title, depends_on=[prerequisite_title]),
        ],
    })
    _write_json(state_path, {
        "schema_version": "1.0.0",
        "states": [{
            "input_index": 1,
            "status": "closed",
            "closed_at": "2026-08-20T12:00:00Z",
        }],
    })

    before_preview = _digests(root)
    preview = _run(
        sys.executable, str(WRITER), "artifacts", "--repo-root", str(root),
        "--input", str(input_path), "--plan", str(plan_path),
        "--initial-state", str(state_path), "--dry-run",
    )
    assert preview["status"] == "dry_run"
    assert preview["write_count"] == 0
    assert _digests(root) == before_preview

    applied = _run(
        sys.executable, str(WRITER), "artifacts", "--repo-root", str(root),
        "--input", str(input_path), "--plan", str(plan_path),
        "--initial-state", str(state_path),
    )
    assert applied["owner"] == "C02/run-dev-graph-node"
    assert applied["c11_staged"]["valid"] is True  # type: ignore[index]
    assert [row["initial_state"] for row in applied["applied"]] == [  # type: ignore[index]
        None,
        {"status": "closed", "closed_at": "2026-08-20T12:00:00Z"},
    ]
    prerequisite_id, target_id = [row["graph_node_id"] for row in applied["applied"]]  # type: ignore[index]

    stable_graph = (root / ".dev-graph/state/graph.json").read_bytes()
    repeated = _run(
        sys.executable, str(WRITER), "artifacts", "--repo-root", str(root),
        "--input", str(input_path), "--plan", str(plan_path),
        "--initial-state", str(state_path),
    )
    assert repeated["applied"] == [] and len(repeated["unchanged"]) == 2
    assert (root / ".dev-graph/state/graph.json").read_bytes() == stable_graph

    nonlocal_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    nonlocal_plan["decisions"][1]["tracker_binding"] = "auto"
    _write_json(plan_path, nonlocal_plan)
    rejected = _run(
        sys.executable, str(WRITER), "artifacts", "--repo-root", str(root),
        "--input", str(input_path), "--plan", str(plan_path),
        "--initial-state", str(state_path), expected=2,
    )
    assert "local-only" in rejected["error"]
    assert (root / ".dev-graph/state/graph.json").read_bytes() == stable_graph
    nonlocal_plan["decisions"][1]["tracker_binding"] = "none"
    _write_json(plan_path, nonlocal_plan)

    before_status = _digests(root)
    report = _run(
        sys.executable, str(STATUS), "--repo-root", str(root), "--id", target_id,
    )
    assert _digests(root) == before_status
    assert report["owner"] == "C18/run-dev-graph-status"
    assert report["operation"] == "status_search"
    assert report["result_count"] == 1
    assert report["results"] == [{
        "graph_node_id": target_id,
        "artifact_kind": "task",
        "project_id": "status-runtime",
        "domain": "runtime",
        "tags": ["status-runtime"],
        "file_path": f"tasks/{target_id}.md",
        "status": "closed",
        "closed_at": "2026-08-20T12:00:00Z",
        "depends_on": [prerequisite_id],
        "dependents": [],
        "parent_feature": None,
        "feature_package_id": None,
        "tracker_binding": "none",
        "linkage": {
            "issue_linkage": None,
            "beads_linkage": None,
            "github_project_linkages": [],
            "pull_request_linkages": [],
        },
    }]
    assert report["c11"] == {"valid": True, "violations": []}
    assert report["digests_unchanged"] is True
    assert report["digest_evidence"]["file_count"] == 4  # type: ignore[index]
    assert report["digest_evidence"]["sha256_before"] == report["digest_evidence"]["sha256_after"]  # type: ignore[index]
    assert report["write_count"] == 0
    assert report["external_writes"] == {"github": 0, "beads": 0}
    assert not (root / ".beads").exists()
    source = STATUS.read_text(encoding="utf-8")
    assert "gh-bridge.py" not in source and "bd-bridge.py" not in source

    empty = _run(
        sys.executable, str(STATUS), "--repo-root", str(root), "--id", "missing-node",
    )
    assert empty["result_count"] == 0 and empty["results"] == []
