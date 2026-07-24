# slide-report-generator

presentation-slide-generator v8.4.2 の全機能を移植した共通コア + `output_mode = slide | report` の 2 モード・ビジュアル生成ハーネス。意匠/技術層 (Kanagawa 配色 / 16:9 / GSAP / インライン SVG2 / Codex Image2 / 決定論レンダラ / A4 印刷 / style genome) を**単一 SSOT で共有**し、コンテンツ意図層のみ mode 別に分岐する。

- **slide モード**: 1スライド1メッセージ / chip 強制 / 長文禁止 (BP11-13) / 16:9 / 97 slideType。
- **report モード**: 読み物 (文章多め可) / セクション+段落 / 1項目1ビジュアル最適化 / 4 reportType / Mermaid 統合。**report-structure 1.2.0 で「情報の羅列」→「構造化された読み物」へ**: 節内論理展開 (`section.narrative` = 本質課題→解決→活用) / 文書アーク (`meta.throughLine`) / 構造化本文ブロック (`section.body[]` = 表・コードブロック・番号リスト・小見出し・キーポイント強調ボックス・統計タイル・callout・引用・定義リスト・脚注引用・タスクリスト) / 色覚非依存の要点強調 / 図解の意味的配置 (`placement.grid` / `emphasisZone` / `readingOrder`) / 図表番号・目次 (`meta.toc`) を `render-report.js` が決定論 HTML 化する。既存 `paragraphs[]` は後方互換で温存 (body[] 優先)。設計指針の正本は [`references/report-narrative-logic.md`](references/report-narrative-logic.md)、golden 例は [`skills/run-slide-report-generate/examples/report-structured-120-example.json`](skills/run-slide-report-generate/examples/report-structured-120-example.json)。品質は `validate-report-visual.py` と report-quality-checklist RQ21-34 (積極評価。1.3.0 読者中心の入口設計=入口ホリゾンタル・中身バーティカルを含む) が担う。

Node 製レンダリング/画像/印刷/検証エンジンは `vendor/` に **byte 携行** し、skill/agent から `Bash(node *)` で起動する (Python-stdlib へ書き換えない = 既存資産の毀損回避)。

## 構成

| surface | 実体 |
|---|---|
| skills | `run-slide-report-generate` (主オーケストレータ) / `run-slide-report-modify` / `run-cross-deck-review` |
| agents | 17 thin Task adapters (詳細 7 層 prompt は各 owner skill の `prompts/R*.md`) |
| commands | `/slide-report-generate` / `/slide-report-status` |
| hooks | `hook-postgen-eval.py` (PostToolUse・生成後評価の自動起動・fail-soft) |
| scripts | 6 plugin-root scripts: `validate-output-mode.py` / `lint-vendor-parity.py` / `validate-plugin-completeness.py` / `lint-reference-attribution.py` / `validate-report-visual.py` / `lint-contract-drift.py` |
| schemas | `structure.schema.json` (slide) / `report-structure.schema.json` (report・共通コア共有) ほか |
| references | 42 upstream + report 新規 5 (report-types / report-writing-rules / report-visual-strategy / mermaid-integration / report-narrative-logic) |
| vendor | Node engine 一式 (191 files byte 携行: 真 schema 4本は plugin-root `schemas/` live SSOT) + report 新規 Node 2 (render-report.js / mermaid-render.js) |

## 使い方 (概要)

```
/slide-report-generate --mode slide  <topic>     # HTML スライド生成
/slide-report-generate --mode report --report-type internal-analysis <topic>   # HTML レポート生成
/slide-report-status <project-dir>               # 進行状況/フェーズ確認
```

`run-slide-report-generate` skill が hearing → 構成設計 → 仕様確定ゲート → 生成 (HTML / 決定論 render-slide.cjs / Codex 画像 / report render-report.js) → 生成後評価 (deck-evaluator・30種思考法・mode-aware) を駆動する。

## 初回セットアップ

Node engine は `vendor/` に携行済み。初回は次の1コマンドで、lockfileどおりの `node_modules` とOS/CPUに合うChromiumをプラグイン内へ復元する:

```bash
python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/setup-playwright.py" --install
python3 "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-output-mode.py" --preflight
```

Chromium は platform-specific のためgitには固定同梱せず、インストール先ごとに `vendor/playwright-browsers/` へ取得する。`vendor/package.json` の `postinstall` も同じinstallerを呼ぶため、`vendor/` で `npm ci` した場合もglobal Playwright cacheへは保存しない。runtimeは自身のファイル位置からplugin rootを解決するため、install先の絶対パスに依存しない。

`vendor/package.json` / lockfile とPlaywright runtimeは additive semantic gate、upstream vendor本体はsha256 pinで検証する。検証の正本は `EVALS.json` の `harness.mechanical[]` と下記の品質コマンド。

Mermaid は runtime 依存を増やさず、`mermaid-render.js` が CDN 初期化 + `<pre class="mermaid">` fallback を出力する。オフラインでは図が SVG 化されない場合があるが、定義テキストは可読な fallback として残る。

## reportType (report モード 4 骨格)

| reportType | 骨格 |
|---|---|
| `internal-analysis` | 要約 → 背景 → 現状分析 → 所見 → 次アクション |
| `client-proposal` | 課題 → 解決策 → 効果実績 → 導入ステップ → CTA |
| `tech-doc` | 概要 → 前提 → 手順構造 → 注意点 → 参照 |
| `learning` | 問い → 核心概念 → 図解理解 → 例応用 → まとめ |

## 品質・再現性

- **vendor byte-parity**: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/lint-vendor-parity.py"` が `vendor/vendor-digest-manifest.json` (191 files sha256 pin) と照合する。runtime schema は重複を避けて plugin-root `schemas/` を live SSOT にし、vendor parity では example fixtures + README のみを固定する。
- **plugin completeness**: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-plugin-completeness.py"` が manifest 名・entry_points・hook 実体・必須 surface を検証する。
- **mode 検証**: `validate-output-mode.py` が `output_mode`/`reportType` の値域を fail-closed 検証。
- **生成後評価**: `hook-postgen-eval.py` が deck/report 中核ファイル書込を検知し deck-evaluator を mode 判定つきで起動を促す。
- **改善要望ループ**: `run-skill-feedback`（`skills/run-skill-feedback` は harness-creator の SSOT へ向く任意 symlink adapter）で本プラグインの skill への改善要望を起票・集約できる。これは本プラグイン所有の entry point ではないため、handoff routes / `plugin-composition.yaml` / `.claude-plugin/plugin.json` には含めない。

`distributable: false` (社内専用・marketplace/bundle 非登録)。

## ドキュメントとリリース状態

このプラグインは `plugin-plans/slide-report-generator/` の L3 計画から、ユーザー指示により実体 build まで進めたローカル plugin 版。公開 marketplace / bundle / PR 配布は非スコープで、release 判定は local plugin としての manifest・composition・EVALS・vendor parity・mechanical tests の PASS を基準にする。

中学生向けに言うと、slide は「発表用の1枚ずつの紙」、report は「読み物のレポート」。どちらも同じ色・部品・描画エンジンを使い、内容の組み立て方だけを `output_mode` で切り替える。
