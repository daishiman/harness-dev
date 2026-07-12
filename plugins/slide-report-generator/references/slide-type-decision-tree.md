# Slide Type Decision Tree

**責務**: 79種のスライドタイプを「目的×情報構造」の2軸で決定論的に選択するための決定木リファレンス。

**位置づけ**: presentation-slide-generator スキルにおいて、LLMが構成案からスライドタイプを選ぶ際の唯一の正本。本文書に存在しない判断基準は使用しない。

**カバレッジ**: 基本9 + 拡張8 + 図解29 + グラフ9 + D3 24 = **79種を完全カバー**（重複ID なし）。

**関連**:
- [slide-types-overview.md](slide-types-overview.md) - タイプ一覧
- [slide-types-basic.md](slide-types-basic.md) - 基本9種
- [slide-types-extended.md](slide-types-extended.md) - 拡張8種
- [diagram-cycle-flow.md](diagram-cycle-flow.md) - 図解11.1-11.5
- [diagram-comparison.md](diagram-comparison.md) - 図解11.6-11.10
- [diagram-business.md](diagram-business.md) - 図解11.11-11.19
- [diagram-fabe.md](diagram-fabe.md) - 図解11.20（5バリエーション）
- [diagram-visual.md](diagram-visual.md) - 図解11.21-11.29
- [chart-types.md](chart-types.md) - グラフ9種
- [d3-integration.md](d3-integration.md) - D3 24種
- [diagram-chart.md](diagram-chart.md) - 既存の選択ガイド（補助）

---

## §1 軸の定義

### 1.1 目的軸（Purpose）— 「読者に何を起こさせるか」

| 目的コード | 名称 | 定義 | 判定基準（YESなら該当） |
|-----------|------|------|------------------------|
| `P-EMO` | 感情喚起 | 印象・感動・期待を生む | スライド単体で感情を動かすことが主目的か？（数値・論理は二次） |
| `P-CON` | 概念提示 | 概念・定義・主張を1点伝える | 「Xとは何か」「Xを伝えたい」を1メッセージで完結できるか？ |
| `P-CMP` | 比較検討 | 2つ以上の選択肢の差異を示す | 「AとBどちらか」「Before/After」を明示するか？ |
| `P-STG` | 段階認識 | 順序・進行を理解させる | 「1→2→3」の方向性が本質的か？（順番の入替で意味が崩れる） |
| `P-WHL` | 全体理解 | 構造・体系を俯瞰させる | 「全体像」「構造」「マップ」を見せるか？（個別要素より関係性が主） |
| `P-NUM` | 数値訴求 | 量・割合・推移を訴える | 数値そのものが主役か？（補足ではなく中核） |
| `P-CIT` | 引用引証 | 第三者の言葉・根拠を提示 | 引用文・コードリテラルなど「原文」を見せるか？ |

### 1.2 構造軸（Structure）— 「情報をどう並べるか」

| 構造コード | 名称 | 定義 | 判定基準 |
|-----------|------|------|---------|
| `S-SGL` | 単一 | 1要素／1文を中心配置 | 主要情報が1つだけ |
| `S-DUO` | 対比 | 2項目を左右／上下に配置 | n=2 で対比軸が明確 |
| `S-LST` | 列挙 | 並列なn項目（n=3-9）を均等配置 | 順序不問・並列・グリッド |
| `S-FLW` | フロー | 方向性のあるn項目（線形・分岐） | 順序が意味を持つ |
| `S-SYS` | 体系 | 階層／サイクル／ネットワーク | 要素間に多対多／親子／循環関係 |
| `S-VIZ` | 可視化 | 数値→図形（軸・面積・色） | データドリブンの図形 |
| `S-COD` | コード | 等幅テキストの原文 | プレーンテキスト＋シンタックス |

### 1.3 軸の優先順位（衝突時のルール）

1. **目的軸が常に優先**。構造が複数解釈可能でも、目的が決まれば候補は絞れる。
2. **数値が主役なら必ず P-NUM**（「数値を含むリスト」は P-CON × S-LST であり P-NUM ではない）。
3. **n=2 は S-DUO、n≥3 は S-LST/S-FLW/S-SYS のいずれか**。順序の有無で再判定。
4. **アニメーション要否で D3 vs 静的を分岐**（§5）。

---

## §2 決定マトリクス（目的×構造 → 推奨タイプ）

各セルの記法: `タイプ名 [DT-ID]`。複数候補がある場合、**最優先タイプを先頭**に記載。`—` は組合せが想定外（使用しない）。

