# FABE型（商品・サービス紹介フレームワーク）

**責務**: FABE型スライドの5種レイアウトバリエーション、CSS、HTML、アニメーション

---

## 概要

特徴（Feature）→ 利点（Advantage）→ ベネフィット（Benefit）→ 証拠（Evidence）の4段階で商品・サービスを説明。セールスプレゼン・製品紹介・提案資料に最適。

**レイアウトバリエーション**:
| バリエーション | クラス | 特徴 |
|--------------|--------|------|
| 横フロー型 | `slide-fabe` | デフォルト、プログレスラインあり |
| 縦スタック型 | `slide-fabe fabe-vertical` | 縦並び、ラインフィルアニメ |
| 2×2グリッド型 | `slide-fabe fabe-grid` | 中央回転インジケータ |
| タイムライン型 | `slide-fabe fabe-timeline` | ジグザグ配置 |
| 円形配置型 | `slide-fabe fabe-circular` | 軌道アニメーション |

---

## 1. 基本CSS（共通スタイル）

```css
/* ===== FABE型 共通スタイル ===== */
.slide-fabe .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
  position: relative;
}

.slide-fabe .fabe-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slide-fabe .fabe-title i {
  color: var(--wave-blue);
}

.slide-fabe .fabe-subtitle {
  font-size: var(--fs-body);
  color: var(--fg-dim);
  text-align: center;
  margin-top: -1rem;
}

/* カード共通スタイル */
.slide-fabe .fabe-card {
  background: var(--bg-dim);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  position: relative;
  overflow: hidden;
}

.slide-fabe .fabe-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, transparent, var(--card-accent), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.slide-fabe .fabe-card:hover::before {
  opacity: 1;
}

.slide-fabe .fabe-card:hover {
  transform: translateY(-8px) scale(1.02);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
}

/* カード別アクセントカラー */
.slide-fabe .fabe-card.feature {
  border-bottom: 4px solid var(--wave-blue);
  --card-accent: var(--wave-blue);
}
.slide-fabe .fabe-card.advantage {
  border-bottom: 4px solid var(--spring-green);
  --card-accent: var(--spring-green);
}
.slide-fabe .fabe-card.benefit {
  border-bottom: 4px solid var(--autumn-yellow);
  --card-accent: var(--autumn-yellow);
}
.slide-fabe .fabe-card.evidence {
  border-bottom: 4px solid var(--sakura-pink);
  --card-accent: var(--sakura-pink);
}

/* ステップ番号バッジ */
.slide-fabe .fabe-step-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 700;
  z-index: 5;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.slide-fabe .fabe-card.feature .fabe-step-badge { background: var(--wave-blue); color: #fff; }
.slide-fabe .fabe-card.advantage .fabe-step-badge { background: var(--spring-green); color: #1f1f28; }
.slide-fabe .fabe-card.benefit .fabe-step-badge { background: var(--autumn-yellow); color: #1f1f28; }
.slide-fabe .fabe-card.evidence .fabe-step-badge { background: var(--sakura-pink); color: #fff; }

/* アイコンサークル */
.slide-fabe .fabe-icon-wrap {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 0.5rem;
  font-size: 1.8rem;
  position: relative;
  transition: transform 0.3s ease;
}

.slide-fabe .fabe-card:hover .fabe-icon-wrap {
  transform: scale(1.1) rotate(5deg);
}

/* アイコン背景グラデーション */
.slide-fabe .fabe-card.feature .fabe-icon-wrap {
  background: linear-gradient(135deg, rgba(126, 156, 216, 0.3), rgba(126, 156, 216, 0.1));
  color: var(--wave-blue);
  box-shadow: 0 4px 20px rgba(126, 156, 216, 0.3);
}
.slide-fabe .fabe-card.advantage .fabe-icon-wrap {
  background: linear-gradient(135deg, rgba(152, 187, 108, 0.3), rgba(152, 187, 108, 0.1));
  color: var(--spring-green);
  box-shadow: 0 4px 20px rgba(152, 187, 108, 0.3);
}
.slide-fabe .fabe-card.benefit .fabe-icon-wrap {
  background: linear-gradient(135deg, rgba(220, 165, 97, 0.3), rgba(220, 165, 97, 0.1));
  color: var(--autumn-yellow);
  box-shadow: 0 4px 20px rgba(220, 165, 97, 0.3);
}
.slide-fabe .fabe-card.evidence .fabe-icon-wrap {
  background: linear-gradient(135deg, rgba(228, 104, 118, 0.3), rgba(228, 104, 118, 0.1));
  color: var(--sakura-pink);
  box-shadow: 0 4px 20px rgba(228, 104, 118, 0.3);
}

/* パルスアニメーション */
.slide-fabe .fabe-icon-wrap::after {
  content: '';
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid var(--card-accent);
  animation: fabe-pulse 2s ease-out infinite;
  opacity: 0;
}

@keyframes fabe-pulse {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.5); opacity: 0; }
}

/* ラベル */
.slide-fabe .fabe-label {
  font-size: var(--fs-small);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  text-align: center;
}

.slide-fabe .fabe-card.feature .fabe-label { color: var(--wave-blue); }
.slide-fabe .fabe-card.advantage .fabe-label { color: var(--spring-green); }
.slide-fabe .fabe-card.benefit .fabe-label { color: var(--autumn-yellow); }
.slide-fabe .fabe-card.evidence .fabe-label { color: var(--sakura-pink); }

/* 日本語サブラベル */
.slide-fabe .fabe-label-jp {
  font-size: 0.75rem;
  color: var(--fg-dim);
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
}

/* 見出し */
.slide-fabe .fabe-heading {
  font-size: var(--fs-body-lg);
  font-weight: 700;
  text-align: center;
  line-height: 1.4;
}

/* 説明テキスト */
.slide-fabe .fabe-desc {
  font-size: var(--fs-body);
  color: var(--fg-dim);
  text-align: center;
  line-height: 1.6;
}

/* ポイントリスト */
.slide-fabe .fabe-points {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.slide-fabe .fabe-points li {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

.slide-fabe .fabe-points li i {
  margin-top: 0.2rem;
  color: var(--card-accent);
}

/* 矢印コネクター */
.slide-fabe .fabe-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  color: var(--fuji-gray);
  position: relative;
}

.slide-fabe .fabe-arrow::before {
  content: '';
  position: absolute;
  width: 40px;
  height: 2px;
  background: linear-gradient(90deg, var(--fuji-gray), transparent);
}

/* Evidence用統計ハイライト */
.slide-fabe .fabe-evidence-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.5rem;
  padding: 1rem;
  background: linear-gradient(135deg, rgba(228, 104, 118, 0.15), rgba(228, 104, 118, 0.05));
  border-radius: 12px;
  border: 1px solid rgba(228, 104, 118, 0.3);
}

.slide-fabe .fabe-stat-value {
  font-size: var(--fs-subheading);
  font-weight: 700;
  color: var(--sakura-pink);
}

.slide-fabe .fabe-stat-label {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* 複数統計表示 */
.slide-fabe .fabe-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.slide-fabe .fabe-stat-item {
  text-align: center;
  padding: 0.5rem;
  background: rgba(228, 104, 118, 0.1);
  border-radius: 8px;
}

.slide-fabe .fabe-stat-item .value {
  font-size: var(--fs-body-lg);
  font-weight: 700;
  color: var(--sakura-pink);
}

.slide-fabe .fabe-stat-item .label {
  font-size: 0.7rem;
  color: var(--fg-dim);
}
```

