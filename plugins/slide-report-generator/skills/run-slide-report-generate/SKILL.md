---
name: run-slide-report-generate
description: スライドやレポートを新規に作りたいとき、ヒアリングで output_mode(slide/report) を確定し構成設計→仕様確定ゲート→生成(HTML・決定論 render-slide.cjs・report render-report.js・Codex 画像)→30種思考法の生成後評価まで駆動したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[topic?] [--mode slide|report] [--report-type internal-analysis|client-proposal|tech-doc|learning] [--out-dir <path>]"
arguments: [topic, mode, report_type, out_dir]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(node *)
  - Bash(python3 *)
  - Task
  - Glob
  - Grep
effect: local-artifact
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
schema_refs:
  - ../../schemas/structure.schema.json
  - ../../schemas/report-structure.schema.json
  - schemas/generation-report.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 受入基準(purpose-acceptance)。deck-evaluator の生成後評価 verdict と突合し汎用ゲート言い換えへ退化させない
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-output-mode で output_mode(slide/report)と reportType の値域を送信前検証し、確定 mode が構成設計へ一貫伝播して仕様確定ゲート入力の欠落が0件
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 生成後に slide/report とも想定読者の共有課題→読者の変化→専門的で具体的な解決→自分へ移す行動の流れを持ち、slide は1スライド1メッセージ/長文なし・report は読み物/1項目1ビジュアルで、生成後評価(30種思考法)が視覚崩れ0で PASS する
      verify_by: test
---

# run-slide-report-generate

