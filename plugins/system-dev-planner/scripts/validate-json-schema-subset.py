#!/usr/bin/env python3
# /// script
# name: validate-json-schema-subset
# purpose: 同梱 runtime schema が使う JSON Schema サブセットの決定論検証器を C12 向けに保持する。
# inputs: argv なし (validate-system-plan.py から読み込まれる library module)
# outputs: 呼び出し側への違反文字列リスト (stdout 出力なし)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""C12 が同梱 schema を検証するための最小 JSON Schema サブセット実装。

外部依存を持たない決定論検証器として、`feature-execution-package` および
`workstream-inventory` schema が実際に使う keyword だけを実装する。

**C14 (`build-system-handoff.py`) はこの module を import しない。** C14 は承認済み
成果物を生成する立場として C12 へのビルド依存を持たない設計であり、意図的に自前の
サブセット実装を保持する (当該 file の docstring 参照)。両者の重複は DRY 違反ではなく、
依存の非対称性を保つための設計判断である。統合したくなったときはこの制約を先に確認する。
"""
from __future__ import annotations

import json
import re
from datetime import datetime


def _type_matches(value: object, expected: object) -> bool:
    choices = expected if isinstance(expected, list) else [expected]
    mapping = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "boolean": lambda x: isinstance(x, bool),
        "null": lambda x: x is None,
    }
    return any(kind in mapping and mapping[kind](value) for kind in choices)


def _resolve_local_ref(root_schema: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported non-local schema ref: {ref}")
    value: object = root_schema
    for raw in ref[2:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"unresolved local schema ref: {ref}")
        value = value[key]
    if not isinstance(value, dict):
        raise ValueError(f"schema ref does not resolve to object: {ref}")
    return value


def schema_violations(value: object, schema: dict, path: str = "$", root_schema: dict | None = None) -> list[str]:
    """Validate the JSON-Schema subset used by the bundled runtime schemas.

    Supported constraints intentionally include every keyword used by
    feature-execution-package and workstream-inventory: local refs, type,
    required, properties/additionalProperties, const/enum/pattern, bounds,
    array prefix/items/uniqueness, allOf and if/then.
    """
    root = root_schema or schema
    if "$ref" in schema:
        return schema_violations(value, _resolve_local_ref(root, schema["$ref"]), path, root)
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None and not _type_matches(value, expected):
        return [f"{path}: type must be {expected!r}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is outside enum")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: pattern mismatch")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError:
                errors.append(f"{path}: invalid date-time")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: required property missing: {key}")
        properties = schema.get("properties", {})
        for key, child in properties.items():
            if key in value:
                errors.extend(schema_violations(value[key], child, f"{path}.{key}", root))
        extras = set(value) - set(properties)
        additional = schema.get("additionalProperties", True)
        if additional is False:
            for key in sorted(extras):
                errors.append(f"{path}: additional property forbidden: {key}")
        elif isinstance(additional, dict):
            for key in sorted(extras):
                errors.extend(schema_violations(value[key], additional, f"{path}.{key}", root))
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            errors.append(f"{path}: fewer than minProperties")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errors.append(f"{path}: more than maxProperties")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items are not unique")
        prefix = schema.get("prefixItems", [])
        for index, child in enumerate(prefix[:len(value)]):
            errors.extend(schema_violations(value[index], child, f"{path}[{index}]", root))
        items = schema.get("items")
        start = len(prefix) if prefix else 0
        if items is False and len(value) > start:
            errors.append(f"{path}: additional array items forbidden")
        elif isinstance(items, dict):
            for index in range(start, len(value)):
                errors.extend(schema_violations(value[index], items, f"{path}[{index}]", root))
    for child in schema.get("allOf", []):
        errors.extend(schema_violations(value, child, path, root))
    condition = schema.get("if")
    if isinstance(condition, dict) and not schema_violations(value, condition, path, root):
        then = schema.get("then")
        if isinstance(then, dict):
            errors.extend(schema_violations(value, then, path, root))
    return errors
