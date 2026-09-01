# Task仕様書：図解プロンプト設計

## 1. メタ情報

| 項目     | 内容                          |
| -------- | ----------------------------- |
| 名前     | Diagram Prompt Designer       |
| 専門領域 | 拡散モデル向けプロンプト構築   |
| Phase    | 4.2（プロンプト設計）          |
| 入力元   | `visual-structure.json`（`x-longpost-analyze-visual-structure.md` の出力） |
| 出力先   | `${XLP_IMAGE_DIR}/diagram.prompt.txt` |

---

## 2. 目的

構造データを、拡散モデル（gpt-image-2）が**毎回同じ版面で描ける**プロンプト文へ変換する。

再現性の要は3つある。版面を座標で指定すること、画像内の日本語を引用符で固定して単一の正本にすること、退化パターンを Negative で名指しで禁じることである。文章で雰囲気を伝えると出力がばらつく。

## 3. 責務

| 責務                     | 成果物                     |
| ------------------------ | -------------------------- |
| 5ブロック構成への変換     | `diagram.prompt.txt`       |
| 日本語テキストの正本固定 | プロンプト内の引用符つき文字列 |
| 退化の明示的禁止         | NEGATIVE ブロック          |

---

## 4. 制約（最重要）

| ID | 制約 |
|----|------|
| DP-C01 | プロンプトの**地の文は英語**、画像に描く文字は**日本語を引用符で囲って**そのまま埋め込む。日本語ラベルを英訳しない |
| DP-C02 | `visual-structure.json` の文字列を**一字一句そのまま**使う。プロンプト設計の段階で言い換え・要約をしない |
| DP-C03 | 5ブロック（STYLE / LAYOUT / CONTENT / TYPOGRAPHY / NEGATIVE）をこの順で必ず全て書く |
| DP-C04 | NEGATIVE には [`diagram-style-canon.md` §5](../skills/run-x-visual-generate/references/diagram-style-canon.md) の退化パターン6種をすべて書く |
| DP-C05 | 絵文字をプロンプトに含めない |
| DP-C06 | 出力は `.prompt.txt`（`.md` にしない）。Obsidian が vault 内の `.md` を同期取り込みして消すため |

## 5. 参照リソース

| 目的 | ファイル | 必須 |
|------|----------|------|
| 絶対ルール・版面・退化パターン | [diagram-style-canon.md](../skills/run-x-visual-generate/references/diagram-style-canon.md) | 必須 |
| アイコンの粒度 | [icon-vocabulary.md](../skills/run-x-visual-generate/references/icon-vocabulary.md) | 必須 |

---

## 6. 実行仕様

### ブロック1: STYLE

画風を固定する。文言は原則そのまま使う。

```
STYLE: A clean, minimal Japanese infographic diagram. Pure white background (#FFFFFF).
Strictly black and white line art: solid black filled human silhouettes without facial
features, black outlined objects with uniform stroke weight. Flat vector pictogram style,
no gradients, no shadows, no textures, no 3D. One accent color only: red, used exclusively
for the ✕ mark that denotes failure.
```

### ブロック2: LAYOUT

`primaryType` に応じて中段の組み方を変える。三分割そのものは型によらず固定する。

```
LAYOUT: 16:9 canvas divided into three horizontal bands.
Top band (15% height): one centered bold black Japanese headline.
Middle band (60% height): three columns of equal width, separated by thick black
horizontal arrows pointing left to right. Each column has a small bold heading at its top,
below it a chain of 2-5 pictograms connected by medium-weight arrows.
Bottom band (25% height): three bold two-line Japanese captions, one under each column.
Generous white margins on all four sides.
```

`nestedType` が `T2` のときは、該当ゾーンに次を追記する。

```
In column {N}, arrange the pictograms in a closed clockwise circle connected by curved arrows
instead of a left-to-right line.
```

`nestedType` が `T3` のときは次を追記する。

```
In column {N}, place two pictogram groups side by side; mark the left group with a large red ✕.
```

`nestedType` が `T1` `T4` `null` のときは**何も追記しない**。上の LAYOUT が既に左から右への単線配置なので、T4 は追記なしで表現できており、T1 の入れ子は三分割そのものと重なるため意味を持たない。ここで独自の追記を発明すると、同じ構造データから毎回違う版面が出る。

### ブロック3: CONTENT

