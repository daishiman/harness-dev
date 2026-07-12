---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
C01/C02 の `harness_coverage` (min≥80・kind_pass) を設計として確定し、build 後に実測される達成率の数値は本 phase では焼き込まず「≥80% を満たす設計」の要件化に留める (Goodhart 回避)。

## 背景
harness-coverage は mechanical/llm_eval の対で測定する。C01はIN1-IN16/OUT1-OUT3、C02はtask envelopeとknowledge relevanceを含むgenuine verdictを網羅する。

## 前提条件
- P05 の実装設計が確定している。

## ドメイン知識
- 新規 pytest ファイル (P05 の設計に対応): `test_derive_task_graph.py` (C2/C11 canonicalize 再現性)・`test_validate_task_graph.py` (C1/C2/C3/C11 の 6 検査項目。C1=`task-graph.schema.json` による node identity/phase_ref/entity_ref/write_scope/acceptance と edge 4 型の機械検証を担う)・`test_compute_ready_set.py` (C4 の 4 ケース、P04 の受入例テーブルをフィクスチャとして使用)・`test_accept_discovered_task.py` (C5 の additive/structural 二段受理)・`test_apply_handoff_notes.py` (C12 の件数/文字数上限・有界伝播)・`test_task_graph_backward_compat.py` (C7: task-graph.json 不在時に既存ゲート全 exit0)・`test_check_plan_ledger.py` (C13: active 重複 fail-closed 検出・status enum 値域・cycle_id 形式 (`CYCLE_ID_RE`) 検証)・`test_migrate_plan_layout.py` (C13: 既存 flat 配置 → cycle-id 配置への移行・`plugin-plans/finish/` 配下は台帳への `status: finished` 登録のみで物理移動しないことの確認)・`test_check_shape_non_regression.py` (C14: (a) 二値受入基準携帯率が旧shape基準線を下回らないことの計測・(c) task-graph byte 一致 + 仕様書構成一致の再現性検証。P04 の A/B fixture (旧shape/新shape) をそのままフィクスチャとして使用)・`test_render_task_graph_mermaid.py` (C15: 同一graphからの2回連続renderがbyte一致すること・出力mermaidのnode id集合が入力graphのnode id集合とset一致すること (graph外要素非描画) をP04のT1-T4フィクスチャで検証)・`test_check_task_state_schema.py` (C16: task-state.schema.json整合 (running状態のlease必須) + graph_hash pin不一致のfail-closed検出をP04のfixtureで検証)。
- 追加pytest: `test_render_task_execution_envelope.py` (C17)、`test_project_task_status.py` (C18)、`test_check_cycle_knowledge.py` (C19)。
- 既存 pytest への追加: `check-build-handoff.py` の `_check_task_graph_ref` (C6=handoff の `task_graph_ref` 参照整合)・`verify-index-topsort.py` の `_shape_marker` (C10=新旧 shape の機械判別) のデフォルト引数ケース (未設定時に検査スキップ・既定値フォールバック) を既存テストファイルへ追加する。この 2 件は新規 pytest ファイルではなく既存ファイルへの追記ゆえ「既存11本+追加3本」の内数ではなく、C6/C10 の pytest 担体を別途構成する。
- 現状の plugin-dev-planner 全体テスト件数 (既存 388+ 件、`test_gate_parity.py` の 9 parity アサーション) からの退行が 0 であることを OUT1 として設計する。
- 被覆担体対応 (C1-C19 × 担体) — 本 phase の被覆正本。§5 完了チェックリストの「既存11本+追加3本がC1-C19を被覆する」は pytest 担体の集約表現であり、pytest で機械検証できない C8・C9・C14(b) は下記の非 pytest 担体 (決定論ゲート網 / evaluator) が被覆する。担体は 4 種 (pytest 単体 / pytest 既存拡張 / 決定論ゲート網 / evaluator)、各 criteria に `verify_by` (script=機械検証 / human=genuine 判定) を付す。

  | criteria | 担体 | 検証手段 | verify_by |
  |---|---|---|---|
  | C1 | pytest 単体 | `test_validate_task_graph.py` (`task-graph.schema.json` の node identity/edge 4 型検証) | script |
  | C2 | pytest 単体 | `test_derive_task_graph.py` / `test_validate_task_graph.py` | script |
  | C3 | pytest 単体 | `test_validate_task_graph.py` (consumes 参照先 producer 実在) | script |
  | C4 | pytest 単体 | `test_compute_ready_set.py` | script |
  | C5 | pytest 単体 | `test_accept_discovered_task.py` | script |
  | C6 | pytest 既存拡張 | `check-build-handoff.py` の `_check_task_graph_ref` ケース | script |
  | C7 | pytest 単体 | `test_task_graph_backward_compat.py` | script |
  | C8 | evaluator | C02 (`assign-plugin-plan-evaluator`) fork evaluator の genuine 判定 (タスク細分化粒度の着手可能性・エッジ4型意味論の誤用有無を `plan-findings.json` で判定) | human |
  | C9 | 決定論ゲート網 | 同梱決定論ゲート core5/6invocations + 拡張6本の全 exit0 | script |
  | C10 | pytest 既存拡張 | `verify-index-topsort.py` の `_shape_marker` ケース | script |
  | C11 | pytest 単体 | `test_derive_task_graph.py` / `test_validate_task_graph.py` (canonical byte 一致 + 非正準拒否) | script |
  | C12 | pytest 単体 | `test_apply_handoff_notes.py` | script |
  | C13 | pytest 単体 | `test_check_plan_ledger.py` / `test_migrate_plan_layout.py` | script |
  | C14(a),(c) | pytest 単体 | `test_check_shape_non_regression.py` (精度携帯率 + byte/構成再現性) | script |
  | C14(b) | evaluator | C02 の A/B比較 genuine 判定 (旧shape/新shape の下流ハーネス実効性の劣化なし判定) | human |
  | C15 | pytest 単体 | `test_render_task_graph_mermaid.py` | script |
  | C16 | pytest 単体 | `test_check_task_state_schema.py` | script |
  | C17 | pytest 単体 | `test_render_task_execution_envelope.py` | script |
  | C18 | pytest 単体 | `test_project_task_status.py` | script |
  | C19 | pytest 単体 | `test_check_cycle_knowledge.py` | script |

  この対応表により C8/C9/C14(b) の非 pytest 被覆が本文に明示され、§5 checklist 項目文言を変えずに被覆の正本を確立する (checklist は pytest 層の集約射影、本表が層構造の正本)。

## 成果物
- C01/C02 の `harness_coverage` ブロック (component-inventory.json に反映済み・min:80)。

## スコープ外
- 実測カバレッジ数値の記録 (build 後の実測作業・本 plan の対象外)。

## 完了チェックリスト
- [ ] C01/C02 双方の harness_coverage.min が 80 以上に設計されている。
- [ ] kind_pass が component の kind (run/assign) に整合する型で記述されている。
- [ ] 既存11本+追加3本がC1-C19を被覆する。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: `test_compute_ready_set.py` が P04 の 4 ケーステーブルをそのままフィクスチャとして使用する設計になっている。
- 満たさない例: 「テストを追加する」とだけ記され、対象ファイル名・検証観点が未確定である。

### 事前解決済み判断
- 分岐点: harness_coverage.min に現状の実測値 (未計測) を仮に記載するか → 判断: 記載しない (constraints: harness 現状未達数値は component へ焼かない。「≥80% を満たす設計」の要件化に留める)。

## 参照情報
- P05 (implementation)。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/test_gate_parity.py`。
- 後続 P07 (acceptance-criteria)。
