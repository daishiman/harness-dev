#!/usr/bin/env python3
"""notion_report_sink.py (C04・Design D) を fake-store req モックで完全オフライン検証する。

Design D = 単一恒久レポート DB を **指定トグル (report_toggle_block) の中**で更新対象にする。
Notion API は database を block_id (トグル) 親で『作成』できないが、UI で作られたトグル内 DB の
『更新』(行 upsert・列 PATCH) はできる。ゆえに出力先の優先順は:
  1. トグル内の既存 report DB を更新 (location='in-block')
  2. 無ければプレーン見出し直下の既存 report DB を更新 (location='under-heading')
  3. 無ければ親ページ直下の既存 report DB を更新 (location='page')
  4. どれも無ければ見出しの下 (ページ直下) へ新規作成 (location='page-created')
単一 DB に複数月を保持し、行同定キー (対象月 YYYY-MM, 取引先名, 商品名) で同月の再実行のみ上書き
(重複行 0)・別月/以前 run の行は非破壊保持 (deleted 常時 0)。ネットワークは一切叩かない。
"""
import json

import notion_report_sink as sink


# ---------------------------------------------------------------------------
# fake Notion store: トグル/ページ子ブロック + DB (properties 込み) + ページを in-memory dict で模す。
#   - GET  /blocks/{id}/children  → その container の子ブロック list
#   - GET  /databases/{id}        → DB の properties (スキーマ・_ensure_db_schema 用)
#   - PATCH /databases/{id}       → DB へ列 (properties) を追加
#   - POST /databases            → child_database 作成 (parent=page_id・親ページ子へ登録)
#   - POST /databases/{id}/query → その DB のページ list
#   - POST /pages                → ページ作成
#   - PATCH /pages/{id}          → ページ更新
# ---------------------------------------------------------------------------

def _db_block(db_id, title, props=None):
    """child_database ブロック (id=database_id 一致)。"""
    return {"id": db_id, "type": "child_database", "child_database": {"title": title}}


def _default_props():
    """既存 report DB の 8 列スキーマ (対象月含む)。fake GET /databases が返す schema。"""
    return {name: sink.build_property(sink._COLUMN_SPECS[name]) for name in sink.COLUMN_ORDER}


def _legacy_props():
    """対象月列が無い旧 7 列スキーマ (UI/旧版で作られた DB を模す・_ensure_db_schema の対象)。"""
    return {name: sink.build_property(sink._COLUMN_SPECS[name])
            for name in sink.COLUMN_ORDER if name != sink.PROP_TARGET_MONTH}


def _make_store(block_children=None, dbs=None):
    """block_children = {container_id: [blocks]}・dbs = {db_id: {"title":.., "properties":..}}。"""
    state = {
        "block_children": {k: list(v) for k, v in (block_children or {}).items()},
        "dbs": {k: {"title": v.get("title", ""), "properties": dict(v.get("properties") or _default_props())}
                for k, v in (dbs or {}).items()},
        "pages": {},   # page_id -> {"db":.., "properties":..}
        "seq": 0,
        "calls": [],
    }

    def req(method, path, token, body=None):
        state["calls"].append((method, path, body))

        if method == "GET" and path.startswith("/blocks/") and "/children" in path:
            bid = path[len("/blocks/"):path.index("/children")]
            return {"results": list(state["block_children"].get(bid, [])), "has_more": False}

        if method == "GET" and path.startswith("/databases/"):
            dbid = path[len("/databases/"):]
            db = state["dbs"].get(dbid, {"properties": {}})
            return {"id": dbid, "properties": db.get("properties", {})}

        if method == "PATCH" and path.startswith("/databases/"):
            dbid = path[len("/databases/"):]
            state["dbs"].setdefault(dbid, {"title": "", "properties": {}})
            state["dbs"][dbid]["properties"].update(body.get("properties", {}))
            return {"id": dbid}

        if method == "POST" and path == "/databases":
            assert body["parent"]["type"] == "page_id" and body["parent"].get("page_id"), \
                f"POST /databases parent は page_id 必須 (block_id 親は作成不可): {body['parent']}"
            state["seq"] += 1
            db_id = f"db-{state['seq']}"
            title = body["title"][0]["text"]["content"]
            state["dbs"][db_id] = {"title": title, "properties": dict(body["properties"])}
            page = body["parent"]["page_id"]
            state["block_children"].setdefault(page, []).append(_db_block(db_id, title))
            return {"id": db_id}

        if method == "POST" and path.startswith("/databases/") and path.endswith("/query"):
            db_id = path[len("/databases/"):-len("/query")]
            results = [{"id": pid, "properties": p["properties"]}
                       for pid, p in state["pages"].items() if p["db"] == db_id]
            return {"results": results, "has_more": False}

        if method == "POST" and path == "/pages":
            state["seq"] += 1
            pid = f"pg-{state['seq']}"
            state["pages"][pid] = {"db": body["parent"]["database_id"],
                                   "properties": dict(body["properties"])}
            return {"id": pid}

        if method == "PATCH" and path.startswith("/pages/"):
            pid = path[len("/pages/"):]
            state["pages"][pid]["properties"].update(body["properties"])
            return {"id": pid}

        raise AssertionError((method, path, body))

    return req, state


def _rows_in(state, db_id):
    """DB の (対象月, 取引先名, 商品名) キー集合 (fake store 上の実行後スナップショット)。"""
    keys = set()
    for p in state["pages"].values():
        if p["db"] != db_id:
            continue
        props = p["properties"]
        cust = sink._title_plain(props.get(sink.PROP_CUSTOMER))
        tm = sink._rich_text_plain(props.get(sink.PROP_TARGET_MONTH))
        prod = sink._rich_text_plain(props.get(sink.PROP_PRODUCT))
        keys.add((tm, cust, prod))
    return keys


# ---------------------------------------------------------------------------
# 純関数
# ---------------------------------------------------------------------------

def test_target_to_yyyymm():
    assert sink.target_to_yyyymm("2607") == "2026-07"
    assert sink.target_to_yyyymm("2601") == "2026-01"


def test_valid_target():
    assert sink._valid_target("2607") and sink._valid_target("2601")
    assert not sink._valid_target("2613")   # 月 13 は不正
    assert not sink._valid_target("260")     # 桁不足
    assert not sink._valid_target("26o7")    # 非数字


def test_stored_key_includes_target_month():
    # Design D: 同定キーは (対象月, 取引先名, 商品名)。対象月で月をまたいだ行を区別する。
    assert sink._stored_key("2026-07", "A社", "月額P") == ("2026-07", "a社", "月額p")
    # 別月は別キー (非破壊共存)。
    assert sink._stored_key("2026-07", "A社", "P") != sink._stored_key("2026-06", "A社", "P")


def test_stored_key_absorbs_name_drift():
    import unicodedata
    nfc = "ダイヤ商事"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfd != nfc
    assert sink._stored_key("2026-07", nfd, "月額P") == sink._stored_key("2026-07", nfc, "月額P")
    assert sink._stored_key("2026-07", "テスト株式会社", "P") == sink._stored_key("2026-07", "テスト㈱", "P")


def test_prefer_action_keeps_gap_over_normal():
    normal = {"gap_check": "正常", "customer": "A社", "product": "P", "contract_id": "C1"}
    action = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2"}
    assert sink._prefer_action(normal, action) is action
    assert sink._prefer_action(action, normal) is action


def test_is_structural_normal_discriminates_bare_normal():
    assert sink._is_structural_normal(
        {"gap_check": "正常", "period_diff": "前月あり今月なし (契約完了)"}) is True
    # 要件1(2026-07-10): 継続発行=月契約の権威ある正常ゆえ構造的正常マーカーに含める (True へ反転)。
    assert sink._is_structural_normal({"gap_check": "正常", "period_diff": "継続発行"}) is True
    # 構造事由の無い bare 正常 (period_diff がマーカー非該当) は False のまま (guard 保持対象)。
    assert sink._is_structural_normal({"gap_check": "正常", "period_diff": "新規発行"}) is False
    assert sink._is_structural_normal(
        {"gap_check": "要対応", "period_diff": "前月あり今月なし (年契約周期)"}) is False


