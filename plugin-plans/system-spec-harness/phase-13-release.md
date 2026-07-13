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
プラグイン開発ドメインへの写像として、UBM 固有の IPC/Cloudflare 等は全 DROP し、PR/リリースは本 planner の責務外として soft note に留める (評価ゲート化しない) 完了フェーズ。marketplace 配布可否は distributable:true として GAP-DISTRIBUTION-DECISION の resolution で確定済であり、その解決記録を引き継いで配布フローへ進める状態にする。

## 背景
PR/リリース/マーケットプレイス登録は本 planner の責務外 (責務は計画の生成のみ)。UBM 固有の IPC/Cloudflare/D1/Workers 等ドメイン外項目は DROP し、リリースは soft note に留めてゲート化しない。PR/配布が別途実行される前提を明示する完了フェーズ。goal-spec の open_questions にあった「marketplace 配布可否」はユーザー承認により distributable:true で確定済 (GAP-DISTRIBUTION-DECISION resolved・commit 00cf8f7) であり、その解決記録もここで明示的に引き継ぐ。

## 前提条件
- P01-P12 が完了している。
- ドメイン外項目 (IPC/Cloudflare/D1/Workers) の DROP 判断が済んでいる。
- PR/配布はユーザー承認後に別途実行する前提を共有している。

## ドメイン知識
- 本フェーズ固有の追加ドメイン知識は無い (plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記 (満たさなくても plan は完了扱い)。

## 成果物
- リリース準備完了の記録 (PR/配布は soft note・評価ゲート化しない)。
- distributable:true 確定 (GAP-DISTRIBUTION-DECISION resolved・commit 00cf8f7) の解決記録を open_issues から引き継いだ記録。

## スコープ外
- PR 作成・marketplace 登録・バージョン bump の実行 (ユーザー承認後の別作業・planner の責務外)。
- build 済み実体の修正 (不備は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] リリースに向けた残タスクが soft note として整理されている (PR 自体はゲート化しない)。
- [ ] ドメイン外項目 (IPC/Cloudflare 等) が写像対象外として DROP 記録されている。
- [ ] distributable:true の確定が open_issues の GAP-DISTRIBUTION-DECISION (status: resolved) として記録され、その解決記録が引き継がれて配布フローへ進める状態になっている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: distributable:true の確定が open_issues (GAP-DISTRIBUTION-DECISION resolved・利用単位の判断を含む) の解決記録として引き継がれ、PR/配布は soft note に留まっている。
- 満たさない例: リリース準備の完了条件に PR merge や marketplace 登録を含めてゲート化する。

### 事前解決済み判断
- 分岐点: marketplace 登録まで本 plan で扱うか → 判断: 扱わない (planner の責務は計画生成のみ・配布はユーザー承認後の別作業として soft note 化)。

## 参照情報
- `references/phase-lifecycle.md` §7 (DROP 読替表)。
- P01-P12 の完了。
- 配布/PR は soft note (本 planner の責務外)。
