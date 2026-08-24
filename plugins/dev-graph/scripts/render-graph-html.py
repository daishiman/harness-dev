#!/usr/bin/env python3
# /// script
# name: render-graph-html
# purpose: Deterministically render a task graph as dependency-free static HTML/SVG.
# inputs: ["argv: --repo-root DIR --graph FILE --out FILE [--scope ID] [--registration-receipt FILE ...]"]
# outputs: ["file: static HTML", "stdout: JSON result"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: caller repository contained argv --out only
# ///
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from _common import ContractError, contained, dump


SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
PHASES = [f"P{index:02d}" for index in range(1, 14)]


def _load_json_object(path: Path, label: str) -> tuple[dict[str, object], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid {label} JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be a JSON object: {path}")
    return value, raw


def _repo_path(raw_path: str, root: Path, label: str, *, must_exist: bool) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    authority = root.resolve(strict=True)
    lexical = Path(os.path.abspath(candidate))
    try:
        relative = lexical.relative_to(authority)
    except ValueError as exc:
        raise ContractError(
            f"{label} path escapes authority root: {raw_path}"
        ) from exc
    try:
        resolved = contained(candidate, authority, must_exist=must_exist)
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, ContractError):
            raise
        state = "does not exist" if must_exist else "is invalid"
        raise ContractError(f"{label} {state}: {raw_path}") from exc
    current = authority
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ContractError(f"{label} path must not traverse a symlink: {raw_path}")
        if not current.exists():
            break
    if must_exist and not resolved.is_file():
        raise ContractError(f"{label} must be a regular file: {raw_path}")
    return resolved


