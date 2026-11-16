"""build-yaml-spec-cache.py の genuine 機能テスト (network 不要)。

このスクリプトは唯一 `fetch()` のみが network I/O を持つ。テストはその関数を
monkeypatch / in-process import で完全に置換し、HTML→text 抽出ロジック・出力ファイル
生成・失敗集計・終了コードを実入力で駆動する。

- TextExtractor / extract_body : 実 HTML 断片を feed して抽出結果を assert
- fetch                        : urllib.request.urlopen を fake してヘッダ/decode を検証
- main                         : module の SOURCES/OUT_PATH/fetch を monkeypatch し
                                  成功(exit 0)・全失敗(exit 2)・一部失敗を in-process 駆動
                                  + subprocess(fetch 全失敗)で実 CLI の exit 2 を確認

実 .claude/ は一切書き換えない (OUT_PATH を tmp_path へ差し替え, subprocess は tmp の repo に
写した script を、閉じた port の proxy を通させて動かす)。
network: false。
"""
import datetime
import http.client
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-yaml-spec-cache.py"


def _load():
    """毎テストで独立な module インスタンスを得る (monkeypatch の干渉回避)。"""
    spec = importlib.util.spec_from_file_location("build_yaml_spec_cache_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


# ── TextExtractor ─────────────────────────────────────────────────────────
def test_text_extractor_collects_visible_data():
    p = MOD.TextExtractor()
    p.feed("<p>Hello</p><p>World</p>")
    assert p.text() == "Hello\nWorld"


def test_text_extractor_skips_script_and_style():
    p = MOD.TextExtractor()
    p.feed(
        "<div>keep</div>"
        "<script>var x = 1; alert('drop');</script>"
        "<style>.a{color:red}</style>"
        "<div>also-keep</div>"
    )
    assert p.text() == "keep\nalso-keep"


def test_text_extractor_skips_nav_footer_header_noscript():
    p = MOD.TextExtractor()
    p.feed(
        "<nav>nav-drop</nav>"
        "<header>head-drop</header>"
        "<main>visible</main>"
        "<footer>foot-drop</footer>"
        "<noscript>ns-drop</noscript>"
    )
    assert p.text() == "visible"


def test_text_extractor_strips_whitespace_only_data():
    p = MOD.TextExtractor()
    p.feed("<p>   </p><p>real</p>")
    # 空白のみの data は parts に入らない
    assert p.text() == "real"


def test_text_extractor_nested_skip_depth_balances():
    p = MOD.TextExtractor()
    # script の中に nav がネストしても skip_depth が正しく増減し、外側 text を拾える
    p.feed("<script><nav>x</nav>y</script><p>after</p>")
    assert p.text() == "after"


def test_text_extractor_endtag_without_open_does_not_underflow():
    p = MOD.TextExtractor()
    # 開きタグ無しの </script> でも skip_depth が負にならない (>0 ガード)
    p.feed("</script><p>safe</p>")
    assert p.skip_depth == 0
    assert p.text() == "safe"


# ── extract_body ──────────────────────────────────────────────────────────
def test_extract_body_returns_text_from_html():
    # 見出しは h<N> → `#` を N+2 個 (cache の `#` 表題・`##` 節の下に入れる)
    out = MOD.extract_body("<html><body><h1>Title</h1><p>Body</p></body></html>")
    assert out == "### Title\nBody"


def test_extract_body_truncates_to_max_body_chars(monkeypatch):
    # 見出しも改行も無い 1 行は字の境界で切り、切った旨の行を残す
    monkeypatch.setattr(MOD, "MAX_BODY_CHARS", 5)
    out = MOD.extract_body("<p>abcdefghij</p>")
    kept, marker = out.split("\n\n")
    assert kept == "abcde"
    assert marker.startswith("[truncated: kept 5 of 10 chars at a character boundary;")
    assert MOD.TRUNCATED_RE.match(marker)


def test_extract_body_empty_html_returns_empty():
    assert MOD.extract_body("") == ""


# ── fetch (urlopen fake, no real network) ─────────────────────────────────
class _FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_sets_user_agent_and_decodes_utf8(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["ua"] = req.get_header("User-agent")
        captured["timeout"] = timeout
        return _FakeResp("café".encode("utf-8"))

    monkeypatch.setattr(MOD.urllib.request, "urlopen", fake_urlopen)
    out = MOD.fetch("https://example.com/x")
    assert out == "café"
    assert captured["url"] == "https://example.com/x"
    assert captured["ua"] == "harness-yaml-spec-fetcher/1.0"
    assert captured["timeout"] == MOD.FETCH_TIMEOUT_SEC


def test_fetch_replaces_invalid_bytes(monkeypatch):
    # errors="replace" のため不正バイトは U+FFFD に置換され例外にならない
    def fake_urlopen(req, timeout=None):
        return _FakeResp(b"\xff\xfeok")

    monkeypatch.setattr(MOD.urllib.request, "urlopen", fake_urlopen)
    out = MOD.fetch("https://example.com/bad")
    assert "ok" in out
    assert "�" in out


# ── main (in-process, OUT_PATH/SOURCES/fetch all patched) ─────────────────
def _patch_outpath(monkeypatch, tmp_path):
    out = tmp_path / "ref" / "yaml-spec-cache.md"
    monkeypatch.setattr(MOD, "OUT_PATH", out)
    return out


def test_main_success_writes_file_and_returns_zero(monkeypatch, tmp_path, capsys):
    out = _patch_outpath(monkeypatch, tmp_path)
    monkeypatch.setattr(
        MOD, "SOURCES", [("skills", "https://docs.example/skills")]
    )
    monkeypatch.setattr(MOD, "fetch", lambda url: "<p>SPEC BODY</p>")

    rc = MOD.main()
    assert rc == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "# YAML Spec Cache" in text
    assert "last_fetched:" in text
    assert "fetcher: scripts/build-yaml-spec-cache.py" in text
    assert "## Source (skills): https://docs.example/skills" in text
    assert "SPEC BODY" in text
    captured = capsys.readouterr()
    assert "failures=0" in captured.out
    assert "sources=1" in captured.out


def test_main_all_fetch_fail_returns_two_and_records_failure(monkeypatch, tmp_path, capsys):
    out = _patch_outpath(monkeypatch, tmp_path)
    monkeypatch.setattr(
        MOD, "SOURCES", [("skills", "https://docs.example/skills")]
    )

    def boom(url):
        raise urllib.error.URLError("dns down")

    monkeypatch.setattr(MOD, "fetch", boom)
    rc = MOD.main()
    assert rc == 2
    text = out.read_text(encoding="utf-8")
    assert "FETCH_FAILED: URLError" in text
    assert "dns down" in text
    assert "failures=1" in capsys.readouterr().out


def test_main_partial_failure_returns_two(monkeypatch, tmp_path, capsys):
    out = _patch_outpath(monkeypatch, tmp_path)
    monkeypatch.setattr(
        MOD,
        "SOURCES",
        [
            ("ok", "https://docs.example/ok"),
            ("bad", "https://docs.example/bad"),
        ],
    )

    def selective(url):
        if url.endswith("/bad"):
            raise TimeoutError("slow")
        return "<p>GOOD</p>"

    monkeypatch.setattr(MOD, "fetch", selective)
    rc = MOD.main()
    assert rc == 2  # 1件でも失敗すれば 2
    text = out.read_text(encoding="utf-8")
    assert "GOOD" in text
    assert "FETCH_FAILED: TimeoutError" in text
    assert "failures=1" in capsys.readouterr().out


def _cache_text(stamp: str, body: str) -> str:
    return "\n".join([
        "# YAML Spec Cache", "", f"last_fetched: {stamp}",
        "fetcher: scripts/build-yaml-spec-cache.py", "",
        "## Source (s): https://x/y", "", body, "",
    ])


def _days_ago(days: int) -> str:
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return when.strftime(MOD.STAMP_FORMAT)


def test_main_keeps_file_when_body_unchanged_and_fresh(monkeypatch, tmp_path, capsys):
    # 本文が同じ週は last_fetched も書き換えない (毎週の commit と版上げを生まない)
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    before = _cache_text(_days_ago(7), "SAME")
    out.write_text(before, encoding="utf-8")
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])
    monkeypatch.setattr(MOD, "fetch", lambda url: "<p>SAME</p>")
    assert MOD.main() == 0
    assert out.read_text(encoding="utf-8") == before
    assert "unchanged" in capsys.readouterr().out


