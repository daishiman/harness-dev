#!/usr/bin/env python3
"""build_notion_db.py の build_property / ensure_schema / main を Notion API を mock して検証。

deprecated 列削除は test_db_migration.py が担保済み。本ファイルは未カバーだった
build_property の型変換・タイトル列リネーム・select option 追加・main の 2 モード
(既存DB適用 / 新規DB作成 / parent 欠落エラー) を固定する。
"""
import json

import build_notion_db as b


def _existing_from_schema(schema):
    """schema から Notion GET /databases のレスポンス形 (properties) を組み立てる。

    select は options まで再現し ensure_schema が『追加なし』と判断できる完全形にする。
    (--import-mode=importlib では test 同士を import できないため各 test file に閉じて持つ。)
    """
    props = {}
    for name, spec in schema["properties"].items():
        entry = {"type": spec["type"]}
        if spec["type"] == "select":
            entry["select"] = {"options": [{"name": o} for o in spec.get("options", [])]}
        elif spec["type"] == "number":
            entry["number"] = {"format": "yen"}
        else:
            entry[spec["type"]] = {}
        props[name] = entry
    return props


# --- build_property: 型変換 ---

def test_build_property_each_type():
    assert b.build_property({"type": "title"}) == {"title": {}}
    assert b.build_property({"type": "rich_text"}) == {"rich_text": {}}
    assert b.build_property({"type": "number"}) == {"number": {"format": "yen"}}
    assert b.build_property({"type": "date"}) == {"date": {}}
    assert b.build_property({"type": "checkbox"}) == {"checkbox": {}}
    sel = b.build_property({"type": "select", "options": ["x", "y"]})
    assert sel == {"select": {"options": [{"name": "x"}, {"name": "y"}]}}


def test_build_property_unsupported_raises():
    import pytest
    with pytest.raises(ValueError):
        b.build_property({"type": "formula"})


# --- merge_select_property: 既存を消さず不足だけ足す ---

def test_merge_select_keeps_existing_adds_missing():
    existing = {"select": {"options": [{"name": "発行漏れ候補", "color": "red"}]}}
    merged = b.merge_select_property(existing, {"options": ["発行漏れ候補", "継続発行"]})
    names = {o["name"] for o in merged["select"]["options"]}
    assert names == {"発行漏れ候補", "継続発行"}
    # 既存 option の色などメタは保持される。
    kept = [o for o in merged["select"]["options"] if o["name"] == "発行漏れ候補"][0]
    assert kept.get("color") == "red"


# --- ensure_schema: タイトルリネーム + 不足追加 + select option 追加 ---

def test_ensure_schema_renames_title_and_adds_missing(monkeypatch):
    schema = b.load_schema()
    # 既存はタイトル列が別名 + 一部プロパティ欠落の DB を模擬。
    existing = {"名前": {"type": "title"}}
    captured = {}

    def fake_req(method, path, token, body=None):
        if method == "GET":
            return {"title": [{"plain_text": "旧DB"}], "properties": existing}
        if method == "PATCH":
            captured["body"] = body
            return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(b, "_req", fake_req)
    assert b.ensure_schema("db1", schema, "tok") == 0
    patch = captured["body"]["properties"]
    # タイトル列が schema 名へリネームされる。
    assert patch["名前"] == {"name": "取引先企業名"}
    # 不足していた事実列が追加される。
    assert "顧客ID" in patch and "今月金額" in patch


def test_ensure_schema_adds_missing_select_option(monkeypatch):
    schema = b.load_schema()
    # 今月の発行状況 select に option が一部しか無い既存 DB。それ以外は全て揃った状態にする。
    existing = _existing_from_schema(schema)
    existing["今月の発行状況"]["select"]["options"] = [{"name": "発行漏れ候補"}]
    captured = {}

    def fake_req(method, path, token, body=None):
        if method == "GET":
            return {"title": [{"plain_text": "DB"}], "properties": existing}
        if method == "PATCH":
            captured["body"] = body
            return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(b, "_req", fake_req)
    assert b.ensure_schema("db1", schema, "tok") == 0
    opts = {o["name"] for o in captured["body"]["properties"]["今月の発行状況"]["select"]["options"]}
    assert {"発行漏れ候補", "継続発行", "今月新規"} <= opts


# --- 改名 A: ensure_schema の select 列 値保持リネーム (renames 機構) ---

def test_ensure_schema_renames_select_column_value_preserving(monkeypatch):
    """schema.renames の old が既存 DB にあり new が無ければ {old:{name:new}} で改名する。

    タイトル列リネームと同型で値 (select option) を保持する。new を空列で新規作成しない。
    """
    schema = b.load_schema()
    # 改名前の状態を再現: 旧名 判定 (select 3値) を持ち、新名 今月の発行状況 はまだ無い。
    existing = _existing_from_schema(schema)
    existing["判定"] = existing.pop("今月の発行状況")
    captured = {}

    def fake_req(method, path, token, body=None):
        if method == "GET":
            return {"title": [{"plain_text": "DB"}], "properties": existing}
        if method == "PATCH":
            captured["body"] = body
            return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(b, "_req", fake_req)
    assert b.ensure_schema("db1", schema, "tok") == 0
    patch = captured["body"]["properties"]
    # 旧名 判定 を新名へ値保持リネーム (name のみの patch)。
    assert patch["判定"] == {"name": "今月の発行状況"}
    # 新名を空の select 列として新規追加しない (リネームで用意するため)。
    assert "今月の発行状況" not in patch


