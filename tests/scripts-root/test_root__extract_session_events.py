"""Genuine functional tests for scripts/extract-session-events.py.

extract-session-events は Claude Code の hook (UserPromptSubmit / PostToolUse /
Stop) から呼ばれ、session event を `.claude/logs/<YYYY-MM-DD>.jsonl` に追記する
network 不要スクリプト。hook が session を blocking しないため exit code は常に 0。

戦略:
- 純関数 (build_event / read_hook_payload / append_log) は import して実入力で assert。
  build_event は kind 別 (user_prompt / tool_use / stop) の各分岐 +
  payload 欠落 / env fallback / tool_response 非 dict / truncate を網羅。
- main() は LOG_ROOT を tmp_path へ向け (CLAUDE_LOG_ROOT) フレッシュ import し、
  stdin / argv を差し替えて全分岐 (未知 kind / 各 kind / 例外 swallow) を assert。
- subprocess: 子プロセスとして起動し exit0 + jsonl 生成を end-to-end で assert。

副作用なし: 全 fixture は tmp_path に書き、実 .claude を触らない。
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "extract-session-events.py"


def _load_module(log_root: Path):
    """LOG_ROOT は module-load 時に env から固定されるため、
    env を立ててから毎回フレッシュに読み込む。"""
    os.environ["CLAUDE_LOG_ROOT"] = str(log_root)
    spec = importlib.util.spec_from_file_location("extract_session_events_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeStdin:
    def __init__(self, text: str, isatty: bool = False):
        self._text = text
        self._isatty = isatty

    def read(self) -> str:
        return self._text

    def isatty(self) -> bool:
        return self._isatty


# ---------- build_event: 共通フィールド ----------

def test_build_event_common_fields(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("user_prompt", {"session_id": "sess-1", "prompt": "hi"})
    assert ev["schema_version"] == mod.SCHEMA_VERSION == "1.0"
    assert ev["event"] == "user_prompt"
    assert ev["session_id"] == "sess-1"
    # ts は ISO8601 UTC + "Z"
    assert ev["ts"].endswith("Z")
    assert ev["ts"][4] == "-" and ev["ts"][10] == "T"
    assert len(ev["ts"]) == len("2026-01-01T00:00:00Z")


def test_build_event_session_id_from_env_when_absent(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-sess")
    ev = mod.build_event("stop", {})
    assert ev["session_id"] == "env-sess"


def test_build_event_session_id_unknown_fallback(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    ev = mod.build_event("stop", {})
    assert ev["session_id"] == "unknown"


def test_build_event_payload_session_id_overrides_env(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-sess")
    ev = mod.build_event("stop", {"session_id": "payload-sess"})
    assert ev["session_id"] == "payload-sess"


# ---------- build_event: user_prompt ----------

def test_build_event_user_prompt_text(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("user_prompt", {"prompt": "create a skill"})
    assert ev["text"] == "create a skill"


def test_build_event_user_prompt_text_truncated_to_2000(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("user_prompt", {"prompt": "X" * 5000})
    assert len(ev["text"]) == 2000
    assert set(ev["text"]) == {"X"}


def test_build_event_user_prompt_missing_prompt_empty(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("user_prompt", {})
    assert ev["text"] == ""


# ---------- build_event: tool_use ----------

def test_build_event_tool_use_skill_invoked_true(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event(
        "tool_use",
        {"tool_name": "Skill", "tool_input": {"skill": "run-build-skill"}},
    )
    assert ev["tool_name"] == "Skill"
    assert ev["skill_invoked"] is True
    assert ev["skill"] == "run-build-skill"
    assert ev["success"] is True


def test_build_event_tool_use_non_skill_tool(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("tool_use", {"tool_name": "Bash"})
    assert ev["tool_name"] == "Bash"
    assert ev["skill_invoked"] is False
    assert ev["skill"] == ""


def test_build_event_tool_use_subagent_type_used_as_skill(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event(
        "tool_use",
        {"tool_name": "Task", "tool_input": {"subagent_type": "reviewer"}},
    )
    assert ev["skill"] == "reviewer"


def test_build_event_tool_use_tool_input_not_dict_no_skill_key(tmp_path):
    mod = _load_module(tmp_path / "logs")
    # tool_input がリスト -> isinstance(dict) False -> "skill" キーは付与されない
    ev = mod.build_event("tool_use", {"tool_name": "X", "tool_input": ["a", "b"]})
    assert "skill" not in ev


def test_build_event_tool_use_success_false_from_response(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event(
        "tool_use",
        {"tool_name": "Bash", "tool_response": {"success": False}},
    )
    assert ev["success"] is False


def test_build_event_tool_use_success_default_true_when_response_missing(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("tool_use", {"tool_name": "Bash"})
    assert ev["success"] is True


def test_build_event_tool_use_success_true_when_response_not_dict(tmp_path):
    mod = _load_module(tmp_path / "logs")
    # tool_response が文字列 -> isinstance(dict) False -> success default True
    ev = mod.build_event("tool_use", {"tool_name": "Bash", "tool_response": "done"})
    assert ev["success"] is True


# ---------- build_event: stop ----------

def test_build_event_stop_reason(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("stop", {"reason": "completed"})
    assert ev["reason"] == "completed"


def test_build_event_stop_reason_default_empty(tmp_path):
    mod = _load_module(tmp_path / "logs")
    ev = mod.build_event("stop", {})
    assert ev["reason"] == ""


# ---------- read_hook_payload ----------

def test_read_hook_payload_valid_json(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin('{"prompt": "hi"}'))
    assert mod.read_hook_payload() == {"prompt": "hi"}


def test_read_hook_payload_empty_string(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin(""))
    assert mod.read_hook_payload() == {}


def test_read_hook_payload_whitespace_only(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin("   \n\t "))
    assert mod.read_hook_payload() == {}


def test_read_hook_payload_invalid_json(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin("{not json,,"))
    assert mod.read_hook_payload() == {}


def test_read_hook_payload_isatty_returns_empty(tmp_path, monkeypatch):
    mod = _load_module(tmp_path / "logs")
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin("ignored", isatty=True))
    assert mod.read_hook_payload() == {}


# ---------- append_log ----------

def test_append_log_creates_dated_file(tmp_path):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    event = {"ts": "2026-06-24T12:00:00Z", "event": "stop", "session_id": "s"}
    mod.append_log(event)
    f = log_root / "2026-06-24.jsonl"
    assert f.exists()
    line = f.read_text(encoding="utf-8").strip()
    assert json.loads(line) == event


def test_append_log_appends_multiple_lines(tmp_path):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    mod.append_log({"ts": "2026-06-24T01:00:00Z", "event": "stop", "n": 1})
    mod.append_log({"ts": "2026-06-24T02:00:00Z", "event": "stop", "n": 2})
    f = log_root / "2026-06-24.jsonl"
    lines = f.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["n"] == 1
    assert json.loads(lines[1])["n"] == 2


def test_append_log_non_ascii_preserved(tmp_path):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    mod.append_log({"ts": "2026-06-24T03:00:00Z", "event": "user_prompt", "text": "日本語"})
    f = log_root / "2026-06-24.jsonl"
    raw = f.read_text(encoding="utf-8")
    assert "日本語" in raw  # ensure_ascii=False


def test_append_log_separate_days(tmp_path):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    mod.append_log({"ts": "2026-06-23T23:00:00Z", "event": "stop"})
    mod.append_log({"ts": "2026-06-24T00:00:00Z", "event": "stop"})
    assert (log_root / "2026-06-23.jsonl").exists()
    assert (log_root / "2026-06-24.jsonl").exists()


# ---------- main: 分岐 ----------

def _run_main(monkeypatch, mod, argv, stdin_text):
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin(stdin_text))
    return mod.main(argv)


def test_main_unknown_kind_warns_and_returns_0(tmp_path, monkeypatch, capsys):
    mod = _load_module(tmp_path / "logs")
    rc = _run_main(monkeypatch, mod, ["prog", "nonsense"], "{}")
    assert rc == 0
    err = capsys.readouterr().err
    assert "unknown event kind" in err
    # 未知 kind では何も書かれない
    assert not (tmp_path / "logs").exists() or not list((tmp_path / "logs").glob("*.jsonl"))


def test_main_missing_argv_warns_and_returns_0(tmp_path, monkeypatch, capsys):
    mod = _load_module(tmp_path / "logs")
    rc = _run_main(monkeypatch, mod, ["prog"], "{}")
    assert rc == 0
    assert "unknown event kind" in capsys.readouterr().err


def test_main_user_prompt_writes_log(tmp_path, monkeypatch):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    rc = _run_main(monkeypatch, mod, ["prog", "user_prompt"], '{"session_id":"s1","prompt":"hello"}')
    assert rc == 0
    files = list(log_root.glob("*.jsonl"))
    assert len(files) == 1
    ev = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert ev["event"] == "user_prompt"
    assert ev["text"] == "hello"
    assert ev["session_id"] == "s1"


def test_main_tool_use_writes_log(tmp_path, monkeypatch):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    payload = json.dumps({"session_id": "s", "tool_name": "Skill", "tool_input": {"skill": "x"}})
    rc = _run_main(monkeypatch, mod, ["prog", "tool_use"], payload)
    assert rc == 0
    ev = json.loads(next(log_root.glob("*.jsonl")).read_text(encoding="utf-8").strip())
    assert ev["event"] == "tool_use"
    assert ev["skill_invoked"] is True


def test_main_stop_writes_log(tmp_path, monkeypatch):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    rc = _run_main(monkeypatch, mod, ["prog", "stop"], '{"reason":"done"}')
    assert rc == 0
    ev = json.loads(next(log_root.glob("*.jsonl")).read_text(encoding="utf-8").strip())
    assert ev["event"] == "stop"
    assert ev["reason"] == "done"


def test_main_empty_stdin_still_writes(tmp_path, monkeypatch):
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)
    rc = _run_main(monkeypatch, mod, ["prog", "stop"], "")
    assert rc == 0
    ev = json.loads(next(log_root.glob("*.jsonl")).read_text(encoding="utf-8").strip())
    assert ev["event"] == "stop"
    assert ev["session_id"] == "unknown" or ev["session_id"]  # env fallback


def test_main_swallows_exception_returns_0(tmp_path, monkeypatch, capsys):
    # append_log を例外を投げるよう差し替えて except 分岐 (warn + rc0) を踏む
    log_root = tmp_path / "logs"
    mod = _load_module(log_root)

    def _boom(_event):
        raise OSError("disk full")

    monkeypatch.setattr(mod, "append_log", _boom)
    rc = _run_main(monkeypatch, mod, ["prog", "stop"], '{"reason":"x"}')
    assert rc == 0
    assert "WARN extract-session-events: disk full" in capsys.readouterr().err


# ---------- subprocess: end-to-end ----------

def _run_subprocess(log_root: Path, kind: str, stdin_text: str):
    env = dict(os.environ)
    env["CLAUDE_LOG_ROOT"] = str(log_root)
    return subprocess.run(
        [sys.executable, str(SCRIPT), kind],
        input=stdin_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def test_subprocess_stop_exit0_and_writes(tmp_path):
    log_root = tmp_path / "logs"
    r = _run_subprocess(log_root, "stop", json.dumps({"session_id": "ss", "reason": "ok"}))
    assert r.returncode == 0
    files = list(log_root.glob("*.jsonl"))
    assert len(files) == 1
    ev = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert ev["event"] == "stop"
    assert ev["reason"] == "ok"
    assert ev["session_id"] == "ss"


def test_subprocess_unknown_kind_exit0_warns(tmp_path):
    log_root = tmp_path / "logs"
    r = _run_subprocess(log_root, "garbage", "{}")
    assert r.returncode == 0
    assert "unknown event kind" in r.stderr
    assert not list(log_root.glob("*.jsonl")) if log_root.exists() else True


def test_subprocess_no_argv_exit0(tmp_path):
    log_root = tmp_path / "logs"
    env = dict(os.environ)
    env["CLAUDE_LOG_ROOT"] = str(log_root)
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="{}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    assert "unknown event kind" in r.stderr
