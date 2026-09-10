"""Durable initial-draft diagnosis and user-selected improvement gate."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = REPO_ROOT / "plugins/harness-creator/skills/run-build-skill"
SCRIPT = RUN_BUILD / "scripts/build-improvement-gate.py"
LAUNCH_SCRIPT = RUN_BUILD / "scripts/build-review-launch.py"
PROOF_SCRIPT = RUN_BUILD / "scripts/build-usable-draft-proof.py"
METHODS = REPO_ROOT / "plugins/harness-creator/skills/run-elegant-review/references/thought-methods.yaml"
LEVELS = RUN_BUILD / "references/improvement-levels.json"
REVIEW_SCHEMA = RUN_BUILD / "schemas/initial-draft-review.schema.json"
DECISION_SCHEMA = RUN_BUILD / "schemas/improvement-decision.schema.json"
EVENT_SCHEMA = RUN_BUILD / "schemas/improvement-user-event.schema.json"
PRESENTATION_SCHEMA = RUN_BUILD / "schemas/artifact-presentation-receipt.schema.json"
PRE_DIAGNOSTIC_SCHEMA = RUN_BUILD / "schemas/pre-diagnostic-choice-event.schema.json"
COMMAND = REPO_ROOT / "plugins/harness-creator/commands/capability-build.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_improvement_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_launch_module():
    spec = importlib.util.spec_from_file_location("build_review_launch_for_gate", LAUNCH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_proof_module():
    spec = importlib.util.spec_from_file_location("produce_usable_draft_proof_for_gate", PROOF_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _verification_plan(*, run_id: str = "build-20260820-01", status: str = "usable-draft", ready: bool = True) -> dict:
    return {
        "schema_version": 1,
        "subject": "demo-plugin",
        "run_id": run_id,
        "profile": "incremental",
        "stage": "draft",
        "stage_gate": {
            "status": status,
            "handoff_ready": ready,
            "auto_promote": False,
            "deferred_to_release": ["semantic:demo"],
        },
        "obligations": [
            {"id": "build:demo", "kind": "generative", "stage": "draft", "fingerprint_sha256": "a" * 64},
            {"id": "machine:demo", "kind": "deterministic", "stage": "draft", "fingerprint_sha256": "b" * 64},
            {"id": "semantic:demo", "kind": "semantic", "stage": "release", "fingerprint_sha256": "c" * 64},
        ],
    }


def _write_capability_artifact(path: Path, capability_kind: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if capability_kind == "skill":
        path.write_text(
            "---\nname: run-gate-test\ndescription: A deterministic skill artifact for gate tests.\n"
            "kind: run\nversion: 1.0.0\nowner: team-test\ntriggers:\n  - when gate tests run\n---\n# Gate test\n",
            encoding="utf-8",
        )
        return path
    value = {
        "name": f"demo-{capability_kind}",
        "description": f"{capability_kind} capability artifact with a deterministic validation contract.",
        "kind": capability_kind,
        "version": "1.0.0",
        "owner": "team-test",
    }
    if capability_kind == "agent":
        value.update(tools=["Read"], isolation="fork", phase="draft")
    elif capability_kind == "hook":
        value.update(event="PreToolUse", command="python3 validate.py", timeout_ms=1000)
    elif capability_kind == "command":
        value.update({"argument-hint": "<target>", "allowed-tools": ["Read"]})
    elif capability_kind == "prompt":
        value.update(layers=[{"index": index, "title": f"Layer {index}"} for index in range(1, 8)])
    elif capability_kind == "workflow":
        value.update(phases=[{"id": "draft", "agents": ["builder"]}])
    elif capability_kind == "plugin-composition":
        value.update(capabilities=[{"kind": "hook", "ref": "hook:demo"}])
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _usable_draft_proof(tmp_path: Path, plan: dict, *, capability_kind: str = "skill", capability_artifact: Path | None = None) -> dict:
    proof_mod = _load_proof_module()
    identity = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    proof_dir = tmp_path / "zz-proof-inputs" / identity / capability_kind
    plan_path = proof_dir / "verification-plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    upstream_phase = "content-review" if capability_kind == "skill" else "non-skill-build-lint"
    receipt_types = ("content-review",) if capability_kind == "skill" else ("generation", "kind-lint")
    receipts = []
    for receipt_type in receipt_types:
        evidence = proof_dir / f"{receipt_type}.txt"
        evidence.write_text(f"{capability_kind}:{receipt_type}\n", encoding="utf-8")
        receipt = proof_dir / f"{receipt_type}-receipt.json"
        receipt.write_text(json.dumps({
            "schema_version": 1,
            "capability_kind": capability_kind,
            "producer_phase": upstream_phase,
            "receipt_type": receipt_type,
            "status": "PASS",
            "verification_plan_sha256": plan_sha,
            "evidence_refs": [{
                "path": evidence.relative_to(tmp_path).as_posix(),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }],
        }), encoding="utf-8")
        receipts.append(receipt)
    if capability_artifact is None:
        filename = "SKILL.md" if capability_kind == "skill" else "plugin-composition.json" if capability_kind == "plugin-composition" else "capability.json"
        capability_artifact = _write_capability_artifact(
            tmp_path / "zz-proof-artifacts" / identity / capability_kind / filename,
            capability_kind,
        )
    artifact_ref = capability_artifact.resolve(strict=True).relative_to(tmp_path.resolve(strict=True))
    return proof_mod.produce(
        verification_plan=plan_path,
        capability_kind=capability_kind,
        capability_artifact=artifact_ref,
        upstream_receipts=receipts,
        repo_root=tmp_path,
    )


def _usable_draft_proof_file(tmp_path: Path, plan: dict, *, capability_kind: str = "skill", capability_artifact: Path | None = None) -> Path:
    proof = _usable_draft_proof(tmp_path, plan, capability_kind=capability_kind, capability_artifact=capability_artifact)
    path = tmp_path / "runtime" / f"{capability_kind}-usable-draft-proof.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof), encoding="utf-8")
    return path


def _scope_with_proof(mod, tmp_path: Path, targets: list[Path], state_dir: Path, proof: dict) -> dict:
    artifact = tmp_path / proof["capability_artifact"]["path"]
    return mod.build_target_scope([*targets, artifact], root=tmp_path, state_dir=state_dir)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _presentation_and_prechoice(
    mod,
    *,
    plan: dict,
    proof: dict,
    manifest: list[dict],
    diagnostic_level: str = "detailed",
) -> tuple[dict, dict]:
    binding = mod.contract_binding(manifest)
    proof_time = mod._parse_datetime(proof["generated_at"], "proof generated_at")
    presented_at = proof_time + timedelta(microseconds=1)
    choice_at = presented_at + timedelta(microseconds=1)
    artifact = proof["capability_artifact"]
    presentation = {
        "schema_version": 1,
        "event_id": "artifact-presented-current-turn",
        "event_type": "artifact-presented",
        "source": "host",
        "run_id": plan["run_id"],
        "subject": plan["subject"],
        "artifact_path": artifact["path"],
        "artifact_sha256": artifact["sha256"],
        "target_manifest_sha256": binding["target_manifest_sha256"],
        "contract_binding_sha256": mod._canonical_sha(binding),
        "usable_draft_proof_sha256": mod._canonical_sha(proof),
        "artifact_created_at": _rfc3339(proof_time),
        "smoke": {"status": "PASS", "mode": "parse-or-open", "exit_code": 0},
        "occurred_at": _rfc3339(presented_at),
    }
    choice = {
        "schema_version": 1,
        "event_id": "pre-diagnostic-choice-current-turn",
        "event_type": "pre-diagnostic-choice",
        "source": "user",
        "run_id": plan["run_id"],
        "subject": plan["subject"],
        "artifact_path": artifact["path"],
        "artifact_sha256": artifact["sha256"],
        "target_manifest_sha256": binding["target_manifest_sha256"],
        "contract_binding_sha256": mod._canonical_sha(binding),
        "presentation_receipt_sha256": mod._canonical_sha(presentation),
        "selected_level": diagnostic_level,
        "occurred_at": _rfc3339(choice_at),
    }
    return presentation, choice


def _cli_pre_diagnostic_args(
    mod,
    tmp_path: Path,
    *,
    plan: dict,
    proof_path: Path,
    target_paths: list[Path],
    state_dir: Path,
    diagnostic_level: str = "detailed",
) -> tuple[list[str], dict, dict]:
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    scope = mod.build_target_scope(target_paths, root=tmp_path, state_dir=state_dir)
    presentation, choice = _presentation_and_prechoice(
        mod,
        plan=plan,
        proof=proof,
        manifest=scope["target_manifest"],
        diagnostic_level=diagnostic_level,
    )
    runtime = tmp_path / "runtime" / f"pre-diagnostic-{diagnostic_level}"
    runtime.mkdir(parents=True, exist_ok=True)
    presentation_path = runtime / "artifact-presentation.json"
    choice_path = runtime / "pre-diagnostic-choice.json"
    presentation_path.write_text(json.dumps(presentation), encoding="utf-8")
    choice_path.write_text(json.dumps(choice), encoding="utf-8")
    return [
        "--artifact-presentation-receipt", str(presentation_path),
        "--pre-diagnostic-choice-event", str(choice_path),
    ], presentation, choice


def _proof_artifact_from_file(tmp_path: Path, proof_path: Path) -> Path:
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    return tmp_path / proof["capability_artifact"]["path"]


def _claim(mod, tmp_path: Path, *, plan: dict | None = None) -> dict:
    plan = plan or _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "review-state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    manifest = scope["target_manifest"]
    presentation, pre_diagnostic_choice = _presentation_and_prechoice(
        mod, plan=plan, proof=proof, manifest=manifest
    )
    result = mod.build_gate(
        plan,
        target_manifest=manifest,
        target_scope=scope,
        usable_draft_proof=proof,
        artifact_presentation_receipt=presentation,
        pre_diagnostic_choice_event=pre_diagnostic_choice,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    return {
        "plan": plan,
        "target": target,
        "manifest": manifest,
        "scope": scope,
        "proof": proof,
        "presentation": presentation,
        "pre_diagnostic_choice": pre_diagnostic_choice,
        "root": tmp_path,
        "state_dir": state_dir,
        "claim": result,
    }


def _default_findings(path: str) -> list[dict]:
    return [
        {
            "id": "IDR-001", "title": "critical", "description": "critical issue",
            "severity": "critical", "affects_goal": True, "actionable": True,
            "recommendation": "fix critical", "location": {"path": path, "line": 1},
            "remediation_paths": [path],
            "condition_signals": ["C1"],
        },
        {
            "id": "IDR-002", "title": "goal medium", "description": "goal medium issue",
            "severity": "medium", "affects_goal": True, "actionable": True,
            "recommendation": "fix medium", "location": {"path": path, "line": 1},
            "remediation_paths": [path],
            "condition_signals": ["C2"],
        },
        {
            "id": "IDR-003", "title": "non-actionable", "description": "informational issue",
            "severity": "medium", "affects_goal": False, "actionable": False,
            "recommendation": "observe only", "location": {"path": path, "line": 1},
            "remediation_paths": [path],
            "condition_signals": ["C3"],
        },
        {
            "id": "IDR-004", "title": "low", "description": "low issue",
            "severity": "low", "affects_goal": False, "actionable": True,
            "recommendation": "consider low", "location": {"path": path, "line": 1},
            "remediation_paths": [path],
            "condition_signals": ["C4"],
        },
    ]


def _consume_launch(mod, env: dict, *, runtime: str = "codex") -> dict:
    if "launch" in env:
        return env["launch"]
    state_path = Path(env["claim"]["state_ref"])
    request_id = "IRL-" + hashlib.sha256(
        f"{env['claim']['initial_review']['claim_id']}:{runtime}".encode("utf-8")
    ).hexdigest()
    choice_at = mod._parse_datetime(
        env["pre_diagnostic_choice"]["occurred_at"], "pre-diagnostic choice occurred_at"
    )
    consumed_at = choice_at + timedelta(microseconds=1)
    receipt = {
        "claim_id": env["claim"]["initial_review"]["claim_id"],
        "artifact_fingerprint_sha256": env["claim"]["artifact_fingerprint_sha256"],
        "run_id": env["plan"]["run_id"],
        "runtime": runtime,
        "request_id": request_id,
        "consumed_at": _rfc3339(consumed_at),
        "lease_expires_at": _rfc3339(consumed_at + timedelta(minutes=5)),
        "delivery_attempts": 1,
    }
    with mod._locked_state(state_path):
        mod._atomic_write_json(mod._launch_receipt_path(state_path), receipt)
    env["launch"] = receipt
    return receipt


def _review(mod, env: dict, *, findings: list[dict] | None = None, recommended: str = "standard", consume_launch: bool = True) -> dict:
    launch = _consume_launch(mod, env) if consume_launch else {
        "request_id": "IRL-" + "a" * 64,
        "runtime": "codex",
    }
    findings = findings if findings is not None else _default_findings(env["manifest"][0]["path"])
    finding_ids = [finding["id"] for finding in findings]
    condition_refs = {
        key: [finding["id"] for finding in findings if key in finding["condition_signals"]]
        for key in ("C1", "C2", "C3", "C4")
    }
    conditions = {}
    for key, refs in condition_refs.items():
        severities = {finding["severity"] for finding in findings if finding["id"] in refs}
        verdict = "FAIL" if "critical" in severities else "PARTIAL" if refs else "PASS"
        conditions[key] = {"verdict": verdict, "summary": f"{key} diagnosis", "finding_refs": refs}
    method_ids = mod.load_method_ids(METHODS)
    produced_at = mod._parse_datetime(launch.get("consumed_at", env["pre_diagnostic_choice"]["occurred_at"]), "launch consumed_at") + timedelta(microseconds=1)
    return {
        "schema_version": 1,
        "run_id": env["plan"]["run_id"],
        "subject": env["plan"]["subject"],
        "baseline_fingerprint_sha256": env["claim"]["baseline_fingerprint_sha256"],
        "review_claim_id": env["claim"]["initial_review"]["claim_id"],
        "launch_request_id": launch["request_id"],
        "contract_binding": env["claim"]["contract_binding"],
        "target_manifest": env["manifest"],
        "evaluator": {"id": "elegant-initial-draft-evaluator", "context_count": 1, "runtime": launch["runtime"]},
        "review_mode": "diagnostic-only",
        "edited_target": False,
        "thought_reset": {
            "performed": True,
            "physical_deletion_performed": False,
            "parent_history_used": False,
            "fresh_target_read": True,
            "attested_at": _rfc3339(produced_at),
        },
        "evidence": [{"id": "EVD-001", "path": env["manifest"][0]["path"], "line": 1}],
        "method_observations": [
            {
                "method_id": method_id,
                "rationale": f"{method_id} applies its canonical lens to this artifact",
                "observation": f"{method_id} observation",
                "evidence_refs": ["EVD-001"],
                "finding_refs": finding_ids if index == 0 else [],
            }
            for index, method_id in enumerate(method_ids)
        ],
        "findings": findings,
        "four_conditions": conditions,
        "recommended_level": recommended,
        "summary": "Initial diagnosis completed without editing the target.",
        "produced_at": _rfc3339(produced_at),
    }


def _complete(mod, env: dict, review: dict | None = None, *, raw_sha: str | None = None) -> tuple[dict, dict]:
    review = review or _review(mod, env)
    result = mod.build_gate(
        env["plan"], target_manifest=env["manifest"], target_scope=env["scope"], state_dir=env["state_dir"],
        usable_draft_proof=env["proof"],
        artifact_presentation_receipt=env["presentation"],
        pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
        review=review, review_source_sha256=raw_sha,
        claim_id=env["claim"]["initial_review"]["claim_id"],
        methods_path=METHODS, levels_path=LEVELS,
    )
    return review, result


def _event(env: dict, completed: dict, event_type: str, *, event_id: str, selected_level: str | None = None, occurred_at: str | None = None) -> dict:
    if occurred_at is None:
        state = json.loads(Path(completed["state_ref"]).read_text(encoding="utf-8"))
        occurred_at = _rfc3339(
            datetime.fromisoformat(state["review"]["produced_at"].replace("Z", "+00:00"))
            + timedelta(microseconds=1)
        )
    event = {
        "schema_version": 1,
        "event_id": event_id,
        "event_type": event_type,
        "source": "user",
        "run_id": env["plan"]["run_id"],
        "subject": env["plan"]["subject"],
        "artifact_fingerprint_sha256": completed["artifact_fingerprint_sha256"],
        "review_sha256": completed["initial_review"]["review_sha256"],
        "occurred_at": occurred_at,
    }
    if selected_level is not None:
        event["selected_level"] = selected_level
    return event


def _select(mod, env: dict, completed: dict, level: str, *, choice: dict | None = None, exhaustive: dict | None = None, risk: dict | None = None) -> dict:
    choice = choice or _event(env, completed, "improvement-level-selected", event_id=f"turn-choice-{level}", selected_level=level)
    return mod.build_gate(
        env["plan"], target_manifest=env["manifest"], target_scope=env["scope"], state_dir=env["state_dir"],
        usable_draft_proof=env["proof"],
        artifact_presentation_receipt=env["presentation"],
        pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
        selected_level=level, choice_event=choice,
        exhaustive_confirmation_event=exhaustive, risk_acknowledgement_event=risk,
        methods_path=METHODS, levels_path=LEVELS,
    )


def test_not_ready_plan_cannot_enter_the_proof_gated_review(mod, tmp_path: Path):
    plan = _verification_plan()
    proof = _usable_draft_proof(tmp_path, plan)
    plan["stage_gate"].update(status="draft-building", handoff_ready=False)
    target = tmp_path / "target.md"
    target.write_text("draft", encoding="utf-8")
    state_dir = tmp_path / "state"
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    manifest = scope["target_manifest"]
    with pytest.raises(mod.GateError, match="stage_gate"):
        mod.build_gate(plan, target_manifest=manifest, target_scope=scope, usable_draft_proof=proof, state_dir=state_dir, methods_path=METHODS, levels_path=LEVELS)
    assert list(state_dir.glob("*.json")) == []


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda value: value.update(schema_version=2), "schema_version"),
        (lambda value: value.update(stage="release"), "stage=draft"),
        (lambda value: value.update(run_id=""), "run_id"),
        (lambda value: value["stage_gate"].update(auto_promote=True), "auto promotion"),
        (lambda value: value.update(obligations=[]), "obligations"),
    ],
)
def test_verification_plan_fails_closed(mod, tmp_path: Path, mutate, match):
    plan = _verification_plan()
    proof = _usable_draft_proof(tmp_path, plan)
    mutate(plan)
    target = tmp_path / "target.md"
    target.write_text("draft", encoding="utf-8")
    state_dir = tmp_path / "state"
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    manifest = scope["target_manifest"]
    with pytest.raises(mod.GateError, match=match):
        mod.build_gate(plan, target_manifest=manifest, target_scope=scope, usable_draft_proof=proof, state_dir=state_dir, methods_path=METHODS, levels_path=LEVELS)


@pytest.mark.parametrize(
    "capability_kind",
    ["skill", "agent", "hook", "command", "plugin-composition", "prompt", "workflow"],
)
def test_all_seven_capability_kinds_require_producer_proof_before_gate_claim(mod, tmp_path: Path, capability_kind: str):
    plan = _verification_plan(run_id=f"run-{capability_kind}")
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "state"
    proof = _usable_draft_proof(tmp_path, plan, capability_kind=capability_kind)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    result = mod.build_gate(
        plan,
        target_manifest=scope["target_manifest"],
        target_scope=scope,
        usable_draft_proof=proof,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    assert result["status"] == "awaiting-artifact-presentation"
    assert result["initial_review"]["authorized"] is False
    assert not list(state_dir.glob("initial-draft-review-*.json"))

    presentation, pre_choice = _presentation_and_prechoice(
        mod, plan=plan, proof=proof, manifest=scope["target_manifest"]
    )
    claimed = mod.build_gate(
        plan,
        target_manifest=scope["target_manifest"],
        target_scope=scope,
        usable_draft_proof=proof,
        artifact_presentation_receipt=presentation,
        pre_diagnostic_choice_event=pre_choice,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    assert claimed["status"] == "initial-review-required"
    assert claimed["initial_review"]["authorized"] is True


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda p: p.update(status="FAIL"), "status=PASS"),
        (lambda p: p.update(capability_kind="agent"), "upstream_phase"),
        (lambda p: p.update(verification_plan_sha256="0" * 64), "plan sha256"),
        (lambda p: p.update(upstream_receipts=[]), "incomplete upstream"),
        (lambda p: p["stage_gate"].update(auto_promote=True), "non-promoting"),
    ],
)
def test_usable_draft_proof_fails_closed_on_status_kind_digest_upstream_or_gate_mismatch(mod, tmp_path: Path, mutate, match):
    plan = _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    mutate(proof)
    with pytest.raises(mod.GateError, match=match):
        mod.build_gate(
            plan,
            target_manifest=scope["target_manifest"],
            target_scope=scope,
            usable_draft_proof=proof,
            state_dir=state_dir,
            methods_path=METHODS,
            levels_path=LEVELS,
        )


def test_usable_draft_proof_rejects_tampered_upstream_receipt_after_production(mod, tmp_path: Path):
    plan = _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    receipt = tmp_path / proof["upstream_receipts"][0]["path"]
    receipt.write_text("{}", encoding="utf-8")
    with pytest.raises(mod.GateError, match="receipt sha256 mismatch"):
        mod.build_gate(
            plan,
            target_manifest=scope["target_manifest"],
            target_scope=scope,
            usable_draft_proof=proof,
            state_dir=state_dir,
            methods_path=METHODS,
            levels_path=LEVELS,
        )


def test_method_and_level_ssots_fail_closed_when_drifted(mod, tmp_path: Path):
    methods = tmp_path / "thought-methods.yaml"
    methods.write_text('version: "1"\ntotal: 1\n  - id: only-one\n', encoding="utf-8")
    with pytest.raises(mod.GateError, match="30 unique"):
        mod.load_method_ids(methods)
    levels = json.loads(LEVELS.read_text(encoding="utf-8"))
    levels["levels"]["light"]["max_rounds"] = "many"
    levels_path = tmp_path / "levels.json"
    levels_path.write_text(json.dumps(levels), encoding="utf-8")
    with pytest.raises(mod.GateError, match="max_rounds"):
        mod.load_levels(levels_path)


def test_low_level_contract_helpers_fail_closed(mod, tmp_path: Path):
    with pytest.raises(mod.GateError, match="non-empty date-time"):
        mod._parse_datetime(None, "event")
    with pytest.raises(mod.GateError, match="timezone"):
        mod._parse_datetime("2026-08-20T00:00:00", "event")
    with pytest.raises(mod.GateError, match="must be an object"):
        mod._require_exact_keys([], required={"id"}, label="receipt")
    with pytest.raises(mod.GateError, match="missing required"):
        mod._require_exact_keys({}, required={"id"}, label="receipt")
    with pytest.raises(mod.GateError, match="cannot read thought-methods"):
        mod.load_method_ids(tmp_path / "missing-methods.yaml")
    versionless = tmp_path / "versionless.yaml"
    versionless.write_text("total: 30\n", encoding="utf-8")
    with pytest.raises(mod.GateError, match="version is required"):
        mod._method_catalog_version(versionless)
    invalid_levels = tmp_path / "invalid-levels.json"
    invalid_levels.write_text("{", encoding="utf-8")
    with pytest.raises(mod.GateError, match="cannot read improvement level"):
        mod.load_levels(invalid_levels)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda d: d.update(schema_version=2), "schema_version=1"),
        (lambda d: d["levels"].pop("light"), "closed level set"),
        (lambda d: d.update(offered_order=["light"] * 5), "five unique"),
        (lambda d: d["levels"]["light"].update(label=""), "label/description"),
        (lambda d: d["levels"]["light"].update(selection="mystery"), "selection policy"),
        (lambda d: d["levels"]["light"].update(next_stage="unknown"), "next_stage"),
        (lambda d: d["levels"]["light"].update(next_profile="unknown"), "next_profile"),
        (lambda d: d["levels"]["light"].update(offered_by_default="yes"), "must be boolean"),
        (lambda d: d["levels"]["accept-draft"].update(selection="all"), "zero-edit"),
        (lambda d: d["levels"]["light"].update(offered_by_default=False), "offered levels"),
        (lambda d: d["levels"]["release"].update(next_stage="draft"), "release/incremental"),
        (lambda d: d["levels"]["exhaustive"].update(offered_by_default=True), "separate release/exhaustive"),
    ],
)
def test_each_improvement_level_invariant_is_fail_closed(mod, tmp_path: Path, mutate, match):
    levels = json.loads(LEVELS.read_text(encoding="utf-8"))
    mutate(levels)
    path = tmp_path / "levels.json"
    path.write_text(json.dumps(levels), encoding="utf-8")
    with pytest.raises(mod.GateError, match=match):
        mod.load_levels(path)


def test_target_and_draft_proof_contracts_fail_closed(mod, tmp_path: Path):
    with pytest.raises(mod.GateError, match="at least one target"):
        mod.build_target_manifest([], root=tmp_path)
    with pytest.raises(mod.GateError, match="repo root"):
        mod.build_target_manifest([Path("target.md")], root=tmp_path / "missing-root")
    with pytest.raises(mod.GateError, match="inside repo root"):
        mod.build_target_manifest([tmp_path / "missing.md"], root=tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(mod.GateError, match="contains no files"):
        mod.build_target_manifest([empty], root=tmp_path)
    with pytest.raises(mod.GateError, match="must not be empty"):
        mod.contract_binding([])
    for obligations, match in (
        (["not-an-object"], "must be an object"),
        ([{"id": "bad", "kind": "generative", "stage": "draft", "fingerprint_sha256": "bad"}], "invalid draft"),
        ([{"id": "later", "kind": "semantic", "stage": "release", "fingerprint_sha256": "a" * 64}], "no draft"),
    ):
        plan = _verification_plan()
        plan["obligations"] = obligations
        with pytest.raises(mod.GateError, match=match):
            mod._draft_proofs(plan)


def test_target_scope_closes_runtime_exclusion_and_rejects_existing_target_overlap(mod, tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "target.md").write_text("target\n", encoding="utf-8")
    existing_review = project / "review.json"
    existing_review.write_text("target content, not a runtime receipt\n", encoding="utf-8")
    state_dir = project / ".harness" / "review-state"

    with pytest.raises(mod.GateError, match="overlaps target content"):
        mod.build_target_scope(
            [project],
            root=tmp_path,
            state_dir=state_dir,
            runtime_paths=[existing_review],
        )
    with pytest.raises(mod.GateError, match="target root or its parent"):
        mod.build_target_scope([project], root=tmp_path, state_dir=project)

    scope = mod.build_target_scope([project], root=tmp_path, state_dir=state_dir)
    assert scope["target_root"] == str(tmp_path.resolve())
    assert scope["target_roots"] == [{"path": "project", "kind": "directory"}]
    assert scope["target_exclusions"] == ["project/.harness/review-state"]
    assert {item["path"] for item in scope["target_manifest"]} == {
        "project/review.json",
        "project/target.md",
    }


def test_manifest_shape_is_checked_even_for_api_callers(mod):
    for manifest, match in (
        ({}, "stale"),
        ([{"path": "", "sha256": "a" * 64, "size": 1}], "path/sha256"),
        ([{"path": "target.md", "sha256": "a" * 64, "size": -1}], "size"),
    ):
        with pytest.raises(mod.GateError, match=match):
            mod._validate_manifest(manifest, manifest if isinstance(manifest, list) else [])


def test_artifact_fingerprint_excludes_run_id_but_changes_with_target_or_contract(mod, tmp_path: Path):
    target = tmp_path / "target.md"
    target.write_text("v1", encoding="utf-8")
    manifest = mod.build_target_manifest([target], root=tmp_path)
    first = mod.baseline_fingerprint(_verification_plan(run_id="run-a"), manifest, methods_path=METHODS)
    second = mod.baseline_fingerprint(_verification_plan(run_id="run-b"), manifest, methods_path=METHODS)
    assert first == second
    target.write_text("v2", encoding="utf-8")
    changed = mod.build_target_manifest([target], root=tmp_path)
    assert mod.baseline_fingerprint(_verification_plan(run_id="run-b"), changed, methods_path=METHODS) != first


def test_durable_claim_authorizes_only_once_even_under_concurrency(mod, tmp_path: Path):
    plan = _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable", encoding="utf-8")
    state_dir = tmp_path / "state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    manifest = scope["target_manifest"]
    presentation, pre_choice = _presentation_and_prechoice(
        mod, plan=plan, proof=proof, manifest=manifest
    )
    def invoke():
        return mod.build_gate(plan, target_manifest=manifest, target_scope=scope, usable_draft_proof=proof, artifact_presentation_receipt=presentation, pre_diagnostic_choice_event=pre_choice, state_dir=state_dir, methods_path=METHODS, levels_path=LEVELS)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: invoke(), range(2)))
    assert sorted(result["initial_review"]["authorized"] for result in results) == [False, True]
    assert {result["status"] for result in results} == {"initial-review-required", "initial-review-in-progress"}
    state = json.loads(Path(results[0]["state_ref"]).read_text(encoding="utf-8"))
    assert state["schema_version"] == 2
    assert state["target_root"] == str(tmp_path.resolve())
    assert state["target_roots"] == sorted([
        {"path": "target.md", "kind": "file"},
        {"path": proof["capability_artifact"]["path"], "kind": "file"},
    ], key=lambda item: item["path"])
    assert state["target_exclusions"] == []


def test_review_without_consumed_launch_is_rejected(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env, consume_launch=False)
    with pytest.raises(mod.GateError, match="durably launched"):
        mod.build_gate(
            env["plan"],
            target_manifest=env["manifest"],
            target_scope=env["scope"],
            usable_draft_proof=env["proof"],
            artifact_presentation_receipt=env["presentation"],
            pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
            state_dir=env["state_dir"],
            review=review,
            claim_id=env["claim"]["initial_review"]["claim_id"],
            methods_path=METHODS,
            levels_path=LEVELS,
        )


def test_launch_receipt_transition_is_visible_and_review_must_match_request(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    launch = _consume_launch(mod, env, runtime="claude-code")
    in_progress = mod.build_gate(
        env["plan"],
        target_manifest=env["manifest"],
        target_scope=env["scope"],
        usable_draft_proof=env["proof"],
        artifact_presentation_receipt=env["presentation"],
        pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
        state_dir=env["state_dir"],
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    assert in_progress["initial_review"]["launch"] == launch

    review = _review(mod, env)
    review["launch_request_id"] = "IRL-" + "0" * 64
    with pytest.raises(mod.GateError, match="launch_request_id"):
        mod.build_gate(
            env["plan"],
            target_manifest=env["manifest"],
            target_scope=env["scope"],
            usable_draft_proof=env["proof"],
            artifact_presentation_receipt=env["presentation"],
            pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
            state_dir=env["state_dir"],
            review=review,
            claim_id=env["claim"]["initial_review"]["claim_id"],
            methods_path=METHODS,
            levels_path=LEVELS,
        )

    review["launch_request_id"] = launch["request_id"]
    review["evaluator"]["runtime"] = launch["runtime"]
    completed = mod.build_gate(
        env["plan"],
        target_manifest=env["manifest"],
        target_scope=env["scope"],
        usable_draft_proof=env["proof"],
        artifact_presentation_receipt=env["presentation"],
        pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
        state_dir=env["state_dir"],
        review=review,
        claim_id=env["claim"]["initial_review"]["claim_id"],
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    assert completed["status"] == "awaiting-improvement-choice"


def test_real_launch_adapter_consumes_claim_then_gate_accepts_its_bound_review(mod, tmp_path: Path):
    launch_mod = _load_launch_module()
    env = _claim(mod, tmp_path)
    launch_request = launch_mod.build_launch_request(env["claim"], runtime="codex")
    launch_receipt = json.loads(
        launch_mod.launch_state_path(Path(env["claim"]["state_ref"])).read_text(encoding="utf-8")
    )
    assert launch_request["runtime_neutral_request"]["launch_request_id"] == launch_receipt["request_id"]
    env["launch"] = launch_receipt
    review = _review(mod, env)
    assert review["launch_request_id"] == launch_request["request_id"]
    completed = mod.build_gate(
        env["plan"],
        target_manifest=env["manifest"],
        target_scope=env["scope"],
        usable_draft_proof=env["proof"],
        artifact_presentation_receipt=env["presentation"],
        pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
        state_dir=env["state_dir"],
        review=review,
        claim_id=env["claim"]["initial_review"]["claim_id"],
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    assert completed["status"] == "awaiting-improvement-choice"


def test_crash_before_review_recovers_same_request_then_completed_result_prevents_restart(mod, tmp_path: Path):
    launch_mod = _load_launch_module()
    env = _claim(mod, tmp_path)
    first = launch_mod.build_launch_request(env["claim"], runtime="codex")
    with pytest.raises(launch_mod.LaunchError, match="lease is active"):
        launch_mod.build_launch_request(env["claim"], runtime="codex")

    receipt_path = launch_mod.launch_state_path(Path(env["claim"]["state_ref"]))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["lease_expires_at"] = "2000-01-01T00:00:00Z"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    recovered = launch_mod.build_launch_request(env["claim"], runtime="codex")
    assert recovered == first

    env["launch"] = json.loads(receipt_path.read_text(encoding="utf-8"))
    review = _review(mod, env)
    _, completed = _complete(mod, env, review)
    assert completed["status"] == "awaiting-improvement-choice"
    with pytest.raises(launch_mod.LaunchError, match="no longer authorizes"):
        launch_mod.build_launch_request(env["claim"], runtime="codex")


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda value: value.update(extra=True), "additional properties"),
        (lambda value: value.update(claim_id="IRC-" + "0" * 32), "another claim"),
        (lambda value: value.update(artifact_fingerprint_sha256="0" * 64), "another artifact"),
        (lambda value: value.update(run_id="another-run"), "another run"),
        (lambda value: value.update(runtime="other"), "runtime is invalid"),
        (lambda value: value.update(request_id="bad"), "request_id is invalid"),
        (lambda value: value.update(consumed_at="2026-08-20T00:00:00"), "timezone"),
    ],
)
def test_sibling_launch_receipt_is_strictly_bound_to_claim_artifact_and_run(mod, tmp_path: Path, mutate, match):
    env = _claim(mod, tmp_path)
    receipt = deepcopy(_consume_launch(mod, env))
    mutate(receipt)
    mod._atomic_write_json(
        mod._launch_receipt_path(Path(env["claim"]["state_ref"])),
        receipt,
    )
    with pytest.raises(mod.GateError, match=match):
        mod.build_gate(
            env["plan"],
            target_manifest=env["manifest"],
            target_scope=env["scope"],
            usable_draft_proof=env["proof"],
            artifact_presentation_receipt=env["presentation"],
            pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
            state_dir=env["state_dir"],
            methods_path=METHODS,
            levels_path=LEVELS,
        )


def test_completed_review_is_reused_by_another_run_for_same_artifact(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    second_plan = _verification_plan(run_id="build-20260820-02")
    second_proof = _usable_draft_proof(tmp_path, second_plan, capability_artifact=tmp_path / env["proof"]["capability_artifact"]["path"])
    second_presentation, second_pre_choice = _presentation_and_prechoice(
        mod, plan=second_plan, proof=second_proof, manifest=env["manifest"]
    )
    reused = mod.build_gate(second_plan, target_manifest=env["manifest"], target_scope=env["scope"], usable_draft_proof=second_proof, artifact_presentation_receipt=second_presentation, pre_diagnostic_choice_event=second_pre_choice, state_dir=env["state_dir"], methods_path=METHODS, levels_path=LEVELS)
    assert reused["status"] == "awaiting-improvement-choice"
    assert reused["initial_review"]["authorized"] is False
    assert reused["initial_review"]["reused_from_run_id"] == env["plan"]["run_id"]
    assert reused["initial_review"]["review_sha256"] == completed["initial_review"]["review_sha256"]


def test_target_change_after_claim_or_review_cannot_use_stale_receipt(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    env["target"].write_text("mutated", encoding="utf-8")
    changed_scope = _scope_with_proof(mod, tmp_path, [env["target"]], env["state_dir"], env["proof"])
    changed = changed_scope["target_manifest"]
    with pytest.raises(mod.GateError, match="target manifest digest"):
        mod.build_gate(env["plan"], target_manifest=changed, target_scope=changed_scope, usable_draft_proof=env["proof"], artifact_presentation_receipt=env["presentation"], pre_diagnostic_choice_event=env["pre_diagnostic_choice"], state_dir=env["state_dir"], review=review, claim_id=env["claim"]["initial_review"]["claim_id"], methods_path=METHODS, levels_path=LEVELS)


def test_target_change_after_completed_review_blocks_the_choice(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    choice = _event(env, completed, "improvement-level-selected", event_id="turn-choice-stale", selected_level="standard")
    env["target"].write_text("changed after review", encoding="utf-8")
    changed_scope = _scope_with_proof(mod, tmp_path, [env["target"]], env["state_dir"], env["proof"])
    changed = changed_scope["target_manifest"]
    with pytest.raises(mod.GateError, match="target manifest digest"):
        mod.build_gate(
            env["plan"], target_manifest=changed, target_scope=changed_scope, state_dir=env["state_dir"],
            usable_draft_proof=env["proof"],
            artifact_presentation_receipt=env["presentation"],
            pre_diagnostic_choice_event=env["pre_diagnostic_choice"],
            selected_level="standard", choice_event=choice,
            methods_path=METHODS, levels_path=LEVELS,
        )


def test_prompt_contract_change_invalidates_the_artifact_fingerprint(mod, tmp_path: Path):
    target = tmp_path / "target.md"
    target.write_text("usable", encoding="utf-8")
    manifest = mod.build_target_manifest([target], root=tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("contract v1", encoding="utf-8")
    first = mod.baseline_fingerprint(_verification_plan(), manifest, methods_path=METHODS, prompt_path=prompt)
    prompt.write_text("contract v2", encoding="utf-8")
    second = mod.baseline_fingerprint(_verification_plan(), manifest, methods_path=METHODS, prompt_path=prompt)
    assert first != second


def test_strict_review_and_all_three_schemas_validate(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    mod.validate_review(review, env["plan"], env["manifest"], claim_id=env["claim"]["initial_review"]["claim_id"], expected_run_id=env["plan"]["run_id"], launch_receipt=env["launch"], target_scope=env["scope"], methods_path=METHODS)
    schema = json.loads(REVIEW_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(review)) == []
    for path in (DECISION_SCHEMA, EVENT_SCHEMA):
        Draft7Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_evidence_line_must_exist_in_the_current_target_file(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    review["evidence"][0]["line"] = 2
    with pytest.raises(mod.GateError, match="actual line count"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


def test_evidence_symlink_escape_is_rejected_even_when_manifest_was_previously_valid(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("usable draft\n", encoding="utf-8")
    env["target"].unlink()
    env["target"].symlink_to(outside)
    with pytest.raises(mod.GateError, match="escapes target root"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


def test_missing_evidence_file_is_rejected_even_with_a_stale_manifest(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    env["target"].unlink()
    with pytest.raises(mod.GateError, match="does not exist"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


def _finding_location_env(mod, tmp_path: Path, *, finding_payload: bytes = b"finding\n") -> tuple[dict, dict, Path]:
    project = tmp_path / "project"
    project.mkdir()
    evidence_path = project / "evidence.md"
    finding_path = project / "finding.md"
    evidence_path.write_text("evidence\n", encoding="utf-8")
    finding_path.write_bytes(finding_payload)
    state_dir = tmp_path / "review-state"
    plan = _verification_plan()
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [project], state_dir, proof)
    presentation, pre_choice = _presentation_and_prechoice(
        mod, plan=plan, proof=proof, manifest=scope["target_manifest"]
    )
    claim = mod.build_gate(
        plan,
        target_manifest=scope["target_manifest"],
        target_scope=scope,
        usable_draft_proof=proof,
        artifact_presentation_receipt=presentation,
        pre_diagnostic_choice_event=pre_choice,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    env = {
        "plan": plan,
        "target": finding_path,
        "manifest": scope["target_manifest"],
        "scope": scope,
        "proof": proof,
        "presentation": presentation,
        "pre_diagnostic_choice": pre_choice,
        "root": tmp_path,
        "state_dir": state_dir,
        "claim": claim,
    }
    review = _review(mod, env)
    evidence_relative = evidence_path.relative_to(tmp_path).as_posix()
    finding_relative = finding_path.relative_to(tmp_path).as_posix()
    review["evidence"][0]["path"] = evidence_relative
    for finding in review["findings"]:
        finding["location"]["path"] = finding_relative
        finding["remediation_paths"] = [finding_relative]
    return env, review, finding_path


def test_finding_location_line_must_exist_in_the_current_utf8_file(mod, tmp_path: Path):
    env, review, _ = _finding_location_env(mod, tmp_path, finding_payload="一行目\n二行目\n".encode("utf-8"))
    review["findings"][0]["location"]["line"] = 3
    with pytest.raises(mod.GateError, match="finding line exceeds actual line count"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


def test_finding_location_file_must_be_valid_utf8(mod, tmp_path: Path):
    env, review, _ = _finding_location_env(mod, tmp_path, finding_payload=b"\xff\n")
    with pytest.raises(mod.GateError, match="finding file must be valid UTF-8"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


def test_finding_location_rejects_file_changed_after_manifest(mod, tmp_path: Path):
    env, review, finding_path = _finding_location_env(mod, tmp_path)
    finding_path.write_text("tampered finding\n", encoding="utf-8")
    with pytest.raises(mod.GateError, match="finding file no longer matches target manifest"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


def test_finding_location_rejects_symlink_escape_even_when_evidence_is_separate(mod, tmp_path: Path):
    env, review, finding_path = _finding_location_env(mod, tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-finding-outside.md"
    outside.write_text("finding\n", encoding="utf-8")
    finding_path.unlink()
    finding_path.symlink_to(outside)
    with pytest.raises(mod.GateError, match="finding path escapes target root"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


def test_semantically_duplicate_findings_are_rejected_even_with_different_ids(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    duplicate = deepcopy(review["findings"][0])
    duplicate["id"] = "IDR-005"
    review["findings"][0]["title"] = "Issue"
    review["findings"][0]["description"] = "Critical issue"
    review["findings"][0]["recommendation"] = "Fix critical"
    duplicate["title"] = " ★ Ｉｓｓｕｅ！ "
    duplicate["description"] = "Critical   issue。"
    duplicate["recommendation"] = "✓ FIX CRITICAL."
    review["findings"].append(duplicate)
    review["method_observations"][0]["finding_refs"].append("IDR-005")
    review["four_conditions"]["C1"]["finding_refs"].append("IDR-005")
    with pytest.raises(mod.GateError, match="semantic duplicate"):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Compiler error E-123", "Compiler error E123"),
        ("C++ parser", "C parser"),
        ("node.js failure", "nodejs failure"),
    ],
)
def test_semantic_normalization_preserves_meaningful_identifier_symbols(mod, left: str, right: str):
    assert mod._normalize_semantic_text(left) != mod._normalize_semantic_text(right)


def test_identifier_distinct_findings_are_not_merged(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    review["findings"][0]["title"] = "Compiler error E-123"
    duplicate = deepcopy(review["findings"][0])
    duplicate["id"] = "IDR-005"
    duplicate["title"] = "Compiler error E123"
    review["findings"].append(duplicate)
    review["method_observations"][0]["finding_refs"].append("IDR-005")
    review["four_conditions"]["C1"]["finding_refs"].append("IDR-005")
    mod.validate_review(
        review,
        env["plan"],
        env["manifest"],
        claim_id=env["claim"]["initial_review"]["claim_id"],
        expected_run_id=env["plan"]["run_id"],
        launch_receipt=env["launch"],
        target_scope=env["scope"],
        methods_path=METHODS,
    )


def test_remediation_paths_allow_future_files_inside_a_directory_target(mod, tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "review-state"
    plan = _verification_plan()
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [project], state_dir, proof)
    presentation, pre_choice = _presentation_and_prechoice(
        mod, plan=plan, proof=proof, manifest=scope["target_manifest"]
    )
    claim = mod.build_gate(
        plan,
        target_manifest=scope["target_manifest"],
        target_scope=scope,
        usable_draft_proof=proof,
        artifact_presentation_receipt=presentation,
        pre_diagnostic_choice_event=pre_choice,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )
    env = {
        "plan": plan,
        "target": target,
        "manifest": scope["target_manifest"],
        "scope": scope,
        "proof": proof,
        "presentation": presentation,
        "pre_diagnostic_choice": pre_choice,
        "root": tmp_path,
        "state_dir": state_dir,
        "claim": claim,
    }
    review = _review(mod, env)
    review["findings"][0]["remediation_paths"].append("project/tests/test_future.py")
    mod.validate_review(
        review,
        plan,
        env["manifest"],
        claim_id=claim["initial_review"]["claim_id"],
        expected_run_id=plan["run_id"],
        launch_receipt=env["launch"],
        target_scope=scope,
        methods_path=METHODS,
    )


@pytest.mark.parametrize(
    ("paths", "match"),
    [
        (["future.md"], "include finding location"),
        (["target.md", "*.py"], "glob"),
        (["target.md", "../escape.py"], "invalid"),
        (["target.md", "outside/new.py"], "target roots"),
    ],
)
def test_remediation_paths_are_closed_to_exact_authoritative_target_scope(mod, tmp_path: Path, paths, match):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    review["findings"][0]["remediation_paths"] = paths
    with pytest.raises(mod.GateError, match=match):
        mod.validate_review(
            review,
            env["plan"],
            env["manifest"],
            claim_id=env["claim"]["initial_review"]["claim_id"],
            expected_run_id=env["plan"]["run_id"],
            launch_receipt=env["launch"],
            target_scope=env["scope"],
            methods_path=METHODS,
        )


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda r: r.update(extra=True), "additional properties"),
        (lambda r: r.update(schema_version=2), "schema_version"),
        (lambda r: r.update(run_id="other-run"), "run_id/subject"),
        (lambda r: r.update(review_claim_id="IRC-wrong"), "claim id"),
        (lambda r: r.update(baseline_fingerprint_sha256="0" * 64), "baseline_fingerprint"),
        (lambda r: r["evaluator"].update(runtime="other"), "evaluator contract"),
        (lambda r: r["evaluator"].update(runtime="claude-code"), "runtime does not match"),
        (lambda r: r.update(edited_target=True), "diagnostic-only"),
        (lambda r: r["thought_reset"].update(performed=False), "thought reset"),
        (lambda r: r.update(produced_at="not-a-date"), "date-time"),
        (lambda r: r.update(evidence=[]), "non-empty array"),
        (lambda r: r["evidence"][0].update(id="bad"), "evidence id"),
        (lambda r: r["evidence"][0].update(path="other.md"), "evidence location"),
        (lambda r: r["evidence"][0].update(section=1), "evidence section"),
        (lambda r: r["method_observations"].pop(), "exactly 30"),
        (lambda r: r["method_observations"][1].update(rationale=r["method_observations"][0]["rationale"]), "method-specific"),
        (lambda r: r["method_observations"][0].update(observation=""), "empty method observation"),
        (lambda r: r["method_observations"][0].update(evidence_refs=[]), "evidence_refs"),
        (lambda r: r["method_observations"][0].update(finding_refs=["IDR-001", "IDR-001"]), "unique array"),
        (lambda r: r["method_observations"][1].update(method_id=r["method_observations"][0]["method_id"]), "all 30 canonical"),
        (lambda r: r.update(findings="not-an-array"), "must be an array"),
        (lambda r: r["findings"][0].update(id="bad"), "finding id"),
        (lambda r: r["findings"][0].update(severity="urgent"), "severity/flags"),
        (lambda r: r["findings"][0].update(title=""), "title is empty"),
        (lambda r: r["findings"][0].update(condition_signals=[]), "condition_signals"),
        (lambda r: r["method_observations"][0].update(finding_refs=["IDR-999"]), "unknown findings"),
        (lambda r: [item.update(finding_refs=[]) for item in r["method_observations"]], "every finding"),
        (lambda r: r["findings"][0]["location"].update(path="other.md"), "location"),
        (lambda r: r.update(four_conditions={"C1": r["four_conditions"]["C1"]}), "exactly C1-C4"),
        (lambda r: r["four_conditions"]["C1"].update(summary=""), "invalid four_conditions"),
        (lambda r: r["four_conditions"]["C1"].update(finding_refs=[]), "linkage"),
        (lambda r: r["four_conditions"]["C1"].update(verdict="PASS"), "must FAIL"),
        (lambda r: (r["findings"][1].update(severity="high"), r["four_conditions"]["C2"].update(verdict="PASS")), "cannot PASS"),
        (lambda r: r.update(recommended_level="exhaustive"), "exhaustive or unknown"),
        (lambda r: r.update(recommended_level="accept-draft"), "cannot be recommended"),
        (lambda r: (r["findings"][0].update(severity="low"), r["four_conditions"]["C1"].update(verdict="PARTIAL"), r.update(recommended_level="light")), "at least standard"),
        (lambda r: r.update(summary=""), "summary is required"),
        (lambda r: r["contract_binding"].update(prompt_sha256="0" * 64), "contract binding"),
    ],
)
def test_review_contract_fails_closed_on_malformed_or_semantically_inconsistent_receipt(mod, tmp_path: Path, mutate, match):
    env = _claim(mod, tmp_path)
    review = _review(mod, env)
    mutate(review)
    with pytest.raises(mod.GateError, match=match):
        mod.validate_review(review, env["plan"], env["manifest"], claim_id=env["claim"]["initial_review"]["claim_id"], expected_run_id=env["plan"]["run_id"], launch_receipt=env["launch"], target_scope=env["scope"], methods_path=METHODS)


def test_findings_and_per_level_actionable_previews_are_shown_before_choice(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    review, completed = _complete(mod, env)
    previews = {item["id"]: item for item in completed["question"]["levels"]}
    assert completed["status"] == "awaiting-improvement-choice"
    assert completed["improvement"]["authorized"] is False
    assert completed["findings"] == review["findings"]
    assert previews["light"]["selected_finding_ids"] == ["IDR-001"]
    assert previews["standard"]["selected_finding_ids"] == ["IDR-001", "IDR-002"]
    assert previews["detailed"]["selected_finding_ids"] == ["IDR-001", "IDR-002", "IDR-004"]
    assert previews["detailed"]["selected_finding_count"] == 3
    assert completed["question"]["exhaustive_is_separate_opt_in"] is True


@pytest.mark.parametrize(
    ("level", "ids", "rounds", "stage", "profile"),
    [
        ("light", ["IDR-001"], 1, "draft", "incremental"),
        ("standard", ["IDR-001", "IDR-002"], 2, "draft", "incremental"),
        ("detailed", ["IDR-001", "IDR-002", "IDR-004"], 3, "draft", "incremental"),
        ("release", ["IDR-001", "IDR-002", "IDR-004"], 3, "release", "incremental"),
    ],
)
def test_user_level_deterministically_selects_only_actionable_findings(mod, tmp_path: Path, level, ids, rounds, stage, profile):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    result = _select(mod, env, completed, level)
    assert result["improvement"]["selected_finding_ids"] == ids
    assert result["improvement"]["selected_finding_count"] == len(ids)
    assert result["improvement"]["max_rounds"] == rounds
    assert result["improvement"]["next_stage"] == stage
    assert result["improvement"]["next_profile"] == profile
    assert result["auto_promote_release"] is False
    assert result["auto_promote_exhaustive"] is False


def test_empty_actionable_selection_is_a_noop(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    findings = _default_findings(env["manifest"][0]["path"])
    for finding in findings:
        finding["actionable"] = False
    review = _review(mod, env, findings=findings, recommended="accept-draft")
    _, completed = _complete(mod, env, review)
    result = _select(mod, env, completed, "detailed")
    assert result["status"] == "usable-draft"
    assert result["improvement"]["authorized"] is False
    assert result["improvement"]["selected_finding_ids"] == []


def test_critical_accept_draft_requires_distinct_risk_acknowledgement(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    choice = _event(env, completed, "improvement-level-selected", event_id="turn-choice-accept", selected_level="accept-draft")
    with pytest.raises(mod.GateError, match="risk acknowledgement"):
        _select(mod, env, completed, "accept-draft", choice=choice)
    same = _event(env, completed, "critical-risk-acknowledged", event_id=choice["event_id"])
    with pytest.raises(mod.GateError, match="different"):
        _select(mod, env, completed, "accept-draft", choice=choice, risk=same)
    risk = _event(
        env,
        completed,
        "critical-risk-acknowledged",
        event_id="turn-risk-ack",
        occurred_at=_rfc3339(mod._parse_datetime(choice["occurred_at"], "choice") + timedelta(microseconds=1)),
    )
    result = _select(mod, env, completed, "accept-draft", choice=choice, risk=risk)
    assert result["improvement"]["authorized"] is False
    assert result["decision"]["critical_risk_acknowledgement_event_id"] == "turn-risk-ack"


def test_choice_event_is_strictly_bound_to_level_run_artifact_and_review(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    event = _event(env, completed, "improvement-level-selected", event_id="turn-choice-light", selected_level="light")
    for mutate, match in (
        (lambda e: e.update(extra=True), "additional properties"),
        (lambda e: e.update(selected_level="standard"), "selected_level"),
        (lambda e: e.update(review_sha256="0" * 64), "another artifact or review"),
        (lambda e: e.update(run_id="other-run"), "current run"),
    ):
        broken = deepcopy(event)
        mutate(broken)
        with pytest.raises(mod.GateError, match=match):
            _select(mod, env, completed, "light", choice=broken)


@pytest.mark.parametrize("occurred_at", ["2026-08-20T00:00:59Z", "2026-08-20T00:01:00Z"])
def test_user_choice_must_occur_strictly_after_the_review(mod, tmp_path: Path, occurred_at: str):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    choice = _event(
        env,
        completed,
        "improvement-level-selected",
        event_id="turn-choice-too-early",
        selected_level="light",
        occurred_at=occurred_at,
    )
    with pytest.raises(mod.GateError, match="after the review"):
        _select(mod, env, completed, "light", choice=choice)


def test_exhaustive_requires_a_distinct_later_second_user_event(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    choice = _event(env, completed, "improvement-level-selected", event_id="turn-choice-exhaustive", selected_level="exhaustive")
    with pytest.raises(mod.GateError, match="separate"):
        _select(mod, env, completed, "exhaustive", choice=choice)
    confirmation_at = _rfc3339(mod._parse_datetime(choice["occurred_at"], "choice") + timedelta(microseconds=1))
    same = _event(env, completed, "exhaustive-confirmed", event_id=choice["event_id"], occurred_at=confirmation_at)
    with pytest.raises(mod.GateError, match="different"):
        _select(mod, env, completed, "exhaustive", choice=choice, exhaustive=same)
    confirmation = _event(env, completed, "exhaustive-confirmed", event_id="turn-exhaustive-confirm", occurred_at=confirmation_at)
    result = _select(mod, env, completed, "exhaustive", choice=choice, exhaustive=confirmation)
    assert result["improvement"]["next_stage"] == "release"
    assert result["improvement"]["next_profile"] == "exhaustive"
    assert result["decision"]["explicit_exhaustive_confirmation"] is True


def test_decision_schema_contains_executor_contract_and_no_auto_promotion(mod, tmp_path: Path):
    env = _claim(mod, tmp_path)
    _, completed = _complete(mod, env)
    result = _select(mod, env, completed, "standard")
    decision = result["decision"]
    schema = json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(decision)) == []
    assert decision["improvement_authorized"] is True
    assert decision["baseline_target_manifest_sha256"] == completed["contract_binding"]["target_manifest_sha256"]
    assert decision["auto_promote_release"] is False
    assert decision["auto_promote_exhaustive"] is False


def test_review_schema_supports_only_the_two_declared_runtimes():
    schema = json.loads(REVIEW_SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["evaluator"]["properties"]["runtime"]["enum"] == ["claude-code", "codex"]


def test_cli_fails_closed_without_durable_state_and_target(tmp_path: Path):
    plan_path = tmp_path / "verification-plan.json"
    plan_path.write_text(json.dumps(_verification_plan()), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "--verification-plan", str(plan_path)], cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode == 2
    assert "--state-dir" in proc.stderr and "--target-path" in proc.stderr and "--usable-draft-proof" in proc.stderr


def test_cli_atomically_authorizes_only_the_first_review_claim(tmp_path: Path):
    mod = _load_module()
    plan = _verification_plan()
    plan_path = tmp_path / "verification-plan.json"
    target = tmp_path / "target.md"
    state_dir = tmp_path / "review-state"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    _write_capability_artifact(target, "skill")
    proof_path = _usable_draft_proof_file(tmp_path, plan, capability_artifact=target)
    argv = [sys.executable, str(SCRIPT), "--verification-plan", str(plan_path), "--usable-draft-proof", str(proof_path), "--repo-root", str(tmp_path), "--target-path", str(target), "--state-dir", str(state_dir)]
    pre_args, _, _ = _cli_pre_diagnostic_args(mod, tmp_path, plan=plan, proof_path=proof_path, target_paths=[target], state_dir=state_dir)
    argv += pre_args
    first = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    second = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(first.stdout)["initial_review"]["authorized"] is True
    assert json.loads(second.stdout)["status"] == "initial-review-in-progress"


def test_cli_e2e_requires_presentation_then_prechoice_and_accept_is_zero_context(tmp_path: Path):
    mod = _load_module()
    plan = _verification_plan()
    plan_path = tmp_path / "verification-plan.json"
    target = _write_capability_artifact(tmp_path / "SKILL.md", "skill")
    state_dir = tmp_path / "state"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    proof_path = _usable_draft_proof_file(tmp_path, plan, capability_artifact=target)
    base = [
        sys.executable, str(SCRIPT),
        "--verification-plan", str(plan_path),
        "--usable-draft-proof", str(proof_path),
        "--repo-root", str(tmp_path),
        "--target-path", str(target),
        "--state-dir", str(state_dir),
    ]

    proof_only = subprocess.run(base, cwd=REPO_ROOT, capture_output=True, text=True)
    assert proof_only.returncode == 0, proof_only.stderr
    assert json.loads(proof_only.stdout)["status"] == "awaiting-artifact-presentation"
    assert not list(state_dir.glob("initial-draft-review-*.json"))

    accept_args, _, _ = _cli_pre_diagnostic_args(
        mod,
        tmp_path,
        plan=plan,
        proof_path=proof_path,
        target_paths=[target],
        state_dir=state_dir,
        diagnostic_level="accept-as-is",
    )
    accepted = subprocess.run(base + accept_args, cwd=REPO_ROOT, capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stderr
    accepted_result = json.loads(accepted.stdout)
    assert accepted_result["status"] == "usable-draft"
    assert accepted_result["initial_review"]["evaluator_contexts"] == 0
    assert accepted_result["improvement"]["improver_contexts"] == 0
    assert not list(state_dir.glob("initial-draft-review-*.json"))

    detailed_args, _, _ = _cli_pre_diagnostic_args(
        mod,
        tmp_path,
        plan=plan,
        proof_path=proof_path,
        target_paths=[target],
        state_dir=state_dir,
        diagnostic_level="detailed",
    )
    claimed = subprocess.run(base + detailed_args, cwd=REPO_ROOT, capture_output=True, text=True)
    assert claimed.returncode == 0, claimed.stderr
    claimed_result = json.loads(claimed.stdout)
    assert claimed_result["status"] == "initial-review-required"
    assert claimed_result["initial_review"]["authorized"] is True


def test_cli_project_local_state_is_not_hashed_as_target_content(tmp_path: Path):
    mod = _load_module()
    plan = _verification_plan()
    project = tmp_path / "project"
    project.mkdir()
    artifact = _write_capability_artifact(project / "SKILL.md", "skill")
    plan_path = tmp_path / "verification-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    proof_path = _usable_draft_proof_file(tmp_path, plan, capability_artifact=artifact)
    state_dir = project / ".harness" / "review-state"
    argv = [
        sys.executable,
        str(SCRIPT),
        "--verification-plan", str(plan_path),
        "--usable-draft-proof", str(proof_path),
        "--repo-root", str(tmp_path),
        "--target-path", str(project),
        "--state-dir", str(state_dir),
    ]
    pre_args, _, _ = _cli_pre_diagnostic_args(mod, tmp_path, plan=plan, proof_path=proof_path, target_paths=[project], state_dir=state_dir)
    argv += pre_args
    first = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    second = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(first.stdout)["status"] == "initial-review-required"
    assert json.loads(second.stdout)["status"] == "initial-review-in-progress"


def test_cli_decision_binds_raw_review_file_digest(tmp_path: Path, mod):
    plan = _verification_plan()
    plan_path = tmp_path / "plan.json"
    target = tmp_path / "SKILL.md"
    state_dir = tmp_path / "state"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    _write_capability_artifact(target, "skill")
    proof_path = _usable_draft_proof_file(tmp_path, plan, capability_artifact=target)
    base_argv = [sys.executable, str(SCRIPT), "--verification-plan", str(plan_path), "--usable-draft-proof", str(proof_path), "--repo-root", str(tmp_path), "--target-path", str(target), "--state-dir", str(state_dir)]
    pre_args, presentation, pre_choice = _cli_pre_diagnostic_args(mod, tmp_path, plan=plan, proof_path=proof_path, target_paths=[target], state_dir=state_dir)
    base_argv += pre_args
    claimed_proc = subprocess.run(base_argv, cwd=REPO_ROOT, capture_output=True, text=True)
    claimed = json.loads(claimed_proc.stdout)
    env = {"plan": plan, "manifest": claimed["initial_review"]["target_manifest"], "claim": claimed, "presentation": presentation, "pre_diagnostic_choice": pre_choice}
    review = _review(mod, env)
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    completed_proc = subprocess.run(base_argv + ["--review", str(review_path), "--claim-id", claimed["initial_review"]["claim_id"]], cwd=REPO_ROOT, capture_output=True, text=True)
    assert completed_proc.returncode == 0, completed_proc.stderr
    completed = json.loads(completed_proc.stdout)
    raw_sha = hashlib.sha256(review_path.read_bytes()).hexdigest()
    assert completed["initial_review"]["review_sha256"] == raw_sha
    event = _event({"plan": plan}, completed, "improvement-level-selected", event_id="turn-choice-standard", selected_level="standard")
    event_path = tmp_path / "choice.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    decision_path = tmp_path / "decision.json"
    selected_proc = subprocess.run(base_argv + ["--selected-level", "standard", "--user-choice-event", str(event_path), "--decision-out", str(decision_path)], cwd=REPO_ROOT, capture_output=True, text=True)
    assert selected_proc.returncode == 0, selected_proc.stderr
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    assert decision["review_sha256"] == raw_sha


def test_level_policy_and_two_runtime_surfaces_are_aligned():
    levels = json.loads(LEVELS.read_text(encoding="utf-8"))
    assert levels["default"] == "ask"
    assert levels["offered_order"] == ["accept-draft", "light", "standard", "detailed", "release"]
    assert levels["levels"]["exhaustive"]["offered_by_default"] is False
    for surface in (COMMAND, RUN_BUILD / "SKILL.md"):
        text = surface.read_text(encoding="utf-8")
        assert "AskUserQuestion" in text
        assert "elegant-initial-draft-evaluator" in text
        assert "30思考法" in text
        assert "release" in text and "exhaustive" in text and "自動昇格" in text
    composition = (REPO_ROOT / "plugins/harness-creator/plugin-composition.yaml").read_text(encoding="utf-8")
    assert "agents/elegant-initial-draft-evaluator" in composition
    assert "scripts/build-improvement-gate.py" in composition


def test_usable_proof_alone_cannot_claim_or_authorize_initial_review(mod, tmp_path: Path):
    plan = _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "review-state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)

    result = mod.build_gate(
        plan,
        target_manifest=scope["target_manifest"],
        target_scope=scope,
        usable_draft_proof=proof,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )

    assert result["status"] == "awaiting-artifact-presentation"
    assert result["initial_review"] == {"authorized": False}
    assert result["improvement"] == {"authorized": False}
    assert not list(state_dir.glob("initial-draft-review-*.json"))


def test_accept_as_is_after_actual_presentation_finishes_without_claim_or_agents(mod, tmp_path: Path):
    plan = _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "review-state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    presentation, choice = _presentation_and_prechoice(
        mod,
        plan=plan,
        proof=proof,
        manifest=scope["target_manifest"],
        diagnostic_level="accept-as-is",
    )

    result = mod.build_gate(
        plan,
        target_manifest=scope["target_manifest"],
        target_scope=scope,
        usable_draft_proof=proof,
        artifact_presentation_receipt=presentation,
        pre_diagnostic_choice_event=choice,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )

    assert result["status"] == "usable-draft"
    assert result["initial_review"] == {"authorized": False, "evaluator_contexts": 0}
    assert result["improvement"] == {"authorized": False, "improver_contexts": 0}
    assert result["handoff"]["artifact_presented"] is True
    assert result["handoff"]["selected_level"] == "accept-as-is"
    assert not list(state_dir.glob("initial-draft-review-*.json"))


def test_detailed_prechoice_is_required_and_bound_before_claim(mod, tmp_path: Path):
    plan = _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "review-state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    presentation, choice = _presentation_and_prechoice(
        mod, plan=plan, proof=proof, manifest=scope["target_manifest"]
    )

    claim = mod.build_gate(
        plan,
        target_manifest=scope["target_manifest"],
        target_scope=scope,
        usable_draft_proof=proof,
        artifact_presentation_receipt=presentation,
        pre_diagnostic_choice_event=choice,
        state_dir=state_dir,
        methods_path=METHODS,
        levels_path=LEVELS,
    )

    assert claim["status"] == "initial-review-required"
    assert claim["initial_review"]["authorized"] is True
    assert claim["artifact_presentation_receipt"] == presentation
    assert claim["pre_diagnostic_choice_event"] == choice
    assert claim["initial_review"]["pre_diagnostic_choice_event_sha256"] == mod._canonical_sha(choice)
    state = json.loads(Path(claim["state_ref"]).read_text(encoding="utf-8"))
    assert state["decisions"]["pre_diagnostic"]["presentation_receipt_sha256"] == mod._canonical_sha(presentation)
    assert state["decisions"]["pre_diagnostic"]["choice_event_sha256"] == mod._canonical_sha(choice)
    presentation_schema = json.loads(PRESENTATION_SCHEMA.read_text(encoding="utf-8"))
    pre_diagnostic_schema = json.loads(PRE_DIAGNOSTIC_SCHEMA.read_text(encoding="utf-8"))
    checker = FormatChecker()
    assert list(Draft7Validator(presentation_schema, format_checker=checker).iter_errors(presentation)) == []
    assert list(Draft7Validator(pre_diagnostic_schema, format_checker=checker).iter_errors(choice)) == []


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda presentation, choice: presentation.update(artifact_sha256="0" * 64), "artifact"),
        (lambda presentation, choice: choice.update(contract_binding_sha256="0" * 64), "contract"),
        (lambda presentation, choice: choice.update(occurred_at=presentation["occurred_at"]), "strictly after"),
        (lambda presentation, choice: choice.update(selected_level="release"), "pre-diagnostic"),
    ],
)
def test_presentation_and_prechoice_fail_closed_on_tamper_or_invalid_order(
    mod, tmp_path: Path, mutate, match
):
    plan = _verification_plan()
    target = tmp_path / "target.md"
    target.write_text("usable draft\n", encoding="utf-8")
    state_dir = tmp_path / "review-state"
    proof = _usable_draft_proof(tmp_path, plan)
    scope = _scope_with_proof(mod, tmp_path, [target], state_dir, proof)
    presentation, choice = _presentation_and_prechoice(
        mod, plan=plan, proof=proof, manifest=scope["target_manifest"]
    )
    mutate(presentation, choice)

    with pytest.raises(mod.GateError, match=match):
        mod.build_gate(
            plan,
            target_manifest=scope["target_manifest"],
            target_scope=scope,
            usable_draft_proof=proof,
            artifact_presentation_receipt=presentation,
            pre_diagnostic_choice_event=choice,
            state_dir=state_dir,
            methods_path=METHODS,
            levels_path=LEVELS,
        )
    assert not list(state_dir.glob("initial-draft-review-*.json"))
