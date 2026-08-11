# D3図解設計規約（d3-diagram-designer 手続き知識 SSOT）

> **正本**: このファイルは d3-diagram-designer から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/d3-diagram-designer.md）の双方がこれを参照する。規則の上位正本 (SR-ID) は spec-registry.md を辿る。

**責務**: D3.js インタラクティブ図解のドメイン定義（用語集・評価基準・制約カタログ CONST_001-005）と生成規約（D3コンポーネントマッピング27種・データ構造テンプレート5系統・D3アニメーション設定・全コード例）の逐語正本。d3-diagram-designer（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| chartType | 図解に割り当てる D3 コンポーネント名（4.1 表の値に限定） | コンポーネント選択 |
| 図解意図 | 比較・構成・関係・推移・分布・階層のいずれかの目的分類 | Andy Kirk 目的分類 |
| データ系統 | サイクル/階層/フロー/グラフ/ネットワークの5区分 | データ構造テンプレート |
| データインク比 | 描画に占める情報量の割合。最大化で過剰装飾を排除 | Tufte / options 最小化 |
| ツールチップ | 短語化した本文の詳細（desc 等）にアクセスする補足経路 | CONST_005 |

## 評価基準
| 基準 | 条件 |
|------|------|
| コンポーネント選択 | 受理=`chartType` が 4.1 表に存在し意図ラベルと整合（例: 推移→line、階層→tree/sunburst）/ 拒否=4.1 表に無い値 |
| データ構造 | 合格=各 `data` が選択コンポーネントの期待形（配列 or 階層 or nodes/links）に一致し `validate-d3.js` を通過 / 不合格=形式不一致 |
| アニメーション持続時間 | 適合=600〜1500ms（自動シミュレーションを除く）/ 不適合=範囲外 |
| 検証通過判定 | PASS=`node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/validate-d3.js"` が exit 0 / FAIL=exit 非0 |

## ビジネスルール
- **CONST_001 (D3 v7 使用)**: D3.js は CDN 経由で v7 を使用する。独自バンドルや他バージョンは指定しない。
  - 目的: html-generator の `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/d3-integration.md` 実装と API シグネチャを一致させ、描画エラーを防ぐ。
  - 背景: コンポーネント API は D3 メジャーバージョン間で非互換があり、バージョン混在は実行時失敗を招くため。
- **CONST_002 (Kanagawa 配色)**: 配色は Kanagawa テーマカラー定義に準拠する。任意の色指定をしない。
  - 目的: デッキ全体の視覚的統一を保ち、図解だけが浮く事態を防ぐ。
  - 背景: `validate-d3.js` がテーマ色の一貫性を検証し、`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/d3-integration.md` がテーマ配色を正本として定義しているため。
- **CONST_003 (レスポンシブ)**: SVG は `viewBox` と `preserveAspectRatio` を指定し、固定 px 寸法に依存しない。
  - 目的: 16:9 厳守のスライド枠内で図解が崩れず拡縮することを保証する。
  - 背景: スライドは画面・印刷の双方で表示され、固定寸法ははみ出し・余白を生むため。
- **CONST_004 (アニメーション時間)**: 登場アニメーションの持続時間は 600〜1500ms の範囲に収める（自動シミュレーションを除く）。
  - 目的: 速すぎて視認できない／遅すぎてテンポを損なう事態を防ぐ。
  - 背景: 4.4 設定の実測レンジであり、スライド送りのリズムを保つため。
- **CONST_005 (ツールチップ必須)**: インタラクティブな図解にはツールチップを付与する。
  - 目的: ラベルを短語化しても詳細（`desc` 等）にアクセスできる経路を残す。
  - 背景: Tufte のデータインク比最大化で本文を削るため、補足はツールチップに退避する設計を採るため。

## D3コンポーネントマッピング（27種）

> 以下の D3コンポーネントマッピング（27種）・データ構造テンプレート（5系統）・D3アニメーション設定は、意図ラベルから `chartType` / `data` / `options` を一意に導くための決定論的な生成規約であり、`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/d3-integration.md` 正本に対応する参照テーブルとして本知識ベースに保持する。

