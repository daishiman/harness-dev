#!/usr/bin/env python3
# /// script
# name: init-project-layout
# purpose: caller repository に repo-local config/roots/templates を missing-only で冪等生成する。
# inputs: argv --repo-root/--config/--asset
# outputs: stdout init receipt JSON
# contexts: [C, E]
# network: false
# write-scope: caller-repository only
# dependencies: [resolve-project-context.py]
# requires-python: ">=3.10"
# ///
"""C10: non-destructive repository-local initializer."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ASSET = HERE.parent / "assets" / "default-project-config.json"


def _resolver():
    spec = importlib.util.spec_from_file_location("sdp_context", HERE / "resolve-project-context.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _merge_missing(current: dict, defaults: dict, prefix: str = "") -> tuple[dict, list[str]]:
    merged = dict(current)
    added: list[str] = []
    for key, value in defaults.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if key not in merged:
            merged[key] = value
            added.append(dotted)
        elif isinstance(value, dict) and isinstance(merged[key], dict):
            merged[key], nested = _merge_missing(merged[key], value, dotted)
            added.extend(nested)
    return merged, added


def _atomic_json(path: Path, value: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Initialize system-dev-planner caller layout")
    p.add_argument("--repo-root")
    p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--asset", default=str(DEFAULT_ASSET))
    args = p.parse_args(argv)
    c09 = _resolver()
    try:
        root, source, evidence = c09.resolve_repo_root(args.repo_root, dict(os.environ))
        config_path = c09.guard_relative_path(root, args.config)
        defaults = json.loads(Path(args.asset).read_text(encoding="utf-8"))
        repository_id, id_source = c09.derive_repository_id(root)
        defaults["repository_id"] = repository_id
        defaults.pop("repository_id_note", None)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        actions: list[dict] = []
        if config_path.exists():
            current = json.loads(config_path.read_text(encoding="utf-8"))
            stored = current.get("repository_id")
            if stored not in (None, c09.SENTINEL_REPOSITORY_ID, repository_id):
                raise c09.PolicyError(f"existing repository_id mismatch: {stored} != {repository_id}")
            if stored in (None, c09.SENTINEL_REPOSITORY_ID):
                current["repository_id"] = repository_id
            merged, added = _merge_missing(current, defaults)
            if merged != current:
                _atomic_json(config_path, merged)
                actions.append({"path": args.config, "status": "merged_missing", "keys": added})
            else:
                actions.append({"path": args.config, "status": "skipped_same", "keys": []})
            config = merged
        else:
            _atomic_json(config_path, defaults)
            config = defaults
            actions.append({"path": args.config, "status": "created"})

        for section in ("content_roots", "local_state", "plan_roots"):
            for rel in config.get(section, {}).values():
                target = c09.guard_relative_path(root, str(rel))
                # File-like local_state values (for example graph.json) create only the parent.
                directory = target.parent if Path(str(rel)).suffix else target
                if directory.exists():
                    actions.append({"path": directory.relative_to(root).as_posix(), "status": "skipped_existing"})
                else:
                    directory.mkdir(parents=True, exist_ok=False)
                    actions.append({"path": directory.relative_to(root).as_posix(), "status": "created"})
        receipt = {
            "schema_version": "1.0.0", "status": "initialized", "repo_root": str(root),
            "root_source": source, "root_trust_evidence": evidence,
            "repository_id": repository_id, "repository_id_source": id_source, "actions": actions,
        }
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, c09.UsageError) as exc:
        print(f"[init] {exc}", file=sys.stderr)
        return 1
    except c09.PolicyError as exc:
        print(f"[init fail-closed] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
