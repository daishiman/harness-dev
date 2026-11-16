"""Repository-wide hard gate for artifact-first normal entrypoints."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


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
PRE_CHOICE_TRANSITIONS = [
    {"from": "artifact_created", "event": "minimum_guard_pass", "to": "minimal_guard_passed"},
    {"from": "minimal_guard_passed", "event": "present_actual_artifact", "to": "artifact_presented"},
    {"from": "artifact_presented", "event": "record_user_choice", "to": "user_choice_recorded"},
]
# 2 択 (harness-znj) の後の正本。
TRANSITIONS = [
    *PRE_CHOICE_TRANSITIONS,
    {"from": "user_choice_recorded", "event": "accept-as-is", "to": "handoff_complete"},
    {"from": "user_choice_recorded", "event": "diagnose", "to": "semantic_evaluator_started"},
    {"from": "semantic_evaluator_started", "event": "improvement_complete", "to": "handoff_complete"},
]
# 移行前に 166 本へ写されていた形 (COPIED_CONTRACT_V1 が凍結している)。
V1_TRANSITIONS = [
    *PRE_CHOICE_TRANSITIONS,
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
    policy = root / "references/artifact-delivery-policy.json"
    if not policy.exists():
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text((ROOT / "references/artifact-delivery-policy.json").read_text(encoding="utf-8"), encoding="utf-8")
    contract = "artifact_delivery: artifact-delivery-v1\n" if include_contract else ""
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
    phase_activation: str | None = None,
    gate_order: list[str] | None = None,
) -> None:
    if phase_activation is None:
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
                    "phase_activation": phase_activation,
                },
                "phases": [
                    {
                        "id": "legacy-heavy",
                        "title": "Run evaluator workers and revise until pass",
                        **({"choices": choices} if choices is not None else {}),
                    }
                ],
                **({"gate_order": gate_order} if gate_order is not None else {}),
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
            assert mod.read_artifact_delivery(entrypoint.path) == "artifact-delivery-v1"
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


# --- 契約は id で参照し、state machine を写さない (harness-vvd) ---------------------

_PAIRED_BODY = (
    "# Future\n\n## 選ぶ前の実成果物の作成\n成果物を作って見せる。\n\n"
    "## 選んだ深さでの改善の実行\n選んだ深さで評価する。\n"
)


def test_canonical_contract_keeps_the_former_copy_shape_with_the_two_way_choice():
    """移行前の写しと同じ形で、違うのは診断へ進む event が diagnose になった 1 点だけ。"""
    mod = _load_module()
    assert mod.CANONICAL_CONTRACT == {
        "contract": "artifact-delivery-v1",
        "state_machine": {
            "initial": "artifact_created",
            "states": STATES,
            "transitions": TRANSITIONS,
            "pre_choice_forbidden": FORBIDDEN_HEAVY,
            "accept_contexts": {"evaluator": 0, "improver": 0},
        },
        "release": "explicit-only",
        "exhaustive": "explicit-only",
    }


def test_frozen_v1_copy_is_independent_of_the_live_contract():
    """replay artifact-delivery-v1 の再現性: 凍結した写しは移行前の 166 本と同じ形の literal。"""
    mod = _load_module()
    assert mod.COPIED_CONTRACT_V1["state_machine"]["states"] == STATES
    assert mod.COPIED_CONTRACT_V1["state_machine"]["transitions"] == V1_TRANSITIONS
    assert mod.COPIED_CONTRACT_V1["state_machine"]["pre_choice_forbidden"] == FORBIDDEN_HEAVY
    # 正本を 2 択へ変えても凍結側は 4 択の形のまま (同じ object を共有していない)
    live = mod.CANONICAL_CONTRACT["state_machine"]["transitions"]
    assert mod.COPIED_CONTRACT_V1["state_machine"]["transitions"] != live
    assert mod.COPIED_CONTRACT_V1["state_machine"]["transitions"] is not live


def _copied_skill_text(mod, *, newline: str = "\n") -> str:
    import yaml

    copied = yaml.safe_dump(
        {"artifact_delivery": mod.COPIED_CONTRACT_V1}, allow_unicode=True, sort_keys=False
    )
    text = (
        "---\nname: run-x\ndescription: |\n  複数行の\n  説明\n"
        + copied
        + "kind: run\nowner: test\n---\n\n# body\nartifact_delivery: 本文の同名行は触らない\n"
    )
    return text.replace("\n", newline)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_rewrite_copied_contract_keeps_everything_but_the_contract(newline):
    mod = _load_module()
    text = _copied_skill_text(mod, newline=newline)
    out = mod.rewrite_copied_contract(text)
    assert out == (
        "---\nname: run-x\ndescription: |\n  複数行の\n  説明\n"
        "artifact_delivery: artifact-delivery-v1\n"
        "kind: run\nowner: test\n---\n\n# body\nartifact_delivery: 本文の同名行は触らない\n"
    ).replace("\n", newline)
    # 冪等: 移行済みは None (replay を 2 回当てても結果が変わらない)
    assert mod.rewrite_copied_contract(out) is None


def test_rewrite_copied_contract_ignores_files_without_a_copy():
    mod = _load_module()
    assert mod.rewrite_copied_contract("# no frontmatter\n") is None
    assert mod.rewrite_copied_contract("---\nname: run-x\n---\nbody\n") is None


def test_rewrite_copied_contract_refuses_a_drifted_copy():
    """正本と 1 か所でも違う写しは持ち主の意図が混ざっている可能性があるので機械的に消さない。"""
    mod = _load_module()
    text = _copied_skill_text(mod).replace("release: explicit-only", "release: on-demand")
    with pytest.raises(mod.LintError, match="exact copy"):
        mod.rewrite_copied_contract(text)


def test_rewrite_copied_contract_refuses_duplicate_keys():
    mod = _load_module()
    text = _copied_skill_text(mod).replace("kind: run\n", "kind: run\nartifact_delivery: artifact-delivery-v1\n")
    with pytest.raises(mod.LintError, match="2 times"):
        mod.rewrite_copied_contract(text)


def test_print_contract_resolves_the_reference(capsys):
    mod = _load_module()
    assert mod.main(["--print-contract"]) == 0
    assert json.loads(capsys.readouterr().out) == mod.CANONICAL_CONTRACT


def test_copied_state_machine_in_skill_frontmatter_is_rejected(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(tmp_path, _PAIRED_BODY)
    assert mod.lint_repository(tmp_path) == []
    copied = "artifact_delivery:\n  contract: artifact-delivery-v1\n  release: explicit-only\n"
    skill.write_text(skill.read_text(encoding="utf-8").replace("artifact_delivery: artifact-delivery-v1\n", copied), encoding="utf-8")
    errors = mod.lint_repository(tmp_path)
    assert any("contract id only" in error for error in errors)


def test_unknown_contract_id_is_rejected(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(tmp_path, _PAIRED_BODY)
    skill.write_text(skill.read_text(encoding="utf-8").replace("artifact-delivery-v1", "artifact-delivery-v0"), encoding="utf-8")
    errors = mod.lint_repository(tmp_path)
    assert any("must reference artifact-delivery-v1" in error for error in errors)


def test_copied_state_machine_in_workflow_manifest_is_rejected(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(tmp_path, _PAIRED_BODY)
    _write_workflow(skill)
    assert mod.lint_repository(tmp_path) == []
    manifest = skill.parent / "workflow-manifest.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["artifact_delivery_contract"]["state_machine"] = mod.CANONICAL_CONTRACT["state_machine"]
    manifest.write_text(json.dumps(document), encoding="utf-8")
    errors = mod.lint_repository(tmp_path)
    assert any("exactly contract and phase_activation" in error for error in errors)


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda policy: policy["user_choice"].update(improvement_levels=["accept-as-is", "detailed"]), "drifted from DIAGNOSTIC_CHOICES"),
        (lambda policy: policy.update(policy_id="artifact-delivery-v2"), "policy_id must be artifact-delivery-v1"),
    ],
    ids=["choices-drift", "policy-id-drift"],
)
def test_policy_and_lint_cannot_drift(tmp_path: Path, mutate, expected):
    mod = _load_module()
    _write_temp_entrypoint(tmp_path, _PAIRED_BODY)
    policy_path = tmp_path / "references/artifact-delivery-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    mutate(policy)
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    errors = mod.lint_repository(tmp_path)
    assert any(expected in error for error in errors)


def test_missing_policy_fails_closed(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(tmp_path, _PAIRED_BODY)
    (tmp_path / "references/artifact-delivery-policy.json").unlink()
    errors = mod.lint_repository(tmp_path)
    assert any("cannot read the artifact-delivery policy" in error for error in errors)


def test_selected_branch_event_is_derived_from_the_choices():
    """P4 で選択肢を変えても、遷移の event は DIAGNOSTIC_CHOICES 1 か所の変更で追従する。"""
    mod = _load_module()
    events = {(t["from"], t["to"]): t["event"] for t in mod.CANONICAL_CONTRACT["state_machine"]["transitions"]}
    assert events[("user_choice_recorded", "handoff_complete")] == mod.DIAGNOSTIC_CHOICES[0]
    assert events[("user_choice_recorded", "semantic_evaluator_started")] == mod.DIAGNOSTIC_CHOICES[1]
    gated = {(t["from"], t["to"]): t["event"] for t in mod.GATED_CONTRACT["state_machine"]["transitions"]}
    assert gated[("user_choice_recorded", "gate_review_started")] == mod.DIAGNOSTIC_CHOICES[0]
    assert gated[("user_choice_recorded", "diagnosis_delegated")] == mod.DIAGNOSTIC_CHOICES[1]


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
            "artifact_delivery: artifact-delivery-v1\n",
            "goal_seek:\n  fork: subagent\n  max_loops: 5\nartifact_delivery: artifact-delivery-v1\n",
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


_GATED_BODY = """# Future

