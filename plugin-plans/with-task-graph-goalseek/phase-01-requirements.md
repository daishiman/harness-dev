---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: 
---

# P01 — requirements (要件)

## 目的
with-goal-seek の engine 変種 `engine: task-graph` の要件を確定し、goal-spec.json checklist C1-C12 を本 plan の構造的到達基準として固定する。

## 背景
現状の生成物 goal-seek (with-goal-seek) は Goal+二値checklist の逐次反復のみで、タスク間の依存順序も実行中の新タスク発見(self-reflect)も持たない。ユーザーが求めるのは、生成された 1 ハーネスが実行中に新タスク/課題を見つけたら自分のタスク集合へ反映し、依存充足順(最適手順)で最終ゴールまで自己完結ループする能力である。A2 設計原則(goal-spec background 逐語)は【単一truth】: 別状態ファイル(task-graph.json)を新設せず、with-goal-seek の既存状態(progress.json の checklist + intermediate.jsonl アンカー)を唯一の真実源とし、(1) checklist item へ依存順序 depends_on を additive 付与、(2) self-reflect = 実行中に発見した新タスクを『新しい checklist item』として追記する(単一truthゆえ discovered task が自動的に完了判定を gate し、未処理のまま done にならない)、(3) 依存充足順の ready 集合を checklist から算出し逐次実行する。既存 build-pipeline (`plugin-plans/harness-creator/`) の compute-ready-set が同一 write_scope 候補を tie-break するのは『バグ』ではなく複数 dispatcher 並列前提の意図的 fail-closed(勝者以外を deferred/conflicts として返し上位が直列化する契約)であり、逐次単一 self-writer の本機構では並列書込 race が構造的に発生しないため write_scope 並列衝突機構自体を持ち込まない(死機構を複製しない)。独立 combinator を新設せず with-goal-seek の engine 変種として畳むことで、default/opt-in 軸・状態二重化・reconciliation 欠落を構造的に排除する。

## 前提条件
- `goal-spec.json` (本 plan_dir 直下) が確定済みで checklist C1-C12 / constraints 5 件を保持する。
- 参照実装として `plugins/harness-creator/skills/run-build-skill/` の既存 combinator 機構(with-goal-seek 等、`render-combinators.py`)が実在し編集可能である。
- `plugin-plans/harness-creator/` (既存 build-pipeline task-graph consumer 側計画) が既に build 済みで、その producer/consumer writer 分離パターンが対比先として参照できる。

## ドメイン知識
用語集本体は index.md ## ドメイン知識 を参照(engine 変種 / depends_on / ready 集合 / self-reflect append / 単一truth / consumption verifier 等)。本 phase 固有の追加事項: 「既存 build-pipeline task-graph」(`plugin-plans/harness-creator/` の producer=plugin-dev-planner / consumer=capability-build 機構)と「本 plan の with-goal-seek engine:task-graph 変種」は名称が似るが別概念であり、本 plan 全体を通じて後者のみを対象とする(goal-spec constraints #2、本 index 受入確認で再宣言する)。

## 成果物
- 確定した checklist C1-C12 の充足基準(本 index.md 完了チェックリスト/受入確認への転記)。
- with-goal-seek への統合方式(独立 combinator flag を新設せず engine 変種として畳む)が Phase02 で機構詳細まで確定するための判断材料。
- 単一truth原則(別状態ファイル非新設・checklist+intermediate.jsonl のみを状態源とする)が Phase02 で機構詳細まで確定するための判断材料。
- build 実体そのものは component-inventory.json が SSOT であり本 phase では確定しない。

## スコープ外
- component の分解・quality_gates/harness_coverage の値決定 → Phase02(設計)へ委譲する。
- 既存 build-pipeline task-graph(`plugin-plans/harness-creator/`)の要件見直し → 対象外(goal-spec constraints #2/#3)。

## 完了チェックリスト
- [ ] goal-spec.json checklist C1-C12 が本 index.md 完了チェックリスト/受入確認に転記されている
- [ ] 単一truth原則・engine 変種としての畳み込み方針が Phase02 への設計委譲事項として明示されている
- [ ] 既存 build-pipeline task-graph との非改変境界(constraints #2)が本 phase 内で再確認されている

### 受入例 (満たす例 / 満たさない例)
- 満たす例: goal-spec checklist C1-C12 の 12 項目が index.md の完了チェックリスト/受入確認へ 1 対 1 で転記され、既存 build-pipeline task-graph(`plugin-plans/harness-creator/`)への非改変境界が constraints #2 逐語で本 phase 内に再掲されている。
- 満たさない例: 「概ね goal-spec に沿う」とだけ記述し C1-C12 個別の転記先(index.md の節・行)が示されないまま Phase02 の設計へ進む。

### 事前解決済み判断
- 分岐点: 計画名に「task-graph」が含まれるため、生成ハーネス側にも task-graph.json 相当の別状態ファイルを新設すべきという誤読が生じうる → 判断: goal-spec background 逐語の【単一truth】原則により生成ハーネス内部(with-goal-seek engine:task-graph 変種)は別状態ファイルを新設しない。一方 `<PLAN_DIR>/task-graph.json`(本 plan 自身の 13 phase §5 完了チェックリスト + component-inventory から `derive-task-graph.py` が決定論導出する build-dispatch メタ成果物)は plan の handoff メタ契約層であり、生成ハーネスの内部設計原則とは別レイヤであることを Phase01 時点で明確化し混同を回避する。

## 参照情報
- `goal-spec.json`(本 plan_dir)
- `plugin-plans/harness-creator/index.md`(既存 build-pipeline task-graph 計画・対比先)
- `plugins/harness-creator/skills/run-build-skill/SKILL.md`(既存 combinator 機構)
