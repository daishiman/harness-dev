"""Genuine functional tests (scripts4) for scripts/notion-upsert-plugin.py.

このスクリプトは Notion スキル一覧 DB へプラグインを冪等 upsert する。既存の
tests/scripts-root/test_scripts__notion_upsert_plugin.py は純関数 + dry-run/引数異常のみを
カバーし、network/keychain 経路 (curl / find_existing / replace_page_children /
main の create/update publish 分岐) が未到達 (74%)。本ファイルはその穴を埋める。

network / keychain は一切叩かない:
  - `subprocess.check_output` (curl の実体) を monkeypatch でメモリ stub に差し替え、
    method/URL/headers/body の組み立てと HTTP code/JSON のパースを実値で検証する。
  - `notion_config.require_or_skip` / `get_db_id` を monkeypatch して keychain/config
    解決を擬似する。
  - すべての I/O は monkeypatch.chdir(tmp_path) + tmp_path 配下に限定し repo を汚さない。

他ディレクトリ (tests/scripts-root/ 及び tests/scripts-plugins/...) と同名にならないよう _r4 サフィックスを付す。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "notion-upsert-plugin.py"

# notion-upsert-plugin.py は import 時に plugins/harness-creator/scripts を sys.path へ
# 入れて `import notion_config` する。module body をそのまま exec すれば解決される。
# invalidate_caches で stale .pyc を無効化し coverage が必ず行をトレースできるようにする。
importlib.invalidate_caches()
_SPEC = importlib.util.spec_from_file_location("notion_upsert_plugin_r4", SCRIPT)
NUP = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(NUP)


# ============================================================
# curl(): subprocess stub で method/URL/header/body 組み立て & パース検証
# ============================================================

class _FakeCheckOutput:
    """subprocess.check_output の置き換え。最後に渡された argv を記録し、固定出力を返す。"""

    def __init__(self, http_code=200, payload=None, payload_raw=None):
        self.http_code = http_code
        self.payload = payload if payload is not None else {}
        self.payload_raw = payload_raw  # 文字列を直接返したい場合
        self.calls = []

    def __call__(self, cmd, *a, **kw):
        self.calls.append(cmd)
        # body を --data-binary @file で渡している場合、その JSON を読み取り保持
        body_text = None
        if "--data-binary" in cmd:
            ref = cmd[cmd.index("--data-binary") + 1]
            assert ref.startswith("@")
            body_text = Path(ref[1:]).read_text()
        self.calls[-1] = {"argv": cmd, "body": body_text}
        if self.payload_raw is not None:
            tail = self.payload_raw
        else:
            tail = json.dumps(self.payload)
        return (f"{tail}\n__HTTP__{self.http_code}").encode()


def test_curl_get_builds_headers_and_parses(monkeypatch):
    fake = _FakeCheckOutput(http_code=200, payload={"ok": True, "results": []})
    monkeypatch.setattr(subprocess, "check_output", fake)
    code, data = NUP.curl("GET", "https://api.notion.com/v1/x", "tok-123")
    assert code == 200
    assert data == {"ok": True, "results": []}
    argv = fake.calls[0]["argv"]
    assert argv[0] == "curl"
    assert "-X" in argv and argv[argv.index("-X") + 1] == "GET"
    # Authorization に token が入る
    assert any(a == "Authorization: Bearer tok-123" for a in argv)
    assert any(a == "Notion-Version: 2022-06-28" for a in argv)
    # body 無し → --data-binary を付けない
    assert "--data-binary" not in argv
    assert fake.calls[0]["body"] is None


def test_curl_post_writes_body_tempfile_and_cleans_up(monkeypatch):
    fake = _FakeCheckOutput(http_code=201, payload={"id": "page-xyz"})
    monkeypatch.setattr(subprocess, "check_output", fake)
    body = {"parent": {"database_id": "db1"}, "properties": {"a": 1}}
    code, data = NUP.curl("POST", "https://api.notion.com/v1/pages", "tok", body=body)
    assert code == 201
    assert data == {"id": "page-xyz"}
    # body が一時ファイル経由で渡り、内容が JSON 一致
    sent = json.loads(fake.calls[0]["body"])
    assert sent == body
    # 一時ファイルは os.unlink で消えている (curl 内で削除)
    ref = fake.calls[0]["argv"][fake.calls[0]["argv"].index("--data-binary") + 1]
    assert not Path(ref[1:]).exists()


def test_curl_empty_payload_returns_empty_dict(monkeypatch):
    # 204 等で空ボディの場合 → {} を返す
    fake = _FakeCheckOutput(http_code=204, payload_raw="")
    monkeypatch.setattr(subprocess, "check_output", fake)
    code, data = NUP.curl("DELETE", "https://api.notion.com/v1/blocks/b1", "tok")
    assert code == 204
    assert data == {}


# ============================================================
# _parse_frontmatter: 各分岐 (file 無し / fm 無し / triggers 各書式 / Purpose)
# ============================================================

def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_frontmatter_missing_file(tmp_path):
    out = NUP._parse_frontmatter(tmp_path / "nope.md")
    assert out["description"] == "" and out["triggers"] == [] and out["kind"] == ""


def test_parse_frontmatter_no_frontmatter(tmp_path):
    p = _write(tmp_path / "SKILL.md", "no frontmatter here\n## Purpose\nx")
    out = NUP._parse_frontmatter(p)
    assert out["description"] == "" and out["triggers"] == []


def test_parse_frontmatter_unterminated(tmp_path):
    # 開始 --- はあるが閉じ --- が無い → 空 out
    p = _write(tmp_path / "SKILL.md", "---\ndescription: x\nkind: run\n")
    out = NUP._parse_frontmatter(p)
    assert out["kind"] == ""  # end is None → 早期 return


def test_parse_frontmatter_list_block_style(tmp_path):
    md = (
        "---\n"
        "description: 'スキルを作る'\n"
        "argument-hint: <name>\n"
        "kind: run\n"
        "version: 1.2.0 # latest\n"
        "triggers:\n"
        "  - 'スキルを作りたい'\n"
        "  - ワークフロー連携\n"
        "owner: x\n"  # triggers ブロックを ":" 行で終える
        "---\n"
        "## Purpose\n"
        "このスキルは目的を達成する。\n"
        "次の段落は無視。\n"
    )
    out = NUP._parse_frontmatter(_write(tmp_path / "SKILL.md", md))
    assert out["description"] == "スキルを作る"
    assert out["argument_hint"] == "<name>"
    assert out["kind"] == "run"
    assert out["version"] == "1.2.0"  # コメント除去
    assert out["triggers"] == ["スキルを作りたい", "ワークフロー連携"]
    assert "目的を達成する" in out["purpose"]
    assert "無視" in out["purpose"]  # 空行までは連結される


def test_parse_frontmatter_inline_list_next_line(tmp_path):
    # triggers: の *次行* に inline [..] を置くと展開される (同一行記法は非対応の実挙動)
    md = (
        "---\n"
        "description: x\n"
        "triggers:\n"
        "  ['a', \"b\", c]\n"
        "kind: run\n"
        "---\n"
        "## 目的\n説明文\n"
    )
    out = NUP._parse_frontmatter(_write(tmp_path / "SKILL.md", md))
    assert out["triggers"] == ["a", "b", "c"]
    assert out["kind"] == "run"
    assert out["purpose"] == "説明文"


def test_parse_frontmatter_same_line_inline_not_parsed(tmp_path):
    # triggers: と同一行に [..] を書くと展開されない (実挙動の固定; ブロック/次行記法を使う)
    md = "---\ndescription: x\ntriggers: ['a', 'b']\nkind: run\n---\n"
    out = NUP._parse_frontmatter(_write(tmp_path / "SKILL.md", md))
    assert out["triggers"] == []
    assert out["kind"] == "run"


def test_parse_frontmatter_purpose_stops_at_next_heading(tmp_path):
    # Purpose 本文の後に別 heading → buf 確定済みで break (line 97 経路)
    md = (
        "---\n"
        "description: x\n"
        "kind: run\n"
        "---\n"
        "## Purpose\n"
        "目的の説明。\n"
        "## 次の節\n"
        "ここは含めない。\n"
    )
    out = NUP._parse_frontmatter(_write(tmp_path / "SKILL.md", md))
    assert out["purpose"] == "目的の説明。"
    assert "含めない" not in out["purpose"]


def test_parse_frontmatter_multiline_bracket_open_close(tmp_path):
    md = (
        "---\n"
        "triggers:\n"
        "  [\n"
        "  'x',\n"
        "  ]\n"
        "kind: ref\n"
        "---\n"
    )
    out = NUP._parse_frontmatter(_write(tmp_path / "SKILL.md", md))
    assert out["triggers"] == ["x"]
    assert out["kind"] == "ref"


def test_parse_frontmatter_quoted_scalar_trigger(tmp_path):
    md = (
        "---\n"
        "triggers:\n"
        '  "quoted-trigger"\n'
        "kind: run\n"
        "---\n"
    )
    out = NUP._parse_frontmatter(_write(tmp_path / "SKILL.md", md))
    assert out["triggers"] == ["quoted-trigger"]


# ============================================================
# scan_plugin: .claude-plugin/plugin.json 読み / skills 走査 / 壊れた plugin.json
# ============================================================

def _make_plugin(tmp_path, name="demo", version="9.9.9", skills=None):
    pdir = tmp_path / "plugins" / name
    pdir.mkdir(parents=True)
    (pdir / ".claude-plugin").mkdir()
    (pdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version, "description": "demo plugin"}), encoding="utf-8"
    )
    sdir = pdir / "skills"
    sdir.mkdir()
    for sk in skills or []:
        skd = sdir / sk["name"]
        skd.mkdir()
        (skd / "SKILL.md").write_text(sk["md"], encoding="utf-8")
    return pdir


def test_scan_plugin_reads_version_and_skills(tmp_path):
    md = "---\ndescription: 作る\nkind: run\ntriggers:\n  - t1\n---\n## Purpose\n目的\n"
    pdir = _make_plugin(tmp_path, skills=[{"name": "run-demo", "md": md}])
    info = NUP.scan_plugin(pdir)
    assert info["version"] == "9.9.9"
    assert info["plugin_desc"] == "demo plugin"
    assert info["install_cmd"] == "/plugin install demo"
    assert len(info["skills"]) == 1
    s = info["skills"][0]
    assert s["name"] == "run-demo" and s["desc"] == "作る" and s["kind"] == "run"
    assert s["triggers"] == ["t1"]


def test_scan_plugin_broken_plugin_json_swallowed(tmp_path):
    pdir = tmp_path / "plugins" / "broke"
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text("{not json", encoding="utf-8")
    info = NUP.scan_plugin(pdir)  # except 節で握りつぶし
    assert info["version"] == "" and info["skills"] == []


def test_scan_plugin_no_skills_dir(tmp_path):
    pdir = tmp_path / "plugins" / "empty"
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
    info = NUP.scan_plugin(pdir)
    assert info["skills"] == []
    # skills_dir.iterdir で file (非 dir) はスキップされる検証
    (pdir / "skills").mkdir()
    (pdir / "skills" / "stray.txt").write_text("x")
    assert NUP.scan_plugin(pdir)["skills"] == []


def test_scan_plugin_distributable_false_uses_clone_only_instruction(tmp_path):
    pdir = tmp_path / "plugins" / "internal"
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "1.0", "description": "internal", "distributable": False}),
        encoding="utf-8",
    )
    info = NUP.scan_plugin(pdir)
    assert info["distributable"] is False
    assert info["install_cmd"] == "非配布: repo clone 環境で make sync を実行して利用"


# ============================================================
# build_properties: title/relation/インストールコマンド
# ============================================================

def test_build_properties_basic_keys():
    info = {"version": "2.0", "skills": [{}, {}], "install_cmd": "/plugin install p"}
    props = NUP.build_properties("p", info)
    assert props["プラグイン名"]["title"][0]["text"]["content"] == "p"
    assert props["バージョン"]["rich_text"][0]["text"]["content"] == "2.0"
    assert props["概要"]["rich_text"][0]["text"]["content"] == "2 skill(s)"
    assert props["インストールコマンド"]["rich_text"][0]["text"]["content"] == "/plugin install p"
    assert props["リポジトリパス"]["url"] == "plugins/p"
    assert "紐づくヒアリングシート" not in props


def test_build_properties_with_hearing_sheet():
    info = {"version": "", "skills": [], "install_cmd": "x"}
    props = NUP.build_properties("p", info, hearing_sheet_id="hs-1")
    assert props["紐づくヒアリングシート"]["relation"] == [{"id": "hs-1"}]


# ============================================================
# _kind_label / _load_feedback_protocol
# ============================================================

def test_kind_label_known_and_unknown():
    assert NUP._kind_label("run") == "実行系(コマンド)"
    assert NUP._kind_label("assign") == "評価系"
    assert NUP._kind_label("delegate") == "委譲系(外部実行)"
    assert NUP._kind_label("zzz") == "zzz"      # 未知はそのまま
    assert NUP._kind_label("") == "未設定"       # 空は未設定


def test_load_feedback_protocol_reads_real_schema():
    fp = NUP._load_feedback_protocol()
    # SSOT schema からの必須キー
    for key in ("callout_summary", "firing_conditions", "command",
                "intake_fields", "promise_to_reporter", "status_lifecycle"):
        assert key in fp


def test_load_feedback_protocol_missing_exits(monkeypatch, tmp_path):
    # schema に feedback_protocol が無い → sys.exit(2)
    fake_schema = tmp_path / "skill-list.schema.json"
    fake_schema.write_text(json.dumps({"other": 1}), encoding="utf-8")
    monkeypatch.setattr(NUP, "SCHEMA_DIR", tmp_path)
    with pytest.raises(SystemExit) as ei:
        NUP._load_feedback_protocol()
    assert ei.value.code == 2


# ============================================================
# build_page_children: ブロック構造の網羅 (skills 有/無 + >8 + triggers 有無)
# ============================================================

def _block_types(blocks):
    return [b["type"] for b in blocks]


def test_build_page_children_with_skills_full_structure():
    info = {
        "version": "1.0",
        "plugin_desc": "",
        "distributable": False,
        "install_cmd": "非配布: repo clone 環境で make sync を実行して利用",
        "skills": [
            {"name": "run-a", "desc": "Aする", "triggers": ["ta1", "ta2"],
             "argument_hint": "<x>", "kind": "run", "purpose": "目的A"},
            {"name": "ref-b", "desc": "", "triggers": [],
             "argument_hint": "", "kind": "ref", "purpose": ""},
        ],
    }
    blocks = NUP.build_page_children("harness-creator", info)
    types = _block_types(blocks)
    # 既知 overview (harness-creator) が callout の先頭に出る
    assert blocks[0]["type"] == "callout"
    assert "土台プラグイン" in blocks[0]["callout"]["rich_text"][0]["text"]["content"]
    # 主要見出しが全部入る
    headings = [b["heading_2"]["rich_text"][0]["text"]["content"]
                for b in blocks if b["type"] == "heading_2"]
    assert any("何ができる" in h for h in headings)
    assert any("こんなときに使う" in h for h in headings)
    assert any("利用方法" in h for h in headings)
    assert any("含まれるスキル一覧" in h for h in headings)
    assert any("改善要望の出し方" in h for h in headings)
    assert any("困ったときは" in h for h in headings)
    # toggle が各スキル分
    toggles = [b for b in blocks if b["type"] == "toggle"]
    assert len(toggles) == 2
    # code ブロックに clone-only instruction が出る
    codes = [b["code"]["rich_text"][0]["text"]["content"] for b in blocks if b["type"] == "code"]
    assert "非配布: repo clone 環境で make sync を実行して利用" in codes
    # triggers 集約: ta1/ta2 が「こんなときに使う」bullet に
    bullets = [b["bulleted_list_item"]["rich_text"]
               for b in blocks if b["type"] == "bulleted_list_item"]
    flat = "".join(rt.get("text", {}).get("content", "")
                   for grp in bullets for rt in grp)
    assert "ta1" in flat and "ta2" in flat


def test_build_page_children_no_skills_uses_fallbacks():
    info = {"version": "", "plugin_desc": "私のプラグイン", "install_cmd": "/plugin install x", "skills": []}
    blocks = NUP.build_page_children("unknown-plugin", info)
    texts = json.dumps(blocks, ensure_ascii=False)
    # overview は plugin_desc にフォールバック
    assert "私のプラグイン" in texts
    # skills 無し時の専用文言
    assert "個別スキルがまだ含まれていません" in texts
    assert "トリガーが各スキルに設定されたら" in texts
    # numbered list は出ない (scenario も skills 無しメッセージ)
    assert "個別スキル追加後にここへシナリオ" in texts


def test_build_page_children_overflow_more_than_8_skills():
    skills = [{"name": f"run-s{i}", "desc": f"d{i}", "triggers": [],
               "argument_hint": "", "kind": "run", "purpose": ""} for i in range(10)]
    info = {"version": "", "plugin_desc": "", "install_cmd": "/plugin install z", "skills": skills}
    blocks = NUP.build_page_children("z", info)
    texts = json.dumps(blocks, ensure_ascii=False)
    # 8件超 → 「…ほか 2 スキル」
    assert "ほか 2 スキル" in texts
    # toggle は全 10 件出る
    assert len([b for b in blocks if b["type"] == "toggle"]) == 10


def test_build_page_children_default_overview_when_no_desc():
    info = {"version": "", "plugin_desc": "", "install_cmd": "x", "skills": [{}]}
    info["skills"] = []  # 0 skills かつ desc 無し → 数ベース文言
    blocks = NUP.build_page_children("brand-new", info)
    assert "0 個のスキルをまとめた" in blocks[0]["callout"]["rich_text"][0]["text"]["content"]


# ============================================================
# find_existing: hit / miss / error exit
# ============================================================

def test_find_existing_hit(monkeypatch):
    monkeypatch.setattr(NUP, "curl",
                        lambda *a, **k: (200, {"results": [{"id": "page-1"}]}))
    res = NUP.find_existing("db", "demo", "tok")
    assert res == {"id": "page-1"}


def test_find_existing_miss(monkeypatch):
    monkeypatch.setattr(NUP, "curl", lambda *a, **k: (200, {"results": []}))
    assert NUP.find_existing("db", "demo", "tok") is None


def test_find_existing_query_error_exits(monkeypatch):
    monkeypatch.setattr(NUP, "curl", lambda *a, **k: (400, {"message": "bad"}))
    with pytest.raises(SystemExit) as ei:
        NUP.find_existing("db", "demo", "tok")
    assert ei.value.code == 2


def test_find_existing_passes_title_filter(monkeypatch):
    captured = {}

    def fake_curl(method, url, token, body=None):
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        return 200, {"results": []}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    NUP.find_existing("DBID", "my-plugin", "tok")
    assert captured["method"] == "POST"
    assert "databases/DBID/query" in captured["url"]
    assert captured["body"]["filter"]["title"]["equals"] == "my-plugin"
    assert captured["body"]["filter"]["property"] == "プラグイン名"


# ============================================================
# replace_page_children: 削除→分割追加、ページネーション、>100 chunk、失敗
# ============================================================

def test_replace_page_children_deletes_then_appends(monkeypatch):
    calls = []

    def fake_curl(method, url, token, body=None):
        calls.append((method, url, body))
        if method == "GET":
            # 既存 2 ブロック、has_more False
            return 200, {"results": [{"id": "b1"}, {"id": "b2"}], "has_more": False}
        return 200, {}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    children = [{"type": "paragraph"} for _ in range(3)]
    ok = NUP.replace_page_children("pg", children, "tok")
    assert ok is True
    methods = [c[0] for c in calls]
    # GET 1 回, DELETE 2 回 (既存ブロック), PATCH 1 回 (3<100 一括)
    assert methods.count("GET") == 1
    assert methods.count("DELETE") == 2
    assert methods.count("PATCH") == 1


def test_replace_page_children_pagination(monkeypatch):
    state = {"page": 0}

    def fake_curl(method, url, token, body=None):
        if method == "GET":
            state["page"] += 1
            if state["page"] == 1:
                return 200, {"results": [{"id": "a"}], "has_more": True, "next_cursor": "C2"}
            return 200, {"results": [{"id": "b"}], "has_more": False}
        return 200, {}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    ok = NUP.replace_page_children("pg", [{"type": "x"}], "tok")
    assert ok is True
    assert state["page"] == 2  # 2 ページ走査


def test_replace_page_children_get_error_breaks_delete_loop(monkeypatch):
    """GET が >=300 → 削除ループ break、その後 append は実行される。"""
    calls = []

    def fake_curl(method, url, token, body=None):
        calls.append(method)
        if method == "GET":
            return 500, {}
        return 200, {}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    ok = NUP.replace_page_children("pg", [{"type": "x"}], "tok")
    assert ok is True
    assert "DELETE" not in calls  # 削除されない
    assert "PATCH" in calls


def test_replace_page_children_chunks_over_100(monkeypatch):
    patch_sizes = []

    def fake_curl(method, url, token, body=None):
        if method == "GET":
            return 200, {"results": [], "has_more": False}
        if method == "PATCH":
            patch_sizes.append(len(body["children"]))
        return 200, {}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    children = [{"type": "p"} for _ in range(250)]
    ok = NUP.replace_page_children("pg", children, "tok")
    assert ok is True
    assert patch_sizes == [100, 100, 50]


def test_replace_page_children_append_failure_returns_false(monkeypatch):
    def fake_curl(method, url, token, body=None):
        if method == "GET":
            return 200, {"results": [], "has_more": False}
        if method == "PATCH":
            return 400, {}
        return 200, {}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    ok = NUP.replace_page_children("pg", [{"type": "x"}], "tok")
    assert ok is False


# ============================================================
# main(): argv 駆動。各分岐を network なしで
# ============================================================

def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["notion-upsert-plugin.py", *argv])
    return NUP.main()


def test_main_plugin_dir_not_found_exits(monkeypatch, tmp_path):
    monkeypatch.setattr(NUP, "ROOT", tmp_path)  # plugins/ 不在
    with pytest.raises(SystemExit) as ei:
        _run_main(monkeypatch, ["--plugin", "ghost"])
    assert ei.value.code == 2


def test_main_dry_run_prints_json(monkeypatch, tmp_path, capsys):
    md = "---\ndescription: 作る\nkind: run\ntriggers:\n  - t\n---\n## Purpose\n目的\n"
    _make_plugin(tmp_path, name="demo", skills=[{"name": "run-demo", "md": md}])
    monkeypatch.setattr(NUP, "ROOT", tmp_path)
    ret = _run_main(monkeypatch, ["--plugin", "demo", "--dry-run"])
    assert ret is None
    out = json.loads(capsys.readouterr().out)
    assert out["plugin"] == "demo"
    assert out["info"]["version"] == "9.9.9"
    assert "プラグイン名" in out["properties_keys"]
    assert out["children_count"] > 0


def test_main_config_missing_returns_0(monkeypatch, tmp_path):
    """require_or_skip が (None, None) → 早期 return 0 (publish せず)。"""
    _make_plugin(tmp_path, name="demo")
    monkeypatch.setattr(NUP, "ROOT", tmp_path)
    monkeypatch.setattr(NUP.notion_config, "require_or_skip", lambda *a, **k: (None, None))
    ret = _run_main(monkeypatch, ["--plugin", "demo"])
    assert ret == 0


def test_main_create_new_page(monkeypatch, tmp_path, capsys):
    """find_existing が None → POST create 経路。"""
    _make_plugin(tmp_path, name="demo")
    monkeypatch.setattr(NUP, "ROOT", tmp_path)
    monkeypatch.setattr(NUP.notion_config, "require_or_skip", lambda *a, **k: ({"x": 1}, "tok"))
    monkeypatch.setattr(NUP.notion_config, "get_db_id", lambda *a, **k: "DBID")
    monkeypatch.setattr(NUP, "find_existing", lambda *a, **k: None)
    seen = {}

    def fake_curl(method, url, token, body=None):
        seen["method"] = method
        seen["url"] = url
        seen["body"] = body
        return 200, {"id": "new-page-id"}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    _run_main(monkeypatch, ["--plugin", "demo"])
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/v1/pages")
    assert seen["body"]["parent"]["database_id"] == "DBID"
    assert "properties" in seen["body"] and "children" in seen["body"]
    assert "[CREATED] demo -> new-page-id" in capsys.readouterr().out


def test_main_create_error_exits(monkeypatch, tmp_path):
    _make_plugin(tmp_path, name="demo")
    monkeypatch.setattr(NUP, "ROOT", tmp_path)
    monkeypatch.setattr(NUP.notion_config, "require_or_skip", lambda *a, **k: ({"x": 1}, "tok"))
    monkeypatch.setattr(NUP.notion_config, "get_db_id", lambda *a, **k: "DBID")
    monkeypatch.setattr(NUP, "find_existing", lambda *a, **k: None)
    monkeypatch.setattr(NUP, "curl", lambda *a, **k: (400, {"message": "bad"}))
    with pytest.raises(SystemExit) as ei:
        _run_main(monkeypatch, ["--plugin", "demo"])
    assert ei.value.code == 2


def test_main_update_existing_page(monkeypatch, tmp_path, capsys):
    """find_existing がヒット → PATCH update + replace_page_children 経路。"""
    _make_plugin(tmp_path, name="demo")
    monkeypatch.setattr(NUP, "ROOT", tmp_path)
    monkeypatch.setattr(NUP.notion_config, "require_or_skip", lambda *a, **k: ({"x": 1}, "tok"))
    monkeypatch.setattr(NUP.notion_config, "get_db_id", lambda *a, **k: "DBID")
    monkeypatch.setattr(NUP, "find_existing", lambda *a, **k: {"id": "existing-pg"})
    patched = {}

    def fake_curl(method, url, token, body=None):
        patched["method"] = method
        patched["url"] = url
        return 200, {}

    monkeypatch.setattr(NUP, "curl", fake_curl)
    replaced = {}
    monkeypatch.setattr(NUP, "replace_page_children",
                        lambda pid, ch, tok: replaced.update(pid=pid) or True)
    _run_main(monkeypatch, ["--plugin", "demo"])
    assert patched["method"] == "PATCH"
    assert "pages/existing-pg" in patched["url"]
    assert replaced["pid"] == "existing-pg"
    assert "[UPDATED] demo -> existing-pg" in capsys.readouterr().out


def test_main_update_error_exits(monkeypatch, tmp_path):
    _make_plugin(tmp_path, name="demo")
    monkeypatch.setattr(NUP, "ROOT", tmp_path)
    monkeypatch.setattr(NUP.notion_config, "require_or_skip", lambda *a, **k: ({"x": 1}, "tok"))
    monkeypatch.setattr(NUP.notion_config, "get_db_id", lambda *a, **k: "DBID")
    monkeypatch.setattr(NUP, "find_existing", lambda *a, **k: {"id": "pg"})
    monkeypatch.setattr(NUP, "curl", lambda *a, **k: (500, {}))
    with pytest.raises(SystemExit) as ei:
        _run_main(monkeypatch, ["--plugin", "demo"])
    assert ei.value.code == 2


def test_main_passes_hearing_sheet_id(monkeypatch, tmp_path):
    """--hearing-sheet-id が properties に伝播 (create body で確認)。"""
    _make_plugin(tmp_path, name="demo")
    monkeypatch.setattr(NUP, "ROOT", tmp_path)
    monkeypatch.setattr(NUP.notion_config, "require_or_skip", lambda *a, **k: ({"x": 1}, "tok"))
    monkeypatch.setattr(NUP.notion_config, "get_db_id", lambda *a, **k: "DBID")
    monkeypatch.setattr(NUP, "find_existing", lambda *a, **k: None)
    body_seen = {}
    monkeypatch.setattr(NUP, "curl",
                        lambda m, u, t, body=None: body_seen.update(b=body) or (200, {"id": "x"}))
    _run_main(monkeypatch, ["--plugin", "demo", "--hearing-sheet-id", "HS-99"])
    rel = body_seen["b"]["properties"]["紐づくヒアリングシート"]["relation"]
    assert rel == [{"id": "HS-99"}]
