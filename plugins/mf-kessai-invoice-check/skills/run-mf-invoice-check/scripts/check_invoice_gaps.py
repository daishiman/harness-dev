#!/usr/bin/env python3
"""月次発行漏れチェック実行スクリプト。

  --collect  : 前月/今月の取引月ベースの発行済み請求を取得→差集合→商品名/金額/企業名突合→未検証候補JSON出力
  --finalize : verify(subagent)が確定した結果を確定リストへ昇格 (誤検出 customer_id を除外)
  --sink     : 確定リストを Notion DB に冪等 upsert (確定リスト不在なら fail-closed で停止)

月は --month YYYY-MM (既定: 実行日の年月)。比較する前月はその1つ前を自動算出。
対象年月(period_ym)ラベルは今月と一致させる。月帰属は transaction.date (取引日) 基準。
例: 2026-06-30 取引・2026-07-01 発行の請求は対象年月=2026-06。
全て GET (参照専用)。MF APIへの POST/PATCH/DELETE は PreToolUse hook で遮断される。

出力先は install パス非依存に解決する (F2 ポータビリティ)。lib import に使う _PLUGIN_ROOT は
__file__ 相対なので任意 install パスで安定するが、成果物(候補/確定 JSON)の置き場は repo 構造に
依存させず、base_url の env-first 思想と同型の優先順位 env > Claude project > CWD で解決する。
"""
import argparse
import calendar
import datetime
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))
from mfk_api import get, iter_all, load_config  # noqa: E402
from mfk_invoice_diff import (  # noqa: E402,F401
    amount_changed,
    billing_lifecycle,  # 年間契約抑制の判定核 (suppress_annual_period_gaps が内部利用)。再エクスポート用に保持
    detect_gaps,
    suppress_annual_period_gaps,
)
import notion_invoice_sink  # noqa: E402

GAP_VERDICT = "発行漏れ候補"
_VERDICT_ENUM = ("発行漏れ候補", "継続発行", "今月新規")
_ALLOWED_ROW_KEYS = {
    "customer_id", "period_ym", "company_name", "verdict", "product_name",
    "prev_amount", "curr_amount", "issue_date", "updated_at",
}
_STRING_FIELDS = {"customer_id", "period_ym", "company_name", "verdict", "product_name"}
_NULLABLE_STRING_FIELDS = {"issue_date", "updated_at"}
_NULLABLE_INT_FIELDS = {"prev_amount", "curr_amount"}


