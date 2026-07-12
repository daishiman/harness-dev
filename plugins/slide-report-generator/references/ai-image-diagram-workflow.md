# AI画像図解ワークフロー

**責務**: ユーザーが明示的に求めた場合だけ、事前確認済みの text-to-image バックエンドを使い、最終スライドの一部図解・ビジュアルを高品質な画像アセットへ差し替える判断基準と実装手順を定義する。既存画像の画風を再利用して量産する場合は `style-genome-packaging.md` を併用する。

---

## 1. 基本方針

デフォルトは HTML / CSS / JavaScript / インラインSVG2 / D3 で構成する。SVG/D3は精密性と再編集性に優れる。AI生成画像は質感、情景、比喩、人物・業務シーン、ヒーロービジュアルに優れるが、ユーザーの明示指示がある場合だけ使う。すべてを画像化せず、プレゼンの説得力が上がる箇所だけを対象にする。

**原則**:

- 通常のAI画像差し替えでは、図解の意味を担う日本語テキストは画像に焼き込まない
- ラベル、数値、見出しはHTML/SVGで重ねる
- 例外として、ユーザーが「漫画チックな図解内に説明文を入れる」「画像生成で説明文入り図解を作る」などを明示し、`textPolicy: baked-with-overlay` を採用した場合だけ画像内テキストを許可する
- 画像内テキストを許可しても、正テキストは必ず `overlayText` に保存し、崩れたらHTML overlayへ切り替える
- 再生成できるようにプロンプトと差し替え理由を保存する
- `structure.md` と HTML の同期を崩さない
- 明示指示がない場合は画像生成候補の抽出も行わず、SVG/CSS/JS/HTMLで実装する

---

## 1.1 起動条件

起動してよい明示指示:

- `Codexで図解を作成して`
- `Codex Image 2 / image2 でスライド各ページを画像生成して`
- `画像生成で差し替えて`
- `AI生成画像を使って`
- `このスライドは生成画像にして`
- `各ページを1枚ずつ生成画像にして`
- `スライド全体を生成画像で構成して`
- `図解を画像アセットとして生成して`
- `この画像のスタイルゲノムを取得して量産できるようにして`
- `漫画チックな図解の中に説明文を入れて`

起動しない指示:

- `図解を作って`
- `見やすくして`
- `デザインを良くして`
- `高品質にして`
- `エレガントにして`

これらは通常のSVG/CSS/JS/HTML改善として扱う。

---

## 1.2 着手前バックエンド確認（必須）

画像生成に入る前に、このセッションで実際に使える text-to-image バックエンドが本当にあるかを必ず確認する。確認せずに候補抽出・プロンプト量産・大量生成へ進んではならない。「全枚を画像化」という指示を受けても、バックエンド未確認のまま生成作業を始めない。

### 確認手順（上から順に存在確認する）

1. **MCP の画像生成ツール**がこのセッションに存在するか（text-to-image を行うツールがツール一覧にあるか）を確認する。
2. **CLI が起動するか**を確認する（例: `codex --version`）。ただし重要: `codex`（OpenAI Codex CLI）は**コーディングエージェントであり、単体の text-to-image サブコマンドを持たない**。本skill内の「Codex/imagegen」という表記は概念的な呼称であり、実体としては別途の画像生成 API / ツールが必要。`codex` が起動しても、それだけでは画像は生成できない。
3. **画像生成 API**（OpenAI 画像 API = gpt-image 等）の APIキー・エンドポイントが使えるかを確認する。APIキーはスクリプトが直接読み、Claude のコンテキストには載せない。

注意（実環境の既知事象）:

- `codex` が `Missing optional dependency @openai/codex-darwin-x64` 等で起動しないケースがある。
- MCP の画像生成ツールが無いセッションもある。
- いずれも事前確認なしに進めると、生成できないまま大量のプロンプトだけが残る。

### この環境での確認済みバックエンド（codex exec）

