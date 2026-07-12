#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# name: render-dependency-graph
# purpose: Render a CapabilityBundle (plugin-composition.yaml) into a Mermaid `graph LR` dependency graph.
# inputs:
#   - argv: [--bundle <plugin-composition.yaml>] [--out <md>] [--self-test] [--raw]
#   - reads: plugin-composition.yaml (capabilities[] / dependencies[])
# outputs:
#   - stdout: Markdown (Mermaid fence) or raw mermaid when --out is omitted
#   - file: Markdown written to --out when provided
#   - exit: 0=OK / 1=bundle load error / 2=usage error
# contexts: [A, B, C]
# network: false
# write-scope: output-arg-only
# dependencies: []
# requires-python: ">=3.10"
# ///
"""render-dependency-graph.py

CapabilityBundle (plugin-composition.yaml) を読み込み、capabilities[] と dependencies[] を
Mermaid `graph LR` 構文に変換するスクリプト。

使い方:
    # 任意の bundle を渡す
    python3 render-dependency-graph.py --bundle path/to/plugin-composition.yaml --out graph.md

    # harness-creator 自身 (dogfooding)
    python3 render-dependency-graph.py --self-test

出力:
    --out 未指定なら stdout、指定すれば Markdown ファイルとして書き出す。

スタイル:
    skill   -> blue
    agent   -> green
    hook    -> orange
    command -> purple
    ref     -> gray (skills/ref-* prefix を ref として再分類)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# PyYAML を優先、無ければ最小 parser にフォールバック
try:
    import yaml  # type: ignore

    def _load_yaml(text: str) -> Dict[str, Any]:
        return yaml.safe_load(text) or {}
except Exception:  # pragma: no cover - fallback path
    def _load_yaml(text: str) -> Dict[str, Any]:
        # 最低限の parser: capabilities[], dependencies[], name, kind のみを抽出する。
        # PyYAML 不在環境のための保険であり、汎用 YAML を網羅しない点に注意。
        data: Dict[str, Any] = {"capabilities": [], "dependencies": []}
        section: Optional[str] = None
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*):\s*(.*)$", line)
            if m_top and not raw.startswith(" "):
                key, val = m_top.group(1), m_top.group(2).strip()
                if key in ("capabilities", "dependencies"):
                    section = key
                else:
                    section = None
                    if val:
                        data[key] = val.strip('"')
                continue
            if section in ("capabilities", "dependencies") and line.lstrip().startswith("-"):
                inline = line.lstrip()[1:].strip()
                # {k: v, k: v} 形式を簡易パース
                if inline.startswith("{") and inline.endswith("}"):
                    body = inline[1:-1]
                    entry: Dict[str, str] = {}
                    for part in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", body):
                        if ":" not in part:
                            continue
                        k, v = part.split(":", 1)
                        entry[k.strip()] = v.strip().strip('"')
                    data[section].append(entry)
        return data


# --------------------------------------------------------------------------- #
# Kind 推定 / スタイル
# --------------------------------------------------------------------------- #

STYLE = {
    "skill":   "fill:#cfe2ff,stroke:#084298,color:#000",   # blue
    "agent":   "fill:#d1e7dd,stroke:#0f5132,color:#000",   # green
    "hook":    "fill:#ffe5b4,stroke:#7c3a00,color:#000",   # orange
    "command": "fill:#e2d6f3,stroke:#432874,color:#000",   # purple
    "ref":     "fill:#e2e3e5,stroke:#41464b,color:#000",   # gray
}

KIND_ORDER = ["skill", "ref", "agent", "command", "hook"]


def classify(kind: str, ref: str) -> str:
    """kind と ref から表示用カテゴリを返す (ref-* prefix は ref に再分類)。"""
    if kind == "skill" and "/ref-" in f"/{ref}":
        return "ref"
    return kind


def node_id(ref: str) -> str:
    """Mermaid ノード ID として安全な識別子へ変換する。"""
    safe = re.sub(r"[^A-Za-z0-9]+", "_", ref).strip("_")
    return f"n_{safe}" if safe else "n_unknown"


def node_label(ref: str) -> str:
    """ノードラベルは ref 末尾セグメント + (hook の場合は subpath) を採用。"""
    if ref.startswith("hook:"):
        return ref  # hook:Event/Name 形式はそのまま
    return ref.split("/")[-1] or ref


# --------------------------------------------------------------------------- #
# Mermaid 生成
# --------------------------------------------------------------------------- #

def render_mermaid(bundle: Dict[str, Any]) -> str:
    name = bundle.get("name", "(unknown)")
    capabilities: List[Dict[str, str]] = bundle.get("capabilities", []) or []
    dependencies: List[Dict[str, str]] = bundle.get("dependencies", []) or []

    # ノード集合 (ref -> category)
    nodes: Dict[str, str] = {}
    for cap in capabilities:
        ref = (cap.get("ref") or "").strip()
        if not ref:
            continue
        nodes[ref] = classify(cap.get("kind", "skill"), ref)

    # dependencies に登場するが capabilities[] に無い ref も補う
    for dep in dependencies:
        for key in ("from", "to"):
            ref = (dep.get(key) or "").strip()
            if ref and ref not in nodes:
                # 推定: ref-* prefix なら ref、agents/ なら agent、commands/ なら command
                if ref.startswith("hook:"):
                    nodes[ref] = "hook"
                elif ref.startswith("agents/"):
                    nodes[ref] = "agent"
                elif ref.startswith("commands/"):
                    nodes[ref] = "command"
                elif "/ref-" in f"/{ref}":
                    nodes[ref] = "ref"
                else:
                    nodes[ref] = "skill"

    lines: List[str] = []
    lines.append(f"%% Generated by render-dependency-graph.py — bundle: {name}")
    lines.append("graph LR")

    # subgraph をカテゴリごとに切る (見やすさのため)
    grouped: Dict[str, List[str]] = {k: [] for k in KIND_ORDER}
    for ref, cat in nodes.items():
        grouped.setdefault(cat, []).append(ref)

    for cat in KIND_ORDER:
        refs = sorted(grouped.get(cat, []))
        if not refs:
            continue
        lines.append(f"  subgraph {cat}s[{cat}]")
        for ref in refs:
            lines.append(f"    {node_id(ref)}[\"{node_label(ref)}\"]")
        lines.append("  end")

    # エッジ
    for dep in dependencies:
        src = (dep.get("from") or "").strip()
        dst = (dep.get("to") or "").strip()
        if not src or not dst:
            continue
        etype = (dep.get("type") or "calls").strip()
        lines.append(f"  {node_id(src)} -- {etype} --> {node_id(dst)}")

    # classDef とノード割当
    for cat, style in STYLE.items():
        lines.append(f"  classDef {cat} {style};")
    for cat in KIND_ORDER:
        refs = grouped.get(cat, [])
        if not refs:
            continue
        ids = ",".join(node_id(r) for r in sorted(refs))
        lines.append(f"  class {ids} {cat};")

    return "\n".join(lines) + "\n"


def wrap_markdown(mermaid: str, title: str) -> str:
    return f"# Dependency Graph: {title}\n\n```mermaid\n{mermaid}```\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _self_test_path() -> Path:
    # 本スクリプトは plugins/harness-creator/skills/run-build-skill/scripts/ 配下にある想定
    here = Path(__file__).resolve()
    return here.parents[3] / "plugin-composition.yaml"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render CapabilityBundle dependency graph as Mermaid.")
    parser.add_argument("--bundle", type=str, help="path to plugin-composition.yaml")
    parser.add_argument("--out", type=str, help="output markdown path (default: stdout)")
    parser.add_argument("--self-test", action="store_true", help="render harness-creator/plugin-composition.yaml (dogfooding)")
    parser.add_argument("--raw", action="store_true", help="output raw mermaid (no markdown fence)")
    args = parser.parse_args(argv)

    if args.self_test and not args.bundle:
        bundle_path = _self_test_path()
    elif args.bundle:
        bundle_path = Path(args.bundle).resolve()
    else:
        parser.error("--bundle か --self-test のいずれかが必要です")
        return 2

    if not bundle_path.exists():
        print(f"[error] bundle not found: {bundle_path}", file=sys.stderr)
        return 1

    text = bundle_path.read_text(encoding="utf-8")
    bundle = _load_yaml(text)
    mermaid = render_mermaid(bundle)
    title = bundle.get("name") or bundle_path.stem
    output = mermaid if args.raw else wrap_markdown(mermaid, title)

    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"[ok] wrote {out_path}")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
