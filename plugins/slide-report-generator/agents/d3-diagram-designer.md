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

## 図解リファレンス（第 4 次 update・型別の参照配線）

図解に関わる作業では、prompt 正本の指示に加えて次を**型別・節番号で**参照する。値（色・座標・件数）は下記 reference が正本で、本ファイルにも prompt にも写さない。

- **型カタログ**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-type-crosswalk.md` §0（4 つの名前空間の対応）→ §1-§8（特に §6 量・分布）→ §10。インタラクションを要さない意図なら決定論ビルダーまたは静的 CSS 型の方が安く堅いため、D3 を選ぶ前に代替経路の有無を確認する。
- **数値契約**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-layout-contract.md` §D-1 4px グリッド / §D-2 複雑度予算（系列数・ノード数・注釈数）/ §D-3 コネクタ 5 原則 / §D-4-1 占有率 / §D-4-3 文脈適合 / §D-4-4 配置と型の接続 / §D-5 annotation の文法。
- **色ロール**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-style-tokens.md` §1 ロール表 / §2 系列色と使用制限 / §3 focal rule / §5 線幅・角丸・影 / §6 書体。**hex 直書き禁止**。

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