def test_title_plain_and_child_db_title():
    assert sink._title_plain({"title": [{"text": {"content": "あ"}}, {"plain_text": "い"}]}) == "あい"
    assert sink._title_plain(None) == ""
    assert sink._child_db_title({"child_database": {"title": "T"}}) == "T"
    assert sink._child_db_title(None) == ""


# ---------------------------------------------------------------------------
# 8 列スキーマ (対象月を含む・列順固定・title=取引先名)
# ---------------------------------------------------------------------------

def test_schema_properties_column_order_and_types():
    props = sink.schema_properties()
    assert list(props.keys()) == [
        "取引先名", "対象月", "漏れチェック", "商品名",
        "先月の金額", "今月の金額", "先月と今月の比較", "コメント"]
    assert "title" in props["取引先名"]
    assert "rich_text" in props["対象月"]
    assert "checkbox" in props["漏れチェック"]
    assert props["先月の金額"]["number"]["format"] == "yen"
    assert props["今月の金額"]["number"]["format"] == "yen"


# ---------------------------------------------------------------------------
# resolve_report_db: トグル内優先 → ページ → 新規作成 (下側フォールバック)
# ---------------------------------------------------------------------------

def test_resolve_targets_existing_db_inside_toggle_heading():
    """(1) トグル見出し配下に既存 report DB があればそれを更新対象にする (location='in-block')。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-tog", "請求漏れ比較レポート 2026-06")]},
        dbs={"db-tog": {"title": "請求漏れ比較レポート 2026-06", "properties": _default_props()}})
    db_id, location, created, placement = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert db_id == "db-tog" and location == "in-block" and created is False
    assert all(not (c[0] == "POST" and c[1] == "/databases") for c in state["calls"])


def _heading(block_id, text="請求書漏れレポート", toggleable=False):
    return {"id": block_id, "type": "heading_2",
            "heading_2": {"is_toggleable": toggleable, "rich_text": [{"plain_text": text}]}}


def test_resolve_targets_db_below_plain_heading():
    """(2) プレーン見出し2 の直下 (ページ兄弟) の DB を、次セクション見出しの手前で同定する。

    実状態の再現: トグル→見出し2 変換で DB がページ直下 (見出しの下) へ移動。ページ末尾に旧重複
    DB があってもこの見出しに属する DB を選ぶ (重複と区別)。"""
    req, state = _make_store(
        block_children={"HEAD": [],  # プレーン見出しは子を持たない
                        "PAGE": [
                            _heading("HEAD", "請求書漏れレポート"),
                            _db_block("db-mine", "請求漏れ比較レポート 2026-06"),   # 見出し直下=正解
                            {"id": "p1", "type": "paragraph"},
                            _heading("HEAD2", "請求書確認シート", toggleable=True),  # 次セクション
                            _db_block("db-dup", "請求漏れ比較レポート 2026-06"),     # 別セクションの重複
                        ]},
        dbs={"db-mine": {"title": "請求漏れ比較レポート 2026-06", "properties": _default_props()},
             "db-dup": {"title": "請求漏れ比較レポート 2026-06", "properties": _default_props()}})
    db_id, location, created, placement = sink.resolve_report_db("HEAD", "PAGE", "tok", req=req)
    assert db_id == "db-mine" and location == "under-heading"   # 見出し直下の DB (重複でない)


def test_resolve_below_heading_stops_at_next_section():
    """見出し直下に DB が無く次セクション見出しが先に来るなら under-heading では拾わない。"""
    req, state = _make_store(
        block_children={"HEAD": [],
                        "PAGE": [
                            _heading("HEAD", "請求書漏れレポート"),
                            _heading("HEAD2", "次の見出し"),
                            _db_block("db-other", "請求漏れ比較レポート"),   # 次セクション配下
                        ]},
        dbs={"db-other": {"title": "請求漏れ比較レポート", "properties": _default_props()}})
    db_id, location, _, _ = sink.resolve_report_db("HEAD", "PAGE", "tok", req=req)
    # under-heading は打ち切り→step3 (ページ直下の任意 report DB) が db-other を拾う。
    assert db_id == "db-other" and location == "page"


def test_resolve_adds_target_month_column_to_legacy_db():
    """トグル内 DB が旧 7 列 (対象月列なし) なら _ensure_db_schema が PATCH で対象月列を後付けする。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-tog", "請求漏れ比較レポート 2026-06")]},
        dbs={"db-tog": {"title": "請求漏れ比較レポート 2026-06", "properties": _legacy_props()}})
    db_id, location, created, placement = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert sink.PROP_TARGET_MONTH in placement["schema_added"]
    patch = next(c for c in state["calls"] if c[0] == "PATCH" and c[1] == "/databases/db-tog")
    assert sink.PROP_TARGET_MONTH in patch[2]["properties"]
    assert sink.PROP_TARGET_MONTH in state["dbs"]["db-tog"]["properties"]   # 反映


def test_resolve_no_patch_when_schema_complete():
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-tog", "請求漏れ比較レポート")]},
        dbs={"db-tog": {"title": "請求漏れ比較レポート", "properties": _default_props()}})
    _, _, _, placement = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert placement["schema_added"] == []                       # 追加なし
    assert all(c[0] != "PATCH" or "/databases" not in c[1] for c in state["calls"])


def test_resolve_falls_back_to_page_db_below_heading():
    """(2) トグル内に DB が無く、ページ直下 (見出しの下側) に既存 report DB があればそれを使う。"""
    req, state = _make_store(
        block_children={"TOG": [], "PAGE": [_db_block("db-page", "請求漏れ比較レポート")]},
        dbs={"db-page": {"title": "請求漏れ比較レポート", "properties": _default_props()}})
    db_id, location, created, placement = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert db_id == "db-page" and location == "page" and created is False
    assert "見出しの下" in placement["note"]


def test_resolve_creates_below_heading_when_none():
    """(3) トグルにもページにも無ければ見出しの下 (ページ直下・page_id 親) へ新規作成する。"""
    req, state = _make_store(block_children={"TOG": [], "PAGE": []})
    db_id, location, created, placement = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert created is True and location == "page-created"
    post = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/databases")
    assert post[2]["parent"] == {"type": "page_id", "page_id": "PAGE"}          # block_id 親でない
    assert post[2]["title"][0]["text"]["content"] == "請求漏れ比較レポート"     # 月非依存 title
    assert list(post[2]["properties"].keys())[:2] == ["取引先名", "対象月"]


def test_resolve_dry_run_does_not_create():
    req, state = _make_store(block_children={"TOG": [], "PAGE": []})
    db_id, location, created, placement = sink.resolve_report_db(
        "TOG", "PAGE", "tok", req=req, apply=False)
    assert db_id is None and location == "none" and created is False
    assert all(not (c[0] == "POST" and c[1] == "/databases") for c in state["calls"])


def test_resolve_prefers_toggle_over_page():
    """トグルとページ両方に report DB があってもトグル内を優先する。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-tog", "請求漏れ比較レポート")],
                        "PAGE": [_db_block("db-page", "請求漏れ比較レポート")]},
        dbs={"db-tog": {"title": "請求漏れ比較レポート", "properties": _default_props()},
             "db-page": {"title": "請求漏れ比較レポート", "properties": _default_props()}})
    db_id, location, _, _ = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert db_id == "db-tog" and location == "in-block"


def _user_props(title_name="名前"):
    """ユーザーが Notion UI で手作りした DB を模す: title 列名が既定『名前』(『取引先名』でない)。

    事実列も無い最小 DB。_ensure_db_schema が対象月等の非 title 列を後付けし、title 列の実名『名前』を
    検出する対象。build_property({'type':'title'}) は {'title': {}} で "title" キーを持つ。
    """
    return {title_name: sink.build_property({"type": "title"})}


def test_resolve_adopts_user_named_db_in_toggle():
    """指定トグル配下の DB は**表示名非依存**で採用する。ユーザーが『請求漏れ確認レポート』等
    prefix 不一致の名前で手作りしても in-block で更新対象にし、別 DB を新規作成しない
    (要件『有れば更新』の核心・title-prefix 依存の二重作成バグ回帰防止)。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-user", "請求漏れ確認レポート")]},   # 『比較』でない
        dbs={"db-user": {"title": "請求漏れ確認レポート", "properties": _default_props()}})
    db_id, location, created, _ = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert db_id == "db-user" and location == "in-block" and created is False
    assert all(not (c[0] == "POST" and c[1] == "/databases") for c in state["calls"])  # 二重作成なし


