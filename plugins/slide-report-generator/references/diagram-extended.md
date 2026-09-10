# 図解タイプ: 運用・体験・増減系（SVG 手書き経路）

<!-- css-route: diagram -->
<!-- この宣言より後ろの var() は diagram 経路の :root とだけ照合される (lint-contract-drift.py check G)。経路が違う例を載せるときは、その直前に別の css-route 宣言を置く -->

**責務**: カンバンボード、ユーザージャーニーマップ、ウォーターフォールチャート、ヒートマップの SVG テンプレート

**含まれるタイプ**: 11.41-11.44

**前提**: [svg-diagram-primitives.md](svg-diagram-primitives.md) のプリミティブと
[diagram-layout-contract.md](diagram-layout-contract.md) 第 4 次 update 章（§D-1〜§D-5）

> 本ファイルの 4 型はいずれも**決定論ビルダー（`vendor/scripts/svg-builder.cjs`）を持たない**。
> `heatmap` / `sankey` は d3 のインタラクティブ tpl だけが存在しており、
> **印刷とスライドに載る静的な 1 枚**を作る経路がなかった。本ファイルはその穴を埋める。
> 決定論ビルダーが無いということは `CAPACITY`・`LAYOUTS`・`safeElbow`・`TOKENS` の
> 4 つの防具が効かないということなので、骨格
> （`assets/diagram-templates/diagram-skeleton-{slide,report}.html`）を必ずコピーして始める。
> 白紙から SVG を書き始めると、色を発明し、座標を思いつきで置き、影を付ける。

**共通の禁止**: `var(--x, fallback)` 以外の色の書き方／4px グリッド外の座標・寸法・角丸／
1 図あたり 3 件以上の `accent`／斜めのコネクタ（§D-3 原則 1）／影（R9-14）。

**斜め線禁止の例外はデータ線だけ**: §11.42 の感情の推移線と §11.43 の橋渡し兼累計線は、
「ノード間を結ぶコネクタ」ではなく**量や気分の推移そのものを形にした線**なので
§D-3 原則 1 の対象外である。この 2 本は `<polyline>` で描く。
`validate-svg-diagram.py` の D5 は `<line>`、D17 は `<path>` を見る検査なので、
型語彙のデータ線を検査対象の要素で書かないことが、契約と検査を同時に満たす唯一の書き方である
（前例: `skills/run-slide-report-generate/examples/diagram-goldens/line-chart-golden.html`）。

---

### 11.41 カンバンボード型（Kanban Board）

**列に積まれた枚数**で仕事の滞留を示す。工程の順序を語る §11.4 フローや
§11.23 シェブロンとの違いは、**主題が「どこを通るか」ではなく「どこに何枚溜まっているか」**である点にある。
枚数と WIP 上限の対比が主張の本体であるときにだけ選ぶ。

| 判断 | 内容 |
|---|---|
| **Best for** | 仕掛かりの滞留、WIP 上限の運用状況、チームの現在地レビュー、着手前／着手中／完了の在庫バランス |
| **使わない場面** | 工程そのものの順序が主題（→ §11.4 フロー・§11.23 シェブロン）／期間の長さが主題（→ §11.8 ガント）／担当と工程の交差が主題（→ スイムレーン） |
| **複雑度上限** | **列 3-5 / カード総数 9**（`diagram-layout-contract.md` §D-2 #1 ノード総数 9 の型別具体化）。1 列 4 枚を超えたら、その列は「盤面」ではなく「バックログ」なので図から外して本文へ移す。`accent` は**超過している列 1 つ + その原因のカード 1 枚**の計 2 件まで（同 #3） |
| **必須情報** | 各列の WIP 上限と現在枚数を見出し右端に「上限 n・m 枚」で、各列の完了条件を列見出しへ括弧で添えて（`レビュー (2 名承認で完了)`）、焦点カードの滞留期間をカード内 2 行目に（`5 週目・上限超過`）、盤面の時点を図の下端 1 行に年を含めて（`2026/04/15 時点`）書く。上限が無ければ枚数が多いのか少ないのか判定できず、完了条件が無ければそのカードが次列へ動くべきか判定できない |
| **推奨配置** | 横帯 |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- 列は 3 列なら幅 `272`・列間 `40`（x = 32 / 344 / 656）。列数を変えるときは
  「左右余白 32 + 列間 40」を固定して幅だけ配り直す。列ごとに幅を変えない
