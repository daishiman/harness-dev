# ベストプラクティス分類・整理

> **目的**: SKILL.md l.165-204 のベストプラクティス表（37項目）を、機械検証可能 / テンプレ強制 / LLM判断 / 重複削除 の4カテゴリに分離し、LLMが暗記すべき項目を10条以下に圧縮する。
>
> **背景**: changelog v6.0 → v6.6 の各失敗事例修正で +30 項目が積み増され、表が肥大化。LLM が全項目を実装段階で参照できず形骸化リスクが高い。
>
> **方針**:
> - A: 機械検証 → `scripts/validate-structure.js` / `scripts/verify-slides.js` / `scripts/check-consistency.js` のチェック項目に変換し、人間が読む規則からは削除
> - B: テンプレ/共通CSS強制 → `assets/styles.css`・`scripts/html-scaffold.js` に埋め込み、原則として消す
> - C: LLM判断必須 → 簡潔な10条に圧縮し SKILL.md に残す
> - D: 重複・冗長 → 削除または `references/spec-registry.md`（新設想定）に SR-* ID で集約

---

## §1 現状の37項目（SKILL.md l.167-203 全列挙）

| # | すべきこと | 避けること | 出典/由来 |
|---|-----------|-----------|----------|
| 01 | structure.mdの共通仕様を忠実に実装 | structure.mdの仕様を無視してHTML生成 | v6.0 基本原則 |
| 02 | スライドタイプ→CSSクラス対応に従う | 独自のCSSクラス名を使う | v6.0 基本原則 |
| 03 | コードブロックはSF Mono/Fira Code | コードにNoto Sans JPを使う | v6.0 タイポグラフィ |
| 04 | Before/Afterは48%/48%/4%gap | Before/Afterの比率を変える | v6.2 失敗事例 |
| 05 | 補足テキストは最大3行/opacity:0.7 | 補足テキストを4行以上にする | v6.2 失敗事例 |
| 06 | 1スライド1メッセージ | 複数メッセージ詰め込み | v6.0 基本原則 |
| 07 | 図解で表現 | 長文をそのまま表示 | v6.0 基本原則 |
| 08 | 図解はインラインSVG2で描画 | CSS absoluteで図を配置 | v6.3 SVG2移行 |
| 09 | SVG fill/strokeにCSS変数使用 | SVG属性にカラーコード直書き | v6.3 SVG2移行 |
| 10 | CSS変数使用 | カラーコード直書き | v6.0 基本原則 |
| 11 | 写真・画像素材はWebP形式 | PNG/JPGを無変換で使用 | v6.1 画像最適化 |
| 12 | 20文字超は`<br>`挿入 | 不自然な自動改行 | v6.0 タイポグラフィ |
| 13 | フォント最小1.4rem | 1rem以下のフォント | v6.0 タイポグラフィ |
| 14 | CSS/JS分離出力 | インラインCSS/JS | v6.0 出力形式 |
| 15 | 背景→質問の順で配置 | 質問を背景情報の前に配置 | v6.4 構成順序 |
| 16 | 質問スライドはfs-subheading | 質問にfs-heading（大きすぎ） | v6.4 構成順序 |
| 17 | 印刷=画面と同じレイアウト | 印刷時にレイアウト構造を変更 | v6.5 印刷対応 |
| 18 | A4横フルサイズ（余白・枠線なし） | 余白margin: 8mm+や枠線border | v6.5 印刷対応 |
| 19 | セクション目次ナビ常時表示 | セクション表示なし／ドット+ラベルのみ | v6.5 ナビ |
| 20 | ページネーション5個区切りマイルストーン | 単色ドットのみ（nth-child(5n)区切り必須） | v6.5 ナビ |
| 21 | 印刷カード比率=画面と同一 | 印刷時にpadding/font/gap等を極端に縮小 | v6.5 印刷対応 |
| 22 | 印刷CSS GSAPスタイルリセット | 印刷時にGSAPインラインstyleが残って非表示 | v6.6 GSAP事故 |
| 23 | GSAP fromでscale最小0.8 | scale:0やscale:0.5（残留transformで要素消失） | v6.6 GSAP事故 |
| 24 | clearPropsはcontent.childrenのみに適用 | querySelectorAll('*')でclearProps（SVG/foreignObject破壊） | v6.6 GSAP事故 |
| 25 | foreignObject内divはclass="fo-card"で保護 | foreignObject内divにインラインstyle（clearPropsで消失） | v6.6 GSAP事故 |
| 26 | ビビッドアクセント各スライド1つ以上 | Lotus原色のみで彩度不足 | v6.4 デザイン |
| 27 | イージング3種以上使い分け | 全要素同一ease | v6.4 デザイン |
| 28 | focus-visible + reduced-motion | アクセシビリティ未対応 | v6.4 a11y |
| 29 | UIテキストopacity 0.6以上 | opacity 0.3等で読めない | v6.4 a11y |
| 30 | SVGテキストは13px以上（対面大画面必須） | SVG `<text>`に11px以下（プロジェクタで不可視） | v6.6 大画面検証 |
| 31 | SVG内はFA unicode禁止・foreignObject+`<i>`またはemoji使用 | SVG `<text>`に`&#xf...;`（CDN未ロード時消失） | v6.6 アイコン事故 |
| 32 | 全スライドタイプにh2 CSS定義必須（slide-quote/slide-message等） | 特定スライドタイプのh2定義を省略（極小表示） | v6.6 CSS網羅 |
| 33 | section-nav CSS定義がHTML全セクションを網羅 | data-section値の一部がCSS未定義（ナビ色表示なし） | v6.6 CSS網羅 |
| 34 | code-block max-heightは420pxで全回統一 | 回ごとに340px等の不統一 | v6.6 一貫性 |
| 35 | list-item/ig-itemにwidth:100%;box-sizing:border-box | width指定なしでカード左寄り半幅表示 | v6.6 レイアウト事故 |
| 36 | （Noto Sans JP明示） | （和欧混植の不備） | v6.0 タイポ（13と一部重複） |
| 37 | （CSS変数：色直書き禁止） | （カラーハードコード） | v6.0 基本（10と重複） |