> **役割**: プレゼンスライド／読み物レポートの**新規生成**を単一 skill で駆動する主オーケストレータ。移植元 `presentation-slide-generator` の 7 フェーズ総体ワークフロー (P1 hearing → P2 structure → P2.5 仕様確定ゲート → P3 生成 → P3.5 UI 検証 → P3.6 生成後評価) を 1 skill に集約し、**意匠／技術コアは単一 SSOT で共有**したまま、**コンテンツ意図だけを `output_mode`(slide／report) で分岐**して 2 モードを 1 経路へ統合する。plugin root = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}`、実行パスは全てここ起点 (repo-root ハードコード禁止)。

## Purpose & Output Contract

`output_mode`(slide／report) と**読者価値ブリーフ**（対象範囲・共有課題/願望・読後/視聴後の変化・専門の橋・深さの証拠・正式タイトル制約）を確定し、意匠／技術コアを共有したまま **構成設計 → 仕様確定ゲート → 生成 → 生成後評価 (30 種思考法)** まで駆動する。入口は想定読者の範囲内で広く、本文は専門的・具体的に深くし、slide は「1 スライド 1 メッセージ／長文なし」、report は「読み物・1 項目 1 ビジュアル」で**視覚崩れ 0** の成果物を作る。

- **入力**: 構想 (自然文) + `output_mode` + 読者価値ブリーフ。report 時は `reportType`／読者／長さ／ビジュアル方針。任意 `--out-dir <path>`。
- **出力**: **生成レポート** (`output_mode` ／ 生成経路 ／ 生成後評価スコア ＋ 生成物パス (slide=`index.html`(+`styles.css`/`scripts.js`) ／ report=`report.html`) ＋ 未達指摘一覧)。
- **完了条件**: (1) `output_mode`・読者価値ブリーフ・(report 時) `reportType` が確定し mode 値域検証を通過、(2) 構成が「共有課題→変化→専門的解決→自分へ移す行動」を既存 schema 内で表現し仕様確定ゲートを PASS、(3) 成果物を生成、(4) `deck-evaluator` の mode-aware 生成後評価が読者フックと視覚崩れ 0 を確認して PASS。

## output_mode 分岐契約 (意匠は共有・意図のみ分岐)

**設計の核**: 意匠／技術層は**単一 SSOT で共有**し mode で重複させない。分岐するのは**コンテンツ意図層のみ**。

- **共有 SSOT (mode で重複させない)**: Kanagawa 配色 ／ 16:9 ／ 最小 1.4rem ／ GSAP ／ インライン SVG2 ／ 印刷 CSS ／ letterbox ／ Codex Image2 ／ style genome ／ 決定論レンダラ ／ `theme`・`aiVisual` schema `$defs`。
- **共有コンテンツ契約**: 読者価値ブリーフを R1→R2→R3 へ一貫伝播し、既存フィールド（title/audience/keyMessage/throughLine/sections）へ翻訳する。schema 外フィールドや素材にない数字・実績を発明しない。正式名称・検索性・適用範囲が必要な文書は主タイトルを保ち、subtitle/keyMessage/summary で読者価値を補う。
- **mode 別 (コンテンツ意図のみ分岐)**:
  - `slide`: 1 スライド 1 メッセージ ／ chip 強制 ／ 長文禁止 ／ 16:9 ／ 97 slideType ／ `schemas/structure.schema.json`。
  - `report`: 読み物 (文章多め可) ／ セクション＋段落 ／ 1 項目 1 ビジュアル最適化 ／ HTML レポート ／ 4 reportType ／ `schemas/report-structure.schema.json`。
- **reportType enum (4)**: `internal-analysis` (社内報告分析: 要約→背景→現状分析→所見→次アクション) ／ `client-proposal` (顧客提案 WP: 課題→解決策→効果実績→導入ステップ→CTA) ／ `tech-doc` (技術ドキュメント: 概要→前提→手順構造→注意点→参照) ／ `learning` (学習解説: 問い→核心概念→図解理解→例応用→まとめ)。
- **確定と伝播**: `hearing-facilitator` が `output_mode`／読者価値ブリーフ／`reportType`／読者／長さ／ビジュアル方針を確定 → 主 skill が下流全 agent へ**一貫伝播** → `validate-output-mode.py` が mode 値域を生成着手前に検証 (fail-closed)。

## ワークフロー (R1 → R2 → R3・agent は Task で name 起動)

参照 agent は **name で Task 起動**する (ファイル依存なし)。各 agent は独立 context (isolation) で自身の 7 層本文に従う。

### R1: ヒアリングと mode 確定

`Task` で **hearing-facilitator** を起動 (`isolation: inherit`・会話履歴を保持して mode 推定)。以下を確定する:

- `output_mode` = slide ／ report。読者価値ブリーフ = 対象範囲・共有課題/願望・読後/視聴後の変化・専門の橋・深さの証拠・正式タイトル制約。
- report 時: `reportType` (4 enum)／読者／長さ／ビジュアル方針。
- 全面画像化ゲート (CONST_006): ユーザーが「画像生成でスライドを作る」等を明示した場合、全面画像生成モードを確定 (背景化バランス型は明示時のみ)。設計方針の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/full-image-deck-method.md` (plugin-root 共有)、Codex Image2 実行導線の正本は skill 私有 `references/ai-image-pipeline.md` (ai-image-diagram-producer が消費) の 2 層に分離する。

確定した mode 一式を**下流 R2／R3 の全 agent へ一貫伝播**する。伝播前に `validate-output-mode.py` (下記 IN1) で値域を検証する。

### R2: 構成設計と仕様確定ゲート

確定 mode に応じて構成を設計し、**仕様確定ゲート**で P3 進入を制御する。

