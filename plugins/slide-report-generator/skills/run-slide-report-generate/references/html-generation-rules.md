# HTML生成規約（html-generator 手続き知識 SSOT）

> **正本**: このファイルは html-generator から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/html-generator.md）の双方がこれを参照する。規則の上位正本 (SR-ID) は spec-registry.md を辿る。

**責務**: slide HTML 生成のドメイン定義（用語集・precheck-layout 判定基準・制約カタログ CONST_001-038）と生成規約（§5.6: 16:9／整合性維持／部分AI画像化／意図的改行／スライドタイプ別問題／HTML生成仕様／PDF出力／操作方法・全コード例）の逐語正本。html-generator（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| 分離形式 | index.html + styles.css + scripts.js の3ファイル構成。インラインCSS/JS禁止 | CONST_002 |
| Kanagawaテーマ | ライトモード既定のカラーパレット（`--bg-dark:#FFFFFF` / `--fg:#2D2D2D`）。CSS変数で統一 | CONST_037 / theme-style.md |
| slide-area | 16:9を強制するコンテナ。`.slider` 内に置き JS の幅計算基準とする | CONST_001 |
| SVG2図解 | サイクル・フロー・ファネル・ベン図等をインラインSVG2で描画。CSS absolute配置禁止 | CONST_004 / svg-diagram-primitives.md |
| code-block / code-compare-body | コードを画像化せず実HTMLで前面描画するコードブロック要素 | CONST_020 / CONST_024 |
| fo-card | foreignObject 内 div に付与し clearProps から保護する CSS クラス | CONST_010 |
| AI画像図解候補 | `data-ai-image-candidate="true"` でマークし ai-image-diagram-producer へ引き継ぐスライド | CONST_028 |
| SR-ID | spec-registry.md のレイアウト計算根拠ID（SR-1 / SR-3 / SR-4） | precheck-layout |

## 評価基準（ドメイン固有の判定基準）

precheck-layout の判定としきい値:

| 判定 | 終了コード | しきい値 | 対応 |
|------|-----------|----------|------|
| PASS | 0 | 高さ使用率 < 85% | Phase 3（HTML生成）に進む |
| WARN | 2 | 85% ≦ 使用率 ≦ 95% | 該当スライドIDをユーザーに提示し、承認を得てから Phase 3 に進む |
| FAIL | 1 | 使用率 > 95% または個別カードでオーバーフロー検出 | HTMLを生成しない。structure-designer に差し戻し、改善提案に従って structure を修正してから再 precheck |

計算根拠: `$CLAUDE_PLUGIN_ROOT/references/spec-registry.md` SR-1 / SR-3 / SR-4 および `$CLAUDE_PLUGIN_ROOT/references/unit-system.md` の vw 換算を使用。

決定論仕様の主要数値:

| 項目 | 値 |
|------|-----|
| アスペクト比 | 16:9 固定（`.slide-area` / `.slider__item` に `aspect-ratio: 16/9`） |
| コードブロック max-height | 420px 固定（340px禁止）、`overflow-y:auto` |
| SVGテキスト最小フォントサイズ | 13px以上（12pxは小バッジ・角の補助ラベルのみ、11px以下禁止） |
| ページネーション区切り | `nth-child(5n)` で accent-aqua色・0.7remサイズ・margin-right:0.5rem |
| GSAP scale 最小値 | 0.8（scale:0 / scale:0.5 等の極端値禁止。x/y移動で代替） |
| clearProps 適用範囲 | `content.children` のみに `clearProps:'all'`（`querySelectorAll('*')` 禁止） |

## ビジネスルール

各制約に CONST_NNN を付番し、目的（防ぐ事象）と背景（採用根拠）を併記する。

### レイアウト・出力形式

- **CONST_001 (16:9アスペクト比)**: 全スライドを 16:9 で固定（最重要）。
  - 目的: 表示環境・印刷で構図が崩れない一貫レイアウトを保証
  - 背景: プレゼンは大画面投影が前提で、比率が崩れると意図した余白・視覚階層が破綻する
- **CONST_002 (分離形式)**: index.html + styles.css + scripts.js の3ファイル構成。インラインCSS/JS禁止。GASデプロイ時のみビルドスクリプトで1ファイル化。
  - 目的: 関心の分離による保守性確保と、structure.md からの再生成を容易にする
  - 背景: インライン混在は差分追跡・部分修正を困難にし、UI品質レビューの修正が当てにくくなる
