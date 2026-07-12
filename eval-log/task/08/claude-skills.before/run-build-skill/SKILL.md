---
name: run-build-skill
description: 新規Skillを作成するとき、既存Skillを更新するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[skill-name] [kind?] [--mode create|update] [--with-subagent] [--with-evaluator] [--with-hooks] [--model opus|sonnet]"
arguments: [skill_name, kind, mode, with_subagent, with_evaluator, with_hooks, model]
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Skill(assign-skill-design-evaluator *)
pair: assign-skill-design-evaluator
kind: run
effect: local-artifact
owner: team-platform
since: 2026-05-17
script_refs:
  - scripts/render-frontmatter.py
  - scripts/validate-naming.py
  - scripts/build-subagent.py
  - scripts/validate-build-trace.py
reference_refs:
  - ref-skill-glossary
  - ref-task-context-map
  - ref-output-routing
# context-budget (CD-005): 章一括ロード禁止。必要な章のみ参照すること。
# max-reference-chapters: 3  # 同時に読む設計書章の上限
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# run-build-skill

> ※ creator-kit Phase 0 移行中は `creator-kit/skills/` が正本、`.claude/skills/` への配置は派生。本SKILL.mdは両配置で動作するよう self-relative パスを使用。

## Purpose & Output Contract

ユーザー要求からClaude Code Skillを1本構築するワークフロー。

**入力**: skill_name (kebab-case), kind (run|ref|assign|wrap|delegate),
         mode (create|update, デフォルト: create),
         with_subagent (フラグ、指定時のみStep7実行),
         model (opus|sonnet, デフォルト: opus)
**出力**:
- `$OUT_BASE/<name>/SKILL.md`（Phase 0 は `creator-kit/skills/`、移行後は `.claude/skills/` または plugin 配置。300行以下、frontmatter完備。本文はパラメーター名を除き日本語）
- 必要に応じ `templates/`, `references/`, `scripts/`, `examples/`
- `eval-log/skill-build-trace.json`（task→refs map、01aフロー、02/03/04/05/06/07/08/09/10/11/13/14/15/16/26/27/28/29/30/31/32/33/34/35 concern への対応証跡）
- assign-skill-design-evaluator による評価レポート (`eval-log/docs/<NN>-<timestamp>.json`) と `eval-log/<plugin>/<date>-score.jsonl` 追記

**完了条件**: rubric score >= 80 かつ high severity 0件。

## Key Rules

