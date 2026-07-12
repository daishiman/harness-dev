#!/usr/bin/env python3
"""notion_reconcile_sink.py の履歴非破壊 upsert を req モックで検証する。

中核保証:
  - 過去月不可侵 : 既存に 2606/2607 があり target_ym=2607 で upsert → 2606 行へ PATCH/POST が
    一度も発行されない (query が当月限定のため構造的に届かない)。
  - 確認済み凍結 : 当月既存行 人間対応済み=true → スキップ (frozen)・PATCH しない。
  - 未確認は更新 : 人間対応済み=false → PATCH で判定更新・人間対応済み/title は送らない。
  - 新規作成     : 既存に無いキー → POST (人間対応済み=false 初期化)。
  - 方向キー分岐 : 順方向/逆方向orphan で別キー (同名 id でも衝突しない)。
  - 改行保持     : 警告 rich_text に \\n が残る。
ネットワークは一切叩かない (req を関数引数で差し替え)。MFK_NOTION_WRITE_GAP は無関係 (実 _req 未使用)。
"""
import notion_reconcile_sink as sink


# ---------------------------------------------------------------------------
# fake Notion store: pages を保持し、対象年月 select でフィルタした query を返す。
# ---------------------------------------------------------------------------

def _make_store(initial_pages=None):
    state = {"pages": dict(initial_pages or {}), "seq": 0, "calls": []}

    def req(method, path, token, body=None):
        state["calls"].append((method, path, body))

        if method == "POST" and path.endswith("/query"):
            # 当月限定フィルタであることを保証する (非破壊の要)。
            assert body["filter"]["property"] == sink.PROP_TARGET_YM
            ym = body["filter"]["select"]["equals"]
            results = []
            for pid, page in state["pages"].items():
                p_ym = ((page.get("properties") or {}).get(sink.PROP_TARGET_YM) or {})
                if (p_ym.get("select") or {}).get("name") == ym:
                    results.append({"id": pid, "properties": page["properties"]})
            return {"results": results, "has_more": False}

        if method == "POST" and path == "/pages":
            state["seq"] += 1
            pid = f"page-{state['seq']}"
            state["pages"][pid] = {"properties": dict(body["properties"])}
            return {"id": pid}

        if method == "PATCH" and path.startswith("/pages/"):
            pid = path.split("/pages/")[1]
            state["pages"][pid]["properties"].update(body["properties"])
            return {"id": pid}

        raise AssertionError((method, path, body))

    return req, state


def _page_props(direction, target_ym, *, contract_id=None, mf_customer_id=None,
                human_done=False, judge=None):
    """既存 DB2 ページの properties を組む (title は方向別の自然キー)。"""
    if direction == sink.DIRECTION_ORPHAN:
        title = f"ORPHAN_{mf_customer_id}_{target_ym}"
    else:
        title = f"{contract_id}_{target_ym}"
    props = {
        sink.PROP_TITLE: {"title": [{"text": {"content": title}, "plain_text": title}]},
        sink.PROP_DIRECTION: {"select": {"name": direction}},
        sink.PROP_TARGET_YM: {"select": {"name": target_ym}},
        sink.PROP_HUMAN_DONE: {"checkbox": human_done},
    }
    if judge:
        props[sink.PROP_JUDGE] = {"select": {"name": judge}}
    return props


def _writes_to(state, page_id):
    """page_id 宛ての PATCH 呼び出し一覧。"""
    return [c for c in state["calls"] if c[0] == "PATCH" and page_id in (c[1] or "")]


# ---------------------------------------------------------------------------
# 純関数 (title キー / title 読取)
# ---------------------------------------------------------------------------

def test_title_for_branches_by_direction():
    fwd = {"direction": "順方向", "contract_id": "C1"}
    orp = {"direction": "逆方向orphan", "mf_customer_id": "M1"}
    assert sink._title_for(fwd, "2607") == "C1_2607"
    assert sink._title_for(orp, "2607") == "ORPHAN_M1_2607"
    # direction 欠落は順方向既定。
    assert sink._title_for({"contract_id": "X"}, "2606") == "X_2606"


