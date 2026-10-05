"""PKG-009 governance-lint wrapper contract tests."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-plugin-package-check"
    / "scripts" / "lint-pkg-009.py"
)
SPEC = importlib.util.spec_from_file_location("lint_pkg_009_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_linter_resolves_to_sibling_plugin_script():
    path = MOD.linter_path()
    assert path.name == "lint-external-refs.py"
    assert path.parent.parent.name == "skill-governance-lint"
    assert path.is_file()


def test_exit_code_is_passed_through(tmp_path):
    # package contract の無い skills dir は linter 自身が非 0 で止まる。wrapper はその exit をそのまま返す。
    args = ["--skills-dir", str(tmp_path / "skills"), "--fail-on-external"]
    direct = subprocess.run([sys.executable, str(MOD.linter_path()), *args], capture_output=True, check=False)
    assert direct.returncode != 0
    assert MOD.main(args) == direct.returncode


def test_missing_resolver_stops(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "PLUGIN_ROOT", tmp_path)
    with pytest.raises(MOD.LinterUnavailable, match="extract-plugin-root.py is missing"):
        MOD.linter_path()


def test_missing_sibling_plugin_stops_with_fail_log(monkeypatch, tmp_path, capsys):
    # resolver だけを持つ harness-creator を置き、兄弟・installed_plugins.json・cache のどこにも
    # skill-governance-lint が無い状態にする。
    plugin_root = tmp_path / "plugins" / "harness-creator"
    (plugin_root / "scripts").mkdir(parents=True)
    resolver = ROOT / "plugins" / "harness-creator" / "scripts" / "extract-plugin-root.py"
    (plugin_root / "scripts" / "extract-plugin-root.py").write_bytes(resolver.read_bytes())
    monkeypatch.setattr(MOD, "PLUGIN_ROOT", plugin_root)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(MOD.LinterUnavailable, match="skill-governance-lint plugin not found"):
        MOD.linter_path()
    # 推測 path で lint を呼ばず、停止理由を PKG-009 の fail ログとして stdout に残す。
    assert MOD.main(["--json"]) == 2
    log = json.loads(capsys.readouterr().out)
    assert log["pkg_id"] == "PKG-009"
    assert log["status"] == "fail"
    assert "skill-governance-lint plugin not found" in log["findings"][0]
