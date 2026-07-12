#!/usr/bin/env python3
# /// script
# name: verify_plan
# purpose: 送信前二段確認の決定論検査。plan.json を独立に再読込し plan_hash 再計算・件数・先頭To・未置換トークン残存・宛先形式・multi_to_visible を承認文字列と照合し verdict JSON を出す。送信はしない。
# inputs:
#   - argv: --plan <plan.json> --approved-plan-hash <h> --approved-count <n> --approved-first-to <to> --approved-nonce <確認語>
# outputs:
#   - stdout: verdict JSON (send-verdict.schema.json 準拠)
#   - exit: 0=verdict出力(pass/fail は JSON 内) / 2=plan読込エラー
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""送信前二段確認 (仕様書 §7 presend-verify / §10 G3)。

context:fork の gmail-send-presend-verifier が呼ぶ独立再検査。build_plan が生成した plan を
親 context の判断に依存せず再計算で検証する。verdict は機械可読で、send 前ゲートの根拠になる。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT))
from lib import plan_build as pb, render_substitute as rs, message_assemble as ma  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--approved-plan-hash", required=True)
    ap.add_argument("--approved-count", required=True, type=int)
    ap.add_argument("--approved-first-to", required=True)
    ap.add_argument("--approved-nonce", default="", help="人間が入力した承認確認語 (照合用)")
    args = ap.parse_args()

    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"verdict": "fail", "error": f"plan読込失敗: {e}"}, ensure_ascii=False))
        return 2

    units = plan.get("units", [])
    mismatches: list[dict] = []

    # 1. plan_hash 独立再計算
    recomputed = pb.plan_hash(units)
    if recomputed != plan.get("plan_hash"):
        mismatches.append({"check": "plan_hash_recompute", "detail": "plan内 plan_hash と再計算値が不一致"})
    if args.approved_plan_hash != plan.get("plan_hash"):
        mismatches.append({"check": "approved_plan_hash", "detail": "承認 plan_hash と plan が不一致"})

    # 2. 件数
    if args.approved_count != len(units):
        mismatches.append({"check": "count", "detail": f"承認 {args.approved_count} ≠ units {len(units)}"})
    if plan.get("count") != len(units):
        mismatches.append({"check": "plan_count", "detail": "plan.count と units 数が不一致"})

    # 3. 先頭To
    first_to = units[0]["to_list"][0] if units and units[0].get("to_list") else ""
    if args.approved_first_to != first_to:
        mismatches.append({"check": "first_to", "detail": f"承認先頭To '{args.approved_first_to}' ≠ '{first_to}'"})

    # 4. 各 unit の未置換トークン / 宛先形式 / content_hash 再計算
    multi_to_units: list[int] = []
    for i, u in enumerate(units):
        unresolved = rs.find_unresolved_tokens(u.get("subject", "")) + rs.find_unresolved_tokens(u.get("body", ""))
        if unresolved:
            mismatches.append({"check": "unresolved_token", "unit": i, "detail": f"未置換 {unresolved}"})
        for addr in u.get("to_list", []) + u.get("cc_list", []):
            if not ma.validate_email(addr):
                mismatches.append({"check": "invalid_addr", "unit": i, "detail": f"不正 {addr}"})
        if pb.content_hash(u) != u.get("content_hash"):
            mismatches.append({"check": "content_hash", "unit": i, "detail": "content_hash 再計算不一致"})
        if u.get("multi_to_visible"):
            multi_to_units.append(i)

    # 承認確認語 (nonce): plan から決定論再計算。空または不一致なら fail。
    nonce_idx, nonce_code = pb.approval_nonce(plan.get("plan_hash", ""), units)
    if nonce_code and args.approved_nonce != nonce_code:
        mismatches.append({"check": "approval_nonce", "detail": "承認確認語が plan 計算値と不一致"})

    verdict = "pass" if not mismatches else "fail"
    print(json.dumps({
        "verdict": verdict,
        "plan_hash": plan.get("plan_hash"),
        "count": len(units),
        "first_to": first_to,
        "approval_nonce_unit": (nonce_idx + 1) if nonce_idx is not None else None,
        "approval_nonce": nonce_code,
        "multi_to_visible_units": multi_to_units,
        "mismatches": mismatches,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
