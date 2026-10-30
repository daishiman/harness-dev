---
name: assign-flyer-evaluator
description: 最新の完成画像や修正後の画像を独立評価したいとき、pilot案から残りの案へ進めてよいか確認したいときに使う。
kind: assign
prefix: assign
owner: harness maintainers
version: 1.3.0
effect: local-artifact
role_suffix: evaluator
user-invocable: false
context: fork
manifest: workflow-manifest.json
responsibility_refs:
  - agents/visual-review-coordinator.md
  - ../../prompts/visual-review.md
schema_refs:
  - ../../schemas/visual-review.schema.json
reference_refs:
  - references/review-contract.md
  - ../../references/stage-common.md
  - ../../references/review-rubric.md
  - ../../references/design-knowledge-index.json
---

# 新しい完成画像を案ごとに独立評価する

実行担当は[stage agent](agents/visual-review-coordinator.md)、手順・評価の量・統合・合否は[stage contract](references/review-contract.md)。PLUGIN_ROOT・記録・戻り先・本質アンカー・知識の読み方・独立性は[stage-common](../../references/stage-common.md)に必ず従う。

## Purpose & Output Contract（目標と入出力）

制作者の説明より先に実画像を観察し、主従・対象認知・均衡・余白・色・写真統合と要望成立を別担当の根拠で確かめる。

- 入力: 評価対象の案（[評価コストの原則](../../references/review-rubric.md#評価コストの原則)）の新PDF由来PNG、render/checksと入力/規範hash、brief/concepts/assets/scene、適用要求と採否、run-create-flyer が生成した評価テンプレート。
- 出力: 新PNG SHAへ対応したvisual-review.jsonのcriteria/expertReviews/要求別充足/mandatoryFixes/preferenceNotesとPASS/FIX。先行試作ではpilot案だけを同じ型でpilot-review.jsonへ返す。

## ゴールシーク実行

未達の判定項目から次の行動を選ぶ。進め方は [共通の判断手順](../../references/stage-common.md#共通の判断手順)、見る順序は [review-rubric](../../references/review-rubric.md#見る順序) に従う。この担当では、意図を読む前の初見と読んだ後の照合を分け、実際の画像領域を根拠に 5 観点と要求の充足を判定する。評価対象と専門レンズは stage contract の「評価の量」で決める。

## Gotchas（完了判定と戻り）

合否は stage contract の「合否と戻り」で決める。PASSは呼出元の[制作担当](../run-create-flyer/SKILL.md)へ返し、finalize は制作担当が行う。FIX は fixClass で決まる戻り先へ返す。

## 実行への接続

この stage はコマンドを実行しない。評価テンプレート（pilot-review.json・visual-review.json の雛形）の生成と finalize は run-create-flyer が行い、評価担当は記入だけを行う。
