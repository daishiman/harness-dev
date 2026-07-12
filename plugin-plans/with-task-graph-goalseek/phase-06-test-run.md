---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P06 — test-run (テスト)

## 目的
Phase05 実装に対し Phase04 で設計した全テストケースを実行し、C01-C04/C06-C08 の tests_min>=80 と C04 拡張 self-test、C08 lint self-test を含む全テストが green であることを確認する。

## 背景
tdd-green(Phase05)の到達を実測で裏付けるフェーズであり、goal-spec checklist C11(11 ゲート全 exit0)の前提となる。

## 前提条件
Phase05 実装完了。

## ドメイン知識
(引用)harness-ratchet 規約(per-script coverage record 添付・floor を下げない)。差分なし。

## 成果物
テスト実行結果(coverage>=80% 記録)。`eval-log/coverage/scripts/` 配下への C01/C02/C06/C07/C08 各 script の coverage record 新規追加。C03(render-combinators.py)/C04(lint-goal-seek.py)は既存 script の Edit であり既存 coverage record の更新。

## スコープ外
実装修正自体(テスト red の場合は Phase08 refactoring または Phase05 への差し戻しへ委譲)。

## 完了チェックリスト
- [ ] C01-C04/C06-C08 の単体テストが green かつ coverage>=80
- [ ] C04 拡張 self-test が exit0
- [ ] C08 lint-capability-graph-knowledge.py が generated harness の dependency graph knowledge consult を検査し exit0
- [ ] C05 の統合テスト(brief.goal_seek.engine=task-graph 指定生成物への lint-goal-seek.py 拡張 self-test + lint-capability-graph-knowledge.py 実行)が exit0

### 受入例 (満たす例 / 満たさない例)
- 満たす例: `eval-log/coverage/scripts/` 配下に C01(`ready-set-from-checklist.py`)/C02(`self-reflect-append.py`)/C06(`extract-capability-dependency-graph.py`)/C07(`record-capability-graph-knowledge.py`)/C08(`lint-capability-graph-knowledge.py`)の per-script coverage record が新規添付され、coverage>=80% が記録されている。
- 満たさない例: 「テストは green」とだけ記述され、coverage record ファイルへの言及や harness-ratchet floor 検証の実行結果が示されない。

### 事前解決済み判断
- 分岐点: C03/C04(既存 script への Edit)は新規 coverage record を追加すべきか既存記録を更新すべきか → 判断: C03/C04 は新規スクリプトでなく既存 script の拡張のため既存 coverage record を更新するのみとし、C01/C02/C06/C07/C08(新規スクリプト)のみ新規 record を追加する(harness-ratchet floor の二重計上・過大申告を避ける)。

## 参照情報
- `eval-log/harness-coverage.json`
- `component-inventory.json` C01-C08
