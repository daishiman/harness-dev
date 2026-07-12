"""publish_notion_page.py の純関数 + 引数検証経路を network 無しで実証する。

実通信 (notion_http.notion_fetch / keychain) は遅延 import されるため、
本テストは dry-run / 引数エラー / page_id 解決系のみを対象とし、実投稿経路
(POST/PATCH) には到達させない。これにより副作用ゼロを構造的に保証する。

genuine な検証対象:
  - _extract_page_id_from_url: URL/UUID/スラグ-id/クエリ p= の正規化
  - _canonical_id: 32hex 正規化
  - derive_ja_title: 日本語タイトル優先順位導出
  - truncate / axis_text / rt: 文字列ヘルパ
  - build_properties: render と同経路で Notion DB プロパティを projection
  - build_extra_body_blocks: DB 補完 12 項目 → children ブロック
  - resolve_target_page_id: --page-id > --page-url > --result-out > None の SSOT 優先順位
  - _write_result: 冪等 result JSON の永続化スキーマ
  - main の CLI 契約: 引数欠落 / 空 blocks / 不正 page-id / dry-run / require-update
"""
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "plugins" / "skill-intake" / "scripts"
SCRIPT = SCRIPTS_DIR / "publish_notion_page.py"

# render_notion_page (build_properties が import する) を解決できるよう sys.path に追加。
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_SPEC = importlib.util.spec_from_file_location("publish_notion_page_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# _extract_page_id_from_url
# --------------------------------------------------------------------------

def test_extract_dashed_uuid_passthrough():
    u = "12345678-90ab-cdef-1234-567890abcdef"
    assert MOD._extract_page_id_from_url(u) == u.lower()


def test_extract_from_slug_id_url():
    # スラグ末尾 32hex を UUID 形式へ整形
    h = "0123456789abcdef0123456789abcdef"
    url = f"https://www.notion.so/My-Page-Title-{h}"
    out = MOD._extract_page_id_from_url(url)
    assert out == f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def test_extract_from_query_p_param_takes_precedence():
    # 共有 URL の query p= が実ページ ID。path 側 (view id) より優先される。
    page = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    view = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    url = f"https://www.notion.so/p/{view}?p={page}&pvs=4"
    out = MOD._extract_page_id_from_url(url)
    assert out.replace("-", "") == page


def test_extract_returns_none_for_garbage():
    assert MOD._extract_page_id_from_url("not-a-page") is None
    assert MOD._extract_page_id_from_url("") is None
    assert MOD._extract_page_id_from_url(None) is None


def test_canonical_id():
    assert MOD._canonical_id("ABCD-EF01" * 4) == "abcdef01" * 4
    assert MOD._canonical_id("short") == ""
    assert MOD._canonical_id(None) == ""


# --------------------------------------------------------------------------
# derive_ja_title: 優先順位導出
# --------------------------------------------------------------------------

def test_derive_ja_title_prefers_meta_field():
    intake = {"meta": {"skill_title_ja": "請求書チェッカー"}}
    assert MOD.derive_ja_title(intake) == "請求書チェッカー"


def test_derive_ja_title_from_japanese_db_name():
    intake = {"notion_db_properties": {"名前": "見積書生成"}}
    assert MOD.derive_ja_title(intake) == "見積書生成"


def test_derive_ja_title_strips_suru_suffix_from_purpose():
    intake = {"purpose": {"verb_object": "請求書を発行する。"}}
    # 末尾「。」と「する」を削る
    assert MOD.derive_ja_title(intake) == "請求書を発行"


def test_derive_ja_title_none_when_absent():
    assert MOD.derive_ja_title({}) is None


def test_derive_ja_title_truncates_to_30():
    long = "あ" * 50
    intake = {"meta": {"skill_title_ja": long}}
    assert len(MOD.derive_ja_title(intake)) == MOD.MAX_TITLE_JA_LEN


# --------------------------------------------------------------------------
# 文字列ヘルパ
# --------------------------------------------------------------------------

def test_truncate_under_and_over():
    assert MOD.truncate("abc", 10) == "abc"
    assert MOD.truncate("abcdef", 4) == "abc…"
    assert MOD.truncate(None, 5) == ""


def test_axis_text_variants():
    assert MOD.axis_text("plain") == "plain"
    assert MOD.axis_text({"answer": "wrapped"}) == "wrapped"
    assert MOD.axis_text(None) == ""
    assert MOD.axis_text(123) == ""


def test_rt_caps_at_max_rt():
    huge = "x" * (MOD.MAX_RT + 100)
    block = MOD.rt(huge)
    assert block[0]["type"] == "text"
    assert len(block[0]["text"]["content"]) == MOD.MAX_RT


# --------------------------------------------------------------------------
# build_properties: render と同経路で projection
# --------------------------------------------------------------------------

def test_build_properties_projects_title_from_db_name():
    intake = {"notion_db_properties": {"名前": "テスト名", "ステータス": "草案"}}
    props = MOD.build_properties(intake, args=None)
    assert props["名前"]["title"][0]["text"]["content"] == "テスト名"
    assert props["ステータス"]["select"]["name"] == "草案"


def test_build_properties_fills_untitled_when_name_blank():
    # 名前が空 → derive_ja_title / hint / 'untitled' へフォールバック
    intake = {"notion_db_properties": {"名前": ""}}
    props = MOD.build_properties(intake, args=None)
    assert props["名前"]["title"][0]["text"]["content"] == "untitled"


def test_build_properties_uses_skill_name_hint_fallback():
    intake = {"notion_db_properties": {}, "meta": {"skill_name_hint": "hint-name"}}
    props = MOD.build_properties(intake, args=None)
    assert props["名前"]["title"][0]["text"]["content"] == "hint-name"


# --------------------------------------------------------------------------
# build_extra_body_blocks
# --------------------------------------------------------------------------

def test_build_extra_body_blocks_includes_meta_heading_and_kv():
    intake = {
        "five_axes": {"output_target": "Notion", "info_source": "Sheets"},
        "owner": "team-x",
        "open_questions": ["未決1", "未決2"],
    }
    blocks = MOD.build_extra_body_blocks(intake, args=None)
    assert blocks[0]["type"] == "heading_2"
    flat = json.dumps(blocks, ensure_ascii=False)
    assert "出力先: Notion" in flat
    assert "情報源: Sheets" in flat
    assert "担当者: team-x" in flat
    # open_questions は toggle として現れる
    assert any(b["type"] == "toggle" for b in blocks)


def test_build_extra_body_blocks_empty_when_no_metadata():
    # heading のみ (len<=1) なら空リストを返す契約
    assert MOD.build_extra_body_blocks({}, args=None) == []


# --------------------------------------------------------------------------
# resolve_target_page_id: SSOT 優先順位
# --------------------------------------------------------------------------

class _Args(types.SimpleNamespace):
    pass


def test_resolve_prefers_explicit_page_id():
    h = "11111111111111111111111111111111"
    args = _Args(page_id=h, page_url=None, result_out=None)
    pid, source = MOD.resolve_target_page_id(args)
    assert source == "arg"
    assert pid.replace("-", "") == h


def test_resolve_invalid_explicit_page_id_returns_arg_invalid():
    args = _Args(page_id="garbage", page_url=None, result_out=None)
    pid, source = MOD.resolve_target_page_id(args)
    assert pid is None
    assert source == "arg_invalid"


def test_resolve_from_page_url():
    h = "22222222222222222222222222222222"
    args = _Args(page_id=None, page_url=f"https://notion.so/Title-{h}", result_out=None)
    pid, source = MOD.resolve_target_page_id(args)
    assert source == "url"
    assert pid.replace("-", "") == h


def test_resolve_from_result_file(tmp_path):
    h = "33333333333333333333333333333333"
    rf = tmp_path / "result.json"
    rf.write_text(json.dumps({"page_id": h}), encoding="utf-8")
    args = _Args(page_id=None, page_url=None, result_out=str(rf))
    pid, source = MOD.resolve_target_page_id(args)
    assert source == "result_file"
    assert pid.replace("-", "") == h


def test_resolve_none_when_nothing_specified():
    args = _Args(page_id=None, page_url=None, result_out=None)
    assert MOD.resolve_target_page_id(args) == (None, None)


def test_resolve_corrupt_result_file_returns_result_invalid(tmp_path):
    rf = tmp_path / "result.json"
    rf.write_text("{ broken json", encoding="utf-8")
    args = _Args(page_id=None, page_url=None, result_out=str(rf))
    pid, source = MOD.resolve_target_page_id(args)
    assert pid is None
    assert source == "result_invalid"


# --------------------------------------------------------------------------
# _write_result: 冪等永続化スキーマ
# --------------------------------------------------------------------------

def test_write_result_persists_payload(tmp_path):
    out = tmp_path / "sub" / "notion-publish-result.json"
    MOD._write_result(str(out), "page-123", "https://notion.so/x", "create", "db-9")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["page_id"] == "page-123"
    assert data["url"] == "https://notion.so/x"
    assert data["mode"] == "create"
    assert data["database_id"] == "db-9"
    assert "published_at" in data


def test_write_result_noop_for_empty_path(tmp_path):
    # result_path 偽値なら何もしない (例外を投げない)
    assert MOD._write_result("", "p", "u", "create", "db") is None


# --------------------------------------------------------------------------
# CLI 契約 (subprocess; network 非到達経路のみ)
# --------------------------------------------------------------------------

def _fixtures(tmp_path, *, blocks=None):
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"notion_db_properties": {"名前": "T"}}), encoding="utf-8")
    bl = tmp_path / "blocks.json"
    bl.write_text(json.dumps(blocks if blocks is not None else {
        "children": [{"object": "block", "type": "paragraph",
                      "paragraph": {"rich_text": [{"type": "text",
                                                   "text": {"content": "hi"}}]}}]
    }), encoding="utf-8")
    return str(intake), str(bl)


