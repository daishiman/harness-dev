"""genuine 機能テスト (scripts2): skill-governance-lint/scripts/lint-manifest-contents.py

tests/scripts-root/ 及び tests/scripts-plugins/ の既存テストとは別ディレクトリ・別観点で、行カバレッジ 80%+ を狙う。

このスクリプトは module import 時に KIT_DIR 等を __file__ から解決し、main() が
それらの module-level 定数を読む。テストでは module の KIT_DIR / MANIFEST /
PLUGIN_MANIFEST / SETTINGS_EXAMPLE / __file__ を tmp_path 側へ monkeypatch し、
- plugin.json 経路 (manifest.json 無し)
- legacy manifest.json 経路 (skills/agents/scripts/config/bidirectional/settings)
- yaml-spec freshness 警告
を in-process で genuine に網羅する (subprocess でなく in-process なので coverage 計測可)。

純関数 (expect / load_excluded_paths / is_excluded / check_bidirectional /
check_yaml_spec_freshness) も実入力で直接呼ぶ。network / 外部 I/O は無い。
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
    spec = importlib.util.spec_from_file_location("lint_manifest_contents_s2", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _point_module_at(tmp_path: Path, monkeypatch) -> Path:
    """module-level の path 定数を tmp_path 側へ向け、repo を汚さず決定論にする。"""
    kit = tmp_path
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    monkeypatch.setattr(MOD, "MANIFEST", kit / "manifest.json")
    monkeypatch.setattr(MOD, "PLUGIN_MANIFEST", kit / ".claude-plugin" / "plugin.json")
    monkeypatch.setattr(
        MOD, "SETTINGS_EXAMPLE", kit / "config" / "claude-settings-hooks.json.example"
    )
    (kit / "scripts").mkdir(exist_ok=True)
    fake_script = kit / "scripts" / "lint-manifest-contents.py"
    fake_script.write_text("# placeholder", encoding="utf-8")
    # check_yaml_spec_freshness が実 repo の cache を読まないよう __file__ を tmp 側へ
    monkeypatch.setattr(MOD, "__file__", str(fake_script))
    return kit


# =========================================================================
# 純関数 expect
# =========================================================================
def test_expect_flags_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "KIT_DIR", tmp_path)
    findings: list[str] = []
    MOD.expect(tmp_path / "a" / "b.md", findings)
    assert findings == ["missing: a/b.md"]


def test_expect_silent_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "KIT_DIR", tmp_path)
    f = tmp_path / "present.txt"
    f.write_text("x", encoding="utf-8")
    findings: list[str] = []
    MOD.expect(f, findings)
    assert findings == []


def test_expect_silent_for_dangling_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "KIT_DIR", tmp_path)
    link = tmp_path / "alias"
    link.symlink_to(tmp_path / "no-such-target")
    findings: list[str] = []
    MOD.expect(link, findings)
    # is_symlink() True なので exists() False でも finding 無し
    assert findings == []


# =========================================================================
# 純関数 load_excluded_paths / is_excluded
# =========================================================================
def test_load_excluded_paths_present():
    assert MOD.load_excluded_paths({"excluded_paths": ["scripts/x.py"]}) == ["scripts/x.py"]


def test_load_excluded_paths_default_empty():
    assert MOD.load_excluded_paths({}) == []


def test_is_excluded_prefix_match():
    assert MOD.is_excluded("scripts/internal/h.py", ["scripts/internal/"]) is True


def test_is_excluded_no_match():
    assert MOD.is_excluded("scripts/pub.py", ["scripts/internal/"]) is False


def test_is_excluded_empty_list():
    assert MOD.is_excluded("anything", []) is False


# =========================================================================
# 純関数 check_bidirectional
# =========================================================================
def _make_kit(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "skills").mkdir(exist_ok=True)
    return tmp_path


def test_bidirectional_flags_unregistered_script(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "registered.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "orphan.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    MOD.check_bidirectional({"scripts": {"lint": ["registered.py"]}}, findings)
    assert "bidirectional: scripts/orphan.py は manifest 未登録" in findings
    assert all("registered.py" not in f for f in findings)


def test_bidirectional_excluded_path_suppresses(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "orphan.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    MOD.check_bidirectional(
        {"scripts": {}, "excluded_paths": ["scripts/orphan.py"]}, findings
    )
    assert findings == []


def test_bidirectional_flags_unregistered_skill(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "skills" / "known").mkdir()
    (kit / "skills" / "stray").mkdir()
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    MOD.check_bidirectional({"scripts": {}, "skills": [{"name": "known"}]}, findings)
    assert "bidirectional: skills/stray は manifest 未登録" in findings


def test_bidirectional_excluded_skill_dir_suppresses(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "skills" / "legacy-skill").mkdir()
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    # excluded_paths は trailing slash 付きの "skills/legacy-skill/" にマッチ
    MOD.check_bidirectional(
        {"scripts": {}, "skills": [], "excluded_paths": ["skills/legacy-skill/"]}, findings
    )
    assert findings == []


def test_bidirectional_skips_non_dir_in_skills(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    # skills/ 直下にファイル -> is_dir() False で continue
    (kit / "skills" / "README.md").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    MOD.check_bidirectional({"scripts": {}, "skills": []}, findings)
    assert findings == []


def test_bidirectional_skips_missing_skills_dir(tmp_path, monkeypatch):
    # skills/ ディレクトリそのものが無い -> skills_dir.exists() False 分岐
    kit = tmp_path
    (kit / "scripts").mkdir()
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    MOD.check_bidirectional({"scripts": {}}, findings)
    assert findings == []


def test_bidirectional_lifecycle_and_bootstrap_register(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "install.sh").write_text("#!/bin/sh", encoding="utf-8")
    (kit / "scripts" / "boot.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    MOD.check_bidirectional(
        {
            "scripts": {},
            "lifecycle": ["install.sh", {"not": "a-string"}],  # 非 str 要素も無視される
            "bootstrap": [{"source": "scripts/boot.py"}, {"no_source": True}, "skip-me"],
        },
        findings,
    )
    assert findings == []


def test_bidirectional_ignores_script_subdirs(tmp_path, monkeypatch):
    kit = _make_kit(tmp_path)
    (kit / "scripts" / "adapters").mkdir()
    (kit / "scripts" / "adapters" / "nested.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    findings: list[str] = []
    MOD.check_bidirectional({"scripts": {}}, findings)
    assert findings == []


# =========================================================================
# 純関数 check_yaml_spec_freshness
# =========================================================================
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


def _aim_freshness(tmp_path, monkeypatch) -> Path:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    fake = scripts_dir / "lint-manifest-contents.py"
    fake.write_text("# placeholder", encoding="utf-8")
    monkeypatch.setattr(MOD, "__file__", str(fake))
    return tmp_path


def test_freshness_warns_when_stale(tmp_path, monkeypatch):
    kit = _aim_freshness(tmp_path, monkeypatch)
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=99)).isoformat()
    _write_cache(kit, old)
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert len(warnings) == 1
    assert "99 days old" in warnings[0]


def test_freshness_silent_when_fresh(tmp_path, monkeypatch):
    kit = _aim_freshness(tmp_path, monkeypatch)
    fresh = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()
    _write_cache(kit, fresh)
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert warnings == []


def test_freshness_silent_when_cache_absent(tmp_path, monkeypatch):
    _aim_freshness(tmp_path, monkeypatch)
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert warnings == []


def test_freshness_ignores_unparsable_timestamp(tmp_path, monkeypatch):
    kit = _aim_freshness(tmp_path, monkeypatch)
    _write_cache(kit, "garbage-date")
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert warnings == []


def test_freshness_handles_cache_without_last_fetched(tmp_path, monkeypatch):
    kit = _aim_freshness(tmp_path, monkeypatch)
    cache = (
        kit / ".claude" / "skills" / "ref-yaml-spec-fetcher" / "references" / "yaml-spec-cache.md"
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("# cache\nno timestamp line here\n", encoding="utf-8")
    warnings: list[str] = []
    MOD.check_yaml_spec_freshness(warnings)
    assert warnings == []


# =========================================================================
# main() — plugin.json 経路 (manifest.json 無し)
# =========================================================================
def test_main_plugin_manifest_ok(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / ".claude-plugin").mkdir()
    (kit / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "p", "version": "1.0.0", "description": "d"}), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    assert rc == 0
    assert "OK: plugin manifest contents valid" in capsys.readouterr().out


def test_main_plugin_manifest_missing_keys(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / ".claude-plugin").mkdir()
    (kit / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "p"}), encoding="utf-8"  # version / description 欠落
    )
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "plugin.json missing required key: version" in out
    assert "plugin.json missing required key: description" in out


# =========================================================================
# main() — legacy manifest.json 経路
# =========================================================================
def test_main_legacy_ok_all_present(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / "skills" / "good-skill").mkdir(parents=True)
    (kit / "skills" / "good-skill" / "SKILL.md").write_text("# s", encoding="utf-8")
    (kit / "agents").mkdir()
    (kit / "agents" / "agent-a.md").write_text("# a", encoding="utf-8")
    (kit / "scripts" / "lint-x.py").write_text("# x", encoding="utf-8")
    # adapters グループ -> scripts/adapters/ 配下を検証する分岐
    (kit / "scripts" / "adapters").mkdir()
    (kit / "scripts" / "adapters" / "ad.py").write_text("# x", encoding="utf-8")
    (kit / "config").mkdir(exist_ok=True)
    (kit / "config" / "settings.json").write_text("{}", encoding="utf-8")
    manifest = {
        "skills": [{"name": "good-skill"}],
        "agents": [{"name": "agent-a", "path": ".claude/agents/agent-a.md"}],
        "scripts": {"lint": ["lint-x.py"], "adapters": ["ad.py"]},
        "config": [{"source": "config/settings.json"}],
    }
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    assert rc == 0
    assert "OK: manifest contents match package files" in capsys.readouterr().out


def test_main_legacy_agent_source_default_path(tmp_path, monkeypatch, capsys):
    # agent に source が無い -> agents/<name>.md がデフォルト。存在しないので missing
    kit = _point_module_at(tmp_path, monkeypatch)
    manifest = {"agents": [{"name": "ghost-agent"}]}
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing: agents/ghost-agent.md" in out


def test_main_legacy_missing_skill_and_bad_agent_target(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / "agents").mkdir()
    (kit / "agents" / "agent-a.md").write_text("# a", encoding="utf-8")
    manifest = {
        "skills": [{"name": "ghost-skill"}],
        "agents": [{"name": "agent-a", "path": "wrong/agent-a.md"}],
    }
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing: skills/ghost-skill/SKILL.md" in out
    assert "agent target must be under .claude/agents/: wrong/agent-a.md" in out


def test_main_legacy_missing_script_and_config(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    manifest = {
        "scripts": {"secrets": ["keychain.py"]},  # scripts/secrets/keychain.py 欠落
        "config": [{"source": "config/missing.json"}],  # 欠落
    }
    (kit / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing: scripts/secrets/keychain.py" in out
    assert "missing: config/missing.json" in out


def test_main_legacy_settings_example_validation(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / "config").mkdir(exist_ok=True)
    (kit / "config" / "claude-settings-hooks.json.example").write_text(
        json.dumps({"permissions": {"deny": []}, "hooks": {}}), encoding="utf-8"
    )
    (kit / "manifest.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing permissions.deny" in out
    assert "missing FileChanged hook" in out
    assert "missing TaskCreated hook" in out


def test_main_legacy_settings_example_valid(tmp_path, monkeypatch, capsys):
    # deny 非空 + FileChanged / TaskCreated 有り -> settings 由来の finding 無し
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / "config").mkdir(exist_ok=True)
    (kit / "config" / "claude-settings-hooks.json.example").write_text(
        json.dumps(
            {
                "permissions": {"deny": ["Bash(rm:*)"]},
                "hooks": {"FileChanged": [], "TaskCreated": []},
            }
        ),
        encoding="utf-8",
    )
    (kit / "manifest.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    assert rc == 0
    assert "OK: manifest contents match package files" in capsys.readouterr().out


def test_main_legacy_bidirectional_flag_detects_orphan(tmp_path, monkeypatch, capsys):
    kit = _point_module_at(tmp_path, monkeypatch)
    (kit / "scripts" / "orphan.py").write_text("# x", encoding="utf-8")
    (kit / "manifest.json").write_text(json.dumps({"scripts": {}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py", "--bidirectional"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "bidirectional: scripts/orphan.py は manifest 未登録" in out


def test_main_legacy_ok_emits_freshness_warning(tmp_path, monkeypatch, capsys):
    # 全ファイル整合 + stale cache -> exit 0 だが WARNING を stdout に出す分岐
    kit = _point_module_at(tmp_path, monkeypatch)
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=120)).isoformat()
    _write_cache(kit, old)
    (kit / "manifest.json").write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["lint-manifest-contents.py"])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARNING: yaml-spec-cache.md" in out
    assert "OK: manifest contents match package files" in out


# =========================================================================
# __main__ 経路 (sys.exit(main())) の genuine 起動を subprocess で確認
# =========================================================================
def test_dunder_main_entrypoint_real_plugin_via_subprocess():
    # 実 plugin は manifest.json 無し + plugin.json 有り -> exit 0
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "OK: plugin manifest contents valid" in proc.stdout
