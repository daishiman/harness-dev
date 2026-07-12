#!/usr/bin/env python3
"""notion_sheet_archive.py (月次アーカイブ&ロールオーバー) を fake-store req モックで完全オフライン検証する。

検証面:
  - dry-run (plan_archive) は Notion へ一切書き込まない (GET/query のみ)。
  - apply は 対象月行を写像先 DB へ移行し、読み戻し検証成功行だけ元シートを archive(削除) する。
  - スキーマ写像: 同型は保持・API 非対応型 (status 等) は rich_text へ降格して値温存・元ページID 付与。
  - 冪等: 再実行で写像先に重複行を作らない (元ページID で PATCH)・archive 済みは query 対象外で no-op。
  - fail-closed: 検証不一致行は元シートから削除しない (温存)・長文は chunk して滞留させない。
ネットワークは一切叩かない (req 注入)。
"""
import json
import os
import sys

import notion_sheet_archive as arch


# ---------------------------------------------------------------------------
# fake Notion store: DB(properties/parent) + 親ページの child ブロック + ページ(archived 状態) を模す。
# ---------------------------------------------------------------------------
def _make_store():
    state = {
        "dbs": {},          # db_id -> {"title", "properties", "parent"}
        "children": {},     # page_id -> [child blocks]
        "pages": {},        # page_id -> {"db", "properties", "archived"}
        "seq": 0,
        "calls": [],
    }

    def _next(prefix):
        state["seq"] += 1
        return f"{prefix}-{state['seq']:04d}"

    def req(method, path, token, body=None):
        state["calls"].append((method, path.split("?")[0], body))
        base = path.split("?")[0]

        if method == "GET" and base.startswith("/databases/"):
            dbid = base[len("/databases/"):]
            db = state["dbs"].get(dbid, {})
            return {"id": dbid, "properties": db.get("properties", {}),
                    "parent": db.get("parent", {})}

        if method == "PATCH" and base.startswith("/databases/"):
            dbid = base[len("/databases/"):]
            props = state["dbs"].setdefault(dbid, {"properties": {}})["properties"]
            for n, d in (body.get("properties") or {}).items():
                props[n] = d
            return {"id": dbid}

        if method == "POST" and base == "/databases":
            dbid = _next("db")
            title = "".join(t.get("text", {}).get("content", "") for t in body.get("title", []))
            parent_page = (body.get("parent") or {}).get("page_id")
            state["dbs"][dbid] = {"title": title,
                                  "properties": dict(body.get("properties") or {}),
                                  "parent": {"type": "page_id", "page_id": parent_page}}
            state["children"].setdefault(parent_page, []).append(
                {"id": dbid, "type": "child_database", "child_database": {"title": title}})
            return {"id": dbid, "url": f"https://notion.so/{dbid}"}

        if method == "GET" and base.startswith("/blocks/") and base.endswith("/children"):
            pid = base[len("/blocks/"):-len("/children")]
            return {"results": list(state["children"].get(pid, [])), "has_more": False}

        if method == "POST" and base.startswith("/databases/") and base.endswith("/query"):
            dbid = base[len("/databases/"):-len("/query")]
            flt = (body or {}).get("filter")
            out = []
            for pid, pg in state["pages"].items():
                if pg["db"] != dbid or pg.get("archived"):
                    continue  # Notion query は archived(trash) を既定で返さない
                if flt:
                    want = ((flt.get("select") or {}).get("equals"))
                    prop = pg["properties"].get(flt.get("property"))
                    if arch.prop_plain_text(prop) != want:
                        continue
                out.append({"id": pid, "properties": pg["properties"]})
            return {"results": out, "has_more": False}

        if method == "POST" and base == "/pages":
            pid = _next("page")
            dbid = (body.get("parent") or {}).get("database_id")
            state["pages"][pid] = {"db": dbid, "properties": dict(body.get("properties") or {}),
                                   "archived": False}
            return {"id": pid}

        if method == "PATCH" and base.startswith("/pages/"):
            pid = base[len("/pages/"):]
            pg = state["pages"][pid]
            if "properties" in (body or {}):
                pg["properties"].update(body["properties"])
            if "archived" in (body or {}):
                pg["archived"] = bool(body["archived"])
            return {"id": pid}

        if method == "GET" and base.startswith("/pages/"):
            pid = base[len("/pages/"):]
            pg = state["pages"][pid]
            return {"id": pid, "properties": pg["properties"], "archived": pg.get("archived")}

        raise AssertionError(f"unexpected req: {method} {path} {body}")

    return state, req


