# 画像フォーマット選択ガイド

**責務**: スライド内画像のフォーマット選択基準（SVG vs WebP vs PNG）とWebP変換手順

---

## フォーマット選択マトリクス

| 用途 | 推奨フォーマット | 理由 |
|------|---------------|------|
| **図解・ダイアグラム** | インラインSVG | スケーラブル、CSS変数連携、印刷品質最高 |
| **AI生成の概念図・情景図** | WebP（PNG元画像保持） | 明示指示時のみ使用。質感・比喩・人物/業務シーンの表現に強い。テキストはHTML/SVGで重ねる |
| **アイコン・ロゴ** | インラインSVG | ベクター、テーマカラー対応、軽量 |
| **写真・画像素材** | WebP | PNG比60-80%軽量、透過対応、高圧縮 |
| **スクリーンショット** | WebP | テキスト+画像の混在に最適 |
| **透過PNG（既存）** | WebP（変換推奨） | 同等品質で大幅に軽量化 |
| **アニメーション** | WebP / GSAP | 短いアニメはWebP、複雑なものはGSAP |
| **印刷専用高品質** | PNG (300dpi) | 一部プリンタのWebP非対応への保険 |

---

## 1. インラインSVG（図解向け）

### 使用すべき場面

- フローチャート、サイクル図、ベン図、マインドマップ
- ファネル、組織図、上昇型チャート
- データ可視化（D3.jsで生成されるSVGも含む）
- アイコン装飾（FontAwesome 6以外で独自アイコンが必要な場合）

### SVG2の利点

| 利点 | 説明 |
|------|------|
| **精密な座標制御** | CSS absolute配置の代わりにSVG座標で正確配置 |
| **CSS変数連携** | `fill="var(--wave-blue,#7E9CD8)"` でテーマ統合 |
| **スケーラブル** | viewBox指定で任意サイズに拡縮、印刷でも劣化なし |
| **`<marker>`** | 矢印・接続点をSVGネイティブで精密描画 |
| **`<path>`** | ベジェ曲線・円弧で滑らかな接続線 |
| **`<filter>`** | ドロップシャドウ、グロー効果 |
| **`<foreignObject>`** | SVG内にHTML/FontAwesome/ツールチップを埋め込み |
| **印刷互換** | ベクターなので印刷時も高品質 |

### SVGは背景レイヤとしても使える

SVGは「図解・ダイアグラム」だけでなく、スライドの**背景レイヤ**としても使える。AI画像のスタイルゲノム量産で `html-composite + backgroundSource: svg`（HTML/CSS/JavaScript/SVG背景でラスター画像を作らない）や `html-primary`（画像を一切使わない退避先）を選ぶ場合、背景はラスター画像（PNG/WebP）を生成せず、SVG2 プリミティブ（`<path>` / `<filter>` / `<foreignObject>` 等）で構築する。これにより文言差し替えに強く、印刷でも劣化しない背景を、ラスター生成のコストと画風退化リスクなしに量産できる。詳細は [style-genome-packaging.md](style-genome-packaging.md) §4.2 を参照する。

### 全面画像デッキの主キャンバスは contain（背景化禁止）

全面 AI 画像デッキ（各ページを 1 枚の生成画像で構成する運用）では、生成画像は背景素材ではなく各ページの**主キャンバス**である。主キャンバスは規定クラス **`.ai-slide-canvas`**（後方互換エイリアス `.slide-fullbg` / `.slide-bg` / `[data-role="main-canvas"]`）に置き、`object-fit: contain`（`imageFit: contain` 既定）で表示する。CSS background や `object-fit: cover` で主画像を切ってはいけない（装飾だけの背景に限り `.slide-bg--cover-safe` の cover を許可）。印刷は A4横 16:9 letterbox（297mm→高さ167mm・上下 off-white 余白）で全ページ端欠けなしにする。主要被写体は safeArea（top/bottom 8% ≈ 115px・left/right 6% ≈ 154px / 2560×1440 基準）内に置く。この表示・印刷フィット契約の正本は [full-image-deck-method.md §0.3](full-image-deck-method.md) であり、実装の正本は `assets/print-styles.css` / `assets/slide-template-single.html`。

### 参照先

- [svg-diagram-primitives.md](svg-diagram-primitives.md) — SVG2基本パーツ
- [diagram-cycle-flow.md](diagram-cycle-flow.md) — サイクル・フロー図解
- [diagram-visual.md](diagram-visual.md) — ビジュアル系図解

