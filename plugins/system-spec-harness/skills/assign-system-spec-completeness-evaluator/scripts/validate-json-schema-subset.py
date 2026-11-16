#!/usr/bin/env python3
# /// script
# name: json-schema-subset
# version: 0.1.0
# purpose: Validate JSON instances with the fail-closed Draft 7 keyword subset shipped by the completeness report schema.
# inputs: [Python mapping schema, JSON-compatible instance]
# outputs: [ValidationError iterator or SchemaDefinitionError]
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Small, dependency-free interpreter for the shipped Draft 7 vocabulary.

This module intentionally is not a general JSON Schema implementation.  It accepts every
keyword used by ``completeness-findings.schema.json`` and rejects unknown keywords,
unsupported keyword shapes, and refs it cannot resolve.  That makes extending the public
schema an explicit code-and-test change instead of silently weakening runtime validation.

``pattern`` is an ASCII-only portable subset shared by Python ``re`` and ECMA-262: optional
edge anchors, ASCII literal characters, positive alphanumeric character classes/ranges, and
the ``?``, ``*``, ``+``, ``{n}``, ``{n,}``, ``{n,m}`` quantifiers.  Escapes, dot, alternation,
groups/lookarounds, negated classes, non-ASCII pattern text, and interior anchors are rejected
at schema-build time.  The intentionally narrow grammar covers the shipped digest pattern
without claiming that Python's Unicode-aware regular expressions implement ECMA-262.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import unquote


SUPPORTED_KEYWORDS = frozenset(
    {
        "$id",
        "$ref",
        "$schema",
        "additionalItems",
        "additionalProperties",
        "allOf",
        "const",
        "definitions",
        "description",
        "enum",
        "items",
        "maximum",
        "maxItems",
        "minimum",
        "minItems",
        "minLength",
        "minProperties",
        "pattern",
        "properties",
        "required",
        "title",
        "type",
    }
)
JSON_TYPES = frozenset({"array", "boolean", "integer", "null", "number", "object", "string"})
DRAFT7_URIS = frozenset(
    {
        "http://json-schema.org/draft-07/schema#",
        "https://json-schema.org/draft-07/schema#",
    }
)
_BAD_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_QUANTIFIER = re.compile(r"\{([0-9]+)(?:,([0-9]*))?\}")


class SchemaDefinitionError(ValueError):
    """The schema uses a keyword or value shape outside the supported subset."""


@dataclass(frozen=True)
class ValidationError:
    """A deterministic instance validation failure."""

    message: str
    absolute_path: tuple[Any, ...]


def _location(path: Sequence[Any]) -> str:
    return "/".join(str(part) for part in path) or "(root)"


def _schema_error(path: Sequence[Any], message: str) -> SchemaDefinitionError:
    return SchemaDefinitionError(f"schema {_location(path)}: {message}")


def _check_portable_pattern(pattern: str, path: tuple[Any, ...]) -> None:
    """Reject regex syntax whose Python and ECMA-262 behavior is outside our contract."""
    if not pattern.isascii():
        raise _schema_error(path, "pattern must contain ASCII syntax only")

    index = 1 if pattern.startswith("^") else 0
    while index < len(pattern):
        char = pattern[index]
        if char == "$":
            if index != len(pattern) - 1:
                raise _schema_error(path, "pattern anchor '$' is supported only at the end")
            return
        if char == "\\":
            raise _schema_error(path, "pattern escape sequences are unsupported")
        if char in ".()|":
            raise _schema_error(path, f"pattern construct {char!r} is unsupported")
        if char == "^":
            raise _schema_error(path, "pattern anchor '^' is supported only at the start")
        if char in "*+?{}]":
            raise _schema_error(path, f"pattern quantifier or delimiter {char!r} lacks an atom")

        if char == "[":
            close = pattern.find("]", index + 1)
            if close < 0:
                raise _schema_error(path, "pattern character class is not closed")
            content = pattern[index + 1 : close]
            if not content or content.startswith("^"):
                raise _schema_error(path, "pattern character class must be positive and non-empty")
            item = 0
            while item < len(content):
                start = content[item]
                if not start.isascii() or not start.isalnum():
                    raise _schema_error(
                        path,
                        "pattern character classes support ASCII alphanumeric atoms/ranges only",
                    )
                if item + 1 < len(content) and content[item + 1] == "-":
                    if item + 2 >= len(content):
                        raise _schema_error(path, "pattern character-class range is incomplete")
                    end = content[item + 2]
                    if not end.isascii() or not end.isalnum() or ord(start) > ord(end):
                        raise _schema_error(path, "pattern character-class range is invalid")
                    item += 3
                else:
                    item += 1
            index = close + 1
        elif 0x20 <= ord(char) <= 0x7E and char not in "[]":
            index += 1
        else:
            raise _schema_error(path, f"pattern literal {char!r} is unsupported")

        if index >= len(pattern) or pattern[index] == "$":
            continue
        if pattern[index] in "*+?":
            index += 1
            continue
        if pattern[index] == "{":
            match = _QUANTIFIER.match(pattern, index)
            if match is None:
                raise _schema_error(path, "pattern counted quantifier is malformed")
            lower = int(match.group(1))
            upper_text = match.group(2)
            if upper_text not in (None, "") and lower > int(upper_text):
                raise _schema_error(path, "pattern counted quantifier range is reversed")
            index = match.end()


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's ``True == 1`` coercion."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if _is_number(left) or _is_number(right):
        return _is_number(left) and _is_number(right) and left == right
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and set(left) == set(right)
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    return False


