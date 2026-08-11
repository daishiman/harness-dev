# 図種カタログ — 実在ビルダー <!-- count: svgBuilder -->38 種

> 対象は `vendor/scripts/svg-builder.cjs`（<!-- count: svgBuilderCore -->27 種）と `vendor/scripts/svg-structures.cjs`（<!-- count: svgBuilderStruct -->10 種）に
> **実在する** ビルダーのみ。ここは「どれを選ぶか」の索引であって、容量・色・寸法の正本ではない。
>
> **ビルダー以外の経路も含めた全体像** → `references/diagram-type-crosswalk.md`（plugin root）。
> 決定論ビルダー <!-- count: svgBuilder -->38 種・CSS 型 <!-- count: cssDiagramType -->44 種・slide テンプレート <!-- count: slideTemplate -->128 本・参考体系 27 型の対応表と、
> 「決定論 / テンプレート穴埋め / 手書き」の経路選択がそこにある。本ファイルに載っていない図を
> 描くとき（＝ビルダーが存在しない型）は、まず crosswalk で経路を決めてから戻ってくる。

## 0. 各項目の読み方

- **容量**: 上限値は書かない。`svg-builder.cjs` の `CAPACITY[<ビルダー名>]` を見る。
  第 2 引数も配列を取る型は `CAPACITY_ARGS`、入れ子を持つ構造図は
  `svg-structures.cjs` の `NESTED_CAPACITY` が正本。
- **決定表**: `schemas/visual-derivation-table.json` の行 ID。
  `render-report.js` の `DERIVED_BUILDERS` に登録されたビルダーだけが本文から自動導出される。
  「行なし」の型は `section.visual.kind` の**明示指定でのみ使う**（`visual.rationale` が必須）。
- **入口**: report 側は `render-report.js` の `VARIANT_SINGLE_ARG` /
  `VARIANT_SINGLE_ARG_STRUCT` / `renderSvgVisual` の個別分岐、
  slide 側は `render-slide.cjs` の `slideType` 分岐。両方に無い型は
  `svg-builder.cjs` を直接 require したときだけ描ける。
- **日本語ラベル**: 幅が「等分割で固定」か「内容から伸ばせる」かだけを書く。
  詰まったときの吸収先は `label-japanese.md` の 3 分類へ。

---

## 1. 決定表の行に紐づく型（7 種）

本文から自動で選ばれうるのはこの 7 種だけ。それ以外は全て明示指定。

### buildBarChart — variant なし（`kind: 'bar'`）
- 容量: `CAPACITY.buildBarChart`
- 決定表: **R02**（stat-tile が 2 件以上・値が全て数値）
- 選ぶとき: 同一尺度の量を並べて**大小そのもの**を読ませたいとき。
- 選ばないとき: 単位が混ざるとき（棒の長さが比較にならない）、
  時間推移を見せたいとき（`buildLineChart`）、構成比を見せたいとき（`buildPieChart`）。
- 日本語ラベル: 軸ラベルは棒の割当幅に縛られる固定幅側。件数が増えるほど 1 本あたりが痩せる。
- 注意: `variant` enum（`schemas/report-structure.schema.json` の `$defs/svgSpec`）に `bar` は無い。
  R02 は enum を経由せず `kind` で描かれる経路である。

### buildVerticalTimeline — variant `timeline` / `roadmap`
- 容量: `CAPACITY.buildVerticalTimeline`
- 決定表: **R03**（表の見出しに開始／終了に相当する語がある）
- 選ぶとき: 出来事に**日付という外部の順序**があり、順序が意味を持つとき。
- 選ばないとき: 順序が手順に過ぎないとき（`buildChevron` / `buildVerticalFlow`）、
  期間の長短を比べたいとき（`buildGantt`）。
- 日本語ラベル: 日付と本文を連結して幅制限つきで折り返す（`kit.wrapText` を `ellipsis: false` で使う）
  ので、内容から伸ばせない固定幅側。長い出来事名は行数が増える。

### buildNeutralComparison — variant `comparison`（`render-report.js` 固有）
- 容量: `NEUTRAL_COMPARISON_MAX_ITEMS`（決定表 R04 の `capacity` と同値・定義は `render-report.js`）
- 決定表: **R04**（見出しがちょうど 2 列の表）
- 選ぶとき: 2 つの選択肢・案・状態を**対等に**並べたいとき。
- 選ばないとき: 一方が改善後で優劣を示したいとき（`buildVs`。ただし善悪の色が固定で付く）、
  3 列以上のとき（`buildItState` / 本文の表のまま）。
