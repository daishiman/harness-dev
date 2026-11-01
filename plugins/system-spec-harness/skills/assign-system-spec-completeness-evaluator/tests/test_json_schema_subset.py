# /// script
# name: test-json-schema-subset
# purpose: stdlib-only Draft 7 subset validator の fail-closed schema build と出荷 schema 互換を検証する
# inputs:
#   - pytest 実行 (argv なし)
# outputs:
#   - pytest 結果
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""`validate-json-schema-subset.py` の Draft 7 subset 契約テスト。"""
from __future__ import annotations

import importlib.util
import itertools
import json
import re
import sys

import pytest

from completeness_test_support import SCRIPTS_DIR, SKILL_DIR, golden_report

_SPEC = importlib.util.spec_from_file_location(
    "json_schema_subset", SCRIPTS_DIR / "validate-json-schema-subset.py"
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["json_schema_subset"] = _MODULE
_SPEC.loader.exec_module(_MODULE)
Draft7SubsetValidator = _MODULE.Draft7SubsetValidator
SchemaDefinitionError = _MODULE.SchemaDefinitionError


PUBLIC_SCHEMA = SKILL_DIR / "schemas" / "completeness-findings.schema.json"


def messages(validator: Draft7SubsetValidator, instance) -> list[str]:
    return [error.message for error in validator.iter_errors(instance)]


def test_shipped_public_schema_builds_and_accepts_golden_report():
    validator = Draft7SubsetValidator(json.loads(PUBLIC_SCHEMA.read_text(encoding="utf-8")))

    assert list(validator.iter_errors(golden_report())) == []


def test_all_24_knowledge_profile_permutations_obey_tuple_order():
    validator = Draft7SubsetValidator(json.loads(PUBLIC_SCHEMA.read_text(encoding="utf-8")))
    canonical = ("knowledge", "doctrine", "required-info", "cross")
    accepted = []
    for permutation in itertools.permutations(canonical):
        report = golden_report()
        knowledge = next(
            item for item in report["gate_results"] if item["id"] == "G-knowledge-graph"
        )
        for subgate, profile in zip(knowledge["subgates"], permutation):
            subgate["profile"] = profile
        if not list(validator.iter_errors(report)):
            accepted.append(permutation)

    assert accepted == [canonical]


def test_schema_valued_additional_properties_are_validated():
    validator = Draft7SubsetValidator(
        {
            "type": "object",
            "properties": {"fixed": {"type": "string"}},
            "additionalProperties": {"type": "integer", "minimum": 0},
        }
    )

    assert messages(validator, {"fixed": "ok", "count": 2}) == []
    assert any("integer" in item for item in messages(validator, {"fixed": "ok", "count": True}))
    assert any("minimum" in item for item in messages(validator, {"fixed": "ok", "count": -1}))


def test_tuple_items_all_of_and_additional_items_are_enforced():
    validator = Draft7SubsetValidator(
        {
            "type": "array",
            "items": [
                {"allOf": [{"type": "string"}, {"minLength": 2}]},
                {"type": "integer"},
            ],
            "additionalItems": False,
        }
    )

    assert messages(validator, ["ok", 1]) == []
    assert messages(validator, ["x", 1])
    assert messages(validator, ["ok", 1, "extra"])


def test_schema_valued_additional_items_validate_every_extra_item():
    validator = Draft7SubsetValidator(
        {
            "type": "array",
            "items": [{"const": "header"}],
            "additionalItems": {"type": "integer", "minimum": 0},
        }
    )

    assert messages(validator, ["header", 0, 2]) == []
    assert any("integer" in item for item in messages(validator, ["header", True]))
    assert any("minimum" in item for item in messages(validator, ["header", -1]))


def test_shipped_ascii_digest_pattern_is_portable_and_enforced():
    validator = Draft7SubsetValidator({"type": "string", "pattern": "^[0-9a-f]{64}$"})

    assert messages(validator, "0" * 64) == []
    assert messages(validator, "g" * 64)


def test_python_unicode_digit_escape_is_rejected_as_nonportable():
    assert re.fullmatch(r"\d", "١") is not None, "Python \\d は Unicode 数字まで受理する反例"

    with pytest.raises(SchemaDefinitionError, match=r"pattern.*escape"):
        Draft7SubsetValidator({"type": "string", "pattern": r"^\d+$"})


@pytest.mark.parametrize(
    "pattern",
    [
        r"^\w+$",
        r"^a\.b$",
        "^(?=a)a$",
        "^(a)$",
        "^a|b$",
        "^.$",
        "^[^a]$",
        "^[a-z]+$?",
    ],
)
def test_unsupported_regex_escapes_and_constructs_fail_schema_build(pattern):
    with pytest.raises(SchemaDefinitionError, match="pattern"):
        Draft7SubsetValidator({"type": "string", "pattern": pattern})


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("#/definitions/%ZZ", "percent"),
        ("#/definitions/%FF", "UTF-8"),
        ("#/definitions/bad~2escape", "JSON Pointer escape"),
        ("#/definitions/bad~", "JSON Pointer escape"),
    ],
)
def test_malformed_local_uri_fragments_fail_schema_build(reference, expected):
    with pytest.raises(SchemaDefinitionError, match=expected):
        Draft7SubsetValidator(
            {"definitions": {"value": {"type": "string"}}, "$ref": reference}
        )


@pytest.mark.parametrize(
    ("key", "reference"),
    [
        ("a/b", "#/definitions/a~1b"),
        ("a~b", "#/definitions/a~0b"),
        ("café", "#/definitions/caf%C3%A9"),
    ],
)
def test_valid_pointer_and_utf8_fragment_encodings_resolve(key, reference):
    validator = Draft7SubsetValidator(
        {"definitions": {key: {"const": "ok"}}, "$ref": reference}
    )

    assert messages(validator, "ok") == []


@pytest.mark.parametrize("declared_type", ["integer", "number"])
def test_bool_is_not_a_json_number(declared_type):
    validator = Draft7SubsetValidator({"type": declared_type})

    assert messages(validator, True)
    assert messages(validator, 1) == []
    assert messages(validator, 1.0) == []


@pytest.mark.parametrize(
    ("schema", "keyword"),
    [
        ({"type": "object", "unknownKeyword": True}, "unknownKeyword"),
        ({"properties": {"x": {"mystery": 1}}}, "mystery"),
        ({"type": "map"}, "type"),
        ({"required": "x"}, "required"),
        ({"minLength": True}, "minLength"),
        ({"items": "string"}, "items"),
        ({"additionalProperties": 1}, "additionalProperties"),
        ({"allOf": []}, "allOf"),
    ],
)
def test_unknown_keywords_and_keyword_value_shapes_fail_schema_build(schema, keyword):
    with pytest.raises(SchemaDefinitionError, match=keyword):
        Draft7SubsetValidator(schema)


@pytest.mark.parametrize(
    "reference",
    [
        "other.schema.json#/definitions/value",
        "https://example.invalid/schema.json#/definitions/value",
        "#/definitions/missing",
    ],
)
def test_nonlocal_and_unresolved_refs_fail_schema_build(reference):
    schema = {
        "definitions": {"value": {"type": "string"}},
        "$ref": reference,
    }

    with pytest.raises(SchemaDefinitionError, match=r"\$ref"):
        Draft7SubsetValidator(schema)
