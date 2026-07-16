#!/usr/bin/env python3
# /// script
# name: guard-spec-drift-close
# purpose: spec-drift-guardian の close 前 fail-closed 関門 (C07)。PreToolUse/Bash の command 文字列から
#          `gh issue close <N>` を検出し、対象 issue の 4 artifact (triage-report / triage-verdict /
#          sync-proposal / sync-audit-verdict) と post-image を C10 (check-triage-complete.py) へ供給する。
#          C10 が applied_verified または independently_verified_no_change を OK 判定したときだけ close を
#          許可 (exit0) し、artifact 欠落・C10 不在・INCOMPLETE は exit2 で close を遮断する。捕捉対象は
#          PreToolUse/Bash 経路の gh issue close のみ (Web UI/API/Actions 経路は非カバー)。
# inputs:
#   - stdin: Claude hook JSON (PreToolUse: {"tool_input": {"command": "..."}, "cwd": "..."})
#   - env: CLAUDE_PROJECT_DIR (.spec-drift/<N>/ artifact 探索起点) / CLAUDE_PLUGIN_ROOT (C10 の所在)
# outputs:
#   - stderr: 遮断理由 (日本語)
#   - exit: 0=pass-through/close 許可 / 2=block(fail-closed) / 1=一般エラー
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""PreToolUse/Bash fail-closed guard — 未対応 spec-drift issue の close を機械層で止める。

正本契約: plugin-plans/spec-drift-guardian/component-inventory.json の C07 エントリ
  (event=PreToolUse / matcher=Bash / exit_semantics=fail-closed-exit2 / fail_closed=true)。

close 検出 (close_detection):
  PreToolUse/Bash の入力 command 文字列に対し正規表現 `gh issue close <N>` を突合し、対象 issue
  番号を抽出する。これは session 内 gh CLI close の捕捉であり、Web UI/API/Actions 経路の close は
  本 hook の非カバー経路 (実際の close 主体は人間のまま)。

artifact 解決 (artifact_resolution):
  issue 番号をキーに $CLAUDE_PROJECT_DIR/.spec-drift/<N>/ 配下の
    triage-report.json / triage-verdict.json / sync-proposal.json / sync-audit-verdict.json
  と対象 post-image を解決し、C10 (scripts/check-triage-complete.py) へ 4 artifact と --target-root を
  供給する。判定ロジック (applied_verified / independently_verified_no_change の許可、proposal-only/
  未承認/未適用/validator 不備の遮断) は C10 が SSOT であり、本 hook では再実装しない。

fail-closed の規律 (boundary):
  close を確証できない全ケース (artifact 欠落 / C10 不在・起動不能 / C10 INCOMPLETE / issue 番号を
  抽出できない gh issue close) は exit2 で遮断する。`gh issue close` に該当しない command は exit0 で
  素通しする (無関係な Bash を巻き込まない)。stdin 解釈不能は hook 自体の故障防止のため exit0。

Hook input (stdin): {"tool_input": {"command": "..."}, "cwd": "..."}
Exit codes:
  0  pass-through (非該当) / close 許可 (C10 OK)
  1  一般エラー
  2  block (fail-closed): artifact 欠落 / C10 不在・INCOMPLETE / issue 番号抽出不能
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# C10 が消費する 4 artifact のファイル名と C10 への引数フラグの対応。
_ARTIFACTS = (
    ("triage-report.json", "--triage-report"),
    ("triage-verdict.json", "--triage-verdict"),
    ("sync-proposal.json", "--sync-proposal"),
    ("sync-audit-verdict.json", "--sync-audit-verdict"),
)

# `gh issue close` 呼び出しを検出する。以降の引数列 (rest) から issue 番号を別途抽出する。
# コマンド連結や別コマンドを巻き込まないよう rest は制御区切り (; & | 改行) の手前までに限定する。
_CLOSE_RE = re.compile(r"\bgh\s+issue\s+close\b(?P<rest>[^\n;&|]*)")

# rest 部分から issue 番号を抽出する。bare number / #N / .../issues/N の3形を許容する。
_ISSUE_URL_RE = re.compile(r"/issues/(\d+)\b")
_ISSUE_NUM_RE = re.compile(r"#?(\d+)\b")


