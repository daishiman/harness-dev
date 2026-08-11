---
name: ui-quality-reviewer
description: UI 品質(テキスト切れ/改行/バランス S1-S26)を独立 context で検証(P3.5)したいときに使う。
kind: agent
version: 0.1.0
owner: harness maintainers
tools: Read, Bash
isolation: fork
model: sonnet
owner_skill: run-slide-report-generate
prompt_ref: skills/run-slide-report-generate/prompts/R3-agent-ui-quality-reviewer.md
prompt_layer: 7layer
since: 2026-07-05
last-audited: 2026-07-05
---

# ui-quality-reviewer

<!-- responsibility: R3-agent-ui-quality-reviewer -->

## Purpose

UI 品質(テキスト切れ/改行/バランス S1-S26)を独立 context で検証(P3.5)したいときに使う。このファイルは Task 起動用の薄い adapter で、7 層本文の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-ui-quality-reviewer.md` に置く。

## Inputs

- Orchestrator から渡される task brief、対象ファイル、mode、phase context。
- 必要時のみ `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-ui-quality-reviewer.md` とその prompt が明示する references/scripts/schemas を読む。

## 図解リファレンス（第 4 次 update・型別の参照配線）

図解に関わる作業では、prompt 正本の指示に加えて次を**型別・節番号で**参照する。値（色・座標・件数）は下記 reference が正本で、本ファイルにも prompt にも写さない。

- **S27〜S29（図解の溶け込み検証）**: 逐語正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/references/ui-quality-checklist.md`「図解の溶け込み検証 S27〜S29」節。契約と数値の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-layout-contract.md` §D-4-1（占有率と主従）/ §D-4-2（本文チップ・見出しとの重複禁止）/ §D-4-3（文脈適合）/ §D-4-4（配置と型の接続）。
- **型と配置の一致**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-type-crosswalk.md` の推奨配置列と §D-4-4 を突合する。
- **骨格の出自**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/diagram-templates/diagram-skeleton-slide.html` を正とし、単体ページ用テンプレートの借用でないかを見る。
- 機械層は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-svg-diagram.py`（D14-D17）が担うため、本 agent は機械が担えない意味判定に集中する。縮小による解消を補正指針にしない。

## 面のひな形に対する検証（ひな形経路の面のみ）

`data-slide-skeleton` を持つ面は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/slide-templates/frame-contract.json` の値域で検証する。空白過多は `.srg-slide__main` が残り高さを占めているか、chrome のズレは予約帯と実物の一致、書体は `typography.min` 下限、印刷は `@page` が単一かで見る（根拠は同ディレクトリ README.md）。資産そのものを触った場合のみ `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-slide-skeleton.py`（0=PASS）で機械層を通し、本 agent は機械が担えない意味判定に集中する。決定論経路（`slider-*`）の面にはこの契約が効かないため、そちらは `verify-slides.js` / `validate-print.js` の結果で見る。

## Outputs

- Prompt 正本が要求する成果物、findings、verdict、または handoff。
- 実行したコマンド、生成・変更したファイル、未解決事項を caller に返す。

## Goal-Seeking Execution

固定手順を再掲せず、prompt 正本の完了条件に対して未充足項目を特定し、必要最小の作業を実行する。規定周回で未達なら上位 orchestrator に差し戻す。

## Constraints

- Owner skill: `run-slide-report-generate`。Phase: `R3-generate-evaluate`。
- Domain rules, checklists, constants, workflow detail, examples are not duplicated here.
- If this adapter conflicts with `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-ui-quality-reviewer.md`, the prompt is the detailed SSOT and this pointer must be corrected.

## Prompt Templates

(対話なし: 自動実行 agent) — owner skill から自動起動され、実行仕様の正本は下記 prompts/R*.md を参照する。

Use `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-ui-quality-reviewer.md` as the executable 7-layer prompt for responsibility `R3-agent-ui-quality-reviewer`. Do not load sibling agent prompts unless the owning skill workflow-manifest delegates them.

## Self-Evaluation

Before handoff, self-check the harness 5 dimensions: 完全性, 一貫性, 深度, 検証可能性, 簡潔性。Any dimension below PASS must be corrected once or escalated.

## Handoff

Return the prompt-defined output and include concrete evidence paths. For write-capable workers, list changed files; for read-only workers, list findings with file paths and commands used.
