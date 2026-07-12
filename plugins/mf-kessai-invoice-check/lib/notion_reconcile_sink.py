#!/usr/bin/env python3
"""月次発行チェック DB2 へ照合結果を **履歴非破壊** で upsert する sink。

目的: 翌月実行しても過去月の行と、人間が確認した記録 (人間対応済み=true) が消えないこと。
反面教師は scratch の load_db2.py で、archive_all で DB2 を全消ししてから再投入していた
(= 過去月も確認済みも毎回消える)。本モジュールはこれを非破壊に置き換える。

非破壊を成立させる 3 つの不変条件 (SSOT):
  1. **当月限定 query**  : 既存行の取得は `対象年月==target_ym` でフィルタする
     (query_month)。過去月 (対象年月≠target_ym) は **読まない・触らない**。query 対象外
     なので翌月実行で先月以前の行は完全に不可侵 (PATCH/POST/archive を一切受けない)。
  2. **確認済み凍結 (L1)**: 当月既存行でも `人間対応済み==true` の行は **スキップ (frozen)**。
     人が確認した記録を機械が絶対に上書きしない。判定/金額/警告も一切 PATCH しない。
  3. **未確認は更新のみ**: 当月既存行で `人間対応済み==false` の行は判定/金額/警告等を PATCH で
     更新する。ただし `人間対応済み` 列には触れない (人間専用 managed 列)。無ければ POST 新規作成。

upsert キー (buildspec D1: 方向でキー分岐):
  - 順方向     : title = `{契約ID}_{target_ym}`  (キー=契約ID)。契約relation も併記。
  - 逆方向orphan: title = `ORPHAN_{MF顧客ID}_{target_ym}` (キー=MF顧客ID)。relation 空。
  どちらも title が自然キーなので、既存当月行は title (契約×年月) で索引化する。

行 (row) の契約 (sink が読むキー。reconcile-result.schema.json と loader が橋渡しする):
  direction        : "順方向" | "逆方向orphan" (既定 順方向)
  contract_id      : DB1 契約ID (順方向 title キー)
  contract_page_id : DB1 ページ id (契約relation。loader が DB1 から解決して渡す。任意)
  mf_customer_id   : MF顧客ID (逆方向 title キー + 証跡 rich_text)
  judge_label      : DB2『判定』select ラベル (verdict-mapping.json で導出済みの日本語)
  expected_amount  : 期待金額 (number, 税抜・明細単価)。None なら書かない
  matched_amount   : 突合金額 (number)。None なら書かない
  expected_count   : 期待件数 (number)。None なら書かない
  supply_count     : MF供給件数 (number)。None なら書かない
  ai_check          : AI確認済み (checkbox)。verdict-mapping.json の ai_check から導出
  mf_billing_id    : MF請求ID (rich_text)
  issue_date       : 発行日 (date "YYYY-MM-DD")
  warning          : 警告 (rich_text・**改行 \\n をそのまま保持**)
  run_at           : 実行日時 (date)。任意

HTTP は notion_transport._req を単一正本として使う (書き込みレート間隔 MFK_NOTION_WRITE_GAP
内蔵)。テスト/呼出側は `req` 引数でモック差し替えできる。各行は try/except で個別に隔離し、
1 行の失敗は failed に計上して残りの処理を続ける。
"""
from notion_transport import _req

# Notion rich_text の content は 1 要素あたり 2000 文字上限。超過は切り詰める。
_MAX_RICH_TEXT = 2000

# DB2 プロパティ名 (monthly-check-db.schema.json と一致)。
PROP_TITLE = "契約×年月"
PROP_RELATION = "契約"
PROP_TARGET_YM = "対象年月"
PROP_DIRECTION = "方向"
PROP_JUDGE = "判定"
PROP_EXPECTED = "期待金額"
PROP_MATCHED = "突合金額"
PROP_EXPECTED_COUNT = "期待件数"
PROP_SUPPLY_COUNT = "MF供給件数"
PROP_AI_CHECK = "AI確認済み"
PROP_MF_CUSTOMER = "MF顧客ID"
PROP_MF_BILLING = "MF請求ID"
PROP_ISSUE_DATE = "発行日"
PROP_WARNING = "警告"
PROP_HUMAN_DONE = "人間対応済み"  # 人間専用 managed 列。機械は新規時のみ false で初期化する。
PROP_RUN_AT = "実行日時"

