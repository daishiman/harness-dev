"""Genuine functional tests for scripts/build-notion-config.py.

The script's only side effect is writing <repo-root>/.notion-config.json, where
repo-root is derived from the script file location (Path(__file__).parent.parent).
To exercise the real write path WITHOUT touching this repo, every subprocess test
copies the script + .notion-config.example.json into an isolated tmp_path that
mirrors the expected layout (<tmp>/scripts/build-notion-config.py and
<tmp>/.notion-config.example.json); the script then treats <tmp> as ROOT, so all
file creation/abort logic operates entirely under tmp_path.

derive_slug() is also imported directly and tested with subprocess.check_output
monkeypatched (no real git invocation), covering the remote-url, .git-suffix
stripping, and CalledProcessError fallback branches.

No network, no keychain, repo untouched.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "build-notion-config.py"
EXAMPLE = REPO_ROOT / ".notion-config.example.json"


def _load_from(path: Path):
    spec = importlib.util.spec_from_file_location("build_notion_config_under_test", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _make_sandbox(tmp_path: Path) -> Path:
    """Mirror the repo layout so the copied script's ROOT == sandbox root."""
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, tmp_path / "scripts" / "build-notion-config.py")
    shutil.copy(EXAMPLE, tmp_path / ".notion-config.example.json")
    return tmp_path


def _run(sandbox: Path, *args):
    return subprocess.run(
        [sys.executable, str(sandbox / "scripts" / "build-notion-config.py"), *args],
        cwd=sandbox, text=True, capture_output=True,
    )


# ── derive_slug (import + monkeypatched git) ──────────────────────────────
def test_derive_slug_from_remote_url(monkeypatch):
    mod = _load_from(SCRIPT)
    monkeypatch.setattr(
        mod.subprocess, "check_output",
        lambda *a, **k: "git@github.com:xl-manju/xl-skills.git\n",
    )
    assert mod.derive_slug() == "xl-skills"


def test_derive_slug_strips_trailing_slash_and_no_git_suffix(monkeypatch):
    mod = _load_from(SCRIPT)
    monkeypatch.setattr(
        mod.subprocess, "check_output",
        lambda *a, **k: "https://example.com/org/cool-repo/\n",
    )
    assert mod.derive_slug() == "cool-repo"


def test_derive_slug_fallback_to_dirname_on_git_error(monkeypatch):
    mod = _load_from(SCRIPT)

    def boom(*a, **k):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(mod.subprocess, "check_output", boom)
    # ROOT is the real repo dir here; fallback returns its basename
    assert mod.derive_slug() == mod.ROOT.name


# ── --print-keychain-cmd (no file written) ────────────────────────────────
def test_print_keychain_cmd_emits_command_and_writes_nothing(tmp_path):
    sandbox = _make_sandbox(tmp_path)
    proc = _run(sandbox, "--slug", "xl-skills", "--print-keychain-cmd")
    assert proc.returncode == 0
    assert "security add-generic-password" in proc.stdout
    assert "-s notion-api-key.xl-skills" in proc.stdout
    assert "-a xl-skills" in proc.stdout
    # config must NOT be created in print-only mode
    assert not (sandbox / ".notion-config.json").exists()


# ── non-interactive write path ────────────────────────────────────────────
def test_non_interactive_writes_config_with_slug_namespacing(tmp_path):
    sandbox = _make_sandbox(tmp_path)
    proc = _run(
        sandbox,
        "--slug", "myrepo", "--non-interactive",
        "--parent-page-id", "PID123", "--parent-page-url", "https://notion/PID123",
        "--skill-list-db", "SL_DB", "--hearing-sheet-db", "HS_DB",
        "--improvement-request-db", "IR_DB",
    )
    assert proc.returncode == 0, proc.stderr
    cfg_path = sandbox / ".notion-config.json"
    assert cfg_path.exists()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["keychain_service"] == "notion-api-key.myrepo"
    assert cfg["keychain_account"] == "myrepo"
    assert cfg["parent_page"]["page_id"] == "PID123"
    assert cfg["parent_page"]["page_url"] == "https://notion/PID123"
    assert cfg["databases"]["skill-list"]["db_id"] == "SL_DB"
    assert cfg["databases"]["hearing-sheet"]["db_id"] == "HS_DB"
    assert cfg["databases"]["improvement-request"]["db_id"] == "IR_DB"
    # _comment from the example template is stripped
    assert "_comment" not in cfg
    assert "wrote" in proc.stdout


def test_non_interactive_uses_placeholders_when_ids_omitted(tmp_path):
    sandbox = _make_sandbox(tmp_path)
    proc = _run(sandbox, "--slug", "myrepo", "--non-interactive")
    assert proc.returncode == 0, proc.stderr
    cfg = json.loads((sandbox / ".notion-config.json").read_text(encoding="utf-8"))
    assert cfg["parent_page"]["page_id"] == "<your-parent-page-id>"
    assert cfg["databases"]["skill-list"]["db_id"] == "<your-skill-list-db-id>"


# ── idempotency guard: existing config without --force aborts ──────────────
def test_existing_config_without_force_aborts_exit_2(tmp_path):
    sandbox = _make_sandbox(tmp_path)
    (sandbox / ".notion-config.json").write_text('{"keep": "me"}', encoding="utf-8")
    proc = _run(sandbox, "--slug", "myrepo", "--non-interactive")
    assert proc.returncode == 2
    assert "already exists" in proc.stderr
    # original content preserved (not overwritten)
    assert json.loads((sandbox / ".notion-config.json").read_text())["keep"] == "me"


def test_existing_config_with_force_overwrites(tmp_path):
    sandbox = _make_sandbox(tmp_path)
    (sandbox / ".notion-config.json").write_text('{"keep": "me"}', encoding="utf-8")
    proc = _run(sandbox, "--slug", "myrepo", "--non-interactive", "--force")
    assert proc.returncode == 0, proc.stderr
    cfg = json.loads((sandbox / ".notion-config.json").read_text(encoding="utf-8"))
    assert "keep" not in cfg
    assert cfg["keychain_service"] == "notion-api-key.myrepo"


# ── interactive abort on 'n' ──────────────────────────────────────────────
def test_interactive_abort_on_no(tmp_path):
    sandbox = _make_sandbox(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(sandbox / "scripts" / "build-notion-config.py"),
         "--slug", "myrepo"],
        cwd=sandbox, text=True, capture_output=True, input="n\n",
    )
    assert proc.returncode == 1
    assert "aborted" in proc.stdout
    assert not (sandbox / ".notion-config.json").exists()


def test_interactive_continue_on_yes_writes(tmp_path):
    sandbox = _make_sandbox(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(sandbox / "scripts" / "build-notion-config.py"),
         "--slug", "myrepo"],
        cwd=sandbox, text=True, capture_output=True, input="y\n",
    )
    assert proc.returncode == 0, proc.stderr
    assert (sandbox / ".notion-config.json").exists()


def test_interactive_empty_input_defaults_to_continue(tmp_path):
    # An empty answer (just Enter) is treated as "yes" per `if ans and ans != "y"`.
    sandbox = _make_sandbox(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(sandbox / "scripts" / "build-notion-config.py"),
         "--slug", "myrepo"],
        cwd=sandbox, text=True, capture_output=True, input="\n",
    )
    assert proc.returncode == 0, proc.stderr
    assert (sandbox / ".notion-config.json").exists()


def test_help_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT, text=True, capture_output=True,
    )
    assert proc.returncode == 0
    assert "--slug" in proc.stdout
    assert "--print-keychain-cmd" in proc.stdout
