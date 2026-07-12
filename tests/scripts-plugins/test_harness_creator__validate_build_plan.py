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


def test_cli_missing_brief_is_note_skip(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--brief", str(tmp_path / "none.json"), "--check",
         "--skill-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
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
