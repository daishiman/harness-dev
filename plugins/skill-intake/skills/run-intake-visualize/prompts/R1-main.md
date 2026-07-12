# Prompt: R1-deterministic-figure-placement

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-intake-visualize |
| responsibility | R1-deterministic-figure-placement (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/output.schema.json |
| reproducible | true (アセットカタログからの選択は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- Mermaid 12 + SVG 8 のアセットカタログ外を新規創作しない (figure_id 必須)。
- 全 12 セクション (§0〜§11) に最低 1 図を配置。

### 1.2 倫理ガード
- 図解で誤情報を作らない (元 sheet.md にない事実を図に注入しない)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: sheet.md / purpose.json を入力に各セクションへ 1-3 図を配置し、SVG を PNG 化する。
- 非担当: ヒアリング、quality 採点、Notion 公開。

### 2.2 ドメインルール
- SVG は Notion 互換性のため必ず PNG 化する。
- 1 セクション当たり図数は 1-3 (4 以上禁止、過剰可視化抑制)。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| sheet | resource://intake/sheet.md | yes | 5 軸シート |
| purpose | resource://intake/purpose.json | yes | true_purpose |
| options | resource://intake/options.json | no | 外部連携選定 (参考。決定論配置は sheet+purpose のみで確定し options は不使用。IN2 determinism 準拠) |
| assets | resource://plugins/skill-intake/assets/ | yes | Mermaid/SVG カタログ |

### 2.4 出力契約
- schema: `schemas/output.schema.json` (additionalProperties:false)
- 必須フィールド: `sections` (section → [{figure_id, type, png_path}]), `catalog_version`

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| section-figure-mapping | references/section-figure-mapping.md | セクション→図種の対応表をロードするとき |
| viz-mandatory | references/visualization-mandatory-pointer.md | 必須ルール確認 |

### 3.2 外部ツール / API
- `plugins/skill-intake/scripts/render_to_image.py` (Mermaid→PNG + SVG 同梱 PNG 配置、aggregator 共有正本)
- `scripts/verify-visuals.py <visuals.json> <out_dir>` (網羅性検証。引数必須: `output/<hint>/visuals.json output/<hint>/visuals/`。両方必須で欠くと IndexError)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- カタログ外 figure 指定 → exit 2 (構造違反)、配置を中断。
- verify-visuals.py FAIL → exit 1 (網羅性不足)、不足セクションを stderr に列挙。

### 4.2 観測 / ロギング
- visuals.json に各 section の figure_id と png_path を残す (後追い再現用)。

### 4.4 最大反復回数
- チェックリスト充足ループ上限: **3 回** (カタログ照合 → PNG 化 → verify の最大往復数)。上限到達で verify FAIL の場合は exit 2 で中断。

### 4.3 セキュリティ
- アセットファイルパスは workspace root 起点の相対パスで記録 (絶対 PATH 漏出回避)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `@visualizer` (決定論バッチ、LLM はカタログ照合のみ、context-fork 不要)

### 5.2 ゴール定義
- 目的: 全 12 セクションへカタログ既存図を決定論的に配置し Notion 互換 PNG を生成する。
- 背景: 図解の創作は誤情報注入リスクが高く、可視化の網羅不足は intake の理解度を下げる。アセット制約と網羅性を機械で担保する。
- 達成ゴール: visuals.json (output.schema.json 準拠) と `output/<hint>/visuals/*.png` が揃い、verify-visuals.py が PASS する状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `visuals.json` が `schemas/output.schema.json` に validate (additionalProperties:false 含む)
- [ ] 全 12 セクション (§0-§11) に 1-3 図が配置 (4 図以上ゼロ、ゼロ図ゼロ)
- [ ] SVG が全て PNG 化されて Notion 互換 (拡張子 `.png`、参照パスは workspace 相対)
- [ ] visuals.json の figure_id が Mermaid 12 + SVG 8 アセットカタログの id 集合に包含 (新規創作ゼロ)
- [ ] verify-visuals.py が PASS (網羅性 / 整合性)
- [ ] 同 sheet + purpose で 2 回連続実行し visuals.json の (section → figure_id) が完全一致 (determinism)
- [ ] sheet.md にない事実が図へ注入されていない (倫理ガード)
- [ ] `references/section-figure-mapping.md` の §×図種対応表に基づく配置で、逸脱は理由付き

### 5.4 実行方式
- 固定手順を持たない。未充足チェック項目を特定→解消手順を都度立案 (カタログ照合 / PNG 化 / verify 起動など)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。
- 逸脱時: 必須セクションに該当図がカタログに無い場合は Layer 4.1 に従い exit 2 で停止しエスカレーション。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-intake` の Phase 7
- 後続 phase: Phase 8 (P8-summary, `skill-intake-summarizer`)

### 6.2 並列性
- セクション単位で並列化可。ただし PNG 書き込みパスの衝突回避必須。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- visuals.json (output.schema.json 準拠) + `output/<hint>/visuals/*.png`

### 7.2 言語
- 本文: 日本語 (figure_id / type は英語のまま)

---

## Self-Evaluation

visuals.json 生成後に以下を自己確認する。未達があれば対応 exit code を返すこと。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| 網羅性 | 全 12 セクション (§0-§11) に 1-3 図が配置されている | PASS/FAIL |
| カタログ遵守 | 全 figure_id が Mermaid 12 + SVG 8 カタログの id 集合に包含されている | PASS/FAIL |
| PNG 化完了 | 全 SVG が PNG 化され Notion 互換パスで記録されている | PASS/FAIL |
| verify 通過 | verify-visuals.py が PASS | PASS/FAIL |
| 事実注入なし | sheet.md にない事実を図に注入していない | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{sheet_path}}` と `{{purpose_path}}` を読み、`section-figure-mapping.md` に従いカタログから各セクション 1-3 図を選択せよ。SVG は `render_to_image.py` で PNG 化し、結果を `visuals.json` (schemas/output.schema.json 準拠) として書き出せ。最後に `verify-visuals.py output/<hint>/visuals.json output/<hint>/visuals/` を実行し PASS を確認すること。出力は JSON のみ、前置き禁止。
