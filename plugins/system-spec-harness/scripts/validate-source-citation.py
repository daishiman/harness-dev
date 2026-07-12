#!/usr/bin/env python3
# /// script
# name: validate-source-citation
# version: 0.1.0
# purpose: 取得対象一覧 (targets) と fetched-references.json を突合し、対象 ID ごとの参照が欠落 0 で、各エントリが retrieved_at/source_url/official_publisher/official_host/(version または last_updated)/latest_checked_at を保持し、source_url の host が宣言済み official_host と一致することを検証する決定論ゲート (goal-spec C5 の形式・全件・host 一致検査)。
# inputs:
#   - argv: --targets FILE --references FILE
# outputs:
#   - stdout: OK summary
#   - stderr: violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""取得対象一覧と fetched-references.json の出典記録を機械検証する。

内容が現行最新版かの意味判定は C08 (doc-freshness-auditor) が公式サイトを再確認して担う。
本 script は形式・全件対応・host 一致のみを決定論検証する。任意の --state (spec-state.json) を
渡すと、user_decision で採択済みの decision があるのに targets が空という drift
(「targets 空∧references 空 → OK」の vacuous-green) を warning surface する (exit は不変)。

targets ファイルの期待形状:
{"targets": [{"target_id": "react", ...}, {"target_id": "postgres", ...}]}
  または {"targets": ["react", "postgres"]}   # 文字列 id の配列でも可

references ファイル (fetched-references.json) の期待形状:
{"references": [
  {"target_id": "react",
   "retrieved_at": "2026-07-11T00:00:00Z",
   "source_url": "https://react.dev/reference/react",
   "official_publisher": "Meta",
   "official_host": "react.dev",
   "version": "19.0",                # version または last_updated のいずれか必須
   "last_updated": "2026-06-01",
   "latest_checked_at": "2026-07-11T00:00:00Z",
   "summary": "..."}
]}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_FIELDS = (
    "target_id",
    "retrieved_at",
    "source_url",
    "official_publisher",
    "official_host",
    "latest_checked_at",
)


def _target_ids(data: dict) -> list[str]:
    raw = data.get("targets", [])
    ids: list[str] = []
    for t in raw:
        if isinstance(t, str):
            ids.append(t)
        elif isinstance(t, dict) and t.get("target_id"):
            ids.append(t["target_id"])
    return ids


def _norm_host(host: str) -> str:
    # 先頭が "www." のときだけ除去する。lstrip("www.") は文字集合 {w,.} の先頭除去で
    # `web.dev` -> `eb.dev` のように別 host を潰すため removeprefix を使う (F6)。
    return host.lower().removeprefix("www.") if host else ""


def _adopted_decision_ids(state_data: dict) -> list[str]:
    """spec-state の decisions[] から user_decision で採択済みの decision id を返す。

    採択済み技術は出典取得対象 (targets) の源泉であり、これが空でないのに targets が空なら
    「targets 空∧references 空 → OK」の vacuous-green を疑える (F3 の決定論可能な部分)。
    """
    decisions = state_data.get("decisions")
    if not isinstance(decisions, list):
        return []
    return [
        d.get("id")
        for d in decisions
        if isinstance(d, dict) and isinstance(d.get("user_decision"), dict)
    ]


def state_target_warnings(targets_data: dict, state_data: dict) -> list[str]:
    """採択技術があるのに targets が空という drift を surface する (F3・warning surface)。

    exit は変えない (既定の緑を壊さないため surface のみ)。決定論可能な範囲=user_decision で
    採択済みの decision が存在するのに取得対象が未登録、に限定する。
    """
    adopted = _adopted_decision_ids(state_data)
    if adopted and not _target_ids(targets_data):
        return [
            f"採択済み decision {adopted} が存在するが targets が空 "
            "(採択技術の出典取得対象が未登録・vacuous-green の疑い)"
        ]
    return []


def validate(targets_data: dict, refs_data: dict) -> list[str]:
    findings: list[str] = []

    target_ids = _target_ids(targets_data)

    refs = refs_data.get("references")
    if not isinstance(refs, list):
        findings.append("references: 配列でない")
        refs = []

    # 出典対象なし = targets 空 かつ references 空 → OK (exit0)。取得対象が 1 件も無い
    # 正当な状態 (外部技術を使わない / 未取得段階) でコンパイル動線を詰まらせない (F2)。
    # ※ targets 空だが references 非空 (orphan) / targets 非空だが references 欠落 は
    #   下の分岐で従来どおり違反として検出する。
    if not target_ids and not refs and not findings:
        return []

    if not target_ids:
        findings.append("targets: 対象 target_id が空 (取得対象一覧が無い)")

    by_id: dict[str, dict] = {}
    for i, ref in enumerate(refs):
        if not isinstance(ref, dict):
            findings.append(f"references[{i}]: オブジェクトでない")
            continue
        tid = ref.get("target_id")
        if not tid:
            findings.append(f"references[{i}]: target_id 欠落")
            continue
        if tid in by_id:
            findings.append(f"references: target_id={tid!r} が重複")
        by_id[tid] = ref

        # 必須フィールド
        for field in REQUIRED_FIELDS:
            if not ref.get(field):
                findings.append(f"references[{tid}]: 必須フィールド {field} が空/欠落")
        # version または last_updated のいずれか
        if not (ref.get("version") or ref.get("last_updated")):
            findings.append(
                f"references[{tid}]: version と last_updated の両方が空 (いずれか必須)"
            )
        # source_url host が official_host と一致
        src = ref.get("source_url")
        host = ref.get("official_host")
        if src and host:
            parsed_host = _norm_host(urlparse(src).netloc)
            if not parsed_host:
                findings.append(f"references[{tid}]: source_url={src!r} から host を解決できない")
            elif _norm_host(host) != parsed_host:
                findings.append(
                    f"references[{tid}]: source_url host={parsed_host!r} が official_host={host!r} と不一致"
                )

    # 全件対応 (欠落 0)
    missing = [t for t in target_ids if t not in by_id]
    if missing:
        findings.append(f"対象 target_id の参照欠落: {missing}")

    return findings


def _load(path_str: str, label: str) -> tuple[dict | None, int]:
    path = Path(path_str)
    if not path.is_file():
        print(f"{label} ファイルが存在しない: {path_str}", file=sys.stderr)
        return None, 2
    try:
        return json.loads(path.read_text(encoding="utf-8")), 0
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"{label} ファイルの JSON parse 失敗: {exc}", file=sys.stderr)
        return None, 2


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="出典記録の決定論検証 (goal-spec C5)")
    ap.add_argument("--targets", required=True, help="取得対象一覧 JSON のパス")
    ap.add_argument("--references", required=True, help="fetched-references.json のパス")
    ap.add_argument(
        "--state",
        help="spec-state.json (任意)。採択済み decision があるのに targets 空の drift を warning surface (F3)",
    )
    args = ap.parse_args(argv)

    targets_data, rc = _load(args.targets, "targets")
    if rc:
        return rc
    refs_data, rc = _load(args.references, "references")
    if rc:
        return rc

    if args.state:
        state_data, rc = _load(args.state, "state")
        if rc:
            return rc
        for warning in state_target_warnings(targets_data, state_data):
            print(f"WARNING: {warning}", file=sys.stderr)

    findings = validate(targets_data, refs_data)
    if findings:
        for f in findings:
            print(f"VIOLATION: {f}", file=sys.stderr)
        print(f"FAIL: {len(findings)} 件の出典記録違反", file=sys.stderr)
        return 1
    print("OK: 出典記録が全件対応・必須フィールド充足・公式 host 一致を満たす")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
