---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計・TDD Red)

## 目的
C1/C2/C3 の各残債と、C6/C7 (機械層検出)・C10/C11 (機械層検出)・C8/C12 (意味層 genuine 判定) に対して、実装着手前に失敗するテストケース (TDD Red) を設計し、goal-spec の checklist (C1-C12) それぞれに対応する verify_by=test/script/reasoning の観測可能な合否条件を固定する。

## 背景
goal-spec の checklist は `verify_by: test`(C1/C2/C4/C5/C6/C7/C9/C10/C11) と `verify_by: script`(C3) と `verify_by: reasoning`(C8/C12) を明示しており、test/script 系はいずれも実装より先に失敗するテストケースの存在を要求する (TDD Red)。既存の `test_check_runtime_portability.py` / `test_check_build_handoff.py` / `test_ci_integration.py` / `assign-plugin-plan-evaluator/tests/test_evaluate_plan.py` に追加する形で設計する (新規テストファイルの乱立を避ける)。

## 前提条件
- P03 の design-gate を通過した設計 (C1/C2/C3 の関数シグネチャ拡張方針、C6/C7/C10/C11 の新規 script 設計、C8/C12 の R1-evaluate.md/plan-rubric.json 拡張設計) が確定している。
- 既存の `_self_test()` パターン (embedded fixture による固定検証) が各対象 script に存在する。

## ドメイン知識
- **C1 のテストケース**: (a) target_plugin_slug と一致する build_target (`plugins/plugin-dev-planner/...`) を含む handoff は exit0 のまま (後方互換)、(b) target_plugin_slug と異なる plugin (`plugins/other-plugin/...`) を含む build_target を持つ handoff は exit1 で不整合を検出結果に含める、(c) target_plugin_slug 省略時 (None) は既存 (P)/(Q) 検査のみ動作し新チェックはスキップされる。
- **C2 のテストケース**: (a) envelope entry_points が inventory の skill/sub-agent/slash-command component を全網羅する fixture は exit0、(b) inventory に存在し envelope entry_points に未網羅の component id を含む fixture は exit1 でその component id を検出結果に含める、(c) hook/script component は entry_points 突合の対象外であることを固定する。
- **C3 のテストケース**: (a) `check-harness-coverage-selfcheck.py` が `validate-harness-coverage.py --json` の plugin-dev-planner 行を正しく抽出し 12 軸 (6 種別×mechanical/llm_eval) の構造的宣言状態を判定できることを embedded fixture で固定する、(b) governance-check.yml の該当 block に新規ステップが追記されていることを `test_ci_integration.py` の新規テスト関数で固定する。
- **C6/C7 のテストケース**: (a) denylist 10 語のいずれかを含む fixture 文字列 (phase 本文/goal/checklist/criterion) は WARN/FAIL 結果に含まれる、(b) denylist を含まない fixture は結果に含まれない、(c) `_PHASE_SECTION_HINT` の節本文と前後空白差のみの fixture (strip 後完全一致) は未カスタマイズとして検出される、(d) 1 文字でも異なる fixture は検出されない (完全一致の厳密度を固定)。
- **C10/C11 のテストケース**: (a) `## 完了チェックリスト` 直下に `### 受入例` サブ見出しを持つ fixture phase 本文 (フル要件対象) は exit0、持たない fixture は exit1 で検出、(b) `### 事前解決済み判断` サブ見出しについても同様、(c) P03/P07/P09/P10 (縮小要件対象) は簡略形の存在のみで exit0 になることを固定する。
- **C8/C12 のテストケース (reasoning・pytest では構造検証のみ)**: (a) `plan-findings.schema.json` の `conditions` が `additionalProperties:false` かつ `required==["C1","C2","C3","C4"]` のまま変更されていないことを既存 `test_evaluate_plan.py` が固定する (回帰防止)、(b) `plan-rubric.json` の `semantic_checks` に C8/C12 相当の新規エントリが `runner: llm-only` で追加されていることを固定する、(c) 実際の genuine 判定結果は pytest では検証できず fork evaluator 実行時の plan-findings.json の findings[] 出現で確認する (P06 の実行対象)。
- **C4/C5/C9 のテストケース**: 既存テストスイート (退行防止のベースライン) を実装前に一度実行し件数を記録する (実装後の P06 で同件数以上の green を比較する基準値とする)。C9 はこのベースライン比較そのものが合否条件である。

## 成果物
- テストケース設計 (本ファイルのドメイン知識に記述した合否条件が、後続 P05 で実際の pytest 関数として実装される仕様となる)。
- 実装前ベースライン (既存テスト件数の記録)。

## スコープ外
- テスト関数の実コード実装 (P05 implementation で行う。本 phase は TDD Red の設計のみ)。
- C4/C5/C9 のベースライン記録以外の新規テスト追加 (退行防止は既存テストの再実行で足りる)。
- C8/C12 の genuine 判定結果そのものの妥当性検証 (fork evaluator の意味判定に委ねる。本 phase は構造契約 (conditions 不変・semantic_checks 追加) のテストのみ設計する)。

## 完了チェックリスト
- [ ] C1 のテストケース 3 件 (一致/不一致/省略時後方互換) が設計されている。
- [ ] C2 のテストケース 3 件 (網羅/未網羅/hook・script 対象外) が設計されている。
- [ ] C3 のテストケース 2 件 (self-check fixture 検証・governance-check.yml ステップ存在) が設計されている。
- [ ] C6/C7 のテストケース 4 件 (denylist 検出/非検出・フォールバック完全一致/1 文字差非一致) が設計されている。
- [ ] C10/C11 のテストケース 3 件 (受入例存在/事前解決済み判断存在/縮小要件 phase の簡略形) が設計されている。
- [ ] C8/C12 の構造契約テスト 2 件 (conditions 不変回帰・semantic_checks 新規エントリ) が設計されている。
- [ ] 実装前の既存テスト件数がベースラインとして記録されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 上記全テストケースが「入力 fixture → 期待される exit code / 検出結果」の形で観測可能に記述され、実装前に red (未実装で失敗) であることが確認できる。
- 満たさない例: テストケースが「正しく動作することを確認する」のような抽象的記述に留まり、具体的な fixture 入力や期待出力が書かれていない。

### 事前解決済み判断
- 分岐点: C8/C12 (verify_by=reasoning) を pytest でどう扱うか → 判断: pytest は構造契約 (conditions 不変・semantic_checks 追加) の回帰テストのみを担い、genuine 判定結果の妥当性そのものは fork evaluator 実行 (P06) と plan-findings.json 出力で確認する (pytest に意味判定の代替をさせない)。

## 参照情報
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/test_check_runtime_portability.py`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/test_check_build_handoff.py`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/test_ci_integration.py`。
- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/tests/test_evaluate_plan.py` / `tests/test_gate_parity.py`。
- 後続 P05 (implementation)。