# ---------------------------------------------------------------------------
# fixtures: 請求書確認シート DB (親ページ配下) + 2606 3行 / 2605 1行。
# ---------------------------------------------------------------------------
SHEET_DB = "sheet-db"
PARENT_PAGE = "parent-page"


def _sheet_props_schema():
    return {
        "取引先": {"type": "title", "title": {}},
        "年月": {"type": "select", "select": {"options": [{"name": "2606", "color": "blue"},
                                                          {"name": "2605", "color": "gray"}]}},
        "金額": {"type": "number", "number": {"format": "yen"}},
        "確認内容": {"type": "rich_text", "rich_text": {}},
        "AI確認": {"type": "checkbox", "checkbox": {}},
        "判定": {"type": "status", "status": {}},  # API で作成不可→rich_text へ降格される
    }


def _row(title, ym, amount, note, ai, judge):
    return {
        "取引先": {"type": "title", "title": [{"text": {"content": title}}]},
        "年月": {"type": "select", "select": {"name": ym}},
        "金額": {"type": "number", "number": amount},
        "確認内容": {"type": "rich_text", "rich_text": [{"text": {"content": note}}]},
        "AI確認": {"type": "checkbox", "checkbox": ai},
        "判定": {"type": "status", "status": {"name": judge}},
    }


def _seed(state, rows_2606, rows_2605=0, long_note=False):
    state["dbs"][SHEET_DB] = {
        "title": "請求書確認シート",
        "properties": _sheet_props_schema(),
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
    }
    state["children"].setdefault(PARENT_PAGE, [])
    n = 0
    for i in range(rows_2606):
        n += 1
        note = ("あ" * 2500) if (long_note and i == 0) else f"確認内容{i}"
        state["pages"][f"src-2606-{i}"] = {
            "db": SHEET_DB, "archived": False,
            "properties": _row(f"取引先{i}", "2606", 1000 * (i + 1), note, i % 2 == 0, "発行漏れ"),
        }
    for i in range(rows_2605):
        state["pages"][f"src-2605-{i}"] = {
            "db": SHEET_DB, "archived": False,
            "properties": _row(f"別月先{i}", "2605", 500, "先月分", True, "AIの確認OK"),
        }


# ===========================================================================
# tests
# ===========================================================================
def test_mirror_schema_demotes_status_and_adds_source_id():
    props, plan, prov = arch.mirror_schema(_sheet_props_schema())
    names = [c["name"] for c in plan]
    assert names == ["取引先", "年月", "金額", "確認内容", "AI確認", "判定"]
    demoted = [c["name"] for c in plan if c["demoted"]]
    assert demoted == ["判定"]                          # status は rich_text へ降格
    assert "title" in props["取引先"]                    # title は保持
    assert props["金額"]["number"]["format"] == "yen"    # number format 継承
    assert "rich_text" in props["判定"]                  # 降格先
    assert prov == arch.PROP_SOURCE_ID                   # 衝突なし→既定の冪等キー
    assert prov in props                                 # 冪等キー列を付与
    assert prov not in names                             # provenance は plan(検証対象)に含めない


def test_dry_run_makes_no_writes():
    state, req = _make_store()
    _seed(state, rows_2606=3, rows_2605=1)
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    assert planned["source_count"] == 3                  # 2605 行は対象外
    assert planned["archive_db_exists"] is False
    assert planned["demoted_columns"] == ["判定"]
    # dry-run は書き込み系メソッドを一切呼ばない。
    writes = [c for c in state["calls"] if c[0] in ("POST", "PATCH") and not c[1].endswith("/query")]
    assert writes == [], writes