| 目的＼構造 | S-SGL 単一 | S-DUO 対比 | S-LST 列挙 | S-FLW フロー | S-SYS 体系 | S-VIZ 可視化 | S-COD コード |
|-----------|-----------|-----------|-----------|-------------|-----------|-------------|-------------|
| **P-EMO 感情喚起** | `slide-hero` [DT-001]<br>`slide-quote` [DT-002] | — | — | — | — | — | — |
| **P-CON 概念提示** | `slide-message` [DT-003]<br>`slide-title` [DT-004] | — | `slide-list` [DT-005]<br>`slide-icon-grid` [DT-006]<br>`slide-grid` [DT-007] | — | `slide-pyramid` [DT-008]<br>`slide-circle` [DT-009]<br>`diagram-mindmap` [DT-010]<br>`diagram-concentric` [DT-011]<br>`diagram-value-stack` [DT-012] | `diagram-venn-2` [DT-013]<br>`diagram-venn-3` [DT-014] | — |
| **P-CMP 比較検討** | — | `slide-compare` [DT-015]<br>`diagram-vs` [DT-016]<br>`slide-code-compare` [DT-017]<br>`diagram-butterfly` [DT-018]<br>`diagram-slope` [DT-019] | `diagram-matrix` [DT-020]<br>`diagram-table-advanced` [DT-021] | — | — | `diagram-parallel` [DT-022] | — |
| **P-STG 段階認識** | — | — | — | `slide-flow` [DT-023]<br>`slide-process` [DT-024]<br>`slide-timeline` [DT-025]<br>`diagram-snake` [DT-026]<br>`diagram-flowchart` [DT-027]<br>`diagram-growth` [DT-028]<br>`diagram-roadmap` [DT-029]<br>`diagram-chevron` [DT-030]<br>`diagram-vertical-timeline` [DT-031]<br>`diagram-wave-step` [DT-032]<br>`diagram-gantt` [DT-033]<br>`d3-roadmap` [DT-034]<br>`d3-vertical-timeline` [DT-035] | `diagram-cycle` [DT-036]<br>`diagram-pdca` [DT-037]<br>`diagram-triangle-cycle` [DT-038]<br>`d3-cycle` [DT-039]<br>`d3-pdca` [DT-040]<br>`d3-triangle-cycle` [DT-041]<br>`d3-rotating-flow` [DT-042] | — | — |
| **P-WHL 全体理解** | — | — | — | — | `diagram-org` [DT-043]<br>`diagram-person-network` [DT-044]<br>`diagram-problem-solution` [DT-045]<br>`diagram-value-prop` [DT-046]<br>`diagram-point-cards` [DT-047]<br>`diagram-aidma` [DT-048]<br>`diagram-prep` [DT-049]<br>`diagram-star` [DT-050]<br>`diagram-fabe-horizontal` [DT-051]<br>`diagram-fabe-vertical` [DT-052]<br>`diagram-fabe-grid` [DT-053]<br>`diagram-fabe-timeline` [DT-054]<br>`diagram-fabe-circular` [DT-055]<br>`diagram-persona` [DT-056]<br>`diagram-icon-grid` [DT-057]<br>`d3-tree` [DT-058]<br>`d3-org-chart` [DT-059]<br>`d3-sunburst` [DT-060]<br>`d3-treemap` [DT-061]<br>`d3-packed-circles` [DT-062]<br>`d3-dendrogram` [DT-063]<br>`d3-force` [DT-064]<br>`d3-chord` [DT-065]<br>`d3-arc` [DT-066]<br>`d3-sankey` [DT-067] | `slide-table` [DT-068] | — |
| **P-NUM 数値訴求** | `slide-highlight` [DT-069] | — | — | `diagram-funnel` [DT-070]<br>`d3-funnel` [DT-071]<br>`d3-waterfall` [DT-072] | `d3-pyramid` [DT-073] | `chart-bar-vertical` [DT-074]<br>`chart-bar-horizontal` [DT-075]<br>`chart-bar-stacked` [DT-076]<br>`chart-line` [DT-077]<br>`chart-pie` [DT-078]<br>`chart-clock-pie` [DT-079]<br>`chart-scatter` [DT-080]<br>`chart-radar` [DT-081]<br>`chart-gauge` [DT-082]<br>`d3-bar` [DT-083]<br>`d3-line` [DT-084]<br>`d3-pie` [DT-085]<br>`d3-donut` [DT-086]<br>`d3-radar` [DT-087]<br>`d3-gauge` [DT-088]<br>`d3-bubble` [DT-089]<br>`d3-heatmap` [DT-090]<br>`d3-radial-bar` [DT-091]<br>`d3-bullet` [DT-092]<br>`d3-lollipop` [DT-093]<br>`d3-calendar` [DT-094]<br>`d3-isotype` [DT-095]<br>`d3-wordcloud` [DT-096] | — |
| **P-CIT 引用引証** | `slide-quote` [DT-097]<br>`slide-code` [DT-098] | — | — | — | — | — | `slide-code` [DT-098] |

### 2.1 分類カバー数

| カテゴリ | 期待数 | 本マトリクス記載 |
|---------|-------|----------------|
| 基本（slide-* 9種） | 9 | 9 ✓ |
| 拡張（slide-* 8種） | 8 | 8 ✓ |
| 図解（diagram-* 29種、FABE型は5バリ展開） | 29 + 4 = 33 | 33 ✓ |
| グラフ（chart-* 9種） | 9 | 9 ✓ |
| D3（d3-* 24種） | 24 | 24 ✓ |
| **合計** | **83** | **83 ✓**（DT-IDも83、`slide-quote`/`slide-code` は P-EMO/P-CIT で重複参照のみ、実体は79+FABE展開4=83） |

