# 全面AI画像化（世界観統一）メソッド

**責務**: スライドデッキ全枚を生成AI画像で構成する特殊運用において、世界観を1つに統一したまま再現性高く量産するための手法書。STYLE BIBLE 雛形・生成プロンプトキット規約・再現性運用・ハイブリッド例外・日本語テキスト対策・検証フローを規約として定義する。既存画像から画風を抽出して再利用する場合は `style-genome-packaging.md` を正本として併用する。

---

## 0. 適用条件（冒頭固定の運用宣言）

このメソッドは、ユーザーが「スライド全体を生成画像で構成する」を**明示した場合のみ**適用する特殊運用である。skill 既定（インライン SVG2 優先 / `ai-image-diagram-workflow.md` §1）を**意図的に上書き**する。デッキ冒頭（structure.md 先頭）に、次の趣旨の運用宣言を固定で置く。

- 本デッキはユーザー明示指示により全 N 枚を AI 画像で構成する特殊運用であること。
- skill 既定（SVG 優先・`ai-image-diagram-workflow.md` §1）を意図的に上書きすること。
- 意図的なハイブリッド例外（QR・ロゴ等の実画像）があればその箇所を明記すること。

着手前に `ai-image-diagram-workflow.md` §1.2「着手前バックエンド確認（必須）」を実行し、使える画像生成バックエンドを確定してから量産に入る。

### 0.0 ページ単位画像生成の解釈（背景化禁止）

ユーザーが「各ページを1枚1枚画像生成する」「スライド全体を生成画像で作る」「Codex Image 2 / image2 でページ画像を作る」と指定した場合、生成画像は**背景素材ではなく、そのページの主キャンバス**として扱う。HTML/CSS は、正テキスト fallback、コードブロック、QR/ロゴ等の正確性必須レイヤ、ページ送り UI のために使う。

> 注: 「Codex Image 2 / image2 / Image 3」はユーザートリガー語として残すが、実体は最新の **gpt-image-2**（2026-04 リリース。Codex CLI の `$imagegen` / `codex exec` が内部で使用）である。トリガー語が何であれ生成エンジンは gpt-image-2 と解釈し、§1.11 の生成設定（size/アスペクト/透過/quality）に従う。

禁止:

- 生成画像を淡い背景や装飾モチーフにだけ使い、前面を通常HTML図解で作ること
- STYLE BIBLE なしで per-slide prompt だけを量産すること
- `05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` の画風再現指示があるのに、同梱 style genome を prompt/meta/structure に流し込まないこと

許可:

- 正確なコード・数値・QR・ロゴは HTML/実画像レイヤで前面化する
- 日本語テキスト崩れ対策として `overlayText` を正本にし、必要時にHTML overlayへ切り替える
- 表を見せるページは、精密な数値・料金・頻繁更新・長文・複数行コードのみ `html-composite`（`html-overlay-table`）/ `html-primary` とし意味テキストをHTML正本にする。それ以外の対照表・5層表などは `image-only` + `tableMode: illustrated-full-table` で見出し＋全セルを画像内に焼き込み、`overlayText` に表全文を正本保持する（HTMLのピンポイント重ねは位置ズレするため使わない。§0.1・`style-genome-packaging.md` §4.1）

### 0.1 量産モードの分岐

全面AI画像化を選んだ場合でも、スライド単位では次の2パターンを明示してから生成する。

| パターン | `pattern` | 主用途 | `textPolicy` |
|---|---|---|---|
| 画像生成完結型 | `image-only` | 漫画チックな説明図、章扉、表紙、簡易表・吹き出し入り図解 | `baked-with-overlay`（`overlayText` が正本）。画像に文字を描かない場合は `overlay-only` |
| 焼き込み表（image-only の表処理既定） | `image-only` + `tableMode: illustrated-full-table` | 対照表・5層表など、見出し＋全セルを画像内に焼き込んで見せる表（HTML重ね不使用） | `baked-with-overlay` 固定（`overlayText` に表全文を正本保持） |
| HTML合成型 | `html-composite` | 精密な数値・料金・頻繁更新・長文・複数行コードの表 | `overlay-only`。画像に文字を焼かない |

image-only デッキで表を見せる場合は `illustrated-full-table`（見出し＋全セルを画像内に verbatim 焼き込む方式）を既定とする。HTML を画像上のピンポイント位置へ重ねる `html-overlay-table` は位置ズレが起きるため image-only では使わず、精密な数値・料金・頻繁更新・長文・複数行コードのみ `html-composite`（`html-overlay-table`）/ `html-primary` へ回す。焼き込み表の構造（`tableContent` / 各セル14字以内・最大5列×6行 / `monospaceColumns` / `camera=structural` 推奨）は `style-genome-packaging.md` §4.1・`ai-image-diagram-workflow.md` §4.1 を正本とする。

パターン/値域（`pattern` / `textPolicy` / `backgroundSource` / `tableMode` の許容値）の定義は `references/style-genome-packaging.md` §4 を正本とする（本表は再定義せず参照に寄せる。DRY）。機械的な許容値は `scripts/validate-ai-image-assets.js` を正本とする。

`pattern` と `textPolicy` は `{slug}.meta.json`、`structure.md`、prompt の3箇所に同じ値で記録する。混在は許可するが、1スライド内で画像内テキストとHTML正本の責務が曖昧になってはいけない。

### 0.2 「全面AI画像化」の定義明確化

「全面AI画像化」とは、デッキの世界観（背景トーン・章扉・配色・モチーフ）を全スライドで画像により統一する運用を指し、全スライドのあらゆる前面要素をラスター化することではない。正本テキストは常にHTMLオーバーレイが正本であり、コードページ（slide-code / slide-code-compare）はこのHTML正本層が前面化した極限ケースである。背景・トーンで世界観を共有しつつ前面は実コードで実装するため、世界観統一は崩れない。

### 0.3 HTML表示サイズと生成画像サイズの契約（印刷ビューポート契約の正本）

> **印刷ビューポート契約の正本はこの節**。全面画像デッキの「16:9 letterbox（297mm→167mm）+ contain + 主キャンバスクラス規定」をここで一本化し、`references/print-layout.md`・`references/image-format-guide.md`・`SKILL.md` は本節を参照する（DRY）。実装の正本は `assets/print-styles.css`（印刷 CSS）と `assets/slide-template-single.html`（画面 CSS・主キャンバス実体マークアップ）。

全面画像生成モードでは、生成画像は 2560×1440 / 16:9 を基準にし、HTML では主キャンバスとして規定クラス **`.ai-slide-canvas`** に配置する。既定の表示契約は `imageFit: contain` であり、CSS background や `object-fit: cover` で主画像を切ってはいけない。

#### 主キャンバスクラス規定（`.ai-slide-canvas` 実体 + エイリアス）

- 規定クラスは **`.ai-slide-canvas`** を正本（実体）とする。後方互換で慣用クラス `.slide-fullbg` / `.slide-bg`、意味属性 `[data-role="main-canvas"]` を**同一の `object-fit: contain` 契約のエイリアス**として受容する。
- CSS は `:where(.ai-slide-canvas, .slide-fullbg, .slide-bg, [data-role="main-canvas"])` で詳細度ゼロに束ね、クラス名密結合を避ける（実装: `assets/slide-template-single.html` 画面 CSS / `assets/print-styles.css` 印刷 CSS）。

#### 表示・印刷フィット契約

- `image-only` は `<picture class="ai-slide-canvas">` に置き、`img { width:100%; height:100%; object-fit:contain; }` とする。意味テキスト・コード・QR・ページ UI は `.visual-overlay`（前面 `z-index:1`）に置き、画像へ焼き込まない。
- `html-composite` でも、生成画像が意味を持つ主ビジュアルなら `.ai-slide-canvas`（またはエイリアス）の `contain` を使う。装飾だけの背景に限り `.slide-bg--cover-safe`（`imageFit: cover-safe`）を許可する。
- `imageFit: cover-safe` は、主要被写体・人物・AIロボット・吹き出し・表・フロー矢印が safe area 内にあり、目視で端欠けがない場合だけ使う。
- 画面・印刷とも `object-fit: contain`（矛盾なし）。印刷は `@media print` で `object-fit: contain !important` を強制し、`cover` による端切れを禁止する（焼込テキスト入り `baked-with-overlay` 画像が印刷で欠けないことを優先）。`cover` の `@media print` 混入は `scripts/validate-print.js` が CRITICAL 検出する。

