# Fidelity Report — verdict=fail

- overall_score: **47.5** / 100
- pass_threshold: 0.85 / warn_threshold: 0.7
- forced_fail (block-section absent): False

| section | present | score | missing_fields | missing_slots |
|---|---|---|---|---|
| 0_executive_summary | True | 27.2 | generated_at, pattern, workflow_pattern (warn-fallback), depth, vocabulary_tier, state, true_purpose_oneliner, design_decision_summary (warn-fallback), value_realized_score (warn-fallback) | cvis-exec-summary-card |
| 1_assumption_challenger | True | 46.5 | deep_candidates, adopted_deep_problem, blindspots (warn-fallback) | mtmpl-mindmap-surface-vs-deep |
| 2_user_profile | True | 63.3 | implications_for_next_phase (warn-fallback) | cvis-persona-card |
| 3_purpose_excavator | True | 60.0 | techniques_used, differentiation (warn-fallback), tacit_locus (warn-fallback) | mtmpl-mindmap-stated-to-excavated |
| 4_option_presenter | True | 48.7 | decision_tables | mtmpl-comparison-table |
| 5_visualizer | True | 26.6 | figures, rules_check | mtmpl-flowchart-lr, mtmpl-flowchart-tb, mtmpl-sequence, mtmpl-before-after-lr, mtmpl-boundary-tb |
| 6_five_axes_summary | True | 19.4 | axes, knowledge_pipeline | mtmpl-comparison-table-5axes |
| 7_design_decisions | True | 16.2 | adoptions, output_priority_finalized | mtmpl-comparison-table-adoptions |
| 8_open_questions | True | 66.7 | questions (warn-fallback), blocking_count, deferred_count | - |
| 9_handoff_contract | True | 46.8 | recommended_next, intake_json_path, starting_command | - |
| 10_self_updater | True | 90.0 | metrics, skipped_next_phases (warn-fallback) | - |
| 11_artifact_index | True | 80.0 | artifacts | - |

> verdict=fail: render_notion_page.py を停止し handoff へ差し戻してください。