実運用の知見として、**この環境では `codex exec` 経由で画像生成の実績がある**（`scripts/generate-images-codex.js` が各 `slide-NN-{slug}.prompt.md` を読み、codex exec へ画像生成を依頼する。1枚 1-2 分・バッチ並列可）。したがって codex exec は本節の「確認済み text-to-image バックエンドの具体例」として扱える。ただし上記2の原則どおり、`codex` という素の CLI 名自体は画像生成モデルではないため、`meta.source` には実体名 `codex-image2` を記録し、plain `codex` 単体を source にはしない。codex exec が起動・生成可能かは着手前に必ず確認し、未確認のまま量産へ進まない（コストはユーザーの codex / OpenAI 課金に発生する）。

なお codex は **imagegen（text-to-image 拡散モデル）を明示しないとコード描画（PIL / matplotlib / SVG）に退化**し、単色角丸ボックス＋テキストの平坦図になる（パイロット実証）。これを避けるため、手書きの `codex exec` ではなく必ず `scripts/generate-images-codex.js` の強制プロンプト経由で呼ぶ（imagegen 使用・コード描画禁止・リッチなアイソメイラスト維持を明示する文言を実装済み）。

### バックエンドが使えない / 壊れている場合のフォールバック順

| 順 | フォールバック | 内容 |
|----|---------------|------|
| (a) | OpenAI 画像 API スクリプト | gpt-image 等を呼ぶスクリプトで生成。APIキーはスクリプトが直接読み、Claude のコンテキストに載せない |
| (b) | ユーザーの手元ツール + 生成プロンプトキット | ChatGPT / Midjourney 等。`{slug}.prompt.md` を渡してユーザー自身が生成 |
| (c) | SVG2 / CSS で実装 | skill 既定（§1）に戻し、インライン SVG2 / CSS / D3 で図解する |
| (d) | プレースホルダ枠で HTML 先行 | 画像欄を空枠で先に組み、後からアセットを差し替える |

確認の結論（どのバックエンドが使えるか、使えない場合どのフォールバックを採るか）は、生成着手前にユーザーへ提示する。

### 1.3 全面画像生成モードへの分岐

ユーザーが「各ページを1枚ずつ生成画像にする」「スライド全体を生成画像で構成する」「Codex Image 2 / image2 でページ画像を生成する」と明示した場合は、本ワークフローの通常差し替え判定を短絡し、`references/full-image-deck-method.md` を適用する。

この場合の生成画像は背景素材ではなく、各ページの主キャンバスである。HTML では規定クラス **`.ai-slide-canvas`**（後方互換エイリアス `.slide-fullbg` / `.slide-bg` / `[data-role="main-canvas"]`）に置き、`object-fit: contain` で表示する（`cover` による端切れ禁止・印刷は A4横 16:9 letterbox 167mm）。表示・印刷フィット契約の正本は [full-image-deck-method.md §0.3](full-image-deck-method.md)。生成前に必ず `assets/style-genome-kanagawa-comic-diagram.json` を project-local `assets/generated/style-genome.json` へコピーし、STYLE BIBLE と全 prompt/meta に反映する。`05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` の画風再現が指定されている場合は、その参照デッキの project-local genome / prompt / meta を優先して差分を整理する。

全面画像生成モードの必須検証（検証ゲート接続）:

```bash
node scripts/validate-ai-image-assets.js <slide-dir> --full-image-deck --strict-style-genome --check-genome-content
node scripts/validate-print.js <slide-dir>/index.html
node scripts/evaluate-deck.js <slide-dir>
```

`evaluate-deck.js` は full-image-deck を検出すると `validate-print.js` と `validate-ai-image-assets.js --full-image-deck --strict-style-genome --check-genome-content` を spawn し、CRITICAL / exit 1 で総合 verdict を FAIL にする。詳細は [full-image-deck-method.md §6](full-image-deck-method.md) を正本とする。

---

## 2. 判定マトリクス

