#!/usr/bin/env python3
# /// script
# name: mfk_fetch_audit
# purpose: MF掛け払い read-only fetch の最新性・完全性を機械検証する監査器 (network=false・fail-closed)。
# inputs:
#   - --fetch-trace FILE : R1/reconcile_invoices が記録した pagination trace JSON
#   - --target YYMM      : 監査基準の当月 (省略時は trace の target_month)
#   - --out FILE         : fidelity report の出力先 (省略時は stdout)
# outputs:
#   - fidelity report JSON (C03 --fidelity-report が読む)
#   - exit: 0=OK / 1=当月or先月 fidelity 違反 (fail-closed) / 3=lookback 部分欠損 (要確認降格) / 2=入力不正
# contexts: [C, E]
# network: false
# write-scope: eval-log
# dependencies: []
# requires-python: ">=3.11"
# ///
"""fetch fidelity 監査器 (C06)。

『最新を漏れなく取れているか』を pagination 完全性 / total 件数突合 / issue_date 範囲 / stale の観点で
機械検証する。**network=false**: 自力で API を叩かず、read-only fetch 経路 (lib/mfk_api.iter_all の
trace_sink / R1 collect) が記録した pagination trace を検証するだけ (取得と監査を分離)。

判定と exit の契約 (C03 mfk_period_report.py が --fidelity-report で消費):
  - **trace 完全不在** (curr/prev/lookback のどれ 1 つも trace が無い) = legacy iter_all の
    pagination.total 破棄残置を通さないため fidelity violation → exit1 (fail-closed)。
  - **当月 (curr) / 先月 (prev) の pagination NG・count 不一致・issue_date 範囲 NG・trace 欠落** →
    exit1 (fail-closed=漏れ確認処理を実行しない)。両月の完全性が正しい前月↔今月比較の前提。
  - **lookback (12ヶ月ルックバック) の一部月が欠落/不完全** かつ当月/先月は OK → exit3
    (fail-closed 全停止でなく該当行を『要確認』へ降格する=部分欠損の中間状態)。
  - 全 OK → exit0。

fetch trace の想定形 (site ごとの pagination trace 一覧を月コンテキストで束ねたもの):
  {
    "target_month": "2606",
    "curr":   [ {site, path, page_index, has_next, end, total, items_count, params}, ... ],
    "prev":   [ ... ],
    "lookback": { "2505": [ ... ], "2506": [ ... ], ... }   # per-month・差分該当取引先のみ
  }

additive (要因C1・任意): 上記に "billings": {"curr": [...], "prev": [...],
"lookback": {YYMM: [...]}} (reconcile_invoices.collect_mf の返り値 "billings" を月コンテキスト
で束ねた生 billing dict 一覧) を含めると、fidelity report に billing.status 別件数の内訳
(billing_status_summary) を開示する。不在でも既存ゲート (pagination/total/issue_date/stale) は
一切影響を受けない (純粋な additive disclosure)。
"""
import argparse
import json
import re
import sys

import mfk_collect_status


def _ym_window(month_ym):
    """YYMM → over-fetch issue_date 窓 (first, last) = [当月初 .. 翌月末]。

    reconcile_invoices._month_range_iso と同じ窓 (取引日基準の当月分は翌月月初発行のため翌月末まで
    over-fetch する)。C06 は params.issue_date_from/to がこの窓と一致するかで stale/範囲 NG を検出する。
    """
    m = re.fullmatch(r"(\d{2})(\d{2})", str(month_ym or ""))
    if not m:
        return None, None
    year = 2000 + int(m.group(1))
    month = int(m.group(2))
    first = f"{year:04d}-{month:02d}-01"
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    # 翌月末日 (28-31)。うるう年は 2 月のみ影響し、_ym_window は monthrange 不要な近似で十分な
    # 「翌月・末日」判定に issue_date_to の year-month 一致を主軸にする (末日 exact は要求しない)。
    return first, f"{ny:04d}-{nm:02d}"