- 列の面は 3 列とも同じ塗り（`paper-2`）。列で塗りを変えると進捗が色の話になる
- カードは列の内側 `16` に `240 × 72`、縦の間隔は `88`（カード高 72 + 16）で**全列そろえる**。
  列ごとにカード高を変えない（高さの差は「重さの差」に読まれる）
- 列見出しは面の上（y = 64）に置き、下端をヘアラインで切る。
  **WIP 上限は見出しの右端に「上限 n・m 枚」の形で必ず出す**。
  上限を書かないカンバン図は、枚数を数える意味を読者へ渡し損ねている
- 盤面の進行方向は図の下端に矢印 1 本だけで示す。カードとカードの間に線を引かない

```html
<figure class="srg-diagram srg-diagram--report" data-diagram-id="f1" data-figure-width="text">
  <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-labelledby="f1-caption">
    <defs>
      <marker id="f1-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
        <polygon points="0 0, 8 3, 0 6" fill="var(--fg-muted)"/>
      </marker>
    </defs>

    <!-- 列の面 (3 列とも同じ塗り) -->
    <rect x="32" y="88" width="272" height="376" rx="8" fill="#F8F7F0"/>
    <rect x="344" y="88" width="272" height="376" rx="8" fill="#F8F7F0"/>
    <rect x="656" y="88" width="272" height="376" rx="8" fill="#F8F7F0"/>

    <!-- 列見出しと WIP 表示 (上限を超えている列だけが accent) -->
    <text x="32" y="64" font-size="16" fill="var(--fg)">{{列1}}</text>
    <text x="304" y="64" text-anchor="end" font-size="12" fill="var(--fg-muted, #6A6A68)">上限なし・3 枚</text>
    <line x1="32" y1="76" x2="304" y2="76" stroke="#DCD7BA" stroke-width="1.25"/>

    <text x="344" y="64" font-size="16" fill="var(--fg)">{{列2}}</text>
    <text x="616" y="64" text-anchor="end" font-size="12" fill="var(--ink, #141412)">WIP 上限 2・3 枚</text>
    <line x1="344" y1="76" x2="616" y2="76" stroke="var(--ink, #141412)" stroke-width="2"/>

    <!-- カード (通常) -->
    <g>
      <rect x="48" y="104" width="240" height="72" rx="6" fill="#FFFFFF" stroke="#DCD7BA" stroke-width="1.25"/>
      <text x="64" y="136" font-size="14" fill="var(--fg)">{{カード名}}</text>
      <text x="64" y="160" font-size="12" fill="var(--fg-muted, #6A6A68)">{{補足}}</text>
    </g>

    <!-- カード (上限超過ぶん = 焦点。1 枚だけ) -->
    <g>
      <rect x="360" y="280" width="240" height="72" rx="6"
            fill="rgba(210, 126, 153, 0.14)" stroke="var(--ink, #141412)" stroke-width="2"/>
      <text x="376" y="312" font-size="14" fill="var(--fg)">{{滞留カード名}}</text>
      <text x="376" y="336" font-size="12" fill="var(--fg-muted)">5 週目・上限超過</text>
    </g>

    <!-- 盤面の読む向き (1 本だけ) -->
    <line x1="32" y1="496" x2="928" y2="496"
          stroke="var(--fg-muted)" stroke-width="2" marker-end="url(#f1-arrow)"/>
    <text x="480" y="488" text-anchor="middle" font-size="12" fill="var(--fg-muted)">左から右へ流れる</text>
  </svg>
  <figcaption id="f1-caption" class="srg-diagram__caption">
    <span class="srg-diagram__label">図 n</span>{{40-120 字}}
  </figcaption>
</figure>
```

