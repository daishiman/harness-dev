#!/usr/bin/env python3
# /// script
# name: resolve-project-context
# purpose: symlink 導入先の caller repository root を --repo-root > trusted env > git toplevel > cwd marker の順で解決し、候補 realpath が host 宣言 $CLAUDE_PROJECT_DIR と一致する場合だけ採用する。repo-local config の repository_id を canonical GitHub remote / local git-dir fingerprint から再導出して照合し、全 content/state path を realpath containment 検査して cross-repo read・absolute/traversal・symlink escape・broken content symlink を診断付き exit 2 で拒否する共有 repo-context resolver。
# inputs:
#   - argv: [--repo-root DIR] [--config REL] [--path REL]
#           [--feature-id ID --feature-context REL] [--json]
#   - env: SYSTEM_DEV_PROJECT_ROOT | CLAUDE_PROJECT_DIR | CLAUDE_PLUGIN_ROOT
# outputs:
#   - stdout: canonical repo context JSON (repo_root/root_source/repository_id/content roots/diagnostics)
#   - stderr: containment / identity / config violations
#   - exit: 0=OK / 1=usage or IO error / 2=fail-closed policy violation
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Caller repository context resolver (C09).

全 content/config/state の authority を「呼出元 repository root」に固定する単一の入口。
plugin source root (symlink 物理元) は code/assets のロードにだけ使い、管理 content の
正本にはしない。root の解決順・host 境界一致・repository_id 再導出・realpath containment を
一箇所へ閉じ、下流 (C08/C10/C11/C12 と C01/C07) はこの JSON を唯一の repo-context 入力にする。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import re
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_POLICY = 2

DEFAULT_CONFIG_REL = ".dev-graph/config.json"
SENTINEL_REPOSITORY_ID = "__DERIVED_AT_INIT__"

# project-config.schema.json の repository_id pattern と同値 (SSOT は schema)。
_GITHUB_ID = "github:"
_LOCAL_ID = "local:sha256:"


class PolicyError(Exception):
    """fail-closed (exit 2) となる契約違反。"""


class UsageError(Exception):
    """usage / IO error (exit 1)。"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(repo: Path, *args: str) -> str | None:
    """repo 内で git を実行し stdout を返す。失敗/未インストールは None。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _realpath(p: Path) -> Path:
    return Path(os.path.realpath(p))


# --------------------------------------------------------------------------- #
# root 解決
# --------------------------------------------------------------------------- #
def resolve_repo_root(repo_root_arg: str | None, env: dict) -> tuple[Path, str, dict]:
    """--repo-root > trusted env > git toplevel > cwd marker の順で候補を解く。

    返り値は (realpath 済み root, root_source, trust_evidence)。
    host 宣言 $CLAUDE_PROJECT_DIR が存在する場合、採用候補の realpath は
    その realpath と一致しなければ PolicyError (exit 2) にする。
    """
    candidate: Path | None = None
    source = None
    evidence: dict = {}

    if repo_root_arg:
        candidate = Path(repo_root_arg)
        source = "repo-root-flag"
    elif env.get("SYSTEM_DEV_PROJECT_ROOT"):
        candidate = Path(env["SYSTEM_DEV_PROJECT_ROOT"])
        source = "trusted-env:SYSTEM_DEV_PROJECT_ROOT"
    elif env.get("CLAUDE_PROJECT_DIR"):
        candidate = Path(env["CLAUDE_PROJECT_DIR"])
        source = "trusted-env:CLAUDE_PROJECT_DIR"
    else:
        toplevel = _git(Path.cwd(), "rev-parse", "--show-toplevel")
        if toplevel:
            candidate = Path(toplevel)
            source = "git-toplevel"
        else:
            marker = _find_marker_upwards(Path.cwd())
            if marker:
                candidate = marker
                source = "cwd-marker"

    if candidate is None:
        raise PolicyError(
            "caller repository root を解決できない "
            "(--repo-root / SYSTEM_DEV_PROJECT_ROOT / CLAUDE_PROJECT_DIR / git / .dev-graph marker のいずれも無い)"
        )
    if not candidate.exists():
        raise PolicyError(f"解決した repo root が存在しない: {candidate} (source={source})")

    root_real = _realpath(candidate)

    declared = env.get("CLAUDE_PROJECT_DIR")
    if declared:
        declared_real = _realpath(Path(declared))
        evidence["host_declared"] = str(declared_real)
        if root_real != declared_real:
            raise PolicyError(
                f"root 候補 ({root_real}, source={source}) が host 宣言 $CLAUDE_PROJECT_DIR "
                f"({declared_real}) と realpath 不一致。曖昧な候補は採用しない"
            )
        evidence["host_boundary_match"] = True
    else:
        evidence["host_declared"] = None
        evidence["host_boundary_match"] = "undeclared-git-or-marker-accepted"

    return root_real, source, evidence


