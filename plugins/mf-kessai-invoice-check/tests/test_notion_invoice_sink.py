#!/usr/bin/env python3
"""notion_invoice_sink.py の顧客ID集約 + 本文 table 月次履歴ロジックを API なしで検証する。

モデル: upsert キー=customer_id 単独。1顧客=1ページ。月次履歴はページ本文の
table block (1行=1対象年月) に蓄積。月が変わっても新規ページを作らず table 行を追加し、
同月再 sink は既存行を更新して重複しない。月次サマリ行は作らない。
"""
import json
import os
import urllib.error

import pytest

import notion_invoice_sink as sink

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "skills", "run-mf-invoice-db-setup", "schemas", "notion-db-schema.json",
)


def _load_db_schema():
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _table_id_of(page_id):
    return f"table-{page_id}"


def _make_fake_store():
    """urllib を叩かず Notion を模擬する。pages とページ本文 table 行をメモリ保持する。

    返り値の state で作成/更新ページ・table 行を観測できる。
    """
    state = {
        "pages": {},          # page_id -> properties (DBプロパティ最新スナップショット)
        "page_customer": {},  # page_id -> customer_id
        "table_rows": {},     # table_id -> [ {id, cells} ... ] (先頭はヘッダ)
        "page_table": {},     # page_id -> table_id
        "page_tables": {},    # page_id -> [table_id, ...]
        "seq": {"page": 0, "row": 0},
        "calls": [],
    }

    def _cells_to_values(cells):
        return [sink._cell_plain(c) for c in cells]

    def fake_req(method, path, token, body=None):
        state["calls"].append((method, path, body))

        # 顧客ID単独フィルタの query。
        if method == "POST" and path.endswith("/query"):
            cid = body["filter"]["rich_text"]["equals"]
            # 顧客ID 単独フィルタであることを保証 (period_ym の二条件 and でない)。
            assert body["filter"]["property"] == "顧客ID"
            assert "and" not in body["filter"]
            hits = [{"id": pid} for pid, c in state["page_customer"].items() if c == cid]
            return {"results": hits}

        # 新規ページ作成 (properties + children=[table])。
        if method == "POST" and path == "/pages":
            state["seq"]["page"] += 1
            pid = f"page-{state['seq']['page']}"
            state["pages"][pid] = body["properties"]
            cid = body["properties"]["顧客ID"]["rich_text"][0]["text"]["content"]
            state["page_customer"][pid] = cid
            # children の table を取り込む。
            children = body.get("children", [])
            tables = [c for c in children if c.get("type") == "table"]
            assert tables, "新規ページは children に table を含むべき"
            tid = _table_id_of(pid)
            state["page_table"][pid] = tid
            state["page_tables"][pid] = [tid]
            rows = []
            for r in tables[0]["table"]["children"]:
                state["seq"]["row"] += 1
                rows.append({"id": f"row-{state['seq']['row']}", "cells": r["table_row"]["cells"]})
            state["table_rows"][tid] = rows
            return {"id": pid}

        # プロパティ更新 (最新月スナップショット)。
        if method == "PATCH" and path.startswith("/pages/"):
            pid = path.split("/pages/")[1]
            state["pages"][pid] = body["properties"]
            return {}

        # ページ本文の children 取得 (table ブロック探索)。
        if method == "GET" and path.startswith("/blocks/") and "/children" in path:
            bid = path.split("/blocks/")[1].split("/")[0]
            if bid in state["page_table"]:  # ページ本文の取得 → table ブロックを返す
                tids = state.get("page_tables", {}).get(bid) or [state["page_table"][bid]]
                return {"results": [{"id": tid, "type": "table"} for tid in tids]}
            if bid in state["table_rows"]:  # table 配下の行群 (実 Notion 同様 100件/ページで分割)
                qs = path.split("?", 1)[1] if "?" in path else ""
                params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
                page_size = int(params.get("page_size", "100"))
                start = int(params.get("start_cursor", "0"))
                all_rows = state["table_rows"][bid]
                chunk = all_rows[start:start + page_size]
                resp = {"results": [{"id": r["id"], "type": "table_row",
                                     "table_row": {"cells": r["cells"]}} for r in chunk]}
                nxt = start + page_size
                if nxt < len(all_rows):
                    resp["has_more"] = True
                    resp["next_cursor"] = str(nxt)
                else:
                    resp["has_more"] = False
                return resp
            return {"results": []}

        # 既存行更新 (同月再実行)。
        if method == "PATCH" and path.startswith("/blocks/") and "/children" not in path:
            rid = path.split("/blocks/")[1]
            for tid, rows in state["table_rows"].items():
                for r in rows:
                    if r["id"] == rid:
                        r["cells"] = body["table_row"]["cells"]
                        return {}
            raise AssertionError(f"unknown row id {rid}")

        # 行/テーブル追加。
        if method == "PATCH" and path.startswith("/blocks/") and "/children" in path:
            bid = path.split("/blocks/")[1].split("/")[0]
            if bid in state["table_rows"]:  # 既存 table へ行追加
                for c in body["children"]:
                    state["seq"]["row"] += 1
                    state["table_rows"][bid].append(
                        {"id": f"row-{state['seq']['row']}", "cells": c["table_row"]["cells"]})
                return {}
            # ページへ table 新規 append (後方移行)。
            tables = [c for c in body["children"] if c.get("type") == "table"]
            assert tables
            tid = _table_id_of(bid)
            state["page_table"][bid] = tid
            state["page_tables"].setdefault(bid, []).append(tid)
            rows = []
            for r in tables[0]["table"]["children"]:
                state["seq"]["row"] += 1
                rows.append({"id": f"row-{state['seq']['row']}", "cells": r["table_row"]["cells"]})
            state["table_rows"][tid] = rows
            return {}

        raise AssertionError((method, path, body))

    state["_cells_to_values"] = _cells_to_values
    return fake_req, state


class _FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


# ---------------------------------------------------------------------------