def _is_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (bool, str)) or _is_number(value):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


class Draft7SubsetValidator:
    """Validate instances against the exact Draft 7 vocabulary shipped by this skill."""

    def __init__(self, schema: Mapping[str, Any]):
        if not isinstance(schema, dict):
            raise _schema_error((), "root schema must be an object")
        self.schema = schema
        self._check_schema(schema, ())
        self._check_refs(schema, ())

    def iter_errors(self, instance: Any) -> Iterator[ValidationError]:
        """Yield every supported validation failure in deterministic traversal order."""
        if not _is_json_value(instance):
            yield ValidationError("instance is not a finite JSON value", ())
            return
        yield from self._validate(instance, self.schema, (), set())

    def _check_schema(self, schema: Any, path: tuple[Any, ...]) -> None:
        if not isinstance(schema, dict):
            raise _schema_error(path, "subschema must be an object")
        unknown = sorted(set(schema) - SUPPORTED_KEYWORDS)
        if unknown:
            raise _schema_error(path, f"unsupported keyword {unknown[0]!r}")

        for keyword in ("$id", "title", "description"):
            if keyword in schema and not isinstance(schema[keyword], str):
                raise _schema_error(path + (keyword,), f"{keyword} must be a string")
        if "$schema" in schema:
            value = schema["$schema"]
            if not isinstance(value, str) or value not in DRAFT7_URIS:
                raise _schema_error(path + ("$schema",), "$schema must identify Draft 7")
        if "$ref" in schema and not isinstance(schema["$ref"], str):
            raise _schema_error(path + ("$ref",), "$ref must be a string")

        if "type" in schema:
            declared = schema["type"]
            declared_types = [declared] if isinstance(declared, str) else declared
            if (
                not isinstance(declared_types, list)
                or not declared_types
                or not all(isinstance(item, str) and item in JSON_TYPES for item in declared_types)
                or len(set(declared_types)) != len(declared_types)
            ):
                raise _schema_error(path + ("type",), "type must be a JSON type or a non-empty unique list of JSON types")

        for keyword in ("minLength", "minProperties", "minItems", "maxItems"):
            if keyword in schema and (not _is_integer(schema[keyword]) or schema[keyword] < 0):
                raise _schema_error(path + (keyword,), f"{keyword} must be a non-negative integer")
        for keyword in ("minimum", "maximum"):
            if keyword in schema and not _is_number(schema[keyword]):
                raise _schema_error(path + (keyword,), f"{keyword} must be a finite number")

        if "pattern" in schema:
            pattern = schema["pattern"]
            if not isinstance(pattern, str):
                raise _schema_error(path + ("pattern",), "pattern must be a string")
            _check_portable_pattern(pattern, path + ("pattern",))
            try:
                re.compile(pattern, flags=re.ASCII)
            except re.error as exc:
                raise _schema_error(path + ("pattern",), f"pattern is invalid: {exc}") from exc

        if "required" in schema:
            required = schema["required"]
            if (
                not isinstance(required, list)
                or not all(isinstance(item, str) for item in required)
                or len(set(required)) != len(required)
            ):
                raise _schema_error(path + ("required",), "required must be a unique list of strings")

        if "enum" in schema:
            values = schema["enum"]
            if not isinstance(values, list) or not values or not all(_is_json_value(item) for item in values):
                raise _schema_error(path + ("enum",), "enum must be a non-empty list of JSON values")
            if any(_json_equal(value, earlier) for index, value in enumerate(values) for earlier in values[:index]):
                raise _schema_error(path + ("enum",), "enum values must be unique")
        if "const" in schema and not _is_json_value(schema["const"]):
            raise _schema_error(path + ("const",), "const must be a JSON value")

        for keyword in ("properties", "definitions"):
            if keyword not in schema:
                continue
            mapping = schema[keyword]
            if not isinstance(mapping, dict) or not all(isinstance(key, str) for key in mapping):
                raise _schema_error(path + (keyword,), f"{keyword} must be an object of schemas")
            for key, subschema in mapping.items():
                self._check_schema(subschema, path + (keyword, key))

        for keyword in ("additionalProperties", "additionalItems"):
            if keyword not in schema:
                continue
            value = schema[keyword]
            if isinstance(value, bool):
                continue
            if not isinstance(value, dict):
                raise _schema_error(path + (keyword,), f"{keyword} must be a boolean or schema")
            self._check_schema(value, path + (keyword,))

        if "items" in schema:
            items = schema["items"]
            if isinstance(items, dict):
                self._check_schema(items, path + ("items",))
            elif isinstance(items, list) and items:
                for index, subschema in enumerate(items):
                    self._check_schema(subschema, path + ("items", index))
            else:
                raise _schema_error(path + ("items",), "items must be a schema or a non-empty list of schemas")

        if "allOf" in schema:
            all_of = schema["allOf"]
            if not isinstance(all_of, list) or not all_of:
                raise _schema_error(path + ("allOf",), "allOf must be a non-empty list of schemas")
            for index, subschema in enumerate(all_of):
                self._check_schema(subschema, path + ("allOf", index))

    def _check_refs(self, schema: Mapping[str, Any], path: tuple[Any, ...]) -> None:
        if "$ref" in schema:
            self._resolve_ref(schema["$ref"], path + ("$ref",))
        for keyword in ("properties", "definitions"):
            mapping = schema.get(keyword)
            if isinstance(mapping, dict):
                for key, subschema in mapping.items():
                    self._check_refs(subschema, path + (keyword, key))
        for keyword in ("additionalProperties", "additionalItems"):
            subschema = schema.get(keyword)
            if isinstance(subschema, dict):
                self._check_refs(subschema, path + (keyword,))
        items = schema.get("items")
        if isinstance(items, dict):
            self._check_refs(items, path + ("items",))
        elif isinstance(items, list):
            for index, subschema in enumerate(items):
                self._check_refs(subschema, path + ("items", index))
        all_of = schema.get("allOf")
        if isinstance(all_of, list):
            for index, subschema in enumerate(all_of):
                self._check_refs(subschema, path + ("allOf", index))

    def _resolve_ref(self, reference: str, path: tuple[Any, ...]) -> Mapping[str, Any]:
        if reference == "#":
            return self.schema
        if not reference.startswith("#/"):
            raise _schema_error(path, f"$ref must be a local JSON Pointer, got {reference!r}")
        target: Any = self.schema
        for raw_part in reference[2:].split("/"):
            if _BAD_PERCENT_ESCAPE.search(raw_part):
                raise _schema_error(path, f"$ref contains an invalid percent escape: {reference!r}")
            try:
                encoded_part = unquote(raw_part, encoding="utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise _schema_error(path, f"$ref contains invalid UTF-8: {reference!r}") from exc
            if re.search(r"~(?![01])", encoded_part):
                raise _schema_error(path, f"$ref contains an invalid JSON Pointer escape: {reference!r}")
            part = encoded_part.replace("~1", "/").replace("~0", "~")
            if isinstance(target, dict) and part in target:
                target = target[part]
            elif isinstance(target, list) and part.isdigit() and int(part) < len(target):
                target = target[int(part)]
            else:
                raise _schema_error(path, f"$ref cannot be resolved: {reference!r}")
        if not isinstance(target, dict):
            raise _schema_error(path, f"$ref target is not a supported schema object: {reference!r}")
        return target

    def _validate(
        self,
        instance: Any,
        schema: Mapping[str, Any],
        path: tuple[Any, ...],
        active: set[tuple[int, int]],
    ) -> Iterator[ValidationError]:
        pair = (id(schema), id(instance))
        if pair in active:
            yield ValidationError("cyclic $ref revisits the same instance", path)
            return
        next_active = active | {pair}

        if "$ref" in schema:
            yield from self._validate(
                instance,
                self._resolve_ref(schema["$ref"], ("$ref",)),
                path,
                next_active,
            )
            return

        for subschema in schema.get("allOf", ()):
            yield from self._validate(instance, subschema, path, next_active)

        if "type" in schema:
            declared = schema["type"]
            choices = (declared,) if isinstance(declared, str) else tuple(declared)
            if not any(self._matches_type(instance, item) for item in choices):
                yield ValidationError(f"value is not of type {list(choices)!r}", path)
                return

        if "const" in schema and not _json_equal(instance, schema["const"]):
            yield ValidationError(f"value does not equal const {schema['const']!r}", path)
        if "enum" in schema and not any(_json_equal(instance, choice) for choice in schema["enum"]):
            yield ValidationError(f"value is not one of {schema['enum']!r}", path)

        if isinstance(instance, dict):
            if "minProperties" in schema and len(instance) < schema["minProperties"]:
                yield ValidationError(f"object has fewer than minProperties={schema['minProperties']}", path)
            for key in schema.get("required", ()):
                if key not in instance:
                    yield ValidationError(f"required property {key!r} is missing", path)
            properties = schema.get("properties", {})
            for key, subschema in properties.items():
                if key in instance:
                    yield from self._validate(instance[key], subschema, path + (key,), next_active)
            additional = schema.get("additionalProperties", True)
            for key in sorted(instance.keys() - properties.keys()):
                if additional is False:
                    yield ValidationError(f"additional property {key!r} is not allowed", path + (key,))
                elif isinstance(additional, dict):
                    yield from self._validate(instance[key], additional, path + (key,), next_active)

        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < schema["minItems"]:
                yield ValidationError(f"array has fewer than minItems={schema['minItems']}", path)
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                yield ValidationError(f"array has more than maxItems={schema['maxItems']}", path)
            items = schema.get("items")
            if isinstance(items, dict):
                for index, item in enumerate(instance):
                    yield from self._validate(item, items, path + (index,), next_active)
            elif isinstance(items, list):
                for index, subschema in enumerate(items[: len(instance)]):
                    yield from self._validate(instance[index], subschema, path + (index,), next_active)
                additional = schema.get("additionalItems", True)
                for index in range(len(items), len(instance)):
                    if additional is False:
                        yield ValidationError("additional array item is not allowed", path + (index,))
                    elif isinstance(additional, dict):
                        yield from self._validate(instance[index], additional, path + (index,), next_active)

        if isinstance(instance, str):
            if "minLength" in schema and len(instance) < schema["minLength"]:
                yield ValidationError(f"string is shorter than minLength={schema['minLength']}", path)
            if "pattern" in schema and re.search(
                schema["pattern"], instance, flags=re.ASCII
            ) is None:
                yield ValidationError(f"string does not match pattern {schema['pattern']!r}", path)

        if _is_number(instance):
            if "minimum" in schema and instance < schema["minimum"]:
                yield ValidationError(f"number is less than minimum={schema['minimum']}", path)
            if "maximum" in schema and instance > schema["maximum"]:
                yield ValidationError(f"number is greater than maximum={schema['maximum']}", path)

    @staticmethod
    def _matches_type(instance: Any, declared: str) -> bool:
        if declared == "null":
            return instance is None
        if declared == "boolean":
            return isinstance(instance, bool)
        if declared == "object":
            return isinstance(instance, dict)
        if declared == "array":
            return isinstance(instance, list)
        if declared == "string":
            return isinstance(instance, str)
        if declared == "number":
            return _is_number(instance)
        if declared == "integer":
            return _is_integer(instance) or (
                isinstance(instance, float) and math.isfinite(instance) and instance.is_integer()
            )
        return False