`visual-structure.json` の中身を写す。**ここが画像内テキストの単一正本になる。**

```
CONTENT:
Headline (top band, large bold): "{headline}"
Column 1 heading: "{zones[0].heading}"
Column 1 pictograms, left to right: {zones[0].chain の icon を英語の概念記述で列挙}
Column 1 pictogram labels (small, under each icon): "{label}", "{label}", ...
Column 1 caption (bottom band, bold, two lines): "{conclusion[0]}" / "{conclusion[1]}"
（Column 2・Column 3 も同形式で続ける）
```

`icon` は日本語の概念記述で入力されるので、ここで**英語の描画指示へ言い換える**。`label` は日本語のまま引用符で固定する（DP-C01 の適用箇所が icon と label で異なる点に注意する）。

| `icon` の例 | 英語の描画指示 |
|-------------|----------------|
| 人物（机で悩む） | a black silhouette of a person sitting at a desk with a question-mark thought bubble |
| AIロボット | a simple robot head with rounded square face and antenna |
| 書類 | a document sheet with folded top-right corner |
| 専門家 | a black silhouette of a person in a suit with a check mark |
| 循環 | a closed circular arrow loop |

### ブロック4: TYPOGRAPHY

```
TYPOGRAPHY: All text is Japanese, rendered in a heavy sans-serif gothic typeface, pure black.
Headline is the largest element on the canvas. Column headings are medium.
Pictogram labels are small. Bottom captions are bold and clearly readable.
Render every quoted Japanese string exactly as written, crisp and undistorted.
Do not add any text that is not quoted above.
```

### ブロック5: NEGATIVE

退化パターン6種を名指しで禁じる。

```
NEGATIVE: no emoji, no colored backgrounds, no gradients, no shadows, no 3D rendering,
no photographic elements, no facial features on human figures, no color other than black,
white and the single red ✕. The background must be an opaque, fully painted white
rectangle covering the entire canvas. Do NOT output a transparent background, and do NOT
include an alpha channel. Do NOT produce flat rounded rectangles filled with paragraphs
of text instead of pictograms. Do NOT render garbled, distorted, or invented Japanese
characters. Do NOT write sentences longer than the quoted strings. Do NOT include the
characters 僕 or 私 anywhere in the image.
```

不透明を明示するのは、STYLE の `Pure white background` だけでは足りないと実測で分かったためである。生成系はこれを「背景を描かない」と解釈してアルファ付きの PNG を返すことがあり、その画像は貼り先の背景色を透かすので、ダークテーマでは黒地に黒文字となって全文が消える。白紙で出るわけではないので目視でも気づきにくい。`validate-visual-assets.js` が color type で検出するが、そこで弾く前にここで防ぐ。

---

## 7. 出力テンプレート

`${XLP_IMAGE_DIR}/diagram.prompt.txt` に、§6 の5ブロックを空行区切りでこの順に連結して保存する。ヘッダやコメント行を足さない（ファイル全文が拡散モデルへの入力になる）。

---

## 8. 品質チェックリスト

| 確認項目 | 判定 |
|----------|------|
| 5ブロックが STYLE / LAYOUT / CONTENT / TYPOGRAPHY / NEGATIVE の順に揃っているか | □ |
| CONTENT の日本語が `visual-structure.json` と一字一句一致しているか（DP-C02） | □ |
| `icon` がすべて英語の描画指示へ言い換えられているか | □ |
| `label` と `conclusion` が日本語のまま引用符で囲われているか | □ |
| NEGATIVE に退化パターン6種がすべて含まれているか（DP-C04） | □ |
| NEGATIVE が背景の不透明・アルファチャンネル禁止を明示しているか（VS-02） | □ |
| 絵文字が含まれていないか（DP-C05） | □ |
| 拡張子が `.prompt.txt` か（DP-C06） | □ |

---

## 9. 次への接続

これは明示的に図解を追加する場合だけ使う **optional diagram-only** 手順である。`build-visual-prompts.js` / `generate-images-codex.js` / `validate-visual-assets.js` のすべてに `--only diagram` を付ける。図解は標準の x-thumb / note-thumb の生成・採用・embed を省略するゲートではない。

## 10. ワークフロー内の位置づけ

標準サムネイル2種と同じ `visual-structure.json` を使う optional の Phase 4.2〜4.4。実行順は指定に応じるが、図解をサムネイルの代わりにしない。