def _paginate_ok(pages):
    """pagination 完全性: has_next=true のページは end(次カーソル)が非空、かつ最終ページで打切っている。

    - has_next=true なのに end 空 = 部分取得のまま停止した痕跡 → NG。
    - 記録された最後のページが has_next=true のまま = ページングが最後まで回っていない (途中で
      trace 記録が切れた/打ち切られた) → NG。正常系は最終ページの has_next=false で終端する。
    """
    if not pages:
        return False, "trace ページが 0 件 (fetch 記録なし)"
    for p in pages:
        if p.get("has_next") and not p.get("end"):
            return False, f"has_next=true だが end(次カーソル)が空 (page {p.get('page_index')})"
    if pages[-1].get("has_next"):
        return False, "最終記録ページが has_next=true (ページングが終端していない=途中打切り)"
    return True, ""


def _totals_ok(pages):
    """total 件数突合: pagination.total を持つ site は Σitems_count == total (取りこぼしなし)。

    site ごとに束ね、total が None のページしか無い site はスキップ (total 非提供 API は突合対象外)。
    total を提供する site で合計が一致しなければ NG (途中欠落 / 二重取得の兆候)。
    """
    by_site = {}
    for p in pages:
        by_site.setdefault(p.get("site") or p.get("path"), []).append(p)
    for site, ps in by_site.items():
        totals = [p.get("total") for p in ps if isinstance(p.get("total"), int)]
        if not totals:
            continue
        declared = max(totals)  # 同一 site の全ページは同じ total を報告する想定。安全側に max。
        fetched = sum(p.get("items_count") or 0 for p in ps)
        if fetched != declared:
            return False, f"site={site} total={declared} だが取得 {fetched} 件 (件数不一致)"
    return True, ""


def _is_billings(p):
    return p.get("site") == "billings" or "billings" in str(p.get("path") or "")


def _sites_present_ok(pages):
    """billings site が trace に含まれるか (当月抽出の entry point=部分 trace 検出)。

    billings site が皆無 = fetch が実行されていない/site を trace し忘れた部分 trace → fail-closed。
    当月に qualified billing が 0 件でも R1 は billings GET を 1 回発行し (空 items の) trace を残す
    ため、billings site は正常系で必ず存在する。LLM が transactions だけ記録し billings を落とす等の
    部分欠落を『最新性 OK』で素通しさせない (トリム trace を通さない)。
    """
    if not any(_is_billings(p) for p in pages):
        return False, "billings site の trace が無い (fetch 未実行/部分 trace=最新性を保証できない)"
    return True, ""


def _issue_date_ok(pages, month_ym):
    """issue_date 範囲 / stale: billings site の issue_date 窓が監査対象月の over-fetch 窓と一致する。

    billings(/billings/qualified) は issue_date 窓で当月を絞る唯一の site。over-fetch 窓は
    [当月初 (YYYY-MM-01) .. 翌月末] (取引日基準の当月分は翌月月初発行のため翌月末まで広げる)。
      - issue_date_from が当月初でなければ別月取得 (stale) か下限ずれ → NG。
      - issue_date_to の year-month が翌月でなければ上限を当月内へ切り詰めた窓ずれ → NG (当月取引の
        翌月発行分の取りこぼし=本改善が最も恐れる症状⑤の再生産を防ぐ)。
    transactions/customer_name は issue_date 窓を持たない site なので対象外。
    """
    first, last_ym = _ym_window(month_ym)
    if first is None:
        return False, f"target 月 {month_ym} が YYMM 不正"
    billing_pages = [p for p in pages if _is_billings(p)]
    if not billing_pages:
        return True, ""  # billings 不在は _sites_present_ok が fail-closed 扱いにする (ここでは判定しない)
    for p in billing_pages:
        params = p.get("params") or {}
        got_from = str(params.get("issue_date_from") or "")
        got_to = str(params.get("issue_date_to") or "")
        if got_from != first:
            return False, (f"billings issue_date_from={got_from or '空'} が対象月 {month_ym} の当月初 "
                           f"{first} と不一致 (stale/下限ずれ)")
        if got_to[:7] != last_ym:
            return False, (f"billings issue_date_to={got_to or '空'} の year-month が over-fetch 上限 "
                           f"{last_ym} (翌月) と不一致 (窓上限ずれ=当月取引の翌月発行分の取りこぼし懸念)")
    return True, ""