> 注: 36/37 は 13/10 と意味的に重なるため §2-D で集約。

---

## §2 分類結果

### A. 機械検証へ移行（→ `validate-structure.js` / `verify-slides.js` / `check-consistency.js`）

人間が暗記する必要がない、コードで自動チェック可能な項目。

| 元# | 項目 | 検証方法 | 検証ID（提案） | 配置先スクリプト |
|----|------|----------|----------------|------------------|
| 04 | Before/After 48%/48%/4%gap | CSS regex（`.before, .after { width: 48% }` / `gap: 4%`） | V-001 | check-consistency.js |
| 05 | 補足テキスト最大3行 | DOM: `.supplement` の `<br>` 個数 ≤ 2 / textContent行数 | V-002 | verify-slides.js |
| 13 | フォント最小1.4rem | computed font-size ≥ 22.4px をPuppeteerで全要素測定 | V-003 | verify-slides.js |
| 21 | 印刷=画面同一比率 | screen / print 両mediaでvw比較、padding/gap差分閾値内 | V-004 | verify-slides.js |
| 34 | code-block max-height 420px | CSS regex（`.code-block { max-height: 420px }`） | V-005 | check-consistency.js |
| 23 | GSAP scale最小0.8 | scripts.js regex（`scale:\s*0?\.[0-7]` を検出して警告） | V-006 | check-consistency.js |
| 30 | SVGテキスト13px以上 | DOM: `<text>` の computed font-size ≥ 13px | V-007 | verify-slides.js |
| 31 | SVG内FA unicode禁止 | SVG内 `<text>` に `&#xf` を含まない | V-008 | check-consistency.js |
| 32 | 全スライドタイプにh2 CSS定義 | 出現 `slide-*` クラスごとに `h2` セレクタが styles.css に存在 | V-009 | check-consistency.js |
| 33 | section-nav 全セクション網羅 | HTML 中の `data-section` 値 ⊆ CSS の `[data-section="..."]` セレクタ | V-010 | check-consistency.js |
| 35 | list-item/ig-item に width:100%/box-sizing | CSS regex（該当クラスに width:100%; box-sizing:border-box;） | V-011 | check-consistency.js |
| 18 | A4横フルサイズ余白なし | `@page { size: A4 landscape; margin: 0 }` の存在 | V-012 | validate-print.js（既存） |
| 17 | 印刷=画面同レイアウト | 印刷mediaで `display:none` 構造変更がない（許容: 装飾系のみ） | V-013 | validate-print.js |
| 22 | 印刷CSS GSAPリセット | `@media print { .gsap-target { transform:none !important; opacity:1 !important; } }` 存在 | V-014 | validate-print.js |
| 24 | clearPropsはcontent.childrenのみ | scripts.js: `clearProps:.*"\*"` または `querySelectorAll\('\*'\)` 検出時エラー | V-015 | check-consistency.js |
| 25 | foreignObject内 fo-card class | SVG `<foreignObject> > div:not(.fo-card)` を検出 | V-016 | check-consistency.js |
| 09 | SVG fill/strokeにCSS変数 | SVG `fill="#..."` / `stroke="#..."` 直書き検出 | V-017 | check-consistency.js |
| 10 | CSS変数使用（色直書き禁止） | styles.css 中の `#[0-9a-f]{3,6}` 出現を `:root` 定義以外で検出 | V-018 | check-consistency.js |
| 11 | 画像WebP形式 | `<img src>` / CSS `url()` の拡張子 .webp 確認 | V-019 | check-consistency.js |
| 14 | CSS/JS分離出力 | `<style>` / `<script>` インラインタグの非存在（外部参照のみ） | V-020 | check-consistency.js |
| 12 | 20文字超は`<br>` | テキストノード20文字超で `<br>` 不在を警告（heuristic） | V-021 | verify-slides.js |
| 29 | UIテキスト opacity ≥ 0.6 | computed opacity の最小値スキャン | V-022 | verify-slides.js |
| 28 | focus-visible + reduced-motion | CSS に `:focus-visible` / `@media (prefers-reduced-motion)` ブロック存在 | V-023 | check-consistency.js |
| 03 | コードはSF Mono/Fira Code | `.code-block` 系の computed font-family に Mono系含む | V-024 | verify-slides.js |
| 02 | 標準CSSクラス名のみ | `class=` 値が許可リスト（slide-types-overview）に含まれる | V-025 | validate-structure.js |
| 16 | 質問は fs-subheading | スライドタイプ=質問 のスライドで `fs-heading` クラス不在 | V-026 | check-consistency.js |
| 19 | section-nav 常時表示 | 各 `<section>` に `.section-nav` が存在し `display:none` でない | V-027 | verify-slides.js |
| 20 | ページネーション5個区切り | `.pagination li:nth-child(5n)` のスタイル定義が styles.css に存在 | V-028 | check-consistency.js |
| 08 | SVG2インライン描画 | スライド内に `<svg>` インライン存在、`position:absolute` での図要素検出時警告 | V-029 | check-consistency.js |
| 15 | 背景→質問の順 | structure.json の slide types 配列順序検証（背景系 index < 質問系 index） | V-030 | validate-structure.js |
| 新規 | コード系 slideType は aiVisual で image-only / baked-with-overlay 不可（コードは実HTMLコードブロックで描画） | structure.json: slideType ∈ {slide-code, slide-code-compare} かつ aiVisual.pattern=image-only または textPolicy=baked-with-overlay を検出 | V-043 | validate-structure.js |

