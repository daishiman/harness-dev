"""genuine な機能テスト: skill-governance-automation/scripts/build-manifest-registration-plan.py

純関数 (registered_sets / infer_skill_category / infer_skill_role /
collect_proposals / apply_proposals / load_manifest / save_manifest) を実入力で
呼び実出力を assert する。collect_proposals は KIT_DIR 配下の実ファイルを走査する
ため module の KIT_DIR を tmp_path へ monkeypatch し repo を汚さず検証する。
main() は subprocess (sys.executable) で実行し returncode と JSON 出力を assert する。

network / keychain / Notion などの外部 I/O はこのスクリプトには存在しない。
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
    spec = importlib.util.spec_from_file_location("build_manifest_plan_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---- infer_skill_category ----
@pytest.mark.parametrize(
    "name,expected",
    [
        ("run-skill-create", "orchestrator"),
        ("run-build-skill", "generator"),
        ("run-skill-elicit", "generator"),
        ("run-skill-rename", "generator"),
        ("assign-skill-design-evaluator", "evaluator"),
        ("run-elegant-review", "evaluator"),
        ("run-skill-rubric-governance", "governance"),
        ("ref-output-routing", "reference"),
        ("run-goal-seek", "workflow"),
        ("totally-unknown", "reference"),
    ],
)
def test_infer_skill_category(name, expected):
    assert MOD.infer_skill_category(name) == expected


# ---- infer_skill_role ----
def test_infer_skill_role_is_todo_placeholder():
    role = MOD.infer_skill_role("foo-bar")
    assert "foo-bar" in role
    assert role.startswith("TODO")


# ---- registered_sets ----
def test_registered_sets_collects_skills_config_and_script_groups():
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


# ---- collect_proposals ----
def _seed_kit(tmp_path: Path) -> Path:
    (tmp_path / "skills").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "adapters").mkdir()
    (tmp_path / "config").mkdir()
    return tmp_path


def test_collect_proposals_detects_unregistered_skill_with_category(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    skill_dir = kit / "skills" / "run-build-thing"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# skill", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"skills": []})
    assert "skills" in proposals
    entry = proposals["skills"][0]
    assert entry["name"] == "run-build-thing"
    assert entry["category"] == "generator"
    assert entry["role"].startswith("TODO")


def test_collect_proposals_skips_registered_skill(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    skill_dir = kit / "skills" / "already-listed"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# skill", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({"skills": [{"name": "already-listed"}]})
    # 登録済みのみ => proposals は空 dict (filtered)
    assert proposals == {}


def test_collect_proposals_categorizes_scripts_by_prefix(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    (kit / "scripts" / "lint-foo.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "validate-bar.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "hook-baz.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "cross_platform_secret.py").write_text("# x", encoding="utf-8")
    (kit / "scripts" / "adapters" / "ad1.py").write_text("# x", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    # collect_proposals は reg["adapters"] を直接参照するため scripts グループの存在が前提。
    # adapters 群を持つ manifest を実入力として与える (= スクリプトの実契約)。
    proposals = MOD.collect_proposals({"scripts": {"adapters": []}})
    assert set(proposals["lint"]) == {"lint-foo.py", "validate-bar.py"}
    assert proposals["hooks"] == ["hook-baz.py"]
    assert proposals["cross_platform"] == ["cross_platform_secret.py"]
    assert proposals["adapters"] == ["ad1.py"]


def test_collect_proposals_config_modes(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    (kit / "config" / "plain.json").write_text("{}", encoding="utf-8")
    (kit / "config" / "governance-params.json").write_text("{}", encoding="utf-8")
    (kit / "config" / "claude-settings-hooks.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    proposals = MOD.collect_proposals({})
    by_source = {c["source"]: c for c in proposals["config"]}
    assert by_source["config/plain.json"]["mode"] == "symlink"
    assert by_source["config/plain.json"]["target"] == ".claude/config/plain.json"
    assert by_source["config/governance-params.json"]["mode"] == "copy"
    assert by_source["config/governance-params.json"]["target"] == "references/governance-params.json"
    assert by_source["config/claude-settings-hooks.json"]["mode"] == "copy"
    assert by_source["config/claude-settings-hooks.json"]["target"] == ".claude/claude-settings-hooks.json"


def test_collect_proposals_empty_when_all_registered(tmp_path, monkeypatch):
    kit = _seed_kit(tmp_path)
    monkeypatch.setattr(MOD, "KIT_DIR", kit)
    assert MOD.collect_proposals({}) == {}


# ---- apply_proposals ----
def test_apply_proposals_merges_into_manifest():
    manifest: dict = {}
    proposals = {
        "skills": [{"name": "new-skill", "role": "r", "category": "workflow"}],
        "adapters": ["a.py"],
        "lint": ["lint-x.py"],
        "config": [{"source": "config/c.json", "target": ".claude/config/c.json", "mode": "symlink"}],
    }
    out = MOD.apply_proposals(manifest, proposals)
    assert out["skills"] == [{"name": "new-skill", "role": "r", "category": "workflow"}]
    assert out["scripts"]["adapters"] == ["a.py"]
    assert out["scripts"]["lint"] == ["lint-x.py"]
    assert out["scripts"]["secrets"] == []  # 全 script グループは初期化される
    assert out["config"] == [
        {"source": "config/c.json", "target": ".claude/config/c.json", "mode": "symlink"}
    ]


def test_apply_proposals_extends_existing_lists():
    manifest = {"skills": [{"name": "existing"}], "scripts": {"lint": ["old.py"]}}
    out = MOD.apply_proposals(manifest, {"skills": [{"name": "added"}], "lint": ["new.py"]})
    assert [s["name"] for s in out["skills"]] == ["existing", "added"]
    assert out["scripts"]["lint"] == ["old.py", "new.py"]


# ---- load_manifest / save_manifest round trip ----
def test_load_and_save_manifest_round_trip(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    payload = {"skills": [{"name": "z"}], "日本語": "値"}
    monkeypatch.setattr(MOD, "MANIFEST", manifest_path)
    MOD.save_manifest(payload)
    written = manifest_path.read_text(encoding="utf-8")
    # ensure_ascii=False なので日本語がエスケープされず保存される
    assert "日本語" in written
    assert written.endswith("\n")
    assert MOD.load_manifest() == payload


# ---- main() via subprocess (real plugin: plugin.json branch) ----
def test_main_subprocess_ok_on_real_plugin():
    # 実 plugin は manifest.json 無し + plugin.json 有り => status ok / format plugin
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["status"] == "ok"
    assert out["format"] == "plugin"
    assert out["proposals"] == {}


def test_main_subprocess_help_exits_zero():
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "--apply" in res.stdout


def test_main_subprocess_invalid_plugin_manifest_reports_missing(tmp_path):
    fake_plugin = tmp_path / "fake-plugin"
    (fake_plugin / "scripts").mkdir(parents=True)
    (fake_plugin / ".claude-plugin").mkdir()
    (fake_plugin / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "x"}', encoding="utf-8"
    )  # version / description 欠落
    script_copy = fake_plugin / "scripts" / "build-manifest-registration-plan.py"
    script_copy.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(script_copy)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    out = json.loads(res.stdout)
    assert out["status"] == "invalid_plugin_manifest"
    assert set(out["missing"]) == {"version", "description"}


# ---- main() in-process against a crafted legacy manifest.json fixture ----
def _point_module_at_legacy(tmp_path: Path, monkeypatch) -> Path:
    """KIT_DIR / MANIFEST / PLUGIN_MANIFEST を tmp_path に向け legacy manifest 経路を実行する。"""
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


def test_main_legacy_no_proposals_returns_ok(tmp_path, monkeypatch, capsys):
    kit = _point_module_at_legacy(tmp_path, monkeypatch)
    (kit / "manifest.json").write_text(json.dumps({"scripts": {"adapters": []}}), encoding="utf-8")
    rc = MOD.main()
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["proposals"] == {}


def test_main_legacy_needs_confirmation_returns_1(tmp_path, monkeypatch, capsys):
    kit = _point_module_at_legacy(tmp_path, monkeypatch)
    skill = kit / "skills" / "run-build-new"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# s", encoding="utf-8")
    (kit / "manifest.json").write_text(json.dumps({"scripts": {"adapters": []}}), encoding="utf-8")
    rc = MOD.main()
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "needs_confirmation"
    assert out["proposals"]["skills"][0]["name"] == "run-build-new"


def test_main_legacy_apply_writes_manifest(tmp_path, monkeypatch, capsys):
    kit = _point_module_at_legacy(tmp_path, monkeypatch)
    skill = kit / "skills" / "run-build-new"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# s", encoding="utf-8")
    (kit / "manifest.json").write_text(json.dumps({"scripts": {"adapters": []}}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build-manifest-registration-plan.py", "--apply"])
    rc = MOD.main()
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "applied"
    # manifest.json が実際に更新され skill が登録される
    written = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    assert any(s["name"] == "run-build-new" for s in written["skills"])


def test_main_plugin_format_returns_ok(tmp_path, monkeypatch, capsys):
    # manifest.json 無し + 妥当な plugin.json => status ok / format plugin
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
    rc = MOD.main()
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["format"] == "plugin"


# ---- main() --plugin: 渡した plugin を調べる (run-skill-create Step 3 の経路) ----
def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _target_plugin(tmp_path: Path, plugin_json: dict) -> Path:
    target = tmp_path / "plugins" / "target-plugin"
    (target / ".claude-plugin").mkdir(parents=True)
    (target / ".claude-plugin" / "plugin.json").write_text(json.dumps(plugin_json), encoding="utf-8")
    return target


def test_main_without_plugin_inspects_own_plugin():
    # 省略時は今の動作のまま: script を置いた skill-governance-automation 自身を読む
    res = _run_cli()
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["name"] == "skill-governance-automation"
    assert Path(out["plugin_manifest"]) == SCRIPT.parents[1] / ".claude-plugin" / "plugin.json"


def test_main_plugin_option_reads_target_plugin_json(tmp_path):
    target = _target_plugin(tmp_path, {"name": "target-plugin", "version": "2.3.4", "description": "d"})
    res = _run_cli("--plugin", str(target))
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["status"] == "ok"
    assert out["format"] == "plugin"
    # 自分の plugin ではなく、渡した plugin の plugin.json を読んだ結果になっている
    assert out["name"] == "target-plugin"
    assert out["version"] == "2.3.4"
    assert Path(out["plugin_manifest"]) == target / ".claude-plugin" / "plugin.json"
    assert out["proposals"] == {}


def test_main_plugin_option_rejects_invalid_target_even_though_own_plugin_is_valid(tmp_path):
    # 自分の plugin.json は妥当なので、exit 1 になるのは対象を検査したときだけ
    target = _target_plugin(tmp_path, {"name": "target-plugin"})
    res = _run_cli("--plugin", str(target))
    assert res.returncode == 1
    out = json.loads(res.stdout)
    assert out["status"] == "invalid_plugin_manifest"
    assert set(out["missing"]) == {"version", "description"}
    assert Path(out["plugin_manifest"]) == target / ".claude-plugin" / "plugin.json"


@pytest.mark.parametrize("plugin_arg", ["plugins/<plugin>", "does-not-exist", ""])
def test_main_plugin_option_missing_target_fails_closed(tmp_path, plugin_arg):
    # 未展開の placeholder・存在しない dir・空文字は、自分の plugin へ戻って ok にしない
    res = subprocess.run([sys.executable, str(SCRIPT), "--plugin", plugin_arg],
                         capture_output=True, text=True, cwd=tmp_path)
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert out["status"] == "plugin_not_found"
    assert out["plugin"] == plugin_arg


def test_main_plugin_option_legacy_target_proposes_and_applies_to_target_only(tmp_path):
    target = tmp_path / "legacy-plugin"
    skill = target / "skills" / "run-build-new"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# s", encoding="utf-8")
    (target / "scripts" / "adapters").mkdir(parents=True)
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps({"scripts": {"adapters": []}}), encoding="utf-8")
    own_manifest = SCRIPT.parents[1] / "manifest.json"
    own_existed = own_manifest.exists()

    plan = _run_cli("--plugin", str(target))
    assert plan.returncode == 1
    out = json.loads(plan.stdout)
    assert out["status"] == "needs_confirmation"
    assert Path(out["manifest"]) == manifest_path
    assert [s["name"] for s in out["proposals"]["skills"]] == ["run-build-new"]

    applied = _run_cli("--plugin", str(target), "--apply")
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["status"] == "applied"
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [s["name"] for s in written["skills"]] == ["run-build-new"]
    # 書き込むのは対象の manifest.json だけで、script を置いた plugin には作らない
    assert own_manifest.exists() == own_existed
