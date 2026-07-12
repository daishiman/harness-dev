# 図解タイプ: ビジュアル系（SVG2+CSS ハイブリッド版）

**責務**: 購買ファネル、組織図、シェブロン、人物関係図、縦タイムライン、PDCA、三角サイクル、ウェーブステップ、アイコン選択グリッドのSVG2/CSSテンプレート

**含まれるタイプ**: 11.21-11.29

**前提**: [svg-diagram-primitives.md](svg-diagram-primitives.md) のSVG2プリミティブを参照

**方針**: ファネル(11.21)はインラインSVG2で描画済み。組織図・PDCA・三角サイクルはCSS維持（SVG2移行は将来対応）。カード型レイアウト（シェブロン、ウェーブステップ）はCSS維持。人物関係図・三角サイクルはCSS+SVG接続線のハイブリッド。

---


### 11.21 購買ファネル型（Funnel・SVG2）

SVG polygonで滑らかな台形段階を描画。clip-pathの印刷問題を解消。

```css
.slide-funnel .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-funnel .funnel-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-funnel .funnel-container {
  display: flex;
  align-items: center;
  gap: 3rem;
}

.slide-funnel .diagram-svg-container {
  width: 100%;
  max-width: 450px;
  aspect-ratio: 4 / 5;
}

.slide-funnel .diagram-svg .funnel-level {
  cursor: pointer;
  transition: opacity 0.3s ease, filter 0.3s ease;
}

.slide-funnel .diagram-svg .funnel-level:hover {
  filter: brightness(1.1);
}

/* 右側の統計情報（CSS維持） */
.slide-funnel .funnel-stats {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slide-funnel .funnel-stat {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--bg-dim);
  border-radius: 8px;
  border-left: 3px solid var(--wave-blue);
}

.slide-funnel .funnel-stat:nth-child(1) { border-left-color: var(--wave-blue); }
.slide-funnel .funnel-stat:nth-child(2) { border-left-color: var(--wave-aqua); }
.slide-funnel .funnel-stat:nth-child(3) { border-left-color: var(--spring-green); }
.slide-funnel .funnel-stat:nth-child(4) { border-left-color: var(--autumn-yellow); }
.slide-funnel .funnel-stat:nth-child(5) { border-left-color: var(--sakura-pink); }

.slide-funnel .funnel-stat-value {
  font-size: var(--fs-subheading);
  font-weight: 700;
}

.slide-funnel .funnel-stat-label {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}
```

```html
<div class="slider__item slide-funnel">
  <div class="slider__content">
    <h2 class="funnel-title"><i class="fas fa-filter"></i> {{タイトル}}</h2>
    <div class="funnel-container">
      <div class="diagram-svg-container">
        <svg viewBox="0 0 400 450" xmlns="http://www.w3.org/2000/svg"
             class="diagram-svg" role="img" aria-label="{{タイトル}}のファネル図">
          <defs>
            <filter id="fn-shadow" x="-5%" y="-5%" width="110%" height="115%">
              <feDropShadow dx="2" dy="3" stdDeviation="3" flood-color="#000" flood-opacity="0.2" />
            </filter>
          </defs>

          <!-- レベル1（最上段・最大幅） -->
          <g class="funnel-level has-tooltip" data-tooltip="{{詳細1}}">
            <polygon points="10,0 390,0 370,80 30,80"
                     fill="var(--wave-blue,#7E9CD8)" filter="url(#fn-shadow)" />
            <text x="200" y="45" text-anchor="middle" dominant-baseline="central"
                  fill="var(--bg-dark,#1F1F28)" font-weight="600" font-size="15">
              {{段階1}} 100%
            </text>
          </g>

          <!-- レベル2 -->
          <g class="funnel-level has-tooltip" data-tooltip="{{詳細2}}">
            <polygon points="35,85 365,85 340,165 60,165"
                     fill="var(--wave-aqua,#7AA89F)" filter="url(#fn-shadow)" />
            <text x="200" y="130" text-anchor="middle" dominant-baseline="central"
                  fill="var(--bg-dark,#1F1F28)" font-weight="600" font-size="15">
              {{段階2}} 60%
            </text>
          </g>

          <!-- レベル3 -->
          <g class="funnel-level has-tooltip" data-tooltip="{{詳細3}}">
            <polygon points="65,170 335,170 310,250 90,250"
                     fill="var(--spring-green,#98BB6C)" filter="url(#fn-shadow)" />
            <text x="200" y="215" text-anchor="middle" dominant-baseline="central"
                  fill="var(--bg-dark,#1F1F28)" font-weight="600" font-size="15">
              {{段階3}} 30%
            </text>
          </g>

          <!-- レベル4 -->
          <g class="funnel-level has-tooltip" data-tooltip="{{詳細4}}">
            <polygon points="95,255 305,255 280,335 120,335"
                     fill="var(--autumn-yellow,#DCA561)" filter="url(#fn-shadow)" />
            <text x="200" y="300" text-anchor="middle" dominant-baseline="central"
                  fill="var(--bg-dark,#1F1F28)" font-weight="600" font-size="15">
              {{段階4}} 10%
            </text>
          </g>

          <!-- レベル5（最下段） -->
          <g class="funnel-level has-tooltip" data-tooltip="{{詳細5}}">
            <polygon points="125,340 275,340 260,420 140,420"
                     fill="var(--sakura-pink,#D27E99)" filter="url(#fn-shadow)" />
            <text x="200" y="385" text-anchor="middle" dominant-baseline="central"
                  fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="15">
              {{段階5}} 5%
            </text>
          </g>
        </svg>
      </div>
      <div class="funnel-stats">
        <div class="funnel-stat">
          <div class="funnel-stat-value">{{数値1}}</div>
          <div class="funnel-stat-label">{{ラベル1}}</div>
        </div>
        <!-- 必要に応じて追加 -->
      </div>
    </div>
  </div>
</div>
```