def test_main_refreshes_stamp_when_body_unchanged_but_old(monkeypatch, tmp_path):
    # 30 日の鮮度 WARNING に届く前に last_fetched だけ更新する
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    old_stamp = _days_ago(MOD.REFRESH_AFTER_DAYS)
    out.write_text(_cache_text(old_stamp, "SAME"), encoding="utf-8")
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])
    monkeypatch.setattr(MOD, "fetch", lambda url: "<p>SAME</p>")
    assert MOD.main() == 0
    text = out.read_text(encoding="utf-8")
    assert old_stamp not in text
    assert "SAME" in text


def test_main_rewrites_when_body_changed(monkeypatch, tmp_path):
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    out.write_text(_cache_text(_days_ago(1), "OLD"), encoding="utf-8")
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])
    monkeypatch.setattr(MOD, "fetch", lambda url: "<p>NEW</p>")
    assert MOD.main() == 0
    text = out.read_text(encoding="utf-8")
    assert "NEW" in text and "OLD" not in text


def test_keep_previous_rejects_missing_or_bad_stamp():
    now = datetime.datetime.now(datetime.timezone.utc)
    assert MOD.keep_previous("", _cache_text(_days_ago(0), "X"), now) is False
    assert MOD.keep_previous(_cache_text("not-a-date", "X"), _cache_text(_days_ago(0), "X"), now) is False


