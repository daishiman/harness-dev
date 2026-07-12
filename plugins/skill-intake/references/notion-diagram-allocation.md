# Notion 章別図解割当 (重複防止正本)

各章固有の図種を 1〜2 枚割り当てる正本マッピング。`section_canonical_map.json` の `viz_slots` と `render_notion_page.py` の章別レンダラーはこの表に従う。**章間で同じ asset_id を使わない** (例外: §5 の fig1-5 のみ同質シリーズとして許容)。

## 章別図種マッピング (重複ゼロ設計)

| § | section_key | primary 図種 | secondary 図種 | 目的 |
|---|---|---|---|---|
| §0 | 0_executive_summary | `cvis-exec-summary-card` (独自 SVG) | — | 90 秒で読む概要カード |
| §1 | 1_assumption_challenger | `mermaid-mindmap-surface-vs-deep` | `mermaid-quadrant-blindspot-map` | 表層→深層の発散 + 盲点 4 象限 |
| §2 | 2_user_profile | `mermaid-radar-6dim` (radar chart 代替実装) | `cvis-persona-card` | 6 軸プロファイル定量 + 質的記述 |
| §3 | 3_purpose_excavator | `mermaid-journey-5whys` (Why深掘り旅程) | `mermaid-mindmap-stated-to-excavated` | 深掘り過程の時系列 + 結論マップ |
| §4 | 4_option_presenter | `mermaid-flowchart-decision-tree` (選択肢分岐) | `mermaid-table-pro-con` | 設計選択の判断木 + Pro/Con 表 |
| §5 | 5_visualizer | `mermaid-flowchart-lr` (architecture) | (4 枚追加固定: flowchart-tb / sequence / before-after / boundary) | 全体アーキ・コア機構・パイプ・前後・責務 |
| §6 | 6_five_axes_summary | `mermaid-pie-5axes-weight` (5 軸の比重) | `mermaid-flowchart-knowledge-pipeline` (ingest→update のパイプ) | 5 軸構成 + ナレッジ流通 |
| §7 | 7_design_decisions | `mermaid-gantt-adoption-timeline` (採択順序) | `mermaid-c4-component-adoptions` (採択構成) | 設計決定の経時 + 構成 |
| §8 | 8_open_questions | `cvis-traffic-light` (blocking/deferred 信号) | `mermaid-quadrant-question-priority` (緊急度×影響度) | 未解決の信号 + 優先順位象限 |
| §9 | 9_handoff_contract | `mermaid-flowchart-next-action` (harness-creator 引継ぎフロー) | `mermaid-state-handoff-modes` (fast-track/standard/onboarding 状態) | 引継ぎ経路 + モード分岐 |
| §10 | 10_self_updater | `cvis-score-gauge` (value_realized_score) | `mermaid-bar-deductions` (控除点の棒) | スコア計器 + 控除内訳 |
| §11 | 11_artifact_index | `mermaid-tree-artifact-files` (ファイルツリー) | — | 成果物階層 |

## 重複防止検証

`scripts/lint_subagent_seven_layer.py` の `SE-intake-viz-uniqueness` ルールが `intake-final-context.json.section_diagrams[].asset_id` を走査し、章間 (§5 例外) で重複を発見したら exit 1。

## 章ごとに「構成 / ワークフロー / 仕組み」のどれを使うか

各章の本質的内容種別に合わせて選定:

| 章 | 種別 | 理由 |
|---|---|---|
| §0/§2/§8/§10/§11 | 構成 (構造可視化) | 状態スナップショット中心 |
| §1/§3/§4/§9 | ワークフロー (フロー / 判断 / 状態遷移) | 意思決定や深掘り過程 |
| §5/§6/§7 | 仕組み (アーキ / パイプライン / 採択構成) | 設計の物理構造 |

## render_notion_page.py 実装方針

各章のレンダラー関数 (`_render_assumption` 等) は以下を必ず呼ぶ:
```python
ctx['section_diagrams'][SECTION_KEY]  # primary + secondary の mermaid_source
for d in diagrams:
    blocks.append(heading(3, d['title']))
    blocks.append(paragraph(d['one_liner']))
    blocks.append(code(d['mermaid_source'], 'mermaid'))
    if d.get('legend'): blocks.append(paragraph(f"凡例: {d['legend']}"))
```

`intake-final-schema.json` に `section_diagrams` (object: section_key → array of diagram object) を追加。生成は `visualizer` SubAgent が `render-intake-final.py` 実行前に各章用 mermaid を組み立てる。

## 段階導入

| 段階 | 範囲 | 状態 |
|---|---|---|
| 段階 1 (本セッション) | 割当表確定 + rubric ルール追加 (SE-intake-viz-uniqueness / coverage / parameters) + 本ドキュメント正本化 | 完了 |
| 段階 2 (次セッション) | section_canonical_map.json の viz_slots 全章書き換え + intake-final-schema.json への section_diagrams 追加 | 未着手 |
| 段階 3 (次セッション) | render_notion_page.py の 10 章レンダラーに mermaid 追加 + visualizer SubAgent への section_diagrams 生成責務追加 | 未着手 |
| 段階 4 (次セッション) | analyze_user_intent.py で内部解析 → render 時に最適解選択 | 未着手 |
| 段階 5 (次セッション) | `/intake-revise <hint>` コマンドで Claude Code チャット往復 → Notion 上書き反映 | 未着手 |
