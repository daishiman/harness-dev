#!/usr/bin/env python3
# /// script
# name: validate-harness-link
# purpose: C01 の preflight。init の write より前、および repo の plugin link を経由する hook/script の起動より前に、plugin 実体から起動して link chain を1 hop ずつたどり、切断・loop・別 plugin への張り替え・非 symlink・使用中の link 欠落・settings が参照する entrypoint の欠落を診断と修復導線つきで fail-closed にする。何も書かない。
# inputs: ["argv: --repo-root PATH [--config PATH] [--hook-source plugin|project-fallback]"]
# outputs: ["stdout: JSON preflight report {status, code, plugin_link, in_use, in_use_by, link_state, hops[], broken_hop, missing_target, entrypoints, findings[], remediation[], write_count}", "exit: 0=pass / 1=rejected (findings and remediation) / 2=usage or IO"]
# requires-python = ">=3.10"
# dependencies: [_common.py, resolve-repo-context.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""C01 harness link preflight.

repo の plugin link (config の ``claude_hooks.project_plugin_link``、既定 ``.claude/dev-graph-plugin``) は、共有 harness
の symlink を経て plugin 実体へ届く。途中の1 hop が切れると、その link を指す project hook は次の起動で ENOENT になる
だけで、何が切れたかは分からない。この script は plugin 実体 (C24 の plugin_source) から起動し、link を ``readlink`` で
1 hop ずつたどって、切れた hop・loop・plugin_source 以外への到達を名指しする。

link が「使用中」なのは、project/local settings の hook command が ``${CLAUDE_PROJECT_DIR}/<link>/`` を参照するとき、
config の ``claude_hooks.source`` が ``project`` のとき、``--hook-source project-fallback`` が計画されたときである。
使用中でない link の欠落は pass とし、存在する link は使用中かどうかに関係なく検査する。

修復導線は実行できる argv の選択肢として返す (共有 harness の hop を直す / この repo の link だけを直す / hook
fallback を manifest で戻す)。どの選択肢も最後に preflight の再実行を含む。report は stdout だけに出し、絶対 path
を repo へ保存しない。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, contained, dump, load_json, run

SCRIPTS = Path(__file__).resolve().parent
RESOLVE = SCRIPTS / "resolve-repo-context.py"
FALLBACK = SCRIPTS / "build-project-hook-fallback.py"
DEFAULT_LINK = ".claude/dev-graph-plugin"
PROJECT_TOKEN = "${CLAUDE_PROJECT_DIR}"
PLUGIN_TOKEN = "${CLAUDE_PLUGIN_ROOT}"
PROJECT_SETTINGS = (".claude/settings.json", ".claude/settings.local.json")
MAX_HOPS = 40


