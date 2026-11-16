#!/usr/bin/env python3
# /// script
# name: extract-yaml-spec-section
# purpose: 公式仕様 cache (yaml-spec-cache.md) のうち、生成する kind に要る節だけを索引 (yaml-spec-index.json) から引き、trace に貼る根拠の 1 行と Read の offset/limit を出す
# inputs:
#   - argv: --kind <capability kind か skill subtype> と --section <source>[:<heading>] (繰り返し可) の少なくとも一方。--list [source] は節・見出しの一覧。--print で本文も出す。--cache/--index で既定パスを上書き
# outputs:
#   - stdout: 1 行目は「yaml-spec-source: {json}」(trace の 15/16 章 coverage に貼る根拠)。続けて節ごとに Read の offset/limit。--print のときは本文
#   - stderr: 切り詰められた節の警告・エラーの理由
#   - exit: 0=OK / 1=索引に無い節や見出し・見出しが 2 つ以上ある・未知の kind・usage error / 2=cache か索引が無い・読めない (UTF-8 でないを含む)・索引の形が壊れている・cache と索引の sha256 が食い違う・索引の行範囲が cache や節の境界と合わない・要る節の取得に失敗している
# requires-python: ">=3.10"
# dependencies: []
# contexts: [A, C]
# network: false
# write-scope: none
# ///
"""kind ごとに読む公式仕様の節を 1 か所で決め、索引から行範囲を引く。

cache は 1MB 近くあり、全文は読まない。索引は cache の bytes だけから決まるので、
sha256 が食い違えば索引は古い (cache を手で直したか、索引の書き忘れ)。そのときは
行範囲を信じずに止める。直し方は harness repo で
`python3 scripts/build-yaml-spec-cache.py --reindex`。

sha256 は cache の bytes を縛るだけで、索引そのものは縛らない。そこで索引の形 (型と列数) と、
行範囲が節の境界に収まることも確かめる。行の数え方は索引を作る側 (build_index) に合わせ、
末尾の改行は行を作らない。

既定の cache と索引は、この script から見た ../../ref-yaml-spec-fetcher/references/ に
ある (plugin root を cwd や repo からの相対位置で推測しない)。
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

REFERENCES = Path(__file__).resolve().parents[2] / "ref-yaml-spec-fetcher" / "references"
DEFAULT_CACHE = REFERENCES / "yaml-spec-cache.md"
DEFAULT_INDEX = REFERENCES / "yaml-spec-index.json"
SUPPORTED_SCHEMA_VERSIONS = {1}
REINDEX_HINT = "harness repo で `python3 scripts/build-yaml-spec-cache.py --reindex` を実行して索引を作り直す"

# kind → 読む節。各要素は (source, heading)。heading が None なら節全体。
# 見出しは索引の title と完全一致で引く (公式 docs の見出しの改名は exit 1 で表に出る)。
KIND_SECTIONS: dict[str, tuple[tuple[str, str | None], ...]] = {
    "skill": (("skills", "Frontmatter reference"),),
    # custom command は skills に統合された (同じ frontmatter を使う)。
    "command": (("skills", "Frontmatter reference"),),
    # tools / permissionMode / mcpServers / skills / memory は「Control subagent capabilities」にある。
    "agent": (
        ("subagents", "Frontmatter reference"),
        ("subagents", "Control subagent capabilities"),
    ),
    # 個別の event の入出力は「Hook events」の下にある。生成する event だけ
    # --section hooks:<event 名> で足す (Hook events 全体は 14 万字を超える)。
    "hook": (
        ("hooks", "Configuration"),
        ("hooks", "Hook input and output"),
    ),
    "plugin-composition": (("plugins-reference", None),),
    "prompt": (),
    "workflow": (),
}
# 公式 docs に対応する節が無い kind と、その理由 (trace の根拠の 1 行に残す)。
NOT_APPLICABLE = {
    "prompt": "harness 独自の prompts/<name>.md で、Claude Code 公式 docs に対応する仕様が無い",
    "workflow": "harness 独自の workflows/<name>.md で、Claude Code 公式 docs に対応する仕様が無い",
}
# 後方互換の skill subtype (build-flags.schema.json の kind)。capability kind の skill として扱う。
SKILL_SUBTYPES = {"run", "ref", "assign", "wrap", "delegate"}


class SpecError(Exception):
    """exit code を持つエラー。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # usage error は 1 (2 は cache の問題に使う)
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(1)