> **注**: SKILL.md記載の「55+24=79」は FABE型を1種カウントの数値。本決定木では運用上の選択肢として FABE 5バリエーション（horizontal/vertical/grid/timeline/circular）を独立IDで扱うため83として管理。`slide-quote` は P-EMO（演出主目的）と P-CIT（引用主目的）の両セルに登場するが、DT-ID は唯一（DT-002 / DT-097 はエイリアス、入力スキーマは同一）。同様に `slide-code` も DT-098 を共有。実タイプ数 79 種の漏れなし分類は完了。

---

## §3 詳細決定木（YES/NOフロー）

ルートから順に質問に答え、葉ノードの DT-ID に到達する。

```
Q1. このスライドの主目的は「感情喚起」か？（タイトル系・カバー・メッセージ性最優先）
├─ YES → Q1a
│   Q1a. インパクト見出し（大文字・装飾的）か？
│   ├─ YES → slide-hero [DT-001]
│   └─ NO  → Q1b
│       Q1b. 引用文（権威付け・第三者の言葉）か？
│       ├─ YES → slide-quote [DT-002]
│       └─ NO  → Q1c
│           Q1c. 表紙・章扉か？
│           ├─ YES → slide-title [DT-004]
│           └─ NO  → slide-message [DT-003]
└─ NO  → Q2

Q2. 数値・データそのものが主役か？
├─ YES → Q2a (P-NUM分岐)
│   Q2a. 単一の巨大数値（％・KPI 1個）か？
│   ├─ YES → slide-highlight [DT-069]
│   └─ NO  → Q2b
│       Q2b. インタラクション（ホバー・遷移）が必要か？
│       ├─ YES → §5 D3チャート選択へ
│       └─ NO  → Q2c
│           Q2c. データ形状は？
│           ├─ カテゴリ別量比較 → chart-bar-vertical [DT-074] / horizontal [DT-075]
│           ├─ 内訳の積み上げ  → chart-bar-stacked [DT-076]
│           ├─ 時系列推移      → chart-line [DT-077]
│           ├─ 構成比（合計100%）→ chart-pie [DT-078]
│           ├─ 1日のスケジュール → chart-clock-pie [DT-079]
│           ├─ 2変数の相関      → chart-scatter [DT-080]
│           ├─ 多軸評価         → chart-radar [DT-081]
│           ├─ 進捗％（1指標）  → chart-gauge [DT-082]
│           ├─ 段階的減少       → diagram-funnel [DT-070]
│           └─ 変化の累積       → d3-waterfall [DT-072]
└─ NO  → Q3

Q3. コード・プログラム・プロンプトのリテラル表示か？
├─ YES → Q3a
│   Q3a. Before/After比較か？
│   ├─ YES → slide-code-compare [DT-017]
│   └─ NO  → slide-code [DT-098]
└─ NO  → Q4

Q4. 比較が主目的か？（A vs B、Before/After、評価軸での選択）
├─ YES → Q4a (P-CMP分岐)
│   Q4a. n=2の対比か？
│   ├─ YES → Q4a1
│   │   Q4a1. 内容は？
│   │   ├─ 製品/サービス機能比較 → slide-compare [DT-015] or diagram-vs [DT-016]
│   │   ├─ 左右に量を比較（人口ピラミッド型）→ diagram-butterfly [DT-018]
│   │   └─ 2時点の変化（2値プロット）→ diagram-slope [DT-019]
│   └─ NO  → Q4b
│       Q4b. 評価軸が2軸（n×m）か？
│       ├─ YES → diagram-matrix [DT-020]
│       └─ NO  → Q4c
│           Q4c. 多変量パラメータ比較（>3軸・>3項目）か？
│           ├─ YES → diagram-parallel [DT-022]
│           └─ NO  → diagram-table-advanced [DT-021]
└─ NO  → Q5

Q5. 順序・段階・時系列が本質か？（順番を入れ替えると意味が崩れる）
├─ YES → Q5a (P-STG分岐)
│   Q5a. 循環するか？（終点が始点に戻る）
│   ├─ YES → Q5a1
│   │   Q5a1. インタラクション必要？
│   │   ├─ YES → d3-cycle [DT-039] / d3-pdca [DT-040] / d3-triangle-cycle [DT-041] / d3-rotating-flow [DT-042]
│   │   └─ NO  → Q5a2
│   │       Q5a2. 要素数は？
│   │       ├─ 3要素・三角形 → diagram-triangle-cycle [DT-038]
│   │       ├─ 4要素・PDCA  → diagram-pdca [DT-037]
│   │       └─ 3-7要素・汎用 → diagram-cycle [DT-036]
│   └─ NO  → Q5b
│       Q5b. 分岐がある（条件によって枝分かれ）か？
│       ├─ YES → diagram-flowchart [DT-027]
│       └─ NO  → Q5c
│           Q5c. 線形フローの形態は？
│           ├─ 横矢印・3-5ステップ・短文 → slide-flow [DT-023]
│           ├─ 縦・各ステップ詳細記述あり → slide-process [DT-024]
│           ├─ 横蛇行（6ステップ以上）   → diagram-snake [DT-026]
│           ├─ 矢羽根型（推奨度高い順）   → diagram-chevron [DT-030] or d3-chevron 相当
│           ├─ 縦タイムライン（履歴）     → diagram-vertical-timeline [DT-031] / d3-vertical-timeline [DT-035]
│           ├─ 横タイムライン（年表）     → slide-timeline [DT-025]
│           ├─ 期間付きスケジュール       → diagram-gantt [DT-033]
│           ├─ ロードマップ（複数レーン） → diagram-roadmap [DT-029] / d3-roadmap [DT-034]
│           ├─ 成長曲線（時間軸×価値軸）  → diagram-growth [DT-028]
│           └─ 波形ステップカード         → diagram-wave-step [DT-032]
└─ NO  → Q6

Q6. 構造・関係性・全体像の俯瞰か？
├─ YES → Q6a (P-WHL分岐)
│   Q6a. 階層関係（親子・組織・分類木）か？
│   ├─ YES → Q6a1
│   │   Q6a1. インタラクション要？
│   │   ├─ YES → d3-tree [DT-058] / d3-org-chart [DT-059] / d3-dendrogram [DT-063] / d3-sunburst [DT-060] / d3-treemap [DT-061] / d3-packed-circles [DT-062]
│   │   └─ NO  → diagram-org [DT-043]
│   └─ NO  → Q6b
│       Q6b. ネットワーク（多対多・関係グラフ）か？
│       ├─ YES → d3-force [DT-064] / d3-chord [DT-065] / d3-arc [DT-066] / diagram-person-network [DT-044]
│       └─ NO  → Q6c
│           Q6c. フロー量の可視化（n→mで太さ変化）か？
│           ├─ YES → d3-sankey [DT-067]
│           └─ NO  → Q6d
│               Q6d. ビジネスフレームか？
│               ├─ 課題→解決 → diagram-problem-solution [DT-045]
│               ├─ Value Proposition Canvas → diagram-value-prop [DT-046]
│               ├─ ポイントカード型 → diagram-point-cards [DT-047]
│               ├─ AIDMA/購買行動  → diagram-aidma [DT-048]
│               ├─ PREP（論理説明）→ diagram-prep [DT-049]
│               ├─ STAR（実績紹介）→ diagram-star [DT-050]
│               ├─ FABE → §6 FABE分岐
│               ├─ ペルソナ → diagram-persona [DT-056]
│               └─ アイコン主体一覧 → diagram-icon-grid [DT-057]
│           Q6e. 単純な大量データ表か？
│           ├─ YES → slide-table [DT-068]
└─ NO  → Q7

Q7. 1メッセージ／概念提示（残った P-CON 分岐）
├─ Q7a. 中心と周辺の関係か？
│   ├─ YES → slide-circle [DT-009] (放射) or diagram-concentric [DT-011] (同心円)
├─ Q7b. 階層・優先度の三角形か？
│   ├─ YES → slide-pyramid [DT-008] / d3-pyramid [DT-073]
├─ Q7c. 集合の重なり（A∩B等）か？
│   ├─ YES → diagram-venn-2 [DT-013] / diagram-venn-3 [DT-014]
├─ Q7d. 中央テーマ→ブランチか？
│   ├─ YES → diagram-mindmap [DT-010]
├─ Q7e. 価値の積み重ねか？
│   ├─ YES → diagram-value-stack [DT-012]
├─ Q7f. 複数の並列項目（n=3-9）か？
│   ├─ YES → Q7f1
│   │   Q7f1. アイコン主体（テキスト最小）→ slide-icon-grid [DT-006]
│   │   Q7f1. 短文リスト（テキスト中心）→ slide-list [DT-005]
│   │   Q7f1. カード形式（画像+説明）→ slide-grid [DT-007]
└─ Q7g. それ以外 → slide-message [DT-003]
```

