# 図解型クロスウォーク（4 つの名前空間の対応表）

> **この文書は値を持たない索引である。** 容量・色・寸法・決定表の条件式は
> それぞれの正本（`svg-builder.cjs` の `CAPACITY` / `svg-kit.cjs` の `TOKENS` /
> `schemas/visual-derivation-table.json`）が持つ。
> 本ファイルが持つのは**「同じ図を指す 4 つの名前の対応」**と
> **「何を見せたいときにどの経路を通るか」**だけである。

## 0. なぜこの表が要るか

本プラグインの図解には**独立した名前空間が 4 つ**ある。

| 名前空間 | 実体 | 数 | 駆動者 |
|---|---|---|---|
| 決定論 SVG ビルダー | `vendor/scripts/svg-builder.cjs` + `svg-structures.cjs` + `render-report.js` | <!-- count: svgBuilder -->38 | `render-report.js` / `render-slide.cjs` |
| CSS/HTML 型（LLM 手書き実例） | `references/diagram-*.md` の §11.1-11.44 | <!-- count: cssDiagramType -->44 | `html-generator` / `report-composer` |
| slide テンプレート | `vendor/scripts/templates/*.html.tpl` | <!-- count: slideTemplate -->128 | `render-slide.cjs`（`slideType` 分岐） |
| 参考体系（diagram-design） | 移植元の型分類 | 27 | 移植の突合基準（本プラグインでは直接使わない） |

同じ「スイムレーン」が `buildSwimlane` / §11.39 / `diagram-swimlane.html.tpl` /
`swimlane` という 4 つの名前を持ち、対応表が無いために
**`references/diagram-*.md` の型カタログがどの prompt からも実質参照されていない**
（第 4 次 update の G1/G2）。本表がその索引である。
（行数・型数はここに書かない。数えた瞬間に陳腐化するため、規模の主張ではなく
「参照経路が無い」という事実だけを根拠に置く。）

### 表の読み方（列の定義・固定）

機械パースはヘッダ行
`| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |`
を目印に読む。

- **決定論ビルダー**: `svg-builder.cjs` / `svg-structures.cjs` の関数名。
  詳細（選ぶ条件・選ばない条件・容量の正本キー）は
  `skills/ref-diagram-system/references/diagram-type-catalog.md` の同名節。
- **CSS 型**: `references/diagram-*.md` の節番号。ファイル名は §1 の対応で引く。
- **slide tpl**: `vendor/scripts/templates/` のファイル名（`.html.tpl` は省略）。
  `slide-` 接頭辞の有無で 2 系統ある（`render-slide.cjs` の `slideType` 分岐が正本）。
- **参考型**: diagram-design の型名。移植の突合用で、本プラグインの経路名ではない。
- **推奨経路**: `決定論` = ビルダーへ渡す / `tpl` = テンプレート穴埋め /
  `手書き` = agent が SVG または HTML/CSS を書く。
- **推奨配置**: R9 溶け込み契約 §D-4-4 の配置分類（`横帯` / `方形` / `縦列` / `全幅`）。
- 対応が存在しないセルは **`—`** と書く。空欄にしない（未調査と区別できなくなるため）。

### CSS 型の節番号 → ファイル

| 節番号 | ファイル |
|---|---|
| §11.1-11.5 | `references/diagram-cycle-flow.md` |
| §11.6-11.10 | `references/diagram-comparison.md` |
| §11.11-11.20 | `references/diagram-business.md` |
| §11.20 の 5 レイアウト詳細（§11.20-1〜§11.20-5） | `references/diagram-fabe.md` |
| §11.21-11.29 | `references/diagram-visual.md` |
| §11.30 | `references/diagram-cycle-flow.md` |
| §11.31-11.32 | `references/diagram-comparison.md` |
| §11.33-11.34 | `references/diagram-visual.md` |
| §11.35-11.40 | `references/diagram-technical.md` |
| §11.41-11.44 | `references/diagram-extended.md` |
| チャート 9 種 | `references/chart-types.md` |
| 注釈（横断プリミティブ・型に属さない） | `references/svg-diagram-primitives.md` §11 |

---

