# テキスト・レイアウトガイドライン

> **正本**: [spec-registry.md](spec-registry.md) — このファイルは設計の文脈・例・適用ガイドのみ。規則の正本は SR-ID で参照すること

**責務**: テキストオーバーフロー対策、スライドタイプ別の実装パターン
**規則の正本**: 最小フォント → [SR-3-04](spec-registry.md#sr-3-04) / [SR-3-05](spec-registry.md#sr-3-05)、カードリスト幅 → [SR-4-05](spec-registry.md#sr-4-05)、補足テキスト → [SR-4-06](spec-registry.md#sr-4-06)

---

## 8. 完成チェックリスト

- [ ] スライドタイプは内容に適しているか
- [ ] ホバーエフェクトは適切に設定されているか
- [ ] ツールチップの内容は適切か
- [ ] アニメーションは滑らかか
- [ ] カラーはテーマに沿っているか

---

## 9. テキストオーバーフロー対策

### 9.1 原則

**テキストがはみ出さない、途中で切れない、変な位置で改行しない設計を徹底する。**

### 9.2 よくある問題と対処法

| 問題 | 原因 | 対処法 |
|------|------|--------|
| カード内でテキストが切れる | `max-width`不足、`font-size`過大 | `max-width`を拡大、`font-size`を縮小 |
| 不自然な改行（単語の途中） | 自動改行の位置が不適切 | 意味の切れ目で`<br>`を明示挿入 |
| 統計値が見切れる | 大きな`font-size`がコンテナに収まらない | `white-space: nowrap`を使用、コンテナを拡大 |
| 楕円形内のテキストがはみ出る | `width ≦ height`の楕円で横幅不足 | `width > height`（横長）にする |
| グリッド2列でテキストが収まらない | 1カードあたりの幅が狭い | 1列レイアウトに変更 |

### 9.3 フォントサイズ管理

最小フォント規則 → [SR-3-04](spec-registry.md#sr-3-04)（画面 1.4rem）/ [SR-3-05](spec-registry.md#sr-3-05)（SVG 13px）。

**実装例**:

```html
<!-- NG -->
<span style="font-size: 0.9rem;">補足テキスト</span>

<!-- OK -->
<span style="font-size: var(--fs-small);">補足テキスト</span>
```

### 9.4 テキスト省略と折り返し

#### 長いテキストの省略（ellipsis）

```css
/* 1行で省略 */
.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 3行で省略 */
.text-ellipsis-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

#### 長いテキストの折り返し（改行）

```css
/* 単語単位で折り返し */
.text-wrap {
  word-break: break-word;
  overflow-wrap: break-word;
}

/* 改行を維持 */
.text-prewrap {
  white-space: pre-wrap;
}
```

### 9.5 ブロック要素のパディング

**すべてのブロック要素に十分なパディングを確保する。**

```css
/* カード */
.card {
  padding: 2rem;
  box-sizing: border-box;
}

/* リストアイテム */
.list-item {
  padding: 1.5rem 2rem;
}

/* 比較カード */
.compare-item {
  padding: 2rem;
}

/* フローステップ */
.flow-step {
  padding: 1.5rem;
}
```

### 9.6 `white-space: nowrap`の適切な使用

**使用シーン**: 数値・統計値・短い見出し

```css
/* 統計値（絶対に改行したくない） */
.stat-value {
  white-space: nowrap;
}

/* 短い見出し */
.card-title {
  white-space: nowrap;
}
```

**注意**: 長いテキストに`white-space: nowrap`を使用するとはみ出すため、短いテキスト専用。

---

## 10. スライドタイプ別ガイドライン

### 10.1 slide-list（リスト）

**推奨**: 1列レイアウト

**理由**: 2列にすると1カードあたりの幅が狭くなり、テキストが収まらないリスクが高い。

```css
/* 推奨: 1列 */
.slide-list .list-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  align-items: center;
}

.slide-list .list-item {
  width: 100%;
  max-width: 700px;
}

/* 非推奨: 2列（文字切れリスク） */
.slide-list .list-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
}
```

### 10.2 slide-circle（サークル）

**推奨サイズ**: `width: 480px; height: 480px;` 以上

**理由**: 円形要素（中心・周辺）にテキストを配置する場合、小さいと文字が収まらない。

```css
/* 推奨 */
.slide-circle .circle-container {
  position: relative;
  width: 500px;
  height: 500px;
}

.slide-circle .circle-center {
  width: 150px;
  height: 150px;
}

.slide-circle .circle-item {
  width: 120px;
  height: 120px;
}
```

**注意**: テキストが長い場合は楕円形（`width > height`）を使用して横幅を確保する。

### 10.3 slide-diagram（図解）

**原則**: 図解中心、テキストは補足程度

**推奨構成**:
1. 図形・矢印でメインの関係性を表現
2. テキストは最小限（10文字以内/要素）
3. 詳細はツールチップ（`has-tooltip`）で補足

```html
<!-- 推奨: 図解主体 -->
<div class="diagram-item has-tooltip" data-tooltip="詳細説明はここに">
  <i class="fas fa-circle"></i>
  <span>要素A</span>
