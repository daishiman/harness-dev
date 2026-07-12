# elegant-review: skill-creator 宣言型化・抜け漏れ防止・再現性の仕組み化

- run_id: 20260702-declarative-skillcreator / scope: plugin / iterations: 2 / 最終判定: **APPROVE (4条件全 PASS)**
- 実行形態: Phase1 reset-observer → Phase2 3並列 analyst (30思考法) → Phase3 executor 3並列 + 追加タスク (SubAgent 分担、ファイル所有権を互いに素に分割)

## 根本原因 (why×5 の終着点)

宣言層 (md/yaml/json) は完備だが**「宣言→実行の突合を検証する機械層」が不在**。より深層では**保証系 sink (FAIL を外に出さない) と学習系 sink (摩擦を記録・集計する) の責務未分離**が、評価ループの構造死 (EVALS 凍結・proposals 未生成) を生んでいた。

## 実装した機構 (宣言→突合の機械層)

| 機構 | 対応 finding | 実体 |
|---|---|---|
| lint 集合の単一正本 + 3消費面突合 | LS-02/LS-07/PF-PARADOX | `references/lint-matrix.json` + `lint-matrix-sync.py` (Step4/p0-gate/CI、コメント行偽陽性封鎖、ci 欠落は理由必須) |
| Checklist→criteria 写像トレーサビリティ | LS-05/PF-DLOOP/F-SYS/F-ISU | `<!-- CL-n -->` アンカー + `criteria[].derived_from` + `lint-criteria-provenance.py` (R1-R6、presence-based opt-in、3 orchestrator skill 適用) |
| 要望カバレッジ RTM | PF-LATERAL | trace `requirement_coverage[]` + `validate-build-trace.py` 被覆検査 (段階導入 WARN→FAIL、意味判定は content-review = 二層分離) |
| 宣言型 lint の escape 封鎖 | LS-01/PF-META | lint-goal-seek の catalog 判定を見出しセクション span 限定へ (字面 escape 廃止) |
| escape hatch の対称化 | PF-ABST | skip_reason 受理を lint/trace/coverage 3面で FEEDBACK_SKIP_KINDS (ref/assign) 限定 |
| 評価ループ蘇生 | F-CAU/F-TRD/LS-04 | aggregate-evals に friction_density anomaly (committed PASS verdict 内の摩擦データ流用、実データ校正で発火率 2/47) |
| Loop B 修理 | F-PLS/F-VAL | auto-record-lesson→index 同時 append + genuine 文脈ゲート + 副産物 lesson 削除 + run-build-skill Step1 consult |
| メタ不変条件 + ratchet | LS-10/F-KAI | invariant「全宣言面は機械可読正本と対向突合 lint を持つ」+ `lint-declaration-coverage.py` (MANUAL_BASELINE=2、増加 CI FAIL) |
| composition 突合 | LS-03 | `lint-plugin-composition.py` (重複/実在/hooks 配線対応) + 二重記載解消 + quality-rubric 真実合わせ |
| 工程宣言の整合 | LS-09/PF-BRAIN/F-KAI | gate_order 宣言 + 本文正本参照化 + init-pre phase + --phase-order 機械検査 + capability_kind_map dangling 修正 |
| 真実合わせ | F-CLP/F-HYP/F-STR | queue=診断ログ明記 / Stop self 通知 (非block) / EVALS 旧経路 deprecated 注記 |

## 検証

- 中央 pytest **5990 passed / 4 skipped** (2回実施、fixture 副産物 revert 済)
- lint battery 10/10 exit 0 (独立 approver が再実走で確認)
- content-review verdict 6件 (3 skill × elegance/rubric) を独立 SubAgent が現 SHA で genuine 再生成。**iteration 1 で run-build-skill が REJECT** (capability_kind_map dangling + schema 正面矛盾の既存バグを独立レビューが検出) → 修正 → iteration 2 PASS。SHA 手書換なし
- proposer ≠ approver: 改善実装 (executor 群) と最終判定 (独立 approver) を分離

## deferred (理由付き意図的残置)

verdict.json の deferred 配列を正本とする。主要: PF-IF tree-hash 鮮度 / PF-NAIVE canonical-registry / exemptions.json 完全版 / compute-dogfooding-metrics 配線 / usage-log.jsonl / handoff 存在 lint。
