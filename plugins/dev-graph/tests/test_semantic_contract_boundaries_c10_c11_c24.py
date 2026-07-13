from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
HOOKS = PLUGIN / "hooks"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *args, stdin=None):
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, args)])
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stdin)))
    code = module.main()
    captured = capsys.readouterr()
    return code, captured


def canonical_issue(file_path: str = "issues/issue-1.md") -> dict:
    now = "2026-07-13T00:00:00Z"
    return {
        "graph_node_id": "issue-1",
        "artifact_kind": "issue",
        "artifact_subtypes": [],
        "title": "Issue one",
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


def write_artifact(root: Path, node: dict, *, omit: str | None = None) -> None:
    path = root / node["file_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in node.items():
        if key != omit:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(["---", "", "# Overview", "", "Substantive content.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_c11_uses_canonical_schema_and_frontmatter_path_contract(tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "validate-graph-schema.py", "validate_contract_c11")
    node = canonical_issue()
    write_artifact(tmp_path, node)
    assert mod.validate([node], repo_root=tmp_path) == []
    graph = tmp_path / ".dev-graph" / "state" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text(json.dumps({"nodes": [node]}), encoding="utf-8")
    code, captured = call_main(mod, monkeypatch, capsys, "--graph", graph, "--repo-root", tmp_path)
    assert code == 0 and json.loads(captured.out)["schema"].endswith("schemas/graph-node.schema.json")

    without_owner = dict(node)
    without_owner.pop("owners")
    findings = mod.validate([without_owner], repo_root=tmp_path)
    assert any(item["code"] == "schema_violation" and "owners" in item["detail"] for item in findings)

    wrong_root = canonical_issue("tasks/issue-1.md")
    findings = mod.validate([wrong_root])
    assert any(item["code"] == "path_parity_error" for item in findings)

    write_artifact(tmp_path, node, omit="tags")
    findings = mod.validate([node], repo_root=tmp_path)
    assert {item["detail"] for item in findings if item["code"] == "frontmatter_missing"} == {"tags"}


def test_c10_invokes_c11_then_still_rejects_direct_mutation(tmp_path, monkeypatch, capsys):
    mod = load(HOOKS / "guard-graph-schema.py", "guard_contract_c10")
    graph = tmp_path / ".dev-graph" / "state" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text('{"nodes": []}\n', encoding="utf-8")
    context = json.dumps({"local_state_paths": {"graph": str(graph)}})
    monkeypatch.setattr(mod, "context_ok", lambda root: (True, context))
    checked: list[Path] = []
    monkeypatch.setattr(mod, "schema_ok", lambda root, output: (checked.append(root) is None, "valid"))

    code, captured = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={"tool_input": {"command": "rm -rf .dev-graph/state/graph.json # validate-graph-schema.py"}},
    )
    assert code == 2
    assert checked == [tmp_path]
    assert "C02 atomic writer" in captured.err

    monkeypatch.setattr(mod, "schema_ok", lambda root, output: (False, "schema invalid"))
    code, captured = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={"tool_input": {"command": "sed -i '' plugins/dev-graph/schemas/graph-node.schema.json"}},
    )
    assert code == 2
    assert "C11 schema validation failed" in captured.err


def test_c10_redirect_detection_is_bound_to_the_redirect_destination(
    tmp_path, monkeypatch, capsys,
):
    mod = load(HOOKS / "guard-graph-schema.py", "guard_redirect_target_contract")
    monkeypatch.setattr(mod, "context_ok", lambda _root: (True, "{}"))
    monkeypatch.setattr(mod, "schema_ok", lambda _root, _detail: (True, "ok"))

    code, _ = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={"tool_input": {"command": "sha256sum .dev-graph/state/graph.json 2>/dev/null"}},
    )
    assert code == 0

    code, _ = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={"tool_input": {"command": "printf '{}' > .dev-graph/state/graph.json"}},
    )
    assert code == 2


def test_c10_destructive_detection_distinguishes_sources_from_destinations(
    tmp_path, monkeypatch, capsys,
):
    mod = load(HOOKS / "guard-graph-schema.py", "guard_operand_contract")
    monkeypatch.setattr(mod, "context_ok", lambda _root: (True, "{}"))
    monkeypatch.setattr(mod, "schema_ok", lambda _root, _detail: (True, "ok"))

    allowed = [
        "cp -rf plugins/dev-graph/templates .dev-graph/templates",
        "cp .dev-graph/state/graph.json /tmp/graph-backup.json",
        "sha256sum .dev-graph/state/graph.json 2>/dev/null",
    ]
    for command in allowed:
        code, _ = call_main(
            mod,
            monkeypatch,
            capsys,
            "--repo-root",
            tmp_path,
            stdin={"tool_input": {"command": command}},
        )
        assert code == 0, command

    blocked = [
        "cp /tmp/graph.json .dev-graph/state/graph.json",
        "mv .dev-graph/state/graph.json /tmp/graph.json",
        "rm -rf .dev-graph",
        "sed -i '' plugins/dev-graph/schemas/graph-node.schema.json",
    ]
    for command in blocked:
        code, _ = call_main(
            mod,
            monkeypatch,
            capsys,
            "--repo-root",
            tmp_path,
            stdin={"tool_input": {"command": command}},
        )
        assert code == 2, command


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, text=True, capture_output=True).stdout.strip()


def init_repo(root: Path) -> None:
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "fixture")
    git(root, "remote", "add", "origin", "https://github.com/Acme/Demo.git")


