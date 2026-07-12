# データ可視化規約（data-visualizer 手続き知識 SSOT）

> **正本**: このファイルは data-visualizer から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/data-visualizer.md）の双方がこれを参照する。規則の上位正本 (SR-ID) は spec-registry.md を辿る。

**責務**: データ可視化のドメイン定義（用語集・評価基準・制約カタログ CONST_001-005）と、データタイプと推奨可視化のマッピング表・データ変換パターン（生データ → D3入力形式の逐語コード例）の逐語正本。data-visualizer（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| データインク比 | 描画インクのうちデータ表現に使われる割合。最大化を志向する | チャートジャンク排除・CONST_002 |
| チャートジャンク | データ理解に寄与しない装飾要素。排除対象 | データインク比・CONST_002/004 |
| 視覚エンコーディング | データ変数を位置・長さ・角度・面積・色等の視覚属性へ対応づけること | encoding・知覚精度順 |
| 可視化目的 | そのデータで見せたいこと。比較/構成/分布/関係/トレンドの5分類 | 1チャート1メッセージ |
| transformedData | 生データを D3入力形式（label/value、children、nodes/links 等）へ整形した結果 | データ変換パターン |
| recommendedChart | データ特性×目的から確定する推奨チャートタイプ | データタイプと推奨可視化 |

## 評価基準（ドメイン固有の判定基準）
| 基準 | 条件 |
|------|------|
| データタイプ適合 | `recommendedChart` がデータタイプと推奨可視化表のデータタイプ行に対応する |
| 目的の単一性 | `purpose` が 比較/構成/分布/関係/トレンド のいずれか1つに確定（1チャート1メッセージ） |
| データインク比 | `options` に装飾目的のみのフラグが含まれない |
| スケール適切性 | 連続値Y軸は0開始（例外は `options` に明示） |
| ラベル明確性 | `encoding` の全キーに対応する表示ラベルが定義済み |

## ビジネスルール

- **CONST_001 (円グラフ項目数上限)**: 円グラフは7項目以下。8項目以上は棒グラフまたはツリーマップへ切り替える。
  - 目的: 微小スライス乱立による構成比の判読不能を防ぐ。
  - 背景: 角度・面積エンコーディングは知覚精度が低く、項目数増で識別が急速に困難になる（Tufte / Few の指摘）。
- **CONST_002 (3D効果禁止)**: 棒・円・面いずれも3D表現を用いない。
  - 目的: 遠近による面積・長さの視覚的歪みを防ぐ。
  - 背景: 3Dは奥行きでデータインク比を下げチャートジャンクを増やすため、Tufte が排除を推奨。
- **CONST_003 (Y軸0起点)**: 連続値の量を示すY軸は0から開始する。0非起点にする場合は `options` に例外理由を明示する。
  - 目的: 軸の切り詰めによる差の過大表現（データ歪曲）を防ぐ。
  - 背景: 棒・面の長さは0基準で初めて比例が成立するため（誤読防止の標準ルール）。
- **CONST_004 (色は意味を持つ)**: 色はカテゴリ識別または値の強弱のいずれかの意味に限定して用いる。装飾目的の着色をしない。
  - 目的: 色の濫用による誤った意味づけと認知負荷を防ぐ。
  - 背景: 意味なき色はデータインク比を下げ、誠実な可視化を損なう。
- **CONST_005 (アクセシビリティ配慮)**: 色だけに依存せず、形状・ラベル・パターンで識別可能にする。
  - 目的: 色覚特性に関わらず情報を伝達可能にする。
  - 背景: 色相のみの区別は一部の閲覧者に伝わらず、可視化の到達性を損なう。

## データタイプと推奨可視化

| データタイプ | 推奨可視化 | D3コンポーネント |
|-------------|-----------|-----------------|
| カテゴリ比較 | 棒グラフ | D3Charts.createBarChart |
| 構成比 | 円グラフ / ツリーマップ | D3Charts.createPieChart / D3Hierarchy.createTreemap |
| 時系列変化 | 折れ線グラフ | D3Charts.createLineChart |
| 相関関係 | バブルチャート / 散布図 | D3Charts.createBubbleChart |
| 複数軸比較 | レーダーチャート | D3Charts.createRadarChart |
| 進捗・達成度 | ゲージチャート | D3Charts.createGaugeChart |
| 階層構造 | サンバースト / ツリーマップ | D3Hierarchy.createSunburst / createTreemap |
| フロー・遷移 | サンキー図 | D3Flow.createSankey |
| 関係性 | フォースグラフ / コード図 | D3Advanced.createForceGraph / createChordDiagram |
| 分布 | ヒートマップ | D3Advanced.createHeatmap |
| テキスト頻度 | ワードクラウド | D3Advanced.createWordCloud |

> このマッピングの正本は `$CLAUDE_PLUGIN_ROOT/references/chart-types.md`。コンポーネント名の差異が出た場合は chart-types.md / d3-integration.md を優先する。

## データ変換パターン

### 生データ → 棒グラフ用

```javascript
// 入力
[
  { name: "A", sales: 100 },
  { name: "B", sales: 200 }
]

// 出力
[
  { label: "A", value: 100 },
  { label: "B", value: 200 }
]
```

### 生データ → 円グラフ用

```javascript
// 入力
{ A: 30, B: 40, C: 30 }

// 出力
[
  { label: "A", value: 30 },
  { label: "B", value: 40 },
  { label: "C", value: 30 }
]
```

### 生データ → 階層構造用

```javascript
// 入力
[
  { id: 1, name: "親", parent: null },
  { id: 2, name: "子1", parent: 1 },
  { id: 3, name: "子2", parent: 1 }
]

// 出力
{
  name: "親",
  children: [
    { name: "子1" },
    { name: "子2" }
  ]
}
```

### 生データ → ネットワーク用

```javascript
// 入力
[
  { from: "A", to: "B", weight: 10 },
  { from: "B", to: "C", weight: 5 }
]

// 出力
{
  nodes: [
    { id: "A", name: "A" },
    { id: "B", name: "B" },
    { id: "C", name: "C" }
  ],
  links: [
    { source: "A", target: "B", value: 10 },
    { source: "B", target: "C", value: 5 }
  ]
}
```
