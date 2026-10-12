#!/usr/bin/env python3
# /// script
# name: lint-rubric-violation
# version: 0.2.0
# purpose: score ログの findings を rule ごとに数える（提案の対象 rule が過去の評価でどれだけ出たかを見る。時系列の招集判定は skill-governance-lint の同名 script）
# inputs:
#   - --logs: score ログを探すディレクトリ（配下の *-score.jsonl を再帰で読む。例 eval-log、eval-log/<plugin>）
#   - --rule: 数える rule id（省略すると全 rule）
# outputs:
#   - stdout: JSON {total, by_rule, score_logs, skipped_no_score, skipped_invalid, unreadable_logs}
#   - stderr: 止めた理由 / 数えなかったレコードと読めなかったファイル
#   - exit: 0=OK / 2=usage・--logs がディレクトリでない・score を持つレコードが 0 件
# requires-python: ">=3.10"
# dependencies: []
# contexts: [A]
# network: false
# write-scope: none
# ///
"""score ログの findings を rule ごとに数える。

Usage:
  lint-rubric-violation.py --logs <dir> [--rule <id>]
Emits JSON: {"total": N, "by_rule": {"FM-003": 12, ...}, "score_logs": F, "skipped_no_score": S, ...}

--logs の配下にある score ログ（write-eval-log.py が書く eval-log/<plugin>/<date>-score.jsonl）を
再帰で読む。score ログでない jsonl（run-skill-rubric-governance/log の governance log など）は読まない。

total は数値の score を持つレコードの数で、by_rule はそのレコードの findings に出た rule id ごとの
finding の件数。score の無いレコードは評価の結果ではないので数えず、件数を skipped_no_score に出す
（数えると、違反の無い評価として total だけが増える）。score を持つレコードが 1 件も無いときは、
「違反なし」と区別できないので結果を出さずに exit 2 で止める。
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

SCORE_LOG_GLOB = "*-score.jsonl"


def has_score(rec: dict) -> bool:
    score = rec.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return False
    return not (isinstance(score, float) and not math.isfinite(score))


def rule_id(finding: dict) -> str:
    rid = finding.get("id") or finding.get("rubric_item_id")
    if isinstance(rid, bool) or not isinstance(rid, (str, int)):
        return "?"
    return str(rid)


def main() -> int:
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--logs", required=True,
                    help="score ログ（*-score.jsonl）を再帰で探すディレクトリ。例: eval-log")
    ap.add_argument("--rule", default=None)
    args = ap.parse_args()

    log_dir = Path(args.logs)
    if not log_dir.is_dir():
        print(f"error: --logs がディレクトリでない: {log_dir}", file=sys.stderr)
        return 2

    counter: Counter[str] = Counter()
    total = 0
    stats = {"score_logs": 0, "skipped_no_score": 0, "skipped_invalid": 0, "unreadable_logs": 0}
    for f in sorted(p for p in log_dir.rglob(SCORE_LOG_GLOB) if p.is_file()):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"warning: score ログを読めない: {f} ({type(exc).__name__})", file=sys.stderr)
            stats["unreadable_logs"] += 1
            continue
        stats["score_logs"] += 1
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                rec = None
            if not isinstance(rec, dict):
                stats["skipped_invalid"] += 1
                continue
            if not has_score(rec):
                stats["skipped_no_score"] += 1
                continue
            total += 1
            findings = rec.get("findings")
            for finding in findings if isinstance(findings, list) else []:
                if not isinstance(finding, dict):
                    continue
                rid = rule_id(finding)
                if args.rule and rid != args.rule:
                    continue
                counter[rid] += 1

    skipped = stats["skipped_no_score"] + stats["skipped_invalid"]
    if skipped:
        print(f"warning: 数えなかったレコード {skipped} 件（score なし {stats['skipped_no_score']}・"
              f"JSON の object でない {stats['skipped_invalid']}）", file=sys.stderr)
    if total == 0:
        print(f"error: {log_dir} の配下に score を持つレコードが無い（{SCORE_LOG_GLOB} {stats['score_logs']} 件を"
              "読んだ）。違反なしと区別できないので止める。--logs には score ログのある場所（例: eval-log）を渡す",
              file=sys.stderr)
        return 2

    out = {"total": total, "by_rule": dict(counter), **stats}
    sys.stdout.write(json.dumps(out, ensure_ascii=False, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
