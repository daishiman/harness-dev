# 構造化データテンプレート（structure.md）

スライド生成時に出力する構造化データのテンプレート。
**index.htmlと完全同期**を維持し、HTML/CSS/JS生成の基礎情報として使用する。

---

## テンプレート

以下の形式でstructure.mdを出力する。{{変数}}は実際の値に置き換える。

---

### ヘッダー

```markdown
## プレゼン構成案

**タイトル**: {{タイトル}}
**総スライド数**: {{N}}枚
**アイコンライブラリ**: FontAwesome 6 Free
**テーマ**: Kanagawa Light
**共通仕様**: コードブロックはスクロール表示（max-height: 420px, overflow-y: auto）、SVGはインライン描画
```

---

### 共通SVG設計仕様セクション

プレゼン内で使うSVG図解の共通パラメータを定義する。
HTML生成時にこの値を参照して正確に描画する。

必須記載項目:
- **基準値**: 標準viewBox幅、日本語テキストのfont-size算出ルール、CSS変数一覧
- **比較スライド（左右対比）**: viewBox、カードサイズ、有効テキスト幅、文字数制限、配置座標
- **横フロー（3-4ステップ）**: viewBox、ステップカードサイズ、矢印仕様、配置座標
- **サイクル図（4ノード循環）**: viewBox、ノードサイズ、中心座標、各ノード座標
- **縦フロー（4-5ステップ）**: viewBox、ステップサイズ、配置座標、矢印仕様
- **プレゼン固有のSVG図**: そのプレゼン特有のSVG図解のパラメータ

テンプレート:
```
#### 基準値
- 標準viewBox幅: 860px
- 日本語テキスト: font-size x 1.0 per character（全角基準）
- CSS変数 (vw 単位 / unit-system.md §3.1): fs-title(2.81vw〜6.25vw), fs-subheading(1.56vw〜2.50vw), fs-body(1.25vw〜1.88vw=24.1px@1280), fs-small(1.09vw〜1.75vw=22.4px@1280)

#### 比較スライド（左右対比）
- viewBox: "0 0 860 400"
- 左右カード: 幅360px, 高さ300px, rx=16, padding=24px
- 有効テキスト幅: 312px
- fs-body: 1行最大12文字 / fs-small: 1行最大13文字
- カード配置: 左x=30, 右x=470, y=50
- タイトル: カード上部、fs-body太字
- リスト: 各行にアイコン+テキスト、行間32px

#### 横フロー（3-4ステップ）
- viewBox: "0 0 860 300"
- ステップカード: 幅200px, 高さ130px, rx=12, padding=16px
- 有効テキスト幅: 168px → fs-small: 1行最大7文字
- 矢印: 幅24px, stroke-width=2, marker-end
- 3ステップ配置: x=60, x=330, x=600
- 4ステップ配置: x=20, x=230, x=440, x=650

#### サイクル図（4ノード循環）
- viewBox: "0 0 860 400"
- ノード: 幅200px, 高さ80px, rx=40
- 中心: (430, 200)
- 各ノード座標: 上=(315,40), 右=(590,160), 下=(315,280), 左=(40,160)
- 有効テキスト幅: 160px → fs-small: 1行最大7文字、2行推奨
- 矢印: curved path, stroke-width=2

#### 縦フロー（4-5ステップ）
- viewBox: "0 0 860 440"
- ステップ: 幅480px(中央揃え), 高さ56px, rx=8
- 配置: x=190, gap=12px
- 矢印: 中央垂直線(x=430) + marker-end
- テキスト: 左にナンバー丸, 右にテキスト, fs-small

#### {{プレゼン固有SVG図名}}
- （プレゼン固有のSVGパラメータをここに記載）
```

---

### A4横配置・印刷品質保証仕様セクション

画面表示とA4印刷で完全一致を保証する仕様。

必須記載項目:
- スライドサイズ（A4横 297mm x 210mm）
- 画面＝印刷 完全一致ルール（単位はvw/vh/% 推奨（rem は段階移行期のみ許容、px禁止、mm は @page 定義のみ））
- 印刷CSS（@page設定、page-break設定）
- ナビゲーション要素の印刷時非表示
- コードブロックの印刷時処理（overflow: visible）

---

