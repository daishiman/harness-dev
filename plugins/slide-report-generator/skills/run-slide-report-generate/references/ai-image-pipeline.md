# Codex Image2 画像パイプライン規範（ai-image-diagram-producer 手続き知識 SSOT）

> **正本**: このファイルは ai-image-diagram-producer から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/ai-image-diagram-producer.md）の双方がこれを参照する。規則の上位正本 (SR-ID) は spec-registry.md を辿る。

**責務**: Codex Image2（gpt-image-2）による全面画像/差し替えパイプラインのドメイン定義（用語集・技術判定基準・生成パターン値域・制約カタログ CONST_001-008）と手続き知識（スタイルゲノム抽出・モード別ページ計画・スライド別 plan 言語化スキーマ・ビルダー連携プロンプト生成・画像生成の不変ルール・プロンプト作成ルール(gpt-image-2 再現性の原則・最小テンプレート)・HTML組み込みルール・全コード例）の逐語正本。ai-image-diagram-producer（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| スタイルゲノム | 参照画像・prompt・meta・HTML から抽出する画風の再利用可能パッケージ（`styleName`・パレット・反復モチーフ・カメラ角） | `style-genome.json` / STYLE BIBLE |
| `pattern` | 生成方式の3区分。`image-only` / `html-composite` / `html-primary` | §パターン表・CONST_005 |
| `textPolicy` | 画像内テキスト方針。`baked-with-overlay` / `overlay-only` / `none` | CONST_003 |
| `backgroundSource` | 背景の出所。`raster`（画像生成）/ `svg`（SVG/CSS描画）/ `none` | パターン表 |
| `overlayText` | `baked-with-overlay` 時の正テキストの真実源（prompt/meta/structure.md と同値） | CONST_003 |
| `meta.source` | 実際に画像を生成したバックエンド名（`codex` 単体は記録しない） | CONST_004 |

## 評価基準（ドメイン固有の判定基準）
| 判定 | 使う技術 | 基準 |
|------|----------|------|
| `code-html-block`（判定前に除外） | 実HTMLコードブロック（画像化しない） | slideType が slide-code / slide-code-compare。判定前に除外し `generate-image` に進めない。コード専用ページとして常に実HTMLコードブロックで描画 |
| `generate-image` | text-to-image backend + WebP | 情景、比喩、人物、プロダクト風モック、質感のある図解 |
| `keep-svg` | インラインSVG2 | 精密フロー、マトリックス、座標制御、ラベル多めの図 |
| `keep-d3` | D3/SVG | データ連動、インタラクション、数値グラフ |
| `needs-user-asset` | ユーザー提供画像 | 実在人物、実在製品、ブランド確認が必要な素材 |

### 生成パターンとテキスト方針の値域表
| パターン | `pattern` | `textPolicy` | `backgroundSource` | 基準 |
|---|---|---|---|---|
| 画像生成完結型 | `image-only` | `baked-with-overlay` / `overlay-only` | n/a | 漫画チック図解、章扉、少量説明文・吹き出し・簡易表を画像内に含める。正テキストは `overlayText` |
| HTML合成型 | `html-composite` | `overlay-only` | `raster` / `svg` | 背景・モチーフを画像生成（`raster`）または SVG/CSS で描画（`svg`）し、見出し・説明文・表・数値は HTML/CSS/SVG で重ねる |
| HTML主役 | `html-primary` | `none` | `none` / `svg` | 表・料金・数値・精密図解。画像生成しない（`none`）、または SVG/CSS 背景地のみ（`svg`） |

値域・パターンの正本は `$CLAUDE_PLUGIN_ROOT/references/style-genome-packaging.md` §4 と `$CLAUDE_PLUGIN_ROOT/vendor/scripts/validate-ai-image-assets.js`（CONST_005）。`baked-with-overlay` は、ユーザーが画像内説明文を明示した場合だけ使用し、文言の正確性は `overlayText` と HTML fallback で担保する。