def test_resolve_prefix_db_wins_when_multiple_in_toggle():
    """トグル配下に prefix 一致 DB と非一致 DB が併存するときは prefix 一致を決定論的に採る
    (ツール作成 DB 後方互換・同点解消)。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-other", "メモ"),
                                _db_block("db-report", "請求漏れ比較レポート 2026-06")]},
        dbs={"db-other": {"title": "メモ", "properties": _default_props()},
             "db-report": {"title": "請求漏れ比較レポート 2026-06", "properties": _default_props()}})
    db_id, location, _, _ = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert db_id == "db-report" and location == "in-block"


def test_resolve_adopts_user_named_db_below_plain_heading():
    """プレーン見出し2 の直下でも表示名非依存で採用する (トグル→見出し2 変換 + ユーザー命名の複合)。"""
    req, state = _make_store(
        block_children={"HEAD": [],
                        "PAGE": [_heading("HEAD", "請求漏れチェック"),
                                 _db_block("db-user", "うちの発行漏れ一覧")]},   # prefix 完全不一致
        dbs={"db-user": {"title": "うちの発行漏れ一覧", "properties": _default_props()}})
    db_id, location, _, _ = sink.resolve_report_db("HEAD", "PAGE", "tok", req=req)
    assert db_id == "db-user" and location == "under-heading"


def test_resolve_detects_nondefault_title_column():
    """既存 DB の title 列名が『取引先名』でなく Notion 既定の『名前』でも、placement.title_prop に
    実名を検出して載せる (行 upsert が正しい列へ title を書けるようにする)。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-user", "請求漏れ確認レポート")]},
        dbs={"db-user": {"title": "請求漏れ確認レポート", "properties": _user_props("名前")}})
    _, location, _, placement = sink.resolve_report_db("TOG", "PAGE", "tok", req=req)
    assert location == "in-block"
    assert placement["title_prop"] == "名前"                       # 実名を検出
    assert sink.PROP_TARGET_MONTH in placement["schema_added"]     # 非 title 列は後付け


# ---------------------------------------------------------------------------
# upsert: 対象月列充足・8 列・非破壊・月内冪等・複数月共存
# ---------------------------------------------------------------------------

def test_upsert_creates_row_with_all_columns_incl_target_month():
    req, state = _make_store()
    rows = [{"gap_check": "正常", "customer": "A社", "contract_id": "C1", "product": "月額プラン",
             "prev_amount": 10000, "amount": 12000,
             "period_diff": "継続発行", "comment": "継続発行・正常"}]
    res = sink.upsert_report_rows(rows, "db-1", "2607", "tok", req=req)
    assert res == {"created": 1, "updated": 0, "skipped": 0, "deleted": 0,
                   "collapsed_multi_contract": 0, "orphaned": 0}
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_CUSTOMER]["title"][0]["text"]["content"] == "A社"
    assert props[sink.PROP_TARGET_MONTH]["rich_text"][0]["text"]["content"] == "2026-07"   # 対象月充足
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is True
    assert props[sink.PROP_PRODUCT]["rich_text"][0]["text"]["content"] == "月額プラン"
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 10000
    assert props[sink.PROP_CURR_AMOUNT]["number"] == 12000


def test_prev_amount_zero_is_written():
    req, state = _make_store()
    sink.upsert_report_rows([{"customer": "A社", "prev_amount": 0, "amount": 5000}],
                            "db-1", "2607", "tok", req=req)
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 0


def test_row_missing_customer_is_skipped():
    req, state = _make_store()
    res = sink.upsert_report_rows([{"product": "P", "amount": 1}], "db-1", "2607", "tok", req=req)
    assert res == {"created": 0, "updated": 0, "skipped": 1, "deleted": 0,
                   "collapsed_multi_contract": 0, "orphaned": 0}
    assert all(not (c[0] == "POST" and c[1] == "/pages") for c in state["calls"])


def test_comment_preserves_newlines():
    req, state = _make_store()
    comment = "年契約のため今月は請求なし\n(2026-04 に一括発行済)"
    sink.upsert_report_rows([{"customer": "A社", "comment": comment}], "db-1", "2607", "tok", req=req)
    content = (next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")
               [2]["properties"][sink.PROP_COMMENT]["rich_text"][0]["text"]["content"])
    assert content == comment and content.count("\n") == 1


def test_idempotent_two_runs_same_month_collapse_to_one_row():
    """同一月へ同一 {対象月×取引先×商品} を 2 回投入 → 1 行 (2 回目は更新)。"""
    req, state = _make_store()
    row = {"customer": "A社", "contract_id": "C1", "product": "月額P", "amount": 100, "comment": "初日"}
    r1 = sink.upsert_report_rows([row], "db-1", "2607", "tok", req=req)
    assert r1["created"] == 1
    r2 = sink.upsert_report_rows([dict(row, comment="2営業日目")], "db-1", "2607", "tok", req=req)
    assert r2["updated"] == 1 and r2["created"] == 0
    assert _rows_in(state, "db-1") == {("2026-07", "A社", "月額P")}


def test_different_months_coexist_non_destructively():
    """単一 DB に別月の行を投入しても以前月の行は消えない (対象月キーで別行・非破壊)。"""
    req, state = _make_store()
    sink.upsert_report_rows([{"customer": "A社", "product": "P"}], "db-1", "2606", "tok", req=req)
    res = sink.upsert_report_rows([{"customer": "A社", "product": "P"}], "db-1", "2607", "tok", req=req)
    assert res["created"] == 1 and res["updated"] == 0 and res["deleted"] == 0
    assert _rows_in(state, "db-1") == {("2026-06", "A社", "P"), ("2026-07", "A社", "P")}
    assert all(c[0] != "DELETE" for c in state["calls"])            # 削除しない


def test_non_destructive_merge_keeps_prior_rows_same_month():
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"customer": "A社", "product": "P"}, {"customer": "B社", "product": "P"}],
        "db-1", "2607", "tok", req=req)
    res2 = sink.upsert_report_rows(
        [{"customer": "A社", "product": "P"}, {"customer": "C社", "product": "P"}],
        "db-1", "2607", "tok", req=req)
    assert res2["deleted"] == 0 and res2["updated"] == 1 and res2["created"] == 1
    assert _rows_in(state, "db-1") == {("2026-07", "A社", "P"), ("2026-07", "B社", "P"),
                                       ("2026-07", "C社", "P")}     # B が残る


def test_same_run_duplicate_rows_collapse():
    req, state = _make_store()
    rows = [{"customer": "A社", "contract_id": "C1", "product": "P", "comment": "old"},
            {"customer": "A社", "contract_id": "C1", "product": "P", "comment": "new"}]
    res = sink.upsert_report_rows(rows, "db-1", "2607", "tok", req=req)
    assert res["created"] == 1
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_COMMENT]["rich_text"][0]["text"]["content"] == "new"


def test_update_does_not_send_title():
    req, state = _make_store()
    row = {"customer": "A社", "product": "P", "comment": "x"}
    sink.upsert_report_rows([row], "db-1", "2607", "tok", req=req)
    sink.upsert_report_rows([dict(row, comment="y")], "db-1", "2607", "tok", req=req)
    patch = next(c for c in state["calls"] if c[0] == "PATCH" and c[1].startswith("/pages/"))
    assert sink.PROP_CUSTOMER not in patch[2]["properties"]


def test_target_month_stamped_on_update_too():
    """対象月は同定キーの一部ゆえ更新でも空クリアせず維持される。"""
    req, state = _make_store()
    row = {"customer": "A社", "product": "P"}
    sink.upsert_report_rows([row], "db-1", "2607", "tok", req=req)
    sink.upsert_report_rows([dict(row, comment="y")], "db-1", "2607", "tok", req=req)
    patch = next(c for c in state["calls"] if c[0] == "PATCH" and c[1].startswith("/pages/"))
    assert patch[2]["properties"][sink.PROP_TARGET_MONTH]["rich_text"][0]["text"]["content"] == "2026-07"