def test_main_creates_parent_directory(monkeypatch, tmp_path):
    # OUT_PATH の親が存在しなくても mkdir(parents=True) される
    out = tmp_path / "deep" / "nested" / "cache.md"
    monkeypatch.setattr(MOD, "OUT_PATH", out)
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])
    monkeypatch.setattr(MOD, "fetch", lambda url: "body")
    assert MOD.main() == 0
    assert out.parent.is_dir()
    assert out.exists()


def test_main_http_error_branch(monkeypatch, tmp_path, capsys):
    out = _patch_outpath(monkeypatch, tmp_path)
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])

    def http_boom(url):
        raise urllib.error.HTTPError("https://x/y", 503, "unavail", {}, None)

    monkeypatch.setattr(MOD, "fetch", http_boom)
    assert MOD.main() == 2
    assert "FETCH_FAILED: HTTPError" in out.read_text(encoding="utf-8")
    assert "failures=1" in capsys.readouterr().out


# ── subprocess: 実 CLI を起動 (外へ出られないので全 source 失敗 → exit 2) ──────
REAL_REFS = ROOT / "plugins" / "harness-creator" / "skills" / "ref-yaml-spec-fetcher" / "references"


def _offline_env() -> dict:
    """閉じた port の proxy を通させ、どの URL もすぐに失敗させる (本当の取得をしない)。"""
    env = dict(os.environ)
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env[key] = "http://127.0.0.1:9"
    for key in ("no_proxy", "NO_PROXY"):
        env[key] = ""
    return env


def test_cli_subprocess_writes_under_script_repo_not_cwd_and_exits_two(tmp_path):
    """書き先は script の場所 (scripts/ の親) から決まり、cwd には依らない。

    script を tmp の repo に写して別の cwd から動かす。実 repo の cache は書き換えない。
    """
    repo = (tmp_path / "repo").resolve()
    (repo / "scripts").mkdir(parents=True)
    copy = repo / "scripts" / SCRIPT.name
    copy.write_bytes(SCRIPT.read_bytes())
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    real_before = {p.name: p.read_bytes() for p in REAL_REFS.glob("yaml-spec-*")}

    proc = subprocess.run(
        [sys.executable, str(copy)], cwd=cwd, env=_offline_env(),
        text=True, capture_output=True, timeout=120,
    )

    assert proc.returncode == 2, proc.stderr
    refs = repo / ".claude" / "skills" / "ref-yaml-spec-fetcher" / "references"
    text = (refs / "yaml-spec-cache.md").read_text(encoding="utf-8")
    assert text.startswith("# YAML Spec Cache")
    assert "FETCH_FAILED:" in text
    assert (refs / "yaml-spec-index.json").exists()
    assert not (cwd / ".claude").exists()
    # 表示は以前と同じ repo root からの相対
    assert "wrote .claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md (sources=" in proc.stdout
    assert {p.name: p.read_bytes() for p in REAL_REFS.glob("yaml-spec-*")} == real_before


