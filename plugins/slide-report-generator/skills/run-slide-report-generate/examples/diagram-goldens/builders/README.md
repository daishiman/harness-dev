# 構造図ビルダーのゴールデン（spec → 出力 HTML の対）

親ディレクトリの <!-- count: diagramGoldenHand -->53 組は**人が書いた図解の正解見本**である。ここの <!-- count: svgBuilderStruct -->10 組は性質が違う。
`vendor/scripts/svg-structures.cjs` の <!-- count: svgBuilderStruct -->10 ビルダーが**現に何を出すか**の記録であり、
手で化粧していない。生成手段は下記の CLI 1 本だけで、それ以外の経路で作らない。

## 1. 生成と検証

```bash
cd plugins/slide-report-generator
node scripts/render-diagram-golden.cjs \
  skills/run-slide-report-generate/examples/diagram-goldens/builders/er-spec.json \
  > skills/run-slide-report-generate/examples/diagram-goldens/builders/er-golden.html

python3 scripts/validate-svg-diagram.py --check-grid --strict <golden>
```

`--skeleton slide|report` で骨格を上書きできる（既定は spec の `surface`）。
同じ spec からは常にバイト同一の HTML が出る。golden を再生成して差分が出たら、
動いたのは golden ではなく **vendor か骨格の側**である。

## 2. spec の書き方

```json
{ "builder": "buildEr", "surface": "report", "diagramId": "f2",
  "title": "…", "figureLabel": "図 2", "caption": "…",
  "spec": { "entities": [...], "relations": [...] } }
```

`spec` のキー名は `vendor/scripts/render-slide.cjs` の dispatch と同じ語
（`zones` / `stages` / `entities` / `actors`+`messages` / `states`+`transitions` /
`lanes`+`stepLabels` / `levels` / `rows`+`columns` / `tiers` / `hub`+`spokes`）を使う。
揃えているのは、ここで通った spec が実運用の経路でも同じ図になるようにするためである。

## 3. 骨格からの意図的な差（3 件）

golden はビルダーの戻り値を 1 バイトも加工しない。その結果、
`assets/diagram-templates/` の骨格とは次の 3 点で食い違う。**直さない。**

1. **アクセシブル名**: 骨格は `aria-labelledby="<id>-caption"` を使うが、
   ビルダーは `aria-label` + `<title>` を出す。`figcaption` の id は骨格どおり残してある。
2. **marker の id**: 骨格は `<id>-arrow` と図解 id で前置するが、ビルダーは
   `arrow-muted` のような固定名を 10 種すべて出す（使っていない色の marker も出る）。
   同一ページに 2 枚並べると id が衝突するため、実運用で複数枚を載せる経路は
   前置の責務を別に持つ必要がある。
3. **font-family**: 骨格は「書体を書かない」と定めるが、ビルダーの `textBlock` は
   `font-family` を書き出す。D13 のホワイトリスト内なので検査は通る。

## 4. 検証状態と、そこへ至るまでに直したもの

10 枚とも `--check-grid --strict` で **errors=0 / warnings=0 → PASS**。

当初は 3 系統の warning が出ていた。いずれも spec 側では消せない
（ビルダーの幾何と検査の数え方に由来する）ものだったので、発生源を直した。

- **D6（4px グリッド）** 全 10 枚で出ていた。原因は 2 層あった。
  土台側は `kit.legendStrip` の見本矩形（10×10・`y+2`）、`kit.arrowLabel` の
  マスク矩形（`h = 行数×lineHeight + 6` = 22）、`distributeWidths` の等分割で
  出る 1-2px の端数、`matrixLayout` / `stackLayout` の `Math.floor` 割り。
  ビルダー側は ER の `headH=34`、state の格子上端 110、high-level の箱高 110、
  swimlane のセル内余白 6/12、dp-integration の `hubW=236` といった
  4 の倍数でない定数。**寸法の作り方そのものをグリッド単位に変えて解消した**
  （文字を包む矩形は `snapUp` で切り上げ、領域の等分は `snapDown` で切り下げ、
  余りは 4px 単位で切り捨て量の大きい順に返す）。
- **D7（強調色の面塗り 3 件）** 焦点を持つ 5 枚で出ていた。実体は焦点ノードでは
  なく、`kit.arrowMarkers` が使用有無に関わらず `<defs>` へ吐く
  `arrow-accent` / `arrow-pink` の 2 個だった。描かれないものを強調として
  数えていた検査側の誤りなので、**`marker-start/mid/end` から実際に参照された
  marker の中身だけを数える**ように `validate-svg-diagram.py` を直した。
- **D5（斜め line）** `dp-integration` の 4 本。放射状スポークは
  `diagram-layout-contract.md` §D-3 原則 1 例外 (a) が明示的に認めた語彙なので、
  **warning への降格ではなく無出力**にした（D17 の `<path>` 版も同じ）。

ビルダー幾何の変更は vendor 配下（`svg-kit.cjs` / `svg-structures.cjs`）で行い、
`lint-vendor-parity.py` の `ADDITIVE_LOCAL_FORK` に不変トークンとして登録済み。

その後に追加した **D18（文字収容）** も 10 枚すべて無警告。決定論経路は
`kit.fitText` が箱の内寸を `幅 − 24px` で見積もるのに対し D18 の許容は
`幅 − 16px` なので、ビルダー生成物は構造上 D18 を通る。逆に言えば
D18 が鳴るのは手書き SVG か、`fitText` を通さず直に `<text>` を置いた箇所。
契約側の目安は `diagram-layout-contract.md` §D-8 にある。