## 1. 流れ・手順を見せる

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 左から右へ進む少数の工程 | `buildHorizontalFlow` | §11.4 | `flow` / `slide-flow` / `process` / `slide-process` | flowchart | 決定論 | 横帯 |
| 後戻りしない段階（矢羽根） | `buildChevron` | §11.23 | `diagram-chevron` | process | 決定論 | 横帯 |
| 段ごとに説明文が要る手順 | `buildVerticalFlow` | §11.25 | `diagram-vertical-timeline` / `d3-vertical-timeline` | process | 決定論 | 縦列 |
| 工程数が多く横幅が尽きる | `buildSnake` | §11.28 | `diagram-snake` / `diagram-wave-step` | process | 決定論 | 全幅 |
| 分岐のある判断ロジック | `buildDataFlow` | §11.4 | `diagram-flowchart` / `diagram-data-flow` | flowchart / data-flow | 決定論 | 方形 |
| 誰が・いつ・受け渡し（レーンで担当を分ける） | `buildSwimlane` | §11.39 | `diagram-swimlane` / `diagram-lane` | swimlane | 決定論 | 横帯 |
| 時系列のメッセージ往復 | `buildSequence` | §11.36 | `diagram-sequence` | sequence | 決定論 | 方形 |
| 状態と遷移と条件 | `buildState` | §11.37 | `diagram-state` | state | 決定論 | 方形 |
| 並行して走る複数の流れ | `buildSnake` | — | `diagram-parallel` | process | 決定論 | 横帯 |
| 状態列ごとのタスク分布（カンバン） | — | §11.41 | — | — | 手書き | 全幅 |
| **複数の要因が一つへ収束する（合流）** | — | — | — | — | **手書き** | 方形 |

合流は上段に並べた 2-4 個の要因から、下段の 1 個の結論へ線を集める。要因の統合・シナジー・多対一の関係に使う。
逆向き（1 個から多数へ広がる）は合流ではなく `buildMindmap`（§11.3）を使う。

## 2. 循環・反復を見せる

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 終わりが始まりへ戻る反復 | `buildCycle` | §11.1 | `diagram-cycle` / `diagram-cycle-flow-1` / `d3-cycle` | loop | 決定論 | 方形 |
| PDCA | `buildCycle` | §11.26 | `diagram-pdca` / `d3-pdca` | loop | tpl | 方形 |
| 3 要素の循環 | `buildCycle` | §11.27 | `diagram-triangle-cycle` / `d3-triangle-cycle` | loop | tpl | 方形 |
| 回転しながら進む流れ | — | — | `d3-rotating-flow` | loop | tpl | 方形 |
| 中心に蓄積するフライホイール | `buildCycle` | §11.30 | `diagram-cycle` | loop | 手書き | 方形 |

## 3. 階層・包含を見せる

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 親子の従属・分類 | `buildHierarchy` | — | `d3-tree` / `d3-dendrogram` | tree | 決定論 | 縦列 |
| 組織・レポートライン | `buildHierarchy` | §11.22 | `diagram-org` / `d3-org-chart` | org-chart | 決定論 | 縦列 |
| 上ほど少なく価値が高い | `buildPyramid` | §11.34 | `pyramid` / `slide-pyramid` / `d3-pyramid` | pyramid | 決定論 | 方形 |
| 下から積み上がる土台関係・抽象度の段（レイヤスタック） | `buildValueStack`（report）/ `buildPyramid`（slide） | §11.16 | `diagram-value-stack` | layers | 決定論 | 縦列 |
| 内側ほど核心（同心円） | `buildConcentric` | §11.14 | `diagram-concentric` | nested | 決定論 | 方形 |
| **包含（枠の入れ子でスコープを示す）** | — | §11.33 | — | nested | **手書き** | 方形 |
| 中心から放射する連想 | `buildMindmap` | §11.3 | `diagram-mindmap` | — | 決定論 | 方形 |
| 人物どうしの関係網 | `buildMindmap` | §11.24 | `diagram-person-network` / `d3-force` | — | 決定論 | 方形 |

