"""assign-plugin-package-evaluator/scripts/validate-plugin-package.py の genuine 機能テスト。

PKG-002〜008 / PKG-014 の各 sub-check を実ファイルパスから importlib でロードし、tmp_path に
合格 fixture / 各違反 fixture を作って純関数を直接呼び、findings の内容を assert する。
さらに main を subprocess (sys.executable) で起動し、exit code / JSON 出力 / 引数エラー
(--check 不正, plugin 不在) を検証する。network/keychain は一切叩かない。

実 repo の plugins は一切書き換えず、全 fixture は tmp_path 配下に構築する。
"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins" / "harness-creator" / "skills" / "assign-plugin-package-evaluator"
    / "scripts" / "validate-plugin-package.py"
)

SPEC = importlib.util.spec_from_file_location("validate_plugin_package_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

def _plugin(base: Path, name: str = "demo") -> Path:
    """tmp_path/<name> を plugin ルートとして返す (.claude-plugin は呼び出し側で作成)。"""
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_plugin_json(plugin_dir: Path, data: dict | None) -> None:
    cp = plugin_dir / ".claude-plugin"
    cp.mkdir(parents=True, exist_ok=True)
    if data is None:
        # 壊れた JSON を書く
        (cp / "plugin.json").write_text("{not json", encoding="utf-8")
    else:
        (cp / "plugin.json").write_text(json.dumps(data), encoding="utf-8")


def _write_package_contract(plugin_dir: Path, data: dict | None = None) -> None:
    """references/package-contract.json を書く (PKG-002 の contract 側必須ファイル)。"""
    refs = plugin_dir / "references"
    refs.mkdir(parents=True, exist_ok=True)
    if data is None:
        data = {"package_mode": "plugin", "entry_points": {}}
    (refs / "package-contract.json").write_text(json.dumps(data), encoding="utf-8")


def _write_skill(plugin_dir: Path, name: str, frontmatter: str | None,
                 body: str = "本文") -> Path:
    sk = plugin_dir / "skills" / name
    sk.mkdir(parents=True, exist_ok=True)
    md = sk / "SKILL.md"
    if frontmatter is None:
        md.write_text(body, encoding="utf-8")
    else:
        md.write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")
    return md


def _full_required_fm() -> str:
    return (
        "name: demo-skill\n"
        "description: a demo\n"
        "kind: run\n"
        "responsibility_refs:\n  - r1\n"
        "schema_refs:\n  - s1\n"
        "manifest: m1"
    )


# ============================================================================
# now_iso / make_finding (純関数)
# ============================================================================

def test_now_iso_format():
    s = MOD.now_iso()
    # 2026-06-24T01:02:03Z 形式
    assert s.endswith("Z")
    assert "T" in s
    assert len(s) == 20


def test_make_finding_id_and_fields():
    f = MOD.make_finding("PKG-004", 7, "loc/x", "evi", severity="P1",
                         suggested_fix="fix it", auto_fixable=True)
    assert f["id"] == "F-PKG004-007"
    assert f["pkg_id"] == "PKG-004"
    assert f["severity"] == "P1"
    assert f["location"] == "loc/x"
    assert f["evidence"] == "evi"
    assert f["suggested_fix"] == "fix it"
    assert f["auto_fixable"] is True


def test_make_finding_defaults():
    f = MOD.make_finding("PKG-002", 1, "l", "e")
    assert f["severity"] == "P0"
    assert f["auto_fixable"] is False
    assert f["suggested_fix"] == ""


# ============================================================================
# parse_frontmatter
# ============================================================================

def test_parse_frontmatter_scalar_and_list():
    text = "---\nname: foo\nkind: run\nrefs:\n  - a\n  - b\n---\nbody"
    fm = MOD.parse_frontmatter(text)
    assert fm["name"] == "foo"
    assert fm["kind"] == "run"
    assert fm["refs"] == ["a", "b"]


def test_parse_frontmatter_no_opening_fence_returns_none():
    assert MOD.parse_frontmatter("no frontmatter here") is None


def test_parse_frontmatter_unterminated_returns_none():
    assert MOD.parse_frontmatter("---\nname: foo\nno closing fence") is None


def test_parse_frontmatter_dangling_list_item_ignored():
    # current_key が無い状態の "- x" は無視される
    text = "---\n- orphan\nname: foo\n---\nb"
    fm = MOD.parse_frontmatter(text)
    assert fm == {"name": "foo"}


# ============================================================================
# load_plugin_json / get_package_mode
# ============================================================================

def test_load_plugin_json_ok(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, {"name": "x", "package_mode": "plugin"})
    data = MOD.load_plugin_json(p)
    assert data["name"] == "x"


def test_load_plugin_json_missing_returns_none(tmp_path):
    p = _plugin(tmp_path)
    assert MOD.load_plugin_json(p) is None


def test_load_plugin_json_broken_returns_none(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, None)
    assert MOD.load_plugin_json(p) is None


def test_get_package_mode_default_skill_only(tmp_path):
    p = _plugin(tmp_path)
    assert MOD.get_package_mode(p) == "skill-only"


def test_get_package_mode_from_json(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, {"name": "x", "package_mode": "plugin"})
    assert MOD.get_package_mode(p) == "plugin"


# ============================================================================
# check_pkg_002 : plugin.json 必須キー
# ============================================================================

def test_pkg_002_missing_plugin_json(tmp_path):
    p = _plugin(tmp_path)
    fs = MOD.check_pkg_002(p)
    assert len(fs) == 1
    assert "plugin.json が存在しない" in fs[0]["evidence"]


def test_pkg_002_all_keys_present_no_findings(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, {k: "v" for k in MOD.PLUGIN_JSON_REQUIRED})
    _write_package_contract(p, {k: "v" for k in MOD.PACKAGE_CONTRACT_REQUIRED})
    assert MOD.check_pkg_002(p) == []


def test_pkg_002_missing_some_keys(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, {"name": "x", "version": "1"})
    _write_package_contract(p, {})
    fs = MOD.check_pkg_002(p)
    evid = {f["evidence"] for f in fs}
    # plugin.json 側 description / contract 側 package_mode + entry_points が欠落
    assert any("package_mode" in e for e in evid)
    assert any("entry_points" in e for e in evid)
    assert any("description" in e for e in evid)
    assert len(fs) == 3


def test_pkg_002_missing_package_contract(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, {k: "v" for k in MOD.PLUGIN_JSON_REQUIRED})
    fs = MOD.check_pkg_002(p)
    assert len(fs) == 1
    assert "package-contract.json" in fs[0]["evidence"]


def test_pkg_002_accepts_scoped_dependencies_within_allow_list(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, {k: "v" for k in MOD.PLUGIN_JSON_REQUIRED})
    _write_package_contract(p, {
        "package_mode": "bundle",
        "entry_points": {"skills": ["run-a", "run-b"]},
        "depends_on": ["dependency-a"],
        "skill_dependencies": {"run-a": ["dependency-a"], "run-b": []},
    })
    assert MOD.check_pkg_002(p) == []


def test_pkg_002_rejects_invalid_scoped_dependency_projection(tmp_path):
    p = _plugin(tmp_path)
    _write_plugin_json(p, {k: "v" for k in MOD.PLUGIN_JSON_REQUIRED})
    _write_package_contract(p, {
        "package_mode": "bundle",
        "entry_points": {"skills": ["run-a"]},
        "depends_on": ["dependency-a"],
        "skill_dependencies": {
            "run-missing": ["dependency-a"],
            "run-a": ["dependency-b", "dependency-b"],
        },
    })
    evidence = [item["evidence"] for item in MOD.check_pkg_002(p)]
    assert any("entry_points.skills 未宣言" in item for item in evidence)
    assert any("重複" in item for item in evidence)
    assert any("depends_on 外" in item for item in evidence)


# ============================================================================
# check_pkg_003 : skill/agent 名前衝突 (実体 vs symlink)
# ============================================================================

def test_pkg_003_no_collision(tmp_path):
    p = _plugin(tmp_path, "demo")
    _write_plugin_json(p, {"name": "demo"})
    _write_skill(p, "uniq-skill", _full_required_fm())
    assert MOD.check_pkg_003(p) == []


def test_pkg_003_skill_name_collision(tmp_path):
    a = _plugin(tmp_path, "demo")
    b = _plugin(tmp_path, "other")
    _write_plugin_json(a, {"name": "demo"})
    _write_plugin_json(b, {"name": "other"})
    _write_skill(a, "shared", _full_required_fm())
    _write_skill(b, "shared", _full_required_fm())
    fs = MOD.check_pkg_003(a)
    assert len(fs) == 1
    assert "shared" in fs[0]["evidence"]
    assert "衝突" in fs[0]["evidence"]


def test_pkg_003_symlink_not_owner(tmp_path):
    a = _plugin(tmp_path, "demo")
    b = _plugin(tmp_path, "other")
    _write_plugin_json(a, {"name": "demo"})
    _write_plugin_json(b, {"name": "other"})
    real = _write_skill(a, "shared", _full_required_fm())
    # b は a の skill ディレクトリへの symlink (共有配備) -> 所有者カウント対象外
    (b / "skills").mkdir(parents=True, exist_ok=True)
    os.symlink(real.parent, b / "skills" / "shared")
    # demo (実体所有) のみ owner -> 衝突なし
    assert MOD.check_pkg_003(a) == []


def test_pkg_003_agent_name_collision(tmp_path):
    a = _plugin(tmp_path, "demo")
    b = _plugin(tmp_path, "other")
    _write_plugin_json(a, {"name": "demo"})
    _write_plugin_json(b, {"name": "other"})
    for plug in (a, b):
        (plug / "agents").mkdir(parents=True, exist_ok=True)
        (plug / "agents" / "judge.md").write_text("agent", encoding="utf-8")
    fs = MOD.check_pkg_003(a)
    assert len(fs) == 1
    assert "agent" in fs[0]["evidence"]
    assert "judge" in fs[0]["evidence"]


def test_pkg_003_agent_symlink_not_owner(tmp_path):
    a = _plugin(tmp_path, "demo")
    b = _plugin(tmp_path, "other")
    _write_plugin_json(a, {"name": "demo"})
    _write_plugin_json(b, {"name": "other"})
    (a / "agents").mkdir(parents=True)
    real_agent = a / "agents" / "judge.md"
    real_agent.write_text("agent", encoding="utf-8")
    (b / "agents").mkdir(parents=True)
    # b は a の agent ファイルへの symlink -> 所有者カウント対象外 (line 132-133)
    os.symlink(real_agent, b / "agents" / "judge.md")
    assert MOD.check_pkg_003(a) == []


def test_pkg_003_ignores_dirs_without_manifest(tmp_path):
    # plugins_root に .claude-plugin を持たないディレクトリがあると continue (line 121-122)
    a = _plugin(tmp_path, "demo")
    _write_plugin_json(a, {"name": "demo"})
    _write_skill(a, "uniq", _full_required_fm())
    # マニフェスト無しディレクトリ + 通常ファイルを兄弟に配置
    (tmp_path / "nomanifest").mkdir()
    (tmp_path / "nomanifest" / "skills").mkdir()
    (tmp_path / "loose.txt").write_text("x", encoding="utf-8")
    assert MOD.check_pkg_003(a) == []


# ============================================================================
# check_pkg_004 : SKILL.md frontmatter 必須/推奨キー
# ============================================================================

def test_pkg_004_no_skills_dir(tmp_path):
    p = _plugin(tmp_path)
    assert MOD.check_pkg_004(p) == []


def test_pkg_004_full_frontmatter_clean(tmp_path):
    p = _plugin(tmp_path)
    _write_skill(p, "sk", _full_required_fm())
    assert MOD.check_pkg_004(p) == []


def test_pkg_004_reasoned_manifest_exemption_is_mechanical_alternative(tmp_path):
    p = _plugin(tmp_path)
    fm = (
        "name: demo-skill\n"
        "description: a demo\n"
        "kind: run\n"
        "responsibility_refs: [prompts/R1.md]\n"
        "schema_refs: [schemas/output.schema.json]\n"
        "completeness_exempt:\n"
        "  - \"manifest: inline goal loop is the runtime SSOT\""
    )
    _write_skill(p, "sk", fm)
    assert MOD.check_pkg_004(p) == []


def test_pkg_004_empty_values_and_unreasoned_exemption_fail(tmp_path):
    p = _plugin(tmp_path)
    fm = (
        "name: demo-skill\n"
        "description: a demo\n"
        "kind: run\n"
        "responsibility_refs: []\n"
        "schema_refs: \"\"\n"
        "manifest: \"\"\n"
        "completeness_exempt:\n"
        "  - \"manifest:\""
    )
    _write_skill(p, "sk", fm)
    fs = MOD.check_pkg_004(p)
    evid = {f["evidence"] for f in fs}
    assert any("responsibility_refs" in e for e in evid)
    assert any("schema_refs" in e for e in evid)
    assert any("manifest" in e for e in evid)


def test_pkg_004_no_frontmatter(tmp_path):
    p = _plugin(tmp_path)
    _write_skill(p, "sk", None)
    fs = MOD.check_pkg_004(p)
    assert len(fs) == 1
    assert "frontmatter が解析できない" in fs[0]["evidence"]


def test_pkg_004_missing_required_and_recommended(tmp_path):
    p = _plugin(tmp_path)
    # name のみ -> description/kind が必須欠落、推奨 3 つも欠落
    _write_skill(p, "sk", "name: only")
    fs = MOD.check_pkg_004(p)
    evid = [f["evidence"] for f in fs]
    assert any("必須キー欠落: description" in e for e in evid)
    assert any("必須キー欠落: kind" in e for e in evid)
    # 推奨キーは P1
    p1 = [f for f in fs if f["severity"] == "P1"]
    assert len(p1) == 3


# ============================================================================
# check_pkg_005 : subagent_refs 宣言と実体の整合
# ============================================================================

def test_pkg_005_no_agents_dir(tmp_path):
    p = _plugin(tmp_path)
    _write_skill(p, "sk", _full_required_fm())
    assert MOD.check_pkg_005(p) == []


def test_pkg_005_declared_agent_missing(tmp_path):
    p = _plugin(tmp_path)
    (p / "agents").mkdir(parents=True)
    (p / "agents" / "present.md").write_text("a", encoding="utf-8")
    fm = _full_required_fm() + "\nsubagent_refs:\n  - present\n  - ghost"
    _write_skill(p, "sk", fm)
    fs = MOD.check_pkg_005(p)
    assert len(fs) == 1
    assert "ghost" in fs[0]["evidence"]


def test_pkg_005_all_declared_present(tmp_path):
    p = _plugin(tmp_path)
    (p / "agents").mkdir(parents=True)
    (p / "agents" / "judge.md").write_text("a", encoding="utf-8")
    fm = _full_required_fm() + "\nsubagent_refs:\n  - judge"
    _write_skill(p, "sk", fm)
    assert MOD.check_pkg_005(p) == []


# ============================================================================
# check_pkg_006 : hook 実体と settings/plugin.json 登録の整合
# ============================================================================

def test_pkg_006_no_hooks_dir(tmp_path):
    p = _plugin(tmp_path)
    assert MOD.check_pkg_006(p) == []


def test_pkg_006_unregistered_hook(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "orphan.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    fs = MOD.check_pkg_006(p)
    assert len(fs) == 1
    assert "orphan.py" in fs[0]["suggested_fix"]


def test_pkg_006_registered_via_plugin_json_hooks(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "guard.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    _write_plugin_json(p, {
        "name": "demo",
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"}]}
            ]
        },
    })
    assert MOD.check_pkg_006(p) == []


def test_pkg_006_registered_via_entry_points(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "guard.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    _write_plugin_json(p, {
        "name": "demo",
        "entry_points": {"hooks": ["hooks/guard.py"]},
    })
    assert MOD.check_pkg_006(p) == []


def test_pkg_006_registered_via_package_contract_sidecar(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "guard.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    _write_plugin_json(p, {
        "name": "demo",
        "version": "1.0.0",
        "description": "native manifest without harness-only keys",
    })
    _write_package_contract(p, {
        "package_mode": "bundle",
        "entry_points": {"hooks": ["guard"]},
        "distribution": {"distributable": False},
        "pkg_checks": {},
    })

    assert MOD.check_pkg_006(p) == []


def test_pkg_006_registered_via_settings(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "guard.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (p / "settings").mkdir(parents=True)
    (p / "settings" / "s.json").write_text(json.dumps({
        "hooks": {"PreToolUse": [{"command": "guard.py"}]}
    }), encoding="utf-8")
    assert MOD.check_pkg_006(p) == []


def test_pkg_006_plugin_json_broken_json(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "guard.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    _write_plugin_json(p, None)  # broken JSON -> data={} -> 未登録扱い
    fs = MOD.check_pkg_006(p)
    assert len(fs) == 1


def test_pkg_006_settings_broken_json_skipped(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "guard.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (p / "settings").mkdir(parents=True)
    (p / "settings" / "bad.json").write_text("{broken", encoding="utf-8")
    # settings は壊れていて skip、registered 空 -> 未登録 finding
    fs = MOD.check_pkg_006(p)
    assert len(fs) == 1


def test_pkg_006_invalid_shlex_command_falls_back_to_split(tmp_path):
    p = _plugin(tmp_path)
    (p / "hooks").mkdir(parents=True)
    (p / "hooks" / "guard.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    # 閉じない引用符で shlex.split が ValueError -> .split() フォールバック
    _write_plugin_json(p, {
        "name": "demo",
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": "python3 'unclosed /hooks/guard.py"}]}
            ]
        },
    })
    assert MOD.check_pkg_006(p) == []


# ============================================================================
# check_pkg_007 : script shebang / +x
# ============================================================================

def test_pkg_007_no_scripts_dir(tmp_path):
    p = _plugin(tmp_path)
    assert MOD.check_pkg_007(p) == []


def test_pkg_007_missing_shebang(tmp_path):
    p = _plugin(tmp_path)
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "noshebang.py").write_text("print('hi')\n", encoding="utf-8")
    fs = MOD.check_pkg_007(p)
    assert any("shebang 欠落" in f["evidence"] for f in fs)


def test_pkg_007_shebang_but_not_executable(tmp_path):
    p = _plugin(tmp_path)
    (p / "scripts").mkdir(parents=True)
    sc = p / "scripts" / "ok.py"
    sc.write_text("#!/usr/bin/env python3\nprint('hi')\n", encoding="utf-8")
    sc.chmod(0o644)  # 実行ビットなし
    fs = MOD.check_pkg_007(p)
    assert any("実行可能ビットなし" in f["evidence"] for f in fs)
    assert any(f["auto_fixable"] for f in fs)


def test_pkg_007_shebang_and_executable_clean(tmp_path):
    p = _plugin(tmp_path)
    (p / "scripts").mkdir(parents=True)
    sc = p / "scripts" / "ok.py"
    sc.write_text("#!/usr/bin/env python3\nprint('hi')\n", encoding="utf-8")
    sc.chmod(sc.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert MOD.check_pkg_007(p) == []


def test_pkg_007_non_script_files_ignored(tmp_path):
    p = _plugin(tmp_path)
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "data.txt").write_text("not a script", encoding="utf-8")
    (p / "scripts" / "subdir").mkdir()  # ディレクトリは is_file=False で無視
    assert MOD.check_pkg_007(p) == []


# ============================================================================
# check_pkg_008 : settings/*.json の $schema / JSON 妥当性
# ============================================================================

def test_pkg_008_no_settings_dir(tmp_path):
    p = _plugin(tmp_path)
    assert MOD.check_pkg_008(p) == []


def test_pkg_008_missing_schema(tmp_path):
    p = _plugin(tmp_path)
    (p / "settings").mkdir(parents=True)
    (p / "settings" / "s.json").write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    fs = MOD.check_pkg_008(p)
    assert len(fs) == 1
    assert "$schema" in fs[0]["evidence"]
    assert fs[0]["severity"] == "P1"


def test_pkg_008_has_schema_clean(tmp_path):
    p = _plugin(tmp_path)
    (p / "settings").mkdir(parents=True)
    (p / "settings" / "s.json").write_text(
        json.dumps({"$schema": "x", "hooks": {}}), encoding="utf-8")
    assert MOD.check_pkg_008(p) == []


def test_pkg_008_broken_json(tmp_path):
    p = _plugin(tmp_path)
    (p / "settings").mkdir(parents=True)
    (p / "settings" / "bad.json").write_text("{broken", encoding="utf-8")
    fs = MOD.check_pkg_008(p)
    assert len(fs) == 1
    assert "JSON 解析エラー" in fs[0]["evidence"]


# ============================================================================
# check_pkg_014 : kind/combinator runtime contract
# ============================================================================

def _runtime_fm(*, kind: str = "run", combinators: str = "") -> str:
    extra = f"\ncombinators: {combinators}" if combinators else ""
    return _full_required_fm() + extra


def test_pkg_014_plain_run_without_optional_combinator_is_clean(tmp_path):
    p = _plugin(tmp_path)
    _write_skill(p, "run-demo", _runtime_fm(), body="# body")
    assert MOD.check_pkg_014(p) == []


def test_pkg_014_goal_seek_and_feedback_wiring_clean(tmp_path):
    p = _plugin(tmp_path)
    fm = _runtime_fm(combinators="[with-goal-seek, with-feedback-contract]") + (
        "\ngoal_seek:\n"
        "  engine: inline\n"
        "  fork: subagent\n"
        "  max_loops: 5\n"
        "feedback_contract:\n"
        "  max_iterations: 3\n"
        "  criteria:\n"
        "    - id: IN1\n"
        "      loop_scope: inner\n"
        "    - id: OUT1\n"
        "      loop_scope: outer"
    )
    _write_skill(p, "run-demo", fm, body="## ゴールシーク実行\nloop and stop")
    assert MOD.check_pkg_014(p) == []


def test_pkg_014_declared_goal_seek_requires_runtime_mapping_and_body(tmp_path):
    p = _plugin(tmp_path)
    _write_skill(p, "run-demo", _runtime_fm(combinators="[with-goal-seek]"))
    fs = MOD.check_pkg_014(p)
    evid = {f["evidence"] for f in fs}
    assert any("goal_seek mapping" in e for e in evid)
    assert any("ゴールシーク実行配線" in e for e in evid)


def test_pkg_014_feedback_contract_requires_inner_and_outer(tmp_path):
    p = _plugin(tmp_path)
    fm = _runtime_fm(combinators="[with-feedback-contract]") + (
        "\nfeedback_contract:\n"
        "  max_iterations: 3\n"
        "  criteria:\n"
        "    - id: IN1\n"
        "      loop_scope: inner"
    )
    _write_skill(p, "run-demo", fm)
    fs = MOD.check_pkg_014(p)
    assert any("loop_scope=outer" in f["evidence"] for f in fs)


def test_pkg_014_runtime_mapping_without_combinator_fails(tmp_path):
    p = _plugin(tmp_path)
    fm = _runtime_fm() + "\ngoal_seek:\n  engine: inline\n  fork: inline\n  max_loops: 1"
    _write_skill(p, "run-demo", fm, body="## ゴールシーク実行")
    fs = MOD.check_pkg_014(p)
    assert any("with-goal-seek combinator が未宣言" in f["evidence"] for f in fs)


def test_pkg_014_feedback_skip_reason_is_explicit_runtime_exemption(tmp_path):
    p = _plugin(tmp_path)
    fm = _runtime_fm(kind="assign") + (
        "\nfeedback_contract:\n"
        "  skip_reason: assign evaluator uses its rubric and fail-closed aggregate gate"
    )
    _write_skill(p, "assign-demo", fm)
    assert MOD.check_pkg_014(p) == []


def test_pkg_014_symlinked_compatibility_skill_is_source_owned(tmp_path):
    p = _plugin(tmp_path)
    (p / "skills").mkdir()
    source = tmp_path / "source-skill"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\n" + _runtime_fm() + "\nfeedback_contract:\n  max_iterations: 1\n---\n",
        encoding="utf-8",
    )
    os.symlink(source, p / "skills" / "run-shared")
    assert MOD.check_pkg_014(p) == []


def test_pkg_014_unknown_combinator_fails_closed(tmp_path):
    p = _plugin(tmp_path)
    _write_skill(p, "run-demo", _runtime_fm(combinators="[with-magic]"))
    fs = MOD.check_pkg_014(p)
    assert any("未定義 combinator" in f["evidence"] for f in fs)


# ============================================================================
# run_checks : package_mode と not_applicable 分岐
# ============================================================================

def test_run_checks_skill_only_na(tmp_path):
    p = _plugin(tmp_path, "demo")
    _write_plugin_json(p, {"name": "demo"})  # package_mode 無し -> skill-only
    result = MOD.run_checks(p, MOD.PKG_IDS)
    # skill-only では NA_FOR_SKILL_ONLY は not_applicable
    for pid in MOD.NA_FOR_SKILL_ONLY:
        assert result["pkg_checks"][pid]["status"] == "not_applicable"
        assert "skip_reason" in result["pkg_checks"][pid]
    # PKG-002/004 は実走
    assert result["pkg_checks"]["PKG-002"]["status"] in ("pass", "fail")
    assert result["verdict"]["total"] == 8
    assert result["verdict"]["not_applicable"] == 6


def test_run_checks_plugin_mode_runs_all(tmp_path):
    p = _plugin(tmp_path, "demo")
    _write_plugin_json(p, {
        "name": "demo", "version": "1", "package_mode": "plugin",
        "description": "d", "entry_points": {},
    })
    _write_skill(p, "sk", _full_required_fm())
    result = MOD.run_checks(p, MOD.PKG_IDS)
    # plugin mode では全 check が pass/fail (not_applicable は出ない)
    for pid in MOD.PKG_IDS:
        assert result["pkg_checks"][pid]["status"] in ("pass", "fail")
    assert result["package_mode"] == "plugin"
    assert result["target_plugin"] == "demo"
    assert "run_id" in result


def test_run_checks_single_id(tmp_path):
    p = _plugin(tmp_path, "demo")
    _write_plugin_json(p, {k: "v" for k in MOD.PLUGIN_JSON_REQUIRED})
    _write_package_contract(p)
    result = MOD.run_checks(p, ["PKG-002"])
    assert result["verdict"]["total"] == 1
    assert result["pkg_checks"]["PKG-002"]["status"] == "pass"


# ============================================================================
# main : subprocess で exit code / 出力 / 引数エラー
# ============================================================================

def _make_plugins_root(tmp_path, name="demo", mode="plugin") -> Path:
    root = tmp_path / "plugins"
    p = _plugin(root, name)
    pj = {"name": name, "version": "1", "description": "d", "entry_points": {}}
    if mode:
        pj["package_mode"] = mode
    _write_plugin_json(p, pj)
    _write_package_contract(p, {"package_mode": mode or "plugin", "entry_points": {}})
    return root


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=120, env=env,
    )


def test_main_plugin_not_found(tmp_path):
    root = _make_plugins_root(tmp_path)
    proc = _run_cli(["--plugin", "nope", "--plugins-root", str(root)])
    assert proc.returncode == 2
    assert "plugin not found" in proc.stderr


def test_main_unsupported_check(tmp_path):
    root = _make_plugins_root(tmp_path)
    proc = _run_cli(["--plugin", "demo", "--plugins-root", str(root),
                     "--check", "pkg-999"])
    assert proc.returncode == 2
    assert "unsupported --check value" in proc.stderr


def test_main_clean_plugin_exit0(tmp_path):
    """全 check pass する完全な plugin -> exit 0、JSON 出力。"""
    root = tmp_path / "plugins"
    p = _plugin(root, "demo")
    _write_plugin_json(p, {
        "name": "demo", "version": "1", "package_mode": "plugin",
        "description": "d", "entry_points": {},
    })
    _write_package_contract(p)
    _write_skill(p, "sk", _full_required_fm())
    proc = _run_cli(["--plugin", "demo", "--plugins-root", str(root)])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["target_plugin"] == "demo"
    assert out["verdict"]["fail"] == 0


def test_main_plugin_dir_exit0_without_plugins_root(tmp_path):
    """marketplace 単独 install では --plugin-dir だけで検査対象を解決する。"""
    p = _plugin(tmp_path / "anywhere" / "harness-creator", "demo")
    _write_plugin_json(p, {
        "name": "demo", "version": "1", "package_mode": "plugin",
        "description": "d", "entry_points": {},
    })
    _write_package_contract(p)
    _write_skill(p, "sk", _full_required_fm())
    proc = _run_cli(["--plugin-dir", str(p)])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["target_plugin"] == "demo"


def test_main_uses_claude_plugin_root_when_no_plugin_arg(tmp_path):
    p = _plugin(tmp_path / "marketplace-cache", "harness-creator")
    _write_plugin_json(p, {
        "name": "harness-creator", "version": "1", "package_mode": "plugin",
        "description": "d", "entry_points": {},
    })
    _write_package_contract(p)
    _write_skill(p, "sk", _full_required_fm())
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(p)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["target_plugin"] == "harness-creator"


def test_main_failing_plugin_exit1(tmp_path):
    """PKG-002 必須キー欠落 -> fail -> exit 1。"""
    root = tmp_path / "plugins"
    p = _plugin(root, "demo")
    # package_mode は plugin にして全 check 走らせるが必須キー欠落で fail
    _write_plugin_json(p, {"name": "demo", "package_mode": "plugin"})
    proc = _run_cli(["--plugin", "demo", "--plugins-root", str(root)])
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["verdict"]["fail"] >= 1


def test_main_check_single_normalization(tmp_path):
    """--check 002 (PKG- 接頭辞なし) -> PKG-002 へ正規化されて走る。"""
    root = _make_plugins_root(tmp_path)
    proc = _run_cli(["--plugin", "demo", "--plugins-root", str(root), "--check", "002"])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verdict"]["total"] == 1
    assert "PKG-002" in out["pkg_checks"]


def test_main_output_to_file(tmp_path):
    """--output <path> でファイルへ書き出す。"""
    root = _make_plugins_root(tmp_path)
    out_path = tmp_path / "out" / "result.json"
    proc = _run_cli(["--plugin", "demo", "--plugins-root", str(root),
                     "--output", str(out_path)])
    assert proc.returncode == 0, proc.stderr
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["target_plugin"] == "demo"
    # stdout には JSON は出ない (ファイル出力モード)
    assert proc.stdout.strip() == ""


# ============================================================================
# main : in-process (sys.argv monkeypatch) で main() 本体の行を直接カバー
# ============================================================================

def _argv(monkeypatch, args: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *args])


def test_main_inproc_plugin_not_found(tmp_path, monkeypatch, capsys):
    root = _make_plugins_root(tmp_path)
    _argv(monkeypatch, ["--plugin", "ghost", "--plugins-root", str(root)])
    rc = MOD.main()
    assert rc == 2
    assert "plugin not found" in capsys.readouterr().err


def test_main_inproc_unsupported_check(tmp_path, monkeypatch, capsys):
    root = _make_plugins_root(tmp_path)
    _argv(monkeypatch, ["--plugin", "demo", "--plugins-root", str(root),
                        "--check", "pkg-999"])
    rc = MOD.main()
    assert rc == 2
    assert "unsupported --check value" in capsys.readouterr().err


def test_main_inproc_all_clean_exit0(tmp_path, monkeypatch, capsys):
    root = tmp_path / "plugins"
    p = _plugin(root, "demo")
    _write_plugin_json(p, {
        "name": "demo", "version": "1", "package_mode": "plugin",
        "description": "d", "entry_points": {},
    })
    _write_package_contract(p)
    _write_skill(p, "sk", _full_required_fm())
    _argv(monkeypatch, ["--plugin", "demo", "--plugins-root", str(root)])
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["verdict"]["fail"] == 0


def test_main_inproc_failing_exit1(tmp_path, monkeypatch, capsys):
    root = tmp_path / "plugins"
    p = _plugin(root, "demo")
    _write_plugin_json(p, {"name": "demo", "package_mode": "plugin"})
    _argv(monkeypatch, ["--plugin", "demo", "--plugins-root", str(root)])
    rc = MOD.main()
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"]["fail"] >= 1


def test_main_inproc_check_all_branch(tmp_path, monkeypatch, capsys):
    """--check all -> PKG_IDS 全件 (line 379-380 の all 分岐)。"""
    root = _make_plugins_root(tmp_path)
    _argv(monkeypatch, ["--plugin", "demo", "--plugins-root", str(root),
                        "--check", "all"])
    rc = MOD.main()
    data = json.loads(capsys.readouterr().out)
    assert rc in (0, 1)
    assert data["verdict"]["total"] == 8


def test_main_inproc_bare_numeric_check_normalized(tmp_path, monkeypatch, capsys):
    """--check 002 (PKG- 接頭辞なし bare 数字) -> line 384 で PKG-002 へ正規化。"""
    root = _make_plugins_root(tmp_path)
    _argv(monkeypatch, ["--plugin", "demo", "--plugins-root", str(root),
                        "--check", "002"])
    rc = MOD.main()
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["verdict"]["total"] == 1
    assert "PKG-002" in data["pkg_checks"]


def test_main_inproc_prefixed_check_passthrough(tmp_path, monkeypatch, capsys):
    """--check pkg-003 -> upper で PKG-003、startswith True -> line 388 でそのまま採用。"""
    root = tmp_path / "plugins"
    p = _plugin(root, "demo")
    _write_plugin_json(p, {
        "name": "demo", "version": "1", "package_mode": "plugin",
        "description": "d", "entry_points": {},
    })
    _argv(monkeypatch, ["--plugin", "demo", "--plugins-root", str(root),
                        "--check", "pkg-003"])
    rc = MOD.main()
    data = json.loads(capsys.readouterr().out)
    assert rc in (0, 1)
    assert "PKG-003" in data["pkg_checks"]
    assert data["verdict"]["total"] == 1


def test_main_inproc_output_to_file(tmp_path, monkeypatch, capsys):
    root = _make_plugins_root(tmp_path)
    out_path = tmp_path / "deep" / "r.json"
    _argv(monkeypatch, ["--plugin", "demo", "--plugins-root", str(root),
                        "--output", str(out_path)])
    rc = MOD.main()
    assert rc == 0
    assert out_path.exists()
    assert capsys.readouterr().out.strip() == ""
