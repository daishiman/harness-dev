"""PKG-009 governance-lint wrapper contract tests."""
from __future__ import annotations

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


def test_exit_code_is_passed_through(tmp_path, capsys):
    # package contract の無い skills dir は linter 自身が非 0 で止まる。wrapper はその exit をそのまま返す。
    args = ["--skills-dir", str(tmp_path / "skills"), "--fail-on-external"]
    direct = subprocess.run([sys.executable, str(MOD.linter_path()), *args], capture_output=True, check=False)
    assert direct.returncode != 0
    assert MOD.main(args) == direct.returncode
    log = json.loads(capsys.readouterr().out)
    assert (log["pkg_id"], log["status"]) == ("PKG-009", "fail")
    assert any("package contract" in f for f in log["findings"])


def _plugin_with_skill(tmp_path: Path, body: str, depends_on: list | None = None) -> Path:
    plugin = tmp_path / "plugins" / "demo"
    (plugin / "references").mkdir(parents=True)
    (plugin / "references" / "package-contract.json").write_text(
        json.dumps({"package_mode": "bundle", "entry_points": {}, "depends_on": depends_on or []}),
        encoding="utf-8",
    )
    skill = plugin / "skills" / "run-demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: run-demo\n---\n{body}\n", encoding="utf-8")
    return plugin / "skills"


def test_clean_plugin_is_pkg_009_pass(tmp_path, capsys):
    # --json を付けなくても PKG-009 の result (pkg_id / status) を出す
    skills = _plugin_with_skill(tmp_path, "参照は references/x.md だけ")
    assert MOD.main(["--skills-dir", str(skills), "--fail-on-external"]) == 0
    log = json.loads(capsys.readouterr().out)
    assert (log["pkg_id"], log["status"], log["findings"]) == ("PKG-009", "pass", [])
    assert log["analysis"]["external_ref_count"] == 0
    assert log["source_exit_code"] == 0
    assert log["last_run_at"].endswith("Z")


@pytest.mark.parametrize("fail_on_external, expected_exit", [(True, 1), (False, 0)])
def test_external_ref_is_pkg_009_fail(tmp_path, capsys, fail_on_external, expected_exit):
    # status は --fail-on-external の有無で変えない。exit だけが lint に従う
    skills = _plugin_with_skill(tmp_path, "外の plugins/other/skills/x/SKILL.md を読む")
    args = ["--skills-dir", str(skills), "--json"] + (["--fail-on-external"] if fail_on_external else [])
    assert MOD.main(args) == expected_exit
    log = json.loads(capsys.readouterr().out)
    assert (log["pkg_id"], log["status"]) == ("PKG-009", "fail")
    assert any("plugins/other/skills/x/SKILL.md" in f for f in log["findings"])


def test_missing_linter_script_emits_fail_json(monkeypatch, tmp_path, capsys):
    # skill-governance-lint は見つかるが lint-external-refs.py が無い。python に無いファイルを渡さず fail JSON で止まる
    (tmp_path / "skill-governance-lint" / "scripts").mkdir(parents=True)
    monkeypatch.setattr(MOD, "resolve_root", lambda name, root: tmp_path / "skill-governance-lint")
    assert MOD.main(["--skills-dir", str(tmp_path)]) == 2
    log = json.loads(capsys.readouterr().out)
    assert (log["pkg_id"], log["status"]) == ("PKG-009", "fail")
    assert "lint-external-refs.py is missing" in log["findings"][0]


@pytest.mark.parametrize("stdout, code, expected_exit", [("not json", 0, 2), ("[]", 1, 2), ("", 3, 3)])
def test_linter_without_json_object_is_fail(monkeypatch, tmp_path, capsys, stdout, code, expected_exit):
    fake = tmp_path / "lint-external-refs.py"
    fake.write_text(f"import sys\nsys.stdout.write({stdout!r})\nsys.exit({code})\n", encoding="utf-8")
    monkeypatch.setattr(MOD, "linter_path", lambda: fake)
    assert MOD.main([]) == expected_exit
    log = json.loads(capsys.readouterr().out)
    assert (log["pkg_id"], log["status"]) == ("PKG-009", "fail")
    assert "JSON を返さなかった" in log["findings"][0]


def test_unreadable_external_count_is_fail():
    log = MOD.normalize({"external_ref_count": None, "reports": [], "contract_errors": []}, 0)
    assert log["status"] == "fail"


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
