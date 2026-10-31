"""C11 の stdin preview (`--graph -`) は未作成 artifact だけを許し、正本 store 検証は fail-closed のまま。

decompose の dry-run は「まだ書いていない node」を preview として流すのが正当な用途なので、
`artifact_missing` をそこでだけ免除する。存在する artifact の frontmatter 不整合は preview でも落とす。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


def issue_node(graph_node_id: str, file_path: str) -> dict:
    now = "2026-07-13T00:00:00Z"
    return {
        "graph_node_id": graph_node_id,
        "artifact_kind": "issue",
        "artifact_subtypes": [],
        "title": "Not yet written",
        "project_id": "project",
        "domain": "runtime",
        "status": "draft",
        "owners": ["team"],
        "tags": ["test"],
        "priority": None,
        "start_date": None,
        "target_date": None,
        "iteration": None,
        "created_at": now,
        "updated_at": now,
        "depends_on": [],
        "related_nodes": [],
        "resource_scope": ["issues"],
        "purpose": None,
        "goal": None,
        "scope_in": [],
        "scope_out": [],
        "acceptance": [],
        "architecture_refs": [],
        "parent_feature": None,
        "feature_package_id": None,
        "phase_ref": None,
        "file_path": file_path,
        "template_id": "issue",
        "template_version": "1.0.0",
        "confirmation_status": "draft",
        "evaluation_status": "pending",
        "confirmation_evidence": {"evaluator": None, "evidence_ref": None, "evaluated_digest": None},
        "source_lineage": {
            "origin_kind": "manual",
            "source_plugin": None,
            "source_path": None,
            "source_version": None,
            "source_digest": None,
            "imported_at": None,
        },
        "classification_confidence": 1.0,
        "classification_reason": "explicit test fixture",
        "classification_candidates": [],
        "github_publication": {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": None},
        "issue_linkage": None,
        "tracker_binding": "none",
        "beads_linkage": None,
        "github_project_linkages": [],
        "pull_request_linkages": [],
        "execution_contexts": [],
        "completion_evidence": {
            "policy": "manual",
            "status": "not_applicable",
            "source": None,
            "completed_at": None,
            "reconciled_at": None,
            "evidence_refs": [],
        },
        "implementation_readiness": {"status": "incomplete", "missing_sections": [], "checked_at": None},
    }


def run_validate(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / "validate-graph-schema.py"), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def violation_codes(proc: subprocess.CompletedProcess) -> set[str]:
    return {item["code"] for item in json.loads(proc.stdout)["violations"]}


def test_canonical_store_rejects_not_yet_written_artifact(tmp_path) -> None:
    root = tmp_path / "repo"
    state = root / ".dev-graph" / "state"
    state.mkdir(parents=True)
    node = issue_node("not-yet-written", "issues/not-yet-written.md")
    graph_path = state / "graph.json"
    graph_path.write_text(
        json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": [node]}),
        encoding="utf-8",
    )

    proc = run_validate("--graph", str(graph_path), "--repo-root", str(root))

    assert proc.returncode == 1, proc.stderr
    result = json.loads(proc.stdout)
    assert result["valid"] is False
    assert {
        "node": "not-yet-written",
        "code": "artifact_missing",
        "detail": "issues/not-yet-written.md",
    } in result["violations"]


def test_stdin_preview_skips_only_absent_artifacts(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / ".dev-graph" / "state").mkdir(parents=True)
    absent = issue_node("not-yet-written", "issues/not-yet-written.md")

    proc = run_validate("--graph", "-", "--repo-root", str(root), stdin=json.dumps({"nodes": [absent]}))
    assert proc.returncode == 0, proc.stdout
    assert json.loads(proc.stdout)["valid"] is True

    broken = root / "issues" / "broken.md"
    broken.parent.mkdir(parents=True)
    broken.write_text("not frontmatter\n", encoding="utf-8")
    present = issue_node("broken", "issues/broken.md")
    proc = run_validate("--graph", "-", "--repo-root", str(root), stdin=json.dumps({"nodes": [absent, present]}))
    assert proc.returncode == 1, proc.stderr
    assert "frontmatter_invalid" in violation_codes(proc)
    assert "artifact_missing" not in violation_codes(proc)


def test_stdin_preview_requires_repo_root_and_valid_json(tmp_path) -> None:
    missing_root = run_validate("--graph", "-", stdin='{"nodes": []}')
    assert missing_root.returncode != 0
    assert "--repo-root" in missing_root.stderr

    broken_json = run_validate("--graph", "-", "--repo-root", str(tmp_path), stdin="{not json")
    assert broken_json.returncode != 0
    assert "not valid JSON" in broken_json.stderr
