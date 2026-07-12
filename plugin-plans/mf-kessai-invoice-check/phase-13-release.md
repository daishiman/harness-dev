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
プラグイン開発ドメインへの写像として、UBM 固有の IPC/Cloudflare 等は全 DROP し、PR/リリースは本 planner の責務外として soft note に留める (評価ゲート化しない) 完了フェーズ。

## 背景
PR/リリース/マーケットプレイス登録は本 planner の責務外 (責務は計画の生成のみ)。UBM 固有の IPC/Cloudflare/D1/Workers 等ドメイン外項目は DROP し、リリースは soft note に留めてゲート化しない。C01〜C06 の build 完了後、ユーザー承認を経て別途 PR (feature→main) が実行される前提を明示する完了フェーズ。

## 前提条件
- P01-P12 が完了している。
- ドメイン外項目 (IPC/Cloudflare/D1/Workers) の DROP 判断が済んでいる。
- PR/配布はユーザー承認後に別途実行する前提を共有している。

## ドメイン知識
本フェーズ固有の追加ドメイン知識は無い (plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記 (満たさなくても plan は完了扱い)。

## 成果物
- リリース準備完了の記録 (PR/配布は soft note・評価ゲート化しない)。

## スコープ外
- PR 作成・marketplace 登録・バージョン bump の実行 (ユーザー承認後の別作業・planner の責務外)。
- build 済み実体 (C01〜C06) の修正 (不備は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] リリースに向けた残タスクが soft note として整理されている (PR 自体はゲート化しない)。
- [ ] ドメイン外項目 (IPC/Cloudflare 等) が写像対象外として DROP 記録されている。

## 参照情報
- `references/phase-lifecycle.md` §7 (DROP 読替表)。
- P01-P12 の完了。
- 配布/PR は soft note (本 planner の責務外)。
