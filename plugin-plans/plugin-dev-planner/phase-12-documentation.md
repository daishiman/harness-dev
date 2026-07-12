---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
task-graphだけでなく、13 phase/task spec/component route/TaskExecutionEnvelope/state projection/cycle knowledgeの棲み分けを利用者向けに確定する。

## 背景
本サイクルは既存プラグインの内部拡張であり、entry_points (skills/agents/commands) の追加・削除を伴わないため、install 手順自体への変更はない。ドキュメントは task-graph という新概念の説明に限定される。

## 前提条件
- P11 の evidence 設計が完了している。

## ドメイン知識
- Part1 (概念): 13 phase=学校全体の時間割/ルール、task spec=今日やる1枚の課題、task-graph=順番の地図、component route=専門の担当者、task-state=進捗帳、status projection=見える掲示板、knowledge=次回に使う要点メモ、と説明する。
- Part2 (技術): node.execution_kind/task_spec_ref→TaskExecutionEnvelope合成、phase_ref policy join、route_ref明示join、graph/state/projection分離、discovered-task外ループ、cycle lineage/knowledge_refsを説明する。
- 明確な回答: 1 nodeは13 phase文書を全部実行しない。titleもpromptではない。dispatcherが1 task specと該当phase policyを合成したenvelopeを実行する。
- 反映先: 新規スクリプト群の変更点は `references/task-graph-contract.md` (新規) へ集約し、既存 `references/phase-lifecycle.md`/`references/component-domain.md` への言及追記は最小限 (task-graph が第 3 の射影であることの 1 文相当) に留める。
- install 手順: entry_points 変更なしのため既存 README/setup 手順は不変。

### 責務の棲み分け
| 情報 | 正本 | 役割 | 更新タイミング |
|---|---|---|---|
| 13 phase policy | `phase-*.md` | 要件・設計・実装・検証など共通の進め方 | policy変更時 |
| task spec | `task-specs/<task-id>.md` | 1 nodeを追加質問なしで実行できる目的・入力・受入・検証 | plan作成/外ループ改善時 |
| task graph | `task-graph.json` | 現revisionのnode/edge/artifact/route構造 | task specsからrevision単位で再導出 |
| runtime state | `task-state.json` + `task-events.jsonl` | pending/running/done/blockedと監査履歴 | dispatcher単一writerが実行中更新 |
| status / execution report | `task-graph-status.json` + `task-progress.md` + `task-execution-report.html` | 機械観測 + 差分確認 + 図解付きの読みやすい実行記録 (成果物/証跡/外ループ/正本リンク) | graph+state+route reports+build-summaryから決定論再生成。最終summary保存後に再投影 |
| component route | inventory + handoff | buildable実体、builder、build_target、component依存 | component設計変更時 |
| cycle history | cycle directory + plan-ledger | 完了spec/graph/evidenceのimmutable provenanceとlineage | cycle終了/開始時 |
| reusable knowledge | knowledge record | source_ref付き要点、freshness、採用/不採用理由 | evidence確認後に蒸留 |

### MF決済インボイスチェックの再改善例
1. cycle Aを`finished`にし、仕様書・graph・evidenceをimmutable保存する。失敗回避知見「CSV列名は表示名でなくstable keyを使う」を`source_ref=cycle-A/evidence/...`付きで蒸留する。
2. 機能追加cycle Bは`predecessor_cycle_id=A`を持つが、Aの完了nodeやdone状態をactive graphへコピーしない。新しいtask specsから新graphを導出する。
3. Bの関連task envelopeには上記knowledge refだけを採用し、`freshness_checked_at`と採用理由を記録する。無関係なUI知見は`decision=rejected`+理由を残す。Aの成果物自体が必要ならpath+hashを`external_inputs`へ明示する。
4. 実行中に「新しい税区分fixtureが必要」と判明したらdiscovered-taskをemitする。現revisionを直接編集せず、外ループでtask specへ追記してcycle B revision 2を再導出し、未完了taskだけを新stateへ引き継ぐ。
5. 完了判定はtask-stateとevidenceで行い、graph構造や過去cycleのdoneを代理判定に使わない。

## 成果物
- `references/task-graph-contract.md` の設計方針 (node/edge 型・ready-set アルゴリズム・discovered-task 受理フロー・canonical 規約・handoff-notes 契約を集約する新規 reference)。

## スコープ外
- README/setup 手順の実編集 (entry_points 変更を伴わないため本 plan では不要)。

## 完了チェックリスト
- [ ] Part1/Part2 の 2 タスク雛形が task-graph という新概念に即して具体化されている。
- [ ] 反映先 (新規 reference ファイルの位置と役割) が明示されている。
- [ ] install 手順への影響有無 (無し) が明示されている。
- [ ] 13 phase/task spec/task graph/component/state/knowledgeの責務表と、MF決済インボイスチェックの再改善例がある。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: Part1 の説明文が「地図」という具体的比喩で task-graph の役割を説明し、Part2 が node/edge 型・ready-set・discovered-task・canonical・handoff-notes の 5 点を具体的に列挙する。
- 満たさない例: 「ドキュメントを更新する」とだけ記され、対象ファイルや説明内容が未確定である。

### 事前解決済み判断
- 分岐点: task-graph の説明を既存 `phase-lifecycle.md` 内に統合するか、新規 reference ファイルへ分離するか → 判断: 新規ファイル (`references/task-graph-contract.md`) へ分離 (task-graphはschema/renderer/validator/state/knowledgeの独立した検証可能契約群を持ち、既存ファイルへの追記のみでは規模に見合わないため)。

## 参照情報
- P11 (evidence)。
- 後続 P13 (release)。