def normalize_kind(kind: str) -> str:
    if kind in SKILL_SUBTYPES:
        return "skill"
    if kind not in KIND_SECTIONS:
        known = ", ".join(sorted(KIND_SECTIONS) + sorted(SKILL_SUBTYPES))
        raise SpecError(1, f"未知の kind: {kind} (使える kind: {known})")
    return kind


def parse_section_arg(value: str) -> tuple[str, str | None]:
    source, sep, heading = value.partition(":")
    source = source.strip()
    if not source:
        raise SpecError(1, f"--section の source が空: {value!r}")
    if not sep:
        return source, None
    heading = heading.strip()
    if not heading:
        raise SpecError(1, f"--section の見出しが空: {value!r} (節全体なら ':' を付けない)")
    return source, heading


def _is_line_no(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _check_index_shape(index: dict, index_path: Path) -> None:
    """索引の型と列数を確かめる。壊れていれば SpecError(2) (KeyError や TypeError で落とさない)。"""

    def broken(what: str) -> SpecError:
        return SpecError(2, f"索引の形が壊れている: {index_path} ({what}); {REINDEX_HINT}")

    sections = index.get("sections")
    if not isinstance(sections, list):
        raise broken("sections が配列でない")
    for i, section in enumerate(sections):
        if not isinstance(section, dict) or not isinstance(section.get("name"), str):
            raise broken(f"sections[{i}] に name が無い")
        if not (_is_line_no(section.get("start_line")) and _is_line_no(section.get("end_line"))):
            raise broken(f"sections[{i}] の start_line/end_line が正の整数でない")
        if not isinstance(section.get("bytes"), int) or isinstance(section.get("bytes"), bool):
            raise broken(f"sections[{i}] の bytes が整数でない")
    headings = index.get("headings")
    if not isinstance(headings, dict):
        raise broken("headings が object でない")
    for source, rows in headings.items():
        if not isinstance(rows, list):
            raise broken(f"headings.{source} が配列でない")
        for j, row in enumerate(rows):
            ok = (isinstance(row, list) and len(row) == 5 and isinstance(row[0], int)
                  and _is_line_no(row[1]) and _is_line_no(row[2])
                  and isinstance(row[3], int) and isinstance(row[4], str))
            if not ok:
                raise broken(f"headings.{source}[{j}] が [level, start_line, end_line, bytes, title] でない")


def load(cache_path: Path, index_path: Path) -> tuple[dict, list[str]]:
    """索引と cache の行を返す。食い違えば SpecError(2)。"""
    try:
        raw = cache_path.read_bytes()
    except OSError as exc:
        raise SpecError(2, f"cache を読めない: {cache_path} ({exc.__class__.__name__})") from exc
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SpecError(2, f"索引を読めない: {index_path} ({exc.__class__.__name__}); {REINDEX_HINT}") from exc
    except UnicodeDecodeError as exc:
        raise SpecError(2, f"索引が UTF-8 でない: {index_path}; {REINDEX_HINT}") from exc
    except json.JSONDecodeError as exc:
        raise SpecError(2, f"索引が JSON として読めない: {index_path} ({exc}); {REINDEX_HINT}") from exc
    if not isinstance(index, dict) or index.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        raise SpecError(2, f"索引の schema_version が未対応: {index_path}; {REINDEX_HINT}")
    actual = hashlib.sha256(raw).hexdigest()
    if index.get("cache_sha256") != actual:
        raise SpecError(
            2,
            f"cache と索引が食い違う (cache sha256={actual[:12]}, 索引={str(index.get('cache_sha256'))[:12]}); {REINDEX_HINT}",
        )
    _check_index_shape(index, index_path)
    try:
        lines = raw.decode("utf-8").split("\n")
    except UnicodeDecodeError as exc:
        raise SpecError(2, f"cache が UTF-8 でない: {cache_path}") from exc
    if lines and lines[-1] == "":
        lines.pop()  # 索引を作る側と同じく、末尾の改行は行を作らない
    return index, lines


def _section_of(index: dict, source: str) -> dict:
    for section in index.get("sections", []):
        if section.get("name") == source:
            return section
    names = ", ".join(s.get("name", "?") for s in index.get("sections", []))
    raise SpecError(1, f"索引に節が無い: {source} (ある節: {names})")


def resolve(index: dict, lines: list[str], source: str, heading: str | None) -> dict:
    """(source, heading) を索引で引き、cache の行と突き合わせた範囲を返す。"""
    section = _section_of(index, source)
    if section.get("fetch_failed"):
        raise SpecError(2, f"節 {source} は取得に失敗した状態で cache にある (FETCH_FAILED)。取り直しが要る")
    sec_start, sec_end = section["start_line"], section["end_line"]
    if not (sec_start <= sec_end <= len(lines)):
        raise SpecError(2, f"索引の行範囲が cache の外: {source} L{sec_start}-{sec_end}; {REINDEX_HINT}")
    if not lines[sec_start - 1].startswith(f"## Source ({source}): "):
        raise SpecError(2, f"索引の行範囲が cache と合わない: {source} L{sec_start}; {REINDEX_HINT}")
    # 節の終わりは次の節の見出しの直前か cache の末尾。そうでなければ範囲が隣の節へはみ出すか、途中で切れる。
    if any(line.startswith("## Source (") for line in lines[sec_start:sec_end]):
        raise SpecError(2, f"索引の節の範囲が隣の節へはみ出す: {source} L{sec_start}-{sec_end}; {REINDEX_HINT}")
    if sec_end < len(lines) and not lines[sec_end].startswith("## Source ("):
        raise SpecError(2, f"索引の節の終わりが cache の節の境界と合わない: {source} L{sec_end}; {REINDEX_HINT}")
    if heading is None:
        start, end, size = sec_start, sec_end, section["bytes"]
    else:
        rows = [row for row in index.get("headings", {}).get(source, []) if row[4] == heading]
        if not rows:
            titles = [row[4] for row in index.get("headings", {}).get(source, [])]
            near = difflib.get_close_matches(heading, titles, n=3, cutoff=0.5)
            hint = f" (近い見出し: {', '.join(near)})" if near else ""
            raise SpecError(1, f"索引に見出しが無い: {source}:{heading}{hint}。--list {source} で一覧を見る")
        if len(rows) > 1:
            where = ", ".join(f"L{row[1]}-{row[2]}" for row in rows)
            raise SpecError(1, f"見出しが {len(rows)} 個ある: {source}:{heading} ({where})")
        _level, start, end, size, _title = rows[0]
        if not (sec_start < start <= end <= sec_end):
            raise SpecError(2, f"索引の見出しの範囲が節 {source} (L{sec_start}-{sec_end}) の外: {heading} L{start}-{end}; {REINDEX_HINT}")
        line = lines[start - 1]
        if not (line.startswith("#") and line.lstrip("#").strip() == heading):
            raise SpecError(2, f"索引の行範囲が cache と合わない: {source}:{heading} L{start}; {REINDEX_HINT}")
    return {
        "source": source,
        "heading": heading,
        "start_line": start,
        "end_line": end,
        "bytes": size,
        "url": section.get("url"),
        "truncated": bool(section.get("truncated")),
        "truncation": section.get("truncation"),
    }


def evidence_line(index: dict, kind: str | None, picked: list[dict]) -> str:
    """trace の 15/16 章 coverage に貼る 1 行。JSON なので後から索引と機械照合できる。"""
    payload: dict = {
        "cache": index.get("cache"),
        "last_fetched": index.get("last_fetched"),
        "cache_sha256": index.get("cache_sha256"),
        "kind": kind,
        "sections": [[p["source"], p["heading"], p["start_line"], p["end_line"]] for p in picked],
    }
    if kind in NOT_APPLICABLE and not picked:
        payload["not_applicable"] = NOT_APPLICABLE[kind]
    return "yaml-spec-source: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def render_list(index: dict, source: str | None) -> str:
    out: list[str] = []
    if not source:
        out.append(f"cache={index.get('cache')} last_fetched={index.get('last_fetched')}")
        for s in index.get("sections", []):
            flags = " truncated" if s.get("truncated") else ""
            flags += " fetch_failed" if s.get("fetch_failed") else ""
            out.append(
                f"{s['name']}\tL{s['start_line']}-{s['end_line']}\t{s['bytes']}B\t{s.get('headings', 0)} headings{flags}"
            )
        return "\n".join(out)
    _section_of(index, source)
    for level, start, end, size, title in index.get("headings", {}).get(source, []):
        out.append(f"{'  ' * (level - 2)}{title}\tL{start}-{end}\t{size}B")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="extract-yaml-spec-section.py",
        description="公式仕様 cache から kind に要る節だけを索引で引く",
    )
    parser.add_argument("--kind", help="capability kind (skill/agent/hook/command/plugin-composition/prompt/workflow) か skill subtype")
    parser.add_argument(
        "--section",
        action="append",
        default=[],
        metavar="SOURCE[:HEADING]",
        help="kind の既定に足す節 (例: hooks:PreToolUse)。繰り返し可",
    )
    parser.add_argument("--list", nargs="?", const="", default=None, metavar="SOURCE", help="節の一覧 (SOURCE を付けるとその見出しの一覧)")
    parser.add_argument("--print", action="store_true", dest="print_body", help="Read の範囲に加えて本文も出す")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    return parser


