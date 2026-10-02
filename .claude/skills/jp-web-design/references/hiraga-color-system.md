# 平賀カラー — UI配色の既定正本(暫定)

INV-15: UIの配色は本書と `assets/hiraga/hiraga-color-system.css` の役割トークンを唯一の既定とする。Mode B(Pop)は利用者が明示指定した場合だけ使う。

## 0. 位置付けと正本の関係

- 平賀運送向けの暫定カラーデザイン。**版(バージョン番号・日付)の宣言は正本CSSの `@hiraga-meta` だけに置き、本書へ転記しない。** 根拠は制作会社が2020年に掲載した公式サイト制作事例画像と公式車両写真。現行サイトの全ページ実測でも、会社承認の正式CIカラーでもない。「公式HEX」「全ページ解析済み」と説明しない。
- 経緯(履歴。現行版の宣言ではない): 初版の灰青の地が「どんより見える」、続く淡い紫系の地も「淡い灰色に見える」との指摘を受け、画面背景を白にし、補助面・罫線・補助文字だけをごく淡いブランド色相へ寄せた。その後、紫・マゼンタ系の基本色をブルー系へ置き換え、アクセントの基本色トークンを `--p-brand-magenta*` から `--p-brand-accent*` へ改名した。いずれの版でも役割トークン名と役割の割り当ては変えていない。
- 正本の順位: `assets/hiraga/hiraga-color-system.css`(機械可読メタデータ・値・共通クラス) → 本書(使い方) → `assets/hiraga/hiraga-color-tokens.json` / standalone preview / catalog実測値(生成物)。
- 本書はHEXや比率を正本として持たない。値はCSS(版は `@hiraga-meta` の `version`)、ペアごとの比は `node scripts/check-hiraga-contrast.mjs` の出力が正。
- 正式CI色や承認済みロゴ素材が届いたら、基本色 `--p-*` だけを差し替える。役割トークン名と役割の割り当ては変えない。
- **色の値・版を変えるときの手順(1回の変更で適用先まで通す。正本はここ)**。次のコマンドはすべて `aidd-agent-kit/` を置いた親ディレクトリ(このリポジトリではリポジトリルート)で実行する。キット共通の更新は1〜5・8、6〜7は該当する適用先がある場合だけ行う:
  1. `aidd-agent-kit/skills/jp-web-design/assets/hiraga/hiraga-color-system.css` だけを編集する(値・`@hiraga-meta` の版)。他のファイルへHEXを書かない。
  2. `node aidd-agent-kit/skills/jp-web-design/scripts/export-hiraga-tokens.mjs` — `hiraga-color-tokens.json` と standalone preview を再生成する(生成物は手書きしない)。
  3. `node aidd-agent-kit/skills/jp-web-design/scripts/inline-catalog-css.mjs` — `assets/reference/catalog.html` の埋め込みを再生成する。
  4. `node aidd-agent-kit/skills/jp-web-design/scripts/check-hiraga-contrast.mjs` と `node aidd-agent-kit/skills/jp-web-design/scripts/check-token-references.mjs` — コントラストと未定義参照を検査する。ペア表に不足があれば足して通す。
  5. `node --test aidd-agent-kit/skills/jp-web-design/tests/` — 参照実装とスクリプトの回帰テストを通す。
  6. report-design-system を使う場合だけ、`node aidd-agent-kit/skills/report-design-system/scripts/sync-kit.mjs --kit aidd-agent-kit` で下流の vendor へ取り込み、同スキルの保守検査を通す。report-design-system がないキットでは不要。
  7. このリポジトリの project scope を更新する場合だけ、`bash aidd-agent-kit/sync-project-mac.command` で `.claude/` `.agents/` の同期コピーへ配布する(同期コピー側を直接編集しない)。
  8. 本書と `SKILL.md` の記述を追随させる。特に §1 の「現在の見え方」欄、§1 の面積比、トークン名の言及箇所。版番号は本文へ書かない(手順の外に出さない)。
