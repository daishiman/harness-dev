#!/usr/bin/env python3
# /// script
# name: build-yaml-spec-cache
# purpose: Claude Code 公式の実仕様ページ群と製品 CHANGELOG を取得し、ref-yaml-spec-fetcher の cache (yaml-spec-cache.md) と、cache だけから決まる索引 (yaml-spec-index.json) を書く。--reindex は取得せず、既存の cache から索引だけを作り直す
# inputs:
#   - argv: [--reindex]
#   - network: SOURCES の各 URL (--reindex のときは出ない)
#   - fs: <repo>/.claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md (前回の cache。UTF-8 必須)
# outputs:
#   - fs: 同じ dir の yaml-spec-cache.md と yaml-spec-index.json (両方を一時ファイルに書き切ってから os.replace で置き換える)
#   - stdout: wrote / unchanged / reindexed の要約と truncated の通知
#   - stderr: 取得に失敗した source・読めない cache・使い方の誤り
#   - exit: 0=OK / 1=使い方の誤り、または cache を読めない (--reindex で cache が無い・cache が UTF-8 でない) / 2=取得に失敗した source がある (前の良い本文があればそれを残し、last_fetched は前回の値のまま)
# contexts: [A, E]
# network: true  (--reindex のときは出ない)
# write-scope: <repo>/.claude/skills/ref-yaml-spec-fetcher/references/ の yaml-spec-cache.md と yaml-spec-index.json だけ。<repo> は script の場所 (scripts/ の親) から決め、cwd には依らない
# dependencies: []
# requires-python: ">=3.10"
# ///
"""build-yaml-spec-cache.py

Claude Code 公式の実仕様ページ群 (frontmatter / settings / hooks / permissions /
agent-teams / commands / plugins など) と製品 CHANGELOG を取得し、
`.claude/skills/ref-yaml-spec-fetcher/references/` に次の 2 つを書き出す。
GitHub Actions の `update-yaml-spec.yml` から週次起動される。

- yaml-spec-cache.md: 本文。節は `## Source (<name>): <url>`。ページ内の見出し (h1-h6) は
  `#` を (N+2) 個 (最大 6) 付けた行にする (h2 → `#### `)。本文の行がたまたま見出しや節の形に
  なるときは先頭に `\\` を付けて、索引の文法とぶつからないようにする。
- yaml-spec-index.json: cache だけから決まる索引。cache_sha256・last_fetched・節ごとの
  開始/終了行・bytes・truncated と、節ごとの見出しの行範囲。読む側は索引を見て
  Read の offset/limit で要る範囲だけを読む (cache は 1MB 近くあり、全文は読まない)。

使い方:
  python3 scripts/build-yaml-spec-cache.py            # 取得して cache と索引を書く
  python3 scripts/build-yaml-spec-cache.py --reindex  # 既存 cache から索引だけ作り直す (ネットに出ない)

本文が前回と同じで取得から日が浅いときは、cache も索引も書き換えない (keep_previous)。
取得に失敗した source は、前回の cache に同じ name・URL の良い本文があればそれを残す
(無ければ `FETCH_FAILED:` の行を置く)。どちらでも exit 2 にする。

監視対象は設計書 `doc/ClaudeCodeスキルの設計書/15-official-source-notes.md` の
依存宣言 (Skills / Subagents / Hooks / Settings / Permissions / Agent Teams …) と
一致させる。ここに無い依存宣言があれば SOURCES 側の取りこぼしなので追加する。

CONVENTIONS:
- stdlib only (urllib, http.client, html.parser, datetime, hashlib, json, os, pathlib, re, stat, sys, tempfile)
- 禁止依存: requests, PyYAML, bs4
- shebang + main + sys.exit(main()) パターン
"""
import argparse
import datetime
import hashlib
import html.parser
import http.client
import json
import os
import pathlib
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.request

EXIT_OK = 0
EXIT_USAGE = 1  # 使い方の誤り・cache を読めない
EXIT_FETCH_FAILED = 2  # 取得に失敗した source がある

# (name, url)。docs ページは HTML を TextExtractor で text にする。URL が .md で終わるもの
# (CHANGELOG) は raw markdown なので HTML として読まず、見出しの深さだけ揃える
# (HTML として読むと `<tool_name>` のような文字列が tag と見なされて消える)。
# 新規追加時は 200 応答を必ず事前確認すること (FETCH_FAILED は exit 2 → 週次ジョブが恒常失敗するため)。
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