- 日本語ラベル: 列幅が固定なので、上限字数を超えた項目があれば**図ごと作らない**（`null` を返す）。
  切り詰めない契約（`references/diagram-layout-contract.md` §3）をビルダー内で守っている数少ない例。
- 例外: 唯一 `CANVAS` を経由せず自前の幅・高さを持つ（SKILL.md 不変条件 6 の既知例外）。

### buildSwimlane — variant `swimlane`
- 容量: `CAPACITY.buildSwimlane` + `NESTED_CAPACITY.buildSwimlane`（レーン内の工程数）
- 決定表: **R05**（見出しに担当・部門に相当する語がある表）
- 選ぶとき: 「誰が」と「いつ」の 2 軸が同時に効き、**受け渡し**が論点のとき。
- 選ばないとき: 担当が 1 つしかないとき（ただの手順なので `buildChevron`）、
  レーン間の線が交差しないとき（レーンを描く意味がない）。
- 日本語ラベル: `kit.laneLayout` の格子セルなので完全に固定幅。レーン見出し幅も固定。

### buildChevron — variant `chevron`
- 容量: `CAPACITY.buildChevron`
- 決定表: **R06**（順序つきリスト）/ **R08**（完了状態が混在しないタスクリスト）
- 選ぶとき: 一方向に進み、**戻らない**手順のとき。矢羽根の形が「後戻りしない」を語る。
- 選ばないとき: 循環するとき（`buildCycle`）、分岐があるとき（`buildHierarchy` / `buildDataFlow`）、
  各段に説明文を添えたいとき（矢羽根に入らないので `buildVerticalFlow`）。
- 日本語ラベル: 横方向の等分割。件数が増えるほど 1 段が狭くなる典型的な固定幅側。

### buildValueStack — variant `value-stack`
- 容量: `CAPACITY.buildValueStack`
- 決定表: **R09**（定義リスト）/ **R10**（箇条書き 少数）
- 選ぶとき: 下から積み上がる依存・土台の関係を見せたいとき。
- 選ばないとき: 並列で優劣のない列挙のとき（積層は上下差を主張してしまう）。
- 実装: `buildPyramid` へそのまま委譲する。先頭項目を土台へ回す反転は**しない**
  （反転すると図の読み順が本文の並びと逆になり突き合わせられなくなるため）。
- 日本語ラベル: 段の高さ・幅とも固定。`buildPyramid` と同じ制約を受ける。

### buildVerticalFlow — variant `stepper`
- 容量: `CAPACITY.buildVerticalFlow`
- 決定表: **R07**（完了状態が混在するタスクリスト・`connector: true`）/ **R11**（箇条書き 多数・
  `connector: false`）/ **R12**（段落が複数）/ **R13**（段落のみで本文が空）
- 選ぶとき: 段ごとに 1 行を超える説明が要るとき。縦に積むので幅を説明へ回せる。
- 選ばないとき: 順序が無いとき（`connector: false` でも縦積みは順序を示唆する）。
- 日本語ラベル: カード幅は固定（`kit.wrapText(t, cardW - 32, 18)`）だが**高さが伸びる**ので、
  行数で吸収できる数少ない型。長い日本語を載せたいときの第一候補。
- 分岐: 決定表は同じビルダーへ `builderOptions.connector` の真偽で 2 つの見え方を作り分ける。

---

## 2. `svg-builder.cjs` の残り（22 種・全て明示指定）

### buildHorizontalFlow — variant `flow`
- 容量: `CAPACITY.buildHorizontalFlow` / 決定表: 行なし
- 選ぶとき: 段数が少なく、左から右へ読ませたいとき。段ごとに補足説明を持てる。
- 選ばないとき: 段数が多いとき（横幅が尽きる → `buildSnake` か `buildVerticalFlow`）。
- 日本語ラベル: `kit.distributeTrack` + `evenWeights` の等分割なので固定幅。
  補足文は `wrapText(..., { ellipsis: false })` で折り返す（切り詰めない）。

