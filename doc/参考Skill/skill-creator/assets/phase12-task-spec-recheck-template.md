# Phase 12 タスク仕様準拠再確認テンプレート

> **用途**: Phase 12 の再監査で、「成果物は存在するが task spec 準拠か不明」な状態を短手順で潰す。
> **使い分け**:
> - task spec 準拠の再確認が主目的なら本テンプレートを先に使う
> - Step 2 の広い仕様更新まで含むなら `phase12-system-spec-retrospective-template.md` へ展開する
> - 仕様書ごとの分担表を明示したい場合は `phase12-spec-sync-subagent-template.md` と併用する

---

## 1. メタ情報

| 項目 | 値 |
| --- | --- |
| タスクID | `<TASK-ID>` |
| workflow | `<docs/30-workflows/...>` |
| 実施日 | `YYYY-MM-DD` |
| ステータス | `completed` / `spec_created` |
| 対象未タスク | `<docs/30-workflows/unassigned-task/...>` |

---

## 2. SubAgent分担（4点突合専用）

| SubAgent | 関心ごと | 主担当 | 完了条件 |
| --- | --- | --- | --- |
| SubAgent-A | workflow状態 | `phase-12-documentation.md` と `outputs/phase-12/` の実体突合 | `completed` / Task 12-1〜12-5 / Task進捗100% が一致 |
| SubAgent-B | 実装ガイド品質 | `implementation-guide.md` の必須要素確認 | `Part 1 / Part 2`、理由先行、日常例え（`たとえば` 明示）、型/API/エッジケース/設定が揃う |
| SubAgent-C | 未タスク整合 | 物理配置、10見出し、links/audit 確認 | `docs/30-workflows/unassigned-task/` 配置 + `currentViolations=0` |
| SubAgent-D | system spec同期 | `task-workflow.md` / `lessons-learned.md` へ実装内容と苦戦箇所を転記 | 検証値と5分解決カードが同値で同期 |
| SubAgent-E | 成果物同期 | `system-spec-update-summary` / `phase12-task-spec-compliance-check` / `unassigned-task-detection` へ実測値を同期 | system spec と outputs の値が一致 |

---

## 3. 4点突合チェック

### 3.1 `phase-12-documentation.md` と `outputs/phase-12`

- [ ] `phase-12-documentation.md` の `ステータス=completed`
- [ ] Task 12-1〜12-5 がすべて `[x]`
- [ ] Task進捗が `100%`
- [ ] `outputs/phase-12/` に canonical 7成果物が存在
- [ ] `system-spec-update-summary.md` / `documentation-changelog.md` / `unassigned-task-detection.md` / `skill-feedback-report.md` / `implementation-guide.md` が実体化

### 3.2 `implementation-guide.md`

- [ ] `## Part 1` がある
- [ ] `## Part 2` がある
- [ ] 理由先行 (`なぜ` / `必要`) がある
- [ ] 日常例え（`たとえば` / `例え`）がある
- [ ] 型 (`type` / `interface`) がある
- [ ] 論理 API がある
- [ ] エッジケースがある
- [ ] 設定値・基準値がある

### 3.3 未タスク指示書

- [ ] `docs/30-workflows/unassigned-task/` 配下に物理ファイルがある
- [ ] `## メタ情報 + ## 1..9` の10見出し
- [ ] `verify-unassigned-links` が `missing=0`
- [ ] `audit --json --diff-from HEAD --target-file <unassigned-file>` が `currentViolations=0`
- [ ] `audit --json --diff-from HEAD` が `currentViolations=0`
- [ ] `audit --json` 単独の repo 全体値は参考値として分離している
- [ ] `currentViolations=0` かつ `baselineViolations>0` の場合、`unassigned-task-detection.md` に既存 backlog と remediation task 参照がある

### 3.4 system spec / outputs 同期

