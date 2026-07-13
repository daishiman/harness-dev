#!/usr/bin/env python3
"""Derive a graph-level verification-obligation contract from build units.

One contract may contain many skills/routes.  Per-unit semantic claims remain
independently cacheable, while the resolver may batch all currently unresolved
claims into the minimum number of LLM contexts allowed by their actual context
size.  This breaks the old route -> review-session coupling.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _repo_rel(repo_root: Path, raw: str | Path) -> str:
    path = Path(raw)
    resolved = path.resolve() if path.is_absolute() else (repo_root / path).resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repo root: {raw}") from exc


def _unit_id(skill_dir: str) -> str:
    parts = Path(skill_dir).parts
    plugin = parts[parts.index("plugins") + 1] if "plugins" in parts and parts.index("plugins") + 1 < len(parts) else "plugin"
    skill = Path(skill_dir).name
    raw = f"{plugin}:{skill}"
    return re.sub(r"[^A-Za-z0-9:._-]+", "-", raw)


def _input(path: str, *, context: bool) -> dict:
    return {"path": path, "required": True, "context": context}


def derive_contract(units: list[dict], repo_root: Path, subject: str) -> dict:
    if not units:
        raise ValueError("at least one build unit is required")
    obligations: list[dict] = []
    semantic_ids: list[str] = []
    terminal_ids: list[str] = []
    audit_inputs: dict[str, dict] = {}
    seen_units: set[str] = set()
    # Contract argv is repository-portable.  Do not bake the current worktree's
    # absolute path into evidence fingerprints.
    validator = "plugins/harness-creator/skills/run-build-skill/scripts/validate-build-plan.py"

    for raw_unit in units:
        for key in ("build_plan", "skill_dir", "brief"):
            if not raw_unit.get(key):
                raise ValueError(f"unit requires {key}: {raw_unit}")
        build_plan = _repo_rel(repo_root, raw_unit["build_plan"])
        skill_dir = _repo_rel(repo_root, raw_unit["skill_dir"])
        brief = _repo_rel(repo_root, raw_unit["brief"])
        unit_id = str(raw_unit.get("id") or _unit_id(skill_dir))
        unit_id = re.sub(r"[^A-Za-z0-9:._-]+", "-", unit_id)
        if unit_id in seen_units:
            raise ValueError(f"duplicate build unit id: {unit_id}")
        seen_units.add(unit_id)
        plan_doc = json.loads((repo_root / build_plan).read_text(encoding="utf-8"))
        tier = str(plan_doc.get("acceptance_tier") or "static")
        if tier not in {"static", "fork", "live"}:
            raise ValueError(f"invalid acceptance_tier for {unit_id}: {tier}")

        machine_id = f"machine:{unit_id}:build-conformance"
        semantic_id = f"semantic:{unit_id}:intent-fidelity"
        common_inputs = [_input(brief, context=False), _input(build_plan, context=False), _input(skill_dir, context=False)]
        obligations.append({
            "id": machine_id,
            "claim": "The built artifact satisfies its deterministic build plan, schema, naming, trace, and dependency checks.",
            "kind": "deterministic",
            "risk": "high",
            "activation": "changed",
            "depends_on": [],
            "inputs": common_inputs,
            "checker": {
                "id": "validate-build-plan",
                "argv": ["python3", validator, "--brief", brief, "--check", "--skill-dir", skill_dir],
            },
            "minimum_confidence": 1.0,
            "reuse": True,
        })
        semantic_inputs = [_input(brief, context=True), _input(build_plan, context=True), _input(skill_dir, context=True)]
        obligations.append({
            "id": semantic_id,
            "claim": "The artifact faithfully solves the stated intent with no contradiction or omission, follows conventions, and has valid dependencies; judge only meaning not already proven by deterministic checks.",
            "kind": "semantic",
            "risk": "high",
            "activation": "changed",
            "depends_on": [machine_id],
            "inputs": semantic_inputs,
            "minimum_confidence": 0.8,
            "reuse": True,
        })
        semantic_ids.append(semantic_id)
        terminal_id = semantic_id
        if tier in {"fork", "live"}:
            observation_id = f"behavior:{unit_id}:{tier}-acceptance"
            obligations.append({
                "id": observation_id,
                "claim": f"The artifact behaves correctly in the minimum required {tier} acceptance environment.",
                "kind": "observational",
                "risk": "high",
                "activation": "changed",
                "depends_on": [machine_id, semantic_id],
                "inputs": [_input(skill_dir, context=True), _input(build_plan, context=False)],
                "observation_tier": tier,
                "minimum_confidence": 0.9,
                "reuse": True,
            })
            terminal_id = observation_id
        terminal_ids.append(terminal_id)
        for entry in semantic_inputs:
            audit_inputs[entry["path"]] = entry

    obligations.append({
        "id": "audit:30-paradigm-adversarial-coverage",
        "claim": "An explicit exhaustive audit uses the 30 thought methods as a coverage catalog and reports a finding or skip reason for every method without multiplying normal runtime review sessions.",
        "kind": "audit",
        "risk": "medium",
        "activation": "exhaustive",
        "depends_on": sorted(set(terminal_ids)),
        "inputs": [audit_inputs[path] for path in sorted(audit_inputs)],
        "minimum_confidence": 0.8,
        "reuse": False,
    })
    return {"schema_version": 1, "subject": subject, "obligations": obligations}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--subject")
    parser.add_argument("--unit-manifest", help="JSON: {subject?, units:[{build_plan,skill_dir,brief,id?}]} ")
    parser.add_argument("--build-plan")
    parser.add_argument("--skill-dir")
    parser.add_argument("--brief")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve()
        if args.unit_manifest:
            manifest = json.loads(Path(args.unit_manifest).read_text(encoding="utf-8"))
            units = manifest.get("units") or []
            subject = args.subject or str(manifest.get("subject") or "")
        else:
            if not all((args.build_plan, args.skill_dir, args.brief)):
                raise ValueError("provide --unit-manifest or all of --build-plan --skill-dir --brief")
            units = [{"build_plan": args.build_plan, "skill_dir": args.skill_dir, "brief": args.brief}]
            subject = args.subject or _unit_id(_repo_rel(repo_root, args.skill_dir))
        if not subject:
            raise ValueError("subject is required")
        contract = derive_contract(units, repo_root, subject)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