---

## 2. WebP（写真・画像素材向け）

### 使用すべき場面

- プレゼンスライド内の写真・画像
- 製品画像、人物写真
- スクリーンショット、画面キャプチャ
- 背景画像
- ユーザーの明示指示により事前確認済みtext-to-imageバックエンドで生成した概念図・情景図・ヒーロービジュアル

### WebPの利点

| 利点 | 説明 |
|------|------|
| **高圧縮** | PNG比60-80%、JPEG比25-34%のファイルサイズ削減 |
| **透過対応** | PNGと同等のアルファチャンネル対応 |
| **ロスレス/ロッシー** | 用途に応じて選択可能 |
| **ブラウザ対応** | 主要ブラウザ全対応（2024年以降97%+） |
| **アニメーション** | GIF代替としても使用可能 |

### 推奨設定

| 用途 | 品質設定 | コマンド例 |
|------|---------|-----------|
| プレゼン写真 | 品質85, ロッシー | `cwebp -q 85 input.png -o output.webp` |
| 高品質画像 | 品質95, ロッシー | `cwebp -q 95 input.png -o output.webp` |
| ロゴ・透過 | ロスレス | `cwebp -lossless input.png -o output.webp` |
| スクリーンショット | 品質90, ロッシー | `cwebp -q 90 input.png -o output.webp` |

### GAS 500KB上限との接続（base64インライン時の膨張に注意）

WebP は PNG 比 60-80% 軽量だが、GAS（Google Apps Script）にデプロイする際は別の上限が効く。GAS の HtmlService が配信できる単一 HTML は実用上 **500KB 上限**で、画像を相対パス参照すると GAS から配信されず broken になるため、軽量デッキは画像を **base64 で HTML へインライン化**して自己完結させる。

- **base64 は実バイト×約1.37に膨張**する（base64 エンコードのオーバーヘッド）。500KB 予算に対し実バイトで見積もる際はこの係数を掛ける。
- 実測 **WebP 1枚平均約184KB → base64 後約252KB**。**2枚で上限到達が目安**で、画像合計が **約340KB 以下に確定する軽量デッキのみ** base64 自己完結（`build-single-html.js --inline-images --full-image-deck`）にできる。
- これを超えるデッキ（全面画像デッキ＝22枚で base64 後約5.5MB・500KB の約11倍 等）は base64 にできない。**外部ホスティング＋絶対URL方式**（`image-asset-manifest.json` 駆動・`build-deck-html.js --manifest`／`--asset-base-url` で Google Drive 直リンク等へ）へ回す。
- 軽量／超過の判定は `build-image-manifest.js` が行う。詳細は [../assets/gas-deploy-guide.md](../assets/gas-deploy-guide.md) §4 / [full-image-deck-method.md](full-image-deck-method.md) §6.9.1 参照。

### HTML記述例

```html
<!-- WebP画像（フォールバック付き） -->
<picture>
  <source srcset="image.webp" type="image/webp">
  <img src="image.png" alt="{{説明}}" loading="lazy"
       style="max-width:100%;height:auto;border-radius:12px;">
</picture>

<!-- WebPのみ（モダンブラウザ前提） -->
<img src="image.webp" alt="{{説明}}" loading="lazy"
     style="max-width:100%;height:auto;border-radius:12px;">
```

---

## 3. 最新モデル（gpt-image-2）の仕様と設定

AI画像生成（概念図・情景図・全面画像デッキ）でラスター画像を作る場合、2026-06時点の最新バックエンドは **gpt-image-2** である。Codex CLI の `$imagegen` / `codex exec` の画像生成も **内部で gpt-image-2 を使用**する（v0.123.0 で gpt-image-1.5 から昇格）。ユーザーが言う通称「**Image 3 / Codex Image 2**」は同一物の俗称であり、実体は gpt-image-2 を指す。

### 3.1 モデル系譜

