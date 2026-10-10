#!/usr/bin/env python3
# /// script
# name: build-skipped-purpose
# purpose: P5 を manifest の skipWhen (interview.json.needs_excavation=false) で SKIP したとき、P6・P7・P11 が読む purpose.json を interview.json から決定論的に作る。深掘りはせず、interview の回答を phase5-purpose.schema.json の形へ写すだけ。
# inputs:
#   - argv: <interview_json_path> --out <purpose_json_path>
# outputs:
#   - file: <purpose_json_path> (phase5-purpose.schema.json 準拠。techniques_used に skip 由来の印を持つ)
#   - stderr: violation 理由 (needs_excavation が false でない / abstract_answers が残る / 必須項目の欠落・型の誤り)
#   - exit: 0=OK / 1=violation (fail-closed) / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: <purpose_json_path> のみ
# dependencies: []
# requires-python: ">=3.10"
# ///
"""P5 skip 経路の最小 purpose.json を interview.json から導出する。

P5 (skill-intake-purpose-excavator) は interview.json.needs_excavation=false のとき SKIP になり、
purpose.json を書かない。一方 P6 / P7 / P11 は purpose.json を必須入力に持つため、SKIP 行を
trace へ書く前にこの script で最小版を作る。値はすべて interview.json からの写しで、推測で
補わない:

  - techniques_used: ["skip:needs_excavation=false"] (深掘り由来でないことの印)
  - rounds: qa_log のうち axis=true-pain の行 (無ければ qa_log 全行) を {question, answer, finding} へ写す
  - agreement_loop_detected: false
  - true_purpose.verb_object: intent_contract の input_spec.raw_materials と output_spec.{audience, sink}
    から「<素材>を<読者>向けに<出力先>へ出力する」を組み立てる
  - true_purpose.underlying_motivation: five_axes.rows の「真の課題」の content

needs_excavation が false でない、または abstract_answers が残る interview.json は P5 を飛ばせない
ので exit 1 で拒否する。同じ入力からは同じ bytes を書く。

Exit 0 = OK, 1 = violation, 2 = usage/IO error。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SKIP_TECHNIQUE = "skip:needs_excavation=false"
TRUE_PAIN_ROW = "真の課題"


class Violation(Exception):
    pass


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Violation(f"{label} が空")
    return value.strip()


def require_texts(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise Violation(f"{label} が空")
    return [require_text(item, f"{label}[{index}]") for index, item in enumerate(value)]


def derive_purpose(interview: dict[str, Any]) -> dict[str, Any]:
    if interview.get("needs_excavation") is not False:
        raise Violation("needs_excavation が false でない (P5 を SKIP できない)")
    if interview.get("abstract_answers"):
        raise Violation("abstract_answers が残っている (P5 を SKIP できない)")

    qa_log = interview.get("qa_log")
    if not isinstance(qa_log, list) or not qa_log:
        raise Violation("qa_log が空")
    picked = [(index, row) for index, row in enumerate(qa_log) if isinstance(row, dict) and row.get("axis") == "true-pain"]
    if not picked:
        picked = list(enumerate(qa_log))
    rounds = []
    for index, row in picked:
        if not isinstance(row, dict):
            raise Violation(f"qa_log[{index}] が object でない")
        rounds.append({
            "question": require_text(row.get("question_text"), f"qa_log[{index}].question_text"),
            "answer": require_text(row.get("normalized_answer"), f"qa_log[{index}].normalized_answer"),
            "finding": f"interview.json qa_log[{index}] の回答をそのまま採用 (needs_excavation=false のため P5 の深掘りは未実施)",
        })

    contract = interview.get("intent_contract")
    if not isinstance(contract, dict):
        raise Violation("intent_contract がない")
    input_spec = contract.get("input_spec") if isinstance(contract.get("input_spec"), dict) else {}
    output_spec = contract.get("output_spec") if isinstance(contract.get("output_spec"), dict) else {}
    materials = "・".join(require_texts(input_spec.get("raw_materials"), "intent_contract.input_spec.raw_materials"))
    audience = require_text(output_spec.get("audience"), "intent_contract.output_spec.audience")
    sink = require_text(output_spec.get("sink"), "intent_contract.output_spec.sink")

    five_axes = interview.get("five_axes")
    rows = five_axes.get("rows") if isinstance(five_axes, dict) else None
    if not isinstance(rows, list):
        raise Violation("five_axes.rows が配列でない")
    pain = next((row for row in rows if isinstance(row, dict) and row.get("name") == TRUE_PAIN_ROW), None)
    if pain is None:
        raise Violation(f"five_axes.rows に「{TRUE_PAIN_ROW}」がない")
    motivation = require_text(pain.get("content"), f"five_axes.rows[{TRUE_PAIN_ROW}].content")

    return {
        "techniques_used": [SKIP_TECHNIQUE],
        "rounds": rounds,
        "agreement_loop_detected": False,
        "true_purpose": {
            "verb_object": f"{materials}を{audience}向けに{sink}へ出力する",
            "underlying_motivation": motivation,
        },
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="P5 skip 経路の最小 purpose.json を interview.json から作る")
    parser.add_argument("interview")
    parser.add_argument("--out", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2  # --help は 0、引数の誤りは 2
    try:
        interview = json.loads(Path(args.interview).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[build-skipped-purpose] input invalid: {exc}\n")
        return 2
    if not isinstance(interview, dict):
        sys.stderr.write("[build-skipped-purpose] violation: interview.json が object でない\n")
        return 1
    try:
        purpose = derive_purpose(interview)
    except Violation as exc:
        sys.stderr.write(f"[build-skipped-purpose] violation: {exc}\n")
        return 1
    try:
        Path(args.out).write_text(json.dumps(purpose, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"[build-skipped-purpose] write failed: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