def test_out_path_is_anchored_at_the_repo_of_the_script():
    assert MOD.OUT_PATH == ROOT / ".claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md"


# ── 本文の形 (harness-o8k): template の除外・見出しの印・切り詰め ──────────────
def test_text_extractor_skips_mintlify_template_manifest():
    # Mintlify は本文の後ろに <template data-mint="manifest"> でサイト設定の JSON を置く。
    # feature flag など毎週動く値を含むので、取り込むと偽の spec diff になる
    p = MOD.TextExtractor()
    p.feed('<main><p>body</p></main><template data-mint="manifest">{"docsConfig":{"x":1}}</template>')
    assert p.text() == "body"


def test_text_extractor_marks_headings_and_drops_zero_width_space():
    p = MOD.TextExtractor()
    p.feed(
        '<h2 id="a"><a class="anchor-link">​</a><span>Configure</span> <code>skills</code></h2>'
        "<h3>Frontmatter reference</h3><p>name</p><h4>Deep</h4>"
    )
    assert p.text().split("\n") == [
        "#### Configure skills", "##### Frontmatter reference", "name", "###### Deep",
    ]


def test_text_extractor_escapes_body_lines_shaped_like_headings():
    # code 例の `### Step` や `## Source (` が索引に見出し・節として拾われないようにする
    p = MOD.TextExtractor()
    p.feed("<pre>### Step 1\n## Source (x): y\n# comment</pre>")
    assert p.text().split("\n") == ["\\### Step 1", "\\## Source (x): y", "# comment"]


def test_truncate_at_heading_cuts_before_the_last_heading_that_fits():
    text = "\n".join(["#### A", "a" * 10, "#### B", "b" * 10, "#### C", "c" * 10])
    out = MOD.truncate_at_heading(text, 40, "why")  # "#### C" の手前までが 35 字
    kept, marker = out.split("\n\n")
    assert kept == "#### A\naaaaaaaaaa\n#### B\nbbbbbbbbbb"
    assert marker == f"[truncated: kept {len(kept)} of {len(text)} chars at a heading boundary; why]"


def test_truncate_at_heading_keeps_text_that_fits():
    assert MOD.truncate_at_heading("#### A\nx", 100, "why") == "#### A\nx"


def test_extract_markdown_shifts_headings_and_keeps_angle_brackets():
    md = "# Changelog\n\n## 2.1.1\n\n- Fixed `<tool_name>` parsing\n```\n## not a heading\n```\n"
    out = MOD.extract_markdown(md)
    assert out.split("\n") == [
        "### Changelog", "", "#### 2.1.1", "", "- Fixed `<tool_name>` parsing",
        "```", "## not a heading", "```",
    ]


def test_extract_source_cuts_changelog_at_a_version_boundary(monkeypatch):
    monkeypatch.setitem(MOD.SOURCE_MAX_CHARS, "changelog", 40)
    md = "# Changelog\n\n## 2.0.2\n\n- new\n\n## 2.0.1\n\n- old old old old old old\n"
    out = MOD.extract_source("changelog", "https://x/CHANGELOG.md", md)
    kept, marker = out.split("\n\n[truncated: ")
    assert kept.endswith("- new") and "2.0.1" not in kept
    assert "newest-first changelog" in marker


def test_extract_source_uses_html_path_for_docs_pages():
    assert MOD.extract_source("skills", "https://x/skills", "<h2>T</h2><p>b</p>") == "#### T\nb"