- 旧既定(グラファイト×アンバー、Light/Dark/auto)は廃止した。「ライトのみ」「既存アプリは色だけ移行」は INV-15 の不変条件で、本書が詳細(§2-10・§9)の正本。

## 1. 配色の軸

値(HEX)は正本CSSと `assets/hiraga/hiraga-color-tokens.json` を見る。本書は「どのトークンが何の役割か」だけを決める。**規則の主語はトークン名で、色名ではない。**「現在の見え方」欄は今の値の説明にすぎず、規則の一部ではない(値が変われば欄だけを直す)。

| 基本色トークン | 役割 | 現在の見え方 |
|---|---|---|
| `--p-brand-indigo` | ブランドの軸。見出し・リンク・副ボタン・ナビの現在地/アイコン・グラフ主系列 | 濃いブルー |
| `--p-brand-accent` | 重要操作のアクセント。主ボタン・フォーカス・必須 | 明るいブルー |
| `--p-brand-vehicle-navy` | 車両を連想する補助色。基本パレットにだけ置き、役割トークンは未割当(使う場合は §8 の手順で追加) | 濃いネイビー |
| `--p-white` | ヘッダー・カード・表本文・入力欄 | 白 |
| `--p-canvas` | 画面の地。カードとの区切りは罫線 `border-subtle` と影で付ける | 白 |
| `--p-surface-subtle` | 補助面・表ヘッダー・hover(面を広く敷かない) | ほぼ白(ブランド色相寄り) |
| `--p-brand-accent-soft` | アクセント面 `surface-accent`・必須・分類タグ | 淡いブルー |

- ブランドの軸(`--p-brand-indigo`)と主操作のアクセント(`--p-brand-accent`)は別の役割。同じ色として扱わず、一方を他方の代わりに使わない。
- 面積の出発点(**本書が正本。`SKILL.md` は数値を持たず本書を参照する**): 地と面(`app-background` / `surface` / `surface-alt` / `surface-subtle`)75% / 文字・罫線・ナビの骨格(`text-*` / `border-*` / `nav-*`)20% / 操作と状態(`action-primary-*` / `status-*`)5%。サイトの実測比率ではない。
- グレー一色の管理画面、既定の青ボタンにロゴだけ載せた画面にしない。画面の地は `app-background`(白)。色付きの地を画面全体に敷かない。面・罫線・補助文字はブランドの色相で作り、無彩色の灰色(`#F5F5F5` `#E5E7EB` など)を足さない。
- `surface-accent`(アクセントの淡い面)は、お知らせ・注目カード・未完了の案内など、1画面1〜2か所の面だけに使う。文字は `text-primary` / `text-heading` にし、面を広げて背景全体に敷かない。

## 2. 適用ルール(12項目)