**ビルダーに `variant` 引数は無い。** `buildHierarchy` / `buildMindmap` /
`buildVerticalTimeline` / `buildGantt` はいずれも `opts.variant` を読まない
（`vendor/scripts/svg-builder.cjs`）。見た目の差は**渡す `slideType` の側**で付く。
`tree` と `org` は同じ `buildHierarchy`、`network` は同じ `buildMindmap` の出力である。

**`diagram-value-stack` は slide と report で通るビルダーが違う。**
`render-slide.cjs` は `diagram-value-stack` を `buildPyramid` へ渡し、
`render-report.js` の `value-stack` は `buildValueStack` へ渡す。
同じ節番号でも面によって幾何が変わるので、容量は使う側のビルダーの `CAPACITY` を見る。

## 4. 比較・対立を見せる

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 2 案を対等に比べる | `buildNeutralComparison` | §11.6 | `compare` / `slide-compare` / `diagram-comparison-1` | — | 決定論 | 横帯 |
| Before / After（優劣あり） | `buildVs` | §11.6 | `diagram-vs` | — | 決定論 | 横帯 |
| 左右対称の量の対比 | `buildButterfly` | — | `diagram-butterfly` | bar | 決定論 | 方形 |
| 行 × 列の交点に意味を置く（対応マトリクス / 象限図 / 可否マトリクス） | `buildMatrix` | §11.7（n×m）/ §11.31（象限）/ §11.32（可否 3 値） | `diagram-matrix` | dp-security-matrix / quadrant | 決定論 | 方形 |
| 集合の重なり | `buildVenn` | §11.2 | `diagram-venn-2` / `diagram-venn-3` | venn | 決定論 | 方形 |
| 2 時点の順位変動 | `buildSlope` | — | `diagram-slope` | line | 決定論 | 方形 |
| 表として読ませる | — | §11.9 | `table` / `slide-table` / `diagram-table-advanced` | — | tpl | 全幅 |
| コードの差分 | — | — | `code-compare` / `slide-code-compare` | — | tpl | 全幅 |

**マトリクス 3 種は経路が 1 つしかない。** `render-slide.cjs` は
`diagram-matrix` と `diagram-table-advanced` を区別せず `buildMatrix` へ渡すので、
n×m・象限・可否のどれを描くつもりでも通る経路は同じである。
差が付くのは**セルへ何を入れるか**だけで、
象限の点のプロットと可否 3 値のグリフは `buildMatrix` が持たない。
そこだけを手書きで足す（§11.31 / §11.32 がその文法の正本）。

## 5. 時間軸を見せる

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 日付を持つ出来事の並び | `buildVerticalTimeline` | §11.25 | `timeline` / `slide-timeline` / `diagram-vertical-timeline` | timeline | 決定論 | 縦列 |
| 施策のロードマップ | `buildVerticalTimeline` | §11.15 | `diagram-roadmap` / `d3-roadmap` | timeline | 決定論 | 横帯 |
| 期間の長短を比べる | `buildGantt` | §11.8 | `diagram-gantt` | gantt | 決定論 | 全幅 |
| 右肩上がりの成長 | `buildGantt` | §11.5 | `diagram-growth` | line | 決定論 | 方形 |
| 時刻を円で示す | `buildClockPie` | — | `chart-clock-pie` | — | tpl | 方形 |
| 日付ごとの密度 | — | — | `d3-calendar` | — | tpl | 全幅 |
| 体験の段階ごとの感情・接点（ジャーニーマップ） | — | §11.42 | — | — | 手書き | 全幅 |

