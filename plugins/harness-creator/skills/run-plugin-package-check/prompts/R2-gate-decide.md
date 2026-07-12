# Prompt: R2-gate-decide

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | gate-decide |
| skill | run-plugin-package-check |
| responsibility | R2 (phase 完了判定 PASS/FAIL) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (応答 YAML、本 prompt §2.4 で固定) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (manifest 正本)**: 判定基準（required_pkg / fail_count_max）は `workflow-manifest.json completion_signals` のみが正本
  - **目的**: 判定根拠の単一情報源を維持するため
  - **背景**: 複数箇所定義は drift と CI failure の温床
- **CONST_002 (緩和は governance 必須)**: `fail_count_max` を 0 以外にする変更は 27章 §4.1 governance 必須
  - **目的**: 品質基準の独断緩和を防ぐため
  - **背景**: proposer ≠ approver 原則 (23章)
- **CONST_003 (予約 ID 除外)**: PKG-016/017 は予約 ID のため判定対象外
- **CONST_004 (PKG-013 は集約済単一キー)**: run_report 上 PKG-013 は単一キーで届く。a/b/c/d の all_must_pass 集約は上流 `validate-plugin-permissions.py`（per-log `sub_checks` に a/b/c/d 明細を保持）が実施し、`aggregate-pkg-findings.py` が単一 `PKG-013` status として surface する。本 prompt は再集約せず単一 `PKG-013` status を消費する
  - **目的**: permission check の部分 pass を誤承認しないため（集約は上流で完了済）
  - **背景**: a/b/c/d は権限の異なる側面を検査し独立では不十分。展開・集約責務は本 prompt でなく上記 2 script にあり、run_report は単一 `PKG-013` キーのみ持つ

### 1.2 倫理ガード

- proposer ≠ approver（23章）: 本 prompt は判定者、改善実行は別 skill
- force_pass 禁止（fail 件数 > fail_count_max は必ず FAIL）

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: phase 別の `required_pkg` と `fail_count_max` を照合し PASS/FAIL を返す
- 非担当: PKG check 実行（R1 orchestrate）、改善実行、governance 起票

### 2.2 ドメインルール

- **Phase 0 完了**: required = [PKG-001..009]、fail_count_max = 0。PKG-001 が skip（claude CLI 不在）でも PASS 許容
- **Phase 1 完了**: Phase 0 PASS + PKG-010 pass
- **Phase 2 完了**: Phase 1 PASS + PKG-011/012/013/014/015 が全 pass / not_applicable。`PKG-013` は a/b/c/d を all_must_pass 集約した単一キー。manifest `completion_signals.phase_2` は原子 ID として PKG-013a/b/c/d を列挙するが、run_report では単一 `PKG-013` キーへ対応づけて 1 件として判定する
- `skill-only` plugin は PKG-002/004 のみ判定対象
- 全 PKG ID の status が `pass` or `not_applicable` で fail = 0 が PASS の必要十分条件（PKG-001 例外あり）

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| `phase` | enum | yes | `0` / `1` / `2` |
| `run_report` | object | yes | R1 が出力した `schemas/run-report.schema.json` 準拠 JSON |
| `package_mode` | enum | no | `bundle` / `skill-only`、default `bundle` |

### 2.4 出力契約

応答は以下の YAML 構造に固定（additionalProperties 禁止）:

```yaml
phase: <0|1|2>
verdict: PASS|FAIL
failed_pkg_ids: [<PKG-NNN>, ...]
skipped_pkg_ids: [<PKG-NNN>, ...]
not_applicable_pkg_ids: [<PKG-NNN>, ...]
exemptions:
  - pkg_id: <ID>
    reason: <e.g., "PKG-001 skip (claude CLI 不在), Phase 0 PASS 許容">
next_action: |
  <FAIL 時のみ: 修正対象 PKG ID と次に取るべきコマンド>
```

- `*_pkg_ids` は run_report `pkg_checks` の集約キー（PKG-001〜015、permission は単一 `PKG-013`）で表現し、a/b/c/d suffix は用いない。PKG-013 の a/b/c/d 明細は per-log `sub_checks` を参照（本 prompt の入力 run_report には含まれない）

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| manifest | `workflow-manifest.json` | `completion_signals.phase_{0,1,2}` を一次情報として読込 |
| catalog | `../ref-pkg-contract/references/pkg-id-catalog.yaml` | PKG ID メタ参照（phase 対応確認） |
| chap27 | `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` §4.1 | governance escalation 経路 |
| chap34 | `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` Phase 0/1/2 | phase 定義の正本 |

