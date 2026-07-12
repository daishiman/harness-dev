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
プラグイン開発ドメインへの写像として、ドメイン外項目は全 DROP し、PR/リリース/marketplace 登録は本 planner の責務外として soft note に留める(評価ゲート化しない)完了フェーズ。加えて、goal-spec の open_questions(plan_dir の -v2 統合是非・in-place改修か新規buildか)が build 段階の判断として未確定のまま残っていることを明記する。

## 背景
PR/リリース/marketplace 登録は本 planner の責務外(責務は計画の生成のみ)。ドメイン外項目は DROP し、リリースは soft note に留めてゲート化しない。本計画は既存 build 済 `plugins/slide-report-generator/` に対する後継設計であり、実際の適用方式(既存への in-place 改修か、新規ビルドか)と plan_dir の最終命名(-v2 のまま残すか既存 plan へ統合するか)は build 段階でユーザー承認の上で判断される未確定事項として引き継ぐ。

## 前提条件
- P01-P12 が完了している。
- ドメイン外項目の DROP 判断が済んでいる。
- open_questions(plan_dir命名/適用方式)が未確定のまま build 段階へ引き継がれる前提を共有している。

## ドメイン知識
- 本フェーズ固有の追加ドメイン知識は無い(plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記(満たさなくても plan は完了扱い)。

## 成果物
- リリース準備完了の記録(PR/配布は soft note・評価ゲート化しない)。
- open_questions(plan_dir命名の是非・in-place改修か新規buildか)を build 段階への申し送り事項として明記した記録。

## スコープ外
- PR 作成・marketplace 登録・バージョン bump の実行(ユーザー承認後の別作業・planner の責務外)。
- build 済み実体の修正(不備は該当 phase へ差し戻し)。
- open_questions の確定判断そのもの(build 段階でユーザー承認の上で判断する)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] リリースに向けた残タスクが soft note として整理されている(PR 自体はゲート化しない)。
- [ ] open_questions(plan_dir命名/適用方式)が build 段階への申し送り事項として明記されている。

## 参照情報
- `references/phase-lifecycle.md` §7(DROP 読替表)。
- P01-P12 の完了。
- `goal-spec.json` open_questions(build 段階への申し送り)。
- 配布/PR は soft note(本 planner の責務外)。
