#!/usr/bin/env python3
# /// script
# name: build-review-report
# purpose: Regenerate the mechanical (derivable) section of review-<scope_mode>.md from findings.json, preserving hand-written prose.
# inputs:
#   - --findings <findings.json>
#   - --report <review-<scope_mode>.md>
#   - --init (insert the generated block when markers are absent)
# outputs:
#   - report file rewritten between the generated markers
#   - stdout: summary of what changed
#   - exit: 0=updated or already current / 1=marker missing without --init / 2=usage or input error
# contexts: [C]
# network: false
# write-scope: report file passed via --report
# dependencies: []
# ///
"""findings.json から review レポートの機械項目だけを再生成する。

レポートの件数表 (4 条件の判定・condition 内訳・findings 一覧) は findings.json から
一意に導ける。これを手書きすると findings.json を更新するたびに古い件数が残り、
「レポートは C1=2 と言うが findings.json は C1=7」という二重帳簿になる
(実際に run-20260809-mvp-tiering で発生した)。

散文の分析は生成できないので、マーカー間だけを置換して他は一切触らない。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BEGIN = "<!-- BEGIN generated: mechanical-summary (build-review-report.py) — この行から下は自動生成。手で編集しない -->"
END = "<!-- END generated: mechanical-summary -->"

SIGNAL_TO_CONDITION = {
    "contradiction": "C1",
    "omission": "C2",
    "inconsistency": "C3",
    "dependency_break": "C4",
}
CONDITION_LABEL = {
    "C1": "矛盾なし",
    "C2": "漏れなし",
    "C3": "整合性あり",
    "C4": "依存関係整合",
}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def collect_issues(data: dict) -> list[dict]:
    return [i for p in data.get("paradigm_findings", []) for i in p.get("issues", [])]


def render(data: dict) -> str:
    issues = collect_issues(data)
    by_signal = Counter(i.get("condition_signal") for i in issues)
    by_condition = Counter(i.get("condition") for i in issues)
    by_severity = Counter(i.get("severity") for i in issues)

    lines: list[str] = [BEGIN, ""]
    lines.append("### 4 条件の判定")
    lines.append("")
    lines.append("| # | 条件 | condition_signal | 件数 | 判定 |")
    lines.append("|---|---|---|---|---|")
    for cond in ("C1", "C2", "C3", "C4"):
        signal = next(s for s, c in SIGNAL_TO_CONDITION.items() if c == cond)
        n = by_signal.get(signal, 0)
        verdict = "**FAIL**" if n else "PASS"
        lines.append(f"| {cond} | {CONDITION_LABEL[cond]} | `{signal}` | {n} | {verdict} |")
    smell = by_signal.get("smell", 0)
    lines.append(f"| — | (警告枠) | `smell` | {smell} | 判定に算入しない |")
    lines.append("")
    lines.append(f"- issues 合計: **{len(issues)} 件** "
                 f"(severity: " + " / ".join(
                     f"{s} {by_severity.get(s, 0)}" for s in ("critical", "high", "medium", "low")) + ")")

    # condition と condition_signal の二重帳簿を検出したら明示する。
    mismatches = [
        i for i in issues
        if i.get("condition_signal") in SIGNAL_TO_CONDITION
        and i.get("condition") != SIGNAL_TO_CONDITION[i["condition_signal"]]
    ]
    smell_with_condition = [i for i in issues if i.get("condition_signal") == "smell" and i.get("condition")]
    counted = {c: by_condition.get(c, 0) for c in ("C1", "C2", "C3", "C4")}
    lines.append(f"- `issues[].condition` の内訳: " + " / ".join(f"{c} {n}" for c, n in counted.items())
                 + f" / 未設定 {by_condition.get(None, 0)}")
    if mismatches or smell_with_condition:
        lines.append("")
        lines.append("> **注意**: `condition` と `condition_signal` が対応していない issue があります。"
                     f"対応不一致 {len(mismatches)} 件 / smell に便宜値が残るもの {len(smell_with_condition)} 件。"
                     "`validate-paradigm-coverage.py --strict-signal` で詳細を確認してください。")

    declared = data.get("fail_counts")
    derived = {k: by_signal.get(k, 0) for k in list(SIGNAL_TO_CONDITION) + ["smell"]}
    if declared is not None and dict(declared) != derived:
        lines.append("")
        lines.append(f"> **注意**: `fail_counts` の宣言値 {dict(declared)} が issues からの再導出値 {derived} と一致しません。")

    lines.append("")
    lines.append("### findings 一覧")
    lines.append("")
    lines.append("| finding_id | condition | signal | severity | 対象 |")
    lines.append("|---|---|---|---|---|")
    for i in sorted(issues, key=lambda x: (SEVERITY_ORDER.get(x.get("severity"), 9), x.get("finding_id", ""))):
        loc = i.get("location") or {}
        target = loc.get("clause") or loc.get("section") or loc.get("file") or "—"
        lines.append(
            f"| {i.get('finding_id', '—')} | {i.get('condition') or '—'} | "
            f"{i.get('condition_signal') or '—'} | {i.get('severity', '—')} | {target} |"
        )
    lines.append("")
    lines.append(END)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    ap.add_argument("--init", action="store_true", help="マーカーが無いとき末尾へ生成ブロックを追加する")
    args = ap.parse_args(argv[1:])

    if not args.findings.is_file():
        print(f"findings not found: {args.findings}", file=sys.stderr)
        return 2
    if not args.report.is_file():
        print(f"report not found: {args.report}", file=sys.stderr)
        return 2
    data = json.loads(args.findings.read_text(encoding="utf-8"))
    block = render(data)

    text = args.report.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        updated = head + block + tail
    elif args.init:
        updated = text.rstrip("\n") + "\n\n## 機械項目 (自動生成)\n\n" + block + "\n"
    else:
        print(f"marker not found in {args.report} (--init を付けると追加します)", file=sys.stderr)
        return 1

    if updated == text:
        print(f"already current: {args.report}")
        return 0
    args.report.write_text(updated, encoding="utf-8")
    print(f"updated: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
