---
name: template-sync-agent
description: 契約書のひな形(.docx)が変わったとき、差分を診断して差込マッピング・台帳を追従させ影響行を作り直し対象にしたいときに使う。
kind: agent
tools: Read, Edit, Bash
model: sonnet
isolation: fork
phase: template-sync
version: 0.2.0
owner: harness maintainers
prompt_ssot: ../skills/run-template-sync/prompts/R1-diagnose-and-resync.md
---

本 SubAgent は R1-diagnose-and-resync 責務の実行アダプタ。7層本文の正本は `../skills/run-template-sync/prompts/R1-diagnose-and-resync.md`(SSOT)。本ファイルは Layer 1〜7 の本文を持たず、起動と停止ゲートの骨格のみを定義する。

## Prompt Templates

<!-- responsibility: R1 -->

> 「ユーザーが『ひな形が変わった/テンプレ更新された』と述べたとき `--type {individual|corporate|all}`(任意 `--docx PATH`)で差分診断(MISSING/UNMAPPED)→マッピング/台帳更新→再診断 exit 0 →`--apply` で影響 completed 行へ再生成フラグ付与(draft/approved は巻き戻さない)」。作成意図の入力では発火しない。

達成ゴール・MISSING/UNMAPPED 用語・入出力契約・利用可能手段・固定手順なしの反復方式など本文詳細は SSOT 正本 `../skills/run-template-sync/prompts/R1-diagnose-and-resync.md` を参照する。

## Self-Evaluation

返す前の停止ゲート(全て YES で完了)。**完全性**と**一貫性**を主停止条件とする。
- [ ] **完全性**: `scan_template`(個人/法人)で MISSING/UNMAPPED を診断し、MISSING アンカー更新・UNMAPPED 台帳列追加(`lib/ledger.py:HEADERS` 手編集)を行った
- [ ] **検証可能性**: 再診断で `scan_template` が exit 0(整合)になった
- [ ] **一貫性**: `--apply` で影響 completed 行のみ 未作成+再生成フラグ◯ にした(draft/approved を巻き戻していない)
- [ ] **一貫性**: 条文本文を改変していない(更新はアンカー定義と台帳列のみ)
- [ ] **完全性**: 作成意図の入力では発火しない(description が「ひな形変更」に限定)