def test_req_retries_transient_notion_429(monkeypatch):
    """Notion 429 は Retry-After を尊重して再試行し、成功レスポンスを返す。"""
    calls = []
    sleeps = []

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, timeout))
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                req.full_url, 429, "rate limited", {"Retry-After": "0"}, None)
        return _FakeHTTPResponse({"ok": True})

    monkeypatch.setattr(sink.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sink.time, "sleep", lambda delay: sleeps.append(delay))
    assert sink._req("GET", "/pages/x", "token") == {"ok": True}
    assert len(calls) == 2
    assert sleeps == [0.0]

def test_props_snapshot_fact_columns_only():
    """_props は最新月スナップショットの事実列のみ。削除/改名した列の扱いを固定する。"""
    row = {
        "customer_id": "c1",
        "period_ym": "2026-06",
        "company_name": "A社",
        "verdict": "発行漏れ候補",
        "product_name": "SaaS",
        "prev_amount": 100,
        "curr_amount": None,
        "checked_at": "2026-06-20T00:00:00+00:00",
        "run_id": "mfk-20260620",
    }
    props = sink._props(row)
    assert props["取引先企業名"]["title"][0]["text"]["content"] == "A社"
    assert props["顧客ID"]["rich_text"][0]["text"]["content"] == "c1"
    assert props["対象年月"]["rich_text"][0]["text"]["content"] == "2026-06"
    # 改名: 表示名は「今月の発行状況」、値 (verdict) は不変。
    assert props["今月の発行状況"]["select"]["name"] == "発行漏れ候補"
    assert props["確認済み日時"]["date"]["start"] == "2026-06-20T00:00:00+00:00"
    # 改名前の旧プロパティ名は書かない。
    assert "判定" not in props
    # 削除したプロパティを書かない (run_id があっても チェック実行ID を書かない)。
    assert "チェック実行ID" not in props
    assert "初回請求月(API推定)" not in props
    # 月次サマリ廃止に伴い削除した列を持たないこと。
    assert "レコード種別" not in props
    assert "発行漏れ件数" not in props
    assert "金額変動件数" not in props
    assert "チェック件数合計" not in props
    assert "初回契約月" not in props


def test_sink_emits_every_declared_fact_column():
    """schema SSOT の fact_columns 全列が sink から漏れなく出力される (silent drop の機械保証)。

    fact_column を schema に足したのに `_props`/`_create_props` への配線を忘れると、Notion DB に
    列はあっても値が入らない (今回の `初回請求月(API推定)` 実バグの再現条件)。schema を正本に
    「完全な行を渡せば全 fact_column が出力キーへ通る」ことを機械検査し、CI で回帰を止める。
    これがプロンプト指示でなく仕組みで『100%構築される』を担保する層。
    """
    schema = _load_db_schema()
    fact_columns = set(schema["fact_columns"])
    managed_columns = set(schema["managed_columns"])
    # 全 fact_column の元データを埋めた行 (条件付き列 発行日/更新日/確認済み日時 含む)。
    complete_row = {
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "継続発行", "product_name": "SaaS",
        "prev_amount": 100, "curr_amount": 120,
        "issue_date": "2026-06-05", "updated_at": "2026-06-06T00:00:00+00:00",
        "checked_at": "2026-06-20T00:00:00+00:00", "run_id": "mfk-x",
    }
    update_keys = set(sink._props(complete_row))
    create_keys = set(sink._create_props(complete_row))
    assert not (fact_columns - update_keys), \
        f"_props が出力しない fact_column: {sorted(fact_columns - update_keys)}"
    assert not (fact_columns - create_keys), \
        f"_create_props が出力しない fact_column: {sorted(fact_columns - create_keys)}"
    # 既存ページ更新 (_props) は managed_column を一切書かない (人の運用記入を上書きしない)。
    assert not (managed_columns & update_keys), \
        f"_props が managed_column を書いている: {sorted(managed_columns & update_keys)}"
    # 新規作成 (_create_props) は managed_column のうち 初回契約月 のみ空欄初期化する。
    assert managed_columns & create_keys == {"初回契約月"}


def test_create_props_initializes_initial_contract_month_blank():
    """新規ページだけ初回契約月を空欄初期化し、既存更新用 _props には混ぜない。

    支払サイクルは月次 sink/新規作成で初期化しない (人が設定する managed 列)。
    """
    row = {
        "customer_id": "c1",
        "period_ym": "2026-06",
        "company_name": "A社",
        "verdict": "今月新規",
        "product_name": "SaaS",
        "prev_amount": None,
        "curr_amount": 100,
    }
    props = sink._create_props(row)
    assert props["初回契約月"]["rich_text"][0]["text"]["content"] == ""
    # 支払サイクルは新規作成時も書き込まない (空欄=未設定で人が選ぶ)。
    assert "支払サイクル" not in props
    assert "初回契約月" not in sink._props(row)


def test_table_block_structure_header_and_cells():
    """新規ページの table は固定5列・has_column_header、空セルも content="" を持つ。"""
    block = sink._table_block([sink._header_row_block(),
                               sink._table_row_block(["2026-06", "発行漏れ候補", "100", "", "ca"])])
    assert block["type"] == "table"
    assert block["table"]["table_width"] == 5
    assert block["table"]["has_column_header"] is True
    header = block["table"]["children"][0]
    assert [sink._cell_plain(c) for c in header["table_row"]["cells"]] == sink.TABLE_COLUMNS
    data = block["table"]["children"][1]
    # 空セルは [] でなく content="" の text 1 つ。
    empty_cell = data["table_row"]["cells"][3]
    assert empty_cell == [{"type": "text", "text": {"content": ""}}]


