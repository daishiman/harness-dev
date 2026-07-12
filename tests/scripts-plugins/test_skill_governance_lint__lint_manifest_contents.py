"""genuine な機能テスト: skill-governance-lint/scripts/lint-manifest-contents.py

純関数 (expect / load_excluded_paths / is_excluded / check_bidirectional /
check_yaml_spec_freshness) を実入力で呼び実出力を assert する。main() は
subprocess (sys.executable) で実行し returncode と stdout を assert する。

network / keychain / Notion などの外部 I/O はこのスクリプトには無い。check_bidirectional
は KIT_DIR 配下の実ファイルを走査するため、module の KIT_DIR を tmp_path へ
monkeypatch し repo を汚さず決定論的に検証する。
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-manifest-contents.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("lint_manifest_contents_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---- load_excluded_paths ----
def test_load_excluded_paths_returns_list_when_present():
    assert MOD.load_excluded_paths({"excluded_paths": ["scripts/foo.py", "skills/bar/"]}) == [
        "scripts/foo.py",
        "skills/bar/",
    ]


def test_load_excluded_paths_defaults_to_empty():
    assert MOD.load_excluded_paths({}) == []


# ---- is_excluded ----
def test_is_excluded_matches_prefix():
    excluded = ["scripts/internal/", "skills/legacy/"]
    assert MOD.is_excluded("scripts/internal/helper.py", excluded) is True
    assert MOD.is_excluded("skills/legacy/old-skill/", excluded) is True


def test_is_excluded_trailing_slash_is_stripped_for_comparison():
    # "skills/legacy/" -> rstrip("/") -> "skills/legacy"; "skills/legacy" startswith ok
    assert MOD.is_excluded("skills/legacy", ["skills/legacy/"]) is True


def test_is_excluded_no_match_returns_false():
    assert MOD.is_excluded("scripts/public.py", ["scripts/internal/"]) is False
    assert MOD.is_excluded("anything", []) is False


# ---- expect ----
def test_expect_appends_finding_for_missing_path(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "KIT_DIR", tmp_path)
    findings: list[str] = []
    MOD.expect(tmp_path / "skills" / "ghost" / "SKILL.md", findings)
    assert findings == ["missing: skills/ghost/SKILL.md"]


def test_expect_silent_for_existing_path(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "KIT_DIR", tmp_path)
    real = tmp_path / "present.txt"
    real.write_text("x", encoding="utf-8")
    findings: list[str] = []
    MOD.expect(real, findings)
    assert findings == []


def test_expect_treats_symlink_as_present(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "KIT_DIR", tmp_path)
    target = tmp_path / "dangling-target"  # 故意に存在しないターゲット
    link = tmp_path / "alias"
    link.symlink_to(target)
    findings: list[str] = []
    # is_symlink() が True なので exists() が False でも finding は出ない
    MOD.expect(link, findings)
    assert findings == []


# ---- check_bidirectional ----
def _make_kit(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "skills").mkdir()
    return tmp_path


def test_check_bidirectional_flags_unregistered_script(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "registered.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "orphan.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    manifest = {"scripts": {"lint": ["registered.py"]}}
    findings: list[str] = []
    MOD.check_bidirectional(manifest, findings)
    assert "bidirectional: scripts/orphan.py は manifest 未登録" in findings
    assert all("registered.py" not in f for f in findings)


def test_check_bidirectional_respects_excluded_paths(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "orphan.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    manifest = {"scripts": {}, "excluded_paths": ["scripts/orphan.py"]}
    findings: list[str] = []
    MOD.check_bidirectional(manifest, findings)
    assert findings == []


def test_check_bidirectional_flags_unregistered_skill(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "skills" / "known-skill").mkdir()
    (kit / "skills" / "stray-skill").mkdir()
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    manifest = {"scripts": {}, "skills": [{"name": "known-skill"}]}
    findings: list[str] = []
    MOD.check_bidirectional(manifest, findings)
    assert "bidirectional: skills/stray-skill は manifest 未登録" in findings
    assert all("known-skill" not in f for f in findings)


def test_check_bidirectional_lifecycle_and_bootstrap_register(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "install.sh").write_text("#!/bin/sh", encoding="utf-8")
    (kit / "scripts" / "boot.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    manifest = {
        "scripts": {},
        "lifecycle": ["install.sh"],
        "bootstrap": [{"source": "scripts/boot.py"}],
    }
    findings: list[str] = []
    MOD.check_bidirectional(manifest, findings)
    # lifecycle / bootstrap 登録済みなので未登録 finding は出ない
    assert findings == []


def test_check_bidirectional_ignores_script_subdirs(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "adapters").mkdir()
    (kit / "scripts" / "adapters" / "unlisted.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    manifest = {"scripts": {}}
    findings: list[str] = []
    MOD.check_bidirectional(manifest, findings)
    # adapters/ サブディレクトリ配下は走査対象外
    assert findings == []


# ---- check_yaml_spec_freshness ----
def _write_cache(kit: Path, ts: str) -> Path:
    cache = (
        kit
        / ".claude"
        / "skills"
        / "ref-yaml-spec-fetcher"
        / "references"
        / "yaml-spec-cache.md"
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(f"# cache\nlast_fetched: {ts}\n", encoding="utf-8")
    return cache


def test_yaml_spec_freshness_warns_when_stale(tmp_path, monkeypatch):
    # __file__.resolve().parents[1] が cache base なので scripts/ のひとつ上が KIT
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    fake_script = scripts_dir / "lint-manifest-contents.py"
    fake_script.write_text("# placeholder", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(fake_script))
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=99)).isoformat()
    _write_cache(tmp_path, old)
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert len(warnings) == 1
    assert "yaml-spec-cache.md" in warnings[0]
    assert "99 days old" in warnings[0]


def test_yaml_spec_freshness_silent_when_fresh(tmp_path, monkeypatch):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    fake_script = scripts_dir / "lint-manifest-contents.py"
    fake_script.write_text("# placeholder", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(fake_script))
    fresh = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    _write_cache(tmp_path, fresh)
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert warnings == []


def test_yaml_spec_freshness_silent_when_cache_absent(tmp_path, monkeypatch):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    fake_script = scripts_dir / "lint-manifest-contents.py"
    fake_script.write_text("# placeholder", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(fake_script))
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert warnings == []


def test_yaml_spec_freshness_ignores_unparsable_timestamp(tmp_path, monkeypatch):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    fake_script = scripts_dir / "lint-manifest-contents.py"
    fake_script.write_text("# placeholder", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(fake_script))
    _write_cache(tmp_path, "not-a-date")
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert warnings == []


# ---- main() via subprocess (real plugin: plugin.json branch) ----
def test_main_subprocess_ok_on_real_plugin():
    # 実 plugin は manifest.json 無し + plugin.json 有り => 検証成功で exit 0
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    assert "OK: plugin manifest contents valid" in res.stdout


def test_main_subprocess_fails_on_invalid_plugin_manifest(tmp_path):
    # plugin.json から required key を欠いた擬似 plugin を作りスクリプトをコピー実行
    fake_plugin = tmp_path / "fake-plugin"
    (fake_plugin / "scripts").mkdir(parents=True)
    (fake_plugin / ".claude-plugin").mkdir()
    (fake_plugin / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "x"}', encoding="utf-8"
    )  # version / description 欠落
    script_copy = fake_plugin / "scripts" / "lint-manifest-contents.py"
    script_copy.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(script_copy)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert "plugin.json missing required key: version" in res.stdout
    assert "plugin.json missing required key: description" in res.stdout


# ---- main() in-process against a crafted legacy manifest.json fixture ----
def _point_module_at(tmp_path: Path, monkeypatch) -> Path:
    """module の KIT_DIR / MANIFEST / PLUGIN_MANIFEST / SETTINGS_EXAMPLE を tmp_path 側へ向ける。

    legacy manifest.json 経路 (plugin.json が無いケース) を in-process で genuine に検証する。
    """
    kit = tmp_path
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    monkeypatch.setattr(MOD, "MANIFEST", kit / "manifest.json")
    monkeypatch.setattr(MOD, "PLUGIN_MANIFEST", kit / ".claude-plugin" / "plugin.json")
    monkeypatch.setattr(MOD, "SETTINGS_EXAMPLE", kit / "config" / "claude-settings-hooks.json.example")
    # check_yaml_spec_freshness が実 repo の cache を読まないよう __file__ も tmp 側へ
    (kit / "scripts").mkdir(exist_ok=True)
    fake_script = kit / "scripts" / "lint-manifest-contents.py"
    fake_script.write_text("# placeholder", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(fake_script))
    return kit


def test_main_legacy_manifest_ok(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / "skills" / "good-skill").mkdir(parents=True)
    (kit / "skills" / "good-skill" / "SKILL.md").write_text("# s", encoding="utf-8")
    (kit / "agents").mkdir()
    (kit / "agents" / "agent-a.md").write_text("# a", encoding="utf-8")
    (kit / "scripts" / "lint" / "lint-x.py").parent.mkdir(parents=True, exist_ok=True)
    (kit / "scripts" / "lint-x.py").write_text("# x", encoding="utf-8")
    (kit / "config").mkdir(exist_ok=True)
    (kit / "config" / "settings.json").write_text("{}", encoding="utf-8")
    manifest = {
        "skills": [{"name": "good-skill"}],
        "agents": [{"name": "agent-a", "path": ".claude/agents/agent-a.md"}],
        "scripts": {"lint": ["lint-x.py"]},
        "config": [{"source": "config/settings.json"}],
    }
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rc = MOD.main()
    assert rc == 0
    assert "OK: manifest contents match package files" in capsys.readouterr().out


def test_main_legacy_manifest_reports_missing_skill_and_bad_agent_target(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    # skill SKILL.md を作らない => missing finding
    # agent target が .claude/agents/ 配下でない => target finding
    (kit / "agents").mkdir()
    (kit / "agents" / "agent-a.md").write_text("# a", encoding="utf-8")
    manifest = {
        "skills": [{"name": "ghost-skill"}],
        "agents": [{"name": "agent-a", "path": "wrong/agent-a.md"}],
    }
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing: skills/ghost-skill/SKILL.md" in out
    assert "agent target must be under .claude/agents/: wrong/agent-a.md" in out


def test_main_legacy_manifest_settings_example_validation(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / "config").mkdir(exist_ok=True)
    # deny 空 + FileChanged / TaskCreated 欠落 の settings example
    (kit / "config" / "claude-settings-hooks.json.example").write_text(
        json.dumps({"permissions": {"deny": []}, "hooks": {}}), encoding="utf-8"
    )
    (kit / "manifest.json").write_text(json.dumps({}), encoding="utf-8")
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing permissions.deny" in out
    assert "missing FileChanged hook" in out
    assert "missing TaskCreated hook" in out


def test_main_legacy_manifest_bidirectional_flag(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    # 登録外スクリプトを置き --bidirectional で未登録検出
    (kit / "scripts" / "orphan.py").write_text("# x", encoding="utf-8")
    (kit / "manifest.json").write_text(json.dumps({"scripts": {}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py", "--bidirectional"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "bidirectional: scripts/orphan.py は manifest 未登録" in out
