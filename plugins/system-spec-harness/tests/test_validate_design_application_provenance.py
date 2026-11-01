"""Provenance-specific coverage for the system-spec matrix validator."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate-coverage-matrix.py"
PLATFORMS = [
    "web",
    "mobile",
    "tablet",
    "desktop-windows",
    "desktop-linux",
    "desktop-macos",
]
CATEGORIES = [
    "database",
    "auth",
    "ui-ux",
    "security",
    "infrastructure",
    "backend",
    "frontend",
    "maintenance-ops",
]


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_provenance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def _application() -> dict:
    return {
        "knowledge_ref": "ddd.md#Bounded Context",
        "principle": "Bounded Context",
        "applicability": "applied",
        "rationale": "単一境界として管理する",
        "tradeoffs": ["境界分割が必要になれば再評価する"],
    }


def _valid_matrix() -> dict:
    return {
        "schema_version": "1.1",
        "design_application_contract_version": "1.0",
        "categories": [{"id": category, "label": category} for category in CATEGORIES],
        "platforms": PLATFORMS,
        "matrix": {
            category: {
                platform: {"state": "確定", "qa_ref": "qa-001"}
                for platform in PLATFORMS
            }
            for category in CATEGORIES
        },
        "qa_log": [{
            "id": "qa-001",
            "question": "q",
            "answer": "a",
            "design_applications": [_application()],
        }],
        "approval_log": [],
    }


def test_provenance_is_fail_closed_and_accepts_canonical_value():
    state = _valid_matrix()
    state["qa_log"][0]["design_application_provenance"] = "legacy_backfill"
    findings = validator.validate(state, require_complete=True)
    assert any("design_application_provenance" in finding for finding in findings)

    state["qa_log"][0]["design_application_provenance"] = {
        "mode": "legacy_backfill",
        "writer": "set-qa-design-applications",
    }
    assert validator.validate(state, require_complete=True) == []


def test_provenance_validation_includes_unreferenced_qa():
    state = _valid_matrix()
    state["qa_log"].append({
        "id": "qa-unreferenced",
        "question": "q",
        "answer": "a",
        "design_application_provenance": {"mode": "legacy_backfill"},
    })
    findings = validator.validate(state, require_complete=False)
    assert any(
        "qa_log[qa-unreferenced].design_application_provenance" in finding
        for finding in findings
    )
