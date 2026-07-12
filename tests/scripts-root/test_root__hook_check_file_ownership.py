"""Genuine functional tests for scripts/hook-check-file-ownership.py.

hook-check-file-ownership は TaskCreated フックで stdin の JSON を受け、
新タスクが `files` / `file_ownership` を宣言した場合に所有権を記録し、
別のアクティブタスクが既に所有するファイルと衝突したら deny (exit 2) する
network 不要スクリプト。所有権未宣言は allow (exit 0)。

戦略:
- 純関数 (load_state / save_state) は STATE_FILE を tmp_path へ向け (env) フレッシュ
  import して実ファイルで round-trip / 欠落 / 不正 JSON / 非 dict を assert。
- main() は stdin を差し替え全分岐を網羅:
  allow (ファイル無宣言 / task_id 無 / files 非 list / 空 list /
  空 stdin / 不正 JSON / 同一 owner 再宣言 / 別ファイル) と
  deny (別タスクが所有するファイルとの衝突, exit 2)。
- subprocess: 子プロセスとして起動し exit code 0/2 と state ファイル更新を assert。

副作用なし: STATE_FILE は tmp_path 配下に固定し、実 .claude を触らない。
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hook-check-file-ownership.py"


def _load_module(state_file: Path):
    """STATE_FILE は module-load 時に env から固定されるため、
    env を立ててから毎回フレッシュに読み込む。"""
    os.environ["CLAUDE_TASK_OWNERSHIP_STATE"] = str(state_file)
    spec = importlib.util.spec_from_file_location("hook_check_file_ownership_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeStdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text


def _run_main(monkeypatch, mod, stdin_text: str):
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin(stdin_text))
    return mod.main()


# ---------- load_state / save_state: 純関数 ----------

def test_load_state_missing_file_returns_empty(tmp_path):
    mod = _load_module(tmp_path / "state.json")
    assert mod.load_state() == {}


def test_save_then_load_roundtrip(tmp_path):
    sf = tmp_path / "nested" / "state.json"
    mod = _load_module(sf)
    state = {"task-1": ["a.py", "b.py"], "task-2": ["c.py"]}
    mod.save_state(state)
    assert sf.exists()  # parent dirs created
    assert mod.load_state() == state


def test_save_state_is_pretty_and_unicode(tmp_path):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    mod.save_state({"t": ["日本語.py"]})
    raw = sf.read_text(encoding="utf-8")
    assert "日本語.py" in raw  # ensure_ascii=False
    assert "\n  " in raw  # indent=2


def test_load_state_invalid_json_returns_empty(tmp_path):
    sf = tmp_path / "state.json"
    sf.write_text("{not valid json,,,", encoding="utf-8")
    mod = _load_module(sf)
    assert mod.load_state() == {}


def test_load_state_non_dict_returns_empty(tmp_path):
    sf = tmp_path / "state.json"
    sf.write_text(json.dumps(["a", "b"]), encoding="utf-8")
    mod = _load_module(sf)
    assert mod.load_state() == {}


# ---------- main: allow 分岐 (exit 0) ----------

def test_main_no_files_declared_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t1"}))
    assert rc == 0
    # ファイル無宣言 -> state は書かれない
    assert not sf.exists()


def test_main_missing_task_id_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    rc = _run_main(monkeypatch, mod, json.dumps({"files": ["a.py"]}))
    assert rc == 0
    assert not sf.exists()


def test_main_empty_files_list_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t1", "files": []}))
    assert rc == 0
    assert not sf.exists()


def test_main_files_not_list_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t1", "files": "a.py"}))
    assert rc == 0
    assert not sf.exists()


def test_main_empty_stdin_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    rc = _run_main(monkeypatch, mod, "")
    assert rc == 0
    assert not sf.exists()


def test_main_invalid_json_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    rc = _run_main(monkeypatch, mod, "{not json,,,")
    assert rc == 0
    assert not sf.exists()


def test_main_records_ownership_first_time(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t1", "files": ["a.py", "b.py"]}))
    assert rc == 0
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["a.py", "b.py"]}


def test_main_uses_id_field_as_task_id(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    # task_id 欠落時は "id" を採用
    rc = _run_main(monkeypatch, mod, json.dumps({"id": "t9", "files": ["x.py"]}))
    assert rc == 0
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t9": ["x.py"]}


def test_main_uses_file_ownership_field(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    # files 欠落時は file_ownership を採用
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t1", "file_ownership": ["y.py"]}))
    assert rc == 0
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["y.py"]}


def test_main_same_owner_redeclaring_same_file_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    # 同じ task_id が既に所有しているファイルを再宣言 -> conflict ではない
    sf.write_text(json.dumps({"t1": ["a.py"]}), encoding="utf-8")
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t1", "files": ["a.py", "b.py"]}))
    assert rc == 0
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["a.py", "b.py"]}


def test_main_different_task_different_files_allows(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    sf.write_text(json.dumps({"t1": ["a.py"]}), encoding="utf-8")
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t2", "files": ["b.py"]}))
    assert rc == 0
    state = json.loads(sf.read_text(encoding="utf-8"))
    assert state == {"t1": ["a.py"], "t2": ["b.py"]}


def test_main_coerces_non_string_paths_to_str(tmp_path, monkeypatch):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    # files に非文字列が混ざっても str() で記録される (active との比較は素の値)
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t1", "files": ["a.py", 42]}))
    assert rc == 0
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["a.py", "42"]}


# ---------- main: deny 分岐 (exit 2) ----------

def test_main_conflict_denies_with_exit2(tmp_path, monkeypatch, capsys):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    # t1 が a.py を所有 -> t2 が a.py を宣言すると衝突
    sf.write_text(json.dumps({"t1": ["a.py"]}), encoding="utf-8")
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t2", "files": ["a.py"]}))
    assert rc == 2
    err = capsys.readouterr().err
    assert "hook-check-file-ownership" in err
    assert "task t2 conflicts" in err
    assert "a.py" in err
    assert "owned by" in err
    assert "t1" in err
    # deny 時は state を書き換えない
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["a.py"]}


def test_main_partial_conflict_denies(tmp_path, monkeypatch, capsys):
    sf = tmp_path / "state.json"
    mod = _load_module(sf)
    # b.py のみ衝突 (a.py は自由) -> conflicts に b.py のみ
    sf.write_text(json.dumps({"t1": ["b.py"]}), encoding="utf-8")
    rc = _run_main(monkeypatch, mod, json.dumps({"task_id": "t2", "files": ["a.py", "b.py"]}))
    assert rc == 2
    err = capsys.readouterr().err
    assert "b.py" in err
    # 衝突報告に a.py (非衝突) は載らない
    assert "['b.py']" in err
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["b.py"]}


# ---------- subprocess: end-to-end ----------

def _run_subprocess(state_file: Path, stdin_text: str):
    env = dict(os.environ)
    env["CLAUDE_TASK_OWNERSHIP_STATE"] = str(state_file)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def test_subprocess_records_and_exit0(tmp_path):
    sf = tmp_path / "state.json"
    r = _run_subprocess(sf, json.dumps({"task_id": "t1", "files": ["a.py"]}))
    assert r.returncode == 0
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["a.py"]}


def test_subprocess_conflict_exit2(tmp_path):
    sf = tmp_path / "state.json"
    sf.write_text(json.dumps({"t1": ["a.py"]}), encoding="utf-8")
    r = _run_subprocess(sf, json.dumps({"task_id": "t2", "files": ["a.py"]}))
    assert r.returncode == 2
    assert "conflicts" in r.stderr
    # state 不変
    assert json.loads(sf.read_text(encoding="utf-8")) == {"t1": ["a.py"]}


def test_subprocess_no_files_exit0(tmp_path):
    sf = tmp_path / "state.json"
    r = _run_subprocess(sf, json.dumps({"task_id": "t1"}))
    assert r.returncode == 0
    assert not sf.exists()


def test_subprocess_empty_stdin_exit0(tmp_path):
    sf = tmp_path / "state.json"
    r = _run_subprocess(sf, "")
    assert r.returncode == 0
