"""Genuine functional tests for plugins/skill-intake/scripts/publish_notion_page.py.

カバレッジ方針:
- 純関数 (rt / axis_text / truncate / derive_ja_title / build_extra_body_blocks /
  _extract_page_id_from_url / _canonical_id / resolve_target_page_id /
  _read_existing_page_id / _write_result / _list_child_ids / _archive_children /
  build_properties) を **in-process** で実値検証する。
- `main()` の引数検証・DB ID 解決・page_id 解決・dry-run / create / update / revise の
  各 fail-closed 分岐・Notion API 呼び出し順を、`notion_config` / `notion_http` /
  `render_notion_page` を `sys.modules` へ stub 注入して network/keychain を一切叩かずに駆動。
- すべての I/O は `monkeypatch.chdir(tmp_path)` + tmp_path 配下に限定し repo を汚さない。

ファイル名は他ディレクトリの publish 系 (intake_publish_pipeline) と衝突しないよう
`_r4` を付して新規作成 (pytest basename 衝突回避)。
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "publish_notion_page.py"

_SPEC = importlib.util.spec_from_file_location("publish_notion_page_s4", SCRIPT)
PUB = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(PUB)


# ===================== 単純 rich-text / 補助 =====================

def test_rt_wraps_and_truncates():
    out = PUB.rt("hi")
    assert out == [{"type": "text", "text": {"content": "hi"}}]
    long = "x" * (PUB.MAX_RT + 50)
    assert len(PUB.rt(long)[0]["text"]["content"]) == PUB.MAX_RT


def test_rt_none_and_number():
    assert PUB.rt(None)[0]["text"]["content"] == ""
    assert PUB.rt(123)[0]["text"]["content"] == "123"


def test_axis_text_variants():
    assert PUB.axis_text(None) == ""
    assert PUB.axis_text("plain") == "plain"
    assert PUB.axis_text({"answer": "from-dict"}) == "from-dict"
    assert PUB.axis_text({"answer": 5}) == ""   # answer が str でない
    assert PUB.axis_text(42) == ""              # dict でも str でもない


def test_truncate():
    assert PUB.truncate("abc", 5) == "abc"
    assert PUB.truncate("abcdef", 3) == "ab…"
    assert PUB.truncate(None, 4) == ""
    # n=0 のとき max(0, n-1)=0 → 空 + 省略記号
    assert PUB.truncate("abcdef", 0) == "…"


# ===================== derive_ja_title 優先順位 =====================

def test_derive_ja_title_meta_first():
    intake = {"meta": {"skill_title_ja": "メタ正式タイトル"}}
    assert PUB.derive_ja_title(intake) == "メタ正式タイトル"


def test_derive_ja_title_meta_truncated():
    long = "あ" * (PUB.MAX_TITLE_JA_LEN + 10)
    intake = {"meta": {"skill_title_ja": long}}
    assert len(PUB.derive_ja_title(intake)) == PUB.MAX_TITLE_JA_LEN


def test_derive_ja_title_from_ndp_japanese():
    # meta 無し → notion_db_properties.名前 が日本語(非ASCII)なら採用
    intake = {"notion_db_properties": {"名前": "日本語名"}}
    assert PUB.derive_ja_title(intake) == "日本語名"


def test_derive_ja_title_ndp_ascii_skipped_falls_to_toplevel():
    # 名前が ASCII のみ → スキップ → top-level skill_title_ja
    intake = {"notion_db_properties": {"名前": "ascii-only"},
              "skill_title_ja": "トップレベル"}
    assert PUB.derive_ja_title(intake) == "トップレベル"


def test_derive_ja_title_from_purpose_strips_suffix():
    intake = {"purpose": {"verb_object": "請求書を発行する。"}}
    # 末尾「。」と「する」を削る
    assert PUB.derive_ja_title(intake) == "請求書を発行"


def test_derive_ja_title_from_true_purpose_suffix_shitai():
    intake = {"purpose": {"true_purpose": "顧客を管理したい"}}
    assert PUB.derive_ja_title(intake) == "顧客を管理"


def test_derive_ja_title_none_when_empty():
    assert PUB.derive_ja_title({}) is None
    # purpose があっても空文字なら None
    assert PUB.derive_ja_title({"purpose": {"verb_object": "   "}}) is None


# ===================== build_properties (render と同経路) =====================

def _install_fake_render(monkeypatch, capture=None):
    """render_notion_page を stub し project_db_properties を差し替える。"""
    fake = types.ModuleType("render_notion_page")

    def project_db_properties(ctx, db_schema=None):
        if capture is not None:
            capture["ctx"] = ctx
            capture["db_schema"] = db_schema
        return {"名前": {"title": [{"text": {"content": ctx.get("notion_db_properties", {}).get("名前", "")}}]}}

    fake.project_db_properties = project_db_properties
    monkeypatch.setitem(sys.modules, "render_notion_page", fake)
    return fake


def test_build_properties_fills_name_from_derive(monkeypatch):
    cap = {}
    _install_fake_render(monkeypatch, cap)
    intake = {"meta": {"skill_title_ja": "導出名"}}
    props = PUB.build_properties(intake, None)
    # 空の名前は derive_ja_title で補完されてから render へ渡る
    assert cap["ctx"]["notion_db_properties"]["名前"] == "導出名"
    assert props["名前"]["title"][0]["text"]["content"] == "導出名"


def test_build_properties_name_already_set_preserved(monkeypatch):
    cap = {}
    _install_fake_render(monkeypatch, cap)
    intake = {"notion_db_properties": {"名前": "既設名"}}
    PUB.build_properties(intake, None)
    assert cap["ctx"]["notion_db_properties"]["名前"] == "既設名"


def test_build_properties_untitled_fallback(monkeypatch):
    cap = {}
    _install_fake_render(monkeypatch, cap)
    # 名前空・導出不能・hint 無し → 'untitled'
    PUB.build_properties({}, None)
    assert cap["ctx"]["notion_db_properties"]["名前"] == "untitled"


def test_build_properties_hint_fallback(monkeypatch):
    cap = {}
    _install_fake_render(monkeypatch, cap)
    intake = {"skill_name_hint": "hint-name"}
    PUB.build_properties(intake, None)
    assert cap["ctx"]["notion_db_properties"]["名前"] == "hint-name"


# ===================== build_extra_body_blocks =====================

def test_extra_blocks_empty_when_no_axes():
    # axes も付加項目も無ければ heading だけ → [] を返す
    assert PUB.build_extra_body_blocks({}, None) == []


def test_extra_blocks_collects_axes_and_toggles():
    intake = {
        "five_axes": {
            "output_target": "Notion",
            "info_source": {"answer": "Slack"},
            "share_target": "team",
        },
        "viz_count": 3,
        "value_score": 88,
        "owner": "manju",
        "updated_at": "2026-06-24",
        "user_profile": {"role": "PM"},
        "open_questions": ["q1", "q2"],
        "integrations": ["notion", "slack"],
    }
    blocks = PUB.build_extra_body_blocks(intake, None)
    types_ = [b["type"] for b in blocks]
    assert types_[0] == "heading_2"
    # paragraph で軸が入っている
    para_texts = [b["paragraph"]["rich_text"][0]["text"]["content"]
                 for b in blocks if b["type"] == "paragraph"]
    assert any("出力先: Notion" in t for t in para_texts)
    assert any("情報源: Slack" in t for t in para_texts)
    assert any("図解枚数: 3" in t for t in para_texts)
    assert any("価値実現スコア: 88" in t for t in para_texts)
    assert any("担当者: manju" in t for t in para_texts)
    # toggle が3つ (profile / open_questions / integrations)
    toggles = [b for b in blocks if b["type"] == "toggle"]
    assert len(toggles) == 3


def test_extra_blocks_bool_viz_count_excluded():
    # viz_count が bool のときは数値扱いしない (isinstance bool ガード)
    intake = {"five_axes": {"output_target": "X"}, "viz_count": True}
    blocks = PUB.build_extra_body_blocks(intake, None)
    para = [b["paragraph"]["rich_text"][0]["text"]["content"]
            for b in blocks if b["type"] == "paragraph"]
    assert not any("図解枚数" in t for t in para)


def test_extra_blocks_output_destination_alias():
    # output_target 不在時 output_destination を使う
    intake = {"five_axes": {"output_destination": "Drive"}}
    blocks = PUB.build_extra_body_blocks(intake, None)
    para = [b["paragraph"]["rich_text"][0]["text"]["content"]
            for b in blocks if b["type"] == "paragraph"]
    assert any("出力先: Drive" in t for t in para)


# ===================== _extract_page_id_from_url =====================

DASHED = "12345678-1234-1234-1234-123456789abc"
COMPACT = "12345678123412341234123456789abc"


def test_extract_none_and_empty():
    assert PUB._extract_page_id_from_url(None) is None
    assert PUB._extract_page_id_from_url("") is None


def test_extract_query_p_param():
    url = f"https://www.notion.so/p/view123?p={COMPACT}&pm=c"
    assert PUB._extract_page_id_from_url(url) == DASHED


def test_extract_query_page_id_param():
    url = f"https://x?page_id={DASHED}"
    assert PUB._extract_page_id_from_url(url) == DASHED


def test_extract_path_dashed_uuid():
    url = f"https://www.notion.so/Some-Title-{DASHED}"
    assert PUB._extract_page_id_from_url(url) == DASHED


def test_extract_slug_compact_token():
    url = f"https://www.notion.so/My-Page-{COMPACT}"
    assert PUB._extract_page_id_from_url(url) == DASHED


def test_extract_invalid_returns_none():
    assert PUB._extract_page_id_from_url("https://www.notion.so/just-a-slug") is None
    # 31 hex (短い) は不採用
    assert PUB._extract_page_id_from_url("https://x/" + "a" * 31) is None


def test_extract_bare_compact_id():
    # path セグメントとして compact 32hex を渡す
    assert PUB._extract_page_id_from_url(COMPACT) == DASHED


# ===================== _canonical_id =====================

def test_canonical_id_dashed_and_compact_equal():
    assert PUB._canonical_id(DASHED) == PUB._canonical_id(COMPACT) == COMPACT


def test_canonical_id_invalid_and_none():
    assert PUB._canonical_id("zzz") == ""
    assert PUB._canonical_id(None) == ""


# ===================== _read_existing_page_id =====================

def test_read_existing_page_id_none_path():
    assert PUB._read_existing_page_id(None) is None


def test_read_existing_page_id_missing_file(tmp_path):
    assert PUB._read_existing_page_id(str(tmp_path / "nope.json")) is None


def test_read_existing_page_id_from_page_id_field(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"page_id": DASHED}), encoding="utf-8")
    assert PUB._read_existing_page_id(str(p)) == DASHED


def test_read_existing_page_id_from_id_field(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"id": COMPACT}), encoding="utf-8")
    assert PUB._read_existing_page_id(str(p)) == DASHED


def test_read_existing_page_id_empty_returns_none(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"other": "x"}), encoding="utf-8")
    assert PUB._read_existing_page_id(str(p)) is None


def test_read_existing_page_id_broken_raises(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        PUB._read_existing_page_id(str(p))


# ===================== resolve_target_page_id =====================

class _Args:
    def __init__(self, **kw):
        self.page_id = kw.get("page_id")
        self.page_url = kw.get("page_url")
        self.result_out = kw.get("result_out")


def test_resolve_explicit_page_id():
    pid, src = PUB.resolve_target_page_id(_Args(page_id=DASHED))
    assert pid == DASHED and src == "arg"


def test_resolve_explicit_page_id_invalid():
    pid, src = PUB.resolve_target_page_id(_Args(page_id="garbage"))
    assert pid is None and src == "arg_invalid"


def test_resolve_page_url():
    url = f"https://www.notion.so/T-{COMPACT}"
    pid, src = PUB.resolve_target_page_id(_Args(page_url=url))
    assert pid == DASHED and src == "url"


def test_resolve_page_url_invalid():
    pid, src = PUB.resolve_target_page_id(_Args(page_url="https://x/slug-only"))
    assert pid is None and src == "url_invalid"


def test_resolve_from_result_file(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"page_id": DASHED}), encoding="utf-8")
    pid, src = PUB.resolve_target_page_id(_Args(result_out=str(p)))
    assert pid == DASHED and src == "result_file"


def test_resolve_result_invalid(tmp_path):
    p = tmp_path / "r.json"
    p.write_text("{broken", encoding="utf-8")
    pid, src = PUB.resolve_target_page_id(_Args(result_out=str(p)))
    assert pid is None and src == "result_invalid"


def test_resolve_none_when_nothing():
    pid, src = PUB.resolve_target_page_id(_Args())
    assert pid is None and src is None


# ===================== _write_result =====================

def test_write_result_none_path_noop(tmp_path):
    # result_path が None なら何もしない (例外なし)
    PUB._write_result(None, "pid", "url", "create", "db")


def test_write_result_payload(tmp_path):
    p = tmp_path / "sub" / "result.json"
    PUB._write_result(str(p), "pid-1", "https://u", "update", "db-1")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["page_id"] == "pid-1"
    assert d["url"] == "https://u"
    assert d["database_id"] == "db-1"
    assert d["mode"] == "update"
    assert "published_at" in d


# ===================== _list_child_ids / _archive_children =====================

def test_list_child_ids_paginates():
    pages = [
        {"results": [{"id": "a"}, {"id": "b"}], "has_more": True, "next_cursor": "c1"},
        {"results": [{"id": "c"}, {"no_id": 1}], "has_more": False},
    ]
    calls = []

    def fake_fetch(path, method="GET", body=None):
        calls.append((path, method))
        return pages.pop(0)

    ids = PUB._list_child_ids(fake_fetch, "PID")
    assert ids == ["a", "b", "c"]
    # 2 ページ目で start_cursor が乗っている
    assert "start_cursor=c1" in calls[1][0]
    assert calls[0][0].startswith("/blocks/PID/children?page_size=100")


def test_archive_children_deletes_each():
    deleted = []
    PUB._archive_children(lambda p, method=None: deleted.append((p, method)), ["x", "y"])
    assert deleted == [("/blocks/x", "DELETE"), ("/blocks/y", "DELETE")]


# ===================== main() : 引数検証 / fail-closed =====================

def _set_argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["publish_notion_page.py", *args])


def _write_json(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _valid_blocks(tmp_path, name="blocks.json"):
    return _write_json(tmp_path, name, {"children": [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}]})


def _valid_intake(tmp_path, name="intake.json"):
    return _write_json(tmp_path, name, {"notion_db_properties": {"名前": "T"}})


def _install_fakes(monkeypatch, *, db_id="db-default", fetch=None, http_error=None):
    """notion_config / notion_http / render_notion_page を一括 stub。"""
    # render
    _install_fake_render(monkeypatch)
    # notion_config
    nc = types.ModuleType("notion_config")
    nc.get_db_id = lambda key: db_id
    monkeypatch.setitem(sys.modules, "notion_config", nc)
    # notion_http
    nh = types.ModuleType("notion_http")

    class NotionHttpError(Exception):
        def __init__(self, message, status=None, body=None):
            super().__init__(message)
            self.status = status
            self.body = body

    nh.NotionHttpError = NotionHttpError
    nh.notion_fetch = fetch if fetch is not None else (lambda *a, **k: {})
    monkeypatch.setitem(sys.modules, "notion_http", nh)
    return nh


def test_main_intake_required(monkeypatch, capsys):
    _set_argv(monkeypatch)
    assert PUB.main() == 2
    assert "--intake is required" in capsys.readouterr().err


def test_main_blocks_required(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    _set_argv(monkeypatch, "--intake", intake)
    assert PUB.main() == 2
    assert "--blocks is required" in capsys.readouterr().err


def test_main_blocks_read_error(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", str(tmp_path / "nope.json"))
    assert PUB.main() == 2
    assert "--blocks read error" in capsys.readouterr().err


def test_main_blocks_empty_children(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _write_json(tmp_path, "blocks.json", {"children": []})
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks)
    assert PUB.main() == 2
    assert "non-empty children array" in capsys.readouterr().err


def test_main_blocks_not_list(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _write_json(tmp_path, "blocks.json", {"foo": "bar"})  # children なし → blocks 自身
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks)
    assert PUB.main() == 2
    assert "non-empty children array" in capsys.readouterr().err


def test_main_notion_config_import_failure(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    # notion_config の import を失敗させる
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "notion_config":
            raise ImportError("boom")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "notion_config", raising=False)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks)
    assert PUB.main() == 2
    assert "notion_config import failed" in capsys.readouterr().err


def test_main_database_id_unresolved(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    _install_fakes(monkeypatch, db_id=None)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks)
    assert PUB.main() == 2
    assert "database_id is required" in capsys.readouterr().err


def test_main_invalid_explicit_page_id(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    _install_fakes(monkeypatch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--page-id", "not-a-valid-id")
    assert PUB.main() == 2
    assert "不正です" in capsys.readouterr().err


def test_main_require_update_no_target(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    _install_fakes(monkeypatch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--require-update")
    assert PUB.main() == 51
    assert "create を禁止します" in capsys.readouterr().err


def test_main_no_target_create_disabled(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    _install_fakes(monkeypatch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks, "--database-id", "db-x")
    assert PUB.main() == 51
    assert "create is disabled by default" in capsys.readouterr().err


def test_main_dry_run_create(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    _install_fakes(monkeypatch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--allow-create", "--dry-run")
    assert PUB.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["mode"] == "create"
    assert out["page_id"] is None
    # db-id-resolution.json が tmp の eval-log に書かれる (repo 非汚染)
    res = json.loads((tmp_path / "eval-log" / "db-id-resolution.json").read_text(encoding="utf-8"))
    assert res["tool"] == "publish_notion_page"
    assert res["source"] == "arg"


def test_main_dry_run_update_with_page_id(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    _install_fakes(monkeypatch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--page-id", DASHED, "--dry-run")
    assert PUB.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "update"
    assert out["page_id"] == DASHED
    assert out["page_id_source"] == "arg"


# ===================== main() : create / update 実投稿経路 =====================

def _make_fetch(recorder, *, page_url="https://notion/created",
                created_id="new-pid", existing_db=None, raise_on=None,
                http_error_cls=None):
    """notion_fetch の挙動を模す。recorder に (path, method, body) を蓄積。"""
    def fetch(path, method="GET", body=None):
        recorder.append((path, method, body))
        if raise_on and raise_on(path, method):
            raise http_error_cls("boom", status=401)
        if method == "POST" and path == "/pages":
            return {"id": created_id, "url": page_url, "created_time": "t0"}
        if method == "GET" and path.startswith("/pages/"):
            parent = {"type": "database_id", "database_id": existing_db} if existing_db else {}
            return {"url": page_url, "parent": parent, "last_edited_time": "t1"}
        if method == "GET" and "/children" in path:
            return {"results": [{"id": "old1"}], "has_more": False}
        return {}
    return fetch


def test_main_create_success(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    rec = []
    fetch = _make_fetch(rec, created_id="created-123")
    _install_fakes(monkeypatch, fetch=fetch)
    monkeypatch.chdir(tmp_path)
    result_out = str(tmp_path / "result.json")
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--allow-create", "--result-out", result_out)
    assert PUB.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "create"
    assert out["id"] == "created-123"
    # POST /pages が呼ばれた
    assert any(p == "/pages" and m == "POST" for p, m, _ in rec)
    # result が永続化された (idempotency-key)
    saved = json.loads(Path(result_out).read_text(encoding="utf-8"))
    assert saved["page_id"] == "created-123"
    assert saved["mode"] == "create"


def test_main_create_paginates_remaining_children(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    # MAX_BLOCKS_PER_APPEND=100 を超える children を用意 (101 個)
    children = [{"object": "block", "type": "paragraph",
                 "paragraph": {"rich_text": []}} for _ in range(101)]
    blocks = _write_json(tmp_path, "blocks.json", {"children": children})
    rec = []
    fetch = _make_fetch(rec, created_id="cid")
    _install_fakes(monkeypatch, fetch=fetch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--allow-create")
    assert PUB.main() == 0
    # POST /pages + 残り children を PATCH /blocks/.../children で追記
    assert any(m == "POST" and p == "/pages" for p, m, _ in rec)
    assert any(m == "PATCH" and "/children" in p for p, m, _ in rec)


def test_main_update_success_archives_old_children(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    rec = []
    fetch = _make_fetch(rec, page_url="https://notion/updated", existing_db="db-x")
    _install_fakes(monkeypatch, fetch=fetch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--page-id", DASHED)
    assert PUB.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "update"
    assert out["id"] == DASHED
    methods = [(p, m) for p, m, _ in rec]
    # プロパティ PATCH と children PATCH と 旧 children DELETE
    assert ("/pages/" + DASHED, "PATCH") in methods
    assert any(p == "/blocks/old1" and m == "DELETE" for p, m, _ in rec)


def test_main_update_db_mismatch_returns_52(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    rec = []
    # 既存ページが別 DB に属する
    fetch = _make_fetch(rec, existing_db="00000000000000000000000000000000")
    _install_fakes(monkeypatch, fetch=fetch)
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", DASHED, "--page-id", COMPACT)
    assert PUB.main() == 52
    assert "different database" in capsys.readouterr().err


def test_main_http_error_401_returns_44(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    rec = []
    nh = _install_fakes(monkeypatch)
    fetch = _make_fetch(rec, raise_on=lambda p, m: p == "/pages" and m == "POST",
                        http_error_cls=nh.NotionHttpError)
    nh.notion_fetch = fetch
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--allow-create")
    assert PUB.main() == 44  # status 401 → 44
    assert "publish_notion_page" in capsys.readouterr().err


def test_main_http_error_other_returns_1(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    rec = []
    nh = _install_fakes(monkeypatch)

    def fetch(path, method="GET", body=None):
        raise nh.NotionHttpError("server", status=500)

    nh.notion_fetch = fetch
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--allow-create")
    assert PUB.main() == 1  # 401 以外 → 1


def test_main_result_write_failure_returns_2(monkeypatch, capsys, tmp_path):
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    rec = []
    fetch = _make_fetch(rec, created_id="cid")
    _install_fakes(monkeypatch, fetch=fetch)
    # _write_result を例外で失敗させる → exit 2
    monkeypatch.setattr(PUB, "_write_result",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--database-id", "db-x", "--allow-create",
              "--result-out", str(tmp_path / "r.json"))
    assert PUB.main() == 2
    assert "result write failed" in capsys.readouterr().err


def test_main_db_id_from_notion_config(monkeypatch, capsys, tmp_path):
    # --database-id 未指定 → notion_config.get_db_id 経由で解決 (source=notion_config)
    intake = _valid_intake(tmp_path)
    blocks = _valid_blocks(tmp_path)
    _install_fakes(monkeypatch, db_id="cfg-db-id")
    monkeypatch.chdir(tmp_path)
    _set_argv(monkeypatch, "--intake", intake, "--blocks", blocks,
              "--allow-create", "--dry-run")
    assert PUB.main() == 0
    res = json.loads((tmp_path / "eval-log" / "db-id-resolution.json").read_text(encoding="utf-8"))
    assert res["source"] == "notion_config"
    assert res["database_id"] == "cfg-db-id"