def run(args: argparse.Namespace) -> int:
    index, lines = load(args.cache, args.index)
    if args.list is not None:
        print(render_list(index, args.list or None))
        return 0
    if not args.kind and not args.section:
        raise SpecError(1, "--kind か --section のどちらかが要る (--list で一覧)")
    kind = normalize_kind(args.kind) if args.kind else None
    wanted: list[tuple[str, str | None]] = list(KIND_SECTIONS[kind]) if kind else []
    for value in args.section:
        pair = parse_section_arg(value)
        if pair not in wanted:
            wanted.append(pair)
    picked = [resolve(index, lines, source, heading) for source, heading in wanted]

    print(evidence_line(index, kind, picked))
    cache_abs = args.cache.resolve()
    for p in picked:
        label = p["source"] if p["heading"] is None else f"{p['source']}:{p['heading']}"
        limit = p["end_line"] - p["start_line"] + 1
        print(f"read: {label} -> {cache_abs} offset={p['start_line']} limit={limit} ({p['bytes']} bytes) {p['url']}")
        if p["truncated"]:
            print(f"warning: 節 {p['source']} は切り詰められている: {p['truncation']}", file=sys.stderr)
    if kind in NOT_APPLICABLE and not picked:
        print(f"read: 不要 ({NOT_APPLICABLE[kind]})")
    if args.print_body:
        for p in picked:
            label = p["source"] if p["heading"] is None else f"{p['source']}:{p['heading']}"
            print(f"\n--- {label} L{p['start_line']}-{p['end_line']} ---")
            print("\n".join(lines[p["start_line"] - 1 : p["end_line"]]))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except SpecError as exc:
        print(f"extract-yaml-spec-section: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