### 11.22 組織図型（Org Chart）

階層的な組織構造を表示。

```css
.slide-org-chart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-org-chart .org-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-org-chart .org-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
}

.slide-org-chart .org-level {
  display: flex;
  justify-content: center;
  gap: 2rem;
  position: relative;
}

/* ノード */
.slide-org-chart .org-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  background: var(--bg-dim);
  border-radius: 12px;
  border: 2px solid var(--wave-blue);
  min-width: 120px;
  text-align: center;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  position: relative;
}

.slide-org-chart .org-node:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}

/* トップレベル（CEO等） */
.slide-org-chart .org-node.top {
  background: linear-gradient(135deg, var(--wave-blue), var(--sakura-pink));
  color: var(--bg-dark);
  border: none;
  padding: 1.25rem 2rem;
}

.slide-org-chart .org-node-icon {
  font-size: 1.5rem;
}

.slide-org-chart .org-node.top .org-node-icon {
  color: var(--bg-dark);
}

.slide-org-chart .org-node-name {
  font-weight: 700;
}

.slide-org-chart .org-node-title {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

.slide-org-chart .org-node.top .org-node-title {
  color: rgba(31, 31, 40, 0.7);
}

/* 接続線 */
.slide-org-chart .org-connector {
  display: flex;
  justify-content: center;
  height: 30px;
}

.slide-org-chart .org-connector-line {
  width: 2px;
  height: 100%;
  background: var(--fuji-gray);
}

.slide-org-chart .org-connector-branch {
  display: flex;
  align-items: flex-end;
  height: 30px;
}

.slide-org-chart .org-connector-branch::before {
  content: '';
  position: absolute;
  top: -30px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  height: 2px;
  background: var(--fuji-gray);
}

/* 中間レベル */
.slide-org-chart .org-level.middle .org-node {
  border-color: var(--wave-aqua);
}

/* 下位レベル */
.slide-org-chart .org-level.bottom .org-node {
  border-color: var(--spring-green);
  min-width: 100px;
  padding: 0.75rem 1rem;
  font-size: var(--fs-small);
}
```

```html
<div class="slider__item slide-org-chart">
  <div class="slider__content">
    <h2 class="org-title"><i class="fas fa-sitemap"></i> {{タイトル}}</h2>
    <div class="org-container">
      <!-- トップレベル -->
      <div class="org-level">
        <div class="org-node top">
          <div class="org-node-icon"><i class="fas fa-crown"></i></div>
          <div class="org-node-name">{{トップ名}}</div>
          <div class="org-node-title">{{トップ役職}}</div>
        </div>
      </div>
      <div class="org-connector">
        <div class="org-connector-line"></div>
      </div>
      <!-- 中間レベル -->
      <div class="org-level middle">
        <div class="org-node">
          <div class="org-node-icon"><i class="fas {{アイコン1}}"></i></div>
          <div class="org-node-name">{{部門1}}</div>
        </div>
        <div class="org-node">
          <div class="org-node-icon"><i class="fas {{アイコン2}}"></i></div>
          <div class="org-node-name">{{部門2}}</div>
        </div>
        <div class="org-node">
          <div class="org-node-icon"><i class="fas {{アイコン3}}"></i></div>
          <div class="org-node-name">{{部門3}}</div>
        </div>
      </div>
      <!-- 下位レベル（必要に応じて） -->
    </div>
  </div>
</div>
```

### 11.23 シェブロン/矢印ステップ型（Chevron Steps）

水平方向の矢印形状ステップ。

```css
.slide-chevron .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-chevron .chevron-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-chevron .chevron-container {
  display: flex;
  gap: 0;
  width: 100%;
  max-width: 1000px;
}

.slide-chevron .chevron-step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1.5rem 2rem;
  text-align: center;
  position: relative;
  transition: filter 0.3s ease;
  clip-path: polygon(0 0, calc(100% - 20px) 0, 100% 50%, calc(100% - 20px) 100%, 0 100%, 20px 50%);
  margin-left: -10px;
}

.slide-chevron .chevron-step:first-child {
  clip-path: polygon(0 0, calc(100% - 20px) 0, 100% 50%, calc(100% - 20px) 100%, 0 100%, 0 50%);
  margin-left: 0;
}

.slide-chevron .chevron-step:last-child {
  clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%, 20px 50%);
}

.slide-chevron .chevron-step:hover {
  filter: brightness(1.15);
  z-index: 10;
}

/* ステップカラー */
.slide-chevron .chevron-step:nth-child(1) { background: var(--wave-blue); }
.slide-chevron .chevron-step:nth-child(2) { background: var(--wave-aqua); }
.slide-chevron .chevron-step:nth-child(3) { background: var(--spring-green); }
.slide-chevron .chevron-step:nth-child(4) { background: var(--autumn-yellow); }
.slide-chevron .chevron-step:nth-child(5) { background: var(--sakura-pink); }

.slide-chevron .chevron-step-number {
  width: 30px;
  height: 30px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: var(--fs-small);
  color: var(--bg-dark);
}

.slide-chevron .chevron-step-text {
  font-weight: 600;
  color: var(--bg-dark);
}

.slide-chevron .chevron-step-desc {
  font-size: var(--fs-small);
  color: rgba(31, 31, 40, 0.7);
}
```

