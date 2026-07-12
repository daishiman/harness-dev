---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
P07 の RTM 確定後、テストを green に保ったまま (goal-spec C1-C8 の合格を崩さないまま) 実装仕様の重複・水増しを見直し、no-split threshold・SRP 分割線が引き続き妥当かを再確認する。

## 背景
tdd-refactor は「テストを壊さずに設計を洗練する」フェーズであり、本 plan では実装仕様 (P05) の再点検として位置づける。特に C02 (`validate-procedure-completeness.py`) が独立 component に値するか (2 消費者・独立検証・280 行超のいずれかの no-split threshold) を再確認する。

## 前提条件
- P07 の RTM が確定し全 checklist 項目が component/phase に対応付けられている。
- P06 のテストケースが (build 側で) green であることを前提とする。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **no-split threshold**: script が独立 component へ昇格する条件 (複数 skill 共有/独立検証/280 行超のいずれか)。単一 skill 専用 script は親 skill へ畳む。

## 成果物
- **C02 独立性の再確認**: `validate-procedure-completeness.py` は C01 (Phase4 完了チェック) と C04 拡張 (Phase9 ハンドオフゲート) の 2 消費者を持つため、no-split threshold (複数消費者) を引き続き満たす。contamination check (goal-spec C7) の追加は C02 の責務拡張であり消費者関係は不変のため、C01 へ畳み込む水増し回避判断は維持する。
- **重複実装の排除確認**: procedure 完全性判定ロジックと contamination check ロジックが C01/C03/C04 内へ重複実装されていないか (いずれも C02 への一元化が維持されているか) を再確認する。
- **schema/handoff-contract 差分の整合再確認**: P05 で仕様化した `interview.schema.json`/`intake.schema.json`/`handoff-contract.md`/`to-be-vocabulary-patterns.md` の差分が P01 のギャップ一覧 (G1-G7) と過不足なく対応しているかを再確認する。

## スコープ外
- 新規機能の追加 (リファクタリングは既存受入基準を維持したままの整理に限定)。
- テストケース自体の変更 (P04 で確定した受入テストを変更しない)。

## 完了チェックリスト
- [ ] C02 が引き続き no-split threshold (2 消費者以上) を満たし、C01/C03 への畳み込みを不要と判定した。
- [ ] procedure 完全性判定ロジックおよび contamination check ロジックの重複実装が無いことを確認した。
- [ ] P05 の schema/handoff-contract/to-be-vocabulary-patterns.md 差分が P01 のギャップ一覧 (G1-G7) と過不足なく対応することを確認した。

## 参照情報
- P02 (no-split threshold 判定の初出)。
- P05 (実装仕様、再点検対象)。
- 後続 P09 (品質保証: quality_gates 一式の充足確認)。