### 3.2 外部ツール / API

- なし（pure decision logic、副作用なし）

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- 入力 schema 違反 → exit 2 + `error: invalid_run_report`
- `run_report.pkg_checks` に required_pkg の一部が欠落 → exit 2 + `error: incomplete_run_report`
- 判定結果 FAIL → exit 0（FAIL は処理成功であり、`verdict: FAIL` を返す）
- structural error（manifest 不在）→ exit 3

### 4.2 観測 / ロギング

- 副作用なし（pure function）
- 35章 observable emit はしない（R1 配下 aggregate-pkg-findings.py の責務）

### 4.3 セキュリティ

- secret 取扱なし
- 入力 run_report は事前 schema validation 済み前提

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- run-plugin-package-check skill 直接呼出（context-fork 不要、pure decision）

### 5.2 ゴール定義

- **目的**: phase 別の `required_pkg` / `fail_count_max` と run_report を照合し、PASS/FAIL の客観判定 YAML を返す
- **背景**: 判定基準は workflow-manifest.json が単一情報源。複数定義は drift を生むため、本 prompt は照合のみを担う pure decision
- **達成ゴール**: §2.4 YAML 構造体が manifest の completion_signals に整合し、`verdict` / `failed_pkg_ids` / `exemptions` / FAIL 時の `next_action` が矛盾なく確定した状態

### 5.3 完了チェックリスト (ゴール到達の唯一の停止条件)

- [ ] manifest の `completion_signals.phase_{phase}` を直接参照（判定基準を本 prompt 内で再定義していない）
- [ ] `package_mode=skill-only` で required_pkg を PKG-002/004 のみに絞込
- [ ] PKG-013 は集約済単一キーとして status を参照し（a/b/c/d 全 pass は上流 `validate-plugin-permissions.py` が status に反映済）、manifest の PKG-013a/b/c/d 要求を run_report の単一 `PKG-013` キーへ対応づけて判定した
- [ ] PKG-001 が `status: skip` + `skip_reason` に `"claude CLI not found in PATH"` (claude CLI 不在。`run-plugin-validate-strict.sh` の出力値が正本) を持つとき Phase 0 で `exemptions[]` に明示
- [ ] `failed_pkg_ids.length <= fail_count_max` かつ全 required_pkg が `pkg_checks` に存在のとき `verdict: PASS`
- [ ] FAIL 時 `next_action` が空でなく、修正対象 PKG ID と次に取るべきコマンドを含む
- [ ] `verdict` が `PASS` / `FAIL` のいずれか（force_pass 禁止）
- [ ] 副作用なし（pure function を維持）

### 5.4 実行方式 (固定手順を持たないゴールシークループ)

- 方針: 固定手順を列挙しない。§5.2 ゴール定義と §5.3 完了チェックリストを唯一の指針とし、入力 `phase` / `run_report` / `package_mode` の組合せに応じて必要な照合手順を都度設計する
- ループ:
  1. §5.3 の未充足項目を特定する
  2. 未充足を解消する手順を立案（入力 schema 検証 / manifest 読込 / required_pkg 絞込 / PKG-013a〜d 要求の単一 `PKG-013` キー対応づけ（集約は上流 script 済） / PKG-001 例外抽出 / verdict 集計 / next_action 生成 等から必要なものを選択）
  3. 立案手順を実行し §2.4 YAML 構造体を更新
  4. §5.3 で自己評価し全項目充足まで反復（上限: Layer 4 最大反復）
- 逸脱時: required_pkg 欠落 / structural error は §4.1 に従い exit 2 / 3 で停止

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-plugin-package-check/R1 orchestrate` (Step 10 verdict 出力の直前判定)、CI/CD pipeline
- 後続 phase: PASS なら次 phase Step、FAIL なら呼出元が改善経路（governance / skill-create 戻り）を選択

### 6.2 並列性

- 完全並列可（pure function / no side effect / 同入力→同出力）

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 機械可読 YAML（§2.4 構造体）
- 上位 skill が markdown レポートに整形する想定

### 7.2 言語

- 本文: 日本語、`verdict` enum / PKG ID / key は英語

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{phase}}` / `{{run_report}}` / `{{package_mode}}` を受け、Layer 5.2 ゴール定義と §5.3 完了チェックリストを停止条件とし、§5.4 ゴールシークループに従い照合手順を動的生成・実行する。最終的に Layer 2.4 の YAML 構造体のみを stdout に出力する。前置き・後書き・思考過程出力は禁止。exit code は §4.1 に従う。
