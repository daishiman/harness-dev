"""run-dev-graph-init OUT3: build-init-scaffold.py は、どの write よりも前に validate-harness-link.py を自分で実行する。

harness link が切れた repo で init を起動し (link は切れているので plugin 実体から起動する)、preflight の診断と
修復の選択肢を返して exit 1 で止まり、repo に1 byte も書かないことを実際の起動で確かめる。返された修復の選択肢を
そのまま実行すると、次の init は通る。
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
LINK = Path(".claude") / "dev-graph-plugin"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("dev_graph_init_preflight_gate", SCRIPTS / "build-init-scaffold.py")
assert SPEC and SPEC.loader
INIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INIT)


def git_repo(root: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return root.resolve()


def tree_bytes(root: Path) -> dict[str, bytes | str]:
    """root 以下の全 entry の中身 (symlink は link 先の文字列)。書込み 0 件の比較に使う。"""
    result: dict[str, bytes | str] = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[key] = "->" + os.readlink(path)
        elif path.is_file():
            result[key] = path.read_bytes()
        else:
            result[key] = "<dir>"
    return result


def run(root: Path, script: str, *argv: str, via: Path = PLUGIN) -> tuple[int, dict]:
    env = {**{k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")},
           "CLAUDE_PROJECT_DIR": str(root)}
    cp = subprocess.run([sys.executable, str(via / "scripts" / script), "--repo-root", str(root), *argv],
                        text=True, capture_output=True, env=env, cwd=str(root), check=False)
    return cp.returncode, json.loads(cp.stdout)


def repair(report: dict, option: str) -> None:
    """init が返した修復の選択肢の argv をそのまま実行する (最後の step は preflight の再実行)。"""
    steps = next(item["steps"] for item in report["remediation"] if item["option"] == option)
    for argv in steps[:-1]:
        subprocess.run(argv, check=True, capture_output=True)
    assert steps[-1][:2] == ["python3", "-B"] and steps[-1][2].endswith("/validate-harness-link.py"), steps[-1]


def test_severed_harness_link_stops_init_before_any_write_and_its_repair_lets_init_run(tmp_path: Path) -> None:
    harness = tmp_path / "harness"
    harness.symlink_to(PLUGIN)
    repo = git_repo(tmp_path / "A")
    assert run(repo, "build-init-scaffold.py", via=harness)[1]["status"] == "applied"
    (repo / LINK).parent.mkdir(exist_ok=True)
    (repo / LINK).symlink_to(harness)
    code, hooked = run(repo, "build-project-hook-fallback.py", "--user-settings", str(tmp_path / "user.json"),
                       "--managed-settings", str(tmp_path / "managed.json"), "--mode", "apply", via=harness)
    assert (code, hooked["status"]) == (0, "applied"), hooked
    # init が作るものを1つ残す (preflight が無ければ docs を作り receipt を書く状態)。
    (repo / "docs").rmdir()
    harness.rename(tmp_path / "harness.severed")
    snapshot = tree_bytes(repo)

    for extra in (("--dry-run",), ()):
        code, report = run(repo, "build-init-scaffold.py", *extra)
        assert (code, report["status"], report["code"], report["write_count"], report["planned_changes"]) == (
            1, "rejected", "harness_link_broken", 0, None), report
        assert report["findings"][0]["code"] == "harness_link_broken" and report["error"] == report["findings"][0]["detail"]
        diagnostic = report["preflight"]
        assert (diagnostic["link_state"], diagnostic["broken_hop"], diagnostic["missing_target"]) == (
            "broken", str(repo / LINK), str(harness)), diagnostic
        assert [item["option"] for item in report["remediation"]] == ["relink-shared-harness", "relink-this-repo"]
        assert tree_bytes(repo) == snapshot

    repair(report, "relink-shared-harness")
    code, report = run(repo, "build-init-scaffold.py")
    assert (code, report["status"], report["created"]) == (0, "applied", ["docs"]), report
    receipt = json.loads((repo / report["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["preflight"] == {"validator": "validate-harness-link.py", "status": "pass", "link_state": "ok",
                                    "in_use": True}


def test_planned_project_fallback_without_a_link_leaves_a_fresh_repo_untouched(tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "B")
    snapshot = tree_bytes(repo)
    for extra in (("--dry-run",), ()):
        code, report = run(repo, "build-init-scaffold.py", "--hook-source", "project-fallback", *extra)
        assert (code, report["code"], report["write_count"]) == (1, "harness_link_missing", 0), report
        assert report["preflight"]["in_use_by"] == ["argv:--hook-source project-fallback"]
        assert tree_bytes(repo) == snapshot and not (repo / ".dev-graph").exists()

    repair(report, "relink-this-repo")
    code, report = run(repo, "build-init-scaffold.py", "--hook-source", "project-fallback")
    assert (code, report["status"], report["hook_source"]) == (0, "applied", "project-fallback"), report
    assert report["preflight"]["link_state"] == "ok"


def test_a_preflight_that_cannot_answer_fails_closed_before_the_repo_context_is_resolved(tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "C")
    snapshot = tree_bytes(repo)
    broken = subprocess.CompletedProcess([], 2, stdout="", stderr="usage: validate-harness-link.py")
    output = io.StringIO()
    with mock.patch.object(INIT.subprocess, "run", return_value=broken) as runner, \
            mock.patch.object(INIT, "_context") as context, redirect_stdout(output):
        code = INIT.main(["--repo-root", str(repo)])
    report = json.loads(output.getvalue())
    assert (code, report["code"], report["error"], report["write_count"]) == (
        1, "harness_link_preflight_error", "usage: validate-harness-link.py", 0), report
    argv = runner.call_args.args[0]
    assert argv[1] == "-B" and argv[2].endswith("/validate-harness-link.py")  # 子も harness に bytecode を書かない
    context.assert_not_called()
    assert tree_bytes(repo) == snapshot
