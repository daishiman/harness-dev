# エージェント1〜5 責務定義 (Layer5 機械可読化)

## Agent 1: elegant-reset-observer (Phase1)
- 役割: 思考リセットして対象を俯瞰観察
- 入力: target_type, target_path
- 出力: { purpose, scope, assumptions, stakeholders, raw_observations[], concrete_values_to_abstract[] }
- 担当思考法: なし (観察のみ、評価しない)
- 禁止: rubric参照、score算出、改善提案

## Agent 2: elegant-logical-structural-analyst (Phase2 並列)
- 役割: 論理分析+構造分解で対象を解剖
- 入力: Agent1出力
- 出力: findings[] (paradigm × C1〜C4 マトリクス、9 paradigms分)
- 担当思考法 (9): 批判的思考/演繹思考/帰納的思考/アブダクション/垂直思考/要素分解/MECE/2軸思考/プロセス思考

## Agent 3: elegant-meta-divergent-analyst (Phase2 並列)
- 役割: メタ抽象+発想拡張で別視点を生成
- 入力: Agent1出力
- 出力: findings[] (paradigm × C1〜C4、9 paradigms分) + reusable_abstraction + template_variables + negative_cases
- 担当思考法 (9): メタ思考/抽象化思考/ダブル・ループ思考/ブレインストーミング/水平思考/逆説思考/類推思考/if思考/素人思考

## Agent 4: elegant-system-strategic-analyst (Phase2 並列)
- 役割: システム+戦略+問題解決で全体最適と実行性を評価
- 入力: Agent1出力
- 出力: findings[] (paradigm × C1〜C4、12 paradigms分)
- 担当思考法 (12): システム思考/因果関係分析/因果ループ/トレードオン思考/プラスサム思考/価値提案思考/戦略的思考/why思考/改善思考/仮説思考/論点思考/KJ法

## Agent 5: elegant-improvement-executor (Phase3)
- 役割: findings を取り込みパッチを生成・適用
- 入力: 集約された findings.json
- 出力: patched target + updated findings.json + 4-condition gate結果
- 完了条件: C1〜C4 すべて PASS、または loop=3 到達でエスカレーション
- 並列対応: 独立パッチは並列適用可
- 変数化責務: 固有名詞・固定パス・固定URL・固定ownerを、変数・テンプレート・config example へ昇格する

## 独立性原則
- Phase2 の3エージェントは互いの中間出力を参照しない
- Agent5 のみが全findingsを統合
