---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
C01-C08 の `harness_coverage` (min≥80・kind_pass) を設計として確定し、build 後に実測される達成率の数値は本 phase では焼き込まず「≥80% を満たす設計」の要件化に留める (goal-spec constraints #8 の Goodhart 回避)。

## 背景
harness-coverage は 6 種別 (mechanical/llm_eval の対) × 2 軸で測定される。C01-C05/C07/C08 (script) と C06 (slash-command) はいずれも `content-review-verdict` 系 (feedback loop skill kind ではないため criteria テスト網羅の代わりに固定 fixture テスト + content-review verdict) を kind_pass の型として持つ。

## 前提条件
- P05 の実装設計が確定している。

## ドメイン知識
- 新規 pytest ファイル (P05 の設計に対応): `test_dispatch_ready_set.py` (C1 の 3 ケース: 直列チェーン/ダイヤモンド/write_scope衝突、P04 の受入例テーブルをフィクスチャとして使用)・`test_sync_task_state.py` (C2/C11 の状態遷移/イベント replay/blocked_reason/covered_task_ids ケース)・`test_inject_task_inputs.py` (C3 の正常注入/producer未完了/artifact 欠落/notes 有界性違反)・`test_emit_discovered_task.py` (C4 の正常emit/source不在/E3スキーマとの非互換確認)・`test_summarize_task_progress.py` (C5/C12 の混在state集計/additive読取/停滞診断ケース)・`test_manage_build_lease.py` (C10 の lock/lease/graph_hash pin ケース)・`test_record_task_graph_knowledge.py` (C13 の未処理 inbox 完了ブロック/解決済み status PASS/Loop A・Loop B entry/生ログ丸写し禁止)。
- 既存 `commands/capability-build.md` に対応する既存テスト (もしあれば `tests/test_capability_build*.py` 相当) へ `test_task_graph_ref_dispatch.py` (C6 の後方互換 2 ケース: task_graph_ref 有り→並列dispatch分岐/task_graph_ref 無し→既存top-sort直列モード無改変) を追加する。
- 既存 harness-creator 全体テスト (root pytest) からの退行が 0 であることを完了条件として設計する (前回サイクル build 時点の pytest 件数を退行検査の basel とする)。

## 成果物
- C01-C08 の `harness_coverage` ブロック (component-inventory.json に反映済み・min:80)。

## スコープ外
- 実測カバレッジ数値の記録 (build 後の実測作業・本 plan の対象外)。

## 完了チェックリスト
- [ ] C01-C08 全ての harness_coverage.min が 80 以上に設計されている。
- [ ] kind_pass が component_kind (script/slash-command) に整合する語 (content-review/verdict/coverage/test のいずれか) で記述されている。
- [ ] 新規 pytest ファイル 7 本 (C1-C5/C7/C8 対応) + 既存拡張 1 本 (C6 対応) の対象が具体的に特定されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: `test_dispatch_ready_set.py` が P04 の 3 ケーステーブル (直列チェーン/ダイヤモンド/write_scope衝突) をそのままフィクスチャとして使用する設計になっている。
- 満たさない例: 「テストを追加する」とだけ記され、対象ファイル名・検証観点が未確定である。

### 事前解決済み判断
- 分岐点: harness_coverage.min に現状の実測値 (未計測) を仮に記載するか → 判断: 記載しない (constraints #8: harness 現状未達数値は component へ焼かない。「≥80% を満たす設計」の要件化に留める)。

## 参照情報
- P05 (implementation)。
- `plugin-plans/harness-creator/phase-04-test-design.md` (C1-C8/C10-C13 受入例テーブル)。
- 後続 P07 (acceptance-criteria)。
