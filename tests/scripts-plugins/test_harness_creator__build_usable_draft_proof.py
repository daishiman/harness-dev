"""Executable contract for the all-Capability usable-draft proof producer."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[2]
RUN_BUILD = ROOT / "plugins/harness-creator/skills/run-build-skill"
SCRIPT = RUN_BUILD / "scripts/build-usable-draft-proof.py"
GATE_SCRIPT = RUN_BUILD / "scripts/build-improvement-gate.py"
SCHEMA = RUN_BUILD / "schemas/usable-draft-proof.schema.json"
CAPABILITY_KINDS = (
    "skill",
    "agent",
    "hook",
    "command",
    "plugin-composition",
    "prompt",
    "workflow",
)


def _load_gate_module():
    spec = importlib.util.spec_from_file_location("build_improvement_gate_for_proof", GATE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _capability_artifact(root: Path, kind: str) -> Path:
    artifact_dir = root / f"artifacts/{kind}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    common = {
        "name": f"demo-{kind}",
        "description": f"{kind} capability artifact with a deterministic validation contract.",
        "kind": kind,
        "version": "1.0.0",
        "owner": "team-test",
    }
    if kind == "skill":
        artifact = artifact_dir / "SKILL.md"
        artifact.write_text(
            "---\n"
            "name: run-demo-skill\n"
            "description: A deterministic skill capability artifact for proof validation.\n"
            "kind: run\n"
            "version: 1.0.0\n"
            "owner: team-test\n"
            "triggers:\n  - when proof validation runs\n"
            "---\n# Demo\n",
            encoding="utf-8",
        )
        return artifact
    if kind == "agent":
        common.update(tools=["Read"], isolation="fork", phase="draft")
    elif kind == "hook":
        common.update(event="PreToolUse", command="python3 validate.py", timeout_ms=1000)
    elif kind == "command":
        common.update({"argument-hint": "<target>", "allowed-tools": ["Read"]})
    elif kind == "prompt":
        common.update(layers=[{"index": index, "title": f"Layer {index}"} for index in range(1, 8)])
    elif kind == "workflow":
        common.update(phases=[{"id": "draft", "agents": ["builder"]}])
    elif kind == "plugin-composition":
        common.update(capabilities=[{"kind": "hook", "ref": "hook:demo"}])
    artifact = artifact_dir / (
        "plugin-composition.json" if kind == "plugin-composition" else "capability.json"
    )
    _write_json(artifact, common)
    return artifact


def _fixture(root: Path, kind: str) -> tuple[Path, list[Path], Path]:
    plan = root / "eval-log/demo/build/verification-plan.json"
    _write_json(
        plan,
        {
            "schema_version": 1,
            "stage": "draft",
            "run_id": f"run-{kind}",
            "subject": f"demo-{kind}",
            "obligations": [{"id": "draft-check"}],
            "stage_gate": {
                "status": "usable-draft",
                "handoff_ready": True,
                "auto_promote": False,
            },
        },
    )
    plan_sha = _sha(plan)
    upstream_phase = "content-review" if kind == "skill" else "non-skill-build-lint"
    receipt_types = ("content-review",) if kind == "skill" else ("generation", "kind-lint")
    receipts = []
    for receipt_type in receipt_types:
        evidence = root / f"artifacts/{kind}/{receipt_type}.txt"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(f"{kind}:{receipt_type}\n", encoding="utf-8")
        receipt = root / f"eval-log/demo/build/{kind}-{receipt_type}-receipt.json"
        _write_json(
            receipt,
            {
                "schema_version": 1,
                "capability_kind": kind,
                "producer_phase": upstream_phase,
                "receipt_type": receipt_type,
                "status": "PASS",
                "verification_plan_sha256": plan_sha,
                "evidence_refs": [
                    {
                        "path": evidence.relative_to(root).as_posix(),
                        "sha256": _sha(evidence),
                    }
                ],
            },
        )
        receipts.append(receipt)
    return plan, receipts, _capability_artifact(root, kind)


def _run(
    root: Path,
    kind: str,
    plan: Path,
    receipts: list[Path],
    artifact: Path,
    out: Path,
):
    command = [
        sys.executable,
        str(SCRIPT),
        "--verification-plan",
        str(plan),
        "--capability-kind",
        kind,
        "--repo-root",
        str(root),
        "--capability-artifact",
        str(artifact.relative_to(root) if artifact.is_absolute() else artifact),
        "--out",
        str(out),
    ]
    for receipt in receipts:
        command.extend(["--upstream-receipt", str(receipt)])
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


@pytest.mark.parametrize("kind", CAPABILITY_KINDS)
def test_all_seven_kinds_produce_schema_valid_gate_input(tmp_path: Path, kind: str):
    plan, receipts, artifact = _fixture(tmp_path, kind)
    out = tmp_path / f"eval-log/demo/build/{kind}-usable-draft-proof.json"
    result = _run(tmp_path, kind, plan, receipts, artifact, out)
    assert result.returncode == 0, result.stderr
    proof = json.loads(out.read_text(encoding="utf-8"))
    Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(proof)
    assert json.loads(result.stdout) == proof
    assert proof["status"] == "PASS"
    assert proof["capability_kind"] == kind
    assert proof["verification_plan_sha256"] == _sha(plan)
    assert proof["upstream_phase"] == (
        "content-review" if kind == "skill" else "non-skill-build-lint"
    )
    assert {item["receipt_type"] for item in proof["upstream_receipts"]} == (
        {"content-review"} if kind == "skill" else {"generation", "kind-lint"}
    )
    assert proof["capability_artifact"] == {
        "path": artifact.relative_to(tmp_path).as_posix(),
        "sha256": _sha(artifact),
    }
    assert proof["artifact_validation"]["reported_kind"] == kind
    assert proof["artifact_validation"]["valid"] is True
    assert proof["artifact_validation"]["exit_code"] == 0
    assert proof["artifact_validation"]["mode"] == (
        "bundle" if kind == "plugin-composition" else "manifest"
    )
    plan_value = json.loads(plan.read_text(encoding="utf-8"))
    assert _load_gate_module()._validate_usable_draft_proof(
        proof,
        plan=plan_value,
        target_scope={
            "target_root": str(tmp_path.resolve()),
            "target_manifest": [
                {
                    "path": artifact.relative_to(tmp_path).as_posix(),
                    "sha256": _sha(artifact),
                    "size": artifact.stat().st_size,
                }
            ],
        },
    ) == proof


@pytest.mark.parametrize("kind", CAPABILITY_KINDS)
def test_schema_binds_reported_kind_to_each_requested_capability_kind(
    tmp_path: Path, kind: str
):
    plan, receipts, artifact = _fixture(tmp_path, kind)
    out = tmp_path / f"{kind}-proof.json"
    result = _run(tmp_path, kind, plan, receipts, artifact, out)
    assert result.returncode == 0, result.stderr
    proof = json.loads(out.read_text(encoding="utf-8"))
    proof["artifact_validation"]["reported_kind"] = (
        "workflow" if kind != "workflow" else "agent"
    )

    errors = list(
        Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).iter_errors(proof)
    )
    assert errors


def test_non_skill_requires_both_generation_and_lint_receipts(tmp_path: Path):
    plan, receipts, artifact = _fixture(tmp_path, "agent")
    result = _run(tmp_path, "agent", plan, receipts[:1], artifact, tmp_path / "proof.json")
    assert result.returncode == 2
    assert "generation and kind-lint" in result.stderr


def test_tampered_evidence_fails_closed(tmp_path: Path):
    plan, receipts, artifact = _fixture(tmp_path, "skill")
    evidence = tmp_path / "artifacts/skill/content-review.txt"
    evidence.write_text("tampered\n", encoding="utf-8")
    result = _run(tmp_path, "skill", plan, receipts, artifact, tmp_path / "proof.json")
    assert result.returncode == 2
    assert "evidence sha256 mismatch" in result.stderr


def test_non_usable_plan_fails_closed(tmp_path: Path):
    plan, receipts, artifact = _fixture(tmp_path, "workflow")
    value = json.loads(plan.read_text(encoding="utf-8"))
    value["stage_gate"]["handoff_ready"] = False
    _write_json(plan, value)
    result = _run(tmp_path, "workflow", plan, receipts, artifact, tmp_path / "proof.json")
    assert result.returncode == 2
    assert "usable-draft" in result.stderr


def test_relative_inputs_and_output_resolve_from_declared_repo_root(tmp_path: Path):
    plan, receipts, artifact = _fixture(tmp_path, "skill")
    result = _run(
        tmp_path,
        "skill",
        plan.relative_to(tmp_path),
        [receipt.relative_to(tmp_path) for receipt in receipts],
        artifact,
        Path("eval-log/demo/build/usable-draft-proof.json"),
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "eval-log/demo/build/usable-draft-proof.json").is_file()


def test_cli_requires_an_actual_capability_artifact_argument(tmp_path: Path):
    plan, receipts, _ = _fixture(tmp_path, "skill")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--verification-plan",
            str(plan),
            "--capability-kind",
            "skill",
            "--upstream-receipt",
            str(receipts[0]),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(tmp_path / "proof.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--capability-artifact" in result.stderr


@pytest.mark.parametrize("kind", CAPABILITY_KINDS)
def test_forged_pass_receipts_cannot_hide_an_invalid_artifact(tmp_path: Path, kind: str):
    plan, receipts, artifact = _fixture(tmp_path, kind)
    artifact.write_text("{}\n", encoding="utf-8")

    result = _run(tmp_path, kind, plan, receipts, artifact, tmp_path / "proof.json")

    assert result.returncode == 2
    assert "capability artifact validator" in result.stderr


def test_gate_rejects_valid_but_unrelated_artifact_outside_target_manifest(tmp_path: Path):
    plan, receipts, artifact = _fixture(tmp_path, "agent")
    out = tmp_path / "proof.json"
    result = _run(tmp_path, "agent", plan, receipts, artifact, out)
    assert result.returncode == 0, result.stderr
    proof = json.loads(out.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="authoritative target manifest"):
        _load_gate_module()._validate_usable_draft_proof(
            proof,
            plan=json.loads(plan.read_text(encoding="utf-8")),
            target_scope={"target_root": str(tmp_path.resolve()), "target_manifest": []},
        )


def test_gate_rejects_validator_identity_tamper(tmp_path: Path):
    plan, receipts, artifact = _fixture(tmp_path, "hook")
    out = tmp_path / "proof.json"
    result = _run(tmp_path, "hook", plan, receipts, artifact, out)
    assert result.returncode == 0, result.stderr
    proof = json.loads(out.read_text(encoding="utf-8"))
    proof["artifact_validation"]["validator_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="validator.*sha256"):
        _load_gate_module()._validate_usable_draft_proof(
            proof,
            plan=json.loads(plan.read_text(encoding="utf-8")),
            target_scope={
                "target_root": str(tmp_path.resolve()),
                "target_manifest": [{
                    "path": artifact.relative_to(tmp_path).as_posix(),
                    "sha256": _sha(artifact),
                    "size": artifact.stat().st_size,
                }],
            },
        )


def test_gate_reexecutes_public_validator_even_when_artifact_hash_is_forged_consistently(
    tmp_path: Path,
):
    plan, receipts, artifact = _fixture(tmp_path, "workflow")
    out = tmp_path / "proof.json"
    result = _run(tmp_path, "workflow", plan, receipts, artifact, out)
    assert result.returncode == 0, result.stderr
    proof = json.loads(out.read_text(encoding="utf-8"))

    artifact.write_text("{}\n", encoding="utf-8")
    forged_sha = _sha(artifact)
    proof["capability_artifact"]["sha256"] = forged_sha

    with pytest.raises(ValueError, match="public validator revalidation failed"):
        _load_gate_module()._validate_usable_draft_proof(
            proof,
            plan=json.loads(plan.read_text(encoding="utf-8")),
            target_scope={
                "target_root": str(tmp_path.resolve()),
                "target_manifest": [{
                    "path": artifact.relative_to(tmp_path).as_posix(),
                    "sha256": forged_sha,
                    "size": artifact.stat().st_size,
                }],
            },
        )


def test_gate_rejects_tampered_validator_binary_even_with_original_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan, receipts, artifact = _fixture(tmp_path, "command")
    out = tmp_path / "proof.json"
    result = _run(tmp_path, "command", plan, receipts, artifact, out)
    assert result.returncode == 0, result.stderr
    proof = json.loads(out.read_text(encoding="utf-8"))
    gate = _load_gate_module()
    tampered_validator = tmp_path / "validate-build-trace.py"
    tampered_validator.write_text("raise SystemExit(0)\n", encoding="utf-8")
    monkeypatch.setattr(gate, "BUILD_TRACE_VALIDATOR_PATH", tampered_validator)

    with pytest.raises(ValueError, match="validator sha256 mismatch"):
        gate._validate_usable_draft_proof(
            proof,
            plan=json.loads(plan.read_text(encoding="utf-8")),
            target_scope={
                "target_root": str(tmp_path.resolve()),
                "target_manifest": [{
                    "path": artifact.relative_to(tmp_path).as_posix(),
                    "sha256": _sha(artifact),
                    "size": artifact.stat().st_size,
                }],
            },
        )


def test_reported_kind_must_match_requested_capability_kind(tmp_path: Path):
    plan, receipts, _ = _fixture(tmp_path, "agent")
    hook_artifact = _capability_artifact(tmp_path, "hook")

    result = _run(tmp_path, "agent", plan, receipts, hook_artifact, tmp_path / "proof.json")

    assert result.returncode == 2
    assert "reported kind" in result.stderr
