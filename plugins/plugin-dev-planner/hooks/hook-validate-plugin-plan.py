#!/usr/bin/env python3
# /// script
# name: hook-validate-plugin-plan
# purpose: plugin-dev-planner 配下の plan 契約に関わる編集後、同梱 sample-plan (生きた手本) の決定論ゲートを再実行して明らかな drift を検出する。実生成 plan (eval-log 配下) の製品ゲートではない — 実 plan の 4 条件検証は assign-plugin-plan-evaluator (context:fork) が担う (proposer≠approver)。
# inputs:
#   - stdin: Claude hook JSON
# outputs:
#   - exit: 0=許可 / 2=plan gate failed
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


TRIGGER_TOKENS = (
    "plugin-dev-planner",
    "run-plugin-dev-plan",
    "plugin-dev-plan",
)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _edited_paths(payload: dict):
    """Claude hook payload から編集対象の file_path を抽出する。"""
    tool_input = payload.get("tool_input") or {}
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            yield value


def _is_relevant(payload: dict) -> bool:
    # 編集対象ファイルのパスにトリガ語が含まれる場合のみ relevant。
    # payload 全体を走査すると、無関係な編集でも内容に plugin 名が含まれるだけで
    # 発火する (過剰発火) ため、まず file_path に限定して判定する。
    paths = list(_edited_paths(payload))
    if paths:
        return any(token in p for p in paths for token in TRIGGER_TOKENS)
    # file_path 不明な編集系イベントのみ保守的に従来挙動へフォールバックする。
    text = "\n".join(_strings(payload))
    return any(token in text for token in TRIGGER_TOKENS)


def _plugin_root() -> Path:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    if not _is_relevant(payload):
        return 0

    plugin_root = _plugin_root()
    plugins_dir = plugin_root.parent
    skill_dir = plugin_root / "skills" / "run-plugin-dev-plan"
    # 責務境界: 本 hook は同梱 sample-plan (生きた手本) の drift 検出器であり、
    # eval-log 配下に生成される実 plan の製品ゲートではない。実生成 plan の
    # 4 条件検証は assign-plugin-plan-evaluator (context:fork) が担う (proposer≠approver)。
    # sample-plan のみを対象にするのは過剰発火・誤帰属を避ける意図。
    plan_dir = skill_dir / "examples" / "sample-plan"
    inventory = plan_dir / "component-inventory.json"
    handoff = plan_dir / "handoff-run-plugin-dev-plan.json"
    goal_spec = plan_dir / "goal-spec.json"
    checks = [
        [sys.executable, str(skill_dir / "scripts" / "check-plugin-goal-spec.py"), str(goal_spec)],
        [sys.executable, str(skill_dir / "scripts" / "verify-index-topsort.py"), str(plan_dir)],
        [sys.executable, str(skill_dir / "scripts" / "detect-unassigned.py"), "--inventory", str(inventory), "--specs-dir", str(plan_dir)],
        [sys.executable, str(skill_dir / "scripts" / "check-spec-frontmatter.py"), "--specs-dir", str(plan_dir)],
        [sys.executable, str(skill_dir / "scripts" / "check-spec-gates.py"), "--specs-dir", str(plan_dir)],
        [sys.executable, str(skill_dir / "scripts" / "check-spec-matrix-coverage.py"), "--self-test"],
        [sys.executable, str(skill_dir / "scripts" / "check-spec-matrix-coverage.py"), str(plan_dir)],
        [sys.executable, str(skill_dir / "scripts" / "check-surface-inventory.py"), str(inventory)],
        [sys.executable, str(skill_dir / "scripts" / "check-build-handoff.py"), str(handoff)],
        [sys.executable, str(skill_dir / "scripts" / "check-requirements-coverage.py"), str(plan_dir)],
        [sys.executable, str(skill_dir / "scripts" / "check-runtime-portability.py"), str(plan_dir)],
        [sys.executable, str(skill_dir / "scripts" / "check-plugin-surface-audit.py"), "--plugins-dir", str(plugins_dir), "--strict-manifest", "--expect-plan-ready", "plugin-dev-planner"],
    ]

    for cmd in checks:
        result = subprocess.run(cmd, text=True, capture_output=True)
        if result.returncode != 0:
            sys.stderr.write("[hook-validate-plugin-plan] BLOCKED: sample-plan gate failed\n")
            sys.stderr.write("$ " + " ".join(cmd) + "\n")
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