# ---------------------------------------------------------------------------
# cross-run safe guard + 構造的正常訂正 + multi-contract collapse
# ---------------------------------------------------------------------------

def test_cross_run_action_not_downgraded_by_bare_normal():
    """F-2: 前 run の 要対応 を、今 run の bare 正常 (構造事由なし) は無条件上書きしない。"""
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"gap_check": "要対応", "customer": "A社", "product": "P", "comment": "漏れ"}],
        "db-1", "2607", "tok", req=req)
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "A社", "product": "P", "comment": "正常"}],
        "db-1", "2607", "tok", req=req)
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    assert len(pages) == 1
    assert pages[0]["properties"][sink.PROP_MISSING_CHECK]["checkbox"] is False   # 要対応保持
    note = "".join((rt.get("text") or {}).get("content", "")
                   for rt in pages[0]["properties"][sink.PROP_COMMENT]["rich_text"])
    assert "cross-run safe guard" in note


def test_cross_run_structural_normal_corrects_prior_action():
    """F-D: 前 run の 要対応 を、今 run の構造的正常事由 (年契約周期) が訂正する (C03 fix を打ち消さない)。"""
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"gap_check": "要対応", "customer": "金子金物", "product": "利用料", "comment": "漏れ候補"}],
        "db-1", "2607", "tok", req=req)
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "金子金物", "product": "利用料",
          "period_diff": "前月あり今月なし (年契約周期)", "comment": "年間一括請求のため今月は請求なし=正常"}],
        "db-1", "2607", "tok", req=req)
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    assert len(pages) == 1
    assert pages[0]["properties"][sink.PROP_MISSING_CHECK]["checkbox"] is True    # 正常へ訂正
    note = "".join((rt.get("text") or {}).get("content", "")
                   for rt in pages[0]["properties"][sink.PROP_COMMENT]["rich_text"])
    assert "構造的正常事由で訂正" in note


def _rt_text(prop):
    return "".join((rt.get("text") or {}).get("content", "")
                   for rt in (prop or {}).get("rich_text", []))


def _page_title(props):
    tp = sink._title_prop_value(props) or {}
    return "".join((t.get("text") or {}).get("content", "") for t in tp.get("title", []))


def test_cross_run_reliable_mf_issued_corrects_prior_action():
    """K4: 前 run の 要対応 を、今 run の reliable MF-issued (C05 実額訂正) が正常へ訂正する。

    bare 正常 (継続発行だが reliable_issued 無し) なら保持されるところ、reliable_issued=True の
    権威ある実額訂正は _STRUCTURAL_NORMAL_MARKERS と同格の bypass 事由として正常☑へ訂正する。
    """
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"gap_check": "要対応", "customer": "アクメ商事", "product": "P", "comment": "漏れ候補(旧バグrun)"}],
        "db-1", "2607", "tok", req=req)
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "アクメ商事", "product": "P", "period_diff": "継続発行",
          "reliable_issued": True, "comment": "MF実績で発行済み"}],
        "db-1", "2607", "tok", req=req)
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    assert len(pages) == 1
    assert pages[0]["properties"][sink.PROP_MISSING_CHECK]["checkbox"] is True   # 正常へ訂正
    assert "MF実績の権威ある実額訂正" in _rt_text(pages[0]["properties"][sink.PROP_COMMENT])


def test_cross_run_bare_normal_without_reliable_flag_keeps_action():
    """K4 の裏: reliable_issued も構造事由も無い bare 正常は前 run の 要対応 を保持する (漏れ隠蔽防止)。

    要件1 で継続発行は構造的正常マーカー入りしたため、bare 正常の例は period_diff が
    マーカー非該当 (新規発行) の行を使う (継続発行は下の corrects テストで訂正側を検証)。
    """
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"gap_check": "要対応", "customer": "ベータ社", "product": "P", "comment": "漏れ"}],
        "db-1", "2607", "tok", req=req)
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "ベータ社", "product": "P", "period_diff": "新規発行",
          "reliable_issued": False, "comment": "正常"}],
        "db-1", "2607", "tok", req=req)
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    assert pages[0]["properties"][sink.PROP_MISSING_CHECK]["checkbox"] is False   # 要対応保持
    assert "cross-run safe guard" in _rt_text(pages[0]["properties"][sink.PROP_COMMENT])


def test_cross_run_continued_corrects_prior_action():
    """要件1(2026-07-10): 前 run の 要対応 を、今 run の継続発行 (両月あり=権威ある月契約正常) が
    reliable_issued 未確定でも正常✓へ訂正する (『金額あるのにチェックが入らない』の根治)。"""
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"gap_check": "要対応", "customer": "ガンマ社", "product": "P", "comment": "漏れ候補"}],
        "db-1", "2607", "tok", req=req)
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "ガンマ社", "product": "P", "period_diff": "継続発行",
          "reliable_issued": False, "comment": "継続発行 (前月・今月とも発行あり)"}],
        "db-1", "2607", "tok", req=req)
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    assert len(pages) == 1
    assert pages[0]["properties"][sink.PROP_MISSING_CHECK]["checkbox"] is True   # 正常✓へ訂正
    assert "構造的正常事由で訂正" in _rt_text(pages[0]["properties"][sink.PROP_COMMENT])


def test_k6_true_orphan_gets_residual_note_not_deleted():
    """K6: 今回 emit に無い対象月既存行 (真 orphan=旧 phantom) へ残置理由を注記する (行削除しない)。"""
    req, state = _make_store()
    # run1: 2 行を作る (残る社 / 消える社)。
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "残る社", "product": "P", "reliable_issued": True},
         {"gap_check": "要対応", "customer": "消える社", "product": "Q", "comment": "旧run phantom"}],
        "db-1", "2607", "tok", req=req)
    # run2: 残る社だけ emit → 消える社は今月MFにも契約在籍にも無い真 orphan。
    res = sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "残る社", "product": "P", "reliable_issued": True}],
        "db-1", "2607", "tok", req=req)
    assert res["orphaned"] == 1
    assert res["deleted"] == 0
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    assert len(pages) == 2   # 行削除しない (非破壊)
    orphan = next(p for p in pages if _page_title(p["properties"]) == "消える社")
    assert "残置行" in _rt_text(orphan["properties"][sink.PROP_COMPARISON])
    cmt = _rt_text(orphan["properties"][sink.PROP_COMMENT])
    assert "契約在籍にも無い" in cmt
    assert "旧run phantom" in cmt          # 既存コメントを消さず追記 (非破壊注記・F10 是正)
    # 冪等: 再 run で残置マーカーが増殖しない。
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "残る社", "product": "P", "reliable_issued": True}],
        "db-1", "2607", "tok", req=req)
    orphan2 = next(p for p in state["pages"].values()
                   if p["db"] == "db-1" and _page_title(p["properties"]) == "消える社")
    assert _rt_text(orphan2["properties"][sink.PROP_COMPARISON]).count("残置行") == 1


def test_k6_other_month_rows_not_flagged_as_orphan():
    """K6 境界: 別対象月の既存行 (Design D 単一 DB 共存) は当月 orphan 走査で触らない。"""
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "先月社", "product": "P", "reliable_issued": True}],
        "db-1", "2606", "tok", req=req)   # 先月分
    res = sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "今月社", "product": "P", "reliable_issued": True}],
        "db-1", "2607", "tok", req=req)   # 当月分 (先月社は別月ゆえ orphan にしない)
    assert res["orphaned"] == 0
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    senmonth = next(p for p in pages if _page_title(p["properties"]) == "先月社")
    assert sink.PROP_COMPARISON not in senmonth["properties"] or \
        "残置行" not in _rt_text(senmonth["properties"].get(sink.PROP_COMPARISON))


