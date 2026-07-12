---
name: run-intake-finalize
description: intake 全 JSON を統合したいとき、intake.md と intake.json を Jinja2 で render して quality_gate と cross_check を通したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.1.1
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成された output/<hint>/intake.json が schemas/output.schema.json に適合し validation.render/quality_gate/cross_check の各 enum と(FAIL 時)failures[].retry_phase を必ず含み、quality_gate.py と cross_check.py を exit 確認できる
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 同一 Phase 1-8 入力に対し render-intake-final.py → convert_md_to_json.py 経路が LLM 推論を混入させず intake.md/intake.json を bit-identical(sha256 一致)に再生成し、欠落成果物を推測補完せず FAIL 返却する決定論を保つ
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 本スキルが Phase 9(全成果物統合と最終 intake 生成)に責務を絞り、render→quality_gate→cross_check の直列順序固定・単一発火点・atomic write を維持して Notion 公開や next-action 生成へ越境しない設計になっている
      verify_by: elegant-review
    - id: IN3
      loop_scope: inner
      text: intake.json 生成前に ../../scripts/validate-procedure-completeness.py と ../../scripts/quality_gate.py --require-procedure の両方を実行し、procedure(現状手順)と true_purpose(本質的課題)のいずれかが欠落、または as-is フィールドへの to-be 語彙混入(contamination.detected=true)を検出したとき exit0 にならず Phase9 を FAIL とし該当 Phase(Phase4 または Phase5/Phase8)へ差し戻す(goal-spec C3/C7)。成功時のみ procedure を sections.6_five_axes_summary.procedure へ、C02 stdout を validation.procedure_completeness へ格納する。
      verify_by: script
    - id: OUT2
      loop_scope: outer
      text: procedure または true_purpose を意図的に欠落させた入力を与えたとき、intake.json が生成されず下流ハンドオフ(run-skill-create/run-plugin-dev-plan)へ進めないことを受入テストが確認する(goal-spec C3)。
      verify_by: test
---

# run-intake-finalize

## Purpose & Output Contract

Phase 9 担当。Phase 1-8 で生成された全 JSON / sheet.md / visuals.json を統合し、最終成果物 `intake.md` (人間向け) と `intake.json` (harness-creator 入力) を **決定論的に**生成する。`render-intake-final.py` (Jinja2) と `quality_gate.py` / `cross_check.py` を順に exec する。harness-creator 引き渡し用の `next-action.json` は Notion 公開後の Phase 11 で生成する。

**入力**: Phase 1-8 の全成果物 + `intake-final-template.md.tmpl` + `intake-final-schema.json`
**出力**:
- `output/<hint>/intake.md`
- `output/<hint>/intake.json` (`schemas/output.schema.json` 準拠、`validation` field 必須。procedure 拡張時は `sections.6_five_axes_summary.procedure` と `validation.procedure_completeness` を含む)

**完了条件**: procedure dual-gate PASS (procedure + true_purpose 両方存在 + as-is フィールドへの to-be 非混入) + render PASS + quality_gate PASS (`--require-procedure`) + cross_check PASS。FAIL 時は `validation.failures[].retry_phase` を埋めて orchestrator へ返却 (procedure/purpose 欠落・to-be 混入は Phase4 へ差し戻し)。

## Key Rules

1. **LLM は呼ばない**: render は Jinja2、検証は決定論 script のみ。
2. **schema/template の正本**: 旧 aggregator references を参照。Phase C で物理移管予定。
3. **失敗時の戻り先明示**: render fail → 該当 Phase へ、quality_gate fail → 該当軸の Phase へ、cross_check fail → 不整合元 Phase へ。
4. **検証順序固定**: render → quality_gate → cross_check の直列 (順序入替・並列起動禁止、atomic write 保証)。
5. **日本語成果物**: 本文・validation reason は日本語、schema key / CLI 引数 / path は英語。
6. **procedure dual-gate (purpose+procedure 両立)**: intake.json 生成前に `../../scripts/validate-procedure-completeness.py --interview <procedure を持つ入力>` を実行し、procedure 完全性と as-is フィールドへの to-be 語彙非混入を確認する。exit0 のときのみ procedure を `sections.6_five_axes_summary.procedure` へ、その stdout を `validation.procedure_completeness` へ格納する。加えて `../../scripts/quality_gate.py --require-procedure` で true_purpose と procedure の両方が非空であることを強制する。procedure/purpose 欠落または contamination 検出時は Phase4 へ差し戻す。**contamination 差し戻しは同一 axis につき上限 2 回**とし、超過時は contamination を warning へ降格して人間確認 1 回へ切り替え、ヒアリング全体を停止させない (goal-spec C2 の「停止しない」原則の escape)。

## ゴールシーク実行

### Goal
Phase 1-8 の全成果物を決定論的に統合し、`schemas/output.schema.json` 準拠の `intake.md` / `intake.json` を bit-identical な再現性で生成、`validation.render` / `validation.quality_gate` / `validation.cross_check` が全 PASS、または FAIL 時に `failures[].retry_phase` が必ず埋まり intake.json に validation サマリが書き戻されている状態。