| コンテンツ | 推奨 | 理由 |
|------------|------|------|
| 抽象概念の比喩図 | 明示指示時のみAI画像 + HTMLラベル | 記憶に残る質感・構図を作れる |
| 業務シーン・顧客体験 | 明示指示時のみAI画像 + WebP | 人の感情や利用状況を表現しやすい |
| プロダクト風モック | 明示指示時のみAI画像 + HTML注釈 | 実画面が未確定でも雰囲気を伝えられる |
| 章扉・タイトル背景 | 明示指示時のみAI画像 | 第一印象を強化できる |
| 漫画チックな説明文入り図解 | `style-genome-packaging.md` Pattern A | 短い説明文・吹き出し・簡易表を画風込みで作り込める。`overlayText` fallback必須 |
| HTMLシャーシ付き図解 | `style-genome-packaging.md` Pattern B | 既存UIを保ち、画像は背景・モチーフに限定できる |
| フロー・階層・マトリックス | SVG2 | 座標・矢印・ラベルの精度が重要 |
| 数値グラフ | D3/SVG | データ正確性が重要 |
| テキスト量が多い図解 | HTML/SVG | 画像生成の文字化けリスクが高い |
| 実在ブランド・人物 | ユーザー提供素材 | 権利・正確性確認が必要 |
| コード（slide-code / slide-code-compare）・数式・精密数値表・コマンド列／APIレスポンス例 | 実HTMLコードブロックで描画（画像化しない） | 逐語の正確性・コピー可能性・印刷品質を担保するため |

コード系 slideType（slide-code / slide-code-compare）は対象外であり、`aiVisual.pattern` を `image-only` にできず、`aiVisual.textPolicy` を `baked-with-overlay` にできない（常に実HTMLコードブロック `.code-block` / `.code-compare-body` で描画する）。この機械契約は `scripts/validate-structure.js`（V-043: slideType×aiVisual 整合）と `schemas/structure.schema.json` を正本とし、本表はその人間可読の写しである。

### 2.1 モード別テキスト方針

`pattern` / `textPolicy` / `backgroundSource` の値域の定義は `style-genome-packaging.md` §4 を正本とする（本表は再定義せず参照に寄せる。DRY）。

| モード | `pattern` | `textPolicy` | 画像内テキスト | 正本 |
|---|---|---|---|---|
| 通常AI画像差し替え | `html-composite` | `overlay-only` | 禁止 | HTML/SVG |
| 部分AI画像化 | `html-composite` → `overlay-only` / `html-primary` → `none` | （pattern 別） | 禁止 | HTML/SVG |
| 全面AI画像化 | `image-only` | `baked-with-overlay` または `overlay-only` | 明示時のみ許可 | `overlayText` |
| 漫画チック説明図 | `image-only` | `baked-with-overlay` | 短文・少量のみ許可 | `overlayText` |
| 焼き込みテーブル | `image-only` | `baked-with-overlay` | 表の見出し+全セルを画像内に verbatim 焼き込み（`tableMode: illustrated-full-table`・`tableContent` で運ぶ）。`camera=structural`（near top-down）推奨・`negativeSpecific` 必須（行数/列数の取り違え禁止）。HTMLのピンポイント重ねは使わない（位置ズレ回避） | `overlayText`（表全文） |

`pattern` と `textPolicy` の対応（`image-only`→`baked-with-overlay`/`overlay-only`、`html-composite`→`overlay-only`、`html-primary`→`none`）の正本は `style-genome-packaging.md` §4 と `scripts/validate-ai-image-assets.js` に置く。

`baked-with-overlay` は例外モードである。使用時は prompt/meta/structure.md のすべてに同じ値を記録し、`overlayText` を空にしない。

---

## 3. 保存規約

```
assets/generated/
  slide-03-growth-loop.png
  slide-03-growth-loop.webp
  slide-03-growth-loop.prompt.md
  slide-03-growth-loop.meta.json
```

`meta.json` 例:

```json
{
  "slide": 3,
  "asset": "assets/generated/slide-03-growth-loop.webp",
  "source": "confirmed-text-to-image-backend",
  "decision": "generate-image",
  "pattern": "html-composite",
  "textPolicy": "overlay-only",
  "backgroundSource": "raster",
  "reason": "SVGでは表現しづらい成長循環の質感を高めるため",
  "alt": "成長サイクルを示す抽象的なループ状ビジュアル",
  "overlayText": ["認知", "体験", "継続"]
}
```

---

## 4. 生成プロンプト仕様

### 4.1 必須要素