1. `hiraga-color-system.css` の役割トークンを使い、画面内へHEXを直接散在させない。
2. サイドナビとモバイル下部タブは、`nav-background` の半透明materialと本文色を共有する。ブランドの軸(`--p-brand-indigo`)は選択indicator・アイコン・ブランドの小面積アクセントに限り、選択項目は `nav-selected-bg` + `nav-selected-text` + `nav-selected-indicator` の細線(`aria-current`も付ける)。
3. 主操作は `--action-primary-bg` + `--action-primary-text`、副操作は `--action-secondary-bg` + `--action-secondary-text` + `--action-secondary-border`、破壊的操作だけ `--action-danger-*`。主操作は作業領域ごとに1つへ絞る。
4. 画面の地は `app-background`(白)、文字は `text-primary` / `text-secondary` / `text-muted`。Liquid Glassは装飾ではなく階層を伝える機能層として、浮遊ヘッダー、サイドナビ、下部タブ、モーダル、重要な操作へ限定する。iPhone-likeとする条件は、透明border + `padding-box` の半透明surface + `border-box` の非対称specular gradient、backdrop blur / saturate、上・左上の局所highlight、下側のごく薄いshade、soft shadowの光学構造とする。通常は均一な固いoutlineで囲まずsoftに保ち、selected / focus / invalid / errorなど意味状態だけindicatorを明確にする(「通常soft・状態時clear」)。文字のあるnav / controlはregular相当、背景が十分制御された小さなicon controlのみclear相当とし、関連iconとactionは同じglass capsule内にまとめる。hoverはrim / shineをわずかに上げ、pressedはshine / 浮きを下げる。ポインタ追従や常時エフェクトは追加しない。通常の表・フォーム・データカードは不透明〜高不透明の `surface` + 低主張の `border-subtle` + `shadow-soft` とし、内容を主役にする。背景の淡いambient lightで透明感を保つが、サイドナビと下部タブは同じ `nav-background` のmaterialを使い、`--action-primary-bg` や意味色(`--status-*`)を混ぜない。ブランドの軸(`--p-brand-indigo`)は現在地・アイコン・ブランドの小面積アクセントに限る。文字は実際の合成面で4.5:1、意味を伝える操作境界は3:1を確認する。`prefers-reduced-transparency` / `prefers-contrast: more` / `prefers-reduced-motion` / 印刷では不透明・単色・無動作へ戻す(上書きのため CSS の末尾に置く)。実装例は `assets/reference/styles.css`。
5. normal / hover / pressed / focus-visible / selected / disabled / readonly / loading / invalid を区別する。hoverだけで意味を伝えない。
6. エラー・警告・成功・情報(`status-{danger,warning,success,info}-*`)を意味色として分離し、淡色背景+文字+アイコンを併用する。アクセント(`--p-brand-accent` / `--action-primary-bg`)を意味色(`--status-danger-*` など)に流用しない。逆に意味色を主操作へ流用しない。
7. 濃色のナビ地にアクセント(`--p-brand-accent` / `--focus-ring`)の小さい文字・線を置かない(コントラスト検査の「避けるペア」)。濃色面上の文字は `text-inverse`、フォーカスリングは `focus-ring-inverse`。
8. 本文4.5:1以上、大きな文字と識別に必要な操作境界・状態表示は3:1以上を、実際の隣接色・合成色で確認する。色だけで選択・状態・必須・エラーを表さない。これだけでWCAG全体に適合済みとは説明しない。
9. グラフは主系列を `chart-main`、他は `chart-1〜5`。系列名・線種・マーカー・凡例・値を省略しない。
10. OSの強制カラーを妨げず、印刷では白黒でも状態名が読めるようにする。テーマはライトのみ。ダークモードを自動追加・自動反転しない。
11. LINEの緑など外部サービスの色、写真の空・植栽・道路や動画サムネイルの色をブランド主色に転用しない(外部サービスのボタン自体は各社ガイドラインの色のまま使う)。
12. 原ロゴを再着色・再生成しない。承認済み素材がなければロゴ風の図形を作らず、会社名を通常テキストで仮表示する。

範囲: 既存の業務要件・画面構成は維持し、色以外を再設計しない。配車・車両・勤怠などの業務機能をこの配色資料から確定させない。資料の画面例は配色検証用の架空データ。

## 3. 役割トークン(コンポーネントはこれだけを参照する)

| 群 | トークン |
|---|---|
| 画面・面 | `app-background` `surface` `surface-alt` `surface-hover` `surface-selected` `surface-accent` `shadow-soft` `shadow-raised` `overlay` |
| 文字 | `text-primary` `text-secondary` `text-muted` `text-heading` `text-inverse` |
| 線 | `border-subtle`(装飾) `border-control`(操作境界) |
| ナビ | `nav-background` `nav-text` `nav-text-muted` `nav-hover` `nav-selected-bg` `nav-selected-text` `nav-selected-indicator` |
| 操作 | `action-primary-{bg,text,hover,active}` `action-secondary-{bg,text,border,hover,active}` `action-quiet-{bg,text,hover}` `action-danger-{bg,text,hover,active}` `action-disabled-{bg,text,border}` |
| リンク・フォーカス | `link` `link-hover` `link-visited` `focus-ring` `focus-ring-inverse` `focus-gap` |
| フォーム | `input-{bg,text,placeholder,border,border-hover,border-focus,readonly-bg,invalid-border,invalid-message}` `required-{text,bg}` `control-on` `control-on-mark` `control-off-border` |
| 一覧 | `table-{head-bg,head-text,body-bg,stripe-bg,hover-bg,selected-bg,selected-indicator}` `tab-indicator` `tab-text-active` `pagination-active-{bg,text}` `tag-{bg,text}` `badge-unread-{bg,text}` |
| 状態 | `status-{neutral,info,success,warning,danger}-{text,bg}` |
| フィードバック | `tooltip-{bg,text}` `progress-{fill,track}` `skeleton-{base,highlight}` `selection-{bg,text}` |
| グラフ | `chart-main` `chart-1`〜`chart-5` `chart-grid` `chart-axis` `chart-threshold`、連続量は基本色 `p-scale-1`〜`p-scale-5` |