### Why
LLM 推論を混入させると同入力で差分が出て、後段 (`run-notion-intake-publish` 公開・diff 監査) が破綻する。検証 2 段 (quality_gate → cross_check) は順序固定でなければ偽陽性/偽陰性が混入する。固定手順を辿るのではなく、**チェックリスト未充足を起点に必要 script をその都度起動して反復**することで、入力欠落や中間生成物破損にも頑健になる。

### 完了チェックリスト (停止条件)
- [ ] Phase 1-8 全成果物 (JSON / sheet.md / visuals.json) の存在と schema 適合を確認した
- [ ] LLM 推論を呼ばずに Jinja2 / script のみで完了している
- [ ] `intake.json` が `schemas/output.schema.json` に適合している
- [ ] `quality_gate.py` と `cross_check.py` を順序通り (順序入替禁止) 実行した
- [ ] FAIL 時に `validation.failures[]` の各項目に `where` / `reason` / `retry_phase` が明示されている
- [ ] 同一 Phase 1-8 入力で `intake.md` / `intake.json` が bit-identical (determinism)
- [ ] 不足成果物を推測補完していない (欠落は FAIL として返している)
- [ ] `intake.json.validation` サマリ書き戻し済み (render / quality_gate / cross_check 各 enum)
- [ ] procedure を持つ入力に対し `validate-procedure-completeness.py` が exit0 (完全性 + to-be 非混入) で、結果を `validation.procedure_completeness` へ格納済み
- [ ] `quality_gate.py --require-procedure` が true_purpose と procedure の両方非空を PASS (いずれか欠落・contamination 検出時は Phase4 へ差し戻し)
- [ ] contamination 差し戻しが同一 axis で 2 回を超えた場合は warning 降格 + 人間確認 1 回へ切り替え、停止させていない

未充足項目を特定 → 必要 script (`render-intake-final.py` / `convert_md_to_json.py` / `quality_gate.py` / `cross_check.py`) を該当ステップから起動 → validation 更新 → 再度チェックリストで自己評価、を反復する。固定手順は持たない。

### 参考: 主要 script 起動例

```bash
# render: output/<hint>/ 直下の per-phase JSON (無ければ context.json) を集約し
# Jinja2 で intake-final.md を生成する (引数は output_dir 1 つ)。
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/render-intake-final.py output/<hint>/
cp output/<hint>/intake-final.md output/<hint>/intake.md

# intake.md → intake.json (front-matter + sections を JSON 化)
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/convert_md_to_json.py \
  output/<hint>/intake.md output/<hint>/intake.json

# procedure dual-gate (intake.json 格納前): 完全性 + as-is フィールドへの to-be 非混入を
# 確認し、その stdout を validation.procedure_completeness へ格納する (C04 が再利用)。
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/validate-procedure-completeness.py \
  --interview output/<hint>/interview.json

# 検証 2 段 (順序固定): quality_gate → cross_check
# cross_check の引数順は <intake.md> <intake.json> (md が先)。
# procedure 拡張 intake は --require-procedure で purpose+procedure 両立を強制する。
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/quality_gate.py --require-procedure output/<hint>/intake.json
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/cross_check.py  output/<hint>/intake.md output/<hint>/intake.json
```

Step/Gate の機械可読定義は `workflow-manifest.json` (P1-collect / P2-render / P3-quality-gate / P4-cross-check) を参照。

## Gotchas

1. **template / schema は移管前**: 旧 aggregator references パスを直書きしている。Phase C で本 references 配下へ移管後にパス書き換える。
2. **render と quality_gate は単一発火点**: 重複呼び出し禁止。orchestrator は本 Skill を 1 回だけ呼ぶ。単一発火点の SSOT 定義は `../run-skill-intake/SKILL.md` 「単一発火点」項を参照。
3. **並列起動禁止**: 検証順序維持と atomic write 保証のため、本 Skill は直列・単発のみ。
4. **欠落の推測補完禁止**: Phase 1-9 成果物に欠けがある場合は FAIL として `retry_phase` を埋めて返す (補完しない)。

## Additional Resources

- `workflow-manifest.json` — Phase (P1-P4) / Gate (C1-C4) / resource の機械可読定義
- `schemas/output.schema.json` — intake.json 出力契約 (validation field 必須)
- `prompts/R1-main.md` — R1 責務プロンプト (7 層 Markdown、決定論実行指示)
- `references/template-pointer.md` — Jinja2 テンプレ / schema の正本パス案内
- `references/validation-flow.md` — render → quality_gate → cross_check の順序と失敗戻り先表
- `../../scripts/validate-procedure-completeness.py` — procedure 完全性 + as-is フィールドへの to-be 混入検出 (dual-gate 第一段, C02)
- `../../scripts/quality_gate.py` — `--require-procedure` で true_purpose+procedure 両立を強制 (C04)
- `references/resource-map.yaml` — リソース一覧 (machine-readable)