class Rejected(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def _context(repo_root: str, config: str) -> dict[str, Any]:
    cp = run([sys.executable, str(RESOLVE), "--repo-root", repo_root, "--config", config, "--mode", "read"], check=False)
    if cp.returncode:
        raise Rejected("c24_context_failed", (cp.stderr or cp.stdout).strip())
    return json.loads(cp.stdout)


def _commands(root: Path) -> dict[str, list[str]]:
    """project/local settings の hook command。読めない settings は fail-closed にする。"""
    commands: dict[str, list[str]] = {}
    for rel in PROJECT_SETTINGS:
        path = root / rel
        if not path.exists():
            continue
        try:
            hooks = load_json(contained(path, root)).get("hooks", {})
            commands[rel] = [hook["command"] for groups in hooks.values() for group in groups
                             for hook in group["hooks"] if isinstance(hook.get("command"), str)]
        except (ContractError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise Rejected("settings_unreadable", f"{rel}: {exc}") from exc
    return commands


def _chain(link: Path) -> tuple[list[dict[str, str]], Path | None, str | None]:
    """link から readlink を1 hop ずつたどる。(hops, 終点, 異常)。終点は symlink でない最初の path で、無ければ切断。"""
    hops: list[dict[str, str]] = []
    current, seen = link, set()
    for _ in range(MAX_HOPS):
        if not current.is_symlink():
            return hops, current, None
        if str(current) in seen:
            return hops, None, "loop"
        seen.add(str(current))
        target = os.readlink(current)
        hops.append({"path": str(current), "target": target})
        current = Path(os.path.realpath(current.parent)) / target
    return hops, None, "loop"


def _entrypoints(prefix: str, commands: list[str]) -> list[str]:
    """command が prefix の下で起動する file (prefix からの相対 path)。"""
    pattern = re.compile(re.escape(prefix) + r"/([^\"'\s]+)")
    return sorted({match for command in commands for match in pattern.findall(command)})


def _remediation(code: str, root: Path, link_rel: str, plugin_source: Path, shared: str | None,
                 rerun: list[str], config: str) -> list[dict[str, Any]]:
    """shared は repo の外にある共有 harness の直す位置 (切断なら消えた path、張り替えなら最後の hop)。

    rerun と hook fallback の argv は、この preflight と同じ ``--config`` を持つ (既定でない config の repo で
    別の config を読み直さない)。"""
    link = str(root / link_rel)
    this_repo = {"option": "relink-this-repo", "scope": "this repository only",
                 "steps": [["mkdir", "-p", str((root / link_rel).parent)], ["ln", "-sfn", str(plugin_source), link], rerun]}
    if code == "harness_link_missing":
        return [this_repo]
    if code == "harness_link_not_symlink":
        return [{**this_repo, "steps": [["mv", link, link + ".pre-dev-graph"], *this_repo["steps"][1:]]}]
    options = []
    if code in {"harness_link_broken", "harness_link_mismatch"} and shared:
        options.append({"option": "relink-shared-harness", "scope": "every repository that links through this hop",
                        "steps": [["ln", "-sfn", str(plugin_source), shared], rerun]})
    if code in {"harness_link_broken", "harness_link_loop", "harness_link_mismatch"}:
        options.append(this_repo)
    if code == "harness_entrypoint_missing":
        manifests = sorted((root / ".dev-graph" / "state" / "receipts").glob("hook-fallback-*.json"))
        fallback = ["python3", str(FALLBACK), "--repo-root", str(root), "--config", config]
        steps = ([[*fallback, "--mode", "rollback", "--manifest", manifests[-1].relative_to(root).as_posix()],
                  [*fallback, "--mode", "apply"]] if manifests else [[*fallback, "--mode", "preview"]])
        options.append({"option": "reapply-hook-fallback", "scope": "this repository only", "steps": [*steps, rerun]})
    return options


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    ctx = _context(args.repo_root, args.config)
    root = Path(ctx["repo_root"]).resolve(strict=True)
    plugin_source = Path(ctx["plugin_source"]).resolve(strict=True)
    config_path = Path(ctx["local_state_paths"]["config"])
    config = load_json(contained(config_path, root)) if config_path.exists() else {}
    hooks_config = config.get("claude_hooks", {})
    link_rel = hooks_config.get("project_plugin_link", DEFAULT_LINK)
    link = root / link_rel
    contained(link.parent, root, must_exist=False)
    prefix = f"{PROJECT_TOKEN}/{link_rel}"

    commands = _commands(root)
    in_use_by = [f"settings:{rel}" for rel, items in commands.items() if any(prefix + "/" in item for item in items)]
    if hooks_config.get("source") == "project":
        in_use_by.append("config:claude_hooks.source=project")
    if args.hook_source == "project-fallback":
        in_use_by.append("argv:--hook-source project-fallback")
    plugin_hooks = load_json(plugin_source / "hooks" / "hooks.json")["hooks"]
    plugin_commands = [hook["command"] for groups in plugin_hooks.values() for group in groups for hook in group["hooks"]]
    required = sorted(set(_entrypoints(prefix, [item for items in commands.values() for item in items]))
                      | (set(_entrypoints(PLUGIN_TOKEN, plugin_commands)) if in_use_by else set()))

    hops, end, anomaly = _chain(link)
    findings: list[dict[str, str]] = []
    exists = end is not None and end.exists()
    if not hops and not exists:
        state = "absent"
        if in_use_by:
            findings.append({"code": "harness_link_missing", "detail": f"{link_rel} is used by {', '.join(in_use_by)} but does not exist"})
    elif not hops:
        state = "not_symlink"
        findings.append({"code": "harness_link_not_symlink", "detail": f"{link_rel} must be a plain symlink to the dev-graph plugin source"})
    elif anomaly == "loop":
        state = "loop"
        findings.append({"code": "harness_link_loop", "detail": f"{link_rel} loops after {len(hops)} hops"})
    elif not exists:
        state = "broken"
        findings.append({"code": "harness_link_broken",
                         "detail": f"{link_rel} is severed at hop {len(hops)}: {hops[-1]['path']} -> {hops[-1]['target']} does not exist"})
    elif end.resolve() != plugin_source:
        state = "mismatch"
        findings.append({"code": "harness_link_mismatch",
                         "detail": f"{link_rel} reaches a directory that is not the running plugin source (dev-graph manifest present: "
                                   f"{(end / '.claude-plugin' / 'plugin.json').is_file()})"})
    else:
        state = "ok"
    missing = [rel for rel in required if not (link / rel).is_file()] if state == "ok" else []
    if missing:
        findings.append({"code": "harness_entrypoint_missing", "detail": f"{link_rel} lacks {', '.join(missing)}"})

    code = findings[0]["code"] if findings else None
    shared = str(end) if state == "broken" else hops[-1]["path"] if state == "mismatch" else None
    if shared and Path(os.path.realpath(Path(shared).parent)).is_relative_to(root):
        shared = None  # repo の中の hop は共有 harness ではない
    rerun = ["python3", str(Path(__file__).resolve()), "--repo-root", str(root), "--config", args.config]
    if args.hook_source:
        rerun += ["--hook-source", args.hook_source]
    return {
        "schema_version": "1.0.0",
        "status": "rejected" if findings else "pass",
        "code": code,
        "repository_id": ctx.get("repository_id"),
        "plugin_link": link_rel,
        "in_use": bool(in_use_by),
        "in_use_by": in_use_by,
        "link_state": state,
        "hops": hops,
        "broken_hop": hops[-1]["path"] if state == "broken" else None,
        "missing_target": str(end) if state == "broken" else None,
        "entrypoints": {"checked": len(required) if state == "ok" else 0, "missing": missing},
        "findings": findings,
        "remediation": _remediation(code, root, link_rel, plugin_source, shared, rerun, args.config) if code else [],
        "write_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo-root", required=True)
    p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--hook-source", choices=("plugin", "project-fallback"))
    a = p.parse_args(argv)
    try:
        report = preflight(a)
    except Rejected as exc:
        report = {"schema_version": "1.0.0", "status": "rejected", "code": exc.code, "findings": [{"code": exc.code, "detail": exc.detail}],
                  "remediation": [], "write_count": 0}
    dump(report)
    return 1 if report["status"] == "rejected" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