## ビジネスルール
- **CONST_001 (明示指示必須)**: ユーザーが画像生成・Codex図解作成・スタイルゲノム量産を明示した場合、または修正案提示後に特定スライドの画像アセット化を承認した場合のみ起動する。「図解を作って」「見やすくして」「デザインを良くして」のみでは起動しない。
  - 目的: 高コスト・テキスト焼き込みリスクを伴う画像生成の暴発を防ぐ。
  - 背景: 通常のスライド生成は HTML/CSS/JS/SVG2/D3 で完結し、画像生成は例外手段だから。
- **CONST_002 (コード非画像化)**: slideType が slide-code / slide-code-compare のスライドは候補抽出の前段で無条件に除外し、`generate-image` / `image-only` / `baked-with-overlay` に進めない。常に実HTMLコードブロックで描画する。世界観背景が要る場合のみ `html-composite` + `backgroundSource: svg` + `overlay-only` に限定し、コードは常にHTML前面に置く。
  - 目的: コードの可読性・コピー可能性・文字正確性を保つ。
  - 背景: 画像化したコードは文字化け・選択不可・印刷崩れを起こし、コード専用ページの価値を損なうから。このガードは最優先・上書き不可。
- **CONST_003 (画像内テキスト原則禁止)**: 日本語ラベル・数値・重要テキストは画像内に焼き込まず HTML/SVG で重ねる（`overlay-only`）。`baked-with-overlay` はユーザーが画像内説明文を明示した場合だけ使用し、正テキストを必ず `overlayText` に保存する。
  - 目的: 文字化け・誤字・修正不能を防ぎ、テキストの真実源を1箇所に固定する。
  - 背景: text-to-image バックエンドは日本語・細かい文字を正しく描けないことが多いから。
- **CONST_004 (バックエンド事前確認必須)**: 着手前に利用可能な text-to-image バックエンドを確認する。`meta.source` には実際に使ったバックエンド名を記録し、`codex` 単体を画像生成器として記録しない。codex exec はこの環境で画像生成の実績がある確認済みの生成系の具体例であり、`$CLAUDE_PLUGIN_ROOT/vendor/scripts/generate-images-codex.js` 経由で使う場合も `meta.source` には実体名 `codex-image2` を記録する（plain `codex` 単体は不可）。
  - 目的: 生成不能環境での空振りと、誤った出自記録を防ぐ。
  - 背景: `codex` は呼び出し起点になり得るが画像生成器ではなく、実バックエンドの有無で実行可否が変わるから。codex exec は確認済みの具体例だが、出自記録は実体名（`codex-image2`）に正規化する。
- **CONST_005 (値域の単一正本)**: `pattern` / `textPolicy` / `backgroundSource` の値域は `$CLAUDE_PLUGIN_ROOT/references/style-genome-packaging.md` §4 と `$CLAUDE_PLUGIN_ROOT/vendor/scripts/validate-ai-image-assets.js` を正本とし、本ファイルで再定義しない。
  - 目的: 仕様の二重管理による不整合を防ぐ。
  - 背景: 値域が複数箇所に分散すると検証スクリプトと記述がずれるから。
- **CONST_006 (structure.md 同期必須)**: 差し替え時は画像パス・alt・prompt ファイル・差し替え理由・`pattern`・`textPolicy`・`styleGenome` を `structure.md` に同期する。
  - 目的: 表示物と仕様（SSoT）の乖離を防ぎ、再現・引き継ぎを可能にする。
  - 背景: `structure.md` が後続エージェントの判断材料であり、未同期だと検証・再生成が破綻するから。
- **CONST_007 (全面画像生成モードは背景化しない)**: ユーザーが「各ページを1枚ずつ画像生成」「スライド全体を生成画像で作る」「Codex Image 2 / image2 でページ画像を作る」と明示した場合、生成画像を単なる背景として扱わない。`$CLAUDE_PLUGIN_ROOT/references/full-image-deck-method.md` を適用し、非コードページは原則 `image-only` または必要時 `html-composite` として、各ページの主キャンバスを生成する。
  - 目的: 「画像生成したはずなのに背景だけ」「スタイルゲノムが一部にしか反映されない」という実装ずれを防ぐ。
  - 背景: 全面画像生成は通常の図解差し替えより強いユーザー意図であり、デッキ全体の世界観を style genome で固定してから量産する必要があるから。