---

## 2. 横フロー型（デフォルト）

```css
/* ===== 横フロー型 ===== */
.slide-fabe .fabe-container {
  display: flex;
  gap: 0.5rem;
  width: 100%;
  max-width: 1050px;
  align-items: stretch;
  position: relative;
}

.slide-fabe .fabe-container .fabe-card {
  flex: 1;
  min-width: 200px;
}

/* プログレスライン（背景） */
.slide-fabe .fabe-progress-line {
  position: absolute;
  top: 50%;
  left: 5%;
  right: 5%;
  height: 3px;
  background: var(--fuji-gray);
  transform: translateY(-50%);
  z-index: 0;
  border-radius: 2px;
}

.slide-fabe .fabe-progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, var(--wave-blue), var(--spring-green), var(--autumn-yellow), var(--sakura-pink));
  border-radius: 2px;
  width: 0;
  transition: width 1.5s ease-out;
}

.slide-fabe.is-active .fabe-progress-fill {
  width: 100%;
}
```

```html
<!-- 横フロー型（デフォルト） -->
<div class="slider__item slide-fabe">
  <div class="slider__content">
    <h2 class="fabe-title"><i class="fas fa-gem"></i> {{タイトル}}</h2>
    <p class="fabe-subtitle">{{サブタイトル}}</p>

    <div class="fabe-container">
      <!-- プログレスライン -->
      <div class="fabe-progress-line">
        <div class="fabe-progress-fill"></div>
      </div>

      <div class="fabe-card feature has-tooltip" data-tooltip="{{Feature詳細}}">
        <div class="fabe-step-badge">1</div>
        <div class="fabe-icon-wrap"><i class="fas fa-cogs"></i></div>
        <div class="fabe-label">Feature<span class="fabe-label-jp">（特徴）</span></div>
        <div class="fabe-heading">{{特徴タイトル}}</div>
        <div class="fabe-desc">{{特徴の説明}}</div>
        <ul class="fabe-points">
          <li><i class="fas fa-check"></i>{{ポイント1}}</li>
          <li><i class="fas fa-check"></i>{{ポイント2}}</li>
        </ul>
      </div>

      <div class="fabe-arrow"><i class="fas fa-chevron-right"></i></div>

      <div class="fabe-card advantage has-tooltip" data-tooltip="{{Advantage詳細}}">
        <div class="fabe-step-badge">2</div>
        <div class="fabe-icon-wrap"><i class="fas fa-chart-line"></i></div>
        <div class="fabe-label">Advantage<span class="fabe-label-jp">（利点）</span></div>
        <div class="fabe-heading">{{利点タイトル}}</div>
        <div class="fabe-desc">{{利点の説明}}</div>
        <ul class="fabe-points">
          <li><i class="fas fa-check"></i>{{ポイント1}}</li>
          <li><i class="fas fa-check"></i>{{ポイント2}}</li>
        </ul>
      </div>

      <div class="fabe-arrow"><i class="fas fa-chevron-right"></i></div>

      <div class="fabe-card benefit has-tooltip" data-tooltip="{{Benefit詳細}}">
        <div class="fabe-step-badge">3</div>
        <div class="fabe-icon-wrap"><i class="fas fa-heart"></i></div>
        <div class="fabe-label">Benefit<span class="fabe-label-jp">（便益）</span></div>
        <div class="fabe-heading">{{ベネフィットタイトル}}</div>
        <div class="fabe-desc">{{ベネフィットの説明}}</div>
        <ul class="fabe-points">
          <li><i class="fas fa-check"></i>{{ポイント1}}</li>
          <li><i class="fas fa-check"></i>{{ポイント2}}</li>
        </ul>
      </div>

      <div class="fabe-arrow"><i class="fas fa-chevron-right"></i></div>

      <div class="fabe-card evidence has-tooltip" data-tooltip="{{Evidence詳細}}">
        <div class="fabe-step-badge">4</div>
        <div class="fabe-icon-wrap"><i class="fas fa-award"></i></div>
        <div class="fabe-label">Evidence<span class="fabe-label-jp">（証拠）</span></div>
        <div class="fabe-heading">{{証拠タイトル}}</div>
        <div class="fabe-stats-grid">
          <div class="fabe-stat-item">
            <div class="value">{{数値1}}</div>
            <div class="label">{{ラベル1}}</div>
          </div>
          <div class="fabe-stat-item">
            <div class="value">{{数値2}}</div>
            <div class="label">{{ラベル2}}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

---

## 3. 縦スタック型

```css
/* ===== 縦スタック型 ===== */
.slide-fabe.fabe-vertical .fabe-container {
  flex-direction: column;
  max-width: 700px;
  gap: 0;
}