基本色 `--p-*` はコンポーネントから直接参照しない(連続量スケールだけ例外)。

### Tailwind v4 への橋渡し

読み込み順(framework import の後ろに正本CSS)と配置先は `catalog-default-contract.md` が正本。`@theme inline` は役割トークン名をそのまま `--color-<役割トークン名>` へ写し、別名を作らない(ユーティリティは `bg-app-background` `text-text-primary` `border-border-subtle` `bg-action-primary-bg` のようになる)。

```css
@theme inline {
  --color-app-background: var(--app-background); --color-surface: var(--surface); --color-surface-alt: var(--surface-alt);
  --color-surface-selected: var(--surface-selected); --color-surface-accent: var(--surface-accent);
  --color-text-primary: var(--text-primary); --color-text-secondary: var(--text-secondary); --color-text-muted: var(--text-muted);
  --color-text-heading: var(--text-heading); --color-text-inverse: var(--text-inverse);
  --color-border-subtle: var(--border-subtle); --color-border-control: var(--border-control); --color-input-border: var(--input-border);
  --color-nav-background: var(--nav-background);
  --color-action-primary-bg: var(--action-primary-bg); --color-action-primary-text: var(--action-primary-text); --color-action-primary-hover: var(--action-primary-hover);
  --color-link: var(--link); --color-focus-ring: var(--focus-ring);
  --color-status-info-text: var(--status-info-text); --color-status-info-bg: var(--status-info-bg);
  --color-status-success-text: var(--status-success-text); --color-status-success-bg: var(--status-success-bg);
  --color-status-warning-text: var(--status-warning-text); --color-status-warning-bg: var(--status-warning-bg);
  --color-status-danger-text: var(--status-danger-text); --color-status-danger-bg: var(--status-danger-bg);
}
```

足りない役割は同じ規則で1行追加する。

Tailwind既定の `slate/gray/blue/indigo-*` ユーティリティや、UIライブラリ・チャートの既定色を残さない。

## 4. 要素別の適用表(73項目)

業務機能を追加する要件ではない。システムに存在する要素へ適用する配色ルール。