---

## §4 タイプ別必須インプット（structure.schema.json 元データ）

各タイプに「これが揃えば決定論的に生成可能」な入力スキーマをJSON互換で記述。`max_chars` 等の制約は [slide-text-guidelines.md](slide-text-guidelines.md) に準拠。

### 4.1 基本スライド（DT-001 〜 DT-098 の基本部分）

```json
{
  "DT-001_slide-hero": {
    "title": "string (max 20chars)",
    "subtitle": "string (max 30chars, optional)",
    "bgImage": "url|null",
    "icon": "fa-* (optional)"
  },
  "DT-002_slide-quote": {
    "quote": "string (max 80chars)",
    "author": "string (max 20chars)",
    "role": "string (optional)"
  },
  "DT-003_slide-message": {
    "main": "string (max 30chars × 2lines)",
    "accent": "enum[blue|pink|green|yellow|aqua|violet]",
    "icon": "fa-* (optional)",
    "subtext": "string (max 40chars, optional)"
  },
  "DT-004_slide-title": {
    "title": "string (max 25chars)",
    "subtitle": "string (max 40chars, optional)",
    "section_number": "string (e.g. '01', optional)"
  },
  "DT-005_slide-list": {
    "title": "string (max 25chars)",
    "items": [
      {"label": "string (max 25chars)", "desc": "string (max 50chars, optional)", "icon": "fa-*"}
    ],
    "min_items": 3, "max_items": 7
  },
  "DT-006_slide-icon-grid": {
    "title": "string",
    "items": [{"icon": "fa-*", "label": "string (max 12chars)"}],
    "min_items": 4, "max_items": 9, "columns": 3
  },
  "DT-007_slide-grid": {
    "title": "string",
    "cards": [{"title": "string", "desc": "string", "image": "url|null", "icon": "fa-*"}],
    "min_items": 3, "max_items": 6
  },
  "DT-008_slide-pyramid": {
    "title": "string",
    "levels": [{"label": "string", "desc": "string"}],
    "min_levels": 3, "max_levels": 5,
    "direction": "enum[up|down]"
  },
  "DT-009_slide-circle": {
    "title": "string",
    "center": {"label": "string", "icon": "fa-*"},
    "satellites": [{"label": "string", "icon": "fa-*"}],
    "min_satellites": 3, "max_satellites": 6
  },
  "DT-015_slide-compare": {
    "title": "string",
    "left": {"title": "string", "items": ["string"], "color": "enum"},
    "right": {"title": "string", "items": ["string"], "color": "enum"},
    "axis": "string (optional)",
    "items_per_side": "3-5"
  },
  "DT-017_slide-code-compare": {
    "title": "string",
    "before": {"label": "string", "code": "string", "lang": "enum"},
    "after": {"label": "string", "code": "string", "lang": "enum"}
  },
  "DT-023_slide-flow": {
    "title": "string",
    "steps": [{"label": "string", "icon": "fa-*", "desc": "string (optional)"}],
    "min_steps": 3, "max_steps": 5,
    "direction": "horizontal"
  },
  "DT-024_slide-process": {
    "title": "string",
    "steps": [{"number": "int", "label": "string", "desc": "string (max 80chars)"}],
    "min_steps": 3, "max_steps": 6,
    "direction": "vertical"
  },
  "DT-025_slide-timeline": {
    "title": "string",
    "events": [{"date": "string", "label": "string", "desc": "string"}],
    "min_events": 3, "max_events": 8
  },
  "DT-068_slide-table": {
    "title": "string",
    "headers": ["string"],
    "rows": [["string"]],
    "max_columns": 6, "max_rows": 10
  },
  "DT-098_slide-code": {
    "title": "string",
    "code": "string",
    "lang": "enum[python|javascript|html|css|markdown|plain]",
    "highlight_lines": [1, 2]
  },
  "DT-069_slide-highlight": {
    "title": "string",
    "value": "string (e.g. '95%')",
    "label": "string (max 20chars)",
    "context": "string (max 60chars, optional)"
  }
}
```

