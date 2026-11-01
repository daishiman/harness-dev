"""plan-live-trials の scenario 契約と証拠再利用を検証する。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = (
    REPO / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial" / "scripts"
)


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), SCRIPTS / f"{stem}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = _load("plan-live-trials")
VERDICT = _load("live-trial-verdict")


def _plugin(tmp_path: Path, skills: list[str]) -> Path:
    plugin = tmp_path / "plugins" / "sample-plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": plugin.name}), encoding="utf-8"
    )
    for skill in skills:
        directory = plugin / "skills" / skill
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {skill}\nkind: run\nallowed-tools: [Read, Skill]\n---\nbody\n",
            encoding="utf-8",
        )
    (plugin / "references").mkdir()
    (plugin / "references" / "package-contract.json").write_text(
        json.dumps(
            {
                "plugin_name": plugin.name,
                "entry_points": {
                    "skills": skills,
                    "agents": [],
                    "commands": [],
                    "hooks": [],
                },
                "depends_on": [],
                "skill_dependencies": {skill: [] for skill in skills},
            }
        ),
        encoding="utf-8",
    )
    return plugin


def _reusable_verdict(eval_root: Path, plugin: Path, skill: str) -> Path:
    run = eval_root / plugin.name / skill / "live-trial" / "20260713T000000"
    run.mkdir(parents=True)
    transcript = run / "transcript.jsonl"
    transcript.write_text('{"type":"system","subtype":"turn_duration"}\n', encoding="utf-8")
    doc = {
        "target_skill": f"{plugin.name}:{skill}",
        "args": "",
        "requested_model": "",
        "actual_model": ["claude-test"],
        "nudge_count": 0,
        "gate_response_count": 0,
        "goal_verdict": {"result": "PASS", "blockers": []},
        "overall": {
            "launch": "PASS",
            "completion": "PASS",
            "goal_fit": "PASS",
            "verdict": "PASS",
        },
        "skill_dir_tree_sha": VERDICT.skill_dir_tree_sha(plugin / "skills" / skill),
        "transcript_sha256": PLANNER._sha256(transcript),
        "scenario_origin": "synthetic",
        "scenario_id": f"{skill}-positive",
        "environment": {
            "claude_version": "test",
            "tmux": True,
            "transcript_layer": "jsonl",
            "permissions_mode": "test",
        },
        "tier": "live",
        "downgrade_reason": None,
        "timeline": {"boot_s": 1, "poll_exit": "DONE", "wall_clock_s": 2},
    }
    path = run / "verdict.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _scenario_fixture(plugin: Path, skill: str | None, scenario_id: str) -> Path:
    path = plugin.joinpath(*PLANNER.SCENARIO_FIXTURE_REL)
    path.parent.mkdir(parents=True, exist_ok=True)
    scenarios = (
        [
            {
                "scenario_id": scenario_id,
                "skill": skill,
                "required_observations": ["a", "b", "c"],
            }
        ]
        if skill
        else []
    )
    path.write_text(
        json.dumps({"schema_version": "1.0.0", "scenarios": scenarios}),
        encoding="utf-8",
    )
    return path


def test_current_scenario_reuses_evidence(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path, ["run-a", "run-b"])
    evidence = _reusable_verdict(tmp_path / "eval-log", plugin, "run-a")
    _scenario_fixture(plugin, "run-a", "run-a-positive")
    plan = PLANNER.build_plan(plugin, tmp_path / "eval-log", max_live_trials=1)
    assert plan["skills"][0]["action"] == "reuse"
    assert plan["skills"][0]["reused_evidence"] == str(evidence)


@pytest.mark.parametrize("removed", [False, True])
def test_changed_or_removed_scenario_invalidates_old_evidence(
    tmp_path: Path, removed: bool
) -> None:
    plugin = _plugin(tmp_path, ["run-a", "run-b"])
    _reusable_verdict(tmp_path / "eval-log", plugin, "run-a")
    _scenario_fixture(
        plugin,
        None if removed else "run-a",
        "run-a-positive-r2",
    )
    plan = PLANNER.build_plan(plugin, tmp_path / "eval-log", max_live_trials=1)
    assert plan["skills"][0]["action"] == "run"
    assert plan["skills"][0]["reason"] == "scenario-contract-superseded"


def test_unreadable_scenario_fixture_fails_closed(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path, ["run-a"])
    _reusable_verdict(tmp_path / "eval-log", plugin, "run-a")
    fixture = _scenario_fixture(plugin, "run-a", "run-a-positive")
    fixture.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        PLANNER.build_plan(plugin, tmp_path / "eval-log")


def test_reuse_reason_reports_newest_evidence(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path, ["run-a"])
    _reusable_verdict(tmp_path / "eval-log", plugin, "run-a")
    stale = tmp_path / "eval-log" / plugin.name / "run-a" / "live-trial" / "20260101"
    stale.mkdir(parents=True)
    (stale / "verdict.json").write_text("{not json", encoding="utf-8")
    _scenario_fixture(plugin, "run-a", "run-a-positive-r2")
    plan = PLANNER.build_plan(plugin, tmp_path / "eval-log")
    assert plan["skills"][0]["reason"] == "scenario-contract-superseded"