### buildCycle — variant `cycle`
- 容量: `CAPACITY.buildCycle` / 決定表: 行なし
- 選ぶとき: 終わりが始まりへ戻る反復のとき（PDCA 等）。
- 選ばないとき: 実際には戻らない手順のとき（円にすると誤読される → `buildChevron`）。
- 日本語ラベル: 円周上の固定幅。中央の見出し・説明は `kit.wrapText` で折り返せる。

### buildPyramid — variant `pyramid`
- 容量: `CAPACITY.buildPyramid` / 決定表: 行なし（`buildValueStack` 経由でのみ R09/R10）
- 選ぶとき: 上に行くほど**数が少なく価値が高い**関係のとき。
- 選ばないとき: 単なる階層構造のとき（`buildHierarchy`）、積層の土台関係のとき（`buildValueStack`）。
- 日本語ラベル: 上段ほど幅が狭い。最上段に長い語を置くと真っ先に破綻する。

### buildHierarchy — variant `tree` / `org`
- 容量: `CAPACITY.buildHierarchy` / 決定表: 行なし
- 選ぶとき: 親子の従属関係、組織図、分類の入れ子。
- 選ばないとき: 横断的な参照があるとき（木で描けない → `buildArchitecture` / `buildMindmap`）。
- 日本語ラベル: 階層ごとに横等分割。深い階層ほど 1 ノードが狭い。

### buildPieChart — variant なし（slide `chart-pie`）
- 容量: `CAPACITY.buildPieChart` / 決定表: 行なし
- 選ぶとき: 全体に対する構成比で、しかも**1 つの支配的な扇形**を読ませたいとき。
- 選ばないとき: 項目が近い値で並ぶとき（角度差が読めない → `buildBarChart`）。
- 日本語ラベル: 扇外の引出し位置に載る。長いラベルは隣と衝突しやすい。

### buildClockPie — variant なし
- 容量: `CAPACITY.buildClockPie` / 決定表: 行なし
- 実装: `buildPieChart` へ委譲する時計回り表現。
- 入口: `render-report.js` にも `render-slide.cjs` にも分岐が**無い**。
  `svg-builder.cjs` を直接 require したときだけ到達する。
- 日本語ラベル: `kit.measureText` で実測した幅の吹き出しを置くので、内容から伸ばせる側。

### buildConcentric — variant `concentric`
- 容量: `CAPACITY.buildConcentric` / 決定表: 行なし
- 選ぶとき: 内側が外側に**含まれる**入れ子（コア↔周辺、影響範囲）。
- 選ばないとき: 並列の分類のとき（同心円は包含を主張する）。
- 日本語ラベル: 各リング帯の高さに縛られる固定幅。

### buildVenn — variant `venn`
- 容量: `CAPACITY.buildVenn`（円 2-3 個の幾何そのものが上限）/ 決定表: 行なし
- 選ぶとき: 集合の**重なり**そのものが論点のとき。
- 選ばないとき: 重なりを説明しないとき（ただの 3 分類なら `buildMatrix` か列挙）。
- 日本語ラベル: 交差領域が最も狭い。ここへ長い語を置くと必ず破綻する。

### buildMatrix — variant `matrix`
- 容量: `CAPACITY.buildMatrix`（2×2 固定）/ 決定表: 行なし
- 選ぶとき: 独立した 2 軸で 4 象限に分類できるとき。
- 選ばないとき: 軸が独立でないとき、5 分類以上あるとき。
- 日本語ラベル: 象限は等分割の固定幅。
- 設計注記: v7.7.0 で象限ごとの系列色ベタ塗り + 白抜き文字をやめ、
  `kit.NODE_STYLES`（白地 + 罫 + 焦点 1 点）へ寄せた。
  4 象限が等しく強い面だと「どこから読むか」が読者任せになるため。

### buildFunnel — variant `funnel`
- 容量: `CAPACITY.buildFunnel` / 決定表: 行なし
- 選ぶとき: 段を下るほど**絞られる**量の減衰があるとき。
- 選ばないとき: 減衰しない手順のとき（幅の変化が嘘になる → `buildChevron`）。
- 日本語ラベル: 下段ほど幅が狭い固定幅。
- 設計注記: 同じく v7.7.0 で段ごとのベタ塗りを廃止。読ませたいのは色ではなく**幅の変化**で、
  焦点は最終到達段 1 つだけに置く。

