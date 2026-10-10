#!/usr/bin/env python3
# /// script
# name: lint-pkg-009
# purpose: Resolve skill-governance-lint from the install layout, run its lint-external-refs.py, and normalize the result into the PKG-009 result contract.
# inputs:
#   - argv: lint-external-refs.py arguments (--skills-dir, --fail-on-external など)。--json は無くても付けて呼ぶ
# outputs:
#   - stdout: PKG-009 result JSON（pkg_id・status・last_run_at・findings を必ず含む。lint の出力は analysis に入れる）
#   - stderr: lint-external-refs.py の stderr と、止まった理由
#   - exit: lint-external-refs.py の exit code（0 か、--fail-on-external で外部参照があれば 1）。
#     lint に届かない・lint が JSON を返さないときは status=fail の JSON を出して exit 2
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [../../../scripts/plugin_resources.py]
# ///
"""PKG-009 の外部参照 lint を、install 配置に依存せず起動する。

出力は run-pkg-015.py と同じ PKG result の形にそろえ、aggregate-pkg-findings.py が
pkg_id と status をそのまま読めるようにする。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from plugin_resources import ResolverUnavailable, resolve_root


PLUGIN_ROOT = Path(__file__).resolve().parents[3]


class LinterUnavailable(RuntimeError):
    """resolver か兄弟 plugin が無く、lint-external-refs.py に届かない。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def linter_path() -> Path:
    """skill-governance-lint の lint-external-refs.py を install 配置に依存せず解決する。

    install 先 (<cache>/<marketplace>/<plugin>/<version>/) では `../` で兄弟 plugin に届かないので、
    harness-creator に同梱した resolver に任せる。
    """
    try:
        found = resolve_root("skill-governance-lint", PLUGIN_ROOT)
    except ResolverUnavailable as exc:
        raise LinterUnavailable(str(exc)) from exc
    if found is None:
        raise LinterUnavailable("skill-governance-lint plugin not found; install it to run PKG-009")
    linter = found / "scripts" / "lint-external-refs.py"
    if not linter.is_file():
        raise LinterUnavailable(f"lint-external-refs.py is missing in skill-governance-lint: {linter}")
    return linter


def fail_result(reason: str) -> dict:
    return {"pkg_id": "PKG-009", "status": "fail", "last_run_at": now_iso(), "findings": [reason]}


def normalize(payload: dict, source_exit_code: int) -> dict:
    """lint-external-refs.py --json の出力を PKG-009 の pass/fail にする。

    外部参照 0 件かつ package contract の読み取りエラー 0 件だけを pass にする
    (--fail-on-external を付けたかどうかで status は変えない)。
    """
    findings: list[str] = [f"package contract: {error}" for error in payload.get("contract_errors") or []]
    for report in payload.get("reports") or []:
        for ref in report.get("external_refs") or []:
            findings.append(f"{report.get('path')}:{ref.get('line')} {ref.get('ref')} ({ref.get('classification')})")
    external_count = payload.get("external_ref_count")
    # 件数が数で読めないときは外部参照の有無を確かめられていないので fail にする
    counted = isinstance(external_count, int) and not isinstance(external_count, bool)
    if not counted:
        findings.append(f"lint-external-refs.py の external_ref_count を読めない: {external_count!r}")
    return {
        "pkg_id": "PKG-009",
        "status": "pass" if counted and not findings else "fail",
        "last_run_at": now_iso(),
        "findings": findings,
        "analysis": payload,
        "source_exit_code": source_exit_code,
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    try:
        linter = linter_path()
    except LinterUnavailable as exc:
        # 推測 path で lint は呼ばない。停止理由を PKG-009 のログ (stdout) に残し、集約で fail と数えさせる。
        print(json.dumps(fail_result(str(exc)), ensure_ascii=False, indent=2))
        print(exc, file=sys.stderr)
        return 2
    if "--json" not in args:
        args.append("--json")
    proc = subprocess.run([sys.executable, str(linter), *args], text=True, capture_output=True, check=False)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        reason = f"lint-external-refs.py が JSON を返さなかった (exit {proc.returncode}): {proc.stderr.strip()}"
        print(json.dumps(fail_result(reason), ensure_ascii=False, indent=2))
        return proc.returncode if proc.returncode not in (0, 1) else 2
    print(json.dumps(normalize(payload, proc.returncode), ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
