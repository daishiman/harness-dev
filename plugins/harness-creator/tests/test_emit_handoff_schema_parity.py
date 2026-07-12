"""emit-improvement-handoff.py (PB-C09) ↔ planner 正本 schema の逆向き parity テスト (F4)。

emit-improvement-handoff.py は cross-plugin import を避けるため improvement-handoff.schema.json
の制約を stdlib で*mirror 再実装*している (意図的)。前方 (planner→harness) は upstream-pins が
守るが、逆方向 (planner が schema を変えたのに harness emitter が無音で非準拠出力を作る) は無防備
だった。本テストは emit の実出力を **planner 正本 schema そのもの**で検証し、schema drift を
CI で赤くする二重化を敷く (mirror 実装自体は変えない)。

CI cwd = plugins/harness-creator から緑。planner schema が同 repo に無い standalone install では
skip する (emit-improvement-handoff / render-skill-brief の standalone fail-open と同じ方針)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# planner 正本 schema (owner)。repo-root 起点で解決 (cwd 非依存・CI cwd=harness-creator でも可)。
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "plugins/plugin-dev-planner/skills/run-plugin-dev-plan"
    / "schemas/improvement-handoff.schema.json"
)


def _load_schema() -> dict:
    if not _SCHEMA_PATH.is_file():
        pytest.skip(f"planner 正本 schema 不在 (standalone install): {_SCHEMA_PATH}")
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _emit_json(emit, tmp_path, findings, **over) -> dict:
    """emit.main を CLI 経由で回し、実際に直列化された improvement-handoff.json を得る。"""
    f = tmp_path / "findings.json"
    f.write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "improvement-handoff.json"
    argv = [
        "--source-kind", over.get("source_kind", "elegant-review"),
        "--source-ref", over.get("source_ref", "plugin-plans/sample/elegant-review-20260705.md"),
        "--target-plugin-slug", over.get("slug", "sample-plugin"),
        "--plan-dir", "plugin-plans/sample-plugin",
        "--findings", str(f),
        "-o", str(out),
    ]
    if over.get("origin_request_ref"):
        argv += ["--origin-request-ref", over["origin_request_ref"]]
    if over.get("origin_request_kind"):
        argv += ["--origin-request-kind", over["origin_request_kind"]]
    rc = emit.main(argv)
    assert rc == 0, f"emit.main が非0終了 (rc={rc})"
    return json.loads(out.read_text(encoding="utf-8"))


_GOOD = [{"id": "F1", "severity": "high", "summary": "断線 X", "recommendation": "配線する", "target_ref": "plugins/x/skills/run-y/SKILL.md"}]


def _validate_against_schema(instance: dict, schema: dict) -> list[str]:
    """jsonschema が使えれば正規に、無ければ schema 駆動の最小 fallback で検証する。

    fallback も enum/required/additionalProperties を **schema から読む** ため、
    planner が schema を変えれば追随して drift を検出する (emit の mirror 定数に依存しない)。
    """
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return _fallback_validate(instance, schema)
    errs: list[str] = []
    validator = jsonschema.Draft7Validator(schema)
    for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        errs.append(f"{list(e.path)}: {e.message}")
    return errs


def _fallback_validate(node, schema, path="$") -> list[str]:
    """object/array/enum/required/additionalProperties:false を再帰評価する最小 validator。"""
    errs: list[str] = []
    enum = schema.get("enum")
    if enum is not None and node not in enum:
        errs.append(f"{path}: {node!r} が enum {enum} に無い")
    typ = schema.get("type")
    types = typ if isinstance(typ, list) else [typ] if typ else []
    if "object" in types and isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                errs.append(f"{path}.{req}: required 欠落")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in node:
                if key not in props:
                    errs.append(f"{path}.{key}: additionalProperties:false 違反 (未知キー)")
        for key, subschema in props.items():
            if key in node:
                errs += _fallback_validate(node[key], subschema, f"{path}.{key}")
    if "array" in types and isinstance(node, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for i, el in enumerate(node):
                errs += _fallback_validate(el, items, f"{path}[{i}]")
    return errs


# ─────────────────── emit 実出力 × planner 正本 schema ───────────────────
def test_emit_elegant_review_output_conforms_to_planner_schema(emit, tmp_path):
    schema = _load_schema()
    instance = _emit_json(emit, tmp_path, _GOOD)
    errs = _validate_against_schema(instance, schema)
    assert errs == [], f"emit(elegant-review) が planner 正本 schema に非準拠: {errs}"


def test_emit_manual_output_conforms_to_planner_schema(emit, tmp_path):
    """source-kind=manual + origin_request (allOf 条件付き required) 経路も正本 schema に準拠する。"""
    schema = _load_schema()
    instance = _emit_json(
        emit, tmp_path, _GOOD,
        source_kind="manual", source_ref="https://notion.so/req-abc",
        origin_request_ref="https://notion.so/req-abc",
        origin_request_kind="notion-improvement-request",
    )
    errs = _validate_against_schema(instance, schema)
    assert errs == [], f"emit(manual) が planner 正本 schema に非準拠: {errs}"


# ─────────────────── mirror 定数 × schema enum の parity (silent drift 検出) ───────────────────
def _schema_enum(schema: dict, *path: str) -> list[str]:
    node = schema
    for seg in path:
        node = node["properties"][seg] if seg not in ("items",) else node["items"]
    return node["enum"]


def test_source_kind_enum_parity(emit):
    """planner が source.kind enum を変えたら emit の SOURCE_KINDS mirror と食い違い赤くなる。"""
    schema = _load_schema()
    assert set(emit.SOURCE_KINDS) == set(_schema_enum(schema, "source", "kind")), (
        "emit.SOURCE_KINDS が planner 正本 source.kind enum と drift"
    )


def test_severity_enum_parity(emit):
    schema = _load_schema()
    sev = schema["properties"]["findings"]["items"]["properties"]["severity"]["enum"]
    assert set(emit.SEVERITIES) == set(sev), "emit.SEVERITIES が planner 正本 severity enum と drift"


def test_origin_request_kind_enum_parity(emit):
    schema = _load_schema()
    ork = (
        schema["properties"]["provenance"]["properties"]
        ["origin_request"]["properties"]["kind"]["enum"]
    )
    assert set(emit.ORIGIN_REQUEST_KINDS) == set(ork), (
        "emit.ORIGIN_REQUEST_KINDS が planner 正本 origin_request.kind enum と drift"
    )


def test_top_level_required_parity(emit, tmp_path):
    """planner が top-level required を増やしたら emit 出力に欠け、schema 検証が赤くなることを保証する。"""
    schema = _load_schema()
    instance = _emit_json(emit, tmp_path, _GOOD)
    missing = [k for k in schema.get("required", []) if k not in instance]
    assert missing == [], f"emit 出力に planner 正本 required が欠落: {missing}"
