# AI Image Diagram Prompt Template

Use this template only when the user explicitly asks for AI-generated images or generated image diagram replacement, and a real text-to-image backend has been confirmed.

注記: コード・数式・精密数値表はこのプロンプトテンプレートの対象外。コードは画像化せず実HTMLコードブロック（slide-code / slide-code-compare）で描画する。

注記（モデル実体）: ユーザートリガー語として「Codex Image 2 / image2 / Image 3」などの呼称はそのまま受け付けるが、実体は最新の gpt-image-2（2026-04・Codex CLI の `$imagegen` / `codex exec` が内部使用するモデル）である。トリガー語は後方互換のため残し、meta の source には確認済みバックエンド名を記録する。

注記（gpt-image-2 のプロンプト記述順）: 本ビルダー（`build-image-prompts.js` の `buildPrompt()`）は**制約先行方式**を採る。不変制約（STYLE LOCK / Geometry lock / consistency anchors）を毎ページ先頭で逐語固定してから、Intended use → Purpose → Background（デッキ内文脈）→ Layout → Dominant accent → Subject → Negative の順で展開する。gpt-image-2 公式の Scene-first 推奨（Scene→Subject→Key details→Constraints+Use case）とは並びが異なるが、デッキ一貫性のため不変要素を先頭固定する設計を優先する。なお本テンプレートの **Background はデッキ内の前後文脈であり、画面シーン（床・空間）ではない**。画面シーンは `subject` 冒頭に書く（例: faint dotted isometric grid floor on off-white #FAFAFA）。曖昧語（beautiful / きれい / high quality）は禁止。具体名詞＋視認可能な属性で書く。正確な展開順の正本は本ファイル「ビルダーが自動展開する固定行」節とする。

注記（v8.2.0・ビルダー自動展開）: 全面画像生成モードでは、本テンプレートのプレースホルダ（`{{STYLE_BIBLE}}` / `{{expanded_style_bible_from_assets_generated_style_genome_json}}` 等）を手動で展開しない。`scripts/build-image-prompts.js` の `buildPrompt()` が `assets/generated/image-deck-plan.json`（per-slide 差分・`schemas/image-deck-plan.schema.json` 準拠）と `assets/generated/style-genome.json` を合成し、STYLE LOCK / MODE（Intended use）/ GEOMETRY LOCK / Layout / Subject / Negative の各行を決定論で展開して `slide-NN-{slug}.prompt.md` / `slide-NN-{slug}.meta.json` を機械生成する。したがって本テンプレートは**ビルダー出力の参照仕様（生成される prompt.md がどんな構造になるかの目安）であり、buildPrompt() の出力が正本**。ビルダーを使わない単発の手動差し替え時にのみ手で埋める。

### ビルダーが自動展開する固定行（buildPrompt() が正本・手で書かない）

以下は `buildPrompt()` が genome と per-slide から毎ページ同一構造で展開する。順序もこの通り。

```text
STYLE LOCK (keep identical on every page):
- Art style: ...
- Camera: ...; structural slides use ...
- Palette (...): ...; 60-30-10 rule, one dominant accent per image.
- Composition: 16:9 (2560x1440). Keep safe margins ... clear for overlay text. ...
- In-image text policy: ...
- Content adaptation: ...
- Print / HTML fit: ...
Intended use: presentation infographic / explanatory diagram for slide N of a deck.   <- MODE（Use case 明示）
Geometry lock: isometric, 30-degree axonometric projection, equal scale on all axes, no perspective foreshortening.   <- GEOMETRY LOCK
[空行]
Layout template: ...; Density level: ...
Figures: ...; AI robot mascot: ...
Table / matrix handling: ...                （tableMode != none のときのみ）
Image fit contract: ...
Safe area (auto-computed ...): ...
Print intent: ...
[空行]
Purpose (why this slide exists): ...        <- Purpose (Why)
Audience takeaway (one sentence ...): ...    <- Audience takeaway (Who)
Background / context: ...                     <- Background (Context)
Layout: grid=...; zones=[area:content; ...]; reading order=a > b > c; focal point=...; emphasis=...   <- Layout/Zones (Where)
Dominant accent for this slide (the 10-percent lead color in the 60-30-10 split): <name> <hex>   <- Dominant accent (accent を HEX 解決して支配色を明示。accent=multi は「1ゾーン1アクセント+1色が60%」)
[空行]
<subject>                                     <- Subject (What)
<diagramStructure>
Required motifs from style genome: ...
Camera: ...
[空行]
Style: ...
Consistency anchors (repeat every page): ...
[空行]
Negative: ...                                 <- Constraints (How)
```