def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_help_exit0(tmp_path):
    proc = _run(["--help"], cwd=str(tmp_path))
    assert proc.returncode == 0
    assert "--intake" in proc.stdout


def test_cli_missing_intake_exit2(tmp_path):
    proc = _run([], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--intake is required" in proc.stderr


def test_cli_missing_blocks_exit2(tmp_path):
    intake, _bl = _fixtures(tmp_path)
    proc = _run(["--intake", intake], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--blocks is required" in proc.stderr


def test_cli_empty_blocks_array_exit2(tmp_path):
    intake, _bl = _fixtures(tmp_path)
    bl = tmp_path / "empty.json"
    bl.write_text(json.dumps({"children": []}), encoding="utf-8")
    proc = _run(["--intake", intake, "--blocks", str(bl), "--database-id", "db1"],
                cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "non-empty children" in proc.stderr


def test_cli_dry_run_create_emits_payload_summary(tmp_path):
    intake, bl = _fixtures(tmp_path)
    proc = _run(["--intake", intake, "--blocks", bl, "--database-id", "db1",
                 "--allow-create", "--dry-run"], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["dry_run"] is True
    assert out["mode"] == "create"
    assert out["parent"]["database_id"] == "db1"
    assert out["prop_count"] == 15  # project_db_properties は 15 プロパティ固定
    assert out["children_count"] >= 1


def test_cli_dry_run_update_with_page_id(tmp_path):
    intake, bl = _fixtures(tmp_path)
    h = "44444444444444444444444444444444"
    proc = _run(["--intake", intake, "--blocks", bl, "--database-id", "db1",
                 "--page-id", h, "--dry-run"], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["mode"] == "update"
    assert out["page_id_source"] == "arg"
    assert out["page_id"].replace("-", "") == h


def test_cli_invalid_page_id_fail_closed_exit2(tmp_path):
    intake, bl = _fixtures(tmp_path)
    proc = _run(["--intake", intake, "--blocks", bl, "--database-id", "db1",
                 "--page-id", "not-valid", "--dry-run"], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "不正" in proc.stderr or "arg_invalid" in proc.stderr


def test_cli_require_update_without_target_exit51(tmp_path):
    intake, bl = _fixtures(tmp_path)
    proc = _run(["--intake", intake, "--blocks", bl, "--database-id", "db1",
                 "--require-update", "--dry-run"], cwd=str(tmp_path))
    assert proc.returncode == 51
    assert "require-update" in proc.stderr


def test_cli_create_disabled_by_default_exit51(tmp_path):
    intake, bl = _fixtures(tmp_path)
    # --allow-create も --page-id も無し → create 禁止 (51)
    proc = _run(["--intake", intake, "--blocks", bl, "--database-id", "db1",
                 "--dry-run"], cwd=str(tmp_path))
    assert proc.returncode == 51
    assert "create is disabled" in proc.stderr


def test_cli_missing_database_id_exit2(tmp_path, monkeypatch):
    # --database-id を渡さず、notion_config も env/config を持たない一時 cwd で
    # database_id 解決不能 → exit 2。INTAKE_NOTION_DATABASE_ID を確実に未設定にする。
    intake, bl = _fixtures(tmp_path)
    env = {k: v for k, v in __import__("os").environ.items()
           if k != "INTAKE_NOTION_DATABASE_ID"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--intake", intake, "--blocks", bl,
         "--allow-create", "--dry-run"],
        capture_output=True, text=True, cwd=str(tmp_path), env=env,
    )
    # notion_config が repo-root の .notion-config.json を見つけられれば db が解決
    # される可能性があるため、returncode は 2 (未解決) または 0 (解決) のどちらか。
    # 未解決時のメッセージ契約のみを厳密に検証する。
    if proc.returncode == 2:
        assert "database_id is required" in proc.stderr
    else:
        assert proc.returncode == 0