| 図解タイプ | D3コンポーネント | 主要オプション |
|-----------|-----------------|----------------|
| サイクル | D3Cycle.createCycle | innerRadius, outerRadius, showArrows |
| PDCA | D3Cycle.createPDCA | innerRadius, outerRadius |
| 三角サイクル | D3Cycle.createTriangleCycle | size, showArrows |
| 回転フロー | D3Cycle.createRotatingFlow | radius, rotationSpeed |
| ツリー | D3Hierarchy.createTree | nodeRadius, horizontal |
| 組織図 | D3Hierarchy.createOrgChart | nodeWidth, nodeHeight |
| ピラミッド | D3Hierarchy.createPyramid | - |
| サンバースト | D3Hierarchy.createSunburst | innerRadius |
| ツリーマップ | D3Hierarchy.createTreemap | padding, round |
| パックドサークル | D3Hierarchy.createPackedCircles | padding |
| サンキー | D3Flow.createSankey | nodeWidth, nodePadding |
| シェブロン | D3Flow.createChevron | - |
| ロードマップ | D3Flow.createRoadmap | - |
| ファネル | D3Flow.createFunnel | - |
| 縦タイムライン | D3Flow.createVerticalTimeline | showLine |
| 棒グラフ | D3Charts.createBarChart | horizontal, showValues |
| 円グラフ | D3Charts.createPieChart | innerRadius, showLabels |
| 折れ線グラフ | D3Charts.createLineChart | showDots, showArea |
| レーダーチャート | D3Charts.createRadarChart | levels |
| ゲージ | D3Charts.createGaugeChart | min, max, label |
| バブルチャート | D3Charts.createBubbleChart | - |
| フォースグラフ | D3Advanced.createForceGraph | nodeRadius |
| コード図 | D3Advanced.createChordDiagram | innerRadius |
| ヒートマップ | D3Advanced.createHeatmap | xLabels, yLabels |
| 放射状棒グラフ | D3Advanced.createRadialBarChart | innerRadius |
| ワードクラウド | D3Advanced.createWordCloud | - |
| アーク図 | D3Advanced.createArcDiagram | - |

## データ構造テンプレート（5系統）

### サイクル系
```json
{
  "type": "cycle",
  "data": [
    { "label": "項目1", "desc": "説明1" },
    { "label": "項目2", "desc": "説明2" }
  ],
  "options": {
    "innerRadius": 80,
    "outerRadius": 150,
    "showArrows": true
  }
}
```

### 階層系（ツリー）
```json
{
  "type": "tree",
  "data": {
    "name": "ルート",
    "children": [
      { "name": "子1", "children": [] },
      { "name": "子2", "children": [] }
    ]
  },
  "options": {
    "nodeRadius": 25,
    "horizontal": true
  }
}
```

### フロー系
```json
{
  "type": "chevron",
  "data": [
    { "label": "ステップ1" },
    { "label": "ステップ2" },
    { "label": "ステップ3" }
  ],
  "options": {}
}
```

### グラフ系
```json
{
  "type": "bar",
  "data": [
    { "label": "カテゴリA", "value": 100 },
    { "label": "カテゴリB", "value": 200 }
  ],
  "options": {
    "horizontal": false,
    "showValues": true
  }
}
```

### ネットワーク系
```json
{
  "type": "force",
  "data": {
    "nodes": [
      { "id": "node1", "name": "ノード1" },
      { "id": "node2", "name": "ノード2" }
    ],
    "links": [
      { "source": "node1", "target": "node2" }
    ]
  },
  "options": {
    "nodeRadius": 20
  }
}
```

## D3アニメーション設定
| コンポーネント | 登場アニメーション | 持続時間 |
|---------------|-------------------|----------|
| サイクル | 各セグメント順次フェードイン | 500ms × n |
| ツリー | リンク描画 → ノード出現 | 600ms + 400ms |
| 棒グラフ | 0から値まで伸長 | 600ms |
| 円グラフ | 0度から360度まで展開 | 800ms |
| 折れ線 | パス描画アニメーション | 1500ms |
| フォースグラフ | シミュレーション開始 | 自動 |