# 書き先は script の場所 (scripts/ の親 = repo root) から決める。cwd から決めると、別の dir で
# 動かしたときにそこへ .claude/ の木を作ってしまう
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_REL = pathlib.Path(".claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md")
OUT_PATH = REPO_ROOT / CACHE_REL
INDEX_NAME = "yaml-spec-index.json"
# docs ページ 1 節の上限 (字数)。以前の 50000 では hooks の約 8 割、skills・subagents の約半分が
# 欠けていた。2026-11 時点の最大は hooks の約 25 万字。上限を超えたら見出しの境界で切り、
# 切ったことを節の末尾の行と索引の truncated に残す (黙って欠けさせない)。
MAX_BODY_CHARS = 400000
# CHANGELOG は新しい版が上に積まれ、際限なく伸びる。変更の検知には新しい版だけあればよいので、
# 版の見出しの境界で切って新しい側だけを持つ。週次の取得の間に出る版がすべて収まる大きさにする
# (2026-11 時点で週 6-7 版・1 版 1-4 万字、1 週で 10-15 万字)。窓を広げても週ごとの差分は
# 増えない (上に足された分と同じ量が下から抜けるだけ) ので、余裕を持たせる。
SOURCE_MAX_CHARS = {"changelog": 250000}
TRUNCATION_REASONS = {
    "changelog": "newest-first changelog; only the latest entries are kept",
}
DEFAULT_TRUNCATION_REASON = "page is longer than MAX_BODY_CHARS; raise the limit"
# 見出しの境界で切ると上限のこの割合も残らないとき (早い位置にしか見出しが無いとき) は、
# 行の境界で切る。見出しの境界にこだわって上限のほとんどを捨てないため
MIN_HEADING_CUT_SHARE = 0.5
FETCH_TIMEOUT_SEC = 30
# 取得の失敗として扱う例外。URLError/HTTPError/TimeoutError/ConnectionResetError は OSError の子、
# 読みの途中で切れたとき (IncompleteRead など) は http.client.HTTPException の子
FETCH_ERRORS = (urllib.error.URLError, http.client.HTTPException, OSError)
# 本文が前回と同じ週は、last_fetched だけの差分で commit と plugin の版上げが毎週起きていた。
# 本文が同じで前回取得から REFRESH_AFTER_DAYS 日未満なら書き換えない。週次で回る前提で、
# lint-manifest-contents の 30 日 WARNING に届く前 (最長 28 日) に last_fetched だけ更新する
# (ref-yaml-spec-fetcher SKILL.md 手順 4)。
REFRESH_AFTER_DAYS = 23
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# ── cache の文法 (索引はこれだけを見て作る) ──
SECTION_RE = re.compile(r"^## Source \(([^)]+)\): (\S+)$")
HEADING_RE = re.compile(r"^(#{3,6}) (.+)$")
TRUNCATED_RE = re.compile(r"^\[truncated: (.+)\]$")
FETCH_FAILED_PREFIX = "FETCH_FAILED:"
HEADING_OFFSET = 2  # h1 → `###`。cache の `#` (表題) と `##` (節) の下に入れる
INDEX_SCHEMA_VERSION = 1
HEADING_COLUMNS = ["level", "start_line", "end_line", "bytes", "title"]
INDEX_LINE_NOTE = (
    "line numbers are 1-based and inclusive; "
    "Read the cache with offset=start_line and limit=end_line-start_line+1"
)

HEADING_TAGS = {f"h{n}": n for n in range(1, 7)}
ZERO_WIDTH_SPACE = "\u200b"  # 見出しの anchor link が独立した行として出していた
# fence の印 (``` か ~~~ を 3 個以上) と、その後ろの info string
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
MD_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+)$")


def heading_line(level: int, title: str) -> str:
    return "#" * min(level + HEADING_OFFSET, 6) + " " + title.strip()


def _escape_line(line: str) -> str:
    """本文の行が cache の文法 (見出し・節・取得失敗・切り詰めの印) の形のときだけ `\\` を付ける。

    索引が本文の行を見出し・節として拾ったり、取得失敗・切り詰めの印と取り違えたりしないように。
    """
    if (HEADING_RE.match(line) or line.startswith("## Source (")
            or line.startswith(FETCH_FAILED_PREFIX) or TRUNCATED_RE.match(line)):
        return "\\" + line
    return line


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


