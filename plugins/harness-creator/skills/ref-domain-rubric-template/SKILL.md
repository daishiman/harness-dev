---
name: ref-domain-rubric-template
description: 新規ドメイン用L1 rubricを作成したいとき、ドメイン特化評価基準を雛形から派生させたいときに使う。
user-invocable: false
disable-model-invocation: false
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

# ref-domain-rubric-template

## Purpose & Output Contract

設計書29 §3 の3層階層モデル (L0 共通 / L1 ドメイン / L2 プロジェクト) における **L1 (ドメイン特化)** rubric の抽象テンプレート。`{{domain_name}}` 変数を実ドメインに置換するだけで新ドメインの L1 rubric が派生できる。

**入力**: domain_name (kebab-case、例: `task-spec`, `meeting-minutes`, `design-doc`)
**出力**: `plugins/harness-creator/skills/ref-domain-<domain_name>-rubric/references/rubric.json` (L1 rubric 実体)
**完了条件**: 派生 rubric が schema (version/layer/upstream/rules) を満たし、`plugins/skill-governance-config/config/rubric-registry.json` に登録されること。

## Key Rules

1. **L0 を upstream に固定**: 派生 rubric は必ず `upstream: ["plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"]` を含む。
2. **layer は L1 固定**: L0 / L2 への混在禁止 (設計書29 §10 アンチパターン)。
3. **rules は最低1件、ドメイン固有のものに限る**: L0 と重複する rule (FM-001 等) を再記述しない。重複は deep-merge で自動継承される。
4. **registry 登録必須**: `plugins/skill-governance-config/config/rubric-registry.json` の `rubrics[]` に新エントリを追加する。

## Steps

### Step 1: domain_name の決定

kebab-case で命名する。既存 rubric-registry.json の `rubrics[].domain` と衝突しないことを確認。

### Step 2: 雛形コピー

```bash
python3 - <<'PY'
from pathlib import Path
import shutil

domain = "task-spec"  # 例
src = Path("plugins/harness-creator/skills/ref-domain-rubric-template")
dst = Path(f"plugins/harness-creator/skills/ref-domain-{domain}-rubric")
shutil.copytree(src, dst)
PY
```

### Step 3: 変数置換

`references/rubric.json` 内の `{{domain_name}}` をすべて `$DOMAIN` に置換し、`rules` の TODO(human) を実ルールで埋める。

### Step 4: registry 登録

`plugins/skill-governance-config/config/rubric-registry.json` の `rubrics[]` に以下エントリを追加:

```json
{
  "domain": "<domain_name>",
  "layer": "L1",
  "rubric": "plugins/harness-creator/skills/ref-domain-<domain_name>-rubric/references/rubric.json",
  "description": "<one-line description>",
  "upstream": ["plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"]
}
```

### Step 5: 整合性検証

```bash
python3 plugins/skill-governance-lint/scripts/lint-rubric-refs-exist.py
python3 plugins/skill-governance-automation/scripts/compute-rubric-hash.py plugins/harness-creator/skills/ref-domain-${DOMAIN}-rubric/references/rubric.json
```

## Gotchas

- **L0 ルールの再記述禁止**: deep-merge が L0 から自動継承するため、L1 で書くと二重採点となる。
- **threshold_override は慎重に**: L0 の threshold=80 を緩める変更は governance 承認が必要 (設計書29 §10)。
- **conflict_policy は most-specific-wins 固定推奨**: error にすると L0 と key 衝突しただけで起動失敗する。

## Additional Resources

- `references/rubric.json` — L1 抽象テンプレート (変数化済み)
- 設計書29: `doc/ClaudeCodeスキルの設計書/29-multi-project-rubric-composition.md`
- 具体例: `plugins/harness-creator/skills/ref-domain-task-spec-rubric/references/rubric.json`
