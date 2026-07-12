# 図解タイプ: サイクル・フロー系（SVG2版）

**責務**: サイクル図、スネーク型、ベン図、マインドマップ、フローチャート、上昇型のインラインSVG2テンプレート

**含まれるタイプ**: 11.1-11.5

**前提**: [svg-diagram-primitives.md](svg-diagram-primitives.md) の `<defs>` を共有

---

## 11. 拡張図解タイプ

### 11.1 サイクル図（循環型）

円形に配置された要素間の循環関係を表現。PDCAサイクル、継続的改善などに最適。

#### 11.1.1 円形サイクル（SVG2）

**CSS（コンテナ+ホバー）**:

```css
.slide-cycle .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-cycle .cycle-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-cycle .diagram-svg-container {
  width: 100%;
  max-width: 700px;
  aspect-ratio: 1 / 1;
}

.slide-cycle .diagram-svg .node-group {
  cursor: pointer;
  transition: opacity 0.3s ease;
}

.slide-cycle .diagram-svg .node-group:hover rect,
.slide-cycle .diagram-svg .node-group:hover circle {
  filter: url(#shadow-lg);
  stroke-width: 3.5;
}
```

**HTML+SVG（4要素サイクル: PDCA等）**:

```html
<div class="slider__item slide-cycle">
  <div class="slider__content">
    <h2 class="cycle-title"><i class="fas fa-sync-alt"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{タイトル}}のサイクル図">
        <defs>
          <marker id="cyc-arrow" viewBox="0 0 10 10" refX="10" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--autumn-yellow,#DCA561)" />
          </marker>
          <filter id="cyc-shadow" x="-10%" y="-10%" width="120%" height="130%">
            <feDropShadow dx="2" dy="4" stdDeviation="4" flood-color="#000" flood-opacity="0.25" />
          </filter>
          <filter id="cyc-shadow-lg" x="-10%" y="-10%" width="120%" height="130%">
            <feDropShadow dx="4" dy="8" stdDeviation="6" flood-color="#000" flood-opacity="0.35" />
          </filter>
        </defs>

        <!-- 中央ラベル -->
        <circle cx="250" cy="250" r="55" fill="var(--sakura-pink,#D27E99)" filter="url(#cyc-shadow)" />
        <foreignObject x="195" y="215" width="110" height="70">
          <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card"
               style="color:var(--bg-dark,#1F1F28);font-weight:700;font-size:1.2rem;">
            <span>{{中央ラベル}}</span>
          </div>
        </foreignObject>

        <!-- 接続円弧（時計回り矢印） -->
        <path d="M 310,100 A 160,160 0 0,1 400,190" fill="none"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5" marker-end="url(#cyc-arrow)" />
        <path d="M 400,310 A 160,160 0 0,1 310,400" fill="none"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5" marker-end="url(#cyc-arrow)" />
        <path d="M 190,400 A 160,160 0 0,1 100,310" fill="none"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5" marker-end="url(#cyc-arrow)" />
        <path d="M 100,190 A 160,160 0 0,1 190,100" fill="none"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5" marker-end="url(#cyc-arrow)" />

        <!-- 要素1: 上（Plan等） -->
        <g class="node-group has-tooltip" data-tooltip="{{説明1}}">
          <rect x="180" y="30" width="140" height="70" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--wave-blue,#7E9CD8)"
                stroke-width="2.5" filter="url(#cyc-shadow)" />
          <foreignObject x="188" y="38" width="124" height="54">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.3rem;font-weight:600;">
              <i class="fas {{アイコン1}}" style="color:var(--wave-blue,#7E9CD8)"></i>
              <span>{{テキスト1}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 要素2: 右（Do等） -->
        <g class="node-group has-tooltip" data-tooltip="{{説明2}}">
          <rect x="370" y="215" width="140" height="70" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--spring-green,#98BB6C)"
                stroke-width="2.5" filter="url(#cyc-shadow)" />
          <foreignObject x="378" y="223" width="124" height="54">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.3rem;font-weight:600;">
              <i class="fas {{アイコン2}}" style="color:var(--spring-green,#98BB6C)"></i>
              <span>{{テキスト2}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 要素3: 下（Check等） -->
        <g class="node-group has-tooltip" data-tooltip="{{説明3}}">
          <rect x="180" y="400" width="140" height="70" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--autumn-yellow,#DCA561)"
                stroke-width="2.5" filter="url(#cyc-shadow)" />
          <foreignObject x="188" y="408" width="124" height="54">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.3rem;font-weight:600;">
              <i class="fas {{アイコン3}}" style="color:var(--autumn-yellow,#DCA561)"></i>
              <span>{{テキスト3}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 要素4: 左（Act等） -->
        <g class="node-group has-tooltip" data-tooltip="{{説明4}}">
          <rect x="-10" y="215" width="140" height="70" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--sakura-pink,#D27E99)"
                stroke-width="2.5" filter="url(#cyc-shadow)" />
          <foreignObject x="-2" y="223" width="124" height="54">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.3rem;font-weight:600;">
              <i class="fas {{アイコン4}}" style="color:var(--sakura-pink,#D27E99)"></i>
              <span>{{テキスト4}}</span>
            </div>
          </foreignObject>
        </g>
      </svg>
    </div>
  </div>
</div>
```

