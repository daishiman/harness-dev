# Phase 02 — 設計 / BUILD CONTRACT (全 builder 共通の正本)

> このファイルは build を分担する全 Agent が **最初に読む単一契約**。ここで宣言した規約から逸脱しないこと。
> plugin root (以下 `$ROOT`) = `plugins/slide-report-generator/`。絶対パス起点 = `/Users/dm/dev/dev/xlocal/xl-skills/.worktrees/task-20260704-203214-wt-8/`。
> 移植元 (upstream, read-only) = `/Users/dm/dev/dev/ObsidianMemo/.claude/skills/presentation-slide-generator/`。

## A. 確定ファイル配置
```
plugins/slide-report-generator/
├── .claude-plugin/plugin.json         # manifest (envelope-draft 適用)
├── plugin-composition.yaml            # composition surface
├── EVALS.json                         # harness_eval surface (slide/report 両モード)
├── README.md                          # plugin README (portability: $CLAUDE_PLUGIN_ROOT 参照)
├── agents/                            # 16 sub-agent (.md, 7layer + repo frontmatter)
│   ├── hearing-facilitator.md         C04 (mode 確定を追加)
│   ├── structure-designer.md          C05
│   ├── structure-validator.md         C06
│   ├── d3-diagram-designer.md         C07
│   ├── data-visualizer.md             C08
│   ├── html-generator.md              C09
│   ├── slide-renderer.md              C10
│   ├── layout-optimizer.md            C11
│   ├── ui-quality-reviewer.md         C12
│   ├── deck-evaluator.md              C13 (mode-aware rubric を追加)
│   ├── ai-image-diagram-producer.md   C14
│   ├── slide-report-modifier.md       C15 (upstream slide-modifier を rename)
│   ├── cross-deck-reviewer.md         C16
│   ├── report-structure-designer.md   C17 (新規)
│   ├── visual-strategist.md           C18 (新規)
│   └── report-composer.md             C19 (新規)
├── skills/
│   ├── run-slide-report-generate/SKILL.md   C01
│   ├── run-slide-report-modify/SKILL.md     C02
│   └── run-cross-deck-review/SKILL.md       C03
├── hooks/hook-postgen-eval.py         C20
├── commands/
│   ├── slide-report-generate.md       C21
│   └── slide-report-status.md         C22
├── scripts/validate-output-mode.py    C23 (plugin-root Python glue)
├── schemas/                           # 真 schema (正本)
│   ├── structure.schema.json          (移植済)
│   ├── report-structure.schema.json   (新規・structure と共通コア共有)
│   ├── image-deck-plan.schema.json    (移植済)
│   ├── evaluation-report.schema.json  (移植済)
│   └── image-asset-manifest.schema.json (移植済)
├── references/                        # 42 upstream .md (移植済) + 4 新規 + feedback/
│   ├── report-types.md                (新規)
│   ├── report-writing-rules.md        (新規)
│   ├── report-visual-strategy.md      (新規)
│   └── mermaid-integration.md         (新規)
├── vendor/                            # byte 携行 (書換禁止) + additive 2 Node
│   ├── scripts/  (160 files, render-slide.cjs 等・書換禁止)
│   │   ├── render-report.js            (新規 additive・C19 owner)
│   │   └── mermaid-render.js           (新規 additive・C19 owner)
│   ├── assets/   (25 files・書換禁止)
│   ├── schemas-fixtures/ (8 files・書換禁止)
│   ├── package.json / package-lock.json  (additive で mermaid 依存追記可)
│   └── tests/                          (新規 Node renderer の最小テスト置き場)
└── tests/                             # plugin-root pytest (validate-output-mode 等)
```

## B. sub-agent frontmatter テンプレート (repo 規約・必須)
移植元 agent は frontmatter を持たない。全 agent に以下 YAML を **本文 (`# タイトル…`) の前に**付与する。
```yaml
---
name: <agent-name>                     # 例 hearing-facilitator (entry_points.agents と一致)
description: <inventory の description をそのまま>
kind: agent
version: 0.1.0
owner: xl-skills maintainers
tools: <inventory の tools をカンマ区切り>   # 例 Read, Write / Read, Bash
isolation: fork                        # worker は fork。C04(hearing)は inherit 可
model: sonnet
owner_skill: <所属 skill>               # C04-C14=run-slide-report-generate / C15=run-slide-report-modify / C16=run-cross-deck-review / C17-C19=run-slide-report-generate
prompt_layer: 7layer
since: 2026-07-05
last-audited: 2026-07-05
---
```
本文はその後に upstream の 7 層構造をそのまま (port は保持・new は 7 層で新規著述)。

