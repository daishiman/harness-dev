from __future__ import annotations

import builtins
import importlib.util
import json
import sys
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load():
    name = "validate_graph_schema_c11_focused"
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / "validate-graph-schema.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def codes(findings: list[dict[str, str]]) -> set[str]:
    return {item["code"] for item in findings}


def test_fallback_validator_exercises_supported_draft_boundaries(monkeypatch):
    mod = load()
    assert mod._is_type(object(), "future-type") is True
    assert mod._format_ok("2026-07-13", "date") is True
    assert mod._format_ok("2026-07-13T12:30:00Z", "date-time") is True
    assert mod._format_ok("https://example.test/x", "uri") is True
    assert mod._format_ok("not-a-date", "date") is False
    assert mod._format_ok("not-a-datetime", "date-time") is False
    assert mod._format_ok("relative", "uri") is False

    assert mod._schema_fallback("x", True, {}) == []
    assert "forbidden" in mod._schema_fallback("x", False, {})[0][1]
    assert "invalid schema" in mod._schema_fallback("x", [], {})[0][1]
    assert "external schema" in mod._schema_fallback("x", {"$ref": "other.json"}, {})[0][1]
    assert "unresolved schema" in mod._schema_fallback("x", {"$ref": "#/missing"}, {})[0][1]

    schema = {
        "$defs": {"identifier": {"type": "string", "minLength": 2, "pattern": "^ID"}},
        "allOf": [{"type": "object"}],
        "type": "object",
        "required": ["identifier", "required_when_enabled"],
        "properties": {
            "identifier": {"$ref": "#/$defs/identifier"},
            "enabled": {"type": "boolean"},
            "required_when_enabled": {"type": ["string", "null"]},
            "choice": {"enum": ["a", "b"]},
            "fixed": {"const": "fixed"},
            "day": {"type": "string", "format": "date"},
            "instant": {"type": "string", "format": "date-time"},
            "url": {"type": "string", "format": "uri"},
            "number": {"type": "number", "minimum": 1, "maximum": 3},
            "items": {
                "type": "array",
                "minItems": 2,
                "maxItems": 3,
                "uniqueItems": True,
                "items": {"type": "integer"},
                "contains": {"const": 7},
            },
        },
        "additionalProperties": False,
        "if": {"properties": {"enabled": {"const": True}}},
        "then": {"required": ["required_when_enabled"]},
    }
    invalid = {
        "identifier": "x",
        "enabled": True,
        "choice": "c",
        "fixed": "wrong",
        "day": "bad",
        "instant": "bad",
        "url": "relative",
        "number": 0,
        "items": [1, 1, "bad", 9],
        "extra": "forbidden",
    }
    messages = [detail for _, detail in mod._schema_fallback(invalid, schema, schema)]
    for fragment in (
        "missing required property",
        "string is shorter",
        "does not match",
        "not in enum",
        "expected const",
        "invalid date",
        "invalid date-time",
        "invalid uri",
        "below minimum",
        "too many items",
        "items are not unique",
        "expected type",
        "contains constraint",
        "unknown properties",
    ):
        assert any(fragment in message for message in messages), fragment

    assert any("above maximum" in detail for _, detail in mod._schema_fallback(4, {"maximum": 3}, {}))
    assert any("too few items" in detail for _, detail in mod._schema_fallback([], {"minItems": 1}, {}))
    assert mod._schema_fallback([7], {"contains": {"const": 7}}, {}) == []
    assert mod._schema_fallback({"x": 1}, {"additionalProperties": {"type": "integer"}}, {}) == []

    real_import = builtins.__import__

    def without_jsonschema(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("focused fallback exercise")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_jsonschema)
    fallback = mod.schema_findings({"id": "x"}, {"type": "object", "required": ["status"]}, 0)
    assert fallback == [{"node": "x", "code": "schema_violation", "detail": "$: missing required property status"}]


