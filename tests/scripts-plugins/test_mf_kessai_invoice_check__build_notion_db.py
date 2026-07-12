"""Genuine functional tests for
plugins/mf-kessai-invoice-check/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py.

このスクリプトは Notion DB を schema 通りに用意する。2 経路(冪等):
  - config に database_id → 既存DBへ schema 適用 (不足プロパティ追加・タイトル列リネーム・
    select option マージ)
  - database_id 無し + parent_page_id → 新規DB作成し database_id を config に記録

network/keychain は絶対に叩かない。build_notion_db が import する
  - notion_invoice_sink._req  (Notion HTTP)
  - notion_invoice_sink._notion_token (keychain)
  - mfk_api.load_config (config 読み)
を monkeypatch でメモリ stub に差し替え、save_config の書き込み先(CONFIG_PATH)を
tmp_path に向けて repo を汚さない。純関数 + ensure_schema の各分岐 + main 各経路を
実入出力で assert する。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "mf-kessai-invoice-check"
SCRIPT = PLUGIN / "skills" / "run-mf-invoice-db-setup" / "scripts" / "build_notion_db.py"

# build_notion_db は lib/{mfk_api,notion_invoice_sink} を import するので lib を sys.path へ。
sys.path.insert(0, str(PLUGIN / "lib"))
_SPEC = importlib.util.spec_from_file_location("build_notion_db_s3", SCRIPT)
BND = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BND)


# ===================== load_schema (実 schema ファイル) =====================

def test_load_schema_reads_real_schema():
    schema = BND.load_schema()
    assert schema["title"]
    props = schema["properties"]
    # title 型は1つ (取引先企業名)
    titles = [n for n, s in props.items() if s["type"] == "title"]
    assert titles == ["取引先企業名"]
    # select 型に options がある (旧名『判定』は renames で『今月の発行状況』へ改名済み)
    assert props["今月の発行状況"]["type"] == "select"
    assert "options" in props["今月の発行状況"]


# ===================== build_property (全型 + ValueError) =====================

def test_build_property_title():
    assert BND.build_property({"type": "title"}) == {"title": {}}


def test_build_property_rich_text():
    assert BND.build_property({"type": "rich_text"}) == {"rich_text": {}}


def test_build_property_number_is_yen():
    assert BND.build_property({"type": "number"}) == {"number": {"format": "yen"}}


def test_build_property_date():
    assert BND.build_property({"type": "date"}) == {"date": {}}


def test_build_property_checkbox():
    assert BND.build_property({"type": "checkbox"}) == {"checkbox": {}}


def test_build_property_select_maps_options():
    out = BND.build_property({"type": "select", "options": ["A", "B"]})
    assert out == {"select": {"options": [{"name": "A"}, {"name": "B"}]}}


def test_build_property_select_no_options():
    out = BND.build_property({"type": "select"})
    assert out == {"select": {"options": []}}


def test_build_property_unsupported_raises():
    with pytest.raises(ValueError, match="unsupported property type: people"):
        BND.build_property({"type": "people"})


def test_build_property_all_schema_types_roundtrip():
    # 実 schema の全プロパティが build_property を例外なく通る
    schema = BND.load_schema()
    for name, spec in schema["properties"].items():
        out = BND.build_property(spec)
        assert isinstance(out, dict) and len(out) == 1


# ===================== merge_select_property =====================

def test_merge_select_adds_missing_keeps_existing():
    existing = {"select": {"options": [
        {"name": "未確認", "color": "red", "id": "x1"},  # 既存属性 (色/id) は保持
    ]}}
    spec = {"type": "select", "options": ["未確認", "対応済"]}
    out = BND.merge_select_property(existing, spec)
    by_name = {o["name"]: o for o in out["select"]["options"]}
    assert set(by_name) == {"未確認", "対応済"}
    assert by_name["未確認"]["color"] == "red"  # 既存 option を消さない
    assert by_name["対応済"] == {"name": "対応済"}  # 不足分は名前だけ追加


def test_merge_select_handles_missing_select_key():
    out = BND.merge_select_property({}, {"type": "select", "options": ["X"]})
    assert out == {"select": {"options": [{"name": "X"}]}}


def test_merge_select_ignores_nameless_existing():
    existing = {"select": {"options": [{"color": "blue"}]}}  # name 無しは無視
    out = BND.merge_select_property(existing, {"options": ["Y"]})
    assert out == {"select": {"options": [{"name": "Y"}]}}


# ===================== _db_title =====================

def test_db_title_joins_plain_text():
    res = {"title": [{"plain_text": "請求書"}, {"plain_text": "チェック"}]}
    assert BND._db_title(res) == "請求書チェック"


def test_db_title_empty_fallback():
    assert BND._db_title({"title": []}) == "(無題)"
    assert BND._db_title({}) == "(無題)"


# ===================== ensure_schema (DB 取得は _req を stub) =====================

def _wire_req(monkeypatch, get_response, patch_capture):
    """_req を GET/PATCH 別に stub。GET は get_response を返し、PATCH は body を記録。"""
    def fake_req(method, path, token, body=None):
        if method == "GET":
            return get_response
        if method == "PATCH":
            patch_capture["path"] = path
            patch_capture["body"] = body
            return {"id": "db-1"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(BND, "_req", fake_req)


def _full_schema():
    """title + rich_text + number + select(2 option) の最小 schema。"""
    return {
        "title": "TestDB",
        "properties": {
            "名前": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "options": ["未確認", "対応済"]},
        },
    }


def test_ensure_schema_no_change_when_up_to_date(monkeypatch, capsys):
    schema = _full_schema()
    existing = {
        "properties": {
            "名前": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "TestDB"}],
    }
    patch = {}
    _wire_req(monkeypatch, existing, patch)
    rc = BND.ensure_schema("db-1", schema, "tok")
    assert rc == 0
    assert patch == {}  # PATCH は呼ばれない
    out = capsys.readouterr().out
    assert "変更なし" in out
    assert "TestDB" in out


def test_ensure_schema_adds_missing_properties(monkeypatch, capsys):
    schema = _full_schema()
    existing = {
        "properties": {
            "名前": {"type": "title"},  # title 正しい
            # メモ/金額/状態 が欠落
        },
        "title": [{"plain_text": "TestDB"}],
    }
    patch = {}
    _wire_req(monkeypatch, existing, patch)
    rc = BND.ensure_schema("db-1", schema, "tok")
    assert rc == 0
    body = patch["body"]["properties"]
    assert set(body) == {"メモ", "金額", "状態"}
    assert body["金額"] == {"number": {"format": "yen"}}
    assert body["状態"]["select"]["options"] == [{"name": "未確認"}, {"name": "対応済"}]
    out = capsys.readouterr().out
    assert "追加プロパティ (3)" in out
    assert "次に verify_db_schema.py" in out


def test_ensure_schema_renames_title_column(monkeypatch, capsys):
    schema = _full_schema()
    existing = {
        "properties": {
            "Name": {"type": "title"},  # 旧名 → 名前 にリネーム必要
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "TestDB"}],
    }
    patch = {}
    _wire_req(monkeypatch, existing, patch)
    rc = BND.ensure_schema("db-1", schema, "tok")
    assert rc == 0
    body = patch["body"]["properties"]
    # タイトル列 Name → 名前 (型変更せず名前のみ)
    assert body["Name"] == {"name": "名前"}
    out = capsys.readouterr().out
    assert "列リネーム (値保持)" in out
    assert "Name→名前" in out


def test_ensure_schema_no_rename_when_target_name_exists(monkeypatch):
    # want_title が既に existing にある場合はリネームしない(衝突回避)
    schema = _full_schema()
    existing = {
        "properties": {
            "Name": {"type": "title"},
            "名前": {"type": "rich_text"},  # 同名が既存 → リネームしない
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "TestDB"}],
    }
    patch = {}
    _wire_req(monkeypatch, existing, patch)
    BND.ensure_schema("db-1", schema, "tok")
    # 名前 は既存なので追加もリネームも patch に出ない
    assert "Name" not in patch.get("body", {}).get("properties", {})


def test_ensure_schema_merges_missing_select_options(monkeypatch, capsys):
    schema = _full_schema()
    existing = {
        "properties": {
            "名前": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            # 状態 は存在するが option 不足 (対応済 が無い)
            "状態": {"type": "select", "select": {"options": [{"name": "未確認"}]}},
        },
        "title": [{"plain_text": "TestDB"}],
    }
    patch = {}
    _wire_req(monkeypatch, existing, patch)
    rc = BND.ensure_schema("db-1", schema, "tok")
    assert rc == 0
    body = patch["body"]["properties"]
    names = {o["name"] for o in body["状態"]["select"]["options"]}
    assert names == {"未確認", "対応済"}  # 既存維持 + 不足追加


def test_ensure_schema_select_complete_no_patch(monkeypatch):
    # select の option が全て揃っていれば patch しない
    schema = _full_schema()
    existing = {
        "properties": {
            "名前": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "TestDB"}],
    }
    patch = {}
    _wire_req(monkeypatch, existing, patch)
    assert BND.ensure_schema("db-1", schema, "tok") == 0
    assert patch == {}


# ===================== main() 経路 =====================

def _isolate_config(monkeypatch, tmp_path, argv=None):
    """save_config の書き込み先を tmp に向けて repo 非汚染にする。

    main() は argparse で sys.argv を読むため、pytest の argv 混入を防ぐべく
    既定で素の argv (オプション無し) に固定する。--parent-page-id 経路を試す
    test は argv を渡す。
    """
    cfg_path = tmp_path / ".mf-kessai-config.json"
    monkeypatch.setattr(BND, "CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(BND, "_notion_token", lambda: "fake-token")
    monkeypatch.setattr(BND.sys, "argv", argv or ["build_notion_db.py"])
    return cfg_path


def test_main_existing_db_path(monkeypatch, tmp_path, capsys):
    _isolate_config(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config", lambda: {"notion": {"database_id": "db-existing"}})
    captured = {}

    def fake_ensure(db_id, schema, token):
        captured["db_id"] = db_id
        captured["token"] = token
        assert "properties" in schema
        return 0

    monkeypatch.setattr(BND, "ensure_schema", fake_ensure)
    assert BND.main() == 0
    assert captured["db_id"] == "db-existing"
    assert captured["token"] == "fake-token"


def test_main_missing_parent_page_id_returns_2(monkeypatch, tmp_path, capsys):
    _isolate_config(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config", lambda: {"notion": {}})  # db_id も parent も無し
    assert BND.main() == 2
    err = capsys.readouterr().err
    assert "parent_page_id が空" in err


def test_main_no_notion_section_returns_2(monkeypatch, tmp_path, capsys):
    _isolate_config(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config", lambda: {})  # notion セクションすら無し
    assert BND.main() == 2
    assert "parent_page_id が空" in capsys.readouterr().err


def test_main_create_new_db(monkeypatch, tmp_path, capsys):
    cfg_path = _isolate_config(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config",
                        lambda: {"notion": {"parent_page_id": "parent-1"}})
    captured = {}

    def fake_req(method, path, token, body=None):
        captured["method"] = method
        captured["path"] = path
        captured["token"] = token
        captured["body"] = body
        return {"id": "new-db-id"}

    monkeypatch.setattr(BND, "_req", fake_req)
    assert BND.main() == 0

    # POST /databases に schema 全プロパティ + parent + title が載る
    assert captured["method"] == "POST"
    assert captured["path"] == "/databases"
    assert captured["token"] == "fake-token"
    body = captured["body"]
    assert body["parent"] == {"type": "page_id", "page_id": "parent-1"}
    schema = BND.load_schema()
    assert body["title"][0]["text"]["content"] == schema["title"]
    assert set(body["properties"]) == set(schema["properties"])

    # config に database_id が記録された
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["notion"]["database_id"] == "new-db-id"
    out = capsys.readouterr().out
    assert "DB作成完了" in out
    assert "new-db-id" in out


def test_main_create_new_db_preserves_existing_config(monkeypatch, tmp_path):
    # load_config が他キーを持つ場合、それを温存して database_id だけ足す
    cfg_path = _isolate_config(monkeypatch, tmp_path)
    monkeypatch.setattr(
        BND, "load_config",
        lambda: {"environment": "sandbox", "notion": {"parent_page_id": "p1"}})
    monkeypatch.setattr(BND, "_req", lambda *a, **k: {"id": "db-X"})
    assert BND.main() == 0
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["environment"] == "sandbox"  # 既存キー温存
    assert saved["notion"]["parent_page_id"] == "p1"
    assert saved["notion"]["database_id"] == "db-X"


def test_main_create_new_db_when_notion_section_absent_on_save(monkeypatch, tmp_path):
    # cfg.setdefault("notion", {}) のフォールバック経路。load_config が
    # parent を返すが、setdefault が新規 dict を作る形を検証。
    cfg_path = _isolate_config(monkeypatch, tmp_path)
    cfg_obj = {"notion": {"parent_page_id": "p9"}}
    monkeypatch.setattr(BND, "load_config", lambda: cfg_obj)
    monkeypatch.setattr(BND, "_req", lambda *a, **k: {"id": "db-Y"})
    assert BND.main() == 0
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["notion"]["database_id"] == "db-Y"


# ===================== save_config (round-trip) =====================

def test_save_config_writes_json_with_trailing_newline(monkeypatch, tmp_path):
    cfg_path = tmp_path / "out.json"
    monkeypatch.setattr(BND, "CONFIG_PATH", str(cfg_path))
    BND.save_config({"notion": {"database_id": "abc"}, "日本語": "値"})
    raw = cfg_path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "日本語" in raw  # ensure_ascii=False
    assert json.loads(raw)["notion"]["database_id"] == "abc"