def _plugin_root() -> Path:
    """C10 を解決するための plugin root を導出する。

    CLAUDE_PLUGIN_ROOT が未設定の環境では hook スクリプト自身の位置から導出する
    (hooks/ の親 = plugin root)。
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


def _project_dir(cwd: Path) -> Path:
    """.spec-drift/<N>/ artifact の探索起点。CLAUDE_PROJECT_DIR 優先、無ければ cwd。"""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    return cwd


def _extract_issue(rest: str) -> str | None:
    """`gh issue close` 直後の引数列から対象 issue 番号を抽出する。抽出不能なら None。"""
    m = _ISSUE_URL_RE.search(rest)
    if m:
        return m.group(1)
    m = _ISSUE_NUM_RE.search(rest)
    if m:
        return m.group(1)
    return None


def _gate_issue(issue: str, project_dir: Path, target_root: Path) -> tuple[int, str]:
    """単一 issue の close 可否を C10 へ委譲して判定する。

    戻り値 (exit_code, reason)。exit_code 0=許可 / 2=遮断。
    """
    artifact_dir = project_dir / ".spec-drift" / issue
    resolved: dict[str, Path] = {}
    missing: list[str] = []
    for filename, flag in _ARTIFACTS:
        path = artifact_dir / filename
        if not path.exists():
            missing.append(filename)
        resolved[flag] = path
    if missing:
        return 2, (
            f"[guard-spec-drift-close] issue #{issue} の close を遮断しました。"
            f"必要な artifact が {artifact_dir} に見つかりません: {', '.join(missing)}。"
            "triage / 独立 verdict / propose / audit を完了してから close してください。"
        )

    c10 = _plugin_root() / "scripts" / "check-triage-complete.py"
    if not c10.exists():
        return 2, (
            f"[guard-spec-drift-close] close ゲート (C10) が見つかりません: {c10}。"
            "環境不備のため fail-closed で close を遮断しました。"
        )

    cmd = [sys.executable, str(c10), "--issue", issue]
    for _, flag in _ARTIFACTS:
        cmd += [flag, str(resolved[flag])]
    cmd += ["--target-root", str(target_root)]

    try:
        rc = subprocess.call(cmd, stdout=sys.stderr, stderr=sys.stderr)
    except OSError as exc:  # C10 起動不能 (実行権限・interpreter 不在等)
        return 2, (
            f"[guard-spec-drift-close] close ゲート (C10) を起動できませんでした: {exc}。"
            "fail-closed で close を遮断しました。"
        )

    if rc == 0:
        return 0, ""
    return 2, (
        f"[guard-spec-drift-close] issue #{issue} は close ゲート (C10) を通過しませんでした "
        f"(exit={rc})。applied_verified または independently_verified_no_change のみ close 可能です。"
        "proposal-only / 未承認 / 未適用 / validator 不備を解消してください。"
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # 解釈不能な payload は hook 自体の故障防止のため pass-through

    command = (payload.get("tool_input") or {}).get("command", "") or ""
    cwd = Path(payload.get("cwd") or os.getcwd())
    project_dir = _project_dir(cwd)
    # target-root は cwd 優先 (実 post-image の所在)。cwd 不明時のみ project_dir。
    target_root = cwd if payload.get("cwd") else project_dir

    closes = list(_CLOSE_RE.finditer(command))
    if not closes:
        return 0  # `gh issue close` 非該当は pass-through

    # gh issue close を検出したが番号を抽出できない = 確証不能 → fail-closed。
    for match in closes:
        issue = _extract_issue(match.group("rest"))
        if issue is None:
            sys.stderr.write(
                "[guard-spec-drift-close] `gh issue close` を検出しましたが issue 番号を"
                "抽出できませんでした。確証不能のため fail-closed で close を遮断しました。\n"
            )
            return 2
        code, reason = _gate_issue(issue, project_dir, target_root)
        if code != 0:
            sys.stderr.write(reason + "\n")
            return code

    return 0  # 全 close 対象が C10 OK → close 許可


if __name__ == "__main__":
    sys.exit(main())
