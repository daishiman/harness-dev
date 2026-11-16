"""validate-build-plan.py の機能テスト。

brief→flags/成果物の決定論導出 (derive) と、生成物ディスク実体との突合 (check) を検証する。
低性能モデル対策の中核ゲート: フラグ要否をモデル判断に委ねない性質をテストで固定する。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "plugins/harness-creator/skills/run-build-skill/scripts/validate-build-plan.py"
)
RUN_BUILD = REPO_ROOT / "plugins/harness-creator/skills/run-build-skill"
COMMAND = REPO_ROOT / "plugins/harness-creator/commands/capability-build.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_build_plan", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# --- derive: brief→flags は純関数 -----------------------------------------


def test_flags_all_derived_from_brief(mod):
    brief = {
        "kind": "run",
        "responsibilities": [{"id": "R1"}],
        "generate_pair_evaluator": True,
        "hook_events": ["PostToolUse"],
        "knowledge_loop": {"pattern": "index-search"},
        "with_subagent_hint": True,
    }
    flags = mod.derive_flags(brief)
    assert flags["with_prompts"] is True
    assert flags["with_evaluator"] is True
    assert flags["with_hooks"] is True
    assert flags["with_knowledge"] is True
    assert flags["with_subagent"] is True
    assert flags["with_goal_seek"] is True
    assert flags["feedback_contract_required"] is True
    assert flags["verification_profile"] == "incremental"
    assert flags["build_stage"] == "draft"


def test_flags_empty_brief_defaults_off(mod):
    flags = mod.derive_flags({"kind": "ref"})
    assert not any(
        flags[k]
        for k in ("with_prompts", "with_evaluator", "with_hooks", "with_subagent", "with_knowledge")
    )
    assert flags["feedback_contract_required"] is False
    # default-ON 系は brief に無くても ON (opt-out は CLI のみ)
    assert flags["feedback_loop_deploy"] is True
    assert flags["content_review"] is True


def test_prompt_creator_policy_skip_disables_prompts(mod):
    flags = mod.derive_flags(
        {"kind": "run", "responsibilities": [{"id": "R1"}], "prompt_creator_policy": "skip"}
    )
    assert flags["with_prompts"] is False


def test_cli_optout_goal_seek(mod):
    flags = mod.derive_flags({"kind": "run"}, {"no_goal_seek": True})
    assert flags["with_goal_seek"] is False


def test_verification_profile_is_explicit_and_closed(mod):
    assert mod.derive_flags(
        {"kind": "run"}, {"verification_profile": "exhaustive"}
    )["verification_profile"] == "exhaustive"
    with pytest.raises(ValueError, match="verification_profile"):
        mod.derive_flags({"kind": "run"}, {"verification_profile": "unbounded"})


def test_build_stage_defaults_to_usable_first_and_release_is_explicit(mod):
    assert mod.derive_flags({"kind": "run"})["build_stage"] == "draft"
    assert mod.derive_flags(
        {"kind": "run"}, {"build_stage": "release"}
    )["build_stage"] == "release"
    with pytest.raises(ValueError, match="build_stage"):
        mod.derive_flags({"kind": "run"}, {"build_stage": "perfect"})


def test_build_stage_contract_is_aligned_across_schemas_and_native_surfaces():
    flags_schema = json.loads(
        (RUN_BUILD / "schemas/build-flags.schema.json").read_text(encoding="utf-8")
    )
    plan_schema = json.loads(
        (RUN_BUILD / "schemas/build-plan.schema.json").read_text(encoding="utf-8")
    )
    assert flags_schema["properties"]["build_stage"]["default"] == "draft"
    assert "build_stage" in plan_schema["properties"]["flags"]["required"]

    # Claude command と Codex/Skill のどちらから入っても同じ2段階契約を見せる。
    for surface in (COMMAND, RUN_BUILD / "SKILL.md"):
        text = surface.read_text(encoding="utf-8")
        assert "--stage draft|release" in text
        assert "usable-draft" in text
        assert "自動昇格" in text


# --- derive: セクション正本はテンプレート ---------------------------------


def test_run_kind_requires_evaluation_section(mod):
    plan = mod.derive_plan({"kind": "run", "skill_name": "run-x"})
    assert "評価・改善ループ契約" in plan["required_sections"]
    assert "変数化契約" in plan["required_sections"]
    assert plan["template"] == "run.md"


def test_ref_kind_has_no_evaluation_section(mod):
    plan = mod.derive_plan({"kind": "ref", "skill_name": "ref-x"})
    assert "評価・改善ループ契約" not in plan["required_sections"]
    assert "手順" in plan["required_sections"]


def test_knowledge_flag_adds_section_and_scripts(mod):
    plan = mod.derive_plan({"kind": "run", "knowledge_loop": {"pattern": "index-search"}})
    assert "ナレッジループ" in plan["required_sections"]
    ids = {d["id"] for d in plan["required_deliverables"]}
    assert "knowledge-script:search_knowledge.py" in ids
    assert "knowledge-script:build-external-intelligence.py" in ids
    assert "frontmatter:knowledge_loop" in ids


def test_assign_evaluator_template_selected(mod):
    plan = mod.derive_plan({"kind": "assign", "role_suffix": "evaluator"})
    assert plan["template"] == "assign-evaluator.md"


# --- check: ディスク実体が真実 ---------------------------------------------


def _write_skill(tmp_path: Path, body: str, name: str = "run-demo") -> Path:
    d = tmp_path / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


def test_check_detects_missing_evaluation_section(mod, tmp_path):
    plan = mod.derive_plan({"kind": "run", "skill_name": "run-demo"})
    d = _write_skill(tmp_path, "---\nname: run-demo\n---\n\n## 目的と出力契約\n\n本文。\n")
    errs = mod.check_plan(plan, d)
    assert any("評価・改善ループ契約" in e for e in errs)


def test_check_detects_stub_section(mod, tmp_path):
    plan = mod.derive_plan({"kind": "ref", "skill_name": "ref-demo"})
    body = "---\nname: ref-demo\n---\n\n" + "\n\n".join(
        f"## {s}\n\nx" for s in plan["required_sections"]
    )
    # 手順 セクションだけ本文を空にする
    body = body.replace("## 手順\n\nx", "## 手順\n")
    d = _write_skill(tmp_path, body, "ref-demo")
    errs = mod.check_plan(plan, d)
    assert any("stub section" in e and "手順" in e for e in errs)


def test_check_detects_unexpanded_placeholder(mod, tmp_path):
    plan = mod.derive_plan({"kind": "ref", "skill_name": "ref-demo"})
    d = _write_skill(tmp_path, "---\nname: ref-demo\n---\n\n## 手順\n\n{{description}}\n", "ref-demo")
    errs = mod.check_plan(plan, d)
    assert any("unexpanded" in e and "{{description}}" in e for e in errs)


def test_check_allows_uppercase_abstraction_vars_and_meta_dots(mod, tmp_path):
    plan = mod.derive_plan({"kind": "ref", "skill_name": "ref-demo"})
    body = "---\nname: ref-demo\n---\n\n" + "\n\n".join(
        f"## {s}\n\n`{{{{PROJECT_ROOT}}}}` と {{{{...}}}} は許容。" for s in plan["required_sections"]
    )
    d = _write_skill(tmp_path, body, "ref-demo")
    errs = mod.check_plan(plan, d)
    assert not any("unexpanded" in e for e in errs), errs


def test_check_missing_prompt_deliverable(mod, tmp_path):
    plan = mod.derive_plan({"kind": "run", "skill_name": "run-demo", "responsibilities": [{"id": "R1"}]})
    body = "---\nname: run-demo\n---\n\n" + "\n\n".join(
        f"## {s}\n\nx" for s in plan["required_sections"]
    )
    d = _write_skill(tmp_path, body)
    errs = mod.check_plan(plan, d)
    assert any("prompt:R1" in e or "prompts/R1" in e for e in errs)
    (d / "prompts").mkdir()
    (d / "prompts" / "R1-do.md").write_text("x", encoding="utf-8")
    errs = mod.check_plan(plan, d)
    assert not any("prompts/R1" in e for e in errs)


def test_check_pair_evaluator_resolved_from_frontmatter(mod, tmp_path):
    plan = mod.derive_plan({"kind": "run", "skill_name": "run-demo", "generate_pair_evaluator": True})
    body = "---\nname: run-demo\npair: assign-demo-evaluator\n---\n\n" + "\n\n".join(
        f"## {s}\n\nx" for s in plan["required_sections"]
    )
    d = _write_skill(tmp_path, body)
    errs = mod.check_plan(plan, d)
    assert any("assign-demo-evaluator" in e for e in errs)
    pair = tmp_path / "skills" / "assign-demo-evaluator"
    pair.mkdir()
    (pair / "SKILL.md").write_text("---\nname: assign-demo-evaluator\n---\n", encoding="utf-8")
    errs = mod.check_plan(plan, d)
    assert not any("assign-demo-evaluator" in e for e in errs)


def test_check_hook_deliverable_matches_event(mod, tmp_path):
    plan = mod.derive_plan({"kind": "run", "skill_name": "run-demo", "hook_events": ["PostToolUse"]})
    body = "---\nname: run-demo\n---\n\n" + "\n\n".join(
        f"## {s}\n\nx" for s in plan["required_sections"]
    )
    d = _write_skill(tmp_path, body)
    errs = mod.check_plan(plan, d)
    assert any("hook" in e.lower() for e in errs)
    (d / "scripts").mkdir()
    (d / "scripts" / "hook-run-demo-post-tool-use.py").write_text("x", encoding="utf-8")
    errs = mod.check_plan(plan, d)
    assert not any("hook-" in e for e in errs), errs


# --- CLI 契約 ---------------------------------------------------------------


def test_cli_self_test():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr


def test_cli_missing_explicit_brief_with_check_exits_2(tmp_path):
    # 以前は NOTE を出して exit 0 だった。contract の checker argv (--brief … --check --skill-dir …) を
    # brief が消えた後に走らせると、検査しないまま PASS と記録されうる
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(tmp_path / "none.json"), "--check",
         "--skill-dir", str(tmp_path / "none-dir")],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "brief not found" in r.stderr
    assert "Traceback" not in r.stderr
    assert r.stdout == ""


def test_cli_missing_explicit_brief_without_check_exits_2_and_keeps_old_out(tmp_path):
    # --out 付きで exit 0 にすると、前回の build-plan.json が残ったまま使われうる
    out = tmp_path / "build-plan.json"
    out.write_text('{"skill_name": "previous"}\n', encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(tmp_path / "none.json"), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "brief not found" in r.stderr
    assert out.read_text(encoding="utf-8") == '{"skill_name": "previous"}\n'


def test_cli_missing_default_brief_with_check_exits_2(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--skill-dir", str(tmp_path)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert r.returncode == 2
    assert "eval-log/skill-brief.json" in r.stderr


def test_cli_missing_default_brief_without_options_is_note_skip(tmp_path):
    # --brief・--check・--out のどれも無い呼び出しだけは、従来どおり NOTE を出して exit 0
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0
    assert "NOTE" in r.stdout


def test_cli_emit_writes_plan(tmp_path):
    brief = tmp_path / "skill-brief.json"
    brief.write_text(json.dumps({"skill_name": "run-x", "kind": "run"}), encoding="utf-8")
    out = tmp_path / "build-plan.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(brief), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["flags"]["feedback_contract_required"] is True
    assert "評価・改善ループ契約" in plan["required_sections"]


def test_cli_stage_alias_emits_explicit_release_plan(tmp_path):
    brief = tmp_path / "skill-brief.json"
    brief.write_text(json.dumps({"skill_name": "run-x", "kind": "run"}), encoding="utf-8")
    out = tmp_path / "build-plan.json"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(brief), "--stage", "release", "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["flags"]["build_stage"] == "release"


def test_cli_check_fails_on_real_gap(tmp_path):
    """回帰ゲート: 実テンプレ正本を使い、評価セクション欠落が exit 1 になる。"""
    brief = tmp_path / "skill-brief.json"
    brief.write_text(json.dumps({"skill_name": "run-x", "kind": "run"}), encoding="utf-8")
    d = tmp_path / "skills" / "run-x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: run-x\n---\n\n## 目的と出力契約\n\n本文のみ充実で評価系が無い偏り。\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(brief), "--check", "--skill-dir", str(d)],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "評価・改善ループ契約" in r.stderr


# --- check: task-graph engine は写しか、同じ plugin の正本参照で満たす (lint と同じ判定) ---------

ENGINE_NAMES = (
    "extract-ready-set-from-checklist.py",
    "build-self-reflection-entry.py",
    "extract-capability-dependency-graph.py",
    "build-capability-graph-knowledge-entry.py",
)
REAL_TEMPLATES = RUN_BUILD / "templates/task-graph-engine/scripts"


def _fake_builder(tmp_path: Path, monkeypatch, mod) -> Path:
    """tmp_path/plugins/hc を builder の plugin に見立て、正本 4 本を置く。"""
    builder = tmp_path / "plugins/hc/skills/run-build-skill"
    canon = builder / "templates/task-graph-engine/scripts"
    canon.mkdir(parents=True)
    for name in ENGINE_NAMES:
        (canon / name).write_bytes((REAL_TEMPLATES / name).read_bytes())
    monkeypatch.setattr(mod, "SKILL_ROOT", builder)
    return builder


def _engine_skill(skill_dir: Path, refs: list[str]) -> Path:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-x\nscript_refs:\n" + "".join(f"  - {ref}\n" for ref in refs) + "---\nx\n",
        encoding="utf-8",
    )
    return skill_dir


def _engine_gaps(mod, skill_dir: Path) -> list[str]:
    plan = mod.derive_plan({"skill_name": "run-x", "kind": "run", "goal_seek": {"engine": "task-graph"}})
    return sorted(e for e in mod.check_plan(plan, skill_dir) if "missing deliverable: scripts/" in e)


def test_check_accepts_same_plugin_canonical_refs_without_copies(mod, tmp_path, monkeypatch):
    _fake_builder(tmp_path, monkeypatch, mod)
    refs = [f"../run-build-skill/templates/task-graph-engine/scripts/{n}" for n in ENGINE_NAMES]
    skill = _engine_skill(tmp_path / "plugins/hc/skills/run-x", refs)
    # 以前は lint が通る構成でも、ここだけ「missing deliverable」で 4 本とも落ちていた
    assert _engine_gaps(mod, skill) == []


def test_check_reports_only_the_engine_scripts_that_are_neither_copied_nor_referenced(mod, tmp_path, monkeypatch):
    _fake_builder(tmp_path, monkeypatch, mod)
    refs = [f"../run-build-skill/templates/task-graph-engine/scripts/{n}" for n in ENGINE_NAMES[:3]]
    skill = _engine_skill(tmp_path / "plugins/hc/skills/run-x", refs)
    assert _engine_gaps(mod, skill) == [f"missing deliverable: scripts/{ENGINE_NAMES[3]} (source=goal_seek_engine=task-graph (brief.goal_seek.engine))"]


def test_check_does_not_accept_canonical_refs_from_another_plugin(mod, tmp_path, monkeypatch):
    _fake_builder(tmp_path, monkeypatch, mod)
    refs = [f"../../../hc/skills/run-build-skill/templates/task-graph-engine/scripts/{n}" for n in ENGINE_NAMES]
    skill = _engine_skill(tmp_path / "plugins/demo/skills/run-x", refs)
    assert len(_engine_gaps(mod, skill)) == 4


def test_check_still_requires_byte_parity_when_a_copy_exists_beside_the_ref(mod, tmp_path, monkeypatch):
    _fake_builder(tmp_path, monkeypatch, mod)
    refs = [f"../run-build-skill/templates/task-graph-engine/scripts/{n}" for n in ENGINE_NAMES]
    skill = _engine_skill(tmp_path / "plugins/hc/skills/run-x", refs)
    (skill / "scripts").mkdir()
    (skill / "scripts" / ENGINE_NAMES[0]).write_text("# 古いまま残った写し\n", encoding="utf-8")
    plan = mod.derive_plan({"skill_name": "run-x", "kind": "run", "goal_seek": {"engine": "task-graph"}})
    assert any("byte drift" in e and ENGINE_NAMES[0] in e for e in mod.check_plan(plan, skill))


# --- 形の崩れた入力は traceback (exit 1 = 欠落ありと区別できない) でなく exit 2 ----------------


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd,
    )


def _assert_invalid_input(r: subprocess.CompletedProcess, message: str) -> None:
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "Traceback" not in r.stderr
    assert message in r.stderr
    assert "OK:" not in r.stdout
    assert not r.stdout.lstrip().startswith("{")  # plan を出さない


def _brief_file(tmp_path: Path, brief: object) -> Path:
    path = tmp_path / "skill-brief.json"
    path.write_text(json.dumps(brief), encoding="utf-8")
    return path


def test_cli_brief_that_is_not_an_object_exits_2(tmp_path):
    _assert_invalid_input(_run_cli("--brief", str(_brief_file(tmp_path, [1]))), "brief must be a JSON object")


def test_cli_brief_that_is_not_an_object_exits_2_in_update_mode(tmp_path):
    # update は derive の前に preserve_update_runtime_profile が brief を読む
    d = _write_skill(tmp_path, "---\nname: run-x\n---\n")
    _assert_invalid_input(
        _run_cli("--brief", str(_brief_file(tmp_path, [1])), "--mode", "update", "--skill-dir", str(d)),
        "brief must be a JSON object",
    )


@pytest.mark.parametrize("field", ["responsibilities", "hook_events", "allowed_tools", "allowed-tools"])
def test_cli_brief_with_a_non_array_iterable_field_exits_2(tmp_path, field):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run", "hook_events": ["PostToolUse"], field: 5})
    _assert_invalid_input(_run_cli("--brief", str(brief)), f"brief.{field} must be")


def test_derive_plan_rejects_non_array_responsibilities(mod):
    with pytest.raises(ValueError, match="brief.responsibilities must be array"):
        mod.derive_plan({"kind": "run", "responsibilities": 5})
    # 空値は従来どおり「無い」と同じ扱い。allowed-tools は frontmatter と同じ文字列も読む
    assert mod.derive_plan({"kind": "run", "responsibilities": None})["flags"]["with_prompts"] is False
    assert mod.derive_plan({"kind": "run", "allowed-tools": "Read, Skill"})["acceptance_tier"] == "live"


@pytest.mark.parametrize("extra", [[], ["--stage", "draft"]], ids=["flags-only", "flags-and-stage"])
def test_cli_flags_that_are_not_an_object_exit_2(tmp_path, extra):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    _assert_invalid_input(_run_cli("--brief", str(brief), "--flags", "[1]", *extra), "--flags must be a JSON object")


def test_derive_flags_rejects_non_object_cli_flags(mod):
    with pytest.raises(ValueError, match="--flags must be a JSON object"):
        mod.derive_flags({"kind": "run"}, [1])


def test_cli_check_with_skill_md_that_is_a_directory_exits_2(tmp_path):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    d = tmp_path / "skills" / "run-x"
    (d / "SKILL.md").mkdir(parents=True)
    _assert_invalid_input(_run_cli("--brief", str(brief), "--check", "--skill-dir", str(d)), "SKILL.md を UTF-8")


def test_cli_check_with_skill_md_that_is_not_utf8_exits_2(tmp_path):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    d = tmp_path / "skills" / "run-x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_bytes(b"---\nname: x\n---\n\xff\xfe\n")
    _assert_invalid_input(_run_cli("--brief", str(brief), "--check", "--skill-dir", str(d)), "SKILL.md を UTF-8")


def test_cli_check_with_missing_skill_md_is_still_a_gap(tmp_path):
    # SKILL.md が無いのは build の欠落なので、従来どおり exit 1 (FAIL)
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    r = _run_cli("--brief", str(brief), "--check", "--skill-dir", str(tmp_path / "skills" / "run-x"))
    assert r.returncode == 1
    assert "SKILL.md not found" in r.stderr


# --- CLI: 未知の引数を黙って無視しない・--help がある ----------------------------------------


def test_cli_rejects_a_misspelled_option_instead_of_emitting_a_plan(tmp_path):
    # 以前は --chek を無視して plan を出し exit 0 (検査しないまま成功) だった
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    r = _run_cli("--brief", str(brief), "--chek")
    assert r.returncode == 2
    assert "unrecognized arguments: --chek" in r.stderr
    assert r.stdout == ""


def test_cli_does_not_expand_option_abbreviations(tmp_path):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    r = _run_cli("--brief", str(brief), "--che", "--skill-dir", str(tmp_path))
    assert r.returncode == 2
    assert r.stdout == ""


def test_cli_brief_without_a_value_exits_2_instead_of_using_the_default(tmp_path):
    # 以前は最後の --brief を無視して既定の eval-log/skill-brief.json に落ちていた
    default = tmp_path / "eval-log" / "skill-brief.json"
    default.parent.mkdir()
    default.write_text(json.dumps({"skill_name": "run-default", "kind": "run"}), encoding="utf-8")
    r = _run_cli("--brief", cwd=tmp_path)
    assert r.returncode == 2
    assert "--brief" in r.stderr
    assert r.stdout == ""


def test_cli_help_lists_every_option_and_exits_0():
    r = _run_cli("--help")
    assert r.returncode == 0, r.stderr
    for option in ("--brief", "--out", "--check", "--skill-dir", "--mode", "--stage", "--flags", "--self-test"):
        assert option in r.stdout
    assert "exit: 0=OK / 1=" in r.stdout


def test_cli_accepts_every_argv_shape_its_callers_pass(tmp_path):
    """呼び出し側が渡す argv は全部受け付ける (未知の引数として exit 2 にしない)。

    - run-build-skill SKILL.md Step 1: --brief … --out … [--stage release] [--mode update --skill-dir …]
    - SKILL.md Step 4 と derive-verification-contract.py の checker argv: --brief … --check --skill-dir … [--mode update]
    """
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    d = _write_skill(tmp_path, "---\nname: run-x\n---\n\n## 目的と出力契約\n\n本文。\n", "run-x")
    out = tmp_path / "eval-log" / "build-plan.json"
    shapes = [
        ["--brief", str(brief), "--out", str(out)],
        ["--brief", str(brief), "--out", str(out), "--stage", "release"],
        ["--brief", str(brief), "--out", str(out), "--mode", "update", "--skill-dir", str(d)],
        ["--brief", str(brief), "--flags", '{"no_goal_seek": true}'],
        ["--brief", str(brief), "--check", "--skill-dir", str(d)],
        ["--brief", str(brief), "--check", "--skill-dir", str(d), "--mode", "update"],
        ["--self-test"],
    ]
    for argv in shapes:
        r = _run_cli(*argv)
        # check は最小の SKILL.md なので欠落あり (1)。どれも usage error (2) や traceback にはならない
        assert r.returncode in (0, 1), (argv, r.returncode, r.stderr)
        assert "Traceback" not in r.stderr, argv
        assert "unrecognized arguments" not in r.stderr, argv


def test_cli_plan_output_is_unchanged_and_matches_out(tmp_path, mod):
    brief_doc = {"skill_name": "run-x", "kind": "run", "responsibilities": [{"id": "R1"}]}
    brief = _brief_file(tmp_path, brief_doc)
    out = tmp_path / "build-plan.json"
    r = _run_cli("--brief", str(brief), "--out", str(out))
    assert r.returncode == 0, r.stderr
    expected = json.dumps(mod.derive_plan(brief_doc), ensure_ascii=False, indent=2)
    assert r.stdout == expected + "\n"
    assert out.read_text(encoding="utf-8") == expected + "\n"


# --- check: 依存する lint を読めないときは「参照なし」に倒さず exit 2 ------------------------


def _builder_copy(tmp_path: Path) -> tuple[Path, Path]:
    """tmp_path/plugins/hc に builder (script・kind template・combinator・engine 正本) を置き、
    写しを持たない task-graph skill を作る。

    kind template と combinator も写す: 必須セクションの正本が無い builder は plan を作れず exit 2 になる
    (以前は空の必須セクションで先へ進んでいた)。
    """
    builder = tmp_path / "plugins/hc/skills/run-build-skill"
    (builder / "scripts").mkdir(parents=True)
    (builder / "scripts" / SCRIPT.name).write_bytes(SCRIPT.read_bytes())
    lint = RUN_BUILD / "scripts" / "lint-capability-graph-knowledge.py"
    (builder / "scripts" / lint.name).write_bytes(lint.read_bytes())
    (builder / "templates/combinators").mkdir(parents=True)
    for src in (RUN_BUILD / "templates").glob("*.md"):
        (builder / "templates" / src.name).write_bytes(src.read_bytes())
    for src in (RUN_BUILD / "templates/combinators").glob("*.patch"):
        (builder / "templates/combinators" / src.name).write_bytes(src.read_bytes())
    canon = builder / "templates/task-graph-engine/scripts"
    canon.mkdir(parents=True)
    for name in ENGINE_NAMES:
        (canon / name).write_bytes((REAL_TEMPLATES / name).read_bytes())
    refs = [f"../run-build-skill/templates/task-graph-engine/scripts/{n}" for n in ENGINE_NAMES]
    skill = _engine_skill(tmp_path / "plugins/hc/skills/run-x", refs)
    return builder, skill


def _check_copy(tmp_path: Path, builder: Path, skill: Path) -> subprocess.CompletedProcess:
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run", "goal_seek": {"engine": "task-graph"}})
    return subprocess.run(
        [sys.executable, str(builder / "scripts" / SCRIPT.name), "--brief", str(brief), "--check", "--skill-dir", str(skill)],
        capture_output=True, text=True,
    )


def test_cli_check_uses_the_peer_lint_when_it_loads(tmp_path):
    builder, skill = _builder_copy(tmp_path)
    r = _check_copy(tmp_path, builder, skill)
    # 正本参照で engine 4 本は満たす。残りは最小 SKILL.md の欠落 (exit 1) で、engine の欠落は出ない
    assert r.returncode == 1, r.stderr
    assert "missing deliverable: scripts/" not in r.stderr


@pytest.mark.parametrize("breakage", ["syntax-error", "deleted", "no-function"])
def test_cli_check_with_an_unusable_peer_lint_exits_2(tmp_path, breakage):
    builder, skill = _builder_copy(tmp_path)
    lint = builder / "scripts" / "lint-capability-graph-knowledge.py"
    if breakage == "syntax-error":
        lint.write_text("def (\n", encoding="utf-8")
    elif breakage == "deleted":
        lint.unlink()
    else:
        lint.write_text("x = 1\n", encoding="utf-8")
    r = _check_copy(tmp_path, builder, skill)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "Traceback" not in r.stderr
    assert "依存する lint を使えない" in r.stderr
    assert "OK:" not in r.stdout


def test_same_plugin_refs_rejects_a_lint_that_returns_a_string(mod, tmp_path, monkeypatch):
    # 文字列が返ると `name in refs` が部分一致になり、写しの欠落を見逃す (PASS 側に倒れる)
    builder = _fake_builder(tmp_path, monkeypatch, mod)
    (builder / "scripts").mkdir()
    (builder / "scripts" / "lint-capability-graph-knowledge.py").write_text(
        "def canonical_engine_refs(skill, root):\n    return ('" + "".join(ENGINE_NAMES) + "', set())\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "__file__", str(builder / "scripts" / SCRIPT.name))
    skill = _engine_skill(tmp_path / "plugins/hc/skills/run-x", [])
    plan = mod.derive_plan({"skill_name": "run-x", "kind": "run", "goal_seek": {"engine": "task-graph"}})
    with pytest.raises(mod.CheckerDependencyError, match="set を返さない"):
        mod.check_plan(plan, skill)


# --- --out は同じ dir の一時ファイルに書いてから置き換える -----------------------------------


def test_write_atomic_replaces_and_leaves_no_temp_file(mod, tmp_path):
    out = tmp_path / "eval-log" / "build-plan.json"
    mod._write_atomic(out, "first\n")
    mod._write_atomic(out, "second\n")
    assert out.read_text(encoding="utf-8") == "second\n"
    assert sorted(p.name for p in out.parent.iterdir()) == ["build-plan.json"]


def test_write_atomic_keeps_the_previous_plan_when_the_replace_fails(mod, tmp_path, monkeypatch):
    out = tmp_path / "build-plan.json"
    out.write_text("previous\n", encoding="utf-8")

    def _fail(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(mod.os, "replace", _fail)
    with pytest.raises(OSError, match="disk full"):
        mod._write_atomic(out, "next\n")
    assert out.read_text(encoding="utf-8") == "previous\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["build-plan.json"]


def test_cli_out_that_cannot_be_written_exits_2(tmp_path):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    target = tmp_path / "is-a-dir"
    target.mkdir()
    _assert_invalid_input(_run_cli("--brief", str(brief), "--out", str(target)), "--out に書けない")
    assert sorted(p.name for p in target.iterdir()) == []
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


# --- header: 宣言が実装と一致する --------------------------------------------------------------


def test_header_declares_every_option_exit_codes_write_scope_and_peer_dependency():
    header = SCRIPT.read_text(encoding="utf-8").split("# ///", 2)[1]
    for option in ("--mode", "--stage", "--self-test", "--flags", "--check", "--skill-dir", "--out", "--help"):
        assert option in header, option
    assert "#   - exit: 0=" in header and "1=--check で欠落あり" in header and "2=usage error" in header
    assert "# write-scope: --out の指定先" in header
    assert "# dependencies: [lint-capability-graph-knowledge.py]" in header


def test_cli_empty_brief_value_is_not_read_as_the_default(tmp_path):
    default = tmp_path / "eval-log" / "skill-brief.json"
    default.parent.mkdir()
    default.write_text(json.dumps({"skill_name": "run-default", "kind": "run"}), encoding="utf-8")
    r = _run_cli("--brief", "", cwd=tmp_path)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "Traceback" not in r.stderr
    assert "run-default" not in r.stdout


# --- (a) template を引けない brief は空の必須セクションで通さない (fail-closed) ------------------


def _all_sections_skill(tmp_path: Path, plan: dict, name: str, fm: str = "") -> Path:
    body = f"---\nname: {name}\n{fm}---\n\n" + "\n\n".join(f"## {s}\n\nx" for s in plan["required_sections"])
    return _write_skill(tmp_path, body, name)


@pytest.mark.parametrize("kind", [None, "", "rn", "Run", "assignn"], ids=["missing", "empty", "typo", "case", "typo-assign"])
def test_derive_plan_rejects_a_missing_or_unknown_kind(mod, kind):
    brief = {"skill_name": "run-x"} if kind is None else {"skill_name": "run-x", "kind": kind}
    with pytest.raises(ValueError, match="brief.kind must be one of"):
        mod.derive_plan(brief)


def test_cli_check_with_a_misspelled_kind_exits_2_instead_of_passing(tmp_path):
    # 以前は template を引けず必須セクションが空になり、見出しの無い SKILL.md でも OK (exit 0) だった
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "rn"})
    d = _write_skill(tmp_path, "---\nname: run-x\n---\n\n本文だけ。\n", "run-x")
    _assert_invalid_input(_run_cli("--brief", str(brief), "--check", "--skill-dir", str(d)), "brief.kind must be one of")


@pytest.mark.parametrize("role", ["absent", None, ""])
def test_assign_without_role_suffix_uses_the_generator_template(mod, role):
    # render-combinators.py selected_patches の `args.role_suffix or "generator"` と同じ既定
    brief = {"skill_name": "assign-x", "kind": "assign"}
    if role != "absent":
        brief["role_suffix"] = role
    plan = mod.derive_plan(brief)
    assert plan["template"] == "assign-generator.md"
    assert plan["role_suffix"] == "generator"
    expected = mod._template_headings(RUN_BUILD / "templates/assign-generator.md")
    assert plan["required_sections"][: len(expected)] == expected and expected


@pytest.mark.parametrize("role", ["contributor", "delegate", "workflow"])
def test_assign_role_suffix_without_a_template_exits_2(mod, tmp_path, role):
    # skill-brief.schema.json は contributor / delegate を許すが、assign の template は generator / evaluator だけ
    with pytest.raises(ValueError, match="has no assign template"):
        mod.derive_plan({"skill_name": "assign-x", "kind": "assign", "role_suffix": role})
    brief = _brief_file(tmp_path, {"skill_name": "assign-x", "kind": "assign", "role_suffix": role})
    d = _write_skill(tmp_path, "---\nname: assign-x\n---\n\n本文だけ。\n", "assign-x")
    _assert_invalid_input(_run_cli("--brief", str(brief), "--check", "--skill-dir", str(d)), "has no assign template")


@pytest.mark.parametrize(
    "brief",
    [
        {"skill_name": "assign-x-evaluator", "kind": "assign"},
        {"skill_name": "assign-x-evaluator", "kind": "assign", "role_suffix": "generator"},
        {"skill_name": "assign-x-generator", "kind": "assign", "role_suffix": "evaluator"},
    ],
    ids=["default-vs-evaluator-name", "generator-vs-evaluator-name", "evaluator-vs-generator-name"],
)
def test_assign_role_that_contradicts_the_skill_name_suffix_exits_2(mod, brief):
    # 名前は -evaluator なのに generator の template で検査すると、違う要求で PASS / FAIL を出す
    with pytest.raises(ValueError, match="食い違う"):
        mod.derive_plan(brief)


def test_assign_role_that_matches_the_skill_name_suffix_is_accepted(mod):
    plan = mod.derive_plan({"skill_name": "assign-x-evaluator", "kind": "assign", "role_suffix": "evaluator"})
    assert plan["template"] == "assign-evaluator.md"
    assert plan["required_sections"]


def test_missing_or_headingless_kind_template_is_a_dependency_error(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "TEMPLATES_DIR", tmp_path)
    with pytest.raises(mod.CheckerDependencyError, match="kind template が無い"):
        mod.derive_plan({"skill_name": "run-x", "kind": "run"})
    (tmp_path / "run.md").write_text("---\nname: x\n---\n\n本文だけで ## 見出しが無い\n", encoding="utf-8")
    with pytest.raises(mod.CheckerDependencyError, match="## 見出しが無い"):
        mod.derive_plan({"skill_name": "run-x", "kind": "run"})


def test_missing_combinator_patch_is_a_dependency_error(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "COMBINATORS_DIR", tmp_path)
    with pytest.raises(mod.CheckerDependencyError, match="combinator patch が無い"):
        mod.derive_plan({"skill_name": "run-x", "kind": "run"})  # with_goal_seek の patch を読む


def test_cli_check_with_a_deleted_kind_template_exits_2(tmp_path):
    builder, skill = _builder_copy(tmp_path)
    (builder / "templates" / "run.md").unlink()
    r = _check_copy(tmp_path, builder, skill)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "Traceback" not in r.stderr
    assert "error: kind template が無い" in r.stderr
    assert "OK:" not in r.stdout


# --- (b) prompt_required: false の責務は prompts を求めない --------------------------------------


def test_prompt_required_false_is_exempt_from_prompts(mod, tmp_path):
    # skill-brief.schema.json と validate-build-trace.py の per_responsibility 集合と同じ規則
    brief = {
        "skill_name": "run-demo",
        "kind": "run",
        "responsibilities": [{"id": "R1"}, {"id": "R2", "prompt_required": False}, {"id": "R3", "prompt_required": True}],
    }
    plan = mod.derive_plan(brief)
    assert [d["id"] for d in plan["required_deliverables"] if d["id"].startswith("prompt:")] == ["prompt:R1", "prompt:R3"]
    d = _all_sections_skill(tmp_path, plan, "run-demo")
    (d / "prompts").mkdir()
    for rid in ("R1", "R3"):
        (d / "prompts" / f"{rid}-do.md").write_text("x", encoding="utf-8")
    assert not any("prompts/" in e for e in mod.check_plan(plan, d))


@pytest.mark.parametrize("value", ["false", 0, None])
def test_prompt_required_that_is_not_a_bool_exits_2(mod, value):
    brief = {"kind": "run", "responsibilities": [{"id": "R1", "prompt_required": value}]}
    with pytest.raises(ValueError, match="prompt_required must be true or false"):
        mod.derive_plan(brief)


# --- (c) acceptance_tier は allowed-tools を inline・flow・block のどれでも読む --------------------


ALLOWED_TOOLS_FORMS = {
    "inline": "allowed-tools: Read, Skill\n",
    "inline-space": "allowed-tools: Read Skill\n",
    "flow": "allowed-tools: [Read, \"Bash(git diff *)\", Skill]\n",
    "flow-multiline": "allowed-tools: [Read,\n  Skill]\n",
    "block": "allowed-tools:\n  - Read\n  - 'Bash(python3 *)'  # 検査用\n  - Skill\n",
    "block-unindented": "allowed-tools:\n- Read\n- Skill\n",
}


@pytest.mark.parametrize("form", sorted(ALLOWED_TOOLS_FORMS))
def test_acceptance_tier_reads_allowed_tools_in_every_yaml_form(mod, tmp_path, form):
    # 以前は 1 行の scalar しか読まず、flow / block の Skill を見落として static 宣言を通していた
    plan = mod.derive_plan({"skill_name": "ref-x", "kind": "ref"})
    fm = "kind: ref\nacceptance_tier: static\n" + ALLOWED_TOOLS_FORMS[form] + "description: x\n"
    d = _all_sections_skill(tmp_path, plan, "ref-x", fm)
    tools = mod._frontmatter_allowed_tools(d.joinpath("SKILL.md").read_text(encoding="utf-8"))
    assert "Skill" in {mod._tool_base(t) for t in tools}, tools
    assert any("acceptance_tier declared=static < derived=live" in e for e in mod.check_plan(plan, d))


def test_acceptance_tier_static_is_kept_when_no_live_tool_is_listed(mod, tmp_path):
    plan = mod.derive_plan({"skill_name": "ref-x", "kind": "ref"})
    fm = "kind: ref\nacceptance_tier: static\nallowed-tools:\n  - Read\n  - Bash(git diff *)\n"
    d = _all_sections_skill(tmp_path, plan, "ref-x", fm)
    assert not any("acceptance_tier" in e for e in mod.check_plan(plan, d))


# --- [低] 個別の取りこぼし -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "filename"),
    [("pre_compact", "hook-run-demo-pre-compact.py"), ("PreCompact", "hook-run-demo-pre_compact.py")],
)
def test_check_hook_event_matches_regardless_of_dash_or_underscore(mod, tmp_path, event, filename):
    # 以前は must_contain 側だけ `_` を残し、pre_compact が hook-pre-compact.py に一致しなかった
    plan = mod.derive_plan({"kind": "run", "skill_name": "run-demo", "hook_events": [event]})
    d = _all_sections_skill(tmp_path, plan, "run-demo")
    (d / "scripts").mkdir()
    (d / "scripts" / filename).write_text("x", encoding="utf-8")
    assert not any("hook-" in e for e in mod.check_plan(plan, d))


@pytest.mark.parametrize("event", ["", "  ", 5])
def test_empty_or_non_string_hook_event_exits_2(mod, event):
    # 空の event は must_contain が空になり、どの hook-*.py でも満たしてしまう
    with pytest.raises(ValueError, match="must be a non-empty string"):
        mod.derive_plan({"kind": "run", "hook_events": [event]})


@pytest.mark.parametrize("rid", ["../SKILL", "R1/../../x", "", "r1", "R1_do"])
def test_responsibility_id_outside_the_schema_pattern_exits_2(mod, tmp_path, rid):
    # id は prompts/<id>*.md の glob に入る。"../SKILL" だと SKILL.md 自身が prompt の実在として数えられていた
    with pytest.raises(ValueError, match="must match"):
        mod.derive_plan({"kind": "run", "responsibilities": [{"id": rid}]})
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run", "responsibilities": [{"id": rid}]})
    _assert_invalid_input(_run_cli("--brief", str(brief)), "must match")


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        ('{"no_goal_seek": "false"}', "--flags.no_goal_seek must be true or false"),
        ('{"with_prompts": 1}', "--flags.with_prompts must be true or false"),
        ('{"no_goal_seeek": true}', "--flags has unknown keys: ['no_goal_seeek']"),
        ('{"build_stage": 1}', "--flags.build_stage must be a string"),
    ],
    ids=["string-bool", "int-bool", "unknown-key", "non-string-stage"],
)
def test_cli_flags_with_a_wrong_type_or_unknown_key_exits_2(tmp_path, flags, message):
    # 以前は "false" を真と読み (opt-out の意図と逆)、綴り違いの key は黙って捨てていた
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    _assert_invalid_input(_run_cli("--brief", str(brief), "--flags", flags), message)


@pytest.mark.parametrize("mode", ["create", "update"])
def test_string_goal_seek_exits_2_in_create_and_update_alike(tmp_path, mode):
    # 以前は create では「無指定」と読んで inline へ倒れ、update だけ exit 2 だった
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run", "goal_seek": "task-graph"})
    d = _write_skill(tmp_path, "---\nname: run-x\n---\n", "run-x")
    extra = ["--mode", "update", "--skill-dir", str(d)] if mode == "update" else []
    _assert_invalid_input(_run_cli("--brief", str(brief), *extra), "brief.goal_seek must be an object")


def test_frontmatter_value_containing_three_dashes_does_not_cut_the_frontmatter(mod, tmp_path):
    # 以前は split('---') で `a---b` の途中から本文扱いになり、後ろの key を見落としていた
    plan = mod.derive_plan({"skill_name": "run-x", "kind": "run", "knowledge_loop": {"pattern": "index-search"}})
    fm = "description: a---b\nkind: run\nacceptance_tier: static\nknowledge_loop:\n  pattern: index-search\n"
    d = _all_sections_skill(tmp_path, plan, "run-x", fm)
    text = (d / "SKILL.md").read_text(encoding="utf-8")
    assert {"description", "kind", "acceptance_tier", "knowledge_loop"} <= mod._parse_frontmatter_keys(text)
    assert mod._frontmatter_value(text, "description") == "a---b"
    errs = mod.check_plan(plan, d)
    assert not any("frontmatter key: knowledge_loop" in e for e in errs), errs
    assert any("acceptance_tier declared=static < derived=fork" in e for e in errs), errs


def test_cli_check_with_a_symlinked_skill_md_exits_2_like_update(tmp_path):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    real = tmp_path / "elsewhere.md"
    real.write_text("---\nname: run-x\n---\n", encoding="utf-8")
    d = tmp_path / "skills" / "run-x"
    d.mkdir(parents=True)
    (d / "SKILL.md").symlink_to(real)
    _assert_invalid_input(_run_cli("--brief", str(brief), "--check", "--skill-dir", str(d)), "symlink")
    _assert_invalid_input(
        _run_cli("--brief", str(brief), "--mode", "update", "--skill-dir", str(d)), "missing or unsafe"
    )


def test_cli_check_without_skill_dir_does_not_write_out(tmp_path):
    # 以前は plan を --out に書いてから usage error にしていた
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    out = tmp_path / "eval-log" / "build-plan.json"
    r = _run_cli("--brief", str(brief), "--check", "--out", str(out))
    assert r.returncode == 2
    assert "--check には --skill-dir" in r.stderr
    assert not out.exists() and not out.parent.exists()


def test_cli_empty_out_is_a_usage_error(tmp_path):
    # 以前は --out '' を「指定なし」と読み、何も書かずに exit 0 だった
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    r = _run_cli("--brief", str(brief), "--out", "")
    assert r.returncode == 2
    assert "--out には空でないパス" in r.stderr
    assert r.stdout == ""


def test_cli_check_that_exits_2_keeps_the_previous_out(tmp_path):
    brief = _brief_file(tmp_path, {"skill_name": "run-x", "kind": "run"})
    d = tmp_path / "skills" / "run-x"
    (d / "SKILL.md").mkdir(parents=True)  # 読めない SKILL.md
    out = tmp_path / "build-plan.json"
    out.write_text("previous\n", encoding="utf-8")
    _assert_invalid_input(
        _run_cli("--brief", str(brief), "--check", "--skill-dir", str(d), "--out", str(out)), "SKILL.md を UTF-8"
    )
    assert out.read_text(encoding="utf-8") == "previous\n"


def test_cli_check_with_a_gap_still_writes_the_plan_to_out(tmp_path, mod):
    brief_doc = {"skill_name": "run-x", "kind": "run"}
    brief = _brief_file(tmp_path, brief_doc)
    d = _write_skill(tmp_path, "---\nname: run-x\n---\n\n## 目的と出力契約\n\n本文。\n", "run-x")
    out = tmp_path / "build-plan.json"
    r = _run_cli("--brief", str(brief), "--check", "--skill-dir", str(d), "--out", str(out))
    assert r.returncode == 1, r.stderr
    assert out.read_text(encoding="utf-8") == json.dumps(mod.derive_plan(brief_doc), ensure_ascii=False, indent=2) + "\n"


@pytest.mark.parametrize("where", ["brief", "flags", "update-deepcopy"])
def test_cli_deeply_nested_json_exits_2_without_a_traceback(tmp_path, where):
    deep = "[" * 100000 + "]" * 100000
    shallow_but_deep_for_deepcopy = "[" * 600 + "]" * 600
    path = tmp_path / "skill-brief.json"
    out = tmp_path / "build-plan.json"
    if where == "brief":
        path.write_text('{"skill_name": "run-x", "kind": "run", "extra": ' + deep + "}", encoding="utf-8")
        r = _run_cli("--brief", str(path), "--out", str(out))
    elif where == "flags":
        path.write_text(json.dumps({"skill_name": "run-x", "kind": "run"}), encoding="utf-8")
        r = _run_cli("--brief", str(path), "--flags", '{"x": ' + deep + "}", "--out", str(out))
    else:
        path.write_text(
            '{"skill_name": "run-x", "kind": "run", "extra": ' + shallow_but_deep_for_deepcopy + "}", encoding="utf-8"
        )
        d = _write_skill(tmp_path, "---\nname: run-x\n---\n", "run-x")
        r = _run_cli("--brief", str(path), "--mode", "update", "--skill-dir", str(d), "--out", str(out))
    _assert_invalid_input(r, "JSON の入れ子が深すぎる")
    assert not out.exists()


@pytest.mark.parametrize(
    "lint_body",
    [
        "raise KeyError('broken at import')\n",
        "def canonical_engine_refs(skill, root):\n    return undefined_name\n",
        "import sys\nsys.exit(3)\n",
    ],
    ids=["key-error", "name-error", "sys-exit"],
)
def test_cli_check_with_a_peer_lint_that_raises_anything_exits_2(tmp_path, lint_body):
    # 以前は except の列挙に無い NameError・KeyError・SystemExit が traceback か exit 3 で抜けていた
    builder, skill = _builder_copy(tmp_path)
    (builder / "scripts" / "lint-capability-graph-knowledge.py").write_text(lint_body, encoding="utf-8")
    r = _check_copy(tmp_path, builder, skill)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "Traceback" not in r.stderr
    assert "依存する lint を使えない" in r.stderr


def test_header_declares_templates_combinators_agent_dirs_and_mkdir():
    header = SCRIPT.read_text(encoding="utf-8").split("# ///", 2)[1]
    for needle in ("templates/<kind>.md", "templates/combinators/*.patch", "templates/task-graph-engine/scripts",
                   "<plugin>/agents/*.md", ".claude/agents/*.md", "mkdir -p"):
        assert needle in header, needle
