"""Genuine functional tests (scripts4) for
plugins/mf-kessai-invoice-check/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py.

このスクリプトは Notion DB を schema 通りに用意する。2 経路(冪等):
  - config に database_id → 既存DBへ schema 適用 (不足プロパティ追加・タイトル列リネーム・
    select option マージ)
  - database_id 無し + parent_page_id → 親ページ配下に新規DBを作成し database_id を
    ローカル .mf-kessai-config.json に記録

network / keychain は絶対に叩かない。build_notion_db が import する
  - notion_invoice_sink._req         (Notion HTTP)
  - notion_invoice_sink._notion_token (keychain / 環境変数)
  - mfk_api.load_config              (config 読み込み)
を monkeypatch でメモリ stub に差し替え、save_config の書き込み先(CONFIG_PATH)を
tmp_path に向けて repo を汚さない。純関数 + ensure_schema の各分岐 + main 各経路を
実入出力で assert する。

scripts3 と同名衝突を避けるため module 名・ファイル名に _r4 サフィックスを付す。
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
_SPEC = importlib.util.spec_from_file_location("build_notion_db_r4", SCRIPT)
BND = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BND)


# ===================== load_schema (実 schema ファイル) =====================


def test_load_schema_reads_real_schema_file():
    schema = BND.load_schema()
    assert schema["title"]  # 非空タイトル
    props = schema["properties"]
    titles = [n for n, s in props.items() if s["type"] == "title"]
    assert titles == ["取引先企業名"]  # title 型は唯一
    # 旧名『判定』は renames で『今月の発行状況』へ改名済み (select 型はこちら)
    assert "今月の発行状況" in props and props["今月の発行状況"]["type"] == "select"
    assert schema["renames"]["判定"] == "今月の発行状況"
    # upsert_key などメタも壊れずに読める (顧客ID 集約へ単一キー化済み)
    assert schema["upsert_key"] == ["顧客ID"]


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
    out = BND.build_property({"type": "select", "options": ["甲", "乙"]})
    assert out == {"select": {"options": [{"name": "甲"}, {"name": "乙"}]}}


def test_build_property_select_default_empty_options():
    assert BND.build_property({"type": "select"}) == {"select": {"options": []}}


def test_build_property_unsupported_type_raises():
    with pytest.raises(ValueError, match="unsupported property type: people"):
        BND.build_property({"type": "people"})


def test_build_property_every_real_schema_prop_roundtrips():
    schema = BND.load_schema()
    for name, spec in schema["properties"].items():
        out = BND.build_property(spec)
        assert isinstance(out, dict) and len(out) == 1, name


# ===================== merge_select_property =====================


def test_merge_select_adds_missing_keeps_existing_attrs():
    existing = {"select": {"options": [{"name": "未確認", "color": "red", "id": "x1"}]}}
    spec = {"type": "select", "options": ["未確認", "対応済"]}
    out = BND.merge_select_property(existing, spec)
    by_name = {o["name"]: o for o in out["select"]["options"]}
    assert set(by_name) == {"未確認", "対応済"}
    assert by_name["未確認"]["color"] == "red"  # 既存 option の色/id を消さない
    assert by_name["対応済"] == {"name": "対応済"}  # 不足分は name のみ


def test_merge_select_missing_select_key():
    out = BND.merge_select_property({}, {"type": "select", "options": ["X"]})
    assert out == {"select": {"options": [{"name": "X"}]}}


def test_merge_select_skips_nameless_existing_options():
    existing = {"select": {"options": [{"color": "blue"}]}}  # name 無し → 無視
    out = BND.merge_select_property(existing, {"options": ["Y"]})
    assert out == {"select": {"options": [{"name": "Y"}]}}


def test_merge_select_no_new_options_preserves_existing_only():
    existing = {"select": {"options": [{"name": "A", "color": "green"}]}}
    out = BND.merge_select_property(existing, {"options": ["A"]})
    assert out == {"select": {"options": [{"name": "A", "color": "green"}]}}


# ===================== _db_title =====================


def test_db_title_concatenates_plain_text():
    res = {"title": [{"plain_text": "請求書"}, {"plain_text": "チェック"}]}
    assert BND._db_title(res) == "請求書チェック"


def test_db_title_fallback_when_empty():
    assert BND._db_title({"title": []}) == "(無題)"
    assert BND._db_title({}) == "(無題)"


# ===================== ensure_schema =====================


def _wire_req(monkeypatch, get_response, capture):
    """_req を GET/PATCH 別に stub。GET は固定 response、PATCH は body を記録。"""

    def fake_req(method, path, token, body=None):
        if method == "GET":
            capture["get_path"] = path
            capture["token"] = token
            return get_response
        if method == "PATCH":
            capture["patch_path"] = path
            capture["body"] = body
            return {"id": "db-1"}
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(BND, "_req", fake_req)


def _schema4():
    return {
        "title": "テストDB",
        "properties": {
            "名前": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "options": ["未確認", "対応済"]},
        },
    }


def _complete_existing():
    return {
        "properties": {
            "名前": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "テストDB"}],
    }


def test_ensure_schema_noop_when_up_to_date(monkeypatch, capsys):
    cap = {}
    _wire_req(monkeypatch, _complete_existing(), cap)
    assert BND.ensure_schema("db-1", _schema4(), "tok") == 0
    assert "body" not in cap  # PATCH 未発火
    assert cap["get_path"] == "/databases/db-1"  # GET は正しいパス
    out = capsys.readouterr().out
    assert "変更なし" in out and "テストDB" in out


def test_ensure_schema_adds_missing_props(monkeypatch, capsys):
    cap = {}
    existing = {"properties": {"名前": {"type": "title"}},
                "title": [{"plain_text": "テストDB"}]}
    _wire_req(monkeypatch, existing, cap)
    assert BND.ensure_schema("db-1", _schema4(), "tok") == 0
    body = cap["body"]["properties"]
    assert set(body) == {"メモ", "金額", "状態"}
    assert body["金額"] == {"number": {"format": "yen"}}
    assert body["状態"]["select"]["options"] == [{"name": "未確認"}, {"name": "対応済"}]
    assert cap["patch_path"] == "/databases/db-1"
    out = capsys.readouterr().out
    assert "追加プロパティ (3)" in out
    assert "verify_db_schema.py" in out


def test_ensure_schema_renames_title_column(monkeypatch, capsys):
    cap = {}
    existing = {
        "properties": {
            "OldName": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "テストDB"}],
    }
    _wire_req(monkeypatch, existing, cap)
    assert BND.ensure_schema("db-1", _schema4(), "tok") == 0
    body = cap["body"]["properties"]
    assert body["OldName"] == {"name": "名前"}  # 型はそのまま名前のみ変更
    out = capsys.readouterr().out
    assert "列リネーム (値保持)" in out
    assert "OldName→名前" in out


def test_ensure_schema_no_rename_when_target_exists(monkeypatch):
    # want_title が既に存在 → 衝突回避でリネームしない
    cap = {}
    existing = {
        "properties": {
            "OldName": {"type": "title"},
            "名前": {"type": "rich_text"},  # 衝突
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "テストDB"}],
    }
    _wire_req(monkeypatch, existing, cap)
    BND.ensure_schema("db-1", _schema4(), "tok")
    assert "OldName" not in cap.get("body", {}).get("properties", {})


def test_ensure_schema_no_title_in_existing_skips_rename(monkeypatch):
    # 既存に title 型が無い場合 cur_title=None → リネーム分岐は走らない。
    # 一方で非 title プロパティ(金額)が欠落しているので追加 patch は走る。
    cap = {}
    existing = {
        "properties": {
            "メモ": {"type": "rich_text"},
            # 金額 が欠落 → 追加されるはず
            "状態": {"type": "select", "select": {"options": [
                {"name": "未確認"}, {"name": "対応済"}]}},
        },
        "title": [{"plain_text": "テストDB"}],
    }
    _wire_req(monkeypatch, existing, cap)
    assert BND.ensure_schema("db-1", _schema4(), "tok") == 0
    body = cap["body"]["properties"]
    # title 型(名前)は ensure_schema のループで除外されるため追加されない
    assert "名前" not in body
    # 欠落していた金額のみ追加。リネーム patch (set=={'name'}) は無い(cur_title=None)
    assert set(body) == {"金額"}
    assert all(set(v) != {"name"} for v in body.values())


def test_ensure_schema_merges_missing_select_options(monkeypatch):
    cap = {}
    existing = {
        "properties": {
            "名前": {"type": "title"},
            "メモ": {"type": "rich_text"},
            "金額": {"type": "number"},
            "状態": {"type": "select", "select": {"options": [{"name": "未確認"}]}},
        },
        "title": [{"plain_text": "テストDB"}],
    }
    _wire_req(monkeypatch, existing, cap)
    assert BND.ensure_schema("db-1", _schema4(), "tok") == 0
    names = {o["name"] for o in cap["body"]["properties"]["状態"]["select"]["options"]}
    assert names == {"未確認", "対応済"}


def test_ensure_schema_select_complete_no_patch(monkeypatch):
    cap = {}
    _wire_req(monkeypatch, _complete_existing(), cap)
    assert BND.ensure_schema("db-1", _schema4(), "tok") == 0
    assert "body" not in cap


def test_ensure_schema_rename_and_add_combined(monkeypatch, capsys):
    # リネーム + 追加 が両方起きる複合経路(renamed/added 両方の print 行)
    cap = {}
    existing = {
        "properties": {"OldName": {"type": "title"}},  # title 旧名のみ、他は欠落
        "title": [{"plain_text": "テストDB"}],
    }
    _wire_req(monkeypatch, existing, cap)
    assert BND.ensure_schema("db-1", _schema4(), "tok") == 0
    body = cap["body"]["properties"]
    assert body["OldName"] == {"name": "名前"}
    assert {"メモ", "金額", "状態"} <= set(body)
    out = capsys.readouterr().out
    assert "列リネーム (値保持)" in out
    assert "追加プロパティ" in out


# ===================== main() 経路 =====================


def _isolate(monkeypatch, tmp_path, argv=None):
    # main() は argparse で sys.argv を読むため、pytest の argv 混入を防ぐべく
    # 既定で素の argv (オプション無し) へ固定する。
    cfg_path = tmp_path / ".mf-kessai-config.json"
    monkeypatch.setattr(BND, "CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(BND, "_notion_token", lambda: "fake-token")
    monkeypatch.setattr(BND.sys, "argv", argv or ["build_notion_db.py"])
    return cfg_path


def test_main_existing_db_dispatches_ensure_schema(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config",
                        lambda: {"notion": {"database_id": "db-existing"}})
    seen = {}

    def fake_ensure(db_id, schema, token):
        seen["db_id"] = db_id
        seen["token"] = token
        assert "properties" in schema  # 実 schema が渡る
        return 0

    monkeypatch.setattr(BND, "ensure_schema", fake_ensure)
    assert BND.main() == 0
    assert seen == {"db_id": "db-existing", "token": "fake-token"}


def test_main_missing_parent_returns_2(monkeypatch, tmp_path, capsys):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config", lambda: {"notion": {}})
    assert BND.main() == 2
    assert "parent_page_id が空" in capsys.readouterr().err


def test_main_no_notion_section_returns_2(monkeypatch, tmp_path, capsys):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config", lambda: {})
    assert BND.main() == 2
    assert "parent_page_id が空" in capsys.readouterr().err


def test_main_creates_new_db_and_records_id(monkeypatch, tmp_path, capsys):
    cfg_path = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config",
                        lambda: {"notion": {"parent_page_id": "parent-1"}})
    cap = {}

    def fake_req(method, path, token, body=None):
        cap.update(method=method, path=path, token=token, body=body)
        return {"id": "new-db-id"}

    monkeypatch.setattr(BND, "_req", fake_req)
    assert BND.main() == 0

    assert cap["method"] == "POST" and cap["path"] == "/databases"
    assert cap["token"] == "fake-token"
    body = cap["body"]
    assert body["parent"] == {"type": "page_id", "page_id": "parent-1"}
    schema = BND.load_schema()
    assert body["title"][0]["text"]["content"] == schema["title"]
    assert set(body["properties"]) == set(schema["properties"])

    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["notion"]["database_id"] == "new-db-id"
    out = capsys.readouterr().out
    assert "DB作成完了" in out and "new-db-id" in out


def test_main_new_db_preserves_other_config_keys(monkeypatch, tmp_path):
    cfg_path = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(
        BND, "load_config",
        lambda: {"environment": "sandbox", "notion": {"parent_page_id": "p1"}})
    monkeypatch.setattr(BND, "_req", lambda *a, **k: {"id": "db-X"})
    assert BND.main() == 0
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["environment"] == "sandbox"
    assert saved["notion"]["parent_page_id"] == "p1"
    assert saved["notion"]["database_id"] == "db-X"


def test_main_new_db_setdefault_when_notion_absent_post_load(monkeypatch, tmp_path):
    # load_config が parent を返すが、setdefault('notion', {}) のフォールバックを通す
    cfg_path = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(BND, "load_config",
                        lambda: {"notion": {"parent_page_id": "p9"}})
    monkeypatch.setattr(BND, "_req", lambda *a, **k: {"id": "db-Y"})
    assert BND.main() == 0
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["notion"]["database_id"] == "db-Y"


# ===================== save_config (round-trip) =====================


def test_save_config_writes_utf8_with_trailing_newline(monkeypatch, tmp_path):
    cfg_path = tmp_path / "out.json"
    monkeypatch.setattr(BND, "CONFIG_PATH", str(cfg_path))
    BND.save_config({"notion": {"database_id": "abc"}, "和": "値"})
    raw = cfg_path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "和" in raw  # ensure_ascii=False で日本語そのまま
    assert json.loads(raw)["notion"]["database_id"] == "abc"
