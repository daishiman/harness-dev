# 図解タイプ: ビジネス系

**責務**: 課題解決型、バリュープロポジション、ポイントカード、同心円、ロードマップ、価値スタック、AIDMA型、PREP型、STAR型、FABE型のCSS・HTMLテンプレート

**含まれるタイプ**: 11.11-11.20

---


### 11.11 課題解決型（Problem-Solution）

問題と解決策を左右に配置して対比表示。

```css
.slide-problem-solution .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-problem-solution .ps-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-problem-solution .ps-container {
  display: flex;
  gap: 2rem;
  align-items: stretch;
  max-width: 1000px;
  width: 100%;
}

/* 問題パネル */
.slide-problem-solution .ps-panel {
  flex: 1;
  background: var(--bg-dim);
  border-radius: 16px;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.slide-problem-solution .ps-panel.problem {
  border-top: 4px solid var(--sakura-pink);
}

.slide-problem-solution .ps-panel.solution {
  border-top: 4px solid var(--spring-green);
}

.slide-problem-solution .ps-panel-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: var(--fs-subheading);
  font-weight: 700;
}

.slide-problem-solution .ps-panel.problem .ps-panel-header {
  color: var(--sakura-pink);
}

.slide-problem-solution .ps-panel.solution .ps-panel-header {
  color: var(--spring-green);
}

.slide-problem-solution .ps-panel-header i {
  font-size: 1.5rem;
}

.slide-problem-solution .ps-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slide-problem-solution .ps-list li {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  transition: transform 0.3s ease;
}

.slide-problem-solution .ps-list li:hover {
  transform: translateX(5px);
}

.slide-problem-solution .ps-list li i {
  margin-top: 0.2rem;
}

.slide-problem-solution .ps-panel.problem .ps-list li i {
  color: var(--sakura-pink);
}

.slide-problem-solution .ps-panel.solution .ps-list li i {
  color: var(--spring-green);
}

/* 中央の矢印 */
.slide-problem-solution .ps-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  color: var(--autumn-yellow);
}
```

```html
<div class="slider__item slide-problem-solution">
  <div class="slider__content">
    <h2 class="ps-title"><i class="fas fa-exchange-alt"></i> {{タイトル}}</h2>
    <div class="ps-container">
      <div class="ps-panel problem">
        <div class="ps-panel-header">
          <i class="fas fa-times-circle"></i>
          <span>課題</span>
        </div>
        <ul class="ps-list">
          <li>
            <i class="fas fa-exclamation-circle"></i>
            <span>{{課題1}}</span>
          </li>
          <li>
            <i class="fas fa-exclamation-circle"></i>
            <span>{{課題2}}</span>
          </li>
          <li>
            <i class="fas fa-exclamation-circle"></i>
            <span>{{課題3}}</span>
          </li>
        </ul>
      </div>
      <div class="ps-arrow">
        <i class="fas fa-arrow-right"></i>
      </div>
      <div class="ps-panel solution">
        <div class="ps-panel-header">
          <i class="fas fa-check-circle"></i>
          <span>解決策</span>
        </div>
        <ul class="ps-list">
          <li>
            <i class="fas fa-check"></i>
            <span>{{解決策1}}</span>
          </li>
          <li>
            <i class="fas fa-check"></i>
            <span>{{解決策2}}</span>
          </li>
          <li>
            <i class="fas fa-check"></i>
            <span>{{解決策3}}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</div>
```

### 11.12 バリュープロポジション型（Value Proposition）

中心に核心価値、周囲に4つの価値・特徴を配置。

