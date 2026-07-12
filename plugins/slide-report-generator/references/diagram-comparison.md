# 図解タイプ: 比較・マトリックス系

**責務**: 対比型、マトリックス型、ガントチャート、高度な表型、ペルソナ型のCSS・HTMLテンプレート

**含まれるタイプ**: 11.6-11.10

---

### 11.6 対比型（製品・サービス比較）

2つ以上の対象を詳細比較。

```css
.slide-comparison .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-comparison .comparison-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-comparison .comparison-container {
  display: flex;
  justify-content: center;
  gap: 2rem;
}

/* 比較カード */
.slide-comparison .comparison-card {
  flex: 1;
  max-width: 350px;
  background: var(--bg-dim);
  border-radius: 16px;
  overflow: hidden;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-comparison .comparison-card:hover {
  transform: translateY(-10px);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
}

.slide-comparison .comparison-card.featured {
  border: 3px solid var(--sakura-pink);
  transform: scale(1.05);
}

.slide-comparison .comparison-card.featured:hover {
  transform: scale(1.08) translateY(-10px);
}

/* ヘッダー */
.slide-comparison .comparison-header {
  padding: 1.5rem;
  text-align: center;
  background: var(--sumi-ink);
}

.slide-comparison .comparison-card:nth-child(1) .comparison-header { border-bottom: 4px solid var(--wave-blue); }
.slide-comparison .comparison-card:nth-child(2) .comparison-header { border-bottom: 4px solid var(--sakura-pink); }
.slide-comparison .comparison-card:nth-child(3) .comparison-header { border-bottom: 4px solid var(--wave-aqua); }

.slide-comparison .comparison-name {
  font-size: var(--fs-subheading);
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.slide-comparison .comparison-price {
  font-size: var(--fs-heading);
  font-weight: 700;
  color: var(--wave-blue);
}

.slide-comparison .comparison-price-unit {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* 特徴リスト */
.slide-comparison .comparison-features {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slide-comparison .comparison-feature {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slide-comparison .comparison-feature i {
  width: 24px;
  text-align: center;
}

.slide-comparison .comparison-feature i.fa-check {
  color: var(--spring-green);
}

.slide-comparison .comparison-feature i.fa-times {
  color: var(--sakura-pink);
}

.slide-comparison .comparison-feature i.fa-minus {
  color: var(--fg-dim);
}

/* CTA */
.slide-comparison .comparison-cta {
  padding: 1.5rem;
  text-align: center;
}

.slide-comparison .comparison-button {
  width: 100%;
  padding: 1rem;
  border: none;
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-comparison .comparison-button:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}

.slide-comparison .comparison-card:nth-child(1) .comparison-button { background: var(--wave-blue); color: var(--bg-dark); }
.slide-comparison .comparison-card:nth-child(2) .comparison-button { background: var(--sakura-pink); color: var(--bg-dark); }
.slide-comparison .comparison-card:nth-child(3) .comparison-button { background: var(--wave-aqua); color: var(--bg-dark); }

/* 2カード・4カード対応 */
.slide-comparison.comparison-2 .comparison-card { max-width: 450px; }
.slide-comparison.comparison-4 .comparison-card { max-width: 250px; }
.slide-comparison.comparison-4 .comparison-header { padding: 1rem; }
.slide-comparison.comparison-4 .comparison-features { padding: 1rem; }
```