```html
<div class="slider__item slide-chevron">
  <div class="slider__content">
    <h2 class="chevron-title"><i class="fas fa-chevron-right"></i> {{タイトル}}</h2>
    <div class="chevron-container">
      <div class="chevron-step">
        <div class="chevron-step-number">1</div>
        <div class="chevron-step-text">{{ステップ1}}</div>
        <div class="chevron-step-desc">{{説明1}}</div>
      </div>
      <div class="chevron-step">
        <div class="chevron-step-number">2</div>
        <div class="chevron-step-text">{{ステップ2}}</div>
        <div class="chevron-step-desc">{{説明2}}</div>
      </div>
      <div class="chevron-step">
        <div class="chevron-step-number">3</div>
        <div class="chevron-step-text">{{ステップ3}}</div>
        <div class="chevron-step-desc">{{説明3}}</div>
      </div>
      <div class="chevron-step">
        <div class="chevron-step-number">4</div>
        <div class="chevron-step-text">{{ステップ4}}</div>
        <div class="chevron-step-desc">{{説明4}}</div>
      </div>
    </div>
  </div>
</div>
```

### 11.24 人物関係図型（Person Network）

中心人物と周囲のステークホルダーとの関係を表示。

```css
.slide-person-network .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-person-network .pn-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-person-network .pn-container {
  position: relative;
  width: 600px;
  height: 500px;
}

/* 中心人物 */
.slide-person-network .pn-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 150px;
  height: 150px;
  background: linear-gradient(135deg, var(--wave-blue), var(--sakura-pink));
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--bg-dark);
  z-index: 10;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
}

.slide-person-network .pn-center-icon {
  font-size: 3rem;
  margin-bottom: 0.5rem;
}

.slide-person-network .pn-center-text {
  font-weight: 700;
}

/* 周囲のノード */
.slide-person-network .pn-node {
  position: absolute;
  width: 100px;
  height: 100px;
  background: var(--bg-dim);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  border: 3px solid var(--wave-blue);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-person-network .pn-node:hover {
  transform: scale(1.15);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  z-index: 20;
}

/* 6方向配置 */
.slide-person-network .pn-node:nth-child(1) { top: 30px; left: 50%; transform: translateX(-50%); border-color: var(--wave-blue); }
.slide-person-network .pn-node:nth-child(2) { top: 100px; right: 50px; border-color: var(--wave-aqua); }
.slide-person-network .pn-node:nth-child(3) { bottom: 100px; right: 50px; border-color: var(--spring-green); }
.slide-person-network .pn-node:nth-child(4) { bottom: 30px; left: 50%; transform: translateX(-50%); border-color: var(--autumn-yellow); }
.slide-person-network .pn-node:nth-child(5) { bottom: 100px; left: 50px; border-color: var(--sakura-pink); }
.slide-person-network .pn-node:nth-child(6) { top: 100px; left: 50px; border-color: var(--wave-blue); }

.slide-person-network .pn-node-icon {
  font-size: 1.5rem;
  margin-bottom: 0.25rem;
}

.slide-person-network .pn-node-text {
  font-size: var(--fs-small);
  font-weight: 600;
}

/* 接続線 */
.slide-person-network .pn-lines {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.slide-person-network .pn-line {
  stroke: var(--fuji-gray);
  stroke-width: 2;
  stroke-dasharray: 5 5;
}
```

```html
<div class="slider__item slide-person-network">
  <div class="slider__content">
    <h2 class="pn-title"><i class="fas fa-users"></i> {{タイトル}}</h2>
    <div class="pn-container">
      <!-- 接続線SVG -->
      <svg class="pn-lines" viewBox="0 0 600 500">
        <line class="pn-line" x1="300" y1="250" x2="300" y2="80"/>
        <line class="pn-line" x1="300" y1="250" x2="500" y2="150"/>
        <line class="pn-line" x1="300" y1="250" x2="500" y2="350"/>
        <line class="pn-line" x1="300" y1="250" x2="300" y2="420"/>
        <line class="pn-line" x1="300" y1="250" x2="100" y2="350"/>
        <line class="pn-line" x1="300" y1="250" x2="100" y2="150"/>
      </svg>

      <!-- 周囲のノード -->
      <div class="pn-node">
        <div class="pn-node-icon"><i class="fas fa-handshake"></i></div>
        <div class="pn-node-text">{{関係者1}}</div>
      </div>
      <div class="pn-node">
        <div class="pn-node-icon"><i class="fas fa-user-tie"></i></div>
        <div class="pn-node-text">{{関係者2}}</div>
      </div>
      <div class="pn-node">
        <div class="pn-node-icon"><i class="fas fa-users"></i></div>
        <div class="pn-node-text">{{関係者3}}</div>
      </div>
      <div class="pn-node">
        <div class="pn-node-icon"><i class="fas fa-building"></i></div>
        <div class="pn-node-text">{{関係者4}}</div>
      </div>
      <div class="pn-node">
        <div class="pn-node-icon"><i class="fas fa-chart-line"></i></div>
        <div class="pn-node-text">{{関係者5}}</div>
      </div>
      <div class="pn-node">
        <div class="pn-node-icon"><i class="fas fa-cog"></i></div>
        <div class="pn-node-text">{{関係者6}}</div>
      </div>

      <!-- 中心人物 -->
      <div class="pn-center">
        <div class="pn-center-icon"><i class="fas fa-user"></i></div>
        <div class="pn-center-text">{{中心人物}}</div>
      </div>
    </div>
  </div>
</div>
```

