# 図解タイプ: 技術系（手書き経路・SVG2）

**責務**: ER・シーケンス・状態遷移・アーキテクチャ層構成・スイムレーンプロセス・システムコンテキストの、LLM が直接書くための SVG2 テンプレート

**含まれるタイプ**: 11.35-11.40

**前提**: [svg-diagram-primitives.md](svg-diagram-primitives.md) のSVG2プリミティブ、[diagram-style-tokens.md](diagram-style-tokens.md) の色・線・書体、[diagram-layout-contract.md](diagram-layout-contract.md) 第 4 次 update §D-1〜§D-5 を参照

> 本ファイルの 6 型は、決定論経路（`svg-structures.cjs` の `buildEr` / `buildSequence` / `buildState` / `buildArchitecture` / `buildSwimlane` / `buildHighLevel`）にも実装がある。**入力が構造化済みでビルダーの容量に収まるなら決定論経路を優先**し、本ファイルは「ビルダーの語彙では言えないことを 1 枚だけ言いたい」ときの手書き経路として引く。どちらを選ぶかの基準は `skills/ref-diagram-system/references/diagram-type-catalog.md` にある。

**方針**: 6 型とも SVG2 のみで描く。CSS 依存を持たせない（ゴールデン実例は断片単体で検査に通す必要があるため、すべて presentation attribute へ展開する）。本ファイルの CSS ブロックは**クラス定義の意味を示すための参考**であり、実際の出力では属性へ落とす。

**この 6 型に共通する禁止事項**

- **斜線を引かない**。crow's foot・ひし形ゲート・斜めの依存線はすべて禁止で、接続は直交エルボー（`diagram-layout-contract.md` §D-3 原則 1）に統一する
- **等幅書体は技術リテラルにだけ使う**。列名・型名・ポート番号・識別子は等幅、人が読む名前（エンティティ名・サービス名・状態名）は既定書体で組む。`font-family` は `monospace` と書く（`var(--font-mono)` は検査の許容書体表に無い。後述の既知の差分を参照）
- **`font-size` は 16 / 14 / 12 の 3 段まで**（§D-2 #21 の上限 4 段に対し 1 段の余裕を残す）
- **accent は 1 要素のみ**。焦点以外の強調は濃度の差だけで表す（§D-2 #3）
- **注釈は最大 2 件・図の余白のみ**（§D-5）。ノードや線の上へ重ねるくらいなら注釈を捨てる

---

### 11.35 ER 図（Entity Relationship・SVG2）

**列の持ち方そのもの**が議論の対象であるときに選ぶ。
「どのテーブルがあるか」ではなく「**どの列がどこにあるか**」を見せる図なので、
本文がこれから触れない列は載せない。
カーディナリティは crow's foot（三つ又）を使わない。三つ又は必ず斜辺を持ち、
§D-3 原則 1 に反するため、**線の両端へ `1` / `N` のテキストを置く方式を正**とする。

| 判断 | 内容 |
|---|---|
| **Best for** | 状態や区分をどのテーブルが持つかの確認、正規化・非正規化の判断、外部キーの向きの合意 |
| **使わない場面** | テーブル間の呼び出し順序が主題（→ §11.36 シーケンス図）／保管場所の階層が主題（→ §11.38 アーキテクチャ層構成図）／列に触れず箱の関係だけ言いたい（→ §11.40 システムコンテキスト図） |
| **複雑度上限** | エンティティ **6 件**（`svg-structures.cjs` CAPACITY `buildEr` 6 と §D-2 #7 の 8 の厳しい方）、1 エンティティあたりのフィールド **6 行**（同 #8）、関係線 **5 本**。960 幅にカード 3 枚が上限なので、6 件を置くなら 2 段に折る |
| **必須情報** | 各エンティティの主キー（列名の右に `PK`。複合キーなら構成列すべてに付ける）、外部キーの参照先（`FK` 止まりにせず `FK→受注.受注番号` と実体名と列名まで）、列の型（`enum` は値域を括弧で並べる。`status : enum (下書/確定/出荷済/取消)`）、カーディナリティ（線の両端の `1` / `N`）、対応の必須性（両端のカーディナリティの 12px 下に `必須` / `任意`）、弱実体の別（エンティティ名の右に `(識別)`）。外部キー列を持つエンティティには必ず関係線を引き、線を持たないエンティティは図から外す。これが欠けると、読者はどの行が一意に決まるか、どちらの実体を先に作れるか、参照先が消えたとき何が壊れるかを判断できない |
| **推奨配置** | 方形（report 骨格・`data-figure-width="text"`） |

**幾何**（`viewBox="0 0 960 360"`・すべて 4px グリッド）

- カードは幅 **256** / 見出し帯 **44** / フィールド行 **32**、列間 **48**（x = 48 / 352 / 656）
- 角丸は `rx="6"`（カード段。`diagram-style-tokens.md` §5）
- 見出し帯は**同じ座標にもう 1 枚 rect を重ねて塗る**。帯の下辺に `#DCD7BA` の 1.25 の
  区切り線を引き、帯と列の領域を分ける
- フィールドは左揃え（x = カード左 + 16）。中央揃えにすると列名の頭が揃わず読めない
- 関係線は**カードより先に書いて下へ潜らせる**。線はカードの縦中央（y = 200）で水平に引く
- カーディナリティは線の両端から 6px 内側、線の 12px 上に置く（左は始点揃え、右は終点揃え）
- 焦点のエンティティだけ枠を `accent` の 2、見出し帯を `accent-tint` にする。
  枠と帯の両方を変えることで、フィールドの塗りを変えずに 1 件だけ立たせられる