#### 印刷 A4横 16:9 letterbox（端欠けなし担保）

- 全面画像デッキは `<div class="slider" data-deck-mode="full-image">`（または `body[data-deck-mode="full-image"]`）を立て、印刷を A4横 16:9 letterbox へ切り替える。
- A4横 297mm × 210mm を基準に 16:9 を幅 297mm へ合わせると高さ **167mm**（167.06mm）。上下に `(210 − 167) / 2 ≈ 21mm` の off-white（#FAFAFA）余白（letterbox）が出て、`contain` の中央配置で全ページ端欠けゼロになる。
- `data-deck-mode="full-image"` を持つデッキのみに限定適用し、通常 HTML デッキ（属性なし）の full-bleed 印刷ルール（`.slider__item` 210mm 系・281mm/170mm）は温存する（後方互換）。
- `scripts/validate-print.js` は P06 を 16:9 letterbox（167mm）許容に拡張し、全ページ印刷対象・`data-hidden` 除外漏れも検査する。

#### safeArea の px 自動計算

- 生成画像プロンプトには「HTML slide with object-fit: contain」「top/bottom 8%, left/right 6% safe margins」「no important subjects at outer edges」を入れる。
- safeArea の % 表記（genome `compositionRules.safeArea` = "top/bottom 8%, left/right 6%"）は、`scripts/build-image-prompts.js` が 2560×1440 基準で **px へ自動計算**（上下 8% ≈ 115px・左右 6% ≈ 154px）し、各 `prompt.md` へセーフエリア指示文を機械挿入、各 `meta.json` に `safeAreaPx` を記録する。手計算で px を直書きしない（D7）。

### 上書きしても保持する不変制約

全面画像化でも次の制約は必ず保持する。

| 不変制約 | 内容 |
|---------|------|
| 1スライド1メッセージ | 1枚に複数主張を詰めない |
| 順序 | デッキの論理順序（背景→問い→手段→結論）を崩さない |
| 16:9 | 全画像 16:9（2560×1440 基準）厳守 |
| 画像フィット | 主キャンバス画像は HTML で `object-fit:contain`。`cover` による端切れ禁止 |
| 絵文字ゼロ | 画像内モチーフも含め絵文字・絵文字風ピクトグラム禁止。意味は FontAwesome 準拠の図形で表現 |
| 配色規律 | パレットを 1 系統に確定し 60-30-10 を守る。ネオン・高彩度・全面グラデ禁止 |

---

## 1. STYLE BIBLE 雛形（全プロンプトが先頭参照する正本）

デッキの「第1部」として STYLE BIBLE を 1 つ置き、全スライドのプロンプトはこれを `{{STYLE_BIBLE}}` として**先頭で参照**する。各スライドのプロンプト本文には差分（被写体・色・配置・画像内テキスト）だけを書き、STYLE BIBLE の値を直書きしない（DRY）。STYLE BIBLE は次の 10 節で構成する。

全面画像生成モードでは、STYLE BIBLE を書く前に必ず同梱プリセット `assets/style-genome-kanagawa-comic-diagram.json` を project-local `assets/generated/style-genome.json` にコピーし、必要な差分だけ `assets/generated/style-genome.json` と structure.md に保存する。この作業は任意ではなく、全面画像生成モードの最初の成果物である。ユーザーが `slide-2026-06-13-skill-mass-production/assets/generated/` の画風を明示した場合は、その参照デッキの project-local genome / prompt / meta を優先して差分を整理する。

実行順:

1. `assets/generated/` を作成する。
2. 同梱プリセット `assets/style-genome-kanagawa-comic-diagram.json` を `assets/generated/style-genome.json` にコピーする。
3. 参照元 `05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` に project-local の `style-genome.json` があり、ユーザーがその画風を指定している場合は、その内容を優先しつつ差分を整理する。
4. `structure.md` 先頭に STYLE BIBLE 10節を置く。
5. per-slide 差分を `assets/generated/image-deck-plan.json`（per-slide 差分の入力契約・`schemas/image-deck-plan.schema.json` 準拠）にまとめる。1デッキ = 1 plan.json で、全スライドを `slides[]` 配列に持つ。
6. `node scripts/build-image-prompts.js <slide-dir>` で plan.json と `assets/generated/style-genome.json` を合成し、各 `slide-NN-{slug}.prompt.md` / `slide-NN-{slug}.meta.json` を機械生成する。STYLE BIBLE preamble は手動展開せず、ビルダーが決定論で展開する（各 prompt 先頭に `Use STYLE GENOME: assets/generated/style-genome.json` または展開済み STYLE BIBLE が入り、各 meta に `styleGenome: "assets/generated/style-genome.json"` が必ず入る）。`--check` で既存との差分のみ確認、`--only slide-06,...` で部分再生成できる。ビルダーを使わない単発手動時のみ、各 `{slug}.prompt.md` 先頭に STYLE BIBLE preamble を手で置く。

### 1.1 アートスタイル定義
基本様式・視点（例: アイソメトリック俯瞰 30度に固定）・線・角丸・影・質感・光源・全体トーンを固定値の表で定義する。全枚で同一に保つ。

#### 1.1.1 イラスト粒度の統一（重要・再発防止）
全スライドを**同一の「リッチなアイソメトリック・イラスト」粒度**で生成する。これはデッキ全体の SSOT であり、内容差し替え・再生成のたびに崩しやすいので明示固定する。

- **必須**: 各概念は、描き込んだ立体オブジェクト・アイコン・人物・デバイス・道具を、奥行きと影を伴ってプラットフォームタイルやシーンとして描く（例: 人物が端末に向かう情景、歯車工房、書類束、配送箱、上昇グラフ）。
- **禁止**: 単色の角丸長方形にテキストを載せただけの平坦な情報図（「SVG/図形をはめ込んだだけ」の見た目）。タイルやカードは"中身が空のラベル枠"にせず、必ずイラスト化したアイコン/オブジェクトを内包する。
- テキスト（見出し・ラベル・補足）は、リッチなシーンの**中のラベルや吹き出し**として添える。テキストを主役の四角ブロックにしない。
- **再生成時の鉄則**: 内容（文言）だけを差し替える時も、イラストの描き込み密度を必ず維持する。テキスト指定を強めるとモデルは平坦なボックス図に退化しやすいため、プロンプトに「リッチなアイソメ・イラスト粒度を維持／平坦なテキストボックス図は禁止」を必ず明記し、可能なら**既存の良質スライドを画風リファレンス（参照画像）として渡す**。
- 粒度の基準は、デッキ内で最も描き込まれた数枚（人物・情景・道具入り）に合わせ、最も簡素な数枚をそこへ引き上げる（粗密の混在禁止）。
- **退化の具体的機序（codex 等コーディングエージェント経由時・必須／パイロット実証）**: codex のようなコーディングエージェント経由で生成する場合、生成器に **imagegen（text-to-image 拡散モデル）の使用を明示強制**する。指示が弱い（「PNG を作って」程度）と、codex は拡散モデルを使わず **コード（PIL / matplotlib / SVG 等）でプログラム描画**してしまい、単色角丸ボックス＋テキストの平坦な情報図（本節が禁止する退化パターンそのもの）になる。プロンプトに「imagegen を使う・PIL/matplotlib/SVG 等のコード描画は禁止・リッチなアイソメ・イラスト粒度を維持」を必ず含めて初めて参考画風が再現できる。`scripts/generate-images-codex.js` はこの強制文言を実装済みである。

#### 1.1.2 全面画像の上のテキスト配置と可読性（中央配置＋半透明パネル・必須）

全面画像（背景フル）の上に HTML テキストを乗せる場合、次を既定とする。実運用で「文字が上に寄って見にくい」「背景画像と干渉して読めない」という不具合が出やすいため明文化する。