## 6. 量・分布を見せる（チャート）

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| カテゴリ間の量の大小 | `buildBarChart` | `chart-types.md` | `chart-bar` / `chart-bar-vertical` / `chart-bar-horizontal` / `d3-bar` | bar | 決定論 | 方形 |
| 内訳を積んだ量 | `buildBarChart` | `chart-types.md` | `chart-bar-stacked` | bar | tpl | 方形 |
| 連続的な推移 | `buildLineChart` | `chart-types.md` | `chart-line` / `d3-line` | line | 決定論 | 方形 |
| 構成比 | `buildPieChart` | `chart-types.md` | `chart-pie` / `d3-pie` / `d3-donut` | — | 決定論 | 方形 |
| 2 変数の相関 | `buildScatterChart` | `chart-types.md` | `chart-scatter` | scatter | 決定論 | 方形 |
| 複数軸のスコア比較 | `buildRadarChart` | `chart-types.md` | `chart-radar` / `d3-radar` | radar | 決定論 | 方形 |
| 単一指標の達成度 | `buildGauge` | `chart-types.md` | `chart-gauge` / `d3-gauge` / `d3-bullet` | — | 決定論 | 方形 |
| 段階的な絞り込み | `buildFunnel` | §11.17 / §11.21 | `diagram-funnel` / `d3-funnel` | pyramid | 決定論 | 方形 |
| 増減の累積 | — | §11.43 | `d3-waterfall` | bar | 手書き | 方形 |
| 量の流れ（流量） | — | — | `d3-sankey` / `d3-chord` | data-flow | tpl | 全幅 |
| 面積で量を示す | — | — | `d3-treemap` / `d3-packed-circles` / `d3-bubble` | — | tpl | 方形 |
| 2 次元の濃淡 | — | §11.44 | `d3-heatmap` | — | 手書き | 方形 |
| 個数を絵で示す | — | — | `d3-isotype` | bar | tpl | 横帯 |
| ランキング | — | — | `d3-lollipop` / `d3-radial-bar` | bar | tpl | 方形 |
| 階層の構成比 | — | — | `d3-sunburst` / `d3-arc` | nested | tpl | 方形 |
| 語の頻度 | — | — | `d3-wordcloud` | — | tpl | 方形 |
| 縦の柱で量を並べる | `buildVerticalColumns` | — | — | bar | 決定論（**両 renderer から未到達**） | 方形 |

## 7. システム構成を見せる

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 構成要素と接続 | `buildArchitecture` | §11.38 | `diagram-architecture` | architecture | 決定論 | 方形 |
| システムと外部アクターの境界（コンテキスト図） | — | §11.40 | — | architecture | 手書き | 方形 |
| 現行の IT 資産（フェーズ／部門別） | `buildItState` | — | `diagram-it-state` | it-state | 決定論 | 全幅 |
| エンド to エンドのデータ基盤 | `buildHighLevel` | — | `diagram-high-level` | high-level | 決定論 | 全幅 |
| 品質層で分けたデータ保管 | `buildMedallion` | — | `diagram-medallion` | medallion | 決定論 | 横帯 |
| 連携トポロジ（source→core→consumer） | `buildDpIntegration` | — | `diagram-dp-integration` | dp-integration | 決定論 | 全幅 |
| 役割ごとのデータ処理の流れ | `buildDataFlow` | — | `diagram-data-flow` | data-flow | 決定論 | 全幅 |
| 実体と項目と関連 | `buildEr` | §11.35 | `diagram-er` | er | 決定論 | 方形 |

## 8. 主張・訴求を見せる（ビジネスフレーム）

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 課題 → 解決 | — | §11.11 | `diagram-problem-solution` | — | tpl | 横帯 |
| 提供価値の構造 | — | §11.12 | `diagram-value-prop` | — | tpl | 方形 |
| 要点をカードで並べる | — | §11.13 | `diagram-point-cards` / `grid` / `slide-grid` | — | tpl | 全幅 |
| AIDMA / 購買心理 | `buildFunnel` | §11.17 | `diagram-aidma` | pyramid | tpl | 方形 |
| PREP（結論→理由→例→結論） | — | §11.18 | `diagram-prep` / `diagram-business-prep` | — | tpl | 横帯 |
| STAR（状況→課題→行動→結果） | — | §11.19 | `diagram-star` | — | tpl | 横帯 |
| FABE（特徴→利点→便益→証拠） | `buildHorizontalFlow` / `buildHierarchy` / `buildSnake` / `buildVerticalTimeline` / `buildCycle` | §11.20 | `diagram-fabe-horizontal` / `-vertical` / `-grid` / `-timeline` / `-circular` | — | 決定論 + tpl | variant別 |
| 人物像 | — | §11.10 | `diagram-persona` | — | tpl | 方形 |
| アイコンで選択肢を並べる | — | §11.29 | `diagram-icon-grid` / `icon-grid` / `slide-icon-grid` | — | tpl | 全幅 |