**チェックリスト**: □ 全列でカード高と縦の間隔が同じか □ カード総数が 9 以下か
□ WIP 上限を明示しているか □ `accent` は超過列とその原因カードの 2 件以下か
□ カード間にコネクタを引いていないか □ 列ごとに面の塗りを変えていないか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/kanban-{input.json,golden.html}`（report 骨格・検査指摘ゼロ）

---

### 11.42 ユーザージャーニーマップ型（User Journey Map）

**フェーズ列 × 行**（行動・感情・接点）の格子で、体験のどこが沈むかを示す。
§11.25 縦タイムラインが「いつ何が起きたか」を語るのに対し、本型は
**「同じ時点で利用者が何をし、どう感じ、どこに触れていたか」を縦に揃えて読ませる**。
列がそろっていることが主張の前提なので、行ごとに列境界をずらさない。

| 判断 | 内容 |
|---|---|
| **Best for** | 離脱箇所の特定、体験の谷と接点の対応づけ、CX 改善の対象選定、部署をまたぐ体験の共有 |
| **使わない場面** | 感情の軸が無く工程だけが主題（→ §11.4 フロー）／時点でなく期間の長さが主題（→ §11.8 ガント）／利用者が 1 人でなく複数属性の比較（→ §11.10 ペルソナ・§11.6 対比） |
| **複雑度上限** | **フェーズ 3-5 列 × 行 3**（行動 / 感情 / 接点）。6 列を超えると 1 セルの日本語が 2 語に痩せる。感情の水準は **5 段以内**（+2 / +1 / 0 / −1 / −2）。`accent` は**谷 1 点とその列の接点セル 1 つ**の計 2 件まで（`diagram-layout-contract.md` §D-2 #3） |
| **必須情報** | 感情行に中立の基準線を引き、その左端に「中立」・上下端に向きの語を 12px で（`満足` / `不満`）、谷の点には根拠数値を点の脇に（`離脱 34%・n=212`）、各フェーズ見出しの下に絶対時点または所要を年を含めて（`2026/03・平均 6 日`）、接点行の各セルに接点の担い手を補足行として書く。基準線と向きが無ければ「沈んでいる」と言えず、根拠数値が無ければ谷が改善対象に値するかを判定できない |
| **推奨配置** | 横帯 |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- 行ラベル列は左 `128`（x = 32-160）。フェーズ列は 4 列なら幅 `192`（境界 160 / 352 / 544 / 736 / 928）
- 行は 行動 `104-176` / 感情 `200-320` / 接点 `336-408`。
  **列境界の縦線は 3 行を貫いて 1 本**にする（行ごとに引き直すと段差が出る）
- 感情行には**中立の基準線**（破線ヘアライン・y = 260）を必ず入れる。
  これが無いと上下が相対値にしか読めず、「沈んでいる」と言えなくなる
- 感情の点は基準線から `±24 / ±44` の 2 段（+2 = 216 / +1 = 232 / 0 = 260 / −1 = 288 / −2 = 304）。
  谷の 1 点だけ半径を `4 → 6` へ上げ、`accent` で塗る
- **推移線は `<polyline>`**（データ線。冒頭の「斜め線禁止の例外」を参照）。
  `<line>` や `<path>` で書き直さない
- 接点行は `paper-2` のセル。焦点の列だけ `accent-tint` + `accent` 枠にして、
  谷と真下で視線がそろうようにする

```html
<!-- フェーズ見出しと、3 行を貫く列境界 -->
<text x="256" y="68" text-anchor="middle" font-size="16" fill="var(--fg)">{{フェーズ1}}</text>
<line x1="160" y1="88" x2="928" y2="88" stroke="#DCD7BA" stroke-width="1.25"/>
<line x1="352" y1="88" x2="352" y2="408" stroke="#DCD7BA" stroke-width="1.25"/>

