"""verify_notion_schema.py の純関数 + main CLI 契約を network/keychain 無しで網羅する。

verify_notion_schema.py は期待スキーマ (references/notion-db-schema.json) と
現状 Notion DB の properties を突き合わせ conflicts を eval-log に書き出すツール。
実通信 (notion_http.get_database) と DB ID 解決 (notion_config.get_db_id) は
**絶対に叩かない**: 両者を sys.modules にフェイク注入し、引数検証・分類ロジック・
レポート構築・エラー経路・exit code を実入力で genuine に assert する。

純関数:
  - normalize_type: 恒等
  - classify_conflict: ok / missing(required) / missing_optional / type_mismatch /
    options_drift(missing/extra) / select 以外は options 無視
  - classify_extras: 期待外プロパティ検出

main (in-process で MOD.main を直接呼ぶ。notion_config / notion_http を fake 化):
  - notion_config import 失敗 -> exit 2
  - database_id 未解決 -> exit 2
  - --database-id 明示 / notion_config 解決 の両 source
  - 無効 --on-conflict -> exit 2
  - NotionHttpError 401 -> exit 44, それ以外 -> exit 1
  - 正常 skip-warn: レポート書き出し + exit 0 + by_kind 集計
  - fail-stop + blocking conflict -> exit 1
  - fail-stop で blocking 無し (missing_optional/extra のみ) -> exit 0
  - --out 明示パス

全て monkeypatch.chdir(tmp_path) で repo 非汚染。
"""
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "plugins" / "skill-intake" / "scripts"
SCRIPT = SCRIPTS_DIR / "verify_notion_schema.py"