def test_apply_migrates_verifies_and_archives_source():
    state, req = _make_store()
    _seed(state, rows_2606=3, rows_2605=1)
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    result = arch.apply_archive(planned, "tok", req)

    assert result["archive_db_created"] is True
    assert result["migrated"] == 3
    assert result["verified"] == 3
    assert result["archived_source"] == 3
    assert result["failed"] == []

    # 元シートの 2606 行は全て archived、2605 行は不可侵。
    assert all(state["pages"][f"src-2606-{i}"]["archived"] for i in range(3))
    assert state["pages"]["src-2605-0"]["archived"] is False

    # 写像先 DB は親ページ配下に『請求書確認シート2606』として作成され 3 行を持つ。
    adb = result["archive_db_id"]
    assert state["dbs"][adb]["title"] == "請求書確認シート2606"
    assert state["dbs"][adb]["parent"]["page_id"] == PARENT_PAGE
    arows = [p for p in state["pages"].values() if p["db"] == adb]
    assert len(arows) == 3
    # 降格列 判定 が rich_text として値温存されている。
    judged = arch.prop_plain_text(arows[0]["properties"]["判定"])
    assert judged == "発行漏れ"
    # 元ページID が写像先に載っている (provenance)。
    assert arch.prop_plain_text(arows[0]["properties"][arch.PROP_SOURCE_ID]).startswith("src-2606-")


def test_query_excludes_2605_from_archive():
    state, req = _make_store()
    _seed(state, rows_2606=2, rows_2605=2)
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    arch.apply_archive(planned, "tok", req)
    # 別月 (2605) は 1 行も archive されない。
    assert all(not state["pages"][f"src-2605-{i}"]["archived"] for i in range(2))


def test_idempotent_rerun_no_duplicate_and_noop():
    state, req = _make_store()
    _seed(state, rows_2606=2)
    source_props = state["dbs"][SHEET_DB]["properties"]

    planned1 = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    r1 = arch.apply_archive(planned1, "tok", req)
    adb = r1["archive_db_id"]
    assert len([p for p in state["pages"].values() if p["db"] == adb]) == 2

    # 2 回目: 元行は archive 済み→ query 対象外→ source_count 0 → no-op (写像先 DB 再利用・重複0)。
    planned2 = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    assert planned2["source_count"] == 0
    assert planned2["archive_db_exists"] is True         # 既存 DB を find できる
    r2 = arch.apply_archive(planned2, "tok", req)
    assert r2["archive_db_created"] is False
    assert r2["migrated"] == 0
    assert len([p for p in state["pages"].values() if p["db"] == adb]) == 2  # 重複なし


def test_crash_safe_reupsert_existing_archive_page():
    """写像先ページが既存 (前回 crash で移行済みだが元行未削除) でも重複せず PATCH で収束する。"""
    state, req = _make_store()
    _seed(state, rows_2606=1)
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    # 写像先 DB を先に作り、src-2606-0 の写像先ページを事前投入 (crash 途中状態を再現)。
    adb = arch.create_archive_db(PARENT_PAGE, planned["archive_db_title"],
                                 planned["properties"], "tok", req)
    planned["archive_db_id"] = adb
    planned["archive_db_exists"] = True
    src_page = planned["pages"][0]
    arch.upsert_archive_page(adb, src_page, None, planned["plan"], "tok", req,
                             planned["provenance_key"])
    assert len([p for p in state["pages"].values() if p["db"] == adb]) == 1

    result = arch.apply_archive(planned, "tok", req)
    assert result["archived_source"] == 1
    # 重複作成されず 1 行のまま (既存を元ページID で PATCH)。
    assert len([p for p in state["pages"].values() if p["db"] == adb]) == 1


def test_long_note_migrates_via_chunking():
    """2000 字超の確認内容も chunk 分割で完全移行し検証を通す (truncate 滞留を起こさない)。"""
    state, req = _make_store()
    _seed(state, rows_2606=1, long_note=True)
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    result = arch.apply_archive(planned, "tok", req)
    assert result["verified"] == 1
    assert result["archived_source"] == 1
    assert state["pages"]["src-2606-0"]["archived"] is True


