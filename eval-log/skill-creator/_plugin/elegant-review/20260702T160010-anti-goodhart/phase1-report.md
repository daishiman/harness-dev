# Phase 1 俯瞰レポート (elegant-reset-observer)

run-id: 20260702T160010-anti-goodhart / target: plugins/skill-creator (scope=plugin)
改善テーマ: anti-goodhart (run-skill-live-trial + run-skill-iter-improve) の機構を矛盾・重複なく反映し、内側/外側ループを毎回実行可能に常設。self-dogfooding。

## mapping_table (anti-goodhart要素 × skill-creator既存対応物)

| # | anti-goodhart要素 | skill-creator既存対応物 | 第一印象 |
|---|---|---|---|
| 1 | INV1 PASS詐欺禁止(緩め禁止リスト宣言・毎iter自己審問・score急変時外部判定) | run-elegant-review Gotcha3「Goodhartの罠」(宣言1行) / convergence-policy.json anti_patterns / run-build-skill Step5 / lint-content-review.py skill_md_sha256突合 | 精神は散在、運用機構(禁止リスト宣言・審問ログ・急変切り分け)は欠落。部分重複+新規 |
| 2 | INV2 context汚染回避 | elegant-reset-observer / goal-seek-paradigm.md「コンテキスト分離」/ Phase2 3並列独立 | ほぼ重複。「改善ループ毎iterのfresh評価強制」のみ新規 |
| 3 | INV3 goal≠proxy(iter0 GOAL DECLARATION+Step F GOAL VERIFICATION) | goal-seek-paradigm.md 中間成果物アンカー(original_goal不変SHA-256+drift_signal 6enum+merged_directive) / feedback_contract OUT criteria | 重複リスク最大。goal-spec.json vs --goal 1文の正本競合 |
| 4 | INV4 構造改善>対症療法(複数sample再現→skill層修正) | convergence-policy positive_feedback(amplified-patterns.json)が近縁のみ | N並列sample→共通弱点diagnose判定則は完全新規 |
| 5 | INV5 1 iter 1-2件制限 | elegant-improvement-executor(findings DAG化・1周全group改善の全件消化型) | 矛盾候補。適用層境界(レビュー改善vs skill反復改善)の宣言が必要 |
| 6 | INV6 eval-driven commit | elegant-review B7(Phase1/2 read-only・pre-phase3.patch・悪化revert) / wrap-git-commit-safe | ほぼ重複(同型規律) |
| 7 | INV7 自己適用安全(エンジン温存・被験体コピー) | feedback_contract_ssot.py dogfooding境界述語 / Loop B knowledge | 矛盾候補。既存selfレビュー=直接編集モデル vs 被験体コピーモデル |
| 8 | INV8 評価縮退禁止(静的レビュー収束寄与ゼロ・実走行動ログ必須・対照群必須) | content-review-protocol.md(静的LLM評価=Step12 default-ON「ハーネスの核」) / doc/harness-coverage-spec.md | 最大の欠落+潜在矛盾。責務直交(設計adequacy vs 実行acceptance)の層分離が要る |
| 9 | tmux live-trial harness(boot/send/poll/status 4本.sh+jq+transcript JSONL) | 対応物なし(grep 0件) | 新規。forbidden-clis.md(jq禁止・.sh配布禁止・Python stdlib正本)と直接矛盾。Python移植かgovernance例外かの決断必須 |
| 10 | live-trial判定(起動/完走/goal適合3軸+nudge降格+proof model機械gate) | assign-skill-design-evaluator(静的rubric) / run-plugin-package-check / orchestrate-gate-pattern.md Step5/5.5/6直交表 | 新規軸=実行acceptance。既存3層直交表への第4層追加が自然 |
| 11 | 内外ループ関係(iter-improve内側/live-trial外側) | convergence-policy.json loop_bounds(goal_seek_inner=5/content_review_inner_reeval=3/outer=3) | 第4・5の有界反復追加=loop_bounds SSOT拡張必須 |
| 12 | workflow-checklist.md物理契約 | workflow-manifest.json + validate-paradigm-coverage.py --phase-order | 同型の軽量版。既存manifest機構へ吸収可能かが論点 |
| 13 | 判定者独立性(C-5とF-2は別個体・履歴非共有) | elegant-review C4/CL-8 proposer≠approver / 二段確認規律 | 重複するが参考実装が強い。既存規律の強化版として統合可能 |
| 14 | score急上昇疑義(+10pt超は由来切り分け) | convergence-policy L3 Δベクトル/diverged検知 | 近縁だが方向が逆(既存=悪化検知、参考=改善偽装検知)。L3統合余地 |

## first_impressions (懸念点)

1. 実行単位規約の直接衝突: live-trial 4スクリプト(.sh+jq+tmux) vs forbidden-clis(jq/yq禁止・.sh新規禁止・Python stdlib正本)。Python移植・tmuxのみ例外承認・trace記録のいずれか先決。
2. INV8 と content-review の位置づけ: 「設計adequacy(静的)と実行acceptance(実走)は直交」と再定義しないと既存機構の全面否定=大規模矛盾。
3. goalアンカーの二重化: original_goal/intermediate.jsonl/drift_signal と --goal宣言/GOAL VERIFICATION の一本化必須(DUP-PASSAGE自己抵触)。
4. loop_bounds SSOT拡張: iter-improve(max-iter=5)とlive-trial poll上限を第4・5ループとして追記要。
5. INV5 vs Phase3全件消化: 適用スコープの境界宣言が必要。
6. 自己適用モデルの相違: 直接編集 vs エンジン温存・被験体コピー。feedback_contract_ssot.py述語への影響大。
7. 常設化の発火面設計: tmux+本物claude+--dangerously-skip-permissions+trust済repo前提。リモートCIはLLM起動禁止。発火点候補(Stop hook/pre-push/manifest phase/手動command)の選定が過剰設計化しやすい。
8. transcript JSONL密結合: Claude Code版依存。spec-drift検知機構への接続なしだと壊れやすい。
9. frontmatter規約非準拠: anti-goodhartはtemplate:core形式、commonCore 5必須キー欠落。run-build-skill経由の再構築が前提。
10. 重複なしの新規価値の核: N並列fresh実走eval集計・±3-5pt noise弁別・plateau/variant化・nudge降格判定は既存対応物ゼロ=統合の本体価値。残りは既存規律への増強マージが正しい形。
