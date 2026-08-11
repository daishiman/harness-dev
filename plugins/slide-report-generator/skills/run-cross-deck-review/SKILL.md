---
name: run-cross-deck-review
description: 複数の slide deck をシリーズ横断で用語/意匠/構成の整合性検証したいとき、用語ゆれ・意匠差・構成不整合を網羅検出したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[series-dir?]"
arguments: [series_dir]
allowed-tools:
  - Read
  - Bash(node *)
  - Task
  - Glob
  - Grep
effect: conversation-output
owner: harness maintainers
since: 2026-07-05
last-audited: 2026-07-05
output_language: ja
prompt_layer: 7layer
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
responsibility_refs:
  - prompts/R1-orchestrate.md
manifest: workflow-manifest.json
schema_refs:
  - schemas/cross-deck-review-report.schema.json
feedback_contract: # per-skill 受入基準(purpose-acceptance)。横断分析の網羅性 verdict と突合し汎用ゲート言い換えへ退化させない
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: cross-deck-consistency.js が横断対象 slide deck を走査し必須入力欠落・shared-spec 差分・外部 URL 混入・CSS 変数・GSAP・印刷 CSS・rem 逸脱を突合、機械チェック入力(各デッキの structure.md/index.html/styles.css/scripts.js)の欠落が0件
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 既知の機械検出可能な不整合(shared-spec差分/rem単位/外部URL/必須入力欠落)を注入したシリーズで cross-deck-consistency.js が全件検出し、クリーンseriesをPASSとすることを受入テストが確認する
      verify_by: test
---

# run-cross-deck-review

> **役割**: 複数の slide deck を**シリーズ横断**で整合検証する独立起動 skill (移植元 P5 = cross-deck-reviewer 相当)。単一成果物では見えない**シリーズ全体の整合崩れ** (用語ゆれ・意匠差・構成不整合) を、Agent A/B/C の 3 レンズ分析 × 4 条件で網羅検出する (read-only 検出専任)。plugin root = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}`、実行パスは全てここ起点 (repo-root ハードコード禁止)。個別成果物の修正は `run-slide-report-modify` の責務。

## Purpose & Output Contract

複数 slide deck のシリーズ横断で**用語／意匠／構成の整合性**を検証し、用語ゆれ・意匠差・構成不整合が**網羅的に検出された状態**を作る。出力見出しの 3 観点 (用語ゆれ / 意匠差 / 構成不整合) は、分析レンズ Agent A/B/C (論理・構造 / メタ・発想 / システム・戦略) と C1-C15 へ `references/cross-deck-consistency-rules.md` の対応表 (§headline 軸と Agent A/B/C レンズ・C1-C15 の対応) で橋渡しする。

- **入力**: 複数の slide deck 成果物 (シリーズディレクトリ配下の `slide-*` 群)。
- **出力**: **横断レポート** (用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率)。read-only 分析・成果物は書き換えない。
- **完了条件**: (1) 横断対象の slide deck を収集し `cross-deck-consistency.js` で必須入力欠落・shared-spec 差分・外部 URL 混入・CSS 変数・GSAP・印刷 CSS・rem 逸脱を突合、(2) 用語／意匠／構成を Agent A/B/C の 3 レンズ分析 (単一 fork context 内多角分析) で検証、(3) 不整合を網羅検出して報告 (4 条件: 矛盾なし／漏れなし／整合性／依存関係整合)。

## ワークフロー (R1 → R2 → R3・worker は Task で name 起動)

### R1: 横断対象の収集と観点確定

横断対象の slide deck 群と整合観点をヒアリングして確定する。シリーズディレクトリ配下の `slide-*` 成果物を Glob で列挙し、比較の基準 (共通用語・共通意匠 SSOT・章立て構成) を明示する。

### R2: 3 レンズ分析

まず機械的チェックで shared-spec 差分・外部 URL 混入・CSS 変数・GSAP・印刷 CSS・rem 逸脱を突合する:

```bash
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all
```

FAIL／WARN 項目について `Task` で **cross-deck-reviewer** を起動 (`isolation: fork`)。cross-deck-reviewer は**単一 fork context 内で Agent A/B/C の 3 レンズ**(論理・構造 / メタ・発想 / システム・戦略) として用語／意匠／構成の観点を多角分析し (再 fork＝SubAgent 起動はしない)、**4 条件** (矛盾なし／漏れなし／整合性／依存関係整合) で判定する。用語ゆれ (メタファー・専門語の不一致)・意匠差 (配色・レイアウト・shared-spec の乖離)・構成不整合 (章立て・粒度・難易度段階の崩れ) を洗い出す。

### R3: 網羅検出結果の報告

3 レンズ分析の結果を統合し、不整合の網羅検出結果を横断レポート (用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率) として返す。修正が必要な項目は P0/P1/P2 分類付きで `run-slide-report-modify` への委譲として提示する (本 skill は検証・検出のみ・修正しない)。

## 決定論チェック (deterministic_checks)

```bash
# シリーズ横断整合性の機械チェック (shared-spec/URL/CSS変数/GSAP/印刷)
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all
# 個別成果物の統一感検証 (テーマ・スタイル整合)
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/check-consistency.js" <deck-dir>
```

## ゴールシークと受入基準 (combinators)

`with-goal-seek`(max_loops 5) + `with-feedback-contract`。ループ本体は `Task` で cross-deck-reviewer worker (単一 fork) へ委譲し、親へは横断レポートのみ返す。受入基準は当該 skill の goal／checklist 由来の受入条件 (purpose-acceptance):

- **IN1 (inner・script)**: `cross-deck-consistency.js` が横断対象 slide deck を走査し必須入力欠落・shared-spec 差分・外部 URL 混入・CSS 変数・GSAP・印刷 CSS・rem 逸脱を突合し、機械チェック入力 (各デッキの structure.md / index.html / styles.css / scripts.js) の欠落が 0 件。
- **OUT1 (outer・test)**: 既知の機械検出可能な不整合 (shared-spec差分／rem単位／外部URL／必須入力欠落) を注入したシリーズで `cross-deck-consistency.js` が全件検出し、クリーンseriesをPASSとすることを受入テストが確認する。用語ゆれ・構成不整合の意味評価は3レンズ分析とelegant-reviewが担う。

未達は最大 3 周 (inner) / 5 loops (goal-seek) で findings を反映し再実行する。網羅率が閾値未満なら分析観点を追加して再走する。

## 境界

- 入力 = 複数成果物／出力 = 横断整合レポート (read-only 分析・成果物を書き換えない)。
- **個別成果物の修正は `run-slide-report-modify` へ委譲**する (本 skill は検証・検出のみ)。
- 新規生成は `run-slide-report-generate` の責務。

## Gotchas

- **配置非依存**: 全実行パスは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/…` 起点。repo-root 直書き禁止。
- **read-only 分析**: 成果物を書き換えない (`allowed-tools` に Write/Edit を持たない)。検出のみで、修正は委譲。
- **3 レンズ × 4 条件を省略しない**: 用語／意匠／構成の 3 観点を Agent A/B/C の 3 レンズで多角分析し (単一 fork context 内・再 fork＝SubAgent 起動しない)、4 条件 (矛盾なし／漏れなし／整合性／依存関係整合) で判定する。単一観点に縮退させない。
- **網羅性が受入基準**: 機械層はOUT1 fixtureの注入不整合を全件検出し、意味層は3レンズでC1-C15を全件判定する。一部観点だけでPASS扱いにしない。
- **agent は name 参照**: `cross-deck-reviewer` はファイルパス依存でなく Task の name 起動。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本 skill 資産 | `plugins/slide-report-generator/skills/run-cross-deck-review/` |
| 横断レポート | 呼び出し時に指定 (既定は series-dir 直下の分析レポート) |

