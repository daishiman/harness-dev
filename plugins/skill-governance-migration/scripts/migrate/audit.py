#!/usr/bin/env python3
# /// script
# name: migrate-audit
# purpose: Classify Markdown sections into migration categories for run-migrate-audit.
# inputs:
#   - argv: input markdown path and options
# outputs:
#   - stdout: audit JSON
#   - stderr: validation errors
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""run-migrate-audit の機械分類エントリ。

doc/20-migration-path.md Step 1 の 8 区分にMarkdown見出しを分類し
JSON で出力する。LLM を呼ばず stdlib のみで動く決定論的 first-pass。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 区分判定キーワード（classification-rules.md 準拠）
RULES = [
    ("hook",     [r"禁則", r"禁止", r"block", r"pre-?commit", r"決定論"]),
    ("wrap",     [r"ラッパ", r"wrapper", r"実行前検査", r"git\s+commit"]),
    ("assign",   [r"評価", r"採点", r"rubric", r"fork.*起動"]),
    ("delegate", [r"委譲", r"Codex", r"Gemini", r"外部\s*LLM"]),
    ("run",      [r"ワークフロー", r"Step\s*\d", r"フェーズ", r"手順"]),
    ("ref",      [r"リファレンス", r"仕様", r"用語", r"規約", r"glossary"]),
    ("docs",     [r"議事録", r"経緯", r"記録", r"changelog"]),
    ("always-on",[r"常に", r"必ず", r"全タスク", r"short rules"]),
]


def detect_origin(input_path: Path) -> str:
    """入力ファイルパスから origin を判定する（doc/21 source-tier 自動派生用）。

    返値:
      - "article"        : 元記事 Markdown (Agent Skill 大全 等) 由来
      - "internal-doc"   : リポジトリ内製の設計書 (doc/ClaudeCode スキルの設計書/ 等) 由来
      - "external-spec"  : 外部公式仕様 (claude.com docs 等) のローカル写し
      - "unknown"        : 判定不能（保守的に internal 扱いされる）
    """
    s = str(input_path)
    if "Agent Skill" in s or "skill大全" in s.lower():
        return "article"
    if "ClaudeCodeスキルの設計書" in s or "/doc/" in s.replace("\\", "/"):
        return "internal-doc"
    if "claude.com" in s or "external-spec" in s:
        return "external-spec"
    return "unknown"


def classify_section(heading: str, body: str) -> tuple[str, str]:
    text = f"{heading}\n{body}"
    for kind, patterns in RULES:
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return kind, f"matched: {pat}"
    return "always-on", "default fallback (no pattern matched)"


def split_sections(md_text: str) -> list[tuple[str, str]]:
    """## or # 見出し単位で分割する。返却: [(heading, body), ...]"""
    lines = md_text.splitlines()
    sections: list[tuple[str, str]] = []
    cur_h: str | None = None
    cur_body: list[str] = []
    for line in lines:
        m = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if m:
            if cur_h is not None:
                sections.append((cur_h, "\n".join(cur_body)))
            cur_h = m.group(1)
            cur_body = []
        else:
            if cur_h is not None:
                cur_body.append(line)
    if cur_h is not None:
        sections.append((cur_h, "\n".join(cur_body)))
    return sections


def suggest_skill_name(kind: str, heading: str) -> str | None:
    if kind in {"always-on", "docs"}:
        return None
    # heading から英数字以外を除去し小文字 kebab-case 化
    slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:30]
    if not slug:
        slug = "from-migration"
    prefix = {"ref": "ref", "run": "run", "wrap": "wrap",
              "assign": "assign", "delegate": "delegate", "hook": "ref"}[kind]
    return f"{prefix}-{slug}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="path to CLAUDE.md or prompt file")
    ap.add_argument("--output", required=True, help="path to write audit JSON")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(json.dumps({"status": "failure", "errors": [f"not found: {src}"]}))
        return 1

    sections = split_sections(src.read_text(encoding="utf-8"))
    classified = []
    summary = {"ref_candidates": 0, "run_candidates": 0, "hook_candidates": 0,
               "kept_in_claude_md": 0, "total_sections": len(sections)}
    for h, body in sections:
        kind, rationale = classify_section(h, body)
        skill_name = suggest_skill_name(kind, h)
        classified.append({
            "heading": h,
            "classification": kind,
            "rationale": rationale,
            "suggested_skill_name": skill_name,
        })
        if kind == "ref":
            summary["ref_candidates"] += 1
        elif kind == "run":
            summary["run_candidates"] += 1
        elif kind == "hook":
            summary["hook_candidates"] += 1
        elif kind == "always-on":
            summary["kept_in_claude_md"] += 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "input_file": str(src),
        "origin": detect_origin(src),
        "sections": classified,
        "summary": summary,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(out), "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
