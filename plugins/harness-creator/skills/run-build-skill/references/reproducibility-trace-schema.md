# reproducibility-trace-schema

`eval-log/skill-build-trace.json` に保存する再現性トレースの schema。
run-build-skill Step 3.5 はこの schema に従って各キーを埋めること。
`references/build-steps.md#reproducibility-trace` も参照する。

## 必須キー

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
- `prompt_generation_model`: brief.responsibilities[] と prompt-creator の Step 7.5 ループの突合トレース。後述スキーマ参照

## `prompt_generation_model` スキーマ

責務単位の再現性を保証するため、prompt-creator ループの実行結果を responsibility.id で結合可能な形で記録する。

```jsonc
{
  "prompt_generation_model": {
    "policy_resolution": {
      "brief_policy": "auto | required | optional | skip",
      "resolved_policy": "required | optional | skip",
      "resolved_via": "brief.kind=run|assign → required (default) | brief.prompt_creator_policy override | N/A: <reason>"
    },
    "per_responsibility": [
      {
        "id": "R1-elicit",
        "name": "<brief.responsibilities[].name>",
        "owner_agent": "<agent-file-name or null>",
        "layer_yaml_path": "plugins/<plugin>/skills/<skill>/prompts/R1-elicit.md",
        "path_convention": "skill-local-v1",
        "layers_generated": ["L1","L2","L3","L4","L5","L6","L7"],
        "sha256": "<7層 YAML 全文 sha256>",
        "lint_status": "PASS | FAIL",
        "iteration_count": 1,
        "escalation": "none | retry | reframe_brief | abort"
      }
    ],
    "cross_ref": {
      "skill_build_id": "<UUID or commit-sha>",
      "prompt_creator_trace_path": "eval-log/prompt-creator-trace.json",
      "join_key": "responsibility.id"
    },
    "anchor_coverage": {
      "agent_files_checked": ["plugins/<plugin>/agents/<role>.md"],
      "missing_anchors": [],
      "extra_anchors": []
    }
  }
}
```

### N/A 条件

- brief.kind ∈ {ref, wrap, delegate} かつ `prompt_creator_policy` が `skip` または resolved=skip の場合は、`per_responsibility: []` + `policy_resolution.resolved_policy: "skip"` + 理由を `resolved_via` に明記すれば N/A 扱い。
- brief.kind ∈ {run, assign} は prompt 生成必須。`resolved_policy: "optional"` または `"skip"` は `prompt_provenance` 必須化を迂回する downgrade として exit 1。
- prompt-creator を 1 度も呼ばなかった場合、`cross_ref.prompt_creator_trace_path: null` を許容。ただし resolved=required で per_responsibility が空なら validate-build-trace.py が exit 1。

## バリデーション

`scripts/validate-build-trace.py` が上記キーの存在と PASS/FAIL/N/A 理由を検証する。
N/A の場合は理由を必ず添えること（空欄禁止）。

`prompt_generation_model` については追加で次を検証:

1. `policy_resolution.resolved_policy == "required"` のとき `per_responsibility[].lint_status == "PASS"` がすべて満たされること。
2. trace の `brief_path` が指す `brief.responsibilities[]` のうち、`prompt_required: true` または `prompt_required` 省略 (既定=true) の `id` 集合と `per_responsibility[].id` 集合が完全一致すること。`prompt_required: false` は対象外。`brief_path` が宣言されているのに brief を解決できない場合、集合一致を証明できないため exit 1。
3. `anchor_coverage.missing_anchors` が空配列であること (SubAgent.md 側に必要 anchor が全て存在)。
4. `sha256` は同一 brief で 2 回生成した場合に一致する (再現性ハッシュ)。差分が出た場合は `escalation` 非 none が必須。
5. `layer_yaml_path` が次の正規表現に一致すること (`references/prompt-placement-convention.md` 準拠):
   - `path_convention == "skill-local-v1"`: `^plugins/[a-z][a-z0-9-]*/skills/(ref|run|wrap|assign|delegate)-[a-z0-9]+(-[a-z0-9]+)*/prompts/R[0-9]+[a-z]?(-[a-z0-9]+(-[a-z0-9]+)*)?\.(md|yaml)$`
   - `path_convention == "agents-legacy"` (deprecated, 後方互換): `^plugins/[a-z][a-z0-9-]*/agents/prompts/[a-z][a-z0-9-]*\.(md|yaml)$`
   - 正本は `scripts/validate-build-trace.py` の `LAYER_YAML_PATH_PATTERNS` (slug 付き `R1-elicit.md` 形式と `.yaml`/`.md` 両拡張子を受理。項目 6 と整合)。