```css
.slide-value-prop .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-value-prop .vp-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-value-prop .vp-container {
  position: relative;
  width: 700px;
  height: 450px;
}

/* 中央ノードの基本 CSS は diagram-visual.md の中心円パターンを正本として参照 */

.slide-value-prop .vp-center-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.slide-value-prop .vp-center-text {
  font-size: var(--fs-body-lg);
  font-weight: 700;
}

/* 周囲の価値カード */
.slide-value-prop .vp-card {
  position: absolute;
  width: 180px;
  background: var(--bg-dim);
  border-radius: 12px;
  padding: 1.25rem;
  text-align: center;
  border: 2px solid var(--wave-blue);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-value-prop .vp-card:hover {
  transform: scale(1.1);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}

/* 4方向配置 */
.slide-value-prop .vp-card:nth-child(1) { top: 0; left: 50%; transform: translateX(-50%); }
.slide-value-prop .vp-card:nth-child(2) { top: 50%; right: 0; transform: translateY(-50%); }
.slide-value-prop .vp-card:nth-child(3) { bottom: 0; left: 50%; transform: translateX(-50%); }
.slide-value-prop .vp-card:nth-child(4) { top: 50%; left: 0; transform: translateY(-50%); }

.slide-value-prop .vp-card-icon {
  font-size: 2rem;
  color: var(--wave-blue);
  margin-bottom: 0.5rem;
}

.slide-value-prop .vp-card-title {
  font-size: var(--fs-body-lg);
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.slide-value-prop .vp-card-desc {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* 接続線 */
.slide-value-prop .vp-line {
  position: absolute;
  background: var(--fuji-gray);
  z-index: 1;
}

.slide-value-prop .vp-line-v {
  width: 2px;
  height: 80px;
  left: 50%;
  transform: translateX(-50%);
}

.slide-value-prop .vp-line-h {
  height: 2px;
  width: 80px;
  top: 50%;
  transform: translateY(-50%);
}

.slide-value-prop .vp-line.top { top: 80px; }
.slide-value-prop .vp-line.bottom { bottom: 80px; }
.slide-value-prop .vp-line.left { left: 100px; }
.slide-value-prop .vp-line.right { right: 100px; }
```

```html
<div class="slider__item slide-value-prop">
  <div class="slider__content">
    <h2 class="vp-title"><i class="fas fa-gem"></i> {{タイトル}}</h2>
    <div class="vp-container">
      <!-- 接続線 -->
      <div class="vp-line vp-line-v top"></div>
      <div class="vp-line vp-line-v bottom"></div>
      <div class="vp-line vp-line-h left"></div>
      <div class="vp-line vp-line-h right"></div>

      <!-- 周囲の価値カード -->
      <div class="vp-card has-tooltip" data-tooltip="{{詳細1}}">
        <div class="vp-card-icon"><i class="fas {{アイコン1}}"></i></div>
        <div class="vp-card-title">{{価値1}}</div>
        <div class="vp-card-desc">{{説明1}}</div>
      </div>
      <div class="vp-card has-tooltip" data-tooltip="{{詳細2}}">
        <div class="vp-card-icon"><i class="fas {{アイコン2}}"></i></div>
        <div class="vp-card-title">{{価値2}}</div>
        <div class="vp-card-desc">{{説明2}}</div>
      </div>
      <div class="vp-card has-tooltip" data-tooltip="{{詳細3}}">
        <div class="vp-card-icon"><i class="fas {{アイコン3}}"></i></div>
        <div class="vp-card-title">{{価値3}}</div>
        <div class="vp-card-desc">{{説明3}}</div>
      </div>
      <div class="vp-card has-tooltip" data-tooltip="{{詳細4}}">
        <div class="vp-card-icon"><i class="fas {{アイコン4}}"></i></div>
        <div class="vp-card-title">{{価値4}}</div>
        <div class="vp-card-desc">{{説明4}}</div>
      </div>

      <!-- 中央の核心価値 -->
      <div class="vp-center">
        <div class="vp-center-icon"><i class="fas {{中央アイコン}}"></i></div>
        <div class="vp-center-text">{{核心価値}}</div>
      </div>
    </div>
  </div>
</div>
```

### 11.13 ポイントカード型（Point Cards）

アイコン付きカードで複数の特徴・メリットを並列表示。