MODE 行（Intended use）と GEOMETRY LOCK は再現性 must のため必ず展開される。全面画像生成モードでは Purpose / Audience takeaway / Background / Layout / Generation も必須であり、`image-deck-plan.json` に値が無い場合は `build-image-prompts.js` がビルドを停止する。値を省略して「なんとなく良い絵」を生成してはならない。

注記（焼き込みテーブル・`tableMode: illustrated-full-table`）: 表を画像内に見せる場合、HTMLを画像上のピンポイント位置へ重ねるのは位置ズレが起きるため使わず、**表ごと画像に焼き込む**。per-slide に `tableContent`（`headers` / `rows[][]` / `monospaceColumns?` / `caption?`）を置くと、builder が「列数・行数を明示し、各セルを二重引用で verbatim 指定、罫線・整列・legible、コマンド列は monospace、行列の増減/重複/捏造を禁止」する決定論テーブルブロックを Dominant accent 行の直後に展開する。`textPolicy: baked-with-overlay` 固定で、`overlayText` に表全文（全セル）を正本保持し、画像の文字が崩れたときだけ HTML 表へ fallback する。各セル14字以内・最大5列×6行・`generation.quality: high` 推奨。料金・精密数値・長文・複数行コードは焼き込まず `html-overlay-table` / `html-primary` へ回す。

```markdown
Create a premium 16:9 presentation visual for slide {{slide_no}}.

Core message:
{{message}}

Visual concept:
{{concept}}

Audience:
{{audience}}

Style:
Clean editorial consulting deck, Kanagawa-inspired palette, bright white base, vivid blue/aqua/pink accent, soft realistic depth, crisp edges, professional.

Composition:
Leave clear negative space on {{overlay_area}} for HTML title and labels.
Keep the main subject inside safe margins.
The image must work as a diagram-like visual asset, not stock photography.

Do not include:
- readable text
- Japanese or English labels
- logos
- watermarks
- UI gibberish
- brand marks
- overly dark backgrounds

Output:
PNG source image for `assets/generated/slide-XX-{slug}.png`, then convert to WebP.
```

---

## バリアント: 人物なし・非焼き込み・アイソメ アイコン風

部分AI画像化（バランス型）で使うアートスタイル統一バリアント。先頭に `{{STYLE_BIBLE}}` プリアンブルを置き、per-slide では被写体・構図・カメラ角・accent の差分だけを記述する。生成器は事前確認済みの text-to-image バックエンドを用い、画像内テキストは焼き込まず HTML で上乗せする（overlayText が正）。

```markdown
{{STYLE_BIBLE}}

Create a 16:9 presentation visual for slide {{slide_no}} (icon-style isometric illustration, no people).

Per-slide diff only (style fixed by STYLE BIBLE above):
- Subject: {{subject_no_people}}
- Composition: {{composition}}
- Camera angle: {{camera_angle}}
- Accent color: {{accent_hex}}

Style:
Cute flat isometric illustration, 30-degree top-down view, rounded geometric shapes, soft single shadow, bright white base with one accent color, airy negative space, clean editorial consulting style, no people.

Do not include / Negative:
people, humans, figures, faces, hands, photorealistic, photo, 3d render, glossy, metallic, neon, high saturation, full-frame gradient, clutter, logos, brand marks, watermarks, baked text, letters, words, numbers, captions, labels, typography, UI text, distorted/garbled characters, emoji.

Generator: {{confirmed_text_to_image_backend}}.
Text policy: do not bake any text into the image. All on-slide text is overlaid via HTML (overlayText is the source of truth).

Output:
PNG source image for `assets/generated/slide-NN-{slug}.png`, then convert to WebP.
```

---

## バリアント: kanagawa-comic-diagram（assets/generated画像群の再現）