- **CONST_008 (参照画像由来 style genome の先行固定)**: `05_Project/スライド/slide-2026-06-13-skill-mass-production/vendor/assets/generated/` 由来の画風再現を求められた場合は、生成前に同梱プリセット `$CLAUDE_PLUGIN_ROOT/vendor/assets/style-genome-kanagawa-comic-diagram.json` を project-local `vendor/assets/generated/style-genome.json` へコピーし、STYLE BIBLE と各 `{slug}.prompt.md` の先頭に反映する。各 meta は `styleGenome=vendor/assets/generated/style-genome.json` を持つ。
  - 目的: 画風の一貫性をプロンプト作成後の努力目標ではなく、生成前の入力契約にする。
  - 背景: per-slide の差分だけで量産すると、モデルが平坦なボックス図や別画風へ退化しやすいから。

## 5.5.1 スタイルゲノム抽出とモード別ページ計画（不変ルール）
- スタイル再現要求がある場合、参照画像・prompt・meta・HTML から STYLE BIBLE と `style-genome.json` を作る（`styleName`・パレット・反復モチーフ・カメラ角。抽出手順は `$CLAUDE_PLUGIN_ROOT/references/style-genome-packaging.md`）。`slide-2026-06-13-skill-mass-production/vendor/assets/generated/` の画風再現では、同梱プリセット `$CLAUDE_PLUGIN_ROOT/vendor/assets/style-genome-kanagawa-comic-diagram.json` を project-local `vendor/assets/generated/style-genome.json` へコピーし、必要な差分だけ上書きする（CONST_008）。全面画像生成モードで genome が存在しない場合は候補抽出に進まず `pending-style-genome` として停止する。
- 全面画像生成モードでは全スライドを走査し、各ページに `pattern` / `textPolicy` / `backgroundSource` / `styleGenome` / `overlayText` を割り当てる。非コードページは原則 `image-only`、正確な表・数値・逐語が主役のページは `html-composite` または `html-primary`、コード系は実HTMLコードブロックに固定する（`$CLAUDE_PLUGIN_ROOT/references/full-image-deck-method.md` §0〜§2、`$CLAUDE_PLUGIN_ROOT/references/style-genome-packaging.md` §4）。1スライド1行の生成計画を持ち、画像を「背景」としてだけ扱うページを作らない。各ページの prompt は STYLE GENOME / STYLE BIBLE preamble + per-slide diff で構成する。
- 技術判定は Layer 2 生成対象の基準マトリクスに従い、各候補に `keep-svg` / `keep-d3` / `generate-image` / `needs-user-asset` の1判定を付ける。`generate-image` を `image-only` / `html-composite` / `html-primary` に分け、`textPolicy`（必要時 `backgroundSource` の `raster` / `svg`）を Layer 2 パターン表と `$CLAUDE_PLUGIN_ROOT/references/style-genome-packaging.md` §4 の値域内で決める。