## 9. スライド固有の面（図解ではないが `slideType` を共有する）

| 何を見せたいか | 決定論ビルダー | CSS 型 | slide tpl | 参考型 | 推奨経路 | 推奨配置 |
|---|---|---|---|---|---|---|
| 表紙 | — | — | `title` / `slide-title` / `hero` / `slide-hero` | — | tpl | 全幅 |
| 1 メッセージだけを大きく | — | — | `message` / `slide-message` / `highlight` / `slide-highlight` | — | tpl | 全幅 |
| 箇条書き | — | — | `list` / `slide-list` | — | tpl | 全幅 |
| 引用 | — | — | `quote` / `slide-quote` | — | tpl | 全幅 |
| コード | — | — | `code` / `slide-code` | — | tpl | 全幅 |
| 数値を円で示す | — | — | `circle` / `slide-circle` | — | tpl | 方形 |

---

## 10. 経路の選び方（決定論 or tpl or 手書き）

上の表の「推奨経路」列の意味と、迷ったときの判断順序。

### 判断順序（上から順に当てはまる最初のものを採る）

1. **report で本文から自動導出される 7 種か。**
   `buildBarChart` / `buildVerticalTimeline` / `buildNeutralComparison` /
   `buildSwimlane` / `buildChevron` / `buildValueStack` / `buildVerticalFlow`。
   → **決定論・自動**。`schemas/visual-derivation-table.json` の R01-R14 が
   first-match-wins で選ぶ。agent は介入しない。

2. **決定論ビルダーが存在する型か。**
   → **決定論・明示指定**。report は `section.visual.kind`（`visual.rationale` に
   上書きした行 ID を書くことが必須）、slide は `structure.json` の `slideType`。
   容量は `CAPACITY` が正本で、超過分は `guard()` が「ほか N 件」と注記する。

3. **slide でテンプレートが存在するか。**
   → **tpl**。`render-slide.cjs` が `slideType` から `.html.tpl` を引き、
   Mustache subset で穴を埋める。**report にはこの経路が無い**（G7）。

4. **どれも無い。**
   → **手書き**。`assets/diagram-templates/` の骨格をコピーし、
   図解本体だけを書く。このとき `references/diagram-style-tokens.md` の
   ロール表と `diagram-layout-contract.md` 第 4 次 update 章の数値契約が
   唯一の防具になる（`CAPACITY` も `LAYOUTS` も効かない）ので、
   出力前に `python3 scripts/validate-svg-diagram.py --check-grid --strict <file>` を必ず通す。

### 経路ごとの防具の有無

| 防具 | 決定論 | tpl | 手書き |
|---|---|---|---|
| 件数上限（`CAPACITY`） | あり | 一部 | **なし** |
| 座標計算（`LAYOUTS` / `distributeWidths`） | あり | 一部 | **なし** |
| コネクタ入射（`safeElbow`） | あり | なし | **なし** |
| 色トークン（`TOKENS` 参照） | あり | あり | **なし**（自己申告） |
| 成果物側の検査（D0-D21） | あり | あり | あり |

**手書き経路だけが防具を 4 つ失う。** だからこの経路には
骨格テンプレートと数値契約を用意した（第 4 次 update の C21 / C23）。

### 受理される型と、その型専用の絵が出る型は別（被覆の caveat）

schema の `slideType` enum に載っている＝その型の絵が描かれる、ではない。
**型を選ぶ前に上表の「実装」列で描画実体を確認する。** 現行の集約と検査境界は次のとおり。

| 食い違い | 対象 | 何が起きるか |
|---|---|---|
| 集約 | `diagram-snake` / `diagram-wave-step` / `diagram-parallel` / `diagram-point-cards` / `diagram-icon-grid` / `diagram-persona` / `diagram-problem-solution` / `diagram-value-prop` / `diagram-fabe-grid` の 9 型 | `render-slide.cjs` が**すべて `buildSnake` 1 本**へ落とす。9 通りの絵にはならない |
| D3実装 | `radial-bar` / `pyramid` / `funnel` / `waterfall` / `roadmap` / `vertical-timeline` / `wordcloud` / `chevron` | `d3-bootstrap.cjs` に型別描画caseを持つ。未知componentだけは機械検出可能なfallback標識を付け、成功した図に見せない |
| 検査境界 | D3 出力全般 | source静的lintでなく、Playwright描画後ゲートがSVG実体とfallback標識不在を確認する |

