# 標準デザインの使い方

指定がなければ、aidd-agent-kit の jp-web-design の標準カラー (`standard`) と、このプラグインの共通部品・7種類のボードを組み合わせて使う。案件ごとにデザインを作り直さない。配色名の聞き取りは追加しない。

## 正本と責務

| 対象 | 正本 | 使い方 |
| --- | --- | --- |
| 既定の選択 | [quality-thresholds.json](../assets/data/quality-thresholds.json) の `palette_default` | scaffold が指定なしの新規案件へ適用 |
| 色の役割と基本色 | [vendor/standard-color-system.css](../assets/css/vendor/standard-color-system.css) | キットの正本を変えずに写したもの。出所とハッシュは `vendor/SOURCE.json`。手で直さない |
| ボードの言葉・フォント・共通の角丸 | [board-tokens.css](../assets/css/board-tokens.css) | ボードの部品が使う名前をキットの役割へつなぐ。キットに無い色 (ボードの地、注記の番号、端末の枠) だけ値を持つ |
| ボードの共通部品 | [common.css](../assets/css/common.css) | スマホとPCの画面、ボタン、入力欄、注記などを共用 |
| 7種類の構成と型固有の配置 | [page-patterns.md](page-patterns.md)、`assets/templates/board-*.html` | 雛形から組み、必要な位置・幅・間隔だけを調整 |
| まとめHTMLの構成と表示 | [book.html](../assets/templates/book.html) | 案件の `tokens.css` の役割を直接読む。別名や色の値を持たない |

部品は役割の名前 (`--text-primary` `--surface` `--link` など) を使う。基本色 `--p-*` や色の値を部品へ写さない。余白や寸法をすべて変数へ置き換える必要はない。共通する部品の変更は `common.css`、型だけに必要な配置はその雛形に置く。同じ部品を案件のHTMLへ複製して別管理しない。

## 生成と再生成

1. `build-briefing-scaffold.mjs init` が `_src/tokens.css` を、ボードの言葉 → 標準カラー → 案件の上書き (あれば) の順につないで作る (`scripts/lib/palette.mjs`)。同じ名前は後に書いたものが勝つ。共通部品は `_src/common.css` に写す。
2. `boards` が7種類の雛形からボードHTMLを作る。各ボードはこの2つのCSSを読む。
3. `render-board-png.mjs` が同じCSSで描画・検査し、PNGとまとめ用画像を作る。
4. `build-briefing-book.mjs` が案件の `_src/tokens.css` をまとめHTMLへ埋め込む。文書の表示も同じ配色になる。

配色の正は `briefing.json` の `palette`。通常の再実行は既存ファイルを保つ。`init --refresh-css` でCSSを作り直すときも記録した `palette` を使い、記録と違う `--palette` を同時に渡すと止まる。配色を変える場合は `palette` を直してから `--refresh-css` を実行し、PNGとまとめHTMLを作り直す。付け忘れると init は記録と合わないCSSを `stale_css` に並べる。CSSだけを変えて古いPNGを完成品に混ぜない。

## 配色の検査

`scripts/lib/design-tokens.mjs` が、`tokens.css` のトップレベルの `:root` 宣言だけを配色として読む。標準カラーにある部品クラスや `@media` (印刷・高コントラスト) のブロックは読み飛ばす。必須の役割名は標準の組み立てから得るので、キットの版を上げれば必須名も付いてくる。役割の不足、空値、`initial` などの未確定値、参照切れ、循環参照、`@import` を見つけたら止める。

- scaffold は、`tokens.css` を作る・作り直す前に検査し、だめなら何も書かずに止める (exit 2)。
- 描画とまとめは、`tokens.css` が無いか不正なら止める (`TOKENS-MISSING`、`TOKENS-INVALID`)。まとめだけ別の色へフォールバックして成功扱いにしない。`init --refresh-css` で `palette` から作り直して再描画する。
- `palette` が指すCSSが動いて見つからなくても、`--refresh-css` を付けずに再 init するだけなら、配った資料の `tokens.css` はそのまま残す。作り直すときは止まる。

## 案件の配色を指定する場合

キットの決まりどおり、基本色 (`--p-*`) だけを書き換えた上書きのCSSを用意する。役割は基本色に付いてくるので書かなくてよい。役割を直接書いてもよい (最後に置くので勝つ)。コメントとトップレベルの `:root` 宣言だけで書き、`@import` は使わない。標準カラーにもボードにも無い名前を書くと、init が綴りの注意を出す。配置・業務内容・画面の共通部品は配色変更のために作り直さない。

CLIの `--palette <css>` は実行時の作業フォルダから解決し、`briefing.json` には資料フォルダからの相対で記録する。記録した相対パスは、`briefing.json` のある資料フォルダから解決する。通常のスキル実行では [execution-contract.md](execution-contract.md) に従い、CLIに絶対パスを渡す。

## 出典と配布の境界

配色の出典・取り込んだ版・ライセンスは [standard-attribution.md](../assets/css/standard-attribution.md) と `vendor/SOURCE.json` に残す。利用者向けには「標準カラー」「標準デザイン」と表現し、出典や著作権の記録をデザイン名として表示しない。

実行に別のスキルや開発キットの配置は不要。同梱の写しを使うので、単体で同じ生成経路を再現できる。キットの配色が更新されたら `scripts/extract-kit-palette.mjs` で写し直し、`tests/test_palette.py` で出典との一致を確かめ、お手本と一緒に更新する。別スキルのインストール先へ個別に手修正しない。

これは打ち合わせ資料の表示契約。実装アプリの操作・レスポンシブ設計は実装側で扱い、アプリ用カタログの画面構成を固定サイズのボードへそのまま適用しない。