`05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` に含まれている画像群に近い、漫画チックな説明図を量産する時に使う。STYLE GENOME は同梱プリセット `assets/style-genome-kanagawa-comic-diagram.json` をコピーした project-local の `assets/generated/style-genome.json` を正本とし、per-slide では差分だけを書く。

### 全面画像生成モード共通プリセット（各ページ=1枚の主キャンバス）

ユーザーが「各ページを1枚ずつ画像生成」「スライド全体を生成画像で作る」「Codex Image 2 / image2 でページ画像を生成」と明示した場合に使う（呼称はトリガー語・実体は gpt-image-2）。生成画像は背景ではなく、そのページの主キャンバスである。HTML は正テキスト fallback、コード、QR/ロゴ、ページ UI の正確性レイヤとして使う。

この共通プリセットでは、ビルダーが上記「自動展開する固定行」（STYLE LOCK / MODE / GEOMETRY LOCK 等）を毎ページ展開する。per-slide で書くのは下記 5W1H スロットの値だけ。各スロットは役割（Background=デッキ内文脈 / Subject=主題・画面シーン / Style & Constraints=素材+禁止 / MODE 行=用途）に対応する。実際の展開順はビルダーの制約先行順（上記「ビルダーが自動展開する固定行」節が正本）であり、gpt-image-2 公式の Scene-first 推奨とは並びが異なる。

#### 5W1H スロット（per-slide で埋める値・各 1行で何を書くか＋悪い例/良い例）

- **Purpose (Why)** — `purpose`: このスライドが存在する理由を1文。
  - 悪い: きれいに見せたい。 良い: 導入前後の作業フロー差を1枚で対比し、削減対象を示す。
- **Audience takeaway (Who)** — `audienceTakeaway`: 視聴者が掴むべき1文。
  - 悪い: すごいと思ってもらう。 良い: 手作業3工程が自動化2工程に置き換わると一目で分かる。
- **Background (Context)** — `background`: デッキ内の前後文脈・聴衆の前提（画面シーンではない。画面シーンは `subject` 冒頭に書く）。
  - 悪い: ビジネスの背景。 良い: デッキ中盤、各工程の詳細に入る前に全体像を示すスライド。聴衆は工程名をまだ詳しく知らない前提。
- **Subject (What)** — `subject` + `diagramStructure`: 主題と図の骨格。
  - 悪い: 業務改善の図。 良い: 左に手作業デスク、右に自動化パイプライン、中央に右向き矢印フロー。
- **Layout / Zones (Where)** — `layout`（下記 enum 語彙）: 配置・読み順・主役・強調。
  - 悪い: バランス良く配置。 良い: grid=left-right; zones=[left:手作業; right:自動化]; reading order=left > right; focal point=center; emphasis=矢印。
- **Style & Constraints (How)** — `accent` / `motifs` / `camera` ＋ ビルダー展開の Style・Negative: 素材・配色・禁止。
  - 悪い: おしゃれな色で高品質に。 良い: accent=#3B6EA5、navy 輪郭、isometric タイル、neon と写真調を禁止。

#### Layout / Zones の構造化語彙（schema enum・固定値）

`layout` は per-slide オブジェクト。ビルダーが `Layout: grid=...; zones=[...]; reading order=...; focal point=...; emphasis=...` 行に展開する。

- `grid`: `left-right` / `top-bottom` / `center-radial` / `grid-2x2` / `free`
- `zones`: 各要素 `{ area, content }`。`area` は `top` / `bottom` / `left` / `right` / `center` / `foreground` / `background`。`content` は短語。
- `readingOrder`: `area` の並び（読み順）。
- `focalPoint`: `area`（主役の置き場所）。
- `emphasis`: 強調点を自由文で1語〜数語。

#### Text policy（画像内テキストの書式）

- baked-with-overlay 時に画像へ描く日本語ラベルは「引用符で囲む＋verbatim（一字一句改変禁止）＋1〜4語に短語化」して `bakedText` に列挙する。
  - 例: `"自動化"` / `"手作業3工程"`。文章や長いキャプションは画像に焼かない。