```css
/* エンティティ枠 */
.er-card       { fill: #FFFFFF; stroke: var(--fg, #43436c); stroke-width: 1.5; }
.er-card-head  { fill: rgba(67, 67, 108, 0.05); }
.er-card-rule  { stroke: #DCD7BA; stroke-width: 1.25; }

/* 焦点（1 件だけ） */
.er-card--focal      { fill: #FFFFFF; stroke: var(--sakura-pink, #D27E99); stroke-width: 2; }
.er-card-head--focal { fill: rgba(210, 126, 153, 0.14); }

/* 文字（エンティティ名は既定書体、列と型は等幅） */
.er-name   { font-size: 16px; fill: var(--fg, #43436c); }
.er-field  { font-size: 14px; font-family: monospace; fill: var(--fuji-gray, #8a8980); }

/* 関係とカーディナリティ */
.er-rel    { stroke: var(--fg-dim, #54546d); stroke-width: 2; }
.er-card-n { font-size: 12px; fill: var(--fuji-gray, #8a8980); }
```

```html
<!-- 骨格: assets/diagram-templates/diagram-skeleton-report.html
     <defs> のマーカー 3 種は骨格のものをそのまま使う（ER では矢じりを使わない） -->
<figure class="srg-diagram srg-diagram--report" data-diagram-id="f1" data-figure-width="text">
  <svg viewBox="0 0 960 360" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-labelledby="f1-caption">

    <!-- 関係線（先に引いてカードの下へ潜らせる） -->
    <line class="er-rel" x1="304" y1="200" x2="352" y2="200" />
    <text class="er-card-n" x="310" y="188">1</text>
    <text class="er-card-n" x="346" y="188" text-anchor="end">N</text>

    <!-- エンティティ（x = 48 / 352 / 656 の 3 枚まで） -->
    <rect class="er-card"      x="48" y="88" width="256" height="184" rx="6" />
    <rect class="er-card-head" x="48" y="88" width="256" height="44"  rx="6" />
    <line class="er-card-rule" x1="48" y1="132" x2="304" y2="132" />
    <text class="er-name" x="176" y="118" text-anchor="middle">{{エンティティ名}}</text>
    <text class="er-field" x="64" y="160">{{列1}} : {{型}}</text>
    <text class="er-field" x="64" y="192">{{列2}} : {{型}}</text>
    <text class="er-field" x="64" y="224">{{列3}} : {{型}}</text>
    <text class="er-field" x="64" y="256">{{列4}} : {{型}}</text>

    <!-- 焦点のエンティティ（枠と見出し帯だけを差し替える・1 件のみ） -->
    <rect class="er-card--focal"      x="352" y="88" width="256" height="184" rx="6" />
    <rect class="er-card-head--focal" x="352" y="88" width="256" height="44"  rx="6" />

    <!-- 注釈（余白のみ・矢じりなし・最大 2） -->
    <text x="912" y="320" text-anchor="end" font-size="12" font-style="italic"
          fill="var(--fuji-gray,#8a8980)">{{図では言えない一言}}</text>
    <path d="M 856 312 Q 828 296 792 280" fill="none"
          stroke="var(--fuji-gray,#8a8980)" stroke-width="1.25" stroke-dasharray="4 3" />
    <circle cx="792" cy="280" r="2" fill="var(--fuji-gray,#8a8980)" />
  </svg>
  <figcaption id="f1-caption" class="srg-diagram__caption">
    <span class="srg-diagram__label">図 1</span>{{読む順と結論}}
  </figcaption>
</figure>
```

**チェックリスト**: □ crow's foot を使っていないか（`1` / `N` のテキストか）
□ エンティティ 6 件・フィールド 6 行を超えていないか □ 本文が触れない列を載せていないか
□ 列と型が等幅で、エンティティ名が既定書体か □ 関係線がカードの下へ潜っているか
□ `accent` は 1 エンティティだけか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/er-{input.json,golden.html}`（report 骨格・検査指摘ゼロ）

### 11.36 シーケンス図（Sequence・SVG2）

**待たせている区間**を見せる図である。誰と誰が話すかではなく、
「**どの区間が時間を食っているか**」が主張の本体であるときにだけ選ぶ。
だから焦点はアクター（列）ではなく**活性化帯（縦の帯）1 本**に置く。
実線は相手の返事を待つ呼び出し、破線は待たない（戻り・非同期）という
2 語彙だけで書き、3 つ目の線種を作らない。

| 判断 | 内容 |
|---|---|
| **Best for** | 待ち時間の内訳、同期と非同期の境界、往復回数が多すぎる箇所の特定、障害時の順序の説明 |
| **使わない場面** | 順序ではなく状態の移り変わりが主題（→ §11.37 状態遷移図）／担当者間の受け渡し回数が主題（→ §11.39 スイムレーンプロセス図）／登場人物の関係だけ言いたい（→ §11.40 システムコンテキスト図） |
| **複雑度上限** | アクター **5 列**（CAPACITY `buildSequence` 5）、メッセージ **8 本**（§D-2 #2 の 12 に対し、行間 56 で 540 高に収まる本数が先に効く）、活性化帯の焦点 **1 本**、`alt` / `loop` の枠は**使わない**（枠を入れるなら図を 2 枚に割る） |
| **必須情報** | 同期と非同期の別（実線＝返事を待つ / 破線＝待たない の対応を図の余白へ 12px の 1 行で置く。線の形だけに委ねない）、戻り値（破線のラベルに何が返るかを書く）、所要時間または SLA（焦点の活性化帯がかかる区間は `残枠照会 / 1.8s` の形で数値を必ず出す）、失敗したときの行き先（`alt` 枠を使わない規約なので戻りのラベルへ併記する。`残枠を返す / 否認時は受付拒否`）。これが欠けると、読者は待ち時間の内訳を数えられず、どの区間を削れば速くなるか、異常時にどこへ抜けるかを判断できない |
| **推奨配置** | 方形（report 骨格・`data-figure-width="text"`） |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- アクター見出しは幅 **192** / 高さ **64**、列間隔 **224**（x = 48 / 272 / 496 / 720）
- ライフラインは見出しの下端（y = 112）から y = 424 まで。`#DCD7BA` の 1.25 で
  `stroke-dasharray="4 4"`。**ライフラインだけは破線でよい**（メッセージの破線とは
  太さで区別が付く）