def _find_marker_upwards(start: Path) -> Path | None:
    cur = _realpath(start)
    for parent in [cur, *cur.parents]:
        if (parent / DEFAULT_CONFIG_REL).is_file():
            return parent
    return None


# --------------------------------------------------------------------------- #
# repository_id の再導出
# --------------------------------------------------------------------------- #
def derive_repository_id(repo_root: Path) -> tuple[str, str]:
    """canonical GitHub remote から github:<owner>/<repo>、無ければ
    git common-dir realpath の sha256 で local:sha256:<64hex> を導出する。

    C10 init と同じ規則。返り値は (repository_id, source)。
    """
    import hashlib

    remote = _git(repo_root, "remote", "get-url", "origin")
    gh = _parse_github_remote(remote) if remote else None
    if gh:
        return gh, "git-remote-origin"

    common = _git(repo_root, "rev-parse", "--git-common-dir")
    if common:
        common_path = Path(common)
        if not common_path.is_absolute():
            common_path = repo_root / common_path
        fingerprint = hashlib.sha256(str(_realpath(common_path)).encode("utf-8")).hexdigest()
        return f"{_LOCAL_ID}{fingerprint}", "local-git-dir-fingerprint"

    # git を持たない repo は root realpath を最後の拠り所にする。
    fingerprint = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()
    return f"{_LOCAL_ID}{fingerprint}", "local-root-fingerprint"


def _parse_github_remote(url: str) -> str | None:
    """GitHub remote を host 完全一致で正規化する。

    URL 形式と scp-like ``git@github.com:owner/repo.git`` のみを受理する。
    ``evilgithub.com`` や ``github.com.example`` を部分文字列で GitHub と誤認しない。
    """
    u = url.strip()
    host: str | None
    tail: str
    scp = re.fullmatch(r"(?:[^@/:]+@)?([^/:]+):(.+)", u)
    if scp and "://" not in u:
        host, tail = scp.group(1).lower(), scp.group(2)
    else:
        try:
            parsed = urlsplit(u)
        except ValueError:
            return None
        host = parsed.hostname.lower() if parsed.hostname else None
        tail = parsed.path
    if host != "github.com":
        return None
    tail = tail.strip("/")
    if tail.endswith(".git"):
        tail = tail[:-4]
    parts = [seg for seg in tail.split("/") if seg]
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        return None
    owner, repo = parts[0], parts[1]
    return f"{_GITHUB_ID}{owner}/{repo}"


def _valid_repository_id(value: str) -> bool:
    import re
    return bool(re.fullmatch(
        r"github:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|local:sha256:[0-9a-f]{64}", value
    ))


