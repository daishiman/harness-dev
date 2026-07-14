#!/usr/bin/env python3
# /// script
# name: resolve-repo-context
# purpose: Resolve and verify worktree content authority and shared Git coordination authority.
# inputs: ["argv: --repo-root PATH? --config PATH --mode read|write"]
# outputs: ["stdout: JSON repository/worktree context"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, contained, dump, git, load_json, stable_id


DEFAULT_CONTENT_ROOTS = {
    "issues": "issues",
    "tasks": "tasks",
    "specifications": "specs",
    "architecture": "architecture",
    "features": "features",
    "documents": "docs",
    "system_spec": "system-spec",
}
DEFAULT_LOCAL_STATE = {
    "graph": ".dev-graph/state/graph.json",
    "cache": ".dev-graph/cache",
    "locks": ".dev-graph/locks",
}
GITHUB_REMOTE = re.compile(
    r"^(?:https?://github\.com/|ssh://git@github\.com/|git@github\.com:)([^/]+)/(.+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def discover(explicit: str | None) -> tuple[Path, str]:
    choices: list[tuple[str, str]] = []
    if explicit:
        choices.append((explicit, "explicit --repo-root"))
    trusted = os.environ.get("CLAUDE_PROJECT_DIR")
    if trusted:
        choices.append((trusted, "CLAUDE_PROJECT_DIR"))
    cp = __import__("subprocess").run(
        ["git", "rev-parse", "--show-toplevel"], text=True, capture_output=True, check=False
    )
    if cp.returncode == 0:
        choices.append((cp.stdout.strip(), "git toplevel"))
    for parent in (Path.cwd(), *Path.cwd().parents):
        if (parent / ".git").exists() or (parent / ".dev-graph").is_dir():
            choices.append((str(parent), "cwd marker"))
            break
    if not choices:
        raise ContractError("repository root cannot be resolved")
    root = Path(choices[0][0]).expanduser().resolve(strict=True)
    actual = Path(git(["rev-parse", "--show-toplevel"], root)).resolve(strict=True)
    if root != actual:
        raise ContractError(f"selected root is not current worktree root: {root} != {actual}")
    if trusted and Path(trusted).expanduser().resolve(strict=True) != root:
        raise ContractError("--repo-root and CLAUDE_PROJECT_DIR disagree")
    return root, choices[0][1]


def repository_id_for(remote: str, common: Path) -> str:
    """Derive the durable repository identity from the canonical authority."""
    match = GITHUB_REMOTE.fullmatch(remote.strip()) if remote else None
    if match:
        owner, repository = match.groups()
        return f"github:{owner}/{repository.removesuffix('.git')}"
    digest = hashlib.sha256(str(common.resolve(strict=True)).encode("utf-8")).hexdigest()
    return f"local:sha256:{digest}"


def _absolute_git_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    return (root / path).resolve(strict=True) if not path.is_absolute() else path.resolve(strict=True)


def verify_common_ownership(root: Path, git_dir: Path, common: Path) -> None:
    """Prove that the selected worktree and common directory are one repository."""
    try:
        objects = _absolute_git_path(git(["rev-parse", "--git-path", "objects"], root), root)
        config = _absolute_git_path(git(["rev-parse", "--git-path", "config"], root), root)
        common_objects = (common / "objects").resolve(strict=True)
        common_config = (common / "config").resolve(strict=True)
    except OSError as exc:
        raise ContractError(f"git common dir authority is incomplete: {common}: {exc}") from exc
    if objects != common_objects:
        raise ContractError("git common dir objects authority does not belong to selected repository")
    if config != common_config:
        raise ContractError("git common dir config authority does not belong to selected repository")
    if git_dir != common:
        marker = git_dir / "commondir"
        if not marker.is_file() or marker.is_symlink():
            raise ContractError(f"worktree git dir has no trusted commondir marker: {marker}")
        try:
            declared = (git_dir / marker.read_text(encoding="utf-8").strip()).resolve(strict=True)
        except OSError as exc:
            raise ContractError(f"invalid worktree commondir marker: {marker}: {exc}") from exc
        if declared != common:
            raise ContractError(f"worktree commondir mismatch: {declared} != {common}")
    root_remote = git(["remote", "get-url", "origin"], root, check=False)
    common_remote = git(["--git-dir", str(common), "remote", "get-url", "origin"], root, check=False)
    if root_remote != common_remote:
        raise ContractError("worktree and git common dir resolve different origin remotes")


def _validate_relative(raw: Any, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise ContractError(f"{label} must be a non-empty repository-relative path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ContractError(f"{label} escapes repository authority: {raw}")
    return relative


def resolve_declared_path(root: Path, raw: Any, label: str, *, reject_leaf_symlink: bool) -> Path:
    """Resolve an existing target or its longest existing parent without escaping root."""
    relative = _validate_relative(raw, label)
    candidate = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            try:
                target = current.resolve(strict=True)
            except OSError as exc:
                raise ContractError(f"broken content symlink for {label}: {current}: {exc}") from exc
            contained(target, root)
            if reject_leaf_symlink:
                raise ContractError(f"content root path must not traverse a symlink: {label}={current}")
        if not current.exists() and not current.is_symlink():
            break
    try:
        resolved = candidate.resolve(strict=True) if candidate.exists() or candidate.is_symlink() else candidate.resolve(strict=False)
    except OSError as exc:
        raise ContractError(f"cannot resolve {label}: {candidate}: {exc}") from exc
    contained(resolved, root, must_exist=False)
    return resolved


def resolve_config_paths(root: Path, config: dict[str, Any] | None) -> tuple[dict[str, str], dict[str, str]]:
    config = config or {}
    policy = config.get("path_policy") or {}
    if not isinstance(policy, dict):
        raise ContractError("path_policy must be an object")
    forbidden = (
        policy.get("authority") not in {None, "caller-repository"}
        or policy.get("allow_outside_repository") not in {None, False}
        or policy.get("follow_content_symlinks_outside_repository") not in {None, False}
    )
    if forbidden:
        raise ContractError("path_policy weakens caller-repository containment")
    content = config.get("content_roots") or DEFAULT_CONTENT_ROOTS
    local = config.get("local_state") or DEFAULT_LOCAL_STATE
    if not isinstance(content, dict) or not isinstance(local, dict):
        raise ContractError("content_roots and local_state must be objects")
    resolved_content = {
        key: str(resolve_declared_path(root, value, f"content_roots.{key}", reject_leaf_symlink=True))
        for key, value in sorted(content.items())
    }
    resolved_local = {
        key: str(resolve_declared_path(root, value, f"local_state.{key}", reject_leaf_symlink=False))
        for key, value in sorted(local.items())
    }
    return resolved_content, resolved_local


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root")
    parser.add_argument("--config", default=".dev-graph/config.json")
    parser.add_argument("--mode", choices=("read", "write"), default="read")
    args = parser.parse_args()
    root, trust = discover(args.repo_root)
    common_raw = git(["rev-parse", "--git-common-dir"], root)
    common = Path(common_raw)
    if not common.is_absolute():
        common = root / common
    common = common.resolve(strict=True)
    git_dir_raw = git(["rev-parse", "--git-dir"], root)
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    git_dir = git_dir.resolve(strict=True)
    verify_common_ownership(root, git_dir, common)
    remote = git(["remote", "get-url", "origin"], root, check=False)
    repository_id = repository_id_for(remote, common)
    config_arg = Path(args.config)
    if config_arg.is_absolute():
        config_path = contained(config_arg, root, must_exist=False)
    else:
        config_path = root / _validate_relative(args.config, "config")
    config = None
    diagnostics: list[str] = []
    if config_path.exists() or config_path.is_symlink():
        try:
            config_path = contained(config_path, root)
        except OSError as exc:
            raise ContractError(f"broken repository config symlink: {config_path}: {exc}") from exc
        config = load_json(config_path)
        if not isinstance(config, dict):
            raise ContractError("repo config must be a JSON object")
        configured = config.get("repository_id") if isinstance(config, dict) else None
        if configured and configured != repository_id:
            raise ContractError("repo config repository_id does not match derived repository")
    else:
        diagnostics.append("config_missing")
    content_roots, local_state_paths = resolve_config_paths(root, config)
    branch = git(["symbolic-ref", "--quiet", "--short", "HEAD"], root, check=False) or None
    head = git(["rev-parse", "HEAD"], root)
    default_ref = git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], root, check=False)
    default_branch = default_ref.rsplit("/", 1)[-1] if default_ref else (
        ((config or {}).get("worktrees") or {}).get("default_branch") if isinstance(config, dict) else None
    )
    if not default_branch:
        default_branch = "main"
        diagnostics.append("default_branch_fallback_main")
    worktree_id = stable_id("wt_", repository_id, str(root))
    coord = common / "dev-graph"
    plugin_source = Path(__file__).resolve().parents[1]
    trusted = os.environ.get("CLAUDE_PROJECT_DIR")
    result = {
        "repo_root": str(root), "repository_id": repository_id, "worktree_id": worktree_id,
        "git_common_dir": str(common), "git_dir": str(git_dir), "branch": branch,
        "head_sha": head, "default_branch": default_branch,
        "root_trust_evidence": {"selected_by": trust, "git_toplevel_verified": True,
                                "claude_project_dir_verified": not trusted or Path(trusted).resolve() == root,
                                "git_common_dir_ownership_verified": True},
        "content_roots": {"repository": str(root), **content_roots},
        "local_state_paths": {"config": str(config_path), **local_state_paths},
        "coordination_paths": {"root": str(coord), "leases": str(coord / "leases.json"),
                               "events": str(coord / "events.json")},
        "plugin_source": str(plugin_source), "mode": args.mode, "diagnostics": diagnostics,
    }
    dump(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