```css
.slide-point-cards .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-point-cards .pc-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-point-cards .pc-container {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  justify-content: center;
  max-width: 1000px;
}

.slide-point-cards .pc-card {
  width: 280px;
  background: var(--bg-dim);
  border-radius: 16px;
  padding: 2rem;
  text-align: center;
  border-top: 4px solid var(--wave-blue);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-point-cards .pc-card:hover {
  transform: translateY(-10px);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4);
}

/* カラーバリエーション */
.slide-point-cards .pc-card:nth-child(1) { border-top-color: var(--wave-blue); }
.slide-point-cards .pc-card:nth-child(2) { border-top-color: var(--sakura-pink); }
.slide-point-cards .pc-card:nth-child(3) { border-top-color: var(--spring-green); }
.slide-point-cards .pc-card:nth-child(4) { border-top-color: var(--autumn-yellow); }

.slide-point-cards .pc-card-icon {
  width: 80px;
  height: 80px;
  background: rgba(126, 156, 216, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1rem;
  font-size: 2rem;
  color: var(--wave-blue);
}

.slide-point-cards .pc-card:nth-child(1) .pc-card-icon { color: var(--wave-blue); background: rgba(126, 156, 216, 0.2); }
.slide-point-cards .pc-card:nth-child(2) .pc-card-icon { color: var(--sakura-pink); background: rgba(210, 126, 153, 0.2); }
.slide-point-cards .pc-card:nth-child(3) .pc-card-icon { color: var(--spring-green); background: rgba(152, 187, 108, 0.2); }
.slide-point-cards .pc-card:nth-child(4) .pc-card-icon { color: var(--autumn-yellow); background: rgba(220, 165, 97, 0.2); }

.slide-point-cards .pc-card-title {
  font-size: var(--fs-subheading);
  font-weight: 700;
  margin-bottom: 0.75rem;
}

.slide-point-cards .pc-card-desc {
  font-size: var(--fs-body);
  color: var(--fg-dim);
  line-height: 1.6;
}

/* 3カード配置 */
.slide-point-cards.cards-3 .pc-card {
  width: 300px;
}

/* 4カード配置（2x2） */
.slide-point-cards.cards-4 .pc-card {
  width: 260px;
}
```

```html
<div class="slider__item slide-point-cards cards-3">
  <div class="slider__content">
    <h2 class="pc-title"><i class="fas fa-star"></i> {{タイトル}}</h2>
    <div class="pc-container">
      <div class="pc-card has-tooltip" data-tooltip="{{詳細1}}">
        <div class="pc-card-icon"><i class="fas {{アイコン1}}"></i></div>
        <div class="pc-card-title">{{ポイント1}}</div>
        <div class="pc-card-desc">{{説明1}}</div>
      </div>
      <div class="pc-card has-tooltip" data-tooltip="{{詳細2}}">
        <div class="pc-card-icon"><i class="fas {{アイコン2}}"></i></div>
        <div class="pc-card-title">{{ポイント2}}</div>
        <div class="pc-card-desc">{{説明2}}</div>
      </div>
      <div class="pc-card has-tooltip" data-tooltip="{{詳細3}}">
        <div class="pc-card-icon"><i class="fas {{アイコン3}}"></i></div>
        <div class="pc-card-title">{{ポイント3}}</div>
        <div class="pc-card-desc">{{説明3}}</div>
      </div>
    </div>
  </div>
</div>
```

### 11.14 コンセントリックサークル型（Concentric Circles）

同心円で層構造・優先順位を表現。

```css
.slide-concentric .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-concentric .cc-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-concentric .cc-container {
  position: relative;
  width: 500px;
  height: 500px;
}

/* 3層の同心円 */
.slide-concentric .cc-layer {
  position: absolute;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-concentric .cc-layer:hover {
  transform: scale(1.05);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

/* 外層 */
.slide-concentric .cc-layer.outer {
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  background: rgba(126, 156, 216, 0.2);
  border: 3px solid var(--wave-blue);
}

/* 中層 */
.slide-concentric .cc-layer.middle {
  width: 65%;
  height: 65%;
  top: 17.5%;
  left: 17.5%;
  background: rgba(210, 126, 153, 0.3);
  border: 3px solid var(--sakura-pink);
  z-index: 2;
}

/* 内層（コア） */
.slide-concentric .cc-layer.core {
  width: 35%;
  height: 35%;
  top: 32.5%;
  left: 32.5%;
  background: linear-gradient(135deg, var(--autumn-yellow), var(--sakura-pink));
  border: none;
  z-index: 3;
  color: var(--bg-dark);
  font-weight: 700;
}

.slide-concentric .cc-layer-label {
  position: absolute;
  font-size: var(--fs-body);
  font-weight: 600;
}

/* ラベル配置 */
.slide-concentric .cc-layer.outer .cc-layer-label {
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
}

.slide-concentric .cc-layer.middle .cc-layer-label {
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
}

.slide-concentric .cc-layer.core .cc-layer-label {
  position: relative;
  top: auto;
  left: auto;
  transform: none;
}

/* 右側の凡例 */
.slide-concentric .cc-legend {
  position: absolute;
  right: -220px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slide-concentric .cc-legend-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slide-concentric .cc-legend-color {
  width: 16px;
  height: 16px;
  border-radius: 4px;
}

.slide-concentric .cc-legend-color.outer { background: var(--wave-blue); }
.slide-concentric .cc-legend-color.middle { background: var(--sakura-pink); }
.slide-concentric .cc-legend-color.core { background: var(--autumn-yellow); }
```

