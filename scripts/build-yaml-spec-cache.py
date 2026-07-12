#!/usr/bin/env python3
"""build-yaml-spec-cache.py

Claude Code 公式の実仕様ページ群 (frontmatter / settings / hooks / permissions /
agent-teams / commands / plugins など) と製品 CHANGELOG を取得し、
`.claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md`
に書き出す。GitHub Actions の `update-yaml-spec.yml` から週次起動される。

監視対象は設計書 `doc/ClaudeCodeスキルの設計書/15-official-source-notes.md` の
依存宣言 (Skills / Subagents / Hooks / Settings / Permissions / Agent Teams …) と
一致させる。ここに無い依存宣言があれば SOURCES 側の取りこぼしなので追加する。

CONVENTIONS:
- stdlib only (urllib, html.parser, datetime, pathlib, sys)
- 禁止依存: requests, PyYAML, bs4
- shebang + main + sys.exit(main()) パターン
"""
import datetime
import html.parser
import pathlib
import sys
import urllib.error
import urllib.request

# (name, url)。docs ページは HTML、CHANGELOG は raw markdown だが、いずれも
# TextExtractor を通して text 化 → diff 検知に用いる (markdown は tag が無いため
# 実質そのまま通過する)。新規追加時は 200 応答を必ず事前確認すること
# (FETCH_FAILED は exit 2 → 週次ジョブが恒常失敗するため)。
SOURCES = [
    # ── frontmatter / 実行境界の一次仕様 (設計書が明示依存) ──
    ("skills", "https://docs.claude.com/en/docs/claude-code/skills"),
    ("settings", "https://docs.claude.com/en/docs/claude-code/settings"),
    ("subagents", "https://docs.claude.com/en/docs/claude-code/sub-agents"),
    ("hooks", "https://docs.claude.com/en/docs/claude-code/hooks"),
    ("permissions", "https://docs.claude.com/en/docs/claude-code/permissions"),
    ("agent-teams", "https://docs.claude.com/en/docs/claude-code/agent-teams"),
    # ── skill / plugin 生成が契約を直接消費するページ ──
    ("commands", "https://docs.claude.com/en/docs/claude-code/commands"),
    ("plugins", "https://docs.claude.com/en/docs/claude-code/plugins"),
    ("plugins-reference", "https://docs.claude.com/en/docs/claude-code/plugins-reference"),
    ("output-styles", "https://docs.claude.com/en/docs/claude-code/output-styles"),
    ("tools-reference", "https://docs.claude.com/en/docs/claude-code/tools-reference"),
    # ── 製品レベル変更の広域センサー (単一ファイルで「何かあったか」を検知) ──
    ("changelog", "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"),
]

OUT_PATH = pathlib.Path(
    ".claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md"
)
MAX_BODY_CHARS = 50000
FETCH_TIMEOUT_SEC = 30


class TextExtractor(html.parser.HTMLParser):
    SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "harness-yaml-spec-fetcher/1.0"}
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_body(html_doc: str) -> str:
    parser = TextExtractor()
    parser.feed(html_doc)
    return parser.text()[:MAX_BODY_CHARS]


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    lines = [
        "# YAML Spec Cache",
        "",
        f"last_fetched: {now}",
        "fetcher: scripts/build-yaml-spec-cache.py",
        "",
    ]
    failures = 0
    for name, url in SOURCES:
        lines.append(f"## Source ({name}): {url}")
        lines.append("")
        try:
            body = extract_body(fetch(url))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            body = f"FETCH_FAILED: {type(exc).__name__}: {exc}"
            failures += 1
        lines.append(body)
        lines.append("")
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH} (sources={len(SOURCES)}, failures={failures})")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