```html
<div class="slider__item slide-comparison comparison-3">
  <div class="slider__content">
    <h2 class="comparison-title"><i class="fas fa-balance-scale"></i> {{タイトル}}</h2>
    <div class="comparison-container">
      <!-- プラン1 -->
      <div class="comparison-card">
        <div class="comparison-header">
          <div class="comparison-name">{{プラン名1}}</div>
          <div class="comparison-price">{{価格1}}<span class="comparison-price-unit">/月</span></div>
        </div>
        <div class="comparison-features">
          <div class="comparison-feature"><i class="fas fa-check"></i><span>{{機能1}}</span></div>
          <div class="comparison-feature"><i class="fas fa-check"></i><span>{{機能2}}</span></div>
          <div class="comparison-feature"><i class="fas fa-times"></i><span>{{機能3}}</span></div>
        </div>
        <div class="comparison-cta">
          <button class="comparison-button">選択</button>
        </div>
      </div>

      <!-- プラン2（推奨） -->
      <div class="comparison-card featured">
        <div class="comparison-header">
          <div class="comparison-name">{{プラン名2}}</div>
          <div class="comparison-price">{{価格2}}<span class="comparison-price-unit">/月</span></div>
        </div>
        <div class="comparison-features">
          <div class="comparison-feature"><i class="fas fa-check"></i><span>{{機能1}}</span></div>
          <div class="comparison-feature"><i class="fas fa-check"></i><span>{{機能2}}</span></div>
          <div class="comparison-feature"><i class="fas fa-check"></i><span>{{機能3}}</span></div>
        </div>
        <div class="comparison-cta">
          <button class="comparison-button">選択</button>
        </div>
      </div>

      <!-- プラン3 -->
      <div class="comparison-card">
        <!-- 同様 -->
      </div>
    </div>
  </div>
</div>
```

### 11.7 マトリックス型（n×m対応）

分類・対比を2軸で表現。2×2に限らず柔軟に対応。

```css
.slide-matrix .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-matrix .matrix-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-matrix .matrix-container {
  position: relative;
  display: grid;
  gap: 0;
}

/* 軸ラベル */
.slide-matrix .matrix-axis-x {
  position: absolute;
  bottom: -40px;
  left: 50%;
  transform: translateX(-50%);
  font-weight: 700;
  color: var(--fg-dim);
}

.slide-matrix .matrix-axis-y {
  position: absolute;
  left: -40px;
  top: 50%;
  transform: translateY(-50%) rotate(-90deg);
  font-weight: 700;
  color: var(--fg-dim);
}

/* マトリックスセル */
.slide-matrix .matrix-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 1.5rem;
  border: 1px solid var(--fuji-gray);
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.slide-matrix .matrix-cell:hover {
  transform: scale(1.05);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

/* 2×2マトリックス */
.slide-matrix.matrix-2x2 .matrix-container {
  grid-template-columns: repeat(2, 250px);
  grid-template-rows: repeat(2, 200px);
}

/* 3×3マトリックス */
.slide-matrix.matrix-3x3 .matrix-container {
  grid-template-columns: repeat(3, 200px);
  grid-template-rows: repeat(3, 160px);
}

/* 4×4マトリックス */
.slide-matrix.matrix-4x4 .matrix-container {
  grid-template-columns: repeat(4, 160px);
  grid-template-rows: repeat(4, 130px);
}

/* 3×2マトリックス（横長） */
.slide-matrix.matrix-3x2 .matrix-container {
  grid-template-columns: repeat(3, 220px);
  grid-template-rows: repeat(2, 180px);
}

/* 2×3マトリックス（縦長） */
.slide-matrix.matrix-2x3 .matrix-container {
  grid-template-columns: repeat(2, 280px);
  grid-template-rows: repeat(3, 140px);
}

/* セルカラーバリエーション（象限別） */
.slide-matrix.matrix-2x2 .matrix-cell:nth-child(1) { background: rgba(126, 156, 216, 0.2); } /* 左上 */
.slide-matrix.matrix-2x2 .matrix-cell:nth-child(2) { background: rgba(210, 126, 153, 0.2); } /* 右上 */
.slide-matrix.matrix-2x2 .matrix-cell:nth-child(3) { background: rgba(220, 165, 97, 0.2); }  /* 左下 */
.slide-matrix.matrix-2x2 .matrix-cell:nth-child(4) { background: rgba(152, 187, 108, 0.2); } /* 右下 */

/* 動的カラー設定 */
.slide-matrix .matrix-cell.color-blue { background: rgba(126, 156, 216, 0.2); }
.slide-matrix .matrix-cell.color-pink { background: rgba(210, 126, 153, 0.2); }
.slide-matrix .matrix-cell.color-yellow { background: rgba(220, 165, 97, 0.2); }
.slide-matrix .matrix-cell.color-green { background: rgba(152, 187, 108, 0.2); }
.slide-matrix .matrix-cell.color-aqua { background: rgba(122, 162, 247, 0.2); }

/* ヘッダー行・列 */
.slide-matrix .matrix-header {
  background: var(--sumi-ink);
  font-weight: 700;
  color: var(--wave-blue);
}

.slide-matrix .matrix-header.row-header {
  border-right: 2px solid var(--wave-blue);
}

.slide-matrix .matrix-header.col-header {
  border-bottom: 2px solid var(--wave-blue);
}
```