def test_title_plain_reads_and_handles_non_dict():
    assert sink._title_plain({"title": [{"text": {"content": "あ"}}, {"plain_text": "い"}]}) == "あい"
    assert sink._title_plain(None) == ""
    assert sink._title_plain({}) == ""


# ---------------------------------------------------------------------------
# 非破壊の中核: 過去月不可侵
# ---------------------------------------------------------------------------

def test_past_month_is_untouched(monkeypatch):
    """既存 2606/2607、target_ym=2607 で upsert → 2606 ページへ PATCH/POST が一切飛ばない。"""
    req, state = _make_store({
        "p2606": {"properties": _page_props("順方向", "2606", contract_id="C1")},
        "p2607": {"properties": _page_props("順方向", "2607", contract_id="C1")},
    })
    before_2606 = dict(state["pages"]["p2606"]["properties"])
    rows = [{"direction": "順方向", "contract_id": "C1",
             "judge_label": "発行確認OK", "expected_amount": 100}]
    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)

    # 当月行 (2607) だけが更新され、過去月 (2606) は不可侵。
    assert res == {"created": 0, "updated": 1, "frozen": 0, "failed": 0}
    assert _writes_to(state, "p2606") == []
    # query は 2606 を結果に含めない (= そもそも読まれない)。POST も 2607 のみ。
    assert all("p2606" not in (c[1] or "") for c in state["calls"])
    assert state["pages"]["p2606"]["properties"] == before_2606  # 1 byte も変わらない


def test_query_month_filters_to_target_only(monkeypatch):
    """query_month は対象年月==target_ym の行だけを返す (過去月を読まない)。"""
    req, state = _make_store({
        "p2606": {"properties": _page_props("順方向", "2606", contract_id="C1")},
        "p2607a": {"properties": _page_props("順方向", "2607", contract_id="A")},
        "p2607b": {"properties": _page_props("逆方向orphan", "2607", mf_customer_id="M")},
    })
    out = sink.query_month("db2", "2607", "tok", req=req)
    titles = {sink._title_plain(p["properties"][sink.PROP_TITLE]) for p in out}
    assert titles == {"A_2607", "ORPHAN_M_2607"}


def test_query_month_paginates_and_dedups():
    """has_more/next_cursor を辿り全件取得し page_id で dedup する。"""
    pages = [
        {"results": [{"id": "a", "properties": {}}, {"id": "b", "properties": {}}],
         "has_more": True, "next_cursor": "c2"},
        {"results": [{"id": "b", "properties": {}}, {"id": "c", "properties": {}}],
         "has_more": False},
    ]
    cursors = []

    def req(method, path, token, body=None):
        cursors.append((body or {}).get("start_cursor"))
        assert body["filter"]["select"]["equals"] == "2607"
        return pages.pop(0)

    out = sink.query_month("db2", "2607", "tok", req=req)
    assert [p["id"] for p in out] == ["a", "b", "c"]  # b は dedup
    assert cursors == [None, "c2"]


def test_query_month_returns_empty_on_missing_target_option():
    # 新月を初めて処理する初回: 対象年月 select に target_ym option が無く Notion が
    # validation_error(HTTP 400) を返す → その月の行はまだ存在しない(既存ゼロ)ので空を返す。
    # 最初の行を POST する際に option が自動作成され、以降の query は通る。
    def req(method, path, token, body=None):
        raise RuntimeError(
            'Notion POST /databases/db2/query: HTTP 400 {"object":"error",'
            '"code":"validation_error","message":"select option \\"2605\\" not found '
            'for property \\"対象年月\\". Available options: \\"2606\\"."}')
    assert sink.query_month("db2", "2605", "tok", req=req) == []


def test_query_month_reraises_unrelated_400():
    # 対象年月以外の 400 は握りつぶさず再送出する (本当のエラーを隠さない)。
    import pytest
    def req(method, path, token, body=None):
        raise RuntimeError('Notion POST /databases/db2/query: HTTP 400 '
                           '{"message":"body failed validation: something else"}')
    with pytest.raises(RuntimeError):
        sink.query_month("db2", "2605", "tok", req=req)


# ---------------------------------------------------------------------------
# 確認済み凍結 (L1)
# ---------------------------------------------------------------------------