def test_multi_contract_action_survives_collapse():
    req, state = _make_store()
    rows = [
        {"gap_check": "正常", "customer": "A社", "product": "P", "contract_id": "C1", "comment": "正常契約"},
        {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2", "comment": "発行漏れ候補"},
    ]
    res = sink.upsert_report_rows(rows, "db-1", "2607", "tok", req=req)
    assert res["collapsed_multi_contract"] == 1
    posts = [c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages"]
    assert len(posts) == 1
    assert posts[0][2]["properties"][sink.PROP_MISSING_CHECK]["checkbox"] is False   # 要対応が生存


def test_same_severity_action_collapse_merges_comments():
    a = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C1", "comment": "漏れ甲"}
    b = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2", "comment": "漏れ乙"}
    merged = sink._prefer_action(a, b)
    assert "漏れ甲" in merged["comment"] and "漏れ乙" in merged["comment"]
    assert "C1" in merged["comment"] and "C2" in merged["comment"]


def test_action_action_collapse_preserves_prev_amount_symmetrically():
    """K-PREV 回帰: 要対応×要対応マージも今月金額と対称に先月金額の非 None を優先継承する。"""
    a = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C1",
         "comment": "漏れ甲", "prev_amount": None}
    b = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2",
         "comment": "漏れ乙", "prev_amount": 30000}
    merged = sink._prefer_action(a, b)
    assert sink._amount(merged, "prev_amount", "先月の金額") == 30000


def test_normal_normal_collapse_sums_prev_amount_symmetrically():
    """K-PREV 回帰: 正常×正常マージも今月金額の合算と対称に先月金額を合算保全する。"""
    a = {"gap_check": "正常", "customer": "A社", "product": "P",
         "amount": 100000, "prev_amount": 60000, "comment": "甲"}
    b = {"gap_check": "正常", "customer": "A社", "product": "P",
         "amount": 50000, "prev_amount": 40000, "comment": "乙"}
    merged = sink._prefer_action(a, b)
    assert sink._amount(merged, "amount", "curr_amount", "今月の金額") == 150000
    assert sink._amount(merged, "prev_amount", "先月の金額") == 100000


def test_action_action_collapse_sums_amount_when_both_have_own_amount():
    """K-SUM 回帰 (ユーザー実運用報告2026-07-10・近代プラント/OWB/マルワ/ミラタップ/京浜貿易/
    野嵩商会/マスヤ 等の「新規/年→月切替」複数契約 collapse): 要対応×要対応の両者が別契約の
    自己実額 (55000円 + 55000円) を持つとき、従来は base 側だけ残し other 側を無言で捨てて
    実額110,000円のところ55,000円のみ表示していた。正常×正常 (_merge_issued_amounts) と対称に
    Σ合算し、severity=要対応は保持したまま金額の過少表示を防ぐ。"""
    a = {"gap_check": "要対応", "customer": "近代プラント", "product": "P", "contract_id": "C1",
         "comment": "新規/年→月切替", "amount": 55000, "prev_amount": None}
    b = {"gap_check": "要対応", "customer": "近代プラント", "product": "P", "contract_id": "C2",
         "comment": "新規/年→月切替", "amount": 55000, "prev_amount": None}
    for merged in (sink._prefer_action(a, b), sink._prefer_action(b, a)):
        assert sink._severity_rank(merged) == 1, "要対応 severity を保持"
        assert sink._amount(merged, "amount", "curr_amount", "今月の金額") == 110000, \
            "両契約の自己実額を Σ合算し過少表示を防ぐ (順序非依存)"


def test_action_action_collapse_sums_prev_amount_when_both_have_own_prev_amount():
    """K-SUM 回帰: 先月実額も今月と対称に両者非 None なら Σ合算する。"""
    a = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C1",
         "comment": "甲", "prev_amount": 30000}
    b = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2",
         "comment": "乙", "prev_amount": 40000}
    merged = sink._prefer_action(a, b)
    assert sink._amount(merged, "prev_amount", "先月の金額") == 70000


# ---------------------------------------------------------------------------
# C03 (要因C5 sink側): collapse 発行済み実額保全 ∧ 漏れ隠蔽なし
# ---------------------------------------------------------------------------
def test_collapse_phantom_same_identity_resolves_to_normal():
    """新不変則 (Fix B・identity gate): 同一契約が ID照合↔名前照合で二重化した **phantom**
    (contract_id/エンドクライアント一致=identity 同一) が発行済み×gap で collapse するとき、今月の
    権威ある実発行が当月請求を満たす → 正常✓ (record2 ツネマツ型の根治)。gap 候補根拠はコメント保全。
    別契約でなく重複ゆえ漏れ隠蔽にならない。"""
    issued = {"gap_check": "正常", "customer": "ツネマツ", "product": "利用料（2年目以降）",
              "amount": 50000, "reliable_issued": True, "comment": "当月実発行"}   # identity=("","")
    gap = {"gap_check": "要対応", "customer": "ツネマツ", "product": "利用料（2年目以降）",
           "amount": None, "reliable_issued": False, "comment": "継続発行漏れ候補"}  # identity=("","") 同一
    for merged in (sink._prefer_action(issued, gap), sink._prefer_action(gap, issued)):
        assert sink._severity_rank(merged) == 0, "phantom は今月実発行で正常✓ (record2 根治)"
        assert sink._amount(merged, "amount", "curr_amount", "今月の金額") == 50000, "実発行額を保全"
        assert "継続発行漏れ候補" in (merged.get("comment") or ""), "重複候補の根拠を黙殺しない"


def test_collapse_distinct_endclient_preserves_action_no_hiding():
    """漏れ隠蔽の封鎖 (3体エレガント検証 CRITICAL の是正): 代理店の別エンドクライアント=**真の別契約**
    (identity 相違) が発行済み×gap で collapse するとき、gap は本物の発行漏れでありうるため正常化せず
    要対応を保持する (漏れ隠蔽 false-negative を防ぐ)。発行済み実額は今月金額へ保全し金額も失わない。"""
    issued = {"gap_check": "正常", "customer": "HOSONO", "product": "チイキズカン業務委託費",
              "amount": 70000, "reliable_issued": True, "end_client": "乙様", "comment": "（乙様）発行済み"}
    gap = {"gap_check": "要対応", "customer": "HOSONO", "product": "チイキズカン業務委託費",
           "amount": None, "reliable_issued": False, "end_client": "丙様", "comment": "（丙様）発行漏れ候補"}
    for merged in (sink._prefer_action(issued, gap), sink._prefer_action(gap, issued)):
        assert sink._severity_rank(merged) == 1, "別契約(エンドクライアント違い)の漏れを隠さず要対応を保持"
        assert sink._amount(merged, "amount", "curr_amount", "今月の金額") == 70000, \
            "発行済み実額は今月金額へ保全 (金額も失わない)"
        assert "発行済み実額" in (merged.get("comment") or "")


def test_collapse_normal_without_issued_returns_action_unchanged():
    """保全すべき発行済み実額が無い (bare 正常・reliable_issued 無し) なら要対応行をそのまま返す
    (従来挙動・不要な dict コピーを避ける)。"""
    normal = {"gap_check": "正常", "customer": "A社", "product": "P"}
    action = {"gap_check": "要対応", "customer": "A社", "product": "P"}
    assert sink._prefer_action(normal, action) is action
    assert sink._prefer_action(action, normal) is action


def test_collapse_distinct_does_not_overwrite_action_own_amount():
    """別契約 (エンドクライアント違い) で要対応行が既に金額を持つなら発行済み実額で上書きしない (据え置き)。"""
    issued = {"gap_check": "正常", "customer": "A社", "product": "P", "amount": 70000,
              "reliable_issued": True, "end_client": "甲"}
    gap = {"gap_check": "要対応", "customer": "A社", "product": "P", "amount": 55000, "end_client": "乙"}
    merged = sink._prefer_action(gap, issued)
    assert sink._severity_rank(merged) == 1
    assert sink._amount(merged, "amount", "curr_amount", "今月の金額") == 55000, "要対応行の金額を据え置く"