class TextExtractor(html.parser.HTMLParser):
    # template: Mintlify が本文の後ろに置く <template data-mint="manifest"> (サイト設定の JSON
    # 1 行、10 万字超)。本文ではなく、feature flag など毎週動く値を含むので取り込まない。
    SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.parts: list[str] = []
        self._heading_level: int | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif self.skip_depth == 0 and tag in HEADING_TAGS:
            # HTML の parser と同じく、見出しの中で次の見出しが始まったら前の見出しを閉じる
            self._close_heading()
            self._heading_level = HEADING_TAGS[tag]
            self._heading_parts = []

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        # 深さの違う閉じタグ (<h2>…</h3>) でも開いている見出しを閉じる (HTML の parser と同じ)。
        # 深さの一致だけを見ると、残りの本文が全部見出しの中に入って黙って消える
        if tag in HEADING_TAGS:
            self._close_heading()

    def _close_heading(self) -> None:
        if self._heading_level is None:
            return
        title = " ".join(" ".join(self._heading_parts).split())
        if title:
            self.parts.append(heading_line(self._heading_level, title))
        self._heading_level = None
        self._heading_parts = []

    def handle_data(self, data):
        if self.skip_depth != 0:
            return
        data = data.replace(ZERO_WIDTH_SPACE, "")
        if self._heading_level is not None:
            self._heading_parts.append(data)
            return
        text = data.strip()
        if text:
            lines = _normalize_newlines(text).split("\n")
            self.parts.append("\n".join(_escape_line(line) for line in lines))

    def text(self) -> str:
        self._close_heading()  # 閉じないまま文書が終わった見出しも捨てない
        return "\n".join(self.parts)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "harness-yaml-spec-fetcher/1.0"}
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
        return resp.read().decode("utf-8", errors="replace")


def truncate_at_heading(text: str, limit: int, reason: str) -> str:
    """limit 字に収まらなければ、収まる最後の見出しの手前で切り、切った旨の行を足す。

    見出しの境界が無ければ行の境界、1 行目から収まらなければ字の境界で切る。見出しの境界で
    切ると上限の MIN_HEADING_CUT_SHARE も残らないときも、行の境界で切る。
    """
    if len(text) <= limit:
        return text
    lines = text.split("\n")
    heading_cut = line_cut = heading_cut_len = 0
    kept_len = -1  # "\n".join(lines[:i]) の長さ。i=0 は空
    for i, line in enumerate(lines):
        if kept_len > limit:
            break
        if i > 0:
            line_cut = i
            if HEADING_RE.match(line):
                heading_cut, heading_cut_len = i, kept_len
        kept_len += len(line) + 1
    if heading_cut and heading_cut_len >= limit * MIN_HEADING_CUT_SHARE:
        kept, boundary = "\n".join(lines[:heading_cut]), "a heading"
    elif line_cut:
        kept, boundary = "\n".join(lines[:line_cut]), "a line"
    else:
        kept, boundary = text[:limit], "a character"
    kept = kept.rstrip("\n")
    marker = f"[truncated: kept {len(kept)} of {len(text)} chars at {boundary} boundary; {reason}]"
    return f"{kept}\n\n{marker}"


def extract_body(html_doc: str, max_chars: int | None = None,
                 reason: str = DEFAULT_TRUNCATION_REASON) -> str:
    parser = TextExtractor()
    parser.feed(html_doc)
    limit = MAX_BODY_CHARS if max_chars is None else max_chars
    return truncate_at_heading(parser.text(), limit, reason)


