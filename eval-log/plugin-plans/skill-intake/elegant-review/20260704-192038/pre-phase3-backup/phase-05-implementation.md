---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装仕様)

## 目的
P04 のテストケースを満たすための **downstream builder 向け実装仕様** を C01-C04 それぞれについて記述する。goal-spec constraints (「実装は本 goal-spec のスコープ外」) に従い、本 phase は実コードの Edit/新規作成そのものではなく、後段 build (`run-skill-create`/`plugin-scaffold`) が参照する仕様を確定する。

## 背景
本 plan の全 phase は「downstream builder 向けの仕様」であることが環境ポリシー (index `## 環境ポリシー`) で明記されている。本 phase はその中でも最も実装に近い、build_target ごとの具体的な差分内容を仕様化する phase である。

## 前提条件
- P04 のテストケース仕様 (C1/C2/C3/C6/C7) が確定している。
- P03 design-gate が PASS している。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **`--mode update` 差分原則**: 既存 skill (C01/C03) への変更は Edit 差分のみ (全書き換え禁止)。

## 成果物
- **C01 (`run-intake-interview`, extend) 実装仕様**: (1) 5 軸ヒアリングシート完了後に procedure 軸のヒアリングを開始する SKILL.md 手順追記。(2) `interview.json` 出力スキーマ (`schemas/output.schema.json`) へ新規トップレベル `procedure` object を追加 (`mode`/`steps[]`/`difficulty_flag`/`overview`)。(3) `validate-answer-abstraction.py` の `axis` パラメータへ `procedure` を追加。(4) 実在する制御点 `references/question-plan.json`、`scripts/build-questions.py`、`scripts/build-sheet-json.py`、`scripts/check-five-axes-coverage.py` を拡張し、runtime 出力物である `sheet.md` / `sheet.json` に procedure 節が生成されるようにする。(5) **as-is 忠実性指示 (goal-spec C7/C8) の SKILL.md 追記**: 質問時/記録時に一般化・要約・改善提案をしない旨、抽象的・平均的な回答が来た場合は正規化せず「具体的にはどのツール/頻度/関与者か」等の追加質問で具体化を促す旨、ユーザーが自発的に改善提案 (to-be) を述べた場合は handoff 対象の as-is フィールドへ記録せず、別フィールドへの退避もしない旨を明記する。(6) 新規 `references/to-be-vocabulary-patterns.md` を追加 (既存 `abstract-answer-patterns.md` と対の to-be 語彙パターン集: 「べきである」「理想は」「最適化」「より良い方法」「一般的には」等)。
- **C02 (`validate-procedure-completeness.py`, new) 実装仕様**: `plugins/skill-intake/scripts/` 配下に新規配置。argv `--interview FILE` を受け取り、`mode=detailed` は `steps[]` 各要素の非空検証、`mode=overview_fallback` は `difficulty_flag`+`overview` 非空検証を行う。加えて `references/to-be-vocabulary-patterns.md` のパターン集を用いて handoff 対象の as-is フィールド (`procedure.steps[]/overview` の各テキスト値、および `five_axes.rows[name="真の課題"].content`) に to-be 語彙が混入していないかを走査する contamination check (goal-spec C7) を実行する。raw 会話ログは検査対象外であり、C01 が to-be 発話を handoff 対象 as-is フィールドへ保存しないことを前提とする。stdout に `{complete: bool, mode, missing: [...], contamination: {detected: bool, fields: [...], matched_terms: [...]}}` の JSON を出力、exit 0=complete かつ contamination.detected=false / 1=incomplete または contamination.detected=true / 2=usage。
- **C03 (`run-intake-finalize`, extend) 実装仕様**: Phase9 の集約ロジックに、`intake.json` 生成前の `validate-procedure-completeness.py` 呼び出しと結果検査を追加。procedure/purpose いずれか欠落時、または contamination.detected=true のときは該当 Phase (Phase4 または Phase5/Phase8) へ差し戻す分岐を SKILL.md へ追記する。成功時のみ procedure を `intake.json.sections.6_five_axes_summary.procedure` へ格納し、C02 stdout を `intake.json.validation.procedure_completeness` へ格納して C04 が再利用できるようにする。
- **C04 (`quality_gate.py`, extend) 実装仕様**: 既存の決定論ゲートロジックに「`intake.json` の `sections.3_purpose_excavator` または `sections.6_five_axes_summary.axes[axis_id="real_problem"].answer` 由来の true_purpose と、`sections.6_five_axes_summary.procedure` の両方が非空」invariant を追加。加えて `intake.json.validation.procedure_completeness.contamination.detected` を読み込み、混入検出時も違反として扱う (判定ロジック自体は C02 に一元化し C04 内で重複実装しない)。違反時は stderr に `missing_purpose`/`missing_procedure`/`to_be_contamination_detected` を出力し exit 1。
- **references/schemas 更新仕様**: root `references/intake.schema.json` の既存 `sections.6_five_axes_summary` に `procedure` property を追加し、root に任意 `validation.procedure_completeness` を追加する。13 番目 section は新設せず、`schema_version: 2.0.0` は後方互換な additive 拡張として維持する。root `references/handoff-contract.md` へ procedure→build 参照契約行を追加する (goal-spec C5)。

## スコープ外
- 実際のファイル Edit・新規スクリプト作成の実行 (本 plan は仕様書であり、実改修は後段 build へ委譲)。
- テストコードの実装 (P04 で仕様化したテストケースの pytest 化は build 側の責務)。
- to-be (改善提案・理想手順) 専用の永続フィールドの新設 (ヒアリング段階で to-be 設計をしない goal-spec constraints により、混入検出のみを実装し独立保存はしない)。

## 完了チェックリスト
- [ ] C01-C04 それぞれについて、変更対象ファイルと変更内容が具体的に (関数/フィールド単位で) 記述されている。
- [ ] 全ての実装仕様が P04 のテストケース (C1/C2/C3/C6/C7) を満たす設計になっている。
- [ ] 既存 skill (C01/C03) への変更が Edit 差分として記述され、全書き換えを前提としていない。
- [ ] as-is 忠実性指示 (C01 SKILL.md 追記) と contamination check (C02 拡張、to-be-vocabulary-patterns.md 新設) が goal-spec C7/C8 を満たす設計になっている。

## 参照情報
- `plugin-plans/skill-intake/component-inventory.json` (build_target/builder/build_kind の正本)。
- P04 (満たすべきテストケース)。
- 後続 P06 (この実装仕様に基づき生成された実装がテストを通ることを確認する)。