- **CONST_003 (レスポンシブ)**: 16:9を維持しつつビューポートに追従させる。
  - 目的: 画面サイズが変わっても比率と可読性を保つ
  - 背景: 投影環境・ブラウザ幅は不定で、固定px前提だと環境差で破綻する

### SVG図解

- **CONST_004 (SVG2図解必須)**: サイクル・フロー・ファネル・ベン図・マインドマップ・フローチャート・成長曲線はインラインSVG2で描画。CSS absolute配置での図作成は禁止。$CLAUDE_PLUGIN_ROOT/references/svg-diagram-primitives.md のパーツを使用。
  - 目的: 拡縮で劣化せず、テーマ連携・印刷で正確に再現できる図解を保証
  - 背景: CSS absolute の図は要素ずれ・印刷崩れ・スケール非追従が起きやすい
- **CONST_005 (SVGテーマ連携)**: SVGの fill/stroke に CSS変数を使用（例 `fill="var(--wave-blue,#7E9CD8)"`）。カラーコード直書き禁止。
  - 目的: テーマ変更時に図の色を一括追従させる
  - 背景: 直書きはテーマ切替時に色が取り残され、Kanagawa統一が崩れる
- **CONST_006 (SVGテキスト最小13px)**: SVG `<text>` の font-size は13px以上。12pxは小バッジ・角の補助ラベルのみ許容、11px以下禁止。
  - 目的: 対面プレゼンの大画面でテキストが視認可能な下限を担保
  - 背景: 11px以下は投影時に不可視となり情報が伝わらない実害があった
- **CONST_007 (SVG内FA unicode禁止)**: `&#xf...;` 形式の Font Awesome PUAコードを SVG `<text>` 内で使用しない。foreignObject + `<i class="fa-solid ...">` + `class="fo-card"`、または Unicode emoji を使用。
  - 目的: CDN未ロード時にアイコンが全消失する事故を防ぐ
  - 背景: SVG text 内 PUA はフォント未ロード時に描画されず、図の意味が欠落する
- **CONST_008 (共通SVG仕様準拠)**: structure.md の共通SVG設計仕様に記載された viewBox・座標・サイズを厳密に使用。
  - 目的: structure.md と index.html の図解整合性を維持
  - 背景: 座標が乖離すると再生成・修正時に図が破綻する

### アニメーション・GSAP安全

- **CONST_009 (GSAP scale:0 禁止)**: from アニメーションで scale:0 や scale:0.5 等の極端値を禁止。最小 scale:0.8。代替は x:-30, y:30 等の移動アニメーション。
  - 目的: 初期フレームでの不可視・ガクつき・レイアウト計算崩れを防ぐ
  - 背景: scale:0 起点は SVG/テキストの初期描画でちらつき・寸法ゼロ問題を起こす
- **CONST_010 (clearProps安全適用必須)**: updateSlide() と leaveAnimation() の onComplete 両方で `content.children` のみに `clearProps:'all'` を適用。`content.querySelectorAll('*')` は禁止。foreignObject内 div は `class="fo-card"` で CSS クラスベースのレイアウトを適用し clearProps から保護。
  - 目的: SVG の fill/stroke 属性と foreignObject 内レイアウトの破壊を防ぐ
  - 背景: 全要素 clearProps は SVG 色属性・内部レイアウトを消し、図が無色化・崩壊した事例がある
- **CONST_011 (prefers-reduced-motion対応)**: D/S 倍率変数で duration/stagger を制御し、reduced-motion を尊重。
  - 目的: モーション過敏ユーザーへのアクセシビリティ確保
  - 背景: 強制アニメーションは健康影響・WCAG 非準拠となる
- **CONST_012 (イージング多様性)**: GSAP ease を3種以上（power2.out / back.out / power1.inOut 等）使い分ける。単一easeの繰り返し禁止。
  - 目的: 単調さを避け、動きにリズムと意味の差をつける
  - 背景: 単一easeは機械的で、デザイン品質基準を満たさない
- **CONST_013 (アニメーション必須)**: 全スライドに enter/leave アニメーションを定義。
  - 目的: スライド遷移の連続性と注意誘導を保証
  - 背景: 無アニメーションのスライドは唐突な切替で文脈が途切れる

### 印刷・PDF

- **CONST_014 (印刷CSS GSAPスタイルリセット)**: @media print 内で `.slider__content`, `.slider__content > *`, `.slider__content *` に `visibility:visible!important; opacity:1!important; transform:none!important` を強制適用。
  - 目的: GSAP が残した非表示・変形状態を印刷時にリセットし全要素を表示
  - 背景: アニメ途中状態のまま印刷すると要素が消える・ずれる
