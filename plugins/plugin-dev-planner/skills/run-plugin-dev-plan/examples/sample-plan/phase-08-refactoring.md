---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
テストが緑の状態を保ったまま、SSOT 重複を排除する (lint-ssot-duplication・上書き一本化)。本プラグインでは C09/C10 の共有 script が sync/reconcile/backfill から二重定義されない単一実体であることを保証する改善フェーズ。

## 背景
共有ロジック (C09 送信ペイロード検証 / C10 冪等キー) が sync/reconcile/backfill から二重定義されると SSOT が崩れ、片方だけ修正した際にドリフトする。テスト緑を保ったまま重複を上書きで一本化し、第二消費者は import/参照で共有する tdd-refactor。

## 前提条件
- P07 の受入判定が全 PASS。
- P06 のテストが緑。
- lint-ssot-duplication が利用可能で、共有 script C09/C10 が plugin-root へ hoist 済み。

## ドメイン知識
- 上書き一本化: 重複を発見したら両方残さず一方を正本に確定し、他方は削除して import/参照へ置換する (共存縮退は禁止)。
- 第二消費者 = 正本を複製せず import/参照で共有する側 (C09/C10 は plugin-root 実体が正本)。
- tdd-refactor の不変条件: リファクタリング中もテスト緑を維持する (赤に戻ったら即巻き戻し)。

## 成果物
- SSOT 重複が 0 件になった状態 (共有 script が単一実体)。

## スコープ外
- 新機能の追加 (リファクタリングは挙動不変)。
- 受入基準・criteria の変更 (P04/P07 の責務)。
- plugin 外 (他 plugin・repo 共有層) への hoist (本 plan のスコープは plugin 内)。

## 完了チェックリスト
- [ ] lint-ssot-duplication が exit0 で、共有ロジック (C09/C10) が一本化されている。
- [ ] 第二消費者は複製でなく import/参照で共有している。
- [ ] リファクタリングによってテストが赤に戻っていない (tdd-refactor 維持)。

## 参照情報
- lint-ssot-duplication (SSOT 重複検査)。
- 共有 component C09 (validate-sync-payload) / C10 (notion-idempotency-key)。
- 後続 P09 (quality-assurance)。
