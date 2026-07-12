---
name: four-condition-criteria
description: 4条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) の詳細基準を確認したいとき、plan-findings の verdict を確定したいときに読む。
kind: reference
version: 0.1.0
owner: team-platform
since: 2026-06-30
source: plugins/plugin-dev-planner/skills/run-plugin-dev-plan/prompts/R4-verify-traceability.md
source-tier: internal
---

# 4条件 詳細基準 (plan 評価)

`plan-rubric.json` の機械判定を補う人間向け基準。plan-scoped 決定論ゲート (io-contract §11 の plan-scoped 集合) の exit code を一次根拠とし、意味判定は最小限に留める。

## C1 矛盾なし (no_contradiction)

plan 内の契約が相互に衝突しないこと。`check-build-handoff.py` exit0 (handoff routing の builder↔component_kind 整合) を決定論の一次根拠とし、残りは意味判定 (script では捕捉しにくい)。

- inventory component の `component_kind` と handoff route の builder/build_kind が整合するか (例: script kind を run-skill-create へ投入していないか — script は親 skill 付随物)。
- index の `plugin_meta` (manifest/marketplace/cachebuster) と inventory component の `quality_gates` / phase frontmatter の値が相反しないか。
- harness の `surfaces` と実体 capability が矛盾しないか。
- `distributable` フラグと bundles/marketplace 登録意図が整合するか。

**FAIL 例**: inventory component が `component_kind: script` なのに handoff route が run-skill-create/skill を指示している (builder↔component_kind 矛盾)。

## C2 漏れなし (no_missing)

必要な surface が必要性ベースで全評価され、不要なものは根拠付きで除外されていること。

- `detect-unassigned.py` exit0: 13 phase ファイル (P01..P13) が全存在し §5 section 床を満たす + inventory の各 component が ≥1 phase の `entities_covered` に出現 (orphan 0) し `build_target` が非空。
- `check-spec-frontmatter.py` exit0: 各 phase ファイルが PHASE_REQUIRED frontmatter を携帯 + 各 inventory component が `component_kind` 別構造契約を携帯。
- `check-spec-gates.py` exit0: inventory component が quality_gates + harness_coverage を値域まで携帯。
- **単一 skill 退化の検出**: `check-surface-inventory.py` が 5 component_kind の検討証跡と plugin-level surface (harness/manifest/composition/MCP 等) の required/omitted_reason を機械検査する。LLM は omitted_reason の意味妥当性のみ補助判定する。

**FAIL 例**: sub-agent / slash-command / hook / script component を不要とした根拠が goal-spec constraints または index の受入確認に無く、単一 skill plan が既定で通っている。

## C3 整合性あり (consistent)

用語・フォーマット・データ構造が統一されていること。

- `check-spec-matrix-coverage.py --self-test` exit0: マトリクス (harness-creator-spec-reflection.md) の行 ID 集合に drift がない (行数の正本は同 md)。
- `check-spec-matrix-coverage.py PLAN` exit0: 適用行の焼き先が反映され OP/conditional/N-A 内訳が整合。
- 用語 (component_kind / plugin_meta / quality_gates) が inventory component 間・phase ファイル間・index 間で同一語彙。

**FAIL 例**: ある inventory component が `quality_gates`、別 component が `quality-gates` (表記揺れ) を使う。

## C4 依存関係整合 (dependency_integrity)

タスク間・モジュール間の依存が正しく定義されていること。

- `verify-index-topsort.py` exit0: 層1 = index の `## フェーズ一覧` が P01..P13 を phase_number 昇順で全 13 列挙 (漏れ 0 / 重複 0)、層2 = inventory component 依存 DAG が非循環 (top-sort 可能)。
- `detect-unassigned.py` exit0: inventory の各 component が ≥1 phase の `entities_covered` に出現 (orphan 0) し `build_target` が非空。
- `check-build-handoff.py` exit0: handoff routes が inventory 由来で builder↔component_kind 整合・DAG top-sort 成立・envelope gap reason を満たす。
- `check-runtime-portability.py` exit0: 共有 script の plugin-root hoist + build_target の plugin 内自己完結 (install 携帯性)。
- 依存 DAG が inventory component (`depends_on`) 側で非循環、index は phase 軸で昇順。

**FAIL 例**: inventory の C02 が C03 に依存し C03 が C02 に依存する (component DAG 循環)。あるいは index の `## フェーズ一覧` が P04 を P03 より先に並べる (phase_number 昇順違反)。

## verdict 確定

| 条件 | PASS 条件 (gate は `plan-rubric.json` deterministic_gates が正本) |
|---|---|
| C1 | `check-build-handoff` exit0 かつ契約衝突 0 |
| C2 | `detect-unassigned` / `check-spec-frontmatter` / `check-spec-gates` / `check-surface-inventory` / `check-requirements-coverage` (goal-spec 要件→index の RTM 被覆) 全 exit0 かつ単一 skill 退化なし |
| C3 | `check-spec-frontmatter` / `check-spec-gates` / `check-spec-matrix-coverage --self-test` / `check-spec-matrix-coverage PLAN` 全 exit0 かつ語彙統一 |
| C4 | `verify-index-topsort` / `detect-unassigned` / `check-build-handoff` / `check-runtime-portability` 全 exit0 |

`global_thresholds`: high == 0 かつ medium <= 2 かつ all_gates_exit0 == true で全体 PASS。1 つでも high があれば全体 FAIL。
