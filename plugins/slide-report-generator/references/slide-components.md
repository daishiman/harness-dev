# スライドコンポーネント（インデックス）

**注意**: このファイルは分割されました。詳細は各ファイルを参照してください。

## 分割先ファイル一覧

| ファイル | 内容 | 行数 |
|----------|------|------|
| [slide-types-overview.md](slide-types-overview.md) | タイプ一覧・選択ガイド | 70行 |
| [slide-types-basic.md](slide-types-basic.md) | 基本7種 | 460行 |
| [slide-types-extended.md](slide-types-extended.md) | 拡張8種 | 650行 |
| [slide-interactions.md](slide-interactions.md) | ホバー・アニメ | 820行 |
| [slide-text-guidelines.md](slide-text-guidelines.md) | テキスト・レイアウト | 280行 |
| [diagram-cycle-flow.md](diagram-cycle-flow.md) | 図解: サイクル・フロー系 | 920行 |
| [diagram-comparison.md](diagram-comparison.md) | 図解: 比較・マトリックス系 | 940行 |
| [diagram-business.md](diagram-business.md) | 図解: ビジネス系 | 1030行 |
| [diagram-visual.md](diagram-visual.md) | 図解: ビジュアル系 | 1440行 |
| [chart-types.md](chart-types.md) | グラフ9種 | 1510行 |
| [agenda-navigation.md](agenda-navigation.md) | アジェンダナビ | 340行 |

**旧ファイル**: `slide-components-legacy.md`（バックアップ）

## Progressive Disclosure

各ファイルは**必要な時のみ**読み込むこと：

- 基本スライド作成 → `slide-types-basic.md`
- 図解スライド作成 → `diagram-*.md`（該当タイプのみ）
- ホバー実装 → `slide-interactions.md`
- グラフ作成 → `chart-types.md`

---

## アクセシビリティ必須テンプレート（SR-10, 2026-05-09 追加）

全スライド共通で以下の `sr-only` / `aria-live` 雛形を組み込むこと（SR-9-05 / SR-9-06 根拠）。

### 1. `sr-only` ユーティリティクラス（CSS 必須）

```css
/* スクリーンリーダー専用テキスト（視覚的に非表示・読み上げ対象） */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

### 2. スライド遷移通知用 `aria-live` リージョン（HTML 必須）

```html
<!-- スライダーのすぐ近くに 1 つだけ配置 -->
<div id="slide-announcer" class="sr-only" aria-live="polite" aria-atomic="true"></div>
```

JavaScript 側でスライド遷移時に下記を更新する。

```js
// updateSlide() 内で必ず呼ぶ
function announceSlide(currentIndex, total, title) {
  const el = document.getElementById('slide-announcer');
  if (!el) return;
  el.textContent = `スライド ${currentIndex + 1} / ${total}: ${title}`;
}
```

### 3. SVG 図解の `aria-label` 必須（SR-9-05）

```html
<svg role="img" aria-labelledby="diagram-N06-title diagram-N06-desc" viewBox="0 0 960 540">
  <title id="diagram-N06-title">構成要素マップ</title>
  <desc id="diagram-N06-desc">CLAUDE.md・スキル・MCP の3要素が中央のエージェントに接続される図</desc>
  <!-- ... -->
</svg>
```

- 装飾目的の SVG は `role="presentation" aria-hidden="true"` を付与し、上記は省略可。
- 意味のある図解は `<title>` / `<desc>` を**必ず**併記する（aria-label 単独より読み上げ品質が高い）。

### 4. ナビゲーションボタンの `aria-label`

```html
<button class="nav-prev" aria-label="前のスライド (スライド 5/38 へ)">‹</button>
<button class="nav-next" aria-label="次のスライド (スライド 7/38 へ)">›</button>
```

- ナビゲーション時の `aria-label` は静的「前/次」だけでなく**遷移先スライド番号**も含める（過去フィードバック L-04 反映）。

### 5. データ属性連動の確認

- 各 `.slider__item` に `data-slide-id="N06"`, `aria-label="スライド 6/38: <タイトル>"` を付与する。
- セクションナビ `.section-nav__item` には `aria-current="step"` を現在セクションに付与する。

### 6. `prefers-reduced-motion` 対応（SR-9-03 / SR-6-08 と整合）

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

```js
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const ANIM_SCALE = prefersReducedMotion ? 0 : 1;
// gsap.from(el, { duration: 0.4 * ANIM_SCALE, ... })
```

### 検証スクリプトでの確認項目（推奨）

- `<div class="sr-only" aria-live` が HTML に存在
- `.sr-only` クラスが CSS に存在
- 装飾以外の `<svg>` に `aria-label` または `aria-labelledby` 存在
- `prev` / `next` ボタンに `aria-label` 存在