- **縦配置は中央寄せ（`justify-content: center`）を既定**にする。コンテンツ（見出し＋本文＋note）をまとめて画面の縦中央に置き、上下に背景イラストを覗かせる。**上揃え（`flex-start`）にしてコンテンツを上半分に固めない**（下半分が画像だけになり間延びして見える）。見出しだけを上端固定する手法は、背景が白/淡で上部が空く版（画像なし版）では見出しが宙に浮くので避ける。
- **カード地を持たないバラ文字には半透明パネルを敷く**（透過 div 相当）。対象＝見出し（slide-heading）・大ステートメント（statement-big）・注記（note）・タイトル（h1/lead）・クロージング（close-msg）。chip や各種カードは元々地があるので対象外。
  - 明るい背景＝`background: rgba(255,255,255,0.56〜0.70)` ＋ `backdrop-filter: blur(3〜4px)` ＋ `padding` ＋ `border-radius`。背景イラストが薄っすら透けつつ文字が干渉しない透過率に調整する（濃いほど可読・薄いほど画像が映える。見出し0.70 / ステートメント0.66 / 注記0.64 目安）。
  - 暗背景（closing 等）＝`background: rgba(20,28,66,0.30〜0.40)` の暗パネル＋白文字。
  - 見出しパネルは `width: fit-content` で内容幅にフィットさせ、`align-self` は指定せず親の `align-items`（通常スライド＝左、中央寄せメッセージ系＝中央）に追従させる。
- **数値精度が要る表・料金は半透明白パネル＋影付きカードで前面化**（`rgba(255,255,255,0.78〜0.85)`）。背景画像は淡め（スクリム 0.4 前後）にして数字を最優先で読ませる。
- 画像版のみの措置であり、画像なし版（html-primary）はパネル不要（白地で可読）。ただし**縦中央配置は両版で揃える**と比較時に一貫する。
- 印刷時は `@media print` で `backdrop-filter` とパネル影をリセットしてよい（GSAP インラインと同様）。

### 1.2 配色パレット（プロンプト用に1系統へ確定）
画像生成プロンプトに渡す支配色を **1 系統に確定**する（HEX を表で固定）。役割（背景基調・面/カード・アクセント各色・課題/Before 色）ごとに名称・HEX・プロンプト記述語を定義する。HTML オーバーレイ側の CSS 変数は別途推奨値を持ってよいが、画像生成プロンプトの HEX はこの表に統一する。

### 1.3 色貫通マップ
章扉だけでなく本文スライドにも色を貫通させる。スライド群ごとに支配色・差し色を表で割り当て、章（STEP）色がコンテンツまで一貫することを保証する。

### 1.4 反復モチーフ集（意味アンカー具体物）
全スライドで使い回す統一オブジェクトを、**同一名称・同一描写**で定義する。各画像に**意味アンカー具体物を最低1点**含めることを必須とする（例: フローライン / ドットグリッド床 / ノードタイル / アシスタント像 等）。モチーフごとに「統一見た目（プロンプト記述）」と「意味・用途」を表で固定する。

### 1.5 構図・カメラ規定
アスペクト比・テキストセーフエリア・構図タイプ別（章扉 / メッセージ系 / 構造系）の規定を置く。
- **カメラ角の例外規定（重要）**: 方向・順序・個数が意味を持つ構造系スライド（タイムライン / 循環 / 軸図 / Before-After / 多層図 / シェブロン等）は、真上に近い**微俯瞰（top-down, 15度以内）**へ逃がす。これにより順序や個数が正確に読め、かつ「同じジオラマを違うカメラ高度で見ている」と説明でき世界観は壊れない。章扉・メッセージ系は基準アイソメ角（例 30度）。

### 1.6 画像内テキスト方針 + HTMLオーバーレイ fallback（必須）
画像内に見出し・ラベルを描く方針を採る場合でも、各スライドに**正テキストを HTML オーバーレイ fallback として必ず併記**する（`overlayText` 配列）。崩れ判定時はオーバーレイを表示し、画像内文字を装飾扱いに切り替える（詳細は §5）。数値禁止スライドがある場合はその貫通方針もここに明記する。

### 1.7 共通スタイルサフィックス + 共通ネガティブプロンプト
全プロンプト末尾に固定付与する英語の**共通スタイルサフィックス**（アートスタイル・視点・配色・トーンを 1 文に凝縮）と、**共通ネガティブプロンプト**を定義する。ネガティブには最低限 `photorealistic, 3d render, photo, cluttered, neon colors, high saturation, paper texture, hand-drawn wobble, logos, watermarks, brand marks, UI gibberish, distorted text, garbled characters, emoji-style pictograms` を含める。画像内に文字を描く方針なら `readable text` はネガティブに入れず、`distorted text / garbled characters` で崩れだけを抑える。

### 1.8 再現性の三点セット + 保存規約
- **参照画像チェーン(seed非対応)**: gpt-image-2 は seed パラメータを持たないため seed では固定できない。基準ページ(slide-01)を `styleReference.anchorSlug` に指定し、generate-images-codex.js が確定済み画像を codex exec の指示文へ添付する image-to-image でページ間ドリフトを抑える。再現条件は `{slug}.meta.json` の `generation`(model/quality/size) に記録。
- **表紙を style reference に量産**: 表紙を最初に最高品質で確定し、これをデッキ全体の style reference（参照画像）として残りを量産する。
- **命名規則**: `assets/generated/slide-NN-{slug}.png` → WebP 化で `.webp`。`{slug}.prompt.md` / `{slug}.meta.json` を残す。

### 1.9 生成共通仕様
推奨ツール・解像度（2560×1440）・16:9・出力形式（PNG 元画像保持 → WebP 変換・品質 90）・印刷代替（PNG 300dpi 保持、意味テキストは HTML オーバーレイで常に鮮明）を定義する。

### 1.10 章扉共通テンプレート
章（STEP）扉を同一フォーマットに揃える。差分は番号・色・意味アンカー具体物のみ。構図・大番号 + 見出し + サブ・ステッパー強調・意味アンカー割り当てを共通化する。

### 1.11 デッキ全体の構図・画風一貫性（gpt-image-2 ドリフト対策）

gpt-image-2 はページごとに独立生成すると、同じ STYLE BIBLE を渡しても構図の重心・密度・読み方向がページ間でぶれやすい。デッキ全体を「同一ジオラマを巡る連作」として揃えるため、次をデッキ単位の固定値として全ページに同一展開する。

#### 1.11.1 デッキ全体で揃える4軸

- **readingOrder（読み方向）**: デッキ全体で1方向に統一する（例: 全ページ left to right。循環図のみ §1.5 の微俯瞰例外で時計回り）。ページごとに視線誘導の向きを変えない。
- **focalPoint（注視点の高さ）**: 主被写体の重心を画面内の同じ高さ帯に置く（例: 縦 50〜58% 帯）。章扉だけ重心を上げる等の差をつけず、§1.1.2 の縦中央配置とも整合させる。
- **densityLevel（描き込み密度）**: §1.1.1 の粒度基準に従い、最も描き込まれた数枚に密度を合わせ、簡素な枚はそこへ引き上げる。デッキ内で密度を1段階に固定し、粗密混在を禁止する。
- **GEOMETRY LOCK（投影・カメラ）**: style-genome の `consistencyAnchors`（パレットHEX・線種・影方向・ライティング色温度・投影角=30度アイソメ・背景色・余白の固定6〜9アンカー）と GEOMETRY LOCK（投影角・カメラ高度）を**全ページに同一展開**する。構造系スライドの微俯瞰15度（§1.5）はこの LOCK の宣言済み例外として扱い、それ以外で角度を変えない。

これら4軸は style-genome に固定値として持たせ、`build-image-prompts.js` が全 prompt へ同一文面で機械展開する（手動で各ページに別表現を書かない。DRY）。

#### 1.11.2 一貫性の二系統手段（併用が最強）

ドリフトを抑える手段は次の2系統で、併用すると最も安定する。