## 5.5.2 スライド別 plan の言語化スキーマ（プロンプト作成前の必須前提）
各スライドについて、plan を書く前に次の項目と生成条件を必ず言語化してから `image-deck-plan.json`（または単発 plan）へ書く。空欄のまま prompt 作成に進まない。各項目は、100人中100人が同じ目的・場面・構図を理解できる粒度（具体名詞、配置、視認可能属性、禁止事項）で書く。図タイプ別の構図は `$CLAUDE_PLUGIN_ROOT/references/ai-image-diagram-workflow.md` の生成プロンプト仕様（構図プリセット集）を参照し、図タイプに合う `grid` / `zones` / `readingOrder` / `focalPoint` を引く。
- **Purpose**: なぜこの図か（この図が解く課題・伝えたい論点を1文）。
- **AudienceTakeaway**: 聴衆がこのスライドから得る一文（断定表現は避け、得られる理解を中立に書く）。
- **Background**: 場面・前提・前後スライドとの接続・デッキ内役割。単なる「ビジネス背景」ではなく、何の状況を描くかまで書く。
- **Layout**: `grid`（分割構造）/ `zones`（各領域の役割）/ `readingOrder`（視線誘導の順序）/ `focalPoint`（主役の位置）/ `emphasis`（強調点）を言語化する。
- **Accent（支配色）**: `accent` に palette キー名（例 `stepBlue`）/ HEX / `multi` のいずれかを置く。ビルダーが HEX へ解決し「Dominant accent for this slide」行を本文へ展開し `meta.dominantAccentHex` を記録する。60-30-10 の10%主役色を1色に固定する（`multi` は「1ゾーン1アクセント＋1色が60%」）。
- **NegativeSpecific（構造系は必須）**: `camera=structural`（順序/向き/個数が効く図）では `negativeSpecific`（20字以上）を必須で書く。誤ノード数・逆向き・対称崩れなど、間違えてはいけない構成を列挙する（schema と build-image-prompts.js の両方が assert する）。
- **Table（画像内に表を焼く場合）**: `tableMode: illustrated-full-table` + `tableContent`（`headers` / `rows[][]` / `monospaceColumns?` / `caption?`）を言語化する。各セルは短語（14字以内）を verbatim、列数・行数は固定。`textPolicy: baked-with-overlay`、`overlayText` に表全文（全セル）を保持。`illustrated-full-table` も `negativeSpecific` 必須で、表の行数・列数の取り違え禁止（行/列を増減・重複・捏造しない）を毎回宣言する。焼き込み表は `camera=structural`（near top-down）を推奨し、表セルが正対して可読性を上げる。HTMLを画像上のピンポイント位置へ重ねるのは位置ズレするため image-only では使わず、**すべて画像で焼く**。固有名詞・コマンドが14字を超えるセル（例 `dependency-cruiser`=18字）が出る表は焼き込みをやめ `html-overlay-table` へ切り替える。料金/精密数値/長文/複数行コードは `html-overlay-table` / `html-primary` へ回す。
- **StyleReference（再現性・任意）**: デッキ統一のため基準ページ(通常 slide-01)を `styleReference.anchorSlug` に指定する（全ページ共通）。前ページも参照する場合は `refSlugs` に追加(anchor と合わせ16以内)。`inheritMode` は通常 `style-only`（画風のみ継承し主題は差分）。generate-images-codex.js が基準画像を codex exec 指示文へ添付し、seed 非対応の gpt-image-2 でもページ間ドリフトを抑える(画素レベルの決定論アンカー)。
- **Generation（再現条件・必須）**: 密テキスト/図解は `generation.quality: high`、`generation.size: 2560x1440`(両辺16px倍数)。`modelSnapshot` は実行時に使う画像モデルのスナップショットを記録する。meta に記録され再生成時の同条件再現に使う。

これらが言語化済みなら、ビルダー（5.5.3）が決定論で prompt.md へ展開できる。空欄のスライドは prompt 作成に進めない。

