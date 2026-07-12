"""Genuine functional tests for
plugins/skill-governance-hooks/scripts/hook-post-compact.py.

hook-post-compact は PostCompact フックで CLAUDE_HANDOFF_DIR
(既定 .claude/handoff) の最新 *.md スナップショットを読み、
rehydration プロンプトを stdout へ出す network 不要スクリプト。

戦略:
- in-process: HANDOFF_DIR が module-load 時に env から固定されるため、
  env を立ててから読み込み、stdin を差し替えて main() を呼ぶ。
  各分岐 (snapshot 無/有・複数で最新選択・1000文字 truncate・read 失敗・
  stdin 不正/空) を網羅。
- subprocess: 子プロセスで end-to-end の exit code + stdout を assert。

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
SCRIPT = ROOT / "plugins" / "skill-governance-hooks" / "scripts" / "hook-post-compact.py"


def _load_module(handoff_dir: Path):
    os.environ["CLAUDE_HANDOFF_DIR"] = str(handoff_dir)
    spec = importlib.util.spec_from_file_location("hook_post_compact_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeStdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text


def _run_main(monkeypatch, mod, stdin_text: str = ""):
    monkeypatch.setattr(sys, "stdin", _FakeStdin(stdin_text))
    return mod.main()


def _write_snapshot(d: Path, name: str, content: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------- in-process: no snapshot 分岐 ----------

def test_main_noop_when_dir_missing(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "absent"  # 存在しない
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, json.dumps({"session_id": "s"}))
    assert rc == 0
    out = capsys.readouterr().out
    assert out == ""  # no-op なので何も出さない


def test_main_noop_when_dir_empty(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    hd.mkdir()
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_noop_when_no_md_files(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    hd.mkdir()
    (hd / "notes.txt").write_text("not md", encoding="utf-8")
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    assert capsys.readouterr().out == ""


# ---------- in-process: snapshot あり ----------

def test_main_prints_rehydration_for_single_snapshot(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    _write_snapshot(hd, "20260101T000000.md", "# Handoff snapshot\nbody content here")
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, json.dumps({"session_id": "s"}))
    assert rc == 0
    out = capsys.readouterr().out
    assert "[PostCompact] Context restored from handoff snapshot: 20260101T000000.md" in out
    assert "--- HANDOFF SUMMARY (first 1000 chars) ---" in out
    assert "body content here" in out
    assert "--- END HANDOFF SUMMARY ---" in out
    assert "Please resume from the state described above." in out


def test_main_selects_latest_snapshot(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    _write_snapshot(hd, "20260101T000000.md", "OLDEST snapshot")
    _write_snapshot(hd, "20260615T120000.md", "MIDDLE snapshot")
    _write_snapshot(hd, "20260620T235959.md", "NEWEST snapshot")
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    out = capsys.readouterr().out
    # sorted()[-1] = 名前が辞書順最大 = 最新タイムスタンプ
    assert "20260620T235959.md" in out
    assert "NEWEST snapshot" in out
    assert "OLDEST snapshot" not in out
    assert "MIDDLE snapshot" not in out


def test_main_truncates_summary_to_1000_chars(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    big = "A" * 5000
    _write_snapshot(hd, "20260101T000000.md", big)
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    out = capsys.readouterr().out
    start = out.index("--- HANDOFF SUMMARY (first 1000 chars) ---\n") + len(
        "--- HANDOFF SUMMARY (first 1000 chars) ---\n"
    )
    end = out.index("\n--- END HANDOFF SUMMARY ---", start)
    summary = out[start:end]
    assert len(summary) == 1000  # content[:1000]
    assert set(summary) == {"A"}


def test_main_empty_snapshot_file(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    _write_snapshot(hd, "20260101T000000.md", "")
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    out = capsys.readouterr().out
    # 空内容でもヘッダ/フッタは出る
    assert "Context restored from handoff snapshot: 20260101T000000.md" in out
    assert "--- END HANDOFF SUMMARY ---" in out


# ---------- in-process: stdin エッジ (data 解析は出力に影響しないが分岐を踏む) ----------

def test_main_invalid_json_stdin_still_works(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    _write_snapshot(hd, "20260101T000000.md", "resume me")
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "{broken json")
    assert rc == 0
    assert "resume me" in capsys.readouterr().out


def test_main_empty_stdin_still_works(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    _write_snapshot(hd, "20260101T000000.md", "resume me too")
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    assert "resume me too" in capsys.readouterr().out


# ---------- in-process: read 失敗分岐 ----------

def test_main_returns_0_when_read_fails(tmp_path, monkeypatch, capsys):
    hd = tmp_path / "handoff"
    snap = _write_snapshot(hd, "20260101T000000.md", "x")
    mod = _load_module(hd)

    orig_read_text = Path.read_text

    def _boom(self, *a, **k):
        if self == snap:
            raise OSError("simulated read failure")
        return orig_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", _boom)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    captured = capsys.readouterr()
    assert "hook-post-compact: cannot read handoff" in captured.err
    # read 失敗時は rehydration 本文を出さず return
    assert "Please resume" not in captured.out


# ---------- subprocess: end-to-end ----------

def _run_subprocess(handoff_dir: Path, stdin_text: str):
    env = dict(os.environ)
    env["CLAUDE_HANDOFF_DIR"] = str(handoff_dir)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def test_subprocess_noop_no_snapshot(tmp_path):
    hd = tmp_path / "handoff"
    r = _run_subprocess(hd, json.dumps({"session_id": "s"}))
    assert r.returncode == 0
    assert r.stdout == ""


def test_subprocess_prints_latest(tmp_path):
    hd = tmp_path / "handoff"
    _write_snapshot(hd, "20260101T000000.md", "first")
    _write_snapshot(hd, "20260202T000000.md", "second latest")
    r = _run_subprocess(hd, "")
    assert r.returncode == 0
    assert "20260202T000000.md" in r.stdout
    assert "second latest" in r.stdout
    assert "Please resume from the state described above." in r.stdout


def test_subprocess_default_dir(tmp_path):
    # env を渡さず cwd を tmp にし、既定 .claude/handoff から読む
    default_dir = tmp_path / ".claude" / "handoff"
    _write_snapshot(default_dir, "20260101T000000.md", "default body")
    env = dict(os.environ)
    env.pop("CLAUDE_HANDOFF_DIR", None)
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    assert r.returncode == 0
    assert "default body" in r.stdout