- スライド番号と1メッセージ
- Purpose: なぜこの画像が必要か
- Audience takeaway: 聴衆が1文で理解すべきこと
- Background / context: 場面・前提・前後スライドとの接続・デッキ内役割
- Intended use: presentation infographic / explanatory diagram などの成果物用途
- Subject: 視覚化したい概念を具体名詞・視認可能属性で書いた主題
- Diagram structure: 要素数、相対配置、矢印/レイヤ/比較軸などの構造
- Layout: `grid` / `zones` / `readingOrder` / `focalPoint` / `emphasis`
- Dominant accent: `accent`（支配色）。ビルダーが HEX へ解決し「Dominant accent for this slide」行として本文へ展開する。60-30-10 の10%主役色を1色に固定する（`accent=multi` は「1ゾーン1アクセント＋1色が60%」）
- Negative（構造系は必須）: `negativeSpecific`。`camera=structural`（順序/向き/個数が効く図）では必須で、誤ノード数・逆向き・対称崩れなど間違えてはいけない構成を列挙する。`illustrated-full-table`（焼き込み表）も `negativeSpecific` 必須で、表の行数・列数の取り違え禁止（行/列を増減・重複・捏造しない）を毎回宣言する
- Table（表を画像内に焼く場合）: `tableMode: illustrated-full-table` + `tableContent`（`headers` / `rows[][]` / `monospaceColumns?` / `caption?`）。各セルは短語（14字以内）を verbatim、列数・行数は固定。builder が列数/行数明示・罫線・整列・legible・行列増減禁止を本文展開する。`textPolicy: baked-with-overlay` 固定、`overlayText` に表全文を保持（崩れ時 fallback）。`camera=structural`（near top-down）を推奨し、表セルが正対して可読性が上がるようにする。**14字超の境界事例**: 固有名詞・コマンドが14字を超えるセル（例 `dependency-cruiser`=18字）が出る表は焼き込みをやめ `html-overlay-table` へ切り替える（`tsc --noEmit`=12字は範囲内）。料金/精密数値/長文/複数行コードも HTML 側（`html-overlay-table` / `html-primary`）へ
- Generation: `modelSnapshot` / `quality` / `size`（焼き込み表は `quality: high` 推奨）
- 16:9または配置先に合わせた背景/カットアウト指定（バックエンド対応を確認した場合のみ）
- Kanagawaテーマに合う色・質感
- HTMLテキストを重ねる余白位置
- `pattern` と `textPolicy`
- 禁止事項

### 4.2 禁止事項

- 画像内の読める文字
- ロゴ、透かし、架空ブランド名
- 細かすぎるUI文字
- 過度に暗い背景
- スライド本文を隠す強いノイズ
- 実在人物に見える肖像の無断生成

`textPolicy: baked-with-overlay` のときだけ「画像内の読める文字」を禁止事項から外せる。ただし、短文・大きな文字・低密度に限定し、`distorted text, garbled characters` は必ず禁止語に残す。

### 4.3 標準テンプレート

```markdown
Create a premium 16:9 presentation visual for slide {{slide_no}}.

Intended use: presentation infographic / explanatory diagram for slide {{slide_no}} of a deck.
Purpose (why this slide exists): {{purpose}}.
Audience takeaway (one sentence the viewer should grasp): {{audienceTakeaway}}.
Background / context: {{background}}.

Layout: grid={{grid}}; zones=[{{area}}:{{content}}; ...]; reading order={{a > b > c}}; focal point={{area}}; emphasis={{emphasis}}.

Subject:
{{subject}}

Diagram structure:
{{diagramStructure}}

Style: clean editorial consulting deck, Kanagawa-inspired palette, bright white base, vivid blue/aqua/pink accent, soft realistic depth, crisp edges, professional.
Composition: leave negative space on {{overlay_area}} for HTML title and labels. Main subject should remain inside safe margins.
Generation: model={{modelSnapshot}}, quality={{quality}}, size={{size}}.
Do not include readable text, logos, watermarks, UI gibberish, or brand marks.
The image must work as a diagram-like visual asset, not stock photography.
```

### 4.4 図タイプ別 構図プリセット集

