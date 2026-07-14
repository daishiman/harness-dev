#!/usr/bin/env python3
# /// script
# name: emit-improvement-handoff
# purpose: E3 境界の emitter。改善成果物 (run-elegant-review / content-review 等の findings) と routing 引数から improvement-handoff.json を正規化生成し、run-plugin-dev-plan --mode update (PB-C01) が受理できる構造化入力を produce する。
# inputs:
#   - argv: --source-kind K --source-ref R --target-plugin-slug S --plan-dir D --findings F.json [--schema-version V] [--generated-by G] [--source-intake I] [--prev-goal-spec P] [--origin-request-kind OK] [--origin-request-ref OR] [-o OUT]
# outputs:
#   - stdout: OUT 省略時は生成 JSON / 指定時は OK summary
#   - stderr: validation error
#   - exit: 0=OK / 1=validation violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: cwd (--output 指定時のみ)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""改善成果物 → improvement-handoff.json 正規化 emitter (E3)。

改善フロー (run-elegant-review 等) の findings を、run-plugin-dev-plan が --mode update で
受理する improvement-handoff.schema.json 準拠の JSON へ正規化する。schema 正本は
plugins/plugin-dev-planner/skills/run-plugin-dev-plan/schemas/improvement-handoff.schema.json。
本 script は harness-creator/scripts/ の plugin-root script のため cross-plugin import を避け、
schema の制約を stdlib のみで軽量に self-validate する (jsonschema 非依存)。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_KINDS = ("elegant-review", "content-review", "evaluator", "manual")
ORIGIN_REQUEST_KINDS = ("notion-improvement-request", "slack", "verbal", "other")
SEVERITIES = ("high", "medium", "low")


def normalize_findings(raw: object) -> list[dict]:
    """findings 入力を正規化する。bare array / {"findings":[...]} の両形を受理する。"""
    items = raw.get("findings") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        finding = {
            "id": str(item.get("id") or f"F{idx + 1}"),
            "severity": str(item.get("severity") or "medium").lower(),
            "summary": str(item.get("summary") or item.get("text") or "").strip(),
        }
        if item.get("recommendation"):
            finding["recommendation"] = str(item["recommendation"]).strip()
        if item.get("target_ref"):
            finding["target_ref"] = str(item["target_ref"]).strip()
        out.append(finding)
    return out


def build_handoff(args, findings: list[dict]) -> dict:
    handoff: dict = {
        "schema_version": args.schema_version,
        "source": {"kind": args.source_kind, "ref": args.source_ref},
        "target_plugin_slug": args.target_plugin_slug,
        "plan_dir": args.plan_dir,
        "findings": findings,
    }
    if args.generated_by:
        handoff["source"]["generated_by"] = args.generated_by
    provenance: dict = {}
    if args.source_intake is not None or args.prev_goal_spec is not None:
        provenance["source_intake"] = args.source_intake
        provenance["prev_goal_spec"] = args.prev_goal_spec
    if args.origin_request_ref is not None:
        provenance["origin_request"] = {
            "kind": args.origin_request_kind,
            "ref": args.origin_request_ref,
        }
    if provenance:
        handoff["provenance"] = provenance
    return handoff


def validate(handoff: dict) -> list[str]:
    """improvement-handoff.schema.json の fail-closed 制約を stdlib で検査する。"""
    errors: list[str] = []
    if not SCHEMA_VERSION_RE.match(str(handoff.get("schema_version", ""))):
        errors.append("schema_version は semver (X.Y.Z) であること")
    source = handoff.get("source")
    if not isinstance(source, dict):
        errors.append("source が object でない")
    else:
        if source.get("kind") not in SOURCE_KINDS:
            errors.append(f"source.kind は {list(SOURCE_KINDS)} のいずれか")
        if not str(source.get("ref", "")).strip():
            errors.append("source.ref が非空 string でない")
    if not SLUG_RE.match(str(handoff.get("target_plugin_slug", ""))):
        errors.append("target_plugin_slug は ASCII kebab-case であること")
    if not str(handoff.get("plan_dir", "")).strip():
        errors.append("plan_dir が非空 string でない")
    findings = handoff.get("findings")
    if not isinstance(findings, list) or not findings:
        errors.append("findings が非空 list でない (改善反映の実体が必要)")
    else:
        for idx, f in enumerate(findings):
            prefix = f"findings[{idx}]"
            if not str(f.get("id", "")).strip():
                errors.append(f"{prefix}.id が空")
            if f.get("severity") not in SEVERITIES:
                errors.append(f"{prefix}.severity は {list(SEVERITIES)} のいずれか")
            if not str(f.get("summary", "")).strip():
                errors.append(f"{prefix}.summary が空")
    origin = (handoff.get("provenance") or {}).get("origin_request")
    if isinstance(source, dict) and source.get("kind") == "manual" and origin is None:
        errors.append("source.kind=manual では provenance.origin_request が必須")
    if origin is not None:
        if not isinstance(origin, dict):
            errors.append("provenance.origin_request が object でない")
        else:
            if origin.get("kind") not in ORIGIN_REQUEST_KINDS:
                errors.append(f"provenance.origin_request.kind は {list(ORIGIN_REQUEST_KINDS)} のいずれか")
            if not str(origin.get("ref", "")).strip():
                errors.append("provenance.origin_request.ref が非空 string でない")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="改善成果物から improvement-handoff.json を emit する")
    ap.add_argument("--source-kind", required=True, choices=SOURCE_KINDS)
    ap.add_argument("--source-ref", required=True, help="改善成果物の参照 (path or id)")
    ap.add_argument("--target-plugin-slug", required=True)
    ap.add_argument("--plan-dir", required=True)
    ap.add_argument("--findings", required=True, help="findings JSON (bare array or {findings:[...]})")
    ap.add_argument("--schema-version", default="1.0.0")
    ap.add_argument("--generated-by", default=None)
    ap.add_argument("--source-intake", default=None, help="起点 intake.json 参照 (provenance)")
    ap.add_argument("--prev-goal-spec", default=None, help="改善前 goal-spec.json 参照 (provenance)")
    ap.add_argument("--origin-request-kind", default="notion-improvement-request",
                    choices=ORIGIN_REQUEST_KINDS,
                    help="改善の発端種別 (provenance.origin_request.kind)。--origin-request-ref 指定時に有効")
    ap.add_argument("--origin-request-ref", default=None,
                    help="改善の発端への参照 (Notion 改善要望ページ URL 等)。人間ブリッジで起点要望を追跡する (provenance.origin_request.ref)")
    ap.add_argument("-o", "--output", default=None, help="出力先 (省略時 stdout)")
    args = ap.parse_args(argv)

    findings_path = Path(args.findings)
    if not findings_path.is_file():
        sys.stderr.write(f"findings not found: {findings_path}\n")
        return 2
    try:
        raw = json.loads(findings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"findings JSON parse error: {exc}\n")
        return 2

    handoff = build_handoff(args, normalize_findings(raw))
    errors = validate(handoff)
    if errors:
        for err in errors:
            sys.stderr.write(err + "\n")
        return 1

    payload = json.dumps(handoff, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        sys.stdout.write(f"OK: improvement-handoff を {args.output} へ emit ({len(handoff['findings'])} findings)\n")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