# ── 索引 (harness-838) ─────────────────────────────────────────────────────
def _sample_cache() -> str:
    return "\n".join([
        "# YAML Spec Cache", "", "last_fetched: 2026-11-14T00:00:00Z",
        "fetcher: scripts/build-yaml-spec-cache.py", "",
        "## Source (skills): https://x/skills", "",
        "#### Configure", "intro", "##### Frontmatter reference", "name: x", "##### Other", "o",
        "#### Next", "n", "",
        "## Source (changelog): https://x/CHANGELOG.md", "",
        "### Changelog", "#### 2.0.1", "- a", "",
        "[truncated: kept 10 of 99 chars at a heading boundary; newest-first changelog]", "",
        "## Source (hooks): https://x/hooks", "",
        "FETCH_FAILED: URLError: down", "",
    ])


def test_build_index_records_sections_and_heading_ranges():
    raw = _sample_cache().encode("utf-8")
    index = MOD.build_index(raw)
    assert index["cache_sha256"] == __import__("hashlib").sha256(raw).hexdigest()
    assert index["last_fetched"] == "2026-11-14T00:00:00Z"
    lines = _sample_cache().split("\n")
    by_name = {s["name"]: s for s in index["sections"]}
    skills = by_name["skills"]
    assert (skills["start_line"], skills["end_line"]) == (6, 16)
    assert skills["bytes"] == sum(len(x.encode()) + 1 for x in lines[5:16])
    assert skills["truncated"] is False and skills["fetch_failed"] is False
    rows = {r[4]: r for r in index["headings"]["skills"]}
    # 見出しの終わりは、同じか浅い見出しの手前 (無ければ節の終わり)
    assert rows["Configure"][:3] == [2, 8, 13]
    assert rows["Frontmatter reference"][:3] == [3, 10, 11]
    assert rows["Next"][:3] == [2, 14, 16]
    assert lines[rows["Frontmatter reference"][1] - 1] == "##### Frontmatter reference"
    assert by_name["changelog"]["truncated"] is True
    assert "newest-first changelog" in by_name["changelog"]["truncation"]
    assert by_name["hooks"]["fetch_failed"] is True
    assert by_name["hooks"]["end_line"] == len(lines) - 1  # 末尾の改行は行を作らない


def test_render_index_is_json_with_the_section_table_first():
    import json
    rendered = MOD.render_index(MOD.build_index(_sample_cache().encode("utf-8")))
    assert json.loads(rendered) == MOD.build_index(_sample_cache().encode("utf-8"))
    head = rendered.split("\n")
    # 節の表は 1 節 1 行で先頭近くにある (索引の頭だけ読めば行範囲が分かる)
    assert head[6] == '  "sections": ['
    assert head[7].startswith('    {"name": "skills"')


def test_main_writes_index_next_to_cache(monkeypatch, tmp_path):
    out = _patch_outpath(monkeypatch, tmp_path)
    monkeypatch.setattr(MOD, "SOURCES", [("skills", "https://docs.example/skills")])
    monkeypatch.setattr(MOD, "fetch", lambda url: "<h2>Frontmatter reference</h2><p>name</p>")
    assert MOD.main() == 0
    index_path = out.with_name("yaml-spec-index.json")
    assert index_path.read_text(encoding="utf-8") == MOD.render_index(MOD.build_index(out.read_bytes()))


def test_main_keep_previous_touches_neither_cache_nor_index(monkeypatch, tmp_path, capsys):
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    before = _cache_text(_days_ago(7), "SAME")
    out.write_text(before, encoding="utf-8")
    index_path = out.with_name("yaml-spec-index.json")
    index_path.write_text("stale on purpose", encoding="utf-8")
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])
    monkeypatch.setattr(MOD, "fetch", lambda url: "<p>SAME</p>")
    assert MOD.main() == 0
    assert out.read_text(encoding="utf-8") == before
    assert index_path.read_text(encoding="utf-8") == "stale on purpose"
    assert "unchanged" in capsys.readouterr().out


