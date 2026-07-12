#!/usr/bin/env python3
# /// script
# name: resolve-route
# purpose: Resolve output-routing and adapter-registry config into adapter parameters.
# inputs:
#   - argv: task kind and optional config paths
# outputs:
#   - stdout: route JSON
#   - stderr: validation errors
# contexts: [A, B, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""output-routing.json + adapter-registry.json から task_kind に対するadapter解決。

stdlib のみ (CONVENTIONS.md §1 L2)。stdoutに {adapter, params, fallback, multi} のJSON出力。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parent.parent.parent


def _project_root() -> Path:
    return Path(os.environ.get("PROJECT_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())


def _first_existing(candidates: list[Path]) -> Path:
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


PROJECT_ROOT = _project_root()
ROUTING = _first_existing([
    PROJECT_ROOT / ".claude/config/output-routing.json",
    PROJECT_ROOT / ".claude/config/output-routing.json.example",
    KIT_ROOT / "config/output-routing.json",
    KIT_ROOT / "config/output-routing.json.example",
])
REGISTRY = _first_existing([
    PROJECT_ROOT / ".claude/config/adapter-registry.json",
    KIT_ROOT / "config/adapter-registry.json",
])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--routing", default=str(ROUTING))
    ap.add_argument("--registry", default=str(REGISTRY))
    args = ap.parse_args()

    routing_path = Path(args.routing)
    if not routing_path.exists():
        example = routing_path.with_name(routing_path.name + ".example")
        if example.exists():
            routing_path = example
        else:
            print(json.dumps({"status": "failure", "errors": [f"routing config not found: {args.routing}"]}))
            sys.exit(1)

    routing = json.loads(routing_path.read_text())
    registry_path = Path(args.registry)
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {"adapters": []}

    routes = routing.get("routes", {})
    defaults = routing.get("defaults", {"adapter": "local"})

    route = routes.get(args.kind)
    if route is None:
        adapter = defaults.get("adapter", "local")
        resolved = {
            "kind": args.kind,
            "adapter": adapter,
            "params": defaults.get("params", {"path": "out/", "format": "json"} if adapter == "local" else {}),
            "fallback": defaults.get("fallback"),
            "multi": False,
            "_resolved_from": "defaults",
        }
    elif "adapters" in route:
        resolved = {
            "kind": args.kind,
            "adapters": route["adapters"],
            "params": route.get("params", {}),
            "fallback": route.get("fallback"),
            "multi": True,
            "_resolved_from": "multi-sink",
        }
    else:
        resolved = {
            "kind": args.kind,
            "adapter": route["adapter"],
            "params": route.get("params", {}),
            "fallback": route.get("fallback"),
            "multi": False,
            "_resolved_from": "route",
        }

    # adapter存在検証
    registry_by_name = {a["name"]: a for a in registry.get("adapters", [])}
    registered_names = set(registry_by_name)
    targets = resolved.get("adapters", [resolved.get("adapter")]) if resolved.get("multi") else [resolved.get("adapter")]
    for t in targets:
        if t and t not in registered_names:
            print(json.dumps({"status": "failure", "errors": [f"adapter not registered: {t}"]}, ensure_ascii=False))
            return 1
        if t:
            resolved.setdefault("registry", {})[t] = registry_by_name[t]
            params = resolved.get("params", {}).get(t, {}) if resolved.get("multi") else resolved.get("params", {})
            errors = validate_params(t, params, registry_by_name[t].get("params_schema", {}))
            if errors:
                print(json.dumps({"status": "failure", "errors": errors}, ensure_ascii=False))
                return 1

    print(json.dumps(resolved, ensure_ascii=False))
    return 0


def validate_params(adapter: str, params: dict, schema: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(params, dict):
        return [f"{adapter}: params must be object"]
    for name, spec in schema.items():
        if spec.get("required") and name not in params:
            errors.append(f"{adapter}: missing required param: {name}")
        if name in params and "enum" in spec and params[name] not in spec["enum"]:
            errors.append(f"{adapter}: param {name} must be one of {spec['enum']}")
    return errors


if __name__ == "__main__":
    sys.exit(main())