- **slide**: `Task` で **structure-designer** を起動 → `structure.json` (`schemas/structure.schema.json` 準拠) を設計。図解が要る場合は **d3-diagram-designer** (D3) ／ **data-visualizer** (データ可視化) を併用。
- **report**: `Task` で **report-structure-designer** を起動 → `report-structure.json` (`schemas/report-structure.schema.json` 準拠・`sections[]` 主配列) を設計。各 section のビジュアルは **visual-strategist** が「1 項目 1 ビジュアル」の三択 (`svg`／`mermaid`／`codex-image`／`none`) を決定。
- **読者中心設計**: 両 mode とも入口は想定読者の共有課題と変化を先に渡し、本論は確認済みの数字・手順・失敗・条件・限界まで掘る。各主要セクションに「兆候・問い・選択肢・次の行動」のいずれかを置き、自分ごと化する。
- **仕様確定ゲート**: `Task` で **structure-validator** を起動し、`node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/validate-structure.js" <structure|report-structure>` (V-001〜V-043・spec-registry SR-ID 連動) で機械検証する。判定: **PASS→R3** ／ **WARN→該当 ID をユーザー提示し承認後 R3** ／ **FAIL→R2 設計へ差し戻し**。

### R3: 生成と生成後評価

確定 mode ・経路で成果物を生成し、生成後評価まで駆動する。

- **生成経路 (mode ／指示で選択)**:
  - `slide` LLM 経路: `Task` で **html-generator** → `index.html` ＋ `styles.css` ＋ `scripts.js`。
  - `slide` 決定論経路 (推奨・再現性 100%): `Task` で **slide-renderer** → `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/render-slide.cjs" <structure.json> <out-dir>`。
  - `report` 経路: `Task` で **report-composer** → `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/render-report.js" <report-structure.json> <out.html>` で `report.html` を決定論生成。
  - **画像明示時のみ**: `Task` で **ai-image-diagram-producer** (Codex Image2)。導線 = `build-image-prompts.js` → `generate-images-codex.js` (`meta.source=codex-image2`・PNG 署名回収＋リトライ) → `build-deck-html.js` (自己完結 index.html)。`codex` 単体は画像生成器ではなく実 backend を着手前に確認する。
  - **品質補正 (mode 別・slide/report 対称)**:
    - `slide`: 必要に応じ **layout-optimizer** (レイアウト最適化) ／ **ui-quality-reviewer** (テキスト切れ・改行・バランス) を併用 + `verify-slides.js`／`validate-print.js` の決定論視覚ゲート。
    - `report`: **report-quality-reviewer** (読み物文体・段落密度・1 項目 1 ビジュアル整合・reportType 骨格・読者中心入口 RQ31〜RQ34) を併用 + `python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-report-visual.py" <report.html> --structure <report-structure.json> --require-structure --json` の決定論視覚ゲート。
- **生成後評価 (mode-aware)**: `Task` で **deck-evaluator** を起動 (思考リセット後 30 種思考法)。`slide`=視覚崩れ／1 メッセージ、`report`=可読性／図解適合／情報密度の mode 別 rubric 次元で区分評価する。**改善→再評価は最大 3 周** (`feedback_contract.max_iterations`)。CRITICAL (視覚崩れ) が残存する場合はループ枯渇時も未完了 (hard-fail) とし、`未達指摘一覧` は非 CRITICAL に限定する。

状態確認は `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/workflow-manager.js" <out-dir> --check --next` で行える。

## 決定論チェック (deterministic_checks)

送信前・生成後に以下の機械検証を実行する。値域外・仕様逸脱・視覚崩れは exit code で fail する。

```bash
# 送信前: output_mode/reportType 値域検証 (値域外 exit 2・fail-closed)
python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-output-mode.py" --mode <slide|report> [--report-type <enum>]
# 初回/更新後に依存+plugin-local Chromiumを復元し、node/npm/browser/codexをpreflight
python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/setup-playwright.py" --install && python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-output-mode.py" --preflight
# 構成の仕様確定ゲート (V-001〜043・SR-ID 連動)
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/validate-structure.js" <structure|report-structure>
# slide の UI 品質 (テキスト切れ・16:9 比率)
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/verify-slides.js" ./index.html --check-ratio
# report の決定論視覚ゲート (構造正本必須・欠落 exit 2 / 0=PASS / 1=崩れ検出)
python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-report-visual.py" <report.html> --structure <report-structure.json> --require-structure --json
# 生成後評価オーケストレータ (D1 視覚崩れ/D2 文字サイズ/D3 ナビ/D4 仕様適合・0=PASS/4=FAIL)
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/evaluate-deck.js" <out-dir>
# 画像明示時: prompt/meta/WebP 整合と style genome 反映 (PNG/WebP 署名検査)
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/validate-ai-image-assets.js" <out-dir> --full-image-deck --strict-style-genome
# 印刷 letterbox (@media print 内 cover を CRITICAL 検出)
node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/validate-print.js" <index.html>
```