1. **300行制約**: SKILL.md本文は300行以下。超過分は `references/` へ分割（07章）。
2. **descriptionは発動条件のみ**: 動作詳細は本文化（08章）。
3. **triggerは2〜3個**: description内のUse when句は2〜3個の動詞ベース条件（08章 hard rule）。
4. **ディレクトリ名 == frontmatter.name**: 第8条。
5. **クロスプラットフォーム**: Mac/Linux は zsh/bash + python3 stdlib、Windows は PowerShell 5.1+ + python3 stdlib（設計書22章）。OS分岐は本文 `<important if="os=...">` で表現する。
6. **評価分離**: 生成本体は評価しない。`assign-skill-design-evaluator` をforkで呼ぶ（09章 Goodhart対策）。
7. **kindに応じたテンプレ選択**: 11章テンプレを `templates/` から展開。
8. **context予算制約 (CD-005)**: 全章一括ロード禁止。各Stepで必要な章のみ参照。
9. **--mode update**: 既存Skillへの増分改修。既存SKILL.mdを読んでdiffを適用する。
10. **モデル既定値**: build-subagent.py は --model opus で実行（PF-F3-001）。
11. **横展開候補は登録案を作る**: 生成物が Skill Creator 基盤、hook、lint、adapter、rubric、reference に該当する場合は `run-skill-create` の creator-kit 登録判定へ戻し、manifest更新をユーザー確認に委ねる。
12. **正本トレース必須**: 生成・更新ごとに task→refs map の選択、Intent / Contract / Boundary / Execution / Feedback、01a Step 1〜9、02 Skill構造、03 frontmatter、04 invocation/permissions、05 execution layer、06 classification/naming、07 progressive disclosure、08本文設計、09評価編成、10Subagent/Hook連携、11テンプレ適用、13チェックリスト/lint、14 dynamic injection、15公式参照追跡、16公式Skills仕様、26メタSkillドッグフーディング、27rubricガバナンス、28script実行モデル の対応を `skill-build-trace.json` に残す。
13. **実行レイヤー判断を固定化**: Skill / Subagent / Hook / MCP / CLI / script の配置理由を trace に記録し、決定論で落とせる検査は script/hook へ分離する。
14. **再現性ゲートは機械検証**: `scripts/validate-build-trace.py` で source_docs / build_flow_coverage / doc_coverage / layer_decisions / gates を検証し、空欄・未読・N/A理由なしを通さない。
15. **量産情報を消費する**: `pattern_refs` / `variant_axes` / `reuse_targets` / `deterministic_checks` / `placement_candidates` / `hook_events` を trace と生成本文へ反映し、未消費のまま捨てない。
16. **日本語成果物**: SKILL.md、SubAgent、review、完了レポートの説明文は日本語で作成する。frontmatterキー、JSONキー、CLI引数、テンプレート変数などのパラメーター名は英語のままでよい。
17. **26/27/28章ゲートを省略しない**: メタSkill、rubric、script、hook、subagent を生成・更新する場合は、設計書26/27/28章を読み、`dogfooding_model` / `governance_model` / `script_execution_model` を trace に記録する。対象外でも `N/A` と理由を残す。
18. **29〜35章を量産判断へ接続する**: skill creator / 量産 / 再現性 / rubric合成 / output routing / adapter / 類推理解 / creator-kit配布 / change governance / plugin境界 / meta-harness を含む場合は、設計書29〜35章と `references/skill-factory-reproducibility.md` を読み、`rubric_composition_model` / `paradigm_analogy_model` / `output_routing_model` / `implementation_ledger_model` / `change_governance_model` / `plugin_boundary_model` / `meta_harness_model` / `variable_contract` を trace に残す。対象外でも `N/A` と理由を残す。
19. **具体値は変数化する**: 再利用される Skill本文、SubAgent、テンプレート、config example には固定プロジェクト名、固定URL、固定owner、固定チャンネル名、固定secret service名を直書きしない。必要な具体値は `source_trace` に残し、成果物側は `{{PROJECT_ROOT}}` / `{{KIT_ROOT}}` / `{{DOMAIN}}` / `{{TASK_KIND}}` / `{{SECRET_NAMESPACE}}` などの変数で表現する。

## Steps

### Step 1: 要求ヒアリング

> **[MANDATORY - ch15/ch16 公式参照確認]** このステップの最初に `ref-yaml-spec-fetcher` を呼び出して
> `yaml-spec-cache.md` を Read すること。スキップは禁止。
> `validate-build-trace.py` が `15-official-source-notes` / `16-official-skills-reference` を検証し、
> 未実施の場合 exit 1 となる。
>
> ```
> Skill(ref-yaml-spec-fetcher)
> ```

- skill_name の kebab-case とprefix妥当性を確認 → `scripts/validate-naming.py`
- kind を確定（run/ref/assign/wrap/delegate）
- mode を確定（create / update、デフォルト: create）
- `references/resource-map.yaml` を最初に読み、task category と読む設計書を決める
- 01章の5要素（Intent / Contract / Boundary / Execution / Feedback）を1文ずつ埋める
- 01a Step 2 の実行レイヤー判断表で、Skill / Subagent / Hook / MCP / CLI / script の分担を決める
- 02章で配置スコープ / reference-task 境界 / Additional Resources を決める
- 03章で frontmatter の trigger 2〜3個、独自メタデータ、依存注入フィールドを決める
- 04章で `allowed-tools` と `permissions.deny` / hook の責務分離を決める
- 詳細仕様が不足する場合は `references/build-steps.md` を参照
- **context予算**: 設計書は `references/resource-map.yaml` が選んだものだけ読む。同時に読む設計書は原則3章以下。
- **章番号の事前特定**: task category から読むべき章番号を特定してから Read する (CD-005)。
- **メタSkill量産系の追加選定**: 要求に skill creator / rubric / governance / script / hook / subagent / dogfooding / 再現性 が含まれる場合、26/27/28章を優先候補に加える。3章上限を超える場合は、基礎章を `references/build-steps.md` の既読要約で代替し、26/27/28章を正本として読む。
- **L1 ドメイン rubric の解決**: `brief.domain` が指定されている場合、`creator-kit/config/rubric-registry.json` から該当 domain の L1 rubric パスを引き、`DOMAIN_RUBRIC_REFS` 環境変数に空白区切りで詰める。これが Step 5 の assign-evaluator 呼出時に `--rubric-refs` へ append される（設計書29、append-only）。未指定なら L0+L2 のみで採点（L1 スキップ）。
- **量産基盤の文脈選択**: 要求に skill creator / 量産 / 再現性 / rubric合成 / output routing / adapter / 類推理解 / テンプレート変数が含まれる場合は、task category を `skill-factory-reproducibility` にし、設計書29/30/31章と `references/skill-factory-reproducibility.md` を読む。3章上限を超える基礎章は `references/build-steps.md` の既読要約で代替する。