- **(A) スタイル契約（style contract）の逐語再利用**: style-genome から展開した STYLE BIBLE プリアンブル（パレットHEX・線種・影方向・ライティング色温度・投影角・背景色・余白の固定アンカー文面）を、全ページのプロンプトへ**語順・修飾語までバイト同一**で再利用する。アンカーは6〜9個に絞り、ページ間で1語も揺らさない。これはビルダーの decision-deterministic な preamble 展開（§1, §2.1）が担保する。
- **(B) image-to-image 基準ページ参照**: 表紙（1枚目）を最高品質で確定し（§1.8 / §3）、これを**参照画像**として各ページを image-to-image で生成する。参照には**役割ラベルを付けて identity と style を分離**する（`identity reference`=被写体の同一性を保つ参照 / `style reference`=画風・配色・投影だけ借りる参照）。各ページの被写体は変わってよいが style reference として渡せば画風だけが伝播する。meta には参照画像パスと役割ラベルを記録する。

#### 1.11.3 再生成時のドリフト防止

- 再生成は**1度に1変数だけ**変える（色だけ・配置だけ・テキストだけ）。複数同時変更は画風が連鎖崩壊する。
- **最重要ディテールは毎回再記述**する（投影角30度・影方向・パレットHEX・粒度維持・コード描画禁止）。省略するとモデルが平坦化・配色ドリフトへ退化する（§1.1.1）。
- 1ページ再生成後は隣接ページと並べて密度・重心・読み方向の連続性を目視する（§6 の目視に含める）。

#### 1.11.4 gpt-image-2 生成設定（size / アスペクト / 透過 / quality）

全面画像デッキの生成は gpt-image-2 の制約に合わせる。1スライド = 16:9 / **2560×1440** を基本とする。

| 項目 | 設定 | 根拠・注意 |
|------|------|-----------|
| size 基本 | 2560×1440（16:9） | デッキ標準。両辺とも16の倍数を満たす |
| 辺の倍数 | 両辺16pxの倍数 | gpt-image-2 制約。端数サイズは指定しない |
| 長辺上限 | 3840px未満 | 高精細版でも長辺3840px未満に収める（4K相当は 3824×2144 など16px倍数へ丸める） |
| アスペクト上限 | 最大3:1 | 横長パノラマでも3:1を超えない。デッキ標準16:9は範囲内 |
| 透過 | バックエンド対応を事前確認 | 全面画像デッキは印刷・contain表示の安定性を優先し、背景は原則塗る（§1.1 の `backgroundColor` アンカー）。透過前提のレイヤ設計を既定にしない |
| quality | 密テキストは `quality: high` | 画像内に日本語・コード・密ラベルを焼く `baked-with-overlay` ページは high。装飾のみの背景は標準で可 |
| 出力形式 | PNG 元画像保持 → WebP 化 | §1.9 / §6 の変換フローに従う。全面画像デッキでは通常アルファなしの不透明背景にする |

`build-image-prompts.js` の safeArea px 自動計算（§0.3）は 2560×1440 基準のため、size を変える場合は基準解像度との比率で safeArea も再計算する（手書きしない。D7）。

---

## 2. 生成プロンプトキット規約

STYLE BIBLE と各スライド差分から、1 スライド = 1 プロンプトのファイル群を `assets/generated/` 配下に作る。どの画像生成バックエンドでも即実行できる形にする。

v8.2.0 以降、このファイル群は手作業ではなく `scripts/build-image-prompts.js` が `assets/generated/image-deck-plan.json`（per-slide 差分の入力契約・`schemas/image-deck-plan.schema.json` 準拠）と `assets/generated/style-genome.json` を合成して機械生成する。STYLE BIBLE preamble は手動展開せずビルダーが決定論で展開するため、`{slug}.prompt.md` / `{slug}.meta.json` の整合（STYLE GENOME 参照・`styleGenome` フィールド・pattern×textPolicy 整合）が崩れない。手作業はビルダーを使わない単発差し替え時に限る。

### 2.1 `{slug}.prompt.md`（1スライド1プロンプト）
- 先頭に **STYLE BIBLE プリアンブルの実体**（`{{STYLE_BIBLE}}` を展開した文面）を置く（`build-image-prompts.js` がこの展開を機械的に行う。手動展開は不要）。
- 続けてスライド固有プロンプト（Purpose / Audience takeaway / Background / Intended use / Layout / Subject / Diagram structure / Generation / 画像内テキスト方針）。これはイラスト依頼ではなくスライド成果物仕様として書く。
- 末尾に共通スタイルサフィックスと `Negative:` 行。
- 参考コメント（`<!-- -->`）は投入不要情報として末尾に置いてよい。

### 2.2 `{slug}.meta.json`（再現性・検証メタデータ）
最低限のフィールド:

| フィールド | 内容 |
|-----------|------|
| `slide` | スライド番号 |
| `slug` | slug |
| `asset` | 画像ファイル名 |
| `source` | 実際に使った text-to-image バックエンド名（`codex` 単体は不可） |
| `decision` | `generate-image`（必須。生成判断の記録） |
| `pattern` | `image-only` / `html-composite` / `html-primary` |
| `textPolicy` | `baked-with-overlay` / `overlay-only` / `none` |
| `backgroundSource` | `raster` / `svg` / `none`（必須。`image-only` は `none`、`svg`=SVG/CSS背景でラスター画像なし） |
| `styleGenome` | 使用したスタイルゲノムのパス |
| `seed` | 常に null（gpt-image-2 は seed 非対応）。再現条件は `generation`(modelSnapshot/quality/size) に記録 |
| `aspect` | `16:9` |
| `resolution` | `2560x1440` |
| `alt` | 代替テキスト |
| `overlayText` | HTML オーバーレイ正テキストの配列 |
| `reason` | このスライドを画像化する理由 |
| `accent` | 主アクセント色 |
| `camera` | カメラ角（基準アイソメ / 微俯瞰15度 等） |
| `purpose` | この画像が解く課題・スライド上の目的 |
| `audienceTakeaway` | 聴衆が1文で理解すべきこと |
| `background` | 場面・前提・前後スライドとの接続・デッキ内役割 |
| `intendedUse` | presentation infographic / explanatory diagram などの成果物用途 |
| `layout` | `grid` / `zones` / `readingOrder` / `focalPoint` / `emphasis` |
| `generation` | `modelSnapshot` / `quality` / `size`。再生成条件として必須 |

QR・ロゴ等の実画像が必要なスライドは、加えて次を付与する（§4 参照）:

| フィールド | 内容 |
|-----------|------|
| `hybrid` | `true` |
| `real_overlay_asset` | 別レイヤ合成する実画像のパス |

### 2.3 `README.md`
- キットの構成・使い方（プロンプト全文を画像生成ツールへ投入 → `{slug}.png` で保存 → WebP 化 → HTML 参照）。
- 再現性運用（§3）。
- 検証コマンド（§6）。
- slug 主題表（No / slug / 主題メッセージ）。
- 注意（オーバーレイ fallback・ハイブリッド例外・数値禁止スライド・絵文字ゼロ）。

---

## 3. 再現性運用

**再現性の定義**: ここでの「再現性」は、画風・配色・モチーフ・構図ルールという**スタイル仕様（お手本・スタイルガイド）を毎回確実にプロンプトへ反映すること**を指す。1枚1枚をピクセル単位で完全一致させることではない（seed 完全固定・1px 一致は任意目標）。固定するのはスタイル仕様だけであり、図解の中身（ノード数・配置・ラベル・被写体）はスライドごとに自由に変わる。`build-image-prompts.js` が `style-genome.json` の仕様を漏れなくプロンプトへ反映し、`validate-ai-image-assets.js --check-genome-content` が反映漏れを検出することで、この一貫適用を機械的に保証する。

1. **表紙を最初に最高品質で確定**する。これをデッキ全体の style reference（参照画像）とする。
2. 残りのスライドは表紙を `styleReference.anchorSlug` として渡し、画風(STYLE LOCK プリアンブル)＋参照画像チェーンで量産する（seed は非対応。全プロンプトに同一の先頭 STYLE LOCK プリアンブルが入るため画風がぶれない）。
3. 各スライドの再現条件(model/quality/size)を `{slug}.meta.json` の `generation` に記録する（seed は gpt-image-2 非対応のため使わない）。
4. アスペクト比は全枚 16:9（2560×1440）を厳守する。

---

