# Prompt: R2-codex-review

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | codex-review |
| skill | delegate-codex-skill-review |
| responsibility | R2 (codex 応答受領 / response 整形) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/io-contract.schema.json (output ブロック) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (自セッション採点禁止)**: 本 prompt は codex の応答そのものを根拠とする。自セッションでスコアを書き換えない
  - **目的**: Sycophancy / 自己肯定バイアスの混入を物理的に防ぐため
  - **背景**: 09 章評価フローの第三者性要求
- **CONST_002 (Sycophancy 再要求必須)**: codex 応答が肯定所見のみなら最大 N 回再要求する
  - **目的**: 形式的 PASS を許容しないため
  - **背景**: critical rule (rubric `rules[].severity=high` 群) を実効評価するには再要求が必要
- **CONST_003 (version pin)**: codex CLI の version は応答 metadata に記録し、未知 version は escalation
  - **目的**: 採点ロジック drift を観測可能にするため
  - **背景**: version 差で rubric 解釈が変動する

### 1.2 倫理ガード

- proposer ≠ approver: 採点結果に対する自己修正禁止、修正は別 skill (run-skill-rubric-governance) 経由
- force_pass 禁止: critical rule (rubric `rules[].severity=high`) に 1 件でも FAIL があれば `verdict: pass` にしない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: codex 応答を受け取り schema 準拠の response JSON に整形、Sycophancy 検出 / 再要求制御
- 非担当: request 生成（R1-delegate）、SKILL.md 改変、rubric 定義変更、governance 起票

### 2.2 ドメインルール

- critical rule (rubric `rules[].severity=high`) が全 PASS のとき `verdict: pass`、1 件でも FAIL で `verdict: fail`、high 以外 (medium/low) のみ指摘なら `verdict: warn`
- `findings[i]` は `message` 必須（`severity` と任意 `axis` を伴う）。`message` 欠落の finding は incomplete として再要求
- Sycophancy 検出基準: `findings` が全て `severity: info`（指摘実体ゼロ）→ retry
- 再要求は内部カウンタで上限 3（output には出さない）

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| `request_path` | path | yes | R1 が emit した request JSON path |
| `codex_raw_response` | object | yes | codex CLI が返した raw JSON |
| `options.max_sycophancy_retry` | int | no | default 3 |

### 2.4 出力契約

- schema: `schemas/io-contract.schema.json` の output ブロック準拠
- 必須フィールド: `verdict` (`pass|fail|warn|skipped`), `findings[]`。任意: `codex_version`
- 各 `findings[i]` は `severity` (`info|warn|fail`) と `message` を必須とし、`axis` (判定に用いた rule id / area) を任意で付す

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | `schemas/io-contract.schema.json` | output validation |
| request | `eval-log/delegate-codex-request.json` | metadata 突合 |
| rubric | `../ref-skill-design-rubric/references/rubric.json` | critical = `rules[].severity=high` 群 (pass/fail 判定基準)。SKILL.md 規約どおり本 prompt 本文へ焼き込み済みとし、codex 実行時は再読込しない (authoring 時のみ参照) |

### 3.2 外部ツール / API

- 外部 `codex` CLI 自体は本 prompt 内で起動しない（応答を受け取るのみ）
- 必要時 codex 再要求は R1 経由でユーザーに依頼

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- schema validation FAIL → 最大 3 回自己修正、超過で escalation `schema-invalid`
- Sycophancy 上限超過 → escalation `sycophancy-unrecoverable`
- codex CLI 不在（request の status=skipped）→ output も `verdict: skipped` 透過
- structural error → exit 3

### 4.2 観測 / ロギング

- 出力: `eval-log/delegate-codex-response.json`（27 章 §3.1 規約準拠）
- 35 章 observable: verdict=fail で `delegate_review_failed` を emit（aggregator 経由）
- escalation は `log/escalation.jsonl` に追記

### 4.3 セキュリティ

- codex 応答に含まれる外部 URL / コード片は提案として扱い自動適用しない
- secret 取扱なし

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- delegate-codex-skill-review skill 直接呼出（**context: fork 強制**、親 context のバイアスを継承しない）

### 5.2 ゴール定義

- **目的**: codex 応答を schema 準拠の response JSON へ整形し、sycophancy 検出・再要求制御を経て pass/fail 判定を確定する
- **背景**: 自セッション採点禁止 (09章)。codex 側にも肯定バイアスが残るため、severity 構成で sycophancy を検出し最大 N 回まで再要求してから判定する必要がある
- **達成ゴール**: `eval-log/delegate-codex-response.json` が §2.4 schema を満たし、`verdict` / `findings`（各 `severity`+`message`）/ 任意 `codex_version` が矛盾なく整合した状態

### 5.3 完了チェックリスト (ゴール到達の唯一の停止条件)

- [ ] `findings[]` 各要素に `severity` (`info|warn|fail`) と `message` が揃う（任意 `axis`）
- [ ] critical rule (rubric `rules[].severity=high`) 全 PASS のときのみ `verdict: pass`、1 件でも FAIL で `verdict: fail`（force_pass 禁止）
- [ ] sycophancy 検出時（`findings` 全件 `severity: info` で指摘実体ゼロ）内部 retry カウンタを増やし再要求を出した
- [ ] 内部 sycophancy retry が上限（既定 3）以内、超過時は escalation `sycophancy-unrecoverable`
- [ ] `codex_version` を付す場合は request metadata と一致
- [ ] request の `status: skipped` 透過時は output も `verdict: skipped`
- [ ] `schemas/io-contract.schema.json` output ブロック validation を通過
- [ ] SKILL.md / rubric.json / 他 skill への書込みゼロ（fork context 維持）

### 5.4 実行方式 (固定手順を持たないゴールシークループ)

- 方針: 固定手順を列挙しない。§5.2 ゴール定義と §5.3 完了チェックリストを唯一の指針とし、codex_raw_response の形状（正常 / 肯定のみ / schema 不一致 / skipped）に応じて整形・突合・再要求手順を都度設計する
- ループ:
  1. §5.3 の未充足項目を特定する
  2. 未充足を解消する手順を立案（request metadata 取得 / findings 正規化 / sycophancy 検出 / rubric 突合 / verdict 確定 / schema 自己修正 / eval-log 保存 等から必要なものを選択）
  3. response JSON を更新
  4. §5.3 で自己評価し全項目充足まで反復（schema 自己修正最大 3 回、sycophancy 再要求最大 3 回）
- 逸脱時: schema 再試行超過は escalation `schema-invalid`、structural error は §4.1 に従い exit 3 で停止

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: R1-delegate（codex 実行後にユーザーが本 prompt を起動）、`run-skill-create` Gate 4 任意拡張
- 後続: `run-skill-rubric-governance`（fail 時の改善経路）、`assign-skill-design-evaluator`（並走採点）

### 6.2 並列性

- 異なる target への並列可
- 同一 request_path への並列禁止（response 競合）

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 主出力: `eval-log/delegate-codex-response.json`（機械可読 JSON）
- 上位 skill が markdown サマリに整形する想定

### 7.2 言語

- 本文: 日本語、`verdict` enum / `severity` enum / key は英語

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{request_path}}` / `{{codex_raw_response}}` / `{{options}}` を受け、Layer 5.2 ゴール定義と §5.3 完了チェックリストを停止条件とし、§5.4 ゴールシークループに従い整形・突合・再要求手順を動的生成・実行する。最終的に `eval-log/delegate-codex-response.json` を §2.4 schema 準拠で書き出す。前置き・後書き・思考過程出力は禁止。exit code は §4.1 に従う。
