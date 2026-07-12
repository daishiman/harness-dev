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
プラグイン開発ドメインへの写像として、UBM 固有の IPC/Cloudflare 等は全 DROP し、PR/リリース(既存 version 0.3.0 の改善同期・配布更新)は本 planner の責務外として soft note に留める(評価ゲート化しない)完了フェーズ。

## 背景
PR/リリース/マーケットプレイス登録は本 planner の責務外(責務は計画の生成のみ・goal-spec constraints「本 plan は計画成果物のみを生成し実コード・実プラグインは生成しない」に対応)。ユーザー承認後に後段 `/capability-build` 等が実 build と配布を実行する前提を明示する完了フェーズ。

## 前提条件
- P01-P12 が完了している。
- ドメイン外項目(IPC/Cloudflare/D1/Workers)の DROP 判断が済んでいる。
- PR/配布はユーザー承認後に別途実行する前提を共有している(C13 に対応)。

## ドメイン知識
- 本フェーズ固有の追加ドメイン知識は無い(plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記(満たさなくても plan は完了扱い)。

## 成果物
- リリース準備完了の記録(PR/配布は soft note・評価ゲート化しない)。既存 version 0.3.0 の改善説明同期準備。

## スコープ外
- PR 作成・marketplace 登録・バージョン bump の実行(ユーザー承認後の別作業・planner の責務外)。
- build 済み実体の修正(不備は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] 本 plan(index + 13 phase files + component-inventory.json + handoff + task-graph)のみが生成され、実コード・実プラグインが生成されていないことを確認している(C13)。
- [ ] リリースに向けた残タスク(manifest description 同期/PR)が soft note として整理されている(PR 自体はゲート化しない)。

## 参照情報
- `references/phase-lifecycle.md` §7(DROP 読替表)。
- P01-P12 の完了。
- 配布/PR は soft note(本 planner の責務外)。