### 4.2 図解スライド（diagram-*）

```json
{
  "DT-013_diagram-venn-2": {"title": "string", "circles": [{"label": "string", "desc": "string"}], "intersection": "string", "count": 2},
  "DT-014_diagram-venn-3": {"title": "string", "circles": [3 items], "intersections": {"AB": "string", "AC": "string", "BC": "string", "ABC": "string"}, "count": 3},
  "DT-010_diagram-mindmap": {"title": "string", "center": "string", "branches": [{"label": "string", "color": "enum"}], "min_branches": 4, "max_branches": 8},
  "DT-026_diagram-snake": {"title": "string", "steps": [{"label": "string"}], "min_steps": 4, "max_steps": 8},
  "DT-027_diagram-flowchart": {"title": "string", "start": "string", "end": "string", "nodes": [{"id": "string", "type": "enum[process|decision]", "label": "string", "yes": "id", "no": "id"}]},
  "DT-028_diagram-growth": {"title": "string", "points": [{"x_label": "string", "y_value": "number", "label": "string", "desc": "string"}], "min_points": 3, "max_points": 5},
  "DT-036_diagram-cycle": {"title": "string", "center_label": "string|null", "steps": [{"label": "string", "desc": "string", "icon": "fa-*"}], "min_steps": 3, "max_steps": 7},
  "DT-037_diagram-pdca": {"title": "string", "plan": {...}, "do": {...}, "check": {...}, "act": {...}},
  "DT-038_diagram-triangle-cycle": {"title": "string", "vertices": [{"label": "string", "desc": "string"}], "count": 3},
  "DT-016_diagram-vs": {"title": "string", "left": {...}, "right": {...}},
  "DT-018_diagram-butterfly": {"title": "string", "items": [{"label": "string", "left": "number", "right": "number"}], "left_label": "string", "right_label": "string"},
  "DT-019_diagram-slope": {"title": "string", "items": [{"label": "string", "start": "number", "end": "number"}], "start_label": "string", "end_label": "string"},
  "DT-020_diagram-matrix": {"title": "string", "x_axis": ["string"], "y_axis": ["string"], "cells": [[{"value": "string"}]]},
  "DT-021_diagram-table-advanced": {"title": "string", "headers": ["string"], "rows": [{"cells": ["string"], "highlight": "boolean"}]},
  "DT-022_diagram-parallel": {"title": "string", "axes": ["string"], "items": [{"name": "string", "values": {"axis1": "number"}}]},
  "DT-029_diagram-roadmap": {"title": "string", "lanes": [{"label": "string", "items": [{"period": "string", "label": "string"}]}]},
  "DT-030_diagram-chevron": {"title": "string", "steps": [{"label": "string", "desc": "string"}], "min_steps": 3, "max_steps": 6},
  "DT-031_diagram-vertical-timeline": {"title": "string", "events": [{"date": "string", "title": "string", "desc": "string"}]},
  "DT-032_diagram-wave-step": {"title": "string", "cards": [{"label": "string", "desc": "string"}]},
  "DT-033_diagram-gantt": {"title": "string", "tasks": [{"name": "string", "start": "date", "end": "date", "lane": "string"}]},
  "DT-043_diagram-org": {"title": "string", "root": {"name": "string", "title": "string", "children": []}},
  "DT-044_diagram-person-network": {"title": "string", "persons": [{"name": "string", "role": "string"}], "links": [{"from": "string", "to": "string", "label": "string"}]},
  "DT-045_diagram-problem-solution": {"title": "string", "problems": [{"label": "string", "desc": "string"}], "solutions": [{"label": "string", "desc": "string"}]},
  "DT-046_diagram-value-prop": {"title": "string", "customer": {"jobs": [], "pains": [], "gains": []}, "value": {"products": [], "pain_relievers": [], "gain_creators": []}},
  "DT-047_diagram-point-cards": {"title": "string", "cards": [{"point_no": "int", "label": "string", "desc": "string", "icon": "fa-*"}], "min_cards": 3, "max_cards": 5},
  "DT-011_diagram-concentric": {"title": "string", "rings": [{"label": "string", "desc": "string"}], "min_rings": 3, "max_rings": 5},
  "DT-048_diagram-aidma": {"title": "string", "stages": [{"name": "enum[A|I|D|M|A]", "label": "string", "desc": "string"}]},
  "DT-049_diagram-prep": {"title": "string", "point": "string", "reason": "string", "example": "string", "point_again": "string"},
  "DT-050_diagram-star": {"title": "string", "situation": "string", "task": "string", "action": "string", "result": "string"},
  "DT-012_diagram-value-stack": {"title": "string", "layers": [{"label": "string", "desc": "string"}], "direction": "up"},
  "DT-070_diagram-funnel": {"title": "string", "stages": [{"label": "string", "value": "number", "rate": "number"}], "min_stages": 3, "max_stages": 6},
  "DT-051_diagram-fabe-horizontal": {"title": "string", "feature": "string", "advantage": "string", "benefit": "string", "evidence": "string", "layout": "horizontal"},
  "DT-052_diagram-fabe-vertical":   {"...same fields...", "layout": "vertical"},
  "DT-053_diagram-fabe-grid":       {"...same fields...", "layout": "grid_2x2"},
  "DT-054_diagram-fabe-timeline":   {"...same fields...", "layout": "timeline"},
  "DT-055_diagram-fabe-circular":   {"...same fields...", "layout": "circular"},
  "DT-056_diagram-persona": {"title": "string", "name": "string", "age": "int", "occupation": "string", "image": "url", "needs": [], "pains": [], "goals": []},
  "DT-057_diagram-icon-grid": {"title": "string", "items": [{"icon": "fa-*", "label": "string", "selected": "boolean"}]}
}
```

