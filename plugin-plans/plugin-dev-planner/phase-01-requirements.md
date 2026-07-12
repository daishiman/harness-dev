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
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
既存task-graph計画を更新し、`goal-spec.json`のchecklistをC1-C19へ拡張する。特に13 phase共通policy・node task spec・component routeの関係、TaskExecutionEnvelope、task-graph/task-state/status projectionの三層分離、過去cycle lineage/knowledge再利用を要件レベルで固定する。

## 背景
現行実装には依存graph・state writer・ready-set・discovered-task・status projection・knowledge記録が存在する。しかしSubAgentへ渡す完全なtask contractが単一schemaで閉じず、title/phase_ref/entity_refから暗黙にpromptやbuilderを推測する余地がある。さらに、利用者はcanonical graphのstateを直接更新すると誤認しやすく、完了specと蒸留knowledgeの棲み分けもplan上で弱い。

## 前提条件
- 対象プラグイン `plugins/plugin-dev-planner/` は既に 2 skill (run-plugin-dev-plan, assign-plugin-plan-evaluator) を持つ既存プラグインであり、本 plan は `artifact_class: existing-plugin-update` として自己拡張を行う。
- 直前cycleの成果物と現行実装はread-only baselineとして参照する。本planのchecklist C1-C19は現在のtask-graph改善テーマであり、過去cycleの番号空間とはplan-ledger lineageで区別する。

## ドメイン知識
- goal-spec の checklist は19件 (C1-C19)。C17=task execution envelope、C18=状態三層分離、C19=cross-cycle lineage/knowledge reuseである。
- constraints の中核は「task-graph は第 3 の射影であり既存 2 軸の意味論を置換しない」「メタ循環の分離: 本 plan 自体は現行 shape (13 phase ファイル) で記述する」「canonicalizer が唯一の serializer」「blocks は depends_on の逆向き導出ビューで独立宣言禁止」「L4 実 build 実行は本 plan の責務外」の 5 点。
- handoff_targets: run-skill-create / run-build-skill / capability-build。max_loops: 5。

## 成果物
- `goal-spec.json` (確定済み・本 phase 時点で再読込による内容確認のみ行い、書き換えは行わない)。

## スコープ外
- component-inventory.json の分解 (P02 の責務)。
- task-graph の schema/導出/検証ロジックの詳細設計 (P04/P05 の責務)。

## 完了チェックリスト
- [ ] purpose/background/goal が task-graph 追加という改善要求の文脈で一貫している。
- [ ] checklist C1-C19 それぞれに verify_byが付与されている。
- [ ] 13 phaseは共通policy、node task specは実行契約、component routeはbuild写像という三層が区別されている。
- [ ] canonical graphを状態台帳として直接編集せず、task-stateとprojectionで進捗更新要求を満たす方針が固定されている。
- [ ] 完了cycleのimmutable artifactsと次cycleへ渡す蒸留knowledgeの棲み分けが固定されている。
- [ ] target_plugin_slug が `plugin-dev-planner` に固定され、plan_dir が `plugin-plans/plugin-dev-planner` に固定されている。
- [ ] constraints の 5 点 (2軸非置換/メタ循環分離/単一writer/blocks派生専用/L4責務外) が本 plan 全体の設計判断へ反映される前提が明示されている。
- [ ] goal-spec.json の background が現サイクル前提 (既存 task-graph 機構の存在) で purpose/goal・phase-01 背景と一貫している。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: goal-specがphase/task/component/state/knowledgeの責務を明示し、checklist 19件が独立したverify_byを持つ。
- 満たさない例: task-graph の目的が「グラフ機能を追加する」とだけ記され、既存 2 軸との関係 (置換か包含参照か) が未確定のまま P02 へ進む。

### 事前解決済み判断
- 分岐点: 本 plan 自体の出力形式を 13 phase ファイル固定にするか、C10 が要求する可変 shape で書くか → 判断: 13 phase ファイル固定 (constraints のメタ循環分離規約により、本 plan は現行 skill・現行ゲートで生成/検証されるため現行 shape を採る。C10 は将来の plan が可変 shape を使える機能要件であり、本 plan 自身の記述形式ではない)。

## 参照情報
- `plugin-plans/plugin-dev-planner/goal-spec.json`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/phase-lifecycle.md` §7/§8。
- 後続 P02 (design)。