- **CONST_015 (印刷レイアウト=画面同一)**: @media print は画面と同じ grid/flex 構造を維持。データ系は align-items:stretch で全幅。A4横フルサイズ（@page margin:0、border:none）。
  - 目的: 画面と印刷で同一構図を維持し、PDF版の見た目一貫性を保つ
  - 背景: 印刷専用に組み直すと画面と乖離し、配布資料の品質が落ちる
- **CONST_016 (印刷カード比率=画面同一)**: 印刷CSSの padding・font-size・gap・border-radius を画面CSSと同比率で維持。画面の50%以下に縮小禁止。具体基準: カードpadding≧5mm、本文フォント≧10pt、gap≧3mm、border-radius≧3mm。
  - 目的: 印刷で要素が過度に縮小され可読性・余白バランスが崩れるのを防ぐ
  - 背景: 印刷時の自動縮小でカードが潰れ、配布資料が読めなくなる事例があった
- **CONST_017 (印刷カード影=全要素強制オフ)**: @media print 先頭に `* { box-shadow: none !important; }` を必ず入れ、全要素の box-shadow を強制オフにする。新クラスごとの個別追記はしない（全要素一括強制で追記漏れをゼロ化）。
  - 目的: Chrome 印刷＋`print-color-adjust: exact` で影がカード周囲の薄いグレーの塗りつぶしとして出る現象を恒久的に防ぐ
  - 背景: 個別クラス列挙だと新クラス追加時に box-shadow: none の追記漏れが起き、影の塗りつぶしが配布PDFに残っていた
- **CONST_017B (印刷グラデ文字=通常色に戻す)**: @media print 先頭付近に、グラデ文字（`background-clip: text` + `-webkit-text-fill-color: transparent`）を通常色へ戻すルールを必ず入れる。`background: none` + `background-clip: border-box` + 単色 `-webkit-text-fill-color`/`color` を `.gradient-text` とインライン `[style*="background-clip: text"]` 属性セレクタに適用する。`stat-value` 等の既存クラス別変換は温存する。
  - 目的: タイトル等のグラデ切り抜き文字が印刷で「塗りつぶし矩形＋透明文字」となり読めなくなる現象を恒久的に防ぐ
  - 背景: 印刷時は `background-clip: text` が効かず背景グラデが矩形で塗られ、`text-fill-color: transparent` で文字が透明化して青紫の塗りつぶしになる。属性セレクタで捕捉しインライン切り抜きも追記漏れなく単色化する

### ナビゲーション・ページネーション

- **CONST_017 (ページネーション5個区切りマイルストーン)**: nth-child(5n) で accent-aqua色・0.7remサイズ・margin-right:0.5rem 区切り。セクション構造はセクションナビで表現し、ページネーションは位置インジケーターに徹する。
  - 目的: 全体位置の把握しやすさと、ナビとページネーションの責務分離
  - 背景: ページネーションにセクション意味を持たせると役割が重複し混乱する
- **CONST_018 (section-nav CSS全セクション網羅)**: HTML内の全 data-section 値（opening/lecture/demo/ws/summary/closing等）に対し `.section-nav__item.active[data-section="X"]` 定義を漏れなく用意。
  - 目的: アクティブセクションのハイライト欠落を防ぐ
  - 背景: 定義漏れのセクションでナビが反応せず現在地不明になる

### スライドタイプ・コードブロック

- **CONST_019 (h2 CSS定義全スライドタイプ必須)**: slide-quote / slide-message / slide-list / slide-cycle / slide-flow 等すべての `.slide-TYPE h2` に `font-size: var(--fs-heading)` 定義必須。
  - 目的: 見出しサイズの一貫性確保とタイプ別の不揃い防止
  - 背景: 定義漏れタイプで h2 がブラウザ既定サイズになり階層が崩れる
- **CONST_020 (コードブロックmax-height統一)**: code-block の max-height は420px固定（340px禁止）。overflow-y:auto。
  - 目的: コード表示量を統一し、短すぎる枠でのスクロール多発を防ぐ
  - 背景: 340px は実コードで頻繁に見切れ、可読性が低下した
- **CONST_021 (コードブロック書体)**: font-family は 'SF Mono', 'Fira Code', monospace。Noto Sans JP 禁止。
  - 目的: コードの等幅整列を保証
  - 背景: プロポーショナルフォントだとインデント・桁が崩れる