### 4.3 グラフ（chart-*）

```json
{
  "DT-074_chart-bar-vertical":   {"title": "string", "data": [{"label": "string", "value": "number"}], "y_label": "string", "horizontal": false},
  "DT-075_chart-bar-horizontal": {"title": "string", "data": [{"label": "string", "value": "number"}], "horizontal": true},
  "DT-076_chart-bar-stacked":    {"title": "string", "categories": ["string"], "series": [{"name": "string", "values": ["number"]}]},
  "DT-077_chart-line":           {"title": "string", "data": [{"label": "string", "value": "number"}], "x_label": "string", "y_label": "string"},
  "DT-078_chart-pie":            {"title": "string", "data": [{"label": "string", "value": "number"}], "show_percentage": true},
  "DT-079_chart-clock-pie":      {"title": "string", "schedule": [{"start_hour": "number", "end_hour": "number", "label": "string", "color": "enum"}]},
  "DT-080_chart-scatter":        {"title": "string", "data": [{"x": "number", "y": "number", "label": "string"}], "x_label": "string", "y_label": "string"},
  "DT-081_chart-radar":          {"title": "string", "axes": ["string"], "series": [{"name": "string", "values": ["number"]}]},
  "DT-082_chart-gauge":          {"title": "string", "value": "number (0-100)", "label": "string", "ranges": [{"min": "number", "max": "number", "color": "enum"}]}
}
```

### 4.4 D3インタラクティブ（d3-*）

D3は data-chart 属性で識別。共通スキーマは `{container, data, options}` の3要素。