**A合計: 31項目**（V-001〜V-030 + V-043。V-031〜V-038 は v8 拡張で別枠）

### B. テンプレート/CSSで強制（→ `assets/styles.css` 共通化 / `scripts/html-scaffold.js` 自動生成）

LLM が毎回書くのではなく、scaffold 時点で出力に埋め込まれるべき項目。

| 元# | 項目 | 強制方法 |
|----|------|----------|
| 19 | section-nav 全セクション網羅 | `html-scaffold.js` が structure.json から自動生成（人手記述させない） |
| 20 | 5個区切りマイルストーン pagination | 共通 `.pagination` テンプレで `nth-child(5n)` ルール固定 |
| 35 | list-item/ig-item width:100%/box-sizing | 共通CSSクラスとして styles.css に固定済（LLMが書かない） |
| 18 | A4横フルサイズ印刷 | styles.css 共通 `@page` 定義、変更不可 |
| 22 | 印刷GSAPリセット | styles.css 共通 `@media print` ブロック固定 |
| 28 | focus-visible / reduced-motion | styles.css 共通 a11y ブロック固定 |
| 25 | foreignObject `.fo-card` クラス | svg-diagram-primitives テンプレ内で必須化、スニペット提供 |
| 34 | code-block max-height 420px | styles.css 固定値、変更禁止 |