def test_verify_failure_keeps_source_page():
    """読み戻し検証が不一致なら元行を削除しない (fail-closed・過少移行での喪失を防ぐ)。"""
    state, req = _make_store()
    _seed(state, rows_2606=2)
    source_props = state["dbs"][SHEET_DB]["properties"]

    # GET /pages/{id} の読み戻しで 1 ページだけ『確認内容』を破損させる wrapper。
    def broken_req(method, path, token, body=None):
        res = req(method, path, token, body)
        if method == "GET" and path.startswith("/pages/") and res.get("properties"):
            if arch.prop_plain_text(res["properties"].get("取引先")) == "取引先0":
                res = json.loads(json.dumps(res))  # copy
                res["properties"]["確認内容"] = {"type": "rich_text",
                                                 "rich_text": [{"text": {"content": "改竄"}}]}
        return res

    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", broken_req)
    result = arch.apply_archive(planned, "tok", broken_req)
    assert result["migrated"] == 2
    assert result["verified"] == 1                       # 1 行は検証失敗
    assert result["archived_source"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["stage"] == "verify"
    # 検証失敗した元行 (取引先0) は archive されず温存。
    kept = [pid for pid, pg in state["pages"].items()
            if pg["db"] == SHEET_DB and arch.prop_plain_text(pg["properties"]["取引先"]) == "取引先0"]
    assert len(kept) == 1
    assert state["pages"][kept[0]]["archived"] is False


def test_relation_migrates_ids_and_is_delete_safe():
    """relation 列は関連ページ ID を text 忠実 snapshot し、検証を通って安全に削除される
    (回帰: 以前は relation が空文字に潰れ『空一致=検証OK』で実データ喪失のまま誤削除した)。"""
    state, req = _make_store()
    state["dbs"][SHEET_DB] = {
        "title": "請求書確認シート",
        "properties": {"取引先": {"type": "title", "title": {}},
                       "年月": {"type": "select", "select": {"options": [{"name": "2606"}]}},
                       "契約": {"type": "relation", "relation": {"database_id": "db1"}}},
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
    }
    state["children"].setdefault(PARENT_PAGE, [])
    state["pages"]["src-rel"] = {
        "db": SHEET_DB, "archived": False,
        "properties": {"取引先": {"type": "title", "title": [{"text": {"content": "A社"}}]},
                       "年月": {"type": "select", "select": {"name": "2606"}},
                       "契約": {"type": "relation", "relation": [{"id": "pg-1"}, {"id": "pg-2"}]}},
    }
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    result = arch.apply_archive(planned, "tok", req)
    assert result["verified"] == 1 and result["archived_source"] == 1
    assert state["pages"]["src-rel"]["archived"] is True     # 関連ID保全ゆえ削除OK
    adb = result["archive_db_id"]
    arow = next(p for p in state["pages"].values() if p["db"] == adb)
    assert arch.prop_plain_text(arow["properties"]["契約"]) == "pg-1、pg-2"  # ID を text 保全


def test_files_column_holds_row_from_deletion():
    """添付ファイル (files) を持つ行はコピーのみ・元行を削除保留する
    (回帰: files は実体を text で保てないため『名前一致=検証OK』での誤削除を封じる)。"""
    state, req = _make_store()
    state["dbs"][SHEET_DB] = {
        "title": "請求書確認シート",
        "properties": {"取引先": {"type": "title", "title": {}},
                       "年月": {"type": "select", "select": {"options": [{"name": "2606"}]}},
                       "添付": {"type": "files", "files": {}}},
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
    }
    state["children"].setdefault(PARENT_PAGE, [])
    state["pages"]["src-f0"] = {  # 添付あり→保留
        "db": SHEET_DB, "archived": False,
        "properties": {"取引先": {"type": "title", "title": [{"text": {"content": "添付社"}}]},
                       "年月": {"type": "select", "select": {"name": "2606"}},
                       "添付": {"type": "files", "files": [{"name": "invoice.pdf",
                                                           "file": {"url": "https://x"}}]}},
    }
    state["pages"]["src-f1"] = {  # 添付なし→通常削除
        "db": SHEET_DB, "archived": False,
        "properties": {"取引先": {"type": "title", "title": [{"text": {"content": "無添付社"}}]},
                       "年月": {"type": "select", "select": {"name": "2606"}},
                       "添付": {"type": "files", "files": []}},
    }
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    assert planned["lossy_hold_preview"] == 1                # dry-run で保留 1 件を予告
    result = arch.apply_archive(planned, "tok", req)
    assert result["migrated"] == 2                           # 両行コピー
    assert result["archived_source"] == 1                    # 添付なしのみ削除
    assert state["pages"]["src-f0"]["archived"] is False     # 添付社は温存
    assert state["pages"]["src-f1"]["archived"] is True
    assert result["status"] == "incomplete"                  # 全削除でない→未完了
    held = [f for f in result["failed"] if f["stage"] == "lossy-hold"]
    assert held and held[0]["cols"] == ["添付"]


def test_provenance_key_collision_avoids_stall():
    """元シートに『元ページID』同名列があっても、衝突しない冪等キーへ退避して stall しない
    (回帰: 以前はコメントが約束する除外が未実装で全行が恒久 verify 失敗した)。"""
    state, req = _make_store()
    state["dbs"][SHEET_DB] = {
        "title": "請求書確認シート",
        "properties": {"取引先": {"type": "title", "title": {}},
                       "年月": {"type": "select", "select": {"options": [{"name": "2606"}]}},
                       "元ページID": {"type": "rich_text", "rich_text": {}}},  # 同名衝突
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
    }
    state["children"].setdefault(PARENT_PAGE, [])
    state["pages"]["src-c"] = {
        "db": SHEET_DB, "archived": False,
        "properties": {"取引先": {"type": "title", "title": [{"text": {"content": "C社"}}]},
                       "年月": {"type": "select", "select": {"name": "2606"}},
                       "元ページID": {"type": "rich_text", "rich_text": [{"text": {"content": "人間入力値"}}]}},
    }
    source_props = state["dbs"][SHEET_DB]["properties"]
    planned = arch.plan_archive(SHEET_DB, "2606", PARENT_PAGE, source_props, "tok", req)
    assert planned["provenance_key"] == "元ページID_2"        # 衝突回避
    result = arch.apply_archive(planned, "tok", req)
    assert result["archived_source"] == 1                    # stall せず削除完走
    adb = result["archive_db_id"]
    arow = next(p for p in state["pages"].values() if p["db"] == adb)
    # 源の『元ページID』値は保全され、provenance は別列に載る。
    assert arch.prop_plain_text(arow["properties"]["元ページID"]) == "人間入力値"
    assert arch.prop_plain_text(arow["properties"]["元ページID_2"]) == "src-c"


def test_preflight_rejects_bad_schema():
    """年月 select 不在 / title 不在を preflight で検出する (CLI が exit 2 fail-closed にする)。"""
    ok, _ = arch.preflight_source_schema({"取引先": {"type": "title"},
                                          "年月": {"type": "select"}})
    assert ok is True
    bad_month, r1 = arch.preflight_source_schema({"取引先": {"type": "title"},
                                                  "年月": {"type": "rich_text"}})
    assert bad_month is False and "select" in r1
    no_month, _ = arch.preflight_source_schema({"取引先": {"type": "title"}})
    assert no_month is False
    no_title, _ = arch.preflight_source_schema({"年月": {"type": "select"}})
    assert no_title is False


def test_find_child_database_prefix_rename():
    """写像先 DB がリネームされても前方一致で再利用し二重作成しない (Design D 構造同定)。"""
    state, req = _make_store()
    state["children"][PARENT_PAGE] = [
        {"id": "db-x", "type": "child_database",
         "child_database": {"title": "請求書確認シート2606 (確認用)"}},  # リネーム済み
    ]
    found = arch.find_child_database(PARENT_PAGE, "請求書確認シート2606", "tok", req)
    assert found == "db-x"
    # 別月 (2607) は前方一致で混ざらない。
    assert arch.find_child_database(PARENT_PAGE, "請求書確認シート2607", "tok", req) is None


def test_prop_plain_text_all_types():
    """prop_plain_text が全 Notion 型を人間可読 plain-text へ落とす (降格値生成 + 検証の SSOT)。"""
    pt = arch.prop_plain_text
    assert pt(None) == "" and pt("x") == ""
    assert pt({"type": "number", "number": 1000}) == "1000"
    assert pt({"type": "number", "number": 12.5}) == "12.5"
    assert pt({"type": "number", "number": None}) == ""
    assert pt({"type": "select", "select": {"name": "発行漏れ"}}) == "発行漏れ"
    assert pt({"type": "select", "select": None}) == ""
    assert pt({"type": "status", "status": {"name": "済"}}) == "済"
    assert pt({"type": "multi_select",
               "multi_select": [{"name": "A"}, {"name": "B"}]}) == "A、B"
    assert pt({"type": "date", "date": {"start": "2026-06-01"}}) == "2026-06-01"
    assert pt({"type": "date", "date": {"start": "2026-06-01", "end": "2026-06-30"}}) == "2026-06-01〜2026-06-30"
    assert pt({"type": "checkbox", "checkbox": True}) == "true"
    assert pt({"type": "url", "url": "https://x"}) == "https://x"
    assert pt({"type": "email", "email": "a@b"}) == "a@b"
    assert pt({"type": "phone_number", "phone_number": "090"}) == "090"
    assert pt({"type": "people", "people": [{"name": "山田"}, {"id": "u1"}]}) == "山田、u1"
    assert pt({"type": "files", "files": [{"name": "a.pdf"},
                                          {"external": {"url": "http://e"}}]}) == "a.pdf、http://e"
    assert pt({"type": "formula", "formula": {"type": "number", "number": 3}}) == "3"
    assert pt({"type": "formula", "formula": {"type": "boolean", "boolean": True}}) == "true"
    assert pt({"type": "formula", "formula": {"type": "date", "date": {"start": "2026-01-01"}}}) == "2026-01-01"
    assert pt({"type": "formula", "formula": {"type": "string", "string": "s"}}) == "s"
    assert pt({"type": "rollup", "rollup": {"type": "number", "number": 7}}) == "7"
    assert pt({"type": "rollup", "rollup": {"type": "date", "date": {"start": "2026-02-02"}}}) == "2026-02-02"
    assert pt({"type": "rollup", "rollup": {"type": "array",
               "array": [{"type": "select", "select": {"name": "X"}}]}}) == "X"
    assert pt({"type": "created_time", "created_time": "2026-06-01T00:00:00Z"}) == "2026-06-01T00:00:00Z"
    assert pt({"type": "created_by", "created_by": {"name": "作成者"}}) == "作成者"
    assert pt({"type": "unique_id", "unique_id": {"prefix": "INV", "number": 42}}) == "INV-42"
    assert pt({"type": "unique_id", "unique_id": {"number": 42}}) == "42"
    assert pt({"type": "unique_id", "unique_id": {"number": None}}) == ""
    assert pt({"type": "relation", "relation": [{"id": "p1"}, {"id": "p2"}]}) == "p1、p2"
    assert pt({"type": "relation", "relation": []}) == ""
    assert pt({"type": "verification", "verification": {"state": "verified"}}) == "verified"
    assert pt({"type": "button", "button": {}}) == ""
    # type キーが無い payload はキー集合から推測する。
    assert pt({"rich_text": [{"text": {"content": "推測"}}]}) == "推測"
    assert pt({"relation": [{"id": "px"}]}) == "px"          # type 欠落でも relation を推測
    assert pt({"type": "unknown_future_type"}) == ""


def test_notion_type_coverage_is_exhaustive():
    """Notion 公式プロパティ型すべてが _prop_type/prop_plain_text で認識される (MECE ゲート)。

    未マップの型を将来足したら、この網羅テストが落ちて分岐追加を強制する
    (回帰: relation/verification/button の無音ドロップが型網羅の穴として誤削除を招いた)。
    """
    all_types = {
        "title", "rich_text", "number", "select", "status", "multi_select", "date",
        "checkbox", "url", "email", "phone_number", "people", "files", "formula",
        "rollup", "created_time", "last_edited_time", "created_by", "last_edited_by",
        "unique_id", "relation", "verification", "button",
    }
    for t in all_types:
        # 型キーだけの最小 payload でも _prop_type がその型を認識する (無音 None にしない)。
        assert arch._prop_type({t: {}}) == t, f"未認識の型: {t}"


def test_build_prop_value_types():
    """build_prop_value が target_type ごとに正しい書込 payload を組む。"""
    bpv = arch.build_prop_value
    assert bpv("multi_select", {"type": "multi_select", "multi_select": [{"name": "A"}]}) == \
        {"multi_select": [{"name": "A"}]}
    assert bpv("date", {"type": "date", "date": {"start": "2026-06-01", "end": "2026-06-30"}}) == \
        {"date": {"start": "2026-06-01", "end": "2026-06-30"}}
    assert bpv("date", {"type": "date", "date": None}) == {"date": None}
    assert bpv("url", {"type": "url", "url": "https://x"}) == {"url": "https://x"}
    assert bpv("url", {"type": "url", "url": None}) == {"url": None}
    assert bpv("number", {"type": "number", "number": 5}) == {"number": 5.0}
    assert bpv("number", {"type": "number", "number": None}) == {"number": None}
    assert bpv("checkbox", {"type": "checkbox", "checkbox": True}) == {"checkbox": True}
    assert bpv("select", {"type": "select", "select": {"name": "S"}}) == {"select": {"name": "S"}}
    assert bpv("select", {"type": "select", "select": None}) == {"select": None}
    assert bpv("rich_text", {"type": "rich_text", "rich_text": []}) == {"rich_text": []}


def test_build_property_def_types():
    """_build_property_def が写像先 DB 作成用の型定義を組む (url/email/phone/multi_select/date)。"""
    bpd = arch._build_property_def
    assert bpd("url", {}) == {"url": {}}
    assert bpd("email", {}) == {"email": {}}
    assert bpd("phone_number", {}) == {"phone_number": {}}
    assert bpd("date", {}) == {"date": {}}
    assert bpd("checkbox", {}) == {"checkbox": {}}
    ms = bpd("multi_select", {"multi_select": {"options": [{"name": "A", "color": "red"}]}})
    assert ms["multi_select"]["options"] == [{"name": "A", "color": "red"}]
    # 降格型 (status) は rich_text 定義になる。
    assert bpd("status", {"status": {}}) == {"rich_text": {}}


def test_pagination_across_multiple_batches():
    """query_month_pages / index_archive_by_source が has_more/next_cursor を辿り全件取得する。"""
    calls = {"n": 0}

    def paged_req(method, path, token, body=None):
        base = path.split("?")[0]
        if method == "POST" and base.endswith("/query"):
            cur = (body or {}).get("start_cursor")
            if cur is None:
                return {"results": [{"id": "p1", "properties": {}}], "has_more": True,
                        "next_cursor": "c2"}
            return {"results": [{"id": "p2", "properties": {}}], "has_more": False}
        raise AssertionError(path)

    pages = arch.query_month_pages("db", "2606", "tok", paged_req)
    assert [p["id"] for p in pages] == ["p1", "p2"]


# ===========================================================================
# CLI (scripts/mfk_sheet_archive.py) 面: 親ページ解決 + ゲート + exit code。
# ===========================================================================
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import mfk_sheet_archive as cli  # noqa: E402


def test_resolve_parent_prefers_explicit_then_sheet_parent():
    meta = {"parent": {"type": "page_id", "page_id": "sheet-parent-x"}}
    cfg = {"notion": {"report_parent_page": "report-x"}}
    assert cli.resolve_parent_page_id(meta, cfg, "explicit-x") == ("explicit-x", "explicit/config")
    assert cli.resolve_parent_page_id(meta, cfg, None) == ("sheet-parent-x", "sheet-parent")
    # シート親が workspace (page でない) 時は report_parent_page へ fallback。
    meta_ws = {"parent": {"type": "workspace"}}
    assert cli.resolve_parent_page_id(meta_ws, cfg, None) == ("report-x", "report-parent-fallback")
    assert cli.resolve_parent_page_id({"parent": {"type": "workspace"}}, {"notion": {}}, None) == (None, "unresolved")


def test_cli_apply_without_verified_is_fail_closed(capsys):
    assert cli.main(["--target", "2606", "--apply"]) == 2
    assert "verified" in capsys.readouterr().err


def test_cli_bad_target_fail_closed():
    assert cli.main(["--target", "26", "--apply", "--verified"]) == 2


def test_cli_dry_run_and_apply_and_noop(monkeypatch, capsys):
    state, req = _make_store()
    _seed(state, rows_2606=2)
    monkeypatch.setattr(cli.nt, "_notion_token", lambda cfg=None: "tok")
    monkeypatch.setattr(cli.nt, "_req", req)
    monkeypatch.setenv("MFK_SHEET_DB_ID", SHEET_DB)
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "0")

    # dry-run: exit 0・書き込みなし。
    assert cli.main(["--target", "2606"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "dry-run" and out["source_count"] == 2

    # apply --verified: exit 0・元行 archive。
    assert cli.main(["--target", "2606", "--apply", "--verified"]) == 0
    assert all(state["pages"][f"src-2606-{i}"]["archived"] for i in range(2))
    capsys.readouterr()  # バッファをクリア (次の no-op 出力だけを読むため)

    # 再実行 apply: no-op exit 0。
    assert cli.main(["--target", "2606", "--apply", "--verified"]) == 0
    out2 = json.loads(capsys.readouterr().out)
    assert out2.get("note") == "no-op"


def test_cli_preflight_fail_closed(monkeypatch, capsys):
    """年月 が select でない元シートは preflight で exit 2 (Notion 400 の前に明示停止)。"""
    def req(method, path, token, body=None):
        if method == "GET" and path.startswith("/databases/"):
            return {"id": "db", "properties": {"取引先": {"type": "title", "title": {}},
                                               "年月": {"type": "rich_text", "rich_text": {}}},
                    "parent": {"type": "page_id", "page_id": "pp"}}
        raise AssertionError(path)
    monkeypatch.setattr(cli.nt, "_notion_token", lambda cfg=None: "tok")
    monkeypatch.setattr(cli.nt, "_req", req)
    monkeypatch.setenv("MFK_SHEET_DB_ID", "db")
    assert cli.main(["--target", "2606", "--apply", "--verified"]) == 2
    assert "select" in capsys.readouterr().err


def test_cli_api_error_fail_closed(monkeypatch, capsys):
    """Notion API 例外は traceback でなく fail-closed exit 2 にする。"""
    def req(method, path, token, body=None):
        raise RuntimeError("boom 500")
    monkeypatch.setattr(cli.nt, "_notion_token", lambda cfg=None: "tok")
    monkeypatch.setattr(cli.nt, "_req", req)
    monkeypatch.setenv("MFK_SHEET_DB_ID", "db")
    assert cli.main(["--target", "2606", "--apply", "--verified"]) == 2
    assert "fail-closed" in capsys.readouterr().err


def test_cli_incomplete_returns_exit1(monkeypatch, capsys):
    """未移行行 (files 保留) が残ると exit 1・status=incomplete を提示する。"""
    state, req = _make_store()
    state["dbs"][SHEET_DB] = {
        "title": "請求書確認シート",
        "properties": {"取引先": {"type": "title", "title": {}},
                       "年月": {"type": "select", "select": {"options": [{"name": "2606"}]}},
                       "添付": {"type": "files", "files": {}}},
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
    }
    state["children"].setdefault(PARENT_PAGE, [])
    state["pages"]["s0"] = {"db": SHEET_DB, "archived": False,
                            "properties": {"取引先": {"type": "title", "title": [{"text": {"content": "添付社"}}]},
                                           "年月": {"type": "select", "select": {"name": "2606"}},
                                           "添付": {"type": "files", "files": [{"name": "a.pdf"}]}}}
    monkeypatch.setattr(cli.nt, "_notion_token", lambda cfg=None: "tok")
    monkeypatch.setattr(cli.nt, "_req", req)
    monkeypatch.setenv("MFK_SHEET_DB_ID", SHEET_DB)
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "0")
    assert cli.main(["--target", "2606", "--apply", "--verified"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "incomplete"
    assert state["pages"]["s0"]["archived"] is False        # 添付社は削除されない
