from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render-graph-html.py"
PHASES = [f"P{index:02d}" for index in range(1, 14)]


def absolute_stored_paths(value: object, location: str = "$") -> list[str]:
    if isinstance(value, dict):
        return [
            finding
            for key, child in value.items()
            for finding in absolute_stored_paths(child, f"{location}.{key}")
        ]
    if isinstance(value, list):
        return [
            finding
            for index, child in enumerate(value)
            for finding in absolute_stored_paths(child, f"{location}[{index}]")
        ]
    if isinstance(value, str) and Path(value).is_absolute():
        return [location]
    return []


def package_fixture(
    done_count: int = 2,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    feature_id = "feature"
    package_id = "feature-package/feature"
    digest_hex = "a" * 64
    node_ids = [f"feature-P{index:02d}" for index in range(1, 14)]
    nodes: list[dict[str, object]] = [
        {
            "id": "feature-base",
            "title": "Base feature",
            "artifact_kind": "feature",
            "status": "done",
            "depends_on": [],
        },
        {
            "id": feature_id,
            "title": "<Feature>",
            "artifact_kind": "feature",
            "status": "active",
            "depends_on": ["feature-base"],
        },
    ]
    for index, node_id in enumerate(node_ids, 1):
        nodes.append(
            {
                "id": node_id,
                "title": "<First task>" if index == 1 else node_id,
                "artifact_kind": "task",
                "status": "done" if index <= done_count else "active",
                "parent_feature": feature_id,
                "feature_package_id": package_id,
                "phase_ref": f"P{index:02d}",
                "depends_on": ["feature-base"] if index == 1 else [node_ids[index - 2]],
                "source_lineage": {"source_digest": digest_hex},
            }
        )
    nodes.append(
        {
            "id": "unrelated",
            "title": "Outside scope",
            "artifact_kind": "document",
            "status": "draft",
            "depends_on": [],
        }
    )
    receipt: dict[str, object] = {
        "schema_version": "1.0.0",
        "status": "registered",
        "registered_at": "2026-08-24T00:00:00Z",
        "feature_package_id": package_id,
        "parent_feature": feature_id,
        "source_digest": "sha256:" + digest_hex,
        "expected_count": 13,
        "applied_count": 13,
        "phase_refs": PHASES,
        "node_ids": node_ids,
        "graph_revision_before": 0,
        "graph_revision_after": 1,
        "graph_digest_after": "sha256:" + "b" * 64,
        "output_path": "system-plan/package.json",
    }
    return nodes, receipt


def invoke(
    graph: Path,
    out: Path,
    *,
    repo_root: Path | None = None,
    scope: str | None = None,
    receipts: list[Path] | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(SCRIPT),
        "--repo-root",
        str(repo_root or graph.parent),
        "--graph",
        str(graph),
        "--out",
        str(out),
    ]
    if scope is not None:
        argv.extend(["--scope", scope])
    for receipt in receipts or []:
        argv.extend(["--registration-receipt", str(receipt)])
    return subprocess.run(argv, check=False, capture_output=True, text=True)


def test_scope_progress_edge_kinds_lineage_and_digests_are_deterministic(
    tmp_path: Path,
) -> None:
    nodes, receipt = package_fixture(done_count=2)
    graph = tmp_path / "graph.json"
    graph.write_bytes(json.dumps({"nodes": nodes}, sort_keys=True).encode("utf-8"))
    receipt_path = tmp_path / "registration.json"
    receipt_path.write_bytes(json.dumps(receipt, sort_keys=True).encode("utf-8"))

    first_out = tmp_path / "first.html"
    first = invoke(graph, first_out, scope="feature", receipts=[receipt_path])
    assert first.returncode == 0, first.stderr
    result = json.loads(first.stdout)

    assert result["scope"] == "feature"
    assert result["nodes"] == 15
    assert "feature-base" in result["scope_node_ids"]
    assert "unrelated" not in result["scope_node_ids"]
    assert result["edges"] == 14
    assert result["edge_counts"] == {"feature": 1, "task": 12, "other": 1}
    assert result["feature_progress"] == {
        "aggregate": {"done": 2, "total": 13},
        "by_feature": {
            "feature": {"done": 2, "total": 13},
            "feature-base": {"done": 0, "total": 0},
        },
    }
    evidence = result["registration_evidence"]["feature"]
    assert evidence["expected_count"] == evidence["applied_count"] == 13
    assert evidence["node_ids"] == receipt["node_ids"]
    assert evidence["feature_package_id"] == receipt["feature_package_id"]
    assert evidence["source_digest"] == receipt["source_digest"]
    assert (
        evidence["receipt_sha256"]
        == "sha256:" + hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    )
    assert result["out"] == "first.html"
    assert evidence["receipt"] == "registration.json"
    assert absolute_stored_paths(result) == []
    assert result["input_sha256"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    assert result["output_sha256"] == hashlib.sha256(first_out.read_bytes()).hexdigest()
    assert result["render_model_sha256"].startswith("sha256:")

    document = first_out.read_text(encoding="utf-8")
    assert "&lt;First task&gt;" in document
    assert "active · feature · 2/13" in document
    assert 'class="edge edge-feature"' in document
    assert 'class="edge edge-task"' in document
    assert 'class="edge edge-other"' in document
    assert 'aria-label="Edge legend"' in document
    assert "https://" not in document and "http://" not in document
    assert "<script src=" not in document and "<link " not in document

    second_out = tmp_path / "second.html"
    second = invoke(graph, second_out, scope="feature", receipts=[receipt_path])
    assert second.returncode == 0, second.stderr
    repeated = json.loads(second.stdout)
    assert second_out.read_bytes() == first_out.read_bytes()
    assert repeated["render_model_sha256"] == result["render_model_sha256"]
    assert repeated["output_sha256"] == result["output_sha256"]


def test_task_scope_expands_to_parent_package_and_dependencies(tmp_path: Path) -> None:
    nodes, receipt = package_fixture()
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    receipt_path = tmp_path / "registration.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    out = tmp_path / "task-scope.html"
    completed = invoke(graph, out, scope="feature-P07", receipts=[receipt_path])
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["nodes"] == 15
    assert set(receipt["node_ids"]) <= set(result["scope_node_ids"])
    assert {"feature", "feature-base"} <= set(result["scope_node_ids"])
    assert "unrelated" not in result["scope_node_ids"]


def test_registration_contract_and_scope_fail_closed_before_output(
    tmp_path: Path,
) -> None:
    nodes, receipt = package_fixture()
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")

    cases: list[tuple[str, dict[str, object] | None, str, list[Path] | None]] = []
    cases.append(("missing-receipt", None, "registration receipt missing", []))
    cases.append(
        (
            "missing-path",
            None,
            "registration receipt does not exist",
            [tmp_path / "does-not-exist.json"],
        )
    )

    wrong_ids = copy.deepcopy(receipt)
    wrong_ids["node_ids"] = [*receipt["node_ids"][:-1], "other"]
    cases.append(("wrong-ids", wrong_ids, "node_ids do not exactly match", None))

    wrong_order = copy.deepcopy(receipt)
    wrong_order["node_ids"] = list(reversed(receipt["node_ids"]))
    cases.append(
        ("wrong-order", wrong_order, "node_ids are not in exact phase order", None)
    )

    wrong_phases = copy.deepcopy(receipt)
    wrong_phases["phase_refs"] = list(reversed(PHASES))
    cases.append(("wrong-phases", wrong_phases, "phase_refs are not exact", None))

    stale_digest = copy.deepcopy(receipt)
    stale_digest["source_digest"] = "sha256:" + "c" * 64
    cases.append(("stale-digest", stale_digest, "source lineage digest mismatch", None))

    wrong_count = copy.deepcopy(receipt)
    wrong_count["applied_count"] = 12
    cases.append(("wrong-count", wrong_count, "counts do not match", None))

    wrong_package = copy.deepcopy(receipt)
    wrong_package["feature_package_id"] = "feature-package/other"
    cases.append(("wrong-package", wrong_package, "feature_package_id mismatch", None))

    for name, candidate, error, explicit_paths in cases:
        receipt_paths = explicit_paths
        if candidate is not None:
            candidate_path = tmp_path / f"{name}.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            receipt_paths = [candidate_path]
        out = tmp_path / f"{name}.html"
        completed = invoke(graph, out, receipts=receipt_paths)
        assert completed.returncode == 1
        assert error in completed.stderr
        assert not out.exists()

    unknown_scope_out = tmp_path / "unknown-scope.html"
    completed = invoke(graph, unknown_scope_out, scope="unknown")
    assert completed.returncode == 1
    assert "scope node does not exist" in completed.stderr
    assert not unknown_scope_out.exists()


def test_repo_containment_rejects_outside_and_symlink_escape_before_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    nodes, receipt = package_fixture()
    graph = root / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    receipt_path = root / "registration.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    outside_graph = outside / "graph.json"
    outside_graph.write_text(graph.read_text(encoding="utf-8"), encoding="utf-8")
    outside_receipt = outside / "registration.json"
    outside_receipt.write_text(
        receipt_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    cases = [
        ("outside-graph", outside_graph, receipt_path, root / "outside-graph.html"),
        ("outside-receipt", graph, outside_receipt, root / "outside-receipt.html"),
        ("outside-output", graph, receipt_path, outside / "outside-output.html"),
    ]
    for name, candidate_graph, candidate_receipt, candidate_out in cases:
        completed = invoke(
            candidate_graph,
            candidate_out,
            repo_root=root,
            receipts=[candidate_receipt],
        )
        assert completed.returncode == 1, name
        assert "path escapes authority root" in completed.stderr
        assert not candidate_out.exists()

    graph_link = root / "graph-link.json"
    graph_link.symlink_to(outside_graph)
    graph_link_out = root / "graph-link.html"
    completed = invoke(
        graph_link, graph_link_out, repo_root=root, receipts=[receipt_path]
    )
    assert completed.returncode == 1
    assert "path escapes authority root" in completed.stderr
    assert not graph_link_out.exists()

    receipt_link = root / "receipt-link.json"
    receipt_link.symlink_to(outside_receipt)
    receipt_link_out = root / "receipt-link.html"
    completed = invoke(graph, receipt_link_out, repo_root=root, receipts=[receipt_link])
    assert completed.returncode == 1
    assert "path escapes authority root" in completed.stderr
    assert not receipt_link_out.exists()

    output_link = root / "render-link"
    output_link.symlink_to(outside, target_is_directory=True)
    escaped_out = output_link / "index.html"
    completed = invoke(graph, escaped_out, repo_root=root, receipts=[receipt_path])
    assert completed.returncode == 1
    assert "path escapes authority root" in completed.stderr
    assert not escaped_out.exists()

    receipt_before = receipt_path.read_bytes()
    completed = invoke(graph, receipt_path, repo_root=root, receipts=[receipt_path])
    assert completed.returncode == 1
    assert "must not overwrite a registration receipt" in completed.stderr
    assert receipt_path.read_bytes() == receipt_before

    completed = invoke(graph, root, repo_root=root, receipts=[receipt_path])
    assert completed.returncode == 1
    assert "output must be a file path" in completed.stderr


def test_graph_receipt_and_output_reject_internal_symlinks_and_directories_before_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    nodes, receipt = package_fixture()
    graph = root / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    receipt_path = root / "registration.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    graph_link = root / "graph-link.json"
    graph_link.symlink_to(graph.name)
    graph_link_out = root / "graph-link.html"
    completed = invoke(
        graph_link, graph_link_out, repo_root=root, receipts=[receipt_path]
    )
    assert completed.returncode == 1
    assert "graph path must not traverse a symlink" in completed.stderr
    assert not graph_link_out.exists()

    receipt_link = root / "receipt-link.json"
    receipt_link.symlink_to(receipt_path.name)
    receipt_link_out = root / "receipt-link.html"
    completed = invoke(graph, receipt_link_out, repo_root=root, receipts=[receipt_link])
    assert completed.returncode == 1
    assert "registration receipt path must not traverse a symlink" in completed.stderr
    assert not receipt_link_out.exists()

    existing_output = root / "existing.html"
    existing_output.write_text("do not overwrite\n", encoding="utf-8")
    output_link = root / "output-link.html"
    output_link.symlink_to(existing_output.name)
    completed = invoke(graph, output_link, repo_root=root, receipts=[receipt_path])
    assert completed.returncode == 1
    assert "output path must not traverse a symlink" in completed.stderr
    assert existing_output.read_text(encoding="utf-8") == "do not overwrite\n"
    assert output_link.is_symlink()

    internal_directory = root / "directory"
    internal_directory.mkdir()
    for label, candidate_graph, candidate_receipt, candidate_out in (
        ("graph", internal_directory, receipt_path, root / "directory-graph.html"),
        ("registration receipt", graph, internal_directory, root / "directory-receipt.html"),
        ("output", graph, receipt_path, internal_directory),
    ):
        completed = invoke(
            candidate_graph,
            candidate_out,
            repo_root=root,
            receipts=[candidate_receipt],
        )
        assert completed.returncode == 1
        assert label in completed.stderr
        assert internal_directory.is_dir()