## Pre-choice usable artifact execution

Create, minimally guard, and present the actual artifact, then record the choice.

## Post-choice selected improvement execution

Run selected improvement only.
"""


def test_gated_orchestrator_activation_requires_gate_order(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(tmp_path, _GATED_BODY)
    _write_workflow(skill, phase_activation=mod.GATED_ORCHESTRATOR_ACTIVATION)
    errors = mod.lint_repository(tmp_path)
    assert any("gate-ordered activation requires a non-empty gate_order" in error for error in errors)


def test_gated_orchestrator_activation_passes_with_gate_order(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(tmp_path, _GATED_BODY)
    _write_workflow(
        skill,
        phase_activation=mod.GATED_ORCHESTRATOR_ACTIVATION,
        gate_order=["G1", "G2"],
    )
    errors = mod.lint_repository(tmp_path)
    assert not any("activation" in error for error in errors)


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
Then ask the user to choose `accept-as-is / diagnose / release`.

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


def test_future_temp_japanese_heading_pair_passes(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        """# Future

## 選ぶ前の実成果物の作成

「目的と出力契約」の最小の実成果物を親コンテキストで作る。effect に応じた最低限の検査（読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物のパス・ハッシュ値・開き方を見せたうえで、現状で試すか診断するかを記録する（記録する値は順に `accept-as-is`・`diagnose`）。現状で試すならその場で引き継ぎを完了とし、後続の節を実行しない。

