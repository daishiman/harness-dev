"""Bounded improvement result validation for harness-creator."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = REPO_ROOT / "plugins/harness-creator/skills/run-build-skill"
SCRIPT = RUN_BUILD / "scripts/validate-improvement-result.py"
SCHEMA = RUN_BUILD / "schemas/improvement-result.schema.json"
DECISION_SCHEMA = RUN_BUILD / "schemas/improvement-decision.schema.json"
PROMPT = RUN_BUILD / "prompts/R6-bounded-improve.md"
AGENT = REPO_ROOT / "plugins/harness-creator/agents/elegant-bounded-improvement-executor.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_improvement_result", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _sha_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest_sha(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _case(tmp_path: Path) -> dict[str, Path | dict]:
    target_root = tmp_path / "target"
    (target_root / "src").mkdir(parents=True, exist_ok=True)
    (target_root / "src/a.py").write_text("new", encoding="utf-8")
    (target_root / "src/b.py").write_text("same", encoding="utf-8")
    (target_root / "src/c.py").write_text("same-low", encoding="utf-8")
    before = [
        {"path": "src/a.py", "sha256": _file_sha("old"), "size": 3},
        {"path": "src/b.py", "sha256": _file_sha("same"), "size": 4},
        {"path": "src/c.py", "sha256": _file_sha("same-low"), "size": 8},
    ]
    after = copy.deepcopy(before)
    after[0]["sha256"] = _file_sha("new")
    review = {
        "schema_version": 1,
        "run_id": "run-1",
        "subject": "demo-plugin",
        "baseline_fingerprint_sha256": "f" * 64,
        "findings": [
            {
                "id": "IDR-001",
                "title": "critical",
                "description": "must fix",
                "severity": "critical",
                "affects_goal": True,
                "recommendation": "edit a",
                "location": {"path": "src/a.py", "line": 1},
                "remediation_paths": ["src/a.py"],
            },
            {
                "id": "IDR-002",
                "title": "medium",
                "description": "may remain within bounded work",
                "severity": "medium",
                "affects_goal": True,
                "recommendation": "edit b",
                "location": {"path": "src/b.py", "line": 2},
                "remediation_paths": ["src/b.py"],
            },
            {
                "id": "IDR-003",
                "title": "unselected",
                "description": "not authorized",
                "severity": "low",
                "affects_goal": False,
                "recommendation": "do not touch",
                "location": {"path": "src/c.py", "line": 3},
                "remediation_paths": ["src/c.py"],
            },
        ],
    }
    paths = {
        name: tmp_path / f"{name}.json"
        for name in ("before", "after", "review", "decision", "result", "gate_state")
    }
    _write_json(paths["before"], before)
    _write_json(paths["after"], after)
    _write_json(paths["review"], review)
    decision = {
        "schema_version": 1,
        "run_id": "run-1",
        "subject": "demo-plugin",
        "artifact_fingerprint_sha256": "f" * 64,
        "review_sha256": _sha_bytes(paths["review"]),
        "selected_level": "standard",
        "selected_by": "user",
        "user_choice_ref": "conversation:turn-42",
        "improvement_authorized": True,
        "selected_finding_ids": ["IDR-001"],
        "max_rounds": 2,
        "baseline_target_manifest_sha256": _manifest_sha(before),
        "next_stage": "draft",
        "next_profile": "incremental",
        "auto_promote_release": False,
        "auto_promote_exhaustive": False,
        "explicit_exhaustive_confirmation": False,
        "user_choice_event_id": "conversation:turn-42",
        "exhaustive_confirmation_event_id": None,
        "critical_risk_acknowledgement_event_id": None,
        "created_at": "2026-08-20T02:59:00Z",
    }
    _write_json(paths["decision"], decision)
    result = {
        "schema_version": 1,
        "run_id": "run-1",
        "subject": "demo-plugin",
        "review_sha256": _sha_bytes(paths["review"]),
        "decision_sha256": _sha_bytes(paths["decision"]),
        "baseline_target_manifest_sha256": _manifest_sha(before),
        "post_target_manifest_sha256": _manifest_sha(after),
        "selected_level": "standard",
        "rounds_used": 1,
        "changed_paths": ["src/a.py"],
        "change_trace": [
            {
                "path": "src/a.py",
                "finding_ids": ["IDR-001"],
                "summary": "fixed critical issue",
                "validation_refs": ["pytest:test_a"],
            }
        ],
        "finding_outcomes": {
            "resolved": ["IDR-001"],
            "residual": [],
            "regressed": [],
        },
        "four_conditions": {
            key: {
                "verdict": "PASS",
                "summary": f"{key} rechecked",
                "evidence_refs": [
                    {
                        "path": "src/a.py",
                        "line": 1,
                        "sha256": _file_sha("new"),
                    }
                ],
            }
            for key in ("C1", "C2", "C3", "C4")
        },
        "completion_status": "complete",
        "next_stage": "draft",
        "next_profile": "incremental",
        "auto_promote_release": False,
        "auto_promote_exhaustive": False,
        "produced_at": "2026-08-20T03:00:00Z",
    }
    _write_json(paths["result"], result)
    gate_state = {
        "schema_version": 2,
        "artifact_fingerprint_sha256": "f" * 64,
        "subject": "demo-plugin",
        "contract_binding": {},
        "target_root": str(target_root.resolve()),
        "target_roots": [{"path": ".", "kind": "directory"}],
        "target_exclusions": [],
        "target_manifest": before,
        "status": "completed",
        "claim_id": "IRC-" + "a" * 32,
        "claimed_run_id": "run-1",
        "created_at": "2026-08-20T02:00:00Z",
        "review": review,
        "review_sha256": _sha_bytes(paths["review"]),
        "review_content_sha256": _manifest_sha(review),
        "decisions": {"run-1": decision},
    }
    _write_json(paths["gate_state"], gate_state)
    return {**paths, "before_doc": before, "after_doc": after, "review_doc": review,
            "decision_doc": decision, "result_doc": result, "target_root": target_root}


def _rewrite(case: dict, name: str, mutate) -> None:
    path = case[name]
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    _write_json(path, value)


def _validate(mod, case: dict) -> dict:
    return mod.validate_files(
        review_path=case["review"],
        decision_path=case["decision"],
        before_manifest_path=case["before"],
        after_manifest_path=case["after"],
        result_path=case["result"],
        gate_state_path=case["gate_state"],
        target_root=case["target_root"],
    )


def _rebind(case: dict) -> None:
    decision = json.loads(case["decision"].read_text(encoding="utf-8"))
    decision["review_sha256"] = _sha_bytes(case["review"])
    decision["baseline_target_manifest_sha256"] = _manifest_sha(
        json.loads(case["before"].read_text(encoding="utf-8"))
    )
    _write_json(case["decision"], decision)
    result = json.loads(case["result"].read_text(encoding="utf-8"))
    result["review_sha256"] = _sha_bytes(case["review"])
    result["decision_sha256"] = _sha_bytes(case["decision"])
    result["baseline_target_manifest_sha256"] = _manifest_sha(
        json.loads(case["before"].read_text(encoding="utf-8"))
    )
    result["post_target_manifest_sha256"] = _manifest_sha(
        json.loads(case["after"].read_text(encoding="utf-8"))
    )
    _write_json(case["result"], result)
    state = json.loads(case["gate_state"].read_text(encoding="utf-8"))
    review = json.loads(case["review"].read_text(encoding="utf-8"))
    decision = json.loads(case["decision"].read_text(encoding="utf-8"))
    state["review"] = review
    state["review_sha256"] = _sha_bytes(case["review"])
    state["review_content_sha256"] = _manifest_sha(review)
    state["target_manifest"] = json.loads(case["before"].read_text(encoding="utf-8"))
    state["decisions"][decision["run_id"]] = decision
    _write_json(case["gate_state"], state)


def test_valid_bounded_result_passes_schema_and_validator(tmp_path: Path, mod):
    case = _case(tmp_path)
    output = _validate(mod, case)
    assert output["status"] == "pass"
    assert output["changed_paths"] == ["src/a.py"]
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    result = json.loads(case["result"].read_text(encoding="utf-8"))
    assert list(Draft7Validator(schema).iter_errors(result)) == []
    decision_schema = json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))
    decision = json.loads(case["decision"].read_text(encoding="utf-8"))
    assert list(Draft7Validator(decision_schema).iter_errors(decision)) == []


@pytest.mark.parametrize(
    ("name", "mutate", "match"),
    [
        ("decision", lambda v: v.update(review_sha256="0" * 64), "review digest"),
        ("result", lambda v: v.update(decision_sha256="0" * 64), "decision digest"),
        ("decision", lambda v: v.update(baseline_target_manifest_sha256="0" * 64), "baseline manifest"),
        ("result", lambda v: v.update(post_target_manifest_sha256="0" * 64), "post manifest"),
    ],
)
def test_receipts_are_digest_bound(tmp_path: Path, mod, name, mutate, match):
    case = _case(tmp_path)
    _rewrite(case, name, mutate)
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda v: v.update(selected_level="accept-draft"), "accept-draft"),
        (lambda v: v.update(improvement_authorized=False), "not authorized"),
        (lambda v: v.update(selected_finding_ids=[]), "non-empty"),
    ],
)
def test_accept_draft_or_unanswered_choice_cannot_start_executor(tmp_path: Path, mod, mutate, match):
    case = _case(tmp_path)
    _rewrite(case, "decision", mutate)
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


def test_round_limit_is_enforced(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(case, "result", lambda v: v.update(rounds_used=3))
    with pytest.raises(mod.ValidationError, match="rounds_used"):
        _validate(mod, case)


def test_changed_paths_must_equal_manifest_diff(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(case, "result", lambda v: v.update(changed_paths=[]))
    with pytest.raises(mod.ValidationError, match="manifest diff"):
        _validate(mod, case)


def test_declared_remediation_scope_allows_source_and_new_regression_test(tmp_path: Path, mod):
    case = _case(tmp_path)
    test_path = case["target_root"] / "tests/test_a.py"
    test_path.parent.mkdir()
    test_path.write_text("def test_a():\n    assert True\n", encoding="utf-8")
    _rewrite(
        case,
        "review",
        lambda value: value["findings"][0]["remediation_paths"].append("tests/test_a.py"),
    )
    _rewrite(
        case,
        "after",
        lambda value: value.append(
            {
                "path": "tests/test_a.py",
                "sha256": _sha_bytes(test_path),
                "size": test_path.stat().st_size,
            }
        ),
    )
    _rewrite(
        case,
        "result",
        lambda value: (
            value["changed_paths"].append("tests/test_a.py"),
            value["change_trace"].append(
                {
                    "path": "tests/test_a.py",
                    "finding_ids": ["IDR-001"],
                    "summary": "added regression coverage",
                    "validation_refs": ["pytest:test_a"],
                }
            ),
        ),
    )
    _rebind(case)

    assert _validate(mod, case)["changed_paths"] == ["src/a.py", "tests/test_a.py"]


def test_undeclared_third_changed_path_is_rejected(tmp_path: Path, mod):
    case = _case(tmp_path)
    unexpected = case["target_root"] / "src/unexpected.py"
    unexpected.write_text("surprise", encoding="utf-8")
    _rewrite(
        case,
        "after",
        lambda value: value.append(
            {
                "path": "src/unexpected.py",
                "sha256": _sha_bytes(unexpected),
                "size": unexpected.stat().st_size,
            }
        ),
    )
    _rewrite(
        case,
        "result",
        lambda value: (
            value["changed_paths"].append("src/unexpected.py"),
            value["change_trace"].append(
                {
                    "path": "src/unexpected.py",
                    "finding_ids": ["IDR-001"],
                    "summary": "undeclared extra edit",
                    "validation_refs": ["pytest:test_a"],
                }
            ),
        ),
    )
    _rebind(case)

    with pytest.raises(mod.ValidationError, match="remediation scope"):
        _validate(mod, case)


def test_remediation_paths_cannot_escape_authoritative_target_roots(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "review",
        lambda value: value["findings"][0]["remediation_paths"].append("tests/future.py"),
    )
    _rewrite(
        case,
        "gate_state",
        lambda value: value.update(target_roots=[{"path": "src", "kind": "directory"}]),
    )
    _rebind(case)

    with pytest.raises(mod.ValidationError, match="escapes target_roots"):
        _validate(mod, case)


def test_declared_file_deletion_is_an_actual_manifest_diff(tmp_path: Path, mod):
    case = _case(tmp_path)
    (case["target_root"] / "src/b.py").unlink()
    _rewrite(
        case,
        "review",
        lambda value: value["findings"][0]["remediation_paths"].append("src/b.py"),
    )
    _rewrite(case, "after", lambda value: value.pop(1))
    _rewrite(
        case,
        "result",
        lambda value: (
            value["changed_paths"].append("src/b.py"),
            value["change_trace"].append(
                {
                    "path": "src/b.py",
                    "finding_ids": ["IDR-001"],
                    "summary": "removed obsolete file",
                    "validation_refs": ["pytest:test_a"],
                }
            ),
        ),
    )
    _rebind(case)

    assert _validate(mod, case)["changed_paths"] == ["src/a.py", "src/b.py"]


def test_every_changed_path_requires_selected_finding_source_trace(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "result",
        lambda v: v["change_trace"][0].update(finding_ids=["IDR-003"]),
    )
    with pytest.raises(mod.ValidationError, match="unselected finding"):
        _validate(mod, case)

    case = _case(tmp_path)
    _rewrite(
        case,
        "decision",
        lambda v: v["selected_finding_ids"].append("IDR-002"),
    )
    _rewrite(
        case,
        "result",
        lambda v: v["finding_outcomes"]["resolved"].append("IDR-002"),
    )
    _rewrite(
        case,
        "result",
        lambda v: v["change_trace"][0].update(finding_ids=["IDR-002"]),
    )
    _rebind(case)
    with pytest.raises(mod.ValidationError, match="remediation scope"):
        _validate(mod, case)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda v: v["finding_outcomes"]["resolved"].remove("IDR-001"), "closed set"),
        (
            lambda v: v["finding_outcomes"]["residual"].append("IDR-001"),
            "disjoint",
        ),
        (
            lambda v: v["finding_outcomes"]["regressed"].append("IDR-003"),
            "unselected finding",
        ),
    ],
)
def test_finding_outcomes_are_a_disjoint_closed_set(tmp_path: Path, mod, mutate, match):
    case = _case(tmp_path)
    _rewrite(case, "result", mutate)
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


def test_complete_rejects_any_residual_regression_or_nonpass_condition(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "result",
        lambda v: (
            v["finding_outcomes"]["resolved"].remove("IDR-001"),
            v["finding_outcomes"]["residual"].append("IDR-001"),
        ),
    )
    with pytest.raises(mod.ValidationError, match="residual selected"):
        _validate(mod, case)

    case = _case(tmp_path)
    _rewrite(
        case,
        "result",
        lambda v: (
            v["finding_outcomes"]["resolved"].remove("IDR-001"),
            v["finding_outcomes"]["regressed"].append("IDR-001"),
        ),
    )
    with pytest.raises(mod.ValidationError, match="regressed"):
        _validate(mod, case)

    case = _case(tmp_path)
    _rewrite(case, "result", lambda v: v["four_conditions"]["C4"].update(verdict="PARTIAL"))
    with pytest.raises(mod.ValidationError, match="C1-C4"):
        _validate(mod, case)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda v: v.update(next_stage="release"), "next_stage"),
        (lambda v: v.update(next_profile="exhaustive"), "next_profile"),
        (lambda v: v.update(auto_promote_release=True), "auto promotion"),
        (lambda v: v.update(auto_promote_exhaustive=True), "auto promotion"),
    ],
)
def test_result_cannot_promote_beyond_explicit_decision(tmp_path: Path, mod, mutate, match):
    case = _case(tmp_path)
    _rewrite(case, "result", mutate)
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


def test_release_and_exhaustive_require_corresponding_explicit_decision(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "decision",
        lambda v: v.update(next_stage="release", selected_level="standard"),
    )
    with pytest.raises(mod.ValidationError, match="release decision"):
        _validate(mod, case)

    case = _case(tmp_path)
    _rewrite(
        case,
        "decision",
        lambda v: v.update(next_profile="exhaustive", selected_level="release"),
    )
    with pytest.raises(mod.ValidationError, match="exhaustive decision"):
        _validate(mod, case)


def test_manifest_scope_and_paths_fail_closed(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(case, "after", lambda v: v.pop())
    _rebind(case)
    with pytest.raises(mod.ValidationError, match="actual target closure"):
        _validate(mod, case)

    case = _case(tmp_path)
    _rewrite(case, "before", lambda v: v[0].update(path="../outside.py"))
    with pytest.raises(mod.ValidationError, match="relative path"):
        _validate(mod, case)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda v: v.clear(), "non-empty array"),
        (lambda v: v.__setitem__(0, "not-an-object"), "must be an object"),
        (lambda v: v[0].update(sha256="bad"), "sha256 is invalid"),
        (lambda v: v.append(copy.deepcopy(v[0])), "duplicate path"),
        (lambda v: v[0].update(size=-1), "size is invalid"),
    ],
)
def test_manifest_records_fail_closed(tmp_path: Path, mod, mutate, match):
    case = _case(tmp_path)
    _rewrite(case, "before", mutate)
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


@pytest.mark.parametrize(
    ("target", "mutate", "match"),
    [
        ("review", lambda v: v.update(schema_version=2), "review requires"),
        ("review", lambda v: v.update(subject=""), "review subject"),
        ("review", lambda v: v.update(findings={}), "findings must be an array"),
        ("review", lambda v: v["findings"].__setitem__(0, "bad"), "must be an object"),
        ("review", lambda v: v["findings"][0].update(severity="blocker"), "severity"),
        ("decision", lambda v: v.update(schema_version=2), "decision requires"),
        ("decision", lambda v: v.update(run_id="other"), "run_id"),
        ("decision", lambda v: v.update(user_choice_ref=""), "user choice"),
        ("decision", lambda v: v.update(selected_level="unknown"), "invalid or unanswered"),
        ("decision", lambda v: v.update(max_rounds=0), "max_rounds"),
        ("decision", lambda v: v.update(next_stage="ship"), "next_stage"),
        ("decision", lambda v: v.update(next_profile="deep"), "next_profile"),
        ("decision", lambda v: v.update(auto_promote_release=True), "auto promotion"),
        (
            "decision",
            lambda v: v.update(selected_finding_ids=["IDR-999"]),
            "unknown review findings",
        ),
    ],
)
def test_review_and_decision_contracts_fail_closed(tmp_path: Path, mod, target, mutate, match):
    case = _case(tmp_path)
    _rewrite(case, target, mutate)
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda v: v.update(schema_version=2), "result requires"),
        (lambda v: v.update(subject="other"), "run_id/subject"),
        (lambda v: v.update(review_sha256="0" * 64), "result review digest"),
        (lambda v: v.update(baseline_target_manifest_sha256="0" * 64), "result baseline"),
        (lambda v: v.update(selected_level="light"), "selected_level"),
        (lambda v: v.update(change_trace={}), "change_trace must be an array"),
        (lambda v: v["change_trace"].__setitem__(0, "bad"), "must be an object"),
        (lambda v: v["change_trace"][0].update(summary=""), "summary"),
        (lambda v: v["change_trace"][0].update(validation_refs=[]), "must be non-empty"),
        (lambda v: v.update(finding_outcomes=[]), "finding_outcomes must be an object"),
        (lambda v: v.update(four_conditions={}), "exactly C1-C4"),
        (lambda v: v["four_conditions"]["C1"].update(verdict="UNKNOWN"), "verdict"),
        (lambda v: v.update(completion_status="done"), "completion_status"),
        (lambda v: v.update(produced_at=""), "produced_at"),
        (lambda v: v.update(produced_at="not-a-date"), "RFC3339"),
    ],
)
def test_result_contract_fails_closed(tmp_path: Path, mod, mutate, match):
    case = _case(tmp_path)
    _rewrite(case, "result", mutate)
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


def test_decision_created_at_requires_rfc3339(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(case, "decision", lambda v: v.update(created_at="not-a-date"))
    with pytest.raises(mod.ValidationError, match="RFC3339"):
        _validate(mod, case)


def test_incomplete_result_may_report_regression_and_nonpass_condition(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "result",
        lambda v: (
            v.update(completion_status="incomplete"),
            v["finding_outcomes"]["resolved"].remove("IDR-001"),
            v["finding_outcomes"]["regressed"].append("IDR-001"),
            v["four_conditions"]["C1"].update(verdict="FAIL"),
        ),
    )
    assert _validate(mod, case)["completion_status"] == "incomplete"


def test_finding_location_must_be_inside_remediation_scope(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "review",
        lambda v: v["findings"][0].update(remediation_paths=["src/b.py"]),
    )
    _rebind(case)
    with pytest.raises(mod.ValidationError, match="must include location.path"):
        _validate(mod, case)


def test_cli_returns_machine_readable_pass_and_fail(tmp_path: Path):
    case = _case(tmp_path)
    args = [
        sys.executable,
        str(SCRIPT),
        "--review", str(case["review"]),
        "--decision", str(case["decision"]),
        "--before-manifest", str(case["before"]),
        "--after-manifest", str(case["after"]),
        "--result", str(case["result"]),
        "--gate-state", str(case["gate_state"]),
        "--target-root", str(case["target_root"]),
    ]
    passed = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    assert passed.returncode == 0, passed.stderr
    assert json.loads(passed.stdout)["status"] == "pass"

    _rewrite(case, "result", lambda v: v.update(auto_promote_release=True))
    failed = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    assert failed.returncode == 2
    assert "auto promotion" in failed.stderr


def test_prompt_and_agent_define_one_bounded_improvement_worker():
    prompt = PROMPT.read_text(encoding="utf-8")
    agent = AGENT.read_text(encoding="utf-8")
    for token in (
        "selected_finding_ids",
        "max_rounds",
        "baseline_target_manifest",
        "remediation_paths[]",
        "add / delete / modify",
        "{path, line, sha256}",
        "validate-improvement-result.py",
        "--gate-state <state_ref>",
        "--target-root <canonical-target-root>",
        "accept-draft",
        "auto_promote_release=false",
    ):
        assert token in prompt
    assert "elegant-bounded-improvement-executor" in agent
    assert "R6-bounded-improve.md" in agent
    assert "--gate-state <state_ref> --target-root <target_root>" in agent
    assert "remediation_paths[]" in agent
    assert "{path, line, sha256}" in agent
    assert "他Agentを起動しない" in agent


def test_authoritative_gate_state_is_required_and_exact(tmp_path: Path, mod):
    case = _case(tmp_path)
    with pytest.raises(TypeError):
        mod.validate_files(
            review_path=case["review"],
            decision_path=case["decision"],
            before_manifest_path=case["before"],
            after_manifest_path=case["after"],
            result_path=case["result"],
        )

    _rewrite(case, "gate_state", lambda value: value.update(status="claimed"))
    with pytest.raises(mod.ValidationError, match="authoritative gate state"):
        _validate(mod, case)


def test_actual_target_closure_rejects_hidden_or_unreported_file(tmp_path: Path, mod):
    case = _case(tmp_path)
    (case["target_root"] / "src/hidden.py").write_text("hidden edit", encoding="utf-8")

    with pytest.raises(mod.ValidationError, match="actual target closure"):
        _validate(mod, case)


def test_actual_target_digest_rejects_self_reported_after_manifest(tmp_path: Path, mod):
    case = _case(tmp_path)
    (case["target_root"] / "src/b.py").write_text("unreported edit", encoding="utf-8")

    with pytest.raises(mod.ValidationError, match="actual target closure"):
        _validate(mod, case)


def test_actual_target_rejects_symlink_and_root_identity_drift(tmp_path: Path, mod):
    case = _case(tmp_path)
    (case["target_root"] / "src/link.py").symlink_to(case["target_root"] / "src/a.py")
    with pytest.raises(mod.ValidationError, match="symlink"):
        _validate(mod, case)

    case = _case(tmp_path / "root-drift")
    _rewrite(case, "gate_state", lambda value: value.update(target_root=str(tmp_path.resolve())))
    with pytest.raises(mod.ValidationError, match="target_root"):
        _validate(mod, case)

    case = _case(tmp_path / "path-escape")
    _rewrite(
        case,
        "gate_state",
        lambda value: value.update(target_roots=[{"path": "../outside", "kind": "directory"}]),
    )
    with pytest.raises(mod.ValidationError, match="normalized relative path"):
        _validate(mod, case)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda ref: ref.update(path="missing.txt"), "evidence path"),
        (lambda ref: ref.update(line=99), "evidence line"),
        (lambda ref: ref.update(sha256="0" * 64), "evidence digest"),
    ],
)
def test_four_condition_evidence_is_bound_to_real_file_line_and_digest(
    tmp_path: Path, mod, mutate, match
):
    case = _case(tmp_path)
    _rewrite(case, "result", lambda value: mutate(value["four_conditions"]["C1"]["evidence_refs"][0]))
    with pytest.raises(mod.ValidationError, match=match):
        _validate(mod, case)


def test_complete_resolved_finding_requires_actual_changed_source_trace(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "decision",
        lambda value: value["selected_finding_ids"].append("IDR-002"),
    )
    _rewrite(
        case,
        "result",
        lambda value: value["finding_outcomes"]["resolved"].append("IDR-002"),
    )
    _rebind(case)

    with pytest.raises(mod.ValidationError, match="resolved finding.*actual changed source trace"):
        _validate(mod, case)


def test_gate_state_pre_snapshot_and_closed_exclusions_are_authoritative(tmp_path: Path, mod):
    case = _case(tmp_path)
    _rewrite(
        case,
        "gate_state",
        lambda value: value["target_exclusions"].append("src/c.py"),
    )
    with pytest.raises(mod.ValidationError, match="exclusions"):
        _validate(mod, case)

    case = _case(tmp_path / "snapshot")
    _rewrite(case, "gate_state", lambda value: value["target_manifest"].pop())
    with pytest.raises(mod.ValidationError, match="pre snapshot"):
        _validate(mod, case)


def test_gate_state_directory_is_the_only_valid_in_scope_exclusion(tmp_path: Path, mod):
    case = _case(tmp_path)
    state_dir = case["target_root"] / ".gate-state"
    state_dir.mkdir()
    state_path = state_dir / "initial-draft-review.json"
    state = json.loads(case["gate_state"].read_text(encoding="utf-8"))
    state["target_exclusions"] = [".gate-state"]
    _write_json(state_path, state)
    case["gate_state"] = state_path

    assert _validate(mod, case)["status"] == "pass"