def test_collapse_3way_distinct_preserves_issued_amount_order_independent():
    """F-TRADE-1 回帰: 別契約3者衝突 (発行済み正常 + 要対応A + 要対応B・全て別エンドクライアント) が
    同一キーへ collapse するとき、発行済み実額が要対応×要対応マージで null に潰れず保全され続ける
    (順序非依存)。別契約ゆえ要対応 severity は保持し漏れを隠さない。"""
    issued = {"gap_check": "正常", "customer": "代理店", "product": "業務委託費",
              "amount": 70000, "reliable_issued": True, "end_client": "甲", "comment": "（甲様）発行済み"}
    gapA = {"gap_check": "要対応", "customer": "代理店", "product": "業務委託費",
            "amount": None, "end_client": "乙", "comment": "（乙様）漏れ"}
    gapB = {"gap_check": "要対応", "customer": "代理店", "product": "業務委託費",
            "amount": None, "end_client": "丙", "comment": "（丙様）漏れ"}
    import itertools
    for order in itertools.permutations([issued, gapA, gapB]):
        acc = order[0]
        for nxt in order[1:]:
            acc = sink._prefer_action(acc, nxt)
        assert sink._severity_rank(acc) == 1, f"別契約は要対応 severity 保持 (順序={[r['comment'] for r in order]})"
        assert sink._amount(acc, "amount") == 70000, \
            f"発行済み実額 70000 が保全される (順序={[r['comment'] for r in order]}・自己矛盾行を作らない)"


def test_collapse_distinct_severity_mixed_sums_multiple_issued_amounts_order_independent():
    """BUG-1 回帰: 別契約 (異エンドクライアント) の reliable 正常2件以上 + 要対応が collapse するとき、
    要対応が畳込順の最後でなくても発行済み実額が Σ 保全され過少報告しない (fold 順非依存)。別契約ゆえ
    要対応 severity を保持しつつ発行済み総額を今月金額へ保全する。"""
    ko = {"gap_check": "正常", "customer": "HOSONO", "product": "業務委託費",
          "amount": 210000, "reliable_issued": True, "end_client": "甲", "comment": "（甲様）発行済み"}
    otsu = {"gap_check": "正常", "customer": "HOSONO", "product": "業務委託費",
            "amount": 70000, "reliable_issued": True, "end_client": "乙", "comment": "（乙様）発行済み"}
    hei = {"gap_check": "要対応", "customer": "HOSONO", "product": "業務委託費",
           "amount": None, "end_client": "丙", "comment": "（丙様）発行漏れ候補"}
    import itertools
    for order in itertools.permutations([ko, otsu, hei]):
        acc = order[0]
        for nxt in order[1:]:
            acc = sink._prefer_action(acc, nxt)
        labels = [r["comment"] for r in order]
        assert sink._severity_rank(acc) == 1, f"別契約は要対応 severity 保持 (順序={labels})"
        assert sink._amount(acc, "amount") == 280000, \
            f"発行済み実額 210000+70000=280000 を Σ 保全 (順序={labels}・2件目以降を脱落させない)"


def test_distinct_severity_mixed_collapse_through_upsert_keeps_action():
    """実 entry point (upsert_report_rows) を通して、別契約 (異エンドクライアント) の severity 混在
    collapse が要対応☐ を保持し発行済み実額 Σ を number 列『今月の金額』へ着地させる (漏れを隠さず
    金額も失わない・本番配線)。identity 相違で multi-contract counter も発火する。"""
    ko = {"gap_check": "正常", "customer": "HOSONO", "product": "業務委託費", "amount": 210000,
          "reliable_issued": True, "end_client": "甲", "comment": "（甲様）発行済み"}
    otsu = {"gap_check": "正常", "customer": "HOSONO", "product": "業務委託費", "amount": 70000,
            "reliable_issued": True, "end_client": "乙", "comment": "（乙様）発行済み"}
    hei = {"gap_check": "要対応", "customer": "HOSONO", "product": "業務委託費", "amount": None,
           "end_client": "丙", "comment": "（丙様）発行漏れ候補"}
    for order in ([hei, ko, otsu], [ko, otsu, hei], [ko, hei, otsu]):   # 要対応=先頭/最後/中間
        req, state = _make_store()
        result = sink.upsert_report_rows(order, "db-1", "2606", "tok", req=req)
        posts = [c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages"]
        assert len(posts) == 1, "3契約が同一(取引先,商品)へ collapse し1行"
        props = posts[0][2]["properties"]
        assert props[sink.PROP_MISSING_CHECK]["checkbox"] is False, "別契約の漏れを隠さず要対応☐ を保持"
        assert props[sink.PROP_CURR_AMOUNT]["number"] == 280000, \
            "発行済み実額 210000+70000 が number 列へ Σ 着地 (fold 順非依存・過少報告なし)"
        assert result["collapsed_multi_contract"] >= 1, "別契約 collapse を可観測化 (ゼロテレメトリ封鎖)"


def test_collapse_distinct_preserves_action_when_action_has_own_amount():
    """別契約で要対応行が自己金額を持つ場合、発行済み実額で上書きせず据え置き、要対応を保持する。"""
    issued = {"gap_check": "正常", "customer": "A社", "product": "P", "amount": 70000,
              "reliable_issued": True, "end_client": "甲"}
    action_with_amt = {"gap_check": "要対応", "customer": "A社", "product": "P", "amount": 55000,
                       "end_client": "乙"}
    merged = sink._prefer_action(action_with_amt, issued)
    assert sink._severity_rank(merged) == 1, "別契約の要対応を保持"
    assert sink._amount(merged, "amount") == 55000, "要対応行の自己金額を据え置く"
    assert "別契約に発行済み実額" in (merged.get("comment") or "")


def test_collapse_notes_avoid_english_jargon():
    """F-NAIVE1 回帰: 経理担当向け成果物の注記に英 IT 用語 'collapse' を出さない (平易な日本語)。"""
    issued = {"gap_check": "正常", "customer": "A社", "product": "P", "amount": 70000,
              "reliable_issued": True, "comment": "発行済み"}
    gap = {"gap_check": "要対応", "customer": "A社", "product": "P", "amount": None,
           "comment": "漏れ"}
    merged = sink._prefer_action(issued, gap)
    assert "collapse" not in (merged.get("comment") or "").lower()
    # 要対応×要対応マージの注記も同様。
    a = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C1", "comment": "甲"}
    b = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2", "comment": "乙"}
    assert "collapse" not in (sink._prefer_action(a, b).get("comment") or "").lower()


def test_failed_row_is_isolated_and_counted_as_skipped():
    posts = []

    def req(method, path, token, body=None):
        if method == "POST" and path.endswith("/query"):
            return {"results": [], "has_more": False}
        if method == "POST" and path == "/pages":
            posts.append(body)
            if len(posts) == 2:
                raise RuntimeError("boom")
            return {"id": f"pg{len(posts)}"}
        raise AssertionError((method, path))

    rows = [{"customer": "A社", "product": "P1"}, {"customer": "B社", "product": "P2"},
            {"customer": "C社", "product": "P3"}]
    res = sink.upsert_report_rows(rows, "db-1", "2607", "tok", req=req)
    assert res == {"created": 2, "updated": 0, "skipped": 1, "deleted": 0,
                   "collapsed_multi_contract": 0, "orphaned": 0}


def test_row_contract_maps_every_producer_key_to_column():
    """ROW_CONTRACT の各 producer キーが _build_row_props で mapped 列へ着地する (SSOT drift 検出)。"""
    sentinels = {
        "gap_check": "要対応", "customer": "顧客X", "target_month": "2607", "product": "商品Y",
        "prev_amount": 111, "amount": 222, "period_diff": "比較Z", "comment": "コメントW",
    }
    props = sink._build_row_props(sentinels, "2026-07", creating=True)
    for producer_key, col in sink.ROW_CONTRACT.items():
        assert col in props, f"ROW_CONTRACT[{producer_key}]→{col} が不在 (SSOT drift)"
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is False
    assert props[sink.PROP_TARGET_MONTH]["rich_text"][0]["text"]["content"] == "2026-07"
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 111
    assert props[sink.PROP_CURR_AMOUNT]["number"] == 222


# ---------------------------------------------------------------------------
# query_month: ページング + dedup + 当該 DB スコープ
# ---------------------------------------------------------------------------

def test_query_month_paginates_and_dedups():
    pages = [
        {"results": [{"id": "a", "properties": {}}, {"id": "b", "properties": {}}],
         "has_more": True, "next_cursor": "c2"},
        {"results": [{"id": "b", "properties": {}}, {"id": "c", "properties": {}}], "has_more": False},
    ]
    cursors = []

    def req(method, path, token, body=None):
        cursors.append((body or {}).get("start_cursor"))
        assert path == "/databases/db-1/query"
        return pages.pop(0)

    out = sink.query_month("db-1", "tok", req=req)
    assert [p["id"] for p in out] == ["a", "b", "c"]
    assert cursors == [None, "c2"]


def test_list_block_children_paginates():
    pages = [
        {"results": [{"id": "x"}], "has_more": True, "next_cursor": "n2"},
        {"results": [{"id": "y"}], "has_more": False},
    ]
    seen = []

    def req(method, path, token, body=None):
        seen.append(path)
        return pages.pop(0)

    out = sink.list_block_children("PAGE", "tok", req=req)
    assert [b["id"] for b in out] == ["x", "y"]
    assert "start_cursor=n2" in seen[1]


# ---------------------------------------------------------------------------
# run() orchestration (resolve → upsert) + dry-run + fail-closed
# ---------------------------------------------------------------------------

def _cfg(toggle="TOG", page="PAGE"):
    return {"notion": {"report_parent_page": page, "report_toggle_block": toggle}}


def test_run_apply_updates_toggle_db():
    """run(apply) はトグル内の既存 DB を更新対象にし upsert する (db_location='in-block')。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-tog", "請求漏れ比較レポート 2026-06")]},
        dbs={"db-tog": {"title": "請求漏れ比較レポート 2026-06", "properties": _default_props()}})
    rows = [{"customer": "A社", "product": "P", "amount": 5}]
    res = sink.run(rows, "2607", _cfg(), "tok", req=req, apply=True)
    assert res["created"] == 1 and res["db_location"] == "in-block"
    assert res["report_db_id"] == "db-tog"
    assert _rows_in(state, "db-tog") == {("2026-07", "A社", "P")}


def test_run_writes_to_user_created_db_with_nondefault_title_column():
    """run(apply) はユーザー手作り DB (title 列名『名前』) へも行を書く。

    title 列名を『取引先名』固定で送ると DB に無い列名で POST 400 → 全行 skip の沈黙失敗になる。
    _ensure_db_schema が title 列の実名『名前』を検出し、行 POST の title を『名前』へ書くことで
    created>0 を保証する (要件『有れば更新』が手作り DB でも成立する回帰防止)。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-user", "請求漏れ確認レポート")]},
        dbs={"db-user": {"title": "請求漏れ確認レポート", "properties": _user_props("名前")}})
    res = sink.run([{"customer": "A社", "product": "P", "amount": 5}], "2607",
                   _cfg(), "tok", req=req, apply=True)
    assert res["report_db_id"] == "db-user" and res["db_location"] == "in-block"
    assert res["created"] == 1 and res["skipped"] == 0                 # 全 skip でない
    post = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert post["名前"]["title"][0]["text"]["content"] == "A社"       # 実 title 列名へ書く
    assert "取引先名" not in post                                      # 存在しない列名を送らない
    # 2 回目 run は同一行を PATCH 更新 (title 非依存の _page_match_key が既存を突合)。
    r2 = sink.run([{"customer": "A社", "product": "P", "amount": 9}], "2607",
                  _cfg(), "tok", req=req, apply=True)
    assert r2["updated"] == 1 and r2["created"] == 0


