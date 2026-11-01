---
name: flyer-studio
description: チラシを、一括ヒアリング→（既存紙面があれば）診断と提案評価→制作→別担当による新画像の評価→納品→知見の還元の順に進める入口の地図。印刷PDF・申込導線（QRか代わりの案内）・公開範囲まで完成させたいときに使う。
---

# Flyer Studio

この入口の地図の正本は plugin の `references/kit-entry.md` で、ローカルキットでは [build-local-package](../scripts/build-local-package.py) がリンクを plugin 直下からの相対に直して、plugin 直下の `SKILL.md` として書き出す。PLUGIN_ROOT（プラグインの置き場所）は plugin 直下（[plugin-composition.yaml](../plugin-composition.yaml) のあるフォルダ）。cwd や元の置き場所から推測しない。

skill はライフサイクル順（工程の順）に次の 6 つ。★ は利用者が `/flyer-studio:<skill名>` で直接呼べる入口（user-invocable）で、迷ったら run-intake-flyer から始める。

1. ★[run-intake-flyer](../skills/run-intake-flyer/SKILL.md) — 一括ヒアリングで目的と確定事実を受け取る。様式は写真・漫画・墨絵など自由に受け、言葉にならなければ回答と資料から読み取った案を出して、選ぶか任せるかを決めてもらう
2. ★[run-analyze-flyer](../skills/run-analyze-flyer/SKILL.md) — 既存紙面があるときだけ診断して提案を作る
3. [assign-flyer-analysis-evaluator](../skills/assign-flyer-analysis-evaluator/SKILL.md) — 提案を別の担当が評価する
4. ★[run-create-flyer](../skills/run-create-flyer/SKILL.md) — 制作・修正・納品（finalize）
5. [assign-flyer-evaluator](../skills/assign-flyer-evaluator/SKILL.md) — 評価対象の案（[評価コストの原則](review-rubric.md#評価コストの原則)）の新しい画像を別の担当が評価する
6. ★[run-learn-flyer](../skills/run-learn-flyer/SKILL.md) — 納品済みの案件から知見を還元する

★ の 4 つは、まず実際に使える成果物（ヒアリング要約と様式案・診断と改善案の下書き・1 案の下書き紙面・集計の要約案）を作って見せ、現状で試すか、軽微・標準・詳細のどの深さで改善するかを利用者が選んでから、選んだ深さで評価と改善を進める。下書きは納品物ではなく、別担当の評価を通っていない版は納品しない。

各 skill は [共通の判断手順](stage-common.md#共通の判断手順) を使い、担当固有の判断を既存の契約・指針・型へ結ぶ。intake の資料解釈と様式案、learn の集計解釈と改善仮説は呼び出された AI が担う。評価の 2 つには呼出元が同一版の成果と評価台帳を渡し、評価者は対象を修正しない。工程・FIX（修正指示）の戻り先・改善 cycle の正本は [workflow](workflow.md)、責務の境界と正本の地図は [architecture](architecture.md)、コマンドは [runtime](runtime.md)、部品の登録簿は [registry.json](registry.json)、素材は [素材一覧](../assets/index.html)。個人素材を含むため公開配布しない。