### 11.25 縦タイムラインステップ型（Vertical Timeline Steps）

縦方向のステップ形式タイムライン。

```css
.slide-vertical-steps .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.slide-vertical-steps .vs-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-vertical-steps .vs-container {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding-left: 40px;
  position: relative;
}

/* 縦線 */
.slide-vertical-steps .vs-container::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--fuji-gray);
}

.slide-vertical-steps .vs-step {
  display: flex;
  gap: 1.5rem;
  padding: 1.5rem 0;
  position: relative;
}

/* ステップポイント */
.slide-vertical-steps .vs-step::before {
  content: '';
  position: absolute;
  left: -32px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  background: var(--wave-blue);
  border-radius: 50%;
  border: 3px solid var(--bg-dark);
  box-shadow: 0 0 0 3px var(--wave-blue);
  z-index: 2;
}

.slide-vertical-steps .vs-step:nth-child(1)::before { background: var(--wave-blue); box-shadow: 0 0 0 3px var(--wave-blue); }
.slide-vertical-steps .vs-step:nth-child(2)::before { background: var(--wave-aqua); box-shadow: 0 0 0 3px var(--wave-aqua); }
.slide-vertical-steps .vs-step:nth-child(3)::before { background: var(--spring-green); box-shadow: 0 0 0 3px var(--spring-green); }
.slide-vertical-steps .vs-step:nth-child(4)::before { background: var(--autumn-yellow); box-shadow: 0 0 0 3px var(--autumn-yellow); }
.slide-vertical-steps .vs-step:nth-child(5)::before { background: var(--sakura-pink); box-shadow: 0 0 0 3px var(--sakura-pink); }

.slide-vertical-steps .vs-step-number {
  width: 50px;
  height: 50px;
  background: var(--bg-dim);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: var(--fs-body-lg);
  flex-shrink: 0;
}

.slide-vertical-steps .vs-step:nth-child(1) .vs-step-number { color: var(--wave-blue); }
.slide-vertical-steps .vs-step:nth-child(2) .vs-step-number { color: var(--wave-aqua); }
.slide-vertical-steps .vs-step:nth-child(3) .vs-step-number { color: var(--spring-green); }
.slide-vertical-steps .vs-step:nth-child(4) .vs-step-number { color: var(--autumn-yellow); }
.slide-vertical-steps .vs-step:nth-child(5) .vs-step-number { color: var(--sakura-pink); }

.slide-vertical-steps .vs-step-content {
  flex: 1;
  background: var(--bg-dim);
  padding: 1.25rem;
  border-radius: 12px;
  border-left: 4px solid var(--wave-blue);
  transition: transform 0.3s ease;
}

.slide-vertical-steps .vs-step:hover .vs-step-content {
  transform: translateX(10px);
}

.slide-vertical-steps .vs-step:nth-child(1) .vs-step-content { border-left-color: var(--wave-blue); }
.slide-vertical-steps .vs-step:nth-child(2) .vs-step-content { border-left-color: var(--wave-aqua); }
.slide-vertical-steps .vs-step:nth-child(3) .vs-step-content { border-left-color: var(--spring-green); }
.slide-vertical-steps .vs-step:nth-child(4) .vs-step-content { border-left-color: var(--autumn-yellow); }
.slide-vertical-steps .vs-step:nth-child(5) .vs-step-content { border-left-color: var(--sakura-pink); }

.slide-vertical-steps .vs-step-title {
  font-size: var(--fs-subheading);
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.slide-vertical-steps .vs-step-desc {
  font-size: var(--fs-body);
  color: var(--fg-dim);
}
```

```html
<div class="slider__item slide-vertical-steps">
  <div class="slider__content">
    <h2 class="vs-title"><i class="fas fa-list-ol"></i> {{タイトル}}</h2>
    <div class="vs-container">
      <div class="vs-step">
        <div class="vs-step-number">1</div>
        <div class="vs-step-content">
          <div class="vs-step-title">{{ステップ1}}</div>
          <div class="vs-step-desc">{{説明1}}</div>
        </div>
      </div>
      <div class="vs-step">
        <div class="vs-step-number">2</div>
        <div class="vs-step-content">
          <div class="vs-step-title">{{ステップ2}}</div>
          <div class="vs-step-desc">{{説明2}}</div>
        </div>
      </div>
      <div class="vs-step">
        <div class="vs-step-number">3</div>
        <div class="vs-step-content">
          <div class="vs-step-title">{{ステップ3}}</div>
          <div class="vs-step-desc">{{説明3}}</div>
        </div>
      </div>
      <div class="vs-step">
        <div class="vs-step-number">4</div>
        <div class="vs-step-content">
          <div class="vs-step-title">{{ステップ4}}</div>
          <div class="vs-step-desc">{{説明4}}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 11.26 PDCAサイクル型

継続的改善のPDCAサイクルを表示。

```css
.slide-pdca .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-pdca .pdca-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-pdca .pdca-container {
  position: relative;
  width: 450px;
  height: 450px;
}