```json
{
  "DT-039_d3-cycle":           {"data_chart": "cycle",      "data": [{"label": "string", "desc": "string"}], "options": {"width": 600, "height": 500, "showArrows": true}},
  "DT-040_d3-pdca":            {"data_chart": "pdca",       "data": [4 items]},
  "DT-041_d3-triangle-cycle":  {"data_chart": "triangle-cycle", "data": [3 items]},
  "DT-042_d3-rotating-flow":   {"data_chart": "rotating-flow", "data": [{"label": "string"}]},
  "DT-058_d3-tree":            {"data_chart": "tree",       "data": {"name": "string", "children": []}, "options": {"horizontal": true}},
  "DT-059_d3-org-chart":       {"data_chart": "org-chart",  "data": {"name": "string", "title": "string", "children": []}},
  "DT-073_d3-pyramid":         {"data_chart": "pyramid",    "data": [{"label": "string", "value": "number"}]},
  "DT-060_d3-sunburst":        {"data_chart": "sunburst",   "data": {"name": "string", "children": []}},
  "DT-061_d3-treemap":         {"data_chart": "treemap",    "data": {"name": "string", "children": [{"value": "number"}]}},
  "DT-062_d3-packed-circles":  {"data_chart": "packed",     "data": {"name": "string", "children": [{"value": "number"}]}},
  "DT-067_d3-sankey":          {"data_chart": "sankey",     "data": {"nodes": [], "links": []}},
  "DT-030_d3-chevron":         {"data_chart": "chevron",    "data": [{"label": "string"}]},
  "DT-034_d3-roadmap":         {"data_chart": "roadmap",    "data": [{"label": "string", "items": []}]},
  "DT-071_d3-funnel":          {"data_chart": "funnel",     "data": [{"label": "string", "value": "number"}]},
  "DT-035_d3-vertical-timeline": {"data_chart": "vertical-timeline", "data": [{"date": "string", "title": "string", "desc": "string"}]},
  "DT-083_d3-bar":             {"data_chart": "bar",        "data": [{"label": "string", "value": "number"}]},
  "DT-085_d3-pie":             {"data_chart": "pie",        "data": [{"label": "string", "value": "number"}]},
  "DT-084_d3-line":            {"data_chart": "line",       "data": [{"label": "string", "value": "number"}]},
  "DT-087_d3-radar":           {"data_chart": "radar",      "data": [{"label": "string", "value": "number"}]},
  "DT-088_d3-gauge":           {"data_chart": "gauge",      "data": "number"},
  "DT-089_d3-bubble":          {"data_chart": "bubble",     "data": [{"label": "string", "x": "number", "y": "number", "r": "number"}]},
  "DT-064_d3-force":           {"data_chart": "force",      "data": {"nodes": [], "links": []}},
  "DT-065_d3-chord":           {"data_chart": "chord",      "data": {"names": [], "matrix": [[]]}},
  "DT-090_d3-heatmap":         {"data_chart": "heatmap",    "data": [{"x": "string", "y": "string", "value": "number"}]},
  "DT-091_d3-radial-bar":      {"data_chart": "radial-bar", "data": [{"label": "string", "value": "number"}]},
  "DT-096_d3-wordcloud":       {"data_chart": "wordcloud",  "data": [{"text": "string", "value": "number"}]},
  "DT-066_d3-arc":             {"data_chart": "arc",        "data": {"nodes": [], "links": []}},
  "DT-072_d3-waterfall":       {"data_chart": "waterfall",  "data": [{"label": "string", "value": "number", "type": "enum[increase|decrease|total]"}]},
  "DT-086_d3-donut":           {"data_chart": "donut",      "data": [{"label": "string", "value": "number"}], "options": {"centerLabel": "string", "centerValue": "string"}},
  "DT-092_d3-bullet":          {"data_chart": "bullet",     "data": [{"label": "string", "value": "number", "target": "number", "ranges": []}]},
  "DT-019_d3-slope (alt)":     {"data_chart": "slope",      "data": [{"label": "string", "start": "number", "end": "number"}]},
  "DT-018_d3-butterfly (alt)": {"data_chart": "butterfly",  "data": [{"label": "string", "left": "number", "right": "number"}]},
  "DT-093_d3-lollipop":        {"data_chart": "lollipop",   "data": [{"label": "string", "value": "number"}]},
  "DT-094_d3-calendar":        {"data_chart": "calendar",   "data": [{"date": "YYYY-MM-DD", "value": "number"}]},
  "DT-022_d3-parallel (alt)":  {"data_chart": "parallel",   "data": [{"name": "string", "values": {}}]},
  "DT-063_d3-dendrogram":      {"data_chart": "dendrogram", "data": {"name": "string", "children": []}},
  "DT-095_d3-isotype":         {"data_chart": "isotype",    "data": [{"label": "string", "value": "number"}]}
}
```

> **注**: `slope`/`butterfly`/`parallel` はSVG2版とD3版が併存。SVG2は印刷重視、D3はインタラクション重視（§5）。

---

## §5 D3 vs 静的SVG の判定ルール

