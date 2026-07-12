#!/usr/bin/env python3
"""発行漏れチェック結果を Notion DB に冪等 upsert する sink (顧客ID集約モデル)。

upsert キー = customer_id 単独。1顧客=1 Notion ページ。既存顧客は月が変わっても同じページを
更新し、未登録顧客だけ新規ページを作成する。月ごとの重複ページは作らない。月次履歴は各顧客ページの**本文 table block**
(Notion type:"table") に 1 行=1 対象年月で蓄積する(自然キー=period_ym, 同月再実行は
既存行更新で冪等)。DBプロパティはその顧客の「最新月スナップショット」(事実列のみ)を
書き込み、管理列(初回契約月/請求要否/支払サイクル/チェック済/備考)には触れない
(人の運用記入を自動実行が上書きしないため)。
Notion トークンは Keychain から取得。service/account は env > config(notion.keychain_service/
account) > default の順で解決し (MF キー側 mfk_keychain と対称)、共通リゾルバ
mfk_keychain.resolve_service / fetch_secret を経由する。
"""
import datetime
import json
import os
import re
import sys
# time / urllib は本モジュール自身では未使用だが、既存テストが sink.time.sleep /
# sink.urllib.request.urlopen を monkeypatch する (_req は notion_transport から
# re-export) ため、属性面の後方互換として import を保持する。
import time  # noqa: F401  (back-compat: tests patch sink.time.sleep)
import urllib.error  # noqa: F401
import urllib.request  # noqa: F401  (back-compat: tests patch sink.urllib.request.urlopen)

# Notion HTTP transport は notion_transport.py を単一正本 (SSOT) とし、本モジュールは
# 既存の公開名・挙動を不変に保つため re-export する。他モジュール/テストが
# notion_invoice_sink._req / ._notion_token 等を参照しているため re-export は必須。
from notion_transport import (  # noqa: F401  (re-export: 公開名・挙動を不変に保つ)
    NOTION_API,
    NOTION_VERSION,
    _notion_account,
    _notion_cfg,
    _notion_service,
    _notion_token,
    _req,
    _rich_text_plain,
    _select_name,
)

# 本文 table block の固定列定義 (1行=1対象年月)。順序がセル順を規定する。
TABLE_COLUMNS = ["対象年月", "今月の発行状況", "前月金額", "今月金額", "確認済み日時"]
# 後方互換: 旧ヘッダ ("判定") の既存 table を月次履歴として認識し続けるための別名。
# 既存ページ本文の table は旧ヘッダのまま残るため、新ヘッダだけ見ると _find_table_id が
# 月次履歴 table を取りこぼし、二重 table を append する事故が起きる。これを防ぐ。
TABLE_COLUMNS_LEGACY = ["対象年月", "判定", "前月金額", "今月金額", "確認済み日時"]
TABLE_WIDTH = len(TABLE_COLUMNS)


def _find_page(database_id, customer_id, token):
    """customer_id 単独で既存ページを検索。あれば page_id を返す。

    顧客IDは一意のはず。複数ヒットは冪等キー破壊なので暗黙に先頭採用せず raise する。
    """
    body = {"filter": {"property": "顧客ID", "rich_text": {"equals": customer_id}}}
    res = _req("POST", f"/databases/{database_id}/query", token, body)
    items = res.get("results", [])
    if len(items) > 1:
        raise RuntimeError(
            f"重複ページ検出: 顧客ID={customer_id} が {len(items)}件存在。"
            "手動で重複を解消してから再実行してください (顧客ID は一意のはず)。")
    return items[0]["id"] if items else None


def fetch_initial_contract_months(database_id, token=None):
    """Notion DB を全件クエリし年間抑制用の契約情報を返す (read-only)。

    返り値は {customer_id: {"initial_contract_month": "YYYY-MM", "payment_cycle": "年間払い"}}。
    `支払サイクル` が年間払いの顧客だけを返す。月払い/空欄/不正値は dict に含めず、
    発行漏れ候補に残す fail-safe に倒す。token は未指定なら Keychain から取得する。

    返り値 dict は collect() の `initial_contract_months` 引数へ渡し suppress_annual_period_gaps
    で年間期間中の顧客を発行漏れ候補から除外する。GET/POST(query) のみで DB を変更しない。
    """
    token = token or _notion_token()
    out = {}
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = _req("POST", f"/databases/{database_id}/query", token, body)
        for page in res.get("results", []):
            props = page.get("properties") or {}
            cid = _rich_text_plain(props.get("顧客ID")).strip()
            month = _rich_text_plain(props.get("初回契約月")).strip()
            cycle = _select_name(props.get("支払サイクル")).strip()
            if cid and cycle == "年間払い" and re.fullmatch(r"\d{4}-\d{2}", month):
                out[cid] = {"initial_contract_month": month, "payment_cycle": cycle}
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


