#!/usr/bin/env python3
# /// script
# name: recount-palette-orphans
# purpose: C02 (assign-blueprint-fidelity-evaluator) の common-mode 破り検査。C11 (doc-emit.py
#          --check-screens) が構造化キーアクセスで判定する「観測色の palette 孤児 0」不変量を、
#          C11 実装を import せず blueprint.json の screens 部分木を generic な color-key/正規表現
#          走査で数え直す独立経路で再計数する。両者が同一バグを持つ common-mode 誤りを排除するため、
#          走査アルゴリズムを意図的に C11 と別実装にする (同一ロジックの共有を禁止)。
# inputs:
#   - argv: --blueprint BLUEPRINT_JSON
# outputs:
#   - stdout: {observed_count, palette_count, orphan_count, orphans[]} (JSON)
#   - stderr: orphan 詳細 (orphan_count != 0 のとき)
#   - exit: 0=孤児0 / 1=孤児検出 / 2=usage
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""観測色 palette 孤児の非共有再計数 (common-mode 破り・stdlib 完結・network なし)。

C11 (doc-emit._observed_colors) は paint/typography の固定キー集合を構造的に読む。本 script は
同じ不変量 (screens 上で観測された色 ⊆ design_tokens.palette) を、screens 部分木を再帰走査して
「キー名に color を含む値」と「hex/rgb にマッチする文字列値」を generic に集める別アルゴリズムで
再計数する。同一の色正規化仕様 (hex3/4/6/8・rgb/rgba → hex8) を独立実装し、両経路の結果を C02 が
照合する。C11 が exit0 でも本 script が孤児を検出したら C11 の走査漏れ=common-mode 誤りとして FAIL。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 色として扱わないキーワード (キー名に color を含んでも値がこれらは観測色でない)。
_SKIP_COLOR_VALUES = {
    "", "transparent", "none", "currentcolor", "inherit", "initial", "unset", "auto",
}
# hex / rgb を素朴に拾う正規表現 (C11 の re.fullmatch とは別に部分一致で走査)。
_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_RGB_RE = re.compile(r"rgba?\([^)]*\)", re.IGNORECASE)
# キー名が観測色を指すか (palette 定義側の役割名 role/name は除外)。
_COLOR_KEY_RE = re.compile(r"color", re.IGNORECASE)
_SKIP_STATUS = {"not_observed", "blocked"}


def _norm_hex(token: str) -> str | None:
    """#rgb / #rgba / #rrggbb / #rrggbbaa を hex8 へ (C11 と別実装・同一仕様)。"""
    m = re.fullmatch(r"#([0-9a-fA-F]{3,8})", token.strip())
    if not m:
        return None
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h) + "ff"
    elif len(h) == 4:
        h = "".join(c * 2 for c in h)
    elif len(h) == 6:
        h = h + "ff"
    elif len(h) == 8:
        pass
    else:
        return None
    return "#" + h


def _norm_rgb(token: str) -> str | None:
    """rgb()/rgba() を hex8 へ (C11 と別実装・同一仕様)。"""
    m = re.fullmatch(r"rgba?\(([^)]+)\)", token.strip(), re.IGNORECASE)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).replace("/", ",").split(",") if p.strip()]
    if len(parts) < 3:
        return None
    try:
        r, g, b = (int(round(float(p.rstrip("%")))) for p in parts[:3])
        if len(parts) > 3:
            a = parts[3]
            av = float(a.rstrip("%"))
            av = av / 100 if "%" in a else av
        else:
            av = 1.0
        alpha = max(0, min(255, int(round(av * 255))))
    except (TypeError, ValueError):
        return None
    return "#{:02x}{:02x}{:02x}{:02x}".format(r & 255, g & 255, b & 255, alpha)


