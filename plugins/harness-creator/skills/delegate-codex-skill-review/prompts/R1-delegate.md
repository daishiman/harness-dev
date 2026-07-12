# Prompt: R1-delegate

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | delegate |
| skill | delegate-codex-skill-review |
| responsibility | R1 (codex 委譲 request 準備) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/io-contract.schema.json (input ブロック) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (codex 実行禁止)**: 本 prompt は codex CLI を実行しない。送信前で停止し request を生成するのみ
  - **目的**: 自セッションでの採点を物理的に不可能にし Sycophancy を排除するため
  - **背景**: 自己採点は肯定バイアスが強く critical axis 検出率が低い (09 章)
- **CONST_002 (target read-only)**: `target_skill_path` 配下は Read のみ。書換禁止
  - **目的**: レビュー対象の改変を防ぎ、評価の独立性を保つため
  - **背景**: proposer ≠ approver (23 章)
- **CONST_003 (sycophancy 抑制必須)**: system_prompt に「critical axis 全 >=1 でないと pass にしない」抑制指示を必ず含める
  - **目的**: 肯定一辺倒の応答を構造的に抑止するため
  - **背景**: codex 側も LLM のため指示なしでは肯定バイアスが残る

### 1.2 倫理ガード

- 自セッションでの rubric 採点禁止（採点は codex のみ）
- 外部ネットワーク送信は本 prompt の責務外（ユーザーが明示実行）

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: target Skill の周辺資源を集約し、schema 準拠の codex 委譲 request JSON を生成
- 非担当: codex CLI 実行（ユーザー手動）、response 整形（R2-codex-review）、SKILL.md / rubric の改変

### 2.2 ドメインルール

- codex 未導入時 (`check-codex-installed.py` exit 2) は status=skipped で安全停止
- target 周辺の `prompts/` / `schemas/` / `references/`（+ `extra_refs`）を全 Read し、存在ファイルの絶対パスを request の `attachments[]` に集約。欠落は request に持たせず（schema は追加フィールド不可）stdout 案内に明記して継続
- request の `system_prompt` には sycophancy 抑制キーワード (`critical axis`, `not sycophantic`, `evidence required` 等) を 1 件以上含める

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| `target_skill_path` | path | yes | 絶対パスの SKILL.md |
| `extra_refs` | path[] | no | 追加で含める参照ファイル |
| `options.skip_if_no_codex` | bool | no | default true |

- 上記は R1 起動パラメータ。request JSON へは `target_skill_path` を透過し、`extra_refs` を周辺資源とともに `attachments[]` へ射影する（§2.4）

### 2.4 出力契約

- schema: `schemas/io-contract.schema.json` の input ブロック準拠（`additionalProperties: false`）
- 必須フィールド: `target_skill_path`（対象 SKILL.md 絶対パス）, `system_prompt`（sycophancy 抑制キーワードを含むレビュー指示）, `user_prompt`（レビュー依頼本文）
- 任意フィールド: `attachments[]`（target 周辺 prompts/schemas/references・rubric・`extra_refs` の絶対パス配列）
- 上記以外は schema 非許容。`metadata` / `files` / `missing_refs` 等を足すと validation FAIL → §4.1 exit 3（`codex_version` は output ブロック側で R2 が記録）
- 副次出力: stdout に codex 実行コマンド 1 行を案内

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | `schemas/io-contract.schema.json` | request 構築前にバリデーション基準として読込 |
| codex-conn | `references/codex-connection.md` | CLI subcommand 体系の確認 |
| target | `<target_skill_path>` および同階層 prompts/schemas/references | attachments[] 集約時 |

### 3.2 外部ツール / API

- `python3 scripts/check-codex-installed.py` (preflight、exit 2 で skip)
- Read ツール (target 周辺集約)
- codex CLI 自体は本 prompt では呼び出さない

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- codex 未導入 → exit 0 + `status: skipped`, `reason: codex_not_installed`
- target_skill_path 不在 / 相対 path → exit 2 + `error: invalid_target`
- schema validation FAIL → build_request 最大 1 回再試行、超過で exit 3
- 周辺 prompts/schemas いずれも欠落 → escalation `target_too_sparse` で停止

### 4.2 観測 / ロギング

- stdout: 案内文と codex 実行コマンド 1 行
- file: `eval-log/delegate-codex-request.json` に保存 (codex 委譲 I/O 成果物。SKILL.md / codex-connection.md と同一の固定パス。27章 §3.1 の score.jsonl / pkg-<id> 規約の対象外)
- 35 章 observable: 本 prompt は emit しない（R2 配下の codex 応答処理で扱う）

