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
プラグイン開発ドメインへの写像として、PR/リリースは本 planner の責務外として soft note に留める (評価ゲート化しない) 完了フェーズ。既存 plugin への改善計画であるため、バージョン bump (semver) の要否判断も soft note として残す。

## 背景
PR/リリース/マーケットプレイス登録は本 planner の責務外 (責務は計画の生成のみ)。既存 plugin への additive 改善であるため破壊的変更は無い前提だが、バージョン番号の更新自体はユーザー承認後の別作業とする。リリースは soft note に留めてゲート化しない。

## 前提条件
- P01-P12 が完了している。
- 既存 capability A/B への非後退が最終確認済み (P10)。
- PR/配布はユーザー承認後に別途実行する前提を共有している。

## ドメイン知識
- 本フェーズ固有の追加ドメイン知識は無い (plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記 (満たさなくても plan は完了扱い)。

## 成果物
- リリース準備完了の記録 (PR/配布/バージョン bump は soft note・評価ゲート化しない)。

## スコープ外
- PR 作成・marketplace 登録・バージョン bump の実行 (ユーザー承認後の別作業・planner の責務外)。
- build 済み実体の修正 (不備は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] リリースに向けた残タスク (PR・バージョン bump) が soft note として整理されている (PR 自体はゲート化しない)。
- [ ] 既存 capability A/B への非後退が最終確認済みであることが記録されている。

### 受入例
全gate/evidence/docが揃い、実build後のfeature→main判断だけが人手境界として残る。

### 事前解決済み判断
本planはcommit/push/PR/deployを実行しない。

## 参照情報
- `references/phase-lifecycle.md` §7 (DROP 読替表)。
- P01-P12 の完了。
- 配布/PR は soft note (本 planner の責務外)。
