# Workflow Sequence (run-skill-intake 11 phase)

## 起動順序と前提 JSON

実行順の正本は `workflow-manifest.json` の `phases[]` で、この表は人が読むための写し。phase が失敗したら、その attempt を `status=FAIL` と `error` 付きで `intake-trace.json` に追記して停止する。再開は同じ trace で失敗した phase を attempt+1 としてやり直す（SKILL.md「失敗からの再開」）。「失敗時の戻り先」は、原因が前段の成果物にあったときに見直す phase の目安で、自動では巻き戻さない。前段を作り直すときは同じ trace では続けず、新しい trace で P1 から実行する（manifest が自動で戻すのは Gate A 否認時の P8→P4 だけ）。

| Phase | 種別 | 名前 | 入力 | 出力 | 失敗時の戻り先 |
|--|--|--|--|--|--|
| 1 | Skill | run-intake-kickoff | initial utterance | kickoff.json | (なし、再起動) |
| 2 | SubAgent | skill-intake-assumption-challenger | kickoff.json | assumption.json | Phase 1 |
| 3 | SubAgent | skill-intake-user-profiler | kickoff.json, assumption.json | profile.json | Phase 2 |
| 4 | Skill | run-intake-interview | profile.json | sheet.md, interview.json | Phase 3 |
| 5 | SubAgent | skill-intake-purpose-excavator | sheet.md (needs_excavation=true 時のみ) | purpose.json（SKIP 時は `scripts/build-skipped-purpose.py` が interview.json から作る） | Phase 4 |
| 6 | Skill | run-intake-option-catalog | purpose.json | options.json | Phase 5 |
| 7 | Skill | run-intake-visualize | sheet.md, purpose.json | visuals.json + PNG 群 | Phase 6 |
| 8 | SubAgent | skill-intake-summarizer | 全 JSON | summary.{md,json} + Gate A 承認 | Phase 4 (再ヒアリング) |
| 9 | Skill | run-intake-finalize | 全 JSON | intake.{md,json} | (各 JSON 不整合時は当該 phase へ) |
| 10 | Skill | run-notion-intake-publish | intake.json | notion-url.txt | (Notion 側のみ、再公開可能) |
| 11 | Skill | run-intake-next-action | summary.json, purpose.json, options.json, kickoff.json + Notion 公開の記録 (notion-publish-result.json, notion-log.json) | next-action.json | Phase 10 |

## SubAgent 化判断基準

Phase 2/3/5/8 のみ SubAgent (fresh context) とする理由:

- **Phase 2 (assumption-challenger)**: 表層仮説への同意ループ回避。主スレッド context があると Yes バイアス。
- **Phase 3 (user-profiler)**: 6 軸推定の客観性。発話履歴に引きずられない fresh 推定。
- **Phase 5 (purpose-excavator)**: 8 技法を独立適用。直近 5 ターンの同意ループ検出も fresh context が前提。
- **Phase 8 (summarizer)**: Gate A の独立レビュー価値。生成側の自己肯定回避。

Phase 1/4/6/7/9/10/11 は主スレッド Skill で十分:
- Phase 1/4 は AskUserQuestion 主体の対話 (SubAgent 化すると往復オーバヘッドのみ増える)
- Phase 6/7/9/10/11 は決定論処理 (script 駆動) で LLM 判断小