def test_upsert_new_customer_creates_page_with_table(monkeypatch):
    """新規顧客 → POST /pages に children table を含めて1ページ作成 (created=1)。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    rows = [{
        "customer_id": "c1",
        "period_ym": "2026-06",
        "company_name": "A社",
        "verdict": "発行漏れ候補",
        "product_name": "SaaS",
        "prev_amount": 100,
        "curr_amount": None,
    }]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")
    assert result["created"] == 1
    assert result["updated"] == 0
    assert result["period_ym"] == "2026-06"

    # ページは1つだけ。月次サマリ用の追加ページを作らない。
    assert len(state["pages"]) == 1
    pid = next(iter(state["pages"]))
    assert state["pages"][pid]["初回契約月"]["rich_text"][0]["text"]["content"] == ""
    rows_in_table = state["table_rows"][state["page_table"][pid]]
    # ヘッダ + 当月1行 = 2 行。
    assert len(rows_in_table) == 2
    assert state["_cells_to_values"](rows_in_table[0]["cells"]) == sink.TABLE_COLUMNS
    assert state["_cells_to_values"](rows_in_table[1]["cells"])[0] == "2026-06"


def test_upsert_same_month_is_idempotent_updates_row(monkeypatch):
    """同月の再 sink は既存ページ更新 + table 行を更新し、行を重複させない。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    rows = [{
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "発行漏れ候補", "product_name": "SaaS",
        "prev_amount": 100, "curr_amount": None,
    }]
    sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")

    # 2 回目: 金額を変えて同月再実行。
    rows2 = [dict(rows[0], curr_amount=200)]
    result = sink.upsert("db1", rows2, token="token", checked_at="2026-06-21T00:00:00+00:00")
    assert result["created"] == 0
    assert result["updated"] == 1

    assert len(state["pages"]) == 1  # 新規ページを作らない
    pid = next(iter(state["pages"]))
    rows_in_table = state["table_rows"][state["page_table"][pid]]
    # ヘッダ + 当月1行のまま (重複なし)。
    assert len(rows_in_table) == 2
    vals = state["_cells_to_values"](rows_in_table[1]["cells"])
    assert vals[0] == "2026-06"
    assert vals[3] == "200"  # 今月金額が更新されている


