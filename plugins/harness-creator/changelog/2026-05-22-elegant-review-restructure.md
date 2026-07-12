# 2026-05-22 elegant-review restructure

## 概要

run-elegant-review の内部構造を prefix-driven (run/assign/ref) で整理し、rubric placement を `references/rubric.json` に統一した。skill-creator 配下に蓄積基盤 (EVALS / changelog / lessons-learned) を新設。

## 変更 Skill

- ref-domain-rubric-template / ref-domain-task-spec-rubric / ref-skill-design-rubric: `rubric.json` を `references/rubric.json` へ移動。
- skill-governance-lint: rubric placement check を追加。
- skill-creator (plugin root): EVALS.json / changelog/ / lessons-learned/ を新設。

## 影響範囲

- `rubric-registry.json` 参照パスは未更新 (別 executor 担当)。
- run-* Skill のロジックは不変。

## 関連

- lessons-learned/2026-05-22-prefix-driven-internal-structure.md