</div>
```

### 10.4 楕円形要素のサイズ

**原則**: `width > height` で横長にしてテキスト収容力を確保

```css
/* 推奨: 横長楕円 */
.ellipse {
  width: 180px;
  height: 100px;
  border-radius: 50%;
}

/* 非推奨: 縦長楕円（テキスト収まらない） */
.ellipse {
  width: 100px;
  height: 180px;
  border-radius: 50%;
}
```

### 10.5 slide-grid（グリッド）

**推奨列数**: 2列または3列

**理由**: 4列以上にすると1カードあたりの幅が狭くなりすぎる。

```css
/* 推奨: 2列 */
.slide-grid .grid-container {
  grid-template-columns: repeat(2, 340px);
}

/* 推奨: 3列 */
.slide-grid .grid-container {
  grid-template-columns: repeat(3, 250px);
}

/* 非推奨: 4列（文字切れリスク） */
.slide-grid .grid-container {
  grid-template-columns: repeat(4, 200px);
}
```

**対策**: 4項目以上ある場合は、3列グリッドで2行にするか、別のスライドタイプ（リスト）を使用する。

### 10.6 統計値・数字スライド

**必須**: `white-space: nowrap`を使用

**理由**: 大きな数字は改行すると見栄えが悪い。

```css
.stat-value {
  font-size: var(--fs-title);
  white-space: nowrap;
}

.stat-label {
  font-size: var(--fs-subheading);
  white-space: nowrap;
}
```

### 10.7 完成チェックリスト（タイプ別）

| スライドタイプ | チェック項目 |
|--------------|-------------|
| **slide-list** | □ 1列レイアウトか、2列の場合カード幅は十分か |
| **slide-circle** | □ コンテナサイズは480x480px以上か |
| **slide-diagram** | □ 図解主体で、テキストは補足程度か |
| **楕円形要素** | □ `width > height`（横長）になっているか |
| **slide-grid** | □ 3列以下か、4列の場合文字切れはないか |
| **統計値** | □ `white-space: nowrap`を使用しているか |
| **全般** | □ 最小フォントサイズ1.4remを維持しているか |
| **全般** | □ ブロック要素に十分なパディングがあるか |
| **全般** | □ 長いテキストは意味の切れ目で`<br>`挿入済みか |

---

## 用語注釈先出しフロー（SR-13, 2026-05-09 追加）

### 背景

非エンジニア / 非専門家向けプレゼンで、本文中に専門用語を**初めて出すスライドの 1 枚前**に「用語予告スライド」を入れることで、聴衆の理解度が大きく向上する（過去フィードバック: 04-03 素人思考レビュー由来）。

### 推奨フロー

```
[用語予告スライド] → [本論で用語を使うスライド群]
   1 枚                 N 枚
```

1. デッキ作成中に専門用語（クライアント業界外で意味が通じない語）を抽出
2. 同じ章で 2 回以上登場する用語は**章冒頭に予告スライド**を 1 枚追加
3. 1 つの予告スライドで扱う用語は **3-5 個まで**（多すぎると読み込めない）

### 予告スライド標準テンプレート（`slide-glossary` 仮称）

```html
<div class="slider__item slide-glossary" data-type="slide-glossary">
  <div class="slider__content">
    <h2>このパートで使う言葉</h2>
    <div class="glossary-grid">
      <div class="glossary-card">
        <i class="fa-solid fa-terminal" aria-hidden="true"></i>
        <h3 class="g-term">CLI</h3>
        <p class="g-def">ターミナルで文字を打って操作する画面のこと</p>
      </div>
      <div class="glossary-card">
        <i class="fa-solid fa-cube" aria-hidden="true"></i>
        <h3 class="g-term">MCP</h3>
        <p class="g-def">AI に外部ツールを使わせる共通の入口</p>
      </div>
      <!-- 3-5 件 -->
    </div>
  </div>
</div>
```

### スタイル要件

- **g-term**（用語名）: `font-size: 1.85rem`、太字、accent-blue-vivid
- **g-def**（やさしい定義）: `font-size: 1.45rem`、line-height 1.6、**1 文・40 字以内**
- 定義文は**専門用語で専門用語を説明しない**（「API は HTTP で…」のような連鎖は禁止）
- 比喩・日常物の言い換えを優先（「ターミナル＝魔法のチャット欄」等）

### 配置ルール

| 配置 | タイミング |
|------|----------|
| 章冒頭 | その章で 3+ 個の専門用語を使う場合（推奨） |
| デッキ冒頭 | デッキ全体で頻出する用語を一括予告（3-5 個） |
| 本論直前 | 1 つの用語を深掘りする場合は専用スライドで対応 |

### アンチパターン

- 「全用語集」を 1 枚に詰め込む（10 個以上 → 読まれない）
- 用語名だけ並べて定義を入れない（聴衆が認識できない）
- 既知の用語まで予告する（時間ロス・聴衆を見下した印象）

### 検証

- `slide-text-guidelines` ベースのレビュー時、「初出専門用語が 3 個以上で予告スライドなし」をフラグ
- 予告スライドの定義文が 40 字超なら警告

---

