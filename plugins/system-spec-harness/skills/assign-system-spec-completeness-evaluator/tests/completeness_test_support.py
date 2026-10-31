"""assign-system-spec-completeness-evaluator のテスト共通 fixture。"""
from __future__ import annotations

import importlib
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_aggregate():
    path = SCRIPTS_DIR / "aggregate-completeness.py"
    spec = importlib.util.spec_from_file_location("aggregate_completeness", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGGREGATE = _load_aggregate()
AUDIT = importlib.import_module("audit_fork_attribution")


def golden_aspects(verdicts=None):
    verdicts = verdicts or {}
    return {
        aspect_id: {
            "verdict": verdicts.get(aspect_id, "PASS"),
            "auditor": specification["auditor"],
            "component": specification["component"],
            "summary": f"{specification['label']}: 監査 PASS",
            "evidence": ["exit=0"],
        }
        for aspect_id, specification in AGGREGATE.ASPECTS.items()
    }


def golden_delegations(verdicts=None, session_id="sess-1"):
    verdicts = verdicts or {}
    return [
        {
            "aspect": requirement["aspect"],
            "role": requirement["role"],
            "auditor": requirement["auditor"],
            "component": requirement["component"],
            "dispatch": {
                "tool": "Task", "subagent_type": requirement["auditor"], "session_id": session_id,
                "response_sha256": response_digest(requirement["auditor"], verdicts.get(requirement["aspect"], "PASS")),
            },
            "verdict": verdicts.get(requirement["aspect"], "PASS"),
            "evidence": [f"{requirement['auditor']}: 独立 context で監査"],
        }
        for requirement in AUDIT.required_delegations()
    ]


def response_digest(auditor: str, verdict: str = "PASS") -> str:
    return hashlib.sha256(f"{auditor}:{verdict}".encode("utf-8")).hexdigest()


def golden_ledger(auditors=None, session_id="sess-1", verdicts=None):
    if auditors is None:
        auditors = [requirement["auditor"] for requirement in AUDIT.required_delegations()]
    verdicts = verdicts or {}
    verdict_by_auditor = {
        requirement["auditor"]: verdicts.get(requirement["aspect"], "PASS")
        for requirement in AUDIT.required_delegations()
    }
    return {
        "path": "eval-log/system-spec-harness/audit-fork-ledger.jsonl",
        "exists": True,
        "dispatched": {name: 1 for name in auditors},
        "sessions": {name: {session_id: 1} for name in auditors},
        "receipts": {
            name: {
                session_id: {
                    response_digest(name, verdict_by_auditor.get(name, "PASS")): {
                        "tool_name": "Task", "verdict": verdict_by_auditor.get(name, "PASS"),
                    }
                }
            }
            for name in auditors
        },
        "receipts_v12": {},
        "malformed": 0,
    }


def golden_report(verdict="PASS", verdicts=None, findings=None, gaps=None, delegations=None):
    return {
        "evaluator": {"name": AGGREGATE.EVALUATOR_NAME, "version": "0.1.0", "context": "fork"},
        "verdict": verdict,
        "artifact_snapshot": {
            "schema_version": "system-spec-artifact-snapshot/v1",
            "artifacts": {"system-spec/index.md": "0" * 64},
        },
        "aspects": golden_aspects(verdicts),
        "audit_delegations": golden_delegations(verdicts) if delegations is None else delegations,
        "gate_results": [
            {"id": "G-matrix", "name": "validate-coverage-matrix", "exit_code": 0},
            {"id": "G-source-citation", "name": "validate-source-citation", "exit_code": 0},
            {
                "id": "G-knowledge-graph",
                "name": "validate-knowledge-graph",
                "exit_code": 0,
                "subgates": [
                    {
                        "profile": profile,
                        "command": ["python3", "validate-knowledge-graph.py"],
                        "exit_code": 0,
                        "stderr": "",
                    }
                    for profile in ("knowledge", "doctrine", "required-info", "cross")
                ],
            },
        ],
        "findings": findings if findings is not None else [{"severity": "info", "bucket": "matrix_coverage", "observation": "全観点 PASS"}],
        "gaps": gaps if gaps is not None else [],
    }


def write_ledger(path: Path, auditors=None, extra_lines=()):
    if auditors is None:
        auditors = [requirement["auditor"] for requirement in AUDIT.required_delegations()]
    lines = [
        json.dumps({
            "schema_version": "1.1", "ts": "2026-07-21T22:00:00Z", "session_id": "sess-1",
            "tool_name": "Task", "subagent_type": name, "prompt_sha256": "0" * 64,
            "response_sha256": response_digest(name), "audit_verdict": "PASS", "cwd": "/tmp/project",
        }, ensure_ascii=False)
        for name in auditors
    ]
    lines.extend(extra_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_matrix(path: Path, complete: bool = True):
    categories = ["database", "auth", "ui-ux", "security", "infrastructure", "backend", "frontend", "maintenance-ops"]
    platforms = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]
    matrix = {category: {platform: {"state": "確定", "qa_ref": "qa-1"} for platform in platforms} for category in categories}
    if not complete:
        matrix["database"]["web"] = {"state": "未収集"}
    path.write_text(json.dumps({
        "schema_version": "1.1",
        "design_application_contract_version": "1.0",
        "categories": [{"id": category, "label": category} for category in categories],
        "platforms": platforms,
        "matrix": matrix,
        "qa_log": [{
            "id": "qa-1",
            "design_applications": [{
                "knowledge_ref": "design-knowledge:test",
                "principle": "complete coverage",
                "applicability": "applied",
                "rationale": "the fixture confirms every matrix cell",
                "tradeoffs": ["one shared fixture decision"],
            }],
        }],
        "approval_log": [],
    }, ensure_ascii=False), encoding="utf-8")