## 4. ハイブリッド例外（実画像が必要なスライド）

QR コード・ロゴなど、**読み取り精度・正確性が必要な実画像**は生成画像に描かせない。

- 生成画像内では描画を禁止する（ネガティブに `no QR code, no barcode` 等を追加）。生成画像は背景のみとする。
- 実画像は**別レイヤで HTML 合成**する（角丸パネル余白を生成画像側に空けておく）。
- `{slug}.meta.json` に `hybrid: true` と `real_overlay_asset`（実画像パス）を付与する。
- ハイブリッド例外は運用宣言（§0）に必ず明記し、デッキ内で例外箇所を最小限にとどめる。

---

## 5. 日本語テキスト崩れ対策

画像内に日本語を焼く方針（`textPolicy: baked-with-overlay`）でも、生成 AI は日本語（濁点・長音・英数混在）の正確描画が不安定で、1 枚の誤字でも信頼を損なう。

- `baked-with-overlay` はユーザーが画像内説明文を明示した場合だけ使う。
- 各スライドに **HTML オーバーレイ fallback（正テキスト）を必ず併記**する（`overlayText` 配列が正本）。
- 崩れ判定時はオーバーレイを表示し、画像内文字は装飾扱いに切り替える。
- オーバーレイ部のテキストは skill のテキスト規律を守る（`<ul><li>` 文字列リスト禁止 → chip / カード / アイコン+ラベル、本文・見出し・chip の最小サイズ、20文字超見出しの `<br>`）。
- 印刷時も意味テキストは HTML オーバーレイで常に鮮明にする（画像内文字が崩れても可読）。

---

## 6. 検証フロー

1. `node scripts/convert-to-webp.js <slide-dir> --quality 90` … PNG → WebP（品質90）
2. `node scripts/validate-ai-image-assets.js <slide-dir> --full-image-deck --strict-style-genome --check-genome-content` … prompt / meta / WebP / style-genome 契約の整合検証（各 prompt の STYLE GENOME / STYLE BIBLE 参照に加え、promptSuffix 主要語・motif 名・accent HEX などスタイル仕様の prompt 反映まで検証）。**PNG/WebP 署名検査**：各 `.png` の先頭バイトが PNG 署名（`89 50 4E 47 0D 0A 1A 0A`・最低でも先頭4バイト `89 50 4E 47`）であること、各 `.webp` が RIFF/WEBP 署名であることを検証し、中身がテキスト/壊れ（例: 先頭が `# Image Generation Skill`）の場合は FAIL（`--full-image-deck` では `image-deck-plan.json` の全スライドについて png/webp 双方を検査）。`index.html` を読み主キャンバス class（`.ai-slide-canvas` ＋エイリアス）＋`object-fit:contain`＋`imageFit` meta の cross-check、`image-deck-plan.json` 不在の FAIL 昇格、`meta.builtBy` マーカー無し（手書き meta）の警告まで含む
3. `node scripts/validate-print.js <slide-dir>/index.html` … 印刷契約検証。P06 を 16:9 letterbox（167mm）許容に拡張し、`@media print` 内 `object-fit: cover` を CRITICAL 検出、全ページ印刷対象・`data-hidden` 除外漏れを検査
4. `node scripts/verify-slides.js ./index.html --check-ratio` … 16:9 比率検証
5. `node scripts/evaluate-deck.js <slide-dir>` … 生成後評価ゲート（D1〜D4）。**full-image-deck を検出すると `validate-print.js` と `validate-ai-image-assets.js --full-image-deck --strict-style-genome --check-genome-content` を spawn し、CRITICAL / exit 1 で総合 verdict を FAIL にする**。手動で 2/3 を飛ばしてもこのゲートで再検出される（検証ゲート接続）
6. 目視 … 被写体切れ・文字崩れ・コントラストを確認。画像は Read ツールまたは PNG/WEBP 署名で実体検証する（§6.9.2 / §6.9.3）
7. A4 印刷 … PNG 欠落なし・端欠けなしを確認（印刷は PNG 300dpi 保持・意味テキストは HTML オーバーレイで鮮明、主画像は 16:9 letterbox の contain）
8. `structure.md` 同期 … 画像パス・alt・prompt/meta パス・差し替え理由・オーバーレイテキスト・修正履歴を同期
9. 動作確認（必須・完成条件）… 自己完結HTML（§6.9.1）を playwright で開き、全枚が画像として表示され（broken 無し）左右ページ送りが実際に動くことをスクショで目視する。Bash 出力・サイズ・"PASS" を完成判定に使わない（§6.9.3 / §6.9.4）
10. GAS デプロイ前のみ … `node scripts/validate-ai-image-assets.js <slide-dir> --gas-check` で相対パス画像残存を確認する（相対パス画像は GAS で broken になるため、マニフェスト＋外部URL／軽量 base64 への切替を確認。§6.9.1）

---

## 6.9 再現性・堅牢性の鉄則（実運用反映）

全面画像デッキを実運用したところ、検証は緑なのに「スライドが動かない」「画像が表示されない」「テキストが .png 名で保存されていた」という事故が複数起きた。原因は (a) CSS/JS が別ファイルで環境により消失、(b) codex の image_gen が指定パスへのコピーに失敗・一部で画像生成自体に失敗し説明テキストを `.png` 名で保存、(c) この運用環境では Bash 標準出力が改変されることがあり `echo`/サイズ/"PASS" を完成判定に使うと誤判定する、の3点である。次の5鉄則を全面画像デッキの不変運用とする。

### 6.9.1 自己完結HTMLを既定にする（CSS/JS インライン化）

styles.css / scripts.js が別ファイルだと、環境によって消失して「ページ送りができない・スライドが動かない」事故が起きた。全面画像デッキでは **CSS と JS を `index.html` に `<style>` / `<script>` でインライン化した自己完結HTML を既定**とする。

- index.html 単体をブラウザで開くだけで、全スライド表示・左右ページ送り・キーボード送り・ページネーションが動くこと。外部 `styles.css` / `scripts.js` への `<link>` / `<script src>` 依存をデフォルトで持たない。
- 別ファイル版（`styles.css` / `scripts.js` 分離）は**任意・後方互換**として残してよいが、その場合も配布・検証は3ファイル一式が揃っていることを前提にする。GAS デプロイ用1ファイル化（`build-single-html.js`）とは別概念で、全面画像デッキは**生成時点から自己完結**を既定にする。
- ここでの「自己完結HTML」は **CSS と JS を index.html へインライン化したもの**を指し、**画像までは含まない**（用語の過大評価をしない）。インライン化対象は CSS と JS のみで、画像（`.webp` / `.png`）の既定は外部ファイル参照（相対パス）である。
- **ローカル動作・印刷・別ファイル配布**では、画像は相対パスのままでよい（インライン data URI 化は不要）。
- **GAS デプロイ時のみ別契約**: 相対パス画像は GAS から配信されず broken になる。GAS で画像を表示するには (a) **マニフェスト＋外部URL参照**（既定。`assets/generated/image-asset-manifest.json` 駆動・`build-deck-html.js --manifest`／`--asset-base-url`）、または (b) **軽量デッキのみ base64 自己完結**（`build-single-html.js --inline-images --full-image-deck`）が要る。base64 は実バイト×約1.37に膨張するため、合計が GAS 500KB 上限を超える全面画像デッキでは (a) を使う。詳細は [../assets/gas-deploy-guide.md](../assets/gas-deploy-guide.md) / [image-format-guide.md](image-format-guide.md)。

#### 自己完結HTMLは `build-deck-html.js` で決定論生成する（手作業禁止）

自己完結 index.html は手作業で `<style>` / `<script>` を書き起こさず、**`scripts/build-deck-html.js` で `image-deck-plan.json` と各 `slide-NN-{slug}.meta.json`（alt）から決定論生成**する。CSS / JS はスクリプト内の固定テンプレート（LLM 非依存）であり、同じ plan からは常に同じ HTML が出力される（手書きによる `<style>`/`<script>` 消失・記述ぶれの再発を断つ）。

