# slide-templates — ページ単位のスライドひな形

面 (1 ページ) の**配置の型**を 22 種に固定し、107 種の slideType をそこへ写像する。
生成のたびに面を組み立て直さず、決まったひな形へ内容を嵌める。同じ slideType は
常に同じ骨格へ載るので、粒度と精度が回ごとにぶれない。

id は `layout-<役割>` で、通し番号ではない。**ひな形 1 枚 = 1 ページではなく型**なので、
同じ `layout-diagram-main` を 1 つの deck で何枚使ってもよく、deck の総ページ数は
ひな形の枚数と無関係。

## 何を解決しているか

従来頻発していた 4 つの症状には、それぞれ構造的な原因があった。下記の封じ手が効くのは
**このひな形をコピーして書いた面**に限る。決定論経路 (`render-slide.cjs`) は
`frame-contract.json` を読まず独自の `slider-*` 体系で描くため、同じ症状は
`verify-slides.js` / `validate-print.js` 側で見る。

| 症状 | 原因 | ここでの封じ手 |
|---|---|---|
| 空白が余り過ぎる | 面が flex-column + gap だけで、要素が減ると隙間が伸びていた | `.srg-slide__main` が `flex: 1 1 auto` で残り高さを必ず占める |
| インデックス・ページ番号がズレる | chrome の「予約余白」と「実物の描画」が別ファイルで別々に管理されていた | 予約帯も実物も `frame-contract.json` の同じ値を読み、`validate-slide-skeleton.py` が突合する |
| 戻るページが反映されない | 端の面でナビ要素ごと消していたため、幅と参照が崩れていた | nav 帯を持つひな形では `data-nav="prev"/"next"` を常に両方置き、端では `data-disabled="true"` にするだけ。S9 が片方向化を落とす (表紙・章扉・目次・全面画像・締め・連絡先は元から nav 帯を持たない) |
| PDF でズレる | 画面が vw 基準・印刷が mm 基準で、別々の寸法体系だった | 面の内部は 1280×720 の絶対座標で固定。印刷は `zoom` 倍率だけが変わり、レターボックス帯は要素 margin ではなく `@page margin` が作る。`@page` 宣言は `slide-skeleton.css` の 1 つだけ（導出は下記「印刷 (A4)」節） |

## 構成

| ファイル | 役割 | 種別 |
|---|---|---|
| `frame-contract.json` | 寸法の唯一の正本 (canvas / chrome / stage / spacing / typography / fill / print / media) | 手で編集する |
| `slide-skeleton.css` | 上記から生成した面の CSS | **生成物** |
| `slide-skeleton.js` | `data-autofit` (自動縮小) と `--srg-fit` (画面フィット) の実装 | **生成物** |
| `layout-*.html` | ページひな形 <!-- count: slideSkeleton -->22 種 | **生成物** |
| `registry.json` | slideType 107 種 → ひな形 + media 種別の写像表、役割ページの引き先 | 手で編集する |

色は `frame-contract.json` ではなく `vendor/scripts/style-builder.cjs` の `SPEC.colors`
が正本で、CSS 生成器がそこから `--srg-*` トークンを**定義**する。ひな形や CSS の使用箇所へ
16 進を直書きすると、パレットを変えてもその面だけ取り残される (S11 が落とす)。

生成物を直接編集しても、次の再生成で消えるうえ検査 (S4) が赤くなる。変更は
`frame-contract.json` か `scripts/build-slide-skeletons.py` の `_SKELETONS` へ入れる。

```bash
python3 scripts/build-slide-skeleton-css.py     # CSS 再生成
python3 scripts/build-slide-skeleton-js.py      # JS 再生成
python3 scripts/build-slide-skeletons.py        # ひな形 22 種 再生成
python3 scripts/validate-slide-skeleton.py      # 契約検査 (PASS=exit0)
python3 scripts/validate-slide-skeleton.py --self-test   # 検査器自身の検出能
```

## ひな形 <!-- count: slideSkeleton -->22 種

slideType から引くもの (`registry.json` の `map`):

| id | 用途 | 受け入れる差し込み物 |
|---|---|---|
| `layout-message` | 主張 1 つを面いっぱいで言い切る | なし |
| `layout-lead-list` | 結論 1 行 + 根拠 3〜5 点 | なし |
| `layout-compare-2` | 2 案・Before/After の左右対比 | なし |
| `layout-diagram-main` | 図解が主役 | svg / d3 / chart / block |
| `layout-diagram-side` | 本文が主、図解が従 | svg / d3 / chart / block |
| `layout-chart-main` | チャート + 「そこから何が言えるか」 | chart / d3 |
| `layout-table` | 表・マトリクス (行と列の交点に意味がある) | block |
| `layout-grid-cards` | 並列項目 4〜6 件のカード格子 | なし |
| `layout-timeline` | 時系列・段階を左→右の 1 本で | svg / d3 |
| `layout-quote` | 一次情報の言葉をそのまま | なし |
| `layout-image-full` | 生成画像を全面、題を重ねる | codex-image |
| `layout-image-side` | 生成画像 + 本文 | codex-image |
| `layout-image-grid` | 生成画像 3 枚前後の格子 | codex-image |

構造ページ (`structural_pages`。structure.json のメタから生成される):