- **CONST_022 (コードブロック変数ハイライト)**: `{変数}` を accent-yellow 背景でハイライト。
  - 目的: テンプレート変数を視認しやすくする
  - 背景: 地のコードと区別がつかないと変数の認識漏れが起きる
- **CONST_023 (Before/Afterレイアウト)**: 左48%/右48%/gap4%、Before=accent-pink、After=accent-aqua ヘッダー。
  - 目的: 比較の左右対称性と色による前後識別を保証
  - 背景: 非対称・同色だと比較の対比効果が弱まる
- **CONST_024 (コードは常に実HTMLコードブロック)**: image-only/全面画像デッキでも slide-code / slide-code-compare のコードは画像化せず、.code-block / .code-compare-body の実HTMLで前面描画。背景に画像/SVGを敷く場合もコードは常にHTML前面。
  - 目的: コードのコピー可能性・可読性・テーマ追従を保証
  - 背景: コードを画像化すると選択不可・低解像度・テーマ非追従となる

### 質問スライド

- **CONST_025 (質問スライド配置)**: 質問スライド（.question-badge）は各セクションの最後（背景情報の後）に配置。
  - 目的: 文脈を提示してから問いを投げる学習効果の確保
  - 背景: 背景なしの先出し質問は受け手が答えに必要な情報を持たない
- **CONST_026 (質問フォント調整)**: 質問バッジ付きスライドは `.question-badge ~ .main-message { font-size: var(--fs-subheading) }` を適用。
  - 目的: バッジ併存時のメッセージサイズ過大を抑え収まりを良くする
  - 背景: 既定サイズだとバッジとメッセージが競合しオーバーフローする

### 画像・AI画像図解

- **CONST_027 (画像フォーマット)**: 写真・スクリーンショット→WebP（品質85）、図解→インラインSVG、印刷専用→PNG。$CLAUDE_PLUGIN_ROOT/references/image-format-guide.md 参照。
  - 目的: 用途別に最適な画質・容量・印刷品質を選ぶ
  - 背景: 一律PNG等は容量肥大やWeb品質低下を招く
- **CONST_028 (AI画像図解差し替え)**: ユーザーが明示した場合のみ Phase 3.2 で事前確認済み text-to-image バックエンドにより生成。明示指示がなければ SVG/CSS/JS/HTML で完結。通常は画像内テキスト禁止。`kanagawa-comic-diagram` の `image-only + baked-with-overlay` 時のみ短文・簡易表の焼き込みを許可し、正テキストは `overlayText` に残す。$CLAUDE_PLUGIN_ROOT/references/ai-image-diagram-workflow.md / style-genome-packaging.md 参照。
  - 目的: 意図しない画像化・画像内テキストの可読性低下を防ぐ
  - 背景: AI画像は文字・数値が崩れやすく、誤情報・編集不能の原因になる
- **CONST_028A (生成画像フィット契約)**: 生成画像をスライド主キャンバスとして使う場合は `.ai-slide-canvas` に置き、既定を `object-fit: contain` にする。`.slide-bg` は装飾/補助レイヤ専用で、`cover` は `imageFit: cover-safe` と主要被写体の切れ目視確認がある場合だけ許可する。
  - 目的: 1920x1080 のページ画像がHTMLスライド枠で途中切れ・端欠けする事故を防ぐ
  - 背景: 主キャンバス画像を背景画像扱いして `object-fit: cover` で表示すると、比率差・印刷縮尺・ブラウザ差で端の人物/図解/ラベルが切れる

### デザイン品質

- **CONST_029 (ビビッドアクセント必須)**: 各スライドに `--accent-*-vivid` 変数を1つ以上使用。装飾だけでなく意味を持つ色使い。
  - 目的: フォーカルポイントの明確化と単調配色の回避
  - 背景: アクセント不在のスライドは視線誘導が弱く印象に残らない
- **CONST_030 (シャドウ段階適用)**: カード=--shadow-subtle、ホバー=--shadow-medium、モーダル=--shadow-prominent。
  - 目的: 奥行きの段階表現で要素の重要度・状態を伝える
  - 背景: 単一シャドウは階層感がなく平板に見える
- **CONST_031 (アクセシビリティ必須)**: prefers-reduced-motion, focus-visible, sr-only, aria-live を実装。UIテキストの opacity は0.6以上。
  - 目的: キーボード操作・スクリーンリーダー・モーション過敏への配慮
  - 背景: 未実装は WCAG 非準拠で一部利用者が操作・認識できない