## ゴールシークと受入基準 (combinators)

本 skill は固定手順でなく、**ゴール** (上記「目的と出力契約」の完了条件) へ向けて未達項目を埋める手順を都度生成して反復する。`with-goal-seek`(max_loops 5) + `with-feedback-contract` を適用する。ループ本体は親セッションで直接回さず `Task` で SubAgent へ fork し (`goal_seek.fork: subagent`)、親へは最終成果物パスと生成レポートのみ返す。

受入基準 (`feedback_contract.criteria`・frontmatter に焼込済) は当該 skill の goal／checklist 由来の**受入条件 (purpose-acceptance)** であり、汎用品質ゲートの言い換えに退化させない:

- **IN1 (inner・script)**: `validate-output-mode` で `output_mode`(slide／report) と `reportType` の値域を送信前検証し、確定 mode が構成設計へ一貫伝播して仕様確定ゲート入力の欠落が 0 件。
- **OUT1 (outer・test)**: 生成後に両 mode が「共有課題→読者の変化→専門的で具体的な解決→自分へ移す行動」を持ち、slide は 1 スライド 1 メッセージ／長文なし・report は読み物／1 項目 1 ビジュアルで、生成後評価が読者フックと視覚崩れ 0 を確認して PASS。

未達は最大 3 周 (inner) / 5 loops (goal-seek) で findings を反映し再実行、超過時は未達指摘一覧として生成レポートへ残す。

## 境界

- 入力 = 構想と `output_mode`／出力 = HTML 成果物 (`index.html`／`report.html`)。
- **既存成果物の局所修正は `run-slide-report-modify` へ委譲**する (本 skill は新規生成のみ)。
- **シリーズ横断の整合検証は `run-cross-deck-review` へ委譲**する。

## Gotchas

- **配置非依存**: 全実行パスは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}` 起点。vendor script = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/…`、plugin-root glue = `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/…`。repo-root 直書き禁止。
- **意匠は共有・mode で重複させない**: 配色／サイズ／レンダラ／schema `$defs` は単一 SSOT。slide／report で意匠を二重定義しない (`output_mode` 分岐契約)。
- **入口を広げても対象範囲・正確さを壊さない**: audience/reportType は維持し、正式名称・検索語・適用範囲が必要なら主タイトルに残す。読者価値は subtitle/keyMessage/summary で補い、素材にない数字・実績を作らない。
- **codex は画像生成器ではない**: `ai-image-diagram-producer` 起動時は着手前に実 text-to-image backend を確認する。`meta.source` は実体名 `codex-image2` を記録し plain `codex` は不可。
- **全面画像デッキは自己完結 HTML**: CSS/JS を `<style>`/`<script>` にインライン化 (`build-deck-html.js`)。別ファイル版は環境で消失しページ送り不可事故になりうる。
- **完成判定は実体で**: `echo`／サイズ／"PASS" 文字列で完成判断しない。ファイルは Read、画像は PNG/WebP 署名で検証し、出荷前にスクショ目視を推奨する。
- **agent は name 参照**: worker agent はファイルパス依存でなく Task の name 起動。存在は plugin の他 component が保証する。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本 skill 資産 | `plugins/slide-report-generator/skills/run-slide-report-generate/` |
| slide 成果物 | `<out-dir>/index.html`(+`styles.css`/`scripts.js`)／決定論経路は `render-slide.cjs` の出力先 |
| report 成果物 | `<out-dir>/report.html` (`render-report.js` の出力) |
| 生成後評価レポート | `<out-dir>/evaluation-report.json` / `.md` (`evaluate-deck.js` 出力) |

