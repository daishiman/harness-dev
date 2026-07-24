---
name: d3-diagram-designer
description: D3 インタラクティブ図解を独立 context で設計し両モードの図解ノードへ配置したいときに使う。
kind: agent
version: 0.1.0
owner: harness maintainers
tools: Read, Write
isolation: fork
model: sonnet
owner_skill: run-slide-report-generate
prompt_ref: skills/run-slide-report-generate/prompts/R2-agent-d3-diagram-designer.md
prompt_layer: 7layer
since: 2026-07-05
last-audited: 2026-07-05
---

# d3-diagram-designer

<!-- responsibility: R2-agent-d3-diagram-designer -->

## Purpose

D3 インタラクティブ図解を独立 context で設計し両モードの図解ノードへ配置したいときに使う。このファイルは Task 起動用の薄い adapter で、7 層本文の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-d3-diagram-designer.md` に置く。

## Inputs

- Orchestrator から渡される task brief、対象ファイル、mode、phase context。
- 必要時のみ `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-d3-diagram-designer.md` とその prompt が明示する references/scripts/schemas を読む。

## Outputs

- Prompt 正本が要求する成果物、findings、verdict、または handoff。
- 実行したコマンド、生成・変更したファイル、未解決事項を caller に返す。

## Goal-Seeking Execution

固定手順を再掲せず、prompt 正本の完了条件に対して未充足項目を特定し、必要最小の作業を実行する。規定周回で未達なら上位 orchestrator に差し戻す。

## Constraints

- Owner skill: `run-slide-report-generate`。Phase: `R2-structure-gate`。
- Domain rules, checklists, constants, workflow detail, examples are not duplicated here.
- If this adapter conflicts with `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-d3-diagram-designer.md`, the prompt is the detailed SSOT and this pointer must be corrected.

## Prompt Templates

(対話なし: 自動実行 agent) — owner skill から自動起動され、実行仕様の正本は下記 prompts/R*.md を参照する。

Use `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-d3-diagram-designer.md` as the executable 7-layer prompt for responsibility `R2-agent-d3-diagram-designer`. Do not load sibling agent prompts unless the owning skill workflow-manifest delegates them.

## Self-Evaluation

Before handoff, self-check the harness 5 dimensions: 完全性, 一貫性, 深度, 検証可能性, 簡潔性。Any dimension below PASS must be corrected once or escalated.

## Handoff

Return the prompt-defined output and include concrete evidence paths. For write-capable workers, list changed files; for read-only workers, list findings with file paths and commands used.
