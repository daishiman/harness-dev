"""run-build-skill/scripts/render-settings-proposal.py の機能テスト。

skill brief から settings.json hook マージ案 (proposal) を生成するスクリプトを
genuine に検証する:

  - hook_events から event 別 hooks 配線 (command は
    `python3 {{SCRIPT_ROOT}}/hook-<skill>-<event_lc>.py` 形式) を生成
  - permissions.deny skeleton の同梱、ensure_ascii=False の日本語保持
  - hook_events 空/欠落 → hooks は空 dict のまま proposal を書く
  - 親ディレクトリ自動作成、stderr の手動マージ通知 2 行
  - 異常系: brief 不在 (FileNotFoundError) / 壊れた JSON (JSONDecodeError) →
    未捕捉例外で exit 1
  - argparse 必須引数欠落 → exit 2

write-scope: output-dir — 書き込みは全て tmp_path 配下で完結する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
          / "scripts" / "render-settings-proposal.py")

_SPEC = importlib.util.spec_from_file_location(
    "render_settings_proposal_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _call_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["render-settings-proposal.py", *argv])
    return MOD.main()


def _write_brief(tmp_path, payload):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return brief


# --------------------------------------------------------------------------
# 正常系: hook_events → hooks 配線 + permissions skeleton
# --------------------------------------------------------------------------

def test_main_renders_hooks_for_each_event(tmp_path, monkeypatch, capsys):
    brief = _write_brief(tmp_path, {"hook_events": ["PreToolUse", "Stop"]})
    out = tmp_path / "settings-proposal.json"
    rc = _call_main(monkeypatch, [
        "--skill-name", "run-demo", "--brief", str(brief), "--out", str(out),
    ])
    assert rc == 0
    proposal = json.loads(out.read_text(encoding="utf-8"))
    assert set(proposal["hooks"]) == {"PreToolUse", "Stop"}
    cmd = proposal["hooks"]["PreToolUse"][0]["hooks"][0]
    assert cmd["type"] == "command"
    assert cmd["command"] == "python3 {{SCRIPT_ROOT}}/hook-run-demo-pretooluse.py"
    stop_cmd = proposal["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert stop_cmd.endswith("hook-run-demo-stop.py")
    err = capsys.readouterr().err
    assert f"proposal written: {out}" in err
    assert "merge manually" in err


def test_main_permissions_deny_skeleton_keeps_japanese(tmp_path, monkeypatch):
    brief = _write_brief(tmp_path, {"hook_events": ["Stop"]})
    out = tmp_path / "p.json"
    rc = _call_main(monkeypatch, [
        "--skill-name", "run-x", "--brief", str(brief), "--out", str(out),
    ])
    assert rc == 0
    raw = out.read_text(encoding="utf-8")
    # ensure_ascii=False なので日本語がそのまま残る (\uXXXX にならない)。
    assert "deny rule を追加" in raw
    proposal = json.loads(raw)
    deny = proposal["permissions"]["deny"]
    assert len(deny) == 1
    assert "run-x" in deny[0]


def test_main_empty_or_missing_hook_events_yields_empty_hooks(tmp_path, monkeypatch):
    for payload in ({"hook_events": []}, {}):
        brief = _write_brief(tmp_path, payload)
        out = tmp_path / "p.json"
        rc = _call_main(monkeypatch, [
            "--skill-name", "run-x", "--brief", str(brief), "--out", str(out),
        ])
        assert rc == 0
        proposal = json.loads(out.read_text(encoding="utf-8"))
        assert proposal["hooks"] == {}
        assert "permissions" in proposal
        out.unlink()


def test_main_creates_parent_dirs(tmp_path, monkeypatch):
    brief = _write_brief(tmp_path, {"hook_events": ["Stop"]})
    out = tmp_path / "deep" / "nested" / "p.json"
    rc = _call_main(monkeypatch, [
        "--skill-name", "run-x", "--brief", str(brief), "--out", str(out),
    ])
    assert rc == 0
    assert out.exists()


# --------------------------------------------------------------------------
# 異常系: brief 不在 / 壊れた JSON → 未捕捉例外 (in-process) / exit 1 (CLI)
# --------------------------------------------------------------------------

def test_main_brief_not_found_raises(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError):
        _call_main(monkeypatch, [
            "--skill-name", "run-x",
            "--brief", str(tmp_path / "absent.json"),
            "--out", str(tmp_path / "p.json"),
        ])
    assert not (tmp_path / "p.json").exists()


def test_main_corrupt_brief_raises(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_text("{ broken json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _call_main(monkeypatch, [
            "--skill-name", "run-x", "--brief", str(brief),
            "--out", str(tmp_path / "p.json"),
        ])


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


def test_cli_writes_proposal_exit0(tmp_path):
    brief = _write_brief(tmp_path, {"hook_events": ["PreToolUse"]})
    out = tmp_path / "p.json"
    proc = _run("--skill-name", "run-demo", "--brief", str(brief),
                "--out", str(out), cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "proposal written" in proc.stderr
    proposal = json.loads(out.read_text(encoding="utf-8"))
    assert "PreToolUse" in proposal["hooks"]


def test_cli_brief_not_found_exit1(tmp_path):
    proc = _run("--skill-name", "run-x",
                "--brief", str(tmp_path / "absent.json"),
                "--out", str(tmp_path / "p.json"), cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "FileNotFoundError" in proc.stderr


def test_cli_missing_args_exit2(tmp_path):
    proc = _run("--skill-name", "run-x", cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--brief" in proc.stderr or "--out" in proc.stderr
