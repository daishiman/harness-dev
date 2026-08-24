from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
WRITER = PLUGIN / "scripts" / "register-package.py"
C11 = PLUGIN / "scripts" / "validate-graph-schema.py"
KINDS = ["issue", "task", "specification", "architecture", "document", "feature"]
TITLES = [
    "Billing PDF fails", "Add queue backoff", "Subscription contract",
    "Billing architecture", "Billing runbook", "Rebuild billing platform",
]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _headings(path: Path) -> list[str]:
    return [match.group(1) for match in re.finditer(r"^#{1,4} (.+)$", path.read_text(encoding="utf-8"), re.M)]


def _body(kind: str, subtypes: list[str], contract: dict[str, object]) -> str:
    artifact_contract = contract["artifacts"][kind]  # type: ignore[index]
    required = artifact_contract["required_sections"]  # type: ignore[index]
    lines: list[str] = []
    for index, heading in enumerate(required):
        lines.extend([f"{'#' if index == 0 else '##'} {heading}", "", f"Verified content for {heading}.", ""])
    if kind == "specification" and "api" in subtypes:
        overlay = _headings(PLUGIN / "templates" / "api-contract.md")
        lines.extend(["### API: create-subscription", "", "Verified API operation.", ""])
        for heading in overlay[1:]:
            lines.extend([f"#### {heading}", "", f"Verified API content for {heading}.", ""])
    if kind == "architecture":
        subtype_templates = artifact_contract["subtype_templates"]  # type: ignore[index]
        for subtype in subtypes:
            overlay = _headings(PLUGIN / "templates" / subtype_templates[subtype])  # type: ignore[index]
            lines.extend([f"### {overlay[0]}", "", f"Verified {subtype} architecture.", ""])
            for heading in overlay[1:]:
                lines.extend([f"#### {heading}", "", f"Verified content for {heading}.", ""])
    return "\n".join(lines).rstrip() + "\n"


def _decision(index: int, kind: str, contract: dict[str, object]) -> dict[str, object]:
    subtypes = ["api"] if kind == "specification" else ["backend", "data", "security"] if kind == "architecture" else []
    dependencies = [TITLES[0]] if kind == "task" else []
    related = [TITLES[1]] if kind == "issue" else []
    architecture_refs = [TITLES[3]] if kind == "specification" else []
    return {
        "input_index": index,
        "artifact_kind": kind,
        "artifact_subtypes": subtypes,
        "project_id": "billing-platform",
        "domain": "billing",
        "owners": ["billing-team"],
        "tags": ["billing"],
        "priority": "high" if kind == "issue" else None,
        "resource_scope": [f"src/{kind}"],
        "classification_confidence": 0.95,
        "classification_reason": f"Fixture is deterministically classified as {kind}.",
        "classification_candidates": [{"artifact_kind": "document" if kind != "document" else "task", "confidence": 0.05}],
        "decision_source": "automatic",
        "tracker_binding": "auto",
        "depends_on_titles": dependencies,
        "related_node_titles": related,
        "architecture_ref_titles": architecture_refs,
        "rendered_body": "" if kind == "feature" else _body(kind, subtypes, contract),
    }


def _run(root: Path, *arguments: str, expected: int = 0) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(WRITER), "artifacts", "--repo-root", str(root), *arguments],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == expected, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, object]]:
    root = tmp_path / "repo"
    root.mkdir()
    for directory in ("issues", "tasks", "specs", "architecture", "features", "docs"):
        (root / directory).mkdir()
    shutil.copytree(PLUGIN / "templates", root / ".dev-graph" / "templates")
    _write_json(root / ".dev-graph" / "config.json", {
        "schema_version": "1.0.0",
        "local_state": {"graph": ".dev-graph/graph.json", "templates": ".dev-graph/templates"},
        "execution_tracker": {"mode": "beads"},
    })
    graph = root / ".dev-graph" / "graph.json"
    _write_json(graph, {"schema_version": "1.0.0", "nodes": []})
    input_path = root / "mixed-artifacts.json"
    payload = {
        "batch_id": "ARTIFACT-BATCH-001",
        "artifacts": [{"title": title, "body": f"Raw semantic source for {title}."} for title in TITLES],
    }
    _write_json(input_path, payload)
    contract = json.loads((PLUGIN / "templates" / "template-contract.json").read_text(encoding="utf-8"))
    plan_path = root / "artifact-plan.json"
    _write_json(plan_path, {
        "schema_version": "1.0.0",
        "observed_at": "2026-08-24T03:00:00Z",
        "decisions": [_decision(index, kind, contract) for index, kind in enumerate(KINDS)],
    })
    return root, input_path, plan_path, payload


