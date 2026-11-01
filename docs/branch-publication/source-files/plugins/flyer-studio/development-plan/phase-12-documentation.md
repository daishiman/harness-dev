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
  reason: チラシ制作の再現性と導入品質のため適用
---

# P12 — documentation

## 目的
操作と制作知識・プロンプトを次回も使える状態にする。

## 背景
毎回の用途・素材・表現を再確認する入口と、過去の失敗条件が探せないと再現性は続かない。説明を実コマンドへ結び付ける。

## 前提条件
P11の検証結果、prompts3件、references/、catalog galleryがある。

## ドメイン知識
既定素材は候補であり自動採用ではない。参照flyerは構図/字体分析用で人物・固有文言を転載しない。

## 成果物
README.md・INSTALL.md・references/runtime.md・interview.md・workflow.md・design-rules.md・production-history/。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] READMEの開始例から素材候補・形式ヒアリング・白黒・新構図・実生成・個別検査・納品へ辿れ、実CLIと矛盾しない。
- [ ] INSTALLがClaude/Codexの導入surfaceと外部依存、未検証経路、global導入未依頼の境界を説明する。
- [ ] README・references/runtime.md・root SKILL.mdの実行例がpython3 scripts/flyer.py入口にそろい、4段階の入口(既存紙面の改善はrun-analyze-flyer、新規はrun-create-flyer)を同じ言葉で説明する。
- [ ] README・references/workflow.mdが、原依頼と本質成果を基準にする制作の周回と、プラグインを改善する時のessence-check手順(本質成果IDと実事例を添えて変更を出し、基準を超える変更は利用者の承認記録が無い限り受け付けられない)を説明する。
- [ ] .codex-plugin/plugin.jsonのlongDescriptionとdefaultPromptを4段階の説明へ更新し、plugin.json・.claude-plugin/plugin.json・.codex-plugin/plugin.jsonのname/version/descriptionが一致する。

### 受入例
- 満たす例: 「白系は外周を紙白へ」「下部文字は全紙面中央」と画像なしでも次回実行者が判断できる。
- 満たさない例: 13旧案を固定templateとしてコピー、過去の個人event日付を新企画の事実として自動確定する。

### 事前解決済み判断
過去のHyogo briefは未確認example。新企画の住所/価格/日付/人物許可は制作ごとに確認する。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