| 分類 | 要素 | トークン・方針 | 注意点 |
|---|---|---|---|
| ブランド | ロゴ | 承認済みの元データ。濃色面では承認済み白版か白い台座 | 再着色・類似ロゴ生成をしない |
| ブランド | アプリ・ファビコン | `--p-brand-indigo` をベース、`--p-brand-accent` を少量 | 原ロゴの余白・色指定は別途確認 |
| 画面基盤 | 画面全体 | `app-background` | 白。グレーや色付きの地を全面に敷かない |
| 画面基盤 | ヘッダー | `surface` / `text-heading` | 本文を妨げない半透明〜高不透明の機能層 |
| 画面基盤 | サイドナビ・下部タブ通常 | `nav-background` / `nav-text` / `nav-text-muted` | `nav-background` のregular glass。両者で同じmaterialを使う |
| 画面基盤 | サイドナビ・下部タブhover | `nav-hover` / `nav-text` | rim / shineだけをわずかに上げる |
| 画面基盤 | サイドナビ・下部タブ選択 | `nav-selected-bg` / `nav-selected-text` / `nav-selected-indicator` | 淡い面+濃色文字+細い `nav-selected-indicator` 線+`aria-current` |
| 画面基盤 | 見出し・パンくず | `text-heading` / `text-secondary` / `link` | パンくずリンクは下線で識別 |
| 画面基盤 | カード・パネル | `surface` / `border-subtle` / `shadow-soft` | 薄い線を操作可能性の唯一の手掛かりにしない |
| 画面基盤 | 補足・折り畳み | `surface-alt` / `text-secondary` | 文字のコントラストを保つ |
| 画面基盤 | 罫線・区切り | `border-subtle` | 入力枠・必須の境界に流用しない |
| 画面基盤 | 影・浮遊領域 | `shadow-soft` / `shadow-raised` | 濃い黒影を多用しない |
| 操作 | 主ボタン | `action-primary-bg` / `action-primary-text` | 作業領域で最重要の操作に限定 |
| 操作 | 主ボタンhover・押下 | `action-primary-hover` / `action-primary-active` | それぞれ専用色 |
| 操作 | 副ボタン | `action-secondary-bg` / `-text` / `-border` | 白地+濃色文字・枠 |
| 操作 | 副ボタンhover・押下 | `action-secondary-hover` / `-active` | `action-primary-*` と同じ面積・同じ主張にしない |
| 操作 | テキストボタン・リンク | `action-quiet-text` / `link` / `link-hover` / `link-visited` | リンクは下線。訪問済みで意味を変えない |
| 操作 | 危険操作 | `action-danger-*` | 削除・取り消せない操作だけ。明確な動詞 |
| 操作 | 無効ボタン | `action-disabled-bg` / `-text` / `-border` | opacityで薄くせず、無効理由を表示 |
| 操作 | キーボードフォーカス | `focus-ring` / `focus-gap` | 白の分離帯+3pxリング。クリップ・被覆に注意 |
| 操作 | 暗背景フォーカス | `focus-ring-inverse` | 濃色面では専用トークン。`focus-ring` を流用しない |
| 操作 | ローディングボタン | `action-primary-bg` / `-text` | 白スピナー+「保存中」。二重送信防止はアプリ側 |
| フォーム | 入力欄通常 | `input-bg` / `input-text` / `input-border` | 入力枠は3:1以上 |
| フォーム | 入力欄hover・focus | `input-border-hover` / `input-border-focus` / `focus-ring` | エラーの赤枠をhoverで消さない |
| フォーム | ラベル・説明文 | `text-primary` / `text-secondary` | ラベルを常時表示 |
| フォーム | プレースホルダー | `input-placeholder` | ラベル代替にせず、薄すぎるグレーにしない |
| フォーム | 必須ラベル | `required-bg` / `required-text` | 「必須」の文字を添える |
| フォーム | 入力エラー | `input-invalid-border` / `input-invalid-message` / `status-danger-bg` | 赤枠+アイコン+具体的なメッセージ |
| フォーム | 読み取り専用 | `input-readonly-bg` / `input-text` | 無効と区別し、読めるコントラスト |
| フォーム | 無効入力 | `action-disabled-bg` / `-text` | 利用できない理由を文字で |
| フォーム | チェック・ラジオ | `control-on` / `control-on-mark` / `control-off-border` | 形状でも選択を示す |
| フォーム | スイッチ | 同上 | ON/OFFラベルとノブ位置を併用 |
| フォーム | セレクト・候補一覧 | `surface` / `surface-hover` / `surface-selected` / `text-primary` | 選択にチェック。focusとselectedを混同しない |
| フォーム | 検索・フィルター | `surface` / `input-border` / `tag-bg` / `tag-text` | 適用中は件数と解除ボタン |
| フォーム | 日付選択 | `surface` / `pagination-active-bg` / `-text` | 本日は枠、選択日は塗り |
| フォーム | アップロード | `surface-alt` / `border-control` / `focus-ring` / `status-danger-text` | ドロップ可能は点線+説明文 |
| 一覧 | 表ヘッダー | `table-head-bg` / `table-head-text` | ブランド色相のほぼ白の面+濃色文字 |
| 一覧 | 表本文・交互行 | `table-body-bg` / `table-stripe-bg` / `text-primary` | 強い縞模様にしない |
| 一覧 | 行hover | `table-hover-bg` | 選択状態と分離 |
| 一覧 | 選択行 | `table-selected-bg` / `table-selected-indicator` | 左線やチェックを併用 |
| 一覧 | ソート・フィルター適用 | `text-heading` / `tab-indicator` | 矢印の向き・条件ラベル |
| 一覧 | 固定列・固定ヘッダー | `surface` / `table-head-bg` / `shadow-soft` | 不透明な背景 |
| 一覧 | タブ | `tab-text-active` / `tab-indicator` / `text-secondary` | 下線+太字+`aria-selected` |
| 一覧 | ページネーション | `pagination-active-bg` / `-text` | 数値と`aria-current` |
| 一覧 | 分類タグ | `tag-bg` / `tag-text` | 状態タグと別体系 |
| 一覧 | 未読件数 | `badge-unread-bg` / `-text` | 障害表示と混同させない。ラベルを付ける |
| 状態 | 未処理・下書き | `status-neutral-*` | ブランド色相の淡い面と補助文字。無彩色の灰色にしない |
| 状態 | 情報・処理中 | `status-info-*` | 文字ラベル必須 |
| 状態 | 成功・完了 | `status-success-*` | チェックマーク+「完了」 |
| 状態 | 注意・遅延 | `status-warning-*` | 警告記号+内容。黄/橙地に白小文字を置かない |
| 状態 | 障害・エラー | `status-danger-*` | ×記号+内容。`action-primary-bg` をエラー色に流用しない |
| フィードバック | 通知・トースト | 該当する `status-*` | 保存成功と主ボタンの色は違ってよい |
| フィードバック | ツールチップ | `tooltip-bg` / `tooltip-text` | フォーカスでも表示 |
| フィードバック | 空データ | `surface-alt` / `text-heading` / `text-secondary` | 意味のある説明文 |
| フィードバック | スケルトン | `skeleton-base` / `skeleton-highlight` | アニメーションを止められる |
| フィードバック | 進捗バー | `progress-track` / `progress-fill` | 値・ラベルを併用 |
| 重ね合わせ | モーダル・ドロワー | `surface` / `text-primary` / `shadow-raised` | 実際の合成背景で検証 |
| 重ね合わせ | 背景マスク | `overlay` | 上に直接小さい文字を置かない |
| データ可視化 | 主指標・KPI | `text-heading` / `chart-main` | 好不調は状態色と文字を併用 |
| データ可視化 | カテゴリ系列 | `chart-1`〜`chart-5` | 名称・マーカー・線種を併用(色覚対応の認証済みではない) |
| データ可視化 | 連続量 | `p-scale-1`〜`p-scale-5` | 淡色セルは数値ラベルと境界 |
| データ可視化 | 目盛・軸・グリッド | `chart-axis` / `chart-grid` | 装飾線と情報線を区別 |
| データ可視化 | 閾値・異常線 | `chart-threshold` | 赤の破線+値・説明 |
| 業務表示例 | カレンダー・配車表・ガント | `surface` / 状態色 / `surface-selected` | 業務機能を要件化しない |
| 業務表示例 | 地図・位置マーカー | `chart-main` / 状態色 | 実地図との合成で検証。形状・ラベルで区別 |
| アカウント | ログイン・権限表示 | `nav-background` / `surface` / `action-primary-bg` / 状態色 | 権限は文字で説明 |
| 環境 | モバイル・タッチ | 通常・選択・focusトークン | hoverだけで意味を伝えない |
| 環境 | ダークモード | 本版では未定義 | 自動反転禁止。導入時は別トークンと再検証 |
| 環境 | 印刷・白黒帳票 | 白背景・黒文字・罫線・状態ラベル | 背景色が印刷されなくても意味が残る |
| 環境 | OS強制カラー | システムカラーを尊重 | `forced-color-adjust: none` で一括固定しない |
| 環境 | 選択文字 | `selection-bg` / `selection-text` | 可読性を維持 |
| 品質管理 | 追加画面・外部UI部品 | 全色を役割トークンへマッピング | 既定のslate/gray/blue・チャート既定色の残留を確認 |
| 品質管理 | 色の保守 | 基本色→役割色→部品の順で管理 | HEXを散在させない。変更後はコントラストを再計算 |