.slide-fabe.fabe-vertical .fabe-card {
  flex-direction: row;
  align-items: center;
  gap: 1.5rem;
  padding: 1.25rem 1.5rem;
  border-bottom: none;
  border-left: 5px solid var(--card-accent);
  border-radius: 0 16px 16px 0;
}

.slide-fabe.fabe-vertical .fabe-card:hover {
  transform: translateX(10px);
}

.slide-fabe.fabe-vertical .fabe-step-badge {
  position: relative;
  top: auto;
  left: auto;
  transform: none;
  flex-shrink: 0;
}

.slide-fabe.fabe-vertical .fabe-icon-wrap {
  margin: 0;
  flex-shrink: 0;
  width: 60px;
  height: 60px;
  font-size: 1.5rem;
}

.slide-fabe.fabe-vertical .fabe-card-content {
  flex: 1;
  text-align: left;
}

.slide-fabe.fabe-vertical .fabe-label,
.slide-fabe.fabe-vertical .fabe-heading,
.slide-fabe.fabe-vertical .fabe-desc {
  text-align: left;
}

.slide-fabe.fabe-vertical .fabe-arrow {
  transform: rotate(90deg);
  padding: 0.5rem 0;
}

/* 縦ライン */
.slide-fabe.fabe-vertical .fabe-vertical-line {
  position: absolute;
  left: 28px;
  top: 10%;
  bottom: 10%;
  width: 3px;
  background: var(--fuji-gray);
  z-index: 0;
}

.slide-fabe.fabe-vertical .fabe-vertical-line .fill {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 0;
  background: linear-gradient(180deg, var(--wave-blue), var(--sakura-pink));
  transition: height 1.5s ease-out;
}