### buildSnake — variant `snake` / `wave-step`
- 容量: `CAPACITY.buildSnake` / 決定表: 行なし
- 選ぶとき: 段数が横幅に収まらないが、順序は保ちたいとき（折り返しフロー）。
- 選ばないとき: 段数が少ないとき（折り返す意味がない → `buildHorizontalFlow`）。
- 日本語ラベル: 行内で等分割の固定幅。

### buildSlope — variant `slope`
- 容量: `CAPACITY_ARGS.buildSlope`（左右 2 配列）/ 決定表: 行なし
- 選ぶとき: 2 時点の間で**順位の入れ替わり**を読ませたいとき。
- 選ばないとき: 順位が変わらないとき（線が平行に並ぶだけ → `buildBarChart`）。
- 日本語ラベル: 左右端の余白に置く固定幅。線が密なところで縦に衝突する。

### buildButterfly — variant `butterfly`
- 容量: `CAPACITY_ARGS.buildButterfly`（左右 2 配列）/ 決定表: 行なし
- 選ぶとき: 共通の項目軸に対して 2 群の量を左右対称に比べるとき。
- 選ばないとき: 項目軸が揃わないとき（対称にする前提が壊れる）。
- 日本語ラベル: 中央の項目名列が固定幅。左右の棒には載せない。

### buildMindmap — variant `mindmap` / `network`
- 容量: `CAPACITY.buildMindmap` / 決定表: 行なし
- 選ぶとき: 中心概念から放射状に広がる関連で、枝の間に順序が無いとき。
- 選ばないとき: 枝どうしに関係があるとき（放射では描けない → `buildArchitecture`）。
- 日本語ラベル: v7.5.0 で外円の**外側**へリーダー線付きに移し、
  `kit.wrapText(label, labelW, 16, { maxLines: 3, ellipsis: false })` で 3 行まで折り返す。
  文字切れ解消のための設計変更なので、ここは行数で吸収する型。

### buildVs — variant なし（slide `diagram-vs` 系）
- 容量: `CAPACITY_ARGS.buildVs`（左右 2 配列）/ 決定表: 行なし
- 選ぶとき: Before / After で**優劣の方向が確定している**とき。左を赤系、右を緑・青系に固定描画する。
- 選ばないとき: 2 案が対等なとき。色が善悪を主張してしまうので `buildNeutralComparison` を使う。
- 日本語ラベル: 項目テキストは `kit.wrapText(..., { maxLines: 3, ellipsis: false })` で 3 行まで。
- 制約: `buildVs` は善悪の意味を色と位置に固定するため、対等比較には使わない。中立版は意味ownerを分けるための別実装である。

### buildLineChart — variant なし（slide `chart-line`）
- 容量: `CAPACITY.buildLineChart` / 決定表: 行なし
- 選ぶとき: 連続量の**推移**を読ませたいとき。
- 選ばないとき: 系列間の順序が無いカテゴリのとき（線で結ぶと嘘の連続性が出る）。
- 日本語ラベル: 横軸の目盛りラベルは点間隔に縛られる固定幅。

### buildRadarChart — variant なし（slide `chart-radar`）
- 容量: `CAPACITY_ARGS.buildRadarChart`（軸配列・系列配列）/ 決定表: 行なし
- 選ぶとき: 同一尺度の複数評価軸で**形の違い**を読ませたいとき。
- 選ばないとき: 軸の尺度が揃わないとき、軸が少なすぎる／多すぎるとき。
- 日本語ラベル: 軸の外周に配置。上下の軸ラベルほど余白が薄い。

### buildScatterChart — variant なし（slide `chart-scatter`）
- 容量: `CAPACITY.buildScatterChart` / 決定表: 行なし
- 選ぶとき: 2 変量の相関・分布を読ませたいとき。
- 選ばないとき: 点数が少なく相関が語れないとき。
- 日本語ラベル: 点の脇に置くので互いに重なりやすい。件数を絞る側で調整する。

### buildGauge — variant なし（slide `chart-gauge`）
- 容量: 登録なし。**スカラ 1 個を取る**ため `CAPACITY` に項目が無い唯一のビルダー。
- 決定表: 行なし
- 選ぶとき: 単一の達成率・充足率を 1 点だけ見せたいとき。
- 選ばないとき: 比較対象があるとき（ゲージ 2 個を並べるより `buildBarChart`）。
- 日本語ラベル: 中央の数値と短い単位のみ。長い語は載せない前提の型。

