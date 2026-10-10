from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest
import yaml


PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]
INVENTORY = REPO / "plugin-plans" / "dev-graph" / "component-inventory.json"
EVALS = PLUGIN / "EVALS.json"
LINT = REPO / "scripts" / "lint-content-review.py"
CRITERIA_SCHEMA = PLUGIN / "schemas" / "criteria-scenario-verdict.schema.json"
LIVE_TRIAL_ROOT = (
    REPO / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial"
)
LIVE_TRIAL_SCHEMA = LIVE_TRIAL_ROOT / "schemas" / "live-trial-verdict.schema.json"
LIVE_TRIAL_VERDICT = LIVE_TRIAL_ROOT / "scripts" / "live-trial-verdict.py"
POSITIVE_SCENARIOS = PLUGIN / "tests" / "fixtures" / "live-trial-positive-scenarios.json"


def _load_content_lint():
    spec = importlib.util.spec_from_file_location("dev_graph_content_review_lint", LINT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_live_trial_verdict():
    spec = importlib.util.spec_from_file_location(
        "dev_graph_live_trial_verdict", LIVE_TRIAL_VERDICT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _skill_criteria(skill_path: Path) -> dict[str, dict]:
    text = skill_path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _opening, frontmatter, _body = text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    criteria = metadata["feedback_contract"]["criteria"]
    return {criterion["id"]: criterion for criterion in criteria}


def _contained_repo_ref(value: str) -> Path:
    ref = Path(value)
    assert not ref.is_absolute(), f"evidence ref must be repo-relative: {value}"
    path = (REPO / ref).resolve(strict=True)
    path.relative_to(REPO.resolve())
    return path


def _targets() -> list[tuple[str, str, Path, set[str]]]:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in inventory["components"]}
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["criteria_tests"]["components"]
    return [
        (
            component_id,
            Path(contract["skill"]).parent.name,
            PLUGIN / contract["skill"],
            {item["id"] for item in by_id[component_id]["feedback_contract"]["criteria"]},
        )
        for component_id, contract in sorted(evals.items())
    ]


@pytest.mark.parametrize(
    ("component_id", "skill_name", "skill_path", "criteria_ids"),
    _targets(),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_independent_scenario_receipt_covers_exact_criteria(
    component_id: str,
    skill_name: str,
    skill_path: Path,
    criteria_ids: set[str],
) -> None:
    receipt_path = (
        REPO / "eval-log" / "dev-graph" / skill_name / "criteria-test" / "scenario-verdict.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_schema = json.loads(CRITERIA_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(receipt_schema).validate(receipt)
    current_sha = hashlib.sha256(skill_path.read_bytes()).hexdigest()
    assert receipt["target"] == {
        "plugin": "dev-graph",
        "skill": skill_name,
        "component_id": component_id,
        "skill_md_sha256": current_sha,
    }
    assert receipt["verdict"] == "PASS"
    assert receipt["reviewer"].strip()
    assert receipt["reviewer"] != "root"
    assert receipt["loop_scope"] == "both"
    assert receipt["iteration_limit"] == 3
    results = receipt["criteria_results"]
    assert set(results) == criteria_ids
    criteria = _skill_criteria(skill_path)
    assert set(criteria) == criteria_ids
    live_verdict_module = _load_live_trial_verdict()
    live_schema = json.loads(LIVE_TRIAL_SCHEMA.read_text(encoding="utf-8"))
    for criterion_id, result in results.items():
        assert result["status"] == "PASS", f"{component_id}/{criterion_id}"
        expected_verify_by = criteria[criterion_id]["verify_by"]
        assert result["verify_by"] == expected_verify_by, (
            f"{component_id}/{criterion_id}: receipt verify_by must equal SKILL frontmatter"
        )
        assert result["evidence_kind"] in {
            "pytest", "independent-scenario-review", "hybrid", "live-trial"
        }
        assert result["test_refs"]
        assert result["observed"]
        if expected_verify_by != "live-trial":
            continue

        assert result["evidence_kind"] == "live-trial"
        verdict_ref = result["live_trial_verdict_ref"]
        assert verdict_ref in result["test_refs"]
        verdict_path = _contained_repo_ref(verdict_ref)
        expected_live_root = (
            REPO / "eval-log" / "dev-graph" / skill_name / "live-trial"
        ).resolve()
        verdict_path.relative_to(expected_live_root)
        assert verdict_path.name == "verdict.json"
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(live_schema).validate(verdict)
        assert verdict["scenario_id"] == result["scenario_id"]
        assert verdict["target_skill"] == f"dev-graph:{skill_name}"
        assert verdict["tier"] == "live"
        assert verdict["downgrade_reason"] is None
        assert verdict["actual_model"]
        assert verdict["transcript_sha256"] is not None
        assert verdict["environment"]["transcript_layer"] == "jsonl"
        assert verdict["goal_verdict"] == {"result": "PASS", "blockers": []}
        assert verdict["overall"] == {
            "launch": "PASS",
            "completion": "PASS",
            "goal_fit": "PASS",
            "verdict": "PASS",
        }
        assert verdict["skill_dir_tree_sha"] == live_verdict_module.skill_dir_tree_sha(
            skill_path.parent
        ), f"{component_id}/{criterion_id}: stale behavior closure digest"


def _synthetic_scenario_receipt(verdict: str, statuses: tuple[str, ...]) -> dict:
    return {
        "schema_version": "1.1.0",
        "target": {
            "plugin": "dev-graph", "skill": "synthetic-contract-test",
            "component_id": "C02", "skill_md_sha256": "0" * 64,
        },
        "verdict": verdict,
        "reviewer": "independent-contract-test",
        "loop_scope": "both",
        "iteration_limit": 3,
        "criteria_results": {
            f"OUT{index}": {
                "status": status, "verify_by": "test", "evidence_kind": "pytest",
                "test_refs": ["synthetic/contract-case"], "observed": f"Synthetic result: {status}",
            }
            for index, status in enumerate(statuses, start=1)
        },
    }


@pytest.mark.parametrize(("verdict", "statuses", "valid"), [
    ("PASS", ("PASS", "PASS"), True),
    ("FAIL", ("PASS", "FAIL"), True),
    ("PASS", ("PASS", "FAIL"), False),
    ("FAIL", ("PASS", "PASS"), False),
    ("FAIL", ("PASS", "UNKNOWN"), False),
    ("UNKNOWN", ("PASS", "FAIL"), False),
])
def test_failure_receipt_contract_preserves_verdict_consistency(
    verdict: str, statuses: tuple[str, ...], valid: bool,
) -> None:
    schema = json.loads(CRITERIA_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    receipt = _synthetic_scenario_receipt(verdict, statuses)
    if valid:
        validator.validate(receipt)
    else:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(receipt)


@pytest.mark.parametrize(("status", "has_verdict_ref", "valid"), [
    ("FAIL", False, True),
    ("FAIL", True, True),
    ("PASS", False, False),
    ("PASS", True, True),
])
def test_live_receipt_contract_requires_actual_verdict_only_for_pass(
    status: str, has_verdict_ref: bool, valid: bool,
) -> None:
    receipt = _synthetic_scenario_receipt(status, (status,))
    result = receipt["criteria_results"]["OUT1"]
    result.update({
        "verify_by": "live-trial", "evidence_kind": "live-trial",
        "scenario_id": "synthetic-planned-scenario",
        "test_refs": ["synthetic/host-blocking-report"],
        "observed": "Synthetic fixture: prerequisite blocked; no live verdict exists." if not has_verdict_ref
                    else "Synthetic fixture: attempted run has an explicit verdict reference.",
    })
    if has_verdict_ref:
        result["live_trial_verdict_ref"] = "synthetic/attempted-run/verdict.json"
    schema = json.loads(CRITERIA_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    if valid:
        validator.validate(receipt)
    else:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(receipt)


def test_failed_receipt_remains_blocked_by_acceptance_gate(tmp_path, monkeypatch) -> None:
    component_id, skill_name, skill_path, criteria_ids = _targets()[0]
    receipt = _synthetic_scenario_receipt("FAIL", ("FAIL",))
    receipt["target"] = {
        "plugin": "dev-graph", "skill": skill_name, "component_id": component_id,
        "skill_md_sha256": hashlib.sha256(skill_path.read_bytes()).hexdigest(),
    }
    result = receipt["criteria_results"]["OUT1"]
    receipt["criteria_results"] = {criterion_id: dict(result) for criterion_id in criteria_ids}
    schema = json.loads(CRITERIA_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(receipt)
    receipt_path = tmp_path / "eval-log" / "dev-graph" / skill_name / "criteria-test" / "scenario-verdict.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setitem(globals(), "REPO", tmp_path)
    with pytest.raises(AssertionError, match="FAIL"):
        test_independent_scenario_receipt_covers_exact_criteria(
            component_id, skill_name, skill_path, criteria_ids,
        )


def test_positive_live_trial_scenarios_cover_out1_without_eval_log_fixture_coupling() -> None:
    suite = json.loads(POSITIVE_SCENARIOS.read_text(encoding="utf-8"))
    scenarios = suite["scenarios"]
    assert suite["schema_version"] == "1.0.0"
    assert {(item["component_id"], item["criterion_id"]) for item in scenarios} == {
        ("C02", "OUT1"),
        ("C03", "OUT1"),
        ("C04", "OUT1"),
        ("C19", "OUT1"),
    }
    assert len({item["scenario_id"] for item in scenarios}) == len(scenarios)
    inventory_targets = {
        component_id: (skill_name, skill_path)
        for component_id, skill_name, skill_path, _criteria_ids in _targets()
    }
    for scenario in scenarios:
        assert scenario["mode"] == "positive"
        assert scenario["task_args_template"].strip()
        assert "--dry-run" not in scenario["task_args_template"]
        assert len(scenario["required_observations"]) >= 3
        assert all(item.strip() for item in scenario["required_observations"])
        skill_name, skill_path = inventory_targets[scenario["component_id"]]
        assert scenario["skill"] == skill_name
        criterion = _skill_criteria(skill_path)[scenario["criterion_id"]]
        assert criterion["loop_scope"] == "outer"
        assert criterion["verify_by"] == "live-trial"


@pytest.mark.parametrize(
    ("component_id", "skill_name", "skill_path", "criteria_ids"),
    _targets(),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_canonical_content_reviews_are_current_and_complete(
    component_id: str,
    skill_name: str,
    skill_path: Path,
    criteria_ids: set[str],
) -> None:
    lint = _load_content_lint()
    review_dir = REPO / "eval-log" / "dev-graph" / skill_name / "content-review"
    for filename in ("elegance-verdict.json", "rubric-verdict.json"):
        error = lint._check_verdict(
            review_dir / filename,
            "dev-graph",
            skill_name,
            filename,
        )
        assert error is None, f"{component_id}/{filename}: {error}"
        verdict = json.loads((review_dir / filename).read_text(encoding="utf-8"))
        loop = verdict["feedback_loop"]
        assert set(loop["criteria_evaluated"]) == criteria_ids
        assert loop["loop_scope"] == "both"
        assert loop["iteration_limit"] == 3
        assert loop["iteration"] <= loop["iteration_limit"]
        assert loop["next_action"] == "none"
