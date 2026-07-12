# v8 拡張フィールド総覧

> presentation-slide-generator v8 で導入された **スライド単位の粒度制御** フィールドのリファレンス。すべて optional。`meta.schemaVersion: "8.0.0"` を指定したときのみ render-slide.cjs / validate-structure.js が解釈する。未指定 (=v7) では一切影響しない。

互換性: v7 spec はそのまま動作する。v8 フィールドは additive only。

---

## 1. meta 拡張

| フィールド | 型 | 用途 |
|---|---|---|
| `schemaVersion` | enum: "7.0.0" \| "8.0.0" | v8 機能のゲート。デフォルト "7.0.0" |
| `tagline` | string ≤80 | 表紙腰キャッチ。`cover.tagline` のフォールバック |
| `event` | object | 表紙・ヘッダで再利用するイベント情報 (name/date/venue/round) |
| `hero` | heroMeta | 表紙ヒーロビジュアル既定値。各スライドの `cover.hero` のフォールバック |

`heroMeta` の kind: `icon` (Font Awesome) / `svg` (svg-builder 関数名) / `image` (WebP path) / `diagram` (diagramSpec 参照) / `none`。

## 2. theme 拡張

| フィールド | 用途 |
|---|---|
| `accentColors` | maxItems を 2→8 に拡張。セクション別配色を一元管理 |
| `pagination` | `style` (dots/bar/numeric/section-dots/none), `milestoneEvery`, `showSectionHighlight`, `showCurrentStep` |
| `footer` | `show`, `left`, `center`, `right`。`right` 内の `{page}/{total}` がページカウンタに置換される |
| `header` | `show`, `showSection`, `showEventName`, `logoIcon` |

セクション色テーマ:

```jsonc
"sections": [
  { "id": "section-intro", "title": "...", "color": "blue", "icon": "fa-flag",
    "theme": { "primaryAccent": "blue", "secondaryAccent": "amber",
               "background": "tint", "paginationColor": "blue" },
    "slides": [1, 2] }
]
```

## 3. スライド単位フィールド

### 3-1. `cover` — 表紙の詳細指定

`slide-hero` / `slide-title` で使用。variant ごとにレンダリング戦略が変わる。

| variant | 用途 |
|---|---|
| `minimal` | 文字のみ |
| `hero-icon` | Font Awesome 大型アイコン |
| `hero-svg` | svg-builder の関数を呼ぶ |
| `hero-image` | WebP 画像 (imagePath 必須・V-032) |
| `split` | 左右2カラム |
| `centered-large` | 中央巨大タイトル |

主要フィールド: `title`, `subtitle`, `tagline`, `presenter`, `eventName`, `eventDate`, `venue`, `hero`, `background`。

### 3-2. `index` — 目次・アジェンダ・章扉

| フィールド | 用途 |
|---|---|
| `style` | `list` / `grid` / `timeline` / `stepper` / `card` |
| `showSectionNumbers` | 1. 2. 3. 表示 |
| `showSectionIcons` | section.icon を表示 |
| `highlightCurrent` | 章扉で「今ここ」を強調 |
| `currentSection` | 強調対象 section.id (V-034 で参照整合) |
| `showStep` | (1/3) 等のステップ表示 |
| `items[]` | 明示指定 (省略時は `sections` から自動生成 / V-033) |

### 3-3. `diagram` — 共通図解データモデル

variant: `tree` / `mindmap` / `flow` / `cycle` / `pyramid` / `matrix` / `venn` / `network` / `timeline` / `roadmap` / `chevron` / `funnel` / `org` / `concentric` / `value-stack` / `snake` / `wave-step` / `comparison` / `stepper` / `custom`。

- `nodes[]` (必須・最大60): id (`^n-`), label, subtext, icon, color, level (ピラミッド階層), weight (ファネル幅), position (明示座標 0–100%), shape, emphasis, group。V-036 で id 一意性を検証。
- `edges[]`: from / to (V-035 でノード参照整合検証), label, kind (arrow/line/dashed/double/thick), color, emphasis。
- `groups[]`: id (`^g-`), label, color, kind (box/tint/outline)。複数ノードの囲み。
- `annotations[]`: text, kind (note/warning/tip/caution), anchor (node.id or group.id), icon。警告補足吹き出し。
- `legend`: show + items[]。色凡例。

### 3-4. `pageOverride` — スライド単位の色・背景・装飾上書き

| フィールド | 用途 |
|---|---|
| `primaryAccent` / `secondaryAccent` | --accent-primary / --accent-secondary を上書き |
| `background` | `default` / `tint` / `gradient` / `dark` / `image` |
| `backgroundImage` | background=image 時に必須 (V-037) |
| `pagination.show` | false で当該スライドのナビ非表示 (例: 表紙) |
| `pagination.color` | --accent-pagination 上書き |
| `footer` / `header` | スライド単位で上書き |

優先順位: `pageOverride > section.theme > theme`。

## 4. レンダラ実装

`render-slide.cjs` は schemaVersion=8.0.0 のときだけ:

1. `<div class="slider__item">` に以下を付与
   - `data-section`, `data-bg`, `data-pg-hide`, `data-v8-cover/index/diagram`
   - `style="--accent-primary: var(--accent-X); --accent-secondary: ...; --accent-pagination: ...; --bg-image: url(...)"`
2. scaffold に `<header class="slider-header">` / `<footer class="slider-footer">` を生成
3. スライダールートに `data-pg-style` を付与（CSS でスタイル切替）
4. ctx に `cover` / `index` / `diagram` / `pageOverride` を露出（テンプレ側で利用可能）

未対応のテンプレートは v8 フィールドを無視するだけで安全。

## 5. 検証 V-031〜V-038

| V-ID | 内容 | level |
|---|---|---|
| V-031 | cover.variant=hero-icon は cover.hero.icon (fa-*) 必須 | FAIL |
| V-032 | cover.variant=hero-image は cover.hero.imagePath 必須・WebP推奨 | FAIL |
| V-033 | index.items または sections のいずれかが必要 | FAIL |
| V-034 | index.currentSection は sections.id に存在 | FAIL |
| V-035 | diagram.edges の from/to は nodes.id に存在 | FAIL |
| V-036 | diagram.nodes.id は重複なし | FAIL |
| V-037 | pageOverride.background=image は backgroundImage 必須 | FAIL |
| V-038 | section.theme/pageOverride の色は theme.accentColors に含む | WARN |

schemaVersion≠8.0.0 のとき V-031〜V-038 は SKIPPED。

## 6. サンプル

`schemas/example.v8.structure.json` 参照。
