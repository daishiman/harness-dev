#!/usr/bin/env python3
# /// script
# name: mfk_verdict_export
# purpose: reconcile() の全 rows(GAP/SUPPRESS 含む)+orphans を MF実績 carrier 込みで
#          curr/prev-verdicts JSON へ無損失に直列化する決定論 producer (要因C2 構造的主因の根治)。
# inputs:
#   - export_curr_prev(): sheet_rows + 当月/先月 mf_raw({customers:...}) + 対象月YYMM
#   - serialize_verdicts(): reconcile() の返り値 {rows, orphans, target_ym}
# outputs:
#   - curr-verdicts.json / prev-verdicts.json ({target_month, rows:[...], orphans:[...]})
#     各 row は actual_amount/reliable_issued/supply_state/canceled_at carrier を保持
# contexts: [C]
# network: false
# write-scope: none   # API GET は R1 が担い、本 module は fetched データの純変換のみ
# dependencies: [mfk_reconcile, sheet_to_master, mfk_period_report]
# requires-python: ">=3.11"
# ///
"""curr/prev-verdicts を吐く決定論 producer (要因C2・構造的主因の第一級根治)。

## なぜ必要か (curr=None 症状の真因)
skills/run-mf-invoice-report/prompts/R1-collect.md の LLM 手動直列化が発行済み社の当月行を
落としていた(実レポート DB で 2nd Community/HOSONO=今月金額 null・「今月行なし(curr=None)」
だが忠実 reconcile では MATCH_MONTHLY 50000/210000/70000)。PR#85 の下流修正(C03/C04/reconcile)は
全て R1 の下流ゆえ R1 が落とす限り直らない=「前回直したのに直らない」の真因。

## 何をするか
lib/mfk_reconcile.reconcile()(C01 収集拡張・C04 分類是正が適用済)を当月/先月で実行し、
classify() が全 contract へ状態問わず1行返す既存性質を利用して **rows 全件(GAP/SUPPRESS 含む)+
orphans** を carrier(actual_amount/reliable_issued/supply_state/canceled_at)込みで無損失に
直列化する。contract 由来の行は必ず出るため curr=None は構造的に起きない(fidelity plan の
open_issue GAP-R1-COLLECT-CURR-PRESENT を副次効果で根治)。MF実績はあるがマスタ未登録の請求は
orphans(要マスタ登録)へ分離し、curr=None ではなく可視の逆方向行として保持する。

## 設計上の不変則
- **再照合しない**: 突合・分類は lib/mfk_reconcile が SSOT。本 module は reconcile() を呼んで
  その出力を直列化するだけで、normalize/find_mf_match/classify を再実装しない
  (guard-mfk-no-reinvent の allowlist に mfk_verdict_export.py を登録済み・関数名は
  serialize_verdicts/export_curr_prev で classify/compare/period_diff 語幹を避ける)。
- **evidence 据え置き**: find_mf_match の evidence は書き換えず、そのまま直列化する(DB2 温存境界)。
- **carrier fail-closed**: 直列化前に全 row の carrier キー存在を検証し、欠落があれば exit 1
  (schema 違反)。過少報告=真の月次漏れを隠す方向の退行を機械的に止める。
- **network なし**: MF API の GET は R1(mfk_api 経由)が担い、本 module は fetched 済みの
  mf_raw / sheet_rows を JSON で受ける純変換器(API GET 専用ポリシー C8 を割らない)。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..", "lib")
for _p in (_LIB, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mfk_reconcile as R  # noqa: E402
import sheet_to_master  # noqa: E402
from mfk_period_report import _prev_month_ym  # noqa: E402  (月計算 SSOT を再利用)

# 全 row が保持すべき MF実績 carrier(C05 mfk_actuals が classify 経由で焼く)。
# category_confirmed: reliable_issued が category 確定一致由来か (True) / category-agnostic fallback の
# 非確定一致か (False)。消費側が権威判定 (要対応☐の上書き) から fallback 一致を除外する安全弁。
CARRIER_KEYS = ("actual_amount", "reliable_issued", "supply_state", "canceled_at",
                "category_confirmed")


def _orphan_to_row(orphan):
    """逆方向 orphan(MF実績ありマスタ未登録)を period_report が読める row 形へ写像する。

    orphan は active 供給の集約(detect_orphans は services のみ集計)なので carrier は
    reliable_issued=True・supply_state=active・actual_amount=集約額。customer←cust / product←desc。
    元フィールドも残し無損失にする(要マスタ登録の候補提示に MF顧客ID/services を使う)。
    """
    row = dict(orphan)
    row.setdefault("customer", orphan.get("cust"))
    row.setdefault("product", orphan.get("desc"))
    row["actual_amount"] = orphan.get("amount")
    row["reliable_issued"] = True
    row["supply_state"] = R.mfk_actuals.SUPPLY_ACTIVE
    row.setdefault("canceled_at", None)
    row.setdefault("category_confirmed", True)  # orphan=MF実績集約・category 制約なし=presence 権威
    return row


def serialize_verdicts(recon):
    """reconcile() 返り値を {target_month, rows, orphans} の直列化ドキュメントへ変換する。

    rows は classify() 出力(全 contract 1 行・carrier 焼き込み済み)をそのまま無損失に載せる。
    orphans は _orphan_to_row で period_report 読み取り可能な形へ写像して併載する(curr=None でなく
    可視の要マスタ登録行として保持)。
    """
    rows = [dict(r) for r in recon.get("rows", [])]
    # 安全弁 carrier の後方互換 backfill: category_confirmed 未設定の行 (legacy/外部入力/find_mf_match
    # 未経由) は presence 権威扱いの既定 True を焼く (絶対に権威剥奪の誤爆をしない安全側)。
    for r in rows:
        r.setdefault("category_confirmed", True)
    orphans = [_orphan_to_row(o) for o in recon.get("orphans", [])]
    return {
        "target_month": recon.get("target_ym"),
        "generated_by": "mfk_verdict_export",
        "rows": rows,
        "orphans": orphans,
        "summary": recon.get("summary", {}),
    }


def validate_carrier(doc):
    """直列化ドキュメントの全 row が carrier + 識別子 + verdict を持つか検証する(fail-closed)。

    返り値: 違反メッセージの list(空=OK)。row 脱落や carrier 欠落を機械検知し、
    curr=None / 過少報告方向の退行を止める。
    """
    violations = []
    for i, row in enumerate(doc.get("rows", [])):
        for k in CARRIER_KEYS:
            if k not in row:
                violations.append(f"rows[{i}] carrier '{k}' 欠落 (verdict={row.get('verdict')})")
        if not row.get("verdict"):
            violations.append(f"rows[{i}] verdict 欠落")
        if not (row.get("customer") or row.get("取引先")):
            violations.append(f"rows[{i}] customer/取引先 欠落")
    return violations


def export_curr_prev(sheet_rows, mf_curr_raw, mf_prev_raw, target_ym):
    """当月/先月の mf_raw と契約シート行から curr/prev-verdicts ドキュメント対を作る決定論変換。

    - build_mf_index(mf_raw) で当月/先月の索引を作り(active/inactive 分別 SSOT を再利用)、
    - build_contracts(sheet_rows, mf_index=mf_raw, ...) で契約を組み(MF顧客ID 解決=C02 を内包)、
    - reconcile() を各月で実行して全 rows+orphans を serialize_verdicts で直列化する。
    先月の対象月は _prev_month_ym(target_ym)(月計算 SSOT の再利用)で導出する。
    """
    prev_ym = _prev_month_ym(target_ym)
    if not prev_ym:
        raise ValueError(f"target_ym が YYMM 不正: {target_ym!r}")

    curr_idx = R.build_mf_index(mf_curr_raw)
    prev_idx = R.build_mf_index(mf_prev_raw)
    curr_contracts = sheet_to_master.build_contracts(sheet_rows, mf_index=mf_curr_raw,
                                                     target_ym=target_ym)
    prev_contracts = sheet_to_master.build_contracts(sheet_rows, mf_index=mf_prev_raw,
                                                     target_ym=prev_ym)
    curr_doc = serialize_verdicts(R.reconcile(curr_contracts, curr_idx, target_ym))
    prev_doc = serialize_verdicts(R.reconcile(prev_contracts, prev_idx, prev_ym))
    return curr_doc, prev_doc


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rows_from(payload):
    """sheet 入力を list 形へ正規化する(list そのもの or {"rows":[...]} / {"results":[...]})。"""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in ("rows", "results", "records", "items"):
            if isinstance(payload.get(k), list):
                return payload[k]
    return []


def _write_json(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="curr/prev-verdicts 決定論 producer (C05・reconcile 全行 carrier 直列化)")
    p.add_argument("--sheet", required=True, help="請求確認シート行 JSON (list or {rows:[...]})")
    p.add_argument("--mf-curr", required=True, help="当月 collect_mf raw JSON ({customers:...})")
    p.add_argument("--mf-prev", required=True, help="先月 collect_mf raw JSON")
    p.add_argument("--target", required=True, help="対象月 YYMM (今月)")
    p.add_argument("--out-curr", required=True, help="curr-verdicts 出力パス")
    p.add_argument("--out-prev", required=True, help="prev-verdicts 出力パス")
    args = p.parse_args(argv)

    try:
        sheet_rows = _rows_from(_load_json(args.sheet))
        mf_curr = _load_json(args.mf_curr)
        mf_prev = _load_json(args.mf_prev)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"[verdict-export] 入力読込エラー: {e}\n")
        return 2

    try:
        curr_doc, prev_doc = export_curr_prev(sheet_rows, mf_curr, mf_prev, args.target)
    except ValueError as e:
        sys.stderr.write(f"[verdict-export] {e}\n")
        return 2

    violations = validate_carrier(curr_doc) + validate_carrier(prev_doc)
    if violations:
        for v in violations[:20]:
            sys.stderr.write(f"[verdict-export] schema 違反: {v}\n")
        sys.stderr.write(f"[verdict-export] carrier/row 検証違反 {len(violations)}件 (fail-closed)\n")
        return 1

    _write_json(args.out_curr, curr_doc)
    _write_json(args.out_prev, prev_doc)
    print(f"[verdict-export] 今月={args.target} rows={len(curr_doc['rows'])} "
          f"orphans={len(curr_doc['orphans'])} / 先月={prev_doc['target_month']} "
          f"rows={len(prev_doc['rows'])} orphans={len(prev_doc['orphans'])} "
          f"(全行 carrier 直列化・curr=None なし)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
