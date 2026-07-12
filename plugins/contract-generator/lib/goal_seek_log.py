#!/usr/bin/env python3
# /// script
# name: goal_seek_log
# purpose: ゴールシーク周回アンカー(progress.json/intermediate.jsonl)を記録する。契約書生成本体から分離した横断関心事。
# inputs:
#   - results(process_row結果リスト) + progress_dir
# outputs:
#   - eval-log への progress.json / intermediate.jsonl 追記
# contexts: [C]
# network: false
# write-scope: local-eval-log
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: ゴールシーク周回記録(SKILL.md ゴールシーク配線の実体)。

engine.py から抽出。各実行を1周回とみなし original_goal 不変アンカー + スナップショット +
次周回への指示を eval-log に追記する。契約書生成(Google API)とは依存層が異なる(ローカルfsのみ)。
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

ORIGINAL_GOAL = (
    "管理台帳の作成指示◯行を個人/法人それぞれのひな形から黄色維持Google Docs版と"
    "黄色除去PDF版として該当フォルダに生成し、台帳へURL・ステータス・日時を書き戻した状態"
)


def record_iteration(skill, results, progress_dir, dry_run):
    """ゴールシーク周回アンカーを記録する。

    skill: 呼出元 skill 名 (例: "run-contract-generate" / "run-contract-finalize" /
      "run-template-sync")。progress.json / intermediate.jsonl のファイル名に組込み、
      skill 間のログ混在を防ぐ (H3 修正: 以前はハードコード)。
    """
    if dry_run:
        return
    pdir = Path(progress_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    prog_path = pdir / f"{skill}-progress.json"
    inter_path = pdir / f"{skill}-intermediate.jsonl"

    prev = json.loads(prog_path.read_text(encoding="utf-8")) if prog_path.exists() else {}
    iteration = prev.get("iteration", -1) + 1
    done = sum(1 for r in results if r["status"] == "completed")
    needs = [r for r in results if r["status"] == "needs-input"]
    drift = [r for r in results if r["status"] == "drift"]
    invalid = [r for r in results if r["status"] == "invalid"]
    snapshot = f"完了{done}/{len(results)} 残り(needs-input={len(needs)}, drift={len(drift)}, invalid={len(invalid)})"

    if not (needs or drift or invalid):
        directive, signal = "全対象完了。追加周回不要", "aligned"
    elif needs:
        directive, signal = "欠損必須列をAskUserQuestionで補完し台帳へ書戻して再実行", "compressing"
    elif drift:
        directive, signal = "scan_template.pyでひな形差分を診断しtemplate-mapping.json/台帳を更新", "widening"
    else:
        directive, signal = "validateエラー(口座/日付/金額等)を台帳修正して再実行", "compressing"

    prev_remaining = prev.get("remaining")
    remaining = len(needs) + len(drift) + len(invalid)
    if prev_remaining is not None and prev_remaining == remaining and remaining > 0:
        signal = "stagnant"
        # stagnant 時は directive を昇格: SubAgent fork で根本原因分析を促す
        directive = "[STAGNANT] 同一残数連続。SubAgent fork で根本原因分析(" + directive + ")"

    # feedback_loop からの正負シグナル要約を merged_directive に組込
    # O21: 例外無音化は eval-log 不在/壊れ JSON/期待キー欠落のみに限定。
    # それ以外 (ImportError 以外のロジックエラー等) は logging.exception 後に raise。
    try:
        import feedback_loop
        fb = feedback_loop.derive_next_directive(skill, iteration,
                                                 eval_log_dir=str(pdir))
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        fb = ""
    except Exception:
        logging.exception("[goal-seek] feedback_loop.derive_next_directive failed")
        raise
    merged_directive = directive + (f" | {fb}" if fb else "")

    entry = {
        "iteration": iteration,
        "original_goal": ORIGINAL_GOAL,
        "current_goal_snapshot": snapshot,
        "delta_from_original": "初回実行" if iteration == 0 else f"前周回比 残り{prev_remaining}→{remaining}",
        "merged_directive_for_next": merged_directive,
        "drift_signal": signal,
    }
    with inter_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    prog_path.write_text(json.dumps({
        "iteration": iteration,
        "original_goal_hash": hashlib.sha256(ORIGINAL_GOAL.encode()).hexdigest(),
        "remaining": remaining,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[goal-seek] iteration={iteration} {snapshot} → {merged_directive} (signal={signal})")
