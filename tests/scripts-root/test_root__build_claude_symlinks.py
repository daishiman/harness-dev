"""scripts/build-claude-symlinks.py の genuine で網羅的な機能テスト (network 不要)。

plugin-owned の agents/skills/commands を .claude/<kind>/ 配下へ相対 symlink で展開する
ビルダ。tests/test_build_claude_symlinks.py が subprocess の主要契約を担保するのに対し、
本ファイルは in-process で純関数 (parse_kinds / discover_* / desired_entries /
compute_plan / apply_plan / check_drift / summarize) と main(argv) の全 exit path を
直接呼び、各分岐 (create/update/noop/conflict/prune/orphan/broken, SSOT alias 解決,
不正レイアウト) を行カバレッジ込みで網羅する。

外部 I/O は tmp_path 上の symlink 操作のみ。実 .claude は書き換えない。
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-claude-symlinks.py"

SPEC = importlib.util.spec_from_file_location("build_claude_symlinks_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

def _skill(plugins: Path, plugin: str, name: str, *, frontmatter_name=None,
           skill_md=True):
    sd = plugins / plugin / "skills" / name
    sd.mkdir(parents=True)
    if skill_md:
        header = "---\n"
        if frontmatter_name:
            header += f"name: {frontmatter_name}\n"
        header += "---\n# Skill\n"
        (sd / "SKILL.md").write_text(header, encoding="utf-8")
    return sd


def _agent(plugins: Path, plugin: str, name: str):
    ad = plugins / plugin / "agents"
    ad.mkdir(parents=True, exist_ok=True)
    f = ad / name
    f.write_text("agent\n", encoding="utf-8")
    return f


def _run_main(monkeypatch, cwd, *argv):
    monkeypatch.chdir(cwd)
    return MOD.main(list(argv))


# --- parse_args / parse_kinds / help ----------------------------------------

def test_parse_args_defaults():
    a = MOD.parse_args([])
    assert a.plugins_dir == "plugins"
    assert a.target_dir == ".claude"
    assert a.kinds == "agents,skills,commands"
    assert a.prune is False
    assert a.exclude_plugin == []
    assert a.conflicts_only is False


def test_parse_args_exclude_plugin_repeatable():
    a = MOD.parse_args(["--exclude-plugin", "v2", "--exclude-plugin", "scratch"])
    assert a.exclude_plugin == ["v2", "scratch"]


def test_parse_kinds_ok():
    assert MOD.parse_kinds("skills,agents") == ["skills", "agents"]


def test_parse_kinds_strips_whitespace():
    assert MOD.parse_kinds(" skills , commands ") == ["skills", "commands"]


def test_parse_kinds_empty_raises():
    with pytest.raises(MOD.LayoutError):
        MOD.parse_kinds("")


def test_parse_kinds_invalid_raises():
    with pytest.raises(MOD.LayoutError):
        MOD.parse_kinds("skills,bogus")


def test_help_matches_contract_usage():
    res = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                         text=True, capture_output=True)
    assert res.returncode == 0
    assert res.stdout.startswith("usage: build-claude-symlinks.py [-h]")
    assert "--prune" in res.stdout
    assert "--exclude-plugin" in res.stdout
    assert "--conflicts-only" in res.stdout


# --- discover_plugins --------------------------------------------------------

def test_discover_plugins_missing_dir_raises(tmp_path):
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(tmp_path / "absent")


def test_discover_plugins_not_dir_raises(tmp_path):
    f = tmp_path / "file"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_plugins(f)


def test_discover_plugins_sorted_dirs_only(tmp_path):
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / "afile").write_text("x", encoding="utf-8")
    out = [p.name for p in MOD.discover_plugins(tmp_path)]
    assert out == ["alpha", "beta"]


def test_discover_plugins_excludes_named_dirs(tmp_path):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "slide-report-generator-v2").mkdir()
    out = [
        p.name
        for p in MOD.discover_plugins(
            tmp_path, exclude_plugins=["slide-report-generator-v2"]
        )
    ]
    assert out == ["alpha"]


# --- discover_items ----------------------------------------------------------

def test_discover_items_missing_kind_dir_returns_empty(tmp_path):
    (tmp_path / "p").mkdir()
    assert MOD.discover_items(tmp_path / "p", "skills") == []


def test_discover_items_kind_not_dir_raises(tmp_path):
    p = tmp_path / "p"
    p.mkdir()
    (p / "skills").write_text("file", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_items(p, "skills")


def test_discover_items_skill_must_be_dir(tmp_path):
    p = tmp_path / "p"
    (p / "skills").mkdir(parents=True)
    (p / "skills" / "afile").write_text("x", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_items(p, "skills")


def test_discover_items_skill_missing_skill_md(tmp_path):
    _skill(tmp_path, "p", "nomd", skill_md=False)
    with pytest.raises(MOD.LayoutError):
        MOD.discover_items(tmp_path / "p", "skills")


def test_discover_items_agent_must_be_file(tmp_path):
    p = tmp_path / "p"
    (p / "agents").mkdir(parents=True)
    (p / "agents" / "subdir").mkdir()
    with pytest.raises(MOD.LayoutError):
        MOD.discover_items(p, "agents")


def test_discover_items_agent_must_be_markdown(tmp_path):
    p = tmp_path / "p"
    (p / "agents").mkdir(parents=True)
    (p / "agents" / "a.txt").write_text("x", encoding="utf-8")
    with pytest.raises(MOD.LayoutError):
        MOD.discover_items(p, "agents")


def test_discover_items_returns_sorted(tmp_path):
    _skill(tmp_path, "p", "z")
    _skill(tmp_path, "p", "a")
    out = [i.name for i in MOD.discover_items(tmp_path / "p", "skills")]
    assert out == ["a", "z"]


# --- read_skill_frontmatter_name --------------------------------------------

def test_read_skill_frontmatter_name_present(tmp_path):
    sd = _skill(tmp_path, "p", "demo", frontmatter_name="alias")
    assert MOD.read_skill_frontmatter_name(sd) == "alias"


def test_read_skill_frontmatter_name_none_when_no_frontmatter(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text("# body only\n", encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) is None


def test_read_skill_frontmatter_name_closes_without_name(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text("---\ndescription: d\n---\n", encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) is None


def test_read_skill_frontmatter_name_missing_file_raises(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()  # SKILL.md なし
    with pytest.raises(MOD.LayoutError):
        MOD.read_skill_frontmatter_name(sd)


def test_read_skill_frontmatter_name_empty_file(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text("", encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) is None


def test_read_skill_frontmatter_name_unterminated_no_name(tmp_path):
    # frontmatter が "---" で開くが閉じず name もない -> ループ尽きて return None (行99)
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "SKILL.md").write_text("---\ndescription: d\nfoo: bar\n", encoding="utf-8")
    assert MOD.read_skill_frontmatter_name(sd) is None


# --- desired_entries ---------------------------------------------------------

def test_desired_entries_single_skill(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    entries, conflicts = MOD.desired_entries(plugins, tmp_path / ".claude", ["skills"])
    assert len(entries) == 1
    assert conflicts == set()
    assert entries[0]["dst"].name == "demo"


def test_desired_entries_name_conflict_distinct_realpaths(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    _skill(plugins, "beta", "demo")
    entries, conflicts = MOD.desired_entries(plugins, tmp_path / ".claude", ["skills"])
    assert len(conflicts) >= 1  # 同 dst, 異なる realpath -> conflict


def test_desired_entries_exclude_plugin_avoids_name_conflict(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "slide-report-generator", "run-slide-report-generate")
    _skill(plugins, "slide-report-generator-v2", "run-slide-report-generate")
    entries, conflicts = MOD.desired_entries(
        plugins,
        tmp_path / ".claude",
        ["skills"],
        exclude_plugins=["slide-report-generator-v2"],
    )
    assert len(entries) == 1
    assert conflicts == set()
    assert entries[0]["src"].parts[-3] == "slide-report-generator"


def test_desired_entries_frontmatter_alias_conflict(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "first", frontmatter_name="shared")
    _skill(plugins, "beta", "second", frontmatter_name="shared")
    entries, conflicts = MOD.desired_entries(plugins, tmp_path / ".claude", ["skills"])
    # identifiers の (skills, shared) に 2 realpath -> conflict
    assert len(conflicts) >= 1


def test_desired_entries_symlink_alias_collapses_to_single(tmp_path):
    """2 plugin の同名 skill が同一 realpath を指す symlink alias -> 単一エントリ。"""
    plugins = tmp_path / "plugins"
    real = _skill(plugins, "alpha", "demo")
    # beta/skills/demo を alpha の実体への symlink にする
    beta_skills = plugins / "beta" / "skills"
    beta_skills.mkdir(parents=True)
    (beta_skills / "demo").symlink_to(real)
    entries, conflicts = MOD.desired_entries(plugins, tmp_path / ".claude", ["skills"])
    # 同 dst (skills/demo) で realpath 1 つ -> 単一 canonical エントリ, conflict なし
    dsts = [e["dst"].name for e in entries]
    assert dsts.count("demo") == 1
    assert conflicts == set()


def test_desired_entries_all_symlink_alias_uses_fallback_canonical(tmp_path):
    """alias group の全 src が symlink (非 symlink canonical 不在) -> fallback 選択 (行144)。

    実体を plugins/ の外に置き、alpha/beta 双方の skills/demo を同一実体への symlink にする。
    どちらも非 symlink でないため最初の next() は None を返し、2 つ目の next() が走る。
    """
    plugins = tmp_path / "plugins"
    real = tmp_path / "real_store" / "demo"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\n---\n# Skill\n", encoding="utf-8")
    for plugin in ("alpha", "beta"):
        sk = plugins / plugin / "skills"
        sk.mkdir(parents=True)
        (sk / "demo").symlink_to(real)
    entries, conflicts = MOD.desired_entries(plugins, tmp_path / ".claude", ["skills"])
    dsts = [e["dst"].name for e in entries]
    assert dsts.count("demo") == 1
    assert conflicts == set()


# --- compute_plan: create/update/noop/conflict ------------------------------

def test_compute_plan_create(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"])
    assert plan[0]["action"] == "create"
    assert plan[0]["reason"] == "missing symlink"


def test_compute_plan_noop_existing_correct_link(tmp_path):
    plugins = tmp_path / "plugins"
    src = _skill(plugins, "alpha", "demo")
    dst = tmp_path / ".claude" / "skills" / "demo"
    dst.parent.mkdir(parents=True)
    dst.symlink_to(os.path.relpath(src, dst.parent))
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"])
    assert plan[0]["action"] == "noop"


def test_compute_plan_update_wrong_link(tmp_path):
    plugins = tmp_path / "plugins"
    src = _skill(plugins, "alpha", "demo")
    other = _skill(plugins, "alpha", "other")
    dst = tmp_path / ".claude" / "skills" / "demo"
    dst.parent.mkdir(parents=True)
    dst.symlink_to(os.path.relpath(other, dst.parent))
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"])
    demo = next(p for p in plan if p["dst"].endswith("demo"))
    assert demo["action"] == "update"
    assert demo["reason"] == "wrong target"


def test_compute_plan_conflict_real_file(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    dst = tmp_path / ".claude" / "skills" / "demo"
    dst.parent.mkdir(parents=True)
    dst.write_text("real file", encoding="utf-8")
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"])
    assert plan[0]["action"] == "conflict"
    assert plan[0]["reason"] == "real file/dir found"


def test_compute_plan_name_conflict_entry(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    _skill(plugins, "beta", "demo")
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"])
    assert any(p["action"] == "conflict" and p["reason"] == "name conflict" for p in plan)


def test_compute_plan_exclude_plugin_skips_conflicting_v2(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "slide-report-generator", "run-slide-report-generate")
    _skill(plugins, "slide-report-generator-v2", "run-slide-report-generate")
    plan = MOD.compute_plan(
        plugins,
        tmp_path / ".claude",
        ["skills"],
        exclude_plugins=["slide-report-generator-v2"],
    )
    assert not any(p["action"] == "conflict" for p in plan)
    assert len(plan) == 1
    assert plan[0]["action"] == "create"


def test_compute_plan_kind_path_not_directory_conflict(tmp_path):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "skills").write_text("not a dir", encoding="utf-8")
    plan = MOD.compute_plan(plugins, target, ["skills"])
    assert any(p["reason"] == "target kind path is not a directory" for p in plan)


# --- compute_plan: orphan / broken / prune ----------------------------------

def test_compute_plan_orphan_symlink_noop(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()  # 該当 skill なし
    orphan_target = tmp_path / "real_target"
    orphan_target.mkdir()
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "gone").symlink_to(os.path.relpath(orphan_target, skills_dir))
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"])
    gone = next(p for p in plan if p["dst"].endswith("gone"))
    assert gone["action"] == "noop"
    assert gone["reason"] == "orphan symlink"


def test_compute_plan_broken_symlink_noop_reason(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "broken").symlink_to("../does-not-exist")
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"])
    broken = next(p for p in plan if p["dst"].endswith("broken"))
    assert broken["reason"] == "broken symlink"


def test_compute_plan_prune_marks_update_with_empty_src(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "broken").symlink_to("../does-not-exist")
    plan = MOD.compute_plan(plugins, tmp_path / ".claude", ["skills"], prune=True)
    broken = next(p for p in plan if p["dst"].endswith("broken"))
    assert broken["action"] == "update"
    assert broken["src"] == ""
    assert broken["reason"].startswith("prune")


# --- summarize / check_drift / plan_item / is_known_source ------------------

def test_summarize_counts():
    plan = [
        {"action": "create", "reason": "x"},
        {"action": "update", "reason": "x"},
        {"action": "noop", "reason": "x"},
        {"action": "conflict", "reason": "x"},
        {"action": "noop", "reason": "x"},
    ]
    assert MOD.summarize(plan) == {"created": 1, "updated": 1, "noop": 2, "conflict": 1}


def test_check_drift_true_on_create():
    assert MOD.check_drift([{"action": "create", "reason": "missing symlink"}]) is True


def test_check_drift_true_on_orphan_reason():
    assert MOD.check_drift([{"action": "noop", "reason": "orphan symlink"}]) is True


def test_check_drift_true_on_broken_reason():
    assert MOD.check_drift([{"action": "noop", "reason": "broken symlink"}]) is True


def test_check_drift_false_when_clean():
    assert MOD.check_drift([{"action": "noop", "reason": "already linked"}]) is False


def test_plan_item_src_none():
    item = MOD.plan_item("update", None, Path("/a/b"), "prune")
    assert item["src"] == "" and item["dst"] == "/a/b"


def test_is_known_source_true_and_false(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    dst = tmp_path / ".claude" / "skills" / "demo"
    dst.parent.mkdir(parents=True)
    rel = os.path.relpath(target, dst.parent)
    assert MOD.is_known_source(rel, dst, {target.resolve()}) is True
    assert MOD.is_known_source(rel, dst, set()) is False


# --- apply_plan --------------------------------------------------------------

def test_apply_plan_dry_run_noop(tmp_path):
    plan = [MOD.plan_item("create", tmp_path / "src", tmp_path / "dst", "missing")]
    MOD.apply_plan(plan, dry_run=True)
    assert not (tmp_path / "dst").exists()


def test_apply_plan_create_symlink(tmp_path):
    src = tmp_path / "plugins" / "alpha" / "skills" / "demo"
    src.mkdir(parents=True)
    dst = tmp_path / ".claude" / "skills" / "demo"
    plan = [MOD.plan_item("create", src, dst, "missing symlink")]
    MOD.apply_plan(plan)
    assert dst.is_symlink()
    assert (dst.parent / os.readlink(dst)).resolve() == src.resolve()


def test_apply_plan_update_relink(tmp_path):
    src = tmp_path / "plugins" / "alpha" / "skills" / "demo"
    src.mkdir(parents=True)
    other = tmp_path / "plugins" / "alpha" / "skills" / "other"
    other.mkdir(parents=True)
    dst = tmp_path / ".claude" / "skills" / "demo"
    dst.parent.mkdir(parents=True)
    dst.symlink_to(os.path.relpath(other, dst.parent))
    MOD.apply_plan([MOD.plan_item("update", src, dst, "wrong target")])
    assert (dst.parent / os.readlink(dst)).resolve() == src.resolve()


def test_apply_plan_prune_unlink(tmp_path):
    dst = tmp_path / ".claude" / "skills" / "broken"
    dst.parent.mkdir(parents=True)
    dst.symlink_to("../missing")
    MOD.apply_plan([MOD.plan_item("update", None, dst, "prune broken symlink")])
    assert not dst.is_symlink()


def test_apply_plan_skips_conflict_and_noop(tmp_path):
    dst = tmp_path / ".claude" / "skills" / "x"
    plan = [
        MOD.plan_item("conflict", tmp_path / "s", dst, "name conflict"),
        MOD.plan_item("noop", tmp_path / "s", dst, "already linked"),
    ]
    MOD.apply_plan(plan)
    assert not dst.exists()


# --- build_report / print_report --------------------------------------------

def test_build_report_shape(tmp_path):
    plan = [MOD.plan_item("create", tmp_path / "s", tmp_path / "d", "missing symlink")]
    report = MOD.build_report(tmp_path / "plugins", tmp_path / ".claude", ["skills"], plan)
    assert report["kinds"] == ["skills"]
    assert report["summary"]["created"] == 1
    assert report["plan"] == plan


def test_print_report_text(capsys):
    report = {"summary": {"created": 1, "updated": 0, "noop": 2, "conflict": 0}}
    MOD.print_report(report, as_json=False)
    out = capsys.readouterr().out
    assert "created=1 updated=0 noop=2 conflict=0" in out


def test_print_report_json(capsys):
    report = {"summary": {"created": 0, "updated": 0, "noop": 0, "conflict": 0}, "k": 1}
    MOD.print_report(report, as_json=True)
    assert json.loads(capsys.readouterr().out)["k"] == 1


# --- main(): 各 exit path (in-process, cwd を tmp に向ける) -------------------

def test_main_create_returns_0_and_links(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "skills")
    assert rc == 0
    dst = tmp_path / ".claude" / "skills" / "demo"
    assert dst.is_symlink()
    assert "created=1" in capsys.readouterr().out


def test_main_dry_run_no_filesystem_change(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "skills", "--dry-run", "--json")
    assert rc == 0
    assert not (tmp_path / ".claude" / "skills" / "demo").exists()
    assert '"plan"' in capsys.readouterr().out


def test_main_idempotent_check_clean(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    assert _run_main(monkeypatch, tmp_path, "--kinds", "skills") == 0
    assert _run_main(monkeypatch, tmp_path, "--kinds", "skills", "--check") == 0


def test_main_check_reports_drift_returns_1(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "skills", "--check")
    assert rc == 1


def test_main_conflict_returns_2(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    _skill(plugins, "beta", "demo")
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "skills", "--json")
    assert rc == 2
    assert "conflict" in capsys.readouterr().out


def test_main_invalid_kinds_returns_3(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "bogus")
    assert rc == 3
    assert "invalid kinds" in capsys.readouterr().err


def test_main_layout_error_missing_plugins_dir_returns_3(tmp_path, monkeypatch, capsys):
    # plugins/ が存在しない -> discover_plugins LayoutError -> exit 3
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "skills")
    assert rc == 3
    assert "plugins dir does not exist" in capsys.readouterr().err


def test_main_oserror_returns_4(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    _skill(plugins, "alpha", "demo")
    monkeypatch.setattr(MOD, "apply_plan", mock.Mock(side_effect=OSError("io fail")))
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "skills")
    assert rc == 4
    assert "io fail" in capsys.readouterr().err


def test_main_prune_removes_broken_symlink(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "broken").symlink_to("../missing")
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "skills", "--prune")
    assert rc == 0
    assert not (skills_dir / "broken").is_symlink()


def test_main_agents_kind_create(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    _agent(plugins, "alpha", "myagent.md")
    rc = _run_main(monkeypatch, tmp_path, "--kinds", "agents")
    assert rc == 0
    assert (tmp_path / ".claude" / "agents" / "myagent.md").is_symlink()
