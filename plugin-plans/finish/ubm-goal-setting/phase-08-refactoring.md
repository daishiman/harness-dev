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
テストが緑の状態を保ったまま、SSOT 重複を排除する (lint-ssot-duplication・上書き一本化)。本プラグインでは capability A (目標設定対話・info-collector が読取) と capability B (ナレッジ同期・knowledge-extractor が書込) が、plugin-root 共有 knowledge substrate (`plugins/ubm-goal-setting/knowledge/`) + schema.json 契約 + Rule A-F (C15 knowledge-extractor が保持) を対称参照する構造が二重定義されない単一実体であることを保証する改善フェーズ。knowledge はもはや外部 (vault) 前提ではなく、L1 curated (vendor seed) / L3 bookkeeping (seed+plugin同梱 knowledge/ への直書き) として plugin 内に実在するデータであることを前提に dedup 検査する。

## 背景
共有ロジック (knowledge 格納規約 Rule A-F・schema.json 契約) が capability A/B から二重定義されると SSOT が崩れ、片方だけ修正した際にドリフトする。本プラグインは移植プロジェクトのため、旧資産 (`.claude/skills/ubm-goal-setting/` 配下に散在していた規約) を plugin-root へ hoist する過程で重複が生じやすい。テスト緑を保ったまま重複を上書きで一本化し、第二消費者は import/参照で共有する tdd-refactor。

## 前提条件
- P07 の受入判定が全 PASS。
- P06 のテストが緑。
- lint-ssot-duplication が利用可能で、schema.json/Rule A-F が plugin-root (`plugins/ubm-goal-setting/knowledge/`) へ hoist 済み。

## ドメイン知識
- 上書き一本化: 重複を発見したら両方残さず一方を正本に確定し、他方は削除して import/参照へ置換する (共存縮退は禁止)。
- 第二消費者 = 正本を複製せず import/参照で共有する側 (C16 の info-collector が読取、C17 の knowledge-extractor が書込む schema.json/Rule A-F は plugin-root 実体が正本)。
- tdd-refactor の不変条件: リファクタリング中もテスト緑を維持する (赤に戻ったら即巻き戻し)。

## 成果物
- SSOT 重複が 0 件になった状態 (ナレッジ格納規約 Rule A-F・schema.json が plugin-root 共有の単一実体、C16/C17 双方が同一ファイルを対称参照)。

## スコープ外
- 新機能の追加 (リファクタリングは挙動不変)。
- 受入基準・criteria の変更 (P04/P07 の責務)。
- plugin 外 (他 plugin・repo 共有層) への hoist (本 plan のスコープは plugin 内)。

## 完了チェックリスト
- [ ] lint-ssot-duplication が exit0 で、共有ロジック (schema.json/Rule A-F) が一本化されている。
- [ ] 第二消費者 (C16 info-collector / C17 knowledge-extractor) は複製でなく import/参照で共有している。
- [ ] リファクタリングによってテストが赤に戻っていない (tdd-refactor 維持)。

## 参照情報
- lint-ssot-duplication (SSOT 重複検査)。
- 共有 surface `plugins/ubm-goal-setting/knowledge/schema.json` (C16/C17 対称参照)。
- 後続 P09 (quality-assurance)。