def test_frozen_when_human_done_true():
    """当月既存行 人間対応済み=true → スキップ (frozen++)・PATCH されない。"""
    req, state = _make_store({
        "p1": {"properties": _page_props("順方向", "2607", contract_id="C1",
                                         human_done=True, judge="要確認(金額差)")},
    })
    rows = [{"direction": "順方向", "contract_id": "C1",
             "judge_label": "発行漏れ", "expected_amount": 999}]
    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)

    assert res == {"created": 0, "updated": 0, "frozen": 1, "failed": 0}
    assert [c for c in state["calls"] if c[0] == "PATCH"] == []  # 機械は一切上書きしない
    # 既存判定が温存される (機械が書き換えていない)。
    assert state["pages"]["p1"]["properties"][sink.PROP_JUDGE]["select"]["name"] == "要確認(金額差)"


# ---------------------------------------------------------------------------
# 未確認は更新 (人間対応済み/title を送らない)
# ---------------------------------------------------------------------------

def test_unconfirmed_row_is_patched_without_human_flag():
    """人間対応済み=false → PATCH で判定更新。人間対応済み列と title は送らない。"""
    req, state = _make_store({
        "p1": {"properties": _page_props("順方向", "2607", contract_id="C1",
                                         human_done=False, judge="要確認(金額差)")},
    })
    rows = [{"direction": "順方向", "contract_id": "C1",
             "judge_label": "発行確認OK", "expected_amount": 100, "matched_amount": 100,
             "ai_check": True, "warning": "解消"}]
    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)

    assert res == {"created": 0, "updated": 1, "frozen": 0, "failed": 0}
    patch = next(c for c in state["calls"] if c[0] == "PATCH")
    props = patch[2]["properties"]
    assert props[sink.PROP_JUDGE]["select"]["name"] == "発行確認OK"
    assert props[sink.PROP_EXPECTED]["number"] == 100
    assert props[sink.PROP_AI_CHECK]["checkbox"] is True
    # 人間専用 managed 列と不変キー (title) は更新で送らない。
    assert sink.PROP_HUMAN_DONE not in props
    assert sink.PROP_TITLE not in props


# ---------------------------------------------------------------------------
# 新規作成
# ---------------------------------------------------------------------------

def test_create_when_key_absent():
    """既存に無いキー → POST 新規作成。人間対応済み=false 初期化・契約relation 付与。"""
    req, state = _make_store()
    rows = [{"direction": "順方向", "contract_id": "C9", "contract_page_id": "db1-9",
             "judge_label": "発行確認OK", "expected_amount": 100}]
    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)

    assert res == {"created": 1, "updated": 0, "frozen": 0, "failed": 0}
    post = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")
    props = post[2]["properties"]
    assert props[sink.PROP_TITLE]["title"][0]["text"]["content"] == "C9_2607"
    assert props[sink.PROP_HUMAN_DONE]["checkbox"] is False
    assert props[sink.PROP_RELATION]["relation"] == [{"id": "db1-9"}]
    assert post[2]["parent"] == {"database_id": "db2"}


def test_create_includes_all_fact_fields():
    """全 fact 列が値ありで揃えば props に漏れなく載る (number/date/rich_text 各分岐)。"""
    req, state = _make_store()
    rows = [{"direction": "順方向", "contract_id": "C1", "contract_page_id": "d1",
             "judge_label": "発行確認OK", "expected_amount": 100, "matched_amount": 100,
             "expected_count": 3, "supply_count": 3, "mf_billing_id": "BILL1",
             "ai_check": True, "mf_customer_id": "CUST1",
             "issue_date": "2026-07-05", "run_at": "2026-07-26",
             "warning": "ok"}]
    sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)
    p = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert p[sink.PROP_DIRECTION]["select"]["name"] == "順方向"
    assert p[sink.PROP_TARGET_YM]["select"]["name"] == "2607"
    assert p[sink.PROP_EXPECTED]["number"] == 100
    assert p[sink.PROP_MATCHED]["number"] == 100
    assert p[sink.PROP_EXPECTED_COUNT]["number"] == 3
    assert p[sink.PROP_SUPPLY_COUNT]["number"] == 3
    assert p[sink.PROP_AI_CHECK]["checkbox"] is True
    assert p[sink.PROP_MF_BILLING]["rich_text"][0]["text"]["content"] == "BILL1"
    assert p[sink.PROP_MF_CUSTOMER]["rich_text"][0]["text"]["content"] == "CUST1"
    assert p[sink.PROP_ISSUE_DATE]["date"]["start"] == "2026-07-05"
    assert p[sink.PROP_RUN_AT]["date"]["start"] == "2026-07-26"


