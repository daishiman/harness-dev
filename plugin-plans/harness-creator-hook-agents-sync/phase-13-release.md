---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 進行中
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P13 — release (完了・PR/リリース)

## 目的

local implementation、runtime activation、git publish を独立 gate として完了させ、rollback可能な状態で統合する。

## 背景

旧計画は release で10 pluginへ一括 apply しつつ、enabled/trusted scope を未整理にしていた。新計画では source selection と user gate を満たすまで一括 apply を禁止する。

## 前提条件

- P12 documentation 完了。
- local acceptance PASS。
- runtime install/enable/trust と git operations はそれぞれ別の user approval を得る。

## ドメイン知識

- Gate R1: repo-owned apply + check。
- Gate R2: Codex install/enable/trust + new-session smoke。
- Gate R3: commit/push/PR。
- Gate R4: merge後 observation/rollback readiness。
- まとめ承認は禁止する。

## 成果物

- R1-R4 evidence と approval record。
- current artifact digest、changed path inventory、rollback commands/results。
- runtime verified または明示 pending state。

## スコープ外

- public marketplace publish。
- approval なしの global/user state mutation。

## 完了チェックリスト

- [ ] R1 apply→check が repo-present / exact project-enabled identity の local projection scope で exit0。install/trust は R2 user gate と分離される。
- [ ] C02 native parity/freshness PASS。
- [ ] R2 trust前 non-run / trust後 SessionStart run / concurrency safety PASS。
- [ ] uninstall/prune/rollback PASS。
- [ ] R3 は明示承認後のみ実行。
- [ ] local observation と failure remediation が記録される。R4 merge後 observation は R3 が `not_applicable` の current wave では同じく非実行と明記する。
- [ ] PR 準備時は `make native-surfaces-pr-ready` が common TOML の hook/discovery 契約と plugin manifest/marketplace 正本を結合し、`.claude/settings.json`、`.codex/hooks.json`、`.codex/config.toml`、`.agents/plugins/marketplace.json` を apply→check する。`.claude/{skills,agents,commands}` を含む managed projection 差分が review 対象に含まれ、本 preflight は commit/push/PR を実行しない。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: R1だけ完了なら local_implementation_pass とし、R2未承認をruntime pendingで残す。
- 満たさない例: route5件doneだけで完了、または全pluginへ無条件applyする。

### 事前解決済み判断

- apply、trust、git publish は別承認。
- current local wave では R1、local observation/remediation、reproducible fixture を実行する。R2 は `pending_user_gate`、R3 の commit/push/PR は user 指示により `not_applicable`。merge が存在しないため R4 merge後 observation も current wave では非実行とし、runtime SessionStart observation は R2 の `P13-x-03` が所有する。

## 参照情報

- P11 evidence ledger
- P12 runbook
- `handoff-run-plugin-dev-plan.json` execution_policy
