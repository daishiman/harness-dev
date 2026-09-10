# Task仕様書：サムネイルプロンプト設計

## 1. メタ情報

| 項目     | 内容                          |
| -------- | ----------------------------- |
| 名前     | Thumbnail Prompt Designer     |
| 専門領域 | 拡散モデル向けプロンプト構築（サムネイル2種） |
| Phase    | 4.2（プロンプト設計）          |
| 入力元   | `visual-structure.json` の `thumbnails` セクション |
| 出力先   | `${XLP_IMAGE_DIR}/x-thumb.prompt.txt` と `${XLP_IMAGE_DIR}/note-thumb.prompt.txt` |

---

## 2. 目的

同じ構造データから、**5:2** と **1280x670** の2枚を作る。kind・比率・生成/納品寸法・palette は [`visual-spec.json`](../skills/run-x-visual-generate/references/visual-spec.json) を参照する。

図解が「理解させる絵」であるのに対し、サムネイルは「読む前の人の足を止める絵」である。**図解を縮小して流用せず、図解の画風も継承しない。** 画風の正本は [`thumbnail-style-canon.md`](../skills/run-x-visual-generate/references/thumbnail-style-canon.md) であり、図解の `diagram-style-canon.md` とは別系統である。

## 3. 責務

| 責務                     | 成果物                     |
| ------------------------ | -------------------------- |
| X サムネイル（5:2）のプロンプト | `x-thumb.prompt.txt`       |
| note サムネイル（1280x670）のプロンプト | `note-thumb.prompt.txt` |
| 2枚の画風の一致           | 同一の STYLE / TYPOGRAPHY / NEGATIVE ブロック |

---

## 4. 制約（最重要）

| ID | 制約 |
|----|------|
| TP-C01 | プロンプトの**地の文は英語**、画像に描く文字は**日本語を引用符で囲って**そのまま埋め込む。5ブロック（STYLE / LAYOUT / CONTENT / TYPOGRAPHY / NEGATIVE）をこの順で必ず全て書く。出力は `.prompt.txt`（`.md` にしない） |
| TP-C02 | STYLE / TYPOGRAPHY / NEGATIVE は**2枚のサムネイル間で完全に同一の文字列**を使い、**図解プロンプトからは複写しない**。差し替えるのは LAYOUT と CONTENT だけである（TS-12） |
| TP-C03 | 主文は `thumbnails.{x,note}.main` を一字一句そのまま使う。6〜24字の範囲外なら構造解析へ差し戻す（ここで勝手に変えない） |
| TP-C04 | 図形要素は**3個以内**。矢印つきの連鎖は note 版で1本まで、X 版では作らない（TS-07） |
| TP-C05 | 四辺に 5% 以上の余白と、枠線で囲まない指示を LAYOUT に必ず含める（TS-08） |
| TP-C06 | NEGATIVE に、人物禁止（TS-03）・透過背景とアルファチャンネルの禁止（TS-02）・[`thumbnail-style-canon.md` §3](../skills/run-x-visual-generate/references/thumbnail-style-canon.md) の情報商材的意匠**6分類すべて**を書く |
| TP-C07 | STYLE には palette の3色を**hex 値で**書く。色名だけで指定しない（生成のたびに色味が動くため） |

## 5. 参照リソース

| 目的 | ファイル | 必須 |
|------|----------|------|
| 画風・配色・禁止事項の正本 | [thumbnail-style-canon.md](../skills/run-x-visual-generate/references/thumbnail-style-canon.md) | 必須 |
| 寸法・版面 | [thumbnail-specs.md](../skills/run-x-visual-generate/references/thumbnail-specs.md) | 必須 |
| 機械可読値（palette・比率・寸法） | [visual-spec.json](../skills/run-x-visual-generate/references/visual-spec.json) | 必須 |
| アイコンの粒度 | [icon-vocabulary.md](../skills/run-x-visual-generate/references/icon-vocabulary.md) | 任意 |

---

## 6. 実行仕様

### ブロック1: STYLE（2枚で共通・文言をそのまま使う）

