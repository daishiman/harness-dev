# Prompt: R2b-readiness

> C11の純粋validation report、C02保存済みimplementation_readiness/evaluation_status/source digest、validate-system-plan.pyのP01..P13 exact-set/13-node DAGを照合し、不一致またはincomplete/pending/fail/staleならmissing sectionsをsurfaceしてhandoffを保留する

## Layer 1: 基本定義層

- `responsibility_id`: `R2b-readiness`
- `skill`: `run-dev-graph-requirements`
- responsibility summary: C11の純粋validation reportとC02が保存したimplementation_readiness/evaluation_statusを照合し、不一致またはincomplete/pending/fail/staleならmissing sectionsをsurfaceしてhandoffを保留する
- 不変目的: C11の純粋validation report、C02保存済みimplementation_readiness/evaluation_status/source digest、validate-system-plan.pyのP01..P13 exact-set/13-node DAGを照合し、不一致またはincomplete/pending/fail/staleならmissing sectionsをsurfaceしてhandoffを保留する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- C11 report、C02保存readiness/evaluation、source digest。

### 出力契約

- ready/blocked/stale verdictとnode/section別missing_sections。

### 責務境界

- statusを更新せず不一致を隠さずincomplete/pending/fail/staleをreadyにしない。

### 受入条件

- C11 reportとC02 saved state/source digestが一致し、validate-system-plan.pyのP01..P13 exact-set/13-node DAGがPASSしたcomplete/pass/confirmedだけreadyになる。

## Layer 3: インフラ層

- 使用資産: validate-graph-schemaとvalidate-system-plan。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-requirements/R2b-readiness`

### 5.2 ゴール定義

- 目的: C11の純粋validation report、C02保存済みimplementation_readiness/evaluation_status/source digest、validate-system-plan.pyのP01..P13 exact-set/13-node DAGを照合し、不一致またはincomplete/pending/fail/staleならmissing sectionsをsurfaceしてhandoffを保留する
- 達成ゴール: ready/blocked/stale verdictとnode/section別missing_sectionsが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] C11 reportとC02 saved state/source digestが一致し、validate-system-plan.pyのP01..P13 exact-set/13-node DAGがPASSしたcomplete/pass/confirmedだけreadyになる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- PASSのみR3、FAILは不足一覧へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