```bash
# brief.domain → L1 rubric 解決
DOMAIN="$(python3 -c "import json,sys; d=json.load(open('eval-log/skill-brief.json')); print(d.get('domain',''))")"
if [ -n "$DOMAIN" ]; then
  REGISTRY="${RUBRIC_REGISTRY_PATH:-creator-kit/config/rubric-registry.json}"
  DOMAIN_RUBRIC_REFS="$(python3 -c "
import json, sys
reg=json.load(open('$REGISTRY'))
print(' '.join(r['rubric'] for r in reg.get('rubrics',[]) if r['domain']=='$DOMAIN'))
")"
  export DOMAIN_RUBRIC_REFS
fi
```

### Step 2: テンプレ展開（create）/ 既存読込（update）

**kind → template 選択表**（COMPOSER_MODE=template の場合）:

| kind / role_suffix | 旧テンプレ (Phase 0) | atomic combinator (Phase 1) |
|---|---|---|
| `run` (workflow) | `templates/run.md` | `_base.md` + `with-run.patch` |
| `run` (agent-team 複合) | `templates/agent-team.md` | `with-run.patch` + `with-subagent.patch` |
| `run` (orchestrator 複合) | `templates/orchestrator.md` | `with-run.patch` + `with-subagent.patch`×N |
| `run` (hook-integrated 複合) | `templates/hook-integrated.md` | `with-run.patch` + `with-hooks.patch` |
| `ref` | `templates/ref.md` | `_base.md` + `with-ref.patch` |
| `assign` + `role_suffix=generator` | `templates/assign-generator.md` | `with-assign-generator.patch` (+ `with-evaluator.patch`) |
| `assign` + `role_suffix=evaluator` | `templates/assign-evaluator.md` | `with-assign-evaluator.patch` |
| `wrap` | `templates/wrap.md` | `_base.md` + `with-wrap.patch` |
| `delegate` | `templates/delegate.md` | `_base.md` + `with-delegate.patch` |

`COMPOSER_MODE="atomic"` を選択した場合は kind-specific combinator を必ず 1 つ適用し、flag combinator を 0〜N 個重ねる（順序固定: kind → flag）。詳細は `templates/combinators/README.md`。

**create モード**:

OS判定プリアンブル（設計書22）:
```
!`uname -s 2>/dev/null || ver`
```

<important if="os=mac,os=linux">
```bash
# パス解決ロジックを外部スクリプトに移譲 (300行 cap 対策)
# SKILL_DIR / OUT_BASE を確立する
source creator-kit/scripts/resolve-skill-dirs.sh
mkdir -p "$OUT_BASE/$SKILL_NAME"
python3 "$SKILL_DIR/scripts/render-frontmatter.py" \
  --name "$SKILL_NAME" --kind "$KIND" \
  --brief eval-log/skill-brief.json \
  --template "$SKILL_DIR/templates/${KIND}.md" \
  > "$OUT_BASE/$SKILL_NAME/SKILL.md"
```
</important>

<important if="os=windows">
```powershell
# Windows経路: PowerShell 5.1+ で resolve-skill-dirs.ps1 を dot-source
. .\creator-kit\scripts\resolve-skill-dirs.ps1
New-Item -ItemType Directory -Force -Path "$env:OUT_BASE\$env:SKILL_NAME" | Out-Null
python "$env:SKILL_DIR\scripts\render-frontmatter.py" `
  --name "$env:SKILL_NAME" --kind "$env:KIND" `
  --brief eval-log\skill-brief.json `
  --template "$env:SKILL_DIR\templates\$($env:KIND).md" `
  | Out-File -Encoding utf8 "$env:OUT_BASE\$env:SKILL_NAME\SKILL.md"
```
</important>

<important if="os=unknown">
OS判定に失敗した。`ref-cross-platform-runtime` のフォールバック動線に従い、
ユーザーに OS (macOS / Windows / Linux) を確認してから対応分岐に進むこと。
</important>

