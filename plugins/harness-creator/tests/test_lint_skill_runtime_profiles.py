from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "plugins/harness-creator/scripts/lint-skill-runtime-profiles.py"
SPEC = importlib.util.spec_from_file_location("lint_skill_runtime_profiles", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _skill(
    tmp_path: Path,
    *,
    kind: str = "run",
    goal_seek: str = "  engine: inline\n  fork: inline\n",
    tools: tuple[str, ...] = ("Read",),
) -> tuple[Path, Path]:
    root = tmp_path
    skill = root / "plugins/demo/skills/run-demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    tools_yaml = "\n".join(f"  - {tool}" for tool in tools)
    block = f"goal_seek:\n{goal_seek}" if goal_seek else ""
    skill.write_text(
        f"---\nname: run-demo\nallowed-tools:\n{tools_yaml}\nkind: {kind}\n"
        f"prefix: {kind}\n{block}---\n\n## ゴールシーク実行\n",
        encoding="utf-8",
    )
    return root, skill


def test_inline_profile_passes(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()
    assert profile.engine == "inline"
    assert profile.fork == "inline"


def test_inline_without_agent_tool_rejects_mandatory_agent_fork_prose(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + "\n- `Agent` で分離 context に fork する。\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("本文が分離委譲を必須化" in finding for finding in profile.findings)


def test_loop_profile_is_required(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path, goal_seek="")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("goal_seek block" in finding for finding in profile.findings)
    assert any("goal_seek.engine" in finding for finding in profile.findings)
    assert any("goal_seek.fork" in finding for finding in profile.findings)


def test_subagent_requires_agent_tool(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path, goal_seek="  engine: inline\n  fork: subagent\n"
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("allowed-tools に Agent/Task がない" in finding for finding in profile.findings)


def test_subagent_with_agent_tool_passes(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek="  engine: inline\n  fork: subagent\n",
        tools=("Read", "Agent"),
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()


def test_subagent_with_claude_task_tool_passes(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek="  engine: inline\n  fork: subagent\n",
        tools=("Read", "Task"),
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()


def test_task_graph_requires_all_assets(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek=(
            "  engine: task-graph\n"
            "  engine_profile: checklist-graph\n"
            "  full_task_spec_graph: false\n"
            "  fork: inline\n"
        ),
    )
    skill.write_text(
        skill.read_text(encoding="utf-8")
        + "depends_on extract-ready-set-from-checklist.py build-self-reflection-entry.py "
        + "ready_set selected_item\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("engine asset が不足" in finding for finding in profile.findings)

    scripts = skill.parent / "scripts"
    scripts.mkdir()
    templates = (
        root
        / "plugins/harness-creator/skills/run-build-skill/templates"
        / "task-graph-engine/scripts"
    )
    templates.mkdir(parents=True)
    for name in MODULE.TASK_GRAPH_ASSETS:
        (templates / name).write_text("# fixture\n", encoding="utf-8")
        (scripts / name).write_text("# fixture\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()

    (scripts / MODULE.TASK_GRAPH_ASSETS[0]).write_text("# drift\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("正本と不一致" in finding for finding in profile.findings)


def test_inline_rejects_unused_task_graph_assets(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    scripts = skill.parent / "scripts"
    scripts.mkdir()
    (scripts / MODULE.TASK_GRAPH_ASSETS[0]).write_text("# fixture\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("task-graph asset が残存" in finding for finding in profile.findings)


def test_goal_seek_anchor_validator_must_match_canonical(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    skill.write_text(
        skill.read_text(encoding="utf-8") + "\nvalidate-inline-goal-seek-anchor.py\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("plugin scripts/ に不在" in finding for finding in profile.findings)

    canonical = (
        root
        / "plugins/harness-creator/skills/run-build-skill/templates"
        / "goal-seek-runtime/scripts/validate-inline-goal-seek-anchor.py"
    )
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")
    deployed = root / "plugins/demo/scripts/validate-inline-goal-seek-anchor.py"
    deployed.parent.mkdir(parents=True)
    deployed.write_text("# drift\n", encoding="utf-8")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("正本と不一致" in finding for finding in profile.findings)
    deployed.write_bytes(canonical.read_bytes())
    assert MODULE.inspect_skill(skill, root / "plugins").findings == ()


def test_agent_team_requires_fan_out_fan_in_and_ownership(tmp_path: Path) -> None:
    root, skill = _skill(
        tmp_path,
        goal_seek="  engine: inline\n  fork: agent-team\n",
        tools=("Read", "Agent"),
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("並列所有権配線が不足" in finding for finding in profile.findings)

    skill.write_text(
        skill.read_text(encoding="utf-8")
        + "fan-out workers, fan-in results, explicit file ownership\n",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.findings == ()


def test_non_loop_skill_is_not_applicable(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path, kind="assign", goal_seek="")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert profile.applicable is False
    assert profile.findings == ()


def test_non_loop_skill_rejects_runtime_profile(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path, kind="assign")
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("runtime profile 非適用" in finding for finding in profile.findings)


def test_collection_excludes_nested_test_fixtures(tmp_path: Path) -> None:
    root, canonical = _skill(tmp_path)
    fixture = root / "plugins/demo/tests/fixtures/skills/run-fixture/SKILL.md"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("---\nkind: run\n---\n", encoding="utf-8")
    assert MODULE.collect_skills(root) == [canonical]


def test_manifest_dependencies_and_delegate_refs_are_validated(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    text = skill.read_text(encoding="utf-8").replace(
        "prefix: run\n", "prefix: run\nmanifest: workflow-manifest.json\n"
    )
    skill.write_text(text, encoding="utf-8")
    (skill.parent / "workflow-manifest.json").write_text(
        '{"phases": ['
        '{"id": "P1", "dependsOn": ["P2"], "delegateSkill": "missing"},'
        '{"id": "P2", "dependsOn": ["P1"]}'
        "]}",
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("delegateSkill が不在" in finding for finding in profile.findings)
    assert any("dependsOn が循環" in finding for finding in profile.findings)


def test_manifest_agent_ref_must_exist(tmp_path: Path) -> None:
    root, skill = _skill(tmp_path)
    text = skill.read_text(encoding="utf-8").replace(
        "prefix: run\n", "prefix: run\nmanifest: workflow-manifest.json\n"
    )
    skill.write_text(text, encoding="utf-8")
    (skill.parent / "workflow-manifest.json").write_text(
        '{"phases": [{"id": "P1", "dependsOn": [], '
        '"delegateType": "agent", "delegateName": "missing-agent"}]}',
        encoding="utf-8",
    )
    profile = MODULE.inspect_skill(skill, root / "plugins")
    assert any("delegate agent が不在" in finding for finding in profile.findings)