def test_maintained_c02_artifact_cli_add_update_dry_run_and_c14(tmp_path: Path) -> None:
    root, input_path, plan_path, payload = _fixture(tmp_path)
    graph_path = root / ".dev-graph" / "graph.json"
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    preview = _run(root, "--input", str(input_path), "--plan", str(plan_path), "--dry-run")
    assert preview["status"] == "dry_run"
    assert len(preview["applied"]) == 5
    assert preview["write_count"] == 0
    assert preview["features_registered"] == 0
    assert preview["c11_staged"]["valid"] is True  # type: ignore[index]
    assert preview["temporary_driver"] is False
    assert before == {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    added = _run(root, "--input", str(input_path), "--plan", str(plan_path))
    assert added["status"] == "applied"
    assert len(added["applied"]) == 5
    assert [item["code"] for item in added["rejected"]] == ["c14_macro_feature_only"]  # type: ignore[index]
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert {node["artifact_kind"] for node in graph["nodes"]} == set(KINDS) - {"feature"}
    assert not list((root / "features").glob("*.md"))
    contract = json.loads((PLUGIN / "templates" / "template-contract.json").read_text(encoding="utf-8"))
    for node in graph["nodes"]:
        assert node["file_path"].startswith(contract["graph_projection"]["root_map"][node["artifact_kind"]])
        artifact_headings = _headings(root / node["file_path"])
        assert set(contract["artifacts"][node["artifact_kind"]]["required_sections"]) <= set(artifact_headings)
    specification = next(node for node in graph["nodes"] if node["artifact_kind"] == "specification")
    specification_headings = _headings(root / specification["file_path"])
    assert specification["artifact_subtypes"] == ["api"]
    assert "API: create-subscription" in specification_headings
    assert set(_headings(PLUGIN / "templates" / "api-contract.md")[1:]) <= set(specification_headings)
    architecture = next(node for node in graph["nodes"] if node["artifact_kind"] == "architecture")
    architecture_headings = _headings(root / architecture["file_path"])
    assert architecture["artifact_subtypes"] == ["backend", "data", "security"]
    for subtype in architecture["artifact_subtypes"]:
        template = contract["artifacts"]["architecture"]["subtype_templates"][subtype]
        assert set(_headings(PLUGIN / "templates" / template)) <= set(architecture_headings)
    identity = {node["title"]: (node["graph_node_id"], node["file_path"]) for node in graph["nodes"]}
    issue_before = (root / identity[TITLES[0]][1]).read_text(encoding="utf-8").split("\n---\n", 1)[1]
    other_bytes = {
        node["graph_node_id"]: (root / node["file_path"]).read_bytes()
        for node in graph["nodes"] if node["artifact_kind"] != "issue"
    }

    updated_payload = copy.deepcopy(payload)
    updated_payload["artifacts"][0]["body"] += " A permanent remediation was approved."  # type: ignore[index]
    _write_json(input_path, updated_payload)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["observed_at"] = "2026-08-24T03:10:00Z"
    _write_json(plan_path, plan)
    patches = root / "artifact-patches.json"
    _write_json(patches, {"patches": [{
        "input_index": 0,
        "append_sections": [{"heading": "## Permanent remediation", "body": "Use separate interactive and batch lanes."}],
    }]})
    changed = _run(root, "--input", str(input_path), "--plan", str(plan_path), "--patches", str(patches))
    assert [(item["operation"], item["graph_node_id"]) for item in changed["applied"]] == [  # type: ignore[index]
        ("update", identity[TITLES[0]][0])
    ]
    after_graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert {node["title"]: (node["graph_node_id"], node["file_path"]) for node in after_graph["nodes"]} == identity
    issue_after = (root / identity[TITLES[0]][1]).read_text(encoding="utf-8").split("\n---\n", 1)[1]
    assert issue_after.startswith(issue_before.rstrip("\n") + "\n\n## Permanent remediation")
    assert other_bytes == {
        node["graph_node_id"]: (root / node["file_path"]).read_bytes()
        for node in after_graph["nodes"] if node["artifact_kind"] != "issue"
    }

    stable_digest = hashlib.sha256(graph_path.read_bytes()).hexdigest()
    rerun = _run(root, "--input", str(input_path), "--plan", str(plan_path), "--patches", str(patches))
    assert rerun["applied"] == []
    assert len(rerun["unchanged"]) == 5
    assert hashlib.sha256(graph_path.read_bytes()).hexdigest() == stable_digest

    feature_input = root / "feature-like-input.json"
    feature_plan = root / "feature-like-plan.json"
    _write_json(feature_input, {"artifacts": [payload["artifacts"][5]]})  # type: ignore[index]
    feature_decision = _decision(0, "feature", json.loads((PLUGIN / "templates" / "template-contract.json").read_text()))
    _write_json(feature_plan, {"schema_version": "1.0.0", "observed_at": "2026-08-24T03:20:00Z", "decisions": [feature_decision]})
    rejected = _run(root, "--input", str(feature_input), "--plan", str(feature_plan), expected=1)
    assert rejected["status"] == "rejected"
    assert rejected["write_count"] == 0
    assert rejected["features_registered"] == 0
    assert hashlib.sha256(graph_path.read_bytes()).hexdigest() == stable_digest
    assert not list(root.rglob("c02-write.py"))

    c11 = subprocess.run(
        [sys.executable, str(C11), "--graph", str(graph_path), "--repo-root", str(root)],
        capture_output=True, text=True, check=False,
    )
    assert c11.returncode == 0, c11.stdout + c11.stderr
    assert json.loads(c11.stdout)["valid"] is True


def test_new_artifact_rejects_every_existing_leaf_without_writes(tmp_path: Path) -> None:
    cases = ("regular", "directory", "symlink-in", "symlink-out", "symlink-broken")
    for case in cases:
        case_root = tmp_path / case
        case_root.mkdir()
        root, input_path, plan_path, _ = _fixture(case_root)
        graph_path = root / ".dev-graph" / "graph.json"
        preview = _run(root, "--input", str(input_path), "--plan", str(plan_path), "--dry-run")
        target = root / preview["applied"][0]["file_path"]  # type: ignore[index]
        if case == "regular":
            target.write_text("user-owned\n", encoding="utf-8")
        elif case == "directory":
            target.mkdir()
        elif case == "symlink-in":
            target.symlink_to(input_path)
        elif case == "symlink-out":
            outside = case_root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            target.symlink_to(outside)
        else:
            target.symlink_to(root / "missing.md")

        graph_before = graph_path.read_bytes()
        occupant_before = (
            ("symlink", os.readlink(target))
            if target.is_symlink()
            else ("directory", None)
            if target.is_dir()
            else ("file", target.read_bytes())
        )
        for dry_run in (True, False):
            arguments = ["--input", str(input_path), "--plan", str(plan_path)]
            if dry_run:
                arguments.append("--dry-run")
            rejected = _run(root, *arguments, expected=2)
            assert rejected["valid"] is False
            expected = "must not be a symlink" if case.startswith("symlink") else "already exists without durable graph node"
            assert expected in rejected["error"]  # type: ignore[operator]
            assert graph_path.read_bytes() == graph_before
            occupant_after = (
                ("symlink", os.readlink(target))
                if target.is_symlink()
                else ("directory", None)
                if target.is_dir()
                else ("file", target.read_bytes())
            )
            assert occupant_after == occupant_before
            assert json.loads(graph_path.read_text(encoding="utf-8"))["nodes"] == []


def test_existing_artifact_update_rejects_symlink_without_writes(tmp_path: Path) -> None:
    root, input_path, plan_path, payload = _fixture(tmp_path)
    graph_path = root / ".dev-graph" / "graph.json"
    added = _run(root, "--input", str(input_path), "--plan", str(plan_path))
    issue = next(item for item in added["applied"] if item["input_index"] == 0)  # type: ignore[union-attr]
    target = root / issue["file_path"]
    user_owned = target.with_name("user-owned-issue.md")
    target.replace(user_owned)
    target.symlink_to(user_owned.name)

    changed_payload = copy.deepcopy(payload)
    changed_payload["artifacts"][0]["body"] += " New evidence."  # type: ignore[index]
    _write_json(input_path, changed_payload)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["observed_at"] = "2026-08-24T03:30:00Z"
    _write_json(plan_path, plan)
    patches = root / "artifact-patches.json"
    _write_json(patches, {"patches": [{
        "input_index": 0,
        "append_sections": [{"heading": "## New evidence", "body": "Observed after registration."}],
    }]})

    graph_before = graph_path.read_bytes()
    user_owned_before = user_owned.read_bytes()
    for dry_run in (True, False):
        arguments = [
            "--input", str(input_path), "--plan", str(plan_path), "--patches", str(patches),
        ]
        if dry_run:
            arguments.append("--dry-run")
        rejected = _run(root, *arguments, expected=2)
        assert rejected["valid"] is False
        assert "must not be a symlink" in rejected["error"]  # type: ignore[operator]
        assert graph_path.read_bytes() == graph_before
        assert target.is_symlink()
        assert os.readlink(target) == user_owned.name
        assert user_owned.read_bytes() == user_owned_before
