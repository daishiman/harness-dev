#!/usr/bin/env python3
# /// script
# name: run-pkg-015
# purpose: Normalize rubric violation lint exit codes into the plugin PKG result contract.
# inputs:
#   - --plugin: plugin name
#   - --log-dir: rubric score log root
#   - --out: PKG-015 result JSON
# outputs:
#   - stdout/file: PKG-015 pass/fail/not_applicable result
# contexts: [C, E]
# network: false
# write-scope: --out parent only
# dependencies: [../../../scripts/plugin_resources.py]
# ///
"""Adapter from governance trigger semantics to package-gate semantics."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from plugin_resources import ResolverUnavailable, resolve_root


def _resolve_repo_root() -> Path:
    """$CLAUDE_PROJECT_DIR → 本ファイル parents[5] → cwd の順 (validate-plugin-permissions.py と同じ)。

    install 先では parents[5] が marketplace のディレクトリになるので、plugins/ を含むときだけ採る。
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and (Path(env) / "plugins").is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    if len(here.parents) > 5 and (here.parents[5] / "plugins").is_dir():
        return here.parents[5]
    return Path.cwd()


REPO_ROOT = _resolve_repo_root()
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


class LinterUnavailable(RuntimeError):
    """resolver か兄弟 plugin が無く、lint-rubric-violation.py に届かない。"""


def linter_path() -> Path:
    """skill-governance-lint の lint-rubric-violation.py を install 配置に依存せず解決する。

    repo の plugins/ を前提にした固定パスは、install 先 (<cache>/<marketplace>/<plugin>/<version>/)
    では兄弟 plugin に届かない。harness-creator に同梱した resolver に任せる。
    """
    try:
        found = resolve_root("skill-governance-lint", PLUGIN_ROOT)
    except ResolverUnavailable as exc:
        raise LinterUnavailable(str(exc)) from exc
    if found is None:
        raise LinterUnavailable("skill-governance-lint plugin not found; install it to run PKG-015")
    return found / "scripts" / "lint-rubric-violation.py"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(plugin: str, log_dir: Path, out_path: Path, bootstrap_threshold: int = 20) -> tuple[dict, int]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        linter = linter_path()
    except LinterUnavailable as exc:
        # 推測 path で lint は呼ばない。停止理由を --out に残し、集約で fail と数えさせる。
        return {"pkg_id": "PKG-015", "status": "fail", "last_run_at": now_iso(), "plugin": plugin,
                "findings": [str(exc)]}, 1
    with tempfile.NamedTemporaryFile(prefix="pkg-015-", suffix=".json", dir=out_path.parent, delete=False) as handle:
        raw_path = Path(handle.name)
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(linter),
                "--log-dir",
                str(log_dir),
                "--out",
                str(raw_path),
                "--bootstrap-threshold",
                str(bootstrap_threshold),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            analysis = json.loads(raw_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            result = {
                "pkg_id": "PKG-015",
                "status": "fail",
                "last_run_at": now_iso(),
                "findings": [f"rubric linter output unavailable: {exc}; stderr={proc.stderr.strip()}"],
            }
            return result, 1
    finally:
        raw_path.unlink(missing_ok=True)

    breached = analysis.get("breached", [])
    if proc.returncode == 0 and not breached:
        status = "pass"
        findings: list[object] = []
        skip_reason = None
    elif proc.returncode == 3 and analysis.get("bootstrap") is True:
        status = "not_applicable"
        findings = []
        skip_reason = (
            "rubric history bootstrap: "
            f"{analysis.get('total_records', 0)}/{analysis.get('bootstrap_threshold', bootstrap_threshold)} records; "
            "threshold verdict is not yet statistically applicable"
        )
    else:
        status = "fail"
        findings = breached or [
            f"rubric linter failed with exit {proc.returncode}: {analysis.get('warning') or proc.stderr.strip()}"
        ]
        skip_reason = None
    result = {
        "pkg_id": "PKG-015",
        "status": status,
        "last_run_at": now_iso(),
        "plugin": plugin,
        "findings": findings,
        "analysis": analysis,
        "source_exit_code": proc.returncode,
    }
    if skip_reason is not None:
        result["skip_reason"] = skip_reason
    return result, 1 if status == "fail" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--log-dir")
    parser.add_argument("--out", required=True)
    parser.add_argument("--bootstrap-threshold", type=int, default=20)
    args = parser.parse_args(argv)
    log_dir = Path(args.log_dir) if args.log_dir else REPO_ROOT / "eval-log" / args.plugin
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    result, exit_code = run(args.plugin, log_dir, out_path, args.bootstrap_threshold)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