**update モード (CD-002)**:
```bash
# 既存SKILL.mdを読み込み、findingsを差分適用する
# 1. 既存ファイルをバックアップ
cp "$OUT_BASE/$SKILL_NAME/SKILL.md" "$OUT_BASE/$SKILL_NAME/SKILL.md.bak"
# 2. findingsに基づき Edit で差分適用（新規作成しない）
# 3. validate-frontmatter.py で整合性確認
```

### Step 3: 補助ファイル生成

- run系: `templates/`, `scripts/`, `examples/`
- ref系: `references/articles-full.md` 等の長文置き場
- assign系: `references/rubric.json`, `scripts/render-findings-score.py`
- いずれも本文100行超なら `references/` に追い出す
- `references/` は `skill-build-trace.json` の `source_docs` / `doc_coverage` に対応付ける
- **context予算**: このステップで読む設計書は11章のみ。

### Step 3.5: 再現性トレース生成

`references/build-steps.md#reproducibility-trace` の schema に従い、以下を `eval-log/skill-build-trace.json` に保存する:

- `design_model`: 01章5要素（Intent / Contract / Boundary / Execution / Feedback）
- `context_map_decision`: resource-map が選んだ task category / selected_docs / 理由
- `build_flow_coverage`: 01a Step 1〜9 の PASS/FAIL と証跡パス
- `doc_coverage`: 02 / 03 / 04 / 05 / 06 / 07 / 08 / 09 / 10 / 11 / 13 / 14 / 15 / 16 / 26 / 27 / 28 / 29 / 30 / 31 / 32 / 33 / 34 / 35 章の設計判断をどこへ反映したかの PASS/FAIL と証跡パス
- `layer_decisions`: Skill / Subagent / Hook / MCP / CLI / script の採否理由、deterministic判定、fallback、依存方向、macOS stdlib 適合
- `variant_support`: run/ref/assign/wrap/delegate と role-suffix の適用可否
- `pattern_decisions`: `pattern_refs` の採否、量産対象パターン、再利用先、negative cases
- `script_execution_model`: 28章に基づく script 種別、実行コンテキスト A-E、優先順位、権限境界、frontmatter 状態
- `governance_model`: 27章に基づく rubric version/hash、提案要否、影響評価、役割分離、猶予条件
- `dogfooding_model`: 26章に基づく artifact 化、fork evaluator、再帰チェック、eval-log 出力先
- `reproducibility_gates`: lint / evaluator / elegant-review / governance の結果
- `rubric_composition_model`: 設計書29に基づく L0/L1/L2 `rubric_refs`、合成順序、merge_strategy、conflict_policy、hash 証跡
- `paradigm_analogy_model`: 設計書30に基づく既存パラダイム類推、適用限界、最終配置判断
- `output_routing_model`: 設計書31に基づく task_kind、payload schema、route、adapter registry、fallback、secret境界
- `implementation_ledger_model`: 設計書32に基づく manifest登録、正本/派生、残課題、C1-C4判定の証跡
- `change_governance_model`: 設計書33に基づく P0-P3分類、approval、cooldown、blast radius、changelog の証跡
- `plugin_boundary_model`: 設計書34に基づく plugin境界、外部参照棚卸し、Phase gate、移行禁止条件の証跡
- `meta_harness_model`: 設計書35に基づく observables、ログスキーマ、hook opt-in、再現性しきい値の証跡
- `variable_contract`: 具体値からテンプレート変数への写像、既定値、必須性、不適用条件、source_trace

### Step 4: 命名・構造Lint

```bash
python3 creator-kit/scripts/lint-skill-name.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 creator-kit/scripts/lint-skill-description.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 creator-kit/scripts/lint-skill-tree.py "$OUT_BASE/$SKILL_NAME"
python3 creator-kit/scripts/validate-frontmatter.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 creator-kit/scripts/lint-script-frontmatter.py "$OUT_BASE/$SKILL_NAME"
python3 "$SKILL_DIR/scripts/validate-build-trace.py" eval-log/skill-build-trace.json
```

ここでの lint は `manual-preflight` とし、28章の A/B 実行禁止に該当する強制 gate とは呼ばない。最終強制は Hook/CI の `enforced-hook-ci` で同じ検査を再実行する。

6つすべて exit 0 でなければ Step 2 または Step 3.5 へ戻る。

### Step 5: フォーク評価

`assign-skill-design-evaluator` をforkで呼び出し、rubric採点:

```
Skill(assign-skill-design-evaluator) target=$OUT_BASE/$SKILL_NAME
```

出力JSON:
```json
{"rubric_id":"skill-design","rubric_version":"1.0.0","score":N,"findings":[...]}
```

