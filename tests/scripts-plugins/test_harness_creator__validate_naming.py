"""run-build-skill/scripts/validate-naming.py の機能テスト。

pre-flight 命名検査 (kebab-case / prefix / 長さ上限) を genuine に検証する:

  - 引数なし → usage を stderr に出して exit 2
  - 正常系: 各許可 prefix + kebab-case → stdout "ok" / exit 0
  - 第1条 (kebab-case 違反) / 第2条 (prefix なし) / 第5条 (60文字超過) の
    単独発火と複合発火 → exit 1 + stderr に条文
  - CLI 契約は subprocess、行カバレッジは in-process main() の両輪で担保

network: false / write-scope: none のスクリプトなのでファイル I/O はない。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
          / "scripts" / "validate-naming.py")

_SPEC = importlib.util.spec_from_file_location("validate_naming_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _call_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["validate-naming.py", *argv])
    return MOD.main()


# --------------------------------------------------------------------------
# 正常系
# --------------------------------------------------------------------------

@pytest.mark.parametrize("prefix", MOD.PREFIXES)
def test_main_ok_for_each_allowed_prefix(monkeypatch, capsys, prefix):
    rc = _call_main(monkeypatch, [f"{prefix}demo-skill"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "ok"
    assert captured.err == ""


def test_main_ok_with_digits_and_single_segment_suffix(monkeypatch, capsys):
    assert _call_main(monkeypatch, ["run-a1-b2"]) == 0
    assert capsys.readouterr().out.strip() == "ok"


# --------------------------------------------------------------------------
# 引数なし → usage / exit 2
# --------------------------------------------------------------------------

def test_main_no_args_usage_exit2(monkeypatch, capsys):
    rc = _call_main(monkeypatch, [])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


# --------------------------------------------------------------------------
# 各条文の単独発火 (exit 1)
# --------------------------------------------------------------------------

def test_main_kebab_violation_only(monkeypatch, capsys):
    # prefix は満たすが大文字混入で kebab-case のみ違反。
    rc = _call_main(monkeypatch, ["run-Foo"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "第1条" in err
    assert "第2条" not in err
    assert "第5条" not in err


def test_main_prefix_violation_only(monkeypatch, capsys):
    rc = _call_main(monkeypatch, ["foo-bar"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "第2条" in err
    assert "第1条" not in err


def test_main_length_violation_only(monkeypatch, capsys):
    name = "run-" + "a" * 57  # 61 文字 (kebab / prefix は適合)
    rc = _call_main(monkeypatch, [name])
    assert rc == 1
    err = capsys.readouterr().err
    assert "第5条" in err
    assert "第1条" not in err
    assert "第2条" not in err


def test_main_length_boundary_60_is_ok(monkeypatch, capsys):
    name = "run-" + "a" * 56  # ちょうど 60 文字 → 適合
    assert _call_main(monkeypatch, [name]) == 0
    assert capsys.readouterr().out.strip() == "ok"


# --------------------------------------------------------------------------
# 複合発火: 全エラーが stderr に並ぶ
# --------------------------------------------------------------------------

def test_main_multiple_violations_reported_together(monkeypatch, capsys):
    rc = _call_main(monkeypatch, ["BAD_NAME"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "第1条" in err
    assert "第2条" in err


def test_main_empty_segment_is_kebab_violation(monkeypatch, capsys):
    # 連続ハイフンは空セグメントとして kebab-case 違反。
    rc = _call_main(monkeypatch, ["run--foo"])
    assert rc == 1
    assert "第1条" in capsys.readouterr().err


# --------------------------------------------------------------------------
# CLI 契約 (subprocess): exit code / ストリーム
# --------------------------------------------------------------------------

def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_valid_name_exit0(tmp_path):
    proc = _run("run-demo", cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_cli_invalid_name_exit1(tmp_path):
    proc = _run("not-prefixed", cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "第2条" in proc.stderr
    assert proc.stdout == ""


def test_cli_no_args_exit2(tmp_path):
    proc = _run(cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "usage:" in proc.stderr
