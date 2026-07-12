"""Genuine functional tests for
plugins/skill-governance-hooks/scripts/hook-handoff.py.

hook-handoff は PreCompact フックで stdin の JSON を受け、
CLAUDE_HANDOFF_DIR (既定 .claude/handoff) にタイムスタンプ付き
markdown スナップショットを書き出す network 不要スクリプト。

戦略:
- in-process: import した module の main() を、stdin/cwd/env を差し替え、
  OUT_DIR を tmp_path に向けて実行 (実ファイル書き込みを assert)。
  各分岐 (正常 JSON / 空 stdin / 不正 JSON / payload truncate / mkdir 失敗) を網羅。
- subprocess: 子プロセスとして起動し exit code と生成物を assert (end-to-end)。

副作用なし: 全 fixture は tmp_path に書き、実 .claude を触らない。
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-hooks" / "scripts" / "hook-handoff.py"


def _load_module(handoff_dir: Path):
    """OUT_DIR が module-load 時に env から固定されるため、
    env を立ててから毎回フレッシュに読み込む。"""
    os.environ["CLAUDE_HANDOFF_DIR"] = str(handoff_dir)
    spec = importlib.util.spec_from_file_location("hook_handoff_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeStdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text


def _run_main(monkeypatch, mod, stdin_text: str, cwd: Path):
    monkeypatch.setattr(sys, "stdin", _FakeStdin(stdin_text))
    monkeypatch.chdir(cwd)
    return mod.main()


# ---------- in-process: 正常系 ----------

def test_main_writes_snapshot_with_valid_payload(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    payload = {"session_id": "sess-123", "trigger": "PreCompact", "extra": "x"}
    work = tmp_path / "work"
    work.mkdir()
    rc = _run_main(monkeypatch, mod, json.dumps(payload), work)
    assert rc == 0
    files = list(hd.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "# Handoff snapshot" in text
    assert "- trigger: PreCompact" in text
    assert "- session_id: sess-123" in text
    assert f"- cwd: {work}" in text
    assert "## Raw hook payload" in text
    assert '"extra": "x"' in text


def test_main_filename_is_timestamped_md(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, json.dumps({"session_id": "s"}), tmp_path)
    assert rc == 0
    files = list(hd.glob("*.md"))
    assert len(files) == 1
    stem = files[0].stem  # YYYYmmddTHHMMSS
    assert len(stem) == 15
    assert stem[8] == "T"
    assert stem.replace("T", "").isdigit()


def test_main_default_trigger_when_absent(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, json.dumps({"session_id": "s"}), tmp_path)
    assert rc == 0
    text = next(hd.glob("*.md")).read_text(encoding="utf-8")
    # trigger key 欠落 -> default "PreCompact"
    assert "- trigger: PreCompact" in text


def test_main_session_id_empty_when_absent(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, json.dumps({"trigger": "Manual"}), tmp_path)
    assert rc == 0
    text = next(hd.glob("*.md")).read_text(encoding="utf-8")
    assert "- session_id: \n" in text or text.rstrip().count("- session_id:") == 1
    assert "- trigger: Manual" in text


def test_main_creates_nested_outdir(tmp_path, monkeypatch):
    hd = tmp_path / "deep" / "nested" / "handoff"
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, json.dumps({"session_id": "s"}), tmp_path)
    assert rc == 0
    assert hd.is_dir()
    assert len(list(hd.glob("*.md"))) == 1


# ---------- in-process: stdin エッジ ----------

def test_main_empty_stdin_yields_empty_data(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "", tmp_path)
    assert rc == 0
    text = next(hd.glob("*.md")).read_text(encoding="utf-8")
    # 空 stdin -> data={} -> trigger default
    assert "- trigger: PreCompact" in text
    assert "{}" in text


def test_main_whitespace_only_stdin(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "   \n  \t ", tmp_path)
    assert rc == 0
    text = next(hd.glob("*.md")).read_text(encoding="utf-8")
    assert "{}" in text


def test_main_invalid_json_falls_back_to_empty(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, "{not valid json,,,", tmp_path)
    assert rc == 0
    # 不正 JSON でも except 経由で data={} になり書き込みは成功する
    text = next(hd.glob("*.md")).read_text(encoding="utf-8")
    assert "- trigger: PreCompact" in text
    assert "{}" in text


def test_main_truncates_huge_payload_to_8000(tmp_path, monkeypatch):
    hd = tmp_path / "handoff"
    mod = _load_module(hd)
    big = {"blob": "Z" * 50000}
    rc = _run_main(monkeypatch, mod, json.dumps(big), tmp_path)
    assert rc == 0
    text = next(hd.glob("*.md")).read_text(encoding="utf-8")
    # json.dumps(data,...)[:8000] により payload 部は 8000 文字以下
    start = text.index("```json\n") + len("```json\n")
    end = text.index("\n```", start)
    payload_block = text[start:end]
    assert len(payload_block) <= 8000
    # 巨大なので必ず 8000 で打ち切られている (= ``` 閉じが見つかる位置の検証)
    assert "ZZZ" in payload_block


# ---------- in-process: 書き込み失敗分岐 (mkdir/write 例外) ----------

def test_main_returns_0_and_warns_when_outdir_unwritable(tmp_path, monkeypatch, capsys):
    # OUT_DIR の親をファイルにして mkdir を失敗させる -> except 分岐 -> stderr warn, rc 0
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file", encoding="utf-8")
    hd = blocker / "handoff"  # 親がファイルなので mkdir(parents=True) で失敗
    mod = _load_module(hd)
    rc = _run_main(monkeypatch, mod, json.dumps({"session_id": "s"}), tmp_path)
    assert rc == 0
    err = capsys.readouterr().err
    assert "hook-handoff: skipped" in err
    assert not hd.exists()


# ---------- subprocess: end-to-end ----------

def _run_subprocess(handoff_dir: Path, stdin_text: str, cwd: Path):
    env = dict(os.environ)
    env["CLAUDE_HANDOFF_DIR"] = str(handoff_dir)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(cwd),
        env=env,
    )


def test_subprocess_exit0_and_writes(tmp_path):
    hd = tmp_path / "handoff"
    work = tmp_path / "work"
    work.mkdir()
    r = _run_subprocess(hd, json.dumps({"session_id": "ss", "trigger": "PreCompact"}), work)
    assert r.returncode == 0
    files = list(hd.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "- session_id: ss" in text
    assert f"- cwd: {work}" in text


def test_subprocess_empty_stdin_exit0(tmp_path):
    hd = tmp_path / "handoff"
    r = _run_subprocess(hd, "", tmp_path)
    assert r.returncode == 0
    assert len(list(hd.glob("*.md"))) == 1


def test_subprocess_default_dir_when_env_absent(tmp_path):
    # env を渡さず cwd を tmp にして既定 .claude/handoff へ書くことを確認
    env = dict(os.environ)
    env.pop("CLAUDE_HANDOFF_DIR", None)
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({"session_id": "x"}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    assert r.returncode == 0
    default_dir = tmp_path / ".claude" / "handoff"
    assert default_dir.is_dir()
    assert len(list(default_dir.glob("*.md"))) == 1