```html
<!-- 2×2マトリックス -->
<div class="slider__item slide-matrix matrix-2x2">
  <div class="slider__content">
    <h2 class="matrix-title"><i class="fas fa-th"></i> {{タイトル}}</h2>
    <div class="matrix-container">
      <div class="matrix-axis-x">{{X軸ラベル}}</div>
      <div class="matrix-axis-y">{{Y軸ラベル}}</div>
      <div class="matrix-cell has-tooltip" data-tooltip="{{詳細1}}">
        <i class="fas {{アイコン1}}"></i>
        <span>{{象限1}}</span>
      </div>
      <div class="matrix-cell has-tooltip" data-tooltip="{{詳細2}}">
        <i class="fas {{アイコン2}}"></i>
        <span>{{象限2}}</span>
      </div>
      <div class="matrix-cell has-tooltip" data-tooltip="{{詳細3}}">
        <i class="fas {{アイコン3}}"></i>
        <span>{{象限3}}</span>
      </div>
      <div class="matrix-cell has-tooltip" data-tooltip="{{詳細4}}">
        <i class="fas {{アイコン4}}"></i>
        <span>{{象限4}}</span>
      </div>
    </div>
  </div>
</div>

<!-- ヘッダー付き3×3マトリックス -->
<div class="slider__item slide-matrix matrix-3x3">
  <div class="slider__content">
    <h2 class="matrix-title"><i class="fas fa-th"></i> {{タイトル}}</h2>
    <div class="matrix-container">
      <!-- ヘッダー行 -->
      <div class="matrix-cell matrix-header"></div>
      <div class="matrix-cell matrix-header col-header">{{列1}}</div>
      <div class="matrix-cell matrix-header col-header">{{列2}}</div>
      <!-- 行1 -->
      <div class="matrix-cell matrix-header row-header">{{行1}}</div>
      <div class="matrix-cell">{{セル1-1}}</div>
      <div class="matrix-cell">{{セル1-2}}</div>
      <!-- 行2 -->
      <div class="matrix-cell matrix-header row-header">{{行2}}</div>
      <div class="matrix-cell">{{セル2-1}}</div>
      <div class="matrix-cell">{{セル2-2}}</div>
    </div>
  </div>
</div>
```

### 11.8 ガントチャート

プロジェクトスケジュールの視覚化。