### スライドタイプ定義セクション（重要）

このプレゼンで使用するスライドタイプとCSSクラスの対応を定義する。
HTML生成時はこのマッピングに従ってクラスを付与する。

テンプレート:
```
### スライドタイプ定義

| タイプ名 | CSSクラス | 用途 |
|---------|-----------|------|
| タイトル | .slide-title | 冒頭タイトル |
| ヒーロー | .slide-hero | キーメッセージ強調 |
| メッセージ | .slide-message | 単一メッセージ |
| 引用 | .slide-quote | 講師の言葉・引用文 |
| 比較 | .slide-compare | Before/After、対比 |
| フロー | .slide-flow | 横方向プロセス |
| サイクル | .slide-cycle | 循環プロセス |
| 縦フロー | .slide-vertical-flow | 縦方向プロセス |
| タイムライン | .slide-timeline | 時系列表示 |
| 図解 | .slide-diagram | SVG図解全般 |
| コード | .slide-code | プロンプト/コード表示 |
| コード比較 | .slide-code-compare | Before/Afterコード |
| リスト | .slide-list | 箇条書き・列挙 |
| アイコングリッド | .slide-icon-grid | アイコン付きグリッド |
```

---

### コードブロック共通仕様セクション

コードブロックを含むスライドの共通スタイル。

テンプレート:
```
#### コードブロック共通仕様
- max-height: 420px
- overflow-y: auto
- background: var(--code-bg) with 0.03 opacity border
- border-radius: 12px
- padding: 20px 24px
- font-family: 'SF Mono', 'Fira Code', monospace
- font-size: 1.75vw
- line-height: 1.7
- ヘッダー行(#): accent-blue, 太字
- 変数({変数}): accent-yellow ハイライト

#### Before/After コードブロックレイアウト
- 2カラム: 左48% / 右48% / gap 4%
- 各カラムmax-height: 280px
- ヘッダー: Before=accent-pink背景、After=accent-aqua背景
- ラベル: 上部にBefore/Afterラベル（fs-small, 太字）
```

---

### GSAPアニメーション共通仕様セクション

テンプレート:
```
#### GSAPアニメーション共通設定
- デフォルト: duration=0.6, stagger=0.15, ease="power2.out"
- 個別スライドでオーバーライド可能
- enter: 画面内に登場するアニメーション
- leave: 画面外に退場するアニメーション
```

---

### フォント仕様セクション

テンプレート:
```
#### フォント仕様
- 本文: 'Noto Sans JP', sans-serif (400, 700)
- コード: 'SF Mono', 'Fira Code', monospace
- Google Fonts CDN: https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap
```

---

### 補足テキスト表示ルールセクション

テンプレート:
```
#### 補足テキスト表示ルール
- 最大3行
- font-size: fs-small (1.75vw)
- opacity: 0.7
- 20文字を超える場合は明示的に<br>で改行
```

---

### アクセントカラー統一ルールセクション

テンプレート:
```
#### アクセントカラー統一ルール
- 主要/正解: accent-blue or accent-aqua
- 警告/NG例: accent-pink
- 強調/変数: accent-yellow
- 補助: accent-violet
```

---

### セクション目次ナビゲーション仕様セクション

画面上部に常時表示されるセクション目次。現在位置をハイライトし、クリックでジャンプ可能。

テンプレート:
```
#### セクション目次ナビゲーション
- 要素: <nav class="section-nav">（横並びタブ、画面上部固定）
- 背景: 半透明ブラー rgba(250,250,250,0.92) + backdrop-filter: blur(0.63vw)
- 下部ボーダー: 1px solid var(--sumi-ink)
- 各セクション: <button class="section-nav__item">
  - 内容: カラードット(0.63vw丸) + セクション名 + 下部バー(3px)
  - 非アクティブ: opacity 0.5、バー非表示
  - アクティブ: opacity 1、バーにセクション対応アクセント色
  - hover: opacity 0.8、背景 var(--bg-dim)
  - focus-visible: 2px solid var(--accent-blue-vivid)
- セクション定義:
  | セクション | ラベル | アクセント色 | data-first-slide |
  |-----------|--------|-------------|-----------------|
  | opening | オープニング | accent-blue | 0 |
  | lecture | 講義 | accent-aqua | {{先頭スライドindex}} |
  | demo | デモ | accent-yellow | {{先頭スライドindex}} |
  | ws | ワークショップ | accent-violet | {{先頭スライドindex}} |
  | summary | まとめ | accent-pink | {{先頭スライドindex}} |
- クリック: 該当セクション先頭スライドへジャンプ（goTo）
- 自動更新: スライド遷移時に現在セクションの.activeを切替
- 印刷時: display: none
```