def extract_markdown(md_doc: str, max_chars: int | None = None,
                     reason: str = DEFAULT_TRUNCATION_REASON) -> str:
    """raw markdown の見出しを docs ページと同じ深さに揃える (`## 2.1.0` → `#### 2.1.0`)。

    fence は CommonMark と同じく、開いた印と同じ文字で同じか長い印、info string の無い行でだけ
    閉じる (```` の中の ``` で閉じたことにして、中の `## …` を見出しにしない)。
    """
    out = []
    fence: tuple[str, int] | None = None  # 開いている fence の (印の文字, 印の長さ)
    for line in _normalize_newlines(md_doc).split("\n"):
        mark = FENCE_RE.match(line)
        if mark:
            ticks, info = mark.group(1), mark.group(2)
            if fence is None:
                fence = (ticks[0], len(ticks))
                out.append(line)
                continue
            if ticks[0] == fence[0] and len(ticks) >= fence[1] and not info.strip():
                fence = None
                out.append(line)
                continue
        match = None if fence is not None else MD_HEADING_RE.match(line)
        out.append(heading_line(len(match.group(1)), match.group(2)) if match else _escape_line(line))
    limit = MAX_BODY_CHARS if max_chars is None else max_chars
    return truncate_at_heading("\n".join(out).strip("\n"), limit, reason)


def extract_source(name: str, url: str, raw: str) -> str:
    limit = SOURCE_MAX_CHARS.get(name)
    reason = TRUNCATION_REASONS.get(name, DEFAULT_TRUNCATION_REASON)
    if url.endswith(".md"):
        return extract_markdown(raw, limit, reason)
    return extract_body(raw, limit, reason)


def _split_stamp(text: str) -> tuple[str | None, list[str]]:
    """(last_fetched の値, last_fetched 行を除いた本文行) を返す。"""
    stamp = None
    body = []
    for line in text.splitlines():
        if line.startswith("last_fetched:"):
            stamp = line.partition(":")[2].strip()
        else:
            body.append(line)
    return stamp, body


def _parse_stamp(stamp: str | None) -> datetime.datetime | None:
    if stamp is None:
        return None
    try:
        return datetime.datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def keep_previous(prev_text: str, new_text: str, now: datetime.datetime) -> bool:
    """本文が同じで前回の last_fetched がまだ新しいとき True (= 書き換えない)。"""
    prev_stamp, prev_body = _split_stamp(prev_text)
    if prev_stamp is None or prev_body != _split_stamp(new_text)[1]:
        return False
    fetched = _parse_stamp(prev_stamp)
    if fetched is None:
        return False
    return now - fetched < datetime.timedelta(days=REFRESH_AFTER_DAYS)


# ── 索引 ──────────────────────────────────────────────────────────────────
def index_path_for(cache_path: pathlib.Path) -> pathlib.Path:
    return cache_path.with_name(INDEX_NAME)


def _bytes_of(lines: list[str]) -> int:
    return sum(len(line.encode("utf-8")) + 1 for line in lines)


def build_index(raw: bytes) -> dict:
    """cache の bytes だけから索引を作る (同じ cache からは必ず同じ索引になる)。"""
    lines = raw.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # 末尾の改行は行を作らない (Read・awk の数え方に合わせる)
    last_fetched = None
    starts = []  # (line_no, name, url)
    for no, line in enumerate(lines, 1):
        match = SECTION_RE.match(line)
        if match:
            starts.append((no, match.group(1), match.group(2)))
        elif not starts and last_fetched is None and line.startswith("last_fetched:"):
            last_fetched = line.partition(":")[2].strip()
    sections, headings = [], {}
    for k, (start, name, url) in enumerate(starts):
        end = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(lines)
        body = lines[start:end]  # 節の見出し行の次から
        filled = [line for line in body if line.strip()]
        trunc = TRUNCATED_RE.match(filled[-1]) if filled else None
        found = []  # [level, start_line, title]
        for offset, line in enumerate(body):
            match = HEADING_RE.match(line)
            if match:
                found.append([len(match.group(1)) - HEADING_OFFSET, start + 1 + offset, match.group(2).strip()])
        rows = []
        for j, (level, h_start, title) in enumerate(found):
            h_end = end
            for later_level, later_start, _ in found[j + 1:]:
                if later_level <= level:
                    h_end = later_start - 1
                    break
            rows.append([level, h_start, h_end, _bytes_of(lines[h_start - 1:h_end]), title])
        sections.append({
            "name": name,
            "url": url,
            "start_line": start,
            "end_line": end,
            "bytes": _bytes_of(lines[start - 1:end]),
            "truncated": trunc is not None,
            "truncation": trunc.group(1) if trunc else None,
            "fetch_failed": bool(filled) and filled[0].startswith(FETCH_FAILED_PREFIX),
            "headings": len(rows),
        })
        headings[name] = rows
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "cache": OUT_PATH.name,
        "cache_sha256": hashlib.sha256(raw).hexdigest(),
        "last_fetched": last_fetched,
        "line_numbers": INDEX_LINE_NOTE,
        "sections": sections,
        "heading_columns": HEADING_COLUMNS,
        "headings": headings,
    }