- 長文・正確な値（料金・固有名詞・コード）は画像に焼かず、HTML 前面に `overlayText` として重ねる（overlayText が正テキスト）。
- 生成後は必ず目視で文字化け・誤字を校正する。崩れていたら baked をやめ overlay-only に切り替える。

```markdown
（ビルダー自動展開: STYLE LOCK / Intended use（MODE）/ Geometry lock / Layout template / Figures /
 Table handling / Image fit / Safe area / Print intent / Reference images(styleReference時) / Lock tier 1-2 / Variable details(tier3) / generation コメント ... ここまで buildPrompt() が plan+genome から展開）

Purpose (why this slide exists): {{purpose}}
Audience takeaway (one sentence the viewer should grasp): {{audienceTakeaway}}
Background / context: {{background}}
Layout: grid={{grid}}; zones=[{{area}}:{{content}}; ...]; reading order={{a > b > c}}; focal point={{area}}; emphasis={{emphasis}}.

{{subject}}
{{diagramStructure}}
Required motifs from style genome: {{motifs_and_primitives}}.
Camera: {{camera}}.

Style: {{genome.promptSuffix}}
Consistency anchors (repeat every page): {{genome.consistencyAnchors}}.

Negative: {{genome.negativePrompt}}{{ + slide.negativeSpecific}}
```

per-slide 入力（image-deck-plan.json の1スライド分・5W1H に対応）:

```text
- pattern: {{image-only / html-composite}}        Use case 分岐
- textPolicy: {{baked-with-overlay / overlay-only}} Text policy
- purpose / audienceTakeaway / background           Why / Who / Context
- subject / diagramStructure                        What
- layout: {grid, zones, readingOrder, focalPoint, emphasis}  Where
- accent / motifs / camera                          How（Style 詳細）
- bakedText（baked-with-overlay 時のみ・引用符短語）  How（焼き込みテキスト）
- overlayText（HTML 前面の正テキスト）               正テキスト fallback
```

meta.json（ビルダーが併産・主要キー）:
pattern, textPolicy, backgroundSource, styleGenome=assets/generated/style-genome.json, source={{確認済みバックエンド（実体 gpt-image-2）}}, builtBy=build-image-prompts, decision=generate-image, reason, alt, overlayText, prompt=assets/generated/slide-NN-{slug}.prompt.md, imageFit, layoutTemplate, densityLevel, tableMode, figures, robotMascot, purpose, audienceTakeaway, background, layout。

### Pattern A: 画像生成完結型（説明文・吹き出し・簡易表を画像内に含める）

5W1H 対応: Why=Core message（何のための図か）/ What=Visual structure（subject+diagramStructure）/ Where=Composition の配置（上の Layout enum で記述）/ How=Style suffix + Negative + 画像内 baked テキスト。textPolicy=baked-with-overlay の画像内テキストは「引用符＋verbatim＋1〜4語短語」、長文は焼かず overlay に回す。生成後は目視校正。

表を Pattern A（image-only）で見せる場合は、見出し＋全セルを画像内に焼き込む `tableMode: illustrated-full-table` を使う（`tableContent`{headers, rows[][], monospaceColumns?, caption?} で各セルを一字一句運び、各セル14字以内・最大5列×6行・コマンド列は monospace・`generation.quality: high` 推奨・`camera=structural` 推奨）。HTML を画像上のピンポイント位置へ重ねるのは位置ズレするため image-only では使わず、`overlayText` に表全文を正本保持して崩れ時のみ HTML 表へ fallback する。精密な数値・料金・頻繁更新・長文・複数行コードは焼き込まず html-overlay-table / html-primary へ回す（詳細は上記「焼き込みテーブル」注記・`references/style-genome-packaging.md` §4.1）。