- 活性化帯は幅 **8**、ライフラインの中心から左へ 4 ずらす。通常は白 + `muted` の 1.25、
  焦点だけ `accent-tint` + `accent` の 2
- メッセージは y = 160 から **56 ずつ**下げる。ラベルは線の 10px 上に置く
- 戻りと非同期だけ `stroke-dasharray="5 4"`。外部連携のメッセージは `link` の色と
  `-arrow-link` のマーカーにする
- ラベルが他の線と交差する位置に来たら、**先に `#FFFFFF` の矩形マスクを敷いてから**文字を置く

```css
.sq-head      { fill: #FFFFFF; stroke: var(--fg, #43436c); stroke-width: 1.5; }
.sq-name      { font-size: 16px; fill: var(--fg, #43436c); }
.sq-lifeline  { stroke: #DCD7BA; stroke-width: 1.25; stroke-dasharray: 4 4; }

.sq-act       { fill: #FFFFFF; stroke: var(--fg-dim, #54546d); stroke-width: 1.25; }
.sq-act--focal{ fill: rgba(210, 126, 153, 0.14); stroke: var(--sakura-pink, #D27E99); stroke-width: 2; }

.sq-msg       { stroke: var(--fg-dim, #54546d); stroke-width: 2; }
.sq-msg--soft { stroke: var(--fg-dim, #54546d); stroke-width: 2; stroke-dasharray: 5 4; }
.sq-msg--link { stroke: var(--wave-blue, #7E9CD8); stroke-width: 2; stroke-dasharray: 5 4; }
.sq-label     { font-size: 14px; fill: var(--fg, #43436c); }
.sq-mask      { fill: #FFFFFF; }
```

```html
<!-- 骨格: assets/diagram-templates/diagram-skeleton-report.html -->
<figure class="srg-diagram srg-diagram--report" data-diagram-id="f2" data-figure-width="text">
  <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-labelledby="f2-caption">

    <!-- アクター見出しとライフライン（x = 48 / 272 / 496 / 720） -->
    <rect class="sq-head" x="48" y="48" width="192" height="64" rx="6" />
    <text class="sq-name" x="144" y="86" text-anchor="middle">{{アクター1}}</text>
    <line class="sq-lifeline" x1="144" y1="112" x2="144" y2="424" />

    <!-- 活性化帯（通常） -->
    <rect class="sq-act" x="140" y="152" width="8" height="240" />
    <!-- 活性化帯（焦点・1 本のみ） -->
    <rect class="sq-act--focal" x="588" y="208" width="8" height="72" />

    <!-- メッセージ（y = 160 から 56 ずつ・実線は返事を待つ呼び出し） -->
    <line class="sq-msg" x1="148" y1="160" x2="364" y2="160" marker-end="url(#f2-arrow)" />
    <text class="sq-label" x="256" y="150" text-anchor="middle">{{呼び出し}}</text>

    <!-- 戻り（破線・待たない） -->
    <line class="sq-msg--soft" x1="588" y1="272" x2="372" y2="272" marker-end="url(#f2-arrow)" />
    <text class="sq-label" x="480" y="262" text-anchor="middle">{{戻り値}}</text>

    <!-- 非同期・外部連携（link 色 + マスク） -->
    <rect class="sq-mask" x="536" y="304" width="120" height="20" />
    <line class="sq-msg--link" x1="372" y1="328" x2="812" y2="328" marker-end="url(#f2-arrow-link)" />
    <text class="sq-label" x="592" y="318" text-anchor="middle">{{非同期の通知}}</text>

    <!-- 注釈（余白のみ・最大 2） -->
    <text x="912" y="32" text-anchor="end" font-size="12" font-style="italic"
          fill="var(--fuji-gray,#8a8980)">{{図では言えない一言}}</text>
    <path d="M 704 36 Q 700 56 696 70" fill="none"
          stroke="var(--fuji-gray,#8a8980)" stroke-width="1.25" stroke-dasharray="4 3" />
    <circle cx="696" cy="72" r="2" fill="var(--fuji-gray,#8a8980)" />
  </svg>
  <figcaption id="f2-caption" class="srg-diagram__caption">
    <span class="srg-diagram__label">図 2</span>{{読む順と結論}}
  </figcaption>
</figure>
```

