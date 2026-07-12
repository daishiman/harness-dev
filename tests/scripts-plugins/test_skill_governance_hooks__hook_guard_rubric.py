"""genuine 機能テスト (scripts2): hook-guard-rubric.py

対象: plugins/skill-governance-hooks/scripts/hook-guard-rubric.py

PreToolUse hook。canonical rubric (ref-skill-design-rubric/rubric.json,
assign-*/rubric.json, rubric-registry.json 由来 suffix) への Write/Edit/MultiEdit
を deny する。ALLOW_RUBRIC_EDIT=1 でバイパス。network なし。

方針:
  - is_guarded() / registry_guarded_suffixes() は import して実入力で assert。
    cwd / PROJECT_ROOT 由来 registry の追加 suffix・不正 JSON skip・OSError skip も検証。
  - main() は (1) in-process: sys.stdin / 環境変数 / cwd を monkeypatch し
    allow / deny / bypass / tool フィルタ / fail-open の全分岐, (2) subprocess:
    実 stdin JSON を渡し exit code と hookSpecificOutput JSON を assert。
  - エッジ: 空 stdin / 不正 JSON / file_path 欠落 / tool_input null。

外部 I/O は registry ファイル読みのみ (tmp_path に限定し repo を汚さない)。
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-hooks" / "scripts" / "hook-guard-rubric.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("hook_guard_rubric_scripts2", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _clean_env(monkeypatch):
    monkeypatch.delenv("ALLOW_RUBRIC_EDIT", raising=False)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)


def _isolate_cwd(monkeypatch, tmp_path):
    """registry を引かない空の cwd / PROJECT_ROOT に固定 (default suffix のみ残る)。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))