## 追加リソース

**パッケージ (実行 SSOT)**
- `prompts/R1-orchestrate.md` — R1→R2→R3 の 7 層実行 SSOT (Layer 1-7・15 agent/vendor scripts/schema/reference を実体参照。SKILL.md は router 要約、本 prompt が完全駆動契約)。
- `workflow-manifest.json` — phases (R1-hearing-mode → R2-structure-gate → R3-generate-evaluate)・gate(C1-C3)・dependsOn・entryHook/exitHook・fatal_exit_codes・resources[] (references/schemas/scripts の id↔path↔phaseIds)。
**skill 私有 references (10 本・帰属は `references/resource-map.yaml`)**
- `references/structure-design-rules.md` — slide 構成設計 (1スライド1メッセージ分解・共通仕様セクション・slideType 判定)。owner=structure-designer。
- `references/report-structure-types.md` — report 4 reportType 骨格 (社内報告分析/顧客提案WP/技術ドキュメント/学習解説)。owner=report-structure-designer。
- `references/d3-diagram-rules.md` — D3 インタラクティブ図解の意匠/実装規範。owner=d3-diagram-designer。
- `references/data-visualization-rules.md` — データ可視化 (グラフ/chart) 設計規範。owner=data-visualizer。
- `references/html-generation-rules.md` — slide HTML LLM 経路生成規範 (CONST_001-039)。owner=html-generator。
- `references/layout-optimization-rules.md` — レイアウト最適化 (文字数・カード/フォント・印刷 pt 換算)。owner=layout-optimizer。
- `references/ui-quality-checklist.md` — slide UI 品質 S 系観点定義・判定基準。owner=ui-quality-reviewer。
- `references/report-quality-checklist.md` — report 品質観点 RQ1〜RQ34・RQCONST (読み物文体/段落密度/本質図解/through-line/読者中心入口/navigation/runtime layout)。owner=report-quality-reviewer。runtime bundle＋`validate-report-visual.py` と対 (実描画/静的shape/意味を分離)。
- `references/deck-evaluation-rubric.md` — 生成後評価 (30 種思考法 mode-aware rubric・評価次元)。owner=deck-evaluator (hook-postgen-eval も消費)。
- `references/ai-image-pipeline.md` — Codex Image2 全面画像/差替パイプライン規範。owner=ai-image-diagram-producer。
- `references/resource-map.yaml` — 私有 reference の帰属 + progressive disclosure マップ (lint-reference-attribution.py の orphan/dangling 検査対象)。

**plugin 共有 schemas (`schema_refs`)**
- `../../schemas/structure.schema.json` — slide 入力契約 (97 slideType, `$defs`)。
- `../../schemas/report-structure.schema.json` — report 入力契約 (`sections[]`・structure と共通コア `$defs` 共有)。

**plugin 共有 scripts**
- `../../scripts/setup-playwright.py` / `validate-output-mode.py` — plugin-local Chromium復元・検査 + 送信前 mode/reportType 値域検証 (fail-closed exit 2) / 環境 preflight。
- `../../vendor/scripts/` — 決定論レンダラ・validator 群 (`render-slide.cjs`/`render-report.js`/`validate-structure.js`/`verify-slides.js`/`evaluate-deck.js`/`validate-print.js`/`build-image-prompts.js`/`generate-images-codex.js`/`build-deck-html.js`/`validate-ai-image-assets.js`/`workflow-manager.js`。byte 携行・書換禁止)。
- plugin-root references (本文が参照): `../../references/full-image-deck-method.md` / `post-generation-evaluation.md` / `report-types.md` ほか意匠・生成規範の共有正本。
