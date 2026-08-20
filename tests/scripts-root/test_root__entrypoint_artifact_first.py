"""Repository-wide hard gate for artifact-first normal entrypoints."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LINTER = ROOT / "scripts/lint-entrypoint-artifact-first.py"
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
FORBIDDEN_HEAVY = [
    "semantic-evaluator",
    "task-fork",
    "subagent",
    "multi-worker",
    "revise-loop",
]


def _load_module():
    spec = importlib.util.spec_from_file_location("lint_entrypoint_artifact_first", LINTER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_temp_entrypoint(root: Path, body: str, *, include_contract: bool = True) -> Path:
    plugin = root / "plugins/future-temp"
    manifest = plugin / ".claude-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "future-temp", "version": "0.1.0", "description": "fixture"}),
        encoding="utf-8",
    )
    skill = plugin / "skills/run-future-temp/SKILL.md"
    skill.parent.mkdir(parents=True)
    contract = (
        "artifact_delivery:\n"
        "  contract: artifact-delivery-v1\n"
        "  state_machine:\n"
        "    initial: artifact_created\n"
        "    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]\n"
        "    transitions:\n"
        "      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}\n"
        "      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}\n"
        "      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}\n"
        "      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}\n"
        "      - {from: user_choice_recorded, event: 'light|standard|detailed', to: semantic_evaluator_started}\n"
        "      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}\n"
        "    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]\n"
        "    accept_contexts: {evaluator: 0, improver: 0}\n"
        "  release: explicit-only\n"
        "  exhaustive: explicit-only\n"
        if include_contract
        else ""
    )
    skill.write_text(
        "---\nname: run-future-temp\ndescription: fixture\nkind: run\nversion: 0.1.0\nowner: test\neffect: local-artifact\n"
        + contract
        + "---\n"
        + body,
        encoding="utf-8",
    )
    return skill


def _write_workflow(
    skill: Path,
    *,
    activate_legacy_phase: bool = True,
    choices: list[str] | None = None,
) -> None:
    phase_activation = (
        "all-legacy-phases-after-semantic_evaluator_started"
        if activate_legacy_phase
        else "unbound"
    )
    (skill.parent / "workflow-manifest.json").write_text(
        json.dumps(
            {
                "artifact_delivery_contract": {
                    "contract": "artifact-delivery-v1",
                    "state_machine": {
                        "initial": "artifact_created",
                        "states": STATES,
                        "transitions": TRANSITIONS,
                        "pre_choice_forbidden": FORBIDDEN_HEAVY,
                        "accept_contexts": {"evaluator": 0, "improver": 0},
                    },
                    "phase_activation": phase_activation,
                    "release": "explicit-only",
                    "exhaustive": "explicit-only",
                },
                "phases": [
                    {
                        "id": "legacy-heavy",
                        "title": "Run evaluator workers and revise until pass",
                        **({"choices": choices} if choices is not None else {}),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_discovers_every_plugin_normal_entrypoint_without_allowlist():
    mod = _load_module()
    discovered = mod.discover_entrypoints(ROOT)
    manifest_plugins = {
        path.parents[1].name
        for path in (ROOT / "plugins").glob("*/.claude-plugin/plugin.json")
        if path.is_file()
    }
    discovered_plugins = {item.plugin for item in discovered}
    assert discovered_plugins == manifest_plugins

    expected = {
        skill.resolve()
        for plugin in manifest_plugins
        for skill in (ROOT / "plugins" / plugin / "skills").glob("*/SKILL.md")
    }
    assert {item.path.resolve() for item in discovered} == expected
    classifications = [mod.classify_entrypoint(item) for item in discovered]
    assert len(classifications) == len(discovered)
    assert all(classification.mode in {"enforced", "exempt"} for classification in classifications)
    assert all(classification.reason for classification in classifications if classification.mode == "exempt")
    source = LINTER.read_text(encoding="utf-8")
    assert "PLUGIN_ALLOWLIST" not in source


def test_every_current_normal_entrypoint_has_machine_checked_artifact_first_contract():
    mod = _load_module()
    assert mod.lint_repository(ROOT) == []
    for entrypoint in mod.discover_entrypoints(ROOT):
        classification = mod.classify_entrypoint(entrypoint)
        if classification.mode == "enforced":
            contract = mod.read_artifact_delivery(entrypoint.path)
            assert contract["state_machine"]["states"] == STATES
        else:
            assert classification.reason in {
                "kind=ref,effect=none: non-executable reference",
                "kind=assign,user-invocable=false: post-choice internal evaluator",
            }


def test_future_temp_plugin_missing_contract_fails_closed(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(tmp_path, "# Future\nCreate a draft.\n", include_contract=False)
    errors = mod.lint_repository(tmp_path)
    assert any("artifact_delivery contract is required" in error for error in errors)


def test_future_temp_plugin_pre_choice_heavy_loop_fails_even_with_declaration(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        """# Future