集約は意図的な共通トポロジーであり、型固有の絵ではない。D3は実行時生成なので、
source断片0件を合格証跡にせず、描画後ゲートの対象件数で判定する。

---

## 11. 参考体系（diagram-design 27 型）との突合

移植元の 27 型が本プラグインのどこに着地したか。**色・書体・骨格の意匠は
移植しない**（Kanagawa トークンを維持する）ので、この列は
「作図文法の移植先」を示すだけである。

| 参考型 | 本プラグインの着地先 | 状態 |
|---|---|---|
| architecture | `buildArchitecture` | 対応済み |
| it-state | `buildItState` | 対応済み |
| flowchart | `buildDataFlow` / §11.4 / `diagram-flowchart` | 対応済み |
| sequence | `buildSequence` | 対応済み |
| state | `buildState` | 対応済み |
| er | `buildEr` | 対応済み |
| timeline | `buildVerticalTimeline` | 対応済み |
| swimlane | `buildSwimlane` | 対応済み |
| quadrant | `buildMatrix` / §11.31（手書き） | 対応済み（点のプロットは §11.31 が担当） |
| radar | `buildRadarChart` | 対応済み |
| loop | `buildCycle` / §11.30（手書き） | 対応済み（中心ハブへの書き戻しは §11.30 が担当） |
| nested | §11.33（手書き） | 対応済み |
| tree | `buildHierarchy` | 対応済み |
| org-chart | `buildHierarchy`（`tree` と同じ関数。`slideType` で呼び分ける） | 対応済み |
| layers | `buildValueStack` | 対応済み |
| venn | `buildVenn` | 対応済み |
| pyramid | `buildPyramid` / `buildFunnel` / §11.34（手書き） | 対応済み |
| bar | `buildBarChart` | 対応済み |
| line | `buildLineChart` | 対応済み |
| gantt | `buildGantt` | 対応済み |
| scatter | `buildScatterChart` | 対応済み |
| high-level | `buildHighLevel` | 対応済み |
| process | `buildChevron` / `buildHorizontalFlow` | 対応済み |
| medallion | `buildMedallion` | 対応済み |
| data-flow | `buildDataFlow` | 対応済み |
| dp-integration | `buildDpIntegration` | 対応済み |
| dp-security-matrix | `buildMatrix` / §11.32（手書き） | 対応済み（可否 3 値のグリフ文法は §11.32 が担当） |
| annotation プリミティブ | `diagram-layout-contract.md` §D-5（文法の正本）+ `svg-diagram-primitives.md` §11（実装形） | **文法と手書きテンプレートを移植**（決定論経路の描画関数は未実装） |

**未対応・部分対応だった 5 件は R8（不足図解型の追加）で手書き経路の
テンプレートを新設して解消した**（§11.30-§11.34 と `svg-diagram-primitives.md` §11）。
いずれも**手書き経路のみ**の対応であり、決定論ビルダー・`slideType`・`CAPACITY` は
まだ持たない。決定論化するときの配線先は
`skills/ref-diagram-system/references/diagram-type-catalog.md` の冒頭
「新設追加時の必須配線」と同じ 13 項目（`structure.schema.json` の `slideType` enum、
`report-structure.schema.json` の `$defs/svgSpec.variant` enum、`CAPACITY`、
`resource-map.md`、各 prompt の Layer 6、`spec-registry.md` §15 の SR-ID）。

---

## 12. 関連

- 型ごとの選ぶ条件・選ばない条件・容量の正本キー →
  `skills/ref-diagram-system/references/diagram-type-catalog.md`
- 図解 1 枚の契約（幾何・素材・数値） → `references/diagram-layout-contract.md`
- 色ロールの索引 → `references/diagram-style-tokens.md`
- 埋め込み用の骨格 → `assets/diagram-templates/README.md`
- 図種選定の条件式の正本 → `schemas/visual-derivation-table.json`