```html
<div class="slider__item slide-concentric">
  <div class="slider__content">
    <h2 class="cc-title"><i class="fas fa-bullseye"></i> {{タイトル}}</h2>
    <div class="cc-container">
      <div class="cc-layer outer has-tooltip" data-tooltip="{{外層詳細}}">
        <span class="cc-layer-label">{{外層ラベル}}</span>
      </div>
      <div class="cc-layer middle has-tooltip" data-tooltip="{{中層詳細}}">
        <span class="cc-layer-label">{{中層ラベル}}</span>
      </div>
      <div class="cc-layer core has-tooltip" data-tooltip="{{コア詳細}}">
        <span class="cc-layer-label">{{コア}}</span>
      </div>
      <div class="cc-legend">
        <div class="cc-legend-item">
          <div class="cc-legend-color core"></div>
          <span>{{コア説明}}</span>
        </div>
        <div class="cc-legend-item">
          <div class="cc-legend-color middle"></div>
          <span>{{中層説明}}</span>
        </div>
        <div class="cc-legend-item">
          <div class="cc-legend-color outer"></div>
          <span>{{外層説明}}</span>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 11.15 ロードマップ型（Roadmap）

横方向の時間軸・マイルストーン表示。

```css
.slide-roadmap .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-roadmap .rm-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-roadmap .rm-container {
  position: relative;
  width: 100%;
  max-width: 1000px;
  padding: 3rem 0;
}

/* 時間軸ライン */
.slide-roadmap .rm-timeline {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 4px;
  background: var(--fuji-gray);
  transform: translateY(-50%);
}

/* マイルストーン */
.slide-roadmap .rm-milestones {
  display: flex;
  justify-content: space-between;
  position: relative;
  z-index: 2;
}

.slide-roadmap .rm-milestone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  max-width: 200px;
}

/* マイルストーンポイント */
.slide-roadmap .rm-point {
  width: 20px;
  height: 20px;
  background: var(--wave-blue);
  border-radius: 50%;
  border: 4px solid var(--bg-dark);
  box-shadow: 0 0 0 3px var(--wave-blue);
  transition: transform 0.3s ease;
}

.slide-roadmap .rm-milestone:hover .rm-point {
  transform: scale(1.3);
}

/* 完了マイルストーン */
.slide-roadmap .rm-milestone.completed .rm-point {
  background: var(--spring-green);
  box-shadow: 0 0 0 3px var(--spring-green);
}

/* 現在マイルストーン */
.slide-roadmap .rm-milestone.current .rm-point {
  background: var(--autumn-yellow);
  box-shadow: 0 0 0 3px var(--autumn-yellow);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}

/* マイルストーンラベル */
.slide-roadmap .rm-label {
  font-size: var(--fs-body);
  font-weight: 700;
  text-align: center;
}

