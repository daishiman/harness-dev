---
id: "P05-x-38-lint-glob-coverage"
title: "skill-governance-lint の検査対象へ guide-doc-generator を含める"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/skill-governance-lint/"
acceptance_criterion: "SKILL_GLOBS が guide-doc-generator の skills/agents を含み、CI の既定実行で本 plugin が検査される"
objective: "lint-skill-description.py:57 の SKILL_GLOBS は harness-creator/skills と .claude/skills と .claude/agents の 3 本のみで plugins/guide-doc-generator/ を含まない。3 glob の実ヒット 33/91/67 件に handout 系は 0 件。出荷 5 skill + 2 agent へ importlib で直接 check() を当てると全件 ok だが、これはゲートが守った結果ではなく一度も検査されていない結果である"
verify: "SKILL_GLOBS が guide-doc-generator の skills/agents を含み、CI の既定実行で本 plugin が検査される"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-38-lint-glob-coverage.md"]
consumes: []
---

# skill-governance-lint の検査対象へ guide-doc-generator を含める

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: lint-skill-description.py:57 の SKILL_GLOBS は harness-creator/skills と .claude/skills と .claude/agents の 3 本のみで plugins/guide-doc-generator/ を含まない。3 glob の実ヒット 33/91/67 件に handout 系は 0 件。出荷 5 skill + 2 agent へ importlib で直接 check() を当てると全件 ok だが、これはゲートが守った結果ではなく一度も検査されていない結果である

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/skill-governance-lint/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-38-lint-glob-coverage.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

SKILL_GLOBS が guide-doc-generator の skills/agents を含み、CI の既定実行で本 plugin が検査される