def test_upsert_new_month_appends_row_same_page(monkeypatch):
    """別月の sink は同一顧客ページに table 行を追加し、新規ページを作らない。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    rows_jun = [{
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "発行漏れ候補", "product_name": "SaaS",
        "prev_amount": 100, "curr_amount": None,
    }]
    sink.upsert("db1", rows_jun, token="token", checked_at="2026-06-20T00:00:00+00:00")

    rows_jul = [{
        "customer_id": "c1", "period_ym": "2026-07", "company_name": "A社",
        "verdict": "継続発行", "product_name": "SaaS",
        "prev_amount": 100, "curr_amount": 120,
    }]
    result = sink.upsert("db1", rows_jul, token="token", checked_at="2026-07-20T00:00:00+00:00")
    assert result["created"] == 0
    assert result["updated"] == 1

    assert len(state["pages"]) == 1  # 新規ページを作らない
    pid = next(iter(state["pages"]))
    rows_in_table = state["table_rows"][state["page_table"][pid]]
    # ヘッダ + 6月 + 7月 = 3 行。
    assert len(rows_in_table) == 3
    period_col = [state["_cells_to_values"](r["cells"])[0] for r in rows_in_table[1:]]
    assert period_col == ["2026-06", "2026-07"]
    # DBプロパティは最新月 (7月) スナップショット。
    assert state["pages"][pid]["対象年月"]["rich_text"][0]["text"]["content"] == "2026-07"
    assert state["pages"][pid]["今月の発行状況"]["select"]["name"] == "継続発行"


def test_upsert_multi_month_same_customer_keeps_all_history_rows(monkeypatch):
    """同一入力に同一顧客の複数月があっても、最新月だけに潰さず全月を table に残す。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    rows = [
        {"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
         "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None},
        {"customer_id": "c1", "period_ym": "2026-07", "company_name": "A社",
         "verdict": "継続発行", "product_name": "SaaS", "prev_amount": 100, "curr_amount": 120},
    ]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-07-20T00:00:00+00:00")

    assert result["created"] == 1
    assert result["updated"] == 0
    assert len(state["pages"]) == 1
    pid = next(iter(state["pages"]))
    rows_in_table = state["table_rows"][state["page_table"][pid]]
    assert len(rows_in_table) == 3  # header + 6月 + 7月
    period_col = [state["_cells_to_values"](r["cells"])[0] for r in rows_in_table[1:]]
    assert period_col == ["2026-06", "2026-07"]
    # DBプロパティは最新月スナップショット。
    assert state["pages"][pid]["対象年月"]["rich_text"][0]["text"]["content"] == "2026-07"
    assert state["pages"][pid]["今月金額"]["number"] == 120


def test_upsert_multi_month_same_customer_existing_page_updates_all_rows(monkeypatch):
    """既存ページでも複数月入力の各月行を upsert し、最新月だけに落とさない。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    sink.upsert("db1", [{
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None,
    }], token="token", checked_at="2026-06-20T00:00:00+00:00")

    rows = [
        {"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
         "verdict": "継続発行", "product_name": "SaaS", "prev_amount": 100, "curr_amount": 110},
        {"customer_id": "c1", "period_ym": "2026-07", "company_name": "A社",
         "verdict": "継続発行", "product_name": "SaaS", "prev_amount": 110, "curr_amount": 120},
    ]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-07-20T00:00:00+00:00")

    assert result["created"] == 0
    assert result["updated"] == 1
    pid = next(iter(state["pages"]))
    rows_in_table = state["table_rows"][state["page_table"][pid]]
    assert len(rows_in_table) == 3  # header + 6月更新 + 7月追加
    by_period = {state["_cells_to_values"](r["cells"])[0]: state["_cells_to_values"](r["cells"])
                 for r in rows_in_table[1:]}
    assert by_period["2026-06"][3] == "110"
    assert by_period["2026-07"][3] == "120"


def test_upsert_does_not_create_summary_row(monkeypatch):
    """月次サマリ行/サマリページを一切作らない (__monthly_summary__ モデル廃止)。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    rows = [
        {"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
         "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None},
        {"customer_id": "c2", "period_ym": "2026-06", "company_name": "B社",
         "verdict": "継続発行", "product_name": "Sub", "prev_amount": 200, "curr_amount": 200},
    ]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")
    # 2 顧客ぶんのページのみ。サマリページ (合計3) を作らない。
    assert result["created"] == 2
    assert len(state["pages"]) == 2
    customers = set(state["page_customer"].values())
    assert customers == {"c1", "c2"}
    # サマリ専用顧客IDのページが存在しないこと。
    assert "__monthly_summary__" not in customers
    # サマリ用に複数行作る POST も起きていない (各顧客1ページ)。
    page_posts = [c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages"]
    assert len(page_posts) == 2


def test_upsert_empty_rows_noop(monkeypatch):
    """rows が空なら何もせず created/updated=0。サマリ行も作らない。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    result = sink.upsert("db1", [], token="token", period_ym="2026-07",
                         checked_at="2026-07-20T00:00:00+00:00")
    assert result["created"] == 0
    assert result["updated"] == 0
    assert result["period_ym"] == "2026-07"
    # 一切の書き込み API を呼ばない。
    writes = [c for c in state["calls"] if c[0] in ("POST", "PATCH")]
    assert writes == []


# --- I2 冪等性の境界条件 (独立レビューのミューテーションで未カバーが実証された3点) ------

def _seed_page_with_months(state, cid, months):
    """page + 本文 table を state へ直接構築する (months=period_ym のリスト)。

    upsert を何百回も回さずに「長い月次履歴」を作るためのテスト用ヘルパ。
    table_rows[tid] は先頭ヘッダ + 各月 1 行。
    """
    state["seq"]["page"] += 1
    pid = f"page-{state['seq']['page']}"
    state["pages"][pid] = {"顧客ID": {"rich_text": [{"text": {"content": cid}}]}}
    state["page_customer"][pid] = cid
    tid = _table_id_of(pid)
    state["page_table"][pid] = tid
    state["page_tables"][pid] = [tid]
    state["seq"]["row"] += 1
    rows = [{"id": f"row-{state['seq']['row']}",
             "cells": [sink._cell(c) for c in sink.TABLE_COLUMNS]}]  # header
    for ym in months:
        state["seq"]["row"] += 1
        vals = [ym, "継続発行", "100", "100", "2026-06-20T00:00:00+00:00"]
        rows.append({"id": f"row-{state['seq']['row']}", "cells": [sink._cell(v) for v in vals]})
    state["table_rows"][tid] = rows
    return pid, tid


def _seed_foreign_table_before_history(state, pid):
    """ページ本文の先頭に月次履歴ではない table を差し込む。"""
    foreign_tid = f"foreign-{pid}"
    state["seq"]["row"] += 1
    state["table_rows"][foreign_tid] = [{
        "id": f"row-{state['seq']['row']}",
        "cells": [sink._cell("別用途"), sink._cell("メモ")],
    }]
    state["page_tables"][pid] = [foreign_tid] + state["page_tables"][pid]
    return foreign_tid


def test_find_page_raises_on_duplicate_customer_id(monkeypatch):
    """同一顧客IDで2ページ存在 → _find_page は冪等キー破壊として RuntimeError を送出する。

    (独立レビューの M4: len(items)>1 を len(items)>99 に緩めても従来テストは緑のまま
    通過し、この経路が未カバーだったことが実証された。その死角を塞ぐ。)
    """
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    # 同じ customer_id を持つページを 2 つ仕込む。
    state["page_customer"] = {"page-1": "c1", "page-2": "c1"}
    state["pages"] = {"page-1": {}, "page-2": {}}
    with pytest.raises(RuntimeError, match="重複ページ検出"):
        sink._find_page("db1", "c1", "token")


def test_upsert_paginates_beyond_100_rows_no_duplicate(monkeypatch):
    """100行超の月次履歴で、2ページ目にある対象月を再 sink しても重複追記しない (I2)。

    (独立レビューの M3: _all_block_children のカーソル追従を先頭ページのみ取得に改変しても
    従来テストは緑のまま通過し、ページネーション境界が未カバーだったことが実証された。
    fake ストアを実 Notion 同様 100件/ページ分割に拡張し、その死角を塞ぐ。)
    """
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    months = [f"{y}-{m:02d}" for y in range(2016, 2027) for m in range(1, 13)]  # 132 月
    target = months[120]  # ヘッダ込みで index 121 → 2 ページ目 (先頭100件の外)
    pid, tid = _seed_page_with_months(state, "c1", months)
    before = len(state["table_rows"][tid])  # header + 132 = 133

    # ページネーションで全件辿れること (先頭100件のみなら件数が一致しない)。
    fetched = sink._all_block_children(tid, "token")
    assert len(fetched) == before

    # 2 ページ目にある対象月を再 sink → 既存行を更新し、重複追記しない。
    row = {"customer_id": "c1", "period_ym": target, "company_name": "A社",
           "verdict": "継続発行", "product_name": "SaaS", "prev_amount": 100, "curr_amount": 999}
    sink._upsert_month_row(pid, row, "token")
    after = len(state["table_rows"][tid])
    assert after == before, "2ページ目の既存行を取りこぼして重複追記していないこと"
    matching = [r for r in state["table_rows"][tid]
                if sink._cell_plain(r["cells"][0]) == target]
    assert len(matching) == 1
    assert sink._cell_plain(matching[0]["cells"][3]) == "999", "対象月の既存行が更新されている"


def test_upsert_same_month_updates_correct_row_in_multirow_table(monkeypatch):
    """複数月が並ぶ table で同月を再 sink → 正しい行 (当月) だけを更新し他月行を触らない (I2)。

    period_ym マッチが『正しい行』を選ぶことの検証 (単一行 table では担保できない死角)。
    """
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    base = {"customer_id": "c1", "company_name": "A社", "product_name": "SaaS", "prev_amount": 100}
    sink.upsert("db1", [dict(base, period_ym="2026-06", verdict="発行漏れ候補", curr_amount=None)],
                token="t", checked_at="2026-06-20T00:00:00+00:00")
    sink.upsert("db1", [dict(base, period_ym="2026-07", verdict="継続発行", curr_amount=120)],
                token="t", checked_at="2026-07-20T00:00:00+00:00")
    # 6月を金額変更して再 sink。
    sink.upsert("db1", [dict(base, period_ym="2026-06", verdict="継続発行", curr_amount=555)],
                token="t", checked_at="2026-06-25T00:00:00+00:00")

    pid = next(iter(state["pages"]))
    rows = state["table_rows"][state["page_table"][pid]]
    assert len(rows) == 3, "ヘッダ + 6月 + 7月 = 3 行のまま (新規行を作らない)"
    by_period = {sink._cell_plain(r["cells"][0]): r for r in rows[1:]}
    assert sink._cell_plain(by_period["2026-06"]["cells"][3]) == "555", "6月行が更新されている"
    assert sink._cell_plain(by_period["2026-07"]["cells"][3]) == "120", "7月行は触られていない"


def test_upsert_uses_table_with_matching_header_not_first_table(monkeypatch):
    """ページ本文の先頭に別 table があっても、固定ヘッダを持つ月次履歴 table だけを更新する。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    pid, history_tid = _seed_page_with_months(state, "c1", ["2026-06"])
    foreign_tid = _seed_foreign_table_before_history(state, pid)
    before_foreign = list(state["table_rows"][foreign_tid])

    row = {"customer_id": "c1", "period_ym": "2026-07", "company_name": "A社",
           "verdict": "継続発行", "product_name": "SaaS", "prev_amount": 100, "curr_amount": 120}
    sink._upsert_month_row(pid, row, "token")

    assert state["table_rows"][foreign_tid] == before_foreign
    periods = [sink._cell_plain(r["cells"][0]) for r in state["table_rows"][history_tid][1:]]
    assert periods == ["2026-06", "2026-07"]


# --- 年間契約抑制 reader: fetch_initial_contract_months ({customer_id: 契約情報}) ----------

def _rt_prop(value):
    """rich_text プロパティを Notion API レスポンス形に組む。"""
    return {"rich_text": [{"text": {"content": value}, "plain_text": value}]} if value else {"rich_text": []}


def _select_prop(value):
    return {"select": {"name": value}} if value else {"select": None}


def _page(cid, month, cycle="年間払い"):
    return {"properties": {
        "顧客ID": _rt_prop(cid),
        "初回契約月": _rt_prop(month),
        "支払サイクル": _select_prop(cycle),
    }}


def test_fetch_initial_contract_months_maps_customer_to_month(monkeypatch):
    """年間払い顧客だけを {customer_id: 契約情報} に写像する。"""
    def fake_req(method, path, token, body=None):
        assert method == "POST" and path.endswith("/query")
        return {"results": [_page("c1", "2026-04"), _page("c2", "2025-12")], "has_more": False}

    monkeypatch.setattr(sink, "_req", fake_req)
    result = sink.fetch_initial_contract_months("db1", token="t")
    assert result == {
        "c1": {"initial_contract_month": "2026-04", "payment_cycle": "年間払い"},
        "c2": {"initial_contract_month": "2025-12", "payment_cycle": "年間払い"},
    }


def test_fetch_initial_contract_months_skips_blank_and_invalid(monkeypatch):
    """初回契約月/支払サイクルが抑制条件を満たさない顧客は含めない。"""
    def fake_req(method, path, token, body=None):
        return {"results": [
            _page("ok", "2026-04"),
            _page("blank", ""),          # 空 → 除外
            _page("bad", "2026/04"),      # YYYY-MM でない → 除外
            _page("monthly", "2026-04", "月払い"),  # 月払い → 除外
            _page("nocycle", "2026-04", ""),         # cycle 空 → 除外
            _page("", "2026-05"),         # 顧客IDなし → 除外
        ], "has_more": False}

    monkeypatch.setattr(sink, "_req", fake_req)
    result = sink.fetch_initial_contract_months("db1", token="t")
    assert result == {"ok": {"initial_contract_month": "2026-04", "payment_cycle": "年間払い"}}


def test_fetch_initial_contract_months_paginates(monkeypatch):
    """has_more/next_cursor を辿って全ページ取得する (100件超の DB を取りこぼさない)。"""
    pages = [
        {"results": [_page("c1", "2026-01")], "has_more": True, "next_cursor": "cur2"},
        {"results": [_page("c2", "2026-02")], "has_more": False},
    ]
    seen_cursors = []

    def fake_req(method, path, token, body=None):
        seen_cursors.append((body or {}).get("start_cursor"))
        return pages.pop(0)

    monkeypatch.setattr(sink, "_req", fake_req)
    result = sink.fetch_initial_contract_months("db1", token="t")
    assert result == {
        "c1": {"initial_contract_month": "2026-01", "payment_cycle": "年間払い"},
        "c2": {"initial_contract_month": "2026-02", "payment_cycle": "年間払い"},
    }
    # 1ページ目は cursor なし、2ページ目は next_cursor を引き継ぐ。
    assert seen_cursors == [None, "cur2"]


def test_fetch_initial_contract_months_uses_token_arg_without_keychain(monkeypatch):
    """token を渡せば Keychain (_notion_token) を呼ばずに済む (_notion_token 自体は触らない)。"""
    def fake_req(method, path, token, body=None):
        assert token == "explicit-token"
        return {"results": [], "has_more": False}

    monkeypatch.setattr(sink, "_req", fake_req)
    # _notion_token を呼んだら失敗させ、token 引数経路だけを通すことを保証する。
    monkeypatch.setattr(sink, "_notion_token",
                        lambda: (_ for _ in ()).throw(AssertionError("_notion_token を呼ぶべきでない")))
    assert sink.fetch_initial_contract_months("db1", token="explicit-token") == {}


# --- 改名 B: _find_table_id の後方互換 (旧 判定 ヘッダ / 新 今月の発行状況 ヘッダ) ----------

def _seed_page_with_header(state, cid, header):
    """指定ヘッダだけを持つ table を本文に持つページを直接構築する (data 行なし)。"""
    state["seq"]["page"] += 1
    pid = f"page-{state['seq']['page']}"
    state["pages"][pid] = {"顧客ID": {"rich_text": [{"text": {"content": cid}}]}}
    state["page_customer"][pid] = cid
    tid = _table_id_of(pid)
    state["page_table"][pid] = tid
    state["page_tables"][pid] = [tid]
    state["seq"]["row"] += 1
    state["table_rows"][tid] = [
        {"id": f"row-{state['seq']['row']}", "cells": [sink._cell(c) for c in header]}
    ]
    return pid, tid


def test_table_columns_renamed_and_legacy_defined():
    """新ヘッダは 今月の発行状況、旧ヘッダ (判定) は LEGACY 定数で別名保持される。"""
    assert sink.TABLE_COLUMNS == ["対象年月", "今月の発行状況", "前月金額", "今月金額", "確認済み日時"]
    assert sink.TABLE_COLUMNS_LEGACY == ["対象年月", "判定", "前月金額", "今月金額", "確認済み日時"]


def test_find_table_id_matches_new_header(monkeypatch):
    """新ヘッダ (今月の発行状況) の月次履歴 table を _find_table_id が拾う。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    pid, tid = _seed_page_with_header(state, "c1", sink.TABLE_COLUMNS)
    assert sink._find_table_id(pid, "token") == tid


def test_find_table_id_matches_legacy_header(monkeypatch):
    """旧ヘッダ (判定) の既存 table も後方互換で拾い、二重 table append を防ぐ。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    pid, tid = _seed_page_with_header(state, "c1", sink.TABLE_COLUMNS_LEGACY)
    assert sink._find_table_id(pid, "token") == tid


def test_find_table_id_ignores_unrelated_table(monkeypatch):
    """新旧いずれのヘッダにも一致しない table は月次履歴と見なさない (None)。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    pid, _tid = _seed_page_with_header(state, "c1", ["別用途", "メモ"])
    assert sink._find_table_id(pid, "token") is None


def test_upsert_into_legacy_header_table_no_duplicate(monkeypatch):
    """旧ヘッダ table を持つ既存ページへ別月 sink → 同じ table へ追記し二重 table を作らない。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    # 旧ヘッダ (判定) + 6月行 1 件を持つ既存ページを仕込む。
    state["seq"]["page"] += 1
    pid = f"page-{state['seq']['page']}"
    state["pages"][pid] = {"顧客ID": {"rich_text": [{"text": {"content": "c1"}}]}}
    state["page_customer"][pid] = "c1"
    tid = _table_id_of(pid)
    state["page_table"][pid] = tid
    state["page_tables"][pid] = [tid]
    state["seq"]["row"] += 1
    rows = [{"id": f"row-{state['seq']['row']}",
             "cells": [sink._cell(c) for c in sink.TABLE_COLUMNS_LEGACY]}]
    state["seq"]["row"] += 1
    rows.append({"id": f"row-{state['seq']['row']}",
                 "cells": [sink._cell(v) for v in
                           ["2026-06", "継続発行", "100", "100", "2026-06-20T00:00:00+00:00"]]})
    state["table_rows"][tid] = rows

    row = {"customer_id": "c1", "period_ym": "2026-07", "company_name": "A社",
           "verdict": "継続発行", "product_name": "SaaS", "prev_amount": 100, "curr_amount": 120}
    sink._upsert_month_row(pid, row, "token")

    # 既存 (旧ヘッダ) table が 1 つだけのまま、行が追記される (新 table を作らない)。
    assert state["page_tables"][pid] == [tid]
    periods = [sink._cell_plain(r["cells"][0]) for r in state["table_rows"][tid][1:]]
    assert periods == ["2026-06", "2026-07"]


# --- CL4 一元化: _notion_token の service 解決順 (env > config > default), MF 側と対称 -----

def _clear_notion_env(monkeypatch):
    for k in ("NOTION_API_KEY", "NOTION_KEYCHAIN_SERVICE", "NOTION_KEYCHAIN_ACCOUNT"):
        monkeypatch.delenv(k, raising=False)


def test_notion_service_default_when_no_env_no_config(monkeypatch):
    """env も config(notion.keychain_service) も無ければ既定 notion-api-key.<keychain-prefix>。"""
    _clear_notion_env(monkeypatch)
    monkeypatch.setenv("HARNESS_KEYCHAIN_PREFIX", "test-tenant")
    # config を空 dict にして load_config 経由の差し込みを排除する。
    assert sink._notion_service({}) == "notion-api-key.test-tenant"
    assert sink._notion_account({}) == "test-tenant"


def test_notion_service_resolved_from_config(monkeypatch):
    """config(notion.keychain_service/account) を解決できる (MF 側 keychain_service と対称)。"""
    _clear_notion_env(monkeypatch)
    cfg = {"notion": {"keychain_service": "notion-cfg", "keychain_account": "acc-cfg"}}
    assert sink._notion_service(cfg) == "notion-cfg"
    assert sink._notion_account(cfg) == "acc-cfg"


def test_notion_service_env_overrides_config(monkeypatch):
    """env(NOTION_KEYCHAIN_SERVICE) が config より優先される。"""
    _clear_notion_env(monkeypatch)
    monkeypatch.setenv("NOTION_KEYCHAIN_SERVICE", "notion-env")
    monkeypatch.setenv("NOTION_KEYCHAIN_ACCOUNT", "acc-env")
    cfg = {"notion": {"keychain_service": "notion-cfg", "keychain_account": "acc-cfg"}}
    assert sink._notion_service(cfg) == "notion-env"
    assert sink._notion_account(cfg) == "acc-env"


def test_notion_token_env_api_key_short_circuits(monkeypatch):
    """NOTION_API_KEY があれば Keychain を呼ばず env トークンを strip して返す (従来挙動維持)。"""
    _clear_notion_env(monkeypatch)
    monkeypatch.setenv("NOTION_API_KEY", "  env-token  ")
    # fetch_secret を呼んだら失敗させ、env 経路だけを通すことを保証する。
    import mfk_keychain as kc
    monkeypatch.setattr(kc, "fetch_secret",
                        lambda *a, **k: pytest.fail("env トークンがあれば Keychain を呼ぶべきでない"))
    assert sink._notion_token({}) == "env-token"


def test_notion_token_uses_resolved_service_via_fetch_secret(monkeypatch):
    """_notion_token は config 解決した service/account で共通コア fetch_secret を呼ぶ。"""
    _clear_notion_env(monkeypatch)
    captured = {}
    import mfk_keychain as kc

    def fake_fetch(service, account):
        captured["service"] = service
        captured["account"] = account
        return "tok-from-keychain"

    monkeypatch.setattr(kc, "fetch_secret", fake_fetch)
    cfg = {"notion": {"keychain_service": "svc-x", "keychain_account": "acc-x"}}
    assert sink._notion_token(cfg) == "tok-from-keychain"
    assert captured == {"service": "svc-x", "account": "acc-x"}


def test_notion_token_raises_when_keychain_miss(monkeypatch):
    """env も Keychain も無ければ RuntimeError (service/account を含むメッセージ)。"""
    _clear_notion_env(monkeypatch)
    import mfk_keychain as kc
    monkeypatch.setattr(kc, "fetch_secret", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="Notion token lookup failed"):
        sink._notion_token({})


# --- backward remediation: 月次フローの read-only 旧サマリ/余剰列 検知ゲート ----------------
#  forward 生成防止 (sink/schema/test) と対をなす、過去に DB へ作られ残った旧サマリ列を
#  月次 upsert 後に read-only で検知し誘導する経路の回帰固定。列削除は決してしない。

class _RecordStream:
    """warn_residual_summary_columns の stderr 出力を捕捉する簡易ストリーム。"""

    def __init__(self):
        self.text = ""

    def write(self, s):
        self.text += s


def _props_from_schema(schema, *, extra=(), residual=()):
    """schema の現行列 + 任意の extra/residual を載せた live DB properties を組む。"""
    props = {name: {"type": spec["type"]} for name, spec in schema["properties"].items()}
    for name in residual:  # deprecated に属する旧列を残存させる
        props[name] = {"type": "number"}
    for name in extra:  # schema 未知の余剰列 (手動追加サマリ列を含む)
        props[name] = {"type": "number"}
    return props


def test_residual_extra_columns_clean():
    """旧列も余剰列も無ければ (residual, extra) は両方空 (純関数の境界)。"""
    schema = _load_db_schema()
    props = _props_from_schema(schema)
    assert sink.residual_extra_columns(props, schema) == ([], [])


def test_residual_extra_columns_detects_deprecated_residual():
    """deprecated 列 (旧サマリ件数列) が残っていれば residual に挙がる。"""
    schema = _load_db_schema()
    dep = schema["deprecated_properties"][0]  # 例: レコード種別
    props = _props_from_schema(schema, residual=[dep])
    residual, extra = sink.residual_extra_columns(props, schema)
    assert residual == [dep]
    assert extra == []


def test_residual_extra_columns_detects_total_summary_as_residual():
    """全体トータル列は削除対象の既知サマリ列として residual に挙がる。"""
    schema = _load_db_schema()
    props = _props_from_schema(schema, residual=["全体トータル"])
    residual, extra = sink.residual_extra_columns(props, schema)
    assert residual == ["全体トータル"]
    assert extra == []


def test_residual_extra_columns_detects_unknown_extra():
    """schema 未知かつ deprecated でもない手動追加列は extra として検出される。"""
    schema = _load_db_schema()
    props = _props_from_schema(schema, extra=["任意メモ"])
    residual, extra = sink.residual_extra_columns(props, schema)
    assert residual == []
    assert extra == ["任意メモ"]


def test_warn_residual_emits_stderr_when_residual_present(monkeypatch):
    """upsert 後の検知ゲート: 旧サマリ列が残っていれば stderr に誘導が1行出る。"""
    schema = _load_db_schema()
    dep = schema["deprecated_properties"][0]
    props = _props_from_schema(schema, residual=[dep])
    monkeypatch.setattr(sink, "_req",
                        lambda method, path, token, body=None: {"properties": props})
    stream = _RecordStream()
    residual, extra = sink.warn_residual_summary_columns("db1", "token", schema=schema, stream=stream)
    assert residual == [dep]
    assert dep in stream.text
    assert "/run-mf-invoice-db-setup" in stream.text


def test_warn_residual_emits_stderr_when_total_summary_present(monkeypatch):
    """手動追加された全体トータル列も削除対象 residual として誘導 stderr が出る。"""
    schema = _load_db_schema()
    props = _props_from_schema(schema, residual=["全体トータル"])
    monkeypatch.setattr(sink, "_req",
                        lambda method, path, token, body=None: {"properties": props})
    stream = _RecordStream()
    residual, extra = sink.warn_residual_summary_columns("db1", "token", schema=schema, stream=stream)
    assert residual == ["全体トータル"]
    assert extra == []
    assert "全体トータル" in stream.text


def test_warn_residual_silent_when_clean(monkeypatch):
    """残骸が無ければ stderr に何も出さない (誤警告しない)。"""
    schema = _load_db_schema()
    props = _props_from_schema(schema)
    monkeypatch.setattr(sink, "_req",
                        lambda method, path, token, body=None: {"properties": props})
    stream = _RecordStream()
    residual, extra = sink.warn_residual_summary_columns("db1", "token", schema=schema, stream=stream)
    assert (residual, extra) == ([], [])
    assert stream.text == ""


def test_warn_residual_best_effort_on_get_failure(monkeypatch):
    """Notion GET が失敗しても例外を握り潰し検知のみスキップ (本体を止めない)。"""
    def boom(method, path, token, body=None):
        raise RuntimeError("Notion 不通")

    monkeypatch.setattr(sink, "_req", boom)
    stream = _RecordStream()
    # 例外を送出せず (None, None) を返し、stderr も汚さない。
    assert sink.warn_residual_summary_columns("db1", "token", stream=stream) == (None, None)
    assert stream.text == ""


def test_warn_residual_skips_when_db_id_missing():
    """db_id 未解決なら GET せず検知スキップ (best-effort, (None, None))。"""
    stream = _RecordStream()
    assert sink.warn_residual_summary_columns(None, "token", stream=stream) == (None, None)
    assert stream.text == ""


def test_upsert_runs_residual_gate_after_writes(monkeypatch):
    """upsert 完了後に read-only 検知ゲートが1回だけ発火する (発火点の配線)。

    sink 本体の書き込みが終わってから warn が呼ばれること、引数に database_id/token が
    渡ること、戻り値 (created/updated) はゲートに影響されないことを固定する。
    """
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    calls = []

    def fake_warn(database_id, token, *a, **k):
        calls.append((database_id, token))
        return [], []

    monkeypatch.setattr(sink, "warn_residual_summary_columns", fake_warn)
    rows = [{
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None,
    }]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")
    assert result["created"] == 1
    assert calls == [("db1", "token")]


def test_upsert_does_not_crash_when_gate_db_unreachable(monkeypatch):
    """検知ゲートの GET が落ちても upsert 本体は完走する (best-effort 統合確認)。

    fake ストアは未知の GET /databases を AssertionError にするが、warn 内 except で
    握り潰され upsert は created を返す。月次フローが残骸検知失敗で止まらない保証。
    """
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    rows = [{
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None,
    }]
    # warn は本物のまま (GET /databases は fake で AssertionError → except で握り潰し)。
    result = sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")
    assert result["created"] == 1
    assert result["updated"] == 0


# --- 集計疑い検知: suspect_summary_extras 純関数 + 文言出し分け + upsert 戻り昇格 -------------
#  whitelist(deprecated 固定名)に載らない『新名の集計列』が extra に落ちたとき、集計語を含む
#  列だけを『集計列の疑い』として拾い、正当な追加列(任意メモ等)と区別する。FAIL/削除はしない。

def test_suspect_summary_extras_picks_summary_named_columns():
    """集計語(総計/合計金額/月次サマリ/発行漏れ件数)を含む extra だけを sorted で拾う。"""
    extra = ["総計", "合計金額", "月次サマリ", "発行漏れ件数", "担当者", "任意メモ"]
    assert sink.suspect_summary_extras(extra) == ["合計金額", "月次サマリ", "発行漏れ件数", "総計"]


def test_suspect_summary_extras_ignores_legitimate_columns():
    """集計語を含まない正当な追加列(任意メモ/担当者)は拾わない (偽陽性を出さない)。"""
    assert sink.suspect_summary_extras(["任意メモ", "担当者", "社内コード"]) == []


def test_suspect_summary_extras_matches_english_summary_words():
    """英語の集計語(total/sum/count)も大小無視で拾う。"""
    assert sink.suspect_summary_extras(["Total", "row_sum", "Count", "memo"]) == [
        "Count", "Total", "row_sum"]


def test_suspect_summary_extras_empty_and_none():
    """空/None は空を返す (純関数の境界)。"""
    assert sink.suspect_summary_extras([]) == []
    assert sink.suspect_summary_extras(None) == []


def test_upsert_result_includes_residual_extra_suspect(monkeypatch):
    """upsert 戻り dict に residual/extra/suspect_summary が昇格し、既存キーは不変。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    # warn を差し替え、residual=旧列・extra=集計疑い+正当列 のケースを返す。
    monkeypatch.setattr(sink, "warn_residual_summary_columns",
                        lambda database_id, token, *a, **k: (["全体トータル"], ["総計", "任意メモ"]))
    rows = [{
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None,
    }]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")
    # 既存キーは不変 (後方互換)。
    assert result["created"] == 1
    assert result["updated"] == 0
    assert result["period_ym"] == "2026-06"
    assert result["run_id"]
    # 新キー: 検知結果が昇格している。
    assert result["residual"] == ["全体トータル"]
    assert result["extra"] == ["総計", "任意メモ"]
    assert result["suspect_summary"] == ["総計"]  # extra から集計疑いだけ抽出


def test_upsert_result_new_keys_default_empty_when_gate_returns_none(monkeypatch):
    """検知ゲートが (None, None) を返しても新キーは空リストで揃う (画面側が安全に get できる)。"""
    fake_req, state = _make_fake_store()
    monkeypatch.setattr(sink, "_req", fake_req)
    monkeypatch.setattr(sink, "warn_residual_summary_columns",
                        lambda database_id, token, *a, **k: (None, None))
    rows = [{
        "customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
        "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None,
    }]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")
    assert result["residual"] == []
    assert result["extra"] == []
    assert result["suspect_summary"] == []


def test_warn_residual_separates_residual_suspect_other_lines(monkeypatch):
    """文言出し分け: residual / 集計疑い extra / その他 extra が別行で stderr に出る。"""
    schema = _load_db_schema()
    # residual=全体トータル(deprecated), extra=総計(集計疑い)+任意メモ(その他)。
    props = _props_from_schema(schema, residual=["全体トータル"], extra=["総計", "任意メモ"])
    monkeypatch.setattr(sink, "_req",
                        lambda method, path, token, body=None: {"properties": props})
    stream = _RecordStream()
    residual, extra = sink.warn_residual_summary_columns("db1", "token", schema=schema, stream=stream)
    assert residual == ["全体トータル"]
    assert sorted(extra) == ["任意メモ", "総計"]
    lines = [ln for ln in stream.text.splitlines() if ln]
    # 3 行: 旧サマリ/集計列・集計列の疑い・schema 未知。
    assert any("旧サマリ/集計列" in ln and "全体トータル" in ln for ln in lines)
    assert any("集計列の疑いがある追加列" in ln and "総計" in ln for ln in lines)
    assert any("schema 未知の追加列" in ln and "任意メモ" in ln for ln in lines)
    # 集計疑い行と未知行は別行 (混ざらない)。
    suspect_line = next(ln for ln in lines if "集計列の疑い" in ln)
    assert "任意メモ" not in suspect_line


def test_warn_residual_suspect_only_no_residual(monkeypatch):
    """集計疑い extra のみ (residual なし) → 集計疑い行だけ出て residual 行は出ない。"""
    schema = _load_db_schema()
    props = _props_from_schema(schema, extra=["月次サマリ"])
    monkeypatch.setattr(sink, "_req",
                        lambda method, path, token, body=None: {"properties": props})
    stream = _RecordStream()
    residual, extra = sink.warn_residual_summary_columns("db1", "token", schema=schema, stream=stream)
    assert residual == []
    assert extra == ["月次サマリ"]
    assert "旧サマリ/集計列" not in stream.text
    assert "集計列の疑いがある追加列" in stream.text and "月次サマリ" in stream.text
    assert "schema 未知の追加列" not in stream.text


def test_warn_residual_other_extra_only(monkeypatch):
    """集計語を含まない追加列のみ → その他 extra 行だけ出る (集計疑い行は出ない)。"""
    schema = _load_db_schema()
    props = _props_from_schema(schema, extra=["任意メモ"])
    monkeypatch.setattr(sink, "_req",
                        lambda method, path, token, body=None: {"properties": props})
    stream = _RecordStream()
    sink.warn_residual_summary_columns("db1", "token", schema=schema, stream=stream)
    assert "集計列の疑いがある追加列" not in stream.text
    assert "schema 未知の追加列" in stream.text and "任意メモ" in stream.text
