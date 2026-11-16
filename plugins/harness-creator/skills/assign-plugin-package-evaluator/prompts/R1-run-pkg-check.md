# Prompt: R1-run-pkg-check

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | run-pkg-check |
| skill | assign-plugin-package-evaluator |
| responsibility | R1 (PKG-002〜008 / PKG-014 worker 実行) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/findings.schema.json |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (PKG ID 一次情報)**: 本 prompt 内で PKG ID 表を再定義しない。`ref-pkg-contract` を一次情報として参照
  - **目的**: 契約 drift を防ぐため
  - **背景**: validator 側で独自定義すると契約改廃 governance を回避してしまう
- **CONST_002 (eval-log path 規約)**: 27章 §3.1 規約を厳守
  - **目的**: 集約 script の走査整合性を保つため
  - **背景**: 自由パスは aggregate-pkg-findings.py を壊す
- **CONST_003 (受理 ID 限定)**: 静的検査の中核 8 件 (PKG-002/003/004/005/006/007/008/014) のみ受理。それ以外は `unsupported_pkg_id` エラー
  - **目的**: 責務外 ID の誤実行を防ぐため
  - **背景**: PKG-001/009〜013/015 は別 worker / 別 script の管轄

### 1.2 倫理ガード

- proposer ≠ approver（23章）: 本 worker は判定者であり改善実行はしない
- context: fork 強制（`target_plugin` / `pkg_ids` / `options` の構造化入力のみを渡し、親 context の判断履歴は持ち込まない）

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: 指定 PKG ID 群に対し `scripts/validate-plugin-package.py` を順次実行し findings JSON を集約
- 非担当: PKG-001（claude CLI validate, run-plugin-package-check 直接）、PKG-009/015（外部 lint）、PKG-010〜013（smoke / permission scripts）

### 2.2 ドメインルール

- `package_mode=skill-only` の場合、PKG-003/005/006/007/008/014 を即 `not_applicable` 確定（exec しない）
- fail が出ても止めず、指定された全 PKG ID の status を確定する（script に途中停止の option は無い）
- script の判定に加え、SKILL.md「評価者が読んで判定する条件」の表を判定し、違反は当該 PKG ID の findings に足して `status: fail` にする。PKG-007 の実行規則の正本は `validate-plugin-package.py` の `check_pkg_007`
- 入力 `pkg_ids` 省略時は中核 8 件を全件実行

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| `target_plugin` | string | yes | kebab-case plugin 名 |
| `pkg_ids` | string[] | no | 省略時は中核 8 件 |
| `options.output_path` | path | no | eval-log 保存先（指定なしなら stdout のみ） |
| `options.render` | enum | no | `markdown` 指定時のみ `render-pkg-findings.py` 経由で markdown サマリも出力（§3.1 renderer / §7.1）。未指定は JSON のみ |

### 2.4 出力契約

- schema: `schemas/findings.schema.json`
- 必須フィールド: `run_id`, `target_plugin`, `package_mode`, `pkg_checks`, `verdict`
- `pkg_checks` は PKG ID (`PKG-002`〜`PKG-008`, `PKG-014`) をキーとするオブジェクト（`additionalProperties: false`）。各エントリは `status` (`pass|fail|skip|not_applicable`), `findings[]`, `last_run_at` を必須とし、`status ∈ {skip, not_applicable}` のとき `skip_reason` も必須
- 各 `findings[i]` は `id`, `pkg_id`, `severity` (`P0|P1|P2`), `location`, `evidence` を必須とし、`suggested_fix` / `auto_fixable` は任意
- `verdict` は `total`, `pass`, `fail`, `skip`, `not_applicable`（各 integer）を含む

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| validator-script | `scripts/validate-plugin-package.py` | 全 PKG 実行で必須 |
| renderer | `scripts/render-pkg-findings.py` | options.render=markdown 時 |
| pkg-catalog | `../ref-pkg-contract/references/pkg-id-catalog.yaml` | PKG ID メタ参照 |
| pkg-schema | `../ref-pkg-contract/schemas/package-contract.schema.json` | input pkg_ids バリデーション |
| chap27 | `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` §3.1 | eval-log path 規約 |

### 3.2 外部ツール / API

