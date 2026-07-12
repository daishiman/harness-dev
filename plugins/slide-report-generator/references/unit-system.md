# 単位システム（画面↔印刷 差分ゼロ化）

> **目的**: 画面プレビューと印刷PDFの見た目を完全に一致させる（差分ゼロ化）。
> 既存 `references/print-layout.md` の「印刷時に font-size / padding / gap を別途縮小」する方式を撤廃し、
> 画面と印刷の双方を「viewport正規化座標系」上で同一スケールに統一する。

---

## §1 設計原則

1. **正規化座標系の単一化**
    - 1スライド領域は常に `100vw × 56.25vw`（16:9）または `100vw × 100vh`（@page で固定された印刷時）
    - 画面・印刷ともに「スライド＝viewport」を前提とし、内部寸法は viewport 比例（vw / vh / %）で表現する

2. **使用単位は viewport 系のみ**
    - 全レイアウト寸法は `vw` / `vh` / `%` のみ
    - `rem` は段階移行期のみ許容（最終的に廃止）
    - `px` は SVG 内部 `viewBox` の数値座標（単位無し）に限定
    - `mm` は `@page` 定義（A4 landscape）でのみ許容

3. **印刷時の viewport 固定**
    - `@page { size: A4 landscape }` で 297mm × 210mm に固定
    - `html` を `width: 297mm; height: 210mm` にロックすると `1vw = 2.97mm`、`1vh = 2.10mm` が確定
    - 結果、画面で書いた `vw` 値が印刷時に自動的に正しい mm へ換算される
    - **印刷専用の font-size 縮小ルールは不要になる**

4. **SVG は viewBox で正規化**
    - `viewBox="0 0 1280 720"` のように内部座標を固定
    - `width: 100%` / `height: auto` でスライド領域に追従させる
    - 画面・印刷で完全に同一スケール（差分ゼロ）

5. **スケール定数**
    - 基準解像度: **1280 × 720**（16:9）
    - 基準ベース font-size: **16px = 1rem**（移行期の換算用）
    - 換算式:
        - `1vw = 12.80px`（画面 1280px 基準）
        - `1vw = 2.97mm`（印刷 A4 landscape 297mm 基準）
        - `1rem (16px) ≒ 1.25vw`（1280px viewport 基準）

---

## §2 単位ホワイトリスト

| 単位 | 画面 | 印刷 | 用途 | 備考 |
|------|:----:|:----:|------|------|
| `vw` | OK | OK | 全寸法（font-size / padding / gap / width） | **推奨** |
| `vh` | OK | OK | 高さ寸法（縦比例が必要な場合） | 印刷時は `1vh = 2.10mm` |
| `%`  | OK | OK | 親要素相対の幅・gap | フレックス内の比率配分に最適 |
| `rem`| △  | △  | 既存コード移行期のみ | Phase C で全廃 |
| `em` | OK | OK | テキスト相対（line-height 等） | font-size に対する相対 |
| `px` | NG | NG | レイアウト寸法 | **禁止**。SVG `viewBox` 数値のみ例外 |
| `mm` | NG | △ | A4 寸法定義のみ | `@page { size: ... }` だけで使用可 |
| `pt` | NG | NG | 全用途 | 旧来の印刷特化指定は廃止 |
| `cm` | NG | NG | 全用途 | mm 同様、`@page` 以外禁止 |

**SVG 例外**: `<svg viewBox="0 0 1280 720">` 内の `x="640"`, `r="50"`, `font-size="32"` などの単位無し数値は OK。
viewBox がスライド領域に伸縮するため、画面・印刷で完全に一致する。

---

## §3 vw 換算表

### §3.1 タイポグラフィ（`--fs-*` トークン）

現行 `references/theme-style.md` 定義を viewport 基準に変換する。基準 viewport = 1280px。

| トークン | 旧値 (rem) | 新値 (vw) | 画面換算 (1280px) | 印刷換算 (297mm) |
|----------|----------:|----------:|------------------:|-----------------:|
| `--fs-title`      | 5.0rem | **6.25vw**  | 80.0px | 18.56mm |
| `--fs-subtitle`   | 2.5rem | **3.13vw**  | 40.1px | 9.30mm  |
| `--fs-heading`    | 3.0rem | **3.75vw**  | 48.0px | 11.14mm |
| `--fs-subheading` | 2.0rem | **2.50vw**  | 32.0px | 7.43mm  |
| `--fs-body-lg`    | 1.8rem | **2.25vw**  | 28.8px | 6.68mm  |
| `--fs-body`       | 1.5rem | **1.88vw**  | 24.1px | 5.58mm  |
| `--fs-small`      | 1.4rem | **1.75vw**  | 22.4px | 5.20mm  |