- **CONST_032 (視覚階層必須)**: 各スライドに L1（フォーカルポイント）を設定し、L1とL3のサイズ差2倍以上。
  - 目的: 一目で主役が分かる情報設計
  - 背景: 階層差のない要素列挙は読む順序が不明で伝達効率が落ちる
- **CONST_033 (CARP原則適用)**: 近接（グループ内<グループ間）、整列（軸2本以内）、反復（同種同スタイル）、対比（差2倍以上）。
  - 目的: 整理された一貫レイアウトで認知負荷を下げる
  - 背景: CARP 違反は雑然とした印象とグルーピング誤認を生む
- **CONST_034 (60-30-10配色)**: ベース60%、セカンダリ30%、アクセント10%以下。
  - 目的: 色の比率バランスで落ち着きと強調を両立
  - 背景: アクセント過多は強調が分散し、どこが主役か分からなくなる
- **CONST_035 (パターン選択)**: コンテンツ種別に応じたデザインパターンを適用（slide-design-patterns.md 参照）。
  - 目的: 内容に最適な構図を選び表現力を高める
  - 背景: 全スライド同一構図は単調で内容の特性を活かせない

### 基盤

- **CONST_036 (CDN使用)**: GSAP, FontAwesome, Google Fonts のみを CDN で使用（GSAP 3.12.2 / FontAwesome 6.5.1 ほか icons.md の代替可 / Noto Sans JP）。
  - 目的: 依存を限定し再現性・安定性を確保
  - 背景: 不定の外部依存はロード失敗・バージョン差で表示崩れを招く
- **CONST_037 (テーマ準拠)**: Kanagawa カラーパレット使用必須。
  - 目的: スキル全体のビジュアル統一
  - 背景: パレット逸脱はブランド一貫性を損なう
- **CONST_038 (list-item/ig-item全幅)**: list-container・ig-grid に `width:100%`、各item に `width:100%; box-sizing:border-box`。
  - 目的: カードリストを左端から全幅表示し中央寄り片寄りを防ぐ
  - 背景: 幅指定漏れでカードが縮こまり左右非対称になる事例があった

## 5.6 生成規約（ドメインルール）

HTML/CSS/SVG/GSAP/印刷/レイアウトの不変生成規約。5.4 実行方式のループ各周回で本節を判断軸として適用し、5.3 完了チェックリストで充足を確認する。

### 5.6.1 16:9アスペクト比（必須制約）

**重要**: すべてのスライドは16:9アスペクト比を厳守すること（CONST_001）。

#### 必須CSS変数

```css
:root {
  --slide-aspect-ratio: 16 / 9;
  --slide-max-width: min(100vw, calc(100vh * (16 / 9)));
  --slide-max-height: min(100vh, calc(100vw * (9 / 16)));
}
```

#### 必須HTML構造

```html
<div class="slider" id="slider">
  <div class="slide-area">  <!-- 16:9を強制するコンテナ -->
    <div class="slider__container">
      <!-- スライドHTML -->
    </div>
  </div>
</div>
```

#### 必須CSSルール

```css
.slider {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.slide-area {
  width: var(--slide-max-width);
  height: var(--slide-max-height);
  aspect-ratio: 16 / 9;
}

.slider__item {
  aspect-ratio: 16 / 9;
}
```

#### JavaScript注意事項

スライド幅計算は`.slide-area`の幅を使用：

```javascript
this.slideWidth = this.slideArea ? this.slideArea.offsetWidth : window.innerWidth;
```

### 5.6.2 index.html ⇔ structure.md 整合性維持（重要）

**原則: index.htmlとstructure.mdは常に同期を維持すること。**

#### HTML修正時の同期フロー

```
【HTML修正後は必ず以下を実行】
1. index.html を修正
2. structure.md の該当スライド情報を更新
3. structure.md の修正履歴セクションに変更内容を追記
```

#### 必須同期項目

| HTMLの変更 | structure.mdに反映すべき内容 |
|-----------|---------------------------|
| テキスト変更 | 該当スライドのメッセージ/コンテンツ |
| タイプ変更 | スライドタイプ、アニメーション |
| アイコン変更 | 使用アイコン情報 |
| レイアウト調整 | 調整内容をメモに記録 |
| スライド追加/削除 | スライド一覧を全更新 |

#### 非同期による問題