```
STYLE: A calm, minimal Japanese thumbnail graphic. The entire canvas is filled with an
opaque warm off-white background (#F8F3E6), painted edge to edge as a solid rectangle.
All text is set in #1A1A1A. Flat lettering with no text shadow. Geometric shapes may use a
restrained paper-cut texture and shallow soft shadow, but no gradients, flashy 3D, or photos.
Exactly two accent colors, each with a fixed role: #C1C2A0 (muted sage) is used only
for structural elements such as connecting lines, rails and rings, never on text; #D87C45
(terracotta) is used only for a single small band carrying the supporting phrase, and the
text inside that band is white. No other color appears. Never use red.
The composition is quiet and spacious: shapes occupy at most 40 percent of the canvas.
```

`#F8F3E6` を純白にしない理由は TS-02 にある。純白は貼り先の白い UI と地続きになって画像の輪郭が消える。アクセントを色数ではなく**役割**で縛る理由は TS-05 にある。彩度の低いセージが構造を担い、高彩度のテラコッタを帯1枚に閉じ込めることで、2色あっても視線の着地点は1つに保たれる。

### ブロック2: LAYOUT（kind ごとに差し替える）

X サムネイル（5:2）:

```
LAYOUT: 5:2 wide canvas. Split into a left text zone (65% width) and a right shape zone
(35% width). The left zone holds one bold Japanese headline of at most two lines,
vertically centered, left aligned. The right zone holds one to three flat geometric shapes,
no arrows between them, with the accent color used on exactly one of them. Keep at least
5% empty margin on all four sides. Do not draw a border frame around the canvas.
```

note サムネイル（1.91:1）:

```
LAYOUT: 1.91:1 wide canvas. Centered vertical stack: a bold Japanese headline of at most
two lines at the top, one horizontal row of up to three flat geometric shapes in the middle
connected by at most one arrow chain, and a smaller Japanese sub line at the bottom.
The accent color is used on exactly one shape. Everything centered horizontally. Keep at
least 5% empty margin on all four sides. Do not draw a border frame around the canvas.
```

### ブロック3: CONTENT

```
CONTENT:
Main line (very large bold): "{thumbnails.<kind>.main}"
Sub line (smaller, under the main line): "{thumbnails.<kind>.sub}"
Shapes: {thumbnails.<kind>.icons を英語の描画指示へ言い換えて列挙}
```

`sub` が `null` の場合は Sub line の行ごと省く（空文字を渡さない）。引用符で囲むのは主文と補助句の**2本まで**であり、これが画像内テキストの単一正本になる（TS-11）。

### 図形の言い換え（人物を使わない語彙）

図解の対応表は人物シルエットを含むため、そのまま使えない（TS-03）。同じ概念を**もの・場**へ置き換える。

| 概念 | 図解での描画（人物あり） | サムネイルでの描画（人物なし） |
|------|--------------------------|--------------------------------|
| 悩む・迷い | 机で悩む人物のシルエット | a question mark inside a rounded speech bubble |
| 会議・対話 | 向かい合う2人のシルエット | two overlapping speech bubbles |
| 専門家・判断 | スーツの人物とチェック印 | a check mark inside a circle |
| 作業・実務 | 作業する人物 | a stack of three horizontal bars |
| 削減・除外 | 人物と赤 ✕ | an empty square with one bar removed from a stack |
| 循環・反復 | 人物を囲む円環 | a closed circular arrow loop |

### ブロック4: TYPOGRAPHY（2枚で共通）

```
TYPOGRAPHY: All text is Japanese, rendered in a heavy sans-serif gothic typeface in #1A1A1A.
The main line is the largest element on the canvas, at least twice the size of the sub line.
Render every quoted Japanese string exactly as written, crisp and undistorted.
Do not add any text that is not quoted above. Do not decorate the letterforms.
```

### ブロック5: NEGATIVE（2枚で共通・6分類すべてを書く）