#### 要素数バリエーション座標

| 要素数 | 座標計算（中心250,250、半径180） |
|--------|--------------------------------|
| 3要素 | 上(250,70) 右下(406,385) 左下(94,385) |
| 4要素 | 上(250,70) 右(430,250) 下(250,430) 左(70,250) |
| 5要素 | 上(250,70) 右上(421,141) 右下(356,392) 左下(144,392) 左上(79,141) |
| 6要素 | 上(250,70) 右上(406,160) 右下(406,340) 下(250,430) 左下(94,340) 左上(94,160) |

#### 11.1.2 スネーク型サイクル（蛇行フロー・SVG2）

上下に蛇行しながら進むフロー。長いプロセスに最適。

```css
.slide-snake .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-snake .snake-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-snake .diagram-svg-container {
  width: 100%;
  max-width: 900px;
  aspect-ratio: 16 / 9;
}
```

```html
<div class="slider__item slide-snake">
  <div class="slider__content">
    <h2 class="snake-title"><i class="fas fa-stream"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 900 400" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{タイトル}}の蛇行フロー">
        <defs>
          <marker id="snake-arrow" viewBox="0 0 10 10" refX="10" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--autumn-yellow,#DCA561)" />
          </marker>
          <filter id="snake-shadow" x="-5%" y="-5%" width="110%" height="115%">
            <feDropShadow dx="2" dy="3" stdDeviation="3" flood-color="#000" flood-opacity="0.25" />
          </filter>
        </defs>

        <!-- 行1: 左→右 (Step 1-3) -->
        <!-- Step 1 -->
        <g class="node-group">
          <rect x="30" y="30" width="200" height="80" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--wave-blue,#7E9CD8)"
                stroke-width="2.5" filter="url(#snake-shadow)" />
          <circle cx="60" cy="50" r="15" fill="var(--wave-blue,#7E9CD8)" />
          <text x="60" y="55" text-anchor="middle" font-size="14" font-weight="700"
                fill="var(--bg-dark,#1F1F28)">1</text>
          <foreignObject x="80" y="40" width="140" height="60">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="color:var(--fg-default,#DCD7BA);font-size:1.3rem;">
              {{テキスト1}}
            </div>
          </foreignObject>
        </g>

        <!-- 矢印 Step1→2 -->
        <line x1="230" y1="70" x2="310" y2="70"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5"
              marker-end="url(#snake-arrow)" />

        <!-- Step 2 -->
        <g class="node-group">
          <rect x="320" y="30" width="200" height="80" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--wave-blue,#7E9CD8)"
                stroke-width="2.5" filter="url(#snake-shadow)" />
          <circle cx="350" cy="50" r="15" fill="var(--wave-blue,#7E9CD8)" />
          <text x="350" y="55" text-anchor="middle" font-size="14" font-weight="700"
                fill="var(--bg-dark,#1F1F28)">2</text>
          <foreignObject x="370" y="40" width="140" height="60">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="color:var(--fg-default,#DCD7BA);font-size:1.3rem;">
              {{テキスト2}}
            </div>
          </foreignObject>
        </g>

        <!-- 矢印 Step2→3 -->
        <line x1="520" y1="70" x2="600" y2="70"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5"
              marker-end="url(#snake-arrow)" />

        <!-- Step 3 -->
        <g class="node-group">
          <rect x="610" y="30" width="200" height="80" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--wave-blue,#7E9CD8)"
                stroke-width="2.5" filter="url(#snake-shadow)" />
          <circle cx="640" cy="50" r="15" fill="var(--wave-blue,#7E9CD8)" />
          <text x="640" y="55" text-anchor="middle" font-size="14" font-weight="700"
                fill="var(--bg-dark,#1F1F28)">3</text>
          <foreignObject x="660" y="40" width="140" height="60">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="color:var(--fg-default,#DCD7BA);font-size:1.3rem;">
              {{テキスト3}}
            </div>
          </foreignObject>
        </g>

        <!-- 折り返し矢印（右→下→左） -->
        <path d="M 810,110 Q 850,180 810,210" fill="none"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5"
              marker-end="url(#snake-arrow)" />

        <!-- 行2: 右→左 (Step 4-6) -->
        <!-- Step 4 -->
        <g class="node-group">
          <rect x="610" y="220" width="200" height="80" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--spring-green,#98BB6C)"
                stroke-width="2.5" filter="url(#snake-shadow)" />
          <circle cx="640" cy="240" r="15" fill="var(--spring-green,#98BB6C)" />
          <text x="640" y="245" text-anchor="middle" font-size="14" font-weight="700"
                fill="var(--bg-dark,#1F1F28)">4</text>
          <foreignObject x="660" y="230" width="140" height="60">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="color:var(--fg-default,#DCD7BA);font-size:1.3rem;">
              {{テキスト4}}
            </div>
          </foreignObject>
        </g>

        <!-- 矢印 Step4→5（左向き） -->
        <line x1="610" y1="260" x2="530" y2="260"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5"
              marker-end="url(#snake-arrow)" />

        <!-- Step 5 -->
        <g class="node-group">
          <rect x="320" y="220" width="200" height="80" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--spring-green,#98BB6C)"
                stroke-width="2.5" filter="url(#snake-shadow)" />
          <circle cx="350" cy="240" r="15" fill="var(--spring-green,#98BB6C)" />
          <text x="350" y="245" text-anchor="middle" font-size="14" font-weight="700"
                fill="var(--bg-dark,#1F1F28)">5</text>
          <foreignObject x="370" y="230" width="140" height="60">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="color:var(--fg-default,#DCD7BA);font-size:1.3rem;">
              {{テキスト5}}
            </div>
          </foreignObject>
        </g>

        <!-- 矢印 Step5→6（左向き） -->
        <line x1="320" y1="260" x2="240" y2="260"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2.5"
              marker-end="url(#snake-arrow)" />

        <!-- Step 6 -->
        <g class="node-group">
          <rect x="30" y="220" width="200" height="80" rx="12"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--spring-green,#98BB6C)"
                stroke-width="2.5" filter="url(#snake-shadow)" />
          <circle cx="60" cy="240" r="15" fill="var(--spring-green,#98BB6C)" />
          <text x="60" y="245" text-anchor="middle" font-size="14" font-weight="700"
                fill="var(--bg-dark,#1F1F28)">6</text>
          <foreignObject x="80" y="230" width="140" height="60">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="color:var(--fg-default,#DCD7BA);font-size:1.3rem;">
              {{テキスト6}}
            </div>
          </foreignObject>
        </g>
      </svg>
    </div>
  </div>
</div>
```