## 選んだ深さでの改善の実行

以下の既存の節（全体の流れ・ゴールシーク・評価・修正）は、「診断する」が記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。リリースと完全監査は別イベントとして明示されたときだけ行う。
選んだ深さで semantic evaluator を起動し、成果物を修正する。
""",
    )
    assert mod.lint_repository(tmp_path) == []


def test_future_temp_japanese_pre_choice_heavy_loop_fails_like_english(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        """# Future

## 選ぶ前の実成果物の作成

semantic evaluator を起動して評価と修正を繰り返し、その後で作成して提示する。

## 選んだ深さでの改善の実行

選んだ深さで改善を実行する。
""",
    )
    errors = mod.lint_repository(tmp_path)
    assert not any("body requires one ordered" in error for error in errors)
    assert any("pre-choice imperative heavy operation" in error for error in errors)
    assert any("heavy-before-create/present contradiction" in error for error in errors)


@pytest.mark.parametrize(
    ("pre_heading", "post_heading"),
    [
        ("## Pre-choice usable artifact execution", "## 選んだ深さでの改善の実行"),
        ("## 選ぶ前の実成果物の作成", "## Post-choice selected improvement execution"),
    ],
)
def test_future_temp_mixed_language_heading_pair_fails_closed(
    tmp_path: Path, pre_heading: str, post_heading: str
):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        f"""# Future

