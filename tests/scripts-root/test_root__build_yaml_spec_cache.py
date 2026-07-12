"""build-yaml-spec-cache.py の genuine 機能テスト (network 不要)。

このスクリプトは唯一 `fetch()` のみが network I/O を持つ。テストはその関数を
monkeypatch / in-process import で完全に置換し、HTML→text 抽出ロジック・出力ファイル
生成・失敗集計・終了コードを実入力で駆動する。

- TextExtractor / extract_body : 実 HTML 断片を feed して抽出結果を assert
- fetch                        : urllib.request.urlopen を fake してヘッダ/decode を検証
- main                         : module の SOURCES/OUT_PATH/fetch を monkeypatch し
                                  成功(exit 0)・全失敗(exit 2)・一部失敗を in-process 駆動
                                  + subprocess(fetch 全失敗)で実 CLI の exit 2 を確認

実 .claude/ は一切書き換えない (OUT_PATH を tmp_path へ差し替え, subprocess は cwd=tmp_path)。
network: false。
"""
import importlib.util
import io
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
    out = MOD.extract_body("<html><body><h1>Title</h1><p>Body</p></body></html>")
    assert out == "Title\nBody"


def test_extract_body_truncates_to_max_body_chars(monkeypatch):
    monkeypatch.setattr(MOD, "MAX_BODY_CHARS", 5)
    out = MOD.extract_body("<p>abcdefghij</p>")
    assert out == "abcde"
    assert len(out) == 5


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


# ── subprocess: 実 CLI を起動 (network 切断で全 source 失敗 → exit 2) ──────
def test_cli_subprocess_writes_under_cwd_and_exits_two(tmp_path):
    """実バイナリ起動。OUT_PATH は相対パスなので cwd=tmp_path 配下に書かれ、
    network 不通(または到達失敗)で全 source 失敗 → exit 2。実 repo は無傷。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        # 到達できても本番ドメインへ実 fetch されないよう no_proxy 等は触らず、
        # ネットワーク不可前提。到達した場合も内容に依存する assert はしない。
        timeout=180,
    )
    # network 不通環境では failures>0 → exit 2。万一到達して成功すれば exit 0。
    assert proc.returncode in (0, 2)
    written = tmp_path / ".claude" / "skills" / "ref-yaml-spec-fetcher" / "references" / "yaml-spec-cache.md"
    assert written.exists()
    head = written.read_text(encoding="utf-8")
    assert head.startswith("# YAML Spec Cache")
    assert "wrote" in proc.stdout
