#!/usr/bin/env python3
# /// script
# name: feedback_loop
# purpose: ゴールシーク反復で正負シグナルを蓄積し、次周回の merged_directive に反映する SSOT。
# inputs:
#   - API: record_positive(skill, signal, evidence) / record_negative(skill, signal, evidence)
#   - API: derive_next_directive(skill, current_round)
# outputs:
#   - eval-log/{skill}-feedback.jsonl 追記
#   - derive_next_directive: 構造化 directive 文字列([POS-WEIGHT]/[NEG-WEIGHT]/[BALANCED])
# contexts: [C]
# network: none
# write-scope: eval-log/*-feedback.jsonl
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: 採用された差込が再修正されたか等の正負フィードバックを蓄積し、
次周回 directive に「強化軸/回避軸」として注入する。

シグナル例:
  run-contract-generate:
    positive = 「差込結果が再修正なくSlack承認に至った」「validate.py 警告ゼロ」
    negative = 「黄色未塗布で検出」「条件分岐ドリフト」「住所/口座フォーマット警告」
  run-contract-finalize:
    positive = 「Slack承認検知から PDF 出力まで例外なし」
    negative = 「ポーリングタイムアウト」「PDF サイズ異常」
  run-template-sync:
    positive = 「scan_template diff=0 で完了」
    negative = 「MAPPING_DRIFT 再発」「UNMAPPED 列残存」

derive_next_directive は直近 WINDOW 周回(既定 5) の正負シグナルを集計し、
- 負優位 → [NEG-WEIGHT] 検証強化を優先
- 正優位 → [POS-WEIGHT] 周辺ケース展開
- 均衡 → [BALANCED] 現行方針を継続
の構造化文字列を返す。空シグナル時は空文字を返し、呼び出し側(goal_seek_log)で
従来 directive を維持する。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

WINDOW = 5  # 直近何周回を参照するか
EVAL_LOG_DIR_DEFAULT = "eval-log"


def _path(skill: str, eval_log_dir: str = EVAL_LOG_DIR_DEFAULT) -> Path:
    pdir = Path(eval_log_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir / f"{skill}-feedback.jsonl"


def _record(skill: str, polarity: Literal["positive", "negative"],
            signal: str, evidence: dict, eval_log_dir: str = EVAL_LOG_DIR_DEFAULT) -> None:
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "skill": skill,
        "polarity": polarity,
        "signal": signal,
        "evidence": evidence,
    }
    with _path(skill, eval_log_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_positive(skill: str, signal: str, evidence: dict,
                    eval_log_dir: str = EVAL_LOG_DIR_DEFAULT) -> None:
    """正シグナル(採用差込が再修正なし等)を追記。"""
    _record(skill, "positive", signal, evidence, eval_log_dir)


def record_negative(skill: str, signal: str, evidence: dict,
                    eval_log_dir: str = EVAL_LOG_DIR_DEFAULT) -> None:
    """負シグナル(ドリフト・タイムアウト等)を追記。"""
    _record(skill, "negative", signal, evidence, eval_log_dir)


def _load_recent(skill: str, eval_log_dir: str) -> list[dict]:
    p = _path(skill, eval_log_dir)
    if not p.exists():
        return []
    entries = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-WINDOW:]


def _top_signal(entries: list[dict]) -> str:
    """頻度最多のシグナルを返す(同数なら最新)。"""
    counts: dict[str, int] = {}
    last_seen: dict[str, int] = {}
    for i, e in enumerate(entries):
        s = e.get("signal", "")
        counts[s] = counts.get(s, 0) + 1
        last_seen[s] = i
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: (kv[1], last_seen[kv[0]]))[0]


def derive_next_directive(skill: str, current_round: int,
                          eval_log_dir: str = EVAL_LOG_DIR_DEFAULT) -> str:
    """直近 WINDOW 周回の正負シグナルから次周回 directive を生成。

    返り値:
      - 空文字: 蓄積なし → 呼出側は従来 directive を採用
      - "[NEG-WEIGHT] ..." / "[POS-WEIGHT] ..." / "[BALANCED] ..."
    """
    recent = _load_recent(skill, eval_log_dir)
    if not recent:
        return ""
    pos = [e for e in recent if e.get("polarity") == "positive"]
    neg = [e for e in recent if e.get("polarity") == "negative"]
    if len(neg) > len(pos):
        top = _top_signal(neg)
        return (f"[NEG-WEIGHT] 直近{len(recent)}周回で負シグナル{len(neg)}件 "
                f"(最頻: {top!r})。検証強化を優先 (round={current_round})")
    if len(pos) > len(neg):
        top = _top_signal(pos)
        return (f"[POS-WEIGHT] 直近{len(recent)}周回で正シグナル{len(pos)}件 "
                f"(最頻: {top!r}) が継続安定。次は周辺ケース展開 (round={current_round})")
    return (f"[BALANCED] 直近{len(recent)}周回で正{len(pos)}/負{len(neg)} "
            f"均衡。現行方針を継続 (round={current_round})")


def main() -> int:
    """CLI: 簡易 record + derive を CLI から行う。テスト/手動投入向け。"""
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("record")
    pr.add_argument("skill")
    pr.add_argument("--polarity", choices=["positive", "negative"], required=True)
    pr.add_argument("--signal", required=True)
    pr.add_argument("--evidence", default="{}")
    pr.add_argument("--eval-log-dir", default=EVAL_LOG_DIR_DEFAULT)
    pd = sub.add_parser("derive")
    pd.add_argument("skill")
    pd.add_argument("--round", type=int, default=0)
    pd.add_argument("--eval-log-dir", default=EVAL_LOG_DIR_DEFAULT)
    a = p.parse_args()
    if a.cmd == "record":
        _record(a.skill, a.polarity, a.signal, json.loads(a.evidence), a.eval_log_dir)
        print(f"recorded: {a.skill} {a.polarity} {a.signal}")
    else:
        out = derive_next_directive(a.skill, a.round, a.eval_log_dir)
        print(out)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
