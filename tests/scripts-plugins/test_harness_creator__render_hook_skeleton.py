"""run-build-skill/scripts/render-hook-skeleton.py の機能テスト。

hook event 別 skeleton 生成を genuine に検証する:

  - 生成物の構造: shebang / metadata block / main() 定義 / skill 名と event の埋込
  - 生成物が valid Python であり、hook 契約 (stdin JSON → exit 0、壊れた入力でも
    exit 0) で実際に動くこと
  - 実行ビット (0o755) 付与と親ディレクトリの自動作成
  - 既存ファイルは skip して上書きしない (exit 0 + stderr 通知)
  - argparse 必須引数欠落 → exit 2

注意: skeleton 内の TODO コメント文言は本テストの assert 対象外 (文言変更に
非依存)。write-scope: output-dir — 書き込みは全て tmp_path 配下で完結する。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
          / "scripts" / "render-hook-skeleton.py")

_SPEC = importlib.util.spec_from_file_location("render_hook_skeleton_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _call_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["render-hook-skeleton.py", *argv])
    return MOD.main()


# --------------------------------------------------------------------------
# 生成: 構造 / 埋込 / 実行ビット / 親ディレクトリ作成
# --------------------------------------------------------------------------

def test_main_generates_skeleton_structure(tmp_path, monkeypatch, capsys):
    out = tmp_path / "hooks" / "hook-run-demo-pretooluse.py"
    rc = _call_main(monkeypatch, [
        "--skill-name", "run-demo", "--event", "PreToolUse", "--out", str(out),
    ])
    assert rc == 0
    assert f"generated: {out}" in capsys.readouterr().out
    assert out.exists()  # 親 hooks/ ごと自動作成
    text = out.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env python3\n")
    assert "name: hook-run-demo-pretooluse" in text
    assert "PreToolUse hook for skill `run-demo`." in text
    assert "def main() -> int:" in text
    assert 'if __name__ == "__main__":' in text


def test_main_generated_file_is_executable(tmp_path, monkeypatch):
    out = tmp_path / "hook.py"
    rc = _call_main(monkeypatch, [
        "--skill-name", "run-x", "--event", "Stop", "--out", str(out),
    ])
    assert rc == 0
    assert out.stat().st_mode & 0o755 == 0o755


def test_main_generated_file_is_valid_python(tmp_path, monkeypatch):
    out = tmp_path / "hook.py"
    _call_main(monkeypatch, [
        "--skill-name", "run-x", "--event", "PostToolUse", "--out", str(out),
    ])
    # TODO 文言に依存せず、構文として valid であることのみ検証。
    compile(out.read_text(encoding="utf-8"), str(out), "exec")


def test_generated_hook_runs_with_json_and_garbage_stdin(tmp_path, monkeypatch):
    # 生成された hook script 自体を実行: 正常 JSON も壊れた入力も exit 0。
    out = tmp_path / "hook.py"
    _call_main(monkeypatch, [
        "--skill-name", "run-x", "--event", "PreToolUse", "--out", str(out),
    ])
    for stdin in ('{"tool_name": "Bash"}', "", "not json {{"):
        proc = subprocess.run(
            [sys.executable, str(out)],
            input=stdin, capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert proc.returncode == 0, (stdin, proc.stderr)


# --------------------------------------------------------------------------
# 既存ファイルは skip (上書きしない)
# --------------------------------------------------------------------------

def test_main_existing_file_skipped_unchanged(tmp_path, monkeypatch, capsys):
    out = tmp_path / "hook.py"
    out.write_text("ORIGINAL", encoding="utf-8")
    rc = _call_main(monkeypatch, [
        "--skill-name", "run-x", "--event", "Stop", "--out", str(out),
    ])
    assert rc == 0
    assert "already exists, skip" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "ORIGINAL"


# --------------------------------------------------------------------------
# argparse 必須引数欠落 → exit 2
# --------------------------------------------------------------------------

def test_main_missing_required_args_systemexit2(monkeypatch):
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, ["--skill-name", "run-x"])
    assert ei.value.code == 2


# --------------------------------------------------------------------------
# CLI 契約 (subprocess)
# --------------------------------------------------------------------------

def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_generates_and_reports_path(tmp_path):
    out = tmp_path / "deep" / "hook-run-demo-stop.py"
    proc = _run("--skill-name", "run-demo", "--event", "Stop", "--out", str(out),
                cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert str(out) in proc.stdout
    assert out.exists()


def test_cli_existing_file_exit0_with_notice(tmp_path):
    out = tmp_path / "hook.py"
    out.write_text("KEEP", encoding="utf-8")
    proc = _run("--skill-name", "run-x", "--event", "Stop", "--out", str(out),
                cwd=str(tmp_path))
    assert proc.returncode == 0
    assert "already exists, skip" in proc.stderr
    assert out.read_text(encoding="utf-8") == "KEEP"


def test_cli_missing_args_exit2(tmp_path):
    proc = _run("--skill-name", "run-x", cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--event" in proc.stderr or "--out" in proc.stderr