- [ ] `task-workflow.md` に実装内容・苦戦箇所・検証証跡・5分解決カードがある
- [ ] `lessons-learned.md` に再発条件付き苦戦箇所と簡潔解決手順がある
- [ ] `system-spec-update-summary.md` / `phase12-task-spec-compliance-check.md` / `unassigned-task-detection.md` に system spec と同じ実測値がある
- [ ] `phase12-task-spec-compliance-check.md` が root evidence として同じ値を持つ
- [ ] UIタスクでは `phase-11-manual-test.md` に `## 画面カバレッジマトリクス` がある

---

## 4. 検証コマンド

```bash
node .claude/skills/task-specification-creator/scripts/verify-all-specs.js --workflow <workflow-path> --json
node .claude/skills/task-specification-creator/scripts/validate-phase-output.js <workflow-path>
node .claude/skills/task-specification-creator/scripts/validate-phase11-screenshot-coverage.js --workflow <workflow-path>
rg -n '^\| ステータス \| completed' <workflow-path>/phase-12-documentation.md
rg -n '^- \[x\] Task 12-[1-5]' <workflow-path>/phase-12-documentation.md
rg -n '## Part 1|## Part 2|なぜ|必要|例え|たとえば|interface|type|API|エッジケース|設定' <workflow-path>/outputs/phase-12/implementation-guide.md
rg -n '^## 画面カバレッジマトリクス$' <workflow-path>/phase-11-manual-test.md
node .claude/skills/task-specification-creator/scripts/verify-unassigned-links.js
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD --target-file <unassigned-file>
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json --diff-from HEAD
node .claude/skills/task-specification-creator/scripts/audit-unassigned-tasks.js --json
rg -n '^## メタ情報$|^## [1-9]\. ' <unassigned-file>
node .claude/skills/skill-creator/scripts/quick_validate.js .claude/skills/skill-creator
node .claude/skills/skill-creator/scripts/quick_validate.js .claude/skills/task-specification-creator
node .claude/skills/skill-creator/scripts/quick_validate.js .claude/skills/aiworkflow-requirements
```

---

## 5. 最適なファイル形成

### 5.1 記述順序

1. `task-workflow.md`
2. `lessons-learned.md`
3. `outputs/phase-12/system-spec-update-summary.md`
4. `outputs/phase-12/phase12-task-spec-compliance-check.md`
5. `outputs/phase-12/unassigned-task-detection.md`
6. `outputs/phase-12/documentation-changelog.md`
7. `outputs/phase-12/skill-feedback-report.md`

### 5.2 同期する値

- `verify-all-specs`: `13/13, error=0, warning=0` 形式
- `validate-phase-output`: `28項目, error=0, warning=0` 形式
- `validate-phase11-screenshot-coverage`: `expected=X / covered=X` 形式
- `verify-unassigned-links`: `existing / missing` 形式
- `audit --diff-from HEAD --target-file`: `currentViolations / baselineViolations`
- `audit --diff-from HEAD`: `currentViolations / baselineViolations`
- `audit --json`: repo 全体参考値
- `legacy remediation tasks`: 参照した既存未タスク指示書のパス一覧

---

## 6. 完了チェック

- [ ] 4点突合の担当 SubAgent が定義されている
- [ ] `phase-12-documentation.md` と `outputs/phase-12` の実体が一致している
- [ ] `implementation-guide.md` の必須要素が確認済み
- [ ] Part 1 の日常例えが `たとえば` を含んでいる
- [ ] 未タスクの個別合否に `audit --diff-from HEAD --target-file` を使っている
- [ ] repo 全体 `audit --json` を参考値として分離記録している
- [ ] `current=0` でも baseline backlog と既存 remediation task の参照を省略していない
- [ ] `task-workflow.md` / `lessons-learned.md` / `outputs/phase-12` の値が一致している
- [ ] `documentation-changelog.md` に今回の改善対象ファイルが列挙されている
- [ ] `skill-feedback-report.md` にテンプレート改善内容が記録されている
- [ ] UIタスクでは `## 画面カバレッジマトリクス` 見出しを固定している
