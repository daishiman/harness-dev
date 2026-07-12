# ROADMAP

`skill-intake` plugin の短期 / 中期 / 長期ロードマップ。harness-creator 設計書 33 章 `change-governance` の運用方針に従い、各層は目標・成果物・成功指標 (KPI) を明示する。

## 短期 (本 PR 〜 次 1-2 スプリント)

**目標**: harness-creator の CapabilityManifest 仕様へフル準拠し、composition manifest を運用開始する。**成果物**: `plugin-composition.yaml`(capabilities + 依存 DAG + governance)、本 CHANGELOG.md / ROADMAP.md の運用開始、`EVALS.json` の baseline 記録。**KPI**: PKG-002〜008 検査 100% PASS、CapabilityManifest lint 100% PASS、命名規約 100% PASS。

## 中期 (3-6 ヶ月)

**目標**: 11 phase の handoff JSON 契約を強化し、非エンジニア向けヒアリング品質を計測可能にする。**成果物**: phase 間 schema の網羅、Gate A 否認率・図解カバレッジ・Notion 公開成功率の EVALS 自動集計、assign-notion-fidelity-evaluator の粒度判定精度向上。**KPI**: handoff schema validate 取りこぼし率 < 5%、図解カバレッジ 100%(全セクション最低 1 枚)、Notion 公開成功率 >= 95%。

## 長期 (6 ヶ月以降)

**目標**: intake → harness-creator (単一 skill 規模) / plugin-dev-planner (mode P: plugin 規模構想、0.1.2 で契約化済み) の三段パイプライン引き渡しの自動化と、ヒアリング資産(question-bank / vocabulary-tiers)の自己改善ループを確立する。**成果物**: run-intake-next-action の引き渡しモード判定精度向上、eval-log からの question-bank 自動更新パイプライン、非技術者語彙(vocabulary-tiers)の使用実績に基づく継続改善。**KPI**: 引き渡しモード判定の妥当率 >= 90%、question-bank 更新の月次反映数 >= 2 本、非エンジニア完走率 >= 80%。
