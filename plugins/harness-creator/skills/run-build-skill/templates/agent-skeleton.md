---
name: {{CAPABILITY_NAME}}
description: {{TRIGGERS}}
kind: agent
version: 0.1.0
owner: {{OWNER}}
since: {{DATE}}
tools: {{TOOLS_JSON}}
model: {{MODEL}}
isolation: {{ISOLATION}}
phase: {{PHASE}}
fan-out: {{FAN_OUT}}
contract:
  intent: {{PURPOSE}}
  interface:
    input: {{INPUT_SCHEMA_REF}}
    output: {{OUTPUT_SCHEMA_REF}}
  invariant:
    - 親 orchestrator の context を fork した時点の値のみ参照する
    - 出力は Output Contract で宣言した JSON 形のみを返す
    - 評価系 agent は generator の思考過程を読まない (sycophancy 防止)
rubric_refs: []
responsibility_refs: []
---

# {{CAPABILITY_NAME}}

## Layer 1: 基本定義層

{{PURPOSE}}

{{OUTPUT_CONTRACT}}

## Layer 2: ドメイン定義層

{{ROLE_POLICY}}

## Layer 3: インフラストラクチャ定義層

親から入力・解決済み絶対パス・出力契約を受け取る。元スキルの操作制約:

{{OPERATION_CONSTRAINTS}}

## Layer 4: 共通ポリシー層

{{ROLE_POLICY}}

## Layer 5: エージェント定義層

### 5.1 担当エージェント

{{CAPABILITY_NAME}} ({{AGENT_ROLE}})

### 5.2 ゴール定義

目的: 上記の目的と出力契約を満たす。背景: 親が独立した役割として委譲した作業を実行する。

達成ゴール: 親が要求した出力が、目的と出力契約を満たし、根拠をたどれる状態になっている。

### 5.3 完了チェックリスト

- [ ] 必須入力とパスの出所を確かめた。
- [ ] 出力が上の目的と出力契約を満たす。
- [ ] 役割の許可範囲を守り、検証の成否と根拠を親へ返せる。

### 5.4 実行方式

目的と完了チェックリストを読み、未達を解消する方法を状況に応じて決める。実行後に検証し、original_goal（不変）/ current_goal_snapshot / delta_from_original / merged_directive_for_next / drift_signal を親へ返す。親の反復上限に達した場合は残る未達と根拠を返す。

## Layer 6: オーケストレーション層

親が指定した依存順序と停止条件に従い、最終出力・検証結果・未達だけを返す。

## Layer 7: ユーザーインタラクション層

ユーザーへの対話と保存許可は親が担当する。

## プロンプトの型

(対話なし: 自動実行 agent) — 親が入力・役割・出力契約を渡す。

## 自己採点

検証可能性と簡潔性を上の完了チェックリストで確かめ、未達は親へ返す。
