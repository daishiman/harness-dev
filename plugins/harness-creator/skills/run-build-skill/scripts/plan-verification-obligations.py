#!/usr/bin/env python3
"""Resolve a verification-obligation DAG without launching an LLM.

The planner makes verification cost proportional to changed claims and unresolved
uncertainty, not to route, agent, or thought-method counts.  Exact PASS evidence
is reusable only while the claim inputs, checker contract, and dependency
fingerprints remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROFILES = {"incremental", "exhaustive", "build-only"}
KINDS = {"generative", "deterministic", "semantic", "observational", "audit"}
RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEFAULT_MAX_CONTEXT_BYTES = 120_000
DEFAULT_INCREMENTAL_LLM_BATCHES = 1
DEFAULT_INCREMENTAL_MODEL_ACTIONS = 4


class ContractError(ValueError):
    """Raised when a contract cannot be resolved safely."""


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_rel(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ContractError(f"path must be repository-relative and cannot contain '..': {raw}")
    return path


def snapshot_path(repo_root: Path, raw: str) -> dict:
    """Return a deterministic digest/size snapshot for a file, dir, or symlink."""
    rel = _safe_rel(raw)
    path = repo_root / rel
    digest = hashlib.sha256()
    total_bytes = 0
    file_count = 0

    if path.is_symlink():
        target = os.readlink(path)
        digest.update(f"symlink\0{rel.as_posix()}\0{target}".encode("utf-8"))
        return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": len(target), "files": 1, "missing": False}
    if path.is_file():
        data = path.read_bytes()
        digest.update(f"file\0{rel.as_posix()}\0".encode("utf-8"))
        digest.update(data)
        return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": len(data), "files": 1, "missing": False}
    if path.is_dir():
        for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(repo_root).as_posix()):
            child_rel = child.relative_to(repo_root)
            if child.is_symlink():
                target = os.readlink(child)
                digest.update(f"symlink\0{child_rel.as_posix()}\0{target}\0".encode("utf-8"))
                total_bytes += len(target)
                file_count += 1
            elif child.is_file():
                data = child.read_bytes()
                digest.update(f"file\0{child_rel.as_posix()}\0".encode("utf-8"))
                digest.update(data)
                digest.update(b"\0")
                total_bytes += len(data)
                file_count += 1
        digest.update(f"dir\0{rel.as_posix()}\0{file_count}".encode("utf-8"))
        return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": total_bytes, "files": file_count, "missing": False}

    digest.update(f"missing\0{rel.as_posix()}".encode("utf-8"))
    return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": 0, "files": 0, "missing": True}


def _validate_contract(contract: dict) -> list[dict]:
    if contract.get("schema_version") != 1 or not str(contract.get("subject", "")).strip():
        raise ContractError("contract requires schema_version=1 and a non-empty subject")
    obligations = contract.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        raise ContractError("contract.obligations must be a non-empty array")
    ids: set[str] = set()
    for item in obligations:
        if not isinstance(item, dict):
            raise ContractError("every obligation must be an object")
        oid = str(item.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]*", oid):
            raise ContractError(f"invalid obligation id: {oid!r}")
        if oid in ids:
            raise ContractError(f"duplicate obligation id: {oid}")
        ids.add(oid)
        if item.get("kind") not in KINDS:
            raise ContractError(f"unknown obligation kind for {oid}: {item.get('kind')}")
        if not str(item.get("claim", "")).strip():
            raise ContractError(f"obligation claim is empty: {oid}")
        inputs = item.get("inputs")
        if not isinstance(inputs, list):
            raise ContractError(f"obligation inputs must be an array: {oid}")
        if not inputs and not isinstance(item.get("parameters"), dict):
            raise ContractError(f"obligation requires path inputs or inline parameters: {oid}")
        for entry in inputs:
            if not isinstance(entry, dict) or not isinstance(entry.get("required"), bool) or not isinstance(entry.get("context"), bool):
                raise ContractError(f"invalid input entry for {oid}")
            _safe_rel(str(entry.get("path", "")))
        for raw_path in item.get("expected_evidence_paths") or []:
            _safe_rel(str(raw_path))
        if item["kind"] == "generative" and not isinstance(item.get("model_required"), bool):
            raise ContractError(f"generative obligation requires model_required boolean: {oid}")
        if item["kind"] == "deterministic":
            checker = item.get("checker")
            if not isinstance(checker, dict) or not checker.get("id") or not checker.get("argv"):
                raise ContractError(f"deterministic obligation requires checker.id and checker.argv: {oid}")
        if item["kind"] == "audit" and item.get("activation") != "exhaustive":
            raise ContractError(f"audit obligation must use activation=exhaustive: {oid}")
        if item["kind"] == "observational" and item.get("observation_tier") not in {"fork", "live"}:
            raise ContractError(f"observational obligation requires observation_tier=fork|live: {oid}")
    for item in obligations:
        unknown = set(item.get("depends_on") or []) - ids
        if unknown:
            raise ContractError(f"unknown dependencies for {item['id']}: {sorted(unknown)}")
    return obligations


def _topological(obligations: list[dict]) -> list[dict]:
    by_id = {item["id"]: item for item in obligations}
    state: dict[str, int] = {}
    ordered: list[dict] = []

    def visit(oid: str) -> None:
        if state.get(oid) == 1:
            raise ContractError(f"dependency cycle contains: {oid}")
        if state.get(oid) == 2:
            return
        state[oid] = 1
        for dep in sorted(by_id[oid].get("depends_on") or []):
            visit(dep)
        state[oid] = 2
        ordered.append(by_id[oid])

    for oid in sorted(by_id):
        visit(oid)
    return ordered


def _load_receipts(evidence_dir: Path) -> list[tuple[Path, dict]]:
    receipts: list[tuple[Path, dict]] = []
    if not evidence_dir.is_dir():
        return receipts
    for path in sorted(evidence_dir.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        required = {"schema_version", "subject", "obligation_id", "fingerprint_sha256", "status", "confidence", "verifier", "evidence", "finding_codes", "produced_at"}
        structurally_valid = (
            isinstance(doc, dict)
            and required <= set(doc)
            and doc.get("schema_version") == 1
            and doc.get("status") in {"PASS", "FAIL", "INCONCLUSIVE"}
            and isinstance(doc.get("confidence"), (int, float))
            and 0 <= doc["confidence"] <= 1
            and isinstance(doc.get("verifier"), dict)
            and isinstance(doc.get("evidence"), list)
            and isinstance(doc.get("finding_codes"), list)
            and re.fullmatch(r"[0-9a-f]{64}", str(doc.get("fingerprint_sha256", "")))
        )
        if structurally_valid:
            receipts.append((path, doc))
    return receipts


def _receipt_artifacts_current(repo_root: Path, receipt: dict) -> bool:
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    for item in evidence:
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            return False
        try:
            current = snapshot_path(repo_root, str(item["path"]))
        except (OSError, ContractError):
            return False
        if current["missing"] or current["sha256"] != item["sha256"]:
            return False
    return True


def _matching_receipts(receipts: list[tuple[Path, dict]], repo_root: Path, subject: str, oid: str, fingerprint: str) -> list[tuple[Path, dict]]:
    return [
        (path, doc) for path, doc in receipts
        if doc.get("subject") == subject
        and doc.get("obligation_id") == oid
        and doc.get("fingerprint_sha256") == fingerprint
        and _receipt_artifacts_current(repo_root, doc)
    ]


def _pack_llm_batches(records: list[dict], snapshots: dict[str, dict], max_context_bytes: int) -> list[dict]:
    candidates = [record for record in records if record["action"] in {"adjudicate", "audit"}]
    candidates.sort(key=lambda record: (RISK_ORDER.get(record["risk"], 9), record["id"]))
    batches: list[dict] = []
    current_ids: list[str] = []
    current_paths: set[str] = set()

    def emit() -> None:
        if not current_ids:
            return
        size = sum(snapshots[path]["bytes"] for path in current_paths)
        batches.append({
            "batch_id": f"semantic-{len(batches) + 1}",
            "obligation_ids": list(current_ids),
            "context_paths": sorted(current_paths),
            "context_bytes": size,
            "over_budget": size > max_context_bytes,
        })

    for record in candidates:
        candidate_paths = set(record["context_paths"])
        union = current_paths | candidate_paths
        union_size = sum(snapshots[path]["bytes"] for path in union)
        if current_ids and union_size > max_context_bytes:
            emit()
            current_ids = []
            current_paths = set()
        current_ids.append(record["id"])
        current_paths |= candidate_paths
    emit()
    return batches


def build_plan(
    contract: dict,
    repo_root: Path,
    evidence_dir: Path,
    profile: str = "incremental",
    max_context_bytes: int = DEFAULT_MAX_CONTEXT_BYTES,
    max_llm_batches: int | None = None,
    run_id: str | None = None,
    max_model_actions: int | None = None,
) -> dict:
    if profile not in PROFILES:
        raise ContractError(f"unsupported profile: {profile}")
    if max_context_bytes < 1:
        raise ContractError("max_context_bytes must be positive")
    if max_llm_batches is not None and max_llm_batches < 0:
        raise ContractError("max_llm_batches must be non-negative")
    if max_model_actions is not None and max_model_actions < 0:
        raise ContractError("max_model_actions must be non-negative")
    effective_max_batches = (
        max_llm_batches
        if max_llm_batches is not None
        else DEFAULT_INCREMENTAL_LLM_BATCHES if profile == "incremental"
        else 0 if profile == "build-only"
        else None
    )
    effective_max_model_actions = (
        max_model_actions
        if max_model_actions is not None
        else DEFAULT_INCREMENTAL_MODEL_ACTIONS if profile in {"incremental", "build-only"}
        else None
    )
    repo_root = repo_root.resolve()
    obligations = _topological(_validate_contract(contract))
    subject = str(contract["subject"])
    receipts = _load_receipts(evidence_dir.resolve())

    snapshots: dict[str, dict] = {}
    fingerprints: dict[str, str] = {}
    for item in obligations:
        input_states = []
        for entry in item["inputs"]:
            path = str(entry["path"])
            snapshot = snapshots.setdefault(path, snapshot_path(repo_root, path))
            if entry["required"] and snapshot["missing"]:
                raise ContractError(f"required input is missing for {item['id']}: {path}")
            input_states.append({"path": path, "sha256": snapshot["sha256"], "missing": snapshot["missing"]})
        fingerprint_payload = {
            "id": item["id"],
            "claim": item["claim"],
            "kind": item["kind"],
            "risk": item["risk"],
            "activation": item["activation"],
            "checker": item.get("checker"),
            "observation_tier": item.get("observation_tier"),
            "parameters": item.get("parameters", {}),
            "expected_evidence_paths": item.get("expected_evidence_paths", []),
            "model_required": item.get("model_required"),
            "inputs": input_states,
            "dependency_fingerprints": {dep: fingerprints[dep] for dep in sorted(item.get("depends_on") or [])},
        }
        fingerprints[item["id"]] = _canonical_sha(fingerprint_payload)

    records: list[dict] = []
    actions: dict[str, str] = {}
    for item in obligations:
        oid = item["id"]
        fingerprint = fingerprints[oid]
        blocked_by = [dep for dep in item.get("depends_on") or [] if actions.get(dep) != "reuse"]
        context_paths = [str(entry["path"]) for entry in item["inputs"] if entry["context"]]
        record = {
            "id": oid,
            "claim": item["claim"],
            "kind": item["kind"],
            "risk": item["risk"],
            "fingerprint_sha256": fingerprint,
            "action": "blocked",
            "reason": "dependency-proof-missing",
            "blocked_by": blocked_by,
            "context_paths": context_paths,
            "checker": item.get("checker"),
            "observation_tier": item.get("observation_tier"),
            "expected_evidence_paths": item.get("expected_evidence_paths", []),
            "model_required": item.get("model_required"),
            "reused_evidence": None,
        }
        if item["kind"] == "audit" and profile != "exhaustive":
            record.update(action="defer", reason="audit-catalog-is-not-a-runtime-fanout")
        elif item.get("activation") == "exhaustive" and profile != "exhaustive":
            record.update(action="defer", reason="activation-requires-exhaustive")
        elif profile == "build-only" and item["kind"] not in {"generative", "deterministic"}:
            record.update(action="defer", reason="not-run(profile=build-only)")
        elif blocked_by:
            pass
        else:
            matching = _matching_receipts(receipts, repo_root, subject, oid, fingerprint)
            statuses = {doc.get("status") for _, doc in matching}
            minimum_confidence = float(item.get("minimum_confidence", 0.8))
            passes = [
                (path, doc) for path, doc in matching
                if doc.get("status") == "PASS" and float(doc.get("confidence", 0)) >= minimum_confidence
            ]
            may_reuse = item.get("reuse", True) is not False and item.get("activation") != "always"
            if len(statuses) > 1:
                record.update(action="escalate", reason="contradictory-current-evidence")
            elif may_reuse and passes:
                path, _ = sorted(passes, key=lambda pair: str(pair[0]))[-1]
                record.update(action="reuse", reason="exact-proof-current", reused_evidence=str(path))
            elif matching and statuses == {"FAIL"}:
                record.update(action="remediate", reason="current-proof-failed")
            elif matching and (statuses == {"INCONCLUSIVE"} or (statuses == {"PASS"} and not passes)):
                record.update(action="escalate", reason="uncertainty-above-threshold")
            elif item["kind"] == "generative":
                record.update(action="generate", reason="build-proof-missing")
            elif item["kind"] == "deterministic":
                record.update(action="check", reason="machine-proof-missing")
            elif item["kind"] == "semantic":
                record.update(action="adjudicate", reason="irreducible-semantic-proof-missing")
            elif item["kind"] == "observational":
                record.update(action="observe", reason="behavioral-proof-missing")
            else:
                record.update(action="audit", reason="explicit-exhaustive-audit")
        actions[oid] = record["action"]
        records.append(record)

    llm_batches = _pack_llm_batches(records, snapshots, max_context_bytes)
    finding_counts: Counter[tuple[str, str]] = Counter()
    for _, doc in receipts:
        if doc.get("subject") != subject or doc.get("status") not in {"FAIL", "INCONCLUSIVE"}:
            continue
        for code in set(doc.get("finding_codes") or []):
            finding_counts[(str(doc.get("obligation_id")), str(code))] += 1
    automation_candidates = [
        {"obligation_id": oid, "finding_code": code, "occurrences": count, "next_action": "promote-to-deterministic-checker"}
        for (oid, code), count in sorted(finding_counts.items()) if count >= 2
    ]
    counts = {action: sum(1 for record in records if record["action"] == action) for action in sorted(set(actions.values()))}
    total_context_bytes = sum(batch["context_bytes"] for batch in llm_batches)
    reused = counts.get("reuse", 0)
    total = len(records)
    budget_reasons = []
    if any(batch["over_budget"] for batch in llm_batches):
        budget_reasons.append("semantic-context-batch-exceeds-byte-budget")
    if effective_max_batches is not None and len(llm_batches) > effective_max_batches:
        budget_reasons.append("semantic-batch-count-exceeds-run-budget")
    consumed_action_keys = {
        str(doc.get("model_action_id") or path)
        for path, doc in receipts
        if run_id
        and doc.get("subject") == subject
        and doc.get("run_id") == run_id
        and isinstance(doc.get("verifier"), dict)
        and doc["verifier"].get("kind") in {"llm", "live"}
    }
    consumed_model_actions = len(consumed_action_keys)
    planned_model_actions = (
        sum(
            1
            for record in records
            if record["action"] == "generate" and record.get("model_required")
        )
        + len(llm_batches)
        + sum(1 for record in records if record["action"] == "observe")
    )
    if (
        effective_max_model_actions is not None
        and consumed_model_actions + planned_model_actions > effective_max_model_actions
    ):
        budget_reasons.append("cumulative-model-actions-exceed-run-budget")
    return {
        "schema_version": 1,
        "subject": subject,
        "run_id": run_id,
        "profile": profile,
        "cost_model": "changed-obligations-plus-unresolved-uncertainty",
        "counts": counts,
        "cost_summary": {
            "total_obligations": total,
            "proof_reuse_ratio": round(reused / total, 4) if total else 0,
            "avoided_executions": reused,
            "generation_actions": counts.get("generate", 0),
            "deterministic_checks": counts.get("check", 0),
            "semantic_actions": counts.get("adjudicate", 0) + counts.get("audit", 0),
            "observational_actions": counts.get("observe", 0),
            "semantic_context_bytes": total_context_bytes,
            "escalations": counts.get("escalate", 0),
            "consumed_model_actions": consumed_model_actions,
            "planned_model_actions": planned_model_actions,
        },
        "budget_gate": {
            "status": "blocked" if budget_reasons else "ok",
            "reasons": budget_reasons,
            "max_context_bytes_per_batch": max_context_bytes,
            "max_llm_batches": effective_max_batches,
            "max_model_actions": effective_max_model_actions,
            "instruction": "Do not launch model work while blocked; narrow context/contract or obtain an explicit budget override.",
        },
        "llm_batch_count": len(llm_batches),
        "llm_batches": llm_batches,
        "generation_queue": [record["id"] for record in records if record["action"] == "generate"],
        "observational_queue": [record["id"] for record in records if record["action"] == "observe"],
        "automation_candidates": automation_candidates,
        "obligations": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contract", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="incremental")
    parser.add_argument("--max-context-bytes", type=int, default=DEFAULT_MAX_CONTEXT_BYTES)
    parser.add_argument("--max-llm-batches", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--max-model-actions", type=int)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
        plan = build_plan(
            contract,
            Path(args.repo_root),
            Path(args.evidence_dir),
            args.profile,
            args.max_context_bytes,
            args.max_llm_batches,
            args.run_id,
            args.max_model_actions,
        )
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