### buildGantt — variant なし（slide `diagram-gantt` / `diagram-growth`）
- 容量: `CAPACITY.buildGantt` / 決定表: 行なし
- 選ぶとき: 期間の**長さと重なり**が論点のとき。
- 選ばないとき: 期間を持たない出来事の列のとき（`buildVerticalTimeline`）。
- 日本語ラベル: 左のタスク名列が固定幅。バー上には載せない。

### buildStar — variant なし（slide `diagram-star`）
- 容量: `CAPACITY.buildStar` / 決定表: 行なし
- 選ぶとき: 中心の主題に対して同格の要素を強調して並べたいとき。
- 選ばないとき: 要素間に関係線が要るとき（`buildMindmap`）。
- 日本語ラベル: 星形ノード内の固定幅。短い名詞句向け。

### buildVerticalColumns — variant なし
- 容量: `CAPACITY.buildVerticalColumns` / 決定表: 行なし
- 実装: `buildVerticalFlow` へ委譲（AIDMA / FABE の縦カラム用途）。
- 入口: `render-report.js` にも `render-slide.cjs` にも分岐が**無い**。直接 require 専用。
- 日本語ラベル: `buildVerticalFlow` と同じく高さで吸収できる。

---

## 3. `svg-structures.cjs` の構造図（残り 9 種。`buildSwimlane` は決定表つきなので §1）

10 種すべて `base.guard` を通り、入れ子の隠れ件数も `hidden` コールバックで
「ほか N 件」に反映される。設計方針は「配置戦略 × ノード語彙 × コネクタ語彙」の直積で、
斜め線を作らない（直交エルボまたは同半径円弧のみ）。
テキストは 1 行 = 1 個の `<text>` で描く（`tspan` で積むと D1 が連結長で測って偽のはみ出しを出すため）。
ノード幅の下限は `MIN_NODE_W` で、載せられない図は「載せない」側へ倒す。

### buildArchitecture — variant `architecture`
- 配置: `kit.zoneLayout`（ゾーン横並び）+ `kit.columnLayout`（ゾーン内縦積み）
- 容量: `CAPACITY.buildArchitecture` + `NESTED_CAPACITY.buildArchitecture`
- 決定表: 行なし（**明示指定でのみ使う**）
- 選ぶとき: 論理グループ（層・境界）に分かれ、グループ**を跨ぐ**依存が論点のとき。
  `opts.links` でノード名指定の結線を持てる。
- 選ばないとき: グループが 1 つのとき、依存が一方向の一列のとき（`buildDataFlow`）。
- 日本語ラベル: ゾーン幅・ノード幅とも固定。`MIN_NODE_W` を割るなら載せない。

### buildDataFlow — variant `data-flow`
- 配置: `kit.rowLayout` + ラベル付きエルボ
- 容量: `CAPACITY.buildDataFlow` / 決定表: 行なし（明示指定でのみ使う）
- 選ぶとき: 段の間を**何が流れるか**が論点のとき（`stage.via` が矢印ラベルになる）。
- 選ばないとき: 流れる中身に名前が無いとき（`buildHorizontalFlow` で足りる）。
- 日本語ラベル: 段は横等分割の固定幅。`via` は線上に載るので `label-japanese.md` §3 の対象。

### buildEr — variant なし
- 配置: `kit.gridLayout` + フィールド一覧を持つ箱
- 容量: `CAPACITY.buildEr` + `NESTED_CAPACITY.buildEr`（フィールド数）
- 決定表: 行なし / 入口: slide 側 `diagram-er` のみ
- 選ぶとき: エンティティとその属性・関連が論点のとき。
- 選ばないとき: 属性を見せる必要が無いとき（`buildArchitecture` の方が読みやすい）。
- 日本語ラベル: 格子セル幅で固定。フィールド行は 1 行 1 `<text>`。

### buildSequence — variant なし
- 配置: `kit.rowLayout`（アクター上端）+ 縦ライフライン + 水平矢印
- 容量: `CAPACITY_ARGS.buildSequence`（アクター配列・メッセージ配列）
- 決定表: 行なし / 入口: slide 側のみ
- 選ぶとき: **時間順のやり取り**が論点で、誰から誰へが毎回変わるとき。
- 選ばないとき: やり取りが一往復のとき、時間順が本質でないとき。
- 日本語ラベル: メッセージ名は矢印に載る。`label-japanese.md` §3 の「載せない」判断が効く。

