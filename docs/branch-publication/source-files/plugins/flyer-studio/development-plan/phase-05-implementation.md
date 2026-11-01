---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C04, C06, C08]
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P05 — implementation

## 目的
制作と独立評価の各実体を構築する。

## 背景
画像に文字まで焼き込む方式では住所訂正や中央軸調整が再現できない。C01は背景生成と決定論の文字・QR・ロゴ合成を分離する。既存紙面の改善では、長所を失う修正を防ぐため、C04/C06が現物診断と採否理由を先に作り、C08は独立評価済みの提案か決定論検査の失敗項目だけを根拠に制作する。

## 前提条件
P04の異常条件、schemas(brief/assets/concepts/scene/analysis/analysis-review/visual-review/design-intent)、package-lock.json固定依存、P02のC02/C05呼出契約とC12入口設計がある。

## ドメイン知識
ホストの画像生成ツール実呼出とprompts保存は別工程。whiteは外周純白、photoはfade、QRはquiet zoneを保つ独立レイヤーとする。

## 成果物
C01: skills/run-create-flyer/(SKILL.md・workflow-manifest.json・references/production-contract.md)、素材catalog。C08: skills/run-create-flyer/agents/flyer-producer.md。C04: skills/run-analyze-flyer/(SKILL.md・workflow-manifest.json・references/analysis-contract.md)。C06: skills/run-analyze-flyer/agents/artifact-analyst.md。描画backend(project/render/checks/analysis.cjs ほか)はC12の背後に置き、各skillから直接node起動しない。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] C01のinit→import→prompts→validate→render→verify→review-template→finalizeがscripts/flyer.pyから実行でき、projectのbrief/assets/concepts/sceneとoutのHTML/PDF/PNGを生成する。
- [ ] C01がC1/C2/C5の確認をbriefへ保存し、C3/C4/C7の文字・外周・写真条件とC8/C9の鮮度/個別目視gateをfail closedで実装する。
- [ ] C01が背景のgenerated/reuse-approvedの由来、実際のtool/prompt/出力SHAを保持し、ホスト生成ツールが無い時は接続か明示再利用を確認する。
- [ ] C04がanalysis-template→全元画像の実見→analysis-seal→analysis-validate→C05呼出の順で進み、領域付き所見・保持点・要求別の候補と採否理由・nextActionsを欠落なく持つ。
- [ ] C06がC04のstage契約だけを読み、完成画像の合格判定をせず、構図・文字・配色のlensを必要な分だけ読んで、所見を原依頼の本質成果IDへ結ぶ。
- [ ] C01がinit時に原依頼の原文とhash・該当する本質成果IDをbriefへ固定し、各周回の原依頼との差分と所見区分をdelivery.jsonへ記録し、該当する本質成果が全てPASSになった時点で周回を止める(C15)。
- [ ] C08がanalysis-review.jsonのPASSか決定論検査の失敗項目を確認してから制作・修正し、新しいPDF/PNGをC02へ渡す。C02のFIXのうち目的・事実・公開範囲のずれはC04の改訂案とC05の再評価を経て戻り、工程全体の周回を3で打ち切る(C14/C15)。
- [ ] 4skillのSKILL.mdとreferences/runtime.mdの実行例がpython3 scripts/flyer.py経由にそろい、node scripts/cli.cjsの直接起動が残らない。

### 受入例
- 満たす例: 新規projectに選択済み素材と生成済み背景を取り込み、PNGの可変文字とQRを別層で出力する。
- 満たさない例: promptsコマンド実行だけで背景生成済みとする、生成画像内の文字やQRを本番用に採用する。

### 事前解決済み判断
Pythonは標準入口と配布制御、NodeはChromium/QR/PDF用backend。画像編集はホスト画像編集ツールを使用する。制作担当C08は書込み権限を持つ唯一のstage agentとし、分析担当C06の書込みはanalysis.jsonに限る。周回数は提案評価のたびに数え直さない。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