.slide-fabe.fabe-vertical.is-active .fabe-vertical-line .fill {
  height: 100%;
}
```

```html
<!-- 縦スタック型 -->
<div class="slider__item slide-fabe fabe-vertical">
  <div class="slider__content">
    <h2 class="fabe-title"><i class="fas fa-gem"></i> {{タイトル}}</h2>

    <div class="fabe-container">
      <div class="fabe-vertical-line"><div class="fill"></div></div>

      <div class="fabe-card feature">
        <div class="fabe-step-badge">F</div>
        <div class="fabe-icon-wrap"><i class="fas fa-cogs"></i></div>
        <div class="fabe-card-content">
          <div class="fabe-label">Feature<span class="fabe-label-jp">（特徴）</span></div>
          <div class="fabe-heading">{{特徴タイトル}}</div>
          <div class="fabe-desc">{{特徴の説明}}</div>
        </div>
      </div>

      <div class="fabe-card advantage">
        <div class="fabe-step-badge">A</div>
        <div class="fabe-icon-wrap"><i class="fas fa-chart-line"></i></div>
        <div class="fabe-card-content">
          <div class="fabe-label">Advantage<span class="fabe-label-jp">（利点）</span></div>
          <div class="fabe-heading">{{利点タイトル}}</div>
          <div class="fabe-desc">{{利点の説明}}</div>
        </div>
      </div>

      <div class="fabe-card benefit">
        <div class="fabe-step-badge">B</div>
        <div class="fabe-icon-wrap"><i class="fas fa-heart"></i></div>
        <div class="fabe-card-content">
          <div class="fabe-label">Benefit<span class="fabe-label-jp">（便益）</span></div>
          <div class="fabe-heading">{{ベネフィットタイトル}}</div>
          <div class="fabe-desc">{{ベネフィットの説明}}</div>
        </div>
      </div>

      <div class="fabe-card evidence">
        <div class="fabe-step-badge">E</div>
        <div class="fabe-icon-wrap"><i class="fas fa-award"></i></div>
        <div class="fabe-card-content">
          <div class="fabe-label">Evidence<span class="fabe-label-jp">（証拠）</span></div>
          <div class="fabe-heading">{{証拠タイトル}}</div>
          <div class="fabe-evidence-stat">
            <div class="fabe-stat-value">{{数値}}</div>
            <div class="fabe-stat-label">{{数値ラベル}}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

---

## 4. 2×2グリッド型

```css
/* ===== 2×2グリッド型 ===== */
.slide-fabe.fabe-grid .fabe-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
  max-width: 900px;
}

.slide-fabe.fabe-grid .fabe-card {
  min-height: 200px;
}

.slide-fabe.fabe-grid .fabe-arrow {
  display: none;
}

/* グリッド中央のフローインジケーター */
.slide-fabe.fabe-grid .fabe-grid-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 60px;
  height: 60px;
  background: var(--sumi-ink);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  box-shadow: 0 5px 20px rgba(0, 0, 0, 0.4);
}

.slide-fabe.fabe-grid .fabe-grid-center i {
  font-size: 1.5rem;
  color: var(--wave-blue);
  animation: fabe-rotate 8s linear infinite;
}

@keyframes fabe-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* コーナー装飾 */
.slide-fabe.fabe-grid .fabe-card::after {
  content: '';
  position: absolute;
  width: 30px;
  height: 30px;
  border: 2px solid var(--card-accent);
  opacity: 0.3;
}

.slide-fabe.fabe-grid .fabe-card.feature::after { bottom: -15px; right: -15px; border-top: none; border-left: none; }
.slide-fabe.fabe-grid .fabe-card.advantage::after { bottom: -15px; left: -15px; border-top: none; border-right: none; }
.slide-fabe.fabe-grid .fabe-card.benefit::after { top: -15px; right: -15px; border-bottom: none; border-left: none; }
.slide-fabe.fabe-grid .fabe-card.evidence::after { top: -15px; left: -15px; border-bottom: none; border-right: none; }
```

```html
<!-- 2×2グリッド型 -->
<div class="slider__item slide-fabe fabe-grid">
  <div class="slider__content">
    <h2 class="fabe-title"><i class="fas fa-gem"></i> {{タイトル}}</h2>

    <div class="fabe-container">
      <!-- 中央インジケーター -->
      <div class="fabe-grid-center"><i class="fas fa-sync-alt"></i></div>

      <div class="fabe-card feature">
        <div class="fabe-step-badge">F</div>
        <div class="fabe-icon-wrap"><i class="fas fa-cogs"></i></div>
        <div class="fabe-label">Feature</div>
        <div class="fabe-heading">{{特徴}}</div>
        <div class="fabe-desc">{{特徴の説明}}</div>
      </div>

      <div class="fabe-card advantage">
        <div class="fabe-step-badge">A</div>
        <div class="fabe-icon-wrap"><i class="fas fa-chart-line"></i></div>
        <div class="fabe-label">Advantage</div>
        <div class="fabe-heading">{{利点}}</div>
        <div class="fabe-desc">{{利点の説明}}</div>
      </div>

      <div class="fabe-card benefit">
        <div class="fabe-step-badge">B</div>
        <div class="fabe-icon-wrap"><i class="fas fa-heart"></i></div>
        <div class="fabe-label">Benefit</div>
        <div class="fabe-heading">{{ベネフィット}}</div>
        <div class="fabe-desc">{{ベネフィットの説明}}</div>
      </div>

      <div class="fabe-card evidence">
        <div class="fabe-step-badge">E</div>
        <div class="fabe-icon-wrap"><i class="fas fa-award"></i></div>
        <div class="fabe-label">Evidence</div>
        <div class="fabe-heading">{{証拠}}</div>
        <div class="fabe-evidence-stat">
          <div class="fabe-stat-value">{{数値}}</div>
          <div class="fabe-stat-label">{{数値ラベル}}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

---

## 5. タイムライン型

```css
/* ===== タイムライン型 ===== */
.slide-fabe.fabe-timeline .fabe-container {
  flex-direction: column;
  max-width: 100%;
  gap: 0;
  padding: 2rem 0;
}