# --------------------------------------------------------------------------- #
# path guard (realpath containment)
# --------------------------------------------------------------------------- #
def guard_relative_path(repo_root: Path, rel: str) -> Path:
    """repo-relative path を containment 検査し、resolve 済み絶対 path を返す。

    absolute / 空 / '..' segment / NUL を拒否し、既存対象は strict realpath、
    未作成対象は実在する最長親を realpath 化して commonpath 検査する。
    root 外へ逃げる (symlink escape 含む) 場合は PolicyError (exit 2)。
    """
    if rel is None or rel == "":
        raise PolicyError("空の path は許可しない")
    if "\x00" in rel:
        raise PolicyError(f"NUL を含む path を拒否: {rel!r}")
    p = Path(rel)
    if p.is_absolute() or (len(rel) >= 2 and rel[1] == ":"):
        raise PolicyError(f"absolute path を拒否 (repository 相対のみ許可): {rel}")
    if ".." in p.parts:
        raise PolicyError(f".. traversal を含む path を拒否: {rel}")

    repo_real = _realpath(repo_root)
    candidate = repo_root / p
    if candidate.exists():
        cand_real = _realpath(candidate)
    else:
        # 実在する最長の親を realpath 化する (作成予定対象)。
        anchor = candidate.parent
        while not anchor.exists() and anchor != anchor.parent:
            anchor = anchor.parent
        anchor_real = _realpath(anchor)
        cand_real = anchor_real / candidate.relative_to(anchor) if anchor.exists() else candidate

    try:
        common = os.path.commonpath([str(repo_real), str(cand_real)])
    except ValueError as exc:  # 異なる drive 等
        raise PolicyError(f"containment 判定不能 (別 filesystem/drive?): {rel} ({exc})") from exc
    if common != str(repo_real):
        raise PolicyError(
            f"realpath containment 違反: {rel} が repository root ({repo_real}) の外を指す "
            f"(resolved={cand_real})"
        )
    return cand_real