- **入力**: `assets/generated/image-deck-plan.json`（slides[] の slide / slug / pattern 等）＋ 各 `slide-NN-{slug}.meta.json` の `alt`。
- **出力**: `<slide-dir>/index.html`（CSS を `<style>`・JS を `<script>` でインライン化した自己完結 HTML）。
- **生成内容**: 各 `<section>` の `data-type` は slug の接頭辞 `slide-NN-` を除いた残り、`alt` は meta の `alt`、CSS / JS はスクリプト固定テンプレート。

手順:

```bash
# 1) plan.json + meta から自己完結 index.html を決定論生成
node scripts/build-deck-html.js <slide-dir>
# 2) 動作可能性ゲート（Dx）が PASS することを確認（CSS/JS 実在・表示切替CSS・ページ送り制御JS）
node scripts/evaluate-deck.js <slide-dir>
# 3) playwright（実 Chrome）で全枚表示・broken 無し・左右ページ送りをスクショ目視（§6.9.4）
```

`evaluate-deck.js` の Dx PASS は静的検査であり、実描画は保証しない。出荷前は §6.9.4 の playwright スクショ目視を必ず行う。

### 6.9.2 画像回収は PNG署名確認＋リトライ必須

codex の image_gen は generated_images に保存し**指定パスへのコピーが不安定**で、かつ一部で**画像生成に失敗して説明テキストを `.png` 名で保存**することがある。`existsSync` だけの確認では「テキストが入った .png」を成功とみなしてしまう。回収は次の手順で行う。

1. **session-id 特定**: codex exec のセッション/出力ディレクトリ（generated_images）を特定し、生成物の実体を探す。
2. **指定パスへコピー** → コピー漏れに備え generated_images からの回収パスもフォールバックに持つ。
3. **PNG署名確認（必須）**: 回収した `.png` の先頭バイトが PNG マジックナンバー **`89 50 4E 47`**（hex `89504e47` = `\x89PNG`）であることを検査する。WebP は先頭が `52 49 46 46`（`RIFF`）＋オフセット8の `57 45 42 50`（`WEBP`）。署名不一致（テキスト等）は失敗とみなす。
4. **最大3回リトライ**: 署名不一致・コピー失敗・PNG不在のいずれかなら、同一プロンプトで最大3回まで再生成・再回収する。3回失敗したスライドは `pending-imagegen` として明示し、無言で成功扱いにしない。

署名検査コマンド例（hex 先頭4バイト）:

```bash
# PNG なら 89504e47 を返す。テキストや空ファイルは別値。
xxd -p -l 4 assets/generated/slide-01-cover.png   # => 89504e47
# WebP 検査（先頭 RIFF + offset8 WEBP）
xxd -p -l 4 assets/generated/slide-01-cover.webp        # => 52494646 (RIFF)
xxd -p -s 8 -l 4 assets/generated/slide-01-cover.webp   # => 57454250 (WEBP)
```

> 実装状態: `scripts/generate-images-codex.js` は §6.9.2 の回収契約を**実装済み**である。codex に保存を任せず、ログから `session id:` を grep 抽出して `$CODEX_HOME/generated_images/<session-id>/` を特定し（`extractSessionId` / 並列でもログ単位で確実に取得）、その session dir から **PNG署名（`PNG_SIGNATURE = [0x89,0x50,0x4e,0x47]`）を持つファイルだけ**を新しい順で1件回収する（`findFreshPngInSession` / `isPngFile` でテキスト .png を除外）。失敗時は `MAX_RETRIES`（最大3回）で再実行し、webp 化は cwebp →（無ければ macOS の sips）へ自動フォールバックする。`scripts/validate-ai-image-assets.js` も `--full-image-deck` で各 `.png` の PNG署名（`89 50 4E 47 0D 0A 1A 0A`）・各 `.webp` の WebP 署名を検査し、テキスト/壊れを FAIL にする。実装に加え、最終確認として生成後に上記 `xxd` 署名検査を手動実施しておくと安心である（自動検証とは独立した出荷前の目視確認として有用）。

### 6.9.3 検証は実体で行う（Bash出力・md5・"PASS" を信じない）

この運用環境では **Bash の標準出力が改変されることがある**。`echo`・ファイルサイズ・スクリプトの "PASS" 文字列を完成判定に使ってはいけない。

- **ファイルは Read ツールで実体を読む**（HTML/CSS/JS/meta/structure）。Bash の `cat`/`head` 出力で判断しない。
- **画像は Read ツールで目視**するか、§6.9.2 の **PNG/WEBP 署名検査**で妥当性を確認する。
- **md5「固有」は画像妥当性を保証しない**。テキストファイルでも固有の md5 を持つため、「md5 がユニークだから別画像（=正しく生成された）」という推論は誤り。必ず **PNG/WEBP 署名**で「画像であること」を検証する。md5 は同一画像の重複検出（全ページが同じ1枚になっていないか）にのみ補助的に使う。
- 最終形は **playwright スクショ**で確認する（§6.9.4）。スクショは画像なので Bash 出力改変の影響を受けず、実描画を直接見られる。

### 6.9.4 完成条件に「動作確認」を必須化

「ブラウザ / playwright で開いてページ送りが実際に動く」「全枚が画像として表示される（broken 無し）」をスクショで確認するまで**完成と呼ばない**。grep / 評価 PASS だけで完成判断しない（MEMORY: スライド生成後はスクショで目視確認してから完了報告）。

- **動作可能性ゲート（Dx）**: CSS / JS が（インラインまたは実在ファイルとして）実体を持つこと、スライド切替CSSが機能すること、ページ送り制御JSが存在することを `scripts/evaluate-deck.js` の **Dx「動作可能性／自己完結性」**（static・CRITICAL）で検査する。Dx error は verdict を FAIL にする。あわせて D3（左右ページ送り・ページネーション検出）・D1（broken img / 画像欠落）も使う。
- **playwright 全スライド撮影**: chromium で各スライドを撮り、画像が全枚表示され（broken 無し）、ページ送りで実際に次/前へ動くことをスクショで目視する。playwright 実行には `dangerouslyDisableSandbox` が必要（MEMORY: スライド生成後はスクショで目視確認）。

> 実装状態: `scripts/evaluate-deck.js` v3（2026-06-26）で §6.9.1 の **「CSS/JS が自己完結HTMLとして実在（インライン or 実体ファイル）し、スライド切替CSS＋ページ送り制御JSが成立するか」を1つの動作可能性チェック（Dx）として束ねる機能を実装済み**。(1) 参照CSSの実在＋非空 or `<style>` (2) 参照JSの実在＋非空 or `<script>` (3) `.slider__item` の表示切替CSS（opacity/visibility/display × `.is-active`|`.active`）(4) ページ送り制御JS（`querySelectorAll('.slider__item')`＋active付替 / 矢印キー / prevBtn-nextBtn-dots-counter または arrowLeft-arrowRight-slideCounter-pageNav）を CRITICAL で検査し、いずれか欠落で FAIL。chromium 非依存。**ただし「実際に描画されページ送りが動く」最終確認は依然 playwright スクショ目視を必須**とする（静的解析は実描画を保証しない）。

### 6.9.5 順序: 動く骨格を先に、画像は後で流し込む

重く不確実な画像生成（1枚あたり概ね1〜2分・課金あり・失敗あり）より先に、**動く骨格（自己完結HTML）を作って動作確認**してから画像を流し込む。

1. structure / plan.json を確定する（§1, §2）。
2. プレースホルダ画像（または `pending-imagegen` の空枠）で**自己完結HTML（§6.9.1）を先に組み、playwright でページ送り動作を確認**する（§6.9.4）。
3. 動く骨格が確定してから `generate-images-codex.js` で画像を量産し、§6.9.2 の署名確認＋リトライで回収する。
4. 画像を流し込んだ後、再度 playwright スクショで全枚表示・ページ送りを確認する。

これにより、画像生成のコスト・失敗が骨格の動作不良と切り分けでき、「画像は出たが動かない」「動くが画像が壊れている」を別々に潰せる。

---

## 7. 部分AI画像化プリセット（バランス型・HTMLシャーシ併存）

