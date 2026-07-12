---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的
スクショに代わる機械 evidence 5 要素 (lint exit0 ログ / schema parity / build-trace coverage / content-review verdict / coverage JSON) と、それらを読みやすく図解する自己完結 `task-execution-report.html` が build 後に観測可能であることを本 plan の設計として確定する。

## 背景
UBM 由来の必須スクリーンショット提出は DROP され、本プラグインでは決定論ゲートの実行ログとカバレッジ JSON が evidence として機能する (`phase-lifecycle.md` §7 REPLACE 規約)。ただし人間の閲覧性は捨てず、consumer TG-C09 が同じ状態/証跡からHTMLを決定論生成し、slide-report-generator の `validate-report-visual.py --strict` とブラウザ利用可能時の実表示確認を視覚ゲートにする。task-graph 関連の新規ゲート (derive-task-graph.py/validate-task-graph.py/compute-ready-set.py/accept-discovered-task.py/apply-handoff-notes.py) の実行ログもこの 5 要素へ合流する。

## 前提条件
- P10 の final-review が PASS している。

## ドメイン知識
- lint exit0 ログ: p0_lint 8 本 + 新規/拡張ゲート (validate-task-graph.py 等) の実行ログ。
- schema parity: schemas/task-graph.schema.json/discovered-task.schema.json/handoff-notes.schema.json と実装コードの key 一致検証。
- build-trace coverage: build_trace:required に基づく build 実行トレース。
- content-review verdict: PASS + sha_match。
- coverage JSON: `eval-log/coverage/skills/plugin-dev-planner__run-plugin-dev-plan.json` / `eval-log/coverage/skills/plugin-dev-planner__assign-plugin-plan-evaluator.json` 相当。
- **C01 dogfooding 受入例 (自己適用・6 番目の evidence)**: build 後に C01 が生成した `derive-task-graph.py` を本 plan 自身 (`plugin-plans/plugin-dev-planner/`) へ適用し、13 phase の `## 完了チェックリスト` 項目から `task-graph.json` を導出、`compute-ready-set.py` で ready-set を算出して task 粒度の部分進捗 (どの task が done/ready/blocked か) を実証する。C01 は最粗粒度 route (skill 全体) であり route 粒度では自己 route 分割の対象にならない (自己不適用) が、task 粒度では derive→ready-set→部分進捗の自己適用が可能であり、これを evidence として観測する (C01 が生成する機構が自 plan にも機能することの dogfooding・構造分割はしない=ユーザー選択に整合)。
- **C17 evidence**: 代表leaf nodeのTaskExecutionEnvelope、execution_kind/task_spec_ref/route_ref parity、title-only/entity_ref暗黙route/全13phase注入拒否ログ。
- **C18 evidence**: state遷移前後の同一revision graph hash一致、task-state/task-events差分、status projection parity、discovered-task採用時の旧revision不変+新revision/hash発行ログ。加えて `task-execution-report.html` の同一入力byte一致、HTML escape、外部runtime不在、inline SVG/印刷CSS、route evidence/build-summary反映、slide-report-generator strict visual gate PASSを記録する。
- **C19 evidence**: predecessor cycle lineage、採用/不採用knowledge refs、active graphへの旧node混入0件。

## 成果物
- evidence 5 要素の観測可能性設計 (build 後に実際のログ/JSON として生成される前提の宣言)。

## スコープ外
- 実測 evidence の生成 (build 後・本 plan の対象外)。

## 完了チェックリスト
- [ ] evidence 5 要素それぞれが本 plan のどのゲート/成果物に対応するか明示されている。
- [ ] task-graph 関連の新規ゲートの実行ログが lint exit0 ログへ合流することが明示されている。
- [ ] C01 の dogfooding 受入例 (build 後に自 plan へ derive-task-graph→compute-ready-set を適用し task 粒度の部分進捗を実証) が evidence として明示されている。
- [ ] C17-C19のexecution envelope/state projection/cycle knowledge evidenceが明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 5 要素それぞれに対応する具体的なゲート名/JSON パスが列挙され、同じ証跡を構造化した `task-execution-report.html` が strict visual gate をPASSしている。
- 満たさない例: 「テストを実行してスクショを撮る」のように DROP 済みの UBM 固有要素が残存する。

### 事前解決済み判断
- 分岐点: task-graph 関連ゲートの evidence を新規の 6 番目の要素として追加するか、既存 5 要素の「lint exit0 ログ」へ合流させるか → 判断: 合流 (evidence 定義の単一 SSOT (`phase-lifecycle.md` §7 REPLACE 規約 + `io-contract.md` §10) を変更せず、新規ゲートも決定論 script の exit0 判定という同一性質を持つため)。

## 参照情報
- P10 (final-review)。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/phase-lifecycle.md` §7。
- 後続 P12 (documentation)。