**チェックリスト**: □ アクター 5 列・メッセージ 8 本を超えていないか
□ 焦点が活性化帯 1 本に置かれているか（アクターを塗っていないか）
□ 線種が実線と破線の 2 語彙に収まっているか □ 交差するラベルにマスクを敷いたか
□ `alt` / `loop` の枠を持ち込んでいないか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/sequence-{input.json,golden.html}`（report 骨格・検査指摘ゼロ）

### 11.37 状態遷移図（State Transition・SVG2）

**その状態にいる間に何が起きないか**を示す図である。
§11.36 シーケンス図が「時間の順序」を語るのに対し、本型は「**滞在**」を語る。
だから状態の箱には名前だけでなく、**その状態での制約を 1 行**添える。
戻りの遷移は状態列の下を直交エルボーで回し、状態の帯を逆走させない。

| 判断 | 内容 |
|---|---|
| **Best for** | 承認フローの滞留箇所、編集可否・公開可否の切り替わり、リトライやタイムアウトの行き先、差し戻しの戻り先の合意 |
| **使わない場面** | 誰が何をするかが主題（→ §11.39 スイムレーンプロセス図）／呼び出しの往復が主題（→ §11.36 シーケンス図）／状態が 2 つしかない（表か本文で足りる） |
| **複雑度上限** | 状態 **6 個**（CAPACITY `buildState` 6 と §D-2 #1 の 9 の厳しい方。ただし 960 幅に横並びできるのは 3 個なので、4 個以上は 2 段に折る）、遷移 **8 本**（同 #2 の 12 より先に可読性が切れる）、**戻り辺は 1 本**（2 本目を引きたくなったら図を割る） |
| **必須情報** | 初期状態（塗りつぶし円）と終了状態（二重丸。複数あるなら全部描く）、遷移の契機とガード条件（ラベルは `契機 [ガード]` 形式へ統一する。`承認 [限度内]`。ガードを持たない遷移に角括弧は付けない）、滞留の上限（人手の判断を待つ状態は「その状態での制約」の 1 行へ、待ち続けたときの期限と行き先を書く。`3 営業日で自動失効 → 却下`）。これが欠けると、読者はどこから読み始めるか、止まった案件が最後にどうなるか、その遷移が起きる条件は何かを判断できない |
| **推奨配置** | 横帯（slide 骨格） |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- 状態は幅 **176** / 高さ **96**、横間隔 **80**（x = 160 / 416 / 672、y = 192）
- 角丸は `rx="8"`（コンテナ段）。状態名は 16px で y = 236、制約の 1 行は 12px で y = 264
- **開始記号は塗りつぶしの円 `r="12"`**、**終了記号は二重丸 `r="16"` + `r="8"`**。
  どちらも状態ではないので名前を中に入れず、`soft` の 12px を上に添える
- 遷移は状態の縦中央（y = 240）で水平に引く。契機ラベルは線の 10px 上、
  線分の中央に `text-anchor="middle"` で置く
- 戻りの遷移は `M x1 288 V 368 H x2 V 292` の直交エルボーで**状態列の下**を回す。
  y = 368 は状態下端（288）から 80 下で、注釈やキャプションと干渉しない
- 戻りの契機ラベルは経路を跨ぐので、**`#FFFFFF` のマスク矩形を先に敷く**

```css
.st-node       { fill: #FFFFFF; stroke: var(--fg, #43436c); stroke-width: 1.5; }
.st-node--focal{ fill: rgba(210, 126, 153, 0.14); stroke: var(--sakura-pink, #D27E99); stroke-width: 2; }
.st-name       { font-size: 16px; fill: var(--fg, #43436c); }
.st-constraint { font-size: 12px; fill: var(--fg-dim, #54546d); }

.st-terminal-in  { fill: var(--fg, #43436c); }
.st-terminal-out { fill: #FFFFFF; stroke: var(--fg, #43436c); stroke-width: 1.5; }
.st-terminal-cap { font-size: 12px; fill: var(--fuji-gray, #8a8980); }

.st-edge  { fill: none; stroke: var(--fg-dim, #54546d); stroke-width: 2; }
.st-label { font-size: 14px; fill: var(--fg, #43436c); }
.st-mask  { fill: #FFFFFF; }
```

```html
<!-- 骨格: assets/diagram-templates/diagram-skeleton-slide.html -->
<figure class="srg-diagram srg-diagram--slide" data-diagram-id="d3">
  <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-labelledby="d3-caption">

    <!-- 開始記号 -->
    <circle class="st-terminal-in" cx="96" cy="240" r="12" />
    <text class="st-terminal-cap" x="96" y="220" text-anchor="middle">開始</text>

    <!-- 遷移（すべて軸に平行・y = 240） -->
    <line class="st-edge" x1="336" y1="240" x2="412" y2="240" marker-end="url(#d3-arrow)" />
    <text class="st-label" x="376" y="230" text-anchor="middle">{{契機}}</text>

    <!-- 戻りの遷移（直交エルボー・状態列の下を回す・1 本まで） -->
    <path class="st-edge" d="M 504 288 V 368 H 248 V 292" marker-end="url(#d3-arrow)" />

    <!-- 状態（x = 160 / 416 / 672） -->
    <rect class="st-node" x="160" y="192" width="176" height="96" rx="8" />
    <text class="st-name"       x="248" y="236" text-anchor="middle">{{状態名}}</text>
    <text class="st-constraint" x="248" y="264" text-anchor="middle">{{この状態での制約}}</text>

    <!-- 焦点の状態（1 つのみ） -->
    <rect class="st-node--focal" x="416" y="192" width="176" height="96" rx="8" />

    <!-- 戻りの契機ラベル（線を跨ぐのでマスクを先に敷く） -->
    <rect class="st-mask" x="344" y="356" width="64" height="20" />
    <text class="st-label" x="376" y="372" text-anchor="middle">{{戻る契機}}</text>

    <!-- 終了記号（二重丸・ここから出る遷移は無い） -->
    <circle class="st-terminal-out" cx="896" cy="240" r="16" />
    <circle class="st-terminal-in"  cx="896" cy="240" r="8" />
    <text class="st-terminal-cap" x="896" y="212" text-anchor="middle">終了</text>
  </svg>
  <figcaption id="d3-caption" class="srg-diagram__caption">{{読む順と結論}}</figcaption>
</figure>
```