{pre_heading}

Create, minimally guard, and present the actual artifact, then record the choice.

{post_heading}

Run selected improvement only.
""",
    )
    errors = mod.lint_repository(tmp_path)
    assert any("mixed en/ja pre-choice/post-choice headings are forbidden" in error for error in errors)


def test_future_temp_missing_heading_pair_names_both_canonical_pairs(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(tmp_path, "# Future\n\nCreate, minimally guard, and present the actual artifact.\n")
    errors = mod.lint_repository(tmp_path)
    message = next(error for error in errors if "body requires one ordered" in error)
    for pre_heading, post_heading in mod.CHOICE_HEADING_PAIRS.values():
        assert f"'{pre_heading}' then '{post_heading}'" in message
    assert mod.CHOICE_HEADING_PAIRS == {
        "en": ("## Pre-choice usable artifact execution", "## Post-choice selected improvement execution"),
        "ja": ("## 選ぶ前の実成果物の作成", "## 選んだ深さでの改善の実行"),
    }


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


def test_guarded_external_helper_requires_real_contract_not_metadata(tmp_path):
    mod = _load_module()
    import importlib.util
    spec = importlib.util.spec_from_file_location("delivery_for_guard_test", ROOT / "scripts/build-artifact-delivery.py")
    delivery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(delivery)
    source = ROOT / "plugins/ubm-goal-setting/skills/run-ubm-challenge/SKILL.md"
    skill = tmp_path / "SKILL.md"
    text = delivery._ensure_runtime_root_contract(source.read_text(), skill)
    skill.write_text(text)
    assert mod.lint_guarded_external_entrypoint(skill) == []
    for invalid in (text.replace("effect: external-mutation", "effect: read-only"), text.replace("runtime_root_policy: host-skill-path", "runtime_root_policy: cwd"), text.replace(delivery.EXTERNAL_GUARD_BLOCK_BEGIN_JA, ""), text.replace("external_mutation_guard:", "missing_guard:")):
        skill.write_text(invalid)
        assert mod.lint_guarded_external_entrypoint(skill)
    skill.write_text("---\nbroken: [\n---\n")
    assert mod.lint_guarded_external_entrypoint(skill)


def test_mixed_runtime_locale_and_ubm_order_fail(tmp_path):
    mod = _load_module()
    source = ROOT / "plugins/ubm-goal-setting/skills/run-ubm-challenge/SKILL.md"
    skill = tmp_path / "SKILL.md"
    text = source.read_text()
    skill.write_text(text.replace("## 実行時のルートの決め方", "## Runtime root contract"))
    assert any("language mismatch" in e for e in mod.lint_entrypoint(mod.Entrypoint("ubm-goal-setting", skill)))


# --- 2 択 (harness-znj) と gate 型の状態機械 ------------------------------------


def test_gated_contract_shares_the_pre_choice_prefix_and_has_no_evaluator_state():
    """gate 型は選ぶ前の 4 state を共有し、evaluator の state を持たない (診断は委譲先が行う)。"""
    mod = _load_module()
    machine = mod.GATED_CONTRACT["state_machine"]
    assert machine["states"][:4] == EVENT_ORDER[:4]
    assert machine["transitions"][:3] == PRE_CHOICE_TRANSITIONS
    assert "semantic_evaluator_started" not in machine["states"]
    assert machine["pre_choice_forbidden"] == FORBIDDEN_HEAVY
    assert mod.LOOP_ACTIVATION_STATES[mod.GATED_ORCHESTRATOR_ACTIVATION] in machine["states"]


def test_phase_activation_of_falls_back_to_the_stricter_evaluator_contract(tmp_path: Path):
    mod = _load_module()
    skill = _write_temp_entrypoint(tmp_path, _GATED_BODY)
    assert mod.phase_activation_of(skill.parent) == mod.EVALUATOR_ACTIVATION
    _write_workflow(skill, phase_activation="not-a-contract")
    assert mod.phase_activation_of(skill.parent) == mod.EVALUATOR_ACTIVATION
    _write_workflow(skill, phase_activation=mod.GATED_ORCHESTRATOR_ACTIVATION, gate_order=["G1"])
    assert mod.phase_activation_of(skill.parent) == mod.GATED_ORCHESTRATOR_ACTIVATION


def _add_feedback_loop(skill: Path, activation_state: str) -> None:
    text = skill.read_text(encoding="utf-8")
    head, sep, body = text.partition("\n---\n")
    skill.write_text(
        head + f"\nfeedback_contract:\n  max_iterations: 3\n  activation_state: {activation_state}" + sep + body,
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("activation_state", "expect_error"),
    [("semantic_evaluator_started", True), ("gate_review_started", False)],
)
def test_gated_feedback_loop_must_start_at_gate_review(tmp_path: Path, activation_state: str, expect_error: bool):
    """gate 型に evaluator の state は無いので、差し戻しループは gate_review_started の後だけ動く。"""
    mod = _load_module()
    skill = _write_temp_entrypoint(tmp_path, _GATED_BODY)
    _write_workflow(skill, phase_activation=mod.GATED_ORCHESTRATOR_ACTIVATION, gate_order=["G1", "G2"])
    _add_feedback_loop(skill, activation_state)
    errors = mod.lint_repository(tmp_path)
    hit = any("feedback revise loop must activate post-choice at gate_review_started" in e for e in errors)
    assert hit is expect_error, errors


def test_legacy_four_choice_prose_is_rejected(tmp_path: Path):
    mod = _load_module()
    _write_temp_entrypoint(
        tmp_path,
        "# Future\n\n## 選ぶ前の実成果物の作成\n\n現物を見せたうえで、"
        + LEGACY_FOUR_CHOICE_PRE
        + "。\n\n## 選んだ深さでの改善の実行\n選んだ深さで評価する。\n",
    )
    errors = mod.lint_repository(tmp_path)
    assert any("legacy 4-choice prose at body line" in error for error in errors), errors


LEGACY_FOUR_CHOICE_PRE = "現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）"


def test_rewrite_diagnostic_choices_maps_the_four_choice_prose_to_two(tmp_path: Path):
    """書き換えは決定的で、結果は lint の 4 択検査を通る。変わらない文は None。"""
    mod = _load_module()
    body = (
        "# Future\n\n## 選ぶ前の実成果物の作成\n\n現物を見せたうえで、" + LEGACY_FOUR_CHOICE_PRE + "。\n\n"
        "## 選んだ深さでの改善の実行\n以下は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。\n"
    )
    skill = _write_temp_entrypoint(tmp_path, body)
    text = skill.read_text(encoding="utf-8")
    rewritten = mod.rewrite_diagnostic_choices(text)
    assert rewritten is not None
    assert "現状で試すか診断するかを記録する（記録する値は順に `accept-as-is`・`diagnose`）" in rewritten
    assert "「診断する」が記録されて" in rewritten
    assert mod.legacy_diagnostic_choice_lines(rewritten) == []
    assert mod.rewrite_diagnostic_choices(rewritten) is None
    skill.write_text(rewritten, encoding="utf-8")
    assert mod.lint_repository(tmp_path) == []