| id | 用途 | 受け入れる差し込み物 |
|---|---|---|
| `layout-cover` | 表紙。主題と発表者・日付だけ | codex-image (背景・任意) |
| `layout-agenda` | 目次。章題 + その章で分かること 1 行 | なし |
| `layout-section-divider` | 章扉。章番号・章題・その章で分かること 1 行 | なし |
| `layout-closing` | 締めと次の行動 | なし |

役割ページ (`role_pages`。slideType を持たないので役割名で引く):

| 役割名 | id | 用途 | 受け入れる差し込み物 |
|---|---|---|---|
| `self_introduction` | `layout-profile` | 自己紹介・登壇者紹介・ペルソナ (1 名) | codex-image / svg |
| `speaker_list` | `layout-team` | チーム・登壇者一覧 (3〜6 名) | codex-image |
| `key_metrics` | `layout-metrics` | KPI・実績・規模を数値で (3 件まで) | なし |
| `anticipated_questions` | `layout-qa` | 想定質問・FAQ・論点の潰し込み | なし |
| `contact` | `layout-contact` | 連絡先・申込導線 (QR 等) | codex-image |

役割ページが無かったころ、自己紹介や目次のような面は毎回その場で組まれ、結局
ひな形の外へ落ちていた。「slideType が無い面」にも引き先を与えるのがこの表の役目。

## 使い方

1. slideType を持つ面は `registry.json` の `map` で、持たない面 (目次・自己紹介・
   連絡先など) は `role_pages` / `structural_pages` で役割名から引く。
2. visual-strategist が差し込み物を **codex-image** に決めた面は、`media_override`
   に従って画像系 (`layout-image-full` / `layout-image-side` / `layout-image-grid`) へ
   載せ替える。slideType は据え置く
   (構成上の意味は変わらないため)。
3. ひな形をコピーし、`data-slot` を持つ要素の `{{...}}` を埋める。
4. `data-media-slot` の中へ、そのひな形が `data-media-kinds` で宣言した種別の
   差し込み物だけを置く。

骨格 (section の class・chrome・stage・スロット構造) は書き換えない。座標や寸法を
面ごとに直書きしない — 数値は `frame-contract.json` だけが持つ。

## 文字が収まらないとき

1. `data-autofit` を持つ要素は、`slide-skeleton.js` が `scrollHeight > clientHeight`
   の間だけ font-size を 1px ずつ下げる。下限は `--srg-fs-min` (18px)。この JS は
   成果物の `scripts.js` へ**連結**して届ける (下記「成果物への届け方」)。
2. 下限でなお溢れる要素には `data-autofit-floored="true"`、その面には
   `data-overflow="true"` が付く。これは「収まらなかった」という表示であって
   自動修復ではない。**面を割る**か本文を削る。18px 未満へ縮めない —
   読めない文字で「収まった」ことにするのは、溢れているのと同じ壊れ方。

## 成果物への届け方

ひな形をコピーしただけの面は、`.srg-slide__*` も `--srg-*` も `data-autofit` も
未解決のまま出荷される。ひな形 <!-- count: slideSkeleton -->22 枚は例外なく `slide-skeleton.css` の class /
トークンと `slide-skeleton.js` の autofit に依存しているので、面を 1 枚でも
コピーしたら以下を必ず行う。

| 資産 | 届け先 | やり方 |
|---|---|---|
| `slide-skeleton.css` | 成果物の `styles.css` | 先頭へ**そのまま連結**する (`:root` の `--srg-*` 定義を含む。deck 固有の CSS はその後ろへ書く) |
| `slide-skeleton.js` | 成果物の `scripts.js` | 末尾へ**そのまま連結**する (DOMContentLoaded で自走する。呼び出しコードは要らない) |

`<style>` / `<script>` によるインライン埋め込みはしない (CONST_002 の分離形式)。
別ファイルとして増やすのでもない — 成果物は `index.html` + `styles.css` +
`scripts.js` の 3 ファイル構成のままにし、この 2 つは既存の外部 2 ファイルへ
畳み込む。連結ゆえ外部 CDN も追加依存も増えない。

連結を忘れると、全ゲートが緑のまま骨格の無い deck が出る — `validate-slide-skeleton.py`
は `assets/` 配下のひな形資産だけを検査し、生成された deck 側は見ないため。

**連結時の唯一の禁則: deck 側で `@page` を書かない。** `slide-skeleton.css` が
`@page { size: A4 landscape; margin: 21.47mm 0 }` を持っており、`@page` は
カスケードで**後に書いた側が勝つ**。`references/print-layout.md` の印刷 CSS 例に
ある `@page { margin: 0 }` をそのまま後ろへ連結すると、レターボックス帯 (21.47mm)
が消えて A4 全面に伸び、面の縦横比が崩れる。ひな形を使う deck の `@page` は
`slide-skeleton.css` の 1 つだけにする (S7 はひな形資産の中しか見ないので、
成果物側の二重定義は検査に掛からない)。

## 印刷 (A4)

面は 1280×720 の座標系のまま `zoom: 0.8769` で A4 横に落ちる (297×167.06mm)。
上下 21.47mm がレターボックス帯で、これは要素 margin ではなく `@page margin` が
作る — `@page margin` は要素の `zoom` に影響されないので、倍率を変えても帯幅が
狂わない。`@page` 宣言はこの CSS が 1 つだけ持つ (複数あると読み込み順で結果が
変わり、印刷が再現しなくなる。S7 が二重定義を落とす)。

## 関連

- 図解そのものの作図規律: `assets/diagram-templates/README.md`
- どの図解型がどう描かれるか: `references/diagram-type-crosswalk.md`