### 11.2 ベン図（SVG2）

SVGの`<circle>`と`opacity`で正確な重なり表現。

#### 11.2.1 2円ベン図

```css
.slide-venn .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-venn .venn-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-venn .diagram-svg-container {
  width: 100%;
  max-width: 700px;
  aspect-ratio: 3 / 2;
}

.slide-venn .diagram-svg .venn-area {
  cursor: pointer;
  transition: opacity 0.3s ease;
}

.slide-venn .diagram-svg .venn-area:hover {
  opacity: 0.9;
}
```

```html
<div class="slider__item slide-venn venn-2">
  <div class="slider__content">
    <h2 class="venn-title"><i class="fas fa-circle-notch"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{タイトル}}のベン図">
        <!-- 左円 -->
        <g class="venn-area">
          <circle cx="220" cy="200" r="150"
                  fill="var(--wave-blue,#7E9CD8)" fill-opacity="0.4"
                  stroke="var(--wave-blue,#7E9CD8)" stroke-width="3" />
          <foreignObject x="100" y="160" width="140" height="80">
            <div xmlns="http://www.w3.org/1999/xhtml"
                 class="fo-card has-tooltip" data-tooltip="{{詳細A}}"
                 style="gap:4px;color:var(--fg-default,#DCD7BA);font-size:1.4rem;font-weight:700;">
              <i class="fas {{アイコンA}}" style="font-size:1.6rem;color:var(--wave-blue,#7E9CD8)"></i>
              <span>{{ラベルA}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 右円 -->
        <g class="venn-area">
          <circle cx="380" cy="200" r="150"
                  fill="var(--sakura-pink,#D27E99)" fill-opacity="0.4"
                  stroke="var(--sakura-pink,#D27E99)" stroke-width="3" />
          <foreignObject x="360" y="160" width="140" height="80">
            <div xmlns="http://www.w3.org/1999/xhtml"
                 class="fo-card has-tooltip" data-tooltip="{{詳細B}}"
                 style="gap:4px;color:var(--fg-default,#DCD7BA);font-size:1.4rem;font-weight:700;">
              <i class="fas {{アイコンB}}" style="font-size:1.6rem;color:var(--sakura-pink,#D27E99)"></i>
              <span>{{ラベルB}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 交差部分ラベル -->
        <foreignObject x="250" y="170" width="100" height="60">
          <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card"
               style="background:var(--autumn-yellow,#DCA561);border-radius:8px;padding:0.5rem;
                      color:var(--bg-dark,#1F1F28);font-weight:700;font-size:1.2rem;">
            {{A∩B}}
          </div>
        </foreignObject>
      </svg>
    </div>
  </div>
</div>
```