def _repo_ref(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scope_nodes(
    nodes: list[dict[str, object]], scope: str | None
) -> list[dict[str, object]]:
    if scope is None:
        return nodes
    by_id = {str(node["id"]): node for node in nodes}
    if scope not in by_id:
        raise ContractError(f"scope node does not exist: {scope}")
    selected = {scope}
    while True:
        before = set(selected)
        for node_id in tuple(selected):
            node = by_id[node_id]
            selected.update(str(dep) for dep in node["depends_on"])
            parent = node.get("parent_feature")
            if isinstance(parent, str) and parent:
                selected.add(parent)
        selected.update(
            str(node["id"]) for node in nodes if node.get("parent_feature") in selected
        )
        if selected == before:
            break
    return [node for node in nodes if node["id"] in selected]


def _registration_evidence(
    receipt_paths: list[Path],
    nodes: list[dict[str, object]],
    root: Path,
) -> dict[str, dict[str, object]]:
    receipts: dict[str, tuple[dict[str, object], Path, bytes]] = {}
    for path in receipt_paths:
        receipt, raw = _load_json_object(path, "registration receipt")
        parent = receipt.get("parent_feature")
        if not isinstance(parent, str) or not parent:
            raise ContractError(
                f"registration receipt parent_feature is required: {path}"
            )
        if parent in receipts:
            raise ContractError(f"duplicate registration receipt for feature: {parent}")
        receipts[parent] = (receipt, path, raw)

    feature_ids = {str(node["id"]) for node in nodes if node["kind"] == "feature"}
    children_by_feature: dict[str, list[dict[str, object]]] = {
        feature_id: [] for feature_id in feature_ids
    }
    for node in nodes:
        parent = node.get("parent_feature")
        if (
            node["kind"] == "task"
            and isinstance(parent, str)
            and parent in children_by_feature
        ):
            children_by_feature[parent].append(node)

    required_features = {
        feature_id for feature_id, children in children_by_feature.items() if children
    }
    missing = sorted(required_features - set(receipts))
    extra = sorted(set(receipts) - required_features)
    if missing:
        raise ContractError(
            f"registration receipt missing for scoped feature(s): {missing}"
        )
    if extra:
        raise ContractError(
            f"registration receipt has no scoped child task set: {extra}"
        )

    evidence: dict[str, dict[str, object]] = {}
    for feature_id in sorted(required_features):
        receipt, path, raw = receipts[feature_id]
        if receipt.get("status") != "registered":
            raise ContractError(f"registration receipt is not registered: {feature_id}")
        source_digest = receipt.get("source_digest")
        if (
            not isinstance(source_digest, str)
            or SHA256.fullmatch(source_digest) is None
        ):
            raise ContractError(
                f"registration receipt source_digest is invalid: {feature_id}"
            )
        package_id = receipt.get("feature_package_id")
        if not isinstance(package_id, str) or not package_id:
            raise ContractError(
                f"registration receipt feature_package_id is required: {feature_id}"
            )
        children = sorted(
            children_by_feature[feature_id], key=lambda node: str(node["id"])
        )
        child_ids = [str(node["id"]) for node in children]
        receipt_ids = receipt.get("node_ids")
        if (
            not isinstance(receipt_ids, list)
            or any(not isinstance(node_id, str) for node_id in receipt_ids)
            or len(receipt_ids) != len(set(receipt_ids))
            or sorted(receipt_ids) != child_ids
        ):
            raise ContractError(
                f"registration receipt node_ids do not exactly match scoped child tasks: {feature_id}"
            )
        expected_count = receipt.get("expected_count")
        applied_count = receipt.get("applied_count")
        if (
            expected_count != applied_count
            or expected_count != len(child_ids)
            or expected_count != 13
        ):
            raise ContractError(
                f"registration receipt counts do not match scoped child tasks: {feature_id}"
            )
        if receipt.get("phase_refs") != PHASES:
            raise ContractError(
                f"registration receipt phase_refs are not exact P01..P13: {feature_id}"
            )
        child_by_phase = {
            child.get("phase_ref"): str(child["id"]) for child in children
        }
        if len(child_by_phase) != 13 or receipt_ids != [
            child_by_phase.get(phase) for phase in PHASES
        ]:
            raise ContractError(
                f"registration receipt node_ids are not in exact phase order: {feature_id}"
            )
        expected_lineage = source_digest.removeprefix("sha256:")
        for child in children:
            if child.get("feature_package_id") != package_id:
                raise ContractError(
                    f"feature_package_id mismatch for child task: {child['id']}"
                )
            if child.get("lineage_source_digest") != expected_lineage:
                raise ContractError(
                    f"source lineage digest mismatch for child task: {child['id']}"
                )
        evidence[feature_id] = {
            "receipt": _repo_ref(path, root),
            "receipt_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "feature_package_id": package_id,
            "source_digest": source_digest,
            "expected_count": expected_count,
            "applied_count": applied_count,
            "node_ids": list(receipt_ids),
        }
    return evidence


def _edge_kind(source: dict[str, object], target: dict[str, object]) -> str:
    if source["kind"] == target["kind"] == "feature":
        return "feature"
    if (
        source["kind"] == target["kind"] == "task"
        and source.get("parent_feature")
        and source.get("parent_feature") == target.get("parent_feature")
    ):
        return "task"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--graph", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--scope")
    parser.add_argument("--registration-receipt", action="append", default=[])
    args = parser.parse_args()
    try:
        root = Path(args.repo_root).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ContractError(f"repo root does not exist: {args.repo_root}") from exc
    if not root.is_dir():
        raise ContractError(f"repo root is not a directory: {root}")
    source = _repo_path(args.graph, root, "graph", must_exist=True)
    out = _repo_path(args.out, root, "output", must_exist=False)
    if out == root or (out.exists() and not out.is_file()):
        raise ContractError("output must be a file path within the repo root")
    if source == out:
        raise ContractError("output must not overwrite graph input")
    try:
        input_bytes = source.read_bytes()
        data = json.loads(input_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON {source}: {exc}") from exc
    input_sha256 = hashlib.sha256(input_bytes).hexdigest()
    nodes = data.get("nodes", []) if isinstance(data, dict) else data
    if not isinstance(nodes, list):
        raise ContractError("graph nodes must be an array")
    normalized = []
    for raw in nodes:
        if not isinstance(raw, dict):
            raise ContractError("each node must be an object")
        node_id = raw.get("graph_node_id") or raw.get("id")
        if not isinstance(node_id, str):
            raise ContractError("node id is required")
        parent_feature = raw.get("parent_feature")
        if parent_feature is not None and not isinstance(parent_feature, str):
            raise ContractError("parent_feature must be a string when present")
        depends_on = raw.get("depends_on", [])
        if not isinstance(depends_on, list) or any(
            not isinstance(dep, str) for dep in depends_on
        ):
            raise ContractError("depends_on must be an array of node ids")
        lineage = raw.get("source_lineage")
        lineage_source_digest = (
            lineage.get("source_digest") if isinstance(lineage, dict) else None
        )
        normalized.append(
            {
                "id": node_id,
                "title": str(raw.get("title", node_id)),
                "status": str(raw.get("status", "draft")),
                "kind": str(raw.get("artifact_kind", raw.get("kind", "task"))),
                "depends_on": sorted(depends_on),
                "parent_feature": parent_feature,
                "feature_package_id": raw.get("feature_package_id"),
                "phase_ref": raw.get("phase_ref"),
                "lineage_source_digest": lineage_source_digest,
            }
        )
    normalized.sort(key=lambda x: x["id"])
    ids = {x["id"] for x in normalized}
    dangling = sorted({d for n in normalized for d in n["depends_on"] if d not in ids})
    if dangling:
        raise ContractError(f"dangling dependencies: {dangling}")
    dangling_parents = sorted(
        {
            n["parent_feature"]
            for n in normalized
            if n["parent_feature"] and n["parent_feature"] not in ids
        }
    )
    if dangling_parents:
        raise ContractError(f"dangling parent_feature references: {dangling_parents}")
    normalized = _scope_nodes(normalized, args.scope)
    receipt_paths = [
        _repo_path(path, root, "registration receipt", must_exist=True)
        for path in args.registration_receipt
    ]
    if out in receipt_paths:
        raise ContractError("output must not overwrite a registration receipt")
    registration_evidence = _registration_evidence(
        receipt_paths,
        normalized,
        root,
    )
    children_by_feature: dict[str, list[dict[str, object]]] = {}
    for node in normalized:
        if node["kind"] == "task" and node["parent_feature"]:
            children_by_feature.setdefault(str(node["parent_feature"]), []).append(node)
    for node in normalized:
        children = (
            children_by_feature.get(node["id"], []) if node["kind"] == "feature" else []
        )
        node["progress"] = (
            {
                "done": sum(child["status"] == "done" for child in children),
                "total": len(children),
            }
            if children
            else None
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
    width, row_h = 1000, 72
    height = max(160, 80 + len(normalized) * row_h)
    y = {node["id"]: 60 + i * row_h for i, node in enumerate(normalized)}
    by_id = {str(node["id"]): node for node in normalized}
    edge_counts = {"feature": 0, "task": 0, "other": 0}
    lines = []
    for node in normalized:
        for dep in node["depends_on"]:
            kind = _edge_kind(by_id[dep], node)
            edge_counts[kind] += 1
            lines.append(
                f'<path class="edge edge-{kind}" data-edge-kind="{kind}" d="M 360 {y[dep]} C 500 {y[dep]}, 500 {y[node["id"]]}, 640 {y[node["id"]]}"/>'
            )
    cards = []
    for node in normalized:
        safe_id, safe_title = html.escape(node["id"]), html.escape(node["title"])
        progress = node["progress"]
        progress_label = (
            f" · {progress['done']}/{progress['total']}" if progress else ""
        )
        cards.append(
            f'<g class="node status-{html.escape(node["status"])}" data-id="{safe_id}" data-text="{safe_title.lower()}">'
            f'<rect x="40" y="{y[node["id"]] - 24}" width="320" height="48" rx="8"/>'
            f'<text x="54" y="{y[node["id"]] - 3}">{safe_id}</text><text class="title" x="54" y="{y[node["id"]] + 15}">{safe_title}</text>'
            f'<rect x="640" y="{y[node["id"]] - 18}" width="220" height="36" rx="18"/><text x="660" y="{y[node["id"]] + 5}">{html.escape(node["status"])} · {html.escape(node["kind"])}{progress_label}</text></g>'
        )
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True).replace(
        "<", "\\u003c"
    )
    render_model_sha256 = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
    )
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>dev-graph</title><style>body{{font:14px system-ui;margin:0;background:#0b1020;color:#e5e7eb}}header{{position:sticky;top:0;padding:16px;background:#111827;z-index:2}}input{{padding:8px;width:min(420px,70vw)}}.legend{{display:inline-flex;gap:12px;margin-left:16px;font-size:12px}}.legend i{{display:inline-block;width:22px;border-top:3px solid;margin-right:4px}}.legend .feature{{border-color:#a78bfa}}.legend .task{{border-color:#38bdf8}}.legend .other{{border-color:#64748b}}svg{{min-width:{width}px;height:{height}px}}path{{fill:none;stroke-width:2}}.edge-feature{{stroke:#a78bfa}}.edge-task{{stroke:#38bdf8}}.edge-other{{stroke:#64748b;stroke-dasharray:5 4}}.node rect{{fill:#1f2937;stroke:#64748b}}.node text{{fill:#f8fafc}}.node .title{{fill:#cbd5e1;font-size:12px}}.status-done rect{{stroke:#22c55e}}.hidden{{display:none}}</style>
<header><strong>dev-graph</strong> <input id="q" aria-label="Filter nodes" placeholder="Filter id/title/status"><span class="legend" aria-label="Edge legend"><span><i class="feature"></i>feature</span><span><i class="task"></i>task</span><span><i class="other"></i>other</span></span></header>
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Task dependency graph"><g class="edges">{"".join(lines)}</g>{"".join(cards)}</svg>
<script type="application/json" id="graph-data">{payload}</script><script>const q=document.querySelector('#q');q.addEventListener('input',()=>{{const s=q.value.toLowerCase();document.querySelectorAll('.node').forEach(n=>n.classList.toggle('hidden',!((n.dataset.id+' '+n.dataset.text+' '+n.className.baseVal).toLowerCase().includes(s))))}});</script></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{out.name}.", dir=out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, out)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
    output_sha256 = hashlib.sha256(out.read_bytes()).hexdigest()
    dump(
        {
            "ok": True,
            "out": _repo_ref(out, root),
            "nodes": len(normalized),
            "edges": sum(edge_counts.values()),
            "edge_counts": edge_counts,
            "scope": args.scope,
            "scope_node_ids": [str(node["id"]) for node in normalized],
            "input_sha256": input_sha256,
            "render_model_sha256": render_model_sha256,
            "output_sha256": output_sha256,
            "feature_progress": feature_progress,
            "registration_evidence": registration_evidence,
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
