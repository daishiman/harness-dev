# リファレンス実装(構造・UX規律は発注者検収済み・2026-07 / 配色は暫定v0.2・未検収)

このフォルダは、2026-07に発注者検収済みの画面構造・操作・UX規律を実装した動く参照。配色は別契約で、平賀暫定カラーv0.2(`../hiraga/hiraga-color-system.css`)を使用しているが、正式CI色としては未承認・未検収。新しいアプリでは構造とクラス設計を流用し、配色の承認状態はT2の `brand_color_*` へ別に記録する。

## ファイルマップ

| ファイル | 何の見本か |
|---|---|
| `styles.css` | 部品CSSの正本(色の値は持たない)。平賀カラーCSSを `@import` し、役割トークンだけで組んだ全コンポーネント。system-first書体・44px操作領域・機能層のLiquid Glass・標準materialの内容面・reduced-transparency/contrast/motion・印刷fallbackを含む |
| `index.html` | 平賀カラー(既定・ライトのみ)。3項目なので上部ナビを採用。ホーム・一括選択・確認モーダル・下書き・レポートを実装 |
| `app.js` | **UX規律のvanilla実装**。イミュータブルstate・Excel数値整形(Intl)・一括送信(進捗/部分成功/要確認キュー/再試行)・下書き自動保存(debounce/復元通知/破棄/送信時削除)・blur検証+入力中解除・IMEガード・Enter=次フィールド/⌘⌃Enter=送信・全角正規化・トースト(成功自動消滅/エラー残留+アクション) |
| `reference-interactions.js` | catalog / Pop 共通の操作helper。選択、矢印・Enter・Space、現在地とpanel、開閉、短い結果、validation/clear、表sort/filterのARIAと表示状態を同期する |
| `catalog.html` | 部品カタログ。`styles.css`・平賀CSS・`reference-interactions.js` を埋め込んだ単独ファイル(`node scripts/inline-catalog-css.mjs` の生成物。手で編集しない)。外部書体へ依存せず、見出し・ラベル・値・状態・エラーだけで動く見本を示す |
| `catalog-default-profile.json` | build / improve が共通利用する版付き既定profile。適用種別、生成物、v0/v1検査を機械可読に定義 |
| `pop.html` | モードB(Pop・親しみ)。利用者が明示指定した場合だけ使う。パステル変換トークン・マスコット2バージョンの配置・黒太字+傾きの見出し・波線下線・くるっと矢印(確定版)・CTA(ブライト+白字+リング)・白グリフのカスタムチェックボックス・調整ボタン+セグメント・破線機能カード・波フッター |
| `mascot-bordered.svg` / `mascot-borderless.svg` | マスコットの再着色済み2バージョン(原本は `../pop-mascot-editable.svg`) |

## 既定適用

指定なしの可視Web UIは `references/catalog-default-contract.md` を唯一の入口にし、`scripts/catalog-default.mjs` の plan → apply → verify で正本資産と証跡を生成する。新規は既定でapply、既存は適用資格が確定するまでreport-only。v1は `scripts/catalog-runtime-audit.mjs` が生成先そのものを4幅・実操作で検査した証拠だけを受理する。ここにあるHTMLの説明文・架空データ・デバッグ注記は生成先へコピーしない。

## React / TypeScript への移植ルール

構造・クラス名・数値をそのまま持ち込む。フレームワークが変わっても見た目とふるまいの正解はこのフォルダ。

参照HTMLの説明文・架空の物件名や顧客名・デバッグ注記はコピーしない。画面の可視文言は対象業務の資料から作り、境界は `references/information-design.md` §3-1を正本とする。開発者向け情報はMarkdown、HTMLコメント、検査に残す。

1. トークン: 配置先・読み込み順は `references/catalog-default-contract.md`(`scripts/catalog-default.mjs apply` が配置する。手でコピー・書き換え・JS定数への複製をしない)。Tailwind v4の橋渡しは `references/hiraga-color-system.md` §3。ライトのみ(INV-15)。
2. クラス→コンポーネント対応(propsは最小限に):
   - `.btn.btn-primary/secondary/tertiary/danger-outline` → `<Button variant>`(primaryはアクセント色で1画面1つ。secondaryは白+紺枠。実行中は幅固定で「送信中…」+spinner)
   - `.badge.badge-*` → `<StatusBadge status>`(status-*トークン。必ず文言+記号+border)
   - `.field`(label上置き+error-msg) → `<Field>`(エラーはblurで判定・入力中に解除。常設の補足説明は移植しない)
   - `.num / .num-display / .num-sep / .currency / .unit` → `<Num value unit currency display?>`(整形は `Intl.NumberFormat('ja-JP')`+カンマを`<span class="num-sep">`置換)
   - 選択バー / `.deal-card` / `.empty-state` / `.skeleton` / `.kbd` → 同名コンポーネント
   - モーダル(フォーカストラップ・ESC・復帰) / トースト(aria-live) → `app.js` の挙動をそのまま移植
   - Pop: `.pop-cta` `.pop-chip` `.segmented` `.tune-btn` `.mascot-img`
3. 状態ロジック: `app.js` の各関数が仕様。React版のhooks(useDraft / useBulkSelection / useSubmitKeys / runWithConcurrency 等)は Skill ux-design の `assets/ux-patterns.tsx` を使う。
4. モーション: `motion-a11y.md` の時間表を使い、hover/pressed/入場/overlay/loadingを意味のある対象だけへ実装する。再レンダーのたびに入場させない。
5. 検証: 移植後も検収チェックリスト(4幅・hover/touch・reduced-motion・forced-colors・動的パス操作)と `node scripts/check-hiraga-contrast.mjs` を必ず通す。

## 手動移植が必要な場合

CLIがCSS入口を検出できないframeworkだけ `--entry-css=<relative-path>` を指定する。業務DOMと操作は該当部品を開いて移植し、`design-profile.json` の `adopted_components` と `exceptions` へ記録する。CSSの手動複製やprofileの手書きはしない。
