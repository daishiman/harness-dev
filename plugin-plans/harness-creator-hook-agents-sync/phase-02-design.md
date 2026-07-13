---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 完了
gate_type: none
entities_covered: [C01, C02, C03, C04, C05]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的

native surface、owner、activation、failure、依存 DAG を確定し、各変更先に一意の owner を割り当てる。

## 背景

旧設計は Claude の file+settings 方式を Codex へ対称コピーし、5 route と repo integration patch の責務が混在していた。新設計は validator→orchestrator→completion gate/SessionStart→dispatcher の一方向 DAG とする。

## 前提条件

- P01 C1-C10 が正本。
- Claude の local projection scope と product runtime activation/trust gate を別状態として確定する。
- repo marketplace は public distribution ではない。

## ドメイン知識

- 代替案: 全symlink、project hooks集約、native plugin、dual-manifest adapter、repo marketplace、explicit skill config。
- 採用: native plugin + dual-manifest parity + repo marketplace。project固有 hook は `.codex/hooks.json` に残す。
- DAG: `C02 → C01 → {C03,C05} → C04`。`couples_with` は使わない。

## 成果物

- `references/native-surface-contract.md` の設計: source URL/checked_at/supported mapping/ownership/failure taxonomy。
- P05 repo integration task の path matrix: 共通 `native-surfaces.toml`、root reflector、`.codex/hooks.json`/`.codex/config.toml` adapter、Makefile、全CI、dual manifests、`.agents/plugins/marketplace.json`、composition。
- install/enable/trust と build completion の state machine。

## スコープ外

- official surface が無い agents/commands adapter の設計。
- user global config/trust store mutation。

## 完了チェックリスト

- [ ] surface matrix の全行に source・owner・write policy・verification がある。
- [ ] repo integration task の各 path owner が1件に定まる。
- [ ] source selection と prune/uninstall policy が確定する。
- [ ] SessionStart の lock/atomic/hash/timeout/reentrancy 契約が確定する。
- [ ] structural decision 未解決時は downstream dispatch を禁止する。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: `.codex-plugin/plugin.json` と `.agents/plugins/marketplace.json` の役割、trust前後の状態遷移、unsupported kind を図なしで説明できる。
- 満たさない例: 非公式 TOML key や `.agents/hooks` を暫定値のまま route 化する、または同一 Codex layer の `hooks.json` と inline `[hooks]` に同じ hook を複製する。

### 事前解決済み判断

- native surface に置けない kind は「生成してみる」ではなく unsupported report に残す。
- SessionStart は plugin install/trust の bootstrap を担わない。
- **activation scope 確定 (OQ-CLAUDE-ACTIVATION-SCOPE 解決)**: Claude settings reflector が repo で機械観測できる local projection selection は `repo-present ∩ project-enabled-exact-identity` とする。`.claude/settings.json#enabledPlugins` の正確な `plugin@marketplace` key が true で、対応する repo source と marketplace identity が一致する plugin のみ managed source にする。slug のみへ縮約せず、別 marketplace の同名 plugin を有効扱いしない。install / current hook definition の trust は repo settings から観測できない product runtime user gate なので、C01 の local selection 条件に検証済みとして含めず `pending_user_gate` で分離する。全 `plugins/*` の無条件 apply は禁止。prune/uninstall は当該 local scope から外れた managed 値のみ除去し、user 値・未知 event は非破壊 preserve する。**enforcement owner**: exact identity source-selection は C01 (`sync-native-surfaces.py`)、managed/user/未知 event の非破壊 merge は `build-claude-settings.py`、runtime trust は製品 UI と P11/P13 evidence ledger (責務分離)。

## 参照情報

- `component-inventory.json`
- `handoff-run-plugin-dev-plan.json`
- OpenAI Codex plugin/hooks/config official docs
