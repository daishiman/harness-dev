"""PKG-010/011/012 isolated plugin lifecycle smoke tests."""
from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "plugins" / "harness-creator" / "skills" / "run-plugin-package-check" / "scripts"
SCRIPT = SCRIPT_DIR / "sandbox-plugin-lifecycle.py"
SPEC = importlib.util.spec_from_file_location("sandbox_plugin_lifecycle_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _fixture_plugin(tmp_path: Path, *, external_ref: str = "", settings: tuple[str, ...] = ()) -> tuple[Path, Path]:
    plugins_root = tmp_path / "plugins"
    plugin = plugins_root / "demo"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": "1.2.3", "description": "demo"}),
        encoding="utf-8",
    )
    (plugin / "references").mkdir()
    (plugin / "references" / "package-contract.json").write_text(
        json.dumps({"package_mode": "bundle", "entry_points": {}, "depends_on": []}),
        encoding="utf-8",
    )
    skill = plugin / "skills" / "run-demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"---\nname: run-demo\nkind: run\n---\n{external_ref}\n", encoding="utf-8")
    (plugin / "agents").mkdir()
    (plugin / "agents" / "demo.md").write_text("agent\n", encoding="utf-8")
    (plugin / "hooks").mkdir()
    (plugin / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
    (plugin / "scripts").mkdir()
    script = plugin / "scripts" / "run-demo.py"
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if settings:
        (plugin / "settings").mkdir()
        for fragment in settings:
            (plugin / "settings" / fragment).write_text('{"$schema": "x"}\n', encoding="utf-8")
    return plugins_root, plugin


def test_install_smoke_uses_external_ref_ssot_and_passes(tmp_path):
    _, plugin = _fixture_plugin(tmp_path)
    result = MOD.run_install(plugin, tmp_path / "sandbox")
    assert result["status"] == "pass"
    assert result["external_reference_gate"]["checker"].endswith("lint-external-refs.py")
    assert result["external_reference_gate"]["external_ref_count"] == 0
    assert result["installed_surface_count"] == 3


def test_install_smoke_fails_undeclared_cross_plugin_ref(tmp_path):
    _, plugin = _fixture_plugin(tmp_path, external_ref="plugins/ghost/references/contract.md")
    result = MOD.run_install(plugin, tmp_path / "sandbox")
    assert result["status"] == "fail"
    assert result["external_reference_gate"]["external_ref_count"] == 1


def test_uninstall_smoke_leaves_zero_plugin_residue(tmp_path):
    _, plugin = _fixture_plugin(tmp_path)
    sandbox = tmp_path / "sandbox"
    result = MOD.run_uninstall(plugin, sandbox)
    assert result["status"] == "pass"
    assert result["residues"] == []
    assert not (sandbox / "installed-plugins" / "demo").exists()
    assert not (sandbox / ".claude" / "plugin-state" / "demo").exists()


def test_uninstall_removes_settings_namespace_dir(tmp_path):
    # settings 断片は .claude/settings/<plugin>/ に置かれる。link だけ消して空ディレクトリを残すと残留扱いで fail だった
    _, plugin = _fixture_plugin(tmp_path, settings=("a.json", "b.json"))
    sandbox = tmp_path / "sandbox"
    result = MOD.run_uninstall(plugin, sandbox)
    assert result["installed_surface_count"] == 5
    assert result["removed_surface_count"] == 5
    assert result["residues"] == []
    assert result["status"] == "pass"
    assert not (sandbox / ".claude" / "settings" / "demo").exists()


def test_uninstall_leaves_other_plugins_settings(tmp_path):
    _, plugin = _fixture_plugin(tmp_path, settings=("a.json",))
    sandbox = tmp_path / "sandbox"
    other = sandbox / ".claude" / "settings" / "other" / "x.json"
    other.parent.mkdir(parents=True)
    other.write_text("{}\n", encoding="utf-8")
    assert MOD.run_uninstall(plugin, sandbox)["status"] == "pass"
    assert other.is_file()


def test_uninstall_removes_stale_settings_link_from_older_version(tmp_path):
    # 古い版にだけあった断片の link は registration に載らない。名前空間ごと消すので残らない
    _, plugin = _fixture_plugin(tmp_path, settings=("a.json",))
    sandbox = tmp_path / "sandbox"
    MOD.install(plugin, sandbox)
    stale = sandbox / ".claude" / "settings" / "demo" / "old.json"
    stale.symlink_to(sandbox / "installed-plugins" / "demo" / "settings" / "old.json")
    result = MOD.uninstall("demo", sandbox)
    assert result["residues"] == []
    assert not stale.is_symlink()


def test_upgrade_smoke_proves_noop_and_non_destructive_change(tmp_path):
    _, plugin = _fixture_plugin(tmp_path)
    result = MOD.run_upgrade(plugin, tmp_path / "sandbox")
    assert result["status"] == "pass"
    assert result["same_version"] == {
        "version": "1.2.3", "changed": False, "digest_unchanged": True,
    }
    assert result["different_version"]["to"] == "1.2.4"
    assert result["different_version"]["changed"] is True
    assert result["different_version"]["payload_changed"] is True
    assert result["different_version"]["user_state_preserved"] is True
    assert MOD.plugin_version(plugin) == "1.2.3"


def test_cli_uninstall_with_explicit_sandbox(tmp_path, capsys):
    plugins_root, _ = _fixture_plugin(tmp_path)
    rc = MOD.main([
        "--plugin", "demo",
        "--operation", "uninstall",
        "--plugins-root", str(plugins_root),
        "--sandbox-root", str(tmp_path / "sandbox"),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["pkg_id"] == "PKG-011"
    assert payload["status"] == "pass"


def test_shell_wrapper_rejects_missing_plugin_argument():
    proc = subprocess.run(
        [str(SCRIPT_DIR / "smoke-plugin-upgrade.sh")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "--plugin is required" in proc.stderr


def test_upgrade_twice_with_same_sandbox_root(tmp_path, capsys):
    # --sandbox-root を使い回しても前回の upgrade-source の写しで FileExistsError にならない
    plugins_root, _ = _fixture_plugin(tmp_path)
    args = ["--plugin", "demo", "--operation", "upgrade", "--plugins-root", str(plugins_root),
            "--sandbox-root", str(tmp_path / "sandbox")]
    for _ in range(2):
        rc = MOD.main(args)
        payload = json.loads(capsys.readouterr().out)
        assert (rc, payload["status"]) == (0, "pass"), payload["findings"]


def test_array_plugin_json_is_fail_json_not_traceback(tmp_path, capsys):
    plugins_root, plugin = _fixture_plugin(tmp_path)
    (plugin / ".claude-plugin" / "plugin.json").write_text("[1]", encoding="utf-8")
    rc = MOD.main(["--plugin", "demo", "--operation", "install", "--plugins-root", str(plugins_root),
                   "--sandbox-root", str(tmp_path / "sandbox")])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert (payload["pkg_id"], payload["status"]) == ("PKG-010", "fail")
    assert "not a JSON object" in payload["findings"][0]


def test_missing_sibling_lint_plugin_is_fail_json(tmp_path, capsys, monkeypatch):
    # 兄弟 plugin が無いと SystemExit で JSON を出さずに止まっていた。PKG-010 の fail JSON にする
    plugins_root, _ = _fixture_plugin(tmp_path)
    monkeypatch.setattr(MOD, "resolve_root", lambda name, root: None)
    rc = MOD.main(["--plugin", "demo", "--operation", "install", "--plugins-root", str(plugins_root),
                   "--sandbox-root", str(tmp_path / "sandbox")])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert (payload["pkg_id"], payload["status"]) == ("PKG-010", "fail")
    assert "skill-governance-lint plugin not found" in payload["findings"][0]


def test_missing_lint_script_in_sibling_is_fail_json(tmp_path, capsys, monkeypatch):
    plugins_root, _ = _fixture_plugin(tmp_path)
    (tmp_path / "skill-governance-lint" / "scripts").mkdir(parents=True)
    monkeypatch.setattr(MOD, "resolve_root", lambda name, root: tmp_path / "skill-governance-lint")
    rc = MOD.main(["--plugin", "demo", "--operation", "install", "--plugins-root", str(plugins_root),
                   "--sandbox-root", str(tmp_path / "sandbox")])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert "lint-external-refs.py is missing" in payload["findings"][0]
