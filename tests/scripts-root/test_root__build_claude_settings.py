"""scripts/build-claude-settings.py の genuine で網羅的な機能テスト (network 不要)。

このスクリプトは plugin-owned の settings 断片 (hooks / permissions / namespace) を
.claude/settings.json へマージするビルダ。tests/test_build_claude_settings.py が
subprocess 経由の INV 契約を担保しているのに対し、本ファイルは in-process で
main(argv) と純関数を直接呼び、各分岐 (PASS / 違反種別 / エッジ) を行カバレッジ込みで
網羅する (in-process なので --cov=scripts に直接計上される)。

外部 I/O は一切なし。tmp_path に最小 plugins/ ツリーと target を構築し、
main() は monkeypatch で cwd を tmp に向けて相対 default (plugins/.claude) を解決する。
実 .claude は書き換えない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-claude-settings.py"

SPEC = importlib.util.spec_from_file_location("build_claude_settings_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

def _plugin(plugins: Path, name: str, *, manifest_extra=None,
            hooks_files=None, permissions_file=None,
            skills=(), agents=(), commands=(), skip_manifest=False):
    """最小 plugin ツリーを作る。manifest_extra は plugin.json へマージ。"""
    pdir = plugins / name
    (pdir / ".claude-plugin").mkdir(parents=True)
    if not skip_manifest:
        manifest = {"name": name}
        if manifest_extra:
            manifest.update(manifest_extra)
        (pdir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
    for fname, payload in (hooks_files or {}).items():
        (pdir / "hooks").mkdir(exist_ok=True)
        (pdir / "hooks" / fname).write_text(json.dumps(payload), encoding="utf-8")
    if permissions_file is not None:
        (pdir / "settings").mkdir(exist_ok=True)
        (pdir / "settings" / "permissions.json").write_text(
            json.dumps(permissions_file), encoding="utf-8"
        )
    for s in skills:
        if isinstance(s, tuple):
            sname, fm_name = s
        else:
            sname, fm_name = s, None
        sd = pdir / "skills" / sname
        sd.mkdir(parents=True)
        body = "---\n"
        if fm_name:
            body += f"name: {fm_name}\n"
        body += "---\n# Skill\n"
        (sd / "SKILL.md").write_text(body, encoding="utf-8")
    for a in agents:
        (pdir / "agents").mkdir(exist_ok=True)
        (pdir / "agents" / a).write_text("agent\n", encoding="utf-8")
    for c in commands:
        (pdir / "commands").mkdir(exist_ok=True)
        (pdir / "commands" / c).write_text("cmd\n", encoding="utf-8")
    return pdir


def _hook(command, *, event="PreToolUse", matcher="Write|Edit"):
    return {event: [{"matcher": matcher, "hooks": [{"type": "command", "command": command}]}]}


def _run_main(monkeypatch, cwd: Path, *argv):
    """main(argv) を tmp cwd で in-process 駆動。relative default を tmp に閉じ込める。"""
    monkeypatch.chdir(cwd)
    return MOD.main(list(argv))


# --- parse_args / serialize / help -------------------------------------------

def test_parse_args_defaults():
    args = MOD.parse_args([])
    assert args.plugins_dir == "plugins"
    assert args.target == ".claude/settings.json"
    assert args.dry_run is False and args.check is False


def test_serialize_trailing_newline_and_unicode():
    out = MOD.serialize({"日本語": "値"})
    assert out.endswith("\n")
    assert "日本語" in out  # ensure_ascii=False


def test_help_matches_contract_usage():
    res = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                         text=True, capture_output=True)
    assert res.returncode == 0
    assert res.stdout.startswith("usage: build-claude-settings.py [-h]")
    assert "--print-user-section-hash" in res.stdout


# --- load_json_file / load_target -------------------------------------------

def test_load_json_file_invalid_json_raises_layout(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.load_json_file(p)


def test_load_json_file_unreadable_raises_layout(tmp_path):
    # 存在しないパス -> OSError -> LayoutError
    with pytest.raises(MOD.LayoutError):
        MOD.load_json_file(tmp_path / "absent.json")


def test_load_target_missing_returns_empty(tmp_path):
    assert MOD.load_target(tmp_path / "none.json") == {}


def test_load_target_directory_raises(tmp_path):
    d = tmp_path / "isdir"
    d.mkdir()
    with pytest.raises(MOD.LayoutError):
        MOD.load_target(d)


def test_load_target_root_not_object_raises(tmp_path):
    p = tmp_path / "arr.json"
    p.write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.load_target(p)


def test_load_target_valid_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    data = {"permissions": {"deny": ["X"], "ask": []}, "unknown": 1}
    p.write_text(MOD.serialize(data), encoding="utf-8")
    assert MOD.load_target(p) == data


# --- command_from_hook_entry edge cases -------------------------------------

def test_command_from_hook_entry_ok():
    entry = {"hooks": [{"type": "command", "command": "python3 a.py"}]}
    assert MOD.command_from_hook_entry(entry) == ["python3 a.py"]


def test_command_from_hook_entry_missing_hooks_array():
    with pytest.raises(MOD.LayoutError):
        MOD.command_from_hook_entry({"hooks": "nope"})


def test_command_from_hook_entry_non_dict_command_entry():
    with pytest.raises(MOD.LayoutError):
        MOD.command_from_hook_entry({"hooks": ["string"]})


def test_command_from_hook_entry_wrong_type():
    with pytest.raises(MOD.LayoutError):
        MOD.command_from_hook_entry({"hooks": [{"type": "shell", "command": "x"}]})


def test_command_from_hook_entry_empty_command():
    with pytest.raises(MOD.LayoutError):
        MOD.command_from_hook_entry({"hooks": [{"type": "command", "command": ""}]})


# --- normalize_hook_entries --------------------------------------------------

def test_normalize_hook_entries_ok():
    out = MOD.normalize_hook_entries(_hook("python3 a.py"), "plg")
    # 互換修復で managed source hook には provenance 用の source が付く (既定 "unknown")。
    assert out == [{"event": "PreToolUse", "matcher": "Write|Edit",
                    "command": "python3 a.py", "from_plugin": "plg", "source": "unknown"}]


def test_normalize_hook_entries_not_object():
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_hook_entries(["x"], "plg")


def test_normalize_hook_entries_unknown_event():
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_hook_entries({"NopeEvent": []}, "plg")


def test_normalize_hook_entries_event_not_array():
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_hook_entries({"Stop": {}}, "plg")


def test_normalize_hook_entries_entry_not_object():
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_hook_entries({"Stop": ["x"]}, "plg")


def test_normalize_hook_entries_matcher_not_string():
    bad = {"Stop": [{"matcher": 123, "hooks": [{"type": "command", "command": "x"}]}]}
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_hook_entries(bad, "plg")


def test_normalize_hook_entries_matcher_none_ok():
    ok = {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}
    out = MOD.normalize_hook_entries(ok, "plg")
    assert out[0]["matcher"] is None


# --- normalize_permissions ---------------------------------------------------

def test_normalize_permissions_ok():
    out = MOD.normalize_permissions({"deny": ["A"], "ask": ["B"]}, "plg")
    scopes = {(p["decision"], p["rule"]) for p in out}
    assert scopes == {("deny", "A"), ("ask", "B")}


def test_normalize_permissions_not_object():
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_permissions([], "plg")


def test_normalize_permissions_decision_not_array():
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_permissions({"deny": "x"}, "plg")


def test_normalize_permissions_rule_not_string():
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_permissions({"deny": [1]}, "plg")


# --- read_skill_frontmatter_name --------------------------------------------

def test_read_skill_frontmatter_name_present(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text('---\nname: "my-skill"\n---\nbody\n', encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) == "my-skill"


def test_read_skill_frontmatter_name_no_frontmatter(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) is None


def test_read_skill_frontmatter_name_closes_without_name(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text("---\ndescription: d\n---\nbody\n", encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) is None


def test_read_skill_frontmatter_name_missing_file_raises(tmp_path):
    sd = tmp_path / "empty"
    sd.mkdir()
    with pytest.raises(MOD.LayoutError):
        MOD.read_skill_frontmatter_name(sd)


def test_read_skill_frontmatter_name_empty_file(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text("", encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) is None


# --- namespace_items ---------------------------------------------------------

def test_namespace_items_skill_with_frontmatter_alias(tmp_path):
    pdir = _plugin(tmp_path, "p", skills=[("dir-name", "front-name")])
    items = MOD.namespace_items(pdir, "p")
    names = sorted(s["name"] for s in items["skills"])
    assert names == ["dir-name", "front-name"]


def test_namespace_items_agents_and_commands(tmp_path):
    pdir = _plugin(tmp_path, "p", agents=["a.md"], commands=["c.md"])
    items = MOD.namespace_items(pdir, "p")
    assert items["agents"][0]["name"] == "a.md"
    assert items["commands"][0]["name"] == "c.md"


def test_namespace_items_skills_not_dir_raises(tmp_path):
    pdir = _plugin(tmp_path, "p")
    (pdir / "skills").write_text("file not dir", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.namespace_items(pdir, "p")


def test_namespace_items_skill_item_not_dir_raises(tmp_path):
    pdir = _plugin(tmp_path, "p")
    (pdir / "skills").mkdir()
    (pdir / "skills" / "afile").write_text("x", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.namespace_items(pdir, "p")


def test_namespace_items_agents_not_dir_raises(tmp_path):
    pdir = _plugin(tmp_path, "p")
    (pdir / "agents").write_text("file", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.namespace_items(pdir, "p")


def test_namespace_items_agent_not_markdown_raises(tmp_path):
    pdir = _plugin(tmp_path, "p")
    (pdir / "agents").mkdir()
    (pdir / "agents" / "a.txt").write_text("x", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.namespace_items(pdir, "p")


# --- plugin_hooks_from_file / plugin_permissions_from_file -------------------

def test_plugin_hooks_from_file_with_hooks_wrapper(tmp_path):
    f = tmp_path / "h.json"
    f.write_text(json.dumps({"hooks": _hook("python3 a.py")}), encoding="utf-8")
    out = MOD.plugin_hooks_from_file(f, "p")
    assert out[0]["command"] == "python3 a.py"


def test_plugin_hooks_from_file_bare(tmp_path):
    f = tmp_path / "h.json"
    f.write_text(json.dumps(_hook("python3 a.py")), encoding="utf-8")
    out = MOD.plugin_hooks_from_file(f, "p")
    assert out[0]["command"] == "python3 a.py"


def test_plugin_hooks_from_file_root_not_object(tmp_path):
    f = tmp_path / "h.json"
    f.write_text("[]", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.plugin_hooks_from_file(f, "p")


def test_plugin_permissions_from_file_with_wrapper(tmp_path):
    f = tmp_path / "perm.json"
    f.write_text(json.dumps({"permissions": {"deny": ["X"]}}), encoding="utf-8")
    out = MOD.plugin_permissions_from_file(f, "p")
    assert out[0]["rule"] == "X"


def test_plugin_permissions_from_file_root_not_object(tmp_path):
    f = tmp_path / "perm.json"
    f.write_text("\"str\"", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.plugin_permissions_from_file(f, "p")


# --- discover_plugins --------------------------------------------------------

def test_discover_plugins_missing_dir_returns_empty(tmp_path):
    assert MOD.discover_plugins(tmp_path / "absent") == []


def test_discover_plugins_not_dir_raises(tmp_path):
    f = tmp_path / "f"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(f)


def test_discover_plugins_manifest_missing_raises(tmp_path):
    (tmp_path / "broken").mkdir()
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(tmp_path)


def test_discover_plugins_manifest_not_object_raises(tmp_path):
    pdir = tmp_path / "p"
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text("[]", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(tmp_path)


def test_discover_plugins_name_not_string_raises(tmp_path):
    pdir = tmp_path / "p"
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": 5}), encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(tmp_path)


def test_discover_plugins_duplicate_name_raises(tmp_path):
    _plugin(tmp_path, "dirA", manifest_extra={"name": "dup"})
    _plugin(tmp_path, "dirB", manifest_extra={"name": "dup"})
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(tmp_path)


def test_discover_plugins_collects_hooks_perms_namespace(tmp_path):
    _plugin(
        tmp_path, "alpha",
        manifest_extra={"hooks": _hook("python3 m.py"),
                        "permissions": {"deny": ["MP"]}},
        hooks_files={"x.json": _hook("python3 file.py", event="Stop", matcher=None)},
        permissions_file={"deny": ["FP"]},
        skills=["run-a"], agents=["g.md"], commands=["c.md"],
    )
    plugins = MOD.discover_plugins(tmp_path)
    assert len(plugins) == 1
    p = plugins[0]
    cmds = {h["command"] for h in p["hooks"]}
    assert cmds == {"python3 m.py", "python3 file.py"}
    rules = {pm["rule"] for pm in p["permissions"]}
    assert rules == {"MP", "FP"}
    assert any(s["name"] == "run-a" for s in p["namespace"]["skills"])


def test_discover_plugins_hooks_path_not_dir_raises(tmp_path):
    pdir = _plugin(tmp_path, "p")
    (pdir / "hooks").write_text("file", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(tmp_path)


# --- validate_settings_structure --------------------------------------------

def test_validate_settings_structure_ok():
    MOD.validate_settings_structure({"permissions": {"deny": [], "ask": []}, "hooks": {}})


def test_validate_settings_structure_permissions_not_object():
    with pytest.raises(MOD.LayoutError):
        MOD.validate_settings_structure({"permissions": []})


def test_validate_settings_structure_permission_decision_not_array():
    with pytest.raises(MOD.LayoutError):
        MOD.validate_settings_structure({"permissions": {"deny": "x"}})


def test_validate_settings_structure_hooks_not_object():
    with pytest.raises(MOD.LayoutError):
        MOD.validate_settings_structure({"hooks": []})


def test_validate_settings_structure_unknown_event():
    # 互換修復 (PRECONDITION-CLAUDE-REFLECTOR-COMPAT) の非対称契約:
    #   - target 側 (validate_settings_structure = 既存 .claude/settings.json の検証) は
    #     allowlist 外の未知 event を verbatim preserve する (raise しない)。
    #     将来 Claude Code が追加する新 event で reflector が exit3 死する回帰を防ぐため。
    MOD.validate_settings_structure({"hooks": {"Nope": []}})  # no raise = preserve

    # - managed source 側 (plugin manifest 由来の hook) は従来どおり未知 event を
    #   fail-closed で block する。この負側 (block) を assert する。
    with pytest.raises(MOD.LayoutError):
        MOD.normalize_hook_entries(_hook("python3 a.py", event="Nope"), "plg")


def test_validate_settings_structure_event_not_array():
    with pytest.raises(MOD.LayoutError):
        MOD.validate_settings_structure({"hooks": {"Stop": {}}})


def test_validate_settings_structure_entry_not_object():
    with pytest.raises(MOD.LayoutError):
        MOD.validate_settings_structure({"hooks": {"Stop": ["x"]}})


def test_validate_settings_structure_none_sections_ok():
    MOD.validate_settings_structure({"permissions": None, "hooks": None})


# --- managed_from_target / remove_managed_values ----------------------------

def test_managed_from_target_non_dict_metadata():
    out = MOD.managed_from_target({"_build_claude_settings": "x"})
    assert out == {"managed_hooks": [], "managed_permissions": []}


def test_managed_from_target_non_list_values_coerced():
    out = MOD.managed_from_target(
        {"_build_claude_settings": {"managed_hooks": "x", "managed_permissions": 5}})
    assert out == {"managed_hooks": [], "managed_permissions": []}


def test_remove_managed_values_strips_managed_hooks_and_perms():
    target = {
        "_build_claude_settings": {
            "managed_hooks": [{"event": "Stop", "matcher": None, "command": "gen.py"}],
            "managed_permissions": [{"scope": "permissions.deny", "rule": "GEN"}],
        },
        "hooks": {"Stop": [
            {"hooks": [{"type": "command", "command": "gen.py"}]},
            {"hooks": [{"type": "command", "command": "user.py"}]},
        ]},
        "permissions": {"deny": ["GEN", "USER"], "ask": []},
        "custom": True,
    }
    out = MOD.remove_managed_values(target)
    assert "_build_claude_settings" not in out
    assert out["hooks"]["Stop"] == [{"hooks": [{"type": "command", "command": "user.py"}]}]
    assert out["permissions"]["deny"] == ["USER"]
    assert out["custom"] is True


def test_remove_managed_values_drops_empty_hooks_and_perms():
    target = {
        "_build_claude_settings": {
            "managed_hooks": [{"event": "Stop", "matcher": None, "command": "gen.py"}],
            "managed_permissions": [{"scope": "permissions.deny", "rule": "GEN"}],
        },
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "gen.py"}]}]},
        "permissions": {"deny": ["GEN"], "ask": []},
    }
    out = MOD.remove_managed_values(target)
    assert "hooks" not in out
    assert "permissions" not in out


# --- user_section_sha256 -----------------------------------------------------

def test_user_section_sha256_stable_and_64_hex():
    h1 = MOD.user_section_sha256({"a": 1})
    h2 = MOD.user_section_sha256({"a": 1})
    assert h1 == h2 and len(h1) == 64


def test_user_section_sha256_ignores_managed_values():
    base = {"permissions": {"deny": ["USER"], "ask": []}}
    managed = {
        "_build_claude_settings": {
            "managed_hooks": [],
            "managed_permissions": [{"scope": "permissions.deny", "rule": "GEN"}],
        },
        "permissions": {"deny": ["USER", "GEN"], "ask": []},
    }
    assert MOD.user_section_sha256(base) == MOD.user_section_sha256(managed)


# --- namespace_preflight / merge_hooks / merge_permissions ------------------

def test_namespace_preflight_conflict_marks_verdict(tmp_path):
    _plugin(tmp_path, "alpha", skills=["shared"])
    _plugin(tmp_path, "beta", skills=["shared"])
    plugins = MOD.discover_plugins(tmp_path)
    ns = MOD.namespace_preflight(plugins)
    assert any(c["type"] == "skill" and c["name"] == "shared" for c in ns["conflicts"])
    assert any(s.get("verdict") == "conflict" for s in ns["skills"])


def test_namespace_preflight_no_conflict_for_distinct(tmp_path):
    _plugin(tmp_path, "alpha", skills=["one"])
    _plugin(tmp_path, "beta", skills=["two"])
    plugins = MOD.discover_plugins(tmp_path)
    ns = MOD.namespace_preflight(plugins)
    assert ns["conflicts"] == []


def test_merge_hooks_conflict_on_shared_command(tmp_path):
    _plugin(tmp_path, "alpha", manifest_extra={"hooks": _hook("python3 shared.py", matcher="X")})
    _plugin(tmp_path, "beta", manifest_extra={"hooks": _hook("python3 shared.py", matcher="X")})
    plugins = MOD.discover_plugins(tmp_path)
    generated, conflicts, _dedupe = MOD.merge_hooks({}, plugins)
    assert any(c["type"] == "hook" for c in conflicts)


def test_merge_hooks_sorted_by_plugin(tmp_path):
    _plugin(tmp_path, "beta", manifest_extra={"hooks": _hook("python3 b.py")})
    _plugin(tmp_path, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    plugins = MOD.discover_plugins(tmp_path)
    generated, conflicts, _dedupe = MOD.merge_hooks({}, plugins)
    assert [h["from_plugin"] for h in generated] == ["alpha", "beta"]
    assert conflicts == []


def test_merge_permissions_dedupe_count(tmp_path):
    _plugin(tmp_path, "alpha", manifest_extra={"permissions": {"deny": ["RULE"]}})
    _plugin(tmp_path, "beta", manifest_extra={"permissions": {"deny": ["RULE"]}})
    plugins = MOD.discover_plugins(tmp_path)
    deduped, conflicts, dedupe = MOD.merge_permissions(plugins)
    assert dedupe == 1 and conflicts == []
    assert len(deduped) == 1


def test_merge_permissions_decision_conflict(tmp_path):
    _plugin(tmp_path, "alpha", manifest_extra={"permissions": {"deny": ["RULE"]}})
    _plugin(tmp_path, "beta", manifest_extra={"permissions": {"ask": ["RULE"]}})
    plugins = MOD.discover_plugins(tmp_path)
    deduped, conflicts, dedupe = MOD.merge_permissions(plugins)
    assert any(c["type"] == "permission" for c in conflicts)


# --- hook_entry / build_desired_settings ------------------------------------

def test_hook_entry_with_matcher():
    e = MOD.hook_entry({"command": "x", "matcher": "Write"})
    assert e == {"matcher": "Write", "hooks": [{"type": "command", "command": "x"}]}


def test_hook_entry_without_matcher():
    e = MOD.hook_entry({"command": "x", "matcher": None})
    assert "matcher" not in e


def test_build_desired_settings_merges_user_and_generated():
    target = {"permissions": {"deny": ["USER"], "ask": []},
              "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "user.py"}]}]},
              "extra": 1}
    gen_hooks = [{"event": "Stop", "matcher": None, "command": "gen.py", "from_plugin": "p"}]
    gen_perms = [{"scope": "permissions.deny", "decision": "deny", "rule": "GEN", "from_plugin": "p"}]
    desired = MOD.build_desired_settings(target, gen_hooks, gen_perms)
    assert "GEN" in desired["permissions"]["deny"] and "USER" in desired["permissions"]["deny"]
    assert desired["extra"] == 1
    assert desired["_build_claude_settings"]["managed_hooks"][0]["command"] == "gen.py"


def test_build_desired_settings_with_empty_target():
    gen_hooks = [{"event": "Stop", "matcher": "M", "command": "gen.py", "from_plugin": "p"}]
    desired = MOD.build_desired_settings({}, gen_hooks, [])
    assert desired["hooks"]["Stop"][0]["matcher"] == "M"
    assert desired["permissions"] == {"deny": [], "ask": []}


# --- check_mode / atomic_write ----------------------------------------------

def test_check_mode_equal_and_unequal():
    assert MOD.check_mode({"a": 1}, {"a": 1}) is True
    assert MOD.check_mode({"a": 1}, {"a": 2}) is False


def test_atomic_write_creates_file(tmp_path):
    p = tmp_path / "nested" / "out.json"
    MOD.atomic_write(p, "content\n")
    assert p.read_text(encoding="utf-8") == "content\n"


def test_atomic_write_failure_cleans_tmp(tmp_path):
    p = tmp_path / "out.json"
    p.write_text("orig\n", encoding="utf-8")
    with mock.patch.object(MOD.os, "rename", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            MOD.atomic_write(p, "new\n")
    # 元ファイル維持 + .tmp 残骸なし
    assert p.read_text(encoding="utf-8") == "orig\n"
    assert not list(tmp_path.glob(".out.json.*"))


# --- print_report ------------------------------------------------------------

def test_print_report_text(capsys):
    plan = {"summary": {"add": 1, "keep": 0, "dedupe": 2, "conflict": 0}}
    MOD.print_report(plan, as_json=False)
    out = capsys.readouterr().out
    assert "add=1 keep=0 dedupe=2 conflict=0" in out


def test_print_report_json(capsys):
    plan = {"summary": {"add": 0, "keep": 0, "dedupe": 0, "conflict": 0}, "x": 1}
    MOD.print_report(plan, as_json=True)
    out = capsys.readouterr().out
    assert json.loads(out)["x"] == 1


# --- build() -----------------------------------------------------------------

def test_build_user_preserved_true(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text(MOD.serialize({"permissions": {"deny": ["U"], "ask": []}}), encoding="utf-8")
    _, desired, plan = MOD.build(target, plugins)
    assert plan["user_values_preserved"] is True
    assert plan["summary"]["add"] == 1


# --- main() in-process: 各 exit path -----------------------------------------

def _setup_tree(tmp_path, target_data=None):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    if target_data is not None:
        target.write_text(MOD.serialize(target_data), encoding="utf-8")
    return plugins, target


def test_main_apply_writes_and_returns_0(tmp_path, monkeypatch):
    plugins, target = _setup_tree(tmp_path, {"permissions": {"deny": ["U"], "ask": []}})
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    rc = _run_main(monkeypatch, tmp_path)
    assert rc == 0
    written = MOD.load_target(target)
    assert "_build_claude_settings" in written
    assert "U" in written["permissions"]["deny"]


def test_main_dry_run_does_not_write(tmp_path, monkeypatch, capsys):
    plugins, target = _setup_tree(tmp_path)
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    rc = _run_main(monkeypatch, tmp_path, "--dry-run", "--json")
    assert rc == 0
    assert not target.exists()  # default target absent
    assert "namespace" in capsys.readouterr().out


def test_main_check_drift_returns_1(tmp_path, monkeypatch):
    plugins, target = _setup_tree(tmp_path, {})
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    rc = _run_main(monkeypatch, tmp_path, "--check")
    assert rc == 1


def test_main_check_clean_returns_0(tmp_path, monkeypatch):
    plugins, target = _setup_tree(tmp_path, {})
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    assert _run_main(monkeypatch, tmp_path) == 0       # apply
    assert _run_main(monkeypatch, tmp_path, "--check") == 0


def test_main_conflict_returns_2(tmp_path, monkeypatch, capsys):
    plugins, target = _setup_tree(tmp_path, {})
    _plugin(plugins, "alpha", skills=["shared"])
    _plugin(plugins, "beta", skills=["shared"])
    rc = _run_main(monkeypatch, tmp_path, "--json")
    assert rc == 2
    assert '"conflict"' in capsys.readouterr().out


def test_main_print_user_section_hash(tmp_path, monkeypatch, capsys):
    plugins, target = _setup_tree(tmp_path, {"a": 1})
    rc = _run_main(monkeypatch, tmp_path, "--print-user-section-hash")
    assert rc == 0
    assert len(capsys.readouterr().out.strip()) == 64


def test_main_layout_error_returns_3(tmp_path, monkeypatch, capsys):
    plugins, target = _setup_tree(tmp_path, {})
    (plugins / "broken").mkdir()  # manifest 欠如
    rc = _run_main(monkeypatch, tmp_path)
    assert rc == 3
    assert "manifest missing" in capsys.readouterr().err


def test_main_invariant_error_returns_2(tmp_path, monkeypatch, capsys):
    plugins, target = _setup_tree(tmp_path, {})
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    # main() の apply 後 after_hash != before_hash で INV-1 違反させる。
    # 呼び出し順: build()内[before, after], main()内[before(=3回目), after(=4回目)]。
    # 4回目だけ別値を返せば before/after 不一致となり InvariantError -> exit 2。
    real = MOD.user_section_sha256
    calls = {"n": 0}

    def flaky(data):
        calls["n"] += 1
        if calls["n"] == 4:
            return "deadbeef" * 8
        return real(data)

    monkeypatch.setattr(MOD, "user_section_sha256", flaky)
    rc = _run_main(monkeypatch, tmp_path)
    assert rc == 2
    assert "INV-1" in capsys.readouterr().err


def test_main_oserror_returns_3(tmp_path, monkeypatch, capsys):
    plugins, target = _setup_tree(tmp_path, {})
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    monkeypatch.setattr(MOD, "atomic_write", mock.Mock(side_effect=OSError("disk full")))
    rc = _run_main(monkeypatch, tmp_path)
    assert rc == 3
    assert "disk full" in capsys.readouterr().err


def test_main_verbose_text_path_returns_0(tmp_path, monkeypatch, capsys):
    plugins, target = _setup_tree(tmp_path, {})
    _plugin(plugins, "alpha", manifest_extra={"hooks": _hook("python3 a.py")})
    rc = _run_main(monkeypatch, tmp_path, "--dry-run", "--verbose")
    assert rc == 0
    # --verbose -> as_json True -> JSON 出力
    assert "namespace" in capsys.readouterr().out
