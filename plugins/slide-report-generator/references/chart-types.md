# グラフ・チャートタイプ

**責務**: 9種のグラフタイプ（棒、折れ線、円、レーダー等）、アイコン推奨ガイド、選択ガイド

---


## 13. グラフ・チャートタイプ

### 13.1 縦棒グラフ（Bar Chart）

```css
.slide-bar-chart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-bar-chart .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-bar-chart .chart-container {
  position: relative;
  width: 700px;
  height: 350px;
  padding: 2rem 2rem 3rem 4rem;
}

/* Y軸 */
.slide-bar-chart .chart-axis-y {
  position: absolute;
  left: 3rem;
  top: 2rem;
  bottom: 3rem;
  width: 2px;
  background: var(--fuji-gray);
}

.slide-bar-chart .chart-axis-y-label {
  position: absolute;
  left: 0;
  font-size: var(--fs-small);
  color: var(--fg-dim);
  transform: translateX(-100%) translateY(-50%);
  padding-right: 0.5rem;
}

/* X軸 */
.slide-bar-chart .chart-axis-x {
  position: absolute;
  left: 3rem;
  right: 2rem;
  bottom: 3rem;
  height: 2px;
  background: var(--fuji-gray);
}

/* バーエリア */
.slide-bar-chart .chart-bars {
  position: absolute;
  left: 4rem;
  right: 2rem;
  bottom: 3.5rem;
  top: 2rem;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 1rem;
}

.slide-bar-chart .chart-bar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.slide-bar-chart .chart-bar {
  width: 50px;
  background: linear-gradient(180deg, var(--wave-blue), var(--wave-aqua));
  border-radius: 4px 4px 0 0;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  position: relative;
}

.slide-bar-chart .chart-bar:hover {
  transform: scaleY(1.05);
  box-shadow: 0 -5px 20px rgba(126, 156, 216, 0.4);
}

/* バーの値ラベル */
.slide-bar-chart .chart-bar-value {
  position: absolute;
  top: -25px;
  left: 50%;
  transform: translateX(-50%);
  font-size: var(--fs-small);
  font-weight: 700;
  color: var(--wave-blue);
  white-space: nowrap;
}

.slide-bar-chart .chart-bar-label {
  font-size: var(--fs-small);
  color: var(--fg-dim);
  text-align: center;
  margin-top: 0.5rem;
}

/* カラーバリエーション */
.slide-bar-chart .chart-bar.bar-pink { background: linear-gradient(180deg, var(--sakura-pink), #e896b0); }
.slide-bar-chart .chart-bar.bar-aqua { background: linear-gradient(180deg, var(--wave-aqua), #9fd8e8); }
.slide-bar-chart .chart-bar.bar-yellow { background: linear-gradient(180deg, var(--autumn-yellow), #e8c97a); }
.slide-bar-chart .chart-bar.bar-green { background: linear-gradient(180deg, var(--spring-green), #b4d98c); }

/* グリッドライン */
.slide-bar-chart .chart-grid-line {
  position: absolute;
  left: 3rem;
  right: 2rem;
  height: 1px;
  background: var(--fuji-gray);
  opacity: 0.3;
}
```

```html
<div class="slider__item slide-bar-chart">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-chart-bar"></i> {{タイトル}}</h2>
    <div class="chart-container">
      <div class="chart-axis-y">
        <span class="chart-axis-y-label" style="bottom: 100%;">100</span>
        <span class="chart-axis-y-label" style="bottom: 75%;">75</span>
        <span class="chart-axis-y-label" style="bottom: 50%;">50</span>
        <span class="chart-axis-y-label" style="bottom: 25%;">25</span>
        <span class="chart-axis-y-label" style="bottom: 0;">0</span>
      </div>
      <div class="chart-axis-x"></div>
      <div class="chart-grid-line" style="bottom: calc(25% + 3rem);"></div>
      <div class="chart-grid-line" style="bottom: calc(50% + 3rem);"></div>
      <div class="chart-grid-line" style="bottom: calc(75% + 3rem);"></div>
      <div class="chart-bars">
        <div class="chart-bar-group">
          <div class="chart-bar" style="height: 60%;">
            <span class="chart-bar-value">60</span>
          </div>
          <span class="chart-bar-label">{{ラベル1}}</span>
        </div>
        <div class="chart-bar-group">
          <div class="chart-bar bar-pink" style="height: 85%;">
            <span class="chart-bar-value">85</span>
          </div>
          <span class="chart-bar-label">{{ラベル2}}</span>
        </div>
        <div class="chart-bar-group">
          <div class="chart-bar bar-aqua" style="height: 45%;">
            <span class="chart-bar-value">45</span>
          </div>
          <span class="chart-bar-label">{{ラベル3}}</span>
        </div>
        <div class="chart-bar-group">
          <div class="chart-bar bar-yellow" style="height: 72%;">
            <span class="chart-bar-value">72</span>
          </div>
          <span class="chart-bar-label">{{ラベル4}}</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 13.2 横棒グラフ（Horizontal Bar Chart）

```css
.slide-hbar-chart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-hbar-chart .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-hbar-chart .chart-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 700px;
  margin: 0 auto;
}

