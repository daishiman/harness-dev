# role-suffix 語彙の正本

第17条で定める Skill 名末尾の役割サフィックス（role-suffix）の正式語彙とその用途。
新規 suffix の追加は governance board 承認（27章）を経ること。

## 正式語彙

| suffix         | 用途・意味                                                         | 典型 prefix                | 例                                         |
|----------------|----------------------------------------------------------------|--------------------------|-------------------------------------------|
| `-evaluator`   | 採点・評価。rubric に従って findings + score を出す                  | `assign-` / `run-`        | `assign-skill-design-evaluator`            |
| `-generator`   | 新規生成。テンプレ展開や雛形作成を担う                                 | `run-` / `assign-`        | `run-skill-generator`（仮）                |
| `-linter`      | 規約・静的ルール違反検出。pass/fail のみ、修正はしない                  | `assign-` / `run-`        | `assign-naming-linter`                     |
| `-auditor`     | 監査。証跡を残す検査、結果は通常 read-only                              | `assign-` / `run-`        | `assign-rubric-auditor`                    |
| `-aggregator`  | 複数 findings / score の集約・統合                                  | `run-`                    | `run-elegant-findings-aggregator`         |
| `-runbook`     | 手順書実行。governance / 改正 / リリース等の定型 runbook              | `run-`                    | `run-skill-rubric-governance`（runbook 系）|
| `-watcher`     | 観察・監視。状態変化や逸脱検知を担う                                    | `run-`                    | `run-spec-drift-watcher`（仮）             |
| `-dispatcher`  | 振り分け・委譲。条件で別 Skill / agent に橋渡し                       | `delegate-` / `wrap-`      | `delegate-task-dispatcher`（仮）           |

## prefix × suffix の組み合わせ指針

- `run-*-runbook` / `run-*-aggregator` / `run-*-watcher`: workflow 系のメインフロー。
- `assign-*-evaluator` / `assign-*-linter` / `assign-*-auditor`: fork context・user-invocable: false が原則（04章）。
- `delegate-*-dispatcher` / `wrap-*-dispatcher`: 振り分け系ラッパ。
- `ref-*` は通常 role-suffix を付けず、対象ドメイン名で終わる（例: `ref-skill-naming-convention`）。

## 命名時のチェック

1. suffix は上表のいずれか、または明示的に省略（ref 系）。
2. prefix と suffix の意味が衝突しないこと（例: `ref-*-generator` は禁止：refは読み専用）。
3. 新 suffix を追加したい場合は 27章 amendment proposal を経由。
