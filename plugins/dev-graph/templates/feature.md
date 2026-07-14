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
- 生成物: <P01..P13 exact 13 executable task specs + 13-node intra-feature DAG>
- 登録先: <全taskを同一`parent_feature`/`feature_package_id`でC02経由atomic登録。expected/applied=13必須>
- 完了rollup: <exact 13全done + P07/P10/P11 evidenceがfeature acceptanceを満たす場合だけdone>

