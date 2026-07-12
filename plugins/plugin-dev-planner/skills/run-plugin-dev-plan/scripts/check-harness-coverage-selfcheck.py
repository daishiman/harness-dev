#!/usr/bin/env python3
# /// script
# name: check-harness-coverage-selfcheck
# purpose: plugin-dev-planner が「生成 plan に課すハーネス規律」を自分自身へも適用する dogfooding 自己検査。repo-root の validate-harness-coverage.py を subprocess 実行し、6 種別 (scripts/skills/agents/commands/hooks/docs) × 2 軸 (mechanical/llm_eval) = 12 軸が全て report に宣言されている (欠落キーが無い) ことの構造検証に限定する。達成率数値 (met/coverage_pct) は判定に使わない (Goodhart 回避・軸が測定/宣言されているかのみを見る)。
# inputs:
#   - argv: [--self-test]  (通常モードは引数なし。report は subprocess で validator から取得する)
#   - reads (subprocess): <repo-root>/scripts/validate-harness-coverage.py の出力 report
# outputs:
#   - stdout: 12 軸の宣言/計装サマリ
#   - stderr: 欠落軸 violation / validator 不在時の skip 理由
#   - exit: 0=12軸宣言済 or validator 不在で skip / 1=軸欠落 / 2=usage/run error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""harness-coverage の 12 軸自己適用 (C3・dogfooding) を構造検証する self-check。

『生成 plan に harness-creator 規律を課す』(layer a) だけでなく、本 plugin 自身も同じ
12 軸ハーネスで CI 検証される (layer b = 自己適用) ことを保証する。validate-harness-coverage.py
の report は per-plugin でなくグローバル集計 (6 種別 × 2 軸) ゆえ、本 script は「plugin-dev-planner
の artifact が 6 種別すべての測定対象として軸に宣言されているか」= 12 軸の構造存在のみを検査する。

現状の達成率 (met/coverage_pct) は判定に使わない: 率を gate にすると『数字合わせ』を誘発する
(Goodhart)。率の回帰は本 script でなく validate-harness-coverage.py の --ratchet floor が別途担う。
本 script が fail するのは、ある種別/軸が report から消えた=coverage harness が当該 component 種別を
覆わなくなった構造的欠落 (自己適用の断線) のときだけである。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# validate-harness-coverage.py が build_report で必ず出す 6 種別 × 2 軸 = 12 軸。
EXPECTED_TYPES = ("scripts", "skills", "agents", "commands", "hooks", "docs")
AXES = ("mechanical", "llm_eval")


def find_validator() -> Path | None:
    """自 script から祖先を遡上して <repo-root>/scripts/validate-harness-coverage.py を探す。

    repo 文脈でのみ在る (標準 install=repo 外では不在)。見つからなければ None (呼び出し側で skip)。
    """
    for anc in Path(__file__).resolve().parents:
        cand = anc / "scripts" / "validate-harness-coverage.py"
        if cand.is_file():
            return cand
    return None


def load_report(validator: Path) -> dict | None:
    """validator を --json <tmp> で subprocess 実行し report dict を返す (失敗時 None)。"""
    repo_root = validator.parent.parent
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "harness-coverage.json"
        try:
            subprocess.run(
                [sys.executable, str(validator), "--json", str(out)],
                cwd=str(repo_root), capture_output=True, text=True, check=False,
                timeout=120,  # validator hang 時の無限待機を防ぐ (実測 ~1s)
            )
        except subprocess.TimeoutExpired:
            return None
        if not out.is_file():
            return None
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None


def check_report_structure(report: object) -> list[str]:
    """6 種別 × 2 軸 = 12 軸が report に宣言されている (dict として存在) かを検査する。

    達成率 (met/coverage_pct) や instrumented 真偽は判定しない (構造存在のみ・Goodhart 回避)。
    """
    if not isinstance(report, dict):
        return ["harness-coverage report が dict でない (自己適用検証不能)"]
    raw = report.get("sections")
    sections = {
        s["type"]: s
        for s in (raw if isinstance(raw, list) else [])
        if isinstance(s, dict) and isinstance(s.get("type"), str)
    }
    errors: list[str] = []
    for t in EXPECTED_TYPES:
        sec = sections.get(t)
        if sec is None:
            errors.append(f"種別 {t} の coverage section が report に無い (12軸自己適用の断線)")
            continue
        for axis in AXES:
            if not isinstance(sec.get(axis), dict):
                errors.append(f"{t}/{axis} 軸が宣言されていない (キー欠落=自己適用の断線)")
    return errors