<!-- 行ラベル -->
<text x="144" y="144" text-anchor="end" font-size="12" fill="var(--fg-muted, #6A6A68)">行動</text>

<!-- 行動のセル -->
<g>
  <rect x="168" y="104" width="176" height="72" rx="6" fill="#FFFFFF" stroke="#DCD7BA" stroke-width="1.25"/>
  <text x="256" y="136" text-anchor="middle" font-size="14" fill="var(--fg)">{{行動}}</text>
  <text x="256" y="160" text-anchor="middle" font-size="12" fill="var(--fg-muted, #6A6A68)">{{補足}}</text>
</g>

<!-- 感情行: 中立の基準線 + 推移線 (polyline) + 各点 -->
<line x1="160" y1="260" x2="928" y2="260" stroke="#DCD7BA" stroke-width="1.25" stroke-dasharray="4 3"/>
<text x="152" y="252" text-anchor="end" font-size="12" fill="var(--fg-muted, #6A6A68)">中立</text>
<polyline points="256,288 448,304 640,232 832,216"
          fill="none" stroke="var(--fg-muted)" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="256" cy="288" r="4" fill="var(--fg-muted)"/>
<circle cx="448" cy="304" r="6" fill="var(--ink, #141412)"/>

<!-- 接点行: 谷の真下だけが焦点 -->
<g>
  <rect x="360" y="336" width="176" height="72" rx="6"
        fill="rgba(210, 126, 153, 0.14)" stroke="var(--ink, #141412)" stroke-width="2"/>
  <text x="448" y="368" text-anchor="middle" font-size="14" fill="var(--fg)">{{接点}}</text>
  <text x="448" y="392" text-anchor="middle" font-size="12" fill="var(--fg-muted)">{{補足}}</text>
</g>
```

**チェックリスト**: □ 列境界が 3 行を貫いて 1 本か □ 中立の基準線があるか
□ 推移線を `<polyline>` で書いたか（`<line>` / `<path>` で書き直していないか）
□ 谷は 1 点だけか □ 谷と焦点の接点セルが同じ列にあるか □ 6 列以上になっていないか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/journey-map-{input.json,golden.html}`（report 骨格・検査指摘ゼロ）

---

### 11.43 ウォーターフォールチャート型（Waterfall / Bridge Chart）

**開始値から終了値までの差を、増減の棒で橋渡しして分解する。**
`chart-types.md` §13.1 縦棒グラフとの違いは、**棒が基線から立たず、直前の累計から立つ**点にある。
「なぜこの数字になったのか」の内訳が主張の本体であるときにだけ選ぶ。
合計の比較が主題なら普通の棒グラフの方が読みやすい。

| 判断 | 内容 |
|---|---|
| **Best for** | 前期→当期の売上分解、予実差の要因分解、コスト増減の内訳、在庫や人員の期首→期末の橋渡し |
| **使わない場面** | 系列どうしの大小比較（→ `chart-types.md` §13.1 縦棒）／構成比（→ §13.3 積み上げ棒・§13.5 円）／時間推移そのもの（→ §13.4 折れ線）／増減の要因が 7 つ以上（本文の表へ移す） |
| **複雑度上限** | **棒 4-8 本**（開始・終了を含む。`diagram-layout-contract.md` §D-2 #1 の型別具体化）。中間の増減は 6 本まで。それ以上は要因をまとめる。`accent` は**着地点の終了棒 1 本のみ**（同 #3） |
| **必須情報** | 値の単位と桁を目盛の最上ラベルの上へ（`百万円`）、基線が 0 であること、0 でないなら切っている旨を基線ラベルへ（`基線 = 80・0 起点ではない`）、開始棒と終了棒の実数値を 16px で・中間棒の増減を符号付き実数値で 14px で棒の外に、期首と期末の絶対時点と集計定義を図の下端 1 行に年を含めて（`2025年度→2026年度・連結・為替影響込み`）書く。単位と 0 起点の別が無ければ棒の高さ差が何倍の差なのか読めず、期首期末の時点が無ければ他資料と突合できない |
| **推奨配置** | 横帯 |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- 1 単位あたりの px は、最大累計が `y = 88` 付近へ収まる値を選び、**4px へ丸める**。
  下の例は 1 単位 2px・基線 `y = 456`（0）・目盛 40 単位ごと（80px）の 5 本
