#!/usr/bin/env python3
"""scripts/build_reconcile_dbs.py (reconcile DB1/DB2 冪等 find-or-create) の単体テスト。

実ネットワークなし。fake req で GET/POST/PATCH databases を模す。
検証する不変条件:
  - find-or-create: id 実在なら再利用し schema を冪等適用 (列追加のみ・新規作成しない)。
  - 欠落時のみ parent 配下へ作成し id を保存する。parent 未解決は fail-closed(SystemExit 2)。
  - schema type 変換: number は金額=yen/件数=number、relation は db1_id 解決、last_edited_time 対応。
"""
import pytest

import build_reconcile_dbs as B


def test_build_property_type_mapping():
    assert B._build_property("契約ID", {"type": "title"}) == {"title": {}}
    assert B._build_property("備考", {"type": "rich_text"}) == {"rich_text": {}}
    assert B._build_property("現行単価", {"type": "number"})["number"]["format"] == "yen"
    assert B._build_property("期待明細数", {"type": "number"})["number"]["format"] == "number"
    assert B._build_property("契約開始日", {"type": "date"}) == {"date": {}}
    assert B._build_property("AI確認済み", {"type": "checkbox"}) == {"checkbox": {}}
    assert B._build_property("最終更新日", {"type": "last_edited_time"}) == {"last_edited_time": {}}
    sel = B._build_property("方向", {"type": "select", "options": ["順方向", "逆方向orphan"]})
    assert [o["name"] for o in sel["select"]["options"]] == ["順方向", "逆方向orphan"]
    rel = B._build_property("契約", {"type": "relation"}, db1_id="DB1ID")
    assert rel["relation"]["database_id"] == "DB1ID"


def test_build_property_relation_requires_db1():
    with pytest.raises(SystemExit):
        B._build_property("契約", {"type": "relation"})  # db1_id 未解決


def _fake_req(existing_props, log):
    def req(method, path, token, body=None):
        log.append((method, path, body))
        if method == "GET" and path.startswith("/databases/"):
            db_id = path.split("/databases/")[1]
            if db_id in existing_props:
                return {"properties": existing_props[db_id]}
            raise RuntimeError("404")  # 不在 → _resolve は None に倒す
        if method == "PATCH" and path.startswith("/databases/"):
            return {}
        if method == "POST" and path == "/databases":
            return {"id": "NEWDB", "url": "https://notion/NEWDB"}
        raise AssertionError(f"想定外: {method} {path}")
    return req


def test_ensure_db_reuses_when_id_resolves(monkeypatch):
    # 既存 id が GET 解決 → 再利用 + 不足列だけ PATCH 追加 (POST しない)。
    log = []
    schema = {"title": "DB1", "properties": {
        "契約ID": {"type": "title"},
        "備考": {"type": "rich_text"},
        "新列": {"type": "rich_text"},  # 既存に無い → 追加される
    }}
    existing = {"D1": {"契約ID": {"type": "title"}, "備考": {"type": "rich_text"}}}
    monkeypatch.setattr(B.nt, "_req", _fake_req(existing, log))
    saved = {}
    monkeypatch.setattr(B, "_save_local_id", lambda k, v: saved.update({k: v}))
    cfg = {"notion": {"reconcile_db1_id": "D1"}}
    db_id, mode = B._ensure_db("DB1", "reconcile_db1_id", schema, cfg, "tok", parent=None)
    assert db_id == "D1" and mode == "reused"
    assert not any(m == "POST" for m, _, _ in log), "再利用時に新規作成してはいけない"
    patches = [b for m, p, b in log if m == "PATCH"]
    assert patches and "新列" in patches[0]["properties"]
    assert saved == {}, "再利用では id 保存しない"


