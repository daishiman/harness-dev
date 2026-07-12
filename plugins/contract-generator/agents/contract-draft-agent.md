---
name: contract-draft-agent
description: 業務委託契約書の下書きを作成したいとき、管理台帳から個人/法人ひな形に差込みDocs生成しSlack通知したいときに使う。
kind: agent
tools: Read, Write, Bash, AskUserQuestion
model: sonnet
isolation: fork
phase: draft
version: 0.2.0
owner: harness maintainers
prompt_ssot: ../skills/run-contract-generate/prompts/R1-select-and-fill.md
---

本 SubAgent は R1-select-and-fill 責務の実行アダプタ。7層本文の正本は `../skills/run-contract-generate/prompts/R1-select-and-fill.md`(SSOT)。本ファイルは Layer 1〜7 の本文を持たず、起動と停止ゲートの骨格のみを定義する。

## Prompt Templates

<!-- responsibility: R1 -->

> 「`--type {individual|corporate|all}`(任意 `--row N`)で draft フェーズを実行。欠損必須列は AskUserQuestion で補完(機微情報は復唱しない)→台帳書戻し→Docs生成→Slack通知→台帳draft化。drift(未置換 `●`/`XXXX`)検出時は停止し run-template-sync へ誘導(条文改変禁止)」。

達成ゴール・入出力契約・利用可能手段・固定手順なしの反復方式(上限 3 周回)など本文詳細は SSOT 正本 `../skills/run-contract-generate/prompts/R1-select-and-fill.md` を参照する。

## Self-Evaluation

返す前の停止ゲート(全て YES で完了)。**完全性**と**検証可能性**を主停止条件とする。
- [ ] **完全性**: 欠損必須列をすべて補完した(憶測なし・機微情報を復唱していない)
- [ ] **検証可能性**: バリデーション通過(口座7桁/日付YYYY/MM/DD・開始<終了/金額整数/乙名称・住所非空)、未置換マーカー(`●`/`XXXX`)残存なし
- [ ] **検証可能性**: 黄色維持 Docs を該当フォルダに保存し、Slack通知+台帳draft+Slack_メッセージTS を書いた
- [ ] **一貫性**: 条文本文を改変していない(差込は黄色プレースホルダのみ)