.slide-roadmap .rm-date {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* マイルストーンカード */
.slide-roadmap .rm-card {
  background: var(--bg-dim);
  padding: 1rem;
  border-radius: 8px;
  text-align: center;
  border-left: 3px solid var(--wave-blue);
  transition: transform 0.3s ease;
}

.slide-roadmap .rm-milestone:hover .rm-card {
  transform: translateY(-5px);
}

.slide-roadmap .rm-milestone.completed .rm-card {
  border-left-color: var(--spring-green);
}

.slide-roadmap .rm-milestone.current .rm-card {
  border-left-color: var(--autumn-yellow);
}

.slide-roadmap .rm-card-title {
  font-size: var(--fs-body);
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.slide-roadmap .rm-card-desc {
  font-size: var(--fs-small);
  color: var(--fg-dim);
}
```

```html
<div class="slider__item slide-roadmap">
  <div class="slider__content">
    <h2 class="rm-title"><i class="fas fa-road"></i> {{タイトル}}</h2>
    <div class="rm-container">
      <div class="rm-timeline"></div>
      <div class="rm-milestones">
        <div class="rm-milestone completed">
          <div class="rm-card">
            <div class="rm-card-title">{{Phase 1}}</div>
            <div class="rm-card-desc">{{説明1}}</div>
          </div>
          <div class="rm-point"></div>
          <div class="rm-label">{{Phase 1 名}}</div>
          <div class="rm-date">{{日付1}}</div>
        </div>
        <div class="rm-milestone current">
          <div class="rm-card">
            <div class="rm-card-title">{{Phase 2}}</div>
            <div class="rm-card-desc">{{説明2}}</div>
          </div>
          <div class="rm-point"></div>
          <div class="rm-label">{{Phase 2 名}}</div>
          <div class="rm-date">{{日付2}}</div>
        </div>
        <div class="rm-milestone">
          <div class="rm-card">
            <div class="rm-card-title">{{Phase 3}}</div>
            <div class="rm-card-desc">{{説明3}}</div>
          </div>
          <div class="rm-point"></div>
          <div class="rm-label">{{Phase 3 名}}</div>
          <div class="rm-date">{{日付3}}</div>
        </div>
        <div class="rm-milestone">
          <div class="rm-card">
            <div class="rm-card-title">{{Phase 4}}</div>
            <div class="rm-card-desc">{{説明4}}</div>
          </div>
          <div class="rm-point"></div>
          <div class="rm-label">{{Phase 4 名}}</div>
          <div class="rm-date">{{日付4}}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 11.16 価値スタック型（Value Stack）

複数の価値・レイヤーを縦に積み上げて階層を表現。

```css
.slide-value-stack .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-value-stack .vs-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-value-stack .vs-container {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
  max-width: 700px;
}

.slide-value-stack .vs-layer {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.5rem 2rem;
  background: var(--bg-dim);
  border-left: 5px solid var(--wave-blue);
  position: relative;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-value-stack .vs-layer:hover {
  transform: translateX(10px);
  box-shadow: -5px 0 20px rgba(0, 0, 0, 0.3);
}

/* 層別の色 */
.slide-value-stack .vs-layer:nth-child(1) { border-left-color: var(--sakura-pink); }
.slide-value-stack .vs-layer:nth-child(2) { border-left-color: var(--autumn-yellow); }
.slide-value-stack .vs-layer:nth-child(3) { border-left-color: var(--spring-green); }
.slide-value-stack .vs-layer:nth-child(4) { border-left-color: var(--wave-blue); }

/* 上向き矢印 */
.slide-value-stack .vs-arrow {
  display: flex;
  justify-content: center;
  padding: 0.5rem;
  color: var(--autumn-yellow);
  font-size: 1.5rem;
}

.slide-value-stack .vs-layer-icon {
  width: 60px;
  height: 60px;
  background: rgba(126, 156, 216, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
}

.slide-value-stack .vs-layer:nth-child(1) .vs-layer-icon { background: rgba(210, 126, 153, 0.2); color: var(--sakura-pink); }
.slide-value-stack .vs-layer:nth-child(2) .vs-layer-icon { background: rgba(220, 165, 97, 0.2); color: var(--autumn-yellow); }
.slide-value-stack .vs-layer:nth-child(3) .vs-layer-icon { background: rgba(152, 187, 108, 0.2); color: var(--spring-green); }
.slide-value-stack .vs-layer:nth-child(4) .vs-layer-icon { background: rgba(126, 156, 216, 0.2); color: var(--wave-blue); }

.slide-value-stack .vs-layer-content {
  flex: 1;
}

.slide-value-stack .vs-layer-title {
  font-size: var(--fs-subheading);
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.slide-value-stack .vs-layer-desc {
  font-size: var(--fs-body);
  color: var(--fg-dim);
}

.slide-value-stack .vs-layer-level {
  font-size: var(--fs-small);
  color: var(--fg-dim);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
```

```html
<div class="slider__item slide-value-stack">
  <div class="slider__content">
    <h2 class="vs-title"><i class="fas fa-layer-group"></i> {{タイトル}}</h2>
    <div class="vs-container">
      <div class="vs-layer has-tooltip" data-tooltip="{{詳細1}}">
        <div class="vs-layer-icon"><i class="fas {{アイコン1}}"></i></div>
        <div class="vs-layer-content">
          <div class="vs-layer-level">Level 3</div>
          <div class="vs-layer-title">{{レイヤー1}}</div>
          <div class="vs-layer-desc">{{説明1}}</div>
        </div>
      </div>
      <div class="vs-arrow"><i class="fas fa-arrow-up"></i></div>
      <div class="vs-layer has-tooltip" data-tooltip="{{詳細2}}">
        <div class="vs-layer-icon"><i class="fas {{アイコン2}}"></i></div>
        <div class="vs-layer-content">
          <div class="vs-layer-level">Level 2</div>
          <div class="vs-layer-title">{{レイヤー2}}</div>
          <div class="vs-layer-desc">{{説明2}}</div>
        </div>
      </div>
      <div class="vs-arrow"><i class="fas fa-arrow-up"></i></div>
      <div class="vs-layer has-tooltip" data-tooltip="{{詳細3}}">
        <div class="vs-layer-icon"><i class="fas {{アイコン3}}"></i></div>
        <div class="vs-layer-content">
          <div class="vs-layer-level">Level 1</div>
          <div class="vs-layer-title">{{レイヤー3}}</div>
          <div class="vs-layer-desc">{{説明3}}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 11.17 AIDMA/ファネルフレームワーク型

マーケティングファネルやカスタマージャーニーの段階を横方向のフレームワークで表示。

```css
.slide-aidma .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-aidma .aidma-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-aidma .aidma-container {
  width: 100%;
  max-width: 1000px;
}

.slide-aidma .aidma-row {
  display: flex;
  gap: 0;
}

.slide-aidma .aidma-row:first-child .aidma-cell {
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.slide-aidma .aidma-row:last-child .aidma-cell {
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.slide-aidma .aidma-cell {
  flex: 1;
  padding: 1.25rem;
  text-align: center;
  border: 1px solid var(--fuji-gray);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-aidma .aidma-cell:hover {
  transform: scale(1.02);
  box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

/* ヘッダー行 */
.slide-aidma .aidma-row.header .aidma-cell {
  background: var(--sumi-ink);
  font-weight: 700;
  color: var(--wave-blue);
  font-size: var(--fs-body-lg);
}

/* フェーズ名行 */
.slide-aidma .aidma-row.phase .aidma-cell {
  background: rgba(126, 156, 216, 0.15);
  font-weight: 600;
}

/* アクション行 */
.slide-aidma .aidma-row.action .aidma-cell {
  background: var(--bg-dim);
  font-size: var(--fs-small);
  color: var(--fg-dim);
}

/* フェーズ別カラー */
.slide-aidma .aidma-cell:nth-child(1) { border-left-color: var(--wave-blue); border-left-width: 3px; }
.slide-aidma .aidma-cell:nth-child(2) { border-left-color: var(--wave-aqua); border-left-width: 3px; }
.slide-aidma .aidma-cell:nth-child(3) { border-left-color: var(--spring-green); border-left-width: 3px; }
.slide-aidma .aidma-cell:nth-child(4) { border-left-color: var(--autumn-yellow); border-left-width: 3px; }
.slide-aidma .aidma-cell:nth-child(5) { border-left-color: var(--sakura-pink); border-left-width: 3px; }
```

```html
<div class="slider__item slide-aidma">
  <div class="slider__content">
    <h2 class="aidma-title"><i class="fas fa-funnel-dollar"></i> {{タイトル}}</h2>
    <div class="aidma-container">
      <div class="aidma-row header">
        <div class="aidma-cell">Attention</div>
        <div class="aidma-cell">Interest</div>
        <div class="aidma-cell">Desire</div>
        <div class="aidma-cell">Memory</div>
        <div class="aidma-cell">Action</div>
      </div>
      <div class="aidma-row phase">
        <div class="aidma-cell">認知</div>
        <div class="aidma-cell">興味</div>
        <div class="aidma-cell">欲求</div>
        <div class="aidma-cell">記憶</div>
        <div class="aidma-cell">行動</div>
      </div>
      <div class="aidma-row action">
        <div class="aidma-cell">{{施策1}}</div>
        <div class="aidma-cell">{{施策2}}</div>
        <div class="aidma-cell">{{施策3}}</div>
        <div class="aidma-cell">{{施策4}}</div>
        <div class="aidma-cell">{{施策5}}</div>
      </div>
    </div>
  </div>
</div>
```

---

### 11.18 PREP型（論理的説明フレームワーク）

結論（Point）→ 理由（Reason）→ 例（Example）→ 結論（Point）の4段階で論理的に説明。ビジネスプレゼンの基本フレームワーク。

```css
.slide-prep .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-prep .prep-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-prep .prep-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
  max-width: 900px;
}

.slide-prep .prep-step {
  display: flex;
  align-items: stretch;
  gap: 1.5rem;
  padding: 1.5rem;
  background: var(--bg-dim);
  border-radius: 16px;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.slide-prep .prep-step:hover {
  transform: translateX(10px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

/* 各ステップのアクセントカラー */
.slide-prep .prep-step.point-1 { border-left: 5px solid var(--wave-blue); }
.slide-prep .prep-step.reason { border-left: 5px solid var(--spring-green); }
.slide-prep .prep-step.example { border-left: 5px solid var(--autumn-yellow); }
.slide-prep .prep-step.point-2 { border-left: 5px solid var(--sakura-pink); }

.slide-prep .prep-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 100px;
  padding: 1rem;
  border-radius: 12px;
  text-align: center;
}

.slide-prep .prep-step.point-1 .prep-label { background: rgba(126, 156, 216, 0.2); color: var(--wave-blue); }
.slide-prep .prep-step.reason .prep-label { background: rgba(152, 187, 108, 0.2); color: var(--spring-green); }
.slide-prep .prep-step.example .prep-label { background: rgba(220, 165, 97, 0.2); color: var(--autumn-yellow); }
.slide-prep .prep-step.point-2 .prep-label { background: rgba(228, 104, 118, 0.2); color: var(--sakura-pink); }

.slide-prep .prep-label-icon {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
}

.slide-prep .prep-label-text {
  font-size: var(--fs-small);
  font-weight: 700;
  text-transform: uppercase;
}

.slide-prep .prep-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.5rem;
}

.slide-prep .prep-content-title {
  font-size: var(--fs-body-lg);
  font-weight: 700;
}

.slide-prep .prep-content-desc {
  font-size: var(--fs-body);
  color: var(--fg-dim);
}

/* 矢印コネクター */
.slide-prep .prep-arrow {
  display: flex;
  justify-content: center;
  color: var(--fuji-gray);
  font-size: 1.2rem;
}
```

```html
<div class="slider__item slide-prep">
  <div class="slider__content">
    <h2 class="prep-title"><i class="fas fa-bullseye"></i> {{タイトル}}</h2>
    <div class="prep-container">
      <div class="prep-step point-1">
        <div class="prep-label">
          <div class="prep-label-icon"><i class="fas fa-flag"></i></div>
          <div class="prep-label-text">Point</div>
        </div>
        <div class="prep-content">
          <div class="prep-content-title">{{結論}}</div>
          <div class="prep-content-desc">{{結論の補足}}</div>
        </div>
      </div>
      <div class="prep-arrow"><i class="fas fa-arrow-down"></i></div>
      <div class="prep-step reason">
        <div class="prep-label">
          <div class="prep-label-icon"><i class="fas fa-lightbulb"></i></div>
          <div class="prep-label-text">Reason</div>
        </div>
        <div class="prep-content">
          <div class="prep-content-title">{{理由}}</div>
          <div class="prep-content-desc">{{理由の詳細}}</div>
        </div>
      </div>
      <div class="prep-arrow"><i class="fas fa-arrow-down"></i></div>
      <div class="prep-step example">
        <div class="prep-label">
          <div class="prep-label-icon"><i class="fas fa-clipboard-list"></i></div>
          <div class="prep-label-text">Example</div>
        </div>
        <div class="prep-content">
          <div class="prep-content-title">{{具体例}}</div>
          <div class="prep-content-desc">{{具体例の詳細}}</div>
        </div>
      </div>
      <div class="prep-arrow"><i class="fas fa-arrow-down"></i></div>
      <div class="prep-step point-2">
        <div class="prep-label">
          <div class="prep-label-icon"><i class="fas fa-check-circle"></i></div>
          <div class="prep-label-text">Point</div>
        </div>
        <div class="prep-content">
          <div class="prep-content-title">{{再結論}}</div>
          <div class="prep-content-desc">{{まとめ・行動喚起}}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

#### PREP型アニメーション

```javascript
// 登場アニメーション
gsap.from('.slide-prep .prep-step', {
  x: -50,
  opacity: 0,
  duration: 0.6,
  stagger: 0.2,
  ease: 'power2.out'
});

gsap.from('.slide-prep .prep-arrow', {
  scale: 0,
  opacity: 0,
  duration: 0.3,
  stagger: 0.15,
  delay: 0.8,
  ease: 'back.out'
});
```

---

### 11.19 STAR型（事例・実績紹介フレームワーク）

状況（Situation）→ 課題（Task）→ 行動（Action）→ 結果（Result）の4段階で事例を説明。実績紹介・成功事例・面接回答に最適。

```css
.slide-star .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-star .star-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-star .star-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
  width: 100%;
  max-width: 950px;
}

.slide-star .star-card {
  background: var(--bg-dim);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  position: relative;
  overflow: hidden;
}

.slide-star .star-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
}

/* 各カードのアクセントカラー */
.slide-star .star-card.situation { border-top: 4px solid var(--wave-blue); }
.slide-star .star-card.task { border-top: 4px solid var(--autumn-yellow); }
.slide-star .star-card.action { border-top: 4px solid var(--spring-green); }
.slide-star .star-card.result { border-top: 4px solid var(--sakura-pink); }

/* 番号バッジ */
.slide-star .star-badge {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: var(--fs-small);
}

.slide-star .star-card.situation .star-badge { background: var(--wave-blue); color: #fff; }
.slide-star .star-card.task .star-badge { background: var(--autumn-yellow); color: #1f1f28; }
.slide-star .star-card.action .star-badge { background: var(--spring-green); color: #1f1f28; }
.slide-star .star-card.result .star-badge { background: var(--sakura-pink); color: #fff; }

.slide-star .star-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slide-star .star-icon {
  font-size: 1.5rem;
}

.slide-star .star-card.situation .star-icon { color: var(--wave-blue); }
.slide-star .star-card.task .star-icon { color: var(--autumn-yellow); }
.slide-star .star-card.action .star-icon { color: var(--spring-green); }
.slide-star .star-card.result .star-icon { color: var(--sakura-pink); }

.slide-star .star-label {
  font-size: var(--fs-body-lg);
  font-weight: 700;
}

.slide-star .star-content {
  font-size: var(--fs-body);
  line-height: 1.6;
}

.slide-star .star-highlight {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-weight: 600;
  margin-top: 0.5rem;
}

.slide-star .star-card.result .star-highlight {
  background: rgba(228, 104, 118, 0.2);
  color: var(--sakura-pink);
}

/* 中央の接続ライン（オプション） */
.slide-star .star-connector {
  position: absolute;
  width: 2px;
  height: 100%;
  background: var(--fuji-gray);
  left: 50%;
  transform: translateX(-50%);
  z-index: -1;
}
```

```html
<div class="slider__item slide-star">
  <div class="slider__content">
    <h2 class="star-title"><i class="fas fa-star"></i> {{タイトル}}</h2>
    <div class="star-container">
      <div class="star-card situation">
        <div class="star-badge">S</div>
        <div class="star-header">
          <div class="star-icon"><i class="fas fa-map-marker-alt"></i></div>
          <div class="star-label">Situation（状況）</div>
        </div>
        <div class="star-content">{{状況の説明}}</div>
      </div>
      <div class="star-card task">
        <div class="star-badge">T</div>
        <div class="star-header">
          <div class="star-icon"><i class="fas fa-exclamation-triangle"></i></div>
          <div class="star-label">Task（課題）</div>
        </div>
        <div class="star-content">{{課題の説明}}</div>
      </div>
      <div class="star-card action">
        <div class="star-badge">A</div>
        <div class="star-header">
          <div class="star-icon"><i class="fas fa-bolt"></i></div>
          <div class="star-label">Action（行動）</div>
        </div>
        <div class="star-content">{{行動の説明}}</div>
      </div>
      <div class="star-card result">
        <div class="star-badge">R</div>
        <div class="star-header">
          <div class="star-icon"><i class="fas fa-trophy"></i></div>
          <div class="star-label">Result（結果）</div>
        </div>
        <div class="star-content">
          {{結果の説明}}
          <div class="star-highlight">{{数値成果}}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

#### STAR型アニメーション

```javascript
// 登場アニメーション（2x2グリッド対応）
gsap.from('.slide-star .star-card', {
  scale: 0.8,
  opacity: 0,
  duration: 0.5,
  stagger: {
    amount: 0.8,
    grid: [2, 2],
    from: 'start'
  },
  ease: 'back.out(1.2)'
});

// バッジのポップアップ
gsap.from('.slide-star .star-badge', {
  scale: 0,
  duration: 0.3,
  stagger: 0.15,
  delay: 0.6,
  ease: 'elastic.out(1, 0.5)'
});
```

---


### 11.20 FABE型

**詳細**: [diagram-fabe.md](diagram-fabe.md) を参照

5種のレイアウトバリエーション（横フロー・縦スタック・2×2グリッド・タイムライン・円形配置）、詳細アニメーション対応。