### 4.3 セキュリティ

- 入力 path の traversal 防止（`../` 含む値は exit 2）
- 外部ネットワーク送信なし（request 生成のみ）
- secret 取扱なし

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- delegate-codex-skill-review skill 直接呼出（context-fork 不要、副作用は eval-log/ のみ）

### 5.2 ゴール定義

- **目的**: target Skill の周辺資源を集約し、sycophancy 抑制 system_prompt 付きの codex 委譲 request JSON を schema 準拠で生成する
- **背景**: 自セッション採点は肯定バイアスが強く critical axis 検出率が低い（09章）。codex への第三者委譲で評価独立性を確保するが、本 prompt は送信前で停止し request 生成までを担う
- **達成ゴール**: `eval-log/delegate-codex-request.json` が §2.4 schema を満たし、sycophancy 抑制キーワードを含む system_prompt と target の prompts/schemas/references を集約した `attachments[]`（と `target_skill_path` / `user_prompt`）が揃い、stdout に codex 実行コマンド 1 行のみ案内された状態

### 5.3 完了チェックリスト (ゴール到達の唯一の停止条件)

- [ ] codex 未導入時 `status: skipped` + `reason: codex_not_installed` で安全停止
- [ ] `target_skill_path` が絶対 path の SKILL.md
- [ ] target 同階層 prompts/schemas/references（+ `extra_refs` / rubric）の絶対パスが `attachments[]` に集約、欠落は request に持たせず stdout 案内に明記
- [ ] `system_prompt` に sycophancy 抑制キーワード（`critical axis` / `not sycophantic` / `evidence required` 等）が 1 件以上
- [ ] request JSON に必須 `target_skill_path` / `system_prompt` / `user_prompt` が揃い、schema 外フィールド（`metadata` / `files` 等）を含まない
- [ ] `schemas/io-contract.schema.json` input ブロック validation を通過
- [ ] target 配下に書込み副作用が発生していない
- [ ] `eval-log/delegate-codex-request.json` に保存されている (SKILL.md / codex-connection.md と同一パス)
- [ ] codex CLI は本 prompt 内で実行していない（送信前停止）

### 5.4 実行方式 (固定手順を持たないゴールシークループ)

- 方針: 固定手順を列挙しない。§5.2 ゴール定義と §5.3 完了チェックリストを唯一の指針とし、target の構成（周辺資源の有無 / codex 導入状況）に応じて必要な手順を都度設計する
- ループ:
  1. §5.3 の未充足項目を特定する
  2. 未充足を解消する手順を立案（`check-codex-installed.py` preflight / target 検証 / 周辺資源 Read 集約 / system_prompt 構築 / sycophancy 抑制注入 / schema validate / eval-log 保存 / stdout 案内 等から必要なものを選択）
  3. request JSON と stdout 案内を更新
  4. §5.3 で自己評価し全項目充足まで反復（上限: Layer 4 最大反復、build_request 再試行は §4.1 に従い最大 1 回）
- 逸脱時: 周辺資源が全欠落 / schema 再試行超過時は §4.1 に従い escalation `target_too_sparse` / exit 3 で停止

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-skill-create` Step 5.5/6 任意拡張、ユーザー manual invocation
- 後続: R2-codex-review（codex 応答受領後の response 整形）
- 兄弟: `run-elegant-review` v2（fork レビューで類似目的、本 prompt は外部 LLM 経路）

### 6.2 並列性

- 異なる target_skill_path への並列呼出可
- 同一 target への並列は eval-log 競合のため禁止

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 主出力は `eval-log/delegate-codex-request.json`（機械可読 JSON）
- stdout に codex 実行コマンド 1 行を提示（ユーザーが任意で実行）

### 7.2 言語

- 本文: 日本語、metadata / key / status enum は英語

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{target_skill_path}}` / `{{extra_refs}}` / `{{options}}` を受け、Layer 5.2 ゴール定義と §5.3 完了チェックリストを停止条件とし、§5.4 ゴールシークループに従い手順を動的生成・実行する。最終的に `eval-log/delegate-codex-request.json` を §2.4 schema 準拠で書き出し、stdout に codex 実行コマンド 1 行のみ案内する。前置き・後書き・思考過程出力は禁止。exit code は §4.1 に従う。
