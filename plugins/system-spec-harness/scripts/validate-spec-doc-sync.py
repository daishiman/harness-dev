#!/usr/bin/env python3
# /// script
# name: validate-spec-doc-sync
# version: 0.1.0
# purpose: 正本 spec-state.json と成果物 system-spec/*.md の同期を検証する決定論ゲート。既存の3ゲート (coverage / source-citation / knowledge-graph) はいずれも章 Markdown を読まないため、章が何世代遅れても全ゲートが緑になる。本ゲートはその穴を塞ぎ、正本にある上位概念 goal・根拠参照 qa_refs・取得済み出典が章へ投影されているかを検査する。
# inputs:
#   - argv: --matrix spec-state.json --references fetched-references.json --spec-root system-spec
# outputs:
#   - stdout: OK もしくは違反一覧
#   - exit: 0=同期 / 1=未同期 (未投影あり) / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none (read-only)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""spec-state.json (正本) と system-spec/*.md (成果物) の同期ゲート。

背景 — なぜこのゲートが要るか:
  coverage / source-citation / knowledge-graph の 3 ゲートは spec-state.json と
  fetched-references.json しか読まない。章 Markdown を 1 バイトも読まないため、
  正本を更新して章を再生成し忘れても全ゲートが exit0 になる。実際に
  「全ゲート緑・ただし成果物は 1 世代前」という状態が成立し、その章を入力とする
  下流 (system-dev-plan / dev-graph) は新しい goal に由来するタスクを 1 件も
  生成しないまま実装フェーズへ進んだ。measure と target が乖離する Goodhart 穴。

本ゲートが検査する 3 つの投影:
  1. goal 投影   — requirements_foundation の goal id が要件定義書と、
                   その goal を serves_goals に持つ章へ出現するか。
  2. 根拠投影   — 確定セルの qa_ref / qa_refs が当該カテゴリ章へ出現するか。
  3. 出典投影   — fetched-references の target_id がいずれかの章へ出現するか。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIREMENTS_CHAPTER = "00-requirements-definition.md"


class SyncError(Exception):
    """同期検査の入力不備 (章ディレクトリ不在など)。"""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def chapter_texts(spec_root: Path) -> dict[str, str]:
    """章ファイル名 -> 本文。spec_root 直下の *.md を読む。"""
    if not spec_root.is_dir():
        raise SyncError(f"章ディレクトリが無い: {spec_root}")
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(spec_root.glob("*.md"))}
    if not texts:
        raise SyncError(f"章 Markdown が 1 件も無い: {spec_root}")
    return texts


def chapter_serves_goals(text: str) -> set[str]:
    """章 frontmatter の serves_goals を読む。"""
    match = re.search(r"^serves_goals:\s*\[(.*?)\]\s*$", text, re.M)
    if not match:
        return set()
    return {g.strip() for g in match.group(1).split(",") if g.strip()}


def confirmed_cell_refs(spec: dict) -> dict[str, set[str]]:
    """カテゴリ -> そのカテゴリの確定セルが持つ根拠参照 (qa_ref + qa_refs) の和。"""
    out: dict[str, set[str]] = {}
    for cat, row in (spec.get("matrix") or {}).items():
        refs: set[str] = set()
        for cell in (row or {}).values():
            if not isinstance(cell, dict) or cell.get("state") != "確定":
                continue
            if cell.get("qa_ref"):
                refs.add(cell["qa_ref"])
            for ref in cell.get("qa_refs") or []:
                refs.add(ref)
        if refs:
            out[cat] = refs
    return out


def check_goal_projection(spec: dict, texts: dict[str, str]) -> list[str]:
    """goal id が要件定義書と、その goal に資する章へ投影されているか。"""
    violations: list[str] = []
    foundation = spec.get("requirements_foundation") or {}
    goal_ids = [g.get("id") for g in foundation.get("goals") or [] if g.get("id")]
    req_text = texts.get(REQUIREMENTS_CHAPTER, "")
    for gid in goal_ids:
        if gid not in req_text:
            violations.append(f"goal {gid} が {REQUIREMENTS_CHAPTER} に未投影")
    for name, text in texts.items():
        if name in (REQUIREMENTS_CHAPTER, "index.md"):
            continue
        for gid in chapter_serves_goals(text) & set(goal_ids):
            body = text.split("---", 2)[-1]
            if gid not in body:
                violations.append(
                    f"{name}: serves_goals に {gid} を宣言しているが本文に {gid} の記述が無い"
                )
    return violations


def check_evidence_projection(spec: dict, texts: dict[str, str]) -> list[str]:
    """確定セルの根拠参照が当該カテゴリ章へ投影されているか。"""
    violations: list[str] = []
    for cat, refs in confirmed_cell_refs(spec).items():
        text = texts.get(f"{cat}.md")
        if text is None:
            violations.append(f"カテゴリ {cat} の章が無い")
            continue
        for ref in sorted(refs):
            if ref not in text:
                violations.append(f"{cat}.md: 確定セルの根拠 {ref} が章に未投影")
    return violations


def check_citation_projection(refs_data: dict, texts: dict[str, str]) -> list[str]:
    """取得済み出典の target_id がいずれかの章へ投影されているか。"""
    joined = "\n".join(texts.values())
    return [
        f"出典 {tid} がどの章にも未投影"
        for tid in (r.get("target_id") for r in refs_data.get("references") or [])
        if tid and tid not in joined
    ]


def validate(spec: dict, refs_data: dict, spec_root: Path) -> list[str]:
    texts = chapter_texts(spec_root)
    return (
        check_goal_projection(spec, texts)
        + check_evidence_projection(spec, texts)
        + check_citation_projection(refs_data, texts)
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="正本 spec-state.json と成果物 system-spec/*.md の同期を検証する"
    )
    ap.add_argument("--matrix", required=True, help="spec-state.json のパス")
    ap.add_argument("--references", required=True, help="fetched-references.json のパス")
    ap.add_argument("--spec-root", default="system-spec", help="章 Markdown のディレクトリ")
    args = ap.parse_args(argv)

    try:
        violations = validate(
            load_json(Path(args.matrix)),
            load_json(Path(args.references)),
            Path(args.spec_root),
        )
    except (OSError, json.JSONDecodeError, SyncError) as exc:
        print(f"入力エラー: {exc}", file=sys.stderr)
        return 1

    if violations:
        print(f"FAIL: 正本と章の同期に {len(violations)} 件の未投影がある", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("OK: 正本 spec-state.json の goal・根拠・出典が章へ投影されている")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
