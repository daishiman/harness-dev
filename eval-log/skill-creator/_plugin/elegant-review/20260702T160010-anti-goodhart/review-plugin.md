# elegant-review 独立承認レポート — anti-goodhart 統合 (plugins/skill-creator)

- run-id: `20260702T160010-anti-goodhart`
- target: `plugins/skill-creator` (scope=plugin)
- 承認者: 独立 approver (CL-8: proposer≠approver。実装 executor E1-E5 とは別個体)
- 判定: **APPROVE**
- 検証日: 2026-07-02

## 1. 改善サマリ

anti-goodhart 参考実装 (tmux 実走受け入れ + 8 INVARIANTS) を skill-creator へ矛盾・重複なく統合する Phase3 実装 (設計正本 D1-D14 / Phase2 41 issues) を独立検証した。中核は「静的レビュー=design claim / 実走証拠=behavioral claim」の主張型直交 (Gate D) と、その証拠層を機械契約 (schema/SHA/lint/manifest phase) で常設化する点にある。

実装の実在を自分の目で確認した主要成果物:

- **SSOT 機械層**: `convergence-policy.json` loop_bounds に `trial_acceptance`/`iter_improve` を consumed_by 付き追加 (「5つの別ループ」)、`anti_patterns` に evaluator 緩和/score 急上昇の2辺。`feedback_contract_ssot.py` に `ENGINE_SKILLS` frozenset + `requires_subject_copy` 述語 + `CRITERIA_VERIFY_BY += live-trial`。`plugin.json` に `requirements.external_clis`(tmux)。`build-flags.schema.json`/`validate-build-plan.py` に `acceptance_tier` 決定論導出 (`derive_acceptance_tier()`)。
- **文書ゲート層**: `orchestrate-gate-pattern.md` に Gate D (優先 A>B>C>D・loop 実行系のみ・claim 型直交)、`content-review-protocol.md` に「静的=design adequacy」宣言、`goal-seek-paradigm.md` に GOAL VERIFICATION 節 (点数出力禁止・二重宣言禁止)、`feedback-loop-deployment.md` に被験体コピー境界行、`elegant-improvement-executor.md` に適用層境界 (INV5)。
- **新 skill 2本 (交換可能な葉, tier: extension)**: `run-skill-live-trial` (Python stdlib 6 script + verdict schema 15必須キー + task-template/transcript-jsonl references) と `run-skill-iter-improve` (8 INVARIANTS 写像 + interrogation-log schema + goal-declaration)。
- **強制層**: `scripts/lint-live-trial-verdict.py` (D9/D13 record-only + --enforce)、`workflow-manifest.json` phase13 `live-acceptance`、`plugin-composition.yaml` 登録 + invariant 2行、`aggregate-evals.py` 合流、`ROADMAP.md` deferred 4件、CI 3箇所配線。

## 2. 4条件判定 (独立検証結果)

| 条件 | 判定 | 未解消 | 根拠 (要旨) |
|---|---|---|---|
| C1 矛盾 | **PASS** | 0 | 最大矛盾2件 (INV8×content-review核 / forbidden-clis×live-trial) は Gate D + 主張型直交と Python 移植+tmux 登録で両立解消。goal 二重化は単一正本+二重宣言禁止、INV5/INV7 矛盾は適用層境界+述語で層分離。位相語 inner/outer は機能語へ統一。残存矛盾を検出せず。 |
| C2 漏れ | **PASS** | 0 | D1-D14 の実装網羅を確認 (external_clis/goal SSOT/loop_bounds/tier 導出/live-acceptance phase/verdict 15キー/interrogation-log/ROADMAP deferred すべて実在)。Goodhart 未防御辺3本は interrogation-log allOf + 審問ログ必須 artifact + Gate D で封鎖。 |
| C3 整合 | **PASS** | 0 | 数値生値は convergence-policy loop_bounds のみに存在し本文は参照のみ (二重宣言禁止)。lint が harness 実装を importlib 再利用し生成/検査の schema 乖離を排除。用語 (Gate D/design・behavioral claim) 全文書一貫。criteria/parity 274 passed。 |
| C4 依存 | **PASS** | 0 | 両新skillの reference/schema/script refs すべて実在 (dangling 0)、CI 配線 (run-ci-checks L52 / governance L34)、lint-script-naming 6本登録、composition DAG 追加。run-ci-checks PASS 85/FAIL 0。 |