# --------------------------------------------------------------------------
# registry_guarded_suffixes
# --------------------------------------------------------------------------
def test_registry_suffixes_default_only(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    _isolate_cwd(monkeypatch, tmp_path)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    suffixes = MOD.registry_guarded_suffixes()
    assert "ref-skill-design-rubric/rubric.json" in suffixes


def test_registry_suffixes_extends_from_registry(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    reg_dir = tmp_path / "creator-kit" / "config"
    reg_dir.mkdir(parents=True)
    (reg_dir / "rubric-registry.json").write_text(
        json.dumps(
            {
                "rubrics": [
                    {"rubric": "skills/assign-foo/rubric.json"},
                    {"rubric": "skills\\assign-bar\\rubric.json"},  # backslash 正規化
                    {"name": "no-rubric-field"},  # rubric 無しは無視
                ]
            }
        ),
        encoding="utf-8",
    )
    suffixes = MOD.registry_guarded_suffixes()
    assert "skills/assign-foo/rubric.json" in suffixes
    assert "skills/assign-bar/rubric.json" in suffixes  # \\ -> /
    assert "ref-skill-design-rubric/rubric.json" in suffixes


def test_registry_suffixes_malformed_json_is_skipped(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    reg_dir = tmp_path / "creator-kit" / "config"
    reg_dir.mkdir(parents=True)
    (reg_dir / "rubric-registry.json").write_text("{not valid json", encoding="utf-8")
    # JSONDecodeError は continue でスキップ → default のみ残る (例外を投げない)
    suffixes = MOD.registry_guarded_suffixes()
    assert suffixes == set(MOD.GUARDED_SUFFIXES)


def test_registry_suffixes_no_registry_file(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    # registry 無し → default のみ
    assert MOD.registry_guarded_suffixes() == set(MOD.GUARDED_SUFFIXES)


# --------------------------------------------------------------------------
# is_guarded
# --------------------------------------------------------------------------
def test_is_guarded_empty_path(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    _isolate_cwd(monkeypatch, tmp_path)
    assert MOD.is_guarded("") is False
    assert MOD.is_guarded(None) is False


def test_is_guarded_default_suffix(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    _isolate_cwd(monkeypatch, tmp_path)
    assert MOD.is_guarded("/repo/x/ref-skill-design-rubric/rubric.json") is True


def test_is_guarded_assign_glob(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    _isolate_cwd(monkeypatch, tmp_path)
    assert MOD.is_guarded("/repo/plugins/p/skills/assign-foo/rubric.json") is True
    # ネストした assign-*/**/rubric.json も末尾一致で guard
    assert MOD.is_guarded("a/assign-x/nested/rubric.json") is True


def test_is_guarded_backslash_normalized(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    _isolate_cwd(monkeypatch, tmp_path)
    assert MOD.is_guarded("C:\\repo\\skills\\assign-foo\\rubric.json") is True


def test_is_guarded_non_rubric_allowed(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    _isolate_cwd(monkeypatch, tmp_path)
    assert MOD.is_guarded("/repo/skills/assign-foo/SKILL.md") is False
    # assign- を含むが rubric.json で終わらない
    assert MOD.is_guarded("/repo/skills/assign-foo/config.json") is False
    # rubric.json で終わるが assign- を含まず default suffix でもない
    assert MOD.is_guarded("/repo/skills/other/rubric.json") is False


def test_is_guarded_from_registry(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    reg_dir = tmp_path / "creator-kit" / "config"
    reg_dir.mkdir(parents=True)
    (reg_dir / "rubric-registry.json").write_text(
        json.dumps({"rubrics": [{"rubric": "custom/path/myrubric.json"}]}),
        encoding="utf-8",
    )
    assert MOD.is_guarded("/abs/custom/path/myrubric.json") is True
    assert MOD.is_guarded("/abs/custom/path/other.json") is False


# --------------------------------------------------------------------------
# main() — in-process (stdin / env / cwd を monkeypatch)
# --------------------------------------------------------------------------
def _run_main(monkeypatch, tmp_path, stdin_text, env=None):
    _clean_env(monkeypatch)
    _isolate_cwd(monkeypatch, tmp_path)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    return MOD.main()


def test_main_allow_when_env_bypass(monkeypatch, tmp_path, capsys):
    rc = _run_main(
        monkeypatch,
        tmp_path,
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x/ref-skill-design-rubric/rubric.json"}}),
        env={"ALLOW_RUBRIC_EDIT": "1"},
    )
    assert rc == 0
    assert capsys.readouterr().out == ""  # bypass は stdout 無し


def test_main_deny_guarded_edit(monkeypatch, tmp_path, capsys):
    rc = _run_main(
        monkeypatch,
        tmp_path,
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "p/skills/assign-foo/rubric.json"}}),
    )
    assert rc == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "assign-foo/rubric.json" in payload["hookSpecificOutput"]["permissionDecisionReason"]
    # 後方互換のため stderr にも reason を出す
    assert "ALLOW_RUBRIC_EDIT" in captured.err


def test_main_deny_guarded_write(monkeypatch, tmp_path, capsys):
    rc = _run_main(
        monkeypatch,
        tmp_path,
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": "x/ref-skill-design-rubric/rubric.json"}}),
    )
    assert rc == 2
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_deny_guarded_multiedit(monkeypatch, tmp_path, capsys):
    rc = _run_main(
        monkeypatch,
        tmp_path,
        json.dumps({"tool_name": "MultiEdit", "tool_input": {"file_path": "x/ref-skill-design-rubric/rubric.json"}}),
    )
    assert rc == 2


def test_main_allow_non_guarded_file(monkeypatch, tmp_path, capsys):
    rc = _run_main(
        monkeypatch,
        tmp_path,
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "p/skills/assign-foo/SKILL.md"}}),
    )
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_allow_non_edit_tool(monkeypatch, tmp_path, capsys):
    rc = _run_main(
        monkeypatch,
        tmp_path,
        json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x/ref-skill-design-rubric/rubric.json"}}),
    )
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_allow_missing_file_path(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, json.dumps({"tool_name": "Edit", "tool_input": {}}))
    assert rc == 0


def test_main_allow_tool_input_null(monkeypatch, tmp_path, capsys):
    # tool_input が null でも (data.get(...) or {}) で吸収される
    rc = _run_main(monkeypatch, tmp_path, json.dumps({"tool_name": "Edit", "tool_input": None}))
    assert rc == 0


def test_main_allow_missing_tool_name(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, json.dumps({"tool_input": {"file_path": "x/ref-skill-design-rubric/rubric.json"}}))
    assert rc == 0


def test_main_fail_open_empty_stdin(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, "")
    assert rc == 0  # 空入力は fail open


def test_main_fail_open_whitespace_stdin(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, "   \n  ")
    assert rc == 0


def test_main_fail_open_malformed_json(monkeypatch, tmp_path, capsys):
    rc = _run_main(monkeypatch, tmp_path, "{not json}")
    assert rc == 0  # malformed は fail open (except -> return 0)


def test_main_deny_uses_registry_suffix(monkeypatch, tmp_path, capsys):
    _clean_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    reg_dir = tmp_path / "creator-kit" / "config"
    reg_dir.mkdir(parents=True)
    (reg_dir / "rubric-registry.json").write_text(
        json.dumps({"rubrics": [{"rubric": "deep/custom-rubric.json"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "/abs/deep/custom-rubric.json"}})),
    )
    rc = MOD.main()
    assert rc == 2
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"


# --------------------------------------------------------------------------
# main() — subprocess (real stdin pipe)
# --------------------------------------------------------------------------
def _run_subprocess(stdin_text, cwd, env_extra=None):
    env = dict(os.environ)
    env.pop("ALLOW_RUBRIC_EDIT", None)
    env["PROJECT_ROOT"] = str(cwd)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
    )


def test_subprocess_deny_assign_rubric(tmp_path):
    res = _run_subprocess(
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "p/skills/assign-x/rubric.json"}}),
        cwd=tmp_path,
    )
    assert res.returncode == 2
    payload = json.loads(res.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_subprocess_allow_normal_edit(tmp_path):
    res = _run_subprocess(
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "p/skills/foo/SKILL.md"}}),
        cwd=tmp_path,
    )
    assert res.returncode == 0
    assert res.stdout == ""


def test_subprocess_bypass_env(tmp_path):
    res = _run_subprocess(
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x/ref-skill-design-rubric/rubric.json"}}),
        cwd=tmp_path,
        env_extra={"ALLOW_RUBRIC_EDIT": "1"},
    )
    assert res.returncode == 0
    assert res.stdout == ""


def test_subprocess_empty_stdin_fail_open(tmp_path):
    res = _run_subprocess("", cwd=tmp_path)
    assert res.returncode == 0
