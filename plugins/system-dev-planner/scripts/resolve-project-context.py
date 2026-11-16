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
#   - exit: 0=OK / 1=usage or IO error (argparse の使い方の誤り・空の --repo-root / --feature-id / --feature-context・読めない/UTF-8 でない/JSON でない config と feature context・UTF-8 でない git の出力・stat できない path) / 2=fail-closed policy violation (object でない config・文字列でない section 値・空/絶対/'..' の path を含む。path の字面の誤りは root を読む前に返す)
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
import errno
import hashlib
import json
import os
import subprocess
import sys
import re
from stat import S_ISLNK, S_ISREG
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
# project-config.schema.json の relative_path pattern の `(?![A-Za-z]:[\\/])` と同値。OS に依らず
# drive つきの絶対 path を拒否する (`a:b` のような POSIX の正しい相対名は通す)
_WINDOWS_ABS_RE = re.compile(r"[A-Za-z]:[\\/]")
# RFC 3339 の date-time (5.6)。fromisoformat だけでは、区切りの無い basic 形式・時だけ・週の日付・
# NUL 混じりも通る (通る範囲は 3.10〜3.13 で違う)。形はこの式で決め、日付と時刻の範囲だけを
# fromisoformat に確かめさせる。数字は [0-9] に限る (\d は全角などの Unicode の数字も通す)
_RFC3339_RE = re.compile(
    r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})[Tt](?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.[0-9]+)?"
    r"(?P<offset>[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


class PolicyError(Exception):
    """fail-closed (exit 2) となる契約違反。"""


class UsageError(Exception):
    """usage / IO error (exit 1)。"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(repo: Path, *args: str) -> str | None:
    """repo 内で git を実行し stdout を返す。失敗/未インストールは None、出力が UTF-8 でなければ UsageError。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, encoding="utf-8", timeout=10,
        )
    except UnicodeDecodeError as exc:
        # 読めない出力を None (git が無い) と同じに扱うと、repository_id の出所が黙って remote から
        # fingerprint に変わる。読めない config と同じく IO error (exit 1) で止める
        raise UsageError(f"git {' '.join(args)} の出力が UTF-8 でない ({exc})") from exc
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _realpath(p: Path) -> Path:
    return Path(os.path.realpath(p))


# 「無い」とみなす errno (pathlib の _ignore_error と同じ組)。ほか (ENAMETOOLONG・EACCES など) は「確かめられない」
_ABSENT_ERRNOS = frozenset({errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP})


def _stat(path: Path, what: str, *, follow: bool = True) -> os.stat_result | None:
    """path を stat (follow=False なら lstat) し、無ければ None。確かめられなければ IO error (UsageError, exit 1)。

    pathlib の exists / is_file / is_symlink に任せると、ENAMETOOLONG や EACCES が traceback になるか
    False になるかが Python の版で変わる。errno を自分で分け、どの版でも同じ答えを返す。
    """
    try:
        return os.stat(path) if follow else os.lstat(path)
    except OSError as exc:
        if exc.errno in _ABSENT_ERRNOS:
            return None
        raise UsageError(f"{what} を確かめられない: {path} ({type(exc).__name__}: {exc})") from exc


def _is_file(path: Path, what: str) -> bool:
    st = _stat(path, what)
    return st is not None and S_ISREG(st.st_mode)


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

    if repo_root_arg is not None:
        if not repo_root_arg:
            # 明示した空の root を、黙って env や git の候補に倒さない (書く側の init-project-layout もここを通る。
            # 空の値を真偽値で落として渡さない呼ぶ側は、ここに届かない)
            raise UsageError("--repo-root に空の値は渡せない")
        candidate = Path(repo_root_arg)
        source = "repo-root-flag"
    elif env.get("SYSTEM_DEV_PROJECT_ROOT"):
        candidate = Path(env["SYSTEM_DEV_PROJECT_ROOT"])
        source = "trusted-env:SYSTEM_DEV_PROJECT_ROOT"
    elif env.get("CLAUDE_PROJECT_DIR"):
        candidate = Path(env["CLAUDE_PROJECT_DIR"])
        source = "trusted-env:CLAUDE_PROJECT_DIR"
    else:
        try:
            cwd = Path.cwd()
        except OSError as exc:  # cwd が消えている
            raise UsageError(f"cwd を読めない ({type(exc).__name__}: {exc})") from exc
        toplevel = _git(cwd, "rev-parse", "--show-toplevel")
        if toplevel:
            candidate = Path(toplevel)
            source = "git-toplevel"
        else:
            marker = _find_marker_upwards(cwd)
            if marker:
                candidate = marker
                source = "cwd-marker"

    if candidate is None:
        raise PolicyError(
            "caller repository root を解決できない "
            "(--repo-root / SYSTEM_DEV_PROJECT_ROOT / CLAUDE_PROJECT_DIR / git / .dev-graph marker のいずれも無い)"
        )
    if _stat(candidate, "repo root") is None:
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
        # host の宣言は無い。呼ぶ側が root を明示したのか、git や marker から拾ったのかを分けて残す
        explicit = source in ("repo-root-flag", "trusted-env:SYSTEM_DEV_PROJECT_ROOT")
        evidence["host_boundary_match"] = (
            "undeclared-explicit-root-accepted" if explicit else "undeclared-git-or-marker-accepted"
        )

    return root_real, source, evidence