def test_expected_amount_zero_is_written():
    """期待金額=0 は欠落でなく有効値として number に載る (is not None 判定)。"""
    req, state = _make_store()
    rows = [{"direction": "順方向", "contract_id": "C1", "expected_amount": 0}]
    sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)
    p = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert p[sink.PROP_EXPECTED]["number"] == 0


# ---------------------------------------------------------------------------
# 方向キー分岐
# ---------------------------------------------------------------------------

def test_direction_key_branch():
    """順方向/逆方向orphan は別キーで索引され、既存はそれぞれ更新・新規は作成される。"""
    req, state = _make_store({
        "pf": {"properties": _page_props("順方向", "2607", contract_id="C1")},
        "po": {"properties": _page_props("逆方向orphan", "2607", mf_customer_id="M1")},
    })
    rows = [
        {"direction": "順方向", "contract_id": "C1", "judge_label": "発行確認OK"},
        {"direction": "逆方向orphan", "mf_customer_id": "M1", "judge_label": "要マスタ登録"},
        {"direction": "逆方向orphan", "mf_customer_id": "M2", "judge_label": "要マスタ登録"},
    ]
    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)

    assert res == {"created": 1, "updated": 2, "frozen": 0, "failed": 0}
    post = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")
    np = post[2]["properties"]
    assert np[sink.PROP_TITLE]["title"][0]["text"]["content"] == "ORPHAN_M2_2607"
    assert np[sink.PROP_DIRECTION]["select"]["name"] == "逆方向orphan"
    assert np[sink.PROP_MF_CUSTOMER]["rich_text"][0]["text"]["content"] == "M2"


def test_forward_and_orphan_same_id_do_not_collide():
    """順方向 contract_id と 逆方向 mf_customer_id が同名でもキーは別 (衝突しない)。"""
    req, state = _make_store({
        "pf": {"properties": _page_props("順方向", "2607", contract_id="X")},
    })
    rows = [{"direction": "逆方向orphan", "mf_customer_id": "X", "judge_label": "要マスタ登録"}]
    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)
    # ORPHAN_X_2607 != X_2607 → 既存順方向行に当たらず新規作成。
    assert res == {"created": 1, "updated": 0, "frozen": 0, "failed": 0}


# ---------------------------------------------------------------------------
# 改行保持
# ---------------------------------------------------------------------------

def test_warning_preserves_newlines():
    """警告 rich_text は改行 \\n をそのまま 1 content に保持する (split しない)。"""
    req, state = _make_store()
    warn = "数量差: 期待3>供給1\n想定漏れ 90,000円\n要経理確認"
    rows = [{"direction": "順方向", "contract_id": "C1",
             "judge_label": "要確認(数量差)", "warning": warn}]
    sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)
    content = (next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")
               [2]["properties"][sink.PROP_WARNING]["rich_text"][0]["text"]["content"])
    assert content == warn
    assert content.count("\n") == 2


def test_warning_newlines_preserved_on_update():
    """更新経路でも警告の \\n が保持される (新規/更新どちらも _build_props 共有)。"""
    req, state = _make_store({
        "p1": {"properties": _page_props("順方向", "2607", contract_id="C1", human_done=False)},
    })
    warn = "金額差\nMF 215,000 ↔ 確認 357,000"
    sink.upsert_monthly([{"direction": "順方向", "contract_id": "C1",
                          "judge_label": "要確認(金額差)", "warning": warn}],
                        "db2", "2607", "tok", req=req)
    patch = next(c for c in state["calls"] if c[0] == "PATCH")
    assert patch[2]["properties"][sink.PROP_WARNING]["rich_text"][0]["text"]["content"] == warn