## 5. コントラスト(`node scripts/check-hiraga-contrast.mjs`)

比率の正本はスクリプトの出力(CSSの現在値から毎回計算)。本書へ数値を転記しない。スクリプトは次の3群を判定する。

- 本文 4.5:1 以上: 本文・補助・説明文字 × 白/補助面/選択面、主・副・危険・無効ボタン、ナビ、リンク、入力・プレースホルダー・エラー、表、タグ、状態 `status-*`、ツールチップ、選択文字。
- 非テキスト 3:1 以上: 入力枠 `input-border`、チェック枠・ON、フォーカス(白・淡色ナビ上)、進捗、グラフ系列、閾値線。
- 避けるペア(基準未満であるべき): 濃色のナビ地に `focus-ring` / `--p-brand-accent` の小文字、装飾罫線 `border-subtle` を入力境界に使う。

指定ペアの検証であり、実画面・合成色・全状態やWCAG全体の適合を保証しない。

## 6. 部品の色契約

ナビの選び方・幅・下部タブの寸法は `layout-responsive.md`「ナビゲーション骨格」が正本。ここでは色だけを決める: サイドバー・アイコンレール・下部タブは同じ `nav-background` のregular glass materialと`nav-*`状態を共有する。

- `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` と `<meta name="color-scheme" content="light">`。
- ナビの現在地: `nav-selected-text` +太字+ `nav-selected-indicator` の細線。文言と`aria-current`を主符号にする。
- 寸法(高さ44px以上・角丸)は `layout-responsive.md` と `components.md` に従う。
- 状態バッジ: `status-*-bg` + `status-*-text` + 記号 + 文言。色だけで示さない。
- 処理中: `status-info-*` +スピナー+「処理中」。専用のアクセント色を作らない。
- 入力: `input-bg`、`input-border`。ラベルをplaceholderで代替しない。
- カード: `surface` + `border-subtle` + `shadow-soft`。操作可能な場合だけhoverで `border-control`。カード左端の色帯は引き続き禁止(ナビ選択線・選択行の左線はカードではないので可)。
- 状態は `idle / hover / pressed / focus-visible / selected / disabled / readonly / loading / invalid / success / warning / empty` を同じ精度で設計する。
- AIを特別扱いしない。紫・ネオン・専用グラデーションを付けない(`p-chart-purple` はグラフ系列専用)。