```css
.slide-gantt .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-gantt .gantt-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-gantt .gantt-container {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--bg-dim);
  border-radius: 12px;
  overflow: hidden;
}

/* ヘッダー（期間） */
.slide-gantt .gantt-header {
  display: grid;
  background: var(--sumi-ink);
  border-bottom: 2px solid var(--fuji-gray);
}

.slide-gantt .gantt-header-cell {
  padding: 0.75rem;
  text-align: center;
  font-weight: 700;
  font-size: var(--fs-small);
  color: var(--fg-dim);
  border-right: 1px solid var(--fuji-gray);
}

.slide-gantt .gantt-header-cell:first-child {
  background: var(--bg-dim);
}

/* タスク行 */
.slide-gantt .gantt-row {
  display: grid;
  border-bottom: 1px solid var(--fuji-gray);
  align-items: center;
}

.slide-gantt .gantt-row:last-child {
  border-bottom: none;
}

/* タスク名セル */
.slide-gantt .gantt-task-name {
  padding: 0.75rem 1rem;
  font-weight: 600;
  background: var(--bg-dim);
  border-right: 2px solid var(--fuji-gray);
  white-space: nowrap;
}

/* タスクバーセル */
.slide-gantt .gantt-cell {
  position: relative;
  height: 40px;
  border-right: 1px solid var(--fuji-gray);
}

.slide-gantt .gantt-cell:last-child {
  border-right: none;
}

/* タスクバー */
.slide-gantt .gantt-bar {
  position: absolute;
  height: 24px;
  top: 50%;
  transform: translateY(-50%);
  border-radius: 4px;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-gantt .gantt-bar:hover {
  transform: translateY(-50%) scaleY(1.3);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

/* バーカラー */
.slide-gantt .gantt-bar.bar-blue { background: var(--wave-blue); }
.slide-gantt .gantt-bar.bar-pink { background: var(--sakura-pink); }
.slide-gantt .gantt-bar.bar-aqua { background: var(--wave-aqua); }
.slide-gantt .gantt-bar.bar-yellow { background: var(--autumn-yellow); }
.slide-gantt .gantt-bar.bar-green { background: var(--spring-green); }

/* バー位置・幅（グリッドベース） */
.slide-gantt .gantt-bar[data-start="1"][data-duration="2"] { left: 0; width: calc(200% - 4px); margin-left: 2px; }
.slide-gantt .gantt-bar[data-start="1"][data-duration="3"] { left: 0; width: calc(300% - 4px); margin-left: 2px; }
.slide-gantt .gantt-bar[data-start="2"][data-duration="2"] { left: 100%; width: calc(200% - 4px); margin-left: 2px; }
.slide-gantt .gantt-bar[data-start="3"][data-duration="1"] { left: 200%; width: calc(100% - 4px); margin-left: 2px; }

/* 柔軟な列数 */
.slide-gantt.gantt-4 .gantt-header,
.slide-gantt.gantt-4 .gantt-row { grid-template-columns: 150px repeat(4, 1fr); }

.slide-gantt.gantt-6 .gantt-header,
.slide-gantt.gantt-6 .gantt-row { grid-template-columns: 150px repeat(6, 1fr); }

.slide-gantt.gantt-8 .gantt-header,
.slide-gantt.gantt-8 .gantt-row { grid-template-columns: 150px repeat(8, 1fr); }

.slide-gantt.gantt-12 .gantt-header,
.slide-gantt.gantt-12 .gantt-row { grid-template-columns: 120px repeat(12, 1fr); }

/* マイルストーン */
.slide-gantt .gantt-milestone {
  position: absolute;
  top: 50%;
  transform: translateY(-50%) rotate(45deg);
  width: 16px;
  height: 16px;
  background: var(--sakura-pink);
  z-index: 5;
}
```

```html
<div class="slider__item slide-gantt gantt-6">
  <div class="slider__content">
    <h2 class="gantt-title"><i class="fas fa-tasks"></i> {{タイトル}}</h2>
    <div class="gantt-container">
      <!-- ヘッダー -->
      <div class="gantt-header">
        <div class="gantt-header-cell">タスク</div>
        <div class="gantt-header-cell">1月</div>
        <div class="gantt-header-cell">2月</div>
        <div class="gantt-header-cell">3月</div>
        <div class="gantt-header-cell">4月</div>
        <div class="gantt-header-cell">5月</div>
        <div class="gantt-header-cell">6月</div>
      </div>
      <!-- タスク行 -->
      <div class="gantt-row">
        <div class="gantt-task-name">{{タスク1}}</div>
        <div class="gantt-cell">
          <div class="gantt-bar bar-blue" data-start="1" data-duration="2" data-tooltip="{{詳細1}}"></div>
        </div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell"></div>
      </div>
      <div class="gantt-row">
        <div class="gantt-task-name">{{タスク2}}</div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell">
          <div class="gantt-bar bar-pink" data-start="2" data-duration="3"></div>
        </div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell"></div>
        <div class="gantt-cell"></div>
      </div>
      <!-- 必要に応じて追加 -->
    </div>
  </div>
</div>
```

### 11.9 高度な表型

ヘッダー・色分け・アイコンを活用した表。