- 棒は 6 本なら幅 `96`・間隔 `48`（x = 72 / 216 / 360 / 504 / 648 / 792）
- **色役割は 3 つだけ**:
  - 開始棒・終了棒（基準の 2 本）: 開始は `paper-2` + `ink` 枠、終了は `accent-tint` + `accent` 枠
  - 増の棒: 同一色相の不透明度 `0.05`
  - 減の棒: 同一色相の不透明度 `0.20`
  増を緑・減を赤にしない。色相を 2 つ増やすと着地点の焦点が埋もれる。
  **符号は値ラベルの `+` / `−` が既に語っている**
- **橋渡し兼累計線は 1 本の `<polyline>`**（データ線。冒頭の「斜め線禁止の例外」を参照）。
  棒と棒の間では水平に走り、棒の上では累計の傾きとして走る。破線・線幅 2（破線の値は下のコード例。
  線種の語彙は閉じていて、正本は `scripts/validate-svg-diagram.py` の `DASH_VOCAB`＝検査は D25。
  **ここへ値を書き写さない**——語彙外の破線は検査で落ちる）
- 値ラベルは棒の**外**（上）に置く。棒の中に入れると、高さ 16px の細い棒で字が収まらない。
  `16px` を使うのは開始と着地の 2 本だけ、中間の増減は `14px`

```html
<!-- 目盛と基線 -->
<line x1="64" y1="216" x2="928" y2="216" stroke="#DCD7BA" stroke-width="1.25"/>
<text x="56" y="220" text-anchor="end" font-size="12" fill="var(--fg-muted)">120</text>
<line x1="64" y1="456" x2="928" y2="456" stroke="var(--fg-muted, #6A6A68)" stroke-width="2"/>

<!-- 開始棒 (基準) -->
<rect x="72" y="216" width="96" height="240" fill="#F8F7F0" stroke="var(--fg)" stroke-width="1.5"/>
<!-- 増の棒 -->
<rect x="216" y="136" width="96" height="80" fill="rgba(67, 67, 108, 0.05)" stroke="var(--fg-muted)" stroke-width="1.5"/>
<!-- 減の棒 (色相は増と同じ・濃度だけが違う) -->
<rect x="504" y="88" width="96" height="32" fill="rgba(67, 67, 108, 0.20)" stroke="var(--fg-muted)" stroke-width="1.5"/>
<!-- 終了棒 (着地点 = 焦点) -->
<rect x="792" y="136" width="96" height="320" fill="rgba(210, 126, 153, 0.14)" stroke="var(--ink, #141412)" stroke-width="2"/>

<!-- 橋渡し兼累計線 (データ線。polyline で描く) -->
<polyline points="168,216 216,216 312,136 360,136 456,88 504,88 600,120 648,120 744,136 792,136"
          fill="none" stroke="var(--fg-muted)" stroke-width="2" stroke-dasharray="12 4"/>

<!-- 値ラベルは棒の外へ -->
<text x="120" y="204" text-anchor="middle" font-size="16" fill="var(--fg)">120</text>
<text x="264" y="124" text-anchor="middle" font-size="14" fill="var(--fg)">+40</text>
<text x="552" y="76" text-anchor="middle" font-size="14" fill="var(--fg)">−16</text>
```