def _instrumented_summary(report: dict) -> str:
    total = sum(
        1 for s in report.get("sections", []) if isinstance(s, dict)
        for axis in AXES if isinstance(s.get(axis), dict)
    )
    inst = sum(
        1 for s in report.get("sections", []) if isinstance(s, dict)
        for axis in AXES if isinstance(s.get(axis), dict) and s[axis].get("instrumented")
    )
    return f"12軸中 宣言 {total} / 計装 {inst} (率 met={report.get('axes_met')} は参考・判定外)"


# ─────────────────────────── self-test (埋め込み最小 fixture) ───────────────────────────
def _complete_report() -> dict:
    return {"axes_met": 8, "sections": [
        {"type": t, "mechanical": {"instrumented": True, "met": True},
         "llm_eval": {"instrumented": True, "met": False}}
        for t in EXPECTED_TYPES
    ]}


def _self_test() -> tuple[int, list[str]]:
    """12軸宣言済/軸欠落/キー欠落の各判定を埋め込み fixture で固定する。"""
    msgs: list[str] = []

    if check_report_structure(_complete_report()):
        msgs.append(f"(C3) 12軸宣言済 report を誤検出: {check_report_structure(_complete_report())}")

    # 1 種別 (docs) が欠落 → violation
    missing_type = _complete_report()
    missing_type["sections"] = [s for s in missing_type["sections"] if s["type"] != "docs"]
    if not any("docs" in e and "断線" in e for e in check_report_structure(missing_type)):
        msgs.append("(C3) 種別欠落 (docs) を検出できない")

    # 1 軸 (scripts/llm_eval) のキー欠落 → violation
    missing_axis = _complete_report()
    del missing_axis["sections"][0]["llm_eval"]
    if not any("scripts/llm_eval" in e for e in check_report_structure(missing_axis)):
        msgs.append("(C3) 軸キー欠落 (scripts/llm_eval) を検出できない")

    # 達成率が低くても (met=False だらけ) 軸が揃っていれば通る (率は判定外)
    low = _complete_report()
    for s in low["sections"]:
        s["mechanical"]["met"] = False
        s["llm_eval"]["met"] = False
    if check_report_structure(low):
        msgs.append("(C3) 低達成率 report を率で誤検出 (Goodhart 回避違反)")

    return (1 if msgs else 0), msgs


def run() -> tuple[int, list[str], str]:
    validator = find_validator()
    if validator is None:
        return 0, [], "skip: validate-harness-coverage.py 不在 (標準 install=repo 外) — 自己適用検査は repo 文脈のみ"
    report = load_report(validator)
    if report is None:
        return 2, ["validate-harness-coverage.py の report 取得に失敗した"], ""
    errors = check_report_structure(report)
    summary = _instrumented_summary(report) if isinstance(report, dict) else ""
    return (1 if errors else 0), errors, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="harness-coverage の 12軸自己適用を構造検証する")
    ap.add_argument("--self-test", action="store_true", help="埋め込み fixture で C3 検出を自己検査する")
    args = ap.parse_args(argv)

    if args.self_test:
        code, msgs = _self_test()
        if code == 0:
            sys.stdout.write("OK: check-harness-coverage-selfcheck の C3 構造検証が期待どおり\n")
            return 0
        for m in msgs:
            sys.stderr.write(m + "\n")
        return code

    code, errors, summary = run()
    if code == 0:
        if summary.startswith("skip"):
            sys.stderr.write("SKIP:" + summary[len("skip:"):] + "\n")
        else:
            sys.stdout.write(f"OK: harness-coverage 12軸自己適用が宣言済 ({summary})\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
