#!/usr/bin/env python3
# /// script
# name: build-questions
# purpose: depth と既記入軸から「出すべき質問列」を Q-ID で決定論的に確定する。LLM の都度立案を排除。
# inputs:
#   - --plan: references/question-plan.json (Q-ID 選択の正本)
#   - --bank: references/question-bank.md (Q-ID → 文面の正本、索引表)
#   - --depth: light|standard|detailed (kickoff.json 由来。quick/deep は旧 alias)
#   - --pattern: A|B|C|D|E (任意, skip 判定)
#   - --sheet: sheet.md (任意, 記入済み軸の skip 判定)
# outputs:
#   - stdout: JSON 配列 [{order, axis, axis_label, qid, text, options, allow_free_text}] を axis_order 順で
# contexts: [interview phase 4]
# network: false
# write-scope: none
# requires-python: ">=3.10"
# ///
"""ヒアリング質問を決定論的に選択する (同 depth/pattern/既記入軸 → 同じ質問列)。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AXIS_JP = {
    "output": "出力先",
    "source": "情報源",
    "share": "共有相手",
    "true-pain": "真の課題",
    "knowledge-asset": "ナレッジ資産",
}


_AXIS_JP_SET = {"出力先", "情報源", "共有相手", "真の課題", "ナレッジ資産", "横断"}
_DEPTH_SET = {"quick", "light", "standard", "deep", "detailed"}


def parse_bank(bank_text: str) -> dict[str, str]:
    """question-bank.md の索引表 (Q-ID | 軸 | 深度 | 文面) からのみ {Q-ID: 文面} を抽出する。
    後続の 2 列サンプル表など、軸/深度列が規定値でない行は除外する (最初に確定した Q-ID を優先)。"""
    qmap: dict[str, str] = {}
    row = re.compile(r"^\|\s*(Q\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")
    for line in bank_text.splitlines():
        m = row.match(line)
        if not m:
            continue
        qid, axis, depth, text = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
        if axis not in _AXIS_JP_SET or depth not in _DEPTH_SET:
            continue
        qmap.setdefault(qid, text)  # 最初の索引表定義を正とする
    return qmap


def filled_axes(sheet_text: str) -> set[str]:
    """sheet.md で内容があり [?] を含まない軸を『記入済み』とみなす。"""
    done: set[str] = set()
    for axis_key, jp in AXIS_JP.items():
        m = re.search(rf"#+\s*{re.escape(jp)}\s*\n(.+?)(?=\n#+\s|\Z)", sheet_text, re.S)
        if m and m.group(1).strip() and "[?]" not in m.group(1):
            done.add(axis_key)
    return done


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--depth", default=None)
    ap.add_argument("--pattern", default=None)
    ap.add_argument("--sheet", default=None)
    args = ap.parse_args(argv)

    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        bank = parse_bank(Path(args.bank).read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"input error: {e}\n")
        return 2

    requested_depth = (args.depth or "").strip()
    depth_aliases = plan.get("depth_aliases", {})
    normalized_depth = depth_aliases.get(requested_depth, requested_depth)
    depth = normalized_depth if normalized_depth in plan["plan_by_depth"] else plan.get("default_depth", "standard")
    axis_order = plan["axis_order"]
    depth_plan = plan["plan_by_depth"][depth]

    skip: set[str] = set()
    if args.pattern and args.pattern.strip().upper().startswith("C"):
        skip |= set(plan.get("skip_rules", {}).get("pattern_C_skips_axes", []))
    if args.sheet:
        p = Path(args.sheet)
        if p.is_file():
            skip |= filled_axes(p.read_text(encoding="utf-8"))

    out = []
    order = 0
    for axis in axis_order:
        if axis in skip:
            continue
        qid = depth_plan.get(axis)
        if not qid:
            continue
        text = bank.get(qid)
        if text is None:
            sys.stderr.write(f"FAIL: qid {qid} (axis {axis}) が question-bank.md に無い\n")
            return 1
        order += 1
        out.append({
            "order": order,
            "axis": axis,
            "axis_label": AXIS_JP.get(axis, axis),
            "qid": qid,
            "text": text,
            "options": plan.get("ask_user_question_options", {}).get(axis, []),
            "allow_free_text": True,
        })

    sys.stdout.write(json.dumps({"depth": depth, "questions": out}, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
