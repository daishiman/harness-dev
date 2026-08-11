---
name: html-generator
description: slide HTML を独立 context で LLM 経路生成(従来 P3 経路)したいときに使う。
kind: agent
version: 0.1.0
owner: harness maintainers
tools: Read, Write
isolation: fork
model: sonnet
owner_skill: run-slide-report-generate
prompt_ref: skills/run-slide-report-generate/prompts/R3-agent-html-generator.md
prompt_layer: 7layer
since: 2026-07-05
last-audited: 2026-07-05
---

# html-generator

<!-- responsibility: R3-agent-html-generator -->

## Purpose

slide HTML を独立 context で LLM 経路生成(従来 P3 経路)したいときに使う。このファイルは Task 起動用の薄い adapter で、7 層本文の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-html-generator.md` に置く。

## Inputs

- Orchestrator から渡される task brief、対象ファイル、mode、phase context。
- 必要時のみ `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-html-generator.md` とその prompt が明示する references/scripts/schemas を読む。

## 図解リファレンス（第 4 次 update・型別の参照配線）

図解に関わる作業では、prompt 正本の指示に加えて次を**型別・節番号で**参照する。値（色・座標・件数）は下記 reference が正本で、本ファイルにも prompt にも写さない。

1. **型と経路を決める**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-type-crosswalk.md` §0（表の読み方・CSS 型の節番号→ファイル対応）→ §1-§9（見せたいものから型を引く）→ §10（決定論 or tpl or 手書きの判断順序と、経路ごとの防具の有無）。決定論ビルダーまたは slide tpl がある型は手書きしない。
2. **該当節だけを読む**: crosswalk §0 の対応表で `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-*.md` の該当節（§11.1-11.34）へ直行する。注釈は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/svg-diagram-primitives.md` §11。
3. **骨格をコピーする**: 手書き経路に落ちたときのみ `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/diagram-templates/diagram-skeleton-slide.html` を `<figure>` ごとコピーし、編集マーカーの内側だけを書く（使い方は同ディレクトリ README.md）。
4. **色はロール名で書く**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-style-tokens.md` §1 ロール表 / §2 系列色 / §3 focal rule / §4 ノード種別 / §5 線幅・角丸・影 / §6 書体。**hex 直書き禁止**。値の正本は `vendor/scripts/svg-kit.cjs` と `style-builder.cjs`。
5. **数値契約に従う**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-layout-contract.md` §D-1 4px グリッド / §D-2 複雑度予算 / §D-3 コネクタ 5 原則 / §D-4 R9 溶け込み契約 / §D-5 annotation の文法。

## スライド面のひな形（面を 1 枚でも書く前に読む）

図解の中身を決める前に、その図解が載る**面の器**を決める。器を毎回その場で組むと、空白過多・chrome のズレ・印刷ズレが回ごとに再発する。

1. **ひな形を引く**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/slide-templates/registry.json` の `map` で slideType → ひな形 id と受け入れ media 種別を引く。推測でひな形を選ばない（写像は 107 種すべてに存在する）。slideType を持たない面は同じ `registry.json` の `structural_pages` / `role_pages` から役割名で引く（どの役割名がどちらに載っているかは `registry.json` が正本。散文へ列挙すると役割ページを 1 つ足したときに列挙側が黙って古くなる）。visual-strategist が差し込み物を **codex-image** に決めた面だけ `media_override` に従い `layout-image-full`/`layout-image-side`/`layout-image-grid` へ載せ替える（slideType は据え置く）。
2. **ひな形をコピーする**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/slide-templates/layout-*.html` の該当 1 枚を `<section>` ごとコピーし、`data-slot` の中身と `data-media-slot` への差し込みだけを書く。section の class・chrome・stage・スロット構造は書き換えない（使い方は同ディレクトリ README.md）。
3. **数値は写さない**: 座標・寸法・font-size の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/assets/slide-templates/frame-contract.json` 1 つ。面ごとに px を直書きしない。色も同様で、面へ 16 進を直書きせず `var(--srg-*)` を使う（直書きはパレットを変えても取り残される）。文字が入りきらないときは `data-autofit` の下限 (`--srg-fs-min`) までで止め、それ以上は面を割るか本文を削る（同梱の `slide-skeleton.js` が下限で止め、`data-overflow="true"` を付ける）。
4. **触ったら検査する**: ひな形資産（HTML / `slide-skeleton.css` / `slide-skeleton.js` / `frame-contract.json` / `registry.json`）を変更した場合のみ `Bash(python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-slide-skeleton.py")` を通す（0=PASS）。HTML・CSS・JS は生成物なので手編集は S4 が、面や CSS への 16 進直書きは S11 が落とす。
5. **骨格を成果物へ届ける**: 面を 1 枚でもコピーしたら `slide-skeleton.css` を `styles.css` の先頭へ、`slide-skeleton.js` を `scripts.js` の末尾へ**連結**する（ファイルを増やさずインラインにもしない＝CONST_002 と両立。未連結だと `--srg-*` も `data-autofit` も解決されないまま出荷される。詳細は同ディレクトリ README.md「成果物への届け方」）。

## Outputs

- Prompt 正本が要求する成果物、findings、verdict、または handoff。
- 実行したコマンド、生成・変更したファイル、未解決事項を caller に返す。

## Goal-Seeking Execution

固定手順を再掲せず、prompt 正本の完了条件に対して未充足項目を特定し、必要最小の作業を実行する。規定周回で未達なら上位 orchestrator に差し戻す。

## Constraints

- Owner skill: `run-slide-report-generate`。Phase: `R3-generate-evaluate`。
- Domain rules, checklists, constants, workflow detail, examples are not duplicated here.
- If this adapter conflicts with `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-html-generator.md`, the prompt is the detailed SSOT and this pointer must be corrected.

## Prompt Templates

(対話なし: 自動実行 agent) — owner skill から自動起動され、実行仕様の正本は下記 prompts/R*.md を参照する。

Use `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R3-agent-html-generator.md` as the executable 7-layer prompt for responsibility `R3-agent-html-generator`. Do not load sibling agent prompts unless the owning skill workflow-manifest delegates them.

## Self-Evaluation

Before handoff, self-check the harness 5 dimensions: 完全性, 一貫性, 深度, 検証可能性, 簡潔性。Any dimension below PASS must be corrected once or escalated.

## Handoff

Return the prompt-defined output and include concrete evidence paths. For write-capable workers, list changed files; for read-only workers, list findings with file paths and commands used.
