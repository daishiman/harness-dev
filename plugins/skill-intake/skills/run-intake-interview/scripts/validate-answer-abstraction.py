#!/usr/bin/env python3
# /// script
# name: validate-answer-abstraction
# purpose: 回答が抽象的か否かを abstract-answer-patterns.md の規則で機械判定し、needs_excavation を決定論化する。
# inputs:
#   - --patterns: references/abstract-answer-patterns.md (抽象語リストの正本)
#   - --answer: 判定対象の回答文字列
#   - --axis: 任意 (出力に反映するのみ)
# outputs:
#   - stdout: JSON {abstract: bool, matched: [..], reason: str}
#   - exit 0: 具体 / exit 3: 抽象 (needs_excavation=true 相当)
# contexts: [interview phase 4]
# network: false
# write-scope: none
# requires-python: ">=3.10"
# ///
"""回答の抽象度を機械判定する (同じ回答 → 同じ判定、LLM の定性判断を排除)。

判定規則 (abstract-answer-patterns.md 準拠, 決定論):
  1. 曖昧フィラー (何となく/とりあえず/普通に/うまく/ちゃんと/きちんと) を含む → 抽象。
  2. 動作抽象語 (効率化/最適化/自動化/改善/強化/整理) を含み、かつその語の
     直前に目的語マーカー『を』が無い → 抽象 (動詞+目的語に分解できない)。
     例: 「効率化したい」→抽象 / 「顧客アンケート集計を自動化したい」→具体。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# フォールバック既定値 (patterns md が読めない場合)。正本は abstract-answer-patterns.md。
DEFAULT_ACTION_ABSTRACT = ["効率化", "最適化", "自動化", "改善", "強化", "整理"]
DEFAULT_VAGUE_FILLER = ["何となく", "なんとなく", "とりあえず", "普通に", "うまく", "ちゃんと", "きちんと"]

# procedure 軸専用の未回答表現 (完全一致で判定)。手順が言語化できないユーザーの
# overview_fallback 切替トリガ (goal-spec C2/C6)。他軸の既存挙動は変えない。
UNANSWERED_PATTERNS = [
    "わからない", "わかりません", "分からない", "分りません",
    "特にない", "特に無い", "思いつかない", "答えられない", "ない", "なし",
]


def parse_patterns(text: str) -> tuple[list[str], list[str]]:
    """patterns md の箇条書き ('A / B / C') から語を抽出する。
    フィラー系 (何となく等) と動作抽象語系を分類する。"""
    words: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        if "→" in body or "(" in body or "（" in body:  # 例示行は除外
            continue
        for w in re.split(r"[/／]", body):
            w = w.strip()
            if w and re.fullmatch(r"[ぁ-んァ-ヶ一-龠ー]+", w):
                words.append(w)
    vague = [w for w in words if w in set(DEFAULT_VAGUE_FILLER)]
    action = [w for w in words if w not in set(DEFAULT_VAGUE_FILLER)]
    return (action or DEFAULT_ACTION_ABSTRACT, vague or DEFAULT_VAGUE_FILLER)


def _judge_abstract(a: str, action_words: list[str], vague_words: list[str]) -> dict:
    matched: list[str] = []
    # 規則1: 曖昧フィラー
    for w in vague_words:
        if w in a:
            matched.append(w)
    if matched:
        return {"abstract": True, "matched": matched,
                "reason": "曖昧フィラー語を含む (具体性なし)"}
    # 規則2: 動作抽象語 + 直前に『を』が無い
    for w in action_words:
        idx = a.find(w)
        if idx == -1:
            continue
        preceding = a[:idx]
        if "を" not in preceding:
            return {"abstract": True, "matched": [w],
                    "reason": f"抽象語『{w}』の直前に目的語(を)が無く、動詞+目的語に分解できない"}
    return {"abstract": False, "matched": [], "reason": "動詞+目的語に分解できる具体回答"}


def judge(answer: str, action_words: list[str], vague_words: list[str],
          axis: str | None = None) -> dict:
    """回答の抽象度を判定する。axis=procedure のときのみ未回答 (空 / 完全一致の否定表現)
    を検出し、abstract=True かつ unanswered=True を返す (overview_fallback 切替トリガ)。"""
    a = answer.strip()
    if axis == "procedure":
        if not a:
            return {"abstract": True, "unanswered": True, "matched": [],
                    "reason": "手順が未回答 (空)"}
        stripped = a.rstrip("。.!！?？ 　")
        if stripped in UNANSWERED_PATTERNS:
            return {"abstract": True, "unanswered": True, "matched": [stripped],
                    "reason": "手順の未回答表現 (overview_fallback トリガ)"}
    res = _judge_abstract(a, action_words, vague_words)
    res["unanswered"] = False
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", required=True)
    ap.add_argument("--answer", required=True)
    ap.add_argument("--axis", default=None)
    args = ap.parse_args(argv)

    try:
        ptext = Path(args.patterns).read_text(encoding="utf-8")
        action_words, vague_words = parse_patterns(ptext)
    except Exception:
        action_words, vague_words = DEFAULT_ACTION_ABSTRACT, DEFAULT_VAGUE_FILLER

    res = judge(args.answer, action_words, vague_words, args.axis)
    if args.axis:
        res["axis"] = args.axis
    sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
    return 3 if res["abstract"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
