#!/usr/bin/env python3
"""Check Notion fidelity between intake-final-context.json and canonical snapshot.

Usage:
    python3 validate-notion-fidelity.py <intake-final-context.json> \
        [--snapshot <canonical-page-snapshot.json>] \
        [--pass-threshold 0.85] [--warn-threshold 0.70] \
        [--out-dir <dir>]

Exit codes: 0=pass / 1=warn / 2=fail / 64=usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = SKILL_DIR / "references/canonical-page-snapshot.json"

# context.json top-level key → canonical section_key
SECTION_KEY_MAP = {
    "executive_summary": "0_executive_summary",
    "assumption": "1_assumption_challenger",
    "profile": "2_user_profile",
    "purpose": "3_purpose_excavator",
    "options": "4_option_presenter",
    "figures": "5_visualizer",
    "five_axes": "6_five_axes_summary",
    "design_decisions": "7_design_decisions",
    "open_questions": "8_open_questions",
    "handoff": "9_handoff_contract",
    "self_update": "10_self_updater",
    "artifacts": "11_artifact_index",
}
INVERSE_KEY_MAP = {v: k for k, v in SECTION_KEY_MAP.items()}


def section_text_length(value) -> int:
    """rubric 規約に従い、本文相当 string を再帰結合した文字数 (空白除去)。"""
    parts: list[str] = []

    def _walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                _walk(item)
        elif isinstance(v, dict):
            for item in v.values():
                _walk(item)
        # int/float/bool/None は対象外

    _walk(value)
    joined = "".join(parts)
    return len("".join(joined.split()))


def _char_score(length: int, bounds: dict) -> float:
    lo = int(bounds.get("min", 0))
    hi = int(bounds.get("max", lo))
    if lo <= length <= hi:
        return 1.0
    if length < lo:
        return max(0.0, length / lo) if lo > 0 else 0.0
    # length > hi
    return max(0.0, 1.0 - (length - hi) / hi) if hi > 0 else 0.0


def _collect_field_keys(value) -> set[str]:
    """context section に「存在する」キー名を再帰収集。"""
    keys: set[str] = set()

    def _walk(v):
        if isinstance(v, dict):
            for k, vv in v.items():
                keys.add(k)
                _walk(vv)
        elif isinstance(v, list):
            for item in v:
                _walk(item)

    _walk(value)
    return keys


def _field_score(section_canonical: dict, section_value) -> tuple[float, list[str]]:
    required = section_canonical.get("required_fields", [])
    if not required:
        return 1.0, []
    present_keys = _collect_field_keys(section_value)
    total = 0.0
    missing: list[str] = []
    for f in required:
        key = f["key"]
        weight = 1.0
        if key in present_keys:
            total += weight
        else:
            if f.get("absence_behavior") == "warn-fallback":
                total += 0.5 * weight
                missing.append(f"{key} (warn-fallback)")
            else:
                missing.append(key)
    return total / len(required), missing


def _viz_score(section_canonical: dict, section_value) -> tuple[float, list[str], list[str]]:
    slots = section_canonical.get("viz_slots", [])
    mandatory = [s for s in slots if s.get("mandatory")]
    optional = [s for s in slots if not s.get("mandatory")]
    if not mandatory:
        return 1.0, [], [s.get("asset_id", "") for s in optional]
    present_assets: set[str] = set()
    if isinstance(section_value, list):
        for item in section_value:
            if isinstance(item, dict):
                for k in ("asset_id", "kind", "role"):
                    if k in item:
                        present_assets.add(str(item[k]))
    elif isinstance(section_value, dict):
        for k in ("asset_id", "kind", "role", "primary"):
            if k in section_value:
                present_assets.add(str(section_value[k]))
    missing: list[str] = []
    hit = 0
    for s in mandatory:
        aid = s.get("asset_id", "")
        # 互換マッチ: 完全一致 or substring
        if any(aid in p or p in aid for p in present_assets if p):
            hit += 1
        else:
            missing.append(aid)
    return (hit / len(mandatory)), missing, [s.get("asset_id", "") for s in optional]


def evaluate(context: dict, snapshot: dict) -> dict:
    sections_report = []
    weighted_sum = 0.0
    weight_total = 0.0
    forced_fail = False

    for sec in snapshot["sections"]:
        skey = sec["section_key"]
        ctx_key = INVERSE_KEY_MAP.get(skey)
        ctx_val = context.get(ctx_key) if ctx_key else None
        present = ctx_val is not None
        absence_block = sec.get("absence_behavior", "block") == "block"

        if not present:
            if absence_block:
                forced_fail = True
            section_report = {
                "section_key": skey,
                "context_key": ctx_key,
                "present": False,
                "granularity_score": 0,
                "char_score": 0.0,
                "field_score": 0.0,
                "viz_score": 0.0,
                "missing_slots": [s.get("asset_id") for s in sec.get("viz_slots", []) if s.get("mandatory")],
                "excess_slots": [],
                "missing_fields": [f["key"] for f in sec.get("required_fields", [])],
                "warnings": ["section absent"],
            }
            weight = 0.5 if sec.get("absence_behavior") == "warn-fallback" else 1.0
            weighted_sum += 0.0 * weight
            weight_total += weight
            sections_report.append(section_report)
            continue

        length = section_text_length(ctx_val)
        c_score = _char_score(length, sec.get("char_bounds", {}))
        f_score, missing_fields = _field_score(sec, ctx_val)
        v_score, missing_viz, optional_viz = _viz_score(sec, ctx_val)
        section_score = 0.30 * c_score + 0.40 * f_score + 0.30 * v_score
        warnings: list[str] = []
        if c_score < 1.0:
            warnings.append(f"char_bounds out of range (len={length})")
        section_report = {
            "section_key": skey,
            "context_key": ctx_key,
            "present": True,
            "text_length": length,
            "granularity_score": round(section_score * 100, 1),
            "char_score": round(c_score, 3),
            "field_score": round(f_score, 3),
            "viz_score": round(v_score, 3),
            "missing_slots": missing_viz,
            "excess_slots": optional_viz,
            "missing_fields": missing_fields,
            "warnings": warnings,
        }
        weight = 0.5 if sec.get("absence_behavior") == "warn-fallback" else 1.0
        weighted_sum += section_score * weight
        weight_total += weight
        sections_report.append(section_report)

    overall = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    return {
        "sections": sections_report,
        "overall_score": round(overall * 100, 1),
        "overall_score_ratio": round(overall, 4),
        "forced_fail": forced_fail,
    }


def _decide_verdict(overall_ratio: float, forced_fail: bool, pass_thr: float, warn_thr: float) -> tuple[str, int]:
    if forced_fail:
        return "fail", 2
    if overall_ratio >= pass_thr:
        return "pass", 0
    if overall_ratio >= warn_thr:
        return "warn", 1
    return "fail", 2


def _render_markdown(report: dict, verdict: str, thresholds: dict) -> str:
    lines = [
        f"# Fidelity Report — verdict={verdict}",
        "",
        f"- overall_score: **{report['overall_score']}** / 100",
        f"- pass_threshold: {thresholds['pass']} / warn_threshold: {thresholds['warn']}",
        f"- forced_fail (block-section absent): {report['forced_fail']}",
        "",
        "| section | present | score | missing_fields | missing_slots |",
        "|---|---|---|---|---|",
    ]
    for s in report["sections"]:
        lines.append(
            f"| {s['section_key']} | {s['present']} | {s.get('granularity_score', 0)} "
            f"| {', '.join(s.get('missing_fields', [])) or '-'} "
            f"| {', '.join(s.get('missing_slots', [])) or '-'} |"
        )
    lines.append("")
    if verdict == "fail":
        lines.append("> verdict=fail: render_notion_page.py を停止し handoff へ差し戻してください。")
    elif verdict == "warn":
        lines.append("> verdict=warn: 公開は可だが canonical 再生成を検討してください。")
    else:
        lines.append("> verdict=pass: Notion 公開を続行してよい状態です。")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("context", type=Path, help="intake-final-context.json")
    p.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    p.add_argument("--pass-threshold", type=float, default=0.85)
    p.add_argument("--warn-threshold", type=float, default=0.70)
    p.add_argument("--out-dir", type=Path, default=None, help="既定は context.json と同階層")
    args = p.parse_args(argv)

    if not (0.0 <= args.warn_threshold < args.pass_threshold <= 1.0):
        print("[validate-notion-fidelity] threshold order invalid", file=sys.stderr)
        return 64
    if not args.context.is_file():
        print(f"[validate-notion-fidelity] context not found: {args.context}", file=sys.stderr)
        return 64
    if not args.snapshot.is_file():
        print(f"[validate-notion-fidelity] snapshot not found: {args.snapshot}", file=sys.stderr)
        return 64

    context = json.loads(args.context.read_text(encoding="utf-8"))
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    report = evaluate(context, snapshot)
    verdict, code = _decide_verdict(
        report["overall_score_ratio"], report["forced_fail"], args.pass_threshold, args.warn_threshold
    )
    report["verdict"] = verdict
    report["thresholds"] = {"pass": args.pass_threshold, "warn": args.warn_threshold}

    out_dir = args.out_dir or args.context.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fidelity-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "fidelity-report.md").write_text(
        _render_markdown(report, verdict, report["thresholds"]), encoding="utf-8"
    )
    msg = f"[fidelity-guard] verdict={verdict} overall={report['overall_score']}"
    if verdict == "pass":
        print(msg)
    else:
        print(msg, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