def test_reindex_rebuilds_index_without_network(monkeypatch, tmp_path, capsys):
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    out.write_text(_sample_cache(), encoding="utf-8")

    def no_network(url):
        raise AssertionError("--reindex must not fetch")

    monkeypatch.setattr(MOD, "fetch", no_network)
    assert MOD.main(["--reindex"]) == 0
    index_path = out.with_name("yaml-spec-index.json")
    assert index_path.read_text(encoding="utf-8") == MOD.render_index(MOD.build_index(out.read_bytes()))
    assert out.read_text(encoding="utf-8") == _sample_cache()  # cache は触らない
    assert "reindexed" in capsys.readouterr().out


def test_reindex_without_cache_exits_one(monkeypatch, tmp_path):
    _patch_outpath(monkeypatch, tmp_path)
    assert MOD.main(["--reindex"]) == 1


def test_committed_index_matches_index_rebuilt_from_committed_cache():
    """commit 済みの cache から作り直した索引が commit 済みの索引と 1 byte も違わないこと。

    cache を手で直した・script の索引の形を変えたのに `--reindex` を忘れた、を落とす。
    """
    refs = ROOT / "plugins" / "harness-creator" / "skills" / "ref-yaml-spec-fetcher" / "references"
    cache = refs / "yaml-spec-cache.md"
    index = refs / "yaml-spec-index.json"
    assert index.exists(), "yaml-spec-index.json が無い: python3 scripts/build-yaml-spec-cache.py --reindex"
    assert index.read_text(encoding="utf-8") == MOD.render_index(MOD.build_index(cache.read_bytes())), (
        "索引が cache と合わない: python3 scripts/build-yaml-spec-cache.py --reindex を実行して commit する"
    )


# ── 独立レビュー (FAIL 75) の指摘ごとの回帰 ───────────────────────────────────
class _BrokenResp(_FakeResp):
    """読みの途中で切れる応答。"""

    def __init__(self, exc: BaseException):
        super().__init__(b"")
        self._exc = exc

    def read(self):
        raise self._exc


@pytest.mark.parametrize("exc, label", [
    (http.client.IncompleteRead(b"partial"), "FETCH_FAILED: IncompleteRead"),
    (ConnectionResetError("reset by peer"), "FETCH_FAILED: ConnectionResetError: reset by peer"),
])
def test_main_mid_read_error_is_fetch_failed_exit_two(monkeypatch, tmp_path, capsys, exc, label):
    # [中] resp.read() の途中で投げる例外も traceback (exit 1) にせず FETCH_FAILED / exit 2
    out = _patch_outpath(monkeypatch, tmp_path)
    monkeypatch.setattr(MOD, "SOURCES", [("skills", "https://docs.example/skills")])
    monkeypatch.setattr(MOD.urllib.request, "urlopen", lambda req, timeout=None: _BrokenResp(exc))
    assert MOD.main() == 2
    assert label in out.read_text(encoding="utf-8")
    assert "FETCH_FAILED skills:" in capsys.readouterr().err


NON_UTF8_CACHE = b"# x\n\xff\xfe\n"


def test_reindex_non_utf8_cache_exits_one_without_writing(monkeypatch, tmp_path, capsys):
    # [中] --reindex で UTF-8 でない cache: traceback にせず、cache を読めない (exit 1)
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    out.write_bytes(NON_UTF8_CACHE)
    assert MOD.main(["--reindex"]) == 1
    assert not out.with_name("yaml-spec-index.json").exists()
    assert out.read_bytes() == NON_UTF8_CACHE
    assert "UnicodeDecodeError" in capsys.readouterr().err


def test_main_non_utf8_cache_exits_one_before_fetching(monkeypatch, tmp_path, capsys):
    # [中] 通常の実行でも同じ。取得の前に止め、読めない cache を上書きしない
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    out.write_bytes(NON_UTF8_CACHE)
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])

    def no_fetch(url):
        raise AssertionError("must not fetch when the previous cache is unreadable")

    monkeypatch.setattr(MOD, "fetch", no_fetch)
    assert MOD.main() == 1
    assert out.read_bytes() == NON_UTF8_CACHE
    assert not out.with_name("yaml-spec-index.json").exists()
    assert "UTF-8" in capsys.readouterr().err