全面画像化（§0）が「全 N 枚を画像で構成する」特殊運用であるのに対し、本節は **HTML シャーシ（header / footer / section-nav / pagination 等の固定 UI）を持つデッキに、画像を背景・モチーフとして部分的に併存させる**バランス型運用を定義する。§0 とは排他であり、どちらか一方のみを採用する。

### 7.1 適用条件

ユーザーが「部分AI画像化」「バランス型」を**明示的に選択**し、かつデッキが header / footer / section-nav / pagination 等の HTML シャーシを持つ場合にのみ適用する。全面画像化（§0）とは排他で、両者を同一デッキに混在させない。HTML シャーシ・現行コンポーネントは温存したまま、一部スライドにのみ画像レイヤを足す。

### 7.2 不変追加制約プリセット「no-person × no-baked-text × cute-icon-isometric × html-shassis」

部分AI画像化では、§0 の不変制約に加えて次のプリセットを必ず保持する。

| 不変追加制約 | 内容 |
|------------|------|
| no-person（人物ゼロ） | 人物を一切描かない（no people / figures / faces / hands）。人の不在は「空席＋吹き出し」等、人がいる"場"の描写で表す |
| no-baked-text（非焼き込み） | 画像内テキスト完全非焼き込み。文字・数値・ロゴを画像に描かせない。意味テキストは HTML オーバーレイ（`overlayText`）が唯一の正本 |
| cute-icon-isometric（アイコン風アイソメ） | 可愛いアイコン風アイソメトリック（角丸・フラット・ソフト接地影・白基調・余白多め）で統一する |
| html-shassis（HTMLシャーシ限定） | 画像は CSS カードの「背景／モチーフ」に限定する。前面の見出し・ラベル・図解は HTML が担い、画像に意味伝達を負わせない |

### 7.3 形式振り分けルブリック（毎回ヒアリングで決める）

スライドごとに、画像をどの程度使うかを**毎回ヒアリングで決める**。次の3形式へ振り分ける。

| 形式 | 画像の使い方 | 向くページ |
|------|------------|-----------|
| HTML主役 | 画像なし、または背景アクセントのみ | 表・料金・比較マトリクス・数値の塊・密度の高いページ・逐語が頻繁に変わるページ。現行コンポーネントを温存 |
| イラスト主役 | 背景フル＋HTML overlay | 章扉・コンセプト・キーメッセージ・概念図（被写体1点で語れるもの） |
| ハイブリッド | 背景地＋前面 HTML カード | 対比・手順・構造（順序／個数／役割が意味を持つもの） |

原則: **数値・逐語が変わりやすいページほど HTML 主役へ寄せる**（退化耐性。§7.6）。迷ったら HTML 主役を選ぶ。

### 7.4 4レイヤモデル

部分AI画像化のスライドは次の4レイヤで構成する。意味の正本は常に②に置く。

| レイヤ | 役割 | 備考 |
|-------|------|------|
| ① 画像 | 背景・装飾 | アイコン風アイソメの背景／モチーフ。意味テキストは焼かない |
| ② HTMLオーバーレイ | 意味テキスト（正本） | 見出し・ラベル・数値の SSOT。`overlayText` が正 |
| ③ CSSカード図解 | 精密図の例外 | 正確な図解（軸図・順序図等）は CSS カードで描く |
| ④ HTMLシャーシ | 固定 UI | header / footer / section-nav / pagination 等 |

### 7.5 共通ネガティブ強化

部分AI画像化の全プロンプト末尾の `Negative:` 行に、§1.7 の共通ネガティブに加えて次を必ず含める。

`people, humans, figures, faces, hands, photorealistic, 3d, glossy, neon, baked text, letters, words, numbers, captions, labels, typography, logos, watermarks, emoji`

### 7.6 退化耐性

逐語・数値が変わるスライドは**画像化しない**（変更のたびに画像再生成が必要になり退化する）。表紙のみ最初に確定し、これを style reference として凍結する。意味テキストは `overlayText`（②）が正本のため、**文言変更があっても画像の再生成は不要**になる。これにより、内容差し替え時の運用コストと画風退化リスクを断つ。

#### 7.6.1 コード非画像化原則（退化耐性の極限適用）

コード（slide-code / slide-code-compare）は、image-only デッキ・全面AI画像化デッキを含むどの場合でも、生成画像に焼き込まず、常に実HTMLコードブロック（`.code-block` / `.code-compare-body`）で描画する「コード専用ページ」とする。これは新規例外ではなく、退化耐性（§7.6）の最も極端な適用であり、既存原則の一般化である。理由は次の4点。

- **判読性**: コードは1文字の差で意味が変わり、画像の文字描画の不安定さが致命的になる。
- **コピー可能性**: 聴衆が実テキストを選択・コピーできることがコードの価値である。
- **再現性**: 文言変更のたびの画像再生成が不要になる。
- **印刷品質**: 密なコードはラスターで潰れる。

`overlayText` の崩れ時フォールバックはコードでは原理的に機能しない（コードは一部を装飾扱いにできず全体が正本のため）。機械契約として、コード系 slideType は `aiVisual.pattern` を `image-only` にできず、`aiVisual.textPolicy` を `baked-with-overlay` にできない（`scripts/validate-structure.js` V-043 と `schemas/structure.schema.json` が正本）。世界観背景が要る場合のみ `html-composite` + `backgroundSource: svg`（推奨）/ `raster` + `overlay-only` に限定する（背景は装飾・コードは常にHTML前面）。

このコード非画像化原則は、§4 の QR・ロゴ等のハイブリッド例外（実画像が必要なスライド）と同格の例外として扱う。より一般に、正確性必須・逐語コンテンツ（コード・数式・精密数値表・コマンド列／APIレスポンス例）は画像化しない。コード2タイプ（slide-code / slide-code-compare）は機械検証で固定し、数式・精密数値表はLLM判断＋ルブリックで実HTML側へ振り分ける。

### 7.7 生成器

部分AI画像化の画像は、事前確認済みの text-to-image バックエンドで生成する。`codex` はコーディングエージェントであり、単体の画像生成器として扱わない。`{slug}.meta.json` は次のとおりとする。

- `source` に実際に使った生成バックエンド名を記録する。
- 拡張キー `role` を付与し、`illustration-primary` / `hybrid-background` / `none` のいずれかで、そのスライドにおける画像の役割（§7.3 の形式）を記録する。

