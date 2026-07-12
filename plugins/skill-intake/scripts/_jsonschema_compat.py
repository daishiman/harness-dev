#!/usr/bin/env python3
"""Small JSON Schema fallback used when bundled jsonschema is unavailable.

It intentionally implements only the schema keywords used by skill-intake's
bundled schemas. This keeps Claude Code plugin installs usable on machines
where a vendored binary dependency is incompatible.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationError(Exception):
    message: str
    absolute_path: tuple[Any, ...] = ()

    def __str__(self) -> str:
        return self.message


def _type_ok(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return (isinstance(instance, int) or isinstance(instance, float)) and not isinstance(instance, bool)
    if expected == "null":
        return instance is None
    return True


def _resolve_ref(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValidationError(f"unsupported $ref: {ref}")
    cur: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(cur, dict) or part not in cur:
            raise ValidationError(f"unresolved $ref: {ref}")
        cur = cur[part]
    if not isinstance(cur, dict):
        raise ValidationError(f"$ref does not point to schema object: {ref}")
    return cur


def _matches(instance: Any, schema: dict, root: dict) -> bool:
    return not list(_iter_errors(instance, schema, root, ()))


def _iter_errors(instance: Any, schema: Any, root: dict, path: tuple[Any, ...]):
    if not isinstance(schema, dict):
        return

    if "$ref" in schema:
        yield from _iter_errors(instance, _resolve_ref(root, schema["$ref"]), root, path)
        return

    for subschema in schema.get("allOf", []) or []:
        yield from _iter_errors(instance, subschema, root, path)

    if "if" in schema and _matches(instance, schema["if"], root):
        yield from _iter_errors(instance, schema.get("then", {}), root, path)

    if "const" in schema and instance != schema["const"]:
        yield ValidationError(f"{instance!r} is not equal to const {schema['const']!r}", path)
    if "enum" in schema and instance not in schema["enum"]:
        yield ValidationError(f"{instance!r} is not one of {schema['enum']!r}", path)

    expected_type = schema.get("type")
    if expected_type:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_type_ok(instance, t) for t in types):
            yield ValidationError(f"{instance!r} is not of type {expected_type!r}", path)
            return

    if isinstance(instance, str) and schema.get("pattern"):
        if re.search(schema["pattern"], instance) is None:
            yield ValidationError(f"{instance!r} does not match pattern {schema['pattern']!r}", path)
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            yield ValidationError(f"{instance!r} is shorter than minLength {schema['minLength']!r}", path)
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            yield ValidationError(f"{instance!r} is longer than maxLength {schema['maxLength']!r}", path)
        fmt = schema.get("format")
        if fmt == "date-time":
            try:
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
            except ValueError:
                yield ValidationError(f"{instance!r} is not a valid date-time", path)
        elif fmt == "uri":
            parsed = urlparse(instance)
            if not parsed.scheme or not parsed.netloc:
                yield ValidationError(f"{instance!r} is not a valid uri", path)

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            yield ValidationError(f"{instance!r} is less than minimum {schema['minimum']!r}", path)
        if "maximum" in schema and instance > schema["maximum"]:
            yield ValidationError(f"{instance!r} is greater than maximum {schema['maximum']!r}", path)

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            yield ValidationError(f"{instance!r} is too short", path)
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            yield ValidationError(f"{instance!r} is too long", path)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(instance):
                yield from _iter_errors(item, item_schema, root, (*path, i))

    if isinstance(instance, dict):
        props = schema.get("properties") or {}
        for name in schema.get("required", []) or []:
            if name not in instance:
                yield ValidationError(f"{name!r} is a required property", (*path, name))
        for name, subschema in props.items():
            if name in instance:
                yield from _iter_errors(instance[name], subschema, root, (*path, name))
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in props:
                    yield ValidationError(f"additional property {name!r} is not allowed", (*path, name))


class _Validator:
    def __init__(self, schema: dict):
        self.schema = schema

    @classmethod
    def check_schema(cls, schema: dict) -> None:
        if not isinstance(schema, dict):
            raise ValidationError("schema must be an object")

    def iter_errors(self, instance: Any):
        yield from _iter_errors(instance, self.schema, self.schema, ())


class _Validators:
    @staticmethod
    def validator_for(schema: dict):
        return _Validator


validators = _Validators()


def validate(instance: Any, schema: dict) -> None:
    first = next(_iter_errors(instance, schema, schema, ()), None)
    if first:
        raise first