| モデル | 時期 | 位置づけ |
|--------|------|---------|
| gpt-image-1 | 2025-04 | 旧世代。2026-12-01 に API 削除予定 |
| gpt-image-1.5 | 2025-12 | 1世代前。透過（transparent 背景）に対応 |
| **gpt-image-2** | **2026-04-21** | **最新・既定**。構造化ビジュアル/テキスト描画/空間推論が向上 |
| gpt-image-2-image-to-image | 派生 | 参照画像をもとに編集。本スキルは codex エイリアスが bypass フラグ付き(二重指定禁止)のため `-i` は使わず、参照画像パスを codex exec 指示文へ明記する |
| gpt-image-1-mini | 派生 | 低コスト版 |

### 3.2 gpt-image-2 が得意なこと

- 構造化ビジュアル（インフォグラフィック・図解・マルチパネル）の生成
- テキスト描画の精度向上（ただし日本語は §3.4 の制約あり）
- 空間推論の向上（left / behind / overlapping を理解）→ アイソメ図・分解図に好適

### 3.3 size・アスペクト・透過・品質の制約（gpt-image-1.5 と異なる・重要）

| 項目 | gpt-image-2 の制約 | 旧 gpt-image-1.5 |
|------|------------------|-----------------|
| **size 自由度** | 両辺16px倍数・長辺3840px未満・アスペクト比最大3:1・総ピクセル 655,360〜8,294,400 | 1024x1024 / 1536x1024 / 1024x1536 の3択固定 |
| **プレゼン推奨** | **2560x1440（16:9）を基本**（公式の推奨上限付近。これを超える高解像度は実験的） | 上記3択から選択 |
| **透過（background:transparent）** | バックエンド対応を事前確認する。全面画像デッキは印刷・contain表示の安定性を優先し、不透明背景を既定にする | 対応 |
| **input_fidelity** | **無効**（既定で高忠実度のため指定不要） | 指定可 |
| **quality** | 密テキスト・小さい文字を含むときは **`quality:high`** | 同様 |

旧来の「1024固定」前提の記述があれば本ガイドでは採用しない。プレゼンのラスター画像は **2560x1440（16:9）** を基準とし、長辺は3840px未満・両辺16px倍数を守る。

### 3.4 日本語（CJK）ラベルの精度限界と対策

gpt-image-2 のテキスト描画は向上したが、**日本語（CJK）の文字精度は英語より落ちる（実測おおむね60〜70%帯）**。誤字・字形崩れが残る前提で次を守る。

- **短語+引用符+verbatim**: 画像に焼くラベルは短い語にし、プロンプト内で `"○○"` と引用符で囲み「verbatim（一字一句そのまま）」と明示する
- **長文はHTML前面で重ねる**: 段落・箇条書き・正確さが要る文言は画像に焼かず、HTML/SVG を画像の前面に重ねて描く（全面画像デッキの overlay 契約に従う）
- **目視校正必須**: 生成後は必ずスクリーンショットで文字を目視確認し、崩れたラベルは作り直すか HTML 差し替えにする

### 3.5 codex exec での実呼び出し注意

- **出力パスをプロンプト内に明示**する（生成画像の保存先をプロンプト本文へ書く）
- 書き込み権限と作業ディレクトリを付ける: `-s workspace-write -C <作業ディレクトリ>`
- **モデルバージョンは `codex --version` で確認**する（v0.123.0 以上で gpt-image-2）
- **大量生成時は `OPENAI_API_KEY` を設定して API 課金へ切替**える（量産時のレート/コスト最適化）
- 参照画像を使う編集: 本スキルの generate-images-codex.js は codex エイリアス(bypass付き・フラグ二重指定禁止)のため `-i` フラグを使わず、参照画像パスを codex exec の指示文に明記して渡す
- 生成 PNG は本ガイド §4 の WebP 変換ワークフローでスライド用に最適化する

詳細な生成プロンプト設計・全面画像デッキの焼き込み/overlay 契約は [ai-image-diagram-workflow.md](ai-image-diagram-workflow.md) / [full-image-deck-method.md](full-image-deck-method.md) を参照する。

---

## 4. PNG（レガシー/印刷向け）

### 使用すべき場面

- 印刷専用の超高品質画像（300dpi以上）
- WebP非対応環境へのフォールバック
- 既存アセットでWebP変換不要な場合

### 注意

- 新規画像の追加時はWebPを第一選択とすること
- 既存PNGは `scripts/convert-to-webp.js` で一括変換可能

---

## 5. 変換ワークフロー

### 一括変換コマンド