**チェックリスト**: □ 状態 6 個・遷移 8 本を超えていないか □ 戻り辺が 1 本に収まっているか
□ 戻り経路が直交エルボーで状態列の下を回っているか
□ 開始が塗りつぶし円・終了が二重丸になっているか
□ 各状態に「その状態での制約」が 1 行あるか □ 跨ぐラベルにマスクを敷いたか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/state-{input.json,golden.html}`（slide 骨格・検査指摘ゼロ）

### 11.38 アーキテクチャ層構成図（Architecture Layers・SVG2）

**依存が一方向であること**を示す図である。構成要素の一覧ではないので、
本文が触れない箱は載せない。決定論経路の `buildArchitecture` が
ゾーン・凡例・容量制御まで持つのに対し、本型はその**手書き簡易版**で、
「層は 3 つ、依存は上から下だけ」に絞った形を正とする。
層帯は**器であってノードではない**ので塗らない（破線の枠だけで表す）。

| 判断 | 内容 |
|---|---|
| **Best for** | 差し替え対象の切り出し、依存の向きの合意、層をまたぐ違反の指摘、責務の置き場所の議論 |
| **使わない場面** | 外部との境界が主題（→ §11.40 システムコンテキスト図）／呼び出し順序が主題（→ §11.36 シーケンス図）／層が 5 つ以上ある（§D-2 #16 の上限。分割するか決定論経路の `buildArchitecture` へ回す） |
| **複雑度上限** | 層 **3-4**（CAPACITY `buildArchitecture` 4 と §D-2 #16 の 5 の厳しい方）、1 層あたりのノード **4**（864 幅に 192 幅の枠が 3-4 枚。`ARCH_NODES_PER_ZONE` 6 より幅が先に効く）、依存線 **8 本**、凡例 **3 項目**（同 #20 の 5 以内） |
| **必須情報** | 層帯の名前は要素の総称ではなくその層の責務で書き（`データ層` ではなく `受注データの永続化と整合の保証`）、依存線には呼び出しの方式を 12px のラベルで添え（`同期 REST` / `非同期 キュー`）、依存が切れたとき止まる範囲を焦点ノードの脇へ 1 行で書く（`ここが落ちると受付から先が止まる`）。塗りの語彙が処理と保管の 2 つあるので凡例は省略できない。依存線を 1 本も持たない箱は載せない（読者には「載せる必要のある箱」と「線を引き忘れた箱」の区別が付かない）。これが欠けると、どの層を差し替えられるか、どの依存が単一障害点かを判断できない |
| **推奨配置** | 方形（report 骨格・`data-figure-width="text"`） |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- 層帯は幅 **864** / 高さ **112**、層間 **32**（y = 64 / 208 / 352）。`fill="none"` +
  `#DCD7BA` の 1.25 + `stroke-dasharray="4 4"`。**器なので塗らない**
- 層名は帯の左内側（x = 64）に 14px。見出し列として左 176 を空ける
- コンポーネントは幅 **192** / 高さ **64**、列間 **32**（x = 224 / 448 / 672）。
  帯の上下に 32 の余白が残る位置（y = 帯 + 32）に置く
- 「処理」は白 + `ink` の 1.5、「保管」は `rgba(67, 67, 108, 0.05)` + `muted` の 1.5。
  **塗りの語彙が 2 つ以上あるなら凡例を必ず置く**（`diagram-layout-contract.md` §1.6）
- 依存線は**垂直線のみ**。帯の間の 32 + 上下の余白（y = 160 → 236 など）に収め、
  逆流する線を 1 本も引かない
- 凡例は図の外側・下端の水平ストリップ（y = 496）。16×16 の `rx="4"` の見本と 12px の
  ラベルを 112 間隔で並べる。**凡例を置いた面には注釈を置かない**（余白が競合する）

```css
.al-band  { fill: none; stroke: #DCD7BA; stroke-width: 1.25; stroke-dasharray: 4 4; }
.al-band-label { font-size: 14px; fill: var(--fg, #43436c); }

.al-node        { fill: #FFFFFF; stroke: var(--fg, #43436c); stroke-width: 1.5; }
.al-node--store { fill: rgba(67, 67, 108, 0.05); stroke: var(--fg-dim, #54546d); stroke-width: 1.5; }
.al-node--focal { fill: rgba(210, 126, 153, 0.14); stroke: var(--sakura-pink, #D27E99); stroke-width: 2; }
.al-name  { font-size: 16px; fill: var(--fg, #43436c); }

.al-dep   { stroke: var(--fg-dim, #54546d); stroke-width: 2; }
.al-legend-label { font-size: 12px; fill: var(--fg-dim, #54546d); }
```