---

### ページネーション仕様セクション

画面下部のドットナビゲーション。

テンプレート:
```
#### ページネーション
- 位置: 画面下部中央（fixed, bottom, 50%）
- 形状: 各スライドに対応するドット（0.75vw丸）
- 非アクティブ: var(--sumi-ink) 背景
- アクティブ: セクション対応アクセント色 + scale(1.4)
- セクション色: opening=blue, lecture=aqua, demo=yellow, ws=violet, summary=pink
- 5個ごとに右マージン追加（視覚的グルーピング）
- クリックで該当スライドへジャンプ
- 印刷時は非表示
```

---

### スライド一覧テーブル

```
| No | タイプ | CSSクラス | メッセージ | アイコン | アニメーション |
|----|--------|-----------|-----------|----------|---------------|
| 1 | {{タイプ}} | .slide-{{type}} | {{メッセージ}} | {{fa-xxx}} | {{アニメーション概要}} |
```

---

### 各スライド詳細

各スライドの詳細を以下の形式で記載:

```
#### スライド{{N}}: {{タイプ}}（.slide-{{type}}）
- **メッセージ**: {{メッセージ}}
- **アイコン**: {{fa-xxx}}
- **アニメーション**: {{enter: ..., leave: ...}}
- **構成**:
  {{レイアウト構造の説明}}
- **テキスト内容**:
  {{実際のテキスト。改行位置は<br>で明示}}
- **補足テキスト**: {{あれば記載、最大3行、opacity:0.7}}
- **SVG設計メモ**:（SVG図解スライドの場合のみ）
  - viewBox: "0 0 {{W}} {{H}}"
  - レイアウト: {{配置説明}}
  - テキスト文字数検証: {{検証結果}}
- **コードブロック内容**:（コードスライドの場合のみ）
  ```
  {{コードの全文}}
  ```
- **Before/After**:（コード比較スライドの場合のみ）
  - Before: {{改善前コード}}
  - After: {{改善後コード}}
  - 差分ポイント: {{何が変わったか}}
```

---

### 形式振り分けテンプレート（部分AI画像化時）

部分AI画像化（バランス型）を行う場合、全スライドを一律にAI画像化せず、スライドごとに表現形式と画像の役割を振り分ける。以下の表で各スライドの方針を一覧管理する。

テンプレート:
```
#### 形式振り分け一覧

| No | タイプ | 形式 | 画像の役割 | 備考 |
|----|--------|------|-----------|------|
| 1 | {{タイプ}} | イラスト主役 | 背景フル | {{章扉・表紙など}} |
| 2 | {{タイプ}} | HTML主役 | なし | {{SVG図解・コードなど}} |
| 3 | {{タイプ}} | ハイブリッド | 背景アクセント | {{図解+画像の併用}} |
| 4 | {{タイプ}} | HTML主役 | 背景地 | {{淡い地としての画像}} |
| 5 | slide-code / slide-code-compare | HTML主役 | コードは画像なし（実HTMLコードブロック） | {{コード専用ページ・画像化しない}} |
```

形式の定義:
- **イラスト主役**: AI生成画像が主表現。HTMLはタイトル/ラベルのみ上乗せ。
- **HTML主役**: 既存のHTML/CSS/SVGが主表現。AI画像は使わない、または微弱な背景地のみ。
- **ハイブリッド**: HTML図解とAI画像を併用。図解の可読性を最優先し、画像は補助。

画像の役割の定義:
- **背景フル**: スライド全面をAI画像が占める（章扉・表紙向け）。
- **背景地**: 淡く敷くだけの地。テキスト可読性を阻害しない低コントラスト。
- **背景アクセント**: 一部領域のみ画像。残りはHTML。
- **なし**: AI画像を使用しない。

