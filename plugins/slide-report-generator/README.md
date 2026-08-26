# slide-report-generator

presentation-slide-generator v8.4.2 の全機能を移植した共通コア + `output_mode = slide | report` の 2 モード・ビジュアル生成ハーネス。意匠/技術層 (style genome の palette 定義に従う配色 / 16:9 / GSAP / インライン SVG2 / Codex Image2 / 決定論レンダラ / A4 印刷 / style genome) を**単一 SSOT で共有**し、コンテンツ意図層のみ mode 別に分岐する。

- **slide モード**: 1スライド1メッセージ / chip 強制 / 長文禁止 (BP11-13) / 16:9 / <!-- count: slideType -->107 slideType。
- **report モード**: 読み物 (文章多め可) / セクション+段落 / 1項目1ビジュアル最適化 / 4 reportType / Mermaid 統合。**report-structure 1.2.0 で「情報の羅列」→「構造化された読み物」へ**: 節内論理展開 (`section.narrative` = 本質課題→解決→活用) / 文書アーク (`meta.throughLine`) / 構造化本文ブロック (`section.body[]` = 表・コードブロック・番号リスト・小見出し・キーポイント強調ボックス・統計タイル・callout・引用・定義リスト・脚注引用・タスクリスト) / 色覚非依存の要点強調 / 図解の意味的配置 (`placement.grid` / `emphasisZone` / `readingOrder`) / 図表番号・目次 (`meta.toc`) を `render-report.js` が決定論 HTML 化する。既存 `paragraphs[]` は後方互換で温存 (body[] 優先)。設計指針の正本は [`references/report-narrative-logic.md`](references/report-narrative-logic.md)、golden 例は [`skills/run-slide-report-generate/examples/report-structured-120-example.json`](skills/run-slide-report-generate/examples/report-structured-120-example.json)。品質は `validate-report-visual.py` と report-quality-checklist RQ21-34 (積極評価。reader-entry 読者中心の入口設計=入口ホリゾンタル・中身バーティカルを含む) が担う。

Node 製レンダリング/画像/印刷/検証エンジンは `vendor/` に **byte 携行** し、skill/agent から `Bash(node *)` で起動する (Python-stdlib へ書き換えない = 既存資産の毀損回避)。

## 構成

| surface | 実体 |
|---|---|
| skills | エントリポイント集合は `references/package-contract.json` が正本。生成の主オーケストレータは `run-slide-report-generate` |
| agents | thin Task adapters。集合は `references/package-contract.json` が正本で、詳細 7 層 prompt は各 owner skill の `prompts/R*.md` |
| commands | `/slide-report-generate` / `/slide-report-status` |
| hooks | `hook-postgen-eval.py` (PostToolUse・最小guard・成果物提示・利用者選択を促すadvisory・fail-soft) |
| scripts | 主要な plugin-root scripts: `validate-output-mode.py` / `lint-vendor-parity.py` / `validate-plugin-completeness.py` / `lint-reference-attribution.py` / `validate-report-visual.py` / `lint-contract-drift.py` / `lint-count-parity.py` (散文の数詞 ↔ 正本の実測値。件数は `ls scripts/` が正本なのでここに書かない) |
| schemas | `structure.schema.json` (slide) / `report-structure.schema.json` (report・共通コア共有) ほか |
| references | 共通設計・slide/report 固有設計・配布契約。実体集合は `references/` 直下が正本 |
| vendor | Node engine の byte 携行本体（対象集合と件数は `vendor/vendor-digest-manifest.json` が正本。真 schema は plugin-root `schemas/` live SSOT）+ report runtime |

## 使い方 (概要)

```
/slide-report-generate --mode slide  <topic>     # HTML スライド生成
/slide-report-generate --mode report --report-type internal-analysis <topic>   # HTML レポート生成
/slide-report-status <project-dir>               # 進行状況/フェーズ確認
```

`run-slide-report-generate` skill がまず生成 (HTML / 決定論 render-slide.cjs / Codex 画像 / report render-report.js) → 最小guard → 現物提示 → 利用者選択を完了する。`light / standard / detailed` が選ばれた場合だけ、hearing・構成設計・仕様確定ゲート・生成後評価 (deck-evaluator・30種思考法・mode-aware) を選択範囲で駆動する。`accept-as-is` は evaluator 0 / improver 0 でhandoffを終え、release/exhaustiveは別の明示eventを必要とする。

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

- **vendor integrity**: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/lint-vendor-parity.py"` が `vendor/vendor-digest-manifest.json` と照合する。承認済み base snapshot は sha256 pin、明示local overlayは semantic contract + tests/goldens で検証する。runtime schema は重複を避けて plugin-root `schemas/` を live SSOT にする。
- **plugin completeness**: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-plugin-completeness.py"` が native manifest の名前と hook 参照、`references/package-contract.json` の entry point/配布契約、および必須 surface のディスク実体を照合する。
- **mode 検証**: `validate-output-mode.py` が `output_mode`/`reportType` の値域を fail-closed 検証。
- **生成後advisory**: `hook-postgen-eval.py` は deck/report 中核ファイル書込を検知し、実HTMLの UTF-8 open / HTML parse / 空・NUL破損 / secret だけを検査する。子プロセスや deck-evaluator は起動せず、成果物の提示と `accept-as-is / light / standard / detailed` の選択を促す。semantic evaluatorは改善レベル選択後だけ起動する。
- **改善要望ループ**: `run-skill-feedback`（`skills/run-skill-feedback` は harness-creator 所有の byte-identical vendored adapter）で本プラグインの skill への改善要望を起票・集約できる。配布上は `references/package-contract.json` の entry point/runtime dependency に明示するが、所有権は harness-creator にあり、本プラグイン固有の handoff route としては扱わない。

配布契約の正本は `references/package-contract.json`。本 plugin は `distributable: true` で
marketplace と `skills-full` bundle から配布し、entry point・依存・配布先を native manifest に重複記述しない。

## ドキュメントとリリース状態

このプラグインは `plugin-plans/slide-report-generator/` の L3 計画から実体 build まで反映済み。配布対象と配布先は `references/package-contract.json` だけで宣言し、release 判定は manifest・composition・EVALS・vendor parity・mechanical tests の PASS を基準にする。

中学生向けに言うと、slide は「発表用の1枚ずつの紙」、report は「読み物のレポート」。どちらも同じ色・部品・描画エンジンを使い、内容の組み立て方だけを `output_mode` で切り替える。