def _find_marker_upwards(start: Path) -> Path | None:
    cur = _realpath(start)
    for parent in [cur, *cur.parents]:
        if _is_file(parent / DEFAULT_CONFIG_REL, ".dev-graph marker"):
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
    return bool(re.fullmatch(
        r"github:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|local:sha256:[0-9a-f]{64}", value
    ))


# --------------------------------------------------------------------------- #
# path guard (realpath containment)
# --------------------------------------------------------------------------- #
def _check_relative_literal(rel: str) -> Path:
    """root を読まずに字面だけで決まる誤り (空 / NUL / absolute / drive / '..' segment) を PolicyError にする。"""
    if rel is None or rel == "":
        raise PolicyError("空の path は許可しない")
    if "\x00" in rel:
        raise PolicyError(f"NUL を含む path を拒否: {rel!r}")
    p = Path(rel)
    # p.drive は Windows の drive 相対 (`C:x`) を、正規表現は OS に依らず drive つきの絶対 path を拒否する
    if p.is_absolute() or p.drive or _WINDOWS_ABS_RE.match(rel):
        raise PolicyError(f"absolute path を拒否 (repository 相対のみ許可): {rel}")
    if ".." in p.parts:
        raise PolicyError(f".. traversal を含む path を拒否: {rel}")
    return p


def guard_relative_path(repo_root: Path, rel: str) -> Path:
    """repo-relative path を containment 検査し、resolve 済み絶対 path を返す。

    字面の誤りは _check_relative_literal で拒否し、既存対象は strict realpath、
    未作成対象は実在する最長親を realpath 化して commonpath 検査する。
    root 外へ逃げる (symlink escape 含む) 場合は PolicyError (exit 2)。
    """
    p = _check_relative_literal(rel)

    repo_real = _realpath(repo_root)
    candidate = repo_root / p
    # 葉そのものから、lexists で在る最長の path を探して realpath に通す (作成予定対象)。
    # 葉が先の無い symlink でも、途中が壊れた symlink でも、exists だけを見ると飛ばしてしまい、
    # 外を指していても素通りする。葉から始めれば、先の無い葉の symlink も解決先で確かめる。
    anchor = candidate
    while not os.path.lexists(anchor) and anchor != anchor.parent:
        anchor = anchor.parent
    cand_real = _realpath(anchor) / candidate.relative_to(anchor) if os.path.lexists(anchor) else candidate

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
    if not _is_file(path, "feature context"):
        raise UsageError(f"feature context が見つからない: {rel}")
    try:
        # 一度だけ bytes で読み、検査する中身と sha256 を同じ bytes から取る (間の書き換えで食い違わない)
        data = path.read_bytes()
        value = json.loads(data.decode("utf-8"))
    # ValueError は UnicodeDecodeError・JSONDecodeError と、4300 桁を超える int の文字列 (int の桁の上限) を含む
    except (OSError, ValueError, RecursionError) as exc:
        raise UsageError(f"feature context を読めない: {rel} ({type(exc).__name__}: {exc})") from exc
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
    updated_at = value["updated_at"]
    match = _RFC3339_RE.fullmatch(updated_at) if isinstance(updated_at, str) else None
    try:
        if match is None:
            raise ValueError
        # 小数秒は式で確かめ済み (3.10 の fromisoformat は 3 桁と 6 桁しか読まない) なので外して渡す
        offset = "+00:00" if match["offset"].upper() == "Z" else match["offset"]
        datetime.fromisoformat(f"{match['date']}T{match['time']}{offset}")
    except ValueError as exc:
        raise PolicyError("feature context updated_at は timezone 付き RFC3339 必須") from exc
    architecture_paths: list[str] = []
    for ref in value["architecture_refs"]:
        target = guard_relative_path(repo_root, ref)
        if _stat(target, "architecture_ref") is None:
            raise PolicyError(f"feature context architecture_ref が存在しない: {ref}")
        architecture_paths.append(ref)
    return {
        "path": rel,
        "graph_node_id": feature_id,
        "sha256": hashlib.sha256(data).hexdigest(),
        "architecture_refs": architecture_paths,
    }