def validate_feature_context(repo_root: Path, feature_id: str, rel: str) -> dict:
    """Validate the only plan input before any staging path may be created."""
    path = guard_relative_path(repo_root, rel)
    if not path.is_file():
        raise UsageError(f"feature context が見つからない: {rel}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"feature context を読めない: {rel} ({exc})") from exc
    if not isinstance(value, dict):
        raise PolicyError("feature context は JSON object 必須")
    required = {
        "graph_node_id", "artifact_kind", "purpose", "goal", "scope_in",
        "scope_out", "acceptance", "architecture_refs", "updated_at",
    }
    if set(value) != required:
        raise PolicyError(
            f"feature context field exact-set 違反: missing={sorted(required - set(value))} "
            f"extra={sorted(set(value) - required)}"
        )
    if value["graph_node_id"] != feature_id:
        raise PolicyError(
            f"feature id 不一致: --feature-id={feature_id!r} vs context={value['graph_node_id']!r}"
        )
    if value["artifact_kind"] != "feature":
        raise PolicyError("feature context artifact_kind は 'feature' 必須")
    for key in ("graph_node_id", "purpose", "goal"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise PolicyError(f"feature context {key} は非空文字列必須")
    for key in ("scope_in", "scope_out", "acceptance", "architecture_refs"):
        items = value[key]
        if not isinstance(items, list) or not items or any(
            not isinstance(item, str) or not item.strip() for item in items
        ):
            raise PolicyError(f"feature context {key} は非空 string[] 必須")
    try:
        parsed = datetime.fromisoformat(str(value["updated_at"]).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError as exc:
        raise PolicyError("feature context updated_at は timezone 付き RFC3339 必須") from exc
    architecture_paths: list[str] = []
    for ref in value["architecture_refs"]:
        target = guard_relative_path(repo_root, ref)
        if not target.exists():
            raise PolicyError(f"feature context architecture_ref が存在しない: {ref}")
        architecture_paths.append(ref)
    return {
        "path": rel,
        "graph_node_id": feature_id,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "architecture_refs": architecture_paths,
    }


def _diagnose_content_symlink(repo_root: Path, rel: str, diagnostics: list) -> None:
    """content symlink が broken/moved なら診断を積む (exists=False の symlink)。"""
    p = repo_root / rel
    if p.is_symlink() and not p.exists():
        diagnostics.append({
            "kind": "broken-content-symlink",
            "path": rel,
            "detail": "symlink が解決先を失っている (broken/moved)。C09 起動後の検査で拒否対象",
        })


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def load_config(repo_root: Path, config_rel: str) -> dict:
    cfg_abs = guard_relative_path(repo_root, config_rel)
    if not Path(cfg_abs).is_file():
        raise UsageError(f"repo-local config が見つからない: {config_rel} (init 未実行の可能性)")
    try:
        return json.loads(Path(cfg_abs).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"config を読めない: {config_rel} ({exc})") from exc


def validate_and_resolve(repo_root: Path, config: dict, extra_path: str | None) -> dict:
    diagnostics: list = []

    stored_id = str(config.get("repository_id", ""))
    if stored_id == SENTINEL_REPOSITORY_ID or not _valid_repository_id(stored_id):
        raise PolicyError(
            f"config.repository_id が sentinel/不正: {stored_id!r}。"
            "C10 init が canonical remote / git-dir fingerprint から導出済みの値である必要がある"
        )
    derived_id, id_source = derive_repository_id(repo_root)
    if derived_id != stored_id:
        raise PolicyError(
            f"repository_id 不一致: config={stored_id} vs 再導出={derived_id} "
            f"(source={id_source})。repo 移動時は明示 rebind が必要"
        )

    resolved_roots: dict[str, dict] = {}
    for section in ("content_roots", "local_state", "plan_roots"):
        sec = config.get(section)
        if not isinstance(sec, dict):
            raise PolicyError(f"config.{section} が object でない")
        resolved_roots[section] = {}
        for key, rel in sec.items():
            abs_path = guard_relative_path(repo_root, str(rel))
            _diagnose_content_symlink(repo_root, str(rel), diagnostics)
            resolved_roots[section][key] = {"relative": rel, "absolute": str(abs_path)}

    extra = None
    if extra_path:
        extra_abs = guard_relative_path(repo_root, extra_path)
        _diagnose_content_symlink(repo_root, extra_path, diagnostics)
        extra = {"relative": extra_path, "absolute": str(extra_abs)}

    return {
        "repository_id": stored_id,
        "repository_id_source": id_source,
        "resolved_roots": resolved_roots,
        "checked_path": extra,
        "diagnostics": diagnostics,
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build_context(argv: list[str] | None, env: dict) -> dict:
    parser = argparse.ArgumentParser(description="Resolve caller repository context (C09)")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--config", default=DEFAULT_CONFIG_REL)
    parser.add_argument("--path", default=None, help="追加で containment 検査する repo-relative path")
    parser.add_argument("--feature-id", default=None, help="plan input の dev-graph feature id")
    parser.add_argument("--feature-context", default=None, help="plan input の repo-relative feature JSON")
    parser.add_argument("--json", action="store_true", help="常に JSON を stdout に出す (既定)")
    args = parser.parse_args(argv)

    repo_root, root_source, evidence = resolve_repo_root(args.repo_root, env)
    config = load_config(repo_root, args.config)
    resolved = validate_and_resolve(repo_root, config, args.path)
    if bool(args.feature_id) != bool(args.feature_context):
        raise UsageError("--feature-id と --feature-context は同時指定必須")
    feature_context = (
        validate_feature_context(repo_root, args.feature_id, args.feature_context)
        if args.feature_id and args.feature_context else None
    )

    plugin_root = env.get("CLAUDE_PLUGIN_ROOT")
    plugin_source = str(_realpath(Path(plugin_root))) if plugin_root else None

    return {
        "schema": "resolve-project-context/1.0.0",
        "repo_root": str(repo_root),
        "root_source": root_source,
        "root_trust_evidence": evidence,
        "repository_id": resolved["repository_id"],
        "repository_id_source": resolved["repository_id_source"],
        "config_path": args.config,
        "content_roots": resolved["resolved_roots"]["content_roots"],
        "local_state": resolved["resolved_roots"]["local_state"],
        "plan_roots": resolved["resolved_roots"]["plan_roots"],
        "checked_path": resolved["checked_path"],
        "feature_context": feature_context,
        "plugin_source": plugin_source,
        "plugin_source_authority": "code-and-assets-only",
        "resolved_at": _now(),
        "diagnostics": resolved["diagnostics"],
    }


def main(argv: list[str] | None = None) -> int:
    try:
        context = build_context(argv, dict(os.environ))
    except PolicyError as exc:
        print(f"[fail-closed] {exc}", file=sys.stderr)
        return EXIT_POLICY
    except UsageError as exc:
        print(f"[usage] {exc}", file=sys.stderr)
        return EXIT_USAGE

    if context["diagnostics"]:
        # broken/moved content symlink 等は fail-closed 対象。
        print(
            "[fail-closed] content symlink diagnostics: "
            + json.dumps(context["diagnostics"], ensure_ascii=False),
            file=sys.stderr,
        )
        print(json.dumps(context, ensure_ascii=False, indent=2))
        return EXIT_POLICY

    print(json.dumps(context, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
