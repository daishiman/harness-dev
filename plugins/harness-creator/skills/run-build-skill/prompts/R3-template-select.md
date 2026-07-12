# Prompt: R3-template-select

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | template-select |
| skill | run-build-skill |
| responsibility | R3 (kind → 基底テンプレート templates/<kind> 決定) |
| layers_covered | [L2, L4] |
| output_schema | schemas/template-selection.schema.json#/properties/selection_rules/items |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- selection_rules を順次照合し、最初に match した 1 件のみ採用
  - 目的: 決定論的選択を保証
  - 背景: 複数 match の暗黙優先は drift を生む
- 不一致 kind では fallback ではなく明示エラーで停止
  - 目的: silent 誤選択の防止
  - 背景: fallback は誤った skill 生成を量産する

### 1.2 倫理ガード
- 該当 rule を取り違えて自動修正しない
  - 目的: 人間レビューの機会を奪わない
  - 背景: 自動修正は監査困難な変更を残す

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `brief.kind / role_suffix / composite` から template + combinators を 1 件決定
- 非担当: 骨格生成 (R1)、prompt 生成 (R2)、trace 記入 (R4)

### 2.2 ドメインルール
- `COMPOSER_MODE=atomic` の場合、combinators を `atomic_order` (kind → flag) で適用
- 本文に表を埋め込まず、結果のみを build_flow_coverage へ追記

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| kind | string | yes | eval-log/skill-brief.json#/kind |
| role_suffix | string | no | eval-log/skill-brief.json#/role_suffix |
| composite | object | no | eval-log/skill-brief.json#/composite |
| selection_schema | path | yes | schemas/template-selection.schema.json |

### 2.4 出力契約
- schema: `schemas/template-selection.schema.json#/properties/selection_rules/items`
- 必須: 採用 rule + combinators 列 (順序保持)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | schemas/template-selection.schema.json | rule 照合時 |

### 3.2 外部ツール / API
- なし (純粋な決定論的選択ロジック)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 不一致 kind は exit 1 + 該当 kind を log に残す
  - 目的: 新規 kind の追加漏れを検知
  - 背景: schema 更新忘れの早期発見

### 4.2 観測 / ロギング
- 出力先: `build_flow_coverage[template_select]` に採用 rule id を記録

### 4.3 セキュリティ
- 特になし (read-only な選択処理)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R3 SubAgent

### 5.2 ゴール定義
- **目的**: brief の (kind, role_suffix, composite) から 1 件の template + combinators を決定論的に選ぶ
- **背景**: 複数 match の暗黙優先や fallback は drift と誤生成を量産するため、最初の match 1 件のみで停止する
- **達成ゴール**: 同入力で常に同 rule.id が返り、不一致 kind は明示エラーで停止する状態

### 5.3 完了チェックリスト (停止条件)
- [ ] 最初に match した 1 件のみ採用 (複数採用なし)
- [ ] combinators 適用順が atomic_order と一致 (`COMPOSER_MODE=atomic` 時)
- [ ] 不一致 kind に対し fallback ではなく明示エラー (exit 1)
- [ ] 同 (kind, role_suffix, composite) で同一 rule.id を返す (決定論)
- [ ] 採用 rule id を `build_flow_coverage[template_select]` へ記録

### 5.4 実行方式 (動的手順生成ループ)
1. 未充足チェックリスト項目を特定
2. 解消手順を立案 (brief 抽出 / 順次照合 / combinators 並べ替え / trace 追記 のいずれか)
3. 実行し成果物を更新
4. チェックリストで自己評価、全項目充足まで反復

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (R1 と同 scaffold phase・step 2 で並列可。R2=prompts-emit は step 7 で後段のため並列対象外)
- 後続 phase: trace-write (R4)

### 6.2 並列性
- 同 scaffold phase の R1 と独立並列可 (副作用なし)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 採用 rule の id + combinators (JSON)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{kind}} / {{role_suffix}} / {{composite}}` を取り、`{{selection_schema}}` の
selection_rules を順次照合し、最初の match を返す。`COMPOSER_MODE=atomic` の場合は
combinators を `atomic_order` で並べ替える。不一致 kind は exit 1。

出力は `schemas/template-selection.schema.json#/properties/selection_rules/items` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