/* 4象限 */
.slide-pdca .pdca-quadrant {
  position: absolute;
  width: 200px;
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  cursor: pointer;
}

.slide-pdca .pdca-quadrant:hover {
  transform: scale(1.05);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  z-index: 10;
}

/* 位置 */
.slide-pdca .pdca-quadrant.plan {
  top: 0;
  left: 0;
  background: var(--wave-blue);
  border-radius: 100% 0 0 0;
}

.slide-pdca .pdca-quadrant.do {
  top: 0;
  right: 0;
  background: var(--spring-green);
  border-radius: 0 100% 0 0;
}

.slide-pdca .pdca-quadrant.check {
  bottom: 0;
  right: 0;
  background: var(--autumn-yellow);
  border-radius: 0 0 100% 0;
}

.slide-pdca .pdca-quadrant.act {
  bottom: 0;
  left: 0;
  background: var(--sakura-pink);
  border-radius: 0 0 0 100%;
}

.slide-pdca .pdca-label {
  font-size: var(--fs-subtitle);
  font-weight: 700;
  color: var(--bg-dark);
}

.slide-pdca .pdca-desc {
  font-size: var(--fs-small);
  color: rgba(31, 31, 40, 0.7);
  margin-top: 0.5rem;
}

/* 中心円 */
.slide-pdca .pdca-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100px;
  height: 100px;
  background: var(--bg-dark);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 20;
  box-shadow: 0 0 30px rgba(0, 0, 0, 0.5);
}

.slide-pdca .pdca-center-icon {
  font-size: 2rem;
  color: var(--wave-blue);
}

.slide-pdca .pdca-center-text {
  font-size: var(--fs-small);
  color: var(--fg-dim);
  margin-top: 0.25rem;
}

/* 矢印 */
.slide-pdca .pdca-arrows {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 15;
}

.slide-pdca .pdca-arrow {
  position: absolute;
  font-size: 1.5rem;
  color: var(--bg-dark);
}

.slide-pdca .pdca-arrow.arrow-1 { top: 90px; left: 50%; transform: translateX(-50%); }
.slide-pdca .pdca-arrow.arrow-2 { top: 50%; right: 90px; transform: translateY(-50%) rotate(90deg); }
.slide-pdca .pdca-arrow.arrow-3 { bottom: 90px; left: 50%; transform: translateX(-50%) rotate(180deg); }
.slide-pdca .pdca-arrow.arrow-4 { top: 50%; left: 90px; transform: translateY(-50%) rotate(270deg); }
```

```html
<div class="slider__item slide-pdca">
  <div class="slider__content">
    <h2 class="pdca-title"><i class="fas fa-sync-alt"></i> {{タイトル}}</h2>
    <div class="pdca-container">
      <div class="pdca-quadrant plan has-tooltip" data-tooltip="{{Plan詳細}}">
        <div class="pdca-label">Plan</div>
        <div class="pdca-desc">計画</div>
      </div>
      <div class="pdca-quadrant do has-tooltip" data-tooltip="{{Do詳細}}">
        <div class="pdca-label">Do</div>
        <div class="pdca-desc">実行</div>
      </div>
      <div class="pdca-quadrant check has-tooltip" data-tooltip="{{Check詳細}}">
        <div class="pdca-label">Check</div>
        <div class="pdca-desc">評価</div>
      </div>
      <div class="pdca-quadrant act has-tooltip" data-tooltip="{{Act詳細}}">
        <div class="pdca-label">Act</div>
        <div class="pdca-desc">改善</div>
      </div>

      <div class="pdca-center">
        <div class="pdca-center-icon"><i class="fas fa-redo"></i></div>
        <div class="pdca-center-text">継続改善</div>
      </div>

      <div class="pdca-arrows">
        <div class="pdca-arrow arrow-1"><i class="fas fa-chevron-right"></i></div>
        <div class="pdca-arrow arrow-2"><i class="fas fa-chevron-right"></i></div>
        <div class="pdca-arrow arrow-3"><i class="fas fa-chevron-right"></i></div>
        <div class="pdca-arrow arrow-4"><i class="fas fa-chevron-right"></i></div>
      </div>
    </div>
  </div>
</div>
```

### 11.27 三角サイクル型（Triangle Cycle）

3要素の循環関係を三角形で表示。

```css
.slide-triangle-cycle .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-triangle-cycle .tc-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-triangle-cycle .tc-container {
  position: relative;
  width: 500px;
  height: 450px;
}