#### 11.2.2 3円ベン図

```html
<div class="slider__item slide-venn venn-3">
  <div class="slider__content">
    <h2 class="venn-title"><i class="fas fa-circle-notch"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 700 500" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{タイトル}}の3円ベン図">
        <!-- 上円 -->
        <g class="venn-area">
          <circle cx="350" cy="180" r="140"
                  fill="var(--wave-blue,#7E9CD8)" fill-opacity="0.35"
                  stroke="var(--wave-blue,#7E9CD8)" stroke-width="3" />
          <foreignObject x="295" y="100" width="110" height="70">
            <div xmlns="http://www.w3.org/1999/xhtml"
                 class="fo-card has-tooltip" data-tooltip="{{詳細A}}"
                 style="gap:4px;color:var(--fg-default,#DCD7BA);font-size:1.3rem;font-weight:700;">
              <i class="fas {{アイコンA}}" style="color:var(--wave-blue,#7E9CD8)"></i>
              <span>{{ラベルA}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 左下円 -->
        <g class="venn-area">
          <circle cx="250" cy="330" r="140"
                  fill="var(--sakura-pink,#D27E99)" fill-opacity="0.35"
                  stroke="var(--sakura-pink,#D27E99)" stroke-width="3" />
          <foreignObject x="140" y="330" width="110" height="70">
            <div xmlns="http://www.w3.org/1999/xhtml"
                 class="fo-card has-tooltip" data-tooltip="{{詳細B}}"
                 style="gap:4px;color:var(--fg-default,#DCD7BA);font-size:1.3rem;font-weight:700;">
              <i class="fas {{アイコンB}}" style="color:var(--sakura-pink,#D27E99)"></i>
              <span>{{ラベルB}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 右下円 -->
        <g class="venn-area">
          <circle cx="450" cy="330" r="140"
                  fill="var(--spring-green,#98BB6C)" fill-opacity="0.35"
                  stroke="var(--spring-green,#98BB6C)" stroke-width="3" />
          <foreignObject x="450" y="330" width="110" height="70">
            <div xmlns="http://www.w3.org/1999/xhtml"
                 class="fo-card has-tooltip" data-tooltip="{{詳細C}}"
                 style="gap:4px;color:var(--fg-default,#DCD7BA);font-size:1.3rem;font-weight:700;">
              <i class="fas {{アイコンC}}" style="color:var(--spring-green,#98BB6C)"></i>
              <span>{{ラベルC}}</span>
            </div>
          </foreignObject>
        </g>

        <!-- 2円交差ラベル -->
        <text x="280" y="240" text-anchor="middle" font-size="13" font-weight="600"
              fill="var(--fg-default,#DCD7BA)">{{A∩B}}</text>
        <text x="420" y="240" text-anchor="middle" font-size="13" font-weight="600"
              fill="var(--fg-default,#DCD7BA)">{{A∩C}}</text>
        <text x="350" y="380" text-anchor="middle" font-size="13" font-weight="600"
              fill="var(--fg-default,#DCD7BA)">{{B∩C}}</text>

        <!-- 3円交差ラベル -->
        <foreignObject x="305" y="265" width="90" height="50">
          <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card"
               style="background:var(--autumn-yellow,#DCA561);border-radius:8px;
                      color:var(--bg-dark,#1F1F28);font-weight:700;font-size:1.1rem;">
            {{A∩B∩C}}
          </div>
        </foreignObject>
      </svg>
    </div>
  </div>
</div>
```

### 11.3 マインドマップ（SVG2）

SVGのpath接続線で中央から放射状に広がる概念マップを正確に描画。