## C. パス書換規約 (port 時に適用)
移植元 agent 本文は cwd=skill root 前提の相対パスを持つ。新プラグインでは以下に書換える:
- ヘッダの `> 相対パス: .claude/skills/presentation-slide-generator/agents/X.md` → `> 相対パス: $CLAUDE_PLUGIN_ROOT/agents/X.md`
- node 起動 `node scripts/<f>.cjs|.js …` → `node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/<f>.cjs|.js" …`
- 単独の `scripts/<f>` 参照 (backtick 含む) → `vendor/scripts/<f>`
- example fixture `schemas/example*.json` → `vendor/schemas-fixtures/example*.json`
- `references/<f>.md` は **書換不要** (plugins/.../references/ に実在)。
- `schemas/<真schema>.json` (structure/image-deck-plan/evaluation-report/image-asset-manifest) は **書換不要** (plugins/.../schemas/ に実在)。
- `プロジェクトID: presentation-slide-generator / agent: X` → `slide-report-generator / agent: X`。
本文の設計内容 (7層) は**削らない (平均回帰禁止)**。パスと mode 追記以外は byte 相当を保つ。

## D. output_mode 分岐契約 (C2 の焼き先)
- **共有 (単一 SSOT・mode で重複させない)**: 意匠/技術層 = Kanagawa 配色 / 16:9 / 最小 1.4rem / GSAP / インライン SVG2 / 印刷 CSS / letterbox / Codex Image2 / style genome / 決定論レンダラ / theme・aiVisual schema $defs。
- **mode 別 (コンテンツ意図層のみ分岐)**:
  - `slide`: 1スライド1メッセージ / chip 強制 / 長文禁止 (BP11-13) / 16:9 / 97 slideType / structure.schema.json。
  - `report`: 読み物 (文章多め可) / セクション+段落 / 1項目1ビジュアル最適化 / HTML レポート / 4 reportType / report-structure.schema.json。
- **確定点**: hearing-facilitator (C04) が `output_mode` と (report 時) `reportType/読者/長さ/ビジュアル方針` を確定 → 主 skill (C01) が下流へ一貫伝播 → `validate-output-mode.py` (C23) が送信前に値域検証。
- **reportType enum (4)**: `internal-analysis` (社内報告分析: 要約→背景→現状分析→所見→次アクション) / `client-proposal` (顧客提案WP: 課題→解決策→効果実績→導入ステップ→CTA) / `tech-doc` (技術ドキュメント: 概要→前提→手順構造→注意点→参照) / `learning` (学習解説: 問い→核心概念→図解理解→例応用→まとめ)。

## E. report-structure.schema.json 設計 (C17 の型・C3)
- `$id: report-structure.schema.json`、structure.schema.json と**共通コア $defs を共有**: `theme`(kanagawa-lotus 固定)/`aiVisualSpec`/`diagramNode`/`diagramEdge`/`diagramGroup`/`colorVar`/`accentColorEnum`/`fontAwesomeIcon` を同一定義で持つ (コピーで良いが構造キーは一致させる)。
- slide の `slides[]` に対応する report の主配列 = `sections[]`。各 section:
  - `id`, `heading`, `reportType`(4 enum・meta 側でも可), `paragraphs[]` (読み物本文・markdown 可), `visual` (**1項目1ビジュアル**: `{ kind: "svg"|"mermaid"|"codex-image"|"none", spec }` = visual-strategist の三択結果), `readingOrder`, `focalPoint` 任意。
- `required`: `meta`, `theme`, `sections`。`meta.reportType` (4 enum) 必須。`additionalProperties:false`。
- JSON として valid (draft-07 or 2020-12・structure.schema.json と同じ $schema を踏襲)。

