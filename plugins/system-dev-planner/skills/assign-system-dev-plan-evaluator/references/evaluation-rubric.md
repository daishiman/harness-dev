---
name: system-dev-plan-evaluation-rubric
description: assign-system-dev-plan-evaluator が staging の exact-13 package を独立評価する 4 条件 rubric。proposer≠approver・digest 束縛・決定論優先を機械/意味の二層で判定する正本。
type: reference
version: 0.1.0
owner: team-platform
---

# system-dev-plan 4 条件評価 rubric

> `assign-system-dev-plan-evaluator` (C02) が `system-dev-plan-evaluator` (C05) を独立 context (`context: fork`) で起動して採点する際の判定正本。機械根拠は `scripts/validate-system-plan.py` の stdout/exit を先に通し、その後 LLM 意味判断を重ねる。被評価物 (staging) は改変しない。総合 verdict は 1 条件でも FAIL / validator 非 0 / digest 不在 / high finding のいずれかで **FAIL**。

## 評価対象と機械根拠

- 対象: staging 配下の `feature-package.json` / `workstream-inventory.json` / `task-specs/phase-01..13-*.md` / `task-graph.json` / `system-build-handoff.json` / `staging-manifest.json`。
- 機械根拠 (先行): `python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-system-plan.py" --repo-root <root> --staging <relative>` の `status`(pass/fail) / `validated_digest` / `violations[]`。
- 出力: `plan-findings.json` (schema=`schemas/plan-findings.schema.json`)。`evaluated_digest` に validator の `validated_digest` をそのまま pin し、`evaluator.context=fork` を記録。

## 4 条件 (C1..C4) の判定基準

| 条件 | PASS の必要十分 | FAIL シグナル | 主な機械根拠 |
|---|---|---|---|
| **C1 矛盾なし** | task 群・inventory・graph・handoff が相互に矛盾せず、feature-context の goal/scope と齟齬しない。単一 `parent_feature`/`feature_package` に束縛。 | phase 間で相反する acceptance / scope 逸脱 / parent_feature 不一致 | validate: single-parent/package 検査, 意味: 章跨り整合 |
| **C2 漏れなし** | P01..P13 の exact-set (各 1 件・14 件目なし) が揃い、`task_count==13`、placeholder (TODO 等) 0、必須フィールド充足。 | phase 欠落 / 重複 / task_count≠13 / placeholder 残置 / required field 欠落 | validate: exact-set/count/placeholder/inventory-schema |
| **C3 整合性あり** | 命名・phase_ref・task_spec_paths が正本 (`system-plan-phase-names.md`) と一致し、workstream 語彙が schema enum 内。 | phase 名 drift / task path 不一致 / 語彙 enum 外 | validate: PHASES/TASK_PATHS 照合, 意味: 命名規約 |
| **C4 依存関係整合** | intra-feature DAG が前方・非循環で、node/edge が実在 task を指し、source_lineage が接地。 | 循環 / dangling 参照 / 逆向き辺 / lineage 不在 | validate: DAG acyclic/node 実在 |

## 不変ルール (Goodhart 対策)

- **proposer ≠ approver**: 生成時の推論・期待 verdict を渡さない。独立 context (`fork`) で採点する。自己評価の追認 (Sycophancy) を機構で排除。
- **決定論優先**: `validate-system-plan.py` を先に通し exit/violations を根拠化してから意味判断する。script 非 0 は即 FAIL。
- **digest 束縛**: `evaluated_digest` を validator の `validated_digest` に固定。digest 不在・不一致は FAIL。別 digest の verdict/receipt を再利用しない。
- **無改変**: 被評価物 (staging/task-specs) を一切書き換えない。指摘は `plan-findings.json` の `findings[]` に載せ C01 へ差し戻す。
- **severity ゲート**: high finding が 1 件でもあれば、個別条件が PASS でも総合 verdict=FAIL。

## verdict 決定 (決定論規則)

```
verdict = PASS  ⇔  validator.status == "pass"
                  ∧ validated_digest 実在
                  ∧ C1..C4 すべて PASS
                  ∧ high severity finding 数 == 0
それ以外は FAIL
```

正本の交差参照: 出力 schema=`schemas/plan-findings.schema.json` / 評価対象契約=`references/feature-execution-package-contract.md` / 責務 7 層プロンプト=`prompts/R4-evaluate.md`。