```css
.slide-mindmap .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-mindmap .mindmap-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-mindmap .diagram-svg-container {
  width: 100%;
  max-width: 960px;
  aspect-ratio: 16 / 9;
}

.slide-mindmap .diagram-svg .branch-node {
  cursor: pointer;
  transition: opacity 0.3s ease;
}

.slide-mindmap .diagram-svg .branch-node:hover rect {
  filter: url(#mm-shadow-lg);
  stroke-width: 3;
}
```

```html
<div class="slider__item slide-mindmap">
  <div class="slider__content">
    <h2 class="mindmap-title"><i class="fas fa-project-diagram"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{タイトル}}のマインドマップ">
        <defs>
          <filter id="mm-shadow" x="-5%" y="-5%" width="110%" height="115%">
            <feDropShadow dx="2" dy="3" stdDeviation="3" flood-color="#000" flood-opacity="0.25" />
          </filter>
          <filter id="mm-shadow-lg" x="-8%" y="-8%" width="116%" height="120%">
            <feDropShadow dx="3" dy="6" stdDeviation="5" flood-color="#000" flood-opacity="0.35" />
          </filter>
          <linearGradient id="mm-grad-center" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="var(--wave-blue,#7E9CD8)" />
            <stop offset="100%" stop-color="var(--sakura-pink,#D27E99)" />
          </linearGradient>
        </defs>

        <!-- 接続線（中央→各ブランチ） -->
        <path d="M 480,270 Q 600,200 720,160" fill="none"
              stroke="var(--sakura-pink,#D27E99)" stroke-width="2" stroke-opacity="0.6" />
        <path d="M 480,270 Q 620,270 760,270" fill="none"
              stroke="var(--wave-aqua,#7AA89F)" stroke-width="2" stroke-opacity="0.6" />
        <path d="M 480,270 Q 600,340 720,380" fill="none"
              stroke="var(--spring-green,#98BB6C)" stroke-width="2" stroke-opacity="0.6" />
        <path d="M 480,270 Q 360,200 240,160" fill="none"
              stroke="var(--autumn-yellow,#DCA561)" stroke-width="2" stroke-opacity="0.6" />
        <path d="M 480,270 Q 340,270 200,270" fill="none"
              stroke="var(--wave-blue,#7E9CD8)" stroke-width="2" stroke-opacity="0.6" />
        <path d="M 480,270 Q 360,340 240,380" fill="none"
              stroke="var(--wave-blue,#7E9CD8)" stroke-width="2" stroke-opacity="0.6" />

        <!-- 中央ノード -->
        <g filter="url(#mm-shadow)">
          <rect x="390" y="235" width="180" height="70" rx="16"
                fill="url(#mm-grad-center)" />
          <foreignObject x="398" y="243" width="164" height="54">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card"
                 style="color:var(--bg-dark,#1F1F28);font-weight:700;font-size:1.5rem;">
              {{中央テーマ}}
            </div>
          </foreignObject>
        </g>

        <!-- ブランチ1: 右上 -->
        <g class="branch-node">
          <rect x="680" y="130" width="170" height="55" rx="8"
                fill="var(--bg-dim,#2A2A37)"
                stroke="var(--sakura-pink,#D27E99)" stroke-width="2" filter="url(#mm-shadow)" />
          <foreignObject x="688" y="138" width="154" height="39">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.2rem;font-weight:600;">
              <span style="color:var(--sakura-pink,#D27E99)">&#9679;</span>
              {{ブランチ1}}
            </div>
          </foreignObject>
        </g>

        <!-- ブランチ2: 右 -->
        <g class="branch-node">
          <rect x="720" y="245" width="170" height="55" rx="8"
                fill="var(--bg-dim,#2A2A37)"
                stroke="var(--wave-aqua,#7AA89F)" stroke-width="2" filter="url(#mm-shadow)" />
          <foreignObject x="728" y="253" width="154" height="39">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.2rem;font-weight:600;">
              <span style="color:var(--wave-aqua,#7AA89F)">&#9679;</span>
              {{ブランチ2}}
            </div>
          </foreignObject>
        </g>

        <!-- ブランチ3: 右下 -->
        <g class="branch-node">
          <rect x="680" y="355" width="170" height="55" rx="8"
                fill="var(--bg-dim,#2A2A37)"
                stroke="var(--spring-green,#98BB6C)" stroke-width="2" filter="url(#mm-shadow)" />
          <foreignObject x="688" y="363" width="154" height="39">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.2rem;font-weight:600;">
              <span style="color:var(--spring-green,#98BB6C)">&#9679;</span>
              {{ブランチ3}}
            </div>
          </foreignObject>
        </g>

        <!-- ブランチ4: 左上 -->
        <g class="branch-node">
          <rect x="110" y="130" width="170" height="55" rx="8"
                fill="var(--bg-dim,#2A2A37)"
                stroke="var(--autumn-yellow,#DCA561)" stroke-width="2" filter="url(#mm-shadow)" />
          <foreignObject x="118" y="138" width="154" height="39">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.2rem;font-weight:600;">
              <span style="color:var(--autumn-yellow,#DCA561)">&#9679;</span>
              {{ブランチ4}}
            </div>
          </foreignObject>
        </g>

        <!-- ブランチ5: 左 -->
        <g class="branch-node">
          <rect x="70" y="245" width="170" height="55" rx="8"
                fill="var(--bg-dim,#2A2A37)"
                stroke="var(--wave-blue,#7E9CD8)" stroke-width="2" filter="url(#mm-shadow)" />
          <foreignObject x="78" y="253" width="154" height="39">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.2rem;font-weight:600;">
              <span style="color:var(--wave-blue,#7E9CD8)">&#9679;</span>
              {{ブランチ5}}
            </div>
          </foreignObject>
        </g>

        <!-- ブランチ6: 左下 -->
        <g class="branch-node">
          <rect x="110" y="355" width="170" height="55" rx="8"
                fill="var(--bg-dim,#2A2A37)"
                stroke="var(--wave-blue,#7E9CD8)" stroke-width="2" filter="url(#mm-shadow)" />
          <foreignObject x="118" y="363" width="154" height="39">
            <div xmlns="http://www.w3.org/1999/xhtml" class="fo-card fo-card--row"
                 style="gap:6px;color:var(--fg-default,#DCD7BA);font-size:1.2rem;font-weight:600;">
              <span style="color:var(--wave-blue,#7E9CD8)">&#9679;</span>
              {{ブランチ6}}
            </div>
          </foreignObject>
        </g>
      </svg>
    </div>
  </div>
</div>
```