def _props(row):
    """1 顧客の最新月スナップショットを Notion プロパティ形式に変換 (事実列のみ)。"""
    def rt(v):
        return {"rich_text": [{"text": {"content": str(v if v is not None else "")}}]}

    def num(v):
        return {"number": (int(v) if v is not None else None)}

    props = {
        "取引先企業名": {"title": [{"text": {"content": row.get("company_name", "")}}]},
        "顧客ID": rt(row.get("customer_id")),
        "対象年月": rt(row.get("period_ym")),
        # 表示プロパティ名は「今月の発行状況」。内部 verdict キー・enum値 (発行漏れ候補/
        # 継続発行/今月新規) は不変で、Notion 表示名だけを改名した。
        "今月の発行状況": {"select": {"name": row.get("verdict", "発行漏れ候補")}},
        "商品名": rt(row.get("product_name")),
        "前月金額": num(row.get("prev_amount")),
        "今月金額": num(row.get("curr_amount")),
    }
    if row.get("issue_date"):
        props["発行日"] = {"date": {"start": row["issue_date"]}}
    if row.get("updated_at"):
        props["更新日"] = {"date": {"start": row["updated_at"]}}
    if row.get("checked_at"):
        props["確認済み日時"] = {"date": {"start": row["checked_at"]}}
    return props


def _create_props(row):
    """新規ページ作成時のプロパティ。

    _props (fact_column の最新月スナップショット) に加え、managed_column の
    `初回契約月` を**空欄で初期化**する。これにより MF API から取得できない契約開始月が
    未入力の顧客を Notion の「空欄」フィルタで拾い、人が YYYY-MM で補正できる。
    既存ページ更新では `_props` を使い `初回契約月` (人の運用列) には一切触れない
    (再投入で人の記入を上書きしないため = 新規時のみ初期化する関数境界で機械保証)。
    """
    props = _props(row)
    props["初回契約月"] = {"rich_text": [{"text": {"content": ""}}]}
    return props


# --- 本文 table block (月次履歴) -------------------------------------------------

def _cell(text):
    """table_row の 1 セル。空セルも [] でなく content="" の text を1つ持たせる。"""
    return [{"type": "text", "text": {"content": str(text if text is not None else "")}}]


def _table_row_block(values):
    """values (TABLE_WIDTH 個の文字列) から table_row ブロックを構築する。"""
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": [_cell(v) for v in values]},
    }


def _header_row_block():
    return _table_row_block(TABLE_COLUMNS)


def _month_values(row):
    """1 顧客の月次行 (TABLE_COLUMNS 順の値リスト)。"""
    return [
        row.get("period_ym") or "",
        row.get("verdict") or "",
        str(row.get("prev_amount") if row.get("prev_amount") is not None else ""),
        str(row.get("curr_amount") if row.get("curr_amount") is not None else ""),
        row.get("checked_at") or "",
    ]


def _table_block(header_and_rows):
    """新規ページ作成時に children へ渡す table ブロック (header + data 行群)。"""
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": TABLE_WIDTH,
            "has_column_header": True,
            "has_row_header": False,
            "children": header_and_rows,
        },
    }


def _cell_plain(cell):
    """table_row の 1 セル (rich_text 配列) を plain text へ連結する。"""
    return "".join((rt.get("text") or {}).get("content") or "" for rt in (cell or []))


def _all_block_children(block_id, token):
    """block の子要素を has_more/next_cursor で全ページ取得する。

    Notion はブロック子要素を既定 100 件/ページで返す。table の月次行が 100 行
    (約 8 年) を超えても既存行を取りこぼさないようカーソルで全件辿る。取りこぼすと
    period_ym 一致を見落として重複追記し、冪等 (同月は既存行更新) が壊れるため。
    """
    out = []
    cursor = None
    while True:
        query = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        res = _req("GET", f"/blocks/{block_id}/children{query}", token)
        out.extend(res.get("results", []))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


def _find_table_id(page_id, token):
    """ページ本文から月次履歴 table のブロック id を返す。無ければ None。

    人がページ本文の上部に別用途の table を追加しても誤追記しないよう、先頭行が
    月次履歴ヘッダと一致する table だけを月次履歴 table として採用する。
    ヘッダは新 TABLE_COLUMNS だけでなく旧 TABLE_COLUMNS_LEGACY (判定列名) も認める。
    改名前に作られた既存ページの table は旧ヘッダのまま残るため、新ヘッダだけ照合すると
    月次履歴を取りこぼして二重 table を append する事故が起きる。両方を後方互換で拾う。
    """
    for blk in _all_block_children(page_id, token):
        if blk.get("type") == "table":
            rows = _all_block_children(blk["id"], token)
            if not rows:
                continue
            cells = (rows[0].get("table_row") or {}).get("cells") or []
            header = [_cell_plain(c) for c in cells]
            if header in (TABLE_COLUMNS, TABLE_COLUMNS_LEGACY):
                return blk["id"]
    return None