def render_index(index: dict) -> str:
    """節の表を先頭に 1 節 1 行で置き、見出しは後ろに 1 見出し 1 行で置く。

    索引の先頭 20 行ほどを読めば、どの節が何行目から何行目かが分かる。
    """
    def dump(value) -> str:
        return json.dumps(value, ensure_ascii=False)

    out = ["{"]
    for key in ("schema_version", "cache", "cache_sha256", "last_fetched", "line_numbers"):
        out.append(f"  {dump(key)}: {dump(index[key])},")
    rows = ",\n".join(f"    {dump(section)}" for section in index["sections"])
    out.append('  "sections": [' + (f"\n{rows}\n  ]," if rows else "],"))
    out.append(f'  "heading_columns": {dump(index["heading_columns"])},')
    blocks = []
    for name, items in index["headings"].items():
        lines = ",\n".join(f"      {dump(item)}" for item in items)
        blocks.append(f"    {dump(name)}: " + (f"[\n{lines}\n    ]" if lines else "[]"))
    out.append('  "headings": {' + ("\n" + ",\n".join(blocks) + "\n  }" if blocks else "}"))
    out.append("}")
    return "\n".join(out) + "\n"


def _new_file_mode() -> int:
    current = os.umask(0)
    os.umask(current)
    return 0o666 & ~current  # write_bytes で新しく作ったときと同じ mode


def _write_atomically(files: list[tuple[pathlib.Path, bytes]]) -> None:
    """全部を同じ dir の一時ファイルに書き切ってから、順に os.replace で置き換える。

    途中で落ちても半端に書かれたファイルは残らない。cache と索引は 2 回の rename の間だけ
    食い違いうるが、索引の cache_sha256 で読む側が気付ける。
    """
    staged: list[tuple[str, pathlib.Path]] = []
    try:
        for path, data in files:
            target = pathlib.Path(os.path.realpath(path))  # write_bytes と同じく symlink の先へ書く
            mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else _new_file_mode()
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
            staged.append((tmp, target))
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, mode)
        for tmp, target in staged:
            os.replace(tmp, target)
    finally:
        for tmp, _ in staged:
            if os.path.lexists(tmp):  # 置き換え済みのものはもう無い
                os.unlink(tmp)


def write_index(raw: bytes, cache_path: pathlib.Path) -> pathlib.Path:
    path = index_path_for(cache_path)
    _write_atomically([(path, render_index(build_index(raw)).encode("utf-8"))])
    return path


class InvalidCacheError(Exception):
    """既存の cache を読めない (読み込みの失敗・UTF-8 でない)。exit 1。"""


def _read_cache(path: pathlib.Path) -> bytes:
    """既存の cache の bytes を返す。UTF-8 として読めなければ InvalidCacheError。"""
    try:
        raw = path.read_bytes()
        raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidCacheError(
            f"{_display(path)} を読めない ({type(exc).__name__}: {exc})。"
            "cache は UTF-8 で、この script が書いた形である必要がある。git の版に戻すこと"
        ) from exc
    return raw


def _previous_bodies(prev_raw: bytes) -> dict[tuple[str, str], str]:
    """前回の cache の節の本文を (name, url) で引けるようにする。取得に失敗していた節・空の節は入れない。

    main が書く節の形 (見出し行・空行・本文・空行) を逆にたどるので、そのまま書き戻すと同じ行になる。
    """
    if not prev_raw:
        return {}
    lines = prev_raw.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # build_index と同じ数え方にする
    sections = build_index(prev_raw)["sections"]
    bodies = {}
    for k, section in enumerate(sections):
        if section["fetch_failed"]:
            continue
        body = lines[section["start_line"]:section["end_line"]]
        if body and body[0] == "":
            body = body[1:]
        if k + 1 < len(sections) and body and body[-1] == "":
            body = body[:-1]  # 次の節の見出しの前の空行 (最後の節には無い)
        text = "\n".join(body)
        if text.strip():
            bodies[(section["name"], section["url"])] = text
    return bodies