**チェックリスト**: □ 各棒の上端・下端が累計と一致しているか（目分量で読んでも値ラベルと矛盾しないか）
□ 増と減を別の色相で塗り分けていないか □ `accent` は終了棒 1 本だけか
□ 橋渡し線を `<polyline>` で書いたか □ 値ラベルを棒の中に入れていないか
□ 中間の棒が 6 本を超えていないか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/waterfall-{input.json,golden.html}`（slide 骨格・検査指摘ゼロ）

---

### 11.44 ヒートマップ型（Heatmap）

**n×m の格子の濃淡**で、2 つの軸が交わる場所の量を示す。
§11.7 マトリックスが「どの区画に何が入るか」を語るのに対し、本型は
**区画そのものが固定で、そこに載る量だけが動く**。
`d3-integration.md` のインタラクティブ heatmap tpl と役割が違い、
こちらは**印刷とスライドに載る静的な 1 枚**である。

| 判断 | 内容 |
|---|---|
| **Best for** | 曜日 × 時間帯の負荷、機能 × 利用者層の利用率、部門 × 指標の達成度、期間 × 項目の発生件数 |
| **使わない場面** | 量が 2-3 段階しかない（→ §11.32 可否マトリクス）／セルに入るのが量でなく分類（→ §11.7 マトリックス）／軸が 1 本（→ `chart-types.md` §13.2 横棒）／マウス操作で掘る前提（→ `d3-integration.md` の tpl） |
| **複雑度上限** | **セル総数 24（6 列 × 4 行が上限）**。列 8・行 6 を超えないこと。`diagram-layout-contract.md` §D-2 の「密度が語彙である型」（ガント・年表・マトリクス・散布図）と同じ扱いで #1 ノード総数 9 の対象外だが、**24 を超えたセルの日本語ラベルは軸側から読めなくなる**ので、超えたら軸を束ねる。`accent` の**枠**は最濃セル 1 つのみ（同 #3） |
| **必須情報** | 2 軸の名前と並び順の意味を行ラベル列の上と列ラベル行の左に（`曜日（月→日）` / `時間帯（0→23 時・並びは時刻順）`）、セルの数値の単位を凡例の脇に（`件`）、濃さ 5 段それぞれの境界値を凡例の各段の下に数値で（`0 / 8 / 16 / 24 / 32〜`）、集計期間と母数を図の下端 1 行に年を含めて（`2026/01-2026/03・一次受付のみ (n=1,204)`）書く。段の境界値が無ければ「濃い」が何件からなのか読めず、軸の並び順の意味が無ければ読者が勝手に順位軸を発明する |
| **推奨配置** | 方形 |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- 行ラベル列は左 `128`。セルは `120 × 72`、間隔 `8`
  （列 x = 160 / 288 / 416 / 544 / 672 / 800、行 y = 96 / 176 / 256 / 336）
- 角丸は `rx="4"`（小タグ段）。セルの枠は全セル `rule` のヘアライン
- **濃さは 1 色相の不透明度 5 段だけで作る**（`0.05` / `0.14` / `0.20` / `0.30` / `0.50`）。
  値はすべて `NODE_STYLES` の既存段からの引用で、**新しい段を作らない**。
  多色スケール（青→黄→赤）を禁じるのは、色相が変わると読者が「量の順」ではなく
  「種類の違い」を読み始めるためで、**順序を語れるのは同一色相の濃淡だけ**である
- **セルには必ず数値を書く**。濃淡だけに順位を担わせると、印刷・モノクロ・色覚特性で
  順位が消える。数値があれば濃淡は「見つけるための手掛かり」に降格でき、それが正しい役割である
- 焦点は最濃セル 1 つに `accent` の**枠**だけを足す。塗りは濃度段のまま変えない
  （濃度を変えると量が嘘になる）
- 濃さの凡例（5 段・`56 × 24`）を図の下に置き、両端にだけ「少ない / 多い」を添える

> **`accent-tint` の使い方についての例外申告**: `diagram-style-tokens.md` §1 は
> `accent-tint` を「`accent` 枠のノードの塗り。単独の面塗りにしない」と定めている。
> 本型はその濃度段を**連続量のスケール**として枠なしで並べる唯一の型である。
> 成立する理由は 2 つ: (1) 全セルが `rule` のヘアライン枠を持つので「枠の無い accent 面」ではない、
> (2) `accent` の**枠**は最濃セル 1 つにしか付かないので、焦点の件数は §D-2 #3 を守っている。
> この例外は本型に閉じる。他の型で濃度段を面塗りへ流用しない。

```html
<!-- 列ラベル / 行ラベル -->
<text x="220" y="76" text-anchor="middle" font-size="12" fill="var(--fg-muted)">{{列1}}</text>
<text x="144" y="136" text-anchor="end" font-size="12" fill="var(--fg-muted)">{{行1}}</text>