## 7. アクセシビリティ・環境

- `:focus-visible` は `outline: 3px solid var(--focus-ring); outline-offset: 3px; box-shadow: 0 0 0 3px var(--focus-gap)`。暗いナビ内は `outline-color: var(--focus-ring-inverse); box-shadow: none`。
- `@media (forced-colors: active)`: フォーカスは `Highlight`、ボタン・状態バッジに `1px solid ButtonText`。
- `@media print`: 背景白・文字黒・カード黒枠・影なし、状態バッジは白地黒枠。
- `prefers-contrast: more`: `--border-subtle` を `--border-control` へ、`--text-muted` と `--text-secondary` を `--text-primary` へ引き上げる。
- `aria-disabled` だけでは操作は止まらない。アプリ側でイベントを抑止する。
- 375 / 768 / 1280 / 1600px、safe-area、キーボード、スクリーンリーダーで実測する。

## 8. トークンの追加と保守

1. 既存の役割トークンで表せないか先に確認する。
2. 必要なら基本色 `--p-*` → 役割トークン → 部品の順で CSS に追加し、追加理由を T2 に1行で記録する。
3. `node scripts/export-hiraga-tokens.mjs` で JSON を再生成し、`check-hiraga-contrast.mjs` のペア表にも追加して通す。
4. プロジェクト側でコピーした CSS を独自に書き換えない。キット側の正本を更新して再配布する。
5. 生成物の再生成・テスト・下流への配布・記述の追随は §0「色の値・版を変えるときの手順」の全項目を通す(トークン追加も値の変更と同じ手順)。