def config_for(root: Path, tasks: str = "tasks") -> Path:
    config = root / ".dev-graph" / "config.json"
    config.parent.mkdir(exist_ok=True)
    config.write_text(json.dumps({
        "repository_id": "github:Acme/Demo",
        "content_roots": {"tasks": tasks},
        "local_state": {"graph": ".dev-graph/state/graph.json", "cache": ".dev-graph/cache", "locks": ".dev-graph/locks"},
        "path_policy": {
            "authority": "caller-repository",
            "allow_outside_repository": False,
            "follow_content_symlinks_outside_repository": False,
        },
    }), encoding="utf-8")
    return config


def test_c24_enforces_symlink_containment_and_common_repository_ownership(tmp_path, monkeypatch, capsys):
    mod = load(SCRIPTS / "resolve-repo-context.py", "resolve_contract_c24")
    root = tmp_path / "repo"
    init_repo(root)
    config_for(root)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    code, captured = call_main(mod, monkeypatch, capsys, "--repo-root", root)
    assert code == 0
    result = json.loads(captured.out)
    assert result["repository_id"] == "github:Acme/Demo"
    assert result["root_trust_evidence"]["git_common_dir_ownership_verified"] is True

    other = tmp_path / "other"
    init_repo(other)
    with pytest.raises(Exception, match="objects authority"):
        mod.verify_common_ownership(root.resolve(), (root / ".git").resolve(), (other / ".git").resolve())

    outside = tmp_path / "outside"
    outside.mkdir()
    tasks = root / "tasks"
    tasks.symlink_to(outside, target_is_directory=True)
    with pytest.raises(Exception, match="escapes authority root"):
        call_main(mod, monkeypatch, capsys, "--repo-root", root)

    tasks.unlink()
    tasks.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    with pytest.raises(Exception, match="broken content symlink"):
        call_main(mod, monkeypatch, capsys, "--repo-root", root)

    tasks.unlink()
    inside = root / "inside-tasks"
    inside.mkdir()
    tasks.symlink_to(inside, target_is_directory=True)
    with pytest.raises(Exception, match="must not traverse a symlink"):
        call_main(mod, monkeypatch, capsys, "--repo-root", root)

    tasks.unlink()
    config_for(root, "../outside")
    with pytest.raises(Exception, match="escapes repository authority"):
        call_main(mod, monkeypatch, capsys, "--repo-root", root)


def test_c24_discovery_precedence_and_fail_closed_boundaries(tmp_path, monkeypatch):
    mod = load(SCRIPTS / "resolve-repo-context.py", "resolve_contract_c24_discovery")
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: type("CP", (), {"returncode": 1, "stdout": ""})())
    with pytest.raises(mod.ContractError, match="cannot be resolved"):
        mod.discover(None)

    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setattr(mod, "git", lambda args, selected, check=True: str(root))
    assert mod.discover(None) == (root, "CLAUDE_PROJECT_DIR")

    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr(mod, "git", lambda args, selected, check=True: str(other))
    with pytest.raises(mod.ContractError, match="not current worktree root"):
        mod.discover(str(root))


def test_c24_common_dir_marker_remote_and_config_policy_boundaries(tmp_path, monkeypatch):
    mod = load(SCRIPTS / "resolve-repo-context.py", "resolve_contract_c24_common")
    root = tmp_path / "repo"
    common = root / "common"
    git_dir = root / "worktrees" / "wt"
    common.mkdir(parents=True)
    git_dir.mkdir(parents=True)
    (common / "objects").mkdir()
    (common / "config").write_text("[core]\n", encoding="utf-8")
    marker = git_dir / "commondir"
    marker.write_text("../../common\n", encoding="utf-8")

    values = {
        ("rev-parse", "--git-path", "objects"): str(common / "objects"),
        ("rev-parse", "--git-path", "config"): str(common / "config"),
        ("remote", "get-url", "origin"): "https://github.com/Acme/Demo.git",
        ("--git-dir", str(common), "remote", "get-url", "origin"): "https://github.com/Acme/Demo.git",
    }
    monkeypatch.setattr(mod, "git", lambda args, selected, check=True: values[tuple(args)])
    mod.verify_common_ownership(root, git_dir, common)

    marker.unlink()
    with pytest.raises(mod.ContractError, match="no trusted commondir marker"):
        mod.verify_common_ownership(root, git_dir, common)
    marker.write_text("missing-common\n", encoding="utf-8")
    with pytest.raises(mod.ContractError, match="invalid worktree commondir marker"):
        mod.verify_common_ownership(root, git_dir, common)
    other = root / "other-common"
    other.mkdir()
    marker.write_text("../../other-common\n", encoding="utf-8")
    with pytest.raises(mod.ContractError, match="commondir mismatch"):
        mod.verify_common_ownership(root, git_dir, common)

    marker.write_text("../../common\n", encoding="utf-8")
    values[("--git-dir", str(common), "remote", "get-url", "origin")] = "https://github.com/Other/Repo.git"
    with pytest.raises(mod.ContractError, match="different origin remotes"):
        mod.verify_common_ownership(root, git_dir, common)

    with pytest.raises(mod.ContractError, match="path_policy must be an object"):
        mod.resolve_config_paths(root, {"path_policy": ["invalid"]})
    with pytest.raises(mod.ContractError, match="weakens caller-repository containment"):
        mod.resolve_config_paths(root, {"path_policy": {"allow_outside_repository": True}})
    with pytest.raises(mod.ContractError, match="must be objects"):
        mod.resolve_config_paths(root, {"content_roots": ["invalid"], "local_state": {}})
    with pytest.raises(mod.ContractError, match="non-empty repository-relative path"):
        mod.resolve_declared_path(root, "", "content_roots.tasks", reject_leaf_symlink=True)