振り分け原則:
- 情報密度が高いスライド（図解・コード・比較）は HTML主役 を基本とする。
- コード系 slideType（slide-code / slide-code-compare）は常に コードは画像なし（実HTMLコードブロック）。image-only / 全面AI画像化デッキでもコードは画像化しない（コード専用ページ）。世界観背景が要る場合のみ html-composite + backgroundSource: svg + overlay-only。
- 章扉・表紙・キーメッセージは イラスト主役 を許容する。
- 迷う場合は HTML主役 に倒し、画像は背景地に留める（可読性優先）。

---

### STYLE BIBLE 雛形（部分AI画像化・正本）

部分AI画像化時のアートスタイルの正本。全画像プロンプトはこの STYLE BIBLE をプリアンブルとして参照し、per-slide では差分のみを記述する。{{変数}}は実際の値に置き換える。

テンプレート:
```
#### STYLE BIBLE（正本）

##### アートスタイル固定値
- 視点: アイソメトリック 30度トップダウン
- 質感: 可愛いアイコン風フラットイラスト
- 人物: なし（人物・顔・手を一切描かない）
- 形状: 角丸ジオメトリック
- 影: ソフトな単一影
- 基調: 白基調（明るく余白を広く取る）

##### 画像用パレット
- テーマのアクセント色から HEX 1系統を固定: {{accent_hex}}（例: #4C7CF3）
- 補助は同系統の濃淡のみ。多色化しない。
- 背景は白〜極淡グレー。高彩度・全面グラデーション禁止。

##### 反復モチーフ集（人物なし・同名同描写）
- {{motif_1}}: {{同一の描写ルール}}（全スライドで同名・同形・同色）
- {{motif_2}}: {{同一の描写ルール}}
- {{motif_3}}: {{同一の描写ルール}}
- 注: 同じ概念は必ず同じモチーフ・同じ呼称で描く（再現性のため）。

##### 構図・カメラ
- 章扉: アイソメ 30度（俯瞰）
- 構造系（フロー・サイクル・比較）: 微俯瞰 15度
- 被写体はセーフマージン内に収める。

##### 画像内テキスト（完全非焼き込み）
- 画像にテキスト・文字・数字・ラベル・タイポグラフィを一切焼き込まない。
- スライド上の文言は HTML の overlayText が正（画像はビジュアルのみ）。

##### 共通サフィックス＋ネガティブ
- 共通サフィックス: {{common_suffix}}（例: clean editorial consulting style, airy negative space）
- ネガティブ: people, humans, figures, faces, hands, photorealistic, 3d render, baked text, letters, words, numbers, captions, labels, typography, emoji

##### 再現性
- 基準seed: {{base_seed}}
- 表紙画像を style reference として後続スライドに適用
- 命名規則: slide-NN-{{slug}}（PNG/WebP/prompt/meta で共通）
```

---

### kanagawa-comic-diagram スタイルゲノム（assets/generated画像群の再現）

`05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` に含まれている画像群に近い漫画チック図解を量産する場合は、以下を structure.md の共通仕様に含める。

テンプレート:
```
#### 使用スタイルゲノム
- 運用モード: {{通常差し替え / 部分AI画像化 / 全面画像生成}}
- 全面画像生成の場合: 生成画像は背景ではなく各ページの主キャンバス。HTMLは正テキストfallback・コード・QR/ロゴ・ページUIの正確性レイヤ
- preset: kanagawa-comic-diagram
- styleGenome: assets/generated/style-genome.json（同梱プリセットをコピーした project-local 正本）
- presetOrigin: assets/style-genome-kanagawa-comic-diagram.json（コピー元の同梱プリセット）
- 再現対象: slide-2026-06-13-skill-mass-production/assets/generated/ の画像群
- 主要特徴: 白〜オフホワイト背景、薄いアイソメドットグリッド床、角丸アイソメタイル、濃紺太字見出し、吹き出しラベル、青白い発光フロー矢印、Kanagawa淡色パレット
- 量産パターン:
  - Pattern A: image-only + baked-with-overlay + backgroundSource=none（漫画チック図解の中に短い説明文・吹き出し・簡易表を入れる）
  - Pattern B（raster）: html-composite + overlay-only + backgroundSource=raster（画像は背景/モチーフ、正確な説明文・表・数値はHTML）
  - Pattern B（svg）: html-composite + overlay-only + backgroundSource=svg（AI画像なし。SVG2/CSS で背景レイヤを構築）
  - 退避先: html-primary + textPolicy=none + backgroundSource=none|svg（正確な表・料金・数値が主役のとき画像を使わない）
- per-slide meta 必須キー: slide / asset / source（実際に使った text-to-image バックエンド） / decision / reason / alt / pattern / textPolicy / backgroundSource / styleGenome / prompt（`--strict-style-genome` validator 整合）
- 正本ルール: 画像内に説明文を入れる場合でも overlayText が正テキスト。崩れたらHTML overlayへ切替
- 検証: 全面画像生成では `node scripts/validate-ai-image-assets.js <slide-dir> --full-image-deck --strict-style-genome` を必須実行
```