def _two_source_cache(stamp: str, hooks_url: str = "https://x/hooks") -> str:
    return "\n".join([
        "# YAML Spec Cache", "", f"last_fetched: {stamp}",
        "fetcher: scripts/build-yaml-spec-cache.py", "",
        "## Source (ok): https://x/ok", "", "OLD OK", "",
        f"## Source (hooks): {hooks_url}", "", "GOOD HOOKS BODY", "second line", "",
    ])


def _ok_and_failing_hooks(url):
    if url.endswith("/hooks"):
        raise urllib.error.URLError("down")
    return "<p>NEW OK</p>"


def test_main_partial_failure_keeps_previous_good_body(monkeypatch, tmp_path, capsys):
    # [低] 落ちた source の前の良い本文を FETCH_FAILED で上書きしない。exit は 2 のまま
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    stamp = _days_ago(3)
    out.write_text(_two_source_cache(stamp), encoding="utf-8")
    monkeypatch.setattr(MOD, "SOURCES", [("ok", "https://x/ok"), ("hooks", "https://x/hooks")])
    monkeypatch.setattr(MOD, "fetch", _ok_and_failing_hooks)
    assert MOD.main() == 2
    text = out.read_text(encoding="utf-8")
    assert "GOOD HOOKS BODY\nsecond line" in text
    assert "NEW OK" in text and "FETCH_FAILED" not in text
    assert f"last_fetched: {stamp}" in text  # 残した本文より新しい日時を付けない
    index = json.loads(out.with_name("yaml-spec-index.json").read_text(encoding="utf-8"))
    hooks = {s["name"]: s for s in index["sections"]}["hooks"]
    assert hooks["fetch_failed"] is False
    assert MOD._previous_bodies(out.read_bytes())[("hooks", "https://x/hooks")] == "GOOD HOOKS BODY\nsecond line"
    assert "kept the previous body" in capsys.readouterr().err


def test_main_partial_failure_does_not_keep_a_body_from_another_url(monkeypatch, tmp_path):
    # URL が変わった source は前の本文を引き継がない (別のページの本文を新しい URL の下に置かない)
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    out.write_text(_two_source_cache(_days_ago(3), hooks_url="https://x/old-hooks"), encoding="utf-8")
    monkeypatch.setattr(MOD, "SOURCES", [("ok", "https://x/ok"), ("hooks", "https://x/hooks")])
    monkeypatch.setattr(MOD, "fetch", _ok_and_failing_hooks)
    assert MOD.main() == 2
    text = out.read_text(encoding="utf-8")
    assert "GOOD HOOKS BODY" not in text
    assert "FETCH_FAILED: URLError" in text


def test_main_keep_previous_with_failure_still_exits_two(monkeypatch, tmp_path, capsys):
    # 前の本文を残した結果 cache が前と同じでも、取得の失敗は exit 2 で知らせる
    out = _patch_outpath(monkeypatch, tmp_path)
    out.parent.mkdir(parents=True)
    before = _cache_text(_days_ago(1), "SAME")
    out.write_text(before, encoding="utf-8")
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])

    def down(url):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(MOD, "fetch", down)
    assert MOD.main() == 2
    assert out.read_text(encoding="utf-8") == before
    assert "unchanged" in capsys.readouterr().out


def test_extract_body_mismatched_heading_end_tag_keeps_the_rest():
    # [低] <h2>…</h3> の後ろの本文を黙って飲み込まない
    assert MOD.extract_body("<h2>Title</h3><p>body one</p><p>body two</p>") == "#### Title\nbody one\nbody two"


def test_extract_body_unclosed_heading_at_end_is_kept():
    assert MOD.extract_body("<p>a</p><h2>Tail") == "a\n#### Tail"


def test_extract_body_new_heading_closes_the_open_one():
    assert MOD.extract_body("<h2>One<h3>Two</h3><p>b</p>") == "#### One\n##### Two\nb"