.slide-fabe.fabe-timeline .fabe-timeline-row {
  display: flex;
  align-items: center;
  position: relative;
}

.slide-fabe.fabe-timeline .fabe-timeline-row:nth-child(odd) {
  flex-direction: row;
}

.slide-fabe.fabe-timeline .fabe-timeline-row:nth-child(even) {
  flex-direction: row-reverse;
}

.slide-fabe.fabe-timeline .fabe-card {
  flex: 0 0 45%;
  border-bottom: none;
  border-radius: 16px;
}

.slide-fabe.fabe-timeline .fabe-timeline-row:nth-child(odd) .fabe-card {
  border-right: 5px solid var(--card-accent);
}

.slide-fabe.fabe-timeline .fabe-timeline-row:nth-child(even) .fabe-card {
  border-left: 5px solid var(--card-accent);
}

/* タイムラインの中央軸 */
.slide-fabe.fabe-timeline .fabe-timeline-axis {
  flex: 0 0 10%;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}

.slide-fabe.fabe-timeline .fabe-timeline-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--card-accent);
  z-index: 5;
  box-shadow: 0 0 0 4px var(--bg-dim), 0 0 0 6px var(--card-accent);
}

.slide-fabe.fabe-timeline .fabe-timeline-line {
  width: 3px;
  height: 60px;
  background: linear-gradient(180deg, var(--card-accent), var(--fuji-gray));
}

/* コネクター線 */
.slide-fabe.fabe-timeline .fabe-timeline-connector {
  flex: 1;
  height: 2px;
  background: linear-gradient(90deg, var(--card-accent), transparent);
}

.slide-fabe.fabe-timeline .fabe-timeline-row:nth-child(even) .fabe-timeline-connector {
  background: linear-gradient(90deg, transparent, var(--card-accent));
}
```

```html
<!-- タイムライン型 -->
<div class="slider__item slide-fabe fabe-timeline">
  <div class="slider__content">
    <h2 class="fabe-title"><i class="fas fa-gem"></i> {{タイトル}}</h2>

    <div class="fabe-container">
      <div class="fabe-timeline-row">
        <div class="fabe-card feature">
          <div class="fabe-icon-wrap"><i class="fas fa-cogs"></i></div>
          <div class="fabe-label">Feature</div>
          <div class="fabe-heading">{{特徴}}</div>
          <div class="fabe-desc">{{特徴の説明}}</div>
        </div>
        <div class="fabe-timeline-connector"></div>
        <div class="fabe-timeline-axis">
          <div class="fabe-timeline-dot" style="--card-accent: var(--wave-blue)"></div>
          <div class="fabe-timeline-line"></div>
        </div>
        <div style="flex: 0 0 45%"></div>
      </div>

      <div class="fabe-timeline-row">
        <div style="flex: 0 0 45%"></div>
        <div class="fabe-timeline-axis">
          <div class="fabe-timeline-dot" style="--card-accent: var(--spring-green)"></div>
          <div class="fabe-timeline-line"></div>
        </div>
        <div class="fabe-timeline-connector"></div>
        <div class="fabe-card advantage">
          <div class="fabe-icon-wrap"><i class="fas fa-chart-line"></i></div>
          <div class="fabe-label">Advantage</div>
          <div class="fabe-heading">{{利点}}</div>
          <div class="fabe-desc">{{利点の説明}}</div>
        </div>
      </div>

      <div class="fabe-timeline-row">
        <div class="fabe-card benefit">
          <div class="fabe-icon-wrap"><i class="fas fa-heart"></i></div>
          <div class="fabe-label">Benefit</div>
          <div class="fabe-heading">{{ベネフィット}}</div>
          <div class="fabe-desc">{{ベネフィットの説明}}</div>
        </div>
        <div class="fabe-timeline-connector"></div>
        <div class="fabe-timeline-axis">
          <div class="fabe-timeline-dot" style="--card-accent: var(--autumn-yellow)"></div>
          <div class="fabe-timeline-line"></div>
        </div>
        <div style="flex: 0 0 45%"></div>
      </div>

      <div class="fabe-timeline-row">
        <div style="flex: 0 0 45%"></div>
        <div class="fabe-timeline-axis">
          <div class="fabe-timeline-dot" style="--card-accent: var(--sakura-pink)"></div>
        </div>
        <div class="fabe-timeline-connector"></div>
        <div class="fabe-card evidence">
          <div class="fabe-icon-wrap"><i class="fas fa-award"></i></div>
          <div class="fabe-label">Evidence</div>
          <div class="fabe-heading">{{証拠}}</div>
          <div class="fabe-evidence-stat">
            <div class="fabe-stat-value">{{数値}}</div>
            <div class="fabe-stat-label">{{数値ラベル}}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