def audit_group(pages, month_ym):
    """1 グループ (当月 / 先月 / lookback の 1 月) の trace を検証し {ok, violations} を返す。"""
    pages = pages or []
    violations = []
    if not pages:
        return {"ok": False, "violations": ["trace 完全不在 (fetch 記録なし=legacy 非trace経路)"]}
    for check in (_sites_present_ok(pages), _paginate_ok(pages),
                  _totals_ok(pages), _issue_date_ok(pages, month_ym)):
        ok, msg = check
        if not ok:
            violations.append(msg)
    return {"ok": not violations, "violations": violations}


def _prev_ym(month_ym):
    m = re.fullmatch(r"(\d{2})(\d{2})", str(month_ym or ""))
    if not m:
        return None
    yy, mm = int(m.group(1)), int(m.group(2))
    yy, mm = (yy - 1, 12) if mm == 1 else (yy, mm - 1)
    return f"{yy:02d}{mm:02d}"


def _billing_status_summary(trace):
    """trace の additive 'billings' (curr/prev/lookback へ束ねた収集 billing 生配列) から
    mfk_collect_status.summarize_billing_statuses で status 別件数をグループごとに集計する
    (要因C1 収集是正の可視化・開示専用。C11: 既存 fail-closed ゲートには一切影響しない)。

    'billings' キーが無い/shape 不正なら空 dict を返す (fetch trace は元々このキーを持たない
    ため、既存全 trace / 既存テストは常に {} = 後退させない純粋な additive disclosure)。
    """
    billings = trace.get("billings")
    if not isinstance(billings, dict):
        return {}
    out = {}
    for group in ("curr", "prev"):
        items = billings.get(group)
        if isinstance(items, list):
            out[group] = mfk_collect_status.summarize_billing_statuses(items)
    lookback = billings.get("lookback")
    if isinstance(lookback, dict):
        out["lookback"] = {
            ym: mfk_collect_status.summarize_billing_statuses(items)
            for ym, items in lookback.items() if isinstance(items, list)
        }
    return out