両ファイルが整合していない場合：
- 次回の修正時に意図しない結果になる
- 構成変更時にstructure.mdから正しく再生成できない
- 修正履歴が不正確になり、変更追跡が困難になる

### 5.6.3 部分AI画像化（バランス型）合成パターン

ユーザーが「部分AI画像化（バランス型）」を選択した場合の、背景画像＋HTMLオーバーレイ合成の実装規約。全面AI画像化（`$CLAUDE_PLUGIN_ROOT/references/full-image-deck-method.md`）とは異なり、HTMLシャーシを残したまま画像を背景レイヤとして併存させる。

#### 形式振り分け（毎回ヒアリングで使い分け）

structure.md の各スライドに付与された形式区分と `pattern` / `textPolicy` に従う。画像を生成・使用するのは **イラスト主役** と **ハイブリッド** のみ。

| 形式 | 内容 | 画像の扱い |
|------|------|-----------|
| HTML主役 | 表・料金・精密フロー・数値が主役 | 画像を生成しない。現行コンポーネントのまま |
| イラスト主役 | 概念・章扉・世界観が主役 | 背景レイヤに画像、意味テキストは overlay |
| ハイブリッド | 対比・手順など図と説明が拮抗 | 背景に補助的画像、構造は HTML+overlay |

`kanagawa-comic-diagram` を使う場合は、次を追加で守る。

| pattern | textPolicy | HTML実装 |
|---|---|---|
| `image-only` | `baked-with-overlay` | 画像を主表現として配置。`overlayText` は崩れ対策の正本として structure/meta に保持し、必要時だけHTML overlayを表示 |
| `html-composite` | `overlay-only` | 画像は背景/モチーフ。説明文、表、数値、ラベルは必ずHTML/CSS/SVGで前面に描く。背景はラスター画像（`backgroundSource: raster`）の代わりに `backgroundSource: svg`（SVG/CSSで背景を描きラスター画像を作らない）も選べる |
| `html-primary` | `none` | 画像を使わないか、淡いSVG/CSS背景地のみ。表・比較・数値はHTMLが主役 |

`textPolicy` の値域（`baked-with-overlay` / `overlay-only` / `none`）と `pattern` / `backgroundSource` の定義は `$CLAUDE_PLUGIN_ROOT/references/style-genome-packaging.md` §4 を参照する（ここでは再定義しない）。

#### レイヤ構造（z-index 規約）

全面AI画像化（各ページ=1枚の主キャンバス）は `.slide-bg` を使わず、必ず `.ai-slide-canvas` を使う。`.slide-bg` は部分AI画像化の装飾/補助レイヤ専用。

```html
<div class="slider__item" data-ai-pattern="image-only" data-image-fit="contain">
  <!-- 主キャンバス: 生成された1枚スライド画像。背景ではない -->
  <picture class="ai-slide-canvas">
    <source srcset="vendor/assets/generated/slide-XX-{slug}.webp" type="image/webp">
    <img src="vendor/assets/generated/slide-XX-{slug}.png" alt="{{意味が伝わる説明}}">
  </picture>
  <!-- 必要時だけ表示する正テキスト fallback / UI レイヤ -->
  <div class="slider__content visual-overlay">
    {{overlayText / コード / QR / ページUI}}
  </div>
</div>
```

```html
<div class="slider__item">
  <!-- 背景レイヤ: 装飾画像（イラスト主役/ハイブリッドのみ） -->
  <picture class="slide-bg">
    <source srcset="vendor/assets/generated/slide-XX-{slug}.webp" type="image/webp">
    <img src="vendor/assets/generated/slide-XX-{slug}.png" alt="">
  </picture>
  <!-- 前面レイヤ: 意味テキスト（既存 .slider__content を重ねる） -->
  <div class="slider__content visual-overlay">
    {{見出し・ラベル・本文}}
  </div>
</div>
```

| レイヤ | セレクタ | CSS |
|--------|---------|-----|
| 主キャンバス画像 | `.ai-slide-canvas` | `position:absolute; inset:0; z-index:0; display:grid; place-items:center; overflow:hidden`。`<img>` は `width:100%; height:100%; object-fit:contain` |
| 背景画像 | `.slide-bg` | 装飾/補助レイヤ専用。既定は `object-fit:contain`。`cover` は `.slide-bg--cover-safe` かつ `imageFit: cover-safe` の時だけ |
| 意味テキスト | `.visual-overlay`（既存 `.slider__content` を重ねる） | `position:relative; z-index:1`。見出し・数値・ラベルは必ず前面 HTML/SVG |
| 固定UI | header / footer / section-nav / edge-nav / pagination | `z-index:2`（最前面） |