---

## 6. 円形配置型

```css
/* ===== 円形配置型 ===== */
.slide-fabe.fabe-circular .fabe-container {
  position: relative;
  width: 600px;
  height: 500px;
  margin: 0 auto;
}

.slide-fabe.fabe-circular .fabe-card {
  position: absolute;
  width: 200px;
  border-bottom: none;
  border-radius: 16px;
}

/* 4隅に配置 */
.slide-fabe.fabe-circular .fabe-card.feature {
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  border-top: 4px solid var(--wave-blue);
}

.slide-fabe.fabe-circular .fabe-card.advantage {
  top: 50%;
  right: 0;
  transform: translateY(-50%);
  border-right: 4px solid var(--spring-green);
}

.slide-fabe.fabe-circular .fabe-card.benefit {
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  border-bottom: 4px solid var(--autumn-yellow);
}

.slide-fabe.fabe-circular .fabe-card.evidence {
  top: 50%;
  left: 0;
  transform: translateY(-50%);
  border-left: 4px solid var(--sakura-pink);
}

/* 中央の接続サークル */
.slide-fabe.fabe-circular .fabe-center-hub {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 120px;
  height: 120px;
  background: linear-gradient(135deg, var(--wave-blue), var(--sakura-pink));
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
}

.slide-fabe.fabe-circular .fabe-center-hub i {
  font-size: 2rem;
  color: #fff;
  margin-bottom: 0.25rem;
}

.slide-fabe.fabe-circular .fabe-center-hub span {
  font-size: 0.85rem;
  font-weight: 700;
  color: #fff;
}

/* 接続線（SVG使用） */
.slide-fabe.fabe-circular .fabe-connections {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.slide-fabe.fabe-circular .fabe-connection-line {
  fill: none;
  stroke: var(--fuji-gray);
  stroke-width: 2;
  stroke-dasharray: 8 4;
  opacity: 0.5;
}

/* 円形アニメーション */
.slide-fabe.fabe-circular .fabe-orbit {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 350px;
  height: 350px;
  border: 2px dashed var(--fuji-gray);
  border-radius: 50%;
  opacity: 0.3;
}

.slide-fabe.fabe-circular .fabe-orbit-dot {
  position: absolute;
  width: 10px;
  height: 10px;
  background: var(--wave-blue);
  border-radius: 50%;
  animation: fabe-orbit-move 10s linear infinite;
}

@keyframes fabe-orbit-move {
  from { transform: rotate(0deg) translateX(175px) rotate(0deg); }
  to { transform: rotate(360deg) translateX(175px) rotate(-360deg); }
}
```

```html
<!-- 円形配置型 -->
<div class="slider__item slide-fabe fabe-circular">
  <div class="slider__content">
    <h2 class="fabe-title"><i class="fas fa-gem"></i> {{タイトル}}</h2>

    <div class="fabe-container">
      <!-- 軌道線 -->
      <div class="fabe-orbit">
        <div class="fabe-orbit-dot"></div>
      </div>

      <!-- 中央ハブ -->
      <div class="fabe-center-hub">
        <i class="fas fa-star"></i>
        <span>FABE</span>
      </div>

      <div class="fabe-card feature">
        <div class="fabe-icon-wrap"><i class="fas fa-cogs"></i></div>
        <div class="fabe-label">Feature</div>
        <div class="fabe-heading">{{特徴}}</div>
      </div>

      <div class="fabe-card advantage">
        <div class="fabe-icon-wrap"><i class="fas fa-chart-line"></i></div>
        <div class="fabe-label">Advantage</div>
        <div class="fabe-heading">{{利点}}</div>
      </div>

      <div class="fabe-card benefit">
        <div class="fabe-icon-wrap"><i class="fas fa-heart"></i></div>
        <div class="fabe-label">Benefit</div>
        <div class="fabe-heading">{{ベネフィット}}</div>
      </div>

      <div class="fabe-card evidence">
        <div class="fabe-icon-wrap"><i class="fas fa-award"></i></div>
        <div class="fabe-label">Evidence</div>
        <div class="fabe-heading">{{証拠}}</div>
      </div>
    </div>
  </div>
</div>
```

---

## 7. アニメーション（GSAP）