/* 3つのノード */
.slide-triangle-cycle .tc-node {
  position: absolute;
  width: 140px;
  height: 140px;
  background: var(--bg-dim);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  border: 4px solid var(--wave-blue);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-triangle-cycle .tc-node:hover {
  transform: scale(1.1);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
  z-index: 10;
}

/* 3点配置 */
.slide-triangle-cycle .tc-node:nth-child(1) {
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  border-color: var(--wave-blue);
}

.slide-triangle-cycle .tc-node:nth-child(2) {
  bottom: 50px;
  left: 50px;
  border-color: var(--spring-green);
}

.slide-triangle-cycle .tc-node:nth-child(3) {
  bottom: 50px;
  right: 50px;
  border-color: var(--sakura-pink);
}

.slide-triangle-cycle .tc-node-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.slide-triangle-cycle .tc-node:nth-child(1) .tc-node-icon { color: var(--wave-blue); }
.slide-triangle-cycle .tc-node:nth-child(2) .tc-node-icon { color: var(--spring-green); }
.slide-triangle-cycle .tc-node:nth-child(3) .tc-node-icon { color: var(--sakura-pink); }

.slide-triangle-cycle .tc-node-text {
  font-weight: 700;
}

/* 中心 */
.slide-triangle-cycle .tc-center {
  position: absolute;
  top: 55%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100px;
  height: 100px;
  background: linear-gradient(135deg, var(--wave-blue), var(--sakura-pink));
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--bg-dark);
  z-index: 5;
}

.slide-triangle-cycle .tc-center-icon {
  font-size: 1.5rem;
}

.slide-triangle-cycle .tc-center-text {
  font-size: var(--fs-small);
  font-weight: 600;
}

/* 接続矢印 */
.slide-triangle-cycle .tc-arrows {
  position: absolute;
  inset: 0;
}

.slide-triangle-cycle .tc-arrow-svg {
  width: 100%;
  height: 100%;
}