> **依頼仕様の補足換算（base 16px / 旧 fs-title 3.6rem 系のテーマ）**
>
> | 旧値 (rem) | 新値 (vw) | 印刷換算 |
> |----------:|----------:|--------:|
> | 3.6rem | 2.81vw | 8.34mm |
> | 2.4rem | 1.88vw | 5.58mm |
> | 1.6rem | 1.25vw | 3.71mm |
> | 1.4rem | 1.09vw | 3.24mm |

### §3.2 ナビゲーション・チャート系

| 用途 | 旧値 | 新値 (vw/vh/%) | 印刷換算 |
|------|------|---------------:|---------:|
| `--nav-arrow-padding`   | 3rem    | **3.75vw** | 11.14mm |
| `--nav-top-padding`     | 1rem    | **1.25vw** | 3.71mm  |
| `--nav-bottom-padding`  | 2rem    | **2.50vw** | 7.43mm  |
| プログレスバー font-size | 2.5rem  | **3.13vw** | 9.30mm  |
| ドット間隔 gap          | 0.4rem  | **0.50vw** | 1.49mm  |
| ドット padding          | 0.5rem 1rem | **0.63vw 1.25vw** | 1.86mm 3.71mm |

### §3.3 印刷専用上書きの撤廃（旧 print-layout.md §フォント縮小ルール）

下表は `print-layout.md` (l.222-358) で定義されていた印刷時上書き値と、**新ルールでの統一値**の対比。
新ルールでは「印刷時上書き」が消滅し、画面値がそのまま印刷値になる。

| 要素 | 画面値（現行） | 旧 印刷上書き | 新 統一値 (vw) | 印刷換算 |
|------|--------------:|-------------:|--------------:|---------:|
| `.slide-title .title-main`     | `var(--fs-title)` 5rem | 3rem    | **6.25vw** | 18.56mm |
| `.slide-title .title-sub`      | -                      | 1.5rem  | **3.13vw** | 9.30mm  |
| `.slide-title .title-meta`     | -                      | 1rem    | **1.25vw** | 3.71mm  |
| `.slide-section .section-title`| `var(--fs-title)`      | 2.5rem  | **6.25vw** | 18.56mm |
| `.slide-stats .stat-value`     | `var(--fs-title)`      | 2rem    | **6.25vw** | 18.56mm |
| `.slide-stats .stats-container` gap | -                | 1rem    | **1.25vw** | 3.71mm  |
| `.slide-stats .stat-item` padding   | -                | 1rem    | **1.25vw** | 3.71mm  |
| `.slide-list .list-container` gap   | -                | 0.8rem  | **1.00vw** | 2.97mm  |
| `.slide-list .list-item` padding    | -                | 0.8rem 1rem | **1.00vw 1.25vw** | 2.97mm 3.71mm |
| `.slide-list .list-content h3`      | `--fs-subheading`| 1.1rem  | **2.50vw** | 7.43mm  |
| `.slide-list .list-content p`       | `--fs-body`      | 0.9rem  | **1.88vw** | 5.58mm  |
| `.grid-container` gap               | -                | 1rem    | **1.25vw** | 3.71mm  |
| `.grid-card` padding                | -                | 1rem    | **1.25vw** | 3.71mm  |
| `.grid-card h3`                     | `--fs-subheading`| 1rem    | **2.50vw** | 7.43mm  |
| `.grid-card p`                      | `--fs-body`      | 0.85rem | **1.88vw** | 5.58mm  |
| `.slide-table table`                | `--fs-body`      | 0.9rem  | **1.88vw** | 5.58mm  |
| `.slide-table th/td` padding        | -                | 0.6rem 1rem | **0.75vw 1.25vw** | 2.23mm 3.71mm |
| `.slide-flow .flow-container` gap   | -                | 0.5rem  | **0.63vw** | 1.86mm  |
| `.slide-flow .flow-step` padding    | -                | 1rem    | **1.25vw** | 3.71mm  |
| `.slide-compare .compare-container` gap | -            | 1.5rem  | **1.88vw** | 5.58mm  |
| `.slide-compare .compare-panel` padding | -            | 1.5rem  | **1.88vw** | 5.58mm  |
| `.icon-grid-container` gap          | -                | 1rem    | **1.25vw** | 3.71mm  |
| `.icon-grid-item` padding           | -                | 1rem    | **1.25vw** | 3.71mm  |
| `.icon-grid-item h4`                | `--fs-body-lg`   | 0.9rem  | **2.25vw** | 6.68mm  |
| `.icon-grid-item p`                 | `--fs-small`     | 0.8rem  | **1.75vw** | 5.20mm  |
| `.slide-message .message-main`      | `--fs-title`     | 2rem    | **6.25vw** | 18.56mm |
| `.slide-agenda .agenda-item` padding| -                | 0.8rem 1.5rem | **1.00vw 1.88vw** | 2.97mm 5.58mm |

