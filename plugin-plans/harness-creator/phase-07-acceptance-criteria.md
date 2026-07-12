---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
purpose 由来の受入観点 (task-graph consumer 責務が producer 側 SSOT を再実装せず消費すること・task-state.json の単一 writer が保たれること・discovered-task が E4 境界として E3 と分離されていること・task_graph_ref 無し handoff の後方互換が保たれること・未処理 discovered-task を完了ブロックし task-graph 実行知見を knowledge 化すること) を二値の受入基準として index.md の「受入確認」章へ列挙する。

## 背景
C1-C13 の各 checklist は build 後の見方 (どう確認すれば満たされたと言えるか) を持つ必要があり、本 phase はその確認方法を確定する。

## 前提条件
- P06 の harness_coverage 設計が確定している。

## ドメイン知識
- 受入観点は index.md の「受入確認」章で C1-C13 の checklist id ごとに「build 時の確認方法」を列挙する (P12 で index.md へ実際に記述する)。特に C6 (後方互換) は `test_task_graph_ref_dispatch.py` の 2 ケース (有り/無し) の green を確認方法とし、C2/C5 (周回衝突排除) は `resolve_build_dir(target_plugin_slug, cycle_id)` の handoff.cycle_id 有り/無し 2 ケース (+ `--out-dir` 上書き plan の負例) green を確認方法とし、C8 (fork evaluator の意味判定) は human 判定手順 (`assign-plugin-plan-evaluator` 相当の fork evaluator による意味評価) を確認方法とする。C10 (冪等再開・実行排他) は `test_manage_build_lease.py` の lock 取得/二重起動検出/孤児 lease 回収/graph_hash pin 一致・不一致の各ケース green を確認方法とし、C11 (実行イベントログ) は task-events.jsonl の replay 終端 state が task-state.json と一致する整合検査 green、C12 (実行時停滞検出) は `test_summarize_task_progress.py` の停滞診断ケース green、C13 (完了前 discovered-task/knowledge gate) は `test_record_task_graph_knowledge.py` の未処理 inbox 完了拒否・解決済み status PASS・Loop A/Loop B 追記・生ログ丸写し禁止 green を確認方法とする。**2 ループ統合 (外ループ=spec 改善 / 内ループ=build 実行)** は、(結合点1) C08 完了ゲートが未処理 discovered-task で `completion_gate:blocked`+`handback_command` を返し C06 が実行可能ハンドバック (`run-plugin-dev-plan --mode update --discovered-inbox` + capability-build 再実行) を提示すること、(結合点2) 再実行時に C07/C01 が新 graph_hash を再 pin し内ループを改善済み仕様で再始動すること、spec-gap stall (`detect_stall` の `has_spec_gap`) を C04 structural emit で外ループの単一ジョイントへ合流させること、を確認方法とする (producer 側 `accept-discovered-task.py --inbox` ドレイン green と対を成す)。

## 成果物
- 受入観点の一覧設計 (index.md 「受入確認」章の元データ)。

## スコープ外
- index.md の実ファイル記述 (P12 相当、本 plan では index.md 生成時に反映)。

## 完了チェックリスト
- [ ] C1-C13 全てに build 時の確認方法が存在する。

### 受入例
（本 phase は縮小要件対象 [REDUCED_REQUIREMENT_PHASES] のため、見出し直下の本文は簡略形で足りる。）

### 事前解決済み判断
（本 phase は縮小要件対象のため、見出し直下の本文は簡略形で足りる。）

## 参照情報
- P06 (test-run)。
- 後続 P08 (refactoring)。