def test_ensure_db_creates_when_missing(monkeypatch):
    log = []
    schema = {"title": "DB2", "properties": {"契約×年月": {"type": "title"}}}
    monkeypatch.setattr(B.nt, "_req", _fake_req({}, log))  # GET は常に 404
    saved = {}
    monkeypatch.setattr(B, "_save_local_id", lambda k, v: saved.update({k: v}))
    cfg = {"notion": {}}
    db_id, mode = B._ensure_db("DB2", "reconcile_db2_id", schema, cfg, "tok",
                               parent="PARENT")
    assert db_id == "NEWDB" and mode == "created"
    assert any(m == "POST" for m, _, _ in log)
    assert saved == {"reconcile_db2_id": "NEWDB"}


def test_ensure_db_failclosed_without_parent(monkeypatch):
    monkeypatch.setattr(B.nt, "_req", _fake_req({}, []))  # 既存なし
    monkeypatch.setattr(B, "_save_local_id", lambda k, v: None)
    with pytest.raises(SystemExit) as e:
        B._ensure_db("DB1", "reconcile_db1_id", {"title": "x", "properties": {}},
                     {"notion": {}}, "tok", parent=None)
    assert e.value.code == 2


def test_load_schema_reads_real_contract_master():
    schema = B._load_schema("contract-master-db.schema.json")
    assert schema["properties"]["契約ID"]["type"] == "title"
    # 2026-06-27 修正で追加された請求確認シートID列が schema にある (DB1 ドリフト再発防止)。
    assert "請求確認シートID" in schema["properties"]


def test_save_local_id_preserves_other_keys(monkeypatch, tmp_path):
    cfg_path = tmp_path / ".mf-kessai-config.json"
    cfg_path.write_text('{"notion": {"sheet_db_id": "S", "parent_page_id": "P"}}', encoding="utf-8")
    monkeypatch.setattr(B, "_LOCAL_CONFIG", str(cfg_path))
    B._save_local_id("reconcile_db1_id", "NEW1")
    import json
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["notion"]["reconcile_db1_id"] == "NEW1"
    assert saved["notion"]["sheet_db_id"] == "S"   # 既存キー保持
    assert saved["notion"]["parent_page_id"] == "P"


def test_main_reuses_existing_dbs(monkeypatch, capsys):
    # 両 DB id が解決 → 再利用 + DB2 relation を db1 へ解決。新規作成・id 保存なし。
    monkeypatch.setattr("sys.argv", ["build_reconcile_dbs.py"])  # argparse が pytest argv を読まない
    log = []
    existing = {"D1": {"契約ID": {"type": "title"}}, "D2": {"契約×年月": {"type": "title"}}}
    monkeypatch.setattr(B, "_load_config",
                        lambda *a, **k: {"notion": {"reconcile_db1_id": "D1",
                                                    "reconcile_db2_id": "D2"}})
    monkeypatch.setattr(B.nt, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(B.nt, "_req", _fake_req(existing, log))
    saved = {}
    monkeypatch.setattr(B, "_save_local_id", lambda k, v: saved.update({k: v}))
    assert B.main() == 0
    assert not any(m == "POST" for m, _, _ in log)
    assert saved == {}
    assert "再利用" in capsys.readouterr().out


def test_main_creates_when_missing_under_parent(monkeypatch):
    # id 無し + parent あり → DB1→DB2 を作成。DB2 relation は作成済み DB1 id を参照。
    monkeypatch.setattr("sys.argv", ["build_reconcile_dbs.py"])
    log = []
    monkeypatch.setattr(B, "_load_config",
                        lambda *a, **k: {"notion": {"parent_page_id": "PARENT"}})
    monkeypatch.setattr(B.nt, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(B.nt, "_req", _fake_req({}, log))  # GET 常に 404 → 作成
    saved = {}
    monkeypatch.setattr(B, "_save_local_id", lambda k, v: saved.update({k: v}))
    assert B.main() == 0
    posts = [b for m, p, b in log if m == "POST"]
    assert len(posts) == 2  # DB1 + DB2
    assert "reconcile_db1_id" in saved and "reconcile_db2_id" in saved
