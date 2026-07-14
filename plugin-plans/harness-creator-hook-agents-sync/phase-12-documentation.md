---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的

native surface、運用、rollback、unsupported、evidence state を正本ドキュメントへ同期する。

## 背景

旧説明は「Claudeと同じ仕組みをCodexへ展開」としていたため、製品差とtrust境界を隠していた。新説明は中学生向け概念と技術契約を分離する。

## 前提条件

- P11 evidence state が確定。
- official source checked_at が current。

## ドメイン知識

- Part 1: 「2種類の道具箱には置き場所のルールが違う。各道具箱の正しい入口を使い、置き忘れだけを自動チェックする」。
- Part 2: dual manifest、repo marketplace、trust、adapter、lock/atomic/hash、failure taxonomy、freshness。
- unsupported agents/commands は limitation と follow-up trigger を明記する。

## 成果物

- `references/native-surface-contract.md`。
- README/CHANGELOG/lessons-learned/capability-build説明。
- install/enable/trust/upgrade/re-trust/uninstall/rollback runbook。
- unsupported/deferred register と official-source refresh policy。

## スコープ外

- Notion feedback。
- public marketplace publish guide。

## 完了チェックリスト

- [ ] Part1/Part2、変更差分、影響、rollback、今後の課題が揃う。
- [ ] Claude/Codex surface表とowner表が正本化される。
- [ ] user gate と evidence state が記載される。
- [ ] unsupported/deferred の再判定 trigger がある。
- [ ] stale「全symlink/TOML対称化」記述が0。
- [ ] local projection (`repo-present ∩ exact project-enabled identity`) と product runtime trust gate を別語彙で説明する。
- [ ] repo-relative/relocatable command、duplicate hook dedupe、marketplace identity、ledger freshness、owner-token lock の current 契約が runbook/pipeline boundary/README で一致する。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 初見者が marketplace登録とplugin trustの違いを理解でき、operatorがrollbackできる。
- 満たさない例: 「自動反映される」とだけ書き前提とfailureを省略する。

### 事前解決済み判断

- distributable:false でも repo-local marketplace は discovery/install 用に文書化する。

## 参照情報

- `goal-spec.json`
- P11 evidence ledger
