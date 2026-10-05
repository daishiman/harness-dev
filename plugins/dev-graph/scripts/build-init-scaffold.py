#!/usr/bin/env python3
# /// script
# name: build-init-scaffold
# purpose: C01 init の決定論本体。C24 で解決した呼出し元 repo 内に 6 content root と .dev-graph の config/state/graph/cache/locks/templates を欠落時だけ作り、planned changes 0 の再実行は noop を返し、変更したときだけ immutable init receipt を残す。
# inputs: ["argv: --repo-root PATH [--config PATH] [--hook-source plugin|project-fallback] [--dry-run]"]
# outputs: ["stdout: JSON preview/noop/receipt or rejection report"]
# requires-python = ">=3.10"
# dependencies: [_common.py, validate-graph-schema.py, resolve-repo-context.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: caller repository content roots and .dev-graph/ (config, state, graph, cache, locks, templates, init receipts)
# ///
"""run-dev-graph-init の R3 (config/content/state) と R4 (templates) の scaffold。
hook の配線 (R5) は扱わず、選ばれた hook source を receipt に記録するだけにする。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import ContractError, contained, dump, load_json, utc_now

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
OWNER = "C01/run-dev-graph-init"
# 6 content root。system_spec は system-spec-harness (C19) が作るので init は作らない。
CONTENT_KEYS = ("issues", "tasks", "specifications", "architecture", "features", "documents")
EMPTY_GRAPH = {"graph_revision": 0, "nodes": [], "schema_version": "1.0.0"}
CONFIG_SCHEMA = PLUGIN_ROOT / "schemas" / "repo-config.schema.json"
EXAMPLE_CONFIG = PLUGIN_ROOT / "templates" / "repo-config.example.json"


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("dev_graph_validate_graph_schema", HERE / "validate-graph-schema.py")
    if spec is None or spec.loader is None:
        raise ContractError("cannot load validate-graph-schema.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VGS = _load_validator()


class InitError(ContractError):
    def __init__(self, code: str, detail: str, findings: list[dict[str, str]] | None = None) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.findings = code, detail, findings or []


def _context(repo_root: str, config: str) -> dict[str, Any]:
    argv = [sys.executable, str(HERE / "resolve-repo-context.py"), "--repo-root", repo_root,
            "--config", config, "--mode", "write"]
    cp = subprocess.run(argv, text=True, capture_output=True, check=False)
    if cp.returncode:
        raise InitError("c24_context_failed", (cp.stderr or cp.stdout).strip())
    ctx = json.loads(cp.stdout)
    root = Path(ctx["repo_root"]).resolve(strict=True)
    if Path(ctx["content_roots"]["repository"]).resolve(strict=True) != root:
        raise InitError("c24_context_failed", "content_roots.repository differs from repo_root")
    return ctx


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    # atomic_json と同じ直列化にして、init が作った file と writer が書き直した file の差を出さない。
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _issue_prefix(name: str) -> str:
    slug = re.sub(r"^[^a-z]+", "", re.sub(r"[^a-z0-9-]+", "-", name.lower())).strip("-")
    return slug or "dev-graph"


def _new_config(ctx: dict[str, Any], root: Path) -> dict[str, Any]:
    """example を雛形に、C24 が導出した repository_id を埋める。GitHub は enabled=false のまま。"""
    config = load_json(EXAMPLE_CONFIG)
    repository_id = ctx["repository_id"]
    config["repository_id"] = repository_id
    name = root.name
    if repository_id.startswith("github:"):
        config["github"]["issue_repository"] = repository_id.split(":", 1)[1]
        name = repository_id.rsplit("/", 1)[-1]
    config["execution_tracker"]["beads"]["issue_prefix"] = _issue_prefix(name)
    return config


def _config_findings(config: Any) -> list[dict[str, str]]:
    schema = load_json(CONFIG_SCHEMA)
    return [{**item, "node": "repo-config"} for item in VGS.schema_findings(config, schema, 0)]


def _plan(ctx: dict[str, Any], root: Path) -> dict[str, Any]:
    dirs: list[Path] = []
    files: list[tuple[Path, bytes]] = []
    preserved: list[Path] = []
    migration: list[dict[str, str]] = []

    def directory(path: Path) -> None:
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise InitError("path_not_directory", f"{path.relative_to(root).as_posix()} exists but is not a plain directory")
        (preserved if path.is_dir() else dirs).append(path)

    content = {key: contained(Path(ctx["content_roots"][key]), root, must_exist=False) for key in CONTENT_KEYS}
    local = {key: contained(Path(ctx["local_state_paths"][key]), root, must_exist=False)
             for key in ("config", "graph", "cache", "locks")}
    local["templates"] = contained(root / ".dev-graph" / "templates", root, must_exist=False)
    for path in [*content.values(), local["cache"], local["locks"], local["templates"]]:
        directory(path)

    for source in sorted(item for item in (PLUGIN_ROOT / "templates").iterdir() if item.is_file()):
        target = local["templates"] / source.name
        data = source.read_bytes()
        if not (target.exists() or target.is_symlink()):
            files.append((target, data))
        elif target.is_symlink() or not target.is_file():
            raise InitError("path_not_file", f"{target.relative_to(root).as_posix()} exists but is not a plain file")
        elif target.read_bytes() == data:
            preserved.append(target)
        else:
            # 利用者が編集した template は上書きしない。差分の所在だけを残す。
            preserved.append(target)
            migration.append({"path": target.relative_to(root).as_posix(), "plugin_sha256": _sha256(data),
                              "local_sha256": _sha256(target.read_bytes())})

    config_path, graph_path = local["config"], local["graph"]
    for path in (config_path, graph_path):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise InitError("path_not_file", f"{path.relative_to(root).as_posix()} exists but is not a plain file")
    if config_path.exists():
        config = load_json(config_path)
        preserved.append(config_path)
    else:
        config = _new_config(ctx, root)
        files.append((config_path, _json_bytes(config)))
    if graph_path.exists():
        graph = load_json(graph_path)
        preserved.append(graph_path)
    else:
        graph = EMPTY_GRAPH
        files.append((graph_path, _json_bytes(graph)))
    findings = _config_findings(config)
    try:
        findings += VGS.validate(VGS.nodes_of(graph), repo_root=root)
    except ContractError as exc:
        findings.append({"node": "graph", "code": "graph_invalid", "detail": str(exc)})
    if findings:
        # 既存の config/graph が gate を通らないまま scaffold を進めると、部分成功を成功に見せてしまう。
        raise InitError("pre_write_validation_failed", f"{len(findings)} config/graph finding(s)", findings)
    receipts = graph_path.parent / "receipts"
    existing = sorted(receipts.glob("init-*.json")) if receipts.is_dir() else []
    return {"content": content, "local": local, "dirs": dirs, "files": files, "preserved": preserved,
            "migration": migration, "receipts": receipts, "existing": existing,
            "schema_result": {"validator": "validate-graph-schema.py + repo-config.schema.json", "valid": True,
                              "violation_count": 0}}


def _create_file(path: Path, data: bytes) -> None:
    """create-only: 既にある file は決して上書きしない (receipt の不変性もこれで守る)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise InitError("path_appeared_during_init", str(path)) from exc
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def scaffold(args: argparse.Namespace) -> dict[str, Any]:
    ctx = _context(args.repo_root, args.config)
    root = Path(ctx["repo_root"]).resolve(strict=True)
    plan = _plan(ctx, root)

    def rel(path: Path) -> str:
        return path.relative_to(root).as_posix()

    changes = [*plan["dirs"], *(path for path, _ in plan["files"])]
    base = {
        "owner": OWNER, "repository_id": ctx["repository_id"],
        "content_roots": {key: rel(path) for key, path in plan["content"].items()},
        "local_state": {key: rel(path) for key, path in plan["local"].items()},
        "preserved": sorted(rel(path) for path in plan["preserved"]),
        "migration_preview": plan["migration"], "schema_result": plan["schema_result"],
    }
    if not changes and plan["existing"]:
        return {**base, "status": "noop", "valid": True, "dry_run": bool(args.dry_run), "idempotent": True,
                "planned_changes": 0, "created": [], "write_count": 0, "receipt_path": rel(plan["existing"][-1])}
    now = utc_now()
    receipt_path = plan["receipts"] / f"init-{re.sub(r'[^0-9TZ]', '', now)}.json"
    # 手作業の init で receipt だけが無い repo では、receipt を残すこと自体が唯一の planned change になる。
    receipt = {**base, "schema_version": "1.0.0", "status": "applied", "recorded_at": now, "hook_source": args.hook_source,
               "created": sorted(rel(path) for path in changes), "planned_changes": len(changes) + 1,
               "receipt_path": rel(receipt_path)}
    if args.dry_run:
        return {**receipt, "status": "preview", "valid": True, "dry_run": True, "write_count": 0}
    made_dirs: list[Path] = []
    made_files: list[Path] = []
    try:
        for path in plan["dirs"]:
            missing = [parent for parent in [path, *path.parents] if not parent.exists()]
            path.mkdir(parents=True, exist_ok=True)
            made_dirs += reversed(missing)
        for path, data in plan["files"]:
            _create_file(path, data)
            made_files.append(path)
        _create_file(receipt_path, _json_bytes(receipt))
    except BaseException:
        # init は作るだけなので、作ったものを逆順に消せば元の状態に戻る。
        for path in reversed(made_files):
            path.unlink(missing_ok=True)
        for path in reversed(made_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        raise
    return {**receipt, "valid": True, "dry_run": False, "write_count": len(changes) + 1}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C01 init scaffold (欠落時だけ作る・再実行は noop・immutable receipt)")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--config", default=".dev-graph/config.json")
    parser.add_argument("--hook-source", choices=("plugin", "project-fallback"), default="plugin",
                        help="R5 で配線する hook source。receipt に記録するだけで settings は触らない")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        dump(scaffold(args))
        return 0
    except InitError as exc:
        dump({"valid": False, "status": "rejected", "code": exc.code, "error": exc.detail, "findings": exc.findings,
              "planned_changes": None, "write_count": 0})
        return 1
    except (ContractError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        dump({"valid": False, "status": "error", "code": type(exc).__name__, "error": str(exc), "write_count": 0})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