```markdown
Use STYLE GENOME:
assets/generated/style-genome.json

Create a 16:9 manga-like isometric explanatory infographic for slide {{slide_no}}.

Pattern:
image-only

Text policy:
baked-with-overlay. Put only the following short quoted Japanese labels into the image, verbatim, 1-4 words each, large and crisp:
{{baked_text_blocks}}

Core message (Why):
{{message}}

Visual structure (What):
{{diagram_structure}}

Scene objects and primitives (How):
{{motifs_and_primitives}}

Composition (Where):
- bright off-white background with faint dotted isometric grid floor
- rounded isometric platform tiles
- bold dark navy Japanese title centered near top
- rounded speech-bubble labels and pale explanation panels
- glowing blue-white flow arrows or flow line when a process is shown
- keep top/bottom 8% and left/right 6% safe margins
- imageFit: contain. The whole generated page must fit inside the HTML slide and print without cropping; keep all important subjects, labels, arrows, mini tables, people, and AI mascot away from the outer edges.

Style suffix:
Clean manga-like isometric explanatory infographic, Kanagawa-inspired desaturated palette, matte flat vector surfaces with subtle depth, uniform navy outlines, rounded geometry, soft single shadow from upper-left, premium orderly consulting deck, 16:9.

Negative:
photorealistic, 3d render, stock photo, cluttered, noisy background, dark background, neon colors, high saturation, paper texture, rough hand-drawn wobble, logos, watermarks, brand marks, UI gibberish, distorted text, garbled characters, tiny unreadable labels, emoji-style pictograms, chaotic shadows, excessive gradients.

Output:
PNG source image for `assets/generated/slide-NN-{slug}.png`, then convert to WebP.
Also create `{slug}.meta.json` with:
pattern=image-only, textPolicy=baked-with-overlay, backgroundSource=none, styleGenome=assets/generated/style-genome.json, source={{confirmed_text_to_image_backend (実体 gpt-image-2)}}, decision=generate-image, reason={{reason}}, alt={{alt}}, overlayText={{overlay_text}}, prompt=assets/generated/slide-NN-{slug}.prompt.md, imageFit=contain.
```

### Pattern B: HTML合成型（画像は背景・モチーフ、文字/表はHTML）

5W1H 対応: Why=Core message / What=Visual role（背景・モチーフの役割）/ Where=Composition の negative space（Layout enum で記述）/ How=Style suffix + Negative。textPolicy=overlay-only なので画像内テキストは焼かず、全テキストは HTML 前面の overlayText が正。

```markdown
Use STYLE GENOME:
assets/generated/style-genome.json

Create a 16:9 manga-like isometric background/motif visual for slide {{slide_no}}.

Pattern:
html-composite

Text policy:
overlay-only. Do not include any readable text, letters, words, numbers, captions, labels, typography, tables, logos, or UI text in the image.

Core message (Why):
{{message}}

Visual role (What):
{{background_or_motif_role}}

Scene objects and primitives (How):
{{motifs_and_primitives}}

Composition (Where):
- leave clear negative space at {{html_overlay_area}} for HTML title, labels, and tables
- keep generated objects behind or beside the future HTML content
- use rounded isometric platform tiles, faint dotted grid floor, and blue-white flow accents
- avoid any element that looks like garbled text
- imageFit: html-composite-contain by default. If the image is decorative-only and cover is required, mark it cover-safe and confirm that no important subject can be cropped.

Style suffix:
Clean manga-like isometric explanatory infographic, Kanagawa-inspired desaturated palette, matte flat vector surfaces with subtle depth, uniform navy outlines, rounded geometry, soft single shadow from upper-left, premium orderly consulting deck, 16:9.

Negative:
readable text, letters, words, numbers, captions, labels, typography, tables with text, UI gibberish, distorted text, garbled characters, logos, watermarks, brand marks, photorealistic, 3d render, stock photo, cluttered, neon colors, high saturation, emoji-style pictograms.

Output:
PNG source image for `assets/generated/slide-NN-{slug}.png`, then convert to WebP.
Also create `{slug}.meta.json` with:
pattern=html-composite, textPolicy=overlay-only, backgroundSource=raster, styleGenome=assets/generated/style-genome.json, source={{confirmed_text_to_image_backend (実体 gpt-image-2)}}, decision=generate-image, reason={{reason}}, alt={{alt}}, overlayText={{html_overlay_text}}, prompt=assets/generated/slide-NN-{slug}.prompt.md.
```

注記: backgroundSource を `svg` にする場合は画像生成せず、SVG2/CSS で背景レイヤを構築する（assets/generated に画像を作らない・meta は pattern=html-composite, textPolicy=overlay-only, backgroundSource=svg）。詳細は references/style-genome-packaging.md §4.2。