def test_upsert_backfills_legacy_row_without_target_month():
    """対象月が空の既存行 (旧 DB/手作り DB からの移行) は当月行として backfill 更新し二重作成しない。

    採用した既存 DB に対象月未設定の行があると、当月行 (対象月あり) が同定キー不一致で新規作成され
    同一 (取引先,商品) が二重化しうる。migrate_fallback が (取引先,商品) で空月行を当月行へ寄せ、
    update が対象月を backfill する (以後は通常キーで一致・二重化なし)。"""
    req, state = _make_store()
    state["pages"]["pg-legacy"] = {"db": "db-1", "properties": {
        sink.PROP_CUSTOMER: {"title": [{"text": {"content": "金子金物"}}]},
        sink.PROP_PRODUCT: {"rich_text": [{"text": {"content": "利用料"}}]},
    }}   # 対象月列なし=移行前の行
    res = sink.upsert_report_rows(
        [{"customer": "金子金物", "product": "利用料", "amount": 5000}],
        "db-1", "2606", "tok", req=req)
    assert res["created"] == 0 and res["updated"] == 1        # 新規でなく既存を backfill 更新
    backfilled = state["pages"]["pg-legacy"]["properties"]
    assert backfilled[sink.PROP_TARGET_MONTH]["rich_text"][0]["text"]["content"] == "2026-06"
    assert _rows_in(state, "db-1") == {("2026-06", "金子金物", "利用料")}   # 二重化なし (1 行)


def test_upsert_legacy_backfill_adopts_each_blank_row_once():
    """空月行は 1 行につき 1 回だけ採用する (複数当月行が同じ空行を奪い合い誤マージしない)。"""
    req, state = _make_store()
    state["pages"]["pg-blank"] = {"db": "db-1", "properties": {
        sink.PROP_CUSTOMER: {"title": [{"text": {"content": "A社"}}]},
    }}   # 商品名も対象月も空の 1 行
    # 同一取引先で商品違いの当月 2 行。空行の (A社,'') に一致するのは商品空の 1 行のみ。
    res = sink.upsert_report_rows(
        [{"customer": "A社", "product": "", "amount": 1},
         {"customer": "A社", "product": "P2", "amount": 2}],
        "db-1", "2607", "tok", req=req)
    assert res["updated"] == 1 and res["created"] == 1        # 空行は 1 回 backfill・他は新規


def test_run_reuse_across_two_runs_single_db():
    """同一トグル DB を 2 回 run: 同月は上書き・別月は共存 (単一 DB・非破壊)。"""
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-tog", "請求漏れ比較レポート")]},
        dbs={"db-tog": {"title": "請求漏れ比較レポート", "properties": _default_props()}})
    sink.run([{"customer": "A社", "product": "P"}], "2606", _cfg(), "tok", req=req, apply=True)
    r2 = sink.run([{"customer": "A社", "product": "P", "comment": "d2"}], "2607", _cfg(),
                  "tok", req=req, apply=True)
    assert r2["report_db_id"] == "db-tog"
    assert _rows_in(state, "db-tog") == {("2026-06", "A社", "P"), ("2026-07", "A社", "P")}


def test_run_aborts_phantom_when_no_pin_no_existing():
    """要件2(2026-07-10): 明示 pin なし かつ 既存 DB 未発見時は phantom を作らず fail-closed (SinkError)。"""
    import pytest
    req, state = _make_store(block_children={"TOG": [], "PAGE": []})
    with pytest.raises(sink.SinkError):
        sink.run([{"customer": "A社", "product": "P"}], "2607", _cfg(), "tok", req=req, apply=True)
    # phantom を作っていない (POST /databases が呼ばれていない)。
    assert not any(m == "POST" and p == "/databases" for m, p, _ in state["calls"])


def test_run_allow_create_creates_when_none():
    """要件2: --allow-create 明示 opt-in 時のみ従来どおり見出しの下へ新規作成する (初回セットアップ)。"""
    req, state = _make_store(block_children={"TOG": [], "PAGE": []})
    res = sink.run([{"customer": "A社", "product": "P"}], "2607", _cfg(), "tok", req=req,
                   apply=True, allow_create=True)
    assert res["db_created"] is True and res["db_location"] == "page-created"
    assert res["created"] == 1


def test_run_pinned_db_id_writes_directly_step0():
    """要件2 step0: config report_database_id があれば構造同定を経ずその DB へ直接 upsert (pinned)。"""
    req, state = _make_store(dbs={"PINNED-DB": {"properties": _default_props()}})
    cfg = {"notion": {"report_parent_page": "PAGE", "report_toggle_block": "TOG",
                      "report_database_id": "PINNED-DB"}}
    res = sink.run([{"customer": "A社", "product": "P", "amount": 5}], "2607", cfg, "tok",
                   req=req, apply=True)
    assert res["db_location"] == "pinned"
    assert res["report_db_id"] == "PINNED-DB"
    assert res["created"] == 1
    # 構造同定 (トグル/ページ子ブロック探索) を経ていない=pin で直接着地。
    assert not any("/blocks/" in p for m, p, _ in state["calls"])


