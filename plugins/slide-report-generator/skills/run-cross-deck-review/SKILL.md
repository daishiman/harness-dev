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
  activation_state: semantic_evaluator_started
  engine: inline
  fork: subagent
  max_loops: 5
responsibility_refs:
  - prompts/R1-orchestrate.md
manifest: workflow-manifest.json
schema_refs:
  - schemas/cross-deck-review-report.schema.json
feedback_contract: # per-skill 受入基準(purpose-acceptance)。横断分析の網羅性 verdict と突合し汎用ゲート言い換えへ退化させない
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: cross-deck-consistency.js が横断対象 slide deck を走査し必須入力欠落・shared-spec 差分・外部 URL 混入・CSS 変数・GSAP・印刷 CSS・rem 逸脱を突合、機械チェック入力(各デッキの structure.md/index.html と、index.html が実際に読み込む CSS/JS)が全て解決でき未解決参照が0件
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 既知の機械検出可能な不整合(shared-spec差分/rem単位/外部URL/index.html欠落/未解決のローカル参照)を注入したシリーズで cross-deck-consistency.js が全件検出し、クリーンseriesをPASSとすることを受入テストが確認する
      verify_by: test
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
runtime_root_policy: host-skill-path
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-cross-deck-review

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

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
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all --json
```

終了コード 0／1／2 と parse 可能な JSON をそれぞれ PASS／WARN／FAIL の検査結果として受け取り、判定を一次根拠として `Task` で **cross-deck-reviewer** を常に起動する (`isolation: fork`)。機械チェックが全 PASS でも意味・構成上の C3-C10 は自動判定できないため省略しない。JSON を取得できない起動・解析不能だけを実行障害として扱う。cross-deck-reviewer は**単一 fork context 内で Agent A/B/C の 3 レンズ**(論理・構造 / メタ・発想 / システム・戦略) として用語／意匠／構成の観点を多角分析し (再 fork＝SubAgent 起動はしない)、**4 条件** (矛盾なし／漏れなし／整合性／依存関係整合) で判定する。用語ゆれ (メタファー・専門語の不一致)・意匠差 (配色・レイアウト・shared-spec の乖離)・構成不整合 (章立て・粒度・難易度段階の崩れ) を洗い出す。

### R3: 網羅検出結果の報告

3 レンズ分析の結果を統合し、不整合の網羅検出結果を横断レポート (用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率) として返す。修正が必要な項目は P0/P1/P2 分類付きで `run-slide-report-modify` への委譲として提示する (本 skill は検証・検出のみ・修正しない)。

## 決定論チェック (deterministic_checks)

```bash
# シリーズ横断整合性の機械チェック (shared-spec/URL/CSS変数/GSAP/印刷)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all --json
# 個別成果物の統一感検証 (テーマ・スタイル整合)
node "${SRG_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}}/vendor/scripts/check-consistency.js" <deck-dir>
```

## ゴールシーク実行

### 受入基準 (combinators)

`with-goal-seek`(max_loops 5) + `with-feedback-contract`。ループ本体は `Task` で cross-deck-reviewer worker (単一 fork) へ委譲し、親へは横断レポートのみ返す。受入基準は当該 skill の goal／checklist 由来の受入条件 (purpose-acceptance):

- **IN1 (inner・script)**: `cross-deck-consistency.js` が横断対象 slide deck を走査し必須入力欠落・shared-spec 差分・外部 URL 混入・CSS 変数・GSAP・印刷 CSS・rem 逸脱を突合し、機械チェック入力 (各デッキの structure.md / index.html と、index.html が実際に読み込む CSS/JS) が全て解決でき、未解決参照が 0 件。
  - **要件は「CSS/JS が解決できること」であって「`styles.css` / `scripts.js` というファイルが在ること」ではない。** CSS/JS を index.html へインライン化した自己完結デッキは `styles.css` を持たないが正しい。逆に、`<link href="styles.css">` があるのに参照先が無いデッキは未解決参照 1 件として error になる。
  - 検査対象は inline `<style>` / `<script>` と `<link>` / `<script src>` の**両方を合わせたもの**。片方だけではブラウザが実際に適用するものにならない (出荷デッキにはインライン化後もディスク上に旧版の `styles.css` が残っている例があり、そちらを読むと実物と違うものを見て合否を出すことになる)。
- **OUT1 (outer・test)**: 既知の機械検出可能な不整合 (shared-spec差分／rem単位／外部URL／index.html 欠落／未解決のローカル参照) を注入したシリーズで `cross-deck-consistency.js` が全件検出し、クリーンseriesをPASSとすることを受入テストが確認する。用語ゆれ・構成不整合の意味評価は3レンズ分析とelegant-reviewが担う。
  - fixture の `index.html` は `styles.css` / `scripts.js` を実際に `<link>` / `<script src>` で参照する。参照の無い fixture は「ブラウザが決して適用しないファイルの中身」を検査する形になり、実物のデッキを再現しない。

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
| 横断レポート | conversation-output として呼び出し元へ返す (永続ファイルは作成しない) |

## 追加リソース

- `prompts/R1-orchestrate.md` — R1→R2→R3 横断整合検証の 7 層実行 SSOT (Layer 1-7 + Self-Evaluation + 出力指示)。SKILL.md は router、本 prompt は完全駆動の実行契約。
- `workflow-manifest.json` — R1-collect-scope → R2-parallel-analysis → R3-report の phase 定義・dependsOn・entryHook/exitHook・fatal_exit_codes・resources。
- `references/cross-deck-consistency-rules.md` — 用語集 / CONST_001-005 / 検証項目 C1-C15 / 判定マトリクス (4 条件) / Agent A/B/C 3レンズ分析テンプレート / 修正の優先度分類 (P0/P1/P2) / headline 軸と Agent A/B/C レンズ・C1-C15 の対応表 の逐語正本 (cross-deck-reviewer と共有する手続き知識 SSOT)。
- `cross-deck-reviewer` (agent・`../../agents/cross-deck-reviewer.md`) — `Task` で name 起動する独立 context worker (read-only 検出・分類専任)。単一 fork context 内で Agent A/B/C の 3 レンズ分析 × 4 条件を実行 (再 fork しない)。
- `vendor/scripts/cross-deck-consistency.js` — シリーズ横断整合性の機械チェック (必須入力欠落・shared-spec 差分・rem単位・CSS変数・GSAP・印刷・URL混入。C1-C2 / C11-C13 / C15 の一次根拠)。スライドタイプ/命名のC3はAgent Aが目視判定する。
- `vendor/scripts/check-consistency.js` — 個別成果物の統一感検証 (テーマ・スタイル整合)。