def _display(path: pathlib.Path) -> pathlib.Path:
    """repo の中の path は repo root からの相対で出す (以前の cwd 相対の表示と同じになる)。"""
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


class _ArgumentParser(argparse.ArgumentParser):
    """使い方の誤りを exit 1 にする (argparse の既定 2 は取得失敗の 2 と重なる)。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def _report_truncated(raw: bytes) -> None:
    for section in build_index(raw)["sections"]:
        if section["truncated"]:
            note = f"{section['name']}: {section['truncation']}"
            if section["name"] in TRUNCATION_REASONS:
                print(f"truncated (expected) {note}")
            else:
                # GitHub Actions の画面に出す。週次ジョブは止めず、上限の見直しを促す
                print(f"::warning::yaml-spec-cache truncated {note}")


def main(argv: list[str] | tuple = ()) -> int:
    parser = _ArgumentParser(description="Claude Code 公式仕様ページの cache と索引を作る")
    parser.add_argument("--reindex", action="store_true",
                        help="ネットに出ず、既存の cache から索引だけを作り直す")
    args = parser.parse_args(list(argv))
    out_path = OUT_PATH

    if args.reindex:
        if not out_path.exists():
            print(f"ERROR: {_display(out_path)} が無い。先に取得すること", file=sys.stderr)
            return EXIT_USAGE
        try:
            raw = _read_cache(out_path)
        except InvalidCacheError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return EXIT_USAGE
        path = write_index(raw, out_path)
        print(f"reindexed {_display(path)} from {_display(out_path)}")
        return EXIT_OK

    # 前回の cache は取得の前に確かめる (読めない cache を黙って上書きしない・無駄に取得しない)
    try:
        prev_raw = _read_cache(out_path) if out_path.exists() else b""
    except InvalidCacheError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USAGE
    prev_text = prev_raw.decode("utf-8")
    prev_bodies = _previous_bodies(prev_raw)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    sections = []
    failures = kept = 0
    for name, url in SOURCES:
        try:
            raw_doc = fetch(url)
        except FETCH_ERRORS as exc:
            failures += 1
            reason = f"{type(exc).__name__}: {' '.join(str(exc).split())}"  # 1 行に収める
            previous = prev_bodies.get((name, url))
            if previous is None:
                body = f"{FETCH_FAILED_PREFIX} {reason}"
                print(f"FETCH_FAILED {name}: {reason}", file=sys.stderr)
            else:
                body = previous
                kept += 1
                print(f"FETCH_FAILED {name}: {reason}; kept the previous body", file=sys.stderr)
        else:
            body = extract_source(name, url, raw_doc)
        sections += [f"## Source ({name}): {url}", "", body, ""]
    # 前回の本文を残した節があるときは、last_fetched を前回の値のままにする (残した本文より新しい
    # 日時を付けない)。前回の値が無い・日時として読めなければ今の日時
    prev_stamp = _split_stamp(prev_text)[0] if kept else None
    stamp = prev_stamp if _parse_stamp(prev_stamp) else now_dt.strftime(STAMP_FORMAT)
    lines = [
        "# YAML Spec Cache",
        "",
        f"last_fetched: {stamp}",
        "fetcher: scripts/build-yaml-spec-cache.py",
        "",
        *sections,
    ]
    text = "\n".join(lines)
    status = EXIT_OK if failures == 0 else EXIT_FETCH_FAILED
    if keep_previous(prev_text, text, now_dt):
        # cache も索引も触らない (索引は cache から決まるので、cache が同じなら作り直す必要も無い)。
        # 取得に失敗した source があれば、書き換えなくても exit 2 にする
        print(f"unchanged {_display(out_path)} (sources={len(SOURCES)}, failures={failures})")
        return status
    raw = text.encode("utf-8")
    index_path = index_path_for(out_path)
    # 索引は cache の置き換えより前に作る (索引を作れずに cache だけ新しくなる、を起こさない)
    _write_atomically([
        (out_path, raw),
        (index_path, render_index(build_index(raw)).encode("utf-8")),
    ])
    print(f"wrote {_display(out_path)} (sources={len(SOURCES)}, failures={failures})")
    print(f"wrote {_display(index_path)}")
    _report_truncated(raw)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
