"""feedback_contract.criteria IN2 の検証 (prompt-creator/run-prompt-create)。

IN2: workflow-manifest.json の各 phase が eval-log/handoff-*.json の保存先を 1 つずつ持ち、
数値の Gate を持つのは p0-lint (Gate 2) だけで、各 phase の handoff の見本が
schemas/handoff.schema.json に通ること。

validate-prompt.py は null を「欠けている」と扱い gate_id=null の handoff を検証できないため、
ここでは jsonschema で schema そのものに見本を通す。見本は manifest の phase 定義と
prompts/R2-gate-review.md・prompts/R3-governance-decide.md の記録規則から組み立て、
phase ごとに分岐する場面 (Gate 2 の通過/不通過、accept-as-is/diagnose、governance の
approved/blocked、改善の周回、release の記録) を 1 つずつ持つ。p0-lint の commands を
実際に走らせるのは IN1 (lint) の範囲で、ここでは Gate 2 の handoff が exit code だけで決まることを確かめる。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = "prompt-creator"
SKILL = "run-prompt-create"
SKILL_DIR = REPO_ROOT / "plugins" / PLUGIN / "skills" / SKILL
MANIFEST = json.loads((SKILL_DIR / "workflow-manifest.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((SKILL_DIR / "schemas" / "handoff.schema.json").read_text(encoding="utf-8"))
PHASES = {p["id"]: p for p in MANIFEST["phases"]}
HANDOFF_PATH = re.compile(r"^eval-log/handoff-[a-z0-9_]+\.json$")
R2 = "prompts/R2-gate-review.md"


def _validator() -> jsonschema.Draft202012Validator:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    return jsonschema.Draft202012Validator(SCHEMA)


# phase ごとに R2/R3 が handoff に書く成果物の種類。
ARTIFACT_KINDS = {
    "elicit": ["brief"],
    "build": ["prompt", "build-trace"],
    "p0-lint": ["lint-log"],
    "artifact-present-handoff": ["prompt"],
    "diagnostic-choice": ["prompt"],
    "design-evaluate": ["evaluator-result"],
    "governance": ["governance-decision"],
    "report": ["report"],
}
R2_PHASES = ["build", "p0-lint", "artifact-present-handoff", "diagnostic-choice", "design-evaluate", "report"]
RELEASE_EVENT = {"recorded_at": "2026-11-14T00:05:00Z", "user_quote": "このまま release して"}


def _base(phase_id: str, **fields) -> dict:
    record = {
        "step": phase_id,
        "timestamp": "2026-11-14T00:00:00Z",
        "gate_id": PHASES[phase_id]["gate"],
        "approver": "system_auto",
        "artifacts": [{"path": f"eval-log/{phase_id}-{i}", "kind": kind}
                      for i, kind in enumerate(ARTIFACT_KINDS[phase_id])],
        "next_phase": None,
    }
    record.update(fields)
    return record


def _gate2(exit_codes: list[int]) -> dict:
    """R2 2.2 の Gate 2: commands の exit code だけで handoff を決める。"""
    commands = PHASES["p0-lint"]["commands"]
    assert len(exit_codes) == len(commands)
    failed = [c for c, code in zip(commands, exit_codes) if code != 0]
    if not failed:
        return _base("p0-lint", next_phase="artifact-present-handoff")
    return _base("p0-lint", next_phase="build", required_fixes=[f"exit!=0: {c}" for c in failed])


# (phase, 場面, handoff の見本)。見本は R2/R3 の記録規則どおりに組み立てる。
SAMPLES = [
    ("elicit", "create", _base("elicit", mode="create", next_phase="build")),
    ("elicit", "update", _base("elicit", mode="update", next_phase="build")),
    ("build", "first", _base("build", next_phase="p0-lint")),
    ("p0-lint", "all-exit-0", _gate2([0] * 9)),
    ("p0-lint", "one-exit-1", _gate2([0] * 8 + [1])),
    ("artifact-present-handoff", "presented", _base("artifact-present-handoff", next_phase="diagnostic-choice")),
    ("diagnostic-choice", "accept-as-is", _base("diagnostic-choice", approver="user",
                                                user_choice="accept-as-is", next_phase="report")),
    ("diagnostic-choice", "diagnose+release", _base("diagnostic-choice", approver="user", user_choice="diagnose",
                                                    release_event=RELEASE_EVENT, next_phase="design-evaluate")),
    ("design-evaluate", "round-0", _base("design-evaluate", approver="user", improvement_depth="standard",
                                         improvement_round=0, next_phase="build",
                                         required_fixes=["C2: L5 が L3 の tool 名に依存している"])),
    ("design-evaluate", "round-2-release", _base("design-evaluate", improvement_depth="standard",
                                                 improvement_round=2, release_event=RELEASE_EVENT,
                                                 next_phase="governance")),
    ("governance", "approved", _base("governance", approver="solo_operator_auto",
                                     governance_decision="approved", next_phase="report")),
    ("governance", "blocked", _base("governance", governance_decision="blocked", next_phase="report",
                                    required_fixes=["stable_frozen=false"])),
    ("report", "accept-as-is-then-release", _base(
        "report", release_event=RELEASE_EVENT,
        resume_command='/prompt-creator:run-prompt-create --mode update --topic "x"')),
]


def test_IN2_run_prompt_create_criterion_is_verified_by_test() -> None:
    """IN2 の verify_by が test で、本ファイルが検証の正本であること。"""
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    front = yaml.safe_load(text.split("---", 2)[1])
    criteria = {c["id"]: c for c in front["feedback_contract"]["criteria"]}
    assert criteria["IN2"]["verify_by"] == "test"


def test_IN2_run_prompt_create_each_phase_has_one_unique_handoff_path() -> None:
    paths = [p.get("handoff") for p in MANIFEST["phases"]]
    assert all(isinstance(p, str) and HANDOFF_PATH.match(p) for p in paths), paths
    assert len(paths) == len(set(paths)), "handoff の保存先が重複している"


def test_IN2_run_prompt_create_only_p0_lint_has_numeric_gate_2() -> None:
    numeric = {pid: p["gate"] for pid, p in PHASES.items() if p["gate"] is not None}
    assert numeric == {"p0-lint": 2}


def test_IN2_run_prompt_create_samples_cover_every_phase() -> None:
    assert {phase for phase, _, _ in SAMPLES} == set(PHASES)
    assert set(ARTIFACT_KINDS) == set(PHASES)


@pytest.mark.parametrize("phase_id,case,record", SAMPLES, ids=[f"{p}:{c}" for p, c, _ in SAMPLES])
def test_IN2_run_prompt_create_sample_handoff_matches_schema(phase_id: str, case: str, record: dict) -> None:
    _validator().validate(record)
    assert record["step"] == phase_id
    assert record["next_phase"] is None or record["next_phase"] in PHASES
    assert record["gate_id"] == (2 if phase_id == "p0-lint" else None)
    asked = (phase_id == "diagnostic-choice"
             or (phase_id == "design-evaluate" and record.get("improvement_round") == 0))
    assert (record["approver"] == "user") == asked, case
    assert (record["approver"] == "solo_operator_auto") == (record.get("governance_decision") == "approved")


def test_IN2_run_prompt_create_gate_2_is_decided_by_exit_codes_only() -> None:
    """Gate 2 は p0-lint の commands の exit code だけで決まり、どの command も実在する script を指す。"""
    commands = PHASES["p0-lint"]["commands"]
    assert len(commands) == 9
    scripts = [c.split()[1] for c in commands]
    assert all(c.startswith("python3 ") for c in commands)
    assert len(set(scripts)) == 8
    assert all((REPO_ROOT / script).is_file() for script in scripts), scripts
    assert _gate2([0] * 9)["next_phase"] == "artifact-present-handoff"
    for failed_index in range(len(commands)):
        codes = [0] * len(commands)
        codes[failed_index] = 1
        record = _gate2(codes)
        _validator().validate(record)
        assert record["next_phase"] == "build"
        assert record["required_fixes"] == [f"exit!=0: {commands[failed_index]}"]
    rules = (SKILL_DIR / R2).read_text(encoding="utf-8")
    assert "commands 9 本が全件 exit 0 なら gate_id=2・approver=system_auto・next_phase=artifact-present-handoff" in rules
    assert "1 本でも非 0 なら、失敗した command と根本原因を required_fixes に書いて next_phase=build" in rules


@pytest.mark.parametrize(
    "broken",
    [
        {"user_choice": "auto-improve"},
        {"improvement_depth": "exhaustive"},
        {"governance_decision": "pending"},
        {"artifacts": [{"path": "x", "kind": "elegant-findings"}]},
        {"release_event": {"recorded_at": "2026-11-14T00:05:00Z"}},
        {"release_event": {"recorded_at": "2026-11-14T00:05:00Z", "user_quote": ""}},
        {"improvement_round": -1},
    ],
)
def test_IN2_run_prompt_create_schema_rejects_values_outside_the_design(broken: dict) -> None:
    record = {**_base("diagnostic-choice", approver="user", user_choice="diagnose",
                      next_phase="design-evaluate"), **broken}
    assert list(_validator().iter_errors(record)), broken


def test_IN2_run_prompt_create_schema_requires_gate_id_even_when_null() -> None:
    record = _base("build", next_phase="p0-lint")
    del record["gate_id"]
    assert list(_validator().iter_errors(record))


def test_IN2_run_prompt_create_evaluator_and_governance_run_in_fork() -> None:
    assert PHASES["design-evaluate"].get("context") == "fork"
    governance = PHASES["governance"]
    assert governance.get("context") == "fork"
    assert governance.get("delegateSkill") is None
    assert R2 not in governance["resourceIds"]
    assert "prompts/R3-governance-decide.md" in governance["resourceIds"]
    # 会話を引き継がない subagent で起動し、main context が R3 を読んで承認を書かない。
    assert governance.get("subagent") == "general-purpose"
    front = yaml.safe_load((SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
    assert "Agent" in front["allowed-tools"]
    assert "main context は R3 を読まず" in governance["execution"]
    r2_rules = (SKILL_DIR / R2).read_text(encoding="utf-8")
    assert "approver=solo_operator_auto と governance_decision は R2 では書かない" in r2_rules


def test_IN2_run_prompt_create_r2_is_loaded_by_every_phase_it_records() -> None:
    for phase_id in R2_PHASES:
        assert R2 in PHASES[phase_id]["resourceIds"], phase_id


def test_IN2_run_prompt_create_release_and_blocked_paths_are_defined() -> None:
    governance = PHASES["governance"]
    assert governance["condition"] == "explicit_release_event_recorded == true"
    assert "release_event" in governance["condition_evidence"]
    assert PHASES["diagnostic-choice"]["release_event_recorded_in"] == "handoff.release_event"
    assert governance["on_blocked"]["next_phase"] == "report"
    assert {"report", "rework", "no_override"} <= set(governance["on_blocked"])
    assert set(SCHEMA["properties"]["release_event"]["required"]) == {"recorded_at", "user_quote"}


def test_IN2_run_prompt_create_improvement_round_is_recorded() -> None:
    depth = PHASES["design-evaluate"]["depth_choice"]
    assert depth["round_recorded_in"] == "handoff.improvement_round"
    round_schema = SCHEMA["properties"]["improvement_round"]
    assert round_schema["type"] == "integer"
    assert round_schema["minimum"] == 0


def test_IN2_run_prompt_create_depth_is_asked_once_with_bounded_rounds() -> None:
    phase = PHASES["design-evaluate"]
    depth = phase["depth_choice"]
    assert depth["asked"] == "once-after-findings-presented"
    assert depth["options"] == ["findings-only", "light", "standard", "detailed"]
    assert depth["default"] in depth["options"]
    assert set(depth["selection"]) == set(depth["options"])
    assert depth["max_iterations_by_option"] == {
        "findings-only": 0, "light": 1, "standard": 2, "detailed": 3,
    }
    assert max(depth["max_iterations_by_option"].values()) == phase["max_iterations"] == 3
    assert set(depth["options"]) == set(SCHEMA["properties"]["improvement_depth"]["enum"])


def test_IN2_run_prompt_create_no_question_before_the_artifact() -> None:
    assert R2 not in PHASES["elicit"]["resourceIds"]
    assert "--batch" in PHASES["elicit"]["execution"]
    text = json.dumps(MANIFEST, ensure_ascii=False)
    assert "run-skill-rubric-governance" not in text
