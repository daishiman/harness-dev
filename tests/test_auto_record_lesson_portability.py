"""auto-record-lesson.py の書込先移植性 (3 段 fallback) を実証する。

read-only install / cwd 非依存を保証する: plugin-root が書込不能でも user state へ
退避し、全滅でも exit 0 / Traceback 無し。dev では plugin-root へ書ける既存挙動維持。
"""
import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "auto-record-lesson.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("auto_record_lesson", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()

_FAILING_INPUT = json.dumps(
    {
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "tool_input": {"skill": "run-x"},
        "tool_response": {"stderr": "ERROR: something failed Traceback"},
    }
)


def _run_main_with_stdin(monkeypatch, capsys, stdin_text):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    rc = MOD.main()
    return rc, capsys.readouterr()


# --- 既定: plugin-root 配下 (dev 既存挙動・dogfooding 互換) ---

def test_default_dir_is_plugin_root(monkeypatch):
    monkeypatch.delenv("HARNESS_CREATOR_LESSONS_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    d = MOD._lessons_dir()
    assert d == MOD._plugin_root() / "lessons-learned"
    # plugin-root は harness-creator を指す
    assert MOD._plugin_root().name == "harness-creator"


def test_env_plugin_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
    monkeypatch.delenv("HARNESS_CREATOR_LESSONS_DIR", raising=False)
    assert MOD._plugin_root() == tmp_path.resolve()
    assert MOD._lessons_dir() == tmp_path.resolve() / "lessons-learned"


def test_env_lessons_dir_override_is_sole_candidate(monkeypatch, tmp_path):
    monkeypatch.setenv("HARNESS_CREATOR_LESSONS_DIR", str(tmp_path / "ld"))
    cands = MOD._candidate_dirs()
    assert cands == [(tmp_path / "ld").resolve()]


# --- (a) 既定で書ける ---

def test_writes_to_plugin_root_when_writable(monkeypatch, tmp_path, capsys):
    primary = tmp_path / "plugin" / "lessons-learned"
    primary.parent.mkdir(parents=True)
    monkeypatch.setattr(MOD, "_candidate_dirs", lambda: [primary, tmp_path / "fallback"])
    rc, cap = _run_main_with_stdin(monkeypatch, capsys, _FAILING_INPUT)
    assert rc == 0
    assert list(primary.glob("*.md")), "primary に lesson が書かれていない"
    assert "recorded ->" in cap.err  # 書込先を 1 行可視化


# --- (b) plugin-root 書込不能 → user state へ degrade ---

def test_falls_back_when_primary_unwritable(monkeypatch, tmp_path, capsys):
    # primary は親が存在しない & 作れない想定にするため、書込不能フラグを直接注入。
    primary = tmp_path / "ro" / "lessons-learned"
    fallback = tmp_path / "state" / "lessons-learned"
    fallback.parent.mkdir(parents=True)
    monkeypatch.setattr(MOD, "_candidate_dirs", lambda: [primary, fallback])

    def fake_writable(d):
        return d == fallback

    monkeypatch.setattr(MOD, "_dir_is_writable", fake_writable)
    rc, cap = _run_main_with_stdin(monkeypatch, capsys, _FAILING_INPUT)
    assert rc == 0
    assert list(fallback.glob("*.md")), "fallback に退避されていない"
    assert "recorded ->" in cap.err


# --- (c) 全滅でも exit 0 / Traceback 無し ---

def test_no_writable_sink_is_noop_exit0(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(MOD, "_candidate_dirs", lambda: [tmp_path / "a", tmp_path / "b"])
    monkeypatch.setattr(MOD, "_dir_is_writable", lambda d: False)
    rc, cap = _run_main_with_stdin(monkeypatch, capsys, _FAILING_INPUT)
    assert rc == 0
    assert "no writable sink" in cap.err
    assert "Traceback" not in cap.err


def test_no_failure_signature_is_silent_exit0(monkeypatch, capsys):
    rc, cap = _run_main_with_stdin(
        monkeypatch, capsys, json.dumps({"tool_name": "Read", "ok": "all good"})
    )
    assert rc == 0
    assert cap.err == ""


# --- state fallback root の env 解決順 ---

def test_state_fallback_prefers_project_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    root = MOD._state_fallback_root()
    assert root == tmp_path / "proj" / ".claude" / "state" / "harness-creator"


def test_state_fallback_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    root = MOD._state_fallback_root()
    assert root == tmp_path / "xdg" / "harness-creator"


def test_dir_is_writable_walks_to_existing_ancestor(tmp_path):
    # 深い未作成パスでも、書込可能な既存祖先があれば True。
    deep = tmp_path / "a" / "b" / "c"
    assert MOD._dir_is_writable(deep) is True