def test_truncate_at_early_heading_cuts_at_a_line_instead():
    # [低] 早い位置の見出しでしか切れないとき、上限 4000 字のうち 5 字だけにしない
    text = "intro\n#### H\n" + "\n".join(["x" * 50] * 100) + "\n#### Tail\n" + "y" * 50
    out = MOD.truncate_at_heading(text, 4000, "why")
    kept, marker = out.split("\n\n")
    assert len(kept) >= 4000 * MOD.MIN_HEADING_CUT_SHARE
    assert len(kept) <= 4000
    assert text.startswith(kept)
    assert "at a line boundary" in marker


def test_body_lines_shaped_like_markers_are_escaped(monkeypatch, tmp_path):
    # [低] 本文の「FETCH_FAILED:」「[truncated: …]」で索引に誤った印を立てない
    assert MOD.extract_body("<p>FETCH_FAILED: x</p>") == "\\FETCH_FAILED: x"
    assert MOD.extract_markdown("FETCH_FAILED: x\n[truncated: y]") == "\\FETCH_FAILED: x\n\\[truncated: y]"
    out = _patch_outpath(monkeypatch, tmp_path)
    monkeypatch.setattr(MOD, "SOURCES", [("s", "https://x/y")])
    monkeypatch.setattr(MOD, "fetch", lambda url: "<p>FETCH_FAILED: not really</p><p>[truncated: fake]</p>")
    assert MOD.main() == 0
    section = MOD.build_index(out.read_bytes())["sections"][0]
    assert section["fetch_failed"] is False and section["truncated"] is False


def test_extract_markdown_fence_closes_only_with_a_long_enough_plain_mark():
    # [低] ```` の中の ``` で fence を閉じたことにせず、中の `## inside` を見出しにしない
    md = "# T\n````md\n```\n## inside\n```\n````\n## after\n"
    out = MOD.extract_markdown(md)
    assert out.split("\n") == ["### T", "````md", "```", "## inside", "```", "````", "#### after"]
    raw = ("# YAML Spec Cache\n\n## Source (changelog): https://x/CHANGELOG.md\n\n" + out + "\n").encode("utf-8")
    titles = [row[4] for row in MOD.build_index(raw)["headings"]["changelog"]]
    assert titles == ["T", "after"]


def test_extract_markdown_fence_with_info_string_does_not_close():
    out = MOD.extract_markdown("```\n```py\n## inside\n```\n## after")
    assert out.split("\n") == ["```", "```py", "## inside", "```", "#### after"]


def test_write_atomically_leaves_both_files_when_staging_fails(monkeypatch, tmp_path):
    # [低] 2 つ目の一時ファイルを書き切れなければ、どちらも置き換えず一時ファイルも残さない
    cache, index = tmp_path / "yaml-spec-cache.md", tmp_path / "yaml-spec-index.json"
    cache.write_bytes(b"old cache")
    index.write_bytes(b"old index")
    cache.chmod(0o640)
    real_fsync, calls = os.fsync, []

    def flaky_fsync(fd):
        calls.append(fd)
        if len(calls) == 2:
            raise OSError("disk full")
        real_fsync(fd)

    monkeypatch.setattr(MOD.os, "fsync", flaky_fsync)
    with pytest.raises(OSError, match="disk full"):
        MOD._write_atomically([(cache, b"new cache"), (index, b"new index")])
    assert cache.read_bytes() == b"old cache" and index.read_bytes() == b"old index"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["yaml-spec-cache.md", "yaml-spec-index.json"]
    monkeypatch.setattr(MOD.os, "fsync", real_fsync)
    MOD._write_atomically([(cache, b"new cache"), (index, b"new index")])
    assert cache.read_bytes() == b"new cache" and index.read_bytes() == b"new index"
    assert stat.S_IMODE(cache.stat().st_mode) == 0o640  # 置き換えても mode は前のまま


def test_unknown_option_exits_one_not_two(capsys):
    # [低] 使い方の誤りは 1 (2 は取得の失敗だけ)
    with pytest.raises(SystemExit) as info:
        MOD.main(["--bogus"])
    assert info.value.code == 1
    assert "unrecognized arguments: --bogus" in capsys.readouterr().err
