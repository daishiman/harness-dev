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
プラグイン開発ドメインへの写像として、ドメイン外項目は全 DROP し、PR/リリース/marketplace 登録は本 planner の責務外として soft note に留める(評価ゲート化しない)完了フェーズ。加えて、命名・適用方式の旧 open_questions が D1=parallel_slug で確定済 (slug=slide-report-generator-v2・build_target=plugins/slide-report-generator-v2/・v1 は温存) であることと、build 段階へ golden-pin→v2 build→golden diff の適用手順を申し送ることを明記する。

## 背景
PR/リリース/marketplace 登録は本 planner の責務外(責務は計画の生成のみ)。ドメイン外項目は DROP し、リリースは soft note に留めてゲート化しない。本計画は既存 build 済 `plugins/slide-report-generator/` (v1・温存) に対する後継設計であり、適用方式と命名は D1=parallel_slug で確定した: v1 を byte コピー元テンプレートとして plugins/slide-report-generator-v2/ へ新規 (parallel) build し、v1 は破壊しない。build 段階へは golden-pin (v1 代表出力を pin)→v2 build→golden diff PASS の非回帰検証手順を申し送る。

## 前提条件
- P01-P12 が完了している。
- ドメイン外項目の DROP 判断が済んでいる。
- 命名/適用方式は D1=parallel_slug で確定済 (v2 独立 build・v1 温存) であり、build 段階へは適用手順 (golden-pin→build→golden diff) を申し送る前提を共有している。

## ドメイン知識
- 本フェーズ固有の追加ドメイン知識は無い(plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記(満たさなくても plan は完了扱い)。

## 成果物
- リリース準備完了の記録(PR/配布は soft note・評価ゲート化しない)。
- 命名/適用方式が D1=parallel_slug で確定済 (v2 独立 build・v1 温存) であることと、build 段階への適用手順 (golden-pin→build→golden diff) を申し送り事項として明記した記録。
- soft note (申し送り・評価ゲート化しない): v2 受入 (P07/P11 PASS) 後の v1 退役条件と手順 (deploy 切替 → v1 read-only アーカイブ化 → golden 再 pin)。共存期間中に v1 へ入った変更は v2 へ同時反映 (S-REFERENCES byte-identical 検査で強制)。cutover 完了までは .claude deploy namespace 衝突回避のため `scripts/build-claude-symlinks.py --exclude-plugin slide-report-generator-v2 --check --conflicts-only` で v2 を展開対象外とする。

## スコープ外
- PR 作成・marketplace 登録・バージョン bump の実行(ユーザー承認後の別作業・planner の責務外)。
- build 済み実体の修正(不備は該当 phase へ差し戻し)。
- golden-pin/build/golden diff の実行そのもの(build 段階でユーザー承認の上で実施する)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] リリースに向けた残タスクが soft note として整理されている(PR 自体はゲート化しない)。
- [ ] 命名/適用方式が D1=parallel_slug で確定済であることと、build 段階への適用手順 (golden-pin→build→golden diff) が申し送り事項として明記されている。

## 参照情報
- `references/phase-lifecycle.md` §7(DROP 読替表)。
- P01-P12 の完了。
- `goal-spec.json` open_questions(命名/適用方式は D1=parallel_slug で CLOSED・build 段階へは適用手順を申し送り)。
- 配布/PR は soft note(本 planner の責務外)。
