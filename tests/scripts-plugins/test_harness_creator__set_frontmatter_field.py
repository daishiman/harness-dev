"""run-build-skill/scripts/set-frontmatter-field.py の機能テスト。

stdlib のみで SKILL.md frontmatter の 1 フィールドを上書き/挿入するスクリプトを
genuine に検証する:

  - 既存キーの置換 (他キー・本文は不変、末尾改行維持)
  - 未存在キーの閉じ "---" 直前への挿入
  - 前方一致の誤爆なし (`names:` は `name` 置換の対象外)
  - 異常系: ファイル不在 / frontmatter なし / 空ファイル / 閉じ "---" なし → exit 1
  - argparse 必須引数欠落 → exit 2
  - CLI 契約は subprocess、行カバレッジは in-process main() の両輪で担保

write-scope: output-dir — 書き込みは全て tmp_path 配下で完結する。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
          / "scripts" / "set-frontmatter-field.py")

_SPEC = importlib.util.spec_from_file_location("set_frontmatter_field_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _call_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["set-frontmatter-field.py", *argv])
    return MOD.main()


def _skill_md(tmp_path, text):
    p = tmp_path / "SKILL.md"
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# 置換 / 挿入
# --------------------------------------------------------------------------

def test_main_replaces_existing_key(tmp_path, monkeypatch):
    p = _skill_md(tmp_path, "---\nname: old\ndescription: 説明\n---\n本文\n")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "name", "--value", "new"])
    assert rc == 0
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines == ["---", "name: new", "description: 説明", "---", "本文"]


def test_main_inserts_missing_key_before_closing_fence(tmp_path, monkeypatch):
    p = _skill_md(tmp_path, "---\nname: x\n---\n本文\n")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "version", "--value", "1.0.0"])
    assert rc == 0
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines == ["---", "name: x", "version: 1.0.0", "---", "本文"]


def test_main_replace_preserves_body_and_trailing_newline(tmp_path, monkeypatch):
    p = _skill_md(tmp_path, "---\nname: x\n---\n本文1\n\n本文2\n")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "name", "--value", "y"])
    assert rc == 0
    text = p.read_text(encoding="utf-8")
    assert text.endswith("本文1\n\n本文2\n")


def test_main_key_prefix_does_not_false_match(tmp_path, monkeypatch):
    # `names:` は `name:` と前方一致しないため置換されず、`name` は新規挿入される。
    p = _skill_md(tmp_path, "---\nnames: keep\n---\nbody\n")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "name", "--value", "v"])
    assert rc == 0
    lines = p.read_text(encoding="utf-8").splitlines()
    assert "names: keep" in lines
    assert "name: v" in lines
    assert lines.index("names: keep") < lines.index("name: v")


def test_main_replaces_first_occurrence_only(tmp_path, monkeypatch):
    p = _skill_md(tmp_path, "---\nkind: run\nkind: ref\n---\nbody\n")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "kind", "--value", "wrap"])
    assert rc == 0
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "kind: wrap"
    assert lines[2] == "kind: ref"  # 2 個目は据え置き


# --------------------------------------------------------------------------
# 異常系 → exit 1
# --------------------------------------------------------------------------

def test_main_file_not_found_exit1(tmp_path, monkeypatch, capsys):
    rc = _call_main(monkeypatch, [
        "--file", str(tmp_path / "absent.md"), "--key", "k", "--value", "v",
    ])
    assert rc == 1
    assert "file not found" in capsys.readouterr().err


def test_main_no_frontmatter_exit1(tmp_path, monkeypatch, capsys):
    p = _skill_md(tmp_path, "本文のみ\n")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "k", "--value", "v"])
    assert rc == 1
    assert "no frontmatter" in capsys.readouterr().err
    assert p.read_text(encoding="utf-8") == "本文のみ\n"  # 不変


def test_main_empty_file_exit1(tmp_path, monkeypatch, capsys):
    p = _skill_md(tmp_path, "")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "k", "--value", "v"])
    assert rc == 1
    assert "no frontmatter" in capsys.readouterr().err


def test_main_unclosed_frontmatter_exit1(tmp_path, monkeypatch):
    p = _skill_md(tmp_path, "---\nname: x\nbody without closing fence\n")
    original = p.read_text(encoding="utf-8")
    rc = _call_main(monkeypatch, ["--file", str(p), "--key", "k", "--value", "v"])
    assert rc == 1
    assert p.read_text(encoding="utf-8") == original  # 不変


# --------------------------------------------------------------------------
# argparse 必須引数欠落 → exit 2
# --------------------------------------------------------------------------

def test_main_missing_required_args_systemexit2(monkeypatch):
    with pytest.raises(SystemExit) as ei:
        _call_main(monkeypatch, ["--file", "x.md"])
    assert ei.value.code == 2


# --------------------------------------------------------------------------
# CLI 契約 (subprocess)
# --------------------------------------------------------------------------

def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_replace_exit0(tmp_path):
    p = _skill_md(tmp_path, "---\nname: old\n---\nbody\n")
    proc = _run("--file", str(p), "--key", "name", "--value", "new", cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "name: new" in p.read_text(encoding="utf-8")


def test_cli_file_not_found_exit1(tmp_path):
    proc = _run("--file", str(tmp_path / "no.md"), "--key", "k", "--value", "v",
                cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "file not found" in proc.stderr


def test_cli_missing_args_exit2(tmp_path):
    proc = _run("--file", "x.md", cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--key" in proc.stderr or "--value" in proc.stderr
