# Example: Elegant Review on Skill `run-build-skill`

- target_type: skill
- target_path: {{PROJECT_ROOT}}/.claude/skills/run-build-skill/
- reviewed_at: 2026-05-18T10:00:00Z
- loop_count: 2

## 1. Phase1 観察 (Agent 1)
- Purpose: 新規Skillの骨格を自動生成
- Scope: SKILL.md + references + scripts
- Assumptions: rubricは ref-skill-design-rubric 準拠
- Stakeholders: skill作者 / レビュー担当 / 利用者

## 2. 30思考法 findings (要約)

### A. 論理分析系
- 批判的思考: 隠れた前提「scripts必須」を検出 → 改善
- 演繹思考: rubric準拠の前提から雛形を導出 → PASS
- 帰納的思考: 既存5Skillの共通パターンを抽出済 → PASS
- アブダクション: description不足の真因仮説 → 改善
- 垂直思考: 実行不能手順の根本原因まで深掘り → PASS

### B. 構造分解系
- 要素分解: scripts内の責務が混在 → C2 FAIL → 改善
- MECE: SKILL.md / refs / scripts / templates の4分類は MECE → PASS
- 2軸思考: trigger軸とrole軸の分離を確認 → PASS
- プロセス思考: brief→build→lint→evaluate の接続を確認 → PASS

### C. メタ抽象系
- メタ思考: 「rubricに過適合していないか」自問あり → PASS
- 抽象化思考: build vs review の抽象境界明瞭 → PASS
- ダブル・ループ思考: 生成方式自体を brief IR 中心へ見直し → 改善

### D. 発想拡張系
- ブレインストーミング: 代替案20件以上 → PASS
- 水平思考: 別言語実装の可能性検討 → PASS
- 逆説思考: 高品質と高速量産の両立条件を検討 → PASS
- 類推思考: cookiecutter類似 → PASS
- if思考: 100本作成時の重複リスクを検討 → 改善
- 素人思考: 初見で入口が分かるか確認 → PASS

### E. システム系
- システム思考: rubric→skill→review のループ把握 → PASS
- 因果関係分析: path参照切れが検証失敗を起こす連鎖を確認 → C4 注意
- 因果ループ: rubric改訂→既存skill波及 → C4 注意

### F. 戦略価値系
- トレードオン思考: 自動検査と承認ゲートを両立 → PASS
- プラスサム思考: 作成者・レビュア双方の確認負荷を削減 → PASS
- 価値提案思考: 誰でも同じ品質でSkillを増やす価値に集中 → PASS
- 戦略的思考: P0 path/lint、P1 manifest、P2 governance に優先順位付け → PASS

### G. 問題解決系
- why思考: rubric違反の真因まで到達 → PASS
- 改善思考: 小さな修正単位へ分割 → PASS
- 仮説思考: path と manifest 統合検査で欠陥を事前検出できる仮説 → PASS
- 論点思考: 実行可能性、登録、機械強制の3論点へ集約 → PASS
- KJ法: 参照切れ、登録漏れ、宣言先行、依存方向、評価ゲートに分類 → PASS

## 3. 4条件 Gate
| 条件 | Loop1 | Loop2 |
|------|-------|-------|
| C1 矛盾なし | PASS | PASS |
| C2 漏れなし | FAIL | PASS |
| C3 整合性あり | PASS | PASS |
| C4 依存関係整合 | FAIL | PASS |

## 4. 改善パッチ (Agent5)
- Loop1→2 で scripts/ の責務分割、rubric波及検知hookを追加

## 5. 完了判定
- ALL PASS: yes (Loop 2)
