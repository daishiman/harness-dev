#!/usr/bin/env python3
# /// script
# name: render-graph-html
# purpose: Deterministically render a task graph as dependency-free static HTML/SVG.
# inputs: ["argv: --graph FILE --out FILE"]
# outputs: ["file: static HTML", "stdout: JSON result"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: argv --out only
# ///
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
import tempfile
from pathlib import Path

from _common import ContractError, dump


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--graph", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args(); source = Path(args.graph).resolve(strict=True); out = Path(args.out).resolve(strict=False)
    if source == out: raise ContractError("output must not overwrite graph input")
    try:
        input_bytes = source.read_bytes()
        data = json.loads(input_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON {source}: {exc}") from exc
    input_sha256 = hashlib.sha256(input_bytes).hexdigest()
    nodes = data.get("nodes", []) if isinstance(data, dict) else data
    if not isinstance(nodes, list): raise ContractError("graph nodes must be an array")
    normalized = []
    for raw in nodes:
        if not isinstance(raw, dict): raise ContractError("each node must be an object")
        node_id = raw.get("graph_node_id") or raw.get("id")
        if not isinstance(node_id, str): raise ContractError("node id is required")
        parent_feature = raw.get("parent_feature")
        if parent_feature is not None and not isinstance(parent_feature, str):
            raise ContractError("parent_feature must be a string when present")
        normalized.append({"id": node_id, "title": str(raw.get("title", node_id)),
                           "status": str(raw.get("status", "draft")), "kind": str(raw.get("artifact_kind", raw.get("kind", "task"))),
                           "depends_on": sorted(raw.get("depends_on", [])), "parent_feature": parent_feature})
    normalized.sort(key=lambda x: x["id"]); ids = {x["id"] for x in normalized}
    dangling = sorted({d for n in normalized for d in n["depends_on"] if d not in ids})
    if dangling: raise ContractError(f"dangling dependencies: {dangling}")
    dangling_parents = sorted({n["parent_feature"] for n in normalized if n["parent_feature"] and n["parent_feature"] not in ids})
    if dangling_parents: raise ContractError(f"dangling parent_feature references: {dangling_parents}")
    children_by_feature: dict[str, list[dict[str, object]]] = {}
    for node in normalized:
        if node["parent_feature"]:
            children_by_feature.setdefault(str(node["parent_feature"]), []).append(node)
    for node in normalized:
        children = children_by_feature.get(node["id"], []) if node["kind"] == "feature" else []
        node["progress"] = (
            {"done": sum(child["status"] == "done" for child in children), "total": len(children)}
            if children else None
        )
    progress_by_feature = {
        str(node["id"]): node["progress"] or {"done": 0, "total": 0}
        for node in normalized
        if node["kind"] == "feature"
    }
    feature_progress = {
        "aggregate": {
            "done": sum(item["done"] for item in progress_by_feature.values()),
            "total": sum(item["total"] for item in progress_by_feature.values()),
        },
        "by_feature": progress_by_feature,
    }
    width, row_h = 1000, 72; height = max(160, 80 + len(normalized) * row_h)
    y = {node["id"]: 60 + i * row_h for i, node in enumerate(normalized)}
    lines = []
    for node in normalized:
        for dep in node["depends_on"]:
            lines.append(f'<path d="M 360 {y[dep]} C 500 {y[dep]}, 500 {y[node["id"]]}, 640 {y[node["id"]]}"/>')
    cards = []
    for node in normalized:
        safe_id, safe_title = html.escape(node["id"]), html.escape(node["title"])
        progress = node["progress"]
        progress_label = f' · {progress["done"]}/{progress["total"]}' if progress else ""
        cards.append(f'<g class="node status-{html.escape(node["status"])}" data-id="{safe_id}" data-text="{safe_title.lower()}">' 
                     f'<rect x="40" y="{y[node["id"]]-24}" width="320" height="48" rx="8"/>'
                     f'<text x="54" y="{y[node["id"]]-3}">{safe_id}</text><text class="title" x="54" y="{y[node["id"]]+15}">{safe_title}</text>'
                     f'<rect x="640" y="{y[node["id"]]-18}" width="220" height="36" rx="18"/><text x="660" y="{y[node["id"]]+5}">{html.escape(node["status"])} · {html.escape(node["kind"])}{progress_label}</text></g>')
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
    document = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>dev-graph</title><style>body{{font:14px system-ui;margin:0;background:#0b1020;color:#e5e7eb}}header{{position:sticky;top:0;padding:16px;background:#111827;z-index:2}}input{{padding:8px;width:min(420px,70vw)}}svg{{min-width:{width}px;height:{height}px}}path{{stroke:#64748b;fill:none;stroke-width:2}}.node rect{{fill:#1f2937;stroke:#64748b}}.node text{{fill:#f8fafc}}.node .title{{fill:#cbd5e1;font-size:12px}}.status-done rect{{stroke:#22c55e}}.hidden{{display:none}}</style>
<header><strong>dev-graph</strong> <input id="q" aria-label="Filter nodes" placeholder="Filter id/title/status"></header>
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Task dependency graph"><g class="edges">{''.join(lines)}</g>{''.join(cards)}</svg>
<script type="application/json" id="graph-data">{payload}</script><script>const q=document.querySelector('#q');q.addEventListener('input',()=>{{const s=q.value.toLowerCase();document.querySelectorAll('.node').forEach(n=>n.classList.toggle('hidden',!((n.dataset.id+' '+n.dataset.text+' '+n.className.baseVal).toLowerCase().includes(s))))}});</script></html>'''
    out.parent.mkdir(parents=True, exist_ok=True); fd, temp = tempfile.mkstemp(prefix=f".{out.name}.", dir=out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream: stream.write(document); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, out)
    finally:
        try: os.unlink(temp)
        except FileNotFoundError: pass
    output_sha256 = hashlib.sha256(out.read_bytes()).hexdigest()
    dump({
        "ok": True,
        "out": str(out),
        "nodes": len(normalized),
        "edges": sum(len(x["depends_on"]) for x in normalized),
        "input_sha256": input_sha256,
        "output_sha256": output_sha256,
        "feature_progress": feature_progress,
    })
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except ContractError as exc: print(str(exc), file=sys.stderr); raise SystemExit(1)
