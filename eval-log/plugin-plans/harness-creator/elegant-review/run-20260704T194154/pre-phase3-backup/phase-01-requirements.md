---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
「skill-intake→plugin-dev-planner→harness-creator build→改善」量産パイプラインの 3 境界断線 (E1: intake→goal-spec / E2: plan→build / E3: 改善→plan) を目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` を確定させる。`target_plugin_slug=harness-creator` を固定し、実装・実 build はスコープ外であることを明示する。

## 背景
各段 (intake/plan/build/improve) の実行は別々のまま維持する方針のもと、producer 側資産は完備しているのに consumer 側入口・検証ゲート・provenance が欠落しているため、パイプラインが「文書化されているが配線されていない (documented-but-unwired)」状態に落ちている。E1 は intake.json の消費経路、E2 は routes[] の消費経路、E3 は改善成果物の構造化入力契約がそれぞれ欠落しており、これらを機械契約として整備することが本 plan の要件である。

## 前提条件
- パイプライン構想 (E1/E2/E3 断線の実地調査結果) が入力として与えられている。
- 汎用の `run-goal-elicit` (harness-creator) が利用可能で、purpose/background/goal/checklist を `goal-spec.schema.json` で抽出できる (再実装しない)。
- 対象は既存 2 plugin (harness-creator / plugin-dev-planner) の consumer 側修正であり、新規 plugin 作成ではない (`artifact_class: existing-plugin-update`)。

## ドメイン知識
- E1 (intake→goal-spec): producer (skill-intake の intake.json v2.0.0 + handoff-contract.md) は完備、consumer (`/plugin-dev-plan` の intake_json 引数・R1 実行ブロック) が未配線。
- E2 (plan→build): producer (`handoff-run-plugin-dev-plan.json` の routes[]) は完備、consumer (`run-skill-create` の brief_path 受理・`capability-build` の routes[] 直接消費) が未配線。
- E3 (改善→plan): run-elegant-review/run-skill-iter-improve/run-skill-feedback のいずれの出力も `plugin-plans/` や `--mode update` を参照せず、改善成果物を計画へ還流する経路が存在しない。
- provenance chain: intake.json→goal-spec(source_intake)→plan→build handoff→改善成果物(source_improvement)→次サイクル goal-spec、という 5 ノードの追跡可能性。
- その他の plan 全体用語 (component_kind/placement_scope 等) は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist C1-C12/constraints/handoff_targets)。
- target_plugin_slug=`harness-creator` と plan_dir=`plugin-plans/harness-creator/` の確定値。

## スコープ外
- component 分解・envelope 設計 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・実 build (本 plan は計画のみ・後段 build は harness-creator へ委譲)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、E1/E2/E3 の断線記述が background に反映されている。
- [ ] checklist C1-C12 が二値判定可能な項目 (各 verify_by 付き) で確定している。
- [ ] target_plugin_slug=`harness-creator` が確定し以降のフェーズがそれを参照できる。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02 (この goal-spec を component 分解の入力とする)。