```css
.slide-advanced-table .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-advanced-table .table-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-advanced-table table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-dim);
  border-radius: 12px;
  overflow: hidden;
}

/* ヘッダー */
.slide-advanced-table thead {
  background: linear-gradient(135deg, var(--sumi-ink), var(--bg-dim));
}

.slide-advanced-table th {
  padding: 1.25rem 1rem;
  text-align: left;
  font-weight: 700;
  color: var(--wave-blue);
  border-bottom: 3px solid var(--wave-blue);
  white-space: nowrap;
}

.slide-advanced-table th i {
  margin-right: 0.5rem;
}

/* セル */
.slide-advanced-table td {
  padding: 1rem;
  border-bottom: 1px solid var(--fuji-gray);
  transition: background 0.2s ease;
}

.slide-advanced-table tr:hover td {
  background: rgba(126, 156, 216, 0.1);
}

.slide-advanced-table tr:last-child td {
  border-bottom: none;
}

/* ステータスバッジ */
.slide-advanced-table .status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.75rem;
  border-radius: 50px;
  font-size: var(--fs-small);
  font-weight: 600;
}

.slide-advanced-table .status-badge.status-success {
  background: rgba(152, 187, 108, 0.2);
  color: var(--spring-green);
}

.slide-advanced-table .status-badge.status-warning {
  background: rgba(220, 165, 97, 0.2);
  color: var(--autumn-yellow);
}

.slide-advanced-table .status-badge.status-error {
  background: rgba(210, 126, 153, 0.2);
  color: var(--sakura-pink);
}

.slide-advanced-table .status-badge.status-info {
  background: rgba(126, 156, 216, 0.2);
  color: var(--wave-blue);
}

/* 進捗バー */
.slide-advanced-table .progress-cell {
  min-width: 150px;
}

.slide-advanced-table .progress-bar-container {
  height: 8px;
  background: var(--fuji-gray);
  border-radius: 4px;
  overflow: hidden;
}

.slide-advanced-table .progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--wave-blue), var(--wave-aqua));
  transition: width 0.5s ease;
}

/* 数値セル */
.slide-advanced-table .number-cell {
  font-family: 'JetBrains Mono', monospace;
  text-align: right;
}

.slide-advanced-table .number-cell.positive {
  color: var(--spring-green);
}

.slide-advanced-table .number-cell.negative {
  color: var(--sakura-pink);
}

/* アクションセル */
.slide-advanced-table .action-cell {
  display: flex;
  gap: 0.5rem;
}

.slide-advanced-table .action-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.slide-advanced-table .action-btn:hover {
  transform: scale(1.1);
}

.slide-advanced-table .action-btn.action-edit {
  background: var(--wave-blue);
  color: var(--bg-dark);
}

.slide-advanced-table .action-btn.action-delete {
  background: var(--sakura-pink);
  color: var(--bg-dark);
}

/* 行の強調 */
.slide-advanced-table tr.row-highlight {
  background: rgba(220, 165, 97, 0.1);
}

.slide-advanced-table tr.row-highlight td:first-child {
  border-left: 4px solid var(--autumn-yellow);
}
```

```html
<div class="slider__item slide-advanced-table">
  <div class="slider__content">
    <h2 class="table-title"><i class="fas fa-table"></i> {{タイトル}}</h2>
    <table>
      <thead>
        <tr>
          <th><i class="fas fa-user"></i>{{ヘッダー1}}</th>
          <th><i class="fas fa-tag"></i>{{ヘッダー2}}</th>
          <th><i class="fas fa-chart-bar"></i>{{ヘッダー3}}</th>
          <th><i class="fas fa-check-circle"></i>{{ヘッダー4}}</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>{{データ1-1}}</td>
          <td>
            <span class="status-badge status-success">
              <i class="fas fa-check"></i>完了
            </span>
          </td>
          <td class="progress-cell">
            <div class="progress-bar-container">
              <div class="progress-bar-fill" style="width: 75%;"></div>
            </div>
          </td>
          <td class="number-cell positive">+12.5%</td>
        </tr>
        <tr class="row-highlight">
          <td>{{データ2-1}}</td>
          <td>
            <span class="status-badge status-warning">
              <i class="fas fa-clock"></i>進行中
            </span>
          </td>
          <td class="progress-cell">
            <div class="progress-bar-container">
              <div class="progress-bar-fill" style="width: 45%;"></div>
            </div>
          </td>
          <td class="number-cell negative">-3.2%</td>
        </tr>
        <!-- 必要に応じて追加 -->
      </tbody>
    </table>
  </div>
</div>
```