def audit_fetch_trace(trace, target_month=None):
    """fetch trace 全体を監査し fidelity report + exit_code を返す (純ロジック・network なし)。

    exit_code: 0=OK / 1=当月or先月 fidelity 違反 or 完全不在 (fail-closed) / 3=lookback 部分欠損。
    """
    trace = trace or {}
    billing_status_summary = _billing_status_summary(trace)
    target_month = target_month or trace.get("target_month")
    prev_month = _prev_ym(target_month)

    # 型検証 (LLM 生成 trace の shape ブレを fail-closed で弾く=crash 防止・S-04)。curr/prev は
    # page dict の list、lookback は {YYMM: [page...]}、expected_lookback_months は YYMM の list。
    def _as_pages(x):
        return x if isinstance(x, list) else None
    curr_pages = _as_pages(trace.get("curr") or [])
    prev_pages = _as_pages(trace.get("prev") or [])
    lookback = trace.get("lookback") or {}
    shape_bad = curr_pages is None or prev_pages is None or not isinstance(lookback, dict) \
        or any(not isinstance(v, list) for v in lookback.values())
    if shape_bad:
        return {
            "target_month": target_month,
            "curr": {"ok": False, "violations": ["fetch_trace の shape 不正 (curr/prev は list・lookback は {YYMM:[...]})"]},
            "prev": {"ok": False, "violations": ["fetch_trace の shape 不正"]},
            "lookback": {"complete": False, "partial": False, "missing_months": [],
                         "ok_months": [], "ng_months": []},
            "overall": "trace_malformed",
            "exit_code": 1,
            "billing_status_summary": billing_status_summary,
        }

    # trace 完全不在 (どのグループにも 1 件も trace が無い) = legacy 非trace経路 → fail-closed。
    if not curr_pages and not prev_pages and not lookback:
        return {
            "target_month": target_month,
            "curr": {"ok": False, "violations": ["trace 完全不在"]},
            "prev": {"ok": False, "violations": ["trace 完全不在"]},
            "lookback": {"complete": False, "partial": False, "missing_months": [],
                         "ok_months": [], "ng_months": []},
            "overall": "trace_absent",
            "exit_code": 1,
            "billing_status_summary": billing_status_summary,
        }

    curr = audit_group(curr_pages, target_month)
    prev = audit_group(prev_pages, prev_month)

    lb_ok, lb_ng = [], []
    for month, pages in sorted(lookback.items()):
        g = audit_group(pages, month)
        (lb_ok if g["ok"] else lb_ng).append(month)
    # missing_months: R1 が宣言した期待 lookback 月集合 (expected_lookback_months) のうち trace に
    # 存在しない月 = そもそも fetch していない silent omission。present 月だけ巡回する検査は「取って
    # いない月」を原理的に見逃すため、期待集合との差で欠落を顕在化させる (未宣言なら [] のまま=
    # R1 が期待集合を宣言する責務。宣言なしでも per-customer の D1 裏取り不在が安全網)。
    expected = trace.get("expected_lookback_months")
    lb_missing = ([m for m in expected if m not in lookback]
                  if isinstance(expected, list) else [])

    lb_incomplete = bool(lb_ng) or bool(lb_missing)
    lb_report = {
        "complete": not lb_incomplete,
        "partial": lb_incomplete,
        "missing_months": lb_missing,
        "ok_months": lb_ok,
        "ng_months": lb_ng,
        "affected_months": sorted(set(lb_ng) | set(lb_missing)),
    }

    if not curr["ok"] or not prev["ok"]:
        overall, exit_code = "curr_fail", 1
    elif lb_incomplete:
        overall, exit_code = "lookback_partial", 3
    else:
        overall, exit_code = "ok", 0

    return {
        "target_month": target_month,
        "curr": curr,
        "prev": prev,
        "lookback": lb_report,
        "overall": overall,
        "exit_code": exit_code,
        "billing_status_summary": billing_status_summary,
    }


def main(argv=None):
    p = argparse.ArgumentParser(
        description="MF fetch fidelity 監査器 (network=false・pagination/total/issue_date/stale)")
    p.add_argument("--fetch-trace", dest="fetch_trace", required=True,
                   help="R1/reconcile が記録した pagination trace JSON")
    p.add_argument("--target", help="対象月 YYMM (省略時は trace の target_month)")
    p.add_argument("--out", help="fidelity report の出力先 (省略時は stdout)")
    a = p.parse_args(argv)

    try:
        with open(a.fetch_trace, encoding="utf-8") as fh:
            trace = json.load(fh)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[fetch-audit] fetch trace の読込に失敗 (fail-closed): {e}\n")
        return 2

    report = audit_fetch_trace(trace, a.target)
    out = json.dumps(report, ensure_ascii=False, indent=2)
    if a.out:
        try:
            with open(a.out, "w", encoding="utf-8") as fh:
                fh.write(out + "\n")
        except OSError as e:
            sys.stderr.write(f"[fetch-audit] fidelity report の書込に失敗: {e}\n")
            return 2
    else:
        print(out)

    ec = report["exit_code"]
    if ec == 1:
        sys.stderr.write("[fetch-audit] ⛔ 当月/先月 fetch fidelity 違反 (fail-closed)。"
                         "漏れ確認処理を実行しないでください。\n")
    elif ec == 3:
        sys.stderr.write("[fetch-audit] ⚠️ lookback 部分欠損。該当取引先の判定は『要確認』へ降格されます "
                         f"(ng_months={report['lookback']['ng_months']})。\n")
    return ec


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