def eval_log_dir():
    """成果物の出力ディレクトリを install パス非依存に解決する。

    優先順位 (base_url の env-first 思想を出力先へ横展開):
      1. MFK_OUTPUT_DIR (env, 明示上書き)
      2. CLAUDE_PROJECT_DIR (Claude Code 注入の project root)
      3. os.getcwd() (実行 CWD。prompts/agent の裸相対 eval-log/ と基準一致)
    """
    base = os.environ.get("MFK_OUTPUT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.join(base, "eval-log")


def candidates_path():
    """collect が出力する未検証候補 JSON のパス。"""
    return os.path.join(eval_log_dir(), "mfk-gap-candidates.json")


def verified_path():
    """finalize が出力し sink が消費する確定 JSON のパス (二段確認の物理境界)。"""
    return os.path.join(eval_log_dir(), "mfk-gap-verified.json")


def _same_path(a, b):
    return os.path.abspath(a) == os.path.abspath(b)


def validate_rows(rows):
    """sink/finalize 入口の schema 検証 (F4)。違反メッセージのリストを返す (空なら OK)。

    invoice-gap-result.schema.json の必須制約 (customer_id 非空 / period_ym=YYYY-MM /
    verdict enum)、additionalProperties:false、主要型を冪等キー破綻前に機械強制する。
    """
    errs = []
    if not isinstance(rows, list):
        return ["入力が配列でない"]
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            errs.append(f"[{i}] row が object でない: {type(r).__name__}")
            continue
        extra = sorted(set(r) - _ALLOWED_ROW_KEYS)
        if extra:
            errs.append(f"[{i}] schema 外のキー: {extra}")
        cid = r.get("customer_id")
        ym = r.get("period_ym")
        v = r.get("verdict")
        if not (isinstance(cid, str) and cid.strip()):
            errs.append(f"[{i}] customer_id が空/非文字列: {cid!r}")
        if not (isinstance(ym, str) and re.fullmatch(r"\d{4}-\d{2}", ym or "")):
            errs.append(f"[{i}] period_ym が YYYY-MM でない: {ym!r}")
        elif not valid_month(ym):
            errs.append(f"[{i}] period_ym が実在月でない: {ym!r}")
        if v not in _VERDICT_ENUM:
            errs.append(f"[{i}] verdict が enum 外: {v!r}")
        for key in _STRING_FIELDS:
            if key in r and not isinstance(r[key], str):
                errs.append(f"[{i}] {key} が string でない: {r[key]!r}")
        for key in _NULLABLE_STRING_FIELDS:
            if key in r and r[key] is not None and not isinstance(r[key], str):
                errs.append(f"[{i}] {key} が string/null でない: {r[key]!r}")
        for key in _NULLABLE_INT_FIELDS:
            if key in r and r[key] is not None and (
                not isinstance(r[key], int) or isinstance(r[key], bool)
            ):
                errs.append(f"[{i}] {key} が integer/null でない: {r[key]!r}")
        for key in ("company_name", "product_name", "prev_amount", "curr_amount"):
            if key not in r:
                errs.append(f"[{i}] 必須キー不足: {key}")
        if v == "発行漏れ候補":
            if not isinstance(r.get("prev_amount"), int) or isinstance(r.get("prev_amount"), bool):
                errs.append(f"[{i}] 発行漏れ候補の prev_amount は integer 必須: {r.get('prev_amount')!r}")
            if r.get("curr_amount") is not None:
                errs.append(f"[{i}] 発行漏れ候補の curr_amount は null 必須: {r.get('curr_amount')!r}")
        elif v == "継続発行":
            for key in ("prev_amount", "curr_amount"):
                if not isinstance(r.get(key), int) or isinstance(r.get(key), bool):
                    errs.append(f"[{i}] 継続発行の {key} は integer 必須: {r.get(key)!r}")
        elif v == "今月新規":
            if r.get("prev_amount") is not None:
                errs.append(f"[{i}] 今月新規の prev_amount は null 必須: {r.get('prev_amount')!r}")
            if not isinstance(r.get("curr_amount"), int) or isinstance(r.get("curr_amount"), bool):
                errs.append(f"[{i}] 今月新規の curr_amount は integer 必須: {r.get('curr_amount')!r}")
    return errs


def valid_month(ym):
    """YYYY-MM かつ 01〜12 の実在月なら True。"""
    if not isinstance(ym, str) or not re.fullmatch(r"\d{4}-\d{2}", ym):
        return False
    _year, month = map(int, ym.split("-"))
    return 1 <= month <= 12


def _reject_bad_month(label, ym):
    if not valid_month(ym):
        sys.stderr.write(f"[check] {label} が YYYY-MM 形式の実在月でない: {ym!r}\n")
        return True
    return False


def _row_periods(rows):
    return {r.get("period_ym") for r in rows}


def month_range(ym):
    y, m = map(int, ym.split("-"))
    last = calendar.monthrange(y, m)[1]
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"


def issue_fetch_range_for_transaction_month(ym):
    """取引月 ym 用の issue_date 取得窓。

    月帰属は transaction.date (取引日・月末締め) 基準。対象月取引分は翌月月初に発行される
    ため、/billings/qualified は対象月初〜翌月末で over-fetch し、後段で transaction.date に
    よって対象月だけへ絞る。
    """
    y, m = map(int, ym.split("-"))
    first = f"{y:04d}-{m:02d}-01"
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    nlast = calendar.monthrange(ny, nm)[1]
    return first, f"{ny:04d}-{nm:02d}-{nlast:02d}"


def _iso_to_month(iso_date):
    """ISO 日付 (YYYY-MM-DD / YYYY-MM) → YYYY-MM。空/不正は None。"""
    m = re.match(r"\s*(\d{4})-(\d{2})", str(iso_date or ""))
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _amount_to_int(v):
    try:
        return int(float(str(v).replace(",", "").replace("，", "")))
    except (TypeError, ValueError):
        return 0


def prev_month(ym):
    y, m = map(int, ym.split("-"))
    m -= 1
    if m == 0:
        y -= 1
        m = 12
    return f"{y:04d}-{m:02d}"


def default_target_month(today=None):
    """既定の対象月(今月) = 実行日の年月。

    `--month` 未指定時の既定。対象年月(period_ym)ラベルは今月と一致する。
    例: 2026-06-30 23:59 までは対象年月=2026-06、今月金額=2026-06、
    前月金額=2026-05。today を渡せば固定日付で単体テスト可能 (既定は実行日)。
    """
    today = today or datetime.date.today()
    return today.strftime("%Y-%m")


def fetch_issued(ym):
    """取引月 ym の発行済み billing を返す。

    API の一覧絞り込みは issue_date しかないため対象月初〜翌月末で over-fetch し、
    各 billing の /transactions を全ページ取得して transaction.date が ym の取引だけを残す。
    例: 2026-06 分は transaction.date=2026-06-30 を採用し、issue_date=2026-07-01 でも
    6月分として扱う。transaction.date 欠落時だけ transaction.issue_date → billing.issue_date
    へ縮退する。この場合のみ発行日基準となるため、当月取引でも date 欠落かつ翌月発行だと
    翌月へ帰属し当月集合から外れうる (縮退は取りこぼしを防ぐ向きとは限らない)。縮退が起きた
    件数は stderr に1行警告する (silent ではなく可視化。FAIL にはしない)。

    取消 (status=canceled) 取引は発行集合に計上しない (最小 correctness 修正)。canceled の
    transaction.amount は取消前金額を保持するため、status を無視すると取消前金額が継続発行/
    今月新規へ化けて差集合が崩れる。なお本スクリプト (簡易 gap-check) では新 verdict や Notion
    列は足さず canceled を発行集合から除くだけに留める。取消の可視化昇格 (要確認(取消)ラベル・
    取消日時列) は双方向照合の run-mf-invoice-reconcile 側で実装済みで、gap-check への展開は
    スコープ最小化のため別 PR へ defer する。
    """
    first, last = issue_fetch_range_for_transaction_month(ym)
    billings = iter_all("/billings/qualified", {
        "issue_date_from": first, "issue_date_to": last, "status": "invoice_issued",
    })
    out = []
    fallback_count = 0
    canceled_count = 0
    for b in billings:
        bid = b.get("id")
        total = 0
        has_target_transaction = False
        # /transactions は1 billing で 200 件を超えうるため iter_all で全ページ走査する
        # (単発取得だと 201 件目以降を黙って捨て、対象月取引がそこにある billing が脱落する)。
        txs = list(iter_all("/transactions", {"billing_id": bid})) if bid else []
        for t in txs:
            txn_month = _iso_to_month(t.get("date"))
            if txn_month is None:  # date 欠落 → 発行日基準へ縮退 (当月取引が翌月へ帰属しうる)
                fallback_count += 1
                txn_month = (_iso_to_month(t.get("issue_date"))
                             or _iso_to_month(b.get("issue_date")))
            if txn_month is not None and txn_month != ym:
                continue
            # 取消取引は有効発行に計上しない (取消前金額が継続発行/今月新規へ化けるのを防ぐ)。
            if str(t.get("status") or "").lower() == "canceled":
                canceled_count += 1
                continue
            has_target_transaction = True
            details = t.get("transaction_details") or []
            if details:
                total += sum(_amount_to_int(d.get("amount")) for d in details)
            else:
                total += _amount_to_int(t.get("amount") or b.get("amount"))
        if has_target_transaction:
            row = dict(b)
            row["amount"] = total
            out.append(row)
    if fallback_count:
        sys.stderr.write(
            f"[check] 警告: {ym} で transaction.date 欠落により発行日基準へ縮退した取引 "
            f"{fallback_count}件 (当月取引が翌月へ帰属し当月集合から外れる恐れ)。\n")
    if canceled_count:
        sys.stderr.write(
            f"[check] {ym} の取消 (canceled) 取引 {canceled_count}件 を発行集合から除外しました "
            "(取消前金額を継続発行/今月新規に計上しない)。\n")
    return out


def billings_by_customer(billings):
    out = {}
    for b in billings:
        out.setdefault(b["customer_id"], []).append(b)
    return out


def resolve_names(customer_ids):
    names = {}
    ids = list(customer_ids)
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        data = get("/customers", {"ids": chunk, "limit": 200})
        for c in data.get("items", []):
            names[c["id"]] = c.get("name", "")
    if ids and not names:  # 全件解決失敗 = パラメータ形式の疑い。空欄で黙って進めない
        sys.stderr.write(
            f"[check] 警告: 顧客ID {len(ids)}件に対し企業名が1件も解決できませんでした。"
            "/customers?ids= の形式を実APIで確認してください (このままだと企業名が空欄になります)。\n")
    elif ids:
        # A4-009: 部分名寄せ失敗 (一部 ID が /customers で解決できない) も件数付きで警告する。
        # 全件ゼロだけでなく「89件中3件が空欄」も運用者が気付けるようにし、silent な企業名欠落を防ぐ。
        missing = len(ids) - sum(1 for cid in ids if cid in names)
        if missing:
            sys.stderr.write(
                f"[check] 警告: 顧客ID {len(ids)}件中 {missing}件の企業名が解決できませんでした"
                " (該当顧客の企業名は空欄になります)。\n")
    return names


def detail_of(billing_id):
    """billing の商品名(先頭3明細)と更新日を返す。

    MF API に updated_at は存在しない (ref-mf-kessai-api 参照)。更新日は transactions.created_at の
    最新値で代替し、内部キー名 `updated_at` は『更新日列の値』の意味で用いる (取得元は created_at)。
    """
    if not billing_id:
        return {"product_name": "", "updated_at": None}
    data = get("/transactions", {"billing_id": billing_id, "limit": 5})
    descs, updated = [], None
    for t in data.get("items", []):
        ca = t.get("created_at")
        if ca and (updated is None or ca > updated):
            updated = ca
        for d in t.get("transaction_details", []):
            if d.get("description"):
                descs.append(d["description"])
    return {"product_name": " / ".join(descs[:3]), "updated_at": updated}


def detail_of_billings(billings):
    """同一顧客の複数 billing から商品名・更新日・発行日を集約する。"""
    product_names, updated, issue_date = [], None, None
    for b in billings:
        if b.get("issue_date") and (issue_date is None or b["issue_date"] > issue_date):
            issue_date = b["issue_date"]
        det = detail_of(b.get("id"))
        if det.get("product_name"):
            product_names.append(det["product_name"])
        if det.get("updated_at") and (updated is None or det["updated_at"] > updated):
            updated = det["updated_at"]
    # detail_of は各 billing の先頭3明細を返すため、顧客単位でも上限をかけて表示を肥大化させない。
    return {"product_name": " / ".join(product_names[:3]), "updated_at": updated,
            "issue_date": issue_date}


def _empty_detail():
    """detail_of をスキップする顧客(金額変動なし継続発行)の埋め値。

    /transactions を叩かないため product_name は空、updated_at(=transactions.created_at
    代替の更新日列)は None。金額のみ記録する。
    """
    return {"product_name": "", "updated_at": None, "issue_date": None}


def _latest_issue_date(billings):
    dates = [b.get("issue_date") for b in billings if b.get("issue_date")]
    return max(dates) if dates else None


def _load_initial_contract_months(db_id):
    """Notion から年間抑制用 {customer_id: 契約情報} を取得する (失敗は空 dict)。

    db_id 未設定や取得失敗時は空 dict を返し stderr に1行警告する。空 dict だと
    suppress_annual_period_gaps が全候補を fail-safe で残す (= 年間契約抑制をスキップし
    真の発行漏れを隠さない) ため、DB 未設定・Notion 不通でも collect は壊れない。
    """
    if not db_id:
        sys.stderr.write(
            "[check] 初回契約月を取得できず年間契約抑制をスキップ(全候補を発行漏れ候補として扱う)\n")
        return {}
    try:
        return notion_invoice_sink.fetch_initial_contract_months(db_id)
    except Exception as e:  # Notion 不通/権限/形式エラーでも collect 全体は止めない
        sys.stderr.write(
            "[check] 初回契約月を取得できず年間契約抑制をスキップ(全候補を発行漏れ候補として扱う)"
            f": {e}\n")
        return {}


def collect(ym, initial_contract_months=None):
    """対象月の全チェック対象顧客を rows 化する (月次サマリ行廃止後の「チェック証跡」担保)。

    発行漏れ候補(全件)・継続発行(全件: 金額変動の有無に関わらず)・今月新規(全件)を
    1顧客1行で出力する。月が変わっても各顧客ページの本文 table に毎月の行が残り、
    「その月チェックした」証跡が穴にならない。

    年間契約抑制 (ユーザー確定): 発行漏れ候補のうち「支払サイクル=年間払い」かつ
    「初回契約月から12ヶ月の年間契約期間中」の顧客は年間前払いで月次発行が無いのが正常なため、
    suppress_annual_period_gaps で候補から除外し rows に出さない。初回契約月/支払サイクルは
    MF API で取れないため Notion 管理列を人が記入し、機械はそれを読んで抑制に使う。
    支払サイクルが月払い/空欄/不明、または初回契約月が空/不明の顧客は従来どおり
    発行漏れ候補に残る (fail-safe)。

    initial_contract_months ({customer_id: {initial_contract_month, payment_cycle}}) は DI 引数。None かつ config に
    database_id がある場合のみ Notion から取得し、未設定や取得失敗時は空 dict にして抑制を
    スキップする (既存テストや DB 未設定環境でも壊れない後方互換)。

    API 負荷の最適化: detail_of(/transactions 呼び出し)は注目顧客(発行漏れ候補/
    金額変動した継続発行/今月新規)のみ。金額変動のない継続発行は detail_of をスキップし
    商品名空・更新日 None で金額だけ記録する(全顧客×全月でも /transactions が線形爆発
    しないため)。企業名(resolve_names)は全 targets 対象。
    """
    prev_ym = prev_month(ym)
    prev_b = fetch_issued(prev_ym)
    curr_b = fetch_issued(ym)
    res = detect_gaps(prev_b, curr_b)

    # 年間契約期間中の顧客を発行漏れ候補から抑制する (DI: None なら config の database_id で取得)。
    if initial_contract_months is None:
        cfg = load_config()
        db_id = (cfg.get("notion") or {}).get("database_id")
        initial_contract_months = _load_initial_contract_months(db_id)
    real_gaps, in_annual_gaps = suppress_annual_period_gaps(
        res["gap_candidates"], initial_contract_months, ym)
    res["gap_candidates"] = real_gaps
    res["suppressed_annual"] = in_annual_gaps  # summary 用 (年間契約期間中で除外した顧客)

    prev_by, curr_by = billings_by_customer(prev_b), billings_by_customer(curr_b)
    changed = set(amount_changed(res["continuing"], res["prev_amount"], res["curr_amount"]))
    # 企業名は全対象顧客で解決。detail_of(/transactions)は注目顧客のみに絞る。
    targets = set(res["gap_candidates"]) | set(res["continuing"]) | set(res["new_this_month"])
    names = resolve_names(targets)
    rows = []
    for cid in res["gap_candidates"]:
        bs = prev_by.get(cid, [])
        det = detail_of_billings(bs)
        rows.append({
            "customer_id": cid, "period_ym": ym, "company_name": names.get(cid, ""),
            "verdict": "発行漏れ候補", "product_name": det["product_name"],
            "prev_amount": res["prev_amount"].get(cid), "curr_amount": None,
            "issue_date": det["issue_date"], "updated_at": det["updated_at"],
        })
    for cid in res["continuing"]:
        bs = curr_by.get(cid, [])
        # 金額変動した継続発行のみ詳細(商品名/更新日)を取得。変動なしは detail_of スキップ。
        det = detail_of_billings(bs) if cid in changed else _empty_detail()
        # A3-008: 継続発行の issue_date は金額変動の有無に依らず常に当月 billing 由来で埋める。
        # detail_of_billings は当月 billing から issue_date を拾うが、detail_of をスキップする
        # 「金額変動なし継続」では det["issue_date"] が None になる。そのケースも当月 billing の
        # 最新発行日 (_latest_issue_date) で必ず補完し、issue_date 空欄落ちを防ぐ。
        issue_date = det["issue_date"] if det["issue_date"] is not None else _latest_issue_date(bs)
        rows.append({
            "customer_id": cid, "period_ym": ym, "company_name": names.get(cid, ""),
            "verdict": "継続発行", "product_name": det["product_name"],
            "prev_amount": res["prev_amount"].get(cid), "curr_amount": res["curr_amount"].get(cid),
            "issue_date": issue_date, "updated_at": det["updated_at"],
        })
    for cid in res["new_this_month"]:
        bs = curr_by.get(cid, [])
        det = detail_of_billings(bs)
        rows.append({
            "customer_id": cid, "period_ym": ym, "company_name": names.get(cid, ""),
            "verdict": "今月新規", "product_name": det["product_name"],
            "prev_amount": None, "curr_amount": res["curr_amount"].get(cid),
            "issue_date": det["issue_date"], "updated_at": det["updated_at"],
        })
    return res, rows


def _print_summary(ym, res, rows):
    # 継続発行は全件 rows 化される(金額変動なしも記録)。画面では総件数に加え「うち金額変動」
    # の内訳を併記し、注目すべき変動件数(detail_of を取得した顧客数)を運用者が一目で掴める
    # ようにする。res["continuing"] が全件、amount_changed が変動件数。
    changed = len(amount_changed(res["continuing"], res["prev_amount"], res["curr_amount"]))
    suppressed = len(res.get("suppressed_annual", []))
    print(f"== 発行漏れチェック {prev_month(ym)} → {ym} ==")
    print(f"発行漏れ候補: {len(res['gap_candidates'])}件 / "
          f"継続発行(全件): {len(res['continuing'])}件 (うち金額変動: {changed}件) / "
          f"今月新規: {len(res['new_this_month'])}件")
    # 年間契約抑制 (初回契約月+12ヶ月の年間契約期間中は月次発行が無いのが正常) で発行漏れ候補から
    # 機械が除外した件数。抑制が効いたことを運用者が観測できるよう件数を1行で出す。
    print(f"年間契約期間中で除外: {suppressed}件 (支払サイクル=年間払い + 初回契約月で機械抑制)")
    for r in rows:
        amt = f"前月{r['prev_amount']}→今月{r['curr_amount']}"
        print(f"  [{r['verdict']}] {r['company_name']}({r['customer_id']}) {r['product_name']} {amt}")


def month_iter(from_ym, to_ym):
    """from_ym〜to_ym (両端含む) を昇順で yield する。from > to は空。"""
    fy, fm = map(int, from_ym.split("-"))
    ty, tm = map(int, to_ym.split("-"))
    cur = fy * 12 + (fm - 1)
    end = ty * 12 + (tm - 1)
    while cur <= end:
        y, m = divmod(cur, 12)
        yield f"{y:04d}-{m + 1:02d}"
        cur += 1


def backfill(from_ym, to_ym, db_id, force_unverified=False, period_ym=None):
    """過去月の範囲を一括で collect→sink し、顧客ページの table に遡及投入する。

    backfill は複数月を自動で回すため対話 verify を挟めない。発行漏れ候補は誤検出リスクが
    あるため、既存 sink の二段確認境界(verify 済みでない発行漏れ候補は --force-unverified
    でのみ投入)と一貫させる:
      - 既定 (force_unverified=False): 発行漏れ候補をスキップし、継続発行・今月新規
        (誤検出リスク低) のみ投入。発行漏れ候補をスキップした旨を stderr 警告。
      - --force-unverified: 発行漏れ候補も未検証のまま投入。明示フラグ + stderr 警告で
        fail-closed 思想を破らない (運用者が意図的に承認した場合のみ)。
    月の昇順で投入するため、table 行は時系列順 (古い月が上) に並ぶ。
    """
    sys.stderr.write(
        f"[backfill] {from_ym}〜{to_ym} を昇順で遡及投入します。"
        "backfill は対話 verify を挟めません。\n")
    if force_unverified:
        sys.stderr.write(
            "[backfill] 警告: --force-unverified。発行漏れ候補を二段確認なしで投入します"
            "(誤検出が混入する可能性あり)。\n")
    else:
        sys.stderr.write(
            "[backfill] 発行漏れ候補は未検証のためスキップし、継続発行・今月新規のみ投入します"
            "(発行漏れ候補も投入するなら --force-unverified)。\n")

    total = {"created": 0, "updated": 0, "months": 0, "skipped_gaps": 0}
    for ym in month_iter(from_ym, to_ym):
        res, rows = collect(ym)
        _print_summary(ym, res, rows)
        if force_unverified:
            sink_rows = rows
        else:
            skipped = [r for r in rows if r.get("verdict") == GAP_VERDICT]
            total["skipped_gaps"] += len(skipped)
            sink_rows = [r for r in rows if r.get("verdict") != GAP_VERDICT]
        errs = validate_rows(sink_rows)
        if errs:
            sys.stderr.write(
                f"[backfill] {ym}: sink 入力が schema 違反:\n  " + "\n  ".join(errs) + "\n")
            return 2
        r = notion_invoice_sink.upsert(db_id, sink_rows, period_ym=ym)
        total["created"] += r["created"]
        total["updated"] += r["updated"]
        total["months"] += 1
        print(f"  [backfill] {ym} upsert: created={r['created']} updated={r['updated']} "
              f"(投入 {len(sink_rows)}件)")
    print(f"\nbackfill 完了: {total['months']}ヶ月 / created={total['created']} "
          f"updated={total['updated']} / 発行漏れ候補スキップ {total['skipped_gaps']}件。")
    return 0


def finalize(exclude_ids, in_path, out_path):
    """verify(subagent)の確定結果を確定リストへ昇格する (二段確認の物理境界を作る, F1)。

    exclude_ids: 誤検出として除外する customer_id 集合 (発行漏れ候補のみ除外対象)。
    確定リストの存在自体が『verify を通過した』証跡となり、sink はこれを fail-closed で要求する。
    """
    with open(in_path, encoding="utf-8") as f:
        rows = json.load(f)
    errs = validate_rows(rows)
    if errs:
        sys.stderr.write("[finalize] 候補JSONが schema 違反:\n  " + "\n  ".join(errs) + "\n")
        return 2
    excl = {c for c in exclude_ids if c}
    kept = [r for r in rows if not (r.get("verdict") == GAP_VERDICT and r.get("customer_id") in excl)]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"確定リストを {out_path} に出力 ({len(kept)}件 / 誤検出除外 {len(rows) - len(kept)}件)。"
          "--sink で Notion 投入してください。")
    return 0