def _canon(value) -> str | None:
    """1 個の色候補を canonical token へ (未観測/非色は None)。"""
    if isinstance(value, dict):
        if value.get("observation_status") in _SKIP_STATUS:
            return None
        for key in ("canonical_hex8", "exact", "value", "color", "hex"):
            tok = _canon(value.get(key))
            if tok:
                return tok
        return None
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    if s in _SKIP_COLOR_VALUES:
        return None
    return _norm_hex(s) or _norm_rgb(s) or (s if s else None)


def _scan_tokens(text: str) -> set[str]:
    """任意文字列から hex/rgb を部分一致で拾い canonical 化する。"""
    out: set[str] = set()
    for m in _HEX_RE.findall(text):
        tok = _norm_hex(m)
        if tok:
            out.add(tok)
    for m in _RGB_RE.findall(text):
        tok = _norm_rgb(m)
        if tok:
            out.add(tok)
    return out


def collect_observed(screens) -> set[str]:
    """screens 部分木を generic 走査して観測色 canonical token を集める (C11 と独立経路)。"""
    observed: set[str] = set()

    def walk(node, under_color_key: bool):
        if isinstance(node, dict):
            if node.get("observation_status") in _SKIP_STATUS:
                return
            for key, val in node.items():
                key_is_color = bool(_COLOR_KEY_RE.search(str(key)))
                if key_is_color:
                    tok = _canon(val)
                    if tok:
                        observed.add(tok)
                walk(val, under_color_key or key_is_color)
        elif isinstance(node, list):
            for item in node:
                walk(item, under_color_key)
        elif isinstance(node, str):
            # color コンテキスト配下の文字列、または hex/rgb を含む文字列を拾う。
            if under_color_key:
                tok = _canon(node)
                if tok:
                    observed.add(tok)
            observed.update(_scan_tokens(node))

    for sc in screens or []:
        if isinstance(sc, dict) and sc.get("observation_status") in _SKIP_STATUS:
            continue
        walk(sc, under_color_key=False)
    return observed


def collect_palette(design_tokens) -> set[str]:
    """design_tokens.palette と theme_variants から palette token を集める。"""
    tokens: set[str] = set()
    dt = design_tokens or {}

    def add_entries(entries):
        for entry in entries or []:
            if isinstance(entry, dict):
                tok = _canon(entry.get("canonical_hex8")) or _canon(entry.get("value")) or _canon(entry)
            else:
                tok = _canon(entry)
            if tok:
                tokens.add(tok)

    add_entries(dt.get("palette"))
    for tv in dt.get("theme_variants") or []:
        if isinstance(tv, dict):
            add_entries(tv.get("palette"))
            add_entries(tv.get("colors"))
    # document brand 色も palette 一部として許容する。
    brand = dt.get("document_brand") or dt.get("brand")
    if isinstance(brand, dict):
        add_entries(brand.get("colors"))
    elif isinstance(brand, list):
        add_entries(brand)
    return tokens


def recount(blueprint: dict) -> dict:
    screens = blueprint.get("screens") if isinstance(blueprint, dict) else None
    design_tokens = blueprint.get("design_tokens") if isinstance(blueprint, dict) else None
    observed = collect_observed(screens)
    palette = collect_palette(design_tokens)
    orphans = sorted(observed - palette)
    return {
        "observed_count": len(observed),
        "palette_count": len(palette),
        "orphan_count": len(orphans),
        "orphans": orphans,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="観測色 palette 孤児を C11 と独立経路で再計数する common-mode 破り検査",
        add_help=True,
    )
    ap.add_argument("--blueprint", required=True, help="C01 draft の blueprint.json")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    path = Path(args.blueprint)
    try:
        blueprint = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.stderr.write(f"blueprint が存在しない: {path}\n")
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"blueprint を読めない: {path}: {exc}\n")
        return 2
    if not isinstance(blueprint, dict):
        sys.stderr.write("blueprint のルートが object でない\n")
        return 2

    result = recount(blueprint)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    if result["orphan_count"]:
        sys.stderr.write(
            "観測色が palette に不在 (非共有再計数で孤児検出): "
            + ", ".join(result["orphans"][:20])
            + (" ..." if result["orphan_count"] > 20 else "")
            + "\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
