#!/usr/bin/env python3
"""plugin の中に、親ディレクトリ起点で兄弟 plugin を指すパスが無いことを静的検査する (fail-closed)。

なぜ:
  repo では plugins/<a>/ と plugins/<b>/ が隣り合うので `../<b>/...` で兄弟に届く。
  しかし install 先は `<cache>/<marketplace>/<plugin>/<version>/` (Claude は ~/.claude/plugins/cache、
  Codex は ~/.codex/plugins/cache) で、`<plugin root>/..` は同じ plugin の別 version 群を指す。
  親ディレクトリ起点の兄弟パスは install した利用者の環境でだけ壊れ、repo の CI では緑のまま残る。

検出する形 (兄弟 plugin 名 = plugins/*/.claude-plugin/plugin.json を持つディレクトリ名):
  dotdot    `../` を 1 つ以上重ねた直後に兄弟 plugin 名 (`../../../harness-creator/...`)
  dirname   shell の `$(dirname "$PLUGIN_ROOT")/<name>` (親ディレクトリ起点)
  pyparent  Python の `.parent / "<name>"` と `.parents[N] / "<name>"` (改行をまたいでも検出)
  osjoin    `os.path.join(..., "..", "<name>")`

検出しない (許容):
  - 自 plugin の名前 (repo root の検出や自己説明で、兄弟参照ではない)
  - `$schema` の metadata 値と、plugin-composition.yaml の `# 正本スキーマ:` 注記行
    (editor 向けの注記で、runtime は解決しない)
  - `rubric_refs:` 直下のリスト項目 (lint-rubric-refs-exist.py が skill 起点で解決する別契約)
  - README.md / CHANGELOG.md / EVALS.json と、tests/・eval-log/ 配下 (repo での開発・評価用)
  - repo root 起点の `"plugins" / "<name>"` (対象 repo を検査する governance ツールでは正当なため。
    install 先で使う script がこの形を使っていないかは、この lint では見ない)

直し方 (どれを選ぶかは参照の種類で決まる):
  - 実行するコマンド: `SIBLING_ROOT="$(python3 "$PLUGIN_ROOT/scripts/extract-plugin-root.py" <name>)" && python3 "$SIBLING_ROOT/scripts/..."`
    Python からは同梱の scripts/extract-plugin-root.py を importlib で読み、resolve() を呼ぶ
  - resource-map などのメタデータ: `plugin:<name>/<path>` 記法
  - 本文の引用: 「<name> plugin の `<path>` (出典表記)」
  - repo-bundled 前提の plugin と frontmatter の *_refs: `plugins/<name>/...` (repo root 起点)
  - 小さい runtime 資産: 自 plugin へ同梱し、scripts/lint-vendored-ssot.py で byte 一致を強制する

Usage:
  python3 scripts/lint-sibling-plugin-paths.py [--root <repo root>] [--json]

Exit 0 = 該当なし, 1 = 該当あり, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCANNED_SUFFIXES = {
    ".md", ".json", ".yaml", ".yml", ".py", ".sh", ".js", ".cjs", ".mjs", ".toml", ".txt",
}
SKIPPED_DIRS = {"tests", "eval-log", "node_modules", "__pycache__", ".git"}
SKIPPED_FILES = {"README.md", "CHANGELOG.md", "EVALS.json"}
# 値の範囲だけを除外し、同じ JSON 行の runtime command まで免除しない。
SCHEMA_VALUE_RE = re.compile(r'''(?:^|[,{])\s*["']?\$schema["']?\s*:\s*(?:"(?P<double>(?:\\.|[^"\\])*)"|'(?P<single>[^']*)'|(?P<plain>[^\s,}\n]+))''', re.MULTILINE)
SCHEMA_COMMENT_RE = re.compile(r"^\s*# 正本スキーマ:")
RUBRIC_REFS_KEY_RE = re.compile(r"^\s*rubric_refs:\s*(?:#.*)?$")
LIST_ITEM_RE = re.compile(r"^\s*-\s")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    sibling: str
    excerpt: str


def plugin_names(root: Path) -> list[str]:
    """plugin manifest を持つディレクトリ名を返す。一覧を手書きしないので plugin の追加に追随する。"""
    return sorted(
        manifest.parents[1].name
        for manifest in root.glob("plugins/*/.claude-plugin/plugin.json")
    )


def compile_patterns(names: list[str]) -> dict[str, re.Pattern[str]]:
    # 長い名前から試し、`skill-governance-lint` を `skill-governance` などで部分一致させない。
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return {
        "dotdot": re.compile(rf"(?:\.\./)+(?P<name>{alt})(?![\w-])"),
        "dirname": re.compile(rf"dirname[^\n]*?ROOT[^\n]*?\)\"?/(?P<name>{alt})(?![\w-])"),
        "pyparent": re.compile(rf"\.parent(?:s\[\d+\])?\s*/\s*[\"'](?P<name>{alt})[\"']"),
        "osjoin": re.compile(rf"[\"']\.\.[\"']\s*,\s*[\"'](?P<name>{alt})[\"']"),
    }


def _in_rubric_refs(lines: list[str], index: int) -> bool:
    """index 行が `rubric_refs:` 直下の連続したリスト項目に属するか。"""
    if not LIST_ITEM_RE.match(lines[index]):
        return False
    cursor = index - 1
    while cursor >= 0 and LIST_ITEM_RE.match(lines[cursor]):
        cursor -= 1
    return cursor >= 0 and bool(RUBRIC_REFS_KEY_RE.match(lines[cursor]))


def scan_text(
    text: str,
    self_name: str,
    patterns: dict[str, re.Pattern[str]],
    rel_path: str = "<text>",
) -> list[Finding]:
    """1 ファイル分の本文を走査する。改行をまたぐ書き方を拾うため、行ではなく全文に照合する。"""
    lines = text.splitlines()
    schema_values = [
        match.span(group)
        for match in SCHEMA_VALUE_RE.finditer(text)
        for group in ("double", "single", "plain")
        if match.group(group) is not None
    ]
    findings: list[Finding] = []
    for kind, pattern in patterns.items():
        for match in pattern.finditer(text):
            name = match.group("name")
            if name == self_name:
                continue
            # 一致の末尾 (兄弟名) がある行を報告する。pyparent は `.parents[N]` の行から始まりうる。
            index = text.count("\n", 0, match.end())
            line = lines[index] if index < len(lines) else ""
            if any(start <= match.start() and match.end() <= end for start, end in schema_values):
                continue
            if SCHEMA_COMMENT_RE.match(line):
                continue
            if _in_rubric_refs(lines, index):
                continue
            findings.append(Finding(rel_path, index + 1, kind, name, line.strip()[:160]))
    return sorted(findings, key=lambda f: (f.line, f.kind))


def iter_plugin_files(plugin_dir: Path):
    for dirpath, dirnames, filenames in os.walk(plugin_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIPPED_DIRS)
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if filename in SKIPPED_FILES or path.suffix not in SCANNED_SUFFIXES:
                continue
            yield path


def scan(root: Path) -> list[Finding]:
    names = plugin_names(root)
    if not names:
        return []
    patterns = compile_patterns(names)
    findings: list[Finding] = []
    for name in names:
        for path in iter_plugin_files(root / "plugins" / name):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(root).as_posix()
            findings.extend(scan_text(text, name, patterns, rel))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="repo root (既定: この script の 2 階層上)")
    parser.add_argument("--json", action="store_true", help="findings を JSON で stdout へ出す")
    args = parser.parse_args(argv)
    if not (args.root / "plugins").is_dir():
        print(f"[lint-sibling-plugin-paths] plugins/ が見つからない: {args.root}", file=sys.stderr)
        return 2
    findings = scan(args.root)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    if findings:
        print("[lint-sibling-plugin-paths] FAIL: 親ディレクトリ起点で兄弟 plugin を指すパス", file=sys.stderr)
        for f in findings:
            print(f"  - {f.path}:{f.line} [{f.kind}] {f.sibling}: {f.excerpt}", file=sys.stderr)
        print(
            "  install 先 (<cache>/<marketplace>/<plugin>/<version>/) では `..` が兄弟に届かない。"
            " 直し方は scripts/lint-sibling-plugin-paths.py の docstring を参照。",
            file=sys.stderr,
        )
        return 1
    if not args.json:
        print("[lint-sibling-plugin-paths] OK: 親ディレクトリ起点の兄弟 plugin 参照なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