def _upsert_month_row(page_id, row, token):
    """既存ページの本文 table に当月行を upsert する (自然キー=period_ym)。

    手順: table 取得→無ければ append→既存行で period_ym 一致を探し更新、無ければ追加。
    同月の再 sink は既存行更新で重複しない。
    """
    period_ym = row.get("period_ym") or ""
    values = _month_values(row)
    table_id = _find_table_id(page_id, token)
    if table_id is None:
        # 後方データ移行: table が無い旧ページには header + 当月行で table を新規 append。
        _req("PATCH", f"/blocks/{page_id}/children", token,
             {"children": [_table_block([_header_row_block(), _table_row_block(values)])]})
        return

    table_rows = _all_block_children(table_id, token)
    # has_column_header の先頭行はヘッダなので除外して period_ym 一致を探す。
    for idx, blk in enumerate(table_rows):
        if idx == 0:
            continue
        cells = (blk.get("table_row") or {}).get("cells") or []
        if cells and _cell_plain(cells[0]) == period_ym:
            _req("PATCH", f"/blocks/{blk['id']}", token,
                 {"table_row": {"cells": [_cell(v) for v in values]}})
            return
    # 一致行なし → 末尾に追加。
    _req("PATCH", f"/blocks/{table_id}/children", token,
         {"children": [_table_row_block(values)]})


def _run_id(checked_at):
    return "mfk-" + checked_at.replace(":", "").replace("-", "").replace("+", "").replace(".", "")


# --- backward remediation: 月次フローの read-only 旧サマリ/余剰列 検知ゲート ----------------
#  forward 生成防止 (sink/schema/test) と対をなす、過去に DB へ手動で作られ残った旧サマリ/集計列を
#  月次 upsert 後に **read-only (GET 専用)** で検知し /run-mf-invoice-db-setup 再実行へ誘導する。
#  列削除/ PATCH/DELETE は決してしない (参照専用が中核保証)。検知は WARN-not-FAIL で、
#  正当な追加列の偽陽性による恒常 FAIL (オオカミ少年) を避ける。

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "skills", "run-mf-invoice-db-setup", "schemas", "notion-db-schema.json",
)

# 集計語 (日本語 + 英語)。列名にこの語が含まれれば「集計列の疑い」とみなす。
# whitelist (deprecated 固定名) に載らない**新名の集計列**を拾うための語彙。
# 日本語: 総計/合計/小計/集計/サマリ/件数/トータル, 英語: total/sum/count (大小無視)。
_SUMMARY_WORDS_JA = ("総計", "合計", "小計", "集計", "サマリ", "件数", "トータル")
_SUMMARY_WORDS_EN = ("total", "sum", "count")


def _load_default_schema():
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def suspect_summary_extras(extra):
    """extra (schema 未知の余剰列名リスト) から「集計列の疑い」がある列だけを sorted で返す純関数。

    whitelist (deprecated 固定名) に載らない新名の集計列を、列名に集計語を含むかで拾う。
    日本語語彙 (総計/合計/小計/集計/サマリ/件数/トータル) は部分一致、英語語彙 (total/sum/count)
    は大小無視の部分一致。集計語を含まない正当な追加列 (任意メモ/担当者/社内コード等) は拾わない
    (偽陽性を出さない)。空/None は空リスト。FAIL/削除はしない (検知のみ)。
    """
    if not extra:
        return []
    suspects = []
    for name in extra:
        s = str(name)
        lower = s.lower()
        if any(w in s for w in _SUMMARY_WORDS_JA) or any(w in lower for w in _SUMMARY_WORDS_EN):
            suspects.append(s)
    return sorted(suspects)


def residual_extra_columns(props, schema):
    """live DB の properties を schema と突き合わせ、schema 外の列を residual/extra に分類する純関数。

    residual: schema["deprecated_properties"] に登録済みの**既知の旧サマリ/集計列**
              (全体トータル/レコード種別等)。db-setup 再実行で掃除すべき列。
    extra:    schema にも deprecated にも無い**手動追加の未知列** (任意メモ等)。

    schema["properties"] に存在する現行列はどちらにも入れない。列削除はしない (検知のみ)。
    """
    known = set(schema.get("properties", {}).keys())
    deprecated = set(schema.get("deprecated_properties", []))
    residual, extra = [], []
    for name in props.keys():
        if name in known:
            continue
        if name in deprecated:
            residual.append(name)
        else:
            extra.append(name)
    return sorted(residual), sorted(extra)