```javascript
/* ===== FABE型 アニメーション ===== */

// 共通の登場アニメーション関数
function animateFABE(slideElement) {
  const variant = slideElement.classList.contains('fabe-vertical') ? 'vertical' :
                  slideElement.classList.contains('fabe-grid') ? 'grid' :
                  slideElement.classList.contains('fabe-timeline') ? 'timeline' :
                  slideElement.classList.contains('fabe-circular') ? 'circular' : 'default';

  const tl = gsap.timeline();

  // タイトルアニメーション
  tl.from(slideElement.querySelector('.fabe-title'), {
    y: -30,
    opacity: 0,
    duration: 0.5,
    ease: 'power2.out'
  });

  // サブタイトル
  if (slideElement.querySelector('.fabe-subtitle')) {
    tl.from(slideElement.querySelector('.fabe-subtitle'), {
      y: -20,
      opacity: 0,
      duration: 0.3,
      ease: 'power2.out'
    }, '-=0.2');
  }

  // バリアント別アニメーション
  switch (variant) {
    case 'vertical':
      animateFABEVertical(slideElement, tl);
      break;
    case 'grid':
      animateFABEGrid(slideElement, tl);
      break;
    case 'timeline':
      animateFABETimeline(slideElement, tl);
      break;
    case 'circular':
      animateFABECircular(slideElement, tl);
      break;
    default:
      animateFABEDefault(slideElement, tl);
  }

  return tl;
}

// 横フロー型アニメーション
function animateFABEDefault(el, tl) {
  // プログレスライン
  tl.to(el.querySelector('.fabe-progress-fill'), {
    width: '100%',
    duration: 1.5,
    ease: 'power2.inOut'
  }, 0.3);

  // カード順次表示
  tl.from(el.querySelectorAll('.fabe-card'), {
    y: 50,
    opacity: 0,
    scale: 0.9,
    duration: 0.6,
    stagger: 0.2,
    ease: 'back.out(1.2)'
  }, 0.5);

  // ステップバッジ
  tl.from(el.querySelectorAll('.fabe-step-badge'), {
    scale: 0,
    opacity: 0,
    duration: 0.3,
    stagger: 0.15,
    ease: 'elastic.out(1, 0.5)'
  }, '-=0.8');

  // アイコン
  tl.from(el.querySelectorAll('.fabe-icon-wrap'), {
    scale: 0,
    rotation: -180,
    duration: 0.5,
    stagger: 0.12,
    ease: 'back.out(1.5)'
  }, '-=1');

  // 矢印
  tl.from(el.querySelectorAll('.fabe-arrow'), {
    scale: 0,
    opacity: 0,
    duration: 0.3,
    stagger: 0.1,
    ease: 'power2.out'
  }, '-=0.6');

  // テキストフェードイン
  tl.from(el.querySelectorAll('.fabe-heading, .fabe-desc, .fabe-points li'), {
    y: 10,
    opacity: 0,
    duration: 0.3,
    stagger: 0.05,
    ease: 'power2.out'
  }, '-=0.4');
}

// 縦スタック型アニメーション
function animateFABEVertical(el, tl) {
  // 縦ライン
  tl.to(el.querySelector('.fabe-vertical-line .fill'), {
    height: '100%',
    duration: 1.2,
    ease: 'power2.inOut'
  }, 0.3);

  // カード左からスライド
  tl.from(el.querySelectorAll('.fabe-card'), {
    x: -80,
    opacity: 0,
    duration: 0.5,
    stagger: 0.2,
    ease: 'power3.out'
  }, 0.5);

  // バッジ
  tl.from(el.querySelectorAll('.fabe-step-badge'), {
    scale: 0,
    duration: 0.3,
    stagger: 0.15,
    ease: 'back.out(2)'
  }, '-=0.6');

  // アイコン
  tl.from(el.querySelectorAll('.fabe-icon-wrap'), {
    scale: 0,
    duration: 0.4,
    stagger: 0.1,
    ease: 'elastic.out(1, 0.6)'
  }, '-=0.5');
}

// 2×2グリッド型アニメーション
function animateFABEGrid(el, tl) {
  // 中央インジケーター
  tl.from(el.querySelector('.fabe-grid-center'), {
    scale: 0,
    rotation: -360,
    duration: 0.8,
    ease: 'back.out(1.5)'
  }, 0.3);

  // 4カード同時＋グリッドパターン
  tl.from(el.querySelectorAll('.fabe-card'), {
    scale: 0.5,
    opacity: 0,
    duration: 0.5,
    stagger: {
      amount: 0.6,
      grid: [2, 2],
      from: 'center'
    },
    ease: 'back.out(1.3)'
  }, 0.5);

  // バッジとアイコン
  tl.from(el.querySelectorAll('.fabe-step-badge, .fabe-icon-wrap'), {
    scale: 0,
    duration: 0.3,
    stagger: 0.08,
    ease: 'elastic.out(1, 0.5)'
  }, '-=0.3');
}

// タイムライン型アニメーション
function animateFABETimeline(el, tl) {
  // タイムラインドット
  tl.from(el.querySelectorAll('.fabe-timeline-dot'), {
    scale: 0,
    duration: 0.4,
    stagger: 0.3,
    ease: 'back.out(2)'
  }, 0.3);

  // タイムラインライン
  tl.from(el.querySelectorAll('.fabe-timeline-line'), {
    scaleY: 0,
    transformOrigin: 'top center',
    duration: 0.3,
    stagger: 0.25,
    ease: 'power2.out'
  }, 0.4);

  // コネクター
  tl.from(el.querySelectorAll('.fabe-timeline-connector'), {
    scaleX: 0,
    duration: 0.3,
    stagger: 0.2,
    ease: 'power2.out'
  }, '-=0.8');

  // カード交互スライド
  const cards = el.querySelectorAll('.fabe-card');
  cards.forEach((card, i) => {
    const direction = i % 2 === 0 ? -60 : 60;
    tl.from(card, {
      x: direction,
      opacity: 0,
      duration: 0.5,
      ease: 'power3.out'
    }, 0.6 + i * 0.25);
  });
}

// 円形配置型アニメーション
function animateFABECircular(el, tl) {
  // 軌道線
  tl.from(el.querySelector('.fabe-orbit'), {
    scale: 0,
    opacity: 0,
    duration: 0.8,
    ease: 'power2.out'
  }, 0.3);

  // 中央ハブ
  tl.from(el.querySelector('.fabe-center-hub'), {
    scale: 0,
    rotation: -180,
    duration: 0.6,
    ease: 'back.out(1.5)'
  }, 0.5);

  // 4カード放射状
  tl.from(el.querySelectorAll('.fabe-card'), {
    scale: 0,
    opacity: 0,
    duration: 0.5,
    stagger: {
      each: 0.15,
      from: 'start'
    },
    ease: 'back.out(1.3)'
  }, 0.8);

  // アイコン
  tl.from(el.querySelectorAll('.fabe-icon-wrap'), {
    scale: 0,
    rotation: 360,
    duration: 0.4,
    stagger: 0.1,
    ease: 'elastic.out(1, 0.6)'
  }, '-=0.3');

  // 軌道ドット開始
  tl.to(el.querySelector('.fabe-orbit-dot'), {
    opacity: 1,
    duration: 0.3
  }, '-=0.2');
}

// 退場アニメーション
function animateFABELeave(slideElement) {
  const tl = gsap.timeline();

  tl.to(slideElement.querySelectorAll('.fabe-card'), {
    y: -30,
    opacity: 0,
    scale: 0.9,
    duration: 0.4,
    stagger: 0.08,
    ease: 'power2.in'
  });

  tl.to(slideElement.querySelector('.fabe-title'), {
    y: -20,
    opacity: 0,
    duration: 0.3,
    ease: 'power2.in'
  }, '-=0.2');

  return tl;
}

// 数値カウントアップアニメーション
function animateFABECounter(element) {
  const valueEl = element.querySelector('.fabe-stat-value');
  if (!valueEl) return;

  const targetText = valueEl.textContent;
  const targetNum = parseFloat(targetText.replace(/[^0-9.]/g, ''));
  const suffix = targetText.replace(/[0-9.]/g, '');

  if (!isNaN(targetNum)) {
    gsap.fromTo(valueEl,
      { textContent: 0 },
      {
        textContent: targetNum,
        duration: 1.5,
        delay: 1,
        ease: 'power2.out',
        snap: { textContent: targetNum % 1 === 0 ? 1 : 0.1 },
        onUpdate: function() {
          valueEl.textContent = Math.round(this.targets()[0].textContent * 10) / 10 + suffix;
        }
      }
    );
  }
}

// ホバーインタラクション強化
document.querySelectorAll('.slide-fabe .fabe-card').forEach(card => {
  card.addEventListener('mouseenter', () => {
    gsap.to(card.querySelector('.fabe-icon-wrap'), {
      scale: 1.15,
      rotation: 10,
      duration: 0.3,
      ease: 'power2.out'
    });
  });

  card.addEventListener('mouseleave', () => {
    gsap.to(card.querySelector('.fabe-icon-wrap'), {
      scale: 1,
      rotation: 0,
      duration: 0.3,
      ease: 'power2.out'
    });
  });
});
```

---

## 8. レイアウト選択ガイド

| 用途 | 推奨レイアウト | 理由 |
|------|---------------|------|
| 製品紹介・LP | 横フロー型 | 左→右の自然な流れで理解しやすい |
| 詳細な説明 | 縦スタック型 | テキスト量が多い場合に最適 |
| 概要・サマリー | 2×2グリッド型 | 4要素を一目で把握可能 |
| ストーリー形式 | タイムライン型 | 時間軸・段階的な説明に最適 |
| コンセプト紹介 | 円形配置型 | 各要素の関連性を強調 |
