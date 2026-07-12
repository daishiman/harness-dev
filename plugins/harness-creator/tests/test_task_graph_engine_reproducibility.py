from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "plugins/harness-creator/skills/run-build-skill"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATE = _load("validate_build_plan_task_graph_test", SKILL_ROOT / "scripts/validate-build-plan.py")
RENDER = _load("render_combinators_task_graph_test", SKILL_ROOT / "scripts/render-combinators.py")
LINT = _load(
    "lint_capability_graph_task_graph_test",
    SKILL_ROOT / "scripts/lint-capability-graph-knowledge.py",
)


def _brief() -> dict:
    return {
        "skill_name": "run-repro-graph",
        "kind": "run",
        "goal_seek": {"engine": "task-graph"},
    }


def _skill_md() -> str:
    return """---
name: run-repro-graph
kind: run
goal_seek:
  engine: inline
---

# run-repro-graph

## 目的と出力契約

本文。
"""


def _snapshot(skill_dir: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(skill_dir)): path.read_bytes()
        for path in sorted(skill_dir.rglob("*"))
        if path.is_file()
    }


def test_same_brief_derives_same_machine_readable_plan() -> None:
    first = VALIDATE.derive_plan(_brief())
    second = VALIDATE.derive_plan(json.loads(json.dumps(_brief())))

    assert first == second
    assert first["goal_seek_engine"] == "task-graph"
    assert first["engine_profile"] == "checklist-graph"
    assert first["full_task_spec_graph"] is False
    assert "execution-envelope-state-projection" in first["capability_gaps"]
    copies = [
        item
        for item in first["required_deliverables"]
        if item["type"] == "template-copy"
    ]
    assert [item["path"] for item in copies] == [
        f"scripts/{name}" for name in VALIDATE.TASK_GRAPH_ENGINE_SCRIPTS
    ]


def test_materialize_twice_is_byte_identical_and_sets_fail_closed_profile(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills/run-repro-graph"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(_skill_md(), encoding="utf-8")

    first_paths = RENDER.materialize_task_graph_engine(_brief(), skill_dir, SKILL_ROOT / "templates")
    first = _snapshot(skill_dir)
    second_paths = RENDER.materialize_task_graph_engine(_brief(), skill_dir, SKILL_ROOT / "templates")
    second = _snapshot(skill_dir)

    assert first_paths == second_paths
    assert first == second
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "  engine: task-graph" in text
    assert "  engine_profile: checklist-graph" in text
    assert "  full_task_spec_graph: false" in text
    for name in VALIDATE.TASK_GRAPH_ENGINE_SCRIPTS:
        assert (skill_dir / "scripts" / name).read_bytes() == (
            SKILL_ROOT / "templates/task-graph-engine/scripts" / name
        ).read_bytes()


def test_check_detects_missing_and_byte_drift(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills/run-repro-graph"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(_skill_md(), encoding="utf-8")
    plan = VALIDATE.derive_plan(_brief())

    before = VALIDATE.check_plan(plan, skill_dir)
    assert any("ready-set-from-checklist.py" in error and "missing" in error for error in before)
    assert any("engine_profile" in error for error in before)

    RENDER.materialize_task_graph_engine(_brief(), skill_dir, SKILL_ROOT / "templates")
    after = VALIDATE.check_plan(plan, skill_dir)
    assert not any("task-graph-engine:" in error for error in after)
    assert not any("frontmatter value mismatch" in error for error in after)

    drifted = skill_dir / "scripts/ready-set-from-checklist.py"
    drifted.write_bytes(drifted.read_bytes() + b"\n# drift\n")
    drift_errors = VALIDATE.check_plan(plan, skill_dir)
    assert any("byte drift: scripts/ready-set-from-checklist.py" in error for error in drift_errors)

    drifted.unlink()
    missing_errors = VALIDATE.check_plan(plan, skill_dir)
    assert any("missing deliverable: scripts/ready-set-from-checklist.py" in error for error in missing_errors)


def test_non_task_graph_brief_materializes_nothing(tmp_path: Path) -> None:
    brief = {"skill_name": "run-inline", "kind": "run", "goal_seek": {"engine": "inline"}}
    assert RENDER.materialize_task_graph_engine(brief, tmp_path, SKILL_ROOT / "templates") == []
    assert not (tmp_path / "scripts").exists()


def test_engine_defaults_to_task_graph_for_loop_kind_without_explicit_engine() -> None:
    # loop kind + goal_seek 無指定 → 既定で task-graph (量産ハーネスは既定で依存順駆動)。
    for brief in (
        {"skill_name": "run-default", "kind": "run"},
        {"skill_name": "wrap-default", "kind": "wrap", "goal_seek": {"max_loops": 3}},
    ):
        plan = VALIDATE.derive_plan(brief)
        assert plan["goal_seek_engine"] == "task-graph", brief
        assert plan["engine_profile"] == "checklist-graph"
        assert plan["full_task_spec_graph"] is False
        assert RENDER._brief_requests_task_graph(brief) is True
        engine_items = [
            d for d in plan["required_deliverables"]
            if d.get("id") == "frontmatter:goal_seek.engine"
        ]
        assert engine_items and "default" in engine_items[0]["source"]


def test_engine_default_does_not_apply_to_non_loop_or_opted_out() -> None:
    # 非 loop kind は対象外。
    ref_plan = VALIDATE.derive_plan({"skill_name": "ref-doc", "kind": "ref"})
    assert ref_plan["goal_seek_engine"] == ""
    assert RENDER._brief_requests_task_graph({"skill_name": "ref-doc", "kind": "ref"}) is False
    # 明示 inline は opt-out (defaulting は明示値を上書きしない)。
    inline_brief = {"skill_name": "run-inline", "kind": "run", "goal_seek": {"engine": "inline"}}
    inline_plan = VALIDATE.derive_plan(inline_brief)
    assert inline_plan["goal_seek_engine"] == "inline"
    assert inline_plan["engine_profile"] == ""
    assert RENDER._brief_requests_task_graph(inline_brief) is False
    # --no-goal-seek opt-out 時は goal-seek 配線ごと落ちるため defaulting も不発火。
    no_gs_plan = VALIDATE.derive_plan(
        {"skill_name": "run-nogs", "kind": "run"}, {"no_goal_seek": True}
    )
    assert no_gs_plan["goal_seek_engine"] == ""
    assert no_gs_plan["flags"]["with_goal_seek"] is False


def test_lint_requires_assets_per_task_graph_skill_not_elsewhere(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills/run-repro-graph"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        _skill_md() + "\nRuntime は dependency graph knowledge を実行前に consult する。\n",
        encoding="utf-8",
    )
    RENDER.materialize_task_graph_engine(_brief(), skill_dir, SKILL_ROOT / "templates")

    findings, _warnings, applicable = LINT.lint(tmp_path)
    assert applicable is True
    assert findings == []

    # plugin root の別 scripts/ にコピーがあっても、宣言 skill 自身の欠落は充足しない。
    missing = skill_dir / "scripts/self-reflect-append.py"
    elsewhere = tmp_path / "scripts/self-reflect-append.py"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_bytes(missing.read_bytes())
    missing.unlink()
    findings, _warnings, applicable = LINT.lint(tmp_path)
    assert applicable is True
    assert any(str(missing) in finding and "同梱欠落" in finding for finding in findings)