def warn_residual_summary_columns(database_id, token, schema=None, stream=None):
    """upsert 後の read-only 検知ゲート。live DB を GET し残骸列を検知して stream へ WARN 出力する。

    GET /databases/{id} だけを行い (列削除/PATCH/DELETE は一切しない)、schema 外の列を
    residual (deprecated 既知集計列) / suspect (集計疑い extra) / other (schema 未知の正当列)
    の 3 分類で別行に出し、/run-mf-invoice-db-setup 再実行へ誘導する。
    WARN-not-FAIL: 検知のみで本体を止めない。

    返り値:
      (residual, extra)  検知できたとき。stream には残骸があった分類だけ 1 行ずつ出力。
      (None, None)       db_id 未解決 (GET せずスキップ) または GET 失敗 (best-effort で握り潰し)。
    """
    if stream is None:
        stream = sys.stderr
    if not database_id:
        return None, None
    try:
        res = _req("GET", f"/databases/{database_id}", token)
    except Exception:
        # Notion 不通等は検知のみスキップ (本体の月次フローを残骸検知失敗で止めない)。
        return None, None
    if schema is None:
        try:
            schema = _load_default_schema()
        except Exception:
            return None, None
    props = res.get("properties") or {}
    residual, extra = residual_extra_columns(props, schema)
    suspect = suspect_summary_extras(extra)
    others = sorted(set(extra) - set(suspect))
    if residual:
        stream.write(
            f"WARN 旧サマリ/集計列が DB に残存: {residual} "
            f"→ /run-mf-invoice-db-setup を再実行して掃除してください (集計は持たない設計)。\n")
    if suspect:
        stream.write(
            f"WARN 集計列の疑いがある追加列: {suspect} "
            f"→ 意図的でなければ /run-mf-invoice-db-setup を再実行して掃除してください (集計は持たない設計)。\n")
    if others:
        stream.write(
            f"     (参考: schema 未知の追加列: {others})\n")
    return residual, extra


def upsert(database_id, rows, token=None, period_ym=None, checked_at=None):
    """rows を customer_id キーで冪等 upsert。作成/更新件数を返す。

    1 顧客=1 ページ。DBプロパティは最新月スナップショット、月次履歴は本文 table block。
    rows: [{customer_id, period_ym, company_name, verdict, prev_amount, curr_amount,
            issue_date?, updated_at?, product_name, checked_at?, run_id?}, ...]
    period_ym: 今回チェックした対象月 (rows が空でも戻り値に含めるため)。
    rows が空なら何もせず {created:0, updated:0, ...} を返す (候補0件月の「チェック済」
    証跡は collect 側が全顧客行で担保する。sink はサマリ行を作らない)。
    """
    token = token or _notion_token()
    checked_at = checked_at or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    run_id = _run_id(checked_at)
    if rows:
        period_ym = period_ym or rows[0]["period_ym"]

    # customer_id でグループ化。DBプロパティは最新 period_ym の行をスナップショットに
    # 採用し、本文 table には同一顧客の全 period_ym 行を upsert する。
    by_customer = {}
    for row in rows:
        cid = row["customer_id"]
        by_customer.setdefault(cid, []).append(row)

    created = updated = 0
    for cid, customer_rows in by_customer.items():
        enriched_rows = []
        for row in sorted(customer_rows, key=lambda r: r.get("period_ym") or ""):
            enriched = dict(row)
            enriched.setdefault("checked_at", checked_at)
            enriched.setdefault("run_id", run_id)
            enriched_rows.append(enriched)
        snapshot = enriched_rows[-1]
        page_id = _find_page(database_id, cid, token)
        if page_id:
            _req("PATCH", f"/pages/{page_id}", token, {"properties": _props(snapshot)})
            for enriched in enriched_rows:
                _upsert_month_row(page_id, enriched, token)
            updated += 1
        else:
            res = _req("POST", "/pages", token, {
                "parent": {"database_id": database_id},
                "properties": _create_props(snapshot),
                "children": [_table_block(
                    [_header_row_block()] + [_table_row_block(_month_values(r)) for r in enriched_rows]
                )],
            })
            _ = res  # 新規ページは作成時に table を同梱済み。追加処理不要。
            created += 1

    # 書き込み完了後に read-only 検知ゲートを 1 回だけ発火 (列削除はしない=参照専用)。
    # 過去 DB に残った旧サマリ/集計列を検知し戻り値へ昇格する。GET 失敗は best-effort で握り潰される。
    residual, extra = warn_residual_summary_columns(database_id, token)
    residual = residual or []
    extra = extra or []
    suspect_summary = suspect_summary_extras(extra)
    return {
        "created": created, "updated": updated, "period_ym": period_ym, "run_id": run_id,
        "residual": residual, "extra": extra, "suspect_summary": suspect_summary,
    }
