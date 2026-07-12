#!/usr/bin/env python3
# /// script
# name: emit-verdict
# purpose: C02 (assign-blueprint-fidelity-evaluator) の verdict 発行器。R1-evaluate が組み立てた
#          集約 assessment JSON (findings/observation_completeness/load_policy_result/gate_results/
#          recount/reconstruction) へ決定論規則を適用して PASS/FAIL を確定し、draft_hash に束縛した
#          verdict receipt を ESB_VERDICT_DIR へ書く。採点者が恣意的に verdict を決めず、gate 結果と
#          findings から機械規則で導出する (anti-Goodhart)。fail-fast != silent-fail: FAIL でも receipt
#          を必ず書き出し C01 (run-extract-blueprint) の品質ゲート/差し戻し判定が理由を読めるようにする。
# inputs:
#   - argv: --assessment ASSESSMENT_JSON --draft-hash HEX64 --out-dir DIR [--evaluated-at ISO8601]
# outputs:
#   - stdout: verdict サマリ (JSON)
#   - stderr: FAIL 理由 / assessment 構造違反
#   - exit: 0=PASS(receipt 書込) / 1=FAIL(receipt 書込) / 2=usage or 構造違反
# contexts: [E]
# network: false
# write-scope: --out-dir (ESB_VERDICT_DIR) 配下の <draft_hash>.verdict.json のみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""draft_hash 束縛 verdict の決定論発行 (stdlib 完結・network なし・被評価物 非書込)。

PASS の必要十分条件 (全て成立で PASS、1 つでも欠ければ FAIL):
  1. gate_results.mermaid_validate.status == "pass"        (C10 共有ゲート exit0)
  2. gate_results.doc_emit_check_screens.status == "pass"  (C11 共有ゲート exit0)
  3. recount.orphan_count == 0 かつ recount.agrees_with_gate == true (非共有再計数=common-mode 破り)
  4. findings に severity=="high" が 0 件                    (意味判定の致命指摘なし)
  5. observation_completeness.silent_gaps == 0 かつ key_screen_gaps == 0 (無言欠落/鍵画面 gap なし)
  6. load_policy_result.within_budget / concurrency_ok が全 true (screenshot_budget_ok は C15 browser-render を実行した場合のみ評価)
  7. reconstruction.top_level_missing == 0 / open_questions == 0 / scaffold_derivable == true
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
EVALUATOR = "assign-blueprint-fidelity-evaluator"
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
JST = timezone(timedelta(hours=9))

# assessment に必須のトップレベルキー。
_REQUIRED = (
    "findings",
    "observation_completeness",
    "load_policy_result",
    "gate_results",
    "recount",
    "reconstruction",
)


