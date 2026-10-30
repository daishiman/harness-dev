---
name: assign-flyer-analysis-evaluator
description: 元画像と改善提案を独立評価したいとき、修正された提案を制作前に再確認したいときに使う。
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
  - agents/analysis-evaluator.md
schema_refs:
  - ../../schemas/analysis-review.schema.json
reference_refs:
  - references/evaluation-contract.md
  - ../../references/stage-common.md
  - ../../references/design-knowledge-index.json
---

# 分析と改善案を別の担当が検証する

実行担当は[stage agent](agents/analysis-evaluator.md)、判断の基準は[stage contract](references/evaluation-contract.md)。PLUGIN_ROOT・実行形式・記録・戻り先・本質アンカー・知識の読み方・独立性は[stage-common](../../references/stage-common.md)に必ず従う。

## Purpose & Output Contract（目標と入出力）

提案者の説明を追認せず、現物と要望に照らして実施してよい改善案か独立判断する。

- 入力: 分析対象の元画像、最新要求と制約、同じ版のanalysis.json、診断者ID、run-analyze-flyer が生成した analysis-review.json の評価テンプレート。
- 出力: 分析/元画像/規範のhashと別担当IDに対応するanalysis-review.json。PASS/FIXと根拠、必須修正、戻り先を返す。

## ゴールシーク実行

未達の判定項目から次の行動を選ぶ。進め方は [共通の判断手順](../../references/stage-common.md#共通の判断手順)。この担当では最初に元画像を実見し、提案の観察・保持点・採否理由と照合して、制作へ渡してよいかを判断する。候補の作り直しは診断担当へ返す。

## Gotchas（完了判定と戻り）

evidenceAlignment/completeness/changeDiscipline/feasibilityが具体根拠付きPASS、必須修正0、診断者と別担当、同一元画像/分析/規範hashでanalysis-review-validateが通る。これは完成画像PASSではない。

FIX は[診断担当](../run-analyze-flyer/SKILL.md)へ、PASS は呼出側へ返す。制作への進行は [workflow](../../references/workflow.md#stage-ごとの要点) の実行範囲に従い、評価者が制作を起動しない。PASSにしない提案の例は stage contract の「未達診断と戻り」。

## 実行への接続

テンプレートの生成・再発行は呼出元の run-analyze-flyer が行う。評価担当は生成済み台帳を記入し、PLUGIN_ROOT で読取検査だけを実行する。FIX の記録や退避は次の呼出側処理へ渡す。

```text
python3 scripts/build-flyer.py analysis-review-validate --project <DIR>
```
