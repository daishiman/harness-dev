# Prompt: R1-lookup-pkg

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | lookup-pkg |
| skill | ref-pkg-contract |
| responsibility | R1 (PKG ID 単発参照クエリ応答) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (応答は YAML 構造体、本 prompt §2.4 で固定) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (一次情報固定)**: PKG ID 表の再定義禁止。一次情報は `references/pkg-id-catalog.yaml` と `schemas/package-contract.schema.json` のみ
  - **目的**: 契約 drift を防ぐため
  - **背景**: 参照系で再定義すると 36章本文と乖離する
- **CONST_002 (catalog 正本 + drift 併記)**: 36章本文と catalog yaml に齟齬がある場合は **catalog yaml を機械可読正本**として採用、ただし齟齬を `warn: catalog_doc_drift` で併記
  - **目的**: 機械処理を止めず人間レビューに drift を可視化するため
  - **背景**: doc-only update でも CI を止めない運用要件
- **CONST_003 (eval-log path 逐語引用)**: 27章 §3.1 規約を逐語引用。本 prompt で独自定義しない

### 1.2 倫理ガード

- 未知 ID への hallucination 禁止。catalog 不在は `error: unknown_pkg_id` で停止
- PKG-016/017 は予約 ID として `warn: reserved_unresolved` を必ず併記

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: PKG ID 1 件のメタデータ（phase / script / severity / eval-log path / 関連章）を圧縮返答
- 非担当: PKG check の実行（assign-plugin-package-evaluator）、phase 完了判定（run-plugin-package-check/R2）、契約改廃 governance（run-skill-rubric-governance）

### 2.2 ドメインルール

- PKG-013 単体クエリは 013a/b/c/d の 4 件に展開して返す
- `context.package_mode=skill-only` で PKG ID の `package_modes` に `skill-only` を含まない場合は `applicable: false` + `reason` を返す
- `reserved: true` の ID は applicable 判定を実施せず予約状態のみ返す

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| `query.pkg_id` | string | yes | `^PKG-(00[1-9]\|01[0-2]\|013[a-d]?\|01[4-7])$` |
| `query.context.plugin` | string | no | 適用先 plugin 名（kebab-case）|
| `query.context.package_mode` | enum | no | `bundle` / `skill-only` / `legacy` / `dev-only` / `migration` |

### 2.4 出力契約

応答は以下の YAML 構造に固定（additionalProperties 禁止）:

```yaml
pkg_id: "PKG-NNN[a-d?]"
name: <string>
phase: 0|1|2
applicable: <bool>
applicable_reason: <string>      # applicable=false 時のみ
script: <path or "delegate:<skill>">
severity: P0|P1|P2
eval_log_path: "eval-log/<plugin>/pkg-<id>/<YYYY-MM-DD>-<run>.{json,log}"
related_chapter:
  - <章 ID + §節>
warnings:
  - <warn コード>
errors:
  - <err コード>
```

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| catalog | `references/pkg-id-catalog.yaml` | 全 query で必読（一次情報） |
| schema | `schemas/package-contract.schema.json` | pkg_id 正規表現バリデーション |
| chap36 | `doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md` | 齟齬検出時の参照（read-only） |
| chap27 | `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` §3.1 | eval-log path 規約 |

### 3.2 外部ツール / API

- なし（read-only lookup、副作用なし）

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- unknown_pkg_id → exit 2、`errors: [unknown_pkg_id]` を返す（governance escalation 推奨を併記）
- catalog / schema 不在 → exit 3、structural error として呼出元へ
- catalog と 36章本文齟齬検出 → exit 0（応答は返す）+ `warnings: [catalog_doc_drift]`

### 4.2 観測 / ロギング

- 副作用なし（read-only）
- 35章 observable には emit しない（参照系のため）

### 4.3 セキュリティ

- secret 取扱なし
- 入力に外部由来文字列が来る前提で `pkg_id` 正規表現マッチを強制

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- ref-pkg-contract skill 直接呼出（context-fork 不要、read-only）

### 5.2 ゴール定義

- **目的**: PKG ID 1 件のメタデータ (phase / script / severity / eval-log path / 関連章) を catalog 一次情報から圧縮取得し §2.4 YAML で返す
- **背景**: PKG ID 表の参照系は本 prompt のみが正当窓口。catalog yaml が機械可読正本、36章本文は人間用。齟齬は drift として併記し機械処理を止めない
- **達成ゴール**: 入力 `query.pkg_id` に対し catalog 一致 / not-found / reserved / drift の状態が一意に判定され、§2.4 YAML 構造体が `additionalProperties` 無しで返却された状態

### 5.3 完了チェックリスト (ゴール到達の唯一の停止条件)

- [ ] `pkg_id` 正規表現マッチを通過
- [ ] catalog yaml を一次情報として参照（本 prompt 内で PKG 表を再定義していない）
- [ ] PKG-013 単体クエリで 013a/b/c/d 4 件に展開
- [ ] `context.package_mode` 指定時 `applicable` / `applicable_reason` を判定
- [ ] `reserved: true` の ID で `warnings: [reserved_unresolved]` 必須
- [ ] catalog と 36章本文齟齬検出時に `warnings: [catalog_doc_drift]` 併記
- [ ] `eval_log_path` が 27章 §3.1 規約 `eval-log/<plugin>/pkg-<id>/...` 形式
- [ ] 不明 ID は hallucination せず `errors: [unknown_pkg_id]` で停止
- [ ] 副作用なし（read-only を維持）

### 5.4 実行方式 (固定手順を持たないゴールシークループ)

- 方針: 固定手順を列挙しない。§5.2 ゴール定義と §5.3 完了チェックリストを唯一の指針とし、入力 ID 形状（単発 / 013 集約 / reserved）に応じて必要な参照・展開・突合手順を都度設計する
- ループ:
  1. §5.3 の未充足項目を特定する
  2. 未充足を解消する手順を立案（regex 検証 / catalog Read / 013 展開 / package_mode 突合 / reserved 判定 / 36章 drift 検出 等から必要なものを選択）
  3. §2.4 YAML 構造体を組み立て / 更新
  4. §5.3 で自己評価し全項目充足まで反復（上限: Layer 4 最大反復）
- 逸脱時: catalog / schema 不在は §4.1 に従い exit 3 で停止

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-plugin-package-check` (Step 0 入力検証時)、`assign-plugin-package-evaluator` (PKG ID メタ参照時)
- 後続 phase: なし（リーフ参照）

### 6.2 並列性

- 完全並列可（read-only / no side effect / 同入力→同出力）

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 単体応答は YAML 構造体（パラメーター名 / schema key は英語のまま）
- バッチクエリの場合は YAML 配列で返す

### 7.2 言語

- 本文: 日本語、`name` / `applicable_reason` は日本語可、key / enum は英語

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{query}}` を受け、Layer 5.2 ゴール定義と §5.3 完了チェックリストを停止条件とし、§5.4 ゴールシークループに従い参照・展開手順を動的生成・実行する。最終的に Layer 2.4 の YAML 構造体のみを stdout に出力する。前置き・後書き・思考過程出力は禁止。catalog 不在時は exit 3 で停止。