---

### per-slide 画像ブロック雛形

部分AI画像化を行うスライドごとに、以下のブロックを各スライド詳細に併記する。STYLE BIBLE を前提とし、ここには差分のみを記述する。{{変数}}は実際の値に置き換える。

注記: コード系 slideType（slide-code / slide-code-compare）の場合は画像ブロック（aiVisual）を作らず、コードブロック内容のみ記述する（コード専用ページ）。世界観背景が要る場合のみ html-composite + backgroundSource: svg + overlay-only。

テンプレート:
```
##### 画像ブロック（スライド{{N}}）
- slug: {{slug}}
- pattern: {{image-only / html-composite / html-primary}}
- textPolicy: {{baked-with-overlay / overlay-only / none}}
- backgroundSource: {{raster / svg / none}}（html-composite で AI画像背景なら raster、SVG/CSS背景なら svg、背景なしは none）
- decision: {{generate-image / use-svg-background / html-only}}
- source: {{実際に使った text-to-image バックエンド。画像生成なしの場合は svg-css / html-css}}
- reason: {{この形式・パターンを選んだ理由}}
- styleGenome: assets/generated/style-genome.json
- 形式: {{イラスト主役 / HTML主役 / ハイブリッド}}
- 画像の役割: {{背景フル / 背景地 / 背景アクセント / なし}}
- 被写体（人物なし）: {{描く対象。STYLE BIBLEのモチーフ名を流用}}
- 図解プリミティブ: {{rounded-isometric-platform / glowing-flow-arrow / speech-label / explanation-panel / mini-table-panel / tool-workbench / quality-gate / notion-card-stack の実在 motif 名の部分集合のみ}}
- 構図・カメラ角: {{30度俯瞰 / 微俯瞰15度 など}}
- accent: {{accent_hex}}
- pngパス: assets/generated/slide-{{NN}}-{{slug}}.png（backgroundSource=svg / pattern=html-primary は持たない）
- webpパス: assets/generated/slide-{{NN}}-{{slug}}.webp（backgroundSource=svg / pattern=html-primary は持たない）
- alt: {{画像の内容説明（人物なし前提）}}
- overlayText: {{HTMLで上乗せする正本テキスト。改行は<br>で明示}}
- bakedText: {{textPolicy=baked-with-overlay の場合のみ。画像内に入れる短い文言}}
- promptパス: assets/generated/slide-{{NN}}-{{slug}}.prompt.md
- metaパス: assets/generated/slide-{{NN}}-{{slug}}.meta.json（pattern/textPolicy/backgroundSource/styleGenome/prompt を必ず含める）
- hybrid例外: {{ハイブリッド時のみ。画像領域とHTML領域の分担を記述}}
- 印刷代替: {{印刷時に画像をどう扱うか。背景地は低コントラスト維持、なしの場合は省略}}
```

---

## フォーマット設計原則

1. **HTML生成の入力として機能する**: structure.mdの情報だけで、正確なHTML/CSS/JSを生成できる粒度
2. **共通仕様は1箇所で定義**: SVG座標、印刷仕様、フォント等はヘッダー部で一度だけ定義
3. **スライドタイプ→CSSクラス対応を明示**: 各スライドにCSSクラスを指定し、HTML生成時の曖昧さを排除
4. **テキスト改行位置を明示**: <br>で改行を制御し、ブラウザ依存を排除
5. **SVG座標は全て数値で記載**: viewBox、配置座標、サイズを明示し、再現性を保証