`image-deck-plan.schema.json` の `layout` フィールド（`grid` / `zones` / `readingOrder` / `focalPoint` / `emphasis`）を埋める際は、まず本表で図タイプに合うプリセットを引く。builder はここで決めた値を prompt.md の `Layout: grid=...; zones=[...]; reading order=...; focal point=...; emphasis=...` 行へ決定論的に展開する。

語彙の値域（正本は schema）:

- `grid` enum: `left-right` / `top-bottom` / `center-radial` / `grid-2x2` / `free`
- `zones`: `{area, content}` の配列。`area` enum= `top` / `bottom` / `left` / `right` / `center` / `foreground` / `background`
- `readingOrder`: `area` を視線順に2件以上並べる。記法 `a > b > c`（半角の `>` を使い全角矢印は使わない）
- `focalPoint`: `area` を1件指定。`emphasis`: 強調内容を表す自由文

| 図タイプ | grid | zones（area:content） | readingOrder | focalPoint | emphasis | gpt-image-2 1行プロンプト例（英語・短く） |
|---|---|---|---|---|---|---|
| プロセス/フロー図 | left-right | left:起点 / center:変換ステップ / right:成果 | left > center > right | center | 各ゾーンを連結する矢印で時系列を強調する | left-to-right process with three rounded isometric platforms connected by glowing arrows; focal point at center |
| 比較/対比図 | left-right（密度高なら grid-2x2） | left:案A / center:対比軸またはVS / right:案B | left > center > right | center | 中央の対比軸で左右の差を際立たせる | side-by-side comparison of two isometric scenes split by a central contrast axis; focal point at center |
| 構造/関係図 | center-radial | center:中核 / foreground:主要素 / background:文脈 | center > foreground > background | center | 中核から放射する関係線で主従を示す | central hub with radiating elements in foreground and soft contextual layer in background; focal point at center |
| 因果図 | top-bottom | top:原因 / center:メカニズム / bottom:結果 | top > center > bottom | center | 上から下への因果を矢印で示し、因果ループは戻り矢印（return arrow）で表す | top-to-bottom causal chain with downward arrows and a curved return arrow forming a feedback loop; focal point at center |
| 階層/ピラミッド図 | top-bottom | top:頂点または結論 / center:中間層 / bottom:土台 | top > center > bottom（積み上げ説明なら bottom > center > top） | top | 頂点を最大・最濃で強調し下へ段階的に広げる | layered pyramid with a strong apex on top widening to a broad base at bottom; focal point at top |
| 四象限/マトリクス図 | grid-2x2 | top:上段2象限 / left:左列 / right:右列 / bottom:下段2象限 | top > right > bottom > left（左上 > 右上 > 右下 > 左下） | center | 中央で交差する2軸を基準に4象限を均等配置する | 2x2 quadrant matrix with two crossing axes meeting at center, four balanced isometric tiles; focal point at center |

補足:

- `zones` は最小構成を示す。実際の図に応じて area を足してよいが、`readingOrder` は使用した area で必ず整合させる。
- 四象限図は area enum に「左上/右上」が無いため、`top`/`bottom`/`left`/`right` を組み合わせて表現し、`readingOrder` の括弧内に象限の巡回順を補記する。
- 1行プロンプト例は構図確定用の骨子であり、§4.3 標準テンプレートの Style / 禁止事項と併用する（単独で使わない）。

---

### 4.5 再現性アンカー（第2弾・gpt-image-2）

gpt-image-2 は seed 非対応で完全再現ができない。再現性はプロンプト不変＋参照画像チェーン＋評価で担保する。per-slide plan に次を書く。`generation` は必須、`styleReference` はデッキ統一が必要な場合に使う任意項目で、ビルダーが prompt.md と meta へ展開する。