## Pre-choice usable artifact execution

Run expensive_quality_oracle and revise; Ask three workers; Only then create/show the artifact.

## Post-choice selected improvement execution

Run the bounded improvement selected by the user.
""",
    )
    errors = mod.lint_repository(tmp_path)
    assert any("pre-choice imperative heavy operation" in error for error in errors)
    assert any("heavy-before-create/present contradiction" in error for error in errors)


def test_future_temp_frontmatter_fork_and_loop_without_post_choice_activation_fails(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(
        tmp_path,
        """# Future

## Pre-choice usable artifact execution

Create, minimally guard, and present the actual artifact, then record the choice.

## Post-choice selected improvement execution

Run selected improvement only.
""",
    )
    text = skill.read_text(encoding="utf-8")
    skill.write_text(
        text.replace(
            "artifact_delivery:\n",
            "goal_seek:\n  fork: subagent\n  max_loops: 5\nartifact_delivery:\n",
        ),
        encoding="utf-8",
    )
    errors = mod.lint_repository(tmp_path)
    assert any("goal_seek heavy control must activate post-choice" in error for error in errors)


def test_future_temp_workflow_legacy_phase_without_activation_fails_closed(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(
        tmp_path,
        """# Future

## Pre-choice usable artifact execution

Create, minimally guard, and present the actual artifact, then record the choice.

## Post-choice selected improvement execution

Run selected improvement only.
""",
    )
    _write_workflow(skill, activate_legacy_phase=False)
    errors = mod.lint_repository(tmp_path)
    assert any("workflow legacy phases require exact post-choice activation" in error for error in errors)


def test_future_temp_workflow_rejects_noncanonical_diagnostic_choice_vocabulary(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(
        tmp_path,
        """# Future

## Pre-choice usable artifact execution

Create, minimally guard, and present the actual artifact, then record the choice.

## Post-choice selected improvement execution

Run selected improvement only.
""",
    )
    _write_workflow(
        skill,
        choices=["accept-as-is", "focused", "standard", "detailed", "release"],
    )
    errors = mod.lint_repository(tmp_path)
    assert any("workflow diagnostic choices must be canonical" in error for error in errors)


def test_future_temp_body_rejects_release_mixed_into_initial_diagnostic_choices(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        """# Future

## Pre-choice usable artifact execution

Create, minimally guard, and present the actual artifact.
Then ask the user to choose `accept-as-is / light / standard / detailed / release`.

## Post-choice selected improvement execution

Run selected improvement only.
""",
    )
    errors = mod.lint_repository(tmp_path)
    assert any("initial diagnostic choices must exclude release/exhaustive" in error for error in errors)


def test_future_temp_legacy_prose_marker_cannot_mask_later_contradiction(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        """## Artifact delivery boundary (hard gate)

1. `artifact_created`
2. `minimal_guard_passed`
3. `artifact_presented`
4. `user_choice_recorded`
5. `semantic_evaluator_started`

Run expensive_quality_oracle and revise. Ask three workers. Only then create/show.
""",
    )
    errors = mod.lint_repository(tmp_path)
    assert any("legacy prose artifact boundary is forbidden" in error for error in errors)
    assert any("heavy-before-create/present contradiction" in error for error in errors)


def test_future_temp_evaluator_pass_cannot_gate_first_artifact_publication(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        """## Pre-choice usable artifact execution

Create, minimally guard, and present the actual artifact, then record the choice.

## Post-choice selected improvement execution

Do not publish the artifact until evaluator C1-C4 is PASS.
""",
    )
    errors = mod.lint_repository(tmp_path)
    assert any("evaluator-before-first-publication contradiction" in error for error in errors)


def test_known_counterexample_families_are_covered_by_the_dynamic_gate():
    mod = _load_module()
    families = {
        "system-dev-planner",
        "skill-intake",
        "extract-system-blueprint",
        "dev-graph",
    }
    discovered = mod.discover_entrypoints(ROOT)
    assert families <= {entrypoint.plugin for entrypoint in discovered}
    for entrypoint in discovered:
        if entrypoint.plugin in families:
            assert mod.lint_entrypoint(entrypoint) == []
