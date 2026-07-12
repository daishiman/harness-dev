---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P13 — release (完了/PR・リリース)

## 目的
プラグイン開発ドメインへの写像として、UBM 固有のドメイン外項目 (Obsidian 固有の Dataview クエリ表示や個人 vault 運用慣習等) は全 DROP し、PR/リリースは本 planner の責務外として soft note に留める (評価ゲート化しない) 完了フェーズ。

## 背景
PR/リリース/マーケットプレイス登録は本 planner の責務外 (責務は計画の生成のみ)。UBM は distributable:false (個人利用前提) のため、ユーザー承認後も配布は行わず個人利用に留める。Obsidian vault 固有の運用慣習 (Dataview クエリ・vault 内リンク記法等) はプラグイン開発ドメインに写像できないため DROP し、リリースは soft note に留めてゲート化しない。

## 前提条件
- P01-P12 が完了している。
- ドメイン外項目 (Dataview クエリ・vault 内リンク記法等) の DROP 判断が済んでいる。
- distributable:false のため、PR/配布はユーザー承認後も個人利用に留まる前提を共有している。

## ドメイン知識
- 本フェーズ固有の追加ドメイン知識は無い (plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記 (満たさなくても plan は完了扱い)。

## 成果物
- 全フェーズ (P01-P12) の完了条件が満たされていることの最終確認結果。
- リリース準備完了の記録 (PR/配布は soft note・評価ゲート化しない。distributable:false のためユーザー承認後も個人利用に留める案内)。
- Obsidian vault 固有の運用慣習 (Dataview クエリ・vault 内リンク記法等) のドメイン外 DROP 記録。

## スコープ外
- PR 作成・marketplace 登録・バージョン bump の実行 (ユーザー承認後の別作業・planner の責務外。かつ distributable:false のため通常は実行されない)。
- build 済み実体の修正 (不備は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] リリースに向けた残タスクが soft note として整理されている (PR 自体はゲート化しない)。
- [ ] ドメイン外項目 (Dataview クエリ・vault 内リンク記法等) が写像対象外として DROP 記録されている。

## 参照情報
- `references/phase-lifecycle.md` §7 (DROP 読替表)。
- P01-P12 の完了。
- 配布/PR は soft note (本 planner の責務外、distributable:false)。