```html
<!-- 骨格: assets/diagram-templates/diagram-skeleton-report.html -->
<figure class="srg-diagram srg-diagram--report" data-diagram-id="f3" data-figure-width="text">
  <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-labelledby="f3-caption">

    <!-- 層帯（y = 64 / 208 / 352・破線の器・塗らない） -->
    <rect class="al-band" x="48" y="64" width="864" height="112" rx="8" />
    <text class="al-band-label" x="64" y="126">{{層1の名前}}</text>

    <!-- 依存（上から下への垂直線のみ・逆流させない） -->
    <line class="al-dep" x1="320" y1="160" x2="320" y2="236" marker-end="url(#f3-arrow)" />

    <!-- コンポーネント（x = 224 / 448 / 672） -->
    <rect class="al-node" x="224" y="96" width="192" height="64" rx="6" />
    <text class="al-name" x="320" y="134" text-anchor="middle">{{処理の名前}}</text>

    <!-- 保管の語彙 -->
    <rect class="al-node--store" x="224" y="384" width="192" height="64" rx="6" />
    <text class="al-name" x="320" y="422" text-anchor="middle">{{保管の名前}}</text>

    <!-- 焦点（1 つのみ） -->
    <rect class="al-node--focal" x="448" y="240" width="192" height="64" rx="6" />

    <!-- 凡例（図の外・下端・3 項目・112 間隔） -->
    <rect class="al-node" x="48" y="496" width="16" height="16" rx="4" />
    <text class="al-legend-label" x="72" y="508">処理</text>
    <rect class="al-node--store" x="160" y="496" width="16" height="16" rx="4" />
    <text class="al-legend-label" x="184" y="508">保管</text>
    <rect class="al-node--focal" x="272" y="496" width="16" height="16" rx="4" />
    <text class="al-legend-label" x="296" y="508">本文が扱う対象</text>
  </svg>
  <figcaption id="f3-caption" class="srg-diagram__caption">
    <span class="srg-diagram__label">図 3</span>{{読む順と結論}}
  </figcaption>
</figure>
```

**チェックリスト**: □ 層 4・1 層 4 ノードを超えていないか □ 層帯を塗っていないか（破線の器か）
□ 依存線がすべて垂直で、逆流する線が 0 本か □ 塗りの語彙が 2 つ以上あるなら凡例があるか
□ 凡例が 3 項目以内で下端のストリップに収まっているか □ 凡例と注釈を同居させていないか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/architecture-layers-{input.json,golden.html}`（report 骨格・検査指摘ゼロ）

### 11.39 スイムレーンプロセス図（Swimlane Process・SVG2）

**帯をまたぐ回数**を数えるための図である。工程の中身ではなく、
「**誰の手を離れて誰かの着手待ちになる回数**」が主張の本体であるときにだけ選ぶ。
決定論経路の `buildSwimlane` の手書き簡易版として、レーン 3・工程列 4 に絞る。
ゲートに**ひし形を使わない**。ひし形は 4 辺すべてが斜辺で §D-3 原則 1 に反するため、
角丸 4 の低い枠 + 分岐ラベルで表す方式を正とする。

| 判断 | 内容 |
|---|---|
| **Best for** | 承認・精算・受発注などの受け渡し回数の可視化、差し戻しの発生源の特定、担当を減らす提案の裏付け |
| **使わない場面** | 担当者が 1 人（→ 単純なフロー図で足りる）／状態の滞在が主題（→ §11.37 状態遷移図）／システム間の呼び出しが主題（→ §11.36 シーケンス図） |
| **複雑度上限** | レーン **4**（CAPACITY `buildSwimlane` 4 と §D-2 #5 の 5 の厳しい方）、1 レーンあたりの工程 **4**（`SWIM_STEPS` 4 と同 #6 の 6 の厳しい方）、**ゲートは 1 箇所**、戻り線 **1 本** |
| **必須情報** | レーン名は担当（部署または役割）で書き、レーンを跨ぐ線には渡す成果物を 12px で添える（`渡す` ではなく `申請書 + 見積 3 社分`）。ゲートの問いは判断の閾値まで書き（`基準内か` ではなく `5 万円以内か`）、分岐の全枝にラベル（`はい` / `いいえ`）を置く。戻り線には戻る条件と抜ける条件を併記する（`不備あり / 2 回目で上長判断へ`）。工程列の先頭と末尾の見出しは、どこから始まりどこで終わるかが判る名前にする。これが欠けると、どこで案件が止まっているか、誰へ何を渡せば進むかを判断できない |
| **推奨配置** | 全幅（report 骨格・`data-figure-width="bleed"`。レーンは横に伸びるので本文幅では潰れる） |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- レーン帯は幅 **704** / 高さ **112**、レーン間 **16**（y = 136 / 264 / 392）。
  見出し列に左 **160** を空ける（帯は x = 208 から）
- レーン帯は `#FFFFFF` と `#F8F7F0` の**交互 2 段**にする。3 段目の面を作らない
- 工程列の見出しは**レーン帯の外・上端**（y = 112）に 12px の `soft`。
  工程は列であって箱ではないので、見出しに枠を付けない
- 工程枠は幅 **144** / 高さ **64**、列間隔 **176**（列の中心 = 296 / 472 / 648 / 824）
- ゲートは幅 **144** / 高さ **48** / `rx="4"`。工程枠より低くすることで、
  ひし形を使わずに「これは作業ではなく判定」と読ませる
- レーンを跨ぐ受け渡しは `M x 192 H x+16 V 320 H x+28` の直交エルボー。
  分岐ラベル（`はい`）は縦セグメントの右 8px、曲がり角の 8px 上に置く
- 戻り線は**レーン帯の外（下端 y = 528）を回す**。帯の中を逆走させると、
  レーンの読み順（上から下・左から右）が壊れる

```css
.sw-lane      { fill: #FFFFFF; stroke: #DCD7BA; stroke-width: 1.25; }
.sw-lane--alt { fill: #F8F7F0; stroke: #DCD7BA; stroke-width: 1.25; }
.sw-lane-name { font-size: 16px; fill: var(--fg, #43436c); }
.sw-stage     { font-size: 12px; fill: var(--fuji-gray, #8a8980); }

.sw-step      { fill: #FFFFFF; stroke: var(--fg, #43436c); stroke-width: 1.5; }
.sw-gate      { fill: rgba(210, 126, 153, 0.14); stroke: var(--sakura-pink, #D27E99); stroke-width: 2; }
.sw-name      { font-size: 16px; fill: var(--fg, #43436c); }

.sw-flow      { fill: none; stroke: var(--fg-dim, #54546d); stroke-width: 2; }
.sw-label     { font-size: 14px; fill: var(--fg, #43436c); }
```