def test_update_clears_stale_nullable_fact_fields():
    """MATCH→GAP 等の再実行で前回のMF証跡・突合金額・警告が stale に残らない。"""
    stale_props = _page_props("順方向", "2607", contract_id="C1", human_done=False)
    stale_props.update({
        sink.PROP_MATCHED: {"number": 100000},
        sink.PROP_SUPPLY_COUNT: {"number": 1},
        sink.PROP_MF_BILLING: {"rich_text": [{"text": {"content": "OLD-BILL"}}]},
        sink.PROP_MF_CUSTOMER: {"rich_text": [{"text": {"content": "OLD-CUST"}}]},
        sink.PROP_ISSUE_DATE: {"date": {"start": "2026-07-05"}},
        sink.PROP_WARNING: {"rich_text": [{"text": {"content": "old warning"}}]},
        sink.PROP_RUN_AT: {"date": {"start": "2026-07-05"}},
        sink.PROP_RELATION: {"relation": [{"id": "old-db1"}]},
    })
    req, state = _make_store({"p1": {"properties": stale_props}})
    rows = [{"direction": "順方向", "contract_id": "C1",
             "judge_label": "発行漏れ", "expected_amount": 100000, "ai_check": False}]

    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)

    assert res == {"created": 0, "updated": 1, "frozen": 0, "failed": 0}
    props = next(c for c in state["calls"] if c[0] == "PATCH")[2]["properties"]
    assert props[sink.PROP_MATCHED] == {"number": None}
    assert props[sink.PROP_SUPPLY_COUNT] == {"number": None}
    assert props[sink.PROP_MF_BILLING] == {"rich_text": []}
    assert props[sink.PROP_MF_CUSTOMER] == {"rich_text": []}
    assert props[sink.PROP_ISSUE_DATE] == {"date": None}
    assert props[sink.PROP_WARNING] == {"rich_text": []}
    assert props[sink.PROP_RUN_AT] == {"date": None}
    assert props[sink.PROP_RELATION] == {"relation": []}


# ---------------------------------------------------------------------------
# 失敗隔離・既定 req
# ---------------------------------------------------------------------------

def test_failed_row_is_isolated_and_counted():
    """1 行の POST 失敗は failed に計上し、残りの行は処理を続ける。"""
    posts = []

    def req(method, path, token, body=None):
        if method == "POST" and path.endswith("/query"):
            return {"results": [], "has_more": False}
        if method == "POST" and path == "/pages":
            posts.append(body)
            if len(posts) == 2:  # 2 件目だけ失敗させる
                raise RuntimeError("boom")
            return {"id": f"p{len(posts)}"}
        raise AssertionError((method, path))

    rows = [
        {"direction": "順方向", "contract_id": "C1", "judge_label": "発行確認OK"},
        {"direction": "順方向", "contract_id": "C2", "judge_label": "発行確認OK"},
        {"direction": "順方向", "contract_id": "C3", "judge_label": "発行確認OK"},
    ]
    res = sink.upsert_monthly(rows, "db2", "2607", "tok", req=req)
    assert res == {"created": 2, "updated": 0, "frozen": 0, "failed": 1}


def test_default_req_used_when_none(monkeypatch):
    """req 省略時は notion_transport._req (module global) が使われる。"""
    calls = []

    def fake(method, path, token, body=None):
        calls.append((method, path))
        if path.endswith("/query"):
            return {"results": [], "has_more": False}
        if path == "/pages":
            return {"id": "x"}
        raise AssertionError((method, path))

    monkeypatch.setattr(sink, "_req", fake)
    res = sink.upsert_monthly(
        [{"direction": "順方向", "contract_id": "C1", "judge_label": "発行確認OK"}],
        "db2", "2607", "tok")
    assert res["created"] == 1
    assert calls[0] == ("POST", "/databases/db2/query")  # query が先に走る


def test_empty_rows_only_queries_no_writes():
    """rows 空なら query のみで書き込みは発生しない。"""
    req, state = _make_store()
    res = sink.upsert_monthly([], "db2", "2607", "tok", req=req)
    assert res == {"created": 0, "updated": 0, "frozen": 0, "failed": 0}
    assert all(c[0] != "PATCH" and not (c[0] == "POST" and c[1] == "/pages")
               for c in state["calls"])