_SPEC = importlib.util.spec_from_file_location("verify_notion_schema_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# normalize_type
# --------------------------------------------------------------------------

def test_normalize_type_is_identity():
    assert MOD.normalize_type("select") == "select"
    assert MOD.normalize_type(None) is None


# --------------------------------------------------------------------------
# classify_conflict
# --------------------------------------------------------------------------

def test_classify_conflict_match_ok():
    expected = {"name": "名前", "spec": {"type": "title", "required": True}}
    actual = {"type": "title"}
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "ok"
    assert r["detail"] == "match"


def test_classify_conflict_missing_required():
    expected = {"name": "名前", "spec": {"type": "title", "required": True}}
    r = MOD.classify_conflict(expected, None)
    assert r["kind"] == "missing"
    assert "required property absent" in r["detail"]
    assert "type=title" in r["detail"]


def test_classify_conflict_missing_optional():
    expected = {"name": "テーマ抽出", "spec": {"type": "select", "required": False}}
    r = MOD.classify_conflict(expected, None)
    assert r["kind"] == "missing_optional"
    assert "optional property absent" in r["detail"]


def test_classify_conflict_type_mismatch():
    expected = {"name": "真の課題", "spec": {"type": "rich_text", "required": True}}
    actual = {"type": "title"}
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "type_mismatch"
    assert r["detail"] == "expected=rich_text, actual=title"


def test_classify_conflict_options_drift_missing_and_extra():
    expected = {
        "name": "ステータス",
        "spec": {"type": "select", "required": True, "options": ["下書き", "レビュー中"]},
    }
    actual = {
        "type": "select",
        "select": {"options": [{"name": "下書き"}, {"name": "完了"}]},
    }
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "options_drift"
    assert "missing options: [レビュー中]" in r["detail"]
    assert "extra options: [完了]" in r["detail"]


def test_classify_conflict_options_drift_only_missing():
    expected = {
        "name": "深度",
        "spec": {"type": "select", "required": True, "options": ["light", "standard", "detailed"]},
    }
    actual = {"type": "select", "select": {"options": [{"name": "light"}]}}
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "options_drift"
    assert "missing options: [standard, detailed]" in r["detail"]
    assert "extra options" not in r["detail"]


def test_classify_conflict_options_match_returns_ok():
    expected = {
        "name": "深度",
        "spec": {"type": "select", "required": True, "options": ["a", "b"]},
    }
    actual = {"type": "select", "select": {"options": [{"name": "a"}, {"name": "b"}]}}
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "ok"


def test_classify_conflict_multi_select_options_drift():
    expected = {
        "name": "出力先",
        "spec": {"type": "multi_select", "required": True, "options": ["Slack", "Notion"]},
    }
    actual = {"type": "multi_select", "multi_select": {"options": [{"name": "Slack"}]}}
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "options_drift"
    assert "missing options: [Notion]" in r["detail"]


def test_classify_conflict_select_without_options_spec_is_ok():
    # spec.options が list でない場合は options チェックをスキップして ok
    expected = {"name": "x", "spec": {"type": "select", "required": True}}
    actual = {"type": "select", "select": {"options": [{"name": "whatever"}]}}
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "ok"


def test_classify_conflict_non_select_ignores_options():
    # type が select/multi_select 以外なら options drift を見ない
    expected = {"name": "x", "spec": {"type": "rich_text", "required": True, "options": ["a"]}}
    actual = {"type": "rich_text"}
    r = MOD.classify_conflict(expected, actual)
    assert r["kind"] == "ok"


# --------------------------------------------------------------------------
# classify_extras
# --------------------------------------------------------------------------

def test_classify_extras_detects_unexpected():
    expected_names = {"名前", "ステータス"}
    actual_props = {
        "名前": {"type": "title"},
        "幽霊列": {"type": "number"},
        "ステータス": {"type": "select"},
    }
    out = MOD.classify_extras(expected_names, actual_props)
    assert len(out) == 1
    assert out[0]["name"] == "幽霊列"
    assert out[0]["kind"] == "extra"
    assert "unexpected property: number" in out[0]["detail"]


def test_classify_extras_none_when_all_expected():
    expected_names = {"名前", "ステータス"}
    actual_props = {"名前": {"type": "title"}, "ステータス": {"type": "select"}}
    assert MOD.classify_extras(expected_names, actual_props) == []


# --------------------------------------------------------------------------
# main: fakes for notion_config / notion_http
# --------------------------------------------------------------------------

class _FakeNotionHttpError(Exception):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def _install_fakes(monkeypatch, *, db_id_return="cfg-db-id", db_id_raises=False,
                   get_database_return=None, get_database_raises=None):
    """notion_config / notion_http を sys.modules にフェイク注入する。

    main は `import notion_config as _nc` と `from notion_http import get_database, NotionHttpError`
    を関数内で行うため、呼び出し前に sys.modules を差し替えれば実体は import されない。
    """
    fake_cfg = types.ModuleType("notion_config")

    def _get_db_id(key):
        assert key == "hearing-sheet"
        if db_id_raises:
            raise RuntimeError("config broken")
        return db_id_return

    fake_cfg.get_db_id = _get_db_id

    fake_http = types.ModuleType("notion_http")
    fake_http.NotionHttpError = _FakeNotionHttpError

    def _get_database(database_id):
        if get_database_raises is not None:
            raise get_database_raises
        return get_database_return or {}

    fake_http.get_database = _get_database
    fake_http._calls = []

    monkeypatch.setitem(sys.modules, "notion_config", fake_cfg)
    monkeypatch.setitem(sys.modules, "notion_http", fake_http)
    return fake_cfg, fake_http


def _db_with_all_required(overrides=None):
    """schema の必須プロパティを全て満たす擬似 DB レスポンスを組む。"""
    schema = json.loads(MOD.SCHEMA_PATH.read_text(encoding="utf-8"))
    props = {}
    for name, spec in schema["properties"].items():
        t = spec["type"]
        entry = {"type": t}
        if t in ("select", "multi_select") and isinstance(spec.get("options"), list):
            entry[t] = {"options": [{"name": o} for o in spec["options"]]}
        props[name] = entry
    db = {"title": [{"plain_text": "Hearing Sheet"}], "properties": props}
    if overrides:
        db["properties"].update(overrides)
    return db


# --------------------------------------------------------------------------
# main: error paths
# --------------------------------------------------------------------------

def test_main_notion_config_import_failure_exit2(monkeypatch, tmp_path, capsys):
    # notion_config モジュールが import 不能 = ImportError 経路 (except Exception)
    monkeypatch.chdir(tmp_path)
    # わざと notion_config を壊れた値に: get_db_id が無い → AttributeError ではなく
    # ここでは import 自体を失敗させるため sys.modules に raise する偽を入れにくいので
    # get_db_id 内で例外を投げる経路を使う (return 2 を踏む)
    _install_fakes(monkeypatch, db_id_raises=True)
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py"])
    rc = MOD.main()
    assert rc == 2
    err = capsys.readouterr().err
    assert "notion_config failed" in err


def test_main_no_database_id_exit2(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _install_fakes(monkeypatch, db_id_return=None)  # config から解決できず
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py"])
    rc = MOD.main()
    assert rc == 2
    assert "database_id is required" in capsys.readouterr().err


def test_main_invalid_on_conflict_exit2(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _install_fakes(monkeypatch, db_id_return="db-1")
    monkeypatch.setattr(
        sys, "argv", ["verify_notion_schema.py", "--database-id", "db-1", "--on-conflict", "bogus"]
    )
    rc = MOD.main()
    assert rc == 2
    assert "invalid --on-conflict: bogus" in capsys.readouterr().err


def test_main_http_401_exit44(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    err = _FakeNotionHttpError("unauthorized", status=401)
    _install_fakes(monkeypatch, db_id_return="db-1", get_database_raises=err)
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py", "--database-id", "db-1"])
    rc = MOD.main()
    assert rc == 44
    assert "verify_notion_schema" in capsys.readouterr().err


def test_main_http_other_error_exit1(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    err = _FakeNotionHttpError("not found", status=404)
    _install_fakes(monkeypatch, db_id_return="db-1", get_database_raises=err)
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py", "--database-id", "db-1"])
    rc = MOD.main()
    assert rc == 1


# --------------------------------------------------------------------------
# main: success paths
# --------------------------------------------------------------------------

def test_main_success_clean_db_exit0(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    db = _db_with_all_required()
    _install_fakes(monkeypatch, db_id_return="cfg-db", get_database_return=db)
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py"])  # source=notion_config
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "wrote" in out

    # レポート + db-id-resolution が書かれている
    report = json.loads((tmp_path / "eval-log" / "notion-conflicts.json").read_text(encoding="utf-8"))
    assert report["database_id"] == "cfg-db"
    assert report["database_title"] == "Hearing Sheet"
    assert report["mode"] == "skip-warn"
    # 全プロパティ一致なので blocking conflict は無い (missing_optional のみ起き得る)
    blocking = [c for c in report["conflicts"] if c["kind"] not in ("missing_optional", "extra")]
    assert blocking == []

    res = json.loads((tmp_path / "eval-log" / "db-id-resolution.json").read_text(encoding="utf-8"))
    assert res["source"] == "notion_config"
    assert res["database_id"] == "cfg-db"


def test_main_database_id_arg_source(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db = _db_with_all_required()
    _install_fakes(monkeypatch, db_id_return="cfg-db", get_database_return=db)
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py", "--database-id", "arg-db"])
    rc = MOD.main()
    assert rc == 0
    res = json.loads((tmp_path / "eval-log" / "db-id-resolution.json").read_text(encoding="utf-8"))
    assert res["source"] == "arg"
    assert res["database_id"] == "arg-db"


def test_main_conflicts_counted_by_kind(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db = _db_with_all_required()
    # 必須プロパティ「名前」を型違いにする -> type_mismatch
    db["properties"]["名前"] = {"type": "rich_text"}
    # 期待外プロパティを追加 -> extra
    db["properties"]["幽霊"] = {"type": "number"}
    # select の options を欠落 -> options_drift
    db["properties"]["ステータス"] = {"type": "select", "select": {"options": [{"name": "下書き"}]}}
    _install_fakes(monkeypatch, db_id_return="db-x", get_database_return=db)
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py", "--database-id", "db-x"])
    rc = MOD.main()
    assert rc == 0  # skip-warn は常に 0
    report = json.loads((tmp_path / "eval-log" / "notion-conflicts.json").read_text(encoding="utf-8"))
    by_kind = report["summary"]["by_kind"]
    assert by_kind.get("type_mismatch", 0) >= 1
    assert by_kind.get("extra", 0) >= 1
    assert by_kind.get("options_drift", 0) >= 1
    assert report["summary"]["total"] == len(report["conflicts"])


def test_main_fail_stop_with_blocking_exit1(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    db = _db_with_all_required()
    db["properties"]["名前"] = {"type": "rich_text"}  # type_mismatch = blocking
    _install_fakes(monkeypatch, db_id_return="db-x", get_database_return=db)
    monkeypatch.setattr(
        sys, "argv", ["verify_notion_schema.py", "--database-id", "db-x", "--on-conflict", "fail-stop"]
    )
    rc = MOD.main()
    assert rc == 1
    assert "fail-stop" in capsys.readouterr().err


def test_main_fail_stop_only_extras_exit0(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db = _db_with_all_required()
    db["properties"]["幽霊"] = {"type": "number"}  # extra = non-blocking
    _install_fakes(monkeypatch, db_id_return="db-x", get_database_return=db)
    monkeypatch.setattr(
        sys, "argv", ["verify_notion_schema.py", "--database-id", "db-x", "--on-conflict", "fail-stop"]
    )
    rc = MOD.main()
    assert rc == 0


def test_main_explicit_out_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db = _db_with_all_required()
    _install_fakes(monkeypatch, db_id_return="db-x", get_database_return=db)
    out_path = tmp_path / "custom" / "report.json"
    monkeypatch.setattr(
        sys, "argv", ["verify_notion_schema.py", "--database-id", "db-x", "--out", str(out_path)]
    )
    rc = MOD.main()
    assert rc == 0
    assert out_path.exists()
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["database_id"] == "db-x"


def test_main_eval_log_write_failure_swallowed(monkeypatch, tmp_path):
    # eval-log を「ファイル」にして mkdir(exist_ok=True) を FileExistsError にし、
    # db-id-resolution 書き出しの except Exception: pass 経路 (line 87-88) を踏む。
    # 本体レポートは --out で別パスへ逃がして処理は完走させる。
    monkeypatch.chdir(tmp_path)
    (tmp_path / "eval-log").write_text("not a dir", encoding="utf-8")
    db = _db_with_all_required()
    _install_fakes(monkeypatch, db_id_return="db-x", get_database_return=db)
    out_path = tmp_path / "out" / "report.json"
    monkeypatch.setattr(
        sys, "argv", ["verify_notion_schema.py", "--database-id", "db-x", "--out", str(out_path)]
    )
    rc = MOD.main()
    assert rc == 0
    assert out_path.exists()
    # eval-log はファイルのままで db-id-resolution.json は書かれていない (例外が握り潰された)
    assert (tmp_path / "eval-log").is_file()


def test_module_main_guard_via_subprocess(tmp_path):
    # `if __name__ == '__main__': sys.exit(main())` (line 134) を実プロセスで踏む。
    # NOTION_CONFIG_PATH を存在しないファイルに向けると notion_config が FileNotFoundError を
    # 投げ、main は except Exception で exit 2 を返す (network/keychain には到達しない)。
    env = dict(os.environ)
    env["NOTION_CONFIG_PATH"] = str(tmp_path / "does-not-exist.json")
    env.pop("INTAKE_NOTION_DATABASE_ID", None)
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 2
    assert "notion_config failed" in r.stderr


def test_main_missing_optional_classified(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    db = _db_with_all_required()
    # optional プロパティ「テーマ抽出」を削除 -> missing_optional (non-blocking)
    del db["properties"]["テーマ抽出"]
    _install_fakes(monkeypatch, db_id_return="db-x", get_database_return=db)
    monkeypatch.setattr(
        sys, "argv", ["verify_notion_schema.py", "--database-id", "db-x", "--on-conflict", "fail-stop"]
    )
    rc = MOD.main()
    assert rc == 0  # missing_optional は blocking でない
    report = json.loads((tmp_path / "eval-log" / "notion-conflicts.json").read_text(encoding="utf-8"))
    assert report["summary"]["by_kind"].get("missing_optional", 0) >= 1
