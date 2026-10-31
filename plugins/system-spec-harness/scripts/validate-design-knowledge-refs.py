#!/usr/bin/env python3
# /// script
# name: validate-design-knowledge-refs
# version: 0.3.0
# purpose: spec-state の design_applications[].knowledge_ref が実在の知識カードを指すことを検証する決定論ゲート。validate-coverage-matrix.py は形状しか見ないため、存在しない card や見出しを引用したまま緑になる穴を塞ぐ。
# inputs:
#   - argv: --matrix SPEC_STATE_JSON [--repo-root PATH] [--json]
# outputs:
#   - stdout: VIOLATION 行と OK/FAIL summary (--json 時は {checked, findings})
#   - exit: 0=OK / 1=violation / 2=input error
#   - Python API: resolve_knowledge_path / headings (writer の fix-qa-knowledge-ref が同じ解決規則で実在を判定する)
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""``design_applications[].knowledge_ref`` の参照先実在を検証する決定論ゲート。

``validate-coverage-matrix.py`` は design_applications の**形状** (具体原則・採否・章固有理由・
非空 trade-off) を検査するが、``knowledge_ref`` が実在の知識カードを指すかは見ていない。
そのため存在しないファイルや綴り違いのファイル名を参照したまま緑になる。参照先が無い設計解釈は
「C04 の deep card / doctrine anchor に基づいて判断した」という主張の根拠を持たないため、
形状だけ揃った空の引用として通してしまう。

検査対象:
  1. ``knowledge_ref`` の path 部 (``#`` の手前) が repo root 配下に実在すること
  2. path が repo root の外を指さないこと (絶対 path / ``..`` を拒否)
  3. anchor 部 (``#`` の後ろ) がある場合、その見出しが参照先 Markdown に実在すること

解決規則: path はまず repo root 起点で解決する。C04 deep card は harness repo の配置
``plugins/<本 plugin 名>/...`` で書き、repo root に無い場合 (plugin を別の場所へ install した
利用側 repo) に限り、本 script が属する plugin root 起点で解決し直す。他 plugin の prefix は
読み替えない。spec-state の writer (``apply-spec-transition.py fix-qa-knowledge-ref``) も
``resolve_knowledge_path`` / ``headings`` で実在を判定し、validator と writer の判定をずらさない。

使い方:
  python3 validate-design-knowledge-refs.py --matrix <spec-state.json> [--repo-root PATH] [--json]

exit code: 0 = 違反なし / 1 = 違反あり / 2 = 入力エラー
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _plugin_prefix() -> PurePosixPath | None:
    try:
        name = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["name"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return PurePosixPath("plugins", name) if isinstance(name, str) and name else None


PLUGIN_PREFIX = _plugin_prefix()


def _is_safe_relative(value: str) -> bool:
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and str(path) not in {"", "."}


def headings(text: str) -> set[str]:
    return {m.group(1).strip() for m in HEADING_RE.finditer(text)}


def resolve_knowledge_path(raw_path: str, repo_root: Path) -> Path | None:
    target = repo_root / raw_path
    if target.is_file():
        return target
    path = PurePosixPath(raw_path)
    if PLUGIN_PREFIX is not None and path.parts[: len(PLUGIN_PREFIX.parts)] == PLUGIN_PREFIX.parts:
        fallback = PLUGIN_ROOT.joinpath(*path.parts[len(PLUGIN_PREFIX.parts):])
        if fallback.is_file():
            return fallback
    return None


def collect_findings(state: dict, repo_root: Path) -> list[str]:
    findings: list[str] = []
    heading_cache: dict[Path, set[str]] = {}

    for entry in state.get("qa_log", []) or []:
        qa_id = entry.get("id", "<no-id>")
        for i, application in enumerate(entry.get("design_applications") or []):
            if not isinstance(application, dict):
                continue
            ref = application.get("knowledge_ref")
            where = f"qa_log[{qa_id}].design_applications[{i}].knowledge_ref"
            if not isinstance(ref, str) or not ref.strip():
                findings.append(f"{where}: 非空文字列必須")
                continue

            raw_path, _, anchor = ref.partition("#")
            raw_path = raw_path.strip()
            if not _is_safe_relative(raw_path):
                findings.append(f"{where}: repo root 配下の安全な相対パス必須: {raw_path!r}")
                continue

            target = resolve_knowledge_path(raw_path, repo_root)
            if target is None:
                findings.append(f"{where}: 参照先が実在しない: {raw_path}")
                continue

            anchor = anchor.strip()
            if not anchor:
                continue
            if target not in heading_cache:
                try:
                    heading_cache[target] = headings(target.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError) as exc:
                    findings.append(f"{where}: 参照先を読めない: {raw_path}: {exc}")
                    heading_cache[target] = set()
            if anchor not in heading_cache[target]:
                findings.append(f"{where}: 見出しが参照先に存在しない: {raw_path}#{anchor}")

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix", required=True, help="spec-state.json")
    parser.add_argument("--repo-root", default=".", help="knowledge_ref を解決する基準 (既定: cwd)。plugins/<本 plugin 名>/ で始まる path は、ここに無ければ本 plugin root で解決する")
    parser.add_argument("--json", action="store_true", help="findings を JSON で出力")
    args = parser.parse_args(argv)

    matrix_path = Path(args.matrix)
    repo_root = Path(args.repo_root).resolve()
    try:
        state = json.loads(matrix_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: spec-state を読めない: {matrix_path}: {exc}", file=sys.stderr)
        return 2

    findings = collect_findings(state, repo_root)
    checked = sum(
        len(e.get("design_applications") or [])
        for e in state.get("qa_log", []) or []
    )

    if args.json:
        print(json.dumps({"checked": checked, "findings": findings}, ensure_ascii=False, indent=2))
    else:
        for finding in findings:
            print(f"VIOLATION: {finding}")
        if findings:
            print(f"FAIL: design knowledge_ref 違反 {len(findings)} 件 (検査 {checked} 件)")
        else:
            print(f"OK: design knowledge_ref は全て実在する (検査 {checked} 件)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