.slide-triangle-cycle .tc-arrow-path {
  fill: none;
  stroke: var(--fuji-gray);
  stroke-width: 2;
  marker-end: url(#arrowhead);
}
```

```html
<div class="slider__item slide-triangle-cycle">
  <div class="slider__content">
    <h2 class="tc-title"><i class="fas fa-recycle"></i> {{タイトル}}</h2>
    <div class="tc-container">
      <!-- 矢印SVG -->
      <svg class="tc-arrows tc-arrow-svg" viewBox="0 0 500 450">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="var(--autumn-yellow)"/>
          </marker>
        </defs>
        <path class="tc-arrow-path" d="M 280,70 Q 380,150 380,280"/>
        <path class="tc-arrow-path" d="M 380,350 Q 250,400 130,350"/>
        <path class="tc-arrow-path" d="M 120,280 Q 120,150 220,70"/>
      </svg>

      <!-- 3つのノード -->
      <div class="tc-node has-tooltip" data-tooltip="{{詳細1}}">
        <div class="tc-node-icon"><i class="fas {{アイコン1}}"></i></div>
        <div class="tc-node-text">{{要素1}}</div>
      </div>
      <div class="tc-node has-tooltip" data-tooltip="{{詳細2}}">
        <div class="tc-node-icon"><i class="fas {{アイコン2}}"></i></div>
        <div class="tc-node-text">{{要素2}}</div>
      </div>
      <div class="tc-node has-tooltip" data-tooltip="{{詳細3}}">
        <div class="tc-node-icon"><i class="fas {{アイコン3}}"></i></div>
        <div class="tc-node-text">{{要素3}}</div>
      </div>

      <!-- 中心 -->
      <div class="tc-center">
        <div class="tc-center-icon"><i class="fas fa-sync"></i></div>
        <div class="tc-center-text">{{中心}}</div>
      </div>
    </div>
  </div>
</div>
```

### 11.28 ウェーブステップカード型（Wave Step Cards）

波形の装飾付きステップカード。

```css
.slide-wave-steps .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-wave-steps .ws-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-wave-steps .ws-container {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  justify-content: center;
}

.slide-wave-steps .ws-card {
  width: 220px;
  background: var(--bg-dim);
  border-radius: 16px;
  overflow: hidden;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-wave-steps .ws-card:hover {
  transform: translateY(-10px);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
}

/* カードヘッダー（波形） */
.slide-wave-steps .ws-card-header {
  height: 80px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.slide-wave-steps .ws-card:nth-child(1) .ws-card-header { background: var(--wave-blue); }
.slide-wave-steps .ws-card:nth-child(2) .ws-card-header { background: var(--wave-aqua); }
.slide-wave-steps .ws-card:nth-child(3) .ws-card-header { background: var(--spring-green); }
.slide-wave-steps .ws-card:nth-child(4) .ws-card-header { background: var(--autumn-yellow); }

/* 波形SVG */
.slide-wave-steps .ws-card-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 20px;
  background: var(--bg-dim);
  clip-path: ellipse(60% 100% at 50% 100%);
}

.slide-wave-steps .ws-step-number {
  width: 50px;
  height: 50px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--fs-subtitle);
  font-weight: 700;
  color: var(--bg-dark);
}

/* カード本体 */
.slide-wave-steps .ws-card-body {
  padding: 1.5rem;
  text-align: center;
}

.slide-wave-steps .ws-card-title {
  font-size: var(--fs-subheading);
  font-weight: 700;
  margin-bottom: 0.75rem;
}

.slide-wave-steps .ws-card-desc {
  font-size: var(--fs-body);
  color: var(--fg-dim);
  line-height: 1.6;
}

.slide-wave-steps .ws-card-icon {
  font-size: 2rem;
  margin-bottom: 0.75rem;
}

.slide-wave-steps .ws-card:nth-child(1) .ws-card-icon { color: var(--wave-blue); }
.slide-wave-steps .ws-card:nth-child(2) .ws-card-icon { color: var(--wave-aqua); }
.slide-wave-steps .ws-card:nth-child(3) .ws-card-icon { color: var(--spring-green); }
.slide-wave-steps .ws-card:nth-child(4) .ws-card-icon { color: var(--autumn-yellow); }
```

```html
<div class="slider__item slide-wave-steps">
  <div class="slider__content">
    <h2 class="ws-title"><i class="fas fa-water"></i> {{タイトル}}</h2>
    <div class="ws-container">
      <div class="ws-card">
        <div class="ws-card-header">
          <div class="ws-step-number">1</div>
        </div>
        <div class="ws-card-body">
          <div class="ws-card-icon"><i class="fas {{アイコン1}}"></i></div>
          <div class="ws-card-title">{{ステップ1}}</div>
          <div class="ws-card-desc">{{説明1}}</div>
        </div>
      </div>
      <div class="ws-card">
        <div class="ws-card-header">
          <div class="ws-step-number">2</div>
        </div>
        <div class="ws-card-body">
          <div class="ws-card-icon"><i class="fas {{アイコン2}}"></i></div>
          <div class="ws-card-title">{{ステップ2}}</div>
          <div class="ws-card-desc">{{説明2}}</div>
        </div>
      </div>
      <div class="ws-card">
        <div class="ws-card-header">
          <div class="ws-step-number">3</div>
        </div>
        <div class="ws-card-body">
          <div class="ws-card-icon"><i class="fas {{アイコン3}}"></i></div>
          <div class="ws-card-title">{{ステップ3}}</div>
          <div class="ws-card-desc">{{説明3}}</div>
        </div>
      </div>
      <div class="ws-card">
        <div class="ws-card-header">
          <div class="ws-step-number">4</div>
        </div>
        <div class="ws-card-body">
          <div class="ws-card-icon"><i class="fas {{アイコン4}}"></i></div>
          <div class="ws-card-title">{{ステップ4}}</div>
          <div class="ws-card-desc">{{説明4}}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 11.29 アイコン選択グリッド型（Icon Selection Grid）

機能一覧やオプション選択をアイコングリッドで表示。

```css
.slide-icon-grid .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-icon-grid .ig-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-icon-grid .ig-container {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.5rem;
  max-width: 800px;
}

.slide-icon-grid .ig-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1.5rem;
  background: var(--bg-dim);
  border-radius: 16px;
  text-align: center;
  border: 2px solid transparent;
  transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
  cursor: pointer;
}

.slide-icon-grid .ig-item:hover {
  transform: translateY(-5px);
  border-color: var(--wave-blue);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

/* 選択状態 */
.slide-icon-grid .ig-item.selected {
  border-color: var(--sakura-pink);
  background: rgba(210, 126, 153, 0.1);
}

.slide-icon-grid .ig-item-icon {
  width: 60px;
  height: 60px;
  background: rgba(126, 156, 216, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  color: var(--wave-blue);
}

/* アイコンカラーバリエーション */
.slide-icon-grid .ig-item:nth-child(1) .ig-item-icon { color: var(--wave-blue); background: rgba(126, 156, 216, 0.2); }
.slide-icon-grid .ig-item:nth-child(2) .ig-item-icon { color: var(--wave-aqua); background: rgba(122, 162, 247, 0.2); }
.slide-icon-grid .ig-item:nth-child(3) .ig-item-icon { color: var(--spring-green); background: rgba(152, 187, 108, 0.2); }
.slide-icon-grid .ig-item:nth-child(4) .ig-item-icon { color: var(--autumn-yellow); background: rgba(220, 165, 97, 0.2); }
.slide-icon-grid .ig-item:nth-child(5) .ig-item-icon { color: var(--sakura-pink); background: rgba(210, 126, 153, 0.2); }
.slide-icon-grid .ig-item:nth-child(6) .ig-item-icon { color: var(--wave-blue); background: rgba(126, 156, 216, 0.2); }
.slide-icon-grid .ig-item:nth-child(7) .ig-item-icon { color: var(--wave-aqua); background: rgba(122, 162, 247, 0.2); }
.slide-icon-grid .ig-item:nth-child(8) .ig-item-icon { color: var(--spring-green); background: rgba(152, 187, 108, 0.2); }

.slide-icon-grid .ig-item-label {
  font-weight: 600;
  font-size: var(--fs-body);
}

.slide-icon-grid .ig-item-desc {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* 2x4グリッド */
.slide-icon-grid.grid-2x4 .ig-container {
  grid-template-columns: repeat(4, 1fr);
  grid-template-rows: repeat(2, 1fr);
}

/* 3x3グリッド */
.slide-icon-grid.grid-3x3 .ig-container {
  grid-template-columns: repeat(3, 1fr);
}
```

```html
<div class="slider__item slide-icon-grid grid-2x4">
  <div class="slider__content">
    <h2 class="ig-title"><i class="fas fa-th"></i> {{タイトル}}</h2>
    <div class="ig-container">
      <div class="ig-item has-tooltip" data-tooltip="{{詳細1}}">
        <div class="ig-item-icon"><i class="fas {{アイコン1}}"></i></div>
        <div class="ig-item-label">{{ラベル1}}</div>
      </div>
      <div class="ig-item has-tooltip" data-tooltip="{{詳細2}}">
        <div class="ig-item-icon"><i class="fas {{アイコン2}}"></i></div>
        <div class="ig-item-label">{{ラベル2}}</div>
      </div>
      <div class="ig-item has-tooltip" data-tooltip="{{詳細3}}">
        <div class="ig-item-icon"><i class="fas {{アイコン3}}"></i></div>
        <div class="ig-item-label">{{ラベル3}}</div>
      </div>
      <div class="ig-item has-tooltip" data-tooltip="{{詳細4}}">
        <div class="ig-item-icon"><i class="fas {{アイコン4}}"></i></div>
        <div class="ig-item-label">{{ラベル4}}</div>
      </div>
      <div class="ig-item has-tooltip" data-tooltip="{{詳細5}}">
        <div class="ig-item-icon"><i class="fas {{アイコン5}}"></i></div>
        <div class="ig-item-label">{{ラベル5}}</div>
      </div>
      <div class="ig-item has-tooltip" data-tooltip="{{詳細6}}">
        <div class="ig-item-icon"><i class="fas {{アイコン6}}"></i></div>
        <div class="ig-item-label">{{ラベル6}}</div>
      </div>
      <div class="ig-item has-tooltip" data-tooltip="{{詳細7}}">
        <div class="ig-item-icon"><i class="fas {{アイコン7}}"></i></div>
        <div class="ig-item-label">{{ラベル7}}</div>
      </div>
      <div class="ig-item has-tooltip" data-tooltip="{{詳細8}}">
        <div class="ig-item-icon"><i class="fas {{アイコン8}}"></i></div>
        <div class="ig-item-label">{{ラベル8}}</div>
      </div>
    </div>
  </div>
</div>
```

---

## 12. 図解タイプ選択ガイド

### 12.1 用途別推奨タイプ

| ユースケース | 推奨タイプ | 備考 |
|-------------|-----------|------|
| 継続的プロセス（PDCA等） | `slide-cycle` | 3-6要素対応 |
| 長い手順・ステップ | `slide-snake` | 蛇行フロー、6+要素可 |
| 概念の重なり | `slide-venn` | 2円/3円対応 |
| アイデア整理・構造化 | `slide-mindmap` | 階層的展開 |
| 条件分岐を含む処理 | `slide-flowchart` | Mermaid風 |
| 成長・向上の可視化 | `slide-growth` | 時間軸+価値軸 |
| 製品・サービス比較 | `slide-comparison` | 2-4カード対応 |
| 2軸での分類・対比 | `slide-matrix` | n×m対応 |
| プロジェクト計画 | `slide-gantt` | 4-12列対応 |
| 詳細データ表示 | `slide-advanced-table` | ステータス・進捗対応 |
| ターゲット顧客像 | `slide-persona` | 人物プロファイル表示 |
| 問題と解決策 | `slide-problem-solution` | 左右対比レイアウト |
| 製品価値・USP | `slide-value-prop` | 中心+4方向配置 |
| 機能・メリット紹介 | `slide-point-cards` | 3-4カード並列 |
| 優先順位・層構造 | `slide-concentric` | 同心円3層 |
| マイルストーン計画 | `slide-roadmap` | 横方向タイムライン |
| 価値階層 | `slide-value-stack` | 縦積み上げレイヤー |

### 12.2 要素数別ガイド

| 要素数 | サイクル型 | マトリックス型 | 備考 |
|-------|-----------|--------------|------|
| 3 | `cycle-3` | `matrix-3x1` | 三角形配置 |
| 4 | `cycle-4` (デフォルト) | `matrix-2x2` | 最もバランス良い |
| 5 | `cycle-5` | `matrix-5x1`または`matrix-3x2` | 五角形配置 |
| 6 | `cycle-6` | `matrix-3x2`または`matrix-2x3` | 六角形配置 |
| 9 | - | `matrix-3x3` | 9分割マトリックス |
| 16 | - | `matrix-4x4` | 16分割マトリックス |

### 12.3 チェックリスト

| 図解タイプ | チェック項目 |
|-----------|-------------|
| **slide-cycle** | □ 要素数に合った配置クラスを使用しているか |
| **slide-venn** | □ 交差部分のラベルが定義されているか |
| **slide-mindmap** | □ 中央テーマが明確か、ブランチが8方向以内か |
| **slide-flowchart** | □ 開始・終了ノードがあるか、分岐後に合流があるか |
| **slide-growth** | □ data-heightで高さが設定されているか |
| **slide-comparison** | □ featuredカードが1つ指定されているか |
| **slide-matrix** | □ 適切なn×mサイズか、軸ラベルがあるか |
| **slide-gantt** | □ data-start/data-durationが正しいか |
| **slide-persona** | □ 基本情報・課題・ニーズの3セクションがあるか |
| **slide-problem-solution** | □ 課題と解決策が1対1で対応しているか |
| **slide-value-prop** | □ 中央価値と4つの周辺価値が定義されているか |
| **slide-point-cards** | □ cards-3/cards-4クラスが適切に設定されているか |
| **slide-concentric** | □ core/middle/outerの3層が定義されているか |
| **slide-roadmap** | □ completed/current状態が正しく設定されているか |
| **slide-value-stack** | □ 上から下への価値階層が論理的か |
| **全般** | □ ツールチップで補足情報を追加しているか |

---

