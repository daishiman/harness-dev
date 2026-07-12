from __future__ import annotations

# /// script
# name: test-extract-system-blueprint-llm-lanes
# purpose: CWV・compliance・feature fact 対 journey inference・layout template dedup の formal fixture 契約を検証する
# inputs:
#   - system-blueprint schema / tests fixtures JSON
# outputs:
#   - pytest assertions and explicit executable-gap xfail evidence
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [pytest, jsonschema]
# ///

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


TEST_ROOT = Path(__file__).resolve().parent
PLUGIN_ROOT = TEST_ROOT.parent
FIXTURE = json.loads((TEST_ROOT / "fixtures" / "llm-lanes.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((PLUGIN_ROOT / "schemas" / "system-blueprint.schema.json").read_text(encoding="utf-8"))
CONFIDENCE_SCHEMA = json.loads(
    (PLUGIN_ROOT / "schemas" / "fact-inference-confidence.schema.json").read_text(encoding="utf-8")
)


def _validator_for_property(name: str):
    jsonschema = pytest.importorskip("jsonschema")
    prop = copy.deepcopy(SCHEMA["properties"][name])
    prop["$defs"] = copy.deepcopy(SCHEMA.get("$defs", {}))

    def inline_confidence(value):
        if isinstance(value, dict):
            if value.get("$ref") == "fact-inference-confidence.schema.json#/$defs/confidence":
                value.clear()
                value.update(copy.deepcopy(CONFIDENCE_SCHEMA["$defs"]["confidence"]))
            for child in value.values():
                inline_confidence(child)
        elif isinstance(value, list):
            for child in value:
                inline_confidence(child)

    inline_confidence(prop)
    return jsonschema.Draft7Validator(prop)


def _messages(validator, value) -> list[str]:
    return [error.message for error in validator.iter_errors(value)]


def test_cwv_fixture_requires_all_four_metrics_and_scope_note():
    validator = _validator_for_property("cwv_field_sample")
    sample = FIXTURE["cwv_field_sample"]
    assert _messages(validator, sample) == []
    assert set(sample) == {"lcp", "cls", "inp", "ttfb", "scope_note"}
    assert "single visit" in sample["scope_note"]
    assert "no additional network" in sample["scope_note"]
    for required in ("lcp", "cls", "inp", "ttfb", "scope_note"):
        invalid = dict(sample)
        invalid.pop(required)
        assert any(required in message for message in _messages(validator, invalid))


def test_compliance_fixture_requires_privacy_terms_tokushoho_and_cmp():
    validator = _validator_for_property("compliance_surfaces")
    surfaces = FIXTURE["compliance_surfaces"]
    assert _messages(validator, surfaces) == []
    for required in ("privacy_policy", "terms", "tokushoho", "cookie_banner_cmp"):
        record = surfaces[required]
        assert record["present"] is True
        assert record["url"].startswith("https://")
        assert record["structure_summary"]
        invalid = dict(surfaces)
        invalid.pop(required)
        assert any(required in message for message in _messages(validator, invalid))


def test_compliance_schema_rejects_surface_without_url_or_summary():
    validator = _validator_for_property("compliance_surfaces")
    invalid = copy.deepcopy(FIXTURE["compliance_surfaces"])
    invalid["privacy_policy"] = {"present": True}
    assert _messages(validator, invalid), "privacy/terms/tokushoho child shapes are currently unconstrained"


def test_feature_map_fact_shape_is_distinct_from_journey_inference_shape():
    feature_validator = _validator_for_property("feature_map")
    journey_validator = _validator_for_property("user_journeys")
    feature_map = FIXTURE["feature_map"]
    journeys = FIXTURE["user_journeys"]
    assert _messages(feature_validator, feature_map) == []
    assert _messages(journey_validator, journeys) == []
    assert "per_screen_affordances" in feature_map
    assert all(item["evidence_refs"] and item["confidence"]["rationale"] for item in journeys)

    missing_grounding = copy.deepcopy(journeys)
    missing_grounding[0].pop("evidence_refs")
    assert any("evidence_refs" in message for message in _messages(journey_validator, missing_grounding))
    missing_confidence = copy.deepcopy(journeys)
    missing_confidence[0].pop("confidence")
    assert any("confidence" in message for message in _messages(journey_validator, missing_confidence))


def test_doc_emit_lane_gate_rejects_inference_in_feature_fact_and_ungrounded_journey(doc_emit):
    fact_errors = doc_emit._check_fact_lane(
        {"per_screen_affordances": [{"kind": "inference", "claim": "invented intent"}]},
        "feature_map",
    )
    assert any("inference が混入" in message for message in fact_errors)
    journey_errors = doc_emit._check_confidence_and_refs(
        {"kind": "inference", "confidence": {"level": "medium", "rationale": "fixture"}},
        "user_journeys[0]",
    )
    assert any("evidence_refs" in message for message in journey_errors)


def test_emitted_chapters_keep_fact_and_inference_in_separate_sections(doc_emit):
    extraction = {
        "feature_map": FIXTURE["feature_map"],
        "user_journeys": FIXTURE["user_journeys"],
    }
    chapters = doc_emit._render_chapters(extraction)
    assert "feature_map" in chapters["01-frontend-facts.md"]
    assert "start a trial" not in chapters["01-frontend-facts.md"]
    assert "user_journeys" in chapters["03-uiux-rationale.md"]
    assert "operation_types" not in chapters["03-uiux-rationale.md"]


def test_layout_template_hash_dedup_reduces_representative_count():
    implementation = PLUGIN_ROOT / "scripts" / "layout-template-dedup.py"
    proc = subprocess.run(
        [sys.executable, str(implementation), "--input", str(TEST_ROOT / "fixtures" / "llm-lanes.json")],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(proc.stdout)
    expected = FIXTURE["layout_template_dedup"]
    assert result["before_count"] == expected["expected_count_before"]
    assert result["after_count"] == expected["expected_count_after"]
    assert result["selected"] == expected["expected_representative_urls"]
