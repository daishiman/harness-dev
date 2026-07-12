---
name: assign-plugin-package-evaluator
description: 36章 PKG-002〜008 sub-check を実行したいとき、plugin package の静的検査結果を findings JSON で得たいときに使う。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Glob, Grep, Bash(python3 *)]
pair: run-plugin-package-check
kind: assign
prefix: assign
effect: conversation-output
role_suffix: evaluator
owner: team-platform
since: 2026-05-23
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md
source-tier: internal
last-audited: 2026-05-23
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-run-pkg-check.md
schema_refs:
  - schemas/findings.schema.json
  - ../ref-pkg-contract/schemas/package-contract.schema.json
script_refs:
  - scripts/validate-plugin-package.py
  - scripts/render-pkg-findings.py
reference_refs:
  - references/evaluator-contract.md
rubric_refs:
  - ref-pkg-contract
---

# assign-plugin-package-evaluator

## Purpose & Output Contract

36章 Plugin Package Harness Contract の **PKG-002〜008 sub-check** を実装する worker skill。`run-plugin-package-check`（B）から呼ばれ、`plugins/<plugin>/` を入力に findings JSON を返す。PKG-001（公式 CLI ラッパー）/ PKG-009（外部参照）/ PKG-010〜015 は B が直接実装するため本 skill は静的検査の中核 7 件に責務を絞る。

**入力**:
```yaml
target_plugin: "harness-creator"             # 必須。plugins/<name>/ の name
pkg_ids: ["PKG-002", "PKG-003", "PKG-004", "PKG-005", "PKG-006", "PKG-007", "PKG-008"]
options:
  fail_fast: false                          # true なら最初の FAIL で停止
  output_path: "eval-log/<plugin>/pkg-<id>/<date>-<run>.json"
  render: markdown                          # 任意。指定時のみ render-pkg-findings.py で markdown サマリも出力
```

**出力**: `schemas/findings.schema.json` 準拠の findings 配列 + verdict サマリ
**完了条件**: 全 PKG ID で `status ∈ {pass, fail, skip, not_applicable}` が確定し、eval-log に保存されること

## Key Rules

1. **PKG ID 定義は ref-pkg-contract 経由**: 本 skill 内で PKG ID 表を再定義しない（DRY、33章準拠）
2. **findings の thought_method フィールドは不要**: 本 skill は規範的静的検査であり、思考法多視点レビュー（run-elegant-review）とは責務直交
3. **package_mode による適用判定**: `skill-only` plugin に対しては PKG-003/005/006/007/008 を `not_applicable` として返す（PKG-002/004 のみ実行）
4. **fail_fast=false 既定**: 全 PKG ID を走らせて findings を網羅収集
5. **eval-log パスは 27章 §3.1**: 本 skill で再定義しない
6. **schema 違反は exit 2**: validator スクリプト自体の入力 schema 違反は P0 として即停止
7. **context: fork 必須**: 親 context の sycophancy 排除（assign-skill-design-evaluator と同じポリシー）

## ゴールシーク実行

evaluator は一度の採点で完結する read-only 工程。ループは回さず、**採点の網羅性をチェックリストで担保**する。正本: `../run-build-skill/references/goal-seek-paradigm.md`（§評価系の扱い）。

### ゴール (Goal)

指定された全 PKG ID（既定 PKG-002〜008）を採点し、各 finding にエビデンスと severity を付与、全件の `status ∈ {pass, fail, skip, not_applicable}` が確定して `schemas/findings.schema.json` 準拠の findings JSON + verdict サマリが eval-log に返された状態になっている。

### 目的・背景 (Why)

契約適合（PKG check）の中核 7 件を静的検査する worker。採点漏れがあると親 orchestrator の verdict が偽陽性 PASS になるため、規範採点や思考法レビューと直交した「全 rubric 項目の網羅採点」が要る。`context: fork` で親 context の sycophancy を排除する。

### 完了チェックリスト (Checklist)

- [ ] 入力 `pkg_ids` の全項目を採点した（未採点 ID が 0 件）
- [ ] `package_mode=skill-only` の場合 PKG-003/005/006/007/008 を `not_applicable` 判定にした
- [ ] 各 finding に `location` と `evidence`（観測根拠）と `severity` が付与されている
- [ ] 全 PKG ID で `status` が確定し、verdict カウント（total/pass/fail/skip/not_applicable）が算出済み
- [ ] 出力が `schemas/findings.schema.json` に準拠する（schema 違反は exit 2）
- [ ] `exit_code != 0` でも findings JSON は stdout へ必ず出力した

