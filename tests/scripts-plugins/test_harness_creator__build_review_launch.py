"""Runtime-neutral launch contract for the one initial draft evaluator."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN = REPO_ROOT / "plugins/harness-creator"
RUN_BUILD = PLUGIN / "skills/run-build-skill"
SCRIPT = RUN_BUILD / "scripts/build-review-launch.py"
SCHEMA = RUN_BUILD / "schemas/review-launch-request.schema.json"
WORKFLOW = RUN_BUILD / "workflow-manifest.json"

CAPABILITY_KINDS = {
    "skill",
    "agent",
    "hook",
    "command",
    "plugin-composition",
    "prompt",
    "workflow",
}
SKILL_SUBTYPES = {"run", "ref", "assign", "delegate", "wrap"}


def _load_module():
    spec = importlib.util.spec_from_file_location("build_review_launch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _binding(target_manifest_sha256: str = "1" * 64) -> dict:
    return {
        "target_manifest_sha256": target_manifest_sha256,
        "method_catalog_sha256": "2" * 64,
        "method_catalog_version": "2.0",
        "prompt_sha256": "3" * 64,
        "review_schema_sha256": "4" * 64,
        "review_schema_version": 1,
    }


def _gate_plan(tmp_path: Path, *, state_name: str = "state") -> dict:
    method_ids = [f"method-{index:02d}" for index in range(30)]
    readme = tmp_path / "plugins/demo/README.md"
    composition = tmp_path / "plugins/demo/plugin-composition.yaml"
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text("demo readme\n", encoding="utf-8")
    composition.write_text("schemaVersion: 1\nname: demo\n", encoding="utf-8")
    target_manifest = [
        {"path": path.relative_to(tmp_path).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size}
        for path in (readme, composition)
    ]
    binding = _binding(_canonical_sha(target_manifest))
    baseline = "c" * 64
    state_path = tmp_path / state_name / f"initial-draft-review-{baseline}.json"
    presentation = {
        "schema_version": 1,
        "event_id": "artifact-presented-current-turn",
        "event_type": "artifact-presented",
        "source": "host",
        "run_id": "build-20260820-01",
        "subject": "demo-harness",
        "artifact_path": target_manifest[0]["path"],
        "artifact_sha256": target_manifest[0]["sha256"],
        "target_manifest_sha256": binding["target_manifest_sha256"],
        "contract_binding_sha256": _canonical_sha(binding),
        "usable_draft_proof_sha256": "9" * 64,
        "artifact_created_at": "2026-08-20T00:00:00Z",
        "smoke": {"status": "PASS", "mode": "parse-or-open", "exit_code": 0},
        "occurred_at": "2026-08-20T00:00:01Z",
    }
    pre_choice = {
        "schema_version": 1,
        "event_id": "pre-diagnostic-choice-current-turn",
        "event_type": "pre-diagnostic-choice",
        "source": "user",
        "run_id": "build-20260820-01",
        "subject": "demo-harness",
        "artifact_path": target_manifest[0]["path"],
        "artifact_sha256": target_manifest[0]["sha256"],
        "target_manifest_sha256": binding["target_manifest_sha256"],
        "contract_binding_sha256": _canonical_sha(binding),
        "presentation_receipt_sha256": _canonical_sha(presentation),
        "selected_level": "detailed",
        "occurred_at": "2026-08-20T00:00:02Z",
    }
    pre_diagnostic = {
        "selected_level": "detailed",
        "presentation_receipt_sha256": _canonical_sha(presentation),
        "choice_event_sha256": _canonical_sha(pre_choice),
        "presentation_event_id": presentation["event_id"],
        "choice_event_id": pre_choice["event_id"],
    }
    gate = {
        "schema_version": 1,
        "status": "initial-review-required",
        "subject": "demo-harness",
        "run_id": "build-20260820-01",
        "baseline_fingerprint_sha256": baseline,
        "artifact_fingerprint_sha256": baseline,
        "contract_binding": binding,
        "target_root": str(tmp_path.resolve()),
        "target_roots": [
            {"path": "plugins/demo/README.md", "kind": "file"},
            {"path": "plugins/demo/plugin-composition.yaml", "kind": "file"},
        ],
        "target_exclusions": [],
        "state_ref": str(state_path),
        "auto_promote_release": False,
        "auto_promote_exhaustive": False,
        "artifact_presentation_receipt": presentation,
        "pre_diagnostic_choice_event": pre_choice,
        "initial_review": {
            "authorized": True,
            "action": "run-once",
            "claim_id": "IRC-" + "d" * 32,
            "claimed_run_id": "build-20260820-01",
            "evaluator_id": "elegant-initial-draft-evaluator",
            "evaluator_context_limit": 1,
            "review_mode": "diagnostic-only",
            "target_edits_allowed": False,
            "thought_reset_required": True,
            "required_method_count": 30,
            "required_method_ids": method_ids,
            "target_manifest": target_manifest,
            "contract_binding": binding,
            "artifact_presentation_receipt_sha256": pre_diagnostic["presentation_receipt_sha256"],
            "pre_diagnostic_choice_event_sha256": pre_diagnostic["choice_event_sha256"],
            "pre_diagnostic_level": pre_diagnostic["selected_level"],
            "schema_ref": "schemas/initial-draft-review.schema.json",
            "prompt_ref": "prompts/R5-initial-draft-evaluate.md",
        },
        "improvement": {"authorized": False},
        "instruction": "run once",
    }
    state = {
        "schema_version": 2,
        "artifact_fingerprint_sha256": baseline,
        "subject": gate["subject"],
        "contract_binding": binding,
        "target_root": gate["target_root"],
        "target_roots": gate["target_roots"],
        "target_exclusions": gate["target_exclusions"],
        "target_manifest": target_manifest,
        "status": "claimed",
        "claim_id": gate["initial_review"]["claim_id"],
        "claimed_run_id": gate["run_id"],
        "created_at": "2026-08-20T00:00:00Z",
        "review": None,
        "review_sha256": None,
        "review_content_sha256": None,
        "decisions": {"pre_diagnostic": pre_diagnostic},
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return gate


def test_two_runtimes_share_one_strict_read_only_request(mod, tmp_path: Path):
    claude_gate = _gate_plan(tmp_path, state_name="claude")
    codex_gate = _gate_plan(tmp_path, state_name="codex")
    claude = mod.build_launch_request(claude_gate, runtime="claude-code")
    codex = mod.build_launch_request(codex_gate, runtime="codex")

    assert claude["runtime_neutral_request"] == codex["runtime_neutral_request"]
    common = claude["runtime_neutral_request"]
    assert common["context_policy"] == {
        "context_count": 1,
        "fresh_context": True,
        "parent_history_used": False,
    }
    assert common["tool_policy"]["mode"] == "read-only"
    assert common["tool_policy"]["allowed_tools"] == ["Read", "Glob", "Grep"]
    assert set(common["tool_policy"]["forbidden_capabilities"]) == {
        "write",
        "edit",
        "shell",
        "agent-spawn",
    }
    assert common["thought_reset"] == {
        "required": True,
        "physical_deletion_allowed": False,
        "fresh_target_read_required": True,
    }
    assert len(common["required_method_ids"]) == 30

    assert claude["authorized"] is codex["authorized"] is True
    assert claude["launch_count"] == codex["launch_count"] == 1
    assert common["launch_request_id"] == claude["request_id"]
    assert common["idempotency_key"] == claude["idempotency_key"] == claude["request_id"]
    assert claude["runtime_adapter"] == {
        "runtime": "claude-code",
        "invocation_kind": "task",
        "entrypoint": "elegant-initial-draft-evaluator",
    }
    assert codex["runtime_adapter"] == {
        "runtime": "codex",
        "invocation_kind": "subagent",
        "entrypoint": "prompts/R5-initial-draft-evaluate.md",
    }


def test_launcher_rejects_forged_proof_only_gate_without_presentation_and_prechoice(mod, tmp_path: Path):
    gate = _gate_plan(tmp_path)
    gate.pop("artifact_presentation_receipt")
    gate.pop("pre_diagnostic_choice_event")

    with pytest.raises(mod.LaunchError, match="artifact presentation"):
        mod.build_launch_request(gate, runtime="codex")

    assert not mod.launch_state_path(Path(gate["state_ref"])).exists()


def test_launch_request_is_schema_valid_and_sequential_replay_is_rejected(
    mod, tmp_path: Path
):
    gate = _gate_plan(tmp_path)
    first = mod.build_launch_request(gate, runtime="codex")
    with pytest.raises(mod.LaunchError, match="already consumed"):
        mod.build_launch_request(gate, runtime="codex")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft7Validator(schema).iter_errors(first)) == []
    launch_state = json.loads(
        mod.launch_state_path(Path(gate["state_ref"])).read_text(encoding="utf-8")
    )
    assert launch_state == {
        "claim_id": gate["initial_review"]["claim_id"],
        "artifact_fingerprint_sha256": gate["artifact_fingerprint_sha256"],
        "run_id": gate["run_id"],
        "runtime": "codex",
        "request_id": first["request_id"],
        "consumed_at": launch_state["consumed_at"],
        "lease_expires_at": launch_state["lease_expires_at"],
        "delivery_attempts": 1,
    }


def test_stale_lease_recovers_the_same_idempotency_identity(mod, tmp_path: Path):
    gate = _gate_plan(tmp_path)
    first = mod.build_launch_request(gate, runtime="codex")
    assert first["idempotency_key"] == first["request_id"]
    assert first["runtime_neutral_request"]["idempotency_key"] == first["request_id"]
    with pytest.raises(mod.LaunchError, match="lease is active"):
        mod.build_launch_request(gate, runtime="codex")

    receipt_path = mod.launch_state_path(Path(gate["state_ref"]))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["lease_expires_at"] = "2000-01-01T00:00:00Z"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(mod.LaunchError, match="same idempotency identity"):
        mod.build_launch_request(gate, runtime="claude-code")
    recovered = mod.build_launch_request(gate, runtime="codex")
    assert recovered == first
    refreshed = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert refreshed["request_id"] == first["request_id"]
    assert refreshed["delivery_attempts"] == 2
    assert refreshed["lease_expires_at"] != "2000-01-01T00:00:00Z"


def test_tampered_authoritative_state_is_rejected_without_consumption(
    mod, tmp_path: Path
):
    gate = _gate_plan(tmp_path)
    state_path = Path(gate["state_ref"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["claim_id"] = "IRC-" + "0" * 32
    state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(mod.LaunchError, match="does not match"):
        mod.build_launch_request(gate, runtime="claude-code")
    assert not mod.launch_state_path(state_path).exists()


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda value: value.update(status="initial-review-in-progress"), "status"),
        (
            lambda value: value["initial_review"].update(authorized=False),
            "authorized",
        ),
        (
            lambda value: value["initial_review"].update(evaluator_context_limit=2),
            "exactly one",
        ),
        (
            lambda value: value["initial_review"].update(target_edits_allowed=True),
            "read-only",
        ),
        (
            lambda value: value["initial_review"].update(thought_reset_required=False),
            "thought reset",
        ),
        (
            lambda value: value["initial_review"]["required_method_ids"].pop(),
            "30 unique",
        ),
    ],
)
def test_gate_contract_fails_closed_before_launch(mod, tmp_path: Path, mutate, match):
    gate = _gate_plan(tmp_path)
    mutate(gate)
    with pytest.raises(mod.LaunchError, match=match):
        mod.build_launch_request(gate, runtime="codex")


def test_unsupported_runtime_fails_closed_without_writing(tmp_path: Path):
    gate_path = tmp_path / "gate.json"
    out_path = tmp_path / "launch.json"
    gate = _gate_plan(tmp_path)
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--gate-plan",
            str(gate_path),
            "--runtime",
            "other",
            "--out",
            str(out_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "unsupported runtime" in proc.stderr
    assert json.loads(proc.stdout)["authorized"] is False
    assert not out_path.exists()
    assert not Path(f"{gate['state_ref']}.launch.json").exists()


def test_cli_writes_the_same_schema_valid_request(tmp_path: Path):
    gate_path = tmp_path / "gate.json"
    out_path = tmp_path / "launch.json"
    gate_path.write_text(json.dumps(_gate_plan(tmp_path)), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--gate-plan",
            str(gate_path),
            "--runtime",
            "claude-code",
            "--out",
            str(out_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert json.loads(proc.stdout) == written
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft7Validator(schema).iter_errors(written)) == []


def test_cli_multiprocess_replay_allows_exactly_one_launch(tmp_path: Path):
    gate_path = tmp_path / "gate.json"
    gate = _gate_plan(tmp_path)
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    command = [
        sys.executable,
        str(SCRIPT),
        "--gate-plan",
        str(gate_path),
        "--runtime",
        "codex",
    ]
    processes = [
        subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [process.communicate(timeout=10) for process in processes]
    codes = [process.returncode for process in processes]
    assert sorted(codes) == [0, 2]
    payloads = [json.loads(stdout) for stdout, _ in results]
    assert sorted(payload["launch_count"] for payload in payloads) == [0, 1]
    assert sorted(payload["authorized"] for payload in payloads) == [False, True]
    assert sum("already consumed" in stderr for _, stderr in results) == 1


def test_cli_multiprocess_stale_lease_allows_one_same_identity_redelivery(mod, tmp_path: Path):
    gate_path = tmp_path / "gate.json"
    gate = _gate_plan(tmp_path)
    first = mod.build_launch_request(gate, runtime="codex")
    receipt_path = mod.launch_state_path(Path(gate["state_ref"]))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["lease_expires_at"] = "2000-01-01T00:00:00Z"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    command = [sys.executable, str(SCRIPT), "--gate-plan", str(gate_path), "--runtime", "codex"]
    processes = [
        subprocess.Popen(command, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=10) for process in processes]
    assert sorted(process.returncode for process in processes) == [0, 2]
    payloads = [json.loads(stdout) for stdout, _ in results]
    authorized = next(payload for payload in payloads if payload["authorized"] is True)
    assert authorized["request_id"] == first["request_id"]
    assert authorized["idempotency_key"] == first["idempotency_key"]
    refreshed = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert refreshed["delivery_attempts"] == 2


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda value: value.update(baseline_fingerprint_sha256="bad"),
            "SHA-256",
        ),
        (
            lambda value: value.update(auto_promote_release=True),
            "auto promotion",
        ),
        (
            lambda value: value["initial_review"].update(
                evaluator_id="different-evaluator"
            ),
            "evaluator",
        ),
        (
            lambda value: value["initial_review"].update(claim_id="bad"),
            "claim",
        ),
        (
            lambda value: value["initial_review"].update(prompt_ref="other.md"),
            "prompt/schema",
        ),
        (
            lambda value: value["initial_review"]["target_manifest"].append(
                dict(value["initial_review"]["target_manifest"][0])
            ),
            "duplicate target",
        ),
    ],
)
def test_additional_tampering_is_rejected(mod, tmp_path: Path, mutate, match):
    gate = _gate_plan(tmp_path)
    mutate(gate)
    with pytest.raises(mod.LaunchError, match=match):
        mod.build_launch_request(gate, runtime="claude-code")


def test_manifest_routes_every_kind_build_through_common_usable_draft_proof():
    manifest = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    phases = {phase["id"]: phase for phase in manifest["phases"]}

    for phase in phases.values():
        if "kind_filter" in phase:
            assert set(phase["kind_filter"]) <= SKILL_SUBTYPES, phase["id"]
        if "capability_kind_filter" in phase:
            assert set(phase["capability_kind_filter"]) <= CAPABILITY_KINDS, phase["id"]

    init_pre = phases["init-pre"]
    assert "kind_filter" not in init_pre
    assert set(init_pre["capability_kind_filter"]) == CAPABILITY_KINDS

    non_skill_build = phases["non-skill-build-lint"]
    assert non_skill_build["dependsOn"] == ["init-pre"]
    assert set(non_skill_build["capability_kind_filter"]) == CAPABILITY_KINDS - {"skill"}
    assert "kind_filter" not in non_skill_build

    proof = phases["usable-draft-proof"]
    assert set(proof["capability_kind_filter"]) == CAPABILITY_KINDS
    assert "kind_filter" not in proof
    assert set(proof["dependsOn"]) == {"content-review", "non-skill-build-lint"}
    assert proof["dependency_mode"] == "applicable-capability-route"
    assert proof["upstream_by_capability_kind"] == {
        "skill": "content-review",
        "agent": "non-skill-build-lint",
        "hook": "non-skill-build-lint",
        "command": "non-skill-build-lint",
        "plugin-composition": "non-skill-build-lint",
        "prompt": "non-skill-build-lint",
        "workflow": "non-skill-build-lint",
    }
    assert proof["completion_gate"] == (
        "producer.exit_code=0 AND usable-draft-proof.status=PASS AND "
        "artifact-validation.exit_code=0 AND artifact-validation.valid=true AND "
        "artifact-validation.reported_kind=capability_kind"
    )
    assert proof["producer"].startswith("scripts/build-usable-draft-proof.py ")
    assert "--capability-artifact <repo-relative-capability-artifact>" in proof["producer"]
    assert "schema-usable-draft-proof" in proof["resourceIds"]
    assert "script-validate-build-trace" in proof["resourceIds"]

    delivery = phases["artifact-present-handoff"]
    assert delivery["dependsOn"] == ["usable-draft-proof"]
    assert delivery["events"] == [
        "artifact_created", "minimal_guard_passed", "artifact_presented"
    ]
    choice = phases["diagnostic-choice"]
    assert choice["dependsOn"] == ["artifact-present-handoff"]
    assert choice["accept_as_is_evaluator_contexts"] == 0
    assert choice["accept_as_is_improver_contexts"] == 0

    initial = phases["initial-draft-review"]
    assert initial["dependsOn"] == ["diagnostic-choice"]
    assert initial["default_on"] is False
    assert initial["entry_gate"].startswith("usable-draft-proof.status=PASS")
    assert "--usable-draft-proof <usable-draft-proof.json>" in initial["verifier"]
    assert "--artifact-presentation-receipt <artifact-presentation.json>" in initial["verifier"]
    assert "--pre-diagnostic-choice-event <pre-diagnostic-choice.json>" in initial["verifier"]
    assert set(initial["capability_kind_filter"]) == CAPABILITY_KINDS
    assert "kind_filter" not in initial
    assert initial["launcher"] == "scripts/build-review-launch.py"
    assert initial["max_active_launch_leases_per_harness"] == 1
    assert initial["single_active_delivery_lease_per_artifact_contract"] is True
    assert initial["stale_lease_redelivery"] == "same-idempotency-identity"
    assert initial["completed_receipt_reuse"] is True
    assert initial["delivery_semantics"] == "lease-with-idempotent-redelivery"
    assert initial["exactly_once_result_guaranteed"] is False
    assert "single_launch_authorization_per_artifact_contract" not in initial
    assert "max_evaluator_contexts_per_harness" not in initial
    assert "exactly_once_per_run" not in initial
    assert "exactly_once_per_artifact_contract" not in initial
    assert "agent-initial-draft-evaluator" in initial["resourceIds"]

    bounded = phases["bounded-improvement"]
    assert bounded["dependsOn"] == ["initial-draft-review"]
    assert set(bounded["capability_kind_filter"]) == CAPABILITY_KINDS
    assert bounded["executor"] == "elegant-bounded-improvement-executor"
    assert bounded["accept_draft_executor_contexts"] == 0

    post = phases["post-improvement-verification"]
    assert post["dependsOn"] == ["bounded-improvement"]
    assert post["verifier"].startswith("scripts/validate-improvement-result.py ")
    assert "--gate-state <state_ref>" in post["verifier"]
    assert "--target-root <target_root>" in post["verifier"]
    assert post["promotion_source"] == "improvement-decision.json"
    assert post["auto_promote_release"] is False
    assert post["auto_promote_exhaustive"] is False


def test_initial_prompt_and_agent_require_fresh_reset_and_method_evidence():
    prompt = (RUN_BUILD / "prompts/R5-initial-draft-evaluate.md").read_text(
        encoding="utf-8"
    )
    agent = (PLUGIN / "agents/elegant-initial-draft-evaluator.md").read_text(
        encoding="utf-8"
    )
    for text in (prompt, agent):
        assert "parent_history_used=false" in text
        assert "physical_deletion_performed=false" in text
        assert "target_manifest" in text
        assert "evidence_refs" in text
        assert "rationale" in text
        assert "idempotency_key" in text
        assert "symlink escape" in text
        assert "semantic duplicate" in text
        assert "launch_request_id" in text
        assert "evaluator.runtime" in text
        assert "baseline_fingerprint_sha256" in text


def test_skill_uses_only_c01_native_surface_apply_then_check():
    text = (RUN_BUILD / "SKILL.md").read_text(encoding="utf-8")
    assert "sync-native-surfaces.py --repo-root . --apply" in text
    assert "sync-native-surfaces.py --repo-root . --check" in text
    assert "make sync" not in text
    assert "sync-skills-to-claude.sh --apply" not in text
    assert "共通 `usable-draft-proof` (Step 12.4)" in text
    assert "`initial-draft-review` (Step 12.5) へ合流" in text
    assert "評価Agent・改善Agentによる捏造" in text
    assert "別turn" in text
