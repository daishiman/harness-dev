#!/usr/bin/env python3
# /// script
# name: build-verdict
# purpose: Derive verdict.json from findings.json so the 4-condition verdict can never disagree with the findings it summarises.
# inputs:
#   - --findings <findings.json>
#   - --verdict <verdict.json> (existing file supplies the non-derivable identity fields)
#   - --check (verify only; non-zero exit when the file would change)
#   - --plugin/--skill/--scope-mode/--run-id/--aggregated-at (required only when creating from scratch)
# outputs:
#   - verdict.json rewritten with derived values
#   - stdout: what changed / already current
#   - exit: 0=updated or already current / 1=--check found drift / 2=usage or input error
# contexts: [C]
# network: false
# write-scope: verdict file passed via --verdict
# dependencies: []
# ///
"""findings.json から verdict.json の導出可能フィールドを再生成する。

verdict.json の fail_counts / verdict / thought_method_coverage / iteration_count /
status は、すべて findings.json から一意に導ける。にもかかわらず生成器が無く
手書きされていたため、findings.json を 28 件から 34 件へ更新した際に verdict.json が
取り残され、同一 run 内で「verdict は 28 件、findings は 34 件」という状態が発生した
(run-20260809-mvp-tiering で実際に発生)。

導出できないのは run の同定情報 (plugin / skill / scope_mode / run_id / aggregated_at) と
副作用の記録 (safety_valve_fired / observable_emitted) だけなので、それらは既存 verdict.json
から持ち越すか CLI で明示する。--check は CI 用で、書かずに drift だけを検出する。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# 4 条件と、その FAIL を立てる condition_signal の対応。smell はどの条件にも寄与しない
# 警告枠なので、verdict の PASS/FAIL 判定には一切使わない。
CONDITION_TO_SIGNAL = {
    "矛盾なし": "contradiction",
    "漏れなし": "omission",
    "整合性あり": "inconsistency",
    "依存関係整合": "dependency_break",
}
SIGNALS = list(CONDITION_TO_SIGNAL.values()) + ["smell"]

# 導出できず既存ファイル (または CLI) から持ち越すフィールド。
CARRIED_FIELDS = (
    "plugin",
    "skill",
    "scope_mode",
    "run_id",
    "aggregated_at",
    "safety_valve_fired",
    "observable_emitted",
)


def derive(findings: dict, carried: dict) -> dict:
    issues = [i for p in findings.get("paradigm_findings", []) for i in p.get("issues", [])]
    by_signal = Counter(i.get("condition_signal") for i in issues)
    fail_counts = {s: by_signal.get(s, 0) for s in SIGNALS}

    verdict = {
        cond: ("FAIL" if fail_counts[sig] else "PASS")
        for cond, sig in CONDITION_TO_SIGNAL.items()
    }

    out = {k: carried[k] for k in ("plugin", "skill", "scope_mode") if k in carried}
    for k in ("run_id", "aggregated_at"):
        if carried.get(k) is not None:
            out[k] = carried[k]
    out["verdict"] = verdict
    out["fail_counts"] = fail_counts
    coverage = findings.get("thought_method_coverage")
    if coverage is not None:
        out["thought_method_coverage"] = coverage
    out["iteration_count"] = findings.get("loop_count", 0)
    out["status"] = findings.get("run_status", "incomplete")
    for k in ("safety_valve_fired", "observable_emitted"):
        if carried.get(k) is not None:
            out[k] = carried[k]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True, type=Path)
    ap.add_argument("--verdict", required=True, type=Path)
    ap.add_argument("--check", action="store_true", help="書かずに drift のみ検出する (CI 用)")
    for flag in ("--plugin", "--skill", "--scope-mode", "--run-id", "--aggregated-at"):
        ap.add_argument(flag)
    args = ap.parse_args(argv[1:])

    if not args.findings.is_file():
        print(f"findings not found: {args.findings}", file=sys.stderr)
        return 2
    findings = json.loads(args.findings.read_text(encoding="utf-8"))

    existing: dict = {}
    if args.verdict.is_file():
        existing = json.loads(args.verdict.read_text(encoding="utf-8"))

    carried = {k: existing.get(k) for k in CARRIED_FIELDS}
    for key, val in (
        ("plugin", args.plugin),
        ("skill", args.skill),
        ("scope_mode", args.scope_mode),
        ("run_id", args.run_id),
        ("aggregated_at", args.aggregated_at),
    ):
        if val is not None:
            carried[key] = val

    missing = [k for k in ("plugin", "skill", "scope_mode") if not carried.get(k)]
    if missing:
        print(
            f"既存 verdict.json が無く CLI 指定も無いため同定情報を決められない: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    derived = derive(findings, carried)
    text = json.dumps(derived, ensure_ascii=False, indent=2) + "\n"

    if existing == derived:
        print(f"already current: {args.verdict}")
        return 0

    if args.check:
        for key in sorted(set(existing) | set(derived)):
            if existing.get(key) != derived.get(key):
                print(
                    f"drift: {args.verdict}: {key}: verdict={existing.get(key)!r} "
                    f"findings 由来={derived.get(key)!r}",
                    file=sys.stderr,
                )
        return 1

    args.verdict.write_text(text, encoding="utf-8")
    print(f"updated: {args.verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