def test_frontmatter_repo_root_and_artifact_failure_classification(tmp_path):
    mod = load()
    assert mod._scalar(" true ") is True
    assert mod._scalar("'quoted'") == "quoted"
    assert mod._scalar('"double quoted"') == "double quoted"
    assert mod._scalar("bare") == "bare"

    with pytest.raises(mod.ContractError, match="cannot read artifact"):
        mod.frontmatter_of(tmp_path / "absent.md")
    no_frontmatter = tmp_path / "plain.md"
    no_frontmatter.write_text("plain\n", encoding="utf-8")
    with pytest.raises(mod.ContractError, match="no YAML frontmatter"):
        mod.frontmatter_of(no_frontmatter)
    unterminated = tmp_path / "unterminated.md"
    unterminated.write_text("---\nid: one\nignored line\n", encoding="utf-8")
    with pytest.raises(mod.ContractError, match="not terminated"):
        mod.frontmatter_of(unterminated)

    graph = tmp_path / ".dev-graph" / "state" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text('{"nodes": []}\n', encoding="utf-8")
    assert mod._repo_root_for(graph, None) == tmp_path
    assert mod._repo_root_for(graph, str(tmp_path)) == tmp_path
    outside = tmp_path.parent / f"{tmp_path.name}-outside.json"
    outside.write_text("[]\n", encoding="utf-8")
    try:
        with pytest.raises(mod.ContractError, match="outside the canonical"):
            mod._repo_root_for(outside, None)
        with pytest.raises(mod.ContractError, match="escapes authority root"):
            mod._repo_root_for(outside, str(tmp_path))
    finally:
        outside.unlink()

    contract = {"common_frontmatter": {"required": ["graph_node_id", "title"]}}
    missing = {"graph_node_id": "missing", "artifact_kind": "issue", "file_path": "issues/missing.md"}
    result = mod.artifact_findings([missing], tmp_path, contract)
    assert result == [{"node": "missing", "code": "artifact_missing", "detail": "issues/missing.md"}]

    invalid_frontmatter = tmp_path / "issues" / "invalid.md"
    invalid_frontmatter.parent.mkdir()
    invalid_frontmatter.write_text("not frontmatter\n", encoding="utf-8")
    invalid = {"graph_node_id": "invalid", "artifact_kind": "issue", "file_path": "issues/invalid.md"}
    assert "frontmatter_invalid" in codes(mod.artifact_findings([invalid], tmp_path, contract))

    mismatched = tmp_path / "issues" / "mismatch.md"
    mismatched.write_text("---\ngraph_node_id: wrong\n---\n", encoding="utf-8")
    mismatch = {
        "graph_node_id": "right", "artifact_kind": "issue", "file_path": "issues/mismatch.md",
        "template_id": "issue", "template_version": "1.0.0",
    }
    mismatch_findings = mod.artifact_findings([mismatch], tmp_path, contract)
    assert {item["code"] for item in mismatch_findings} == {"frontmatter_missing", "frontmatter_parity_error"}

    escaped = {"id": "escaped", "artifact_kind": "unknown", "file_path": "../escape.md"}
    assert "artifact_path_invalid" in codes(mod.artifact_findings([escaped], tmp_path, contract))
    assert mod.artifact_findings([{"id": "none", "file_path": None}], tmp_path, contract) == []


def task(node_id: str, **overrides):
    node = {
        "id": node_id,
        "artifact_kind": "task",
        "status": "draft",
        "depends_on": [],
        "related_nodes": [],
        "architecture_refs": [],
        "tracker_binding": "none",
    }
    node.update(overrides)
    return node


def test_domain_dag_exact13_evidence_and_readiness_boundaries():
    mod = load()
    bad_refs = task(
        "bad-refs",
        tracker_binding="repo-config-default",
        related_nodes=["missing-related"],
        architecture_refs=["missing-architecture"],
        parent_feature="missing-feature",
    )
    assert {"unresolved_tracker_binding", "dangling_reference"} <= codes(mod.domain_findings([bad_refs]))

    feature = task("feature", artifact_kind="feature", status="done")
    short_package = [feature, task("p01", parent_feature="feature", feature_package_id=None, phase_ref="P01")]
    assert "feature_package_not_exact_13" in codes(mod.domain_findings(short_package))

    members = []
    for number in range(1, 14):
        evidence = [f"evidence-P{number:02d}"] if number in {7, 10, 11} else []
        members.append(task(
            f"p{number:02d}",
            status="done",
            parent_feature="feature",
            feature_package_id="package-1",
            phase_ref=f"P{number:02d}",
            depends_on=[f"p{number - 1:02d}"] if number > 1 else [],
            completion_evidence={"evidence_refs": evidence},
        ))
    exact = mod.domain_findings([feature, *members])
    assert not ({"feature_package_not_exact_13", "non_forward_phase_dependency", "premature_feature_done", "feature_evidence_missing"} & codes(exact))

    missing_evidence = [dict(member) for member in members]
    missing_evidence[6]["completion_evidence"] = {"evidence_refs": []}
    not_done = dict(missing_evidence[0], status="active")
    not_done["confirmation_status"] = "draft"
    not_done["evaluation_status"] = "pending"
    not_done["implementation_readiness"] = {"status": "incomplete"}
    missing_evidence[0] = not_done
    negative_codes = codes(mod.domain_findings([feature, *missing_evidence]))
    assert {"active_not_ready", "premature_feature_done", "feature_evidence_missing"} <= negative_codes


def test_validate_rejects_invalid_authority_documents(monkeypatch):
    mod = load()

    def non_object_schema(path):
        return [] if path == mod.SCHEMA_PATH else {}

    monkeypatch.setattr(mod, "load_json", non_object_schema)
    with pytest.raises(mod.ContractError, match="schema must be an object"):
        mod.validate([])

    def non_object_template(path):
        return {} if path == mod.SCHEMA_PATH else []

    monkeypatch.setattr(mod, "load_json", non_object_template)
    with pytest.raises(mod.ContractError, match="template contract must be an object"):
        mod.validate([])

    with pytest.raises(mod.ContractError, match="invalid canonical graph schema"):
        mod.schema_findings({}, {"type": 42}, 0)
