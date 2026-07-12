"""hook-validate-skill-md.py の genuine 機能テスト (network 不要)。

FileChanged フック。変更ファイルが SKILL.md のとき scripts/validate-frontmatter.py を
起動し、validator が非 0 を返したら stderr に warning を出す。常に exit 0 (warn-only)。

genuine に網羅する分岐 (main の全経路):
  - stdin が空 / 不正 JSON  → 早期 return 0 (data={})
  - file_path が SKILL.md でない  → return 0 (validator 未起動)
  - tool_input.file_path 経由の SKILL.md 解決
  - 対象ファイルが存在しない  → return 0
  - VALIDATOR (scripts/validate-frontmatter.py) が存在しない  → return 0
  - validator returncode==0 (合格)  → warning 無し
  - validator returncode!=0 (違反)  → stderr に warning, それでも return 0
  - subprocess が例外  → "skipped" warning, return 0
  - extract_json 相当の純経路は無いため main を import して直接駆動する。

import 駆動 (monkeypatch stdin / VALIDATOR / subprocess) で大半の行を踏み、
加えて subprocess 経由 (sys.executable) で __main__ 実行経路も実証する。
tmp_path のみ使用し repo を汚さない。
"""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "skill-governance-hooks" / "scripts" / "hook-validate-skill-md.py"
)

_SPEC = importlib.util.spec_from_file_location("hook_validate_skill_md_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _set_stdin(monkeypatch, payload):
    """stdin を payload (str か dict) で差し替える。"""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(text))


class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# --------------------------------------------------------------------------
# 早期 return: stdin 異常
# --------------------------------------------------------------------------

def test_empty_stdin_returns_0(monkeypatch):
    _set_stdin(monkeypatch, "")
    assert MOD.main() == 0


def test_invalid_json_stdin_returns_0(monkeypatch):
    _set_stdin(monkeypatch, "{not valid json")
    assert MOD.main() == 0


# --------------------------------------------------------------------------
# 早期 return: SKILL.md 以外
# --------------------------------------------------------------------------

def test_non_skill_md_path_returns_0_without_invoking_validator(monkeypatch):
    called = {"ran": False}
    monkeypatch.setattr(
        MOD.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("validator should not run")),
    )
    _set_stdin(monkeypatch, {"file_path": "/some/dir/README.md"})
    assert MOD.main() == 0
    assert called["ran"] is False  # validator は呼ばれていない


def test_missing_file_path_key_returns_0(monkeypatch):
    # file_path も tool_input も無い → fp == "" → SKILL.md で終わらず return 0
    _set_stdin(monkeypatch, {"unrelated": "x"})
    assert MOD.main() == 0


def test_tool_input_file_path_resolution_non_skill(monkeypatch):
    # tool_input.file_path 経由でも SKILL.md でなければ return 0
    _set_stdin(monkeypatch, {"tool_input": {"file_path": "/x/foo.py"}})
    assert MOD.main() == 0


# --------------------------------------------------------------------------
# SKILL.md だが対象 / validator が存在しない
# --------------------------------------------------------------------------

