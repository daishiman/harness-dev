"""graph-node schema の任意 metadata (`mvp_alignment` と document の `layer`) を C11 が受け入れる境界。

MVP 判断 3 軸 (目的・背景・MVP 適合度) を持つ task は正本 store として登録でき、
enum 外の `mvp_fit`・未知キー・必須サブ項目の欠落は schema_violation で落ちる。
省略と null は既存 node を invalid 化しない。`layer` は document だけが任意で持てる
小文字 kebab-case の役割名で、他の kind に置くと落ちる。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"

MVP_ALIGNMENT = {
    "mvp_fit": "direct",
    "purpose": "動くMVPを最短で出すための中核機能",
    "background": "品質系タスクが先に選定されMVPが後回しになった",
    "rationale": "ユーザー価値に直結する経路のためdirect",
}


def node_fixture(graph_node_id: str, kind: str = "task", **extra) -> dict:
    root = {"task": "tasks", "document": "docs"}[kind]
    file_path = f"{root}/{graph_node_id}.md"
    now = "2026-07-20T00:00:00Z"
    node = {
        "graph_node_id": graph_node_id,
        "artifact_kind": kind,
        "artifact_subtypes": [],
        "title": "Schema registration fixture",
        "project_id": "project",
        "domain": "runtime",
        "status": "draft",
        "owners": ["team"],
        "tags": ["dev-graph"],
        "priority": None,
        "start_date": None,
        "target_date": None,
        "iteration": None,
        "created_at": now,
        "updated_at": now,
        "depends_on": [],
        "related_nodes": [],
        "resource_scope": [file_path],
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
        "template_id": kind,
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
    node.update(extra)
    return node


def write_artifact(root: Path, node: dict) -> None:
    lines = ["---", *(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in node.items()), "---", ""]
    lines.extend(["# fixture", "", "schema registration fixture の本文。"])
    target = root / node["file_path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_store(tmp_path: Path, nodes: list[dict]) -> tuple[int, dict]:
    root = tmp_path / "repo"
    state = root / ".dev-graph" / "state"
    state.mkdir(parents=True)
    for node in nodes:
        write_artifact(root, node)
    graph = state / "graph.json"
    graph.write_text(json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": nodes}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / "validate-graph-schema.py"), "--graph", str(graph), "--repo-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, json.loads(proc.stdout)


def schema_details(report: dict) -> list[str]:
    return [item["detail"] for item in report["violations"] if item["code"] == "schema_violation"]


def test_mvp_metadata_task_registers(tmp_path) -> None:
    code, report = validate_store(tmp_path, [node_fixture("task-mvp-full", mvp_alignment=dict(MVP_ALIGNMENT))])
    assert code == 0, report
    assert report["valid"] is True and report["violations"] == []


def test_mvp_metadata_omitted_or_null_keeps_existing_nodes_valid(tmp_path) -> None:
    nodes = [node_fixture("task-mvp-omitted"), node_fixture("task-mvp-null", mvp_alignment=None)]
    code, report = validate_store(tmp_path, nodes)
    assert code == 0, report
    assert report["violations"] == []


def test_mvp_metadata_rejects_unknown_fit_extra_key_and_missing_axis(tmp_path) -> None:
    partial = {key: value for key, value in MVP_ALIGNMENT.items() if key != "purpose"}
    cases = {
        "mvp_fit": {**MVP_ALIGNMENT, "mvp_fit": "urgent"},
        "priority": {**MVP_ALIGNMENT, "priority": "high"},
        "purpose": partial,
    }
    for index, (field, value) in enumerate(cases.items()):
        code, report = validate_store(tmp_path / str(index), [node_fixture(f"task-mvp-{index}", mvp_alignment=value)])
        assert code == 1, field
        assert any(field in detail for detail in schema_details(report)), (field, report)


def test_document_layer_is_optional_and_kebab_case(tmp_path) -> None:
    code, report = validate_store(
        tmp_path / "ok",
        [node_fixture("doc-with-layer", "document", layer="feature-design"), node_fixture("doc-without-layer", "document")],
    )
    assert code == 0, report

    for index, invalid in enumerate(("Feature-Design", "feature_design", "-design", "")):
        code, report = validate_store(tmp_path / f"bad{index}", [node_fixture(f"doc-bad-{index}", "document", layer=invalid)])
        assert code == 1, invalid
        assert any("layer" in detail for detail in schema_details(report)), (invalid, report)


def test_non_document_cannot_declare_layer(tmp_path) -> None:
    code, report = validate_store(tmp_path, [node_fixture("task-with-layer", layer="feature-design")])
    assert code == 1
    assert any("layer" in detail for detail in schema_details(report)), report
