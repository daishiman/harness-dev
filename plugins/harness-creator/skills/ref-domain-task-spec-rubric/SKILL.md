---
name: ref-domain-task-spec-rubric
description: タスク仕様書ドメイン用L1 rubricを参照したいとき、Phase 1-13/SRP/ユビキタス言語の評価基準を確認したいときに使う。
user-invocable: false
disable-model-invocation: true
allowed-tools: [Read]
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-05-19
version: 0.1.0
merge_strategy: deep-merge
conflict_policy: most-specific-wins
source: doc/ClaudeCodeスキルの設計書/29-multi-project-rubric-composition.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-search-summarize.md
---

# ref-domain-task-spec-rubric

## Purpose & Output Contract

設計書29 §3 の3層階層モデル (L0 共通 / L1 ドメイン / L2 プロジェクト) における **L1 (タスク仕様書ドメイン特化)** rubric。L0 (`ref-skill-design-rubric`) を upstream に継承し、タスク仕様書ドメイン固有のルール (Phase 1-13 整合、SRP、ユビキタス言語) のみを追加する。L2 (各 evaluator) からは upstream として参照される中間層。

**入力**: なし (参照型 Skill)
**出力**: `references/rubric.json` (L1 rubric 実体)
**完了条件**: 派生 evaluator が `upstream` チェーンを通じて本 rubric を解決できること。

## Key Rules

1. **L0 を upstream に固定**: `upstream: ["plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"]`
2. **layer: L1 固定**: L0 / L2 への混在禁止
3. **rules はタスク仕様書ドメイン固有のものに限定**: L0 と重複する rule (FM-001 等) を再記述しない (deep-merge で自動継承)
4. **registry 登録必須**: `plugins/skill-governance-config/config/rubric-registry.json` の `rubrics[]` に登録

## Steps

### Step 1: rubric.json を参照する

L2 evaluator は `references/rubric.json` の `upstream` に本ファイル (`plugins/harness-creator/skills/ref-domain-task-spec-rubric/references/rubric.json`) を指定する。`compose-rubrics.py` が deep-merge を解決する。

### Step 2: ドメイン固有 rule を追加する

Phase 1-13 整合、SRP 分解粒度、ユビキタス言語整合などタスク仕様書固有の評価軸のみを追加する。汎用 rule は L0 に置く。

### Step 3: rubric hash の検証

`compute-rubric-hash.py` でハッシュを再生成し、registry に記録された値と一致することを確認する。

## Related

- [[ref-domain-rubric-template]] (L1 抽象テンプレート)
- [[ref-skill-design-rubric]] (L0 共通 rubric)
- [[run-skill-rubric-governance]] (rubric 改正フロー)
