# スタイルゲノム・量産パッケージ

**責務**: `05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` に含まれている生成画像群の構成・画風・図解パーツ・ラベル表現を、スキル内の固定スタイルゲノムとして使えるようにする。画像生成だけで作るスライドと、HTML/CSS/JS/SVGに画像を合成するスライドの両方を同一世界観で量産する。

---

## 1. 適用条件

ユーザーが次のいずれかを明示した場合に使用する。

- 共有済み画像のスタイルゲノムをスキルに反映して再現したい
- 漫画チックな図解、説明文入り図解、図解内の表や説明枠を量産したい
- 画像生成パターンと HTML 合成パターンの両方を作りたい
- 既存 `assets/generated/` や `index.deploy.html` と同じ画風をスキルの標準プリセットとして再利用したい

標準のHTML/SVG生成だけで十分な場合は使用しない。

全面画像生成モード（各ページを1枚ずつ画像生成する運用）では本パッケージは必須である。生成画像は背景ではなく各ページの主キャンバスとして扱い、`style-genome.json` / STYLE BIBLE をすべての per-slide prompt と meta に反映してから生成する。

---

## 2. 同梱プリセット

本スキルには、共有済み画像の特徴を反映した標準プリセットを同梱する。

| プリセット | パス | 用途 |
|---|---|---|
| `kanagawa-comic-diagram` | `assets/style-genome-kanagawa-comic-diagram.json` | `slide-2026-06-13-skill-mass-production/assets/generated/` の画像群に近い、漫画チックな説明図、吹き出しラベル、簡易表、角丸アイソメタイル、青い発光フローラインを再現する |

新規デッキでは、このプリセットをコピーして `assets/generated/style-genome.json` として保存し、必要な差分だけ project-local に上書きする。毎回「スタイルゲノム取得プロンプト」を実行する運用ではない。

全面画像生成モードでは、このコピーを生成前ゲートとする。`assets/generated/style-genome.json` が無い状態で `{slug}.prompt.md` を量産しない。各 prompt は `STYLE BIBLE` または `Use STYLE GENOME: assets/generated/style-genome.json` から始め、各 meta は `styleGenome: "assets/generated/style-genome.json"` を持つ。

### 2.1 再現対象ディレクトリの主要特徴

`slide-2026-06-13-skill-mass-production/assets/generated/` の画像群を再現する時は、以下を固定する。実物は人物・AIロボットマスコット込みの複雑め(リッチ)なジオラマであり、シンプルな角丸タイル＋少数モチーフではない。