## 5.5.3 プロンプト生成（ビルダー連携）と画像生成の不変ルール
- 全面画像生成モードでは per-slide 差分を `vendor/assets/generated/image-deck-plan.json`（`$CLAUDE_PLUGIN_ROOT/schemas/image-deck-plan.schema.json` 準拠）にまとめ、`node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/build-image-prompts.js" <slide-dir>` で `image-deck-plan.json` + `vendor/assets/generated/style-genome.json` から `slide-NN-{slug}.prompt.md` / `slide-NN-{slug}.meta.json` を機械生成する。STYLE BIBLE preamble（プレースホルダ `{{STYLE_BIBLE}}`）は手動展開せず、ビルダーが決定論で展開する。`--check` で既存との差分のみ確認、`--only slide-06,...` で部分再生成できる。単発差し替えでテンプレートを直接書く場合のみ `$CLAUDE_PLUGIN_ROOT/vendor/assets/ai-image-diagram-prompt-template.md` を参照仕様として使う（`$CLAUDE_PLUGIN_ROOT/references/style-genome-packaging.md` §3.1 のビルダー連携）。
- 画像生成は `node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/generate-images-codex.js" <slide-dir>` 経由で行う。各 `slide-NN-{slug}.prompt.md` を読み、codex exec（内部で gpt-image-2 を使用・CONST_004 を満たす確認済み生成系）へ画像生成を依頼するコマンドを組み立てる（`--dry-run` でコマンド確認のみ・コスト無し、既定バッチ5）。**imagegen（text-to-image 拡散モデル）の使用を明示強制する文言が必須**で、指示が弱いと codex はコード（PIL / matplotlib / SVG）でプログラム描画し平坦な角丸ボックス図に退化する（パイロット実証）。この強制文言（imagegen 使用・コード描画禁止・リッチなアイソメイラスト維持）を本スクリプトが担保するため、手書き codex exec ではなく必ず本スクリプト経由で呼ぶ。生成後は cwebp で WebP 化する。`meta.source` は実体名 `codex-image2` を記録し、plain `codex` 単体は記録しない（CONST_004 維持）。
- テキストオーバーレイ: `overlay-only` は日本語ラベル・重要テキストを画像内に焼き込まず HTML/SVG で重ねる。`baked-with-overlay` は短い説明文・吹き出し・簡易表だけ画像内に許可し、正テキストを `overlayText` に必ず保存する（prompt/meta/structure.md に同値・Layer 2 パターン表の `textPolicy` 定義）。
- 一貫性評価: `node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/evaluate-image-consistency.js" <slide-dir> --threshold 0.8` で生成画像群の一貫性（genome の lockTiers.tier1 + consistencyAnchors を rubric 化）を LLM-judge 採点し、閾値割れページの再生成推奨を得る（破壊操作なし・目視の前段ゲート）。曖昧語・generation・styleReference を厳格化するには `--strict-intent` を付ける。機械検証は `validate-ai-image-assets.js`（全面時は `--full-image-deck --strict-style-genome`）、切れ・重なり・印刷崩れは `verify-slides.js` と目視で確認し、品質基準は `$CLAUDE_PLUGIN_ROOT/references/design-quality-guide.md` の検証4条件に従う。

## 5.5.4 プロンプト作成ルール（必須要素）
画像生成プロンプトには必ず以下を含める。最新の画像生成モデルは gpt-image-2（Codex CLI の `$imagegen` / codex exec が内部使用）であり、下記の再現性の原則に従って記述する。

- スライドの Purpose（なぜこの図か）、AudienceTakeaway（聴衆が得る一文）、Background（場面・前提・前後スライド接続）
- レイアウト: `grid` / `zones` / `readingOrder` / `focalPoint` / `emphasis`（5.5.2 で言語化済みの値）
- 用途宣言: `intendedUse`（presentation infographic / explanatory diagram など）
- 生成条件: `generation.modelSnapshot` / `generation.quality` / `generation.size`
- 画面比率: 16:9 または配置先に合わせた透明背景カットアウト
- スタイル: Kanagawaテーマ、余白、光源、質感、背景の複雑度
- スタイルゲノム: `styleName`、参照画像、パレット、反復モチーフ、カメラ角
- 生成パターン: `pattern`
- テキスト方針: `textPolicy`
- 禁止事項: 画像内テキスト、ロゴ、透かし、読めないUI文字、過度な装飾
- 合成方針: HTMLで重ねる見出し・ラベルのための余白
- 出力: PNG元画像 + WebP変換後ファイル。`meta.source` には実際に使ったバックエンド名を記録し、`codex` 単体を画像生成器として記録しない

