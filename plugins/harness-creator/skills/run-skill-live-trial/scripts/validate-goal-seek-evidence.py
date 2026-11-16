#!/usr/bin/env python3
# /// script
# name: validate-goal-seek-evidence
# purpose: goal_seek を宣言する skill の live-trial で、実行契約の履行証跡が実在し整合するかを機械検査する。
# inputs:
#   - argv: --skill-dir --eval-root [--skill-name] [--require-declared]
# outputs:
#   - stdout: {"valid": bool, "skill": str, "violations": [str], "checked": {...}}
#   - exit: 0=合格 / 1=違反あり / 2=usage
# contexts: [C, E]
# network: false
# write-scope: none (read-only)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""live-trial の「skill 実行契約を飛ばして下位 script を直叩きする」経路を検出する。

## 背景

SKILL.md は goal_seek 節を「frontmatter の `goal_seek.engine` / `fork` / `max_loops` を
**実行契約とする**」と明記しており、任意の付録ではない。しかし trial が
`Skill({skill: "..."})` でロードした後に下位 script を直接叩いても、`out/status.json` は
正常に出力され `DONE: PASS` で終わる。**成果物だけを見る検査では正常な実走と区別できない。**

`HarnessHub-s7b` の初回再 trial では 2 件とも実際にこの経路を通った
(`run-dev-graph-status/live-trial/20260721T140000-r5` の transcript の tool_use は
`ls` と `status-graph.py` の 2 本のみ)。task.md に明示要求を書くと status は履行したが
render は依然 Agent fork を省略しており、**記載は必要条件ですらない**。

## 何を検査するか

SKILL.md の「### ゴールシーク検証」節に書かれている python ブロックと同じ検査を行う。
同ブロックは trial 側の任意実行に委ねられているため、実行されなければ何も起きない。
本 script はそれを外部から呼べる形に切り出し、強制可能にする。

- `<skill>-goal-spec.json` / `<skill>-progress.json` / `<skill>-intermediate.jsonl` の実在
- `intermediate.jsonl` が非空で、全行に 6 キーが揃うこと
- 全行の `original_goal` が goal-spec の `original_goal` と一致すること
- 全行の `original_goal_hash` が `sha256(goal_spec['original_goal'])` と一致すること

ファイルが存在するだけで中身が空・ダミーなら違反として扱う。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REQUIRED_KEYS = {
    "original_goal",
    "original_goal_hash",
    "current_goal_snapshot",
    "delta_from_original",
    "merged_directive_for_next",
    "drift_signal",
}


def _frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index])
    return ""


def declares_goal_seek(skill_md: Path) -> bool:
    """frontmatter に goal_seek 宣言があるか。本文中の言及は数えない。"""
    if not skill_md.is_file():
        return False
    fm = _frontmatter(skill_md.read_text(encoding="utf-8"))
    return bool(re.search(r"^goal_seek:", fm, re.M))


def verify(skill_dir: Path, eval_root: Path, skill_name: str | None = None,
           require_declared: bool = True) -> dict:
    skill_dir = skill_dir.resolve()
    name = skill_name or skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    declared = declares_goal_seek(skill_md)

    result: dict = {
        "skill": name,
        "goal_seek_declared": declared,
        "eval_root": eval_root.as_posix(),
        "violations": [],
        "checked": {},
    }
    if not declared:
        # goal_seek を宣言しない skill は本検査の対象外 (契約が存在しない)
        result["valid"] = True
        result["checked"]["skipped"] = "frontmatter に goal_seek 宣言なし"
        return result
    if not require_declared:
        result["valid"] = True
        return result

    violations: list[str] = result["violations"]
    goal_path = eval_root / f"{name}-goal-spec.json"
    progress_path = eval_root / f"{name}-progress.json"
    inter_path = eval_root / f"{name}-intermediate.jsonl"
    result["checked"] = {
        "goal_spec": goal_path.as_posix(),
        "progress": progress_path.as_posix(),
        "intermediate": inter_path.as_posix(),
    }

    for label, path in (("goal-spec", goal_path), ("progress", progress_path),
                        ("intermediate", inter_path)):
        if not path.is_file():
            violations.append(
                f"{label}-missing: {path.name} が無い "
                "— skill をロードしながらゴールシーク配線を実行していない疑い"
            )

    if violations:
        result["valid"] = False
        return result

    try:
        goal = json.loads(goal_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        violations.append(f"goal-spec-invalid: {exc}")
        result["valid"] = False
        return result

    original = goal.get("original_goal")
    if not isinstance(original, str) or not original.strip():
        violations.append("goal-spec-empty: original_goal が空または文字列でない")
        result["valid"] = False
        return result

    expected_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
    result["checked"]["expected_original_goal_hash"] = expected_hash

    rows = []
    for lineno, line in enumerate(inter_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append((lineno, json.loads(line)))
        except json.JSONDecodeError as exc:
            violations.append(f"intermediate-invalid: L{lineno}: {exc}")

    if not rows:
        violations.append(
            "intermediate-empty: intermediate.jsonl に有効な行が無い "
            "— 周回記録が残っていない"
        )

    for lineno, row in rows:
        missing = REQUIRED_KEYS - row.keys()
        if missing:
            violations.append(f"intermediate-keys: L{lineno}: 必須キー欠落 {sorted(missing)}")
            continue
        if row["original_goal"] != original:
            violations.append(
                f"goal-drift: L{lineno}: original_goal が goal-spec と不一致 "
                "— 周回中にゴールがすり替わっている"
            )
        if row["original_goal_hash"] != expected_hash:
            violations.append(
                f"goal-hash-mismatch: L{lineno}: original_goal_hash={row['original_goal_hash']} "
                f"!= sha256(goal_spec.original_goal)={expected_hash}"
            )

    result["checked"]["intermediate_rows"] = len(rows)
    result["valid"] = not violations
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="goal_seek 実行契約の履行証跡を検査する (read-only)")
    parser.add_argument("--skill-dir", required=True, help="被験 skill のディレクトリ")
    parser.add_argument("--eval-root", required=True,
                        help="ゴールシーク成果物の置き場 ($DEV_GRAPH_ROOT/eval-log 等)")
    parser.add_argument("--skill-name", help="既定は --skill-dir の basename")
    parser.add_argument("--allow-undeclared", action="store_true",
                        help="goal_seek 宣言がある場合も検査を skip する (調査用)")
    args = parser.parse_args(argv)
    try:
        report = verify(Path(args.skill_dir), Path(args.eval_root),
                        args.skill_name, require_declared=not args.allow_undeclared)
    except OSError as exc:
        json.dump({"valid": False, "error": str(exc)}, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