.slide-hbar-chart .chart-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.slide-hbar-chart .chart-label {
  width: 120px;
  text-align: right;
  font-size: var(--fs-body);
  flex-shrink: 0;
}

.slide-hbar-chart .chart-bar-container {
  flex: 1;
  height: 30px;
  background: var(--bg-dim);
  border-radius: 15px;
  overflow: hidden;
  position: relative;
}

.slide-hbar-chart .chart-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--wave-blue), var(--wave-aqua));
  border-radius: 15px;
  transition: width 0.8s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 1rem;
}

.slide-hbar-chart .chart-bar-value {
  font-size: var(--fs-small);
  font-weight: 700;
  color: var(--bg-dark);
}

/* バー外に値を表示（短いバーの場合） */
.slide-hbar-chart .chart-bar.short-bar .chart-bar-value {
  position: absolute;
  right: -50px;
  color: var(--fg);
}

/* カラーバリエーション */
.slide-hbar-chart .chart-bar.bar-pink { background: linear-gradient(90deg, var(--sakura-pink), #e896b0); }
.slide-hbar-chart .chart-bar.bar-aqua { background: linear-gradient(90deg, var(--wave-aqua), #9fd8e8); }
.slide-hbar-chart .chart-bar.bar-yellow { background: linear-gradient(90deg, var(--autumn-yellow), #e8c97a); }
.slide-hbar-chart .chart-bar.bar-green { background: linear-gradient(90deg, var(--spring-green), #b4d98c); }

/* ホバー効果 */
.slide-hbar-chart .chart-row:hover .chart-bar {
  filter: brightness(1.1);
  box-shadow: 0 5px 20px rgba(126, 156, 216, 0.3);
}
```

```html
<div class="slider__item slide-hbar-chart">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-align-left"></i> {{タイトル}}</h2>
    <div class="chart-container">
      <div class="chart-row">
        <span class="chart-label">{{ラベル1}}</span>
        <div class="chart-bar-container">
          <div class="chart-bar" style="width: 85%;">
            <span class="chart-bar-value">85%</span>
          </div>
        </div>
      </div>
      <div class="chart-row">
        <span class="chart-label">{{ラベル2}}</span>
        <div class="chart-bar-container">
          <div class="chart-bar bar-pink" style="width: 72%;">
            <span class="chart-bar-value">72%</span>
          </div>
        </div>
      </div>
      <div class="chart-row">
        <span class="chart-label">{{ラベル3}}</span>
        <div class="chart-bar-container">
          <div class="chart-bar bar-aqua" style="width: 60%;">
            <span class="chart-bar-value">60%</span>
          </div>
        </div>
      </div>
      <div class="chart-row">
        <span class="chart-label">{{ラベル4}}</span>
        <div class="chart-bar-container">
          <div class="chart-bar bar-yellow" style="width: 45%;">
            <span class="chart-bar-value">45%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 13.3 積み上げ棒グラフ（Stacked Bar Chart）

```css
.slide-stacked-chart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-stacked-chart .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-stacked-chart .chart-container {
  position: relative;
  width: 700px;
  height: 350px;
  padding: 2rem 2rem 3rem 4rem;
}

.slide-stacked-chart .chart-bars {
  position: absolute;
  left: 4rem;
  right: 2rem;
  bottom: 3.5rem;
  top: 2rem;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 2rem;
}

.slide-stacked-chart .chart-bar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.slide-stacked-chart .chart-stacked-bar {
  width: 60px;
  display: flex;
  flex-direction: column-reverse;
  border-radius: 4px 4px 0 0;
  overflow: hidden;
}

.slide-stacked-chart .chart-segment {
  transition: filter 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.slide-stacked-chart .chart-segment:hover {
  filter: brightness(1.2);
}

.slide-stacked-chart .chart-segment-value {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--bg-dark);
}

/* セグメントカラー */
.slide-stacked-chart .segment-1 { background: var(--wave-blue); }
.slide-stacked-chart .segment-2 { background: var(--sakura-pink); }
.slide-stacked-chart .segment-3 { background: var(--wave-aqua); }
.slide-stacked-chart .segment-4 { background: var(--autumn-yellow); }

.slide-stacked-chart .chart-bar-label {
  font-size: var(--fs-small);
  color: var(--fg-dim);
  margin-top: 0.5rem;
}

/* 凡例 */
.slide-stacked-chart .chart-legend {
  display: flex;
  justify-content: center;
  gap: 2rem;
  margin-top: 1rem;
}

.slide-stacked-chart .legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.slide-stacked-chart .legend-color {
  width: 16px;
  height: 16px;
  border-radius: 4px;
}
```

```html
<div class="slider__item slide-stacked-chart">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-layer-group"></i> {{タイトル}}</h2>
    <div class="chart-container">
      <div class="chart-bars">
        <div class="chart-bar-group">
          <div class="chart-stacked-bar" style="height: 200px;">
            <div class="chart-segment segment-1" style="height: 40%;">
              <span class="chart-segment-value">40</span>
            </div>
            <div class="chart-segment segment-2" style="height: 30%;">
              <span class="chart-segment-value">30</span>
            </div>
            <div class="chart-segment segment-3" style="height: 30%;">
              <span class="chart-segment-value">30</span>
            </div>
          </div>
          <span class="chart-bar-label">{{ラベル1}}</span>
        </div>
        <!-- 他のバーグループ -->
      </div>
    </div>
    <div class="chart-legend">
      <div class="legend-item">
        <div class="legend-color segment-1"></div>
        <span>{{凡例1}}</span>
      </div>
      <div class="legend-item">
        <div class="legend-color segment-2"></div>
        <span>{{凡例2}}</span>
      </div>
      <div class="legend-item">
        <div class="legend-color segment-3"></div>
        <span>{{凡例3}}</span>
      </div>
    </div>
  </div>
</div>
```

### 13.4 折れ線グラフ（Line Chart）

```css
.slide-line-chart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-line-chart .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-line-chart .chart-container {
  position: relative;
  width: 700px;
  height: 350px;
  padding: 2rem 2rem 3rem 4rem;
}

/* SVGベースの折れ線 */
.slide-line-chart .chart-svg {
  position: absolute;
  left: 4rem;
  right: 2rem;
  top: 2rem;
  bottom: 3rem;
}

.slide-line-chart .chart-line {
  fill: none;
  stroke: var(--wave-blue);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.slide-line-chart .chart-line.line-pink { stroke: var(--sakura-pink); }
.slide-line-chart .chart-line.line-aqua { stroke: var(--wave-aqua); }
.slide-line-chart .chart-line.line-yellow { stroke: var(--autumn-yellow); }

/* 面グラフ（塗りつぶし） */
.slide-line-chart .chart-area {
  fill: var(--wave-blue);
  opacity: 0.2;
}

/* データポイント */
.slide-line-chart .chart-point {
  fill: var(--wave-blue);
  stroke: var(--bg-dark);
  stroke-width: 2;
  transition: r 0.3s ease;
  cursor: pointer;
}

.slide-line-chart .chart-point:hover {
  r: 8;
}

.slide-line-chart .chart-point.point-pink { fill: var(--sakura-pink); }
.slide-line-chart .chart-point.point-aqua { fill: var(--wave-aqua); }

/* X軸ラベル */
.slide-line-chart .chart-x-labels {
  position: absolute;
  left: 4rem;
  right: 2rem;
  bottom: 1rem;
  display: flex;
  justify-content: space-between;
}

.slide-line-chart .chart-x-label {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* グリッド */
.slide-line-chart .chart-grid {
  stroke: var(--fuji-gray);
  stroke-opacity: 0.3;
  stroke-dasharray: 4 4;
}
```

```html
<div class="slider__item slide-line-chart">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-chart-line"></i> {{タイトル}}</h2>
    <div class="chart-container">
      <div class="chart-axis-y">
        <span class="chart-axis-y-label" style="bottom: 100%;">100</span>
        <span class="chart-axis-y-label" style="bottom: 50%;">50</span>
        <span class="chart-axis-y-label" style="bottom: 0;">0</span>
      </div>
      <div class="chart-axis-x"></div>
      <svg class="chart-svg" viewBox="0 0 600 250" preserveAspectRatio="none">
        <!-- グリッドライン -->
        <line class="chart-grid" x1="0" y1="125" x2="600" y2="125"/>
        <!-- 折れ線 -->
        <polyline class="chart-line" points="0,200 100,150 200,180 300,100 400,120 500,50 600,80"/>
        <!-- データポイント -->
        <circle class="chart-point" cx="0" cy="200" r="5"/>
        <circle class="chart-point" cx="100" cy="150" r="5"/>
        <circle class="chart-point" cx="200" cy="180" r="5"/>
        <circle class="chart-point" cx="300" cy="100" r="5"/>
        <circle class="chart-point" cx="400" cy="120" r="5"/>
        <circle class="chart-point" cx="500" cy="50" r="5"/>
        <circle class="chart-point" cx="600" cy="80" r="5"/>
      </svg>
      <div class="chart-x-labels">
        <span class="chart-x-label">1月</span>
        <span class="chart-x-label">2月</span>
        <span class="chart-x-label">3月</span>
        <span class="chart-x-label">4月</span>
        <span class="chart-x-label">5月</span>
        <span class="chart-x-label">6月</span>
        <span class="chart-x-label">7月</span>
      </div>
    </div>
  </div>
</div>
```

### 13.5 円グラフ（Pie Chart）

```css
.slide-pie-chart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-pie-chart .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-pie-chart .chart-container {
  display: flex;
  align-items: center;
  gap: 3rem;
}

.slide-pie-chart .chart-pie {
  position: relative;
  width: 300px;
  height: 300px;
}

/* CSS conic-gradient ベースの円グラフ */
.slide-pie-chart .pie-chart {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: conic-gradient(
    var(--wave-blue) 0deg 108deg,      /* 30% */
    var(--sakura-pink) 108deg 180deg,  /* 20% */
    var(--wave-aqua) 180deg 270deg,    /* 25% */
    var(--autumn-yellow) 270deg 360deg /* 25% */
  );
  transition: transform 0.3s ease;
}

.slide-pie-chart .pie-chart:hover {
  transform: scale(1.05);
}

/* ドーナツ型（中央に穴） */
.slide-pie-chart .pie-chart.donut::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 60%;
  height: 60%;
  background: var(--bg-dark);
  border-radius: 50%;
}

.slide-pie-chart .pie-center-label {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  z-index: 10;
}

.slide-pie-chart .pie-center-value {
  font-size: var(--fs-title);
  font-weight: 700;
  color: var(--wave-blue);
}

.slide-pie-chart .pie-center-text {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* 凡例 */
.slide-pie-chart .chart-legend {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slide-pie-chart .legend-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slide-pie-chart .legend-color {
  width: 20px;
  height: 20px;
  border-radius: 4px;
}

.slide-pie-chart .legend-color.color-1 { background: var(--wave-blue); }
.slide-pie-chart .legend-color.color-2 { background: var(--sakura-pink); }
.slide-pie-chart .legend-color.color-3 { background: var(--wave-aqua); }
.slide-pie-chart .legend-color.color-4 { background: var(--autumn-yellow); }

.slide-pie-chart .legend-text {
  font-size: var(--fs-body);
}

.slide-pie-chart .legend-value {
  font-weight: 700;
  margin-left: auto;
}
```

```html
<div class="slider__item slide-pie-chart">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-chart-pie"></i> {{タイトル}}</h2>
    <div class="chart-container">
      <div class="chart-pie">
        <div class="pie-chart donut" style="background: conic-gradient(
          var(--wave-blue) 0deg 108deg,
          var(--sakura-pink) 108deg 180deg,
          var(--wave-aqua) 180deg 270deg,
          var(--autumn-yellow) 270deg 360deg
        );"></div>
        <div class="pie-center-label">
          <div class="pie-center-value">100%</div>
          <div class="pie-center-text">合計</div>
        </div>
      </div>
      <div class="chart-legend">
        <div class="legend-item">
          <div class="legend-color color-1"></div>
          <span class="legend-text">{{項目1}}</span>
          <span class="legend-value">30%</span>
        </div>
        <div class="legend-item">
          <div class="legend-color color-2"></div>
          <span class="legend-text">{{項目2}}</span>
          <span class="legend-value">20%</span>
        </div>
        <div class="legend-item">
          <div class="legend-color color-3"></div>
          <span class="legend-text">{{項目3}}</span>
          <span class="legend-value">25%</span>
        </div>
        <div class="legend-item">
          <div class="legend-color color-4"></div>
          <span class="legend-text">{{項目4}}</span>
          <span class="legend-value">25%</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 13.6 時計型円グラフ（1日の流れ）

24時間のタイムスケジュールを時計形式で表示。

```css
.slide-clock-chart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-clock-chart .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-clock-chart .chart-container {
  display: flex;
  align-items: center;
  gap: 3rem;
}

.slide-clock-chart .clock-chart {
  position: relative;
  width: 350px;
  height: 350px;
}

/* 24時間円グラフ（0時が上） */
.slide-clock-chart .clock-pie {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  position: relative;
  /* 例: 睡眠7h(0-7時)、仕事8h(9-17時)、余暇など */
  background: conic-gradient(
    from -90deg,
    var(--wave-blue) 0deg 105deg,      /* 睡眠 0-7時 (7/24 = 105deg) */
    var(--bg-dim) 105deg 135deg,       /* 朝活 7-9時 */
    var(--sakura-pink) 135deg 255deg,  /* 仕事 9-17時 (8/24 = 120deg) */
    var(--wave-aqua) 255deg 300deg,    /* 夕方 17-20時 */
    var(--autumn-yellow) 300deg 360deg /* 夜 20-24時 */
  );
  transition: transform 0.3s ease;
}

.slide-clock-chart .clock-pie:hover {
  transform: scale(1.03);
}

/* 中央の穴 */
.slide-clock-chart .clock-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 50%;
  height: 50%;
  background: var(--bg-dark);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.slide-clock-chart .clock-icon {
  font-size: 2rem;
  color: var(--wave-blue);
  margin-bottom: 0.5rem;
}

.slide-clock-chart .clock-label {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* 時刻マーカー */
.slide-clock-chart .clock-markers {
  position: absolute;
  inset: 0;
}

.slide-clock-chart .clock-marker {
  position: absolute;
  font-size: 0.8rem;
  color: var(--fg-dim);
  font-weight: 700;
}

/* 12時位置から時計回りに配置 */
.slide-clock-chart .clock-marker.h0 { top: 5px; left: 50%; transform: translateX(-50%); }
.slide-clock-chart .clock-marker.h6 { top: 50%; right: 5px; transform: translateY(-50%); }
.slide-clock-chart .clock-marker.h12 { bottom: 5px; left: 50%; transform: translateX(-50%); }
.slide-clock-chart .clock-marker.h18 { top: 50%; left: 5px; transform: translateY(-50%); }

/* 凡例 */
.slide-clock-chart .chart-legend {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slide-clock-chart .legend-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slide-clock-chart .legend-item i {
  width: 24px;
  text-align: center;
}

.slide-clock-chart .legend-color {
  width: 16px;
  height: 16px;
  border-radius: 4px;
}

.slide-clock-chart .legend-time {
  font-size: var(--fs-small);
  color: var(--fg-dim);
  margin-left: auto;
}
```

```html
<div class="slider__item slide-clock-chart">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-clock"></i> 1日のスケジュール</h2>
    <div class="chart-container">
      <div class="clock-chart">
        <div class="clock-pie"></div>
        <div class="clock-center">
          <i class="clock-icon fas fa-sun"></i>
          <span class="clock-label">24時間</span>
        </div>
        <div class="clock-markers">
          <span class="clock-marker h0">0時</span>
          <span class="clock-marker h6">6時</span>
          <span class="clock-marker h12">12時</span>
          <span class="clock-marker h18">18時</span>
        </div>
      </div>
      <div class="chart-legend">
        <div class="legend-item">
          <div class="legend-color" style="background: var(--wave-blue);"></div>
          <i class="fas fa-bed"></i>
          <span>睡眠</span>
          <span class="legend-time">0:00-7:00 (7h)</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: var(--bg-dim);"></div>
          <i class="fas fa-coffee"></i>
          <span>朝活</span>
          <span class="legend-time">7:00-9:00 (2h)</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: var(--sakura-pink);"></div>
          <i class="fas fa-briefcase"></i>
          <span>仕事</span>
          <span class="legend-time">9:00-17:00 (8h)</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: var(--wave-aqua);"></div>
          <i class="fas fa-utensils"></i>
          <span>夕方</span>
          <span class="legend-time">17:00-20:00 (3h)</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: var(--autumn-yellow);"></div>
          <i class="fas fa-book"></i>
          <span>夜</span>
          <span class="legend-time">20:00-24:00 (4h)</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 13.7 散布図（Scatter Plot）

```css
.slide-scatter .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-scatter .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-scatter .chart-container {
  position: relative;
  width: 600px;
  height: 400px;
  padding: 2rem;
}

.slide-scatter .chart-svg {
  width: 100%;
  height: 100%;
}

/* 軸 */
.slide-scatter .axis-line {
  stroke: var(--fuji-gray);
  stroke-width: 2;
}

.slide-scatter .axis-label {
  font-size: var(--fs-small);
  fill: var(--fg-dim);
}

/* グリッド */
.slide-scatter .grid-line {
  stroke: var(--fuji-gray);
  stroke-opacity: 0.2;
  stroke-dasharray: 4 4;
}

/* データポイント */
.slide-scatter .data-point {
  fill: var(--wave-blue);
  stroke: var(--bg-dark);
  stroke-width: 2;
  transition: r 0.3s ease, fill 0.3s ease;
  cursor: pointer;
}

.slide-scatter .data-point:hover {
  r: 10;
  fill: var(--sakura-pink);
}

/* ポイントカラーバリエーション */
.slide-scatter .data-point.group-a { fill: var(--wave-blue); }
.slide-scatter .data-point.group-b { fill: var(--sakura-pink); }
.slide-scatter .data-point.group-c { fill: var(--wave-aqua); }

/* トレンドライン */
.slide-scatter .trend-line {
  stroke: var(--autumn-yellow);
  stroke-width: 2;
  stroke-dasharray: 8 4;
  fill: none;
}

/* 凡例 */
.slide-scatter .chart-legend {
  position: absolute;
  top: 1rem;
  right: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  background: rgba(31, 31, 40, 0.9);
  padding: 0.75rem 1rem;
  border-radius: 8px;
}

.slide-scatter .legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--fs-small);
}

.slide-scatter .legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

/* 軸タイトル */
.slide-scatter .axis-title-x {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

.slide-scatter .axis-title-y {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) rotate(-90deg);
  font-size: var(--fs-small);
  color: var(--fg-dim);
}
```

```html
<div class="slider__item slide-scatter">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-braille"></i> {{タイトル}}</h2>
    <div class="chart-container">
      <svg class="chart-svg" viewBox="0 0 500 350">
        <!-- グリッド -->
        <line class="grid-line" x1="50" y1="50" x2="50" y2="300"/>
        <line class="grid-line" x1="50" y1="300" x2="450" y2="300"/>

        <!-- 軸 -->
        <line class="axis-line" x1="50" y1="300" x2="450" y2="300"/>
        <line class="axis-line" x1="50" y1="50" x2="50" y2="300"/>

        <!-- データポイント グループA -->
        <circle class="data-point group-a" cx="100" cy="250" r="6"/>
        <circle class="data-point group-a" cx="150" cy="200" r="6"/>
        <circle class="data-point group-a" cx="200" cy="180" r="6"/>
        <circle class="data-point group-a" cx="250" cy="150" r="6"/>

        <!-- データポイント グループB -->
        <circle class="data-point group-b" cx="180" cy="220" r="6"/>
        <circle class="data-point group-b" cx="280" cy="160" r="6"/>
        <circle class="data-point group-b" cx="350" cy="100" r="6"/>
        <circle class="data-point group-b" cx="400" cy="80" r="6"/>

        <!-- トレンドライン -->
        <line class="trend-line" x1="80" y1="270" x2="420" y2="70"/>
      </svg>

      <span class="axis-title-x">{{X軸ラベル}}</span>
      <span class="axis-title-y">{{Y軸ラベル}}</span>

      <div class="chart-legend">
        <div class="legend-item">
          <div class="legend-dot" style="background: var(--wave-blue);"></div>
          <span>{{グループA}}</span>
        </div>
        <div class="legend-item">
          <div class="legend-dot" style="background: var(--sakura-pink);"></div>
          <span>{{グループB}}</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 13.8 レーダーチャート（Radar Chart）

```css
.slide-radar .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-radar .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-radar .chart-container {
  display: flex;
  align-items: center;
  gap: 3rem;
}

.slide-radar .radar-chart {
  width: 350px;
  height: 350px;
}

.slide-radar .radar-svg {
  width: 100%;
  height: 100%;
}

/* グリッドライン（5角形/6角形など） */
.slide-radar .radar-grid {
  fill: none;
  stroke: var(--fuji-gray);
  stroke-opacity: 0.3;
}

/* 軸線 */
.slide-radar .radar-axis {
  stroke: var(--fuji-gray);
  stroke-opacity: 0.5;
}

/* データエリア */
.slide-radar .radar-area {
  fill: var(--wave-blue);
  fill-opacity: 0.3;
  stroke: var(--wave-blue);
  stroke-width: 2;
  transition: fill-opacity 0.3s ease;
}

.slide-radar .radar-area:hover {
  fill-opacity: 0.5;
}

/* 複数データセット */
.slide-radar .radar-area.area-pink {
  fill: var(--sakura-pink);
  stroke: var(--sakura-pink);
}

/* データポイント */
.slide-radar .radar-point {
  fill: var(--wave-blue);
  stroke: var(--bg-dark);
  stroke-width: 2;
}

.slide-radar .radar-point.point-pink {
  fill: var(--sakura-pink);
}

/* 軸ラベル */
.slide-radar .radar-label {
  font-size: var(--fs-small);
  fill: var(--fg);
  text-anchor: middle;
}

/* 凡例 */
.slide-radar .chart-legend {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
```

```html
<div class="slider__item slide-radar">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-spider"></i> {{タイトル}}</h2>
    <div class="chart-container">
      <div class="radar-chart">
        <svg class="radar-svg" viewBox="0 0 300 300">
          <!-- 中心点: 150, 150 半径: 100 -->
          <!-- 5角形グリッド -->
          <polygon class="radar-grid" points="150,50 238,105 213,205 87,205 62,105"/>
          <polygon class="radar-grid" points="150,80 209,118 190,178 110,178 91,118"/>
          <polygon class="radar-grid" points="150,110 180,131 168,151 132,151 120,131"/>

          <!-- 軸線 -->
          <line class="radar-axis" x1="150" y1="150" x2="150" y2="50"/>
          <line class="radar-axis" x1="150" y1="150" x2="238" y2="105"/>
          <line class="radar-axis" x1="150" y1="150" x2="213" y2="205"/>
          <line class="radar-axis" x1="150" y1="150" x2="87" y2="205"/>
          <line class="radar-axis" x1="150" y1="150" x2="62" y2="105"/>

          <!-- データエリア -->
          <polygon class="radar-area" points="150,70 200,115 185,180 115,180 100,115"/>

          <!-- データポイント -->
          <circle class="radar-point" cx="150" cy="70" r="4"/>
          <circle class="radar-point" cx="200" cy="115" r="4"/>
          <circle class="radar-point" cx="185" cy="180" r="4"/>
          <circle class="radar-point" cx="115" cy="180" r="4"/>
          <circle class="radar-point" cx="100" cy="115" r="4"/>

          <!-- ラベル -->
          <text class="radar-label" x="150" y="35">{{項目1}}</text>
          <text class="radar-label" x="255" y="105">{{項目2}}</text>
          <text class="radar-label" x="225" y="225">{{項目3}}</text>
          <text class="radar-label" x="75" y="225">{{項目4}}</text>
          <text class="radar-label" x="45" y="105">{{項目5}}</text>
        </svg>
      </div>
      <div class="chart-legend">
        <div class="legend-item">
          <div class="legend-color" style="background: var(--wave-blue);"></div>
          <span>{{データセット名}}</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 13.9 ゲージチャート（進捗インジケーター）

```css
.slide-gauge .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-gauge .chart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-gauge .gauge-container {
  display: flex;
  gap: 3rem;
  justify-content: center;
}

.slide-gauge .gauge {
  position: relative;
  width: 200px;
  height: 120px;
  overflow: hidden;
}

.slide-gauge .gauge-bg {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: conic-gradient(
    from 180deg,
    var(--fuji-gray) 0deg 180deg,
    transparent 180deg 360deg
  );
}

.slide-gauge .gauge-fill {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  /* 例: 75%達成 = 135deg */
  background: conic-gradient(
    from 180deg,
    var(--wave-blue) 0deg 135deg,
    transparent 135deg 360deg
  );
  transition: background 0.5s ease;
}

.slide-gauge .gauge-fill.low {
  background: conic-gradient(
    from 180deg,
    var(--sakura-pink) 0deg var(--fill-angle, 90deg),
    transparent var(--fill-angle, 90deg) 360deg
  );
}

.slide-gauge .gauge-fill.medium {
  background: conic-gradient(
    from 180deg,
    var(--autumn-yellow) 0deg var(--fill-angle, 120deg),
    transparent var(--fill-angle, 120deg) 360deg
  );
}

.slide-gauge .gauge-fill.high {
  background: conic-gradient(
    from 180deg,
    var(--spring-green) 0deg var(--fill-angle, 160deg),
    transparent var(--fill-angle, 160deg) 360deg
  );
}

.slide-gauge .gauge-center {
  position: absolute;
  width: 160px;
  height: 160px;
  top: 20px;
  left: 20px;
  background: var(--bg-dark);
  border-radius: 50%;
}

.slide-gauge .gauge-value {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
}

.slide-gauge .gauge-number {
  font-size: var(--fs-title);
  font-weight: 700;
  color: var(--wave-blue);
}

.slide-gauge .gauge-label {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* マーカー */
.slide-gauge .gauge-markers {
  position: absolute;
  width: 100%;
  display: flex;
  justify-content: space-between;
  bottom: 0;
  padding: 0 10px;
}

.slide-gauge .gauge-marker {
  font-size: 0.7rem;
  color: var(--fg-dim);
}
```

```html
<div class="slider__item slide-gauge">
  <div class="slider__content">
    <h2 class="chart-title"><i class="fas fa-tachometer-alt"></i> {{タイトル}}</h2>
    <div class="gauge-container">
      <div class="gauge">
        <div class="gauge-bg"></div>
        <div class="gauge-fill high" style="--fill-angle: 135deg;"></div>
        <div class="gauge-center"></div>
        <div class="gauge-value">
          <div class="gauge-number">75%</div>
          <div class="gauge-label">{{ラベル1}}</div>
        </div>
        <div class="gauge-markers">
          <span class="gauge-marker">0</span>
          <span class="gauge-marker">100</span>
        </div>
      </div>
      <div class="gauge">
        <div class="gauge-bg"></div>
        <div class="gauge-fill medium" style="--fill-angle: 100deg;"></div>
        <div class="gauge-center"></div>
        <div class="gauge-value">
          <div class="gauge-number">55%</div>
          <div class="gauge-label">{{ラベル2}}</div>
        </div>
        <div class="gauge-markers">
          <span class="gauge-marker">0</span>
          <span class="gauge-marker">100</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

---

## 14. アイコン推奨ガイド

### 14.1 図解タイプ別推奨アイコン

| 図解タイプ | 推奨アイコン | 用途 |
|-----------|------------|------|
| サイクル | `fa-sync-alt`, `fa-recycle`, `fa-redo` | 循環・継続 |
| ベン図 | `fa-circle-notch`, `fa-venn-diagram` | 重なり・交差 |
| マインドマップ | `fa-project-diagram`, `fa-sitemap`, `fa-network-wired` | 構造・接続 |
| フローチャート | `fa-sitemap`, `fa-code-branch`, `fa-stream` | 分岐・フロー |
| 成長グラフ | `fa-chart-line`, `fa-arrow-trend-up`, `fa-rocket` | 上昇・成長 |
| 比較 | `fa-balance-scale`, `fa-not-equal`, `fa-columns` | 対比・比較 |
| マトリックス | `fa-th`, `fa-border-all`, `fa-table` | 分類・整理 |
| ガントチャート | `fa-tasks`, `fa-calendar-alt`, `fa-list-check` | スケジュール |
| 表 | `fa-table`, `fa-list-alt`, `fa-th-list` | データ表示 |

### 14.2 カテゴリ別アイコン推奨

#### ビジネス・業務
| 概念 | アイコン |
|-----|---------|
| 目標 | `fa-bullseye`, `fa-flag`, `fa-target` |
| 戦略 | `fa-chess`, `fa-chess-knight`, `fa-lightbulb` |
| 分析 | `fa-chart-bar`, `fa-magnifying-glass-chart`, `fa-microscope` |
| 会議 | `fa-users`, `fa-handshake`, `fa-comments` |
| 成果 | `fa-trophy`, `fa-medal`, `fa-award` |
| 課題 | `fa-exclamation-triangle`, `fa-circle-exclamation`, `fa-question` |
| 解決 | `fa-check-circle`, `fa-thumbs-up`, `fa-sparkles` |

#### プロセス・フロー
| 概念 | アイコン |
|-----|---------|
| 開始 | `fa-play`, `fa-flag-checkered`, `fa-circle-play` |
| 終了 | `fa-stop`, `fa-flag`, `fa-circle-stop` |
| 次へ | `fa-arrow-right`, `fa-chevron-right`, `fa-forward` |
| 戻る | `fa-arrow-left`, `fa-chevron-left`, `fa-backward` |
| 繰り返し | `fa-sync`, `fa-rotate`, `fa-arrows-rotate` |
| 分岐 | `fa-code-branch`, `fa-route`, `fa-shuffle` |

#### 時間・スケジュール
| 概念 | アイコン |
|-----|---------|
| 時間 | `fa-clock`, `fa-hourglass`, `fa-stopwatch` |
| カレンダー | `fa-calendar`, `fa-calendar-day`, `fa-calendar-check` |
| 締め切り | `fa-bell`, `fa-alarm-clock`, `fa-calendar-times` |
| 期間 | `fa-hourglass-half`, `fa-timeline`, `fa-arrows-left-right` |

#### 品質・状態
| 概念 | アイコン |
|-----|---------|
| 成功 | `fa-check`, `fa-circle-check`, `fa-thumbs-up` |
| 警告 | `fa-exclamation-triangle`, `fa-triangle-exclamation` |
| エラー | `fa-times`, `fa-circle-xmark`, `fa-ban` |
| 進行中 | `fa-spinner`, `fa-clock`, `fa-hourglass-half` |
| 完了 | `fa-check-double`, `fa-flag-checkered` |

#### テクノロジー・IT
| 概念 | アイコン |
|-----|---------|
| AI | `fa-robot`, `fa-brain`, `fa-microchip` |
| データ | `fa-database`, `fa-server`, `fa-hard-drive` |
| クラウド | `fa-cloud`, `fa-cloud-arrow-up`, `fa-cloud-arrow-down` |
| セキュリティ | `fa-shield`, `fa-lock`, `fa-key` |
| コード | `fa-code`, `fa-terminal`, `fa-laptop-code` |
| API | `fa-plug`, `fa-link`, `fa-network-wired` |

#### 人・組織
| 概念 | アイコン |
|-----|---------|
| ユーザー | `fa-user`, `fa-user-circle`, `fa-id-card` |
| チーム | `fa-users`, `fa-people-group`, `fa-user-friends` |
| リーダー | `fa-user-tie`, `fa-crown`, `fa-star` |
| コミュニケーション | `fa-comments`, `fa-envelope`, `fa-message` |

### 14.3 アイコン使用ガイドライン

1. **一貫性**: 同じプレゼン内で同じ概念には同じアイコンを使用
2. **シンプルさ**: 図解要素には装飾的でない明確なアイコンを選択
3. **サイズ**:
   - タイトル用: `2rem` ~ `3rem`
   - 図解要素内: `1.5rem` ~ `2rem`
   - 補足用: `1rem` ~ `1.2rem`
4. **色**: テーマカラー（`--wave-blue`, `--sakura-pink`等）と調和させる

```css
/* アイコンサイズクラス */
.icon-lg { font-size: 2.5rem; }
.icon-md { font-size: 1.5rem; }
.icon-sm { font-size: 1rem; }

/* アイコンカラークラス */
.icon-blue { color: var(--wave-blue); }
.icon-pink { color: var(--sakura-pink); }
.icon-aqua { color: var(--wave-aqua); }
.icon-yellow { color: var(--autumn-yellow); }
.icon-green { color: var(--spring-green); }
```

---

## 15. グラフ・チャート選択ガイド

### 15.1 データ特性別推奨タイプ

| データ特性 | 推奨チャート | 備考 |
|-----------|------------|------|
| 量の比較 | 縦棒/横棒グラフ | カテゴリ数が多い場合は横棒 |
| 割合・構成 | 円グラフ/積み上げ棒 | 項目数5以下推奨 |
| 時系列変化 | 折れ線グラフ | トレンド把握に最適 |
| 相関関係 | 散布図 | 2変数の関係性可視化 |
| 多軸評価 | レーダーチャート | 5-8軸推奨 |
| 進捗状況 | ゲージチャート | 単一KPI表示に最適 |
| 時間割当 | 時計型円グラフ | 24時間表現に最適 |
| プロジェクト計画 | ガントチャート | タスク期間の可視化 |

### 15.2 チェックリスト

| チャートタイプ | チェック項目 |
|--------------|-------------|
| **縦棒グラフ** | □ Y軸ラベルが設定されているか、□ バーの色分けが意味を持つか |
| **横棒グラフ** | □ ラベルが読みやすい幅か、□ 値がバー内/外で適切か |
| **積み上げ棒** | □ 凡例が設定されているか、□ セグメント数は4以下か |
| **折れ線グラフ** | □ データポイントが視認可能か、□ 複数線の場合色分けは明確か |
| **円グラフ** | □ 項目数は5以下か、□ 凡例との対応が明確か |
| **散布図** | □ 軸タイトルが設定されているか、□ トレンドラインは必要か |
| **レーダーチャート** | □ 軸数は5-8か、□ 軸ラベルが配置されているか |
| **ゲージチャート** | □ 目標値が明確か、□ 色分けが直感的か |

---