### gpt-image-2 再現性の原則（必須遵守）
- **(a) 具体記述・曖昧語禁止**: `beautiful` / `きれい` / `high quality` などの曖昧語を禁止し、具体名詞 + 視認可能な属性（色・形・配置・質感・カメラ角）で記述する。
- **(b) 1スライド1主役**: `focalPoint` に置く主役を1つに絞り、複数主役で構図を割らない。
- **(c) 再生成は1変数ずつ**: 再生成時は一度に1変数だけ変える。最重要ディテールは毎回逐語で再記述し、世代間ドリフトを防ぐ。
- **(d) 単一セッション量産**: 可能ならデッキ全画像を単一セッションで生成し、画風の一貫性を保つ（`generate-images-codex.js` のバッチ生成を活用）。
- **(e) 画像内日本語ラベルは短語・逐語**: 画像内に日本語ラベルを置く場合（`baked-with-overlay`）は引用符付き + verbatim + 1〜4語の短語に限定し、長文は HTML 前面に置く。生成後は目視校正を必須とする。
- **(f) seed 非対応・参照画像チェーン**: gpt-image-2 は seed パラメータを持たない。再現性はプロンプト不変(STYLE LOCK / lockTiers)＋参照画像チェーン(`styleReference`)＋一貫性評価(`evaluate-image-consistency.js`)で担保する。seed の固定・記録はしない。複数ページの全面画像デッキでは `styleReference.anchorSlug`（通常 `slide-01`）を全ページ共通で付け、anchor ページを先に生成する（未設定だと `validate-ai-image-assets.js --full-image-deck` が WARN を出す）。
- **(g) 支配色の明示**: `accent` を palette キー / HEX / `multi` で指定する。ビルダーが「Dominant accent for this slide」行へ HEX 展開し、60-30-10 の主役色を1色に固定する。validator は `meta.dominantAccentHex` と prompt 本文の支配色宣言を意味照合する（`--strict-intent` / `--full-image-deck` で error）。
- **(h) 構造系の負制約**: `camera=structural` のスライドは `negativeSpecific`（20字以上）で誤ノード数・逆向き・対称崩れを禁止列挙する（schema・builder の両方が必須化）。
- **(i) 焼き込みテーブル**: 表は画像内に焼く（`illustrated-full-table` + `tableContent`）。HTMLを画像上へピンポイント重ねするのは位置ズレするため image-only では使わない。各セルは verbatim・短語（14字以内・最大5列×6行）、コマンド列は monospace、`generation.quality: high` で再現性を上げる。`negativeSpecific` 必須で表の行数・列数の取り違え禁止を毎回宣言し、`camera=structural`（near top-down）を推奨して表セルを正対させる。表セルは bakedText の18字制限とは別経路（`tableContent`・14字以内）。固有名詞・コマンドが14字を超えるセル（例 `dependency-cruiser`=18字）が出る表は焼き込みをやめ `html-overlay-table` へ切り替える。崩れたら `overlayText` の HTML 表へ fallback。料金/精密数値/長文/複数行コードは `html-overlay-table` / `html-primary` へ。

テンプレートは `$CLAUDE_PLUGIN_ROOT/vendor/assets/ai-image-diagram-prompt-template.md` を優先して使用する。最小テンプレート:

```markdown
Create a premium presentation diagram image for slide {{slide_no}}.
Purpose: {{one_message}}.
Visual: {{scene_or_diagram_description}}.
Style: clean Apple-like editorial design, Kanagawa-inspired palette, vivid but restrained accents, soft depth, high contrast, professional consulting deck.
Composition: 16:9, leave clear negative space at {{overlay_area}} for HTML text overlays.
Text policy: {{overlay-only / baked-with-overlay}}.
Do not include logos, watermarks, UI gibberish, or brand marks in the image.
Output should work as a slide visual asset and remain clear when printed.
```

`overlay-only` の場合は `Do not include readable text, letters, words, numbers, labels.` を追加する。`baked-with-overlay` の場合は、短い指定文言だけ許可し、`distorted text, garbled characters` を Negative に残す。

## 5.5.5 HTML組み込みルール
```html
<picture class="ai-visual">
  <source srcset="vendor/assets/generated/slide-XX-name.webp" type="image/webp">
  <img src="vendor/assets/generated/slide-XX-name.png" alt="{{意味が伝わる説明}}">
</picture>
```

- `alt` は装飾画像なら空、意味を持つ図解なら要約を書く
- 画像の上に重ねるテキストは `.visual-overlay` などで HTML 管理する
- 印刷時も切れないよう `object-fit: contain` を基本にする
- 背景全面で使う場合のみ `object-fit: cover` を許可し、主要被写体の切れを目視確認する