## 3. 機械検証の実行結果 (独立再実行)

- `validate-paradigm-coverage.py findings.json` → **OK: all 30 paradigms covered**
- `findings.json` → `findings.schema.json` (draft-07) **完全準拠** (jsonschema)
- `lint-live-trial-verdict.py --self-test` → **OK: 8 case(s) passed**
- `lint-live-trial-verdict.py --all` → **OK: 0 verified / 0 missing (record-only)** — 両新skillは denylist 被験体のため verify_by: live-trial 宣言でも missing FAIL を踏まない (正しい fail-closed)。
- `run-ci-checks.sh` → **PASS 85 / WARN 3 / FAIL 0** (WARN 3 は mf-kessai/notion-gmail-send completeness・rubric-refs で anti-goodhart と無関係の既存段階導入項目)
- `lint-content-review.py --all` → **OK: 47 skill(s) verified** (verdict 6件の SHA 鮮度含む)
- 対象テスト再実行: `test_live_trial_harness / test_iter_improve_contract / test_lint_live_trial_verdict / test_aggregate_evals / test_check_review_trigger / test_dogfooding_boundary / validate_build_plan` → **156 passed**
- 統合影響テスト: `test_all_skills_criteria / feedback_contract_ssot / parity / render_combinators / validate_build_trace / validate_llm_coverage / lint_plugin_composition / lint_declaration_coverage / lint_criteria_provenance / lint_matrix_sync` → **274 passed**

## 4. deferred (設計上明示済み・未解消扱いにしない)

いずれも ROADMAP.md (11)-(14) と設計決定 D13/D7/D14 に理由付きで記録済み:

1. **P1 パイロット未実施** — live-trial 判定表 (静的 PASS × 実走 FAIL の対照 2-3件) 記録まで lint は record-only WARN 運用。
2. **P3 常設化 go/no-go** — `live-acceptance` の default_on 昇格 / lint --enforce 昇格はパイロット乖離率で判定。
3. **D7 verify_by ratchet** — loop 実行系 outer criteria への `verify_by: live-trial` 要求は新規 skill のみの ratchet (既存 backfill はパイロット後)。
4. **scenario corpus hook** — verdict の `scenario_origin` フィールドのみ実装、replay 自動採取 hook は運用定着後。
5. **実 tmux E2E** — 本 lint はオフライン検査で、実走自体はローカル Claude+tmux (リモート CI 実走は D14 で却下)。

## 5. 残リスク・観察 (REJECT 事由ではない)

- **[観察 / PR hygiene] 別 run の共存**: 本 worktree の untracked に anti-goodhart とは別の改善 (`20260702-declarative-skillcreator`: `lint-matrix.json` / `lint-declaration-coverage.py` / `lint-matrix-sync.py` / `lint-criteria-provenance.py` / `lint-plugin-composition.py` / `build-plan.schema.json`) が混在する。これらは governance-check.yml に配線され CI 緑を維持しており **anti-goodhart の正しさを損なわない**が、A4-015「島跨ぎ混在コミット禁止」に照らし **PR 時は島 (effort) 単位で分離**することを推奨する。`validate-build-plan.py` の `derive_acceptance_tier()` は D8 由来で anti-goodhart 側の成果物。
- **[低 smell] 自己言及 criterion**: `run-skill-live-trial`/`run-skill-iter-improve` は自身の feedback_contract で `verify_by: live-trial` を宣言するが denylist 被験体で実 live-trial は不能。lint 側 `required = declares AND not denied` で missing FAIL を回避しており **設計通り** (harness 自体の IN criteria は test/script で検証)。実害なし。

## 6. 承認

4条件すべて PASS・未解消 violation 0・機械検証すべて exit 0 を独立に確認した。**APPROVE**。上記 §5 の PR 島分離は承認後のマージ運用上の推奨であり、実装差分の再修正を要しない。