### §3.4 スライド外周パディング

| 場所 | 旧値 | 新値 (vw) | 印刷換算 |
|------|------|----------:|---------:|
| `.slider__content` 外周 padding | `15mm 20mm` | **5.05vw 6.73vw** | 15.00mm 19.99mm |
| `.slider__item` 全体            | -           | `width: 100vw; height: 100vh` | 297mm × 210mm |

### §3.5 比率系（変換不要）

| 用途 | 値 | 備考 |
|------|----|------|
| Before/After gap | `4%` | 親要素相対なので画面・印刷で同一動作 |
| 2 カラム grid    | `1fr 1fr` | 比率指定はそのまま |
| flex 子要素 width | `50%`, `33.33%` | % は親基準なので不変 |

---

## §4 印刷時の viewport 固定

### §4.1 必須 CSS（`assets/print-styles.css` 末尾に追記する想定）

```css
/* === A4 横向き、余白ゼロでviewportを固定 === */
@page {
  size: A4 landscape;
  margin: 0;
}

@media print {
  /* SR-09 カード影は全要素で強制オフ（影がグレー塗りつぶしになる現象の恒久対策） */
  * {
    box-shadow: none !important;
  }

  /* viewportをA4横にロック → 1vw = 2.97mm が確定 */
  html {
    width: 297mm;
    height: 210mm;
    font-size: 16px; /* 移行期の rem 互換用ベース */
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  body {
    width: 297mm;
    height: 210mm;
    margin: 0;
    padding: 0;
  }

  /* 1スライド = 1ページ = viewport 全体 */
  .slider__item {
    width: 100vw;
    height: 100vh;
    page-break-after: always;
    break-after: page;
  }

  .slider__item:last-child {
    page-break-after: auto;
    break-after: auto;
  }

  /* GSAPインラインリセット（既存ルール継承） */
  .slider__content,
  .slider__content > *,
  .slider__content * {
    opacity: 1 !important;
    transform: none !important;
    visibility: visible !important;
  }
}
```

### §4.2 画面側の前提

```css
/* 画面表示も同じ正規化座標系 */
:root {
  --slide-w: 100vw;
  --slide-h: 56.25vw; /* 16:9 */
}

.slider__item {
  width: var(--slide-w);
  height: var(--slide-h);
  /* または full-bleed なら 100vh */
}
```

> 印刷時は `@media print` の上書きにより `100vh` が `210mm` に固定される。
> 画面でも `vw` 基準なら resize に追従する。`vw` を一貫して使うことが画面↔印刷一致のキー。

---

## §5 段階移行プラン

### Phase A: 新規スライドは vw ベースで生成（即時開始）
- `scripts/html-scaffold.js` のテンプレート生成箇所で `rem` を出さず `vw` を出力
- 新規 `slide-types-*.md` のサンプルコードは `vw` で記述
- `references/diagram-*.md` の追記分は `vw` 基準

### Phase B: 既存 styles.css の段階置換
対象:
1. `assets/src/styles/variables.css` … `--fs-*` トークン定義を vw 化
2. `assets/src/styles/base.css` … 外周 padding / gap を vw 化
3. `assets/src/styles/slide-types.css` … 各 `.slide-*` の rem を §3 の表に従って置換
4. `assets/src/styles/print.css` … `@page` と viewport 固定のみ残し、印刷専用 font-size 上書きを全削除
5. `assets/print-styles.css` … 同上
6. `assets/slide-template.html` / `slide-template-single.html` / `d3-slide-template.html` … インラインスタイル除去
7. `assets/structure-template.md` … サンプル値更新
8. `references/theme-style.md` … トークン定義表を vw に更新
9. `references/print-layout.md` … §フォント縮小ルール（l.222-358）を全削除し、本ファイルへのリンクに置換
10. `scripts/validate-print.js` … 印刷専用 font-size 上書きを「警告」から「禁止」へ
11. `scripts/cross-deck-consistency.js` … rem 検出を追加
12. `scripts/html-scaffold.js` … テンプレート出力を vw に変更

### Phase C: クリーンアップ
- `print-layout.md` の§フォント縮小ルール削除
- `theme-style.md` の最小値ガード（「`--fs-small` は最小1.4rem」）を「最小1.75vw」に書き換え
- `rem` 全廃 → ホワイトリストから `rem` を削除し、検証スクリプトでエラー化

---

## §6 検証スクリプト要件

新規: `scripts/validate-units.js`

### §6.1 検出ルール