- `styleReference`: 基準ページ(通常 slide-01)を `anchorSlug` に指定し全ページが image-to-image 参照。`inheritMode`(style-only/style-and-layout/full)・`preserve[]`(必ず保持)・`change[]`(変更)で継承を精密化。generate-images-codex.js が基準画像を codex exec 指示文へ添付(エイリアス安全・-i フラグ不使用)。
- `generation`: `modelSnapshot`(既定 gpt-image-2-2026-04-21)・`quality`(密図は high)・`size`(2560x1440・両辺16px倍数)。meta に記録し再生成時の同条件再現に使う。
- genome の `lockTiers`(tier1絶対不変/tier2維持/tier3可変)・`consistencyAnchors` が全プロンプトへ展開され画風を固定する。
- 生成後は `node scripts/evaluate-image-consistency.js <deck> --threshold 0.8` で一貫性(lockTiers.tier1+consistencyAnchors)を LLM-judge 採点し、閾値割れページの再生成推奨を得る(破壊操作なし・目視の前段ゲート)。

## 5. HTML/CSS組み込み

### 5.1 通常配置

```html
<figure class="ai-diagram">
  <picture>
    <source srcset="assets/generated/slide-03-growth-loop.webp" type="image/webp">
    <img src="assets/generated/slide-03-growth-loop.png" alt="成長サイクルを示す抽象的なループ状ビジュアル">
  </picture>
  <figcaption class="sr-only">成長サイクルの概念図</figcaption>
</figure>
```

```css
.ai-diagram {
  margin: 0;
  width: 100%;
  height: 100%;
}

.ai-diagram img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
```

### 5.2 テキストオーバーレイ

```html
<div class="visual-stage">
  <picture class="ai-visual">...</picture>
  <div class="visual-overlay visual-overlay--right">
    <h2>導入後の変化</h2>
    <p>現場の判断速度が上がる</p>
  </div>
</div>
```

画像とテキストの責務を分離する。日本語の正確性はHTML側で担保する。

---

## 6. 検証

1. `node scripts/convert-to-webp.js <slide-dir> --quality 90`
2. 通常差し替え: `node scripts/validate-ai-image-assets.js <slide-dir> --strict-style-genome`
   全面画像生成モード: `node scripts/validate-ai-image-assets.js <slide-dir> --full-image-deck --strict-style-genome`
3. `node scripts/verify-slides.js ./index.html --check-ratio`
4. 画面表示で主要被写体の切れ、テキスト重なり、コントラストを確認
5. 印刷/PDFで画像が欠落しないことを確認
6. `structure.md` に以下が同期されていることを確認

同期項目:

- 画像パス
- alt
- pattern
- textPolicy
- styleGenome（使用時）
- prompt/metaパス
- 差し替え理由
- HTMLオーバーレイのテキスト
- 修正履歴