<!-- セル (濃さは 5 段のみ・数値は必ず書く) -->
<rect x="160" y="96" width="120" height="72" rx="4" fill="rgba(210, 126, 153, 0.14)" stroke="#DCD7BA" stroke-width="1.25"/>
<text x="220" y="140" text-anchor="middle" font-size="14" fill="var(--fg)">12</text>

<!-- 最濃セル (焦点。枠だけを accent にし、塗りは濃度段のまま) -->
<rect x="672" y="336" width="120" height="72" rx="4" fill="rgba(210, 126, 153, 0.50)" stroke="var(--ink, #141412)" stroke-width="2"/>
<text x="732" y="380" text-anchor="middle" font-size="14" fill="var(--fg)">38</text>

<!-- 濃さの凡例 (5 段・両端にだけ語を置く) -->
<rect x="160" y="440" width="56" height="24" rx="4" fill="rgba(210, 126, 153, 0.05)" stroke="#DCD7BA" stroke-width="1.25"/>
<rect x="220" y="440" width="56" height="24" rx="4" fill="rgba(210, 126, 153, 0.14)" stroke="#DCD7BA" stroke-width="1.25"/>
<rect x="280" y="440" width="56" height="24" rx="4" fill="rgba(210, 126, 153, 0.20)" stroke="#DCD7BA" stroke-width="1.25"/>
<rect x="340" y="440" width="56" height="24" rx="4" fill="rgba(210, 126, 153, 0.30)" stroke="#DCD7BA" stroke-width="1.25"/>
<rect x="400" y="440" width="56" height="24" rx="4" fill="rgba(210, 126, 153, 0.50)" stroke="#DCD7BA" stroke-width="1.25"/>
<text x="152" y="456" text-anchor="end" font-size="12" fill="var(--fg-muted, #6A6A68)">少ない</text>
<text x="464" y="456" text-anchor="start" font-size="12" fill="var(--fg-muted, #6A6A68)">多い</text>
```

**チェックリスト**: □ セル総数が 24 以下か □ 濃さが 1 色相の 5 段だけで作られているか
□ 全セルに数値が入っているか □ `accent` の枠が最濃セル 1 つだけか
□ 焦点セルの塗りを濃度段から動かしていないか □ 濃さの凡例があるか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/heatmap-{input.json,golden.html}`（slide 骨格・検査指摘ゼロ）

---

## 関連

- 図解 1 枚の契約（幾何・素材・数値） → `diagram-layout-contract.md`
- 色ロールの索引 → `diagram-style-tokens.md`
- 型と経路の対応 → `diagram-type-crosswalk.md`
- 骨格と埋め込み契約 → `assets/diagram-templates/README.md`
- 完成した 1 枚の実例 → `skills/run-slide-report-generate/examples/diagram-goldens/README.md`
