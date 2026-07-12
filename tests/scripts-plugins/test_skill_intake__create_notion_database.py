"""genuine な機能テスト: skill-intake/scripts/create_notion_database.py

純関数 (build_property_def / build_properties / parse_args) を実入力で呼び実出力を
assert する。Notion REST を叩く経路 (create_db / sync_db / resolve_parent_page) は
notion_fetch / notion_config を monkeypatch で遮断し、dry-run・入力エラー・drift 計算
ロジックのみを genuine に検証する (実通信・keychain・network 一切なし)。

main() は subprocess (sys.executable) で安全引数 (--dry-run / mode 欠落) を与え
returncode と出力を assert する。dry-run は notion_fetch を呼ばないため通信が起きない。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "plugins" / "skill-intake" / "scripts"
SCRIPT = SCRIPTS_DIR / "create_notion_database.py"


def _load_module():
    # create_notion_database は `import notion_config` / `from notion_http import ...`
    # を同階層から行うため scripts dir を sys.path に入れる。
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("create_notion_database_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---- build_property_def ----
@pytest.mark.parametrize(
    "spec,expected",
    [
        ({"type": "title"}, {"title": {}}),
        ({"type": "rich_text"}, {"rich_text": {}}),
        ({"type": "number"}, {"number": {"format": "number"}}),
        ({"type": "checkbox"}, {"checkbox": {}}),
        ({"type": "url"}, {"url": {}}),
        ({"type": "people"}, {"people": {}}),
        ({"type": "created_time"}, {"created_time": {}}),
        ({"type": "last_edited_time"}, {"last_edited_time": {}}),
    ],
)
def test_build_property_def_simple_types(spec, expected):
    assert MOD.build_property_def(spec) == expected


def test_build_property_def_select_maps_options():
    out = MOD.build_property_def({"type": "select", "options": ["A", "B"]})
    assert out == {"select": {"options": [{"name": "A"}, {"name": "B"}]}}


def test_build_property_def_multi_select_maps_options():
    out = MOD.build_property_def({"type": "multi_select", "options": ["x"]})
    assert out == {"multi_select": {"options": [{"name": "x"}]}}


def test_build_property_def_select_without_options_is_empty():
    assert MOD.build_property_def({"type": "select"}) == {"select": {"options": []}}


def test_build_property_def_unsupported_raises():
    with pytest.raises(ValueError, match="unsupported type: rollup"):
        MOD.build_property_def({"type": "rollup"})


# ---- build_properties ----
def test_build_properties_maps_each_property():
    schema = {
        "properties": {
            "名前": {"type": "title"},
            "状態": {"type": "select", "options": ["a", "b"]},
            "メモ": {"type": "rich_text"},
        }
    }
    out = MOD.build_properties(schema)
    assert out["名前"] == {"title": {}}
    assert out["状態"] == {"select": {"options": [{"name": "a"}, {"name": "b"}]}}
    assert out["メモ"] == {"rich_text": {}}


def test_build_properties_against_real_schema():
    # references/notion-db-schema.json を実入力として読み込み、全プロパティが変換可能なことを検証
    schema = json.loads(MOD.SCHEMA_PATH.read_text(encoding="utf-8"))
    out = MOD.build_properties(schema)
    assert set(out.keys()) == set(schema["properties"].keys())
    # title プロパティが少なくとも 1 つ存在する
    assert any(v == {"title": {}} for v in out.values())


# ---- parse_args ----
def test_parse_args_equals_form_mode():
    assert MOD.parse_args(["--mode=create"]) == {"mode": "create"}


def test_parse_args_space_form_all_flags():
    out = MOD.parse_args(
        [
            "--mode",
            "sync",
            "--database-id",
            "DB123",
            "--parent-page",
            "PG1",
            "--parent-page-url",
            "https://notion.so/x",
            "--title",
            "見出し",
            "--dry-run",
        ]
    )
    assert out == {
        "mode": "sync",
        "databaseId": "DB123",
        "parentPage": "PG1",
        "parentPageUrl": "https://notion.so/x",
        "title": "見出し",
        "dryRun": True,
    }


def test_parse_args_empty():
    assert MOD.parse_args([]) == {}


# ---- resolve_parent_page (monkeypatched notion_config) ----
def test_resolve_parent_page_prefers_parent_page(monkeypatch):
    monkeypatch.setattr(MOD.notion_config, "canonical_notion_id", lambda v: f"canon:{v}" if v else None)
    monkeypatch.setattr(MOD.notion_config, "get_parent_page_id", lambda: "FALLBACK")
    assert MOD.resolve_parent_page({"parentPage": "PG"}) == "canon:PG"


def test_resolve_parent_page_falls_back_to_url_then_config(monkeypatch):
    monkeypatch.setattr(MOD.notion_config, "canonical_notion_id", lambda v: f"canon:{v}" if v else None)
    monkeypatch.setattr(MOD.notion_config, "get_parent_page_id", lambda: "FALLBACK")
    assert MOD.resolve_parent_page({"parentPageUrl": "URL"}) == "canon:URL"
    assert MOD.resolve_parent_page({}) == "FALLBACK"


# ---- configured_db_ids (親ページ誤設定ガードの材料) ----
def test_configured_db_ids_canonicalizes_and_skips_empty(monkeypatch):
    monkeypatch.setattr(
        MOD.notion_config,
        "load_config",
        lambda *a, **k: {
            "databases": {
                "hearing-sheet": {"db_id": "36607a0cd18c80bf9effc74aa736645c"},
                "skill-list": {"db_id": ""},
            }
        },
    )
    assert MOD.configured_db_ids() == {"36607a0c-d18c-80bf-9eff-c74aa736645c"}


def test_configured_db_ids_empty_when_no_config(monkeypatch):
    monkeypatch.setattr(MOD.notion_config, "load_config", lambda *a, **k: None)
    assert MOD.configured_db_ids() == set()


# ---- create_db ----
def test_create_db_requires_parent_page_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        MOD.create_db(None, "title", {"properties": {}}, dry_run=False)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "DB新規作成には親“ページ”IDが必要です" in err
    assert "parent_page.page_id" in err


def test_create_db_rejects_parent_equal_to_configured_db_id(monkeypatch, capsys):
    # fail-closed guard: 親ページ ID が databases.*.db_id と同一 (親が DB を指す誤設定) は拒否。
    monkeypatch.setattr(
        MOD.notion_config,
        "load_config",
        lambda *a, **k: {
            "databases": {"hearing-sheet": {"db_id": "36607a0c-d18c-80bf-9eff-c74aa736645c"}}
        },
    )
    with pytest.raises(SystemExit) as exc:
        MOD.create_db(
            "36607a0c-d18c-80bf-9eff-c74aa736645c", None, {"properties": {}}, dry_run=True
        )
    assert exc.value.code == 2
    assert "DB新規作成には親“ページ”IDが必要です" in capsys.readouterr().err


def test_create_db_dry_run_does_not_call_notion(monkeypatch, capsys):
    def _boom(*a, **k):
        raise AssertionError("notion_fetch must not be called in dry-run")

    monkeypatch.setattr(MOD, "notion_fetch", _boom)
    schema = {"properties": {"名前": {"type": "title"}, "メモ": {"type": "rich_text"}}}
    res = MOD.create_db("PAGE_ID", "見出し", schema, dry_run=True)
    assert res is None
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "create"
    assert out["dry_run"] is True
    assert out["parent_page_id"] == "PAGE_ID"
    assert out["title"] == "見出し"
    assert out["property_count"] == 2


def test_create_db_real_call_uses_notion_fetch(monkeypatch, capsys):
    calls: list = []

    def _fake_fetch(path, method="GET", body=None):
        calls.append((path, method, body))
        return {"id": "newdb", "url": "https://notion.so/newdb"}

    monkeypatch.setattr(MOD, "notion_fetch", _fake_fetch)
    schema = {"properties": {"名前": {"type": "title"}}}
    res = MOD.create_db("PAGE_ID", None, schema, dry_run=False)
    assert res == {"id": "newdb", "url": "https://notion.so/newdb"}
    assert calls[0][0] == "/databases"
    assert calls[0][1] == "POST"
    # title 未指定時は既定タイトルが入る
    assert calls[0][2]["title"][0]["text"]["content"] == "skillインタビュー"
    assert "created database id=newdb" in capsys.readouterr().out


# ---- sync_db ----
def test_sync_db_requires_database_id_exits_2():
    with pytest.raises(SystemExit) as exc:
        MOD.sync_db(None, {"properties": {}}, dry_run=False)
    assert exc.value.code == 2


def test_sync_db_no_drift_when_matching(monkeypatch, capsys):
    schema = {"properties": {"名前": {"type": "title"}, "状態": {"type": "select", "options": ["a"]}}}

    def _fake_fetch(path, method="GET", body=None):
        assert method == "GET"  # drift 無しなら PATCH は発行されない
        return {
            "properties": {
                "名前": {"type": "title"},
                "状態": {"type": "select", "select": {"options": [{"name": "a"}]}},
            }
        }

    monkeypatch.setattr(MOD, "notion_fetch", _fake_fetch)
    res = MOD.sync_db("DB1", schema, dry_run=False)
    assert res is None
    assert "no drift; nothing to sync" in capsys.readouterr().out


def test_sync_db_detects_missing_property(monkeypatch, capsys):
    schema = {"properties": {"名前": {"type": "title"}, "メモ": {"type": "rich_text"}}}

    def _fake_fetch(path, method="GET", body=None):
        return {"properties": {"名前": {"type": "title"}}}  # メモ 欠落

    monkeypatch.setattr(MOD, "notion_fetch", _fake_fetch)
    res = MOD.sync_db("DB1", schema, dry_run=True)
    assert res is None
    out = capsys.readouterr().out
    assert "sync plan: メモ" in out
    assert "dry-run: no PATCH issued" in out


def test_sync_db_detects_select_option_drift(monkeypatch, capsys):
    schema = {"properties": {"状態": {"type": "select", "options": ["a", "b"]}}}

    def _fake_fetch(path, method="GET", body=None):
        return {
            "properties": {
                "状態": {"type": "select", "select": {"options": [{"name": "a"}]}}  # b が欠落
            }
        }

    monkeypatch.setattr(MOD, "notion_fetch", _fake_fetch)
    res = MOD.sync_db("DB1", schema, dry_run=True)
    assert res is None
    assert "sync plan: 状態" in capsys.readouterr().out


def test_sync_db_title_rename(monkeypatch, capsys):
    schema = {"properties": {"名前": {"type": "title"}}}

    def _fake_fetch(path, method="GET", body=None):
        return {"properties": {"Name": {"type": "title"}}}  # 旧タイトル名

    monkeypatch.setattr(MOD, "notion_fetch", _fake_fetch)
    res = MOD.sync_db("DB1", schema, dry_run=True)
    assert res is None
    out = capsys.readouterr().out
    assert 'title rename: "Name" -> "名前"' in out


def test_sync_db_applies_patch_when_not_dry_run(monkeypatch, capsys):
    schema = {"properties": {"名前": {"type": "title"}, "メモ": {"type": "rich_text"}}}
    calls: list = []

    def _fake_fetch(path, method="GET", body=None):
        calls.append((path, method, body))
        if method == "GET":
            return {"properties": {"名前": {"type": "title"}}}  # メモ 欠落
        return {"ok": True}

    monkeypatch.setattr(MOD, "notion_fetch", _fake_fetch)
    res = MOD.sync_db("DB1", schema, dry_run=False)
    assert res == {"ok": True}
    patch_call = [c for c in calls if c[1] == "PATCH"][0]
    assert patch_call[0] == "/databases/DB1"
    assert "メモ" in patch_call[2]["properties"]
    assert "synced 1 properties" in capsys.readouterr().out


# ---- main() via subprocess (no network: dry-run / input errors) ----
def test_main_subprocess_no_mode_exits_2():
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS_DIR),
    )
    assert res.returncode == 2
    assert "--mode=create|sync required" in res.stderr


def test_main_subprocess_create_dry_run_no_network(tmp_path):
    # --dry-run は notion_fetch を呼ばないため実通信なし。親ページは引数で与える。
    res = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mode=create",
            "--parent-page",
            "11111111111111111111111111111111",
            "--title",
            "テストDB",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS_DIR),
    )
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["mode"] == "create"
    assert out["dry_run"] is True
    assert out["title"] == "テストDB"
    assert out["property_count"] > 0


# ---- main() in-process (dispatch + error handling, notion_fetch monkeypatched) ----
def test_main_dispatch_create_returns_zero(monkeypatch):
    seen = {}
    monkeypatch.setattr(MOD, "create_db", lambda *a, **k: seen.setdefault("create", a))
    monkeypatch.setattr(MOD, "resolve_parent_page", lambda args: "PG")
    rc = MOD.main(["--mode=create", "--dry-run"])
    assert rc == 0
    assert "create" in seen


def test_main_dispatch_sync_returns_zero(monkeypatch):
    seen = {}
    monkeypatch.setattr(MOD, "sync_db", lambda *a, **k: seen.setdefault("sync", a))
    rc = MOD.main(["--mode=sync", "--database-id", "DB1"])
    assert rc == 0
    assert "sync" in seen


def test_main_missing_mode_returns_2(monkeypatch, capsys):
    rc = MOD.main([])
    assert rc == 2
    assert "--mode=create|sync required" in capsys.readouterr().err


def test_main_notion_http_error_401_maps_to_44(monkeypatch, capsys):
    def _raise(*a, **k):
        raise MOD.NotionHttpError("unauthorized", status=401)

    monkeypatch.setattr(MOD, "sync_db", _raise)
    rc = MOD.main(["--mode=sync", "--database-id", "DB1"])
    assert rc == 44
    assert "unauthorized" in capsys.readouterr().err


def test_main_notion_http_error_other_maps_to_1(monkeypatch, capsys):
    def _raise(*a, **k):
        raise MOD.NotionHttpError("server error", status=500)

    monkeypatch.setattr(MOD, "sync_db", _raise)
    rc = MOD.main(["--mode=sync", "--database-id", "DB1"])
    assert rc == 1
    assert "server error" in capsys.readouterr().err


def test_main_generic_exception_maps_to_1(monkeypatch, capsys):
    def _raise(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(MOD, "create_db", _raise)
    monkeypatch.setattr(MOD, "resolve_parent_page", lambda args: "PG")
    rc = MOD.main(["--mode=create"])
    assert rc == 1
    assert "boom" in capsys.readouterr().err
