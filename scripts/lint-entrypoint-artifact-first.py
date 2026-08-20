#!/usr/bin/env python3
"""Fail closed when any executable plugin entrypoint can run heavy work before handoff choice."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml


EVENT_ORDER = [
    "artifact_created",
    "minimal_guard_passed",
    "artifact_presented",
    "user_choice_recorded",
    "semantic_evaluator_started",
]
STATES = [*EVENT_ORDER, "handoff_complete"]
TRANSITIONS = [
    {"from": "artifact_created", "event": "minimum_guard_pass", "to": "minimal_guard_passed"},
    {"from": "minimal_guard_passed", "event": "present_actual_artifact", "to": "artifact_presented"},
    {"from": "artifact_presented", "event": "record_user_choice", "to": "user_choice_recorded"},
    {"from": "user_choice_recorded", "event": "accept-as-is", "to": "handoff_complete"},
    {"from": "user_choice_recorded", "event": "light|standard|detailed", "to": "semantic_evaluator_started"},
    {"from": "semantic_evaluator_started", "event": "improvement_complete", "to": "handoff_complete"},
]
PRE_CHOICE_FORBIDDEN = [
    "semantic-evaluator",
    "task-fork",
    "subagent",
    "multi-worker",
    "revise-loop",
]
DIAGNOSTIC_CHOICES = ["accept-as-is", "light", "standard", "detailed"]
DIAGNOSTIC_CHOICE_ALIASES = [
    ("accept-as-is", "現状で試す"),
    ("light", "軽微"),
    ("standard", "標準"),
    ("detailed", "詳細"),
]
INITIAL_CHOICE_FORBIDDEN = ("release", "exhaustive", "リリース", "完全監査")
INITIAL_CHOICE_PROMPT_MARKERS = ("ask", "choose", "select", "choice", "聞く", "選ぶ", "選択")
SEPARATE_EVENT_MARKERS = (
    "do not mix",
    "must not include",
    "separate event",
    "別の明示event",
    "別の明示 event",
    "別イベント",
    "混ぜず",
    "含めない",
)
NORMAL_ENTRYPOINT_KINDS = {"run", "wrap", "delegate"}
CONTRACT_KEYS = {
    "contract",
    "state_machine",
    "release",
    "exhaustive",
}
WORKFLOW_CONTRACT_KEYS = {
    "contract",
    "state_machine",
    "phase_activation",
    "release",
    "exhaustive",
}
STATE_MACHINE_KEYS = {
    "initial",
    "states",
    "transitions",
    "pre_choice_forbidden",
    "accept_contexts",
}
PRE_CHOICE_HEADING = "## Pre-choice usable artifact execution"
POST_CHOICE_HEADING = "## Post-choice selected improvement execution"
LEGACY_BOUNDARY_HEADING = "## Artifact delivery boundary (hard gate)"


class Entrypoint(NamedTuple):
    plugin: str
    path: Path


class Classification(NamedTuple):
    mode: str
    reason: str


class LintError(ValueError):
    """A skill cannot be classified or parsed safely."""


def _frontmatter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LintError(f"cannot read UTF-8 skill: {exc}") from exc
    if not text.startswith("---"):
        raise LintError("frontmatter is required")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise LintError("frontmatter closing delimiter is required")
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise LintError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise LintError("frontmatter must be an object")
    return frontmatter, parts[2]


def read_kind(path: Path) -> str:
    frontmatter, _ = _frontmatter_and_body(path)
    return str(frontmatter.get("kind", "")).strip()


def read_artifact_delivery(path: Path) -> dict[str, Any]:
    frontmatter, _ = _frontmatter_and_body(path)
    value = frontmatter.get("artifact_delivery")
    return value if isinstance(value, dict) else {}


def discover_entrypoints(root: Path) -> list[Entrypoint]:
    """Use plugin manifests as the mother set, then enumerate every on-disk skill."""
    plugins_root = root / "plugins"
    manifests = sorted(
        path
        for path in plugins_root.glob("*/.claude-plugin/plugin.json")
        if path.is_file()
    )
    entrypoints: list[Entrypoint] = []
    for manifest in manifests:
        plugin_dir = manifest.parents[1]
        for skill in sorted(plugin_dir.glob("skills/*/SKILL.md")):
            if skill.is_file():
                entrypoints.append(Entrypoint(plugin=plugin_dir.name, path=skill))
    return entrypoints


def classify_entrypoint(entrypoint: Entrypoint) -> Classification:
    frontmatter, _ = _frontmatter_and_body(entrypoint.path)
    kind = str(frontmatter.get("kind", "")).strip()
    effect = str(frontmatter.get("effect", "")).strip()
    if kind in NORMAL_ENTRYPOINT_KINDS:
        return Classification("enforced", f"kind={kind}: executable artifact entrypoint")
    if kind == "ref" and effect == "none":
        return Classification("exempt", "kind=ref,effect=none: non-executable reference")
    if kind == "assign" and frontmatter.get("user-invocable") is False:
        return Classification("exempt", "kind=assign,user-invocable=false: post-choice internal evaluator")
    raise LintError(
        f"unclassified entrypoint kind/effect/role: kind={kind!r}, effect={effect!r}, "
        f"user-invocable={frontmatter.get('user-invocable')!r}"
    )


def _lint_state_machine(machine: Any, *, label: str) -> list[str]:
    if not isinstance(machine, dict) or set(machine) != STATE_MACHINE_KEYS:
        return [f"{label} requires the canonical exact state_machine key set"]
    errors: list[str] = []
    if machine.get("initial") != "artifact_created":
        errors.append(f"{label} state_machine must start at artifact_created")
    if machine.get("states") != STATES:
        errors.append(f"{label} state_machine states must be canonical and exact")
    if machine.get("transitions") != TRANSITIONS:
        errors.append(f"{label} state_machine transitions must preserve accept and selected branches")
    if machine.get("pre_choice_forbidden") != PRE_CHOICE_FORBIDDEN:
        errors.append(f"{label} state_machine must forbid all pre-choice heavy operation classes")
    if machine.get("accept_contexts") != {"evaluator": 0, "improver": 0}:
        errors.append(f"{label} accept-as-is must keep evaluator/improver contexts at zero")
    return errors


def _lint_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not contract:
        return ["artifact_delivery contract is required"]
    if set(contract) != CONTRACT_KEYS:
        errors.append("artifact_delivery contract has an invalid exact key set")
    if contract.get("contract") != "artifact-delivery-v1":
        errors.append("artifact_delivery contract must reference artifact-delivery-v1")
    errors.extend(_lint_state_machine(contract.get("state_machine"), label="artifact_delivery"))
    if contract.get("release") != "explicit-only" or contract.get("exhaustive") != "explicit-only":
        errors.append("release/exhaustive must remain explicit-only")
    return errors


def _lint_frontmatter_control_flow(frontmatter: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    goal_seek = frontmatter.get("goal_seek")
    if isinstance(goal_seek, dict):
        fork = str(goal_seek.get("fork", "inline")).strip().casefold()
        max_loops = goal_seek.get("max_loops", 1)
        is_heavy = fork not in {"", "inline"} or (
            isinstance(max_loops, int) and not isinstance(max_loops, bool) and max_loops > 1
        )
        if is_heavy and goal_seek.get("activation_state") != "semantic_evaluator_started":
            errors.append("goal_seek heavy control must activate post-choice at semantic_evaluator_started")
    feedback = frontmatter.get("feedback_contract")
    if isinstance(feedback, dict):
        iterations = feedback.get("max_iterations", 0)
        if (
            isinstance(iterations, int)
            and not isinstance(iterations, bool)
            and iterations > 0
            and feedback.get("activation_state") != "semantic_evaluator_started"
        ):
            errors.append("feedback revise loop must activate post-choice at semantic_evaluator_started")
    return errors


def _lint_body_control_flow(body: str) -> list[str]:
    lines = body.splitlines()
    errors: list[str] = []
    if LEGACY_BOUNDARY_HEADING in body:
        errors.append("legacy prose artifact boundary is forbidden; use the structured state_machine")
    pre_positions = [index for index, line in enumerate(lines) if line.strip() == PRE_CHOICE_HEADING]
    post_positions = [index for index, line in enumerate(lines) if line.strip() == POST_CHOICE_HEADING]
    if len(pre_positions) != 1 or len(post_positions) != 1 or pre_positions[0] >= post_positions[0]:
        errors.append("body requires one ordered pre-choice usable-artifact section and post-choice selected-improvement section")
        pre_start, post_start = 0, len(lines)
    else:
        pre_start, post_start = pre_positions[0] + 1, post_positions[0]

    for index, line in enumerate(lines):
        normalized = line.casefold()
        option_count = sum(
            any(alias.casefold() in normalized for alias in aliases)
            for aliases in DIAGNOSTIC_CHOICE_ALIASES
        )
        mixes_stage_promotion = (
            option_count >= 3
            and any(marker in normalized for marker in INITIAL_CHOICE_PROMPT_MARKERS)
            and any(marker in normalized for marker in INITIAL_CHOICE_FORBIDDEN)
            and not any(marker in normalized for marker in SEPARATE_EVENT_MARKERS)
        )
        if mixes_stage_promotion:
            errors.append(
                "initial diagnostic choices must exclude release/exhaustive "
                f"at body line {index + 1}"
            )
            break

    imperative_heavy = re.compile(
        r"(?ix)(?:\b(?:run|start|launch|invoke|dispatch|ask|use|execute)\b[^\n]{0,120}"
        r"(?:quality[_ -]?oracle|semantic[_ -]?evaluator|evaluator|\btask\b|subagent|"
        r"multi[_ -]?(?:agent|worker)|\bworkers?\b)|"
        r"\b(?:revise|improve|iterate|loop)\b|"
        r"(?:task|subagent|evaluator|worker|agent).{0,80}(?:\u8d77\u52d5|\u59d4\u8b72|\u5b9f\u884c)|"
        r"(?:\u4fee\u6b63|\u6539\u5584|\u53cd\u5fa9|\u5468\u56de|\u518d\u8a55\u4fa1)(?:\u3059\u308b|\u3057|\u3092))"
    )
    for index in range(pre_start, post_start):
        line = lines[index]
        lowered = line.casefold()
        prohibited = any(
            marker in lowered
            for marker in ("must not", "do not", "forbidden", "reject", "without", "\u7981\u6b62", "\u3057\u306a\u3044", "\u62d2\u5426", "\u4e0d\u8981")
        )
        if not prohibited and imperative_heavy.search(line):
            errors.append(f"pre-choice imperative heavy operation at body line {index + 1}")
            break

    contradiction = re.compile(
        r"(?ix)(?:only\s+then\s+(?:create|show|present|write|emit|publish)|"
        r"(?:run|start|ask|revise|iterate)[^\n]{0,160}\b(?:before|prior to)\b[^\n]{0,80}"
        r"(?:create|show|present|artifact)|"
        r"(?:\u8a55\u4fa1|\u4fee\u6b63|\u53cd\u5fa9|\u5468\u56de|\u59d4\u8b72).{0,100}(?:\u305d\u306e\u5f8c|\u5f8c\u3067|\u304b\u3089)(?:\u751f\u6210|\u4f5c\u6210|\u63d0\u793a))"
    )
    for index, line in enumerate(lines):
        if contradiction.search(line):
            errors.append(f"heavy-before-create/present contradiction at body line {index + 1}")
            break
    publication_gate = re.compile(
        r"(?ix)(?:(?:do\s+not|don't|must\s+not|not)\s+[^\n]{0,80}"
        r"(?:publish|present|show)[^\n]{0,80}(?:until|unless)[^\n]{0,80}"
        r"(?:evaluator|review|pass)|"
        r"(?:evaluator|review)[^\n]{0,80}(?:pass|complete|\u4e00\u81f4)[^\n]{0,80}"
        r"(?:\u307e\u3067|until)[^\n]{0,40}(?:publish|present|show|\u516c\u958b|\u63d0\u793a)(?:\u3057\u306a\u3044|\u7981\u6b62)?)"
    )
    for index, line in enumerate(lines):
        if publication_gate.search(line):
            errors.append(f"evaluator-before-first-publication contradiction at body line {index + 1}")
            break
    return errors


def _lint_workflow_manifest(path: Path) -> list[str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"cannot read workflow-manifest.json: {exc}"]
    if not isinstance(document, dict):
        return ["workflow-manifest.json must be an object"]
    contract = document.get("artifact_delivery_contract")
    if not isinstance(contract, dict):
        return ["workflow-manifest.json requires artifact_delivery_contract"]
    errors: list[str] = []
    if set(contract) != WORKFLOW_CONTRACT_KEYS:
        errors.append("workflow artifact_delivery_contract has an invalid exact key set")
    if contract.get("contract") != "artifact-delivery-v1":
        errors.append("workflow must reference artifact-delivery-v1")
    errors.extend(_lint_state_machine(contract.get("state_machine"), label="workflow artifact_delivery"))
    phases = document.get("phases")
    phase_ids = [phase.get("id") for phase in phases] if isinstance(phases, list) and all(isinstance(phase, dict) for phase in phases) else []
    if len(phase_ids) != len(set(phase_ids)) or any(not isinstance(phase_id, str) or not phase_id for phase_id in phase_ids):
        errors.append("workflow phases require unique non-empty ids")
    if isinstance(phases, list):
        for phase in phases:
            if isinstance(phase, dict) and "choices" in phase:
                if phase.get("choices") != DIAGNOSTIC_CHOICES:
                    errors.append(
                        "workflow diagnostic choices must be canonical: "
                        "accept-as-is|light|standard|detailed"
                    )
    if contract.get("phase_activation") != "all-legacy-phases-after-semantic_evaluator_started":
        errors.append("workflow legacy phases require exact post-choice activation")
    if contract.get("release") != "explicit-only" or contract.get("exhaustive") != "explicit-only":
        errors.append("workflow release/exhaustive must remain explicit-only")
    return errors


def lint_entrypoint(entrypoint: Entrypoint) -> list[str]:
    try:
        classification = classify_entrypoint(entrypoint)
        if classification.mode == "exempt":
            return []
        frontmatter, body = _frontmatter_and_body(entrypoint.path)
        errors = _lint_contract(
            frontmatter.get("artifact_delivery")
            if isinstance(frontmatter.get("artifact_delivery"), dict)
            else {}
        )
        errors.extend(_lint_frontmatter_control_flow(frontmatter))
        errors.extend(_lint_body_control_flow(body))
        workflow = entrypoint.path.parent / "workflow-manifest.json"
        if workflow.exists():
            errors.extend(_lint_workflow_manifest(workflow))
        return errors
    except LintError as exc:
        return [str(exc)]


def lint_repository(root: Path) -> list[str]:
    entrypoints = discover_entrypoints(root)
    if not entrypoints:
        return ["no plugin entrypoints discovered from plugins/*/.claude-plugin/plugin.json"]
    errors: list[str] = []
    for entrypoint in entrypoints:
        relative = entrypoint.path.relative_to(root).as_posix()
        errors.extend(f"{relative}: {message}" for message in lint_entrypoint(entrypoint))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    errors = lint_repository(root)
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    discovered = discover_entrypoints(root)
    enforced = sum(classify_entrypoint(item).mode == "enforced" for item in discovered)
    exempt = len(discovered) - enforced
    print(f"OK: artifact-first entrypoints valid ({len(discovered)} inventory, {enforced} enforced, {exempt} mechanically exempt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