| ルール | 対象パス | 違反検出パターン | 重大度 |
|--------|---------|------------------|--------|
| R1: 印刷以外の `mm` 禁止 | `assets/**/*.css` | `[0-9.]+mm` が `@page` ブロック外に出現 | error |
| R2: `px` 禁止（CSS） | `assets/**/*.css` | `[0-9]+px`（`viewBox`/`stroke-width` の SVG 属性除く） | error |
| R3: `pt` / `cm` 禁止 | `assets/**/*.css` | `[0-9.]+(pt|cm)` | error |
| R4: `@media print` 内 font-size 上書き禁止 | `assets/**/*.css` | `@media print` ブロック内の `font-size:` 出現 | error |
| R5: `rem` 段階廃止警告 | `assets/**/*.css` | `[0-9.]+rem` | warn (Phase B) → error (Phase C) |
| R6: SVG `viewBox` 必須 | `assets/**/*.html`, `references/**/*.md` の `<svg>` | viewBox 属性なし | error |

### §6.2 実装スケルトン

```js
// scripts/validate-units.js
const fs = require('fs');
const path = require('path');
const glob = require('glob');

const ROOT = path.resolve(__dirname, '..');
const targets = glob.sync('assets/**/*.{css,html}', { cwd: ROOT });

const errors = [];
const warnings = [];

for (const rel of targets) {
  const full = path.join(ROOT, rel);
  const src = fs.readFileSync(full, 'utf8');

  // R1: @page 以外での mm
  const stripped = src.replace(/@page\s*\{[^}]*\}/g, '');
  if (/\b\d+(\.\d+)?mm\b/.test(stripped)) {
    errors.push(`${rel}: mm used outside @page`);
  }

  // R2: px in CSS (SVG属性の data-px 系は html では別途除外)
  if (rel.endsWith('.css') && /[^"]\b\d+px\b/.test(src)) {
    errors.push(`${rel}: px used in CSS`);
  }

  // R4: @media print 内 font-size
  const printBlocks = src.match(/@media\s+print\s*\{[\s\S]*?\n\}/g) || [];
  for (const blk of printBlocks) {
    if (/font-size\s*:/.test(blk)) {
      errors.push(`${rel}: font-size override inside @media print`);
    }
  }

  // R5: rem warning
  if (/\b\d+(\.\d+)?rem\b/.test(src)) {
    warnings.push(`${rel}: rem detected (Phase B migration)`);
  }
}

console.log(JSON.stringify({ errors, warnings }, null, 2));
process.exit(errors.length ? 1 : 0);
```

### §6.3 CI/プリコミット連携

- `package.json` の `scripts.validate` に `node scripts/validate-units.js` を追加
- `scripts/check-consistency.js` の最後に呼び出してチェーン実行
- Phase C 移行時に `warn → error` を切替

---

## §7 例外と理由

| 例外 | 許容 | 理由 |
|------|------|------|
| SVG `viewBox` 内部の数値座標（`x`, `y`, `r`, `cx`, `font-size`, `stroke-width` 等） | OK | viewBox がスライド領域に伸縮するため、内部座標は単位無しで OK。画面・印刷で完全に同スケール |
| `@page { size: A4 landscape; margin: 0 }` の `mm` | OK | 印刷ページサイズの物理寸法定義はブラウザ仕様上 `mm` / `cm` / `in` のいずれかが必要 |
| `em` / `line-height: 1.5` 等の無単位 | OK | テキスト相対指定は font-size の vw が伝播するため問題なし |
| `%` （親要素相対） | OK | 比率指定は親要素のサイズに従うため、親が vw ベースなら自動的に正規化される |
| `calc(... * var(--font-scale))` の倍率変数 | OK | `--font-scale` は無次元の係数。基となる値が vw なら結果も vw |
| `rem`（移行期のみ） | △ | Phase B 終了まで暫定許容。Phase C で完全禁止 |

### §7.1 アンチパターン

```css
/* NG: 印刷時の上書き（差分発生源） */
@media print {
  .stat-value { font-size: 2rem; } /* ← 削除対象 */
}

/* NG: px でのレイアウト固定 */
.slide-card { padding: 24px; }

/* NG: 印刷専用 mm */
.slide-list { gap: 5mm; }
```

```css
/* OK: 単一の vw 値で画面・印刷を同時に賄う */
.stat-value { font-size: 6.25vw; }
.slide-card { padding: 1.25vw; }
.slide-list { gap: 1.00vw; }
```

---

## §8 関連ファイル

- `references/print-layout.md` — Phase C で§フォント縮小ルール（l.222-358）を削除し、本ファイルへのリンクに置換
- `references/theme-style.md` — `--fs-*` 定義を §3.1 の vw 値で更新
- `assets/print-styles.css` — §4.1 の @page 定義のみに簡素化
- `scripts/validate-units.js` — §6 で新設
- `scripts/validate-print.js` — R4（@media print 内 font-size）違反検出を追加

---

**改訂履歴**
- v1.0 初版（画面↔印刷の差分ゼロ化方針を確立）
