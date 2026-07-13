---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 完了
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的

repo integration singleton task と5 component を依存順に実装し、各 write scope の owner を一意に保つ。

## 背景

旧 handoff は root reflector repair、Makefile/CI、manifest、marketplace を phase prose に埋めて owner を持たせず、C05 は manifest wiring と aggregate script を1 routeに混在させていた。

## 前提条件

- P04 test-first matrix が承認済み。
- `PRECONDITION-CLAUDE-REFLECTOR-COMPAT` と `OQ-CLAUDE-ACTIVATION-SCOPE` の設計判断が確定済み。

## ドメイン知識

実装順は次の通り。

1. repo integration: `scripts/build-claude-settings.py` compatibility + tests。
2. repo integration: common `plugins/harness-creator/native-surfaces.toml`、native surface contract/schema、Claude settings adapter、Codex project `.codex/hooks.json`/`.codex/config.toml` adapter、`.codex-plugin/plugin.json`、`hooks/hooks.json`、`.agents/plugins/marketplace.json`、`plugin-composition.yaml`。
3. C02 parity validator。
4. C01 orchestrator。
5. C03 completion gates と C05 hook を並列実装。
6. C04 dispatcher。
7. Makefile/CI は apply 可能な current state を作った後に blocking check を有効化。

## 成果物

- C01/C02/C03/C04/C05 の route target。
- repo integration path matrix の全 target と focused tests。
- manifest/marketplace/source digest snapshot、created-path inventory、fixture 内の managed projection rollback→restore 実行結果と migration note。

## スコープ外

- plugin install/enable/trust、runtime hook 発火。
- public publish、PR。

## 完了チェックリスト

- [ ] target unknown event preserve / managed source unknown event block が実装される。
- [ ] `.agents/{agents,commands,hooks}` と非公式 TOML writer が存在せず、`.agents/plugins/marketplace.json`・`.codex/hooks.json`・`.codex/config.toml` は公式 schema の repo-owned managed 部分だけを更新する。
- [ ] common TOML の1 hook は delivery=`plugin|project` のどちらか1つだけを所有し、Claude/Codex の native location へ製品別変換される。
- [ ] C05 は hook script target を持ち、manifest/marketplace wiring は repo integration owner が担う。
- [ ] lock/atomic replace/hash no-op/timeout/structured status が実装される。
- [ ] Makefile/CI/dispatcher/TG-C08 が apply→check 順に配線される。
- [ ] global config/beads/trust store write が0。
- [ ] 投影 command は repo-relative で、別 clone/worktree へ移動しても実在 target へ解決し、個人絶対 path を生成しない。
- [ ] activation は exact `plugin@marketplace` identity を保ち、同名 foreign marketplace と同一 source hook の重複を fail-closed/dedupe する。
- [ ] active な全CI workflow は C01 check-only に単一化され、legacy unfiltered check を native completion gate として呼ばない。
- [ ] runtime evidence ledger は schema/freshness pin 付きで、user-gated node と local-required node を個別に分類する。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: build対象5 routeとrepo integration taskの各 changed pathを owner 1件へ逆引きできる。
- 満たさない例: manifest 更新や root script 修正が「ついで」に入り route/evidence owner がない。

### 事前解決済み判断

- native plugin が読む skills/hooks を別 symlink generator で複製しない。
- CI blocking gate は repair/apply より先に有効化しない。
- **repo integration step 1 (reflector compatibility) 実装履歴 (PRECONDITION-CLAUDE-REFLECTOR-COMPAT 解決)**: target unknown preserve / managed source unknown block / shared-skill real-path dedupe を実装した。当初の `$CLAUDE_PLUGIN_ROOT` 展開は絶対 worktree path を `${CLAUDE_PROJECT_DIR}` へ連結する portability defect を生んだため、current implementation では repo-relative command 導出と relocation test を必須とする。過去の test 件数を current PASS 根拠に流用せず、P06/P09/P10 の fresh evidence で再検証する。

## 参照情報

- `component-inventory.json`
- `handoff-run-plugin-dev-plan.json`
- `references/native-surface-contract.md` (planned)
