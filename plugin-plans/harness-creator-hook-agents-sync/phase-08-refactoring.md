---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 完了
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的

native adapter、orchestrator、gate、hook、dispatcher の責務境界を保ったまま重複を減らす。

## 背景

旧4-reflector対称設計は重複と人工的 coupling を生んだ。新設計では共通 execution/status/lock 処理だけを C01 に集約する。

## 前提条件

- P07 local acceptance PASS。
- behavior-preserving test baseline がある。

## ドメイン知識

- C02=read-only policy/parity、C01=orchestration、C03=completion enforcement、C05=lifecycle adapter、C04=command integration。
- product-specific schema は adapter 境界の外へ漏らさない。
- criterion owner は1件、phase-wide obligation は singleton task。

## 成果物

- 重複 status/lock/digest helper の整理。
- graph node/edge density と owner duplication の再計測。

## スコープ外

- supported surface の追加。
- behavior を変える新機能。

## 完了チェックリスト

- [ ] 各責務 owner が一意。
- [ ] duplicate adapter logic がない。
- [ ] 既存 tests が無変更 green。
- [ ] unnecessary `couples_with` と全組合せ edge がない。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: status taxonomy の実装箇所が1つで各 adapter は mapping のみ持つ。
- 満たさない例: Claude/Codex 用に同じ lock/atomic logic を複製する。

### 事前解決済み判断

- 対称性より native contract とSRPを優先する。

## 参照情報

- `component-inventory.json`
- task graph density report
