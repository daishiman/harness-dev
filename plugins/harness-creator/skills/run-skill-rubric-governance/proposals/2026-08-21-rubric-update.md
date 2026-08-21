---
date: 2026-08-21
kind: rubric-update-proposal
status: draft
trigger: aggregate-evals (SessionEnd)
---

# rubric 更新提案 (自動生成ドラフト)

## 集計サマリ

- 評価件数: 312
- FAIL 率: 1.60%
- 平均スコア: 92.75

## 検出された異常

- **run-skill-create**: friction_density — {"friction_records": 2, "window": 5, "evidence": [{"date": "2026-08-20", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-08-20", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-build-skill**: friction_density — {"friction_records": 2, "window": 5, "evidence": [{"date": "2026-08-20", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-08-20", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-elegant-review**: friction_density — {"friction_records": 2, "window": 5, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-company-master-backfill**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-company-master-build**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **ref-handout-design-system**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-08-18", "iterations": 1, "negative_feedback_count": 6, "findings_count": 0}, {"date": "2026-08-18", "iterations": 1, "negative_feedback_count": 5, "findings_count": 0}]}
- **run-codex-plugin-install**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-08-20", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-08-20", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-codex-plugin-package**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-08-20", "iterations": 3, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-08-20", "iterations": 3, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-skill-feedback**: friction_density — {"friction_records": 2, "window": 4, "evidence": [{"date": "2026-08-11", "iterations": 5, "negative_feedback_count": 2, "findings_count": 0}, {"date": "2026-08-11", "iterations": 5, "negative_feedback_count": 2, "findings_count": 0}]}
- **run-skill-update-notifier**: friction_density — {"friction_records": 2, "window": 4, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-mf-invoice-db-setup**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-mf-invoice-report**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}
- **run-intake-option-catalog**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **ref-diagram-system**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-08-17", "iterations": 2, "negative_feedback_count": 8, "findings_count": 0}, {"date": "2026-08-17", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **ref-system-design-knowledge**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-08-11", "iterations": 4, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-08-11", "iterations": 4, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-ubm-goal-setting**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-08-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-08-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}
- **run-ubm-knowledge-sync**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}

## 主要 finding カテゴリ (top5)

- fixture resetの危険なrm permission gateで自走停止: 1 件
- C11 未達のまま完了扱い: `validate-graph-schema.py --graph .dev-graph/state/graph.json` を評価者側で再実行すると exit=1 / `valid:false` / `feature_package_not_exact_13 (node=LT-FEAT-001, count=2)`。skill 完了チェックリスト1「input graph/scope が schema PASS」も task.md line3「C02/C11契約に従って準備」も満たしていない。被験セッション自身の `eval-log/run-dev-graph-render-progress.json` も CL1 を PARTIAL と記録し、`run-dev-graph-render-intermediate.jsonl` に `drift_signal: contract_conflict_unresolved` と「上位へ handoff」と書きながら、out/status.json は PASS を自己申告している。SKILL.md「全 checklist と feedback_contract.criteria が PASS のときだけ完了する」に反する。: 1 件
- 被験 skill の責務手順を省略: `responsibilities` の R1-elicit / R2-plan / R3-render はいずれも `prompt_required: true` だが、transcript 全 60 tool-use 中 `skills/run-dev-graph-render/prompts/*.md` の Read/cat は 0 件 (init skill の R3-init.md のみ読了)。また `goal_seek.fork: subagent`「未達 responsibility を `Agent` で分離 context に fork する」に対し Agent/Task 呼び出しは 0 件 (Bash 44 / Read 8 / Write 5 / Skill 3)。ゴールシークループは 1 周 (intermediate.jsonl 1 行) のみで、未達 checklist を残したまま停止している。: 1 件
- graph 準備が C02 の gate を通過していない: 登録は canonical writer ではなく scratchpad の自作 script `node_r8.py` で graph.json / node-registration-receipt.json を直接生成しており、node skill が要求する「validate-graph-schema.py を通してから atomic replace」に対し、検証が `valid:false` のまま commit されている。receipt 自身も `receipt_schema_note` で package-registration-receipt.schema.json 非適合を自認しており、schema 準拠の登録 receipt ではない。: 1 件
- (参考: 上記と独立に、task.md line7 の 5 観点は実体で裏づけられた — 外部 script/link・CDN・http(s)/protocol-relative 参照 0 件、inline SVG に node 4 + edge path 1、`active · feature · 1/2` 表示、renderer input_sha256=281cf797…=sha256(graph.json)=receipt.graph_sha256_after、registration receipt source_digest=sha256:477e6414…=sha256(node-registration-source.json)=全 node の source_lineage.source_digest、同一入力で再 render して output digest ce051a7b… が一致、qlmanage で追加 runtime なしに描画確認済み。FAIL は成果物品質ではなく上記の契約未達・手順迂回による。): 1 件

## 提案アクション (要 human review)

- 該当 rubric_id の閾値 / 観点を見直し
- 主要 finding カテゴリに対応する評価項目を新設または重み調整
- 関連する run-* / assign-* Skill の templates を更新

## 備考

本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。