| 要素 | 固定する特徴 |
|---|---|
| 画面 | 16:9、白〜オフホワイト背景(#FAFAFA)、薄いアイソメドットグリッド床 |
| 主体 | 角丸アイソメタイル上に、工程・概念をリッチな小ジオラマとして配置。重なり(occlusion)と奥行きを積極利用 |
| 人物 | 半抽象・無表情の簡略人物。全員が紺〜くすんだ青系の服。座位エンジニア／手を広げて話す立ち姿／タブレット操作者／建設作業者の系統。シーン高の1/4〜1/3。フェーズごとに複数点在 |
| キャラ | 白〜淡青のAIロボットマスコット(濃紺フェイスパネル＋シアン楕円目2つ＋アンテナ＋sparkle)。全身／頭部浮遊／上半身クリップボードの変種。AI・判断・自動化の象徴 |
| 線 | 紺系の細いアウトライン、手描き風ではなく均一でクリーン |
| タイトル | 上部中央に太い濃紺の日本語見出し |
| ラベル | 吹き出し型または角丸ラベル。淡色塗り＋濃紺太字 |
| フロー | 青白い発光矢印・発光ライン。複数フェーズを通す蛇行する青い道(serpentine path)も使う |
| 色 | Kanagawa系の淡い blue / aqua / yellow / violet / pink を章/STEPごとの支配色で使い分け。段ボールのamber茶、植物のteal-green、AIロボ/矢印/ゲートのシアン発光(#BFD9FF)が共通アクセント |
| 反復具体物 | 歯車群・モニター群・書類束・チェッククリップボード・観葉植物・円柱DB・配送箱・トラック・ベルトコンベア・ロボットアーム・信号塔・キャビネット・虫眼鏡・電卓・QRカード・地球儀スクリーン・コーヒー・本棚・位置ピン・吹き出し群・選択式UIタブレット等(genome motifs 参照) |
| 章扉 | 巨大な半透明ゴースト章番号(02/03)＋STEP1-4の角丸ピル進行ナビ＋QRカードが章扉の固定パーツ |
| レイアウト | 表紙ミニマル／章扉(ゴースト番号)／左右二層対比(中央ゲート)／4フェーズ直列(下に循環戻り)／蛇行メカニズムの5型(genome compositionRules.layoutTemplates 参照) |
| 説明文 | 画像内に短い説明文を入れる場合は大きく少量。正確性担保のため `overlayText` に必ず同じ文言を残す |
| 密度 | スライド種別で段階化。表紙/章扉=低、フロー/対比=中、メカニズム解説図=高(数十個の小物・人物・吹き出しを重なりで密配置)。禁止は単色角丸ボックス＋テキストだけの平坦図。1スライド1メッセージは保つ |

## 3. スタイルゲノムの正本フィールド

`assets/style-genome-kanagawa-comic-diagram.json` または project-local の `assets/generated/style-genome.json` は以下を固定値として持つ。

現行 `schemaVersion` は **1.3.0**。下表のフィールド名は実 JSON のキーと一致させる（追加のみ・後方互換。既存フィールド/motif は削除しない）。

| フィールド | 内容 |
|---|---|
| `schemaVersion` | ゲノムのスキーマ版（現行 `1.3.0`） |
| `styleName` | 画風名。`kanagawa-comic-diagram`（唯一の表記） |
| `referenceAssets` | 参照した画像、prompt、meta、HTML のパス |
| `artStyle` | 線、面、角丸、影、質感、視点、カメラ角、`figures`（人物・AIロボット） |
| `artStyle.figures.humanVariationTokens` | 人物バリエーション辞書（職業8 × 姿勢5 × 年齢3）。共通の不変条件（半抽象・無表情・顔描き込み禁止・navy〜dusty-blue 基調・1/4〜1/3 タイル高）は全変種で固定し、職業差は小物1点で表現 |
| `artStyle.figures.aiRobotMascotVariants` | AIロボットマスコットの変種（`full-body` / `floating-head` / `upper-body-clipboard` / `none`。per-slide meta `robotMascot` enum と一致） |
| `palette` | 背景、面、アクセント、Before/After、章色の HEX と用途 |
| `compositionRules` | `safeArea`（"top/bottom 8%, left/right 6%"）、主役位置、章扉/構造/比較/表の構図規則、`layoutTemplates`（章別レイアウト5型） |
| `compositionRules.density` | 密度保持ルール。スライド種別で段階化（表紙/章扉=低・フロー/対比=中・メカニズム解説=高）。禁止は「単色角丸ボックス＋テキストだけの平坦図」のみ。`avoid-cluttered` は低密度ページにのみ適用（再生成時の退化＝平坦ボックス図への degradation を防ぐ） |
| `motifs` | 反復モチーフ辞書（deck共通の語彙・39件）。各 `name`・意味・描写。表は `mini-table-panel`、説明枠は `explanation-panel` |
| `patterns` | `image-only` / `html-composite` / `html-primary` の定義・推奨 `textPolicy`・`backgroundSource` |
| `textPolicies` | `baked-with-overlay` / `overlay-only` / `none` の意味 |
| `backgroundSources` | `raster`（AI生成画像）/ `svg`（SVG/CSS背景）/ `none`（背景なし） |
| `noveltyRule` | 業界別の内容適応ルール。`industryObjectTable`（8業種＝IT_software/manufacturing/medical/finance/education/logistics/construction/legal_admin × 概念 × 具体物候補）＋`fallbackOrder`（業種テーブル不在時の動詞検索→象徴実在物→純抽象は非適用）＋`biasGuard`（同一 motif 偏り抑制・1デッキ概ね6回超で warn 相当・`adaptationTrace` 記録）＋`nonApplicableTypes` |
| `tableAndMatrixRules` | 表/マトリックスの描き分け。`modes`（`illustrated-mini-table` / `illustrated-full-table`＝見出し+全行を画像内に verbatim 焼き込み・HTML重ね不使用 / `html-overlay-table` / `diagram-translation` / `html-primary`）＋`selectionAxes`/`selection`＋`visualBalanceTokens`（HTML表を画像版と世界観統一する surface/outline/cornerRadius/shadow/accent/props トークン）＋`boundaryRule`（混在境界＝slideType の意味境界＝コード/精密表/逐語数値はHTML側）。image-only デッキで表を見せるときは `illustrated-full-table`（全部画像で焼く）を既定にし、精密数値/料金/長文/複数行コードのみ HTML 系へ |
| `printReadinessRules` | 全面画像デッキの全ページ印刷前提（`imageCanvas`＝16:9・safeArea 内・`object-fit:contain` 既定/cover は被写体切れ確認時のみ、`textForPrint`、`contrast`、`validation`） |
| `promptSuffix` / `negativePrompt` | 全プロンプト末尾に固定付与する共通サフィックスと共通禁止語 |
| `machineContract` | 機械SSoT（`scripts/validate-ai-image-assets.js`）へのポインタ。pattern/textPolicy/backgroundSource の許容値はこのスクリプトが正本 |
| `perSlideDiffContract` | per-slide 差分の規約。各スライドで使う motif は plan の `motifs` に書き、genome の `motifs[].name` の部分集合として参照する |
| `reproducibility` | seed、style reference、解像度、保存規約、検証コマンド |

### 3.1 既存プリセットを更新する場合

ユーザーが新しい参照画像を明示した場合だけ、プリセットを更新する。更新は画像を見て共通要素を仕様へ反映する作業であり、「スタイルゲノム取得プロンプト」を別途生成・実行する作業ではない。

1. 代表スライドを次の4種類から確認する: 表紙/章扉、構造図、比較/フロー、説明文または表を含む図解。
2. 共通する値だけを STYLE BIBLE / style genome に反映する。スライド固有の文言、ノード数、表項目は per-slide diff に置く。
3. 良質な表紙または最も画風が安定した画像を `styleReference` として固定し、後続画像生成で参照する。

### 3.2 build-image-prompts.js 連携（スタイルゲノム → プロンプト → 画像生成）

`assets/generated/style-genome.json` は、`scripts/build-image-prompts.js` が `assets/generated/image-deck-plan.json`（per-slide 差分の入力契約・`schemas/image-deck-plan.schema.json` 準拠）と合成して、各 `slide-NN-{slug}.prompt.md` / `slide-NN-{slug}.meta.json` を機械生成するための**入力仕様**である。ビルダーは genome の `artStyle` / `palette` / `compositionRules` / `motifs` / `promptSuffix` / `negativePrompt` を STYLE BIBLE preamble へ決定論で展開し、plan の per-slide 差分（`subject` / `diagramStructure` / `camera` / `accent` / `motifs` / `overlayText` 等）を本文へ流し込む。`scripts/generate-images-codex.js` が生成された prompt.md を codex exec で画像化し（`meta.source` は実体名 `codex-image2`）、`scripts/validate-ai-image-assets.js --check-genome-content` が genome 仕様の prompt 反映（promptSuffix 主要語・motif 名・accent HEX）を検証する。プレースホルダ（`{{STYLE_BIBLE}}` 等）の手動展開は不要。

ビルダーの決定論性・検証ゲートで保証する事項:

- **safeArea の px 自動計算**: genome `compositionRules.safeArea`（"top/bottom 8%, left/right 6%" 等の % 表記）から 2560×1440 基準で px を自動計算（上下8%≈115px・左右6%≈154px、値が無ければ既定の 8%/6%）し、各 `prompt.md` へセーフエリア指示文を機械挿入・各 `meta.json` に `safeAreaPx` を記録する。手計算依存を解消する。
- **`builtBy` マーカー**: 生成 meta に `builtBy: "build-image-prompts"` を付与する。`validate-ai-image-assets.js` は `builtBy` マーカー無しの手書き meta を警告し、決定論チェーンの迂回（手書き混入）を検出可能にする。
- **plan.json 必須**: 全面画像デッキで `assets/generated/image-deck-plan.json` が不在の場合、`validate-ai-image-assets.js --full-image-deck` は FAIL とする（plan.json → build-image-prompts.js の導線を形骸化させない）。
- **実HTML cross-check**: `validate-ai-image-assets.js` は `index.html` を読み、主キャンバス class（`.ai-slide-canvas` ＋後方互換エイリアス `.slide-fullbg` / `.slide-bg` / `[data-role="main-canvas"]`）＋`object-fit:contain`＋meta の `imageFit` を cross-check する。
- **`tableMode` 補助推論**: per-slide 任意フィールド `tableHints`（列数・行数・数値精度・更新頻度・目的）から推奨 `tableMode` を補助推論し（正確な表/料金は HTML 前面、概念比較は `diagram-translation` 優先、短い表は `illustrated-mini-table`）、推奨と根拠を prompt/meta に併記する。明示 `tableMode` があればそれを尊重する。

**スタイルゲノムの位置づけ**: スタイルゲノムは画像生成の**仕様（スタイルガイド・お手本）**であり、ピクセル単位の完全コピーを再生産する金型ではない。固定するのはスタイル仕様（画風・配色・モチーフ・構図ルール）だけで、図解の中身（ノード数・配置・ラベル・被写体）はスライドごとに可変である。ビルダーは「同じスタイル仕様を毎回確実にプロンプトへ反映する」ことで一貫性を担保し、1枚1枚の完全一致は目標にしない（seed 完全固定・1px 一致は任意）。

### 3.3 レイアウトグリッド語彙（構図ユビキタス言語）

構図の指定に使う語彙の**正本（SSoT）**。schema（`image-deck-plan.schema.json` の `layout` フィールド）・builder（`build-image-prompts.js`）・validator（`validate-ai-image-assets.js`）・template / agent（per-slide diff・プロンプト記述）が同一の語彙・enum を参照する。ここで定義する語は gpt-image-2 の再現性（不変要素を曖昧語でなく具体名詞＋属性で逐語再記述する原則）を構図側に適用したもので、視線誘導と配置を構造化し、デッキ全体で同一骨格を反復させる。

最新モデルは **gpt-image-2（2026-04）**。デッキ統一は (A) スタイル契約テキスト（promptSuffix・consistencyAnchors・GEOMETRY LOCK）の逐語再利用と、(B) image-to-image で基準ページを参照画像化（`styleReference`）し identity と style を役割ラベルで分離する併用が最強である。本節の語彙は (A) を構図次元で担う。

#### area enum（画面上の位置定義）

`zones` / `readingOrder` / `focalPoint` が共有する配置領域の語。各語が画面のどこを指すかを固定する。

| area | 画面上の位置 |
|---|---|
| `top` | 上部帯（タイトル・見出し帯の領域） |
| `bottom` | 下部帯（キャプション・進行ナビ・出典の領域） |
| `left` | 画面左半分（左右二分の左ブロック） |
| `right` | 画面右半分（左右二分の右ブロック） |
| `center` | 中央（主役ハブ・中心ゲートの領域） |
| `foreground` | 手前（視点に最も近い前景。人物・近景の主役を置く） |
| `background` | 奥（視点から遠い後景。グリッド床・遠景モチーフを置く） |

#### 構図語彙とパイプライン上の使用箇所

| 語彙 | 定義 | 型（schema） → 展開（builder） → 検査（validator） → 記述（template/agent） |
|---|---|---|
| `grid` | 全体の配置骨格。enum=`left-right`(左右二分) / `top-bottom`(上下二層) / `center-radial`(中央ハブ放射) / `grid-2x2`(2x2四象限) / `free`(自由) | schema: `layout.grid` enum 型で定義 → builder: grid 値を構図指示文（"compose as a left-right split / a 2x2 quadrant grid" 等）へ決定論展開 → validator: enum 外値を不正として検出 → template/agent: per-slide diff の `layout.grid` に内容へ合う1値を記述 |
| `zones` | 各領域に置く要素。配列 `{area, content}`。area=area enum、content=その領域に置く要素・役割（自由文） | schema: `layout.zones` 配列（`area` enum＋`content` 必須） → builder: 各 zone を "place {content} in the {area} area" としてプロンプト本文へ展開 → validator: area enum 検査・content 非空検査 → template/agent: 領域ごとの配置を zones で列挙 |
| `readingOrder` | 視線が辿る順に area enum を並べた配列（最低2要素）。記法 `'a > b > c'` | schema: `layout.readingOrder` 配列（minItems 2・area enum） → builder: "guide the eye {a} then {b} then {c}" 等の視線誘導文へ展開 → validator: 2要素以上・area enum 検査 → template/agent: 主役から従要素への視線順を宣言 |
| `focalPoint` | 最初に目が行く主役の area | schema: `layout.focalPoint`（area enum） → builder: "the visual focal point is the {area} area" として強調 → validator: area enum 検査 → template/agent: 主役領域を1つ指定 |
| `emphasis` | 強調方針（主役を大きく／対比要素を左右に等・自由文・任意） | schema: `layout.emphasis`（string・任意） → builder: 強調指示文として末尾付与 → validator: 型のみ検査 → template/agent: 強調の狙いを短文で記述 |
| `intendedUse` | 用途宣言（MODE setter）。既定 `'presentation infographic / explanatory diagram'`。gpt-image-2 は用途明示で仕上げモード・密度・精度が固定される | schema: トップレベル `intendedUse`（string・default あり） → builder: プロンプト冒頭の用途宣言として固定挿入 → validator: 既定値同等の用途語が反映済みか検査 → template/agent: 用途が既定と異なる時のみ上書き記述 |
| GEOMETRY LOCK | `artStyle.camera.geometry` = `'isometric, 30-degree axonometric projection, equal scale on all axes, no perspective foreshortening.'`。投影法を全ページで固定し、ページ間で視点が揺れるのを防ぐ | 型: genome `artStyle.camera.geometry`（固定文字列） → builder: 全プロンプトへ逐語展開（GEOMETRY LOCK 行） → validator: 各 prompt に geometry 文の主要語が含まれるか検査 → template/agent: 触らない（genome 由来の不変アンカー） |
| `consistencyAnchors` | 全ページで反復する制約アンカー（背景色 `#FAFAFA`／輪郭色 `#0B2A55`／角丸アイソメタイルのみを図解容器に／影は上左45度／`#BFD9FF` glow は AIロボ・フロー矢印・ゲート専用／上下8%左右6%の余白／no stray text・no watermark・no logo）。gpt-image-2 のデッキ統一の主要手段＝不変要素を毎ページ逐語再記述する | 型: genome `consistencyAnchors`（配列） → builder: 全プロンプトへ逐語展開（不変要素を毎回再記述） → validator: 主要アンカー語の prompt 反映を検査 → template/agent: 触らない（genome 由来。per-slide で上書きしない） |
| `lockTiers` | 属性ヒエラルキー。tier1=絶対不変(geometry/navy輪郭/60-30-10) tier2=維持(motif/タイル/glow) tier3=可変(grid密度/影/細部)。固定と可変を分離しドリフト防止 | 型: genome `lockTiers`(tier1/tier2/tier3) → builder: tier1/2 を STYLE LOCK 隣接・tier3 を末尾可変ゾーンへ展開 → evaluate: tier1 を一貫性 rubric に使用 → validator: tier1+anchors をリンター除外語源に使用 |
| `ambiguityReplacements` | 曖昧語→具体属性 の置換辞書(high quality/beautiful/きれい 等→genome 語彙) | 型: genome `ambiguityReplacements`(object) → validator: 曖昧語検出時に置換候補を提示(`--strict-intent` で error 昇格) → builder/template: 直接は使わず作り手が曖昧語を避ける指針として参照 |

### 3.4 デッキ全体一貫性（gpt-image-2）

gpt-image-2 でデッキの世界観を全ページ統一する手段は、(A) スタイル契約テキストの逐語再利用と (B) image-to-image 参照を併用するのが最強である。本パッケージは両方をビルダーで担保する。

- **(A) スタイル契約テキストの逐語再利用**: `promptSuffix` / `negativePrompt` / `consistencyAnchors` / GEOMETRY LOCK / `intendedUse` を、要約・言い換えせず**毎ページのプロンプトへそのまま再記述**する。再現性は「不変要素を毎回逐語再記述」「曖昧語でなく具体名詞＋属性（HEX・px・角度・固有モチーフ名）」で決まる。builder が genome から決定論展開するため、ページ間で語が揺れない。
- **(B) image-to-image 参照（基準ページ）**: 最も画風が安定したページ（多くは表紙）を `styleReference` に固定し、後続ページ生成で参照画像として渡す。役割ラベルで identity（被写体の中身＝各ページ可変）と style（画風・配色・構図骨格＝不変）を分離し、style 側だけを基準ページから継承する。被写体の中身（ノード数・ラベル・概念）はコピーしない。
- (A) はテキスト次元、(B) は画素次元で統一を効かせる。両者は補完関係で、(A) のみだと細部のトーンが揺れ、(B) のみだと文字や構図指示が効きにくい。本パッケージは **(A) を必須**とし、**(B) は full-image-deck（2ページ以上のデッキ）では `styleReference.anchorSlug`（通常 `slide-01`）を全ページ共通で付与することを既定**とする（単発差し替えでは任意）。gpt-image-2 は seed 非対応で、参照画像チェーンが唯一の画素レベルのドリフト抑止手段だからである。生成順序は **anchor ページを最初に生成 → 残りページがそれを参照** する順を守る（`generate-images-codex.js` は anchor 画像が未生成のとき WARN を出して参照なしで続行する）。`validate-ai-image-assets.js --full-image-deck` は、meta が2枚以上ありどれも `styleReference.anchorSlug` を持たない場合に WARN を出す（schema 強制必須化はせず、デッキ運用時だけ推奨を可視化する）。

**再現性アンカーの保守注記**: genome の `referenceAssets` が指す特定デッキのパス（`05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` 等）と `generation.modelSnapshot`（既定 `gpt-image-2-2026-04-21`）はハードコード固定値である。参照デッキの移動・改名や、モデルの deprecate・新スナップショット移行が起きた場合は、これらの固定値を更新する必要がある（自動追従しない）。

### 3.5 検証責務の階層（Tier1/Tier2/Tier3）

画像アセットの検証は3層に分担する。各層は別の手段で別の対象を見る。

- **Tier1（機械ゲート）**: 字数・存在・enum などの形式検証。`scripts/validate-ai-image-assets.js` / `build-image-prompts.js` の validateSlide / schema が担う。`negativeSpecific` の20字以上 assert・`tableContent` の各セル14字以内・列行整合・`pattern`×`textPolicy` 整合・必須キー存在もここ。
- **Tier2（LLM-judge / eval）**: 意味の妥当性。`scripts/evaluate-image-consistency.js` のルブリック採点や `--strict-intent` の意味照合が担う。負制約が「実際に間違えやすい構成」を突いているか、支配色宣言が prompt 本文に意味として反映されているかなど、形式では測れない妥当性を見る。
- **Tier3（目視）**: 生成画像の文字化け・被写体切れ・コントラスト・印刷端欠けの最終確認。人間が見る。

分担の例: `negativeSpecific` の「20字以上」は形式ゲート（Tier1）が assert し、その20字が意味のある負制約になっているか（誤ノード数・逆向き・対称崩れを的確に列挙しているか）の妥当性は Tier2/Tier3 が担う。形式を満たしただけで意味の妥当性が保証されるわけではない。

---

## 4. 量産パターン（2主パターン + html-primary）

ユーザーの2パターン（画像生成でスライドを作る / HTMLと画像・SVGを組み合わせる）を `pattern` の3値で表す。`html-primary` は「HTML側で画像を使わない」退避先で Pattern B の特殊形。機械的な許容値は `scripts/validate-ai-image-assets.js` を正本とする。

| `pattern` | 器 | `textPolicy` | `backgroundSource` |
|---|---|---|---|
| `image-only` | スライド全体=1枚の生成画像 | `baked-with-overlay` / `overlay-only` | `none` |
| `html-composite` | HTML/CSS/JS/SVG が器 | `overlay-only` | `raster` / `svg` |
| `html-primary` | HTML/CSS/SVG のみ（画像なし） | `none` | `none` / `svg` |

コード（slide-code / slide-code-compare）は `pattern` 対象外。常に実HTMLコードブロック（`.code-block` / `.code-compare-body`）で描画し画像化しない（機械契約: `image-only` / `baked-with-overlay` 不可）。

### 4.1 Pattern A: 画像生成完結型（`image-only`）

1枚の生成画像の中に、背景、図解、説明枠、表、吹き出しを作り込む。漫画チックな図解の中に説明文が含まれる表現はこちらを使う。

**向くもの**: 章扉・表紙・コンセプト図 / 情景や漫画的な説明図 / 図解内の短いラベル・少量の説明枠・簡易表 / 画像そのものを配布・再利用したいスライド。

**制約**:

- `textPolicy: baked-with-overlay` を明示した場合だけ画像内テキストを許可する。画像内に文字を描かない場合は `overlay-only`。
- 画像内テキストを使う場合でも、正テキストは必ず `overlayText` に保持する。
- 表は短語中心なら画像内に焼き込む。雰囲気重視で3列×4行程度なら `illustrated-mini-table`、見出し+全行を verbatim に焼くなら `illustrated-full-table`（`tableContent` で各セルを運ぶ・各セル14字以内・最大5列×6行・コマンド列は monospace・`generation.quality: high` 推奨・`camera=structural`（near top-down）推奨）。HTML を画像上のピンポイント位置へ重ねるのは難しく位置ズレが起きるため、image-only では使わず**すべて画像で焼く**。数値の厳密性・料金・長文・頻繁に変わる逐語・複数行コードは `html-composite`（html-overlay-table）/ `html-primary` へ回す。
- **14字超の境界事例**: 固有名詞・コマンドが14字を超えるセルが出る表は、そのスライドは `illustrated-full-table` をやめ `html-overlay-table`（HTML 前面の表）を使う。例: `dependency-cruiser`（18字）を含む表は焼き込まず HTML 側へ。`tsc --noEmit`（12字）は14字以内で焼き込み範囲内。短語化できない長い識別子・コマンド列が1つでもあれば HTML 表へ切り替える。
- **bakedText と tableContent セルの責務境界**: 同じ「画像内に焼き込む文字」でも上限が2系統ある。`bakedText`（見出し・大ラベルの最小限・≤18字）と `tableContent` のセル（表本体・≤14字）は別経路であり、表のセルは必ず `tableContent` 側（≤14字）で運ぶ。見出しを `bakedText` に置くからといってセルを18字まで伸ばさない。
- 日本語崩れが1箇所でもあれば、画像内テキストは装飾扱いに落とし、HTML overlay を正として表示する（`overlayText` が正本）。`illustrated-full-table` の正テキストは `overlayText` に表全文（caption / note を含む全セル）を一字一句保持し、崩れ時のみ HTML 表へ fallback する。

### 4.2 Pattern B: HTML合成型（`html-composite`）

HTML/CSS/JS/SVG を器にし、ビジュアル背景だけを合成する。見出し・説明文・表・数値・フロー・ラベルは HTML/CSS/SVG/JS で重ねる（`textPolicy: overlay-only`）。背景の出自を `backgroundSource` で指定する。

- `backgroundSource: raster` … AI生成ラスター画像（PNG/WebP）を背景・モチーフに使う。
- `backgroundSource: svg` … **SVG/CSS で背景を描く（ラスター画像なし）**。HTML+CSS+JavaScript+SVG背景での量産はこれを使う。`assets/generated/` に画像を作らず、SVG2 プリミティブ（`references/svg-diagram-primitives.md`）で背景レイヤを構築する。

**向くもの**: 正確な表・料金・比較マトリクス・数値グラフ / 文言の差し替えが頻繁なスライド / 順序・個数・依存関係・座標精度が重要な図 / `index.deploy.html` と同じ固定UIを保ったまま量産するデッキ。

**制約**:

- `textPolicy` は `overlay-only`。
- `backgroundSource: raster` の画像に文字・数字・ロゴ・読めるUIを描かせない。
- HTMLシャーシ、pagination、header/footer、section-nav は画像に焼かず、前面レイヤとして維持する。

### 4.3 html-primary（画像を使わない退避先）

正確な表・料金・数値・頻繁に変わる文言が主役のスライドは、AI生成画像を使わず HTML/CSS/SVG だけで作る（`textPolicy: none`、`backgroundSource: none` または `svg` のアクセント）。退化耐性のため、迷ったらここへ寄せる（`full-image-deck-method.md` §7.6）。

---

## 5. per-slide diff 規約

STYLE BIBLE を毎回直書きせず、スライドごとのプロンプトには差分だけを書く。

```json
{
  "slide": 6,
  "slug": "slide-06-cycle-workflow",
  "pattern": "image-only",
  "textPolicy": "baked-with-overlay",
  "backgroundSource": "none",
  "camera": "structural",
  "accent": "multi",
  "purpose": "5工程で進む量産作業の循環構造を一望させ、抜け漏れが起きやすい箇所を確認できるようにする",
  "audienceTakeaway": "ヒアリングから改善までが直線ではなく、改善で次のヒアリングへ戻る循環だと理解できる",
  "background": "デッキ中盤で、個別タスク説明に入る前に全体プロセスの地図を示すスライド。聴衆は各工程名をまだ詳しく知らない前提。",
  "intendedUse": "presentation infographic / explanatory diagram for a workflow overview slide",
  "subject": "A near top-down isometric diorama on a faint dotted-grid floor showing five rounded platform tiles arranged evenly around a circle, connected clockwise by a single glowing ring of arc-arrows.",
  "diagramStructure": "Five node tiles sit at even 72-degree intervals; a luminous flow-line travels the ring clockwise and shifts color step by step; a small glowing core at the center links to all five tiles with hair-thin lines.",
  "layout": {
    "grid": "center-radial",
    "zones": [
      { "area": "center", "content": "small glowing core linking all five process tiles" },
      { "area": "foreground", "content": "five evenly spaced rounded platform tiles on a circular path" },
      { "area": "background", "content": "faint dotted isometric grid floor with no extra decoration" }
    ],
    "readingOrder": ["center", "foreground", "background"],
    "focalPoint": "center",
    "emphasis": "clockwise circular flow and exactly five process nodes"
  },
  "generation": { "modelSnapshot": "gpt-image-2-2026-04-21", "quality": "high", "size": "2560x1440" },
  "styleReference": { "anchorSlug": "slide-01-title-cover", "inheritMode": "style-only" },
  "motifs": ["rounded-isometric-platform", "glowing-flow-arrow", "speech-label"],
  "bakedText": ["5ステップの循環", "ヒアリング", "構築", "改善"],
  "overlayText": ["5ステップの循環ワークフロー", "ヒアリング", "構築", "改善"],
  "reason": "5工程の循環を漫画チックな図解で一枚に収めるため",
  "alt": "5つの工程ノードが循環する俯瞰図"
}
```

- `pattern` は `image-only` / `html-composite` / `html-primary` のいずれか。
- `motifs` は genome `motifs[].name` の部分集合のみ（実在しない名前を使わない）。
- `html-composite` のときは `backgroundSource`（`raster` / `svg`）を付ける。
- 表を画像内に焼くときは `tableMode: illustrated-full-table` + `tableContent`（`headers` / `rows[][]` / `monospaceColumns?` / `caption?`）を付け、`textPolicy: baked-with-overlay` にして `overlayText` に表全文（全セル）を保持する（各セル14字以内・最大5列×6行）。HTML のピンポイント重ねは使わない。
- `styleGenome` には実際に使ったゲノムのパスを書く（§2 でコピーした project-local の `assets/generated/style-genome.json` を推奨）。
- plan の必須キーは `schemas/image-deck-plan.schema.json` を正本とする。生成物 meta の必須キー（`slide` / `asset` / `source` / `decision` / `reason` / `alt` / `pattern` / `textPolicy` / `backgroundSource` / `styleGenome` / `prompt` / `purpose` / `audienceTakeaway` / `background` / `layout` / `generation`）は `scripts/validate-ai-image-assets.js --strict-style-genome --strict-intent` を正本とする。

---

## 6. 検証4条件

| 条件 | PASS基準 |
|---|---|
| 矛盾なし | `pattern` と `textPolicy` が整合（image-only→baked-with-overlay/overlay-only、html-composite→overlay-only、html-primary→none）。`overlay-only`/`none` なのに baked text 指示がない |
| 漏れなし | meta 必須キー（`slide`/`asset`/`source`/`decision`/`reason`/`alt`）が揃い、prompt/styleGenome/overlayText が揃っている（`backgroundSource: svg` の html-composite と html-primary は PNG/WebP を持たない）。全面画像デッキは `assets/generated/image-deck-plan.json` が存在する（不在は FAIL）。ビルダー生成 meta は `builtBy: "build-image-prompts"` を持つ（無い手書き meta は警告） |
| 整合性あり | `structure.md`、meta、HTML参照パス、prompt の slug と slide 番号が一致する。plan/meta の `motifs` が genome `motifs[].name` の部分集合である。`index.html` の主キャンバス class（`.ai-slide-canvas`＋エイリアス）＋`object-fit:contain`＋meta `imageFit` が cross-check 一致する |
| 依存関係整合 | image-only は画像生成→WebP化、html-composite(`raster`) は画像生成→HTML合成、html-composite(`svg`)/html-primary は SVG/HTML構築のみ。どれも最後にUI検証へ進む |
| コード非画像化 | コード系 slideType（slide-code / slide-code-compare）は `aiVisual` で `image-only` / `baked-with-overlay` を持たない（V-043 で機械検証） |

検証コマンド:

```bash
node scripts/validate-ai-image-assets.js <slide-dir> --strict-style-genome
# 全面画像生成モードではこちらを使う
node scripts/validate-ai-image-assets.js <slide-dir> --full-image-deck --strict-style-genome
node scripts/verify-slides.js <slide-dir>/index.html --check-ratio
node scripts/sync-checker.js <slide-dir>/index.html <slide-dir>/structure.md
```

---

## 変更履歴

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-06-23 | 初版。既存画像からのスタイルゲノム抽出、画像生成完結型とHTML合成型の2パターン、textPolicy、検証4条件を定義 |
| 1.1.0 | 2026-06-24 | 矛盾・重複の解消（elegant-review）。`textPolicy` から `html-primary` を廃し `none` を追加（pattern との過負荷解消）。`backgroundSource`(raster/svg/none) を追加し SVG背景型を明示対応。§3 フィールド表を実 genome 構造（patterns/textPolicies/backgroundSources/machineContract/perSlideDiffContract）に同期。per-slide `diagramPrimitives` を `motifs[].name` 参照と定義し例を実在 motif 名へ修正。§5 meta 例に `decision`/`source`/`reason`/`alt` を追加（validator 整合）。`styleName` を `kanagawa-comic-diagram` に統一。値域の正本を validator に一本化 |
| 1.2.0 | 2026-06-24 | 全面画像生成モードのゲートを追加。生成画像を背景扱いにしないこと、`assets/generated/style-genome.json` を生成前に固定すること、全 prompt/meta に STYLE GENOME / STYLE BIBLE を反映し `--full-image-deck --strict-style-genome` で検証することを明記 |
| 1.3.0 | 2026-06-24 | ビルダー連携（SKILL.md v8.2.0）。§3.2「build-image-prompts.js 連携」を追加。`image-deck-plan.json`（per-slide 差分の入力契約・`schemas/image-deck-plan.schema.json`）+ `style-genome.json` → `prompt.md`/`meta.json` を機械生成し、`generate-images-codex.js`（codex exec・`meta.source=codex-image2`）で画像化、`--check-genome-content` で仕様反映を検証する流れを明記。スタイルゲノムの位置づけ＝「画像生成の仕様（お手本・スタイルガイド）であり完全コピーの金型ではない。固定するのはスタイル仕様、図解の中身はスライドごとに可変」を明記 |
| 1.4.0 | 2026-06-24 | 再現性向上（elegant-review・思考リセット＋30種思考法）。参照元画像の実物観察に基づき kanagawa-comic-diagram ゲノムに 人物（青服・半抽象・職業別 human-figure 系）／AIロボットマスコット（ai-robot-mascot）／リッチジオラマ密度／反復具体物30種／章別レイアウト5型／章別支配色 を追加（motifs 8→39、schemaVersion 1.0.0→1.1.0、artStyle.figures と compositionRules.layoutTemplates を新設）。§2.1 を複雑め・人物/キャラ込みへ刷新。density を avoid-cluttered からスライド種別段階化へ修正（平坦な単色ボックス図のみ禁止）。promptSuffix に人物/ロボ/具体物語、negativePrompt に distorted faces 等を追加 |
| 1.5.0 | 2026-06-24 | ゲノム拡充 v1.3.0 と検証強化への同期（elegant-review・D5/D6/D7/D8/D9）。§3 フィールド表を実 JSON（schemaVersion 1.3.0）に同期: `artStyle.figures.humanVariationTokens`（職業8×姿勢5×年齢3）/`aiRobotMascotVariants`、`compositionRules.density`（密度保持・degradation 禁止）、`noveltyRule`（8業種 `industryObjectTable`＋`fallbackOrder`＋`biasGuard`＋`nonApplicableTypes`）、`tableAndMatrixRules`（modes＋`visualBalanceTokens`＋`boundaryRule`）、`printReadinessRules` を追記。§3.2 に safeArea px 自動計算（115/154px）・`builtBy` マーカー・plan.json 必須・実HTML cross-check・`tableHints`→`tableMode` 補助推論を追記。§6 検証4条件にビルダー由来の保証事項（plan.json 不在 FAIL・builtBy 警告・index.html cross-check）を反映 |
| 1.6.0 | 2026-06-25 | 構図ユビキタス言語（レイアウト語彙）の正本を定義。§3.3「レイアウトグリッド語彙」を新設し、area enum（top/bottom/left/right/center/foreground/background の画面位置）と `grid`(left-right/top-bottom/center-radial/grid-2x2/free)/`zones`(area+content)/`readingOrder`(area enum 最低2要素・`a > b > c` 記法)/`focalPoint`/`emphasis`/`intendedUse`(MODE setter・既定 presentation infographic / explanatory diagram)/GEOMETRY LOCK(`artStyle.camera.geometry` 軸測投影固定)/`consistencyAnchors`(全ページ反復制約) を schema enum と一致定義し、各語の 型(schema)→展開(builder)→検査(validator)→記述(template/agent) の使用箇所を明記。§3.4「デッキ全体一貫性（gpt-image-2）」を新設し、(A) スタイル契約テキスト逐語再利用と (B) image-to-image 基準ページ参照（identity/style 分離）の併用を A 必須・B 推奨として追記。gpt-image-2（2026-04）を最新モデルとして反映 |
| 1.7.0 | 2026-06-25 | 焼き込み表（D12）の境界条件・検証責務階層・保守注記の明記（elegant-review 再検証）。§4.1 に (1) 14字超の境界事例（`dependency-cruiser`=18字 は `illustrated-full-table` をやめ `html-overlay-table` へ／`tsc --noEmit`=12字 は範囲内）、(2) `bakedText`(見出し最小限≤18字) と `tableContent` セル(表本体≤14字) の責務境界、(3) `illustrated-full-table` の `camera=structural`(near top-down) 推奨、(4) `overlayText` に表全文(caption/note 含む全セル)を一字一句保持を追記。§3.4 に再現性アンカーの保守注記（`referenceAssets` の特定デッキパス・`modelSnapshot=gpt-image-2-2026-04-21` はハードコード固定のためデッキ移動/改名・モデル deprecate 時は更新が必要）を追記。§3.5「検証責務の階層」を新設し Tier1=機械ゲート（字数・存在・enum・`negativeSpecific` 20字 assert）/ Tier2=LLM-judge・eval（意味妥当性）/ Tier3=目視 の分担を明記 |
