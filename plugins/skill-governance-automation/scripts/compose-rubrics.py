#!/usr/bin/env python3
# /// script
# name: compose-rubrics
# purpose: Compose L0/L1/L2 rubric JSON files deterministically.
# inputs:
#   - argv: --rubric-refs paths, --merge-strategy, --conflict-policy
# outputs:
#   - stdout: composed rubric JSON
#   - stderr: validation errors
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""設計書29に基づき rubric_refs を決定論的に合成する。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

LAYERS = {"L0": 0, "L1": 1, "L2": 2}
STRATEGIES = {"deep-merge", "strict", "override", "layered"}
POLICIES = {"most-specific-wins", "error", "warn-and-merge"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_ref(ref: str) -> tuple[str, Path, dict]:
    path = Path(ref)
    if ref.startswith("ref-"):
        # rubric.json は 2026-05-22 に各 ref-*-rubric skill の references/ 配下へ移動済。
        # 後方互換のため root 直下も候補に残すが、references/ を優先解決する。
        candidates = [
            Path("plugins/harness-creator/skills") / ref / "references" / "rubric.json",
            Path(".claude/skills") / ref / "references" / "rubric.json",
            Path("plugins/harness-creator/skills") / ref / "rubric.json",
            Path(".claude/skills") / ref / "rubric.json",
        ]
        path = next((p for p in candidates if p.exists()), candidates[0])
    if not path.exists():
        raise ValueError(f"rubric not found: {ref} -> {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ref, path.resolve(), data


def validate_schema(ref: str, data: dict) -> None:
    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError(f"{ref}: rules must be list")
    layer = data.get("layer")
    if layer is not None and layer not in LAYERS:
        raise ValueError(f"{ref}: layer must be L0/L1/L2")
    seen: set[str] = set()
    for idx, rule in enumerate(data["rules"]):
        if not isinstance(rule, dict):
            raise ValueError(f"{ref}: rules[{idx}] must be object")
        rid = rule.get("id")
        if not rid:
            raise ValueError(f"{ref}: rules[{idx}].id is required")
        if rid in seen:
            raise ValueError(f"{ref}: duplicate rule id: {rid}")
        seen.add(rid)


def detect_cycles(loaded: list[tuple[str, Path, dict]]) -> None:
    refs = {ref for ref, _, _ in loaded}
    graph = {ref: [x for x in data.get("extends", []) if x in refs] for ref, _, data in loaded}
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visiting:
            raise ValueError(f"cyclic rubric extends detected at {node}")
        if node in visited:
            return
        visiting.add(node)
        for nxt in graph.get(node, []):
            dfs(nxt)
        visiting.remove(node)
        visited.add(node)

    for ref in graph:
        dfs(ref)


def deep_merge(a: Any, b: Any, conflict_policy: str, warnings: list[str], source: str) -> Any:
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for key, value in b.items():
            if key in out:
                out[key] = deep_merge(out[key], value, conflict_policy, warnings, f"{source}.{key}")
            else:
                out[key] = value
        return out
    if a != b:
        if conflict_policy == "error":
            raise ValueError(f"conflict at {source}")
        if conflict_policy == "warn-and-merge":
            warnings.append(f"conflict at {source}; most-specific value used")
    return b


def merge_rules(base: list[dict], overlay: list[dict], strategy: str, policy: str, warnings: list[str], ref: str) -> list[dict]:
    if strategy == "override":
        return [dict(r) for r in overlay]
    by_id = {r["id"]: dict(r) for r in base}
    for rule in overlay:
        rid = rule["id"]
        if rid in by_id:
            if strategy == "strict" or policy == "error":
                raise ValueError(f"rule conflict: {rid} from {ref}")
            if policy == "warn-and-merge":
                warnings.append(f"rule conflict: {rid} from {ref}; most-specific value used")
            by_id[rid] = deep_merge(by_id[rid], rule, "most-specific-wins", warnings, f"rules.{rid}")
        else:
            by_id[rid] = dict(rule)
    return list(by_id.values())


def compose(refs: list[str], strategy: str, policy: str) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"invalid merge_strategy: {strategy}")
    if policy not in POLICIES:
        raise ValueError(f"invalid conflict_policy: {policy}")
    loaded = [load_ref(ref) for ref in refs]
    for ref, _, data in loaded:
        validate_schema(ref, data)
    detect_cycles(loaded)
    loaded.sort(key=lambda item: (LAYERS.get(item[2].get("layer", "L2"), 2), refs.index(item[0])))

    warnings: list[str] = []
    if strategy == "layered":
        result = {
            "rubric_id": "layered",
            "rubric_version": "composed",
            "layers": [{"ref": ref, "path": str(path), "rubric": data} for ref, path, data in loaded],
            "rules": [dict(rule, source_ref=ref, source_layer=data.get("layer")) for ref, _, data in loaded for rule in data.get("rules", [])],
        }
    else:
        result: dict[str, Any] = {"rules": []}
        for ref, _, data in loaded:
            meta = {k: v for k, v in data.items() if k != "rules"}
            if strategy == "strict":
                overlap = set(result) & set(meta)
                overlap.discard("_composition_warnings")
                if overlap:
                    raise ValueError(f"metadata conflict from {ref}: {sorted(overlap)}")
            result = deep_merge(result, meta, policy, warnings, ref)
            result["rules"] = merge_rules(result.get("rules", []), data.get("rules", []), strategy, policy, warnings, ref)

    hash_input = [{"ref": ref, "path": str(path), "rubric": data} for ref, path, data in loaded]
    result["_composition_hash"] = "sha256:" + hashlib.sha256(canonical_json(hash_input).encode("utf-8")).hexdigest()
    result["_composition_refs"] = [ref for ref, _, _ in loaded]
    if warnings:
        result["_composition_warnings"] = warnings
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rubric-refs", nargs="+", required=True)
    parser.add_argument("--merge-strategy", default="deep-merge", choices=sorted(STRATEGIES))
    parser.add_argument("--conflict-policy", default="most-specific-wins", choices=sorted(POLICIES))
    args = parser.parse_args()
    try:
        result = compose(args.rubric_refs, args.merge_strategy, args.conflict_policy)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"compose-rubrics: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
