---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P13 — release (完了/リリース)

## 目的
build 完了後の `plugins/skill-intake/.claude-plugin/plugin.json` バージョン更新・PR 化・後段ハンドオフ (`run-skill-create`/`run-plugin-dev-plan` は本改善では不要、build 実行者自身が C01-C04 を直接実装する) の完了条件を宣言する。

## 背景
本 plan は既存 plugin (skill-intake) への delta 拡張であり、artifact_class=existing-plugin-update のため新規 plugin scaffold は発生しない。release フェーズの成果物は「version bump + PR」という既存プラグイン更新の標準完了条件に限定される。

## 前提条件
- P12 のドキュメント更新仕様が確定している。
- P10 final-gate / P11 evidence が完了している。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **PATCH bump**: 既存 entry_points (commands/skills/agents/hooks) を変更しない後方互換な機能追加のため、`.claude-plugin/plugin.json` の version は 0.1.2 → 0.1.3 (PATCH) とする。

## 成果物
- **version bump 仕様**: `plugins/skill-intake/.claude-plugin/plugin.json` の `version` を `0.1.2` → `0.1.3` へ更新する (entry_points は変更なし)。
- **PR 化仕様**: 変更対象ファイル一覧 (C01: `skills/run-intake-interview/` 配下 Edit 差分 + 新規 `references/to-be-vocabulary-patterns.md`、C02: `scripts/validate-procedure-completeness.py` 新規 (contamination check 含む)、C03: `skills/run-intake-finalize/` 配下 Edit 差分、C04: `scripts/quality_gate.py` Edit 差分、root `references/handoff-contract.md`/`references/intake.schema.json`/`README.md`/`CHANGELOG.md`) を PR 説明に列挙する。
- **完了条件**: build 後の受入で goal-spec checklist C1-C8 が全て `done: true` へ更新され、P10 final-gate の PASS 記録と P11 evidence の証跡に加え、P11 後の実証レビュー sign-off が揃っている。

## スコープ外
- 実際の PR 作成・マージ (本 plan は仕様書であり、実際の git 操作は build 実行者が本 plan を消費した後に行う)。
- marketplace/bundle 設定の変更 (`bundles: [xl-skills-full, xl-skills-intake]` は既存のまま変更しない)。

## 完了チェックリスト
- [ ] version bump 仕様 (0.1.2→0.1.3) が明記されている。
- [ ] PR 化対象ファイル一覧が C01-C04 (to-be-vocabulary-patterns.md 新設を含む) + root 文書更新を過不足なく列挙している。
- [ ] goal-spec checklist C1-C8 の完了条件 (build 後受入で全 `done: true`) が明記されている。

## 参照情報
- `plugins/skill-intake/.claude-plugin/plugin.json` (version bump 対象)。
- `plugin-plans/skill-intake/goal-spec.json` (checklist 完了条件の正本)。
- P12 (文書更新仕様)。
