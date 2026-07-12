<!--
正本: system-dev-planner (生成器) 側の 13 phase 文書テンプレート。
`plugin-plans/dev-graph/templates/system-phase-spec.md` (draft) は現状独立ファイルであり、
P08/P12 で本正本への pointer 化予定。節構成は draft と整合する非後退の骨子とし、
phase 呼称は `references/system-plan-phase-names.md` (sdp 確定表) を正本とする。
-->

# P<NN> — <phase name>

## 目的

<このlifecycle phase完了時に成立するシステム計画状態>

## 背景

<system-spec/architectureの根拠ノードとユーザー価値>

## 前提条件

- Required phase/task nodes: <graph_node_id>
- Entry gate: <machine-verifiable condition>
- Applicability: <applicable | N/A: reason>

## システム設計知識

- 9 workstreamの該当判断: <workstream applicability matrix>
- Architecture decisions: <graph_node_id>

## 成果物

- Produced phase artifacts: <paths and graph nodes>
- Consumed artifacts: <paths and graph nodes>

## スコープ外

- <explicit non-goal>

## 完了チェックリスト

- [ ] <binary, observable phase criterion>

### 受入例

- 満たす例: <positive example>
- 満たさない例: <negative example>

### 事前解決済み判断

- <decision and rationale>

## 参照情報

- System specification: <system-spec-harness output node>
- Architecture: <system-spec-harness output node>
- Typed tasks: <task graph nodes>