def test_run_pin_from_view_url_extracts_db_id():
    """要件2 (OQ-10 c 最小): ビュー/DB URL の path 側 32hex を DB id として抽出し pin する。"""
    req, state = _make_store(dbs={"39907a0cd18c81c19d61d42ee95016b0": {"properties": _default_props()}})
    url = "https://www.notion.so/ws/39907a0cd18c81c19d61d42ee95016b0?v=39907a0cd18c81bd923e000cda89bd33"
    cfg = {"notion": {"report_parent_page": "PAGE", "report_database_id": url}}
    res = sink.run([{"customer": "A社", "product": "P"}], "2607", cfg, "tok", req=req, apply=True)
    assert res["db_location"] == "pinned"
    assert res["report_db_id"] == "39907a0cd18c81c19d61d42ee95016b0"


def test_resolve_no_create_returns_none_when_disallowed():
    """resolve_report_db: allow_create=False かつ 既存未発見なら (None,'none') を返す (phantom 抑止)。"""
    req, state = _make_store(block_children={"TOG": [], "PAGE": []})
    db_id, location, created, _ = sink.resolve_report_db(
        "TOG", "PAGE", "tok", req=req, allow_create=False)
    assert db_id is None and location == "none" and created is False


def test_extract_db_id_forms():
    """要件2 (OQ-10 c): 生 32hex / dashed uuid / ビュー URL / タイトル付き『リンクをコピー』URL / 非id。"""
    hexid = "39907a0cd18c81c19d61d42ee95016b0"
    assert sink._extract_db_id(hexid) == hexid
    assert sink._extract_db_id("39907a0c-d18c-81c1-9d61-d42ee95016b0") == hexid
    assert sink._extract_db_id(f"https://www.notion.so/ws/{hexid}?v=abc123") == hexid
    # タイトルスラッグ付き URL: slug 末尾 dash 後の 32hex を id として採る (タイトル内 hex と分離)。
    assert sink._extract_db_id(f"https://www.notion.so/ws/My-Report-Table-{hexid}?v=deadbeef") == hexid
    assert sink._extract_db_id("PINNED-DB") == "PINNED-DB"   # 非 id は原値 (下流 GET が弾く)
    assert sink._extract_db_id("") == ""
    assert sink._extract_db_id(None) == ""


def test_run_dry_run_touches_no_network():
    called = []

    def req(method, path, token, body=None):
        called.append((method, path))
        raise AssertionError("dry-run must not call network")

    res = sink.run([{"customer": "A社"}, {"product": "no-customer"}], "2607", _cfg(), None,
                   req=req, apply=False)
    assert called == []
    assert res["dry_run"] is True
    assert res["planned_rows"] == 1 and res["skipped"] == 1
    assert res["report_db_id"] is None
    assert "トグル" in res["placement"]["note"]


def test_run_invalid_target_raises():
    import pytest
    with pytest.raises(sink.SinkError):
        sink.run([], "2699", _cfg(), "tok", apply=True)


def test_run_missing_parent_page_raises_on_apply():
    import pytest
    with pytest.raises(sink.SinkError):
        sink.run([{"customer": "A"}], "2607", {"notion": {"report_toggle_block": "TOG"}},
                 "tok", apply=True)


def test_run_target_month_mismatch_is_fail_closed():
    """F-7: 行の target_month と --target 不一致は誤月投入を防ぐため fail-closed。"""
    import pytest
    rows = [{"customer": "A社", "product": "P", "target_month": "2605"}]
    with pytest.raises(sink.SinkError):
        sink.run(rows, "2607", _cfg(), None, apply=False)
    ok = sink.run([{"customer": "A社", "target_month": "2607"}], "2607", _cfg(), None, apply=False)
    assert ok["dry_run"] is True


# ---------------------------------------------------------------------------
# main() CLI (dry-run / apply / fail-closed)
# ---------------------------------------------------------------------------

def test_main_dry_run(tmp_path, capsys):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([{"customer": "A社", "product": "P"}]), encoding="utf-8")
    rc = sink.main(["--rows", str(rows_file), "--target", "2607"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True and out["report_db_id"] is None


def test_main_apply_wires_fake_req(tmp_path, capsys, monkeypatch):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([{"customer": "A社", "product": "P", "amount": 3}]), encoding="utf-8")
    req, state = _make_store(
        block_children={"TOG": [_db_block("db-tog", "請求漏れ比較レポート")]},
        dbs={"db-tog": {"title": "請求漏れ比較レポート", "properties": _default_props()}})
    monkeypatch.setattr(sink, "load_config", lambda p=None: _cfg())
    monkeypatch.setattr(sink, "_notion_token", lambda cfg=None: "tok")
    monkeypatch.setattr(sink, "_req", req)
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply", "--verified"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["created"] == 1 and out["report_db_id"] == "db-tog"


def test_main_invalid_rows_json_fails_closed(tmp_path, capsys):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    rc = sink.main(["--rows", str(rows_file), "--target", "2607"])
    assert rc == 2
    assert "JSON list" in capsys.readouterr().err


def test_main_apply_without_verified_fails_closed(tmp_path, capsys):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([{"customer": "A社"}]), encoding="utf-8")
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply"])
    assert rc == 2
    assert "--verified" in capsys.readouterr().err


def test_main_token_missing_is_fail_closed_exit2(tmp_path, monkeypatch):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sink, "load_config", lambda *a, **k: _cfg())

    def _boom(cfg):
        raise RuntimeError("NOTION_API_KEY 未設定")

    monkeypatch.setattr(sink, "_notion_token", _boom)
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply", "--verified"])
    assert rc == 2


def test_main_apply_runtime_failure_is_fail_closed_exit2(tmp_path, monkeypatch):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sink, "load_config", lambda *a, **k: _cfg())
    monkeypatch.setattr(sink, "_notion_token", lambda cfg: "tok")

    def _api_reject(*a, **k):
        raise RuntimeError("Notion API 拒否")

    monkeypatch.setattr(sink, "run", _api_reject)
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply", "--verified"])
    assert rc == 2


# ---------------------------------------------------------------------------
# SEAM 統合テスト (C03 実出力 → C04 入力・8 列全充足)
# ---------------------------------------------------------------------------

def test_seam_c05_output_populates_all_columns():
    import mfk_period_report as engine
    curr = {"target_month": "2606", "rows": [
        {"取引先": "継続社", "商品": "月額", "verdict": "MATCH_MONTHLY", "現行単価": 12000}]}
    prev = {"rows": [
        {"取引先": "継続社", "商品": "月額", "verdict": "MATCH_MONTHLY", "現行単価": 10000}]}
    rows = engine.build_report(curr, prev, target_month="2606")
    assert len(rows) == 1 and rows[0]["gap_check"] == "正常"

    req, state = _make_store()
    res = sink.upsert_report_rows(rows, "db-1", "2606", "tok", req=req)
    assert res["created"] == 1
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_CUSTOMER]["title"][0]["text"]["content"] == "継続社"
    assert props[sink.PROP_TARGET_MONTH]["rich_text"][0]["text"]["content"] == "2026-06"
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is True
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 10000
    assert props[sink.PROP_CURR_AMOUNT]["number"] == 12000
    assert props[sink.PROP_COMPARISON]["rich_text"][0]["text"]["content"]
    assert props[sink.PROP_COMMENT]["rich_text"][0]["text"]["content"]


def test_seam_stopped_row_has_empty_curr_amount_but_populated_check():
    import mfk_period_report as engine
    curr = {"target_month": "2606", "rows": []}
    prev = {"rows": [{"取引先": "漏れ社", "商品": "月額", "verdict": "MATCH_MONTHLY", "現行単価": 5000}]}
    rows = engine.build_report(curr, prev, target_month="2606")
    assert len(rows) == 1 and rows[0]["gap_check"] == "要対応"
    req, state = _make_store()
    sink.upsert_report_rows(rows, "db-1", "2606", "tok", req=req)
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is False
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 5000
    assert sink.PROP_CURR_AMOUNT not in props or props[sink.PROP_CURR_AMOUNT].get("number") is None
    assert props[sink.PROP_TARGET_MONTH]["rich_text"][0]["text"]["content"] == "2026-06"