```
NEGATIVE: no emoji, no human figures, no human silhouettes, no faces, no hands.
The background must be an opaque, fully painted off-white rectangle covering the entire
canvas; do NOT output a transparent background and do NOT include an alpha channel.
No outlined text, no gradient text, no text shadow, no 3d text, no italic emphasis.
No neon, no highly saturated primary colors, no glowing elements, no dark backgrounds.
No starburst, no explosion marks, no speed lines, no lightning bolt, no crown, no medal.
No huge numbers promising results, no circled numbers, no price figures.
No diagonal band splitting the canvas, no decorative rule, no cluttered composition,
no more than three arrows. No photographic elements, no photorealistic rendering.
Do NOT render garbled, distorted, or invented Japanese characters.
Do NOT include the characters 僕 or 私 anywhere in the image.
```

この列挙は「派手さの禁止」ではなく、**中身ではなく強調記号そのもので注意を引く手法**の禁止である。インパクトは §2 ではなく [`thumbnail-style-canon.md` §2](../skills/run-x-visual-generate/references/thumbnail-style-canon.md) の4手段（余白・要素を1つ・主文を極大・色を1箇所）で作る。

---

## 7. 出力テンプレート

2ファイルそれぞれに、STYLE / LAYOUT / CONTENT / TYPOGRAPHY / NEGATIVE を空行区切りでこの順に連結して保存する。ヘッダやコメント行を足さない（ファイル全文が拡散モデルへの入力になる）。

---

## 8. 品質チェックリスト

`lint-thumbnail-prompt.js` が下表の TL-** を機械判定する。目視項目は**生成後**の絵に対して行う。

| 確認項目 | 判定器 |
|----------|--------|
| 5ブロックが順に揃っているか | TL-01 |
| STYLE が palette 3色を hex で書いているか（TP-C07） | TL-02 |
| 図解 palette（純白背景・赤アクセント）が混入していないか（TP-C02） | TL-03 |
| NEGATIVE が人物禁止を書いているか（TS-03） | TL-04 |
| NEGATIVE が情報商材的意匠6分類を書いているか（TP-C06） | TL-05 |
| NEGATIVE が透過背景とアルファチャンネルを禁じているか（TS-02） | TL-06 |
| LAYOUT が 5% 余白と枠線禁止を書いているか（TP-C05） | TL-07 |
| LAYOUT の canvas 比率が kind と一致するか（TS-01） | TL-08 |
| 引用日本語が2本以内・字数上限内・合計44字以内か（TS-06） | TL-09 |
| 絵文字・禁止語を含まないか（TS-10） | TL-10 |
| 主文・補助句が `visual-structure.json` と一字一句一致するか（TP-C03） | TL-11 |
| 2本の STYLE / TYPOGRAPHY / NEGATIVE が完全一致するか（TP-C02） | TL-12 |
| 図形が3個以内で、X 版に矢印連鎖が無いか（TP-C04） | 目視 |
| 生成物に人物・情報商材化・図解化・アクセント散乱が無いか | 目視（生成後） |

---

## 9. 次への接続

これは標準成功で必ず実行する **thumbnails-only** 手順である。図解は optional であり、サムネイル2種の完成条件にしない。

1. 2本の `.prompt.txt` を書く
2. `node scripts/lint-thumbnail-prompt.js --image-dir "${XLP_IMAGE_DIR}" --structure "${XLP_IMAGE_DIR}/visual-structure.json"` — **exit 0 でなければ生成へ進まない**
3. `build-visual-prompts.js` / `generate-images-codex.js` に `--only x-thumb,note-thumb` を付けて2枚だけ生成する
4. `validate-visual-assets.js --only x-thumb,note-thumb` で比率・PNG 署名・背景の不透明性・背景色を機械検証する
5. `thumbnail-style-canon.md` §5 の退化が無いか2枚とも目視する
6. 2枚を Read / view_image で開き、5項目の PASS receipt を記録してから `--only x-thumb,note-thumb` で embed する

## 10. ワークフロー内の位置づけ

標準の Phase 4.2〜4.4 に属する。accept-as-is は生成済みの2枚を採用する意味であり、サムネイルを作らず終了する意味ではない。
