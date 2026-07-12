"""genuine 機能テスト (scripts2): build-manifest-registration-plan.py

対象: plugins/skill-governance-automation/scripts/build-manifest-registration-plan.py

このスクリプトは network なし・純関数中心なので深くテストできる。
方針:
  - 純関数 (registered_sets / infer_skill_category / infer_skill_role /
    collect_proposals / apply_proposals / load_manifest / save_manifest) は
    import して実入力で assert。
  - collect_proposals は module の KIT_DIR を tmp_path へ monkeypatch し
    全 proposal 種別 (skills/adapters/secrets/migrate/cross_platform/lint/
    hooks/config) を網羅。governance/lint 重複除外・config mode 分岐も検証。
  - main() は (1) in-process で MANIFEST/PLUGIN_MANIFEST/KIT_DIR を monkeypatch し
    legacy / plugin / apply / invalid-plugin の全分岐, (2) subprocess で
    実 plugin (plugin.json 経路) と --help を検証。
  - エッジ: 空 manifest / 欠落 dir / 不正 plugin.json frontmatter。

tests/scripts-root/ 及び tests/scripts-plugins/ の同名テストとは別 module 名で読み込むため衝突しない。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-governance-automation"
    / "scripts"
    / "build-manifest-registration-plan.py"
)


def _load_module():
    # tests/scripts-root/ 及び tests/scripts-plugins/ 側と衝突しないよう scripts2 専用の module 名で読み込む
    spec = importlib.util.spec_from_file_location("bmrp_scripts2_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# --------------------------------------------------------------------------
# infer_skill_category — 全分岐
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name,expected",
    [
        ("run-skill-create", "orchestrator"),
        ("run-build-skill", "generator"),
        ("run-build-anything", "generator"),
        ("run-skill-elicit", "generator"),
        ("run-skill-rename", "generator"),
        ("assign-skill-design-evaluator", "evaluator"),
        ("assign-anything", "evaluator"),
        ("run-elegant-review", "evaluator"),
        ("run-skill-rubric-governance", "governance"),
        ("ref-output-routing", "reference"),
        ("ref-anything", "reference"),
        ("run-goal-seek", "workflow"),
        ("run-anything-else", "workflow"),
        ("totally-unknown", "reference"),
        ("", "reference"),
    ],
)
def test_infer_skill_category_branches(name, expected):
    assert MOD.infer_skill_category(name) == expected


def test_infer_skill_role_is_todo_placeholder():
    role = MOD.infer_skill_role("foo-bar")
    assert role.startswith("TODO")
    assert "foo-bar" in role


# --------------------------------------------------------------------------
# registered_sets
# --------------------------------------------------------------------------
def test_registered_sets_full():
    manifest = {
        "skills": [{"name": "s1"}, {"name": "s2"}],
        "config": [{"source": "config/a.json"}, {"source": "config/b.json"}],
        "scripts": {"adapters": ["x.py"], "lint": ["lint-a.py", "lint-b.py"]},
    }
    reg = MOD.registered_sets(manifest)
    assert reg["skills"] == {"s1", "s2"}
    assert reg["config"] == {"config/a.json", "config/b.json"}
    assert reg["adapters"] == {"x.py"}
    assert reg["lint"] == {"lint-a.py", "lint-b.py"}


def test_registered_sets_empty_manifest():
    reg = MOD.registered_sets({})
    assert reg["skills"] == set()
    assert reg["config"] == set()
    # scripts 群が無くても落ちない
    assert "adapters" not in reg


# --------------------------------------------------------------------------
# collect_proposals — 全 proposal 種別を網羅
# --------------------------------------------------------------------------
def _seed_kit(tmp_path: Path) -> Path:
    (tmp_path / "skills").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "adapters").mkdir()
    (tmp_path / "config").mkdir()
    return tmp_path


def test_collect_proposals_unregistered_skill(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    skill_dir = kit / "skills" / "run-build-thing"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# skill", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"skills": []})
    assert proposals["skills"][0] == {
        "name": "run-build-thing",
        "role": MOD.infer_skill_role("run-build-thing"),
        "category": "generator",
    }


def test_collect_proposals_skips_registered_skill(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    skill_dir = kit / "skills" / "already-listed"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# skill", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"skills": [{"name": "already-listed"}]})
    assert proposals == {}


def test_collect_proposals_script_categories(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    (kit / "scripts" / "lint-foo.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "validate-bar.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "hook-baz.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "cross_platform_secret.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "adapters" / "ad1.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"scripts": {"adapters": []}})
    assert set(proposals["lint"]) == {"lint-foo.py", "validate-bar.py"}
    assert proposals["hooks"] == ["hook-baz.py"]
    assert proposals["cross_platform"] == ["cross_platform_secret.py"]
    assert proposals["adapters"] == ["ad1.py"]


def test_collect_proposals_lint_hook_excluded_when_in_governance(tmp_path, monkeypatch):
    """lint-/hook- が governance グループに登録済みなら proposal から除外される。"""
    kit = _seed_kit(tmp_path)
    (kit / "scripts" / "lint-foo.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "hook-baz.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals(
        {"scripts": {"governance": ["lint-foo.py", "hook-baz.py"]}}
    )
    assert proposals == {}


def test_collect_proposals_lint_hook_excluded_when_in_own_group(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    (kit / "scripts" / "lint-foo.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "hook-baz.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals(
        {"scripts": {"lint": ["lint-foo.py"], "hooks": ["hook-baz.py"]}}
    )
    assert proposals == {}


def test_collect_proposals_adapters_skip_registered(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    (kit / "scripts" / "adapters" / "keep.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "adapters" / "drop.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"scripts": {"adapters": ["drop.py"]}})
    assert proposals["adapters"] == ["keep.py"]


def test_collect_proposals_secrets_and_migrate(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    secrets = kit / "scripts" / "secrets"
    secrets.mkdir()
    (secrets / "sec1.py").write_text("# x", encoding="utf-8")
    (secrets / "sec2.txt").write_text("x", encoding="utf-8")
    # __pycache__ ディレクトリは skip される
    (secrets / "__pycache__").mkdir()
    # sub-dir も skip される (is_dir)
    (secrets / "subdir").mkdir()
    migrate = kit / "scripts" / "migrate"
    migrate.mkdir()
    (migrate / "mig1.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals(
        {"scripts": {"secrets": [], "migrate": []}}
    )
    assert set(proposals["secrets"]) == {"sec1.py", "sec2.txt"}
    assert proposals["migrate"] == ["mig1.py"]


def test_collect_proposals_secrets_skip_registered(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    secrets = kit / "scripts" / "secrets"
    secrets.mkdir()
    (secrets / "known.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"scripts": {"secrets": ["known.py"]}})
    assert proposals == {}


def test_collect_proposals_config_modes(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    (kit / "config" / "plain.json").write_text("{}", encoding="utf-8")
    (kit / "config" / "governance-params.json").write_text("{}", encoding="utf-8")
    (kit / "config" / "claude-settings-hooks.json").write_text("{}", encoding="utf-8")
    # config 直下の dir は skip される (is_file false)
    (kit / "config" / "nested").mkdir()
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({})
    by_source = {c["source"]: c for c in proposals["config"]}
    assert by_source["config/plain.json"] == {
        "source": "config/plain.json",
        "target": ".claude/config/plain.json",
        "mode": "symlink",
    }
    assert by_source["config/governance-params.json"] == {
        "source": "config/governance-params.json",
        "target": "references/governance-params.json",
        "mode": "copy",
    }
    assert by_source["config/claude-settings-hooks.json"] == {
        "source": "config/claude-settings-hooks.json",
        "target": ".claude/claude-settings-hooks.json",
        "mode": "copy",
    }
    assert "config/nested" not in by_source


def test_collect_proposals_config_skip_registered(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    (kit / "config" / "plain.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"config": [{"source": "config/plain.json"}]})
    assert proposals == {}


def test_collect_proposals_empty_when_nothing(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    assert MOD.collect_proposals({}) == {}


def test_collect_proposals_missing_optional_dirs(tmp_path, monkeypatch):
    """secrets / migrate / config dir が存在しなくても落ちない (空 iterable 分岐)。"""
    kit = tmp_path
    (kit / "skills").mkdir()
    (kit / "scripts").mkdir()
    (kit / "scripts" / "adapters").mkdir()
    # secrets / migrate / config を作らない
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    assert MOD.collect_proposals({}) == {}


# --------------------------------------------------------------------------
# apply_proposals
# --------------------------------------------------------------------------
def test_apply_proposals_into_empty_manifest():
    proposals = {
        "skills": [{"name": "new-skill", "role": "r", "category": "workflow"}],
        "adapters": ["a.py"],
        "secrets": ["s.py"],
        "cross_platform": ["cross_platform_secret.py"],
        "migrate": ["m.py"],
        "lint": ["lint-x.py"],
        "hooks": ["hook-y.py"],
        "config": [{"source": "config/c.json", "target": ".claude/config/c.json", "mode": "symlink"}],
    }
    out = MOD.apply_proposals({}, proposals)
    assert out["skills"] == [{"name": "new-skill", "role": "r", "category": "workflow"}]
    for key in ("adapters", "secrets", "cross_platform", "migrate", "lint", "hooks"):
        assert out["scripts"][key] == proposals[key]
    assert out["config"] == proposals["config"]


def test_apply_proposals_extends_existing():
    manifest = {"skills": [{"name": "existing"}], "scripts": {"lint": ["old.py"]}}
    out = MOD.apply_proposals(manifest, {"skills": [{"name": "added"}], "lint": ["new.py"]})
    assert [s["name"] for s in out["skills"]] == ["existing", "added"]
    assert out["scripts"]["lint"] == ["old.py", "new.py"]
    # 未提案のグループも初期化される
    assert out["scripts"]["secrets"] == []


# --------------------------------------------------------------------------
# load_manifest / save_manifest round trip
# --------------------------------------------------------------------------
def test_load_save_round_trip(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    payload = {"skills": [{"name": "z"}], "日本語": "値"}
    monkeypatch.setattr(MOD, "MANIFEST", manifest_path)
    MOD.save_manifest(payload)
    written = manifest_path.read_text(encoding="utf-8")
    assert "日本語" in written  # ensure_ascii=False
    assert written.endswith("\n")
    assert MOD.load_manifest() == payload


# --------------------------------------------------------------------------
# main() — in-process 全分岐
# --------------------------------------------------------------------------
def _point_legacy(tmp_path: Path, monkeypatch) -> Path:
    kit = tmp_path
    (kit / "skills").mkdir(exist_ok=True)
    (kit / "scripts").mkdir(exist_ok=True)
    (kit / "scripts" / "adapters").mkdir(exist_ok=True)
    (kit / "config").mkdir(exist_ok=True)
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    monkeypatch.setattr(MOD, "MANIFEST", kit / "manifest.json")
    monkeypatch.setattr(MOD, "PLUGIN_MANIFEST", kit / ".claude-plugin" / "plugin.json")
    monkeypatch.setattr(sys, "argv", ["build-manifest-registration-plan.py"])
    return kit


def test_main_legacy_ok(tmp_path, monkeypatch, capsys):
    kit = _point_legacy(tmp_path, monkeypatch)
    (kit / "manifest.json").write_text(json.dumps({"scripts": {"adapters": []}}), encoding="utf-8")
    assert MOD.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["proposals"] == {}


def test_main_legacy_needs_confirmation(tmp_path, monkeypatch, capsys):
    kit = _point_legacy(tmp_path, monkeypatch)
    skill = kit / "skills" / "run-build-new"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# s", encoding="utf-8")
    (kit / "manifest.json").write_text(json.dumps({"scripts": {"adapters": []}}), encoding="utf-8")
    assert MOD.main() == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "needs_confirmation"
    assert out["proposals"]["skills"][0]["name"] == "run-build-new"


def test_main_legacy_apply(tmp_path, monkeypatch, capsys):
    kit = _point_legacy(tmp_path, monkeypatch)
    skill = kit / "skills" / "run-build-new"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# s", encoding="utf-8")
    (kit / "manifest.json").write_text(json.dumps({"scripts": {"adapters": []}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build-manifest-registration-plan.py", "--apply"])
    assert MOD.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "applied"
    written = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    assert any(s["name"] == "run-build-new" for s in written["skills"])


def test_main_plugin_format_ok(tmp_path, monkeypatch, capsys):
    kit = tmp_path
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    monkeypatch.setattr(MOD, "MANIFEST", kit / "manifest.json")  # 存在しない
    (kit / ".claude-plugin").mkdir()
    plugin_path = kit / ".claude-plugin" / "plugin.json"
    plugin_path.write_text(
        json.dumps({"name": "p", "version": "1.0.0", "description": "d"}), encoding="utf-8"
    )
    monkeypatch.setattr(MOD, "PLUGIN_MANIFEST", plugin_path)
    monkeypatch.setattr(sys, "argv", ["build-manifest-registration-plan.py"])
    assert MOD.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["format"] == "plugin"


def test_main_plugin_invalid_missing_fields(tmp_path, monkeypatch, capsys):
    kit = tmp_path
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    monkeypatch.setattr(MOD, "MANIFEST", kit / "manifest.json")  # 存在しない
    (kit / ".claude-plugin").mkdir()
    plugin_path = kit / ".claude-plugin" / "plugin.json"
    plugin_path.write_text(json.dumps({"name": "x"}), encoding="utf-8")  # version/description 欠落
    monkeypatch.setattr(MOD, "PLUGIN_MANIFEST", plugin_path)
    monkeypatch.setattr(sys, "argv", ["build-manifest-registration-plan.py"])
    assert MOD.main() == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "invalid_plugin_manifest"
    assert set(out["missing"]) == {"version", "description"}


def test_main_plugin_empty_string_field_is_missing(tmp_path, monkeypatch, capsys):
    """空文字フィールドは falsy なので missing 扱い (not plugin.get(key))。"""
    kit = tmp_path
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    monkeypatch.setattr(MOD, "MANIFEST", kit / "manifest.json")
    (kit / ".claude-plugin").mkdir()
    plugin_path = kit / ".claude-plugin" / "plugin.json"
    plugin_path.write_text(
        json.dumps({"name": "p", "version": "", "description": "d"}), encoding="utf-8"
    )
    monkeypatch.setattr(MOD, "PLUGIN_MANIFEST", plugin_path)
    monkeypatch.setattr(sys, "argv", ["build-manifest-registration-plan.py"])
    assert MOD.main() == 1
    out = json.loads(capsys.readouterr().out)
    assert out["missing"] == ["version"]


# --------------------------------------------------------------------------
# main() — subprocess (実 plugin 経路 / --help)
# --------------------------------------------------------------------------
def test_main_subprocess_real_plugin():
    res = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["status"] == "ok"
    assert out["format"] == "plugin"
    assert out["proposals"] == {}


def test_main_subprocess_help():
    res = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "--apply" in res.stdout