```html
<!-- 骨格: assets/diagram-templates/diagram-skeleton-report.html -->
<figure class="srg-diagram srg-diagram--report" data-diagram-id="f4" data-figure-width="bleed">
  <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-labelledby="f4-caption">

    <!-- 工程見出し（レーンの外・上端・枠を付けない） -->
    <text class="sw-stage" x="296" y="112" text-anchor="middle">{{工程1}}</text>
    <text class="sw-stage" x="472" y="112" text-anchor="middle">{{工程2}}</text>

    <!-- レーン帯（y = 136 / 264 / 392・交互 2 段） -->
    <rect class="sw-lane" x="208" y="136" width="704" height="112" rx="6" />
    <text class="sw-lane-name" x="48" y="196">{{レーン1}}</text>
    <rect class="sw-lane--alt" x="208" y="264" width="704" height="112" rx="6" />
    <text class="sw-lane-name" x="48" y="324">{{レーン2}}</text>

    <!-- 受け渡し（レーンを跨ぐ線は直交エルボー） -->
    <path class="sw-flow" d="M 368 192 H 384 V 320 H 396" marker-end="url(#f4-arrow)" />
    <line class="sw-flow" x1="544" y1="320" x2="572" y2="320" marker-end="url(#f4-arrow)" />
    <text class="sw-label" x="744" y="312">はい</text>

    <!-- 差し戻し（レーン帯の外・下端を回す・1 本まで） -->
    <path class="sw-flow" d="M 648 344 V 528 H 296 V 228" marker-end="url(#f4-arrow)" />
    <text class="sw-label" x="472" y="516" text-anchor="middle">{{戻る条件}}</text>

    <!-- 工程（列の中心 = 296 / 472 / 648 / 824） -->
    <rect class="sw-step" x="224" y="160" width="144" height="64" rx="6" />
    <text class="sw-name" x="296" y="198" text-anchor="middle">{{工程の作業}}</text>

    <!-- ゲート（ひし形を使わない・高さ 48 の低い枠・1 箇所のみ） -->
    <rect class="sw-gate" x="576" y="296" width="144" height="48" rx="4" />
    <text class="sw-name" x="648" y="326" text-anchor="middle">{{判定の問い}}</text>
  </svg>
  <figcaption id="f4-caption" class="srg-diagram__caption">
    <span class="srg-diagram__label">図 4</span>{{読む順と結論}}
  </figcaption>
</figure>
```

**チェックリスト**: □ レーン 4・1 レーン 4 工程を超えていないか □ ゲートがひし形になっていないか
□ ゲートが 1 箇所・戻り線が 1 本に収まっているか □ 戻り線がレーン帯の外を回っているか
□ レーン帯の塗りが 2 段の交互に収まっているか □ 工程見出しに枠を付けていないか
□ `data-figure-width="bleed"` になっているか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/swimlane-process-{input.json,golden.html}`（report 骨格・検査指摘ゼロ）

### 11.40 システムコンテキスト図（System Context・SVG2）

**変えられる範囲の外側**を示す図である。図の主語は中心の 1 つだけで、
周囲の箱は主語ではなく**文脈**である。だから外部は塗りも枠も最も薄くする。
決定論経路の `buildHighLevel` の手書き版にあたり、
外部を**上下左右の 4 方向にだけ**置くことで、連携線をすべて軸に平行にできる。

| 判断 | 内容 |
|---|---|
| **Best for** | 変更の影響範囲の線引き、外部依存の棚卸し、責任分界点の合意、見積り前のスコープ確認 |
| **使わない場面** | 内部構造が主題（→ §11.38 アーキテクチャ層構成図）／連携の順序やタイミングが主題（→ §11.36 シーケンス図）／外部が 5 者以上（4 方向に収まらない。カテゴリでまとめるか図を割る） |
| **複雑度上限** | 中心システム **1 つ**（2 つ置いた時点でこの型ではない）、外部アクター **4**（CAPACITY `buildHighLevel` 4 と 4 方向配置の制約が一致）、連携線 **4 本**、境界枠 **1 つ** |
| **必須情報** | 中心の 1 行（y = 296）には所有するデータか責務を書く（`受注データと在庫引当を持つ`）。連携ラベルには流れるものと頻度を書き（`与信照会 / 都度`・`売上明細 / 日次 1 回`）、矢じりで向きを示す。線の色 2 語彙（既定色＝人の操作 / `link` 色＝システム連携）の対応は、図の余白へ 12px の 1 行で置く。境界枠のラベルには、内側が自分たちで変えられる範囲であることが判る名前を書く。これが欠けると、どの外部が止まったとき何が止まるか、見積りの対象がどこまでかを判断できない |
| **推奨配置** | 方形（slide 骨格） |

**幾何**（`viewBox="0 0 960 540"`・すべて 4px グリッド）

- 中心は幅 **224** / 高さ **96**（x = 368, y = 224）。名前 16px（y = 268）と
  「何を持っているか」の 1 行 12px（y = 296）を入れる
- 責任境界は幅 **288** / 高さ **160**（x = 336, y = 192）で中心の 16 外側。
  `rgba(210, 126, 153, 0.05)` + `rgba(210, 126, 153, 0.50)` の 1.5 + `stroke-dasharray="4 4"`。
  **境界は器なのでノードとして数えない**。ラベルは枠の左上外側（y = 184）に 12px の `soft`
- 外部アクターは幅 **176** / 高さ **80**。上 (392, 64) / 下 (392, 400) / 左 (64, 232) /
  右 (720, 232) の 4 箇所のみ。`rgba(67, 67, 108, 0.03)` + `rgba(67, 67, 108, 0.30)` の 1.5
  と、**面も枠も最も薄い段**にする（自分の管理外であることを濃度で言う）
- 連携線は上下が垂直、左右が水平。**人の操作は既定色**、**外部システムとの連携は
  `link` の色 + `-arrow-link`** と、線の色 2 語彙で「人か機械か」を分ける
- 連携ラベルは 12px。縦の線は線の右 12px、横の線は線の 12px 上に中央揃えで置く
- 注釈は境界の外を指す 1 件に限る。リーダーは `Q` の曲線で、必ず余白を通す

```css
.sc-boundary  { fill: rgba(210, 126, 153, 0.05); stroke: rgba(210, 126, 153, 0.50);
                stroke-width: 1.5; stroke-dasharray: 4 4; }