**B合計: 8項目**

### C. LLM判断が必要（→ SKILL.md に簡潔10条として残す）

文脈・意図・コンテンツによって LLM が都度判断する必要がある原則。これだけは暗記対象。

1. **1スライド1メッセージ**（情報密度の判断はLLM）
2. **長文は図解化**（テキスト → SVG2図解への変換判断）
3. **背景 → 質問の順で配置**（構成順序の意図設計）
4. **ビビッドアクセントを各スライド1箇所以上**（どこに置くかは構図判断）
5. **補足テキストは最大3行・opacity 0.7**（何を補足にするかの取捨）
6. **20文字超は`<br>`で意図的改行**（意味の切れ目はLLM判断）
7. **色・サイズはCSS変数経由**（直書き禁止）
8. **本文 Noto Sans JP / コード SF Mono・Fira Code**（和欧混植判断）
9. **画像は WebP**（素材選定時の方針）
10. **イージング3種以上を使い分け**（演出意図の設計）

**C合計: 10項目**

### D. 削除/集約（→ `references/spec-registry.md` SR-* ID で参照）

重複・冗長または既存仕様書で定義済みの項目。BP表からは削除。

| 元# | 項目 | 集約先 | SR-ID（提案） |
|----|------|--------|---------------|
| 01 | structure.md仕様を忠実に実装 | structure.md 自体が一次ソース | SR-001 |
| 02 | タイプ→CSSクラス対応に従う | slide-types-overview.md の対応表 | SR-002（A-V-025と二重管理せず参照のみ） |
| 06 | 1スライド1メッセージ | C-1 と同一 | C-1 へ集約 |
| 07 | 図解で表現 | C-2 と同一 | C-2 へ集約 |
| 26 | ビビッドアクセント | C-4 と同一 | C-4 へ集約 |
| 27 | イージング3種以上 | C-10 と同一 | C-10 へ集約 |
| 36 | Noto Sans JP（潜在重複） | C-8 へ集約 | C-8 |
| 37 | CSS変数（色直書き禁止） | C-7 と A-V-018 で二重カバー、表からは削除 | C-7 / V-018 |

**D合計: 8項目**（うち6項目はC/Aへ統合、2項目は references 側へ移動）

> **検算**: A30 + B8 + C10 + D8 = 56。元37項目に対し A/B が一部重複カバー（例: #18, #19, #20, #22, #25, #28, #34, #35 は機械検証もテンプレ強制も両方適用）。重複カウントを除いた一意項目は 37 で整合。

---

## §3 移行後の SKILL.md（差分提案）

### 削除対象
- 現 SKILL.md l.165-204（「ベストプラクティス」表全体、37項目）

### 置換後（新ベストプラクティス節・10条）