## 9. 既存アプリの自動移行(色だけ)

`/build-app` `/improve-app` の着手時に、既存画面へ旧配色が残っていないかを検査し、旧Mode Aまたは配色未指定と証明できた場合だけ、安全規則で色を平賀トークンへ置き換える。画面構成・文言・業務要件・余白・フォントは変えない。T2でMode B(Pop)・別ブランドを明示したアプリ、判定信号が競合するアプリ、ファイル名でPopと分かるもの、`aidd-color-migration: exclude-brand` を持つブランド資産は全検出・全置換より先に対象外とする。

1. **dry-run(観測)**: `node <jp-web-design>/scripts/migrate-legacy-colors.mjs <app-src-dir>`。この段階は書き込まず、適用資格・旧トークン・直書きHEX・Dark/テーマ切替・Tailwind色・未対応色構文を列挙する。
2. **plan(判断)**: `--plan --json` でschema v1.0の `eligibility` と `items[{old_value,new_value,automation,status,reason}]` を保存する。`status=eligible`(`source_theme` が `legacy-mode-a` / `unspecified` / `hiraga`)だけ次へ進む。Pop・別ブランド・判定不能はreport-only。
3. **apply(限定実行)**: `--apply` は `automation=safe` だけを全ファイル分計画してからstageし、rename中の失敗時はpreimageへrollbackする。`primary` / `brand` / `border` / `line` / `accent` / `danger` / `text` などの多義トークン、既知値と一致しないHEX、CSS色関数、alpha付きHEXはreview-onlyのまま変更しない。
4. **対応構文**: 自動置換は `var(--token)` と、CSS/SCSSの宣言単位にある `#RGB` / `#RRGGBB` のうちプロパティと既知値から役割が一意なものだけ。CSS-in-JSの意味解析、色関数、alpha付きHEX、プリプロセッサが生成するプロパティは警告して手作業へ送る。
5. **手作業と検証**: 旧トークン定義を正本CSSの読み込みへ差し替え、Dark/テーマ切替を除去する。`check-hiraga-contrast.mjs`、ビルド、4幅、forced-colors、印刷、2回目applyがno-opであることを確認する。
6. **記録**: T2 §5へplan JSONの旧→新対応、review-only残件、適用資格、追加トークン、コントラスト、未検証画面を残す。

catalog-default の plan/apply と組み合わせた全体の順序は `catalog-default-contract.md`「既存アプリの一本化フロー」が正本。

旧→新の対応表は本書に持たない。`migrate-legacy-colors.mjs --plan --json` の `items[].old_value → new_value` と `automation` / `reason` が正本(規則はスクリプトの `LEGACY_RULES`)。review-only になる多義トークンは、次の目安で役割を判断する。

- `--text`: 本文なら `--text-primary`、濃色面上なら `--text-inverse`、ボタン文字なら `--action-*-text`。
- `--text-muted`(旧): 補助本文は `--text-secondary`、説明・placeholderは `--text-muted`。
- `--border` / `--line`: 装飾罫線は `--border-subtle`、入力枠は `--input-border`、操作境界は `--border-control`。
- `--primary` / `--brand`: 主操作は `--action-primary-bg`、リンク・現在地・見出しは `--link` / `--nav-selected-indicator` / `--text-heading`。
- `--brand-deep`: 見出し文字は `--text-heading`、ボタンhover塗りは `--action-primary-hover`。
- `--accent` / `--accent-deep`: 状態は `--status-info-text`、CTAは `--action-primary-bg`。
- `--danger`: 文字は `--status-danger-text`、危険ボタン背景は `--action-danger-bg`。
- `--surface` `--surface-alt` `--focus-ring` は同名のまま平賀CSSの値(フォーカスは3pxの `--focus-ring`)に置き換わる。
