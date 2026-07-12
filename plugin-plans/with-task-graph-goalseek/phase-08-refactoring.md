---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: [C01, C02, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P08 — refactoring (改善)

## 目的
実装の重複・複雑性を解消する。特に C01(ready-set-from-checklist.py)と C02(self-reflect-append.py)が checklist item の id/depends_on 形状パース処理を重複実装していないか、また C06-C08 が surface graph/knowledge entry 形状パース処理を不必要に重複実装していないか(共通ヘルパー化の余地)を再確認する。

## 背景
Phase02 の H1 節は「write_scope tie-break という死機構を複製しない」ことを設計上の必須制約とする。実装段階で C01/C02 が独自に checklist 走査ロジックを複製してしまうと保守性が下がるため、本 phase で重複コードの有無を明示的に点検する。

## 前提条件
Phase06 テスト green・Phase07 受入判定完了。

## ドメイン知識
(引用)SSOT 原則(Layer 1 不変ルール)。差分なし。

## 成果物
リファクタリング後もテストが green のままであることの確認記録。C01/C02 間の checklist パースロジック重複、および C06-C08 間の graph/knowledge パースロジック重複の有無の確認記録(重複があれば共通関数への統合を実施)。

## スコープ外
新機能追加(本 phase は既存実装の整理のみを扱う)。write_scope tie-break 機構の追加(H1 により対象外・不要と確定済み)。

## 完了チェックリスト
- [ ] C01/C02 が checklist item パースロジックを不必要に重複していない
- [ ] C06-C08 が surface graph/knowledge entry パースロジックを不必要に重複していない
- [ ] リファクタリング後も Phase06 のテストが green のまま維持されている

### 受入例 (満たす例 / 満たさない例)
- 満たす例: C01/C02 間で checklist item のパース処理(id/depends_on 抽出)の重複が diff/grep で確認され、重複があれば共通ヘルパーへ統合したうえで Phase06 のテストが green のまま維持される。
- 満たさない例: 「重複はなさそう」という主観的記述のみで、実際のコード比較(diff/grep コマンドと出力)結果が記録されない。

### 事前解決済み判断
- 分岐点: 共通ヘルパー化した場合、C01(読み取り専用)と C02(書き込み)の責務境界が曖昧化しないか → 判断: 共通化の対象はパース処理(読み取り)のみに限定し、書き込み(追記・fail-closed 検査)ロジックは C02 に閉じたまま共有しない(SRP を維持し H1/H3 の設計境界を壊さない)。

## 参照情報
- `phase-02-design.md` H1 節
- `component-inventory.json` C01-C02/C06-C08