### buildState — variant なし
- 配置: `kit.gridLayout` + エルボ（自己遷移は円弧）
- 容量: `CAPACITY_ARGS.buildState`（状態配列・遷移配列）
- 決定表: 行なし / 入口: slide 側のみ
- 選ぶとき: 状態と**遷移条件**が論点のとき。`state.focal` で焦点を 1 つ置ける。
- 選ばないとき: 遷移が一方向の一本道のとき（`buildChevron`）。
- 日本語ラベル: 遷移条件が線に載る。長い条件は載せない側へ倒す。

### buildHighLevel — variant なし
- 配置: `kit.levelLayout`（段ごとに任意個）+ エルボ
- 容量: `CAPACITY.buildHighLevel` + `NESTED_CAPACITY.buildHighLevel`
- 決定表: 行なし / 入口: slide 側のみ
- 選ぶとき: 段ごとの要素数がバラバラな**概観**を 1 枚で見せたいとき。
- 選ばないとき: 各段が同数で揃うとき（`buildSwimlane` / `buildItState` の方が読みやすい）。
- 日本語ラベル: 段内で等分割。要素数の多い段が最も苦しい。

### buildItState — variant なし
- 配置: `kit.matrixLayout`（行 × 列見出しつき）
- 容量: `CAPACITY.buildItState` / 決定表: 行なし / 入口: slide 側のみ
- 選ぶとき: 現状 / 課題 / あるべき姿 のように**列の意味が固定**の対比表のとき。
- 選ばないとき: 列が 2 つのとき（`buildNeutralComparison`）。
- 日本語ラベル: 完全な格子なのでセル幅は固定。長文は本文の表へ残す。

### buildMedallion — variant なし
- 配置: `kit.rowLayout`（層を横並び）+ `kit.columnLayout`（層内）+ 昇格円弧
- 容量: `CAPACITY.buildMedallion` + `NESTED_CAPACITY.buildMedallion`
- 決定表: 行なし / 入口: slide 側のみ
- 選ぶとき: 層を経るごとに**品質が上がる**段階構造のとき。層間の弧が昇格を語る。
- 選ばないとき: 層に品質の序列が無いとき（`buildDataFlow`）。
- 日本語ラベル: 層幅・層内項目とも固定幅。
- 関連: 層を跨ぐ弧の作り方は `connector-incidence.md` §3。

### buildDpIntegration — variant なし
- 配置: `kit.ringLayout`（中央ハブ + 周辺）+ 放射コネクタ
- 容量: `CAPACITY.buildDpIntegration` / 決定表: 行なし / 入口: slide 側のみ
- 選ぶとき: 中央の基盤へ周辺システムが接続し、**向き**（`in` / `out` / `both`）が論点のとき。
- 選ばないとき: 周辺どうしが繋がるとき（ハブ&スポークの前提が崩れる → `buildArchitecture`）。
- 日本語ラベル: リング上のノード幅は固定。`MIN_NODE_W` 未満なら載せない。

---

## 4. 網羅の確認

記載は <!-- count: svgBuilder -->38 項目。内訳は次のとおり。

- `svg-builder.cjs` の実在ビルダー <!-- count: svgBuilderCore -->**27**
  = §1 のうち 5（`buildBarChart` / `buildVerticalTimeline` / `buildChevron` /
  `buildValueStack` / `buildVerticalFlow`）+ §2 の 22。
- `svg-structures.cjs` の実在ビルダー <!-- count: svgBuilderStruct -->**10** = §1 の `buildSwimlane` + §3 の 9。
- 加えて `render-report.js` 固有の `buildNeutralComparison` 1 種（§1）。
- 決定表の行に紐づくのは `render-report.js` の `DERIVED_BUILDERS` に載る **7 種**のみ（§1）。
- 残り 31 種はすべて明示指定または slide 側 `slideType` 経由。
  明示指定するときは `visual.rationale` に上書きした行 ID を書く
  （`schemas/visual-derivation-table.json` の `override.requires`）。
- どちらの renderer からも到達しないのは `buildClockPie` と `buildVerticalColumns` の 2 種。