```markdown
## ベストプラクティス（LLM判断10条）

下記10項目は LLM が文脈に応じて判断する原則。機械検証可能な項目（48%/48%, font-size ≥ 1.4rem 等）は `scripts/check-consistency.js` / `verify-slides.js` で自動検証され、テンプレ強制項目（section-nav, pagination, @page A4 等）は `assets/styles.css` / `scripts/html-scaffold.js` に埋め込まれているため、ここでは原則のみを示す。

| # | 原則 | 補足 |
|---|------|------|
| 1 | 1スライド1メッセージ | 情報密度を抑え、複数論点は分割 |
| 2 | 長文は図解化 | SVG2 で構造表現（references/svg-diagram-primitives.md） |
| 3 | 背景 → 質問の順で配置 | 質問は fs-subheading |
| 4 | ビビッドアクセント各1箇所以上 | Lotus原色のみは禁止 |
| 5 | 補足テキスト最大3行・opacity 0.7 | 取捨選択は LLM 判断 |
| 6 | 20文字超は `<br>` で意図改行 | 自動折返しに任せない |
| 7 | 色・サイズは CSS 変数経由 | カラー直書き禁止 |
| 8 | 本文 Noto Sans JP / コード SF Mono・Fira Code | 和欧混植の整合 |
| 9 | 画像素材は WebP | scripts/convert-to-webp.js |
| 10 | イージング3種以上使い分け | 全要素同一 ease 禁止 |

**詳細・拡張**:
- 機械検証項目（V-001〜V-030）: [references/bp-classification.md §2-A](bp-classification.md)
- テンプレ強制項目: [references/bp-classification.md §2-B](bp-classification.md)
- 仕様レジストリ（SR-*）: references/spec-registry.md（新設）
```

### 影響範囲
- `agents/ui-quality-reviewer.md`: S1-S26 の検証項目と V-001〜V-030 のマッピング表追加（別タスク）
- `references/changelog.md`: v6.7 として「BP表を10条＋機械検証30項目に再構成」エントリ追加（別タスク）

---

## §4 効果見積もり

| 指標 | Before | After | 削減率 |
|------|--------|-------|--------|
| LLMが暗記すべき規則 | 37項目 | 10項目 | **73%削減** |
| 機械検証可能な項目（V-*） | 約8項目（既存 verify-slides.js 程度） | +30項目（V-001〜V-030）＋V-043（コード非画像化, SR-13-01） | +275% |
| テンプレ/CSS強制（書かなくて良い） | 0項目 | 8項目 | 新規 |
| SKILL.md 行数（l.165-204） | 40行（表本体） | 約20行（10条＋参照） | 50%削減 |
| 失敗事例の再発防止 | 人手レビュー依存 | check-consistency.js / verify-slides.js で自動検出 | 自動化率 +80% |

### 副次効果
- 新規失敗事例が出ても **BP表に追加せず** 検証スクリプトに V-031, V-032... として追加する運用に移行可能（表の肥大を恒久的に防止）。実例: V-043（コード系 slideType の画像焼き込み禁止, SR-13-01）はこの運用で追加した
- LLM がプロンプト内で BP を素早く参照でき、生成時の規則違反が減る
- ui-quality-reviewer エージェントの S1-S26 と V-* を統合することで、レビュー品質が向上

---

## §5 次アクション（参考・このファイル外）

1. `scripts/check-consistency.js` に V-001, V-005, V-008, V-010, V-011, V-014〜V-020, V-023, V-026, V-028, V-029 を追加実装
2. `scripts/verify-slides.js` に V-002, V-003, V-007, V-013, V-021, V-022, V-024, V-027 を追加実装
3. `scripts/validate-structure.js` に V-025, V-030 を追加実装
4. `scripts/validate-print.js` に V-012, V-013, V-014 を追加実装
5. `references/spec-registry.md` を新設し SR-001, SR-002 を登録
6. SKILL.md l.165-204 を §3 の置換後内容に差し替え
7. `agents/ui-quality-reviewer.md` の S1-S26 と V-* のマッピング表を追加
8. `references/changelog.md` に v6.7 エントリを追加