#### 必須ルール

| 項目 | 内容 |
|------|------|
| コードは常に実HTMLコードブロック | コード系 slideType（slide-code / slide-code-compare）のスライドでは、コードを画像にも overlay レイヤの装飾にもせず、必ず実HTMLコードブロック（.code-block / .code-compare-body）として本文レイヤに実装する。html-composite で背景画像/SVGを敷く場合も、コードブロック自体はHTML前面で描画する（背景は装飾のみ） |
| HTML主役は画像不使用 | 表・料金等の HTML主役スライドは画像を生成せず、現行コンポーネントのまま出力する |
| 画像内に焼き込まない | テキスト・数値・ロゴ・人物を画像内に描かせない。意味情報はすべて overlay 側に置く |
| 主キャンバス画像を切らない | `image-only` / 全面画像生成ページは `.ai-slide-canvas img { object-fit: contain; }` を既定にし、`cover` 表示しない。画像側も top/bottom 8%, left/right 6% の安全余白内に主要被写体を収める |
| フォールバック成立 | 画像未生成・読込失敗でも overlay ＋ CSS 背景で成立させる。`.slide-bg` 省略時はセクション色系の CSS 背景（グラデーション等）を適用 |
| 生成器 | 事前確認済みの text-to-image バックエンドを使用し、meta の `source` に実名を記録する |
| alt 一致 | overlay/装飾の使い分けに関わらず、構造化データ側で管理する alt は structure.md の alt(aria) と一致させる |

#### CSS フォールバック例

```css
/* 画像がある場合: 主キャンバス/背景レイヤをスライド枠に収める */
.ai-slide-canvas,
.slide-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: var(--bg-dark, #FFFFFF);
}
.ai-slide-canvas img,
.slide-bg img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
.slide-bg--cover-safe img {
  object-fit: cover;
}
@media print {
  .ai-slide-canvas img,
  .slide-bg img {
    object-fit: contain !important;
  }
}

/* 画像がない場合: セクション色系 CSS 背景でフォールバック */
.slider__item:not(:has(.slide-bg)):not(:has(.ai-slide-canvas)) {
  background: linear-gradient(135deg,
    var(--section-accent, var(--wave-blue, #7E9CD8)) 0%,
    var(--bg-dark, #FFFFFF) 100%);
}
.visual-overlay { position: relative; z-index: 1; }
```

### 5.6.4 意図的改行の挿入（LLM責務）

カード・ボックス内のテキストが**15文字以上**の場合、意味のまとまりで`<br>`を挿入すること。
機械的な自動改行では文脈を考慮できないため、**LLMが判断して改行位置を決定**する。

**改行判断基準:**
1. 句読点（。、！？）の後
2. 助詞（は、が、を、に、で）の後で意味が区切れる箇所
3. 固有名詞・専門用語の途中では切らない
4. 1行30-40文字を目安

**対象要素:**
- `.list-item span` - リストカードの説明文
- `.flow-step span` - フローステップの説明文
- `.compare-item li` - 比較リストの項目
- `.grid-card p` - グリッドカードの説明文
- `.point-card p` - ポイントカードの説明文

**例: リストスライド**
```html
<!-- NG: 改行なし（ブラウザ任せで不自然な位置で切れる） -->
<span>講義ではなく、実際にAIを使いながらプロンプト作成を体験</span>

<!-- OK: 意味のまとまりで改行 -->
<span>講義ではなく、<br>実際にAIを使いながら<br>プロンプト作成を体験</span>
```

**例: フロースライド**
```html
<!-- NG -->
<span>プロンプト設計パターンを学ぶ</span>

<!-- OK -->
<span>プロンプト設計<br>パターンを学ぶ</span>
```

**改行チェックリスト:**
- [ ] 15文字以上のカード説明文に`<br>`を挿入したか
- [ ] 固有名詞・専門用語の途中で切れていないか
- [ ] 同一スライド内のカードで行数が揃っているか（視覚的バランス）

### 5.6.5 スライドタイプ別のよくある問題パターンと対処

**統計スライド（slide-stats）**
```css
/* NG: 大きすぎるフォント */
.stat-value { font-size: var(--fs-title); }

/* OK: 適切なサイズ */
.stat-value {
  font-size: var(--fs-heading);
  white-space: nowrap;
}
.stat-item { max-width: 350px; }
```