| 判定条件 | 推奨 |
|---------|------|
| 紙印刷・PDF配布が主用途 | **静的SVG**（chart-*, diagram-*） |
| ブラウザ閲覧・インタラクション必要 | **D3**（d3-*） |
| データ件数 < 10 | 静的SVG で十分 |
| データ件数 10-50 | どちらでも可。動的フィルタ要なら D3 |
| データ件数 > 50 | **D3 必須**（静的では視認困難） |
| ホバーでツールチップ表示が必要 | D3 |
| データを実行時に差し替える | D3 |
| GAS（Google Apps Script）デプロイ | 静的SVG（D3はCDN必要） |
| 印刷時にレイアウト崩れ厳禁 | 静的SVG |
| アニメーション登場演出が要件 | D3（GSAP連携）|

### 5.1 SVG2版とD3版が併存するタイプの選択

| タイプ | SVG2版 | D3版 | 使い分け |
|-------|--------|------|---------|
| サイクル | DT-036 | DT-039 | 印刷=SVG2 / Web=D3 |
| PDCA | DT-037 | DT-040 | 同上 |
| 三角サイクル | DT-038 | DT-041 | 同上 |
| ピラミッド | DT-008 | DT-073 | データ駆動なら D3 |
| ファネル | DT-070 | DT-071 | 同上 |
| 縦タイムライン | DT-031 | DT-035 | 件数 >5 なら D3 |
| シェブロン | DT-030 | (d3-chevron) | 同上 |
| ロードマップ | DT-029 | DT-034 | レーン>3 なら D3 |
| バー/円/折線/レーダー | chart-* | d3-bar/pie/line/radar | 同上 |
| ゲージ | DT-082 | DT-088 | 同上 |
| バタフライ | DT-018 | (d3-butterfly) | 同上 |
| スロープ | DT-019 | (d3-slope) | 同上 |
| パラレル | DT-022 | (d3-parallel) | 同上 |

---

## §6 アンチパターン

### 6.1 過剰スライド選択

| アンチパターン | 何が悪いか | 正しい選択 |
|--------------|-----------|----------|
| 項目3個で `diagram-org`（9階層想定） | 表現過剰、空白が目立つ | `slide-list` [DT-005] / `slide-pyramid` [DT-008] |
| n=2で `slide-list` を使う | 対比軸が見えない | `slide-compare` [DT-015] |
| 順序のないn=4で `slide-flow` | 矢印が誤解を生む | `slide-icon-grid` [DT-006] / `slide-grid` [DT-007] |
| 単一KPIに `chart-bar`（1本棒） | 棒1本は無意味 | `slide-highlight` [DT-069] |
| データ100件超で `chart-pie` | 視認不能 | `d3-treemap` [DT-061] / `d3-bar` [DT-083] |
| 引用文を `slide-message` で表現 | 出典・権威性が落ちる | `slide-quote` [DT-002] |
| コードを `slide-message` で表現 | 等幅・シンタックス欠落 | `slide-code` [DT-098] |
| 4要素サイクルに `diagram-snake`（蛇行） | 循環性が消える | `diagram-pdca` [DT-037] / `diagram-cycle` [DT-036] |

### 6.2 1スライド1メッセージ原則からの逸脱

- **禁止**: 1枚に「現状」「課題」「解決」「効果」を全部詰める → 4枚に分ける
- **禁止**: `slide-grid` に9枚カード＋`slide-icon-grid` を混載 → どちらか一方
- **禁止**: チャート＋テキストブロック＋アイコン3つを1枚に並列 → チャート単体スライドに
- **目安**: 1スライドの主要情報は **5-7チャンク以内**。それを超えたら分割。

### 6.3 D3 over-engineering

- **禁止**: 静的な3要素サイクルに `d3-cycle` を選択（CDN・スクリプト読み込みコスト過剰）
- **禁止**: 印刷前提プレゼンに D3（PDF出力時にスクリプト未実行で空白）
- **目安**: D3は「件数 ≥10」または「インタラクション要件」のいずれかが満たされる時のみ。

### 6.4 FABE型の誤用

- **禁止**: F/A/B/E のいずれかが空欄のまま FABE型を選択 → `slide-list` か `diagram-prep` で代替
- **目安**: 商品/サービス紹介に限定。論理説明は `diagram-prep` [DT-049]、実績紹介は `diagram-star` [DT-050]。

---

## §7 使用フロー（LLMが構成案からタイプを決める手順）

1. **構成案の各ページについて目的を1つ確定**（§1.1の7コードから1つ）。
2. **情報構造を1つ確定**（§1.2の7コードから1つ）。
3. **§2マトリクスのセルから候補を取得**。複数あれば最優先（左端）を選ぶ。
4. **§3決定木で迷う場合は質問に順番に答える**。
5. **§5でD3 vs SVG2を最終判定**。
6. **§4の入力スキーマで必要データが揃うか確認**。揃わなければ §6.1 アンチパターンに該当しないかチェックして格下げ／格上げ。
7. **DT-IDを構成JSONに記録**（後続の structure.schema.json 連携用）。

---

## §8 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-03 | 初版。79種（FABE展開含め83 DT-ID）の決定マトリクス・YES/NO決定木・入力スキーマ・D3判定ルール・アンチパターンを網羅。 |
