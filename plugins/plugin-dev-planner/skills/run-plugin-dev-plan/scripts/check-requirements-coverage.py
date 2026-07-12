#!/usr/bin/env python3
# /// script
# name: check-requirements-coverage
# purpose: 仕様駆動開発 (SDD) の要件トレーサビリティ (RTM) ゲート。goal-spec.json の checklist 各 id が index.md の「完了チェックリスト」または「受入確認」節で参照されることを fail-closed 検証する (要件→計画の被覆・漏れ 0)。
# inputs:
#   - argv: PLAN_DIR (goal-spec.json + index.md を含む plan ディレクトリ)
# outputs:
#   - stdout: OK サマリ
#   - stderr: 未被覆要件 id / 入力欠落 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""goal-spec の要件 (checklist) が計画側へ全件トレースされることを検証する。

仕様駆動開発の中核 = 要件が正本で、計画・実装はその被覆である。detect-unassigned が
「component→phase」の orphan を防ぐのと対で、本ゲートは「要件→index」の orphan を防ぐ
(要件を書いたのにどの完了判定にも現れない=silent drop を封鎖)。被覆の宣言先は index の
`## 完了チェックリスト` / `## 受入確認` 節 (計画全体の完了・受入判定に要件 id を引用する)。

機械の床は「id トークンの出現」まで (意味の充足は evaluator / 下流トラスト=Goodhart 回避)。
id 照合は境界安全: 前に英数字が無く後ろに数字が続かない出現のみ数える
(要件 C1 が component C01 / C11 や日本語文中の「C1が」と混同されない)。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# index 側で要件 id の被覆宣言を受け付ける節 (specfm.INDEX_REQUIRED_SECTIONS の部分集合)。
COVERAGE_SECTIONS = ("## 完了チェックリスト", "## 受入確認")


def _section_text(index_text: str, heading: str) -> str | None:
    """index Markdown から heading 節の本文を返す (節欠落は None)。"""
    lines = index_text.splitlines()
    idx = next(
        (i for i, ln in enumerate(lines)
         if ln.strip() == heading or ln.strip().startswith(heading + " ")),
        None,
    )
    if idx is None:
        return None
    body: list[str] = []
    for ln in lines[idx + 1:]:
        if ln.startswith("## "):
            break
        body.append(ln)
    return "\n".join(body)


def _id_pattern(req_id: str) -> re.Pattern[str]:
    """要件 id の境界安全パターン (C1 は C11/C01/ABC1x に誤マッチしない)。"""
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(req_id)}(?![0-9])")


def uncovered_requirements(goal_spec: dict, index_text: str) -> tuple[list[str], list[str]]:
    """(errors, uncovered_ids) を返す。checklist 空/節欠落は errors で fail-closed。"""
    errors: list[str] = []
    checklist = goal_spec.get("checklist")
    if not isinstance(checklist, list) or not checklist:
        return (["goal-spec.checklist が非空 list でない (要件が無い plan は RTM 検査不能)"], [])

    bodies = []
    for heading in COVERAGE_SECTIONS:
        body = _section_text(index_text, heading)
        if body is None:
            errors.append(f"index.md に被覆宣言節 '{heading}' が無い (INDEX_REQUIRED_SECTIONS の床)")
        else:
            bodies.append(body)
    if errors:
        return (errors, [])

    haystack = "\n".join(bodies)
    uncovered: list[str] = []
    for idx, item in enumerate(checklist):
        req_id = str(item.get("id", "")).strip() if isinstance(item, dict) else ""
        if not req_id:
            errors.append(f"checklist[{idx}] に id が無い (RTM の追跡キー欠落)")
            continue
        if not _id_pattern(req_id).search(haystack):
            uncovered.append(req_id)
    return (errors, uncovered)


def run(plan_dir: Path) -> tuple[int, list[str]]:
    """(exit_code, errors) を返す。"""
    goal_path = plan_dir / "goal-spec.json"
    index_path = plan_dir / "index.md"
    if not goal_path.is_file():
        return 1, [f"goal-spec.json が無い: {goal_path} (要件正本が無い plan は SDD 契約違反)"]
    if not index_path.is_file():
        return 1, [f"index.md が無い: {index_path}"]
    try:
        goal_spec = json.loads(goal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 1, [f"goal-spec.json parse error: {exc}"]
    if not isinstance(goal_spec, dict):
        return 1, ["goal-spec.json root is not an object"]

    errors, uncovered = uncovered_requirements(goal_spec, index_path.read_text(encoding="utf-8"))
    for req_id in uncovered:
        errors.append(
            f"未被覆要件: goal-spec.checklist の {req_id} が index の "
            f"{' / '.join(COVERAGE_SECTIONS)} のどこにも引用されない "
            f"(要件→計画のトレース欠落・silent drop)"
        )
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        sys.stderr.write("usage: check-requirements-coverage.py PLAN_DIR\n")
        return 2
    plan_dir = Path(args[0])
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    code, errors = run(plan_dir)
    if code == 0:
        sys.stdout.write("OK: goal-spec checklist の全要件 id が index の完了チェックリスト/受入確認へトレース済み\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
