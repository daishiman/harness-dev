"""verify_notion_schema.py を network/keychain/Notion を一切叩かず genuine に網羅する。

このスクリプトは main() 内で notion_config (DB ID SSOT) と notion_http
(get_database / NotionHttpError) を *遅延 import* する。実通信を避けるため:

  - notion_config / notion_http を sys.modules に fake module として注入してから main を呼ぶ。
    fake notion_http.get_database は実 HTTP の代わりにメモリ上の DB dict / 例外を返す。
  - notion_config.get_db_id は per-repo config を読まずテストが制御する値を返す。
  - main() は cwd 相対で eval-log/ を作るため monkeypatch.chdir(tmp_path) で repo を汚さない。

純関数 (normalize_type / classify_conflict / classify_extras) は importlib で実ファイルから
直接ロードして実入力で検証する。main は argv を渡して in-process で exit code / 生成 JSON /
stdout / stderr を assert する。tests/scripts3 の既存テストと衝突しない名前 (_r4) を使う。
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "verify_notion_schema.py"

# tests/scripts3 と衝突しないモジュール名で in-process ロード。
_SPEC = importlib.util.spec_from_file_location("verify_notion_schema_r4", SCRIPT)
VNS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VNS)


# --------------------------------------------------------------------------
# 純関数: normalize_type
# --------------------------------------------------------------------------

def test_normalize_type_identity():
    assert VNS.normalize_type("select") == "select"
    assert VNS.normalize_type(None) is None


# --------------------------------------------------------------------------
# 純関数: classify_conflict
# --------------------------------------------------------------------------

def _exp(spec):
    return {"name": "X", "spec": spec}


def test_classify_conflict_ok_match():
    r = VNS.classify_conflict(_exp({"type": "title"}), {"type": "title"})
    assert r["kind"] == "ok"


def test_classify_conflict_missing_required():
    r = VNS.classify_conflict(_exp({"type": "select", "required": True}), None)
    assert r["kind"] == "missing"
    assert "required" in r["detail"]


def test_classify_conflict_missing_optional():
    r = VNS.classify_conflict(_exp({"type": "select", "required": False}), None)
    assert r["kind"] == "missing_optional"
    assert "optional" in r["detail"]


def test_classify_conflict_type_mismatch():
    r = VNS.classify_conflict(_exp({"type": "select"}), {"type": "multi_select"})
    assert r["kind"] == "type_mismatch"
    assert "expected=select" in r["detail"]
    assert "actual=multi_select" in r["detail"]


def test_classify_conflict_select_options_missing():
    spec = {"type": "select", "options": ["A", "B", "C"]}
    actual = {"type": "select", "select": {"options": [{"name": "A"}]}}
    r = VNS.classify_conflict(_exp(spec), actual)
    assert r["kind"] == "options_drift"
    assert "missing options" in r["detail"]
    assert "B" in r["detail"] and "C" in r["detail"]


def test_classify_conflict_select_options_extra():
    spec = {"type": "select", "options": ["A"]}
    actual = {"type": "select", "select": {"options": [{"name": "A"}, {"name": "Z"}]}}
    r = VNS.classify_conflict(_exp(spec), actual)
    assert r["kind"] == "options_drift"
    assert "extra options" in r["detail"]
    assert "Z" in r["detail"]


def test_classify_conflict_select_options_missing_and_extra():
    spec = {"type": "multi_select", "options": ["A", "B"]}
    actual = {"type": "multi_select", "multi_select": {"options": [{"name": "A"}, {"name": "Q"}]}}
    r = VNS.classify_conflict(_exp(spec), actual)
    assert r["kind"] == "options_drift"
    assert "missing options" in r["detail"]
    assert "extra options" in r["detail"]


def test_classify_conflict_select_options_perfect_match_is_ok():
    spec = {"type": "select", "options": ["A", "B"]}
    actual = {"type": "select", "select": {"options": [{"name": "A"}, {"name": "B"}]}}
    r = VNS.classify_conflict(_exp(spec), actual)
    assert r["kind"] == "ok"


def test_classify_conflict_select_options_none_handled():
    # actual.select.options が無い (None) でも例外なく drift として扱える
    spec = {"type": "select", "options": ["A"]}
    actual = {"type": "select", "select": {}}
    r = VNS.classify_conflict(_exp(spec), actual)
    assert r["kind"] == "options_drift"


def test_classify_conflict_no_options_spec_is_ok():
    # spec.options が list でない select → option 比較スキップで ok
    spec = {"type": "select"}
    actual = {"type": "select", "select": {"options": [{"name": "Z"}]}}
    r = VNS.classify_conflict(_exp(spec), actual)
    assert r["kind"] == "ok"


# --------------------------------------------------------------------------
# 純関数: classify_extras
# --------------------------------------------------------------------------

def test_classify_extras_detects_unexpected():
    expected = {"名前"}
    actual = {"名前": {"type": "title"}, "余分": {"type": "rich_text"}}
    out = VNS.classify_extras(expected, actual)
    assert len(out) == 1
    assert out[0]["name"] == "余分"
    assert out[0]["kind"] == "extra"
    assert "rich_text" in out[0]["detail"]


def test_classify_extras_none_when_all_expected():
    expected = {"名前", "ステータス"}
    actual = {"名前": {"type": "title"}, "ステータス": {"type": "select"}}
    assert VNS.classify_extras(expected, actual) == []


# --------------------------------------------------------------------------
# main() — fake module 注入で network なしに全経路を網羅
# --------------------------------------------------------------------------

class _FakeNotionHttpError(Exception):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def _install_fakes(monkeypatch, *, db_id_value, get_database_impl):
    """notion_config / notion_http を fake module として sys.modules に注入する。

    script は `sys.path.insert(0, scriptdir)` 後に `import notion_config` / `from notion_http
    import ...` する。事前に sys.modules に登録しておけば実ファイルを読まず fake が使われる。
    """
    fake_cfg = types.ModuleType("notion_config")
    fake_cfg.get_db_id = lambda key: db_id_value if key == "hearing-sheet" else None
    monkeypatch.setitem(sys.modules, "notion_config", fake_cfg)

    fake_http = types.ModuleType("notion_http")
    fake_http.NotionHttpError = _FakeNotionHttpError
    fake_http.get_database = get_database_impl
    monkeypatch.setitem(sys.modules, "notion_http", fake_http)


def _real_schema_db_matching():
    """実 schema を読んで全プロパティが一致する DB dict を組む (conflicts=0 を作るため)。"""
    schema = json.loads(VNS.SCHEMA_PATH.read_text(encoding="utf-8"))
    props = {}
    for name, spec in schema["properties"].items():
        t = spec["type"]
        entry = {"type": t}
        if t in ("select", "multi_select") and isinstance(spec.get("options"), list):
            entry[t] = {"options": [{"name": o} for o in spec["options"]]}
        props[name] = entry
    return {"properties": props, "title": [{"plain_text": "Hearing"}]}


def _call_main(monkeypatch, argv):
    """sys.argv を差し替えて main() を呼ぶ薄いヘルパ。"""
    monkeypatch.setattr(sys, "argv", ["verify_notion_schema.py", *argv])
    return VNS.main()


def test_main_requires_database_id(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _install_fakes(monkeypatch, db_id_value=None, get_database_impl=lambda *a, **k: {})
    rc = _call_main(monkeypatch, [])
    err = capsys.readouterr().err
    assert rc == 2
    assert "database_id is required" in err


def test_main_notion_config_failure_returns_2(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    # notion_config.get_db_id が例外を投げる → fail-closed return 2
    fake_cfg = types.ModuleType("notion_config")

    def _boom(key):
        raise RuntimeError("config broken")

    fake_cfg.get_db_id = _boom
    monkeypatch.setitem(sys.modules, "notion_config", fake_cfg)
    rc = _call_main(monkeypatch, [])
    err = capsys.readouterr().err
    assert rc == 2
    assert "notion_config failed" in err


def test_main_invalid_on_conflict_returns_2(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _install_fakes(monkeypatch, db_id_value="db-cfg", get_database_impl=lambda *a, **k: {})
    rc = _call_main(monkeypatch, ["--on-conflict", "bogus"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "invalid --on-conflict" in err


def test_main_arg_db_id_overrides_config(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_get_db(db_id, **opts):
        captured["db_id"] = db_id
        return _real_schema_db_matching()

    _install_fakes(monkeypatch, db_id_value="db-from-config", get_database_impl=fake_get_db)
    rc = _call_main(monkeypatch, ["--database-id", "db-from-arg"])
    assert rc == 0
    # --database-id が config より優先
    assert captured["db_id"] == "db-from-arg"
    # db-id-resolution.json に source=arg が記録される
    res = json.loads((tmp_path / "eval-log" / "db-id-resolution.json").read_text())
    assert res["source"] == "arg"
    assert res["database_id"] == "db-from-arg"


def test_main_uses_config_db_id_when_no_arg(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_get_db(db_id, **opts):
        captured["db_id"] = db_id
        return _real_schema_db_matching()

    _install_fakes(monkeypatch, db_id_value="db-cfg-99", get_database_impl=fake_get_db)
    rc = _call_main(monkeypatch, [])
    assert rc == 0
    assert captured["db_id"] == "db-cfg-99"
    res = json.loads((tmp_path / "eval-log" / "db-id-resolution.json").read_text())
    assert res["source"] == "notion_config"


def test_main_perfect_schema_zero_conflicts(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    _install_fakes(
        monkeypatch,
        db_id_value="db1",
        get_database_impl=lambda db_id, **k: _real_schema_db_matching(),
    )
    rc = _call_main(monkeypatch, [])
    out = capsys.readouterr().out
    assert rc == 0
    report = json.loads((tmp_path / "eval-log" / "notion-conflicts.json").read_text())
    assert report["summary"]["total"] == 0
    assert report["conflicts"] == []
    assert report["database_title"] == "Hearing"
    assert report["mode"] == "skip-warn"
    assert "checked_at" in report
    assert "wrote" in out and "mode=skip-warn" in out


def test_main_detects_conflicts_and_extras(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_get_db(db_id, **k):
        db = _real_schema_db_matching()
        # 1) ステータス を type_mismatch に
        db["properties"]["ステータス"]["type"] = "multi_select"
        # 2) 名前 (required title) を削除 → missing
        del db["properties"]["名前"]
        # 3) 余分プロパティ → extra
        db["properties"]["余分カラム"] = {"type": "rich_text"}
        return db

    _install_fakes(monkeypatch, db_id_value="db1", get_database_impl=fake_get_db)
    rc = _call_main(monkeypatch, [])
    assert rc == 0  # skip-warn は conflict があっても 0
    report = json.loads((tmp_path / "eval-log" / "notion-conflicts.json").read_text())
    kinds = {c["name"]: c["kind"] for c in report["conflicts"]}
    assert kinds["ステータス"] == "type_mismatch"
    assert kinds["名前"] == "missing"
    assert kinds["余分カラム"] == "extra"
    assert report["summary"]["by_kind"]["type_mismatch"] >= 1


def test_main_fail_stop_returns_1_on_blocking(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def fake_get_db(db_id, **k):
        db = _real_schema_db_matching()
        db["properties"]["ステータス"]["type"] = "multi_select"  # blocking type_mismatch
        return db

    _install_fakes(monkeypatch, db_id_value="db1", get_database_impl=fake_get_db)
    rc = _call_main(monkeypatch, ["--on-conflict", "fail-stop"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "fail-stop" in err
    assert "blocking conflicts" in err


def test_main_fail_stop_zero_when_only_non_blocking(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_get_db(db_id, **k):
        db = _real_schema_db_matching()
        # extra のみ (non-blocking) → fail-stop でも 0
        db["properties"]["余分"] = {"type": "rich_text"}
        return db

    _install_fakes(monkeypatch, db_id_value="db1", get_database_impl=fake_get_db)
    rc = _call_main(monkeypatch, ["--on-conflict", "fail-stop"])
    assert rc == 0
    report = json.loads((tmp_path / "eval-log" / "notion-conflicts.json").read_text())
    assert report["summary"]["by_kind"].get("extra", 0) >= 1


def test_main_custom_out_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "nested" / "custom-report.json"
    _install_fakes(
        monkeypatch,
        db_id_value="db1",
        get_database_impl=lambda db_id, **k: _real_schema_db_matching(),
    )
    rc = _call_main(monkeypatch, ["--out", str(out)])
    assert rc == 0
    assert out.exists()
    report = json.loads(out.read_text())
    assert report["database_id"] == "db1"


def test_main_http_401_returns_44(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def fake_get_db(db_id, **k):
        raise _FakeNotionHttpError("unauthorized", status=401, body={})

    _install_fakes(monkeypatch, db_id_value="db1", get_database_impl=fake_get_db)
    rc = _call_main(monkeypatch, [])
    err = capsys.readouterr().err
    assert rc == 44
    assert "verify_notion_schema" in err


def test_main_http_other_error_returns_1(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def fake_get_db(db_id, **k):
        raise _FakeNotionHttpError("server error", status=500, body={})

    _install_fakes(monkeypatch, db_id_value="db1", get_database_impl=fake_get_db)
    rc = _call_main(monkeypatch, [])
    err = capsys.readouterr().err
    assert rc == 1
    assert "verify_notion_schema" in err


def test_main_swallows_db_id_resolution_write_failure(monkeypatch, tmp_path):
    """eval-log が file として存在し mkdir/書込が失敗しても best-effort で握り潰し継続する。"""
    monkeypatch.chdir(tmp_path)
    # eval-log を *ファイル* として作る → Path('eval-log').mkdir() が FileExistsError を投げ
    #   db-id-resolution.json の書込ブロック (try/except Exception: pass) に入る。
    (tmp_path / "eval-log").write_text("i am a file, not a dir", encoding="utf-8")
    out = tmp_path / "report.json"  # 本体出力は別パスへ逃がして衝突回避
    _install_fakes(
        monkeypatch,
        db_id_value="db1",
        get_database_impl=lambda db_id, **k: _real_schema_db_matching(),
    )
    rc = _call_main(monkeypatch, ["--out", str(out)])
    # db-id-resolution.json の書込失敗は握り潰され、本体処理は完走する
    assert rc == 0
    assert out.exists()


def test_main_overwrite_mode_accepted(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _install_fakes(
        monkeypatch,
        db_id_value="db1",
        get_database_impl=lambda db_id, **k: _real_schema_db_matching(),
    )
    rc = _call_main(monkeypatch, ["--on-conflict", "overwrite"])
    assert rc == 0
    report = json.loads((tmp_path / "eval-log" / "notion-conflicts.json").read_text())
    assert report["mode"] == "overwrite"