```bash
# スライドディレクトリ内のPNG/JPGをWebPに一括変換
node .claude/skills/presentation-slide-generator/scripts/convert-to-webp.js ./slide-dir/

# 品質指定
node .claude/skills/presentation-slide-generator/scripts/convert-to-webp.js ./slide-dir/ --quality 90

# ロスレス変換
node .claude/skills/presentation-slide-generator/scripts/convert-to-webp.js ./slide-dir/ --lossless
```

### 手動変換（cwebpコマンド）

```bash
# インストール（macOS）
brew install webp

# 変換
cwebp -q 85 input.png -o output.webp
cwebp -q 85 input.jpg -o output.webp
cwebp -lossless input.png -o output.webp
```

---

## 6. SVG vs WebP 判断フローチャート

```
画像を追加する
    ↓
コード・数式・精密数値表・コマンド列／APIレスポンス例か？
    ├─ Yes → 実HTML（slide-code / slide-code-compare、画像化しない）
    └─ No
        ↓
    図解・ダイアグラム・アイコンか？
        ├─ Yes
        │   ↓
        │   精密なラベル・矢印・数値が中心か？
        │       ├─ Yes → インラインSVG（svg-diagram-primitives.md参照）
        │       └─ No
        │           ↓
        │       ユーザーが画像生成・Codex図解作成を明示しているか？
        │           ├─ No → インラインSVG
        │           └─ Yes
        │               ↓
        │       情景・比喩・質感で伝えると効果が上がるか？
        │           ├─ Yes → AI画像生成 + WebP（ai-image-diagram-workflow.md参照）
        │           └─ No → インラインSVG
        └─ No
            ↓
        写真・スクリーンショットか？
            ├─ Yes → WebP（品質85、convert-to-webp.js使用）
            └─ No
                ↓
            印刷専用の超高品質が必要か？
                ├─ Yes → PNG（300dpi）
                └─ No → WebP
```

---

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-15 | 初版: SVG/WebP/PNG選択ガイド、変換ワークフロー、推奨設定 |
| 1.1.0 | 2026-05-06 | AI生成の概念図・情景図をWebP化して差し替える判断を追加 |
| 1.2.0 | 2026-06-24 | 実装整合（elegant-review・D1/D2/D5）。「全面画像デッキの主キャンバスは contain（背景化禁止）」を追加。主キャンバスクラス規定（`.ai-slide-canvas`＋後方互換エイリアス）・`object-fit:contain`・印刷 16:9 letterbox（167mm）・safeArea（115/154px）のフィット契約を明記し、正本を `full-image-deck-method.md §0.3` と実装（`assets/print-styles.css` / `assets/slide-template-single.html`）に参照（DRY） |
| 1.3.0 | 2026-06-25 | 最新モデル gpt-image-2（2026-04-21）の仕様セクション（§3）を追加。モデル系譜（gpt-image-1→1.5→2）、size制約（両辺16px倍数・長辺3840px未満・3:1・総ピクセル範囲、プレゼンは2560x1440基準、旧1024固定を廃止）、透過はバックエンド対応確認・input_fidelity無効・quality:high、Codex CLI が内部で gpt-image-2 を使う事実と通称「Image 3 / Codex Image 2」の実体注記を明記。日本語CJKラベルの精度限界（60〜70%帯）と対策（短語+引用符+verbatim・長文はHTML前面・目視校正）、codex exec 実呼び出し注意（出力パス明示・`codex --version`確認・大量時API課金・`-i`参照）を追加。PNG/変換/フローチャート節を §4〜6 に繰り下げ |
| 1.4.0 | 2026-06-26 | GAS 500KB上限との接続（§2 に小見出し追加）。WebP は PNG 比 60-80% 軽量だが GAS デプロイでは単一HTML 500KB上限が効くこと、base64 インラインは実バイト×約1.37に膨張すること、実測 WebP 1枚平均約184KB→base64後約252KB で 2枚で上限到達が目安・画像合計≤約340KB の軽量確定デッキのみ base64 自己完結（`build-single-html.js --inline-images --full-image-deck`）可、超過デッキ（全面画像デッキ＝22枚で base64後約5.5MB）は外部ホスティング＋絶対URL方式（`image-asset-manifest.json` 駆動・`build-deck-html.js --manifest`）へ回すことを明記。判定は `build-image-manifest.js`、詳細は gas-deploy-guide.md §4 / full-image-deck-method.md §6.9.1 へ参照（DRY） |
