"""評価先を開始時の C24 receipt に束縛し、fork の cwd から分離する。"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
PREPARE = PLUGIN / "skills/run-dev-graph-system-spec/scripts/prepare-evaluation.py"
RESOLVE = PLUGIN / "scripts/resolve-repo-context.py"


@pytest.fixture
def evaluation_repo(tmp_path):
    root = tmp_path / "caller repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "-q", "--allow-empty",
                    "-m", "fixture"], check=True)
    (root / "system-spec").mkdir()
    (root / "system-spec/index.md").write_text("# specification\n")
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    proc = subprocess.run([sys.executable, "-B", str(RESOLVE), "--repo-root", str(root),
                           "--mode", "write"], env=env, check=True, capture_output=True, text=True)
    receipt = tmp_path / "context.json"
    receipt.write_text(proc.stdout)
    return root, receipt, env


def run_prepare(data, cwd, output="eval-log/completeness.json"):
    _, receipt, env = data
    return subprocess.run([sys.executable, "-B", str(PREPARE), "--context-receipt",
                           str(receipt), "--output", output], cwd=cwd, env=env,
                          capture_output=True, text=True, check=False)


def test_fork_cwd_does_not_change_evaluation_target(evaluation_repo, tmp_path):
    root, _, _ = evaluation_repo
    foreign = tmp_path / "different repo"
    (foreign / "system-spec").mkdir(parents=True)
    (foreign / "system-spec/index.md").write_text("# unrelated\n")
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    caller = run_prepare(evaluation_repo, root)
    fork = run_prepare(evaluation_repo, foreign)
    assert caller.returncode == fork.returncode == 0, fork.stderr
    assert json.loads(caller.stdout) == json.loads(fork.stdout)
    result = json.loads(fork.stdout)
    assert shlex.split(result["skill_args"]) == [
        "--spec-dir", str(root / "system-spec"), "--output", str(root / "eval-log/completeness.json")]
    assert result["evidence_ref"] == "eval-log/completeness.json"
    assert before == sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


@pytest.mark.parametrize("field", ["repo_root", "repository_id", "worktree_id", "git_common_dir", "git_dir"])
def test_rejects_changed_context_identity(evaluation_repo, tmp_path, field):
    _, receipt, _ = evaluation_repo
    doc = json.loads(receipt.read_text())
    doc[field] = str(tmp_path) if field.endswith("root") or field.endswith("dir") else "foreign"
    receipt.write_text(json.dumps(doc))
    proc = run_prepare(evaluation_repo, tmp_path)
    assert proc.returncode != 0
    assert proc.stdout == ""
    assert "evaluation_context_invalid:" in proc.stderr


def test_rejects_changed_content_root(evaluation_repo, tmp_path):
    _, receipt, _ = evaluation_repo
    doc = json.loads(receipt.read_text())
    doc["content_roots"]["system_spec"] = str(tmp_path)
    receipt.write_text(json.dumps(doc))
    assert run_prepare(evaluation_repo, tmp_path).returncode != 0


@pytest.mark.parametrize("output", ["../outside.json", "/tmp/outside.json", "docs/report.json", "eval-log/../report.json"])
def test_rejects_unbound_output(evaluation_repo, tmp_path, output):
    proc = run_prepare(evaluation_repo, tmp_path, output)
    assert proc.returncode != 0
    assert proc.stdout == ""
    assert "evaluation_context_invalid:" in proc.stderr


@pytest.mark.parametrize("link", ["system-spec", "eval-log"])
def test_rejects_symlink_escape(evaluation_repo, tmp_path, link):
    root, _, _ = evaluation_repo
    outside = tmp_path / "outside"
    outside.mkdir()
    if link == "system-spec":
        (root / link / "index.md").unlink()
        (root / link).rmdir()
    (root / link).symlink_to(outside, target_is_directory=True)
    proc = run_prepare(evaluation_repo, tmp_path)
    assert proc.returncode != 0
    assert proc.stdout == ""
    assert "evaluation_context_invalid:" in proc.stderr


def test_rejects_conflicting_project_environment(evaluation_repo, tmp_path):
    evaluation_repo[2]["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    assert run_prepare(evaluation_repo, tmp_path).returncode != 0
