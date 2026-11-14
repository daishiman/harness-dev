# Phase 3 計画 iter4（max_iter 超過・利用者の明示指示による追加修正）

- 根拠: loop3 で status=incomplete（4条件すべて FAIL、残り12件）。利用者の指示は「12件すべて直す」「#4 は案A」（2026-11-03）。
- 位置づけ: convergence-policy の max_iterations=3 を超える追加修正。loop3 の verdict（incomplete）は書き換えない。iter4 の結果は loop4 として別に記録し、判定はその findings から導出する。
- 修正前の差分: `pre-iter4.patch`（追跡ファイルのみ。未追跡: tests/test_goal_alignment.py、knowledge/knowledge-relations.json）

## 確定事項 Q（利用者承認）

- Q: 月報の【今月の最重要数字】に、当月の売上目標の金額を1行置く（`今月の売上目標：{金額}`。注記2行の後、人数・回数・件数の前）。1年目標の有無にかかわらず置く。週報（売上＋核心成果）・1年（売上と人数の対）と同じ「売上＋人数」の形にそろえる。確定事項 M〜P は維持する。

## レーン（書き込み範囲は重ならない）

| レーン | 書き込み範囲 | 対象 |
|---|---|---|
| X | references/output-formats.md、assets/golden-sample-weekly.md、assets/action-goals-best-practices.md、SKILL.md、既存 tests（最重要数字の関連だけ）、scripts（必要なら） | #2、#4（案A）、#6（G の初回分岐）、#11、#12 |
| Y | prompts/R1・R3・R5、assets/interview-quick-templates.md、references/thinking-guide.md | #1、#8、R3:49/130、smell（R5:163、thinking-guide:322） |
| Z | agents/goal-reviewer.md、agents/phase3-coordinator.md、references/agent-goal-reviewer-report-template.md、run-ubm-knowledge-sync/assets/kitahara-principles-db.md、run-ubm-consult/references/consult-frames.md | #3、#5、#6（reviewer 側）、#9、#10、smell（coordinator:32、項目6のセクション指定） |
| W | references/data-contract.md、新規 tests/test_field_closure.py | #7（DC の2列と閉包テスト、旧語の類型の正規表現検査） |
| orchestrator | CHANGELOG.md（0.9.3 の項）、統合と全体テスト | CHANGELOG:25 の訂正、iter4 の記載 |

## 完了条件

1. 各レーンの指定箇所が直り、旧語の類型（`追う」?(で|では)なく`、`接点.{0,8}増`）がプラグイン内（knowledge/・引用行・CHANGELOG の過去版・version-history を除く）で0件。
2. 新しいフィールドの閉包テストを含めて pytest が全件 PASS。
3. loop4 の再評価（変更箇所に絞った3レーン）で4条件の判定を導出する。
