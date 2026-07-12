# 目的

<この機能がなぜ必要か (JTBD/価値)>

## 到達状態

<この機能が達成する到達状態 (goal)。旧 目標+ゴールの語彙はここへ一本化する>

## スコープ

- スコープ内: <scope_in 項目>
- スコープ外: <scope_out 項目>

## 受入

- [ ] <acceptance: 確実に実行したい観測可能な二値条件>

## アーキテクチャ参照

- `architecture_refs`: <参照する architecture ノードの graph_node_id>

## 機能間依存

- `depends_on`: <依存する feature ノードの graph_node_id>
- 依存理由: <なぜこの順序/前提が必要か>

## Handoff

- per-feature planning: <ready 時に system-dev-planner (run-system-dev-plan) を自動起動、または人間の手動 `/system-dev-plan` 実行結果を同じ登録経路として受理>
- 生成物の登録先: <system-dev-planner が生成した promoted task を `parent_feature=<この graph_node_id>` で C02 経由 atomic 登録>