def test_skill_md_but_target_missing_returns_0(monkeypatch, tmp_path):
    missing = tmp_path / "skills" / "run-x" / "SKILL.md"  # 作らない
    _set_stdin(monkeypatch, {"file_path": str(missing)})
    monkeypatch.setattr(
        MOD.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert MOD.main() == 0


def test_skill_md_exists_but_validator_missing_returns_0(monkeypatch, tmp_path):
    target = tmp_path / "SKILL.md"
    target.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    # VALIDATOR を存在しないパスへ差し替える
    monkeypatch.setattr(MOD, "VALIDATOR", tmp_path / "does-not-exist.py")
    monkeypatch.setattr(
        MOD.subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    _set_stdin(monkeypatch, {"file_path": str(target)})
    assert MOD.main() == 0


# --------------------------------------------------------------------------
# validator 起動: 合格 / 違反 / 例外
# --------------------------------------------------------------------------

def _prep_skill_and_validator(monkeypatch, tmp_path):
    target = tmp_path / "SKILL.md"
    target.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    validator = tmp_path / "validate-frontmatter.py"
    validator.write_text("# stub validator\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "VALIDATOR", validator)
    return target, validator


def test_validator_passes_no_warning(monkeypatch, capsys, tmp_path):
    target, _ = _prep_skill_and_validator(monkeypatch, tmp_path)
    monkeypatch.setattr(MOD.subprocess, "run", lambda *a, **k: _FakeProc(0))
    _set_stdin(monkeypatch, {"file_path": str(target)})
    assert MOD.main() == 0
    err = capsys.readouterr().err
    assert "hook-validate-skill-md" not in err  # warning は出ない


def test_validator_fails_emits_warning_but_exit_0(monkeypatch, capsys, tmp_path):
    target, _ = _prep_skill_and_validator(monkeypatch, tmp_path)
    monkeypatch.setattr(
        MOD.subprocess, "run",
        lambda *a, **k: _FakeProc(1, stdout="ok-context", stderr="ERR: bad semver"),
    )
    _set_stdin(monkeypatch, {"file_path": str(target)})
    assert MOD.main() == 0  # warn-only: 違反でも 0
    err = capsys.readouterr().err
    assert "hook-validate-skill-md: warnings for" in err
    assert "ERR: bad semver" in err
    assert "ok-context" in err


def test_validator_subprocess_raises_emits_skipped(monkeypatch, capsys, tmp_path):
    target, _ = _prep_skill_and_validator(monkeypatch, tmp_path)

    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=10)

    monkeypatch.setattr(MOD.subprocess, "run", _boom)
    _set_stdin(monkeypatch, {"file_path": str(target)})
    assert MOD.main() == 0
    err = capsys.readouterr().err
    assert "hook-validate-skill-md: skipped" in err


def test_validator_invoked_with_correct_argv(monkeypatch, tmp_path):
    target, validator = _prep_skill_and_validator(monkeypatch, tmp_path)
    captured = {}

    def _capture(cmd, **k):
        captured["cmd"] = cmd
        captured["kwargs"] = k
        return _FakeProc(0)

    monkeypatch.setattr(MOD.subprocess, "run", _capture)
    _set_stdin(monkeypatch, {"file_path": str(target)})
    assert MOD.main() == 0
    assert captured["cmd"] == ["python3", str(validator), str(target)]
    assert captured["kwargs"]["timeout"] == 10
    assert captured["kwargs"]["capture_output"] is True


# --------------------------------------------------------------------------
# __main__ / subprocess 実行経路 (genuine end-to-end)
# --------------------------------------------------------------------------

def _run_script(stdin_text, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text, capture_output=True, text=True, cwd=cwd,
    )


def test_subprocess_empty_stdin_exit0(tmp_path):
    proc = _run_script("", cwd=str(tmp_path))
    assert proc.returncode == 0
    assert proc.stderr == ""


def test_subprocess_non_skill_path_exit0(tmp_path):
    proc = _run_script(json.dumps({"file_path": "/x/y.txt"}), cwd=str(tmp_path))
    assert proc.returncode == 0


def test_subprocess_real_validator_failure_warns(tmp_path):
    # cwd に scripts/validate-frontmatter.py を置き (exit 1 を返すスタブ),
    # SKILL.md を渡すと warn が出るが exit 0 のままなことを実プロセスで確認。
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "validate-frontmatter.py").write_text(
        "import sys\nsys.stderr.write('STUB-FAIL\\n')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    proc = _run_script(json.dumps({"file_path": str(skill)}), cwd=str(tmp_path))
    assert proc.returncode == 0  # warn-only
    assert "hook-validate-skill-md: warnings for" in proc.stderr
    assert "STUB-FAIL" in proc.stderr


def test_subprocess_real_validator_pass_silent(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "validate-frontmatter.py").write_text(
        "raise SystemExit(0)\n", encoding="utf-8"
    )
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    proc = _run_script(json.dumps({"file_path": str(skill)}), cwd=str(tmp_path))
    assert proc.returncode == 0
    assert proc.stderr == ""