**フロースライド（slide-flow）**
```css
/* NG: 狭すぎる */
.flow-step { max-width: 220px; }

/* OK: 十分な幅 */
.flow-step { max-width: 280px; min-width: 180px; }
```

**タイトルスライド**
```html
<!-- NG: 自動改行で不自然な位置で切れる -->
<h1>ChatGPTを"使える"に変える！</h1>

<!-- OK: 意味的な位置で明示改行 -->
<h1>ChatGPTを<br>"使える"に変える！</h1>
```

### 5.6.6 HTML生成仕様

#### 必須CDN

```html
<!-- GSAP -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>

<!-- アイコン（以下から1つ選択、デフォルト: FontAwesome） -->
<!-- FontAwesome 6 Free（推奨） -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<!-- Bootstrap Icons -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
<!-- Material Symbols -->
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined">

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
```

アイコンライブラリ詳細: `$CLAUDE_PLUGIN_ROOT/references/icons.md`（Bootstrap Icons、Material Symbols実装例含む）。推奨は FontAwesome 6 Free。

#### HTML骨格（分離形式 -- インラインCSS/JS禁止）

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{タイトル}}</title>
  {{CDN}}
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="progress-bar"><div class="progress" id="progress"></div></div>
  <div class="slider" id="slider">
    <div class="slide-area">
      <div class="slider__container">
        {{スライドHTML}}
      </div>
    </div>
  </div>
  <ul class="slider-navigation" id="navigation"></ul>
  <div class="slider-controls">
    <button id="prev"><i class="fas fa-chevron-left"></i></button>
    <button id="next"><i class="fas fa-chevron-right"></i></button>
  </div>
  <script src="scripts.js"></script>
</body>
</html>
```

**禁止**: `<style>...</style>` や `<script>...</script>` によるインライン埋め込み。必ず外部ファイル参照を使用すること（CONST_002）。

#### 出力ファイル配置

```
05_Project/
└── スライド/
    └── slide-{{YYYY-MM-DD}}-{{タイトル}}/
        ├── index.html        # HTML本体（スライド構造のみ）
        ├── styles.css        # CSS（テーマ・レイアウト・印刷用）
        ├── scripts.js        # JavaScript（アニメーション・ナビ）
        ├── structure.md      # 構造化データ（改善・修正用）
        └── deploy-guide.md   # GASデプロイ手順（1ファイル化方法含む）
```

#### GASデプロイ用1ファイル化

分離形式から1ファイルHTMLを生成する場合：

```bash
node $CLAUDE_PLUGIN_ROOT/vendor/scripts/build-single-html.js ./slide-dir/
# → index-single.html が生成される
```

このスクリプトは：
1. `index.html`を読み込み
2. `<link rel="stylesheet" href="styles.css">`を`<style>...</style>`に置換
3. `<script src="scripts.js"></script>`を`<script>...</script>`に置換
4. `index-single.html`として出力

### 5.6.7 PDF出力機能

**詳細**: `$CLAUDE_PLUGIN_ROOT/references/print-layout.md`

- **用紙**: A4横向き、1ページ1スライド
- **印刷用CSS**: `$CLAUDE_PLUGIN_ROOT/vendor/assets/print-styles.css`をインライン埋め込み
- **操作**: `Cmd+P` (Mac) / `Ctrl+P` (Windows)

PDF出力チェックリスト:

| 項目 | 基準 |
|------|------|
| @media printがあるか | 印刷用CSSがインライン埋め込み済み |
| A4横向きか | @page { size: A4 landscape; } |
| 1スライド1ページか | page-break-after: always |
| コンテンツが全表示か | overflow: visible, visibility: visible |
| カード影が全要素オフか | @media print 内に `* { box-shadow: none !important; }`（CONST_017） |
| グラデ文字(タイトル等)が印刷で読めるか | @media print 内でグラデ文字(background-clip:text)を通常色に戻している（`background-clip: border-box` + 単色 `-webkit-text-fill-color`/`color`、CONST_017B） |

### 5.6.8 操作方法（ユーザーへの案内）

生成したHTMLの操作方法：

| 操作 | 方法 |
|------|------|
| 次のスライド | →キー / スペースキー / 右ボタン |
| 前のスライド | ←キー / 左ボタン |
| スライドジャンプ | 下部ドットをクリック |
| PDF出力 | Ctrl+P (Windows) / Cmd+P (Mac) |
