"""scripts/sync-notion-schema.py の genuine 機能テスト。

外部 I/O (Notion REST `curl` / Keychain / notion_config.require_or_skip) は
monkeypatch で完全遮断し、純関数 (schema_to_property / diff_props / load_schemas)
を実入力で呼び実出力を assert する。main() は notion_config を stub した上で
in-process 駆動し、SKIP / OK / DRIFT / 適用 / エラー終了 の各経路を検証する。
subprocess 経路は --help と 引数欠如 (mutually exclusive group required) の
returncode のみ検証 (実 Notion 通信は一切行わない)。
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sync-notion-schema.py"

SPEC = importlib.util.spec_from_file_location("sync_notion_schema_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- schema_to_property: 各 type 分岐を実入力で検証 ---------------------------

@pytest.mark.parametrize(
    "t",
    ["title", "rich_text", "people", "url", "email", "phone_number",
     "files", "checkbox", "date", "number", "created_time", "last_edited_time"],
)
def test_schema_to_property_simple_types(t):
    out = MOD.schema_to_property("X", {"type": t}, {})
    assert out == {t: {}}


def test_schema_to_property_select_with_options():
    opts = [{"name": "A", "color": "red"}, {"name": "B"}]
    out = MOD.schema_to_property("sel", {"type": "select", "options": opts}, {})
    assert out == {"select": {"options": opts}}


def test_schema_to_property_multi_select_default_empty_options():
    out = MOD.schema_to_property("ms", {"type": "multi_select"}, {})
    assert out == {"multi_select": {"options": []}}


def test_schema_to_property_relation_resolves_target_db_id():
    lookup = {"skill-list": "DB123"}
    out = MOD.schema_to_property(
        "rel", {"type": "relation", "target_db": "skill-list"}, lookup
    )
    assert out["relation"]["database_id"] == "DB123"
    assert out["relation"]["type"] == "dual_property"
    assert out["relation"]["dual_property"] == {}


def test_schema_to_property_rollup_function_default_count():
    spec = {
        "type": "rollup",
        "relation_property_name": "紐づくプラグイン",
        "rollup_property_name": "名前",
    }
    out = MOD.schema_to_property("ro", spec, {})
    assert out["rollup"]["function"] == "count"
    assert out["rollup"]["relation_property_name"] == "紐づくプラグイン"
    assert out["rollup"]["rollup_property_name"] == "名前"


def test_schema_to_property_rollup_explicit_function():
    spec = {
        "type": "rollup",
        "relation_property_name": "r",
        "rollup_property_name": "p",
        "function": "sum",
    }
    out = MOD.schema_to_property("ro", spec, {})
    assert out["rollup"]["function"] == "sum"


def test_schema_to_property_unsupported_raises():
    with pytest.raises(ValueError) as ei:
        MOD.schema_to_property("bad", {"type": "wormhole"}, {})
    assert "unsupported type" in str(ei.value)
    assert "wormhole" in str(ei.value)


# --- diff_props: 追加 / 型不一致 / 一致 / non-managed 無視 -------------------

def test_diff_props_missing_property_is_addition():
    remote = {}
    managed = {"名前": {"type": "title"}}
    out = MOD.diff_props(remote, managed, {})
    assert out == {"名前": {"title": {}}}


def test_diff_props_type_mismatch_is_addition():
    # remote では rich_text だが managed では title -> 差分として返る
    remote = {"名前": {"type": "rich_text"}}
    managed = {"名前": {"type": "title"}}
    out = MOD.diff_props(remote, managed, {})
    assert out == {"名前": {"title": {}}}


def test_diff_props_type_match_no_addition():
    remote = {"名前": {"type": "title"}}
    managed = {"名前": {"type": "title"}}
    assert MOD.diff_props(remote, managed, {}) == {}


def test_diff_props_ignores_non_managed_remote_props():
    # remote にだけ存在する (managed に無い) プロパティは無視される
    remote = {"既存17プロパティ": {"type": "rich_text"}, "名前": {"type": "title"}}
    managed = {"名前": {"type": "title"}}
    assert MOD.diff_props(remote, managed, {}) == {}


def test_diff_props_relation_addition_uses_lookup():
    remote = {}
    managed = {"紐づくプラグイン": {"type": "relation", "target_db": "skill-list"}}
    out = MOD.diff_props(remote, managed, {"skill-list": "DBxyz"})
    assert out["紐づくプラグイン"]["relation"]["database_id"] == "DBxyz"


# --- load_schemas: 実 SSOT ファイルを読む (repo 同梱) -------------------------

def test_load_schemas_reads_real_ssot_files():
    schemas = MOD.load_schemas()
    assert set(schemas.keys()) == {"hearing-sheet", "skill-list", "improvement-request"}
    # 各 schema は managed_properties を持ち、title type のプロパティを含む
    for key, sc in schemas.items():
        assert "managed_properties" in sc, key
        types = {p["type"] for p in sc["managed_properties"].values()}
        assert "title" in types, key


# --- curl: subprocess.check_output を stub し引数組み立てを検証 ----------------

def test_curl_get_builds_headers_and_parses_http_code(monkeypatch):
    captured = {}

    def fake_check_output(cmd):
        captured["cmd"] = cmd
        # -w が末尾に __HTTP__<code> を付与する挙動を再現
        return b'{"ok":true}\n__HTTP__200'

    monkeypatch.setattr(MOD.subprocess, "check_output", fake_check_output)
    code, payload = MOD.curl("GET", "https://api.notion.com/v1/databases/X", "tok-abc")
    assert code == 200
    assert payload == '{"ok":true}'
    cmd = captured["cmd"]
    assert cmd[0] == "curl"
    assert "GET" in cmd
    assert "Authorization: Bearer tok-abc" in cmd
    assert "Notion-Version: 2022-06-28" in cmd
    # body なし -> --data-binary は付かない
    assert not any(str(c).startswith("--data-binary") for c in cmd)


def test_curl_patch_with_body_writes_tempfile_and_cleans_up(monkeypatch, tmp_path):
    written = {}
    captured = {}
    unlinked = []

    def fake_check_output(cmd):
        captured["cmd"] = cmd
        # --data-binary @<path> から実ファイルを読んで中身を確認
        for c in cmd:
            if isinstance(c, str) and c.startswith("@"):
                written["body"] = Path(c[1:]).read_text()
        return b'{}\n__HTTP__400'

    monkeypatch.setattr(MOD.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(MOD.os, "unlink", lambda p: unlinked.append(p))

    code, payload = MOD.curl(
        "PATCH", "https://api.notion.com/v1/databases/X", "tok",
        {"properties": {"名前": {"title": {}}}},
    )
    assert code == 400
    assert json.loads(written["body"]) == {"properties": {"名前": {"title": {}}}}
    assert any(str(c).startswith("@") for c in captured["cmd"])
    # tempfile は unlink される
    assert len(unlinked) == 1


# --- main(): notion_config / curl を stub し各経路を in-process 駆動 ----------

def _stub_config(monkeypatch, db_ids):
    cfg = {"__path__": "/fake/.notion-config.json"}
    monkeypatch.setattr(MOD.notion_config, "require_or_skip", lambda: (cfg, "tok"))
    monkeypatch.setattr(MOD.notion_config, "get_db_id", lambda key: db_ids.get(key))


def _set_argv(monkeypatch, *flags):
    monkeypatch.setattr(sys, "argv", ["sync-notion-schema.py", *flags])


def test_main_skip_when_no_config(monkeypatch, capsys):
    # require_or_skip が (None, None) を返す (allow_skip 相当) -> return 0
    monkeypatch.setattr(MOD.notion_config, "require_or_skip", lambda: (None, None))
    _set_argv(monkeypatch, "--check")
    assert MOD.main() == 0


def test_main_skip_when_no_databases_configured(monkeypatch, capsys):
    _stub_config(monkeypatch, {})  # 全 key で None
    _set_argv(monkeypatch, "--check")
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "[SKIP]" in out
    assert "no databases configured" in out


def test_main_check_no_drift_returns_none(monkeypatch, capsys):
    # 全 DB 設定済み・remote が managed と完全一致 -> drift なし
    schemas = MOD.load_schemas()
    _stub_config(monkeypatch, {k: f"DB_{k}" for k in MOD.FILES})

    def fake_curl(method, url, token, body=None):
        # url から key を逆引きして、その managed をそのまま remote として返す
        for key in MOD.FILES:
            if f"DB_{key}" in url:
                props = {
                    n: {"type": s["type"]}
                    for n, s in schemas[key]["managed_properties"].items()
                }
                return 200, json.dumps({"properties": props})
        raise AssertionError("unexpected url")

    monkeypatch.setattr(MOD, "curl", fake_curl)
    _set_argv(monkeypatch, "--check")
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc is None  # drift なし -> 明示 return せず None
    assert "[OK]" in out
    assert "no drift" in out


def test_main_check_with_drift_exits_1(monkeypatch, capsys):
    _stub_config(monkeypatch, {k: f"DB_{k}" for k in MOD.FILES})

    def fake_curl(method, url, token, body=None):
        # remote は空 -> 全 managed が drift (additions)
        return 200, json.dumps({"properties": {}})

    monkeypatch.setattr(MOD, "curl", fake_curl)
    _set_argv(monkeypatch, "--check")
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 1
    out = capsys.readouterr().out
    assert "[DRIFT]" in out


def test_main_apply_patches_drift(monkeypatch, capsys):
    _stub_config(monkeypatch, {k: f"DB_{k}" for k in MOD.FILES})
    patched = []

    def fake_curl(method, url, token, body=None):
        if method == "GET":
            return 200, json.dumps({"properties": {}})  # 全 drift
        if method == "PATCH":
            patched.append(body)
            return 200, "{}"
        raise AssertionError(method)

    monkeypatch.setattr(MOD, "curl", fake_curl)
    _set_argv(monkeypatch, "--apply")
    rc = MOD.main()
    out = capsys.readouterr().out
    # apply は drift があっても sys.exit(1) しない (args.check でないため)
    assert rc is None
    assert "[APPLIED]" in out
    # PATCH body は {"properties": {...}} の形
    assert all("properties" in b for b in patched)
    assert len(patched) == len(MOD.FILES)


def test_main_get_error_exits_2(monkeypatch, capsys):
    _stub_config(monkeypatch, {k: f"DB_{k}" for k in MOD.FILES})

    def fake_curl(method, url, token, body=None):
        return 404, '{"message":"not found"}'

    monkeypatch.setattr(MOD, "curl", fake_curl)
    _set_argv(monkeypatch, "--check")
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 2
    err = capsys.readouterr().out
    assert "[ERR] GET" in err


def test_main_apply_patch_error_exits_2(monkeypatch, capsys):
    _stub_config(monkeypatch, {k: f"DB_{k}" for k in MOD.FILES})

    def fake_curl(method, url, token, body=None):
        if method == "GET":
            return 200, json.dumps({"properties": {}})
        return 422, '{"message":"bad property"}'

    monkeypatch.setattr(MOD, "curl", fake_curl)
    _set_argv(monkeypatch, "--apply")
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 2
    out = capsys.readouterr().out
    assert "[ERR] apply" in out


def test_main_skips_db_missing_in_lookup(monkeypatch, capsys):
    # hearing-sheet だけ設定、他は None -> 設定済み DB のみ GET される。
    # 実 schema は cross-DB relation を持つため、対象 DB を relation 無しの
    # 単純 schema に差し替えて「未設定 DB を lookup/GET から除外する」挙動のみ分離検証する。
    _stub_config(monkeypatch, {"hearing-sheet": "DB_hearing-sheet"})
    monkeypatch.setattr(
        MOD, "load_schemas",
        lambda: {"hearing-sheet": {"managed_properties": {"名前": {"type": "title"}}}},
    )
    seen_urls = []

    def fake_curl(method, url, token, body=None):
        seen_urls.append(url)
        return 200, json.dumps({"properties": {}})

    monkeypatch.setattr(MOD, "curl", fake_curl)
    _set_argv(monkeypatch, "--check")
    with pytest.raises(SystemExit):  # hearing-sheet に drift -> exit 1
        MOD.main()
    out = capsys.readouterr().out
    # GET は設定済みの 1 DB のみ (未設定の skill-list / improvement-request は SKIP)
    assert len(seen_urls) == 1
    assert "DB_hearing-sheet" in seen_urls[0]
    assert "[SKIP] skill-list" in out
    assert "[SKIP] improvement-request" in out


def test_main_schema_loop_skips_unconfigured_key(monkeypatch, capsys):
    # schemas は 3 key を返すが db_id_lookup は 1 key のみ ->
    # schemas ループ内で未設定 key が `continue` でスキップされる経路を覆う。
    _stub_config(monkeypatch, {"skill-list": "DB_skill-list"})
    monkeypatch.setattr(
        MOD, "load_schemas",
        lambda: {k: {"managed_properties": {"名前": {"type": "title"}}}
                 for k in MOD.FILES},
    )
    gets = []

    def fake_curl(method, url, token, body=None):
        gets.append(url)
        # remote が managed と一致 -> drift なし
        return 200, json.dumps({"properties": {"名前": {"type": "title"}}})

    monkeypatch.setattr(MOD, "curl", fake_curl)
    _set_argv(monkeypatch, "--check")
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc is None  # drift なし
    # GET は設定済み skill-list のみ。未設定 2 key は schemas ループ内で continue
    assert len(gets) == 1
    assert "DB_skill-list" in gets[0]
    assert "[OK] skill-list" in out


# --- subprocess: 引数バリデーションのみ (実 Notion 通信なし) -----------------

def test_subprocess_help_exits_0():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "--check" in proc.stdout
    assert "--apply" in proc.stdout


def test_subprocess_no_flag_errors():
    # mutually exclusive group required -> argparse が exit 2
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "one of the arguments" in proc.stderr or "required" in proc.stderr