### 11.4 フローチャート型（SVG2）

SVGのpolygon/rectで正確なノード形状、path接続線で精密なフロー表現。

```css
.slide-flowchart .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-flowchart .flowchart-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-flowchart .diagram-svg-container {
  width: 100%;
  max-width: 800px;
  aspect-ratio: 4 / 5;
}

.slide-flowchart .diagram-svg .fc-node {
  cursor: pointer;
  transition: opacity 0.3s ease;
}

.slide-flowchart .diagram-svg .fc-node:hover rect,
.slide-flowchart .diagram-svg .fc-node:hover polygon {
  filter: url(#fc-shadow-lg);
}
```

```html
<div class="slider__item slide-flowchart">
  <div class="slider__content">
    <h2 class="flowchart-title"><i class="fas fa-sitemap"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 500 600" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{タイトル}}のフローチャート">
        <defs>
          <marker id="fc-arrow" viewBox="0 0 10 10" refX="10" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--fuji-gray,#727169)" />
          </marker>
          <filter id="fc-shadow" x="-5%" y="-5%" width="110%" height="115%">
            <feDropShadow dx="2" dy="3" stdDeviation="3" flood-color="#000" flood-opacity="0.25" />
          </filter>
          <filter id="fc-shadow-lg" x="-8%" y="-8%" width="116%" height="120%">
            <feDropShadow dx="3" dy="6" stdDeviation="5" flood-color="#000" flood-opacity="0.35" />
          </filter>
        </defs>

        <!-- 開始（カプセル型） -->
        <g class="fc-node">
          <rect x="180" y="20" width="140" height="45" rx="22" ry="22"
                fill="var(--sakura-pink,#D27E99)" filter="url(#fc-shadow)" />
          <text x="250" y="47" text-anchor="middle" dominant-baseline="central"
                fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="16">開始</text>
        </g>

        <!-- 矢印: 開始→処理1 -->
        <line x1="250" y1="65" x2="250" y2="100"
              stroke="var(--fuji-gray,#727169)" stroke-width="2.5" marker-end="url(#fc-arrow)" />

        <!-- 処理1（矩形） -->
        <g class="fc-node">
          <rect x="170" y="105" width="160" height="55" rx="8"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--wave-blue,#7E9CD8)"
                stroke-width="2.5" filter="url(#fc-shadow)" />
          <text x="250" y="137" text-anchor="middle" dominant-baseline="central"
                fill="var(--fg-default,#DCD7BA)" font-size="15">{{処理1}}</text>
        </g>

        <!-- 矢印: 処理1→判断 -->
        <line x1="250" y1="160" x2="250" y2="200"
              stroke="var(--fuji-gray,#727169)" stroke-width="2.5" marker-end="url(#fc-arrow)" />

        <!-- 判断（ひし形） -->
        <g class="fc-node">
          <polygon points="250,200 330,255 250,310 170,255"
                   fill="var(--autumn-yellow,#DCA561)" filter="url(#fc-shadow)" />
          <text x="250" y="258" text-anchor="middle" dominant-baseline="central"
                fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="14">{{条件?}}</text>
        </g>

        <!-- 分岐: Yes（左） -->
        <line x1="170" y1="255" x2="80" y2="255"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" />
        <line x1="80" y1="255" x2="80" y2="370"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" marker-end="url(#fc-arrow)" />
        <text x="130" y="248" text-anchor="middle" font-size="13" font-weight="700"
              fill="var(--spring-green,#98BB6C)">Yes</text>

        <!-- 処理A -->
        <g class="fc-node">
          <rect x="10" y="375" width="140" height="50" rx="8"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--spring-green,#98BB6C)"
                stroke-width="2.5" filter="url(#fc-shadow)" />
          <text x="80" y="404" text-anchor="middle" dominant-baseline="central"
                fill="var(--fg-default,#DCD7BA)" font-size="14">{{処理A}}</text>
        </g>

        <!-- 分岐: No（右） -->
        <line x1="330" y1="255" x2="420" y2="255"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" />
        <line x1="420" y1="255" x2="420" y2="370"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" marker-end="url(#fc-arrow)" />
        <text x="370" y="248" text-anchor="middle" font-size="13" font-weight="700"
              fill="var(--sakura-pink,#D27E99)">No</text>

        <!-- 処理B -->
        <g class="fc-node">
          <rect x="350" y="375" width="140" height="50" rx="8"
                fill="var(--bg-dim,#2A2A37)" stroke="var(--sakura-pink,#D27E99)"
                stroke-width="2.5" filter="url(#fc-shadow)" />
          <text x="420" y="404" text-anchor="middle" dominant-baseline="central"
                fill="var(--fg-default,#DCD7BA)" font-size="14">{{処理B}}</text>
        </g>

        <!-- 合流線 -->
        <line x1="80" y1="425" x2="80" y2="470"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" />
        <line x1="420" y1="425" x2="420" y2="470"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" />
        <line x1="80" y1="470" x2="420" y2="470"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" />
        <line x1="250" y1="470" x2="250" y2="510"
              stroke="var(--fuji-gray,#727169)" stroke-width="2.5" marker-end="url(#fc-arrow)" />

        <!-- 合流点（丸） -->
        <circle cx="250" cy="470" r="8" fill="var(--fuji-gray,#727169)" />

        <!-- 終了（カプセル型） -->
        <g class="fc-node">
          <rect x="180" y="515" width="140" height="45" rx="22" ry="22"
                fill="var(--sakura-pink,#D27E99)" filter="url(#fc-shadow)" />
          <text x="250" y="542" text-anchor="middle" dominant-baseline="central"
                fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="16">終了</text>
        </g>
      </svg>
    </div>
  </div>
</div>
```