6. `layer_yaml_path` のファイルstemが `per_responsibility[].id` と**完全一致**すること。`R1.md` ↔ id=`R1`、`R1-elicit.md` ↔ id=`R1-elicit`、`R2b-readiness.md` ↔ id=`R2b-readiness` は受理するが、`R1-elicit.md` ↔ id=`R1` は拒否する。拡張子は `.yaml` / `.md` の両者を受理する。

## `prompt_provenance` (route C09 バイパス不能性)

agents/*.md・skills/*/prompts/*.md を生成/更新した build が prompt-creator の7層契約を経由し、route C02 内容 lint (`lint-agent-prompt-content.py`) を通過したことの証跡ブロック。スキーマは `schemas/skill-build-trace.schema.json#/properties/prompt_provenance`。

- `prompt_creator_invocation` (boolean, 必須): prompt-creator 経由で本文7層を生成したか。**false は単独生成のバイパス試行として常に exit 1**。
- `source_contract_ref` (string, 必須): 準拠した契約。agent は `subagent-hybrid-format.md`、prompt は `seven-layer-format.md` を参照する。
- `content_lint` (object, 必須): `{mode: agent|prompt, status: PASS|FAIL|N/A, evidence?}`。route C02 が exit0 でなければ status≠PASS となり生成未完了。

検証 (`_validate_prompt_provenance`):
1. `prompt_generation_model.policy_resolution.resolved_policy == "required"` の build では `prompt_provenance` を必須化 (欠落は exit 1)。`run`/`assign` では `optional`/`skip` への降格も exit 1。`optional`/`skip` の後方互換 escape は prompt 生成非必須 kind に限る。
2. `prompt_creator_invocation != true` は exit 1 (bypass detected)。
3. `source_contract_ref` が上記2契約のいずれも参照しなければ exit 1。
4. `content_lint.status != PASS` または `mode` が agent/prompt 以外は exit 1。

## path_convention deprecation policy

Phase 3 で確定 (2026-05-21)。

### 期限

- `path_convention: "agents-legacy"` (`plugins/<plugin>/agents/prompts/<role>.yaml`) は **2026-08-31 まで** 受理する。
- 2026-09-01 以降、`validate-build-trace.py` は `agents-legacy` を検出した時点で exit 1 (deprecated path)。
- 新規 skill は最初から `skill-local-v1` で生成すること。

### 仮説 KPI

本規約は次の採用率仮説で正当化する:

- **仮説**: harness-creator 経由で生成された skill のうち `path_convention: "skill-local-v1"` 採用率が、2026-08-31 時点で **70% 以上** に到達する。
- **未達時のアクション**: 70% 未満であれば、規約自体を撤回もしくは再設計する (場所変更、命名見直し、policy 緩和等を含む)。撤回判断は skill-governance 側 governance proposal で行う。

### 計測ソース

- ソース: `eval-log/skill-build-trace.json#prompt_generation_model.per_responsibility[].path_convention`
- 集計単位: skill 単位 (同一 skill_build_id は 1 件としてカウント)。
- 計測スクリプト: `scripts/measure-path-convention-adoption.py` (未実装、KPI 計測ジョブとして 2026-Q3 中に追加予定)。