def _warn_residual_to_screen(upsert_result):
    """upsert 戻りの residual/集計疑い列を画面(stdout)に昇格し掃除アクションへ誘導する。

    warn_residual_summary_columns は stderr に出すが、成功サマリ(stdout)に埋もれて人が
    掃除に気づかない経路を塞ぐ(検知→/run-mf-invoice-db-setup 再実行の to-human 到達性)。
    read-only は変えず、表示のみ。
    """
    residual = upsert_result.get("residual") or []
    suspect = upsert_result.get("suspect_summary") or []
    flagged = sorted(set(residual) | set(suspect))
    if flagged:
        print(f"⚠ 旧サマリ/集計列の疑いがある列が DB に残存: {flagged} "
              f"→ /run-mf-invoice-db-setup を再実行して掃除してください(集計は持たない設計)。")


def main():
    p = argparse.ArgumentParser(description="MF掛け払い 月次発行漏れチェック (collect→verify→finalize→sink)")
    p.add_argument("--collect", action="store_true", help="未検証候補を取得・出力")
    p.add_argument("--finalize", action="store_true", help="verify確定結果を確定リストへ昇格")
    p.add_argument("--sink", action="store_true", help="確定リストを Notion へ冪等 upsert")
    p.add_argument("--backfill", action="store_true",
                   help="--from/--to の範囲(両端含む)を月昇順で collect→sink し過去履歴を遡及投入")
    p.add_argument("--month", help="対象月(今月) YYYY-MM (既定: 実行日の年月)")
    p.add_argument("--from", dest="from_ym", help="backfill: 開始月 YYYY-MM (--month と排他)")
    p.add_argument("--to", dest="to_ym", help="backfill: 終了月 YYYY-MM (両端含む, --month と排他)")
    p.add_argument("--exclude-ids", help="finalize: 誤検出として除外する customer_id (カンマ区切り)")
    p.add_argument("--input", help="finalize/sink の入力 JSON path")
    p.add_argument("--out", help="collect/finalize の出力先 path")
    p.add_argument("--force-unverified", action="store_true",
                   help="sink/backfill: 未検証の発行漏れ候補を直接投入 (二段確認スキップ・非推奨)。"
                        "⚠ 二段確認(mfk-gap-verifier)をバイパスし未検証候補を直接 sink。誤検出が Notion に混入しうる")
    a = p.parse_args()

    if a.backfill:
        if not (a.from_ym and a.to_ym):
            sys.stderr.write("[backfill] --from YYYY-MM と --to YYYY-MM の両方が必須です。\n")
            return 2
        if a.month:
            sys.stderr.write("[backfill] --month は --from/--to と排他です。範囲指定のみ使ってください。\n")
            return 2
        for label, ym in (("--from", a.from_ym), ("--to", a.to_ym)):
            if not valid_month(ym):
                sys.stderr.write(f"[backfill] {label} が YYYY-MM 形式の実在月でない: {ym!r}\n")
                return 2
        if a.from_ym > a.to_ym:
            sys.stderr.write(f"[backfill] --from({a.from_ym}) が --to({a.to_ym}) より後です。\n")
            return 2
        cfg = load_config()
        db_id = (cfg.get("notion") or {}).get("database_id")
        if not db_id:
            sys.stderr.write("[backfill] notion.database_id 未設定。先に run-mf-invoice-db-setup を実行してください。\n")
            return 2
        return backfill(a.from_ym, a.to_ym, db_id, force_unverified=a.force_unverified)

    if a.finalize:
        in_path = a.input or candidates_path()
        out_path = a.out or verified_path()
        return finalize((a.exclude_ids or "").split(","), in_path, out_path)

    if a.sink:
        if a.input:
            path = a.input
            if (not a.force_unverified) and not _same_path(path, verified_path()):
                sys.stderr.write(
                    f"[check] --force-unverified なしの --input は確定リスト {verified_path()} のみ許可します。"
                    f"指定値={path!r}。verify→finalize 後の確定リストを使うか、二段確認をスキップする"
                    "意図がある場合のみ --force-unverified を併用してください。\n")
                return 2
            if a.force_unverified:
                sys.stderr.write(
                    "[check] ⚠ 警告: --force-unverified。二段確認(mfk-gap-verifier)をバイパスし"
                    "未検証候補を直接 sink します。誤検出が Notion に混入しうる点に注意してください。\n")
        elif a.force_unverified:
            path = candidates_path()
            sys.stderr.write(
                "[check] ⚠ 警告: --force-unverified。二段確認(mfk-gap-verifier)をバイパスし"
                "未検証候補を直接 sink します。誤検出が Notion に混入しうる点に注意してください。\n")
        else:
            path = verified_path()
            if not os.path.exists(path):
                sys.stderr.write(
                    f"[check] 確定リスト {path} が不在です。collect→verify(subagent)→finalize の後に "
                    "--sink してください (二段確認をスキップして投入するなら --force-unverified)。\n")
                return 2
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        errs = validate_rows(rows)
        if errs:
            sys.stderr.write("[check] sink 入力が schema 違反:\n  " + "\n  ".join(errs) + "\n")
            return 2
        periods = _row_periods(rows)
        if a.month:
            if _reject_bad_month("--month", a.month):
                return 2
            if periods and periods != {a.month}:
                sys.stderr.write(
                    f"[check] --month({a.month}) と入力 rows の period_ym({sorted(periods)}) が一致しません。"
                    "--sink では入力 JSON の対象月と表示対象月をずらさないでください。\n")
                return 2
        cfg = load_config()
        db_id = (cfg.get("notion") or {}).get("database_id")
        if not db_id:
            sys.stderr.write("[check] notion.database_id 未設定。先に run-mf-invoice-db-setup を実行してください。\n")
            return 2
        ym = a.month or (rows[0]["period_ym"] if rows else default_target_month())
        r = notion_invoice_sink.upsert(db_id, rows, period_ym=ym)
        print(f"Notion upsert: created={r['created']} updated={r['updated']} "
              f"period={r['period_ym']} run_id={r['run_id']} (各顧客ページ本文の月次 table に履歴追記)")
        _warn_residual_to_screen(r)
        return 0

    # 既定は collect。既定の対象月は実行日の年月 (default_target_month 参照)。
    ym = a.month or default_target_month()
    if _reject_bad_month("--month", ym):
        return 2
    res, rows = collect(ym)
    _print_summary(ym, res, rows)
    out = a.out or candidates_path()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n候補を {out} に出力 ({len(rows)}件)。subagent(mfk-gap-verifier)検証→--finalize→--sink の順で投入してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
