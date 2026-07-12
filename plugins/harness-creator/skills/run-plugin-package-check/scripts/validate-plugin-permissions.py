#!/usr/bin/env python3
"""PKG-013a〜d: permission scope 検証。

013a: tool permissions（Bash 等）が plugin スコープ宣言内
013b: filesystem permissions が plugin root 配下
013c: network permissions の allowlist が manifest と一致
013d: MCP / external integration permissions が manifest と一致

stub 実装: plugin.json の permissions ブロックの基本構造を検査し、
明らかな範囲超え（ワイルドカードでの全許可、絶対パス指定）を検出する。
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_repo_root() -> Path:
    """repo_root を解決(dev/CI 層②)。

    優先順: $CLAUDE_PROJECT_DIR(plugins/ を含む) → 本ファイル parents[5](同) → cwd。
    marketplace install 環境で誤起動しても IndexError で死なずフォールバックする。
    本スクリプトは主に dev/CI で repo 内 plugin を検査する層。install 環境で
    個別 plugin を検査する場合は --plugin-dir でパスを明示すること。
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and (Path(env) / "plugins").is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    if len(here.parents) > 5 and (here.parents[5] / "plugins").is_dir():
        return here.parents[5]
    return Path.cwd()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_permissions(plugin_dir: Path) -> dict | None:
    pj = plugin_dir / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        return None
    try:
        data = json.loads(pj.read_text())
        return data.get("permissions", {}) if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def check_013a(perms: dict, plugin: str) -> list[dict]:
    findings = []
    tools = perms.get("tools", []) if isinstance(perms, dict) else []
    for idx, t in enumerate(tools, 1):
        if isinstance(t, str) and t in {"Bash(*)", "*"}:
            findings.append({
                "id": f"F-PKG013a-{idx:03d}",
                "pkg_id": "PKG-013a",
                "severity": "P0",
                "location": f"plugins/{plugin}/.claude-plugin/plugin.json:permissions.tools[{idx-1}]",
                "evidence": f"tool permission がワイルドカード全許可: {t}",
                "suggested_fix": "具体的なコマンド範囲に絞る（例: Bash(python3 *), Bash(git diff *)）",
            })
    return findings


def check_013b(perms: dict, plugin: str) -> list[dict]:
    findings = []
    fs = perms.get("filesystem", {}) if isinstance(perms, dict) else {}
    paths = fs.get("write", []) if isinstance(fs, dict) else []
    for idx, p in enumerate(paths, 1):
        if isinstance(p, str) and p.startswith("/") and not p.startswith(f"plugins/{plugin}/"):
            findings.append({
                "id": f"F-PKG013b-{idx:03d}",
                "pkg_id": "PKG-013b",
                "severity": "P0",
                "location": f"plugins/{plugin}/.claude-plugin/plugin.json:permissions.filesystem.write[{idx-1}]",
                "evidence": f"plugin root 外の絶対パス書込権限: {p}",
                "suggested_fix": f"plugins/{plugin}/ 配下の相対パスに変更",
            })
    return findings


def check_013c(perms: dict, plugin: str) -> list[dict]:
    findings = []
    net = perms.get("network", {}) if isinstance(perms, dict) else {}
    allowlist = net.get("allowlist", []) if isinstance(net, dict) else []
    for idx, h in enumerate(allowlist, 1):
        if isinstance(h, str) and h in {"*", "0.0.0.0/0"}:
            findings.append({
                "id": f"F-PKG013c-{idx:03d}",
                "pkg_id": "PKG-013c",
                "severity": "P0",
                "location": f"plugins/{plugin}/.claude-plugin/plugin.json:permissions.network.allowlist[{idx-1}]",
                "evidence": f"network allowlist がワイルドカード全許可: {h}",
                "suggested_fix": "具体的なホスト/ドメインに絞る",
            })
    return findings


def check_013d(perms: dict, plugin: str) -> list[dict]:
    findings = []
    mcp = perms.get("mcp", {}) if isinstance(perms, dict) else {}
    for service, scopes in (mcp.items() if isinstance(mcp, dict) else []):
        if isinstance(scopes, list) and "*" in scopes:
            findings.append({
                "id": f"F-PKG013d-001",
                "pkg_id": "PKG-013d",
                "severity": "P0",
                "location": f"plugins/{plugin}/.claude-plugin/plugin.json:permissions.mcp.{service}",
                "evidence": f"MCP service {service} の scope がワイルドカード",
                "suggested_fix": "具体的な scope に絞る",
            })
    return findings


CHECKS = {"013a": check_013a, "013b": check_013b, "013c": check_013c, "013d": check_013d}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--check", default="013a,013b,013c,013d")
    ap.add_argument(
        "--plugin-dir",
        default=None,
        help="検査対象 plugin ディレクトリを明示する(install 環境用)。"
        "未指定なら repo_root (_resolve_repo_root) から plugins/<plugin> を解決する。",
    )
    args = ap.parse_args()

    # repo_root は module-level 定数ではなく _resolve_repo_root() で解決する
    # (marketplace install / CLAUDE_PROJECT_DIR 環境差を吸収する可搬性層②)。
    # --plugin-dir 明示時はそれを優先 (install 環境で repo 外の plugin を検査する経路)。
    if args.plugin_dir:
        plugin_dir = Path(args.plugin_dir)
    else:
        plugin_dir = _resolve_repo_root() / "plugins" / args.plugin
    perms = load_permissions(plugin_dir)
    if perms is None:
        result = {
            "pkg_id": "PKG-013",
            "status": "not_applicable",
            "skip_reason": "plugin.json に permissions ブロック未定義",
            "last_run_at": now_iso(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    sub_ids = [s.strip() for s in args.check.split(",")]
    sub_results = {}
    any_fail = False
    for sid in sub_ids:
        if sid not in CHECKS:
            continue
        findings = CHECKS[sid](perms, args.plugin)
        sub_results[f"PKG-{sid}"] = {
            "status": "fail" if findings else "pass",
            "findings": findings,
            "last_run_at": now_iso(),
        }
        if findings:
            any_fail = True

    result = {
        "pkg_id": "PKG-013",
        "status": "fail" if any_fail else "pass",
        "sub_checks": sub_results,
        "last_run_at": now_iso(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