### 11.10 ペルソナ型（Persona）

人物プロファイル・ターゲット顧客像を表示。

```css
.slide-persona .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-persona .persona-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-persona .persona-container {
  display: flex;
  gap: 3rem;
  align-items: flex-start;
  max-width: 900px;
}

/* アバター部分 */
.slide-persona .persona-avatar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  min-width: 180px;
}

.slide-persona .persona-avatar-image {
  width: 150px;
  height: 150px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--wave-blue), var(--sakura-pink));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 4rem;
  color: var(--bg-dark);
  border: 4px solid var(--fg-main);
}

.slide-persona .persona-name {
  font-size: var(--fs-subheading);
  font-weight: 700;
}

.slide-persona .persona-role {
  font-size: var(--fs-body);
  color: var(--fg-dim);
}

/* プロファイル情報 */
.slide-persona .persona-profile {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.slide-persona .persona-section {
  background: var(--bg-dim);
  padding: 1.5rem;
  border-radius: 12px;
  border-left: 4px solid var(--wave-blue);
}

.slide-persona .persona-section.challenges {
  border-left-color: var(--sakura-pink);
}

.slide-persona .persona-section.needs {
  border-left-color: var(--spring-green);
}

.slide-persona .persona-section-title {
  font-size: var(--fs-body-lg);
  font-weight: 700;
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.slide-persona .persona-attributes {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.5rem;
}

.slide-persona .persona-attribute {
  display: flex;
  gap: 0.5rem;
}

.slide-persona .persona-attribute-label {
  color: var(--fg-dim);
  min-width: 60px;
}

.slide-persona .persona-attribute-value {
  font-weight: 600;
}

.slide-persona .persona-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.slide-persona .persona-list li {
  padding: 0.25rem 0;
  padding-left: 1.5rem;
  position: relative;
}

.slide-persona .persona-list li::before {
  content: '•';
  position: absolute;
  left: 0.5rem;
  color: var(--autumn-yellow);
}
```

```html
<div class="slider__item slide-persona">
  <div class="slider__content">
    <h2 class="persona-title"><i class="fas fa-user-circle"></i> {{タイトル}}</h2>
    <div class="persona-container">
      <div class="persona-avatar">
        <div class="persona-avatar-image">
          <i class="fas fa-user"></i>
        </div>
        <div class="persona-name">{{名前}}</div>
        <div class="persona-role">{{役職・職業}}</div>
      </div>
      <div class="persona-profile">
        <div class="persona-section">
          <div class="persona-section-title">
            <i class="fas fa-id-card"></i> 基本情報
          </div>
          <div class="persona-attributes">
            <div class="persona-attribute">
              <span class="persona-attribute-label">年齢</span>
              <span class="persona-attribute-value">{{年齢}}</span>
            </div>
            <div class="persona-attribute">
              <span class="persona-attribute-label">業種</span>
              <span class="persona-attribute-value">{{業種}}</span>
            </div>
            <div class="persona-attribute">
              <span class="persona-attribute-label">経験</span>
              <span class="persona-attribute-value">{{経験年数}}</span>
            </div>
            <div class="persona-attribute">
              <span class="persona-attribute-label">規模</span>
              <span class="persona-attribute-value">{{会社規模}}</span>
            </div>
          </div>
        </div>
        <div class="persona-section challenges">
          <div class="persona-section-title">
            <i class="fas fa-exclamation-triangle"></i> 課題
          </div>
          <ul class="persona-list">
            <li>{{課題1}}</li>
            <li>{{課題2}}</li>
            <li>{{課題3}}</li>
          </ul>
        </div>
        <div class="persona-section needs">
          <div class="persona-section-title">
            <i class="fas fa-lightbulb"></i> ニーズ
          </div>
          <ul class="persona-list">
            <li>{{ニーズ1}}</li>
            <li>{{ニーズ2}}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</div>
```