- `python3 scripts/validate-plugin-package.py --check <pkg-id> --plugin <name>` を sub-process 起動
- plugin.json 読込: `plugins/<target_plugin>/.claude-plugin/plugin.json`

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- exit 0: 全 pass / not_applicable
- exit 1: 1 件以上 fail（findings には fail PKG ID を全て含む）
- exit 2: 入力 schema 違反 / unsupported_pkg_id / target_plugin 不在
- sub-process 異常（segfault 等）: 当該 PKG を `status: skip` + `skip_reason: "executor_error: <detail>"` で続行

### 4.2 観測 / ロギング

- stdout: findings JSON（§2.4 schema 準拠）
- stderr: exit 2 の理由だけ（`validate-plugin-package.py` は進捗ログを出さない）
- `options.output_path` 指定時は eval-log に保存。27章 §3.1 の規約は **pkg-<id> 単位** (`eval-log/<plugin>/pkg-<id>/...`)。本 worker は 8 件を 1 回で束ねる batch 出力のため、呼出元 manifest 固有の集約パス `eval-log/<plugin>/pkg-batch/<YYYY-MM-DD>-<run>.json` (run-plugin-package-check/workflow-manifest.json の pkg phase output) を用いる
- 35章 observable は呼出元（run-plugin-package-check の aggregate-pkg-findings.py）が emit

### 4.3 セキュリティ

- secret 取扱なし
- `target_plugin` 値の path traversal 防止（`../` 含む値は exit 2）

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- assign-plugin-package-evaluator skill（kind=assign, **context: fork 強制**）

### 5.2 ゴール定義

- **目的**: 中核 8 件の静的検査を一括実行し findings JSON を集約する
- **背景**: 個別 worker / 別 script との責務分離。本 worker は静的検査 8 件の executor 集約点
- **達成ゴール**: 指定 `target_plugin` の `pkg_checks` が全対象 ID 分揃い、`verdict` が集計され、§2.4 schema 準拠の findings JSON が stdout / eval-log に出力された状態

### 5.3 完了チェックリスト (ゴール到達の唯一の停止条件)

- [ ] 全対象 PKG ID が `pkg_checks` に存在（`pass|fail|skip|not_applicable` のいずれか）
- [ ] `package_mode=skill-only` のとき PKG-003/005/006/007/008/014 が `not_applicable` で確定
- [ ] 「評価者が読んで判定する条件」の表の条件を読んで判定し、違反を findings に反映した
- [ ] `verdict.{total,pass,fail,skip,not_applicable}` が `pkg_checks` と一致
- [ ] `schemas/findings.schema.json` の validation を通過
- [ ] `options.output_path` 指定時、eval-log path が呼出元 manifest の batch 集約規約 (§3.1 pkg-<id> 派生の `pkg-batch/` 集約) に準拠
- [ ] `unsupported_pkg_id` を受理せず exit 2 を返している
- [ ] target 配下に書込み副作用が発生していない

### 5.4 実行方式 (単発評価)

- 方針: 一度の採点で完結し、改善・再採点のループは回さない。§5.2 ゴール定義と §5.3 完了チェックリストで採点の網羅性を確かめる
- 実行: 入力に応じて各対象 PKG ID の機械検査と評価者判定を実行し、findings の集約、verdict の集計、schema 検証、指定時の eval-log 保存を行う
- 失敗時: 入力エラーは §4.1 に従い exit 2 で止める。sub-process 異常で終了した検査のみ `skip_reason` を記録し、残りの対象を採点する

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-plugin-package-check` (PKG-002〜008 / PKG-014 phase で `Skill(assign-plugin-package-evaluator, context=fork)`)
- 後続 phase: `aggregate-pkg-findings.py` が本 worker findings + 他 script findings を結合

### 6.2 並列性

- 同一 target_plugin に対し 1 invocation のみ（plugin.json read 競合回避）
- 異なる target_plugin への並列呼出は可

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 機械可読 JSON（findings.schema.json）が主出力
- `options.render=markdown` 指定時のみ `render-pkg-findings.py` 経由で markdown サマリも出力

### 7.2 言語

- 本文: 日本語、findings の `evidence` / `suggested_fix` フィールドは日本語、key / status enum は英語

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{target_plugin}}` / `{{pkg_ids}}` / `{{options}}` を受け、§5.4 の単発評価を実行し、Layer 5.2 ゴール定義と §5.3 完了チェックリストで採点の網羅性を確かめる。最終的に Layer 2.4 の findings JSON のみを stdout に出力する。前置き・後書き・思考過程出力は禁止。exit code は §4.1 に従う。
