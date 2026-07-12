# Phase 11 — 視覚的検証 (Apple UI/UX エンジニア視点)

> 実プラグインの vendored Node engine で slide/report を実 HTML 生成し、headless Chromium (playwright) でスクリーンショット撮影。両モードの意匠共有と mode 別コンテンツ規律を目視検証する。

## 成果物 (outputs/phase-11/)
| モード | 入力 | レンダラ | HTML | スクリーンショット |
|---|---|---|---|---|
| slide | vendor/schemas-fixtures/example.structure.json | `render-slide.cjs` (vendor・決定論) | slide/index.html (8316B) | screenshots/slide-01.png (2560×1440 = 16:9 @2x) |
| report | vendor/tests/sample-report-structure.json | `render-report.js` (新規・決定論) | report/report.html (16886B) | screenshots/report-full.png (1800×6582 フルページ) |

## slide モード検証 (slide-01.png)
- **レイアウトの一貫性/整列**: 16:9 厳守。ヒーロータイトル「AIで仕事を再発明する」が左揃えで大型、サブタイトルが直下に階層的配置。上部にセクションナビ(オープニング/現状報告/クロージング)、右上にページ番号 1/5、下部にページドット + 前後ナビ。✅
- **タイポグラフィ**: 日本語見出しが超大型ウェイト、本文と明確なコントラスト比。Noto Sans JP。最小サイズ規律(1.4rem 相当)維持。✅
- **カラー/コントラスト**: Kanagawa の青→紫グラデ背景に白系文字。WCAG 上コントラスト良好。✅
- **1スライド1メッセージ**: タイトルスライドとして1メッセージに集中、長文なし(BP11-13 準拠)。✅

## report モード検証 (report-full.png)
- **読み物レイアウト**: A4 縦・縦スクロール。タイトル→サブタイトル→keyMessage コールアウト→reportType バッジ「社内報告分析」+読者→本文。5 section(要約/背景/現状分析/所見/次アクション)が internal-analysis 骨格順に並ぶ。✅
- **1項目1ビジュアル**: 各 section が最大1ビジュアル。背景=SVG flow 図(3ノード)、現状分析=**Mermaid フローチャート(実描画・受信→自動分類→系統判定→3キュー)**、所見=Codex 画像参照、次アクション=SVG cycle 図(4ノード循環)。要約は none(文章のみ)。✅
- **意匠共有の確認 (C2 核心)**: slide と同一の Kanagawa アクセント・フォント・最小サイズ・letterbox なしの読み物射影。意匠トークンは vendored `style-builder.cjs` SPEC の単一 SSOT を流用しており、slide/report で色/フォントが視覚的に一致。✅
- **タイポグラフィ/強調**: 段落内の `**40%**`/`**92%**`/`**自動分類**` がアクセント色 strong で描画。見出しは左アクセントボーダー。可読性(report rubric 次元)良好。✅
- **文章多め (BP緩和)**: slide の1メッセージ/chip 強制を緩和し、section あたり複数段落の読み物。report content-regime 準拠。✅

## Apple UI/UX 観点の指摘
| 観点 | 評価 | 備考 |
|---|---|---|
| レイアウト一貫性・整列 | ◎ | 両モードで余白・整列が規律的。report の section 間リズムが均一 |
| タイポグラフィ | ◎ | 階層・ウェイト・最小サイズが明確 |
| カラーコントラスト/アクセシビリティ | ○ | Kanagawa 高コントラスト。全 visual に alt/aria-label 付与(schema 必須) |
| インタラクションの直感性 | ○ | slide のナビ/ページドット、report の Mermaid 実描画が機能 |
| レスポンシブ/印刷品質 | ○ | report は @page A4 portrait・break-inside:avoid 実装 |

## 既知の許容事項
- report の「所見」section の Codex 画像は `images/support-heatmap.png` 参照のため、実 PNG 未生成のサンプルでは broken-image + alt テキスト表示。これは**設計通り**(実運用では ai-image-diagram-producer が Codex Image2 で PNG を生成・回収する)。サンプル/テストは参照契約の検証が目的。
- Mermaid は CDN(jsdelivr mermaid@11)初期化でクライアント描画。オフライン/CDN 不通時は `<pre class="mermaid">` + fallback テキストへ decay(可読性担保)。

## 判定
両モードが**共有意匠 SSOT の上で mode 別コンテンツ規律を保ったまま実 HTML を生成**できることを目視で確認。C2(mode 分岐)/C3(report 4骨格・visual 三択・Mermaid)/C5(vendor Node engine 起動)の受入を視覚的に満たす。**PASS**。

## 現ビルド追随検証 (2026-07-11 update)

> **注記**: 上記 v1 検証の `report-full.png` (1800×6582) は v1 サンプルであり、下記の第3次UI/図解刷新を反映する **前** のレンダリングである。第3次UI 後の証跡は本セッションの before/after スクリーンショットで別途取得している。以下は検証済みの事実のみを追記する (解像度/サイズの発明なし)。

### 第3次 UI/UX (C16-C18・render-report.js buildReportCss)
- **screen/print 二層 CSS**: screen=本文可読幅+sidebar grid、print=190mm/A4 を `@media print` で温存。
- **sticky sidebar TOC + scrollspy**: IntersectionObserver 自己完結・print 無効・狭画面 900px でインライン TOC へ graceful degrade。scrollspy に aria-current 同期 + afterprint 復帰を追加。
- **タイポ密度是正**: `--fs-body` ≈17px [1.0625rem]・title/body 比 ≈1.93 (≤2.2)。

### 図解機構刷新 (本セッション)
- 全ブロック (callout/keypoint/narrative/throughline/stat/visual) の「左バー+背景ティント=吹き出し」を廃し、「白地フラットカード+上端3pxアクセント+余白リッチ padding」へ一括転換。
- 本文全幅化: `--report-page-max` 1240→1360px・`.report max-width:none`・プレーン段落のみ 78ch。
- **before/after スクリーンショット** (Chrome headless・wide 1500px / narrow 880px) で 5 指摘 (窮屈 / 吹き出し / 文字敷き詰め / 配色 / パワポ的簡潔) の解消を目視実証。

### essence-visual (C8/C19) の視覚証跡
- 本質図解は role 駆動: `validate-report-visual.py` の `_check_essence_visual` が role∈{分析/主張/課題/解決/所見/影響} の論理節に非none visual (`visual.kind!=none`) を要求。

### C25 実装トークン健在の実証
- `validate-report-visual.py` の `_check_uiux_shape` (screen 接合トークン .report-layout/--report-measure/--report-page-max・sticky TOC is-active・aria-current・before/afterprint・@media print .report 幅・狭画面 @media・grid minmax card・タイポ --fs-body 16-18px/title比≤2.2) を現行 report に実行=uiux-shape warn 0・exit0。full-render marker=`--report-width` でゲート。
