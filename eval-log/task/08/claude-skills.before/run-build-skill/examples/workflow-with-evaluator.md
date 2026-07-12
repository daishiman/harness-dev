---
name: run-example-doc-builder
description: Build a doc page. Use when the user asks to scaffold docs, or when refreshing existing docs.
disable-model-invocation: false
allowed-tools: [Read, Write, Edit, Skill(assign-example-doc-evaluator *)]
pair: assign-example-doc-evaluator
kind: run
owner: team-skills
since: 2026-05-17
---

# run-example-doc-builder

## Purpose & Output Contract
Markdown docページを生成し evaluator で採点。

## Key Rules
1. 評価は fork コンテキストで実行。

## Steps
### Step 1
雛形展開 → 内容追記 → evaluator 呼出 → 80点未満なら修正。

## Gotchas
- 自己採点禁止。

## Additional Resources
- pair: assign-example-doc-evaluator