### 11.5 上昇型（SVG2: 成長・向上フロー）

SVGのpath + circleで時間経過に伴う成長を精密に可視化。

```css
.slide-growth .slider__content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  align-items: center;
}

.slide-growth .growth-title {
  font-size: var(--fs-heading);
  font-weight: 700;
  text-align: center;
}

.slide-growth .diagram-svg-container {
  width: 100%;
  max-width: 900px;
  aspect-ratio: 2 / 1;
}

.slide-growth .diagram-svg .growth-point {
  cursor: pointer;
  transition: opacity 0.3s ease;
}

.slide-growth .diagram-svg .growth-point:hover circle {
  r: 32;
  filter: url(#growth-glow);
}
```

```html
<div class="slider__item slide-growth">
  <div class="slider__content">
    <h2 class="growth-title"><i class="fas fa-chart-line"></i> {{タイトル}}</h2>
    <div class="diagram-svg-container">
      <svg viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg"
           class="diagram-svg" role="img" aria-label="{{タイトル}}の上昇フロー">
        <defs>
          <filter id="growth-shadow" x="-5%" y="-5%" width="110%" height="115%">
            <feDropShadow dx="2" dy="3" stdDeviation="3" flood-color="#000" flood-opacity="0.25" />
          </filter>
          <filter id="growth-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feFlood flood-color="var(--wave-blue,#7E9CD8)" flood-opacity="0.4" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="growth-area" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="var(--wave-blue,#7E9CD8)" stop-opacity="0.3" />
            <stop offset="100%" stop-color="var(--wave-blue,#7E9CD8)" stop-opacity="0.05" />
          </linearGradient>
        </defs>

        <!-- 時間軸（X軸） -->
        <line x1="80" y1="340" x2="750" y2="340"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" />
        <text x="760" y="345" font-size="13" fill="var(--fg-dim,#727169)">時間</text>

        <!-- 価値軸（Y軸） -->
        <line x1="80" y1="340" x2="80" y2="40"
              stroke="var(--fuji-gray,#727169)" stroke-width="2" />
        <text x="70" y="30" font-size="13" fill="var(--fg-dim,#727169)" text-anchor="end">価値</text>

        <!-- 上昇エリア（塗りつぶし） -->
        <path d="M 150,300 Q 300,270 400,220 Q 500,150 600,80 L 600,340 L 150,340 Z"
              fill="url(#growth-area)" />

        <!-- 上昇線 -->
        <path d="M 150,300 Q 300,270 400,220 Q 500,150 600,80"
              fill="none" stroke="var(--wave-blue,#7E9CD8)" stroke-width="3" />

        <!-- ステップポイント1 -->
        <g class="growth-point has-tooltip" data-tooltip="{{詳細1}}">
          <circle cx="150" cy="300" r="28" fill="var(--wave-blue,#7E9CD8)" filter="url(#growth-shadow)" />
          <text x="150" y="305" text-anchor="middle" dominant-baseline="central"
                fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="16">1</text>
        </g>
        <text x="150" y="365" text-anchor="middle" font-size="13"
              fill="var(--fg-default,#DCD7BA)">{{ラベル1}}</text>

        <!-- ステップポイント2 -->
        <g class="growth-point has-tooltip" data-tooltip="{{詳細2}}">
          <circle cx="300" cy="260" r="28" fill="var(--wave-blue,#7E9CD8)" filter="url(#growth-shadow)" />
          <text x="300" y="265" text-anchor="middle" dominant-baseline="central"
                fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="16">2</text>
        </g>
        <text x="300" y="365" text-anchor="middle" font-size="13"
              fill="var(--fg-default,#DCD7BA)">{{ラベル2}}</text>

        <!-- ステップポイント3 -->
        <g class="growth-point has-tooltip" data-tooltip="{{詳細3}}">
          <circle cx="450" cy="190" r="28" fill="var(--wave-blue,#7E9CD8)" filter="url(#growth-shadow)" />
          <text x="450" y="195" text-anchor="middle" dominant-baseline="central"
                fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="16">3</text>
        </g>
        <text x="450" y="365" text-anchor="middle" font-size="13"
              fill="var(--fg-default,#DCD7BA)">{{ラベル3}}</text>

        <!-- ステップポイント4 -->
        <g class="growth-point has-tooltip" data-tooltip="{{詳細4}}">
          <circle cx="600" cy="80" r="28" fill="var(--sakura-pink,#D27E99)" filter="url(#growth-shadow)" />
          <text x="600" y="85" text-anchor="middle" dominant-baseline="central"
                fill="var(--bg-dark,#1F1F28)" font-weight="700" font-size="16">4</text>
        </g>
        <text x="600" y="365" text-anchor="middle" font-size="13"
              fill="var(--fg-default,#DCD7BA)">{{ラベル4}}</text>
      </svg>
    </div>
  </div>
</div>
```

---

## CSS→SVG 移行メモ

| 変更点 | 旧（CSS） | 新（SVG2） |
|--------|----------|-----------|
| 要素配置 | `position:absolute` + `nth-child` | SVG座標 `transform="translate(x,y)"` |
| 矢印 | FontAwesome `fa-arrow-*` + CSS回転 | SVG `<marker>` + `<path>` |
| 円弧接続 | CSS疑似要素 | SVG `<path d="...A...">`（円弧コマンド） |
| ひし形 | `clip-path:polygon()` | SVG `<polygon points="...">` |
| 重なり | `rgba()` + `z-index` | SVG `fill-opacity` |
| 接続線 | CSS `border` + 位置計算 | SVG `<line>` / `<path>` |
| ホバー | CSS `:hover { transform }` | CSS `.interactive:hover` + SVG filter |
| ツールチップ | `has-tooltip` on HTML div | `has-tooltip` on `<foreignObject>` child |

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-02-15 | SVG2全面移行: サイクル図・スネーク型・ベン図・マインドマップ・フローチャート・上昇型の全6タイプをインラインSVG2に変換。CSS absoluteポジショニングを廃止し、SVG座標系・path・marker・filterに統一 |
| 1.0.0 | 2026-01-23 | 初版（CSSベース） |