---

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-06 | 初版: Codex/imagegenによる図解・ビジュアル差し替えワークフローを追加 |
| 1.1.0 | 2026-05-06 | 画像生成を明示指示時のみ起動する任意フローへ変更。デフォルトはSVG/CSS/JS/HTML構成と明記 |
| 1.2.0 | 2026-05-06 | prompt/meta/WebPの機械検証スクリプトと標準プロンプトテンプレートの参照を追加 |
| 1.3.0 | 2026-06-02 | §1.2「着手前バックエンド確認（必須）」を追加。実際に使える text-to-image バックエンド（MCP / CLI / 画像API）を生成着手前に確認する手順、codexは画像生成器でない旨、(a)〜(d)のフォールバック順を明記 |
| 1.4.0 | 2026-06-23 | スタイルゲノム量産、Pattern A/B、`textPolicy` を追加。通常は画像内テキスト禁止、漫画/全面画像化の明示時のみ `baked-with-overlay` を許可する形に整理 |
| 1.5.0 | 2026-06-24 | 正準モデル整合（elegant-review）。§2.1 で `textPolicy` の `html-primary` を `none` へ修正（部分AI画像化は `html-composite`→`overlay-only` / `html-primary`→`none`）。`pattern`/`textPolicy`/`backgroundSource` の値域定義を `style-genome-packaging.md` §4 と `scripts/validate-ai-image-assets.js` に一本化（DRY）。§3 meta 例に `backgroundSource` を追加 |
| 1.6.0 | 2026-06-24 | ビルダー連携（SKILL.md v8.2.0）。§1.2 に「この環境での確認済みバックエンド（codex exec）」を追加。codex exec はこの環境で画像生成の実績がある確認済みバックエンドの具体例（`scripts/generate-images-codex.js` 経由）であり、`meta.source` には実体名 `codex-image2` を記録する一方、plain `codex` 単体を source にしない原則は維持 |
| 1.6.1 | 2026-06-24 | パイロット実証の知見反映。§1.2 codex exec 記述に「codex は imagegen（text-to-image 拡散モデル）を明示しないとコード描画（PIL/matplotlib/SVG）に退化し平坦なボックス図になるため、`scripts/generate-images-codex.js` の強制プロンプト経由で呼ぶ」を追記 |
| 1.6.2 | 2026-06-24 | 実装整合（elegant-review・D1/D2/D3）。§1.3 全面画像生成モードの分岐に主キャンバスクラス規定（`.ai-slide-canvas`＋後方互換エイリアス・`object-fit:contain`・印刷 16:9 letterbox 167mm・cover 禁止）を追記し、フィット契約の正本を `full-image-deck-method.md §0.3` に参照（DRY）。必須検証に `validate-print.js` と `evaluate-deck.js`（full-image-deck 検出時に validate-print / validate-ai-image-assets を spawn し FAIL 連動）の検証ゲート接続を追加 |
| 1.7.0 | 2026-06-25 | §4.4「図タイプ別 構図プリセット集」を新設。`image-deck-plan.schema.json` の `layout`（grid/zones/readingOrder/focalPoint/emphasis）を埋めるための6図タイプ（プロセス/フロー・比較/対比・構造/関係・因果・階層/ピラミッド・四象限/マトリクス）プリセットを表で提供し、各タイプに gpt-image-2 用の英語1行プロンプト例を添付。builder が prompt.md の `Layout:` 行へ決定論展開する際の参照元とする |
| 1.8.0 | 2026-06-25 | 再現性第2弾（elegant-review・D10/D11）。§4.1 必須要素に Dominant accent（`accent` を HEX 解決し「Dominant accent for this slide」行を本文展開・60-30-10 の主役色固定）と 構造系の `negativeSpecific` 必須（`camera=structural` は誤ノード数/逆向き/対称崩れを列挙）を追加。builder（build-image-prompts.js v8.2.4）が accent をプロンプト本文へ射影し `meta.dominantAccentHex` を記録、validator（v4）が支配色のprompt反映を意味照合、schema が camera=structural→negativeSpecific を条件付き必須化、evaluate-image-consistency が per-slide 構図（emphasis/focalPoint/negativeSpecific）を rubric へ追加、generate-images-codex が「prompt.md が画像内テキストの単一正本」を明文化 |
| 1.9.0 | 2026-06-25 | 焼き込みテーブルモード（baked-table・D12）。空枠+HTMLピンポイント重ね（位置ズレの原因）を image-only デッキで廃し、表の見出し+全セルを画像内に verbatim 焼き込む `tableMode: illustrated-full-table` を追加。§2.1 にモード行、§4.1 に Table 必須要素を追記。builder（v8.2.5）が `tableContent{headers, rows[][], monospaceColumns?, caption?}` から列数/行数明示・各セルverbatim引用・罫線/整列/legible・行列増減禁止の決定論ブロックを展開し `meta.tableContent` を記録、schema が enum+`tableContent`+allOf（tableMode→tableContent+textPolicy=baked-with-overlay）を追加、validator（v5）が textPolicy固定・セルの prompt verbatim 展開を意味照合・quality!=high を warning。gpt-image-2 の日本語+短英数字セル焼き込み精度向上（quality=high・verbatim引用・短語≤14字・monospace列）を反映。料金/精密数値/長文/複数行コードは html-overlay-table / html-primary 維持 |
| 1.9.1 | 2026-06-25 | 焼き込み表の境界条件・負制約の明記（elegant-review 再検証）。§4.1 Table 要素に 14字超の境界事例（`dependency-cruiser`=18字 を含む表は `illustrated-full-table` をやめ `html-overlay-table` へ切替／`tsc --noEmit`=12字は範囲内）と、`illustrated-full-table` の `negativeSpecific` 必須化（行数・列数の取り違え禁止を毎回宣言）・`camera=structural`（near top-down）推奨を追記。§2.1 モード表の焼き込みテーブル行にも camera=structural 推奨・negativeSpecific 必須を反映 |