評価時は `skill-build-trace.json` も対象に含め、01/01a の正本フローに未対応の Step があれば C2 漏れとして扱う。メタSkill・rubric・script・hook を含む場合は、26/27/28章の trace 欠落を C2 漏れ、rubric自己編集や実行経路矛盾を C1/C4 失敗として扱う。

### Step 6: ゲート判定

- score >= 80 かつ high=0 → 完了
- それ以外 → findings を本文に反映 → Step 4 へ戻る（最大3周）

### Step 7: subagent自動生成と検証（`--with-subagent` 指定時のみ）

`--with-subagent` フラグが指定された場合に実行する (PF-G3-001: 条件明確化):

```bash
# Step 2 で確定した $SKILL_DIR / $OUT_BASE を再利用 (self-relative + fallback)。
python3 "$SKILL_DIR/scripts/build-subagent.py" \
  --skill-name "$SKILL_NAME" \
  --skill-md "$OUT_BASE/$SKILL_NAME/SKILL.md" \
  --output-dir .claude/agents/ \
  --model "${MODEL:-opus}"
python3 creator-kit/scripts/lint-skill-description.py ".claude/agents/$SKILL_NAME-subagent.md"
```

SKILL.md frontmatter と本文の目的・手順から `.claude/agents/<skill-name>-subagent.md` を派生し、派生物も lint 対象にする。詳細は `references/build-steps.md#h2-subagent-生成の詳細実装`。

### Step 8: evaluator ペア自動生成（`--with-evaluator` 指定時 または brief.generate_pair_evaluator=true）

generator として作った skill に対し、対称な evaluator を同時生成して **孤児 evaluator** / 孤児 generator を防ぐ。公式CLIは `render-frontmatter.py --out --pair --rubric-refs` とする。詳細手順は `references/build-steps.md#h5-evaluator-ペア生成`。

### Step 9: Hook 配線自動生成（`--with-hooks` 指定時 または brief.hook_events 非空）

Hook 統合スキルの場合、scripts/hook-<name>-<event>.py スケルトンと settings.json マージ案を生成する。settings.json への自動 merge は行わず、人間承認後の手動 merge とする。詳細手順は `references/build-steps.md#h6-hook-配線生成`。

## 配置先（plugin 移行ロードマップ準拠）

| フェーズ | 出力先 | 正本 |
| **現在（Phase 0 未完了）** | `creator-kit/skills/<skill>/SKILL.md` | `creator-kit/skills/` |
| **Phase 0 完了後** | `plugins/<plugin-name>/skills/<skill>/SKILL.md` | `plugins/<name>/` |

- **正本/派生**: Phase 0 完了後、`.claude/skills/<skill>/` は `plugins/*/skills/` への symlink 経由派生。直接書き込まない
- **`name:` には plugin 名を含めない**: kebab-case の Skill 名のみ。所属 plugin は配置パスで表現（06章第17条）
- 詳細: 34章 § plugin 物理レイアウトと symlink 戦略

## Gotchas

- **frontmatter順序事故**: `disable-model-invocation: true` と `user-invocable: true` の共存は手動呼び出し専用の珍しい構成。禁止ではないが、意図を本文に明記する。
- **description長文化**: 動作詳細を書くと invocation時のtoken浪費（08章）。
- **ref系のbody肥大**: ref-*はSKILL.md本文をサマリに留め、原文は `references/`。300行制約はSKILL.md本文のみに適用。
- **scripts内のyaml import禁止**: stdlibだけで簡易パーサを書く（28章）。
- **fork評価の自己採点禁止**: 同じcontextで採点するとGoodhart罠（09章）。
- **update時の全書き換え禁止 (CD-002)**: --mode update ではEditで差分適用のみ。Writeで上書きしない。
- **全章一括ロード禁止 (CD-005)**: token超過を防ぐため、各Stepで必要な章だけを Read する。

## Additional Resources

- `references/design-docs-index.md` — 設計書00〜35への索引
- `references/resource-map.yaml` — task category → 読む設計書の決定論的map
- `references/build-steps.md` — 詳細手順、再現性trace schema、02/03/04 coverage
- `templates/` — kind別雛形
- `examples/minimal-ref.md`, `examples/workflow-with-evaluator.md` — 完成例
- `scripts/render-frontmatter.py`, `scripts/validate-naming.py`, `scripts/validate-build-trace.py`
- 共通lint: `scripts/lint-skill-name.py` 他
- manifest登録案: `scripts/build-manifest-registration-plan.py`
