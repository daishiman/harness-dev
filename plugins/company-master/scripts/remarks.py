#!/usr/bin/env python3
# /// script
# name: remarks
# purpose: remarks-templates.md(備考定型文言の唯一の正本)をパースし remark_key→定型文言へ展開する(文言をコードに二重定義しない)。
# inputs:
#   - file: references/remarks-templates.md の「remark_key → 文言マッピング」表
#   - api: load_templates() / expand(remark_keys) / expand_template(key, **params)
# outputs:
#   - api: dict[str,str] / 改行区切り文字列
#   - exit: 0=OK (CLI 自己検査)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""備考定型テンプレート展開器 (SSOT 維持)。

文言の唯一の正本は references/remarks-templates.md の markdown 表。本モジュールは
その表をパースして remark_key→文言へ展開するだけで、文言をコードに二重定義しない。
複数失敗時は改行区切りで列挙する (brief key_constraints[A] / remarks-templates.md 運用ルール)。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# references/remarks-templates.md (scripts/ から見て ../references/)
TEMPLATES_MD = Path(__file__).resolve().parent.parent / "references" / "remarks-templates.md"

# 表行: | `key` | `文言` |  (バッククォートは任意許容)
_ROW_RE = re.compile(r"^\|\s*`?([a-z_]+)`?\s*\|\s*`?(.+?)`?\s*\|\s*$")
# 見出し行 / 区切り行 (|---|---|) は除外
_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
_HEADER_KEYS = {"remark_key"}


def load_templates(md_path: Path | None = None) -> dict[str, str]:
    """remarks-templates.md の表をパースして {remark_key: 文言} を返す。

    「remark_key → 文言マッピング」見出し配下の表行のみを採用する。
    """
    path = md_path or TEMPLATES_MD
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    in_mapping = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            # 見出しが変わったらマッピング表 scope を更新
            in_mapping = "remark_key" in stripped or "文言マッピング" in stripped
            continue
        if not in_mapping:
            continue
        if _SEP_RE.match(stripped):
            continue
        m = _ROW_RE.match(stripped)
        if not m:
            continue
        key, phrase = m.group(1), m.group(2).strip().strip("`")
        if key in _HEADER_KEYS:
            continue
        out[key] = phrase
    if not out:
        raise ValueError(
            f"remarks-templates.md からテンプレートを抽出できません: {path} "
            "(「remark_key → 文言マッピング」表の形式を確認してください)"
        )
    return out


def expand(remark_keys: list[str], md_path: Path | None = None) -> str:
    """remark_key 群を定型文言へ展開し改行区切りで連結する (重複は順序保持で除去)。"""
    if not remark_keys:
        return ""
    templates = load_templates(md_path)
    seen: set[str] = set()
    phrases: list[str] = []
    for key in remark_keys:
        if key in seen:
            continue
        seen.add(key)
        phrase = templates.get(key)
        if phrase is None:
            raise KeyError(
                f"remark_key '{key}' が remarks-templates.md に未定義 (正本へ文言追加が必要)"
            )
        phrases.append(phrase)
    return "\n".join(phrases)


def expand_template(key: str, md_path: Path | None = None, **params: str) -> str:
    """placeholder 付き定型文言を埋めて 1 行返す (例: all_tiers_exhausted)。

    fallback tier4 (全段試行不成立。正本 data-sources.md) の備考は試行手段の列挙が行ごとに
    変わるため、`{field}` / `{attempts}` placeholder を持つテンプレートを本関数で展開する。
    文言の骨格は md 正本のみが持ち、検証 (f) は placeholder 部を可変としてパターン照合する。
    """
    templates = load_templates(md_path)
    phrase = templates.get(key)
    if phrase is None:
        raise KeyError(
            f"remark_key '{key}' が remarks-templates.md に未定義 (正本へ文言追加が必要)"
        )
    return phrase.format(**params)


def main() -> int:
    """CLI 自己検査: 全 remark_key を一覧表示し、parse 健全性を確認する。"""
    templates = load_templates()
    for key, phrase in templates.items():
        print(f"{key}\t{phrase}")
    print(f"# loaded {len(templates)} templates from {TEMPLATES_MD}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