.sc-boundary-label { font-size: 12px; fill: var(--fuji-gray, #8a8980); }

.sc-core      { fill: rgba(210, 126, 153, 0.14); stroke: var(--sakura-pink, #D27E99); stroke-width: 2; }
.sc-core-name { font-size: 16px; fill: var(--fg, #43436c); }
.sc-core-sub  { font-size: 12px; fill: var(--fg-dim, #54546d); }

.sc-external  { fill: rgba(67, 67, 108, 0.03); stroke: rgba(67, 67, 108, 0.30); stroke-width: 1.5; }
.sc-name      { font-size: 16px; fill: var(--fg, #43436c); }

.sc-link      { stroke: var(--fg-dim, #54546d); stroke-width: 2; }
.sc-link--sys { stroke: var(--wave-blue, #7E9CD8); stroke-width: 2; }
.sc-label     { font-size: 12px; fill: var(--fg, #43436c); }
```

```html
<!-- 骨格: assets/diagram-templates/diagram-skeleton-slide.html -->
<figure class="srg-diagram srg-diagram--slide" data-diagram-id="d4">
  <svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-labelledby="d4-caption">

    <!-- 責任境界（器であってノードではない） -->
    <rect class="sc-boundary" x="336" y="192" width="288" height="160" rx="8" />
    <text class="sc-boundary-label" x="344" y="184">{{変えられる範囲の名前}}</text>

    <!-- 連携（上下左右の 4 方向のみ・すべて軸に平行） -->
    <line class="sc-link" x1="480" y1="144" x2="480" y2="220" marker-end="url(#d4-arrow)" />
    <text class="sc-label" x="492" y="188">{{人の操作}}</text>
    <line class="sc-link--sys" x1="592" y1="272" x2="712" y2="272" marker-end="url(#d4-arrow-link)" />
    <text class="sc-label" x="660" y="260" text-anchor="middle">{{システム連携}}</text>

    <!-- 中心システム（図の主語・1 つだけ） -->
    <rect class="sc-core" x="368" y="224" width="224" height="96" rx="8" />
    <text class="sc-core-name" x="480" y="268" text-anchor="middle">{{中心システム}}</text>
    <text class="sc-core-sub"  x="480" y="296" text-anchor="middle">{{何を持っているか}}</text>

    <!-- 外部アクター（上 / 下 / 左 / 右の 4 箇所・最も薄い段） -->
    <rect class="sc-external" x="392" y="64"  width="176" height="80" rx="6" />
    <text class="sc-name" x="480" y="112" text-anchor="middle">{{外部1}}</text>
    <rect class="sc-external" x="720" y="232" width="176" height="80" rx="6" />
    <text class="sc-name" x="808" y="280" text-anchor="middle">{{外部2}}</text>

    <!-- 注釈（余白のみ・1 件） -->
    <text x="912" y="512" text-anchor="end" font-size="12" font-style="italic"
          fill="var(--fuji-gray,#8a8980)">{{図では言えない一言}}</text>
    <path d="M 856 500 Q 760 456 632 358" fill="none"
          stroke="var(--fuji-gray,#8a8980)" stroke-width="1.25" stroke-dasharray="4 3" />
    <circle cx="628" cy="356" r="2" fill="var(--fuji-gray,#8a8980)" />
  </svg>
  <figcaption id="d4-caption" class="srg-diagram__caption">{{読む順と結論}}</figcaption>
</figure>
```

**チェックリスト**: □ 中心が 1 つだけか □ 外部が 4 者以内で上下左右に置かれているか
□ 連携線がすべて軸に平行か □ 外部の面と枠が最も薄い段か（中心より目立っていないか）
□ 境界枠をノードとして数えていないか □ 線の色が「人 / 機械」の 2 語彙に収まっているか

ゴールデン実例: `skills/run-slide-report-generate/examples/diagram-goldens/system-context-{input.json,golden.html}`（slide 骨格・検査指摘ゼロ）

---

## 既知の差分（節と検査がぶつかる箇所）

`diagram-style-tokens.md` §6 は等幅書体に `var(--font-mono)` を指定するが、
`scripts/validate-svg-diagram.py` の D13 は `svg-kit.cjs` から抽出した実書体名しか
許容しないため、`var(--font-mono)` は warning になり `--strict` で落ちる。
**本ファイルおよびゴールデン実例では総称名 `monospace` を書く**。
`skills/run-slide-report-generate/examples/diagram-goldens/README.md` の
「節と検査がぶつかったら検査へ寄せる」に従った措置で、検査側が
`var(--font-*)` を解決できるようになれば §6 の記法へ戻す。