def _diagnose_content_symlink(repo_root: Path, rel: str, diagnostics: list) -> None:
    """content symlink が broken/moved なら診断を積む (exists=False の symlink)。

    葉だけでなく途中の component も root 側から順に見る (`blink/sub` の `blink` が壊れていても拾う)。
    途中の component のときは broken_component にその相対 path を足す。
    """
    parts = Path(rel).parts
    for depth in range(1, len(parts) + 1):
        p = repo_root.joinpath(*parts[:depth])
        exists = _stat(p, "content path") is not None
        link = None if exists else _stat(p, "content path", follow=False)
        if link is not None and S_ISLNK(link.st_mode):
            entry = {
                "kind": "broken-content-symlink",
                "path": rel,
                "detail": "symlink が解決先を失っている (broken/moved)。C09 起動後の検査で拒否対象",
            }
            if depth < len(parts):
                entry["broken_component"] = Path(*parts[:depth]).as_posix()
            diagnostics.append(entry)
            return
        if not exists:
            return  # ここから先は未作成 (作成予定)。symlink も無い


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def load_config(repo_root: Path, config_rel: str) -> dict:
    cfg_abs = guard_relative_path(repo_root, config_rel)
    if not _is_file(Path(cfg_abs), "repo-local config"):
        raise UsageError(f"repo-local config が見つからない: {config_rel} (init 未実行の可能性)")
    try:
        return json.loads(Path(cfg_abs).read_text(encoding="utf-8"))
    # ValueError は UnicodeDecodeError・JSONDecodeError と、4300 桁を超える int の文字列 (int の桁の上限) を含む
    except (OSError, ValueError, RecursionError) as exc:
        raise UsageError(f"config を読めない: {config_rel} ({type(exc).__name__}: {exc})") from exc


def validate_and_resolve(
    repo_root: Path, config: dict, extra_path: str | None, *, require_plan_roots: bool = True
) -> dict:
    """identity と全 section の containment を検査する。

    require_plan_roots=False は C07 guard の lock 探索専用の最小モード。plan_roots は sdp 追加
    section (dev-graph init 単独では作られない) なので、**欠落**だけを「sdp 未初期化」として
    None で返す。存在するのに object でない / containment 違反は従来どおり PolicyError。
    repository_id・content_roots・local_state の検査はモードに依らず常に fail-closed。
    """
    diagnostics: list = []

    if not isinstance(config, dict):
        raise PolicyError(f"config は JSON object 必須 (実際は {type(config).__name__})")
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

    resolved_roots: dict[str, dict | None] = {}
    for section in ("content_roots", "local_state", "plan_roots"):
        if section == "plan_roots" and not require_plan_roots and section not in config:
            resolved_roots[section] = None  # sdp 未初期化 (C10 init 前)。不正値とは区別する
            continue
        sec = config.get(section)
        if not isinstance(sec, dict):
            raise PolicyError(f"config.{section} が object でない")
        resolved_roots[section] = {}
        for key, rel in sec.items():
            # schema の relative_path は文字列。str() で通すと null が「None」という path になる
            if not isinstance(rel, str):
                raise PolicyError(f"config.{section}.{key} は repository 相対 path の文字列必須: {rel!r}")
            abs_path = guard_relative_path(repo_root, rel)
            _diagnose_content_symlink(repo_root, rel, diagnostics)
            resolved_roots[section][key] = {"relative": rel, "absolute": str(abs_path)}

    extra = None
    if extra_path is not None:  # 空の --path も飛ばさず guard に通して断る
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
class _ArgumentParser(argparse.ArgumentParser):
    """使い方の誤りを UsageError (exit 1) にする。argparse の既定の exit 2 は policy の 2 と重なる。"""

    def error(self, message):
        raise UsageError(f"{message}\n{self.format_usage().rstrip()}")


def build_context(argv: list[str] | None, env: dict, *, require_plan_roots: bool = True) -> dict:
    """require_plan_roots=False は C07 guard 専用 (validate_and_resolve 参照)。CLI は常に True。"""
    parser = _ArgumentParser(description="Resolve caller repository context (C09)")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--config", default=DEFAULT_CONFIG_REL)
    parser.add_argument("--path", default=None, help="追加で containment 検査する repo-relative path")
    parser.add_argument("--feature-id", default=None, help="plan input の dev-graph feature id")
    parser.add_argument("--feature-context", default=None, help="plan input の repo-relative feature JSON")
    parser.add_argument("--json", action="store_true", help="常に JSON を stdout に出す (既定)")
    args = parser.parse_args(argv)
    # 引数だけで決まる誤りは、root・config・section を読む前に返す (直すべき所を取り違えさせない)
    if (args.feature_id is None) != (args.feature_context is None):
        raise UsageError("--feature-id と --feature-context は同時指定必須")
    for flag, value in (("--feature-id", args.feature_id), ("--feature-context", args.feature_context)):
        if value == "":
            # 両方を空にした組を「feature を指定しない」と同じに扱わない (--path "" を断るのと揃える)
            raise UsageError(f"{flag} に空の値は渡せない")
    # path の字面の誤りも同じ。root や config の後に回すと、同じ引数でも repo の状態で exit と理由が変わる
    for value in (args.config, args.path, args.feature_context):
        if value is not None:
            _check_relative_literal(value)

    repo_root, root_source, evidence = resolve_repo_root(args.repo_root, env)
    config = load_config(repo_root, args.config)
    resolved = validate_and_resolve(repo_root, config, args.path, require_plan_roots=require_plan_roots)
    feature_context = (
        validate_feature_context(repo_root, args.feature_id, args.feature_context)
        if args.feature_id is not None else None
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