class UsageError(Exception):
    """argv/assessment 構造起因の usage エラー (exit 2)。"""


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UsageError(f"入力ファイルが存在しない: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"入力 JSON を読めない: {path}: {exc}") from exc


def _require_keys(obj, keys, ctx):
    if not isinstance(obj, dict):
        raise UsageError(f"{ctx} が object でない")
    missing = [k for k in keys if k not in obj]
    if missing:
        raise UsageError(f"{ctx} に必須キーが欠落: {', '.join(missing)}")


def decide(assessment: dict) -> tuple[str, list[str]]:
    """PASS/FAIL と FAIL 理由リストを決定論で返す。"""
    reasons: list[str] = []

    gates = assessment["gate_results"]
    _require_keys(gates, ("mermaid_validate", "doc_emit_check_screens"), "gate_results")
    for gate_key, label in (
        ("mermaid_validate", "C10 mermaid-validate"),
        ("doc_emit_check_screens", "C11 doc-emit --check-screens"),
    ):
        gate = gates[gate_key]
        if not isinstance(gate, dict) or gate.get("status") != "pass":
            reasons.append(f"{label} が pass でない (status={_get(gate, 'status')})")

    rc = assessment["recount"]
    _require_keys(rc, ("orphan_count", "agrees_with_gate"), "recount")
    if rc.get("orphan_count") != 0:
        reasons.append(f"非共有再計数で palette 孤児 {rc.get('orphan_count')} 件検出")
    if rc.get("agrees_with_gate") is not True:
        reasons.append("非共有再計数が C11 判定と不一致 (common-mode 誤りの疑い)")

    findings = assessment["findings"]
    if not isinstance(findings, list):
        raise UsageError("findings が配列でない")
    highs = [f for f in findings if isinstance(f, dict) and f.get("severity") == "high"]
    if highs:
        ids = ", ".join(str(f.get("id") or f.get("criterion") or "?") for f in highs)
        reasons.append(f"high severity finding {len(highs)} 件 ({ids})")

    oc = assessment["observation_completeness"]
    _require_keys(oc, ("silent_gaps", "key_screen_gaps"), "observation_completeness")
    if oc.get("silent_gaps"):
        reasons.append(f"無言欠落 {oc.get('silent_gaps')} 件 (not_observed+reason でない未取得 field)")
    if oc.get("key_screen_gaps"):
        reasons.append(f"鍵画面 gap {oc.get('key_screen_gaps')} 件")

    lp = assessment["load_policy_result"]
    _require_keys(lp, ("within_budget", "concurrency_ok"), "load_policy_result")
    for flag, label in (
        ("within_budget", "request/byte budget"),
        ("concurrency_ok", "対象 origin 並列 1"),
    ):
        if lp.get(flag) is not True:
            reasons.append(f"低負荷 policy 違反: {label} 未充足")
    # screenshot budget は C15 browser-render 実行時のみ必須。assessment にキーが在り False のとき FAIL 寄与とする。
    if "screenshot_budget_ok" in lp and lp.get("screenshot_budget_ok") is False:
        reasons.append("低負荷 policy 違反: screenshot budget 未充足")

    rec = assessment["reconstruction"]
    _require_keys(rec, ("top_level_missing", "open_questions", "scaffold_derivable"), "reconstruction")
    if rec.get("top_level_missing"):
        reasons.append(f"最小スカフォールド逆テスト: top-level 必須欠落 {rec.get('top_level_missing')} 件")
    if rec.get("open_questions"):
        reasons.append(f"最小スカフォールド逆テスト: 未回答質問 {rec.get('open_questions')} 件")
    if rec.get("scaffold_derivable") is not True:
        reasons.append("最小スカフォールド骨子を追加ヒアリングなしで導出できない")

    return ("FAIL" if reasons else "PASS"), reasons


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else None


def build_receipt(assessment: dict, draft_hash: str, evaluated_at: str) -> dict:
    verdict, _ = decide(assessment)
    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "draft_hash": draft_hash,
        "evaluated_at": evaluated_at,
        "evaluator": EVALUATOR,
        "findings": assessment["findings"],
        "observation_completeness": assessment["observation_completeness"],
        "load_policy_result": assessment["load_policy_result"],
        "gate_results": assessment["gate_results"],
        "recount": assessment["recount"],
        "reconstruction": assessment["reconstruction"],
    }


def run(args) -> int:
    draft_hash = str(args.draft_hash).strip().lower()
    if not _HEX64_RE.match(draft_hash):
        raise UsageError(f"--draft-hash が 64 桁 hex でない: {args.draft_hash}")
    assessment = _load(Path(args.assessment))
    _require_keys(assessment, _REQUIRED, "assessment")

    evaluated_at = args.evaluated_at or datetime.now(JST).isoformat(timespec="seconds")
    receipt = build_receipt(assessment, draft_hash, evaluated_at)
    verdict, reasons = decide(assessment)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / f"{draft_hash}.verdict.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "verdict": verdict,
        "draft_hash": draft_hash,
        "receipt_path": str(receipt_path),
        "fail_reasons": reasons,
        "finding_counts": _severity_counts(assessment["findings"]),
    }
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if verdict == "FAIL":
        for r in reasons:
            sys.stderr.write("FAIL: " + r + "\n")
        return 1
    return 0


def _severity_counts(findings) -> dict:
    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings if isinstance(findings, list) else []:
        sev = f.get("severity") if isinstance(f, dict) else None
        if sev in counts:
            counts[sev] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="draft_hash 束縛 verdict を決定論規則で発行し ESB_VERDICT_DIR へ書く",
        add_help=True,
    )
    ap.add_argument("--assessment", required=True, help="R1-evaluate が組み立てた集約 assessment JSON")
    ap.add_argument("--draft-hash", required=True, help="評価対象の draft_hash (C01 sink-status.json の値)")
    ap.add_argument("--out-dir", default=".esb-verdict", help="ESB_VERDICT_DIR (既定 .esb-verdict)")
    ap.add_argument("--evaluated-at", default=None, help="ISO8601 (既定は実行時刻 JST)")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        return run(args)
    except UsageError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
