#!/usr/bin/env python3
# /// script
# name: enforce-provenance-chain
# purpose: run-plugin-dev-plan --mode update の PreToolUse で、C04 (intake-consumption) / C05 (provenance-chain) の pass marker が現 goal-spec の digest に pin された状態で存在することを確認し、欠落/stale なら exit2 で block する (未検証の破壊的 update を fail-closed で止める)。
# inputs:
#   - stdin: Claude hook JSON (PreToolUse)
# outputs:
#   - stderr: block 理由 (欠落/stale marker)
#   - exit: 0=許可 / 2=block
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""E3 横断 fail-closed hook: --mode update の provenance 事前検証 (backstop)。

役割の位置づけ (honest labeling): primary gate は run-plugin-dev-plan SKILL.md の inline 検証
ブロックで、そこが check-intake-consumption.py / check-provenance-chain.py を `--marker-dir`
付きで実行し marker を*自己生成*する (人間が事前に marker を手作りする必要はない)。本 hook は
その inline gate を bypass した場合の defense-in-depth backstop にすぎず、matcher (Bash|Task) の
被覆範囲に限られる (canonical な slash / Agent dispatch の担保は主に inline gate が負う)。

改善フロー (run-plugin-dev-plan --mode update) が走る前に、C04/C05 のゲートが *現在の*
goal-spec に対して PASS 済みであることを marker (goal-spec の sha256 に pin) で確認する。
marker 欠落 = ゲート未実行、digest 不一致 = goal-spec がゲート後に改変された (stale) を意味し、
いずれも未検証の破壊的 update ゆえ exit2 で block する。plan_dir を特定できない/対象が
--mode update でない場合は関与しない (exit0)。過剰 block を避けるため fail-closed は
「update と識別でき plan_dir も特定できた」ときに限定する。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

TRIGGER_TOKENS = ("run-plugin-dev-plan", "plugin-dev-plan")
# C11 が検証する pass marker のゲート名 (C04/C05 の write_pass_marker と一致する契約)。
REQUIRED_GATES = ("intake-consumption", "provenance-chain")
_UPDATE_RE = re.compile(r"--mode[=\s]+update|\"mode\"\s*:\s*\"update\"")
_OUT_DIR_RE = re.compile(r"--out-dir[=\s]+(\S+)")
_IMPROVEMENT_HANDOFF_RE = re.compile(r"--improvement-handoff[=\s]+(\S+)")
_PLAN_DIR_RE = re.compile(r"(plugin-plans/[A-Za-z0-9._\-/]+)")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _is_update_invocation(text: str) -> bool:
    return any(tok in text for tok in TRIGGER_TOKENS) and bool(_UPDATE_RE.search(text))


def _resolve_plan_dir(text: str) -> Path | None:
    """command 文字列から plan_dir を特定する (--out-dir 優先、次に handoff 内 plan_dir)。"""
    m = _OUT_DIR_RE.search(text)
    if m:
        return Path(m.group(1).rstrip("/"))
    m = _IMPROVEMENT_HANDOFF_RE.search(text)
    if m:
        handoff_path = Path(m.group(1).strip("'\""))
        if handoff_path.is_file():
            try:
                handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                handoff = {}
            plan_dir = handoff.get("plan_dir") if isinstance(handoff, dict) else None
            if isinstance(plan_dir, str) and plan_dir.strip():
                return Path(plan_dir.rstrip("/"))
    m = _PLAN_DIR_RE.search(text)
    if m:
        # plugin-plans/<slug> の 2 セグメントまでに正規化 (末尾のファイル名等を落とす)。
        parts = Path(m.group(1)).parts
        if len(parts) >= 2:
            return Path(parts[0]) / parts[1]
    return None


def check_markers(plan_dir: Path) -> list[str]:
    """plan_dir の C04/C05 marker が現 goal-spec digest に pin されているか検査する。"""
    goal_spec = plan_dir / "goal-spec.json"
    if not goal_spec.is_file():
        return []  # goal-spec が無い = update 対象として特定不能 (関与しない)
    digest = hashlib.sha256(goal_spec.read_bytes()).hexdigest()
    problems: list[str] = []
    for gate in REQUIRED_GATES:
        marker = plan_dir / ".gate" / f"{gate}.pass"
        if not marker.is_file():
            problems.append(f"{gate} の pass marker が無い ({marker}): ゲート未実行のまま --mode update しようとしている")
            continue
        recorded = marker.read_text(encoding="utf-8").strip()
        if recorded != digest:
            problems.append(
                f"{gate} の pass marker が stale ({marker}): goal-spec がゲート後に改変された "
                "(digest 不一致)。ゲートを再実行して marker を更新すること"
            )
    return problems


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    text = "\n".join(_strings(payload))
    if not _is_update_invocation(text):
        return 0

    plan_dir = _resolve_plan_dir(text)
    if plan_dir is None:
        return 0  # plan_dir 特定不能 = 過剰 block を避け関与しない

    problems = check_markers(plan_dir)
    if problems:
        sys.stderr.write("[enforce-provenance-chain] BLOCKED: --mode update の provenance 事前検証に失敗\n")
        for p in problems:
            sys.stderr.write("  - " + p + "\n")
        sys.stderr.write(
            "  対応: 現 goal-spec に対し check-intake-consumption.py / check-provenance-chain.py を "
            "--marker-dir <PLAN_DIR> 付きで PASS させてから再実行する\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