## F. 新規 Node renderer 契約 (C19 owner・render-report.js / mermaid-render.js)
- 実行: `node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/render-report.js" <report-structure.json> <out.html>` で **report.html を決定論生成**。
- 既存 vendor primitives を再利用する (新規発明しない): `vendor/scripts/template-engine.cjs` / `style-builder.cjs` / `svg-builder.cjs` の共有意匠トークンを流用し、report は section+段落+1ビジュアルの読み物レイアウトへ射影。CommonJS (`require`) で vendored .cjs を読める形にする。
- `mermaid-render.js`: Mermaid 定義文字列を受け取り SVG/HTML 片へ変換 (mermaid CLI/lib があれば利用、無ければ `<pre class="mermaid">` フォールバック埋込を決定論生成)。依存を足す場合は package.json/package-lock.json に additive 追記。
- **最小テスト (tests_min≥80 相当)**: `vendor/tests/` に、サンプル report-structure.json を食わせて (1) 例外なく HTML を吐く (2) 出力に必須要素 (`<!DOCTYPE html>`, section heading, theme CSS var) が含まれる、を node で検証するテストを置く。実際に node で走らせて PASS を確認する。
- Kanagawa テーマ / 16:9 は slide 固有。report は A4/レター読み物レイアウト (縦スクロール HTML) で良い。意匠トークン (配色・フォント・最小サイズ) は共有。

## G. skill (C01-C03) 著述契約
- 各 `skills/<name>/SKILL.md` は frontmatter (`name`,`description`,`kind: run`/`skill`,`version`,`allowed-tools`,`user-invocable`) + 7 層本文。
- **C01 run-slide-report-generate**: 主オーケストレータ。R1 hearing(C04)→ mode 確定 → R2 structure/report-structure 設計(C05 or C17)+ 仕様確定ゲート(C06)→ R3 生成(C09 html / C10 render-slide.cjs / C19 report-composer+render-report.js / C14 Codex 画像)+ 生成後評価(C13 deck-evaluator mode-aware)。combinators: with-goal-seek(max_loops 5) + with-feedback-contract。feedback_contract.criteria は inventory の IN1/OUT1 を焼く (purpose-acceptance・汎用言い換え禁止)。deterministic_checks に validate-output-mode.py と vendored validator を列挙。
- **C02 run-slide-report-modify**: 既存成果物 (slide deck/report) の局所修正。worker=C15 slide-report-modifier。独立起動。
- **C03 run-cross-deck-review**: シリーズ横断整合検証。worker=C16 cross-deck-reviewer。独立起動。
- 参照する agent は **name で参照** (ファイル依存なし)。vendor script は `$CLAUDE_PLUGIN_ROOT/vendor/scripts/…` で参照。

## H. hook / command / script 契約
- **C20 hook-postgen-eval.py**: PostToolUse(Write|Edit|MultiEdit) で deck/report 中核ファイル (index.html/report.html/styles.css/scripts.js/structure.*/report-structure.*) の書込を検知 → **mode 判定** (index.html=slide / report.html=report) → 生成後評価 (deck-evaluator) 起動を促す。移植元 `vendor/scripts/hooks/deck-postgen-hook.js` のロジックを Python stdlib で mode-aware 移植。**fail-closed でなく fail-soft** (評価は非ブロッキング推奨・誤爆で通常編集を妨げない)。exit code と JSON 出力は Claude Code hook 仕様準拠。matcher 外/対象外ファイルは exit 0 で即 return。
- **C21 slide-report-generate.md** (command): `--mode slide|report` で生成を手動起動。frontmatter: `name`,`description`,`argument-hint`,`allowed-tools`,`disable-model-invocation:false`。run-slide-report-generate skill を呼ぶ。
- **C22 slide-report-status.md** (command): 進行状況/フェーズ確認 (vendor workflow-manager.js 相当)。`node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/workflow-manager.js" <dir> --check --next` を案内。
- **C23 validate-output-mode.py**: stdlib のみ。`--mode slide|report`, `--report-type <enum>` を検証し値域外は exit 2。`--preflight` で node/npm/node_modules/codex CLI 検出 (無くても preflight は warning、mode 検証は fail-closed)。CLI と import 両対応。`tests/test_validate_output_mode.py` (pytest) を同梱し全ケース PASS。

## I. 品質・非破壊原則
- vendor/ 配下の既存 byte は**書換禁止** (parity 対象)。追加は render-report.js/mermaid-render.js/tests/ と package*.json への additive のみ。
- 平均回帰禁止: port は 7 層本文を削らない。
- portability: 全ての実行パスは `$CLAUDE_PLUGIN_ROOT` 起点 (repo-root ハードコード禁止)。
- 出力言語: 日本語 (agent/skill 本文)。