DIRECTION_FORWARD = "順方向"
DIRECTION_ORPHAN = "逆方向orphan"


def _title_for(row, target_ym):
    """row の方向に応じた title (= 自然キー) を返す (buildspec D1)。

    順方向     : `{契約ID}_{target_ym}`。
    逆方向orphan: `ORPHAN_{MF顧客ID}_{target_ym}`。
    """
    direction = row.get("direction") or DIRECTION_FORWARD
    if direction == DIRECTION_ORPHAN:
        return f"ORPHAN_{row.get('mf_customer_id') or ''}_{target_ym}"
    return f"{row.get('contract_id') or ''}_{target_ym}"


def _title_plain(prop):
    """Notion title プロパティを plain text へ連結する (空/欠落は '')。"""
    if not isinstance(prop, dict):
        return ""
    return "".join(
        (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
        for rt in (prop.get("title") or [])
    )


def _rt(value):
    """rich_text プロパティ。content の改行 \\n はそのまま保持する (split しない)。"""
    s = str(value if value is not None else "")
    return {"rich_text": [{"text": {"content": s[:_MAX_RICH_TEXT]}}]}


def query_month(db2_id, target_ym, token, req=None):
    """DB2 の **当月 (対象年月==target_ym) 行のみ** を取得する (非破壊の要)。

    `対象年月` select が target_ym に等しい行だけを query する。過去月は読まないため、
    後続の upsert で過去月へ触れる経路が構造的に存在しない。has_more/next_cursor を辿り
    全件取得し、page_id で dedup したページ list を返す。
    """
    req = req or _req
    out = {}
    cursor = None
    while True:
        body = {
            "filter": {"property": PROP_TARGET_YM, "select": {"equals": target_ym}},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        try:
            res = req("POST", f"/databases/{db2_id}/query", token, body)
        except RuntimeError as e:
            # 対象年月 select に target_ym option が未作成 (その月を初めて処理する初回) の場合、
            # Notion は select フィルタで存在しない option を validation_error(HTTP 400) にする。
            # その月の DB2 行はまだ存在しない (既存ゼロ) ので空を返す。最初の行を POST する際に
            # option が自動作成され、以降の query は通る。対象年月以外の 400 は握りつぶさず再送出。
            msg = str(e)
            if ("HTTP 400" in msg and "select option" in msg
                    and "not found" in msg and PROP_TARGET_YM in msg):
                return []
            raise
        for page in res.get("results", []):
            pid = page.get("id")
            if pid and pid not in out:  # page_id dedup
                out[pid] = page
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return list(out.values())


def _build_props(row, target_ym, *, creating):
    """row を DB2 プロパティ dict へ整形する。

    creating=True (新規 POST) のときだけ title と `人間対応済み`=false を載せる。
    更新 (PATCH) では title (= 不変な自然キー) と `人間対応済み` (人間専用 managed 列) に
    一切触れない。更新時は nullable な事実列も明示クリアし、前回の MF 証跡や警告が stale に
    残らないようにする。
    """
    direction = row.get("direction") or DIRECTION_FORWARD
    props = {
        PROP_DIRECTION: {"select": {"name": direction}},
        PROP_TARGET_YM: {"select": {"name": target_ym}},
    }
    judge = row.get("judge_label")
    if judge:
        props[PROP_JUDGE] = {"select": {"name": judge}}
    if row.get("expected_amount") is not None:
        props[PROP_EXPECTED] = {"number": row["expected_amount"]}
    elif not creating:
        props[PROP_EXPECTED] = {"number": None}
    if row.get("matched_amount") is not None:
        props[PROP_MATCHED] = {"number": row["matched_amount"]}
    elif not creating:
        props[PROP_MATCHED] = {"number": None}
    if row.get("expected_count") is not None:
        props[PROP_EXPECTED_COUNT] = {"number": row["expected_count"]}
    elif not creating:
        props[PROP_EXPECTED_COUNT] = {"number": None}
    if row.get("supply_count") is not None:
        props[PROP_SUPPLY_COUNT] = {"number": row["supply_count"]}
    elif not creating:
        props[PROP_SUPPLY_COUNT] = {"number": None}
    if row.get("ai_check") is not None:
        props[PROP_AI_CHECK] = {"checkbox": bool(row["ai_check"])}
    if row.get("mf_billing_id"):
        props[PROP_MF_BILLING] = _rt(row["mf_billing_id"])
    elif not creating:
        props[PROP_MF_BILLING] = {"rich_text": []}
    if row.get("mf_customer_id"):
        props[PROP_MF_CUSTOMER] = _rt(row["mf_customer_id"])  # 証跡 + orphan 補助キー
    elif not creating:
        props[PROP_MF_CUSTOMER] = {"rich_text": []}
    if row.get("warning"):
        props[PROP_WARNING] = _rt(row["warning"])  # 改行 \n 保持
    elif not creating:
        props[PROP_WARNING] = {"rich_text": []}
    if row.get("issue_date"):
        props[PROP_ISSUE_DATE] = {"date": {"start": row["issue_date"]}}
    elif not creating:
        props[PROP_ISSUE_DATE] = {"date": None}
    if row.get("run_at"):
        props[PROP_RUN_AT] = {"date": {"start": row["run_at"]}}
    elif not creating:
        props[PROP_RUN_AT] = {"date": None}
    if row.get("contract_page_id"):
        props[PROP_RELATION] = {"relation": [{"id": row["contract_page_id"]}]}
    elif not creating:
        props[PROP_RELATION] = {"relation": []}
    if creating:
        title = _title_for(row, target_ym)[:_MAX_RICH_TEXT]
        props[PROP_TITLE] = {"title": [{"text": {"content": title}}]}
        # 新規時のみ false で初期化。以後この列は人間専用で機械は触れない。
        props[PROP_HUMAN_DONE] = {"checkbox": False}
    return props


def upsert_monthly(rows, db2_id, target_ym, token, req=None):
    """rows を **当月 (target_ym) のみ** 履歴非破壊で upsert する。

    手順:
      1. query_month で当月既存行を取得し、title (= 自然キー) で索引化する。
         過去月は query 対象外なので一切読まない・触らない (非破壊)。
      2. 各 row について title でキー一致を判定:
         - 既存当月行あり & 人間対応済み==true → スキップ (frozen)。機械は上書きしない。
         - 既存当月行あり & 人間対応済み==false → PATCH 更新 (人間対応済みは送らない)。
         - 既存当月行なし                       → POST 新規作成 (人間対応済み=false)。
      3. 各行は try/except で隔離し、個別失敗は failed に計上して継続する。

    返り値: {"created", "updated", "frozen", "failed"} の件数 dict。
    """
    req = req or _req
    existing = query_month(db2_id, target_ym, token, req)
    index = {}
    for page in existing:
        title = _title_plain((page.get("properties") or {}).get(PROP_TITLE))
        if title:
            index[title] = page

    created = updated = frozen = failed = 0
    for row in rows:
        try:
            title = _title_for(row, target_ym)
            page = index.get(title)
            if page is not None:
                done = ((page.get("properties") or {}).get(PROP_HUMAN_DONE) or {}).get("checkbox")
                if done:
                    # L1 凍結: 人が確認した記録は機械が絶対に上書きしない。
                    frozen += 1
                    continue
                props = _build_props(row, target_ym, creating=False)
                req("PATCH", f"/pages/{page['id']}", token, {"properties": props})
                updated += 1
            else:
                props = _build_props(row, target_ym, creating=True)
                req("POST", "/pages", token,
                    {"parent": {"database_id": db2_id}, "properties": props})
                created += 1
        except Exception:  # noqa: BLE001  個別行の失敗は隔離し残りを継続する
            failed += 1
            continue
    return {"created": created, "updated": updated, "frozen": frozen, "failed": failed}