def test_ensure_schema_rename_is_idempotent_when_already_renamed(monkeypatch):
    """既に新名へ改名済み (old が DB に無い) なら rename patch を出さない=冪等。"""
    schema = b.load_schema()
    existing = _existing_from_schema(schema)  # 既に 今月の発行状況 を持つ最新形
    calls = []

    def fake_req(method, path, token, body=None):
        calls.append(method)
        if method == "GET":
            return {"title": [{"plain_text": "DB"}], "properties": existing}
        raise AssertionError("clean な DB に PATCH してはいけない")

    monkeypatch.setattr(b, "_req", fake_req)
    assert b.ensure_schema("db1", schema, "tok") == 0
    # 改名済み + clean なので PATCH を一切送らない。
    assert calls == ["GET"]


def test_ensure_schema_deletes_stale_renamed_column_when_old_and_new_coexist(monkeypatch):
    """旧名と新名が併存する drift は、値保持済みの新名を残して旧名だけ削除する。"""
    schema = b.load_schema()
    existing = _existing_from_schema(schema)
    existing["判定"] = {"type": "select", "select": {"options": [{"name": "発行漏れ候補"}]}}
    captured = {}

    def fake_req(method, path, token, body=None):
        if method == "GET":
            return {"title": [{"plain_text": "DB"}], "properties": existing}
        if method == "PATCH":
            captured["body"] = body
            return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(b, "_req", fake_req)
    assert b.ensure_schema("db1", schema, "tok") == 0
    assert captured["body"]["properties"]["判定"] is None


# --- main: 2 モード ---

def test_main_applies_schema_when_database_id_present(monkeypatch):
    schema = b.load_schema()
    existing = _existing_from_schema(schema)
    monkeypatch.setattr(b.sys, "argv", ["build_notion_db.py"])
    monkeypatch.setattr(b, "load_config", lambda: {"notion": {"database_id": "db1"}})
    monkeypatch.setattr(b, "_notion_token", lambda: "tok")
    monkeypatch.setattr(b, "_req",
                        lambda m, p, t, body=None: {"title": [{"plain_text": "DB"}],
                                                    "properties": existing})
    assert b.main() == 0          # clean なので変更なしで 0


def test_main_creates_db_when_no_database_id(monkeypatch):
    schema = b.load_schema()
    saved = {}
    monkeypatch.setattr(b.sys, "argv", ["build_notion_db.py"])
    monkeypatch.setattr(b, "load_config", lambda: {"notion": {"parent_page_id": "page-parent"}})
    monkeypatch.setattr(b, "_notion_token", lambda: "tok")

    def fake_req(method, path, token, body=None):
        assert method == "POST" and path == "/databases"
        assert body["parent"]["page_id"] == "page-parent"
        # 全 schema プロパティを作成しようとする。
        assert "取引先企業名" in body["properties"]
        return {"id": "db-NEW"}

    monkeypatch.setattr(b, "_req", fake_req)
    monkeypatch.setattr(b, "save_config", lambda cfg: saved.update(cfg))
    assert b.main() == 0
    assert saved["notion"]["database_id"] == "db-NEW"   # 作成 ID が記録される


def test_main_parent_page_arg_forces_create_even_with_default_database_id(monkeypatch):
    saved = {}
    monkeypatch.setattr(b.sys, "argv", ["build_notion_db.py", "--parent-page-id", "page-cli"])
    monkeypatch.setattr(
        b,
        "load_config",
        lambda: {"notion": {"database_id": "default-db", "parent_page_id": "default-parent"}},
    )
    monkeypatch.setattr(b, "_notion_token", lambda: "tok")

    def fake_req(method, path, token, body=None):
        assert method == "POST" and path == "/databases"
        assert body["parent"]["page_id"] == "page-cli"
        return {"id": "db-CLI"}

    monkeypatch.setattr(b, "_req", fake_req)
    monkeypatch.setattr(b, "save_config", lambda cfg: saved.update(cfg))
    assert b.main() == 0
    assert saved["notion"]["database_id"] == "db-CLI"
    assert saved["notion"]["parent_page_id"] == "page-cli"


def test_main_errors_when_no_db_and_no_parent(monkeypatch):
    monkeypatch.setattr(b.sys, "argv", ["build_notion_db.py"])
    monkeypatch.setattr(b, "load_config", lambda: {"notion": {}})
    monkeypatch.setattr(b, "_notion_token", lambda: "tok")
    monkeypatch.setattr(b, "_req",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("API を呼ぶべきでない")))
    assert b.main() == 2


# --- save_config はファイルへ書く ---

def test_save_config_writes_json(monkeypatch, tmp_path):
    cfg_path = tmp_path / ".mf-kessai-config.json"
    monkeypatch.setattr(b, "CONFIG_PATH", str(cfg_path))
    b.save_config({"notion": {"database_id": "dbZ"}})
    written = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert written["notion"]["database_id"] == "dbZ"