---

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-02 | 初版: 全面AI画像化（世界観統一）メソッドを正式リソース化。STYLE BIBLE 10節雛形・生成プロンプトキット規約・再現性運用・ハイブリッド例外・日本語崩れ対策・検証フローを規約化 |
| 1.1.0 | 2026-06-03 | §1.1.1「イラスト粒度の統一（重要・再発防止）」追加。全スライドをリッチなアイソメ・イラスト粒度で統一し、単色角丸ボックス＋テキストだけの平坦図（SVGはめ込み風）を禁止。再生成時に粒度が退化する事象への対策（プロンプト明記＋既存良質スライドを画風リファレンスに）を規約化 |
| 1.2.0 | 2026-06-23 | §7「部分AI画像化プリセット（バランス型・HTMLシャーシ併存）」追加。部分AI画像化プリセット（人物なし×非焼き込み×アイコン風×HTMLシャーシ併存）追加。形式振り分けルブリック・4レイヤモデル・共通ネガティブ強化・退化耐性・Codex Image2 生成器（source: codex-image2 / role 拡張キー）を規約化 |
| 1.3.0 | 2026-06-23 | `style-genome-packaging.md` 連携、Pattern A/B、`pattern`/`textPolicy`/`styleGenome` メタデータを追加。漫画チックな説明文入り図解は `image-only + baked-with-overlay`、HTML合成は `html-composite + overlay-only` として責務分離 |
| 1.4.0 | 2026-06-24 | 正準モデル整合（elegant-review）。`textPolicy` から `html-primary` を廃止し `none` を追加。`backgroundSource`(raster/svg/none) を追加し SVG/CSS背景型に対応。§2.2 meta フィールド表に `decision`=`generate-image`（必須）を明記。パターン/値域の定義を `style-genome-packaging.md` §4（人間可読 正本）と `scripts/validate-ai-image-assets.js`（機械 正本）に一本化 |
| 1.5.0 | 2026-06-24 | ビルダー連携（SKILL.md v8.2.0）。§1 実行順を `image-deck-plan.json`（per-slide 差分の入力契約・`schemas/image-deck-plan.schema.json`）→ `scripts/build-image-prompts.js` による prompt.md/meta.json 機械生成へ更新。§2 生成プロンプトキット規約・§2.1 に STYLE BIBLE preamble の自動展開（手動展開不要）を明記。§3 再現性運用に「目的はスタイル仕様の一貫適用であり、ピクセル単位の完全コピーではない」を明記。§6 検証に `--check-genome-content` を追加 |
| 1.5.1 | 2026-06-24 | パイロット実証の知見反映。§1.1.1 に「退化の具体的機序（codex 等コーディングエージェント経由時）」を追加。codex は imagegen（text-to-image 拡散モデル）の使用を明示強制しないとコード（PIL/matplotlib/SVG）でプログラム描画して平坦なボックス図に退化するため、「imagegen 使用・コード描画禁止・リッチなアイソメイラスト維持」をプロンプトへ必須化（`scripts/generate-images-codex.js` が実装済み） |
| 1.7.0 | 2026-06-25 | gpt-image-2 一貫性指針。§1.11「デッキ全体の構図・画風一貫性（gpt-image-2 ドリフト対策）」追加: readingOrder（left to right 統一）・focalPoint 高さ・densityLevel をデッキ全体で固定し、style-genome の consistencyAnchors（固定6〜9アンカー）と GEOMETRY LOCK を全ページへ同一展開。一貫性の二系統手段（(A) スタイル契約テキストのバイト同一逐語再利用 / (B) image-to-image 基準ページ参照を identity/style 役割ラベルで分離）を明記。再生成は1度に1変数・最重要ディテール毎回再記述でドリフト防止。gpt-image-2 生成設定（両辺16px倍数・長辺3840px未満・アスペクト最大3:1・透過はバックエンド対応確認・全面画像デッキは不透明背景既定・密テキストは quality:high・基本 2560×1440/16:9）を表で固定。§0.0 本文に「Codex Image 2 / image2 / Image 3 トリガー語の実体は最新 gpt-image-2（Codex CLI 内部）」の後方互換注記を追加 |
| 1.6.0 | 2026-06-24 | 実装整合（elegant-review・D1/D2/D3/D7/D10）。§0.3 を「印刷ビューポート契約の正本」と位置づけ一本化。主キャンバスクラス規定を実装に一致（規定 `.ai-slide-canvas` 実体＋後方互換エイリアス `.slide-fullbg`/`.slide-bg`/`[data-role="main-canvas"]` を `:where()` で同一 contain 契約に束ねる）。印刷は A4横 16:9 letterbox（297mm→167mm・上下21mm off-white 余白）＋`object-fit:contain` 強制・`cover` 禁止、`data-deck-mode="full-image"` 限定適用で通常デッキ full-bleed 温存を明記。safeArea の px は `build-image-prompts.js` が 2560×1440 基準で自動計算（上下8%≈115px・左右6%≈154px）し手計算しないことを明記。§6 検証フローに `validate-print.js`（letterbox 許容・cover CRITICAL・全ページ印刷検査）と `evaluate-deck.js` の検証ゲート接続（full-image-deck 検出時に validate-print / validate-ai-image-assets を spawn し FAIL 連動）を追加。実装の正本は `assets/print-styles.css` / `assets/slide-template-single.html` と明記 |
| 1.8.0 | 2026-06-25 | 焼き込み表モード（D12）の反映漏れ修正（elegant-review 再検証）。§0.1 量産モードの分岐表に `image-only` + `tableMode: illustrated-full-table`（見出し＋全セルを画像内に焼き込む・`baked-with-overlay` 固定・`overlayText` に表全文保持）の行を追加し、image-only デッキで表を見せる場合は焼き込みを既定とすることを明記。§0 許可記述の旧方針（「表や比較の正確性が主目的なら html-composite」）を「精密な数値・料金・頻繁更新・長文・複数行コードのみ html-composite/html-primary、それ以外の対照表・5層表は illustrated-full-table で画像内に焼き込む」へ更新。焼き込み表構造の正本は `style-genome-packaging.md` §4.1・`ai-image-diagram-workflow.md` §4.1 と明記 |
| 1.9.0 | 2026-06-26 | 実運用の事故反映（再現性・堅牢性の鉄則）。§6.9「再現性・堅牢性の鉄則（実運用反映）」を新設。(1) 自己完結HTML（CSS/JS を index.html に `<style>`/`<script>` インライン化）を既定化し別ファイル版は任意・後方互換に降格（環境による styles.css/scripts.js 消失でページ送り不可になる事故対策）。(2) 画像回収は session-id 特定＋PNG署名（hex `89504e47`）確認＋最大3回リトライを必須化（codex image_gen のコピー不安定・テキストを .png 名で保存する失敗対策、`xxd` 署名検査コマンド例つき）。(3) 検証は実体で行う＝Bash 標準出力・サイズ・"PASS" を完成判定に使わず Read/署名/playwright で確認、md5「固有」は画像妥当性を保証しないため PNG/WEBP 署名で検証。(4) 完成条件に動作確認（playwright で全枚表示・broken無し・ページ送りが実際に動くスクショ目視）を必須化。(5) 順序＝重く不確実な画像生成より先に動く骨格（自己完結HTML）を作って動作確認してから画像を流し込む。§6 検証フローに手順9（動作確認）と署名検証の参照を追加 |
| 1.9.1 | 2026-06-26 | スクリプト実装完了に伴う実装状態の正確化。`generate-images-codex.js` の署名確認回収（session-id 特定＋PNG署名 `89504e47` 確認＋テキスト .png 除外＋最大3回リトライ＋cwebp/sips webp化）、`evaluate-deck.js` v3 の動作可能性チェック（Dx＝CSS/JS の実在/インライン・`.slider__item` 表示切替CSS・ページ送り制御JS を CRITICAL で静的検査し verdict FAIL 連動）、`validate-ai-image-assets.js` の PNG/WebP 署名検査をいずれも**実装済み**に確定。§6.9.2 / §6.9.4 の「未実装・実装目標・手動が当面必須」記述を実装済みに修正。実装に加え、出荷前の最終確認として playwright スクショ目視と手動 PNG/WEBP 署名検査を推奨する運用ガイドは維持 |
| 1.9.2 | 2026-06-26 | 自己完結HTMLの決定論生成を正規スクリプト化。§6.9.1 に「自己完結HTMLは `scripts/build-deck-html.js` で決定論生成する（手作業禁止）」を追記。`image-deck-plan.json` ＋ 各 `slide-NN-{slug}.meta.json`(alt) を入力に、CSS/JS をスクリプト固定テンプレート（LLM 非依存）として `<style>`/`<script>` にインライン化した `<slide-dir>/index.html` を生成する。各 `<section>` の `data-type` は slug 接頭辞 `slide-NN-` を除いた残り・`alt` は meta の `alt`。手順: `node scripts/build-deck-html.js <slide-dir>` → `node scripts/evaluate-deck.js <slide-dir>` で Dx 動作可能性 PASS 確認 → playwright スクショ目視（§6.9.4）。手書きによる `<style>`/`<script>` 消失・記述ぶれの再発を断つ |
| 8.4.0 | 2026-06-26 | GAS 画像表示対応（v8.4.0 連動）。§6.9.1 の「自己完結HTML」を CSS/JS 限定（画像は含まない）と明示し、用語の過大評価を打ち消し。ローカル動作・印刷・別ファイル配布は相対パス画像のままでよいが、GAS デプロイ時は相対パス画像が broken になるためマニフェスト＋外部URL参照（既定・`build-deck-html.js --manifest`／`--asset-base-url`・`image-asset-manifest.json` 駆動）または軽量デッキのみ base64 自己完結（`build-single-html.js --inline-images --full-image-deck`）が必要、と GAS 文脈を分離して明記（base64 は実バイト×約1.37膨張・500KB上限超過デッキは外部URL）。§6 検証フローに手順10「GAS デプロイ前は `validate-ai-image-assets.js --gas-check` で相対パス画像残存を確認」を追加 |