### 採点フロー

`Step N:` の固定連番は使わない。チェックリストの未充足項目に応じ、`scripts/validate-plugin-package.py --check pkg-<id> --plugin <name>` を必要な PKG ID 分だけ実行し findings を集約、最後に verdict を算出して schema 検証で締める。

## PKG-002〜008 sub-check 詳細

| PKG ID | 検査関数 | fail 条件例 |
|---|---|---|
| PKG-002 | `validate_plugin_json_frontmatter` + `validate_package_contract` | 公式 `plugin.json` の `name`/`version`/`description`、または `references/package-contract.json` の `package_mode`/`entry_points` のいずれか欠落 |
| PKG-003 | `validate_namespace_conflict` | 同一 marketplace 内で skill/agent/hook/permission 名が重複 |
| PKG-004 | `validate_skill_frontmatter` | 03章必須キー欠落、`responsibility_refs`/`schema_refs`/`manifest` 不在 |
| PKG-005 | `validate_agent_definition` | `agents/*.md` の name と `subagent_refs` 不一致 |
| PKG-006 | `validate_hook_registration` | hook ファイル未登録、または登録だけあって実ファイル不在 |
| PKG-007 | `validate_script_present_executable` | 参照 script が存在しない、shebang 欠落、`+x` ビットなし |
| PKG-008 | `validate_settings_fragment` | 34a 章 INV-1〜12 違反、Layer3 衝突 |

各検査は `scripts/validate-plugin-package.py --check pkg-<id> --plugin <name>` 単独実行可能。B からは sub-process でまとめて呼ばれる。

## findings 出力フォーマット

```json
{
  "run_id": "pkg-validate-harness-creator-20260523-001",
  "target_plugin": "harness-creator",
  "package_mode": "bundle",
  "pkg_checks": {
    "PKG-002": {
      "status": "pass",
      "findings": [],
      "last_run_at": "2026-05-23T12:00:00Z"
    },
    "PKG-006": {
      "status": "fail",
      "findings": [
        {
          "id": "F-PKG006-001",
          "pkg_id": "PKG-006",
          "severity": "P0",
          "location": "plugins/harness-creator/hooks/pre-commit.sh",
          "evidence": "hook ファイル実体は存在するが settings 断片の hooks 配列に未登録",
          "suggested_fix": "plugins/harness-creator/settings/hooks.json の hooks 配列に追加"
        }
      ],
      "last_run_at": "2026-05-23T12:00:01Z"
    }
  },
  "verdict": {
    "total": 7,
    "pass": 6,
    "fail": 1,
    "skip": 0,
    "not_applicable": 0
  }
}
```

## Gotchas

1. **`scripts/validate-plugin-completeness.py` との関係**: 既存スクリプトは plugin 完全性の総合検査。本 skill の `validate-plugin-package.py` は **PKG ID 別 sub-command** で findings 形式を返す点が異なる。既存をラップせず別実装にする（責務分離）
2. **PKG-001/009 は本 skill 対象外**: B 側で直接実装。本 skill に投げられたら `unsupported_pkg_id` エラーを返す
3. **PKG-010〜015 も対象外**: smoke/permission/runtime 検査は別 skill（B が直接 or 専用 assign）
4. **`skill-only` plugin への PKG-003 適用は禁止**: 名前空間検査は bundle のみ。skill-only に投げられたら `not_applicable` を返す
5. **`exit_code != 0` でも findings は必ず JSON 出力**: stderr に進捗ログ、stdout に findings JSON 厳守

## Additional Resources

- `scripts/validate-plugin-package.py` — PKG-002〜008 sub-command 実装
- `scripts/render-pkg-findings.py` — findings JSON → 人間可読 markdown レポート
- `schemas/findings.schema.json` — findings JSON 出力 schema
- `prompts/R1-run-pkg-check.md` — R1 単発検査時の応答テンプレ
- `ref-pkg-contract` — PKG ID 表・package-contract schema の正本参照
- 設計書: 36章（正本）、34a §4（PKG-003 共有名前空間）、03章（PKG-004 frontmatter 必須キー）