## 追加リソース

- `prompts/R1-orchestrate.md` — R1→R2→R3 横断整合検証の 7 層実行 SSOT (Layer 1-7 + Self-Evaluation + 出力指示)。SKILL.md は router、本 prompt は完全駆動の実行契約。
- `workflow-manifest.json` — R1-collect-scope → R2-parallel-analysis → R3-report の phase 定義・dependsOn・entryHook/exitHook・fatal_exit_codes・resources。
- `references/cross-deck-consistency-rules.md` — 用語集 / CONST_001-005 / 検証項目 C1-C15 / 判定マトリクス (4 条件) / Agent A/B/C 3レンズ分析テンプレート / 修正の優先度分類 (P0/P1/P2) / headline 軸と Agent A/B/C レンズ・C1-C15 の対応表 の逐語正本 (cross-deck-reviewer と共有する手続き知識 SSOT)。
- `cross-deck-reviewer` (agent・`../../agents/cross-deck-reviewer.md`) — `Task` で name 起動する独立 context worker (read-only 検出・分類専任)。単一 fork context 内で Agent A/B/C の 3 レンズ分析 × 4 条件を実行 (再 fork しない)。
- `vendor/scripts/cross-deck-consistency.js` — シリーズ横断整合性の機械チェック (必須入力欠落・shared-spec 差分・rem単位・CSS変数・GSAP・印刷・URL混入。C1-C2 / C11-C13 / C15 の一次根拠)。スライドタイプ/命名のC3はAgent Aが目視判定する。
- `vendor/scripts/check-consistency.js` — 個別成果物の統一感検証 (テーマ・スタイル整合)。
