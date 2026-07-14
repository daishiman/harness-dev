---
id: IDX0
title: harness-creator-hook-agents-sync 開発計画 index (main)
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: false
    policy:
      installation: AVAILABLE
      authentication: ON_INSTALL
      category: Internal-Tooling
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
  pkg_contract:
    applicable: false
    reason: "public 配布用 package harness は対象外。repo-local marketplace は install/discovery surface として対象"
  governance:
    applicable: true
    reason: "Makefile・governance-check.yml・TG-C08 の3層で native surface drift を検査する"
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    enabled: false
    reason: "skill loop component を新設しない"
---

# harness-creator-hook-agents-sync 開発計画 index (main)

> この計画は Claude Code と Codex の native loading contract に沿って capability を公開し、投影漏れを機械検出するための L3 実行仕様である。初回 planner review は spec-only で行い、後続 capability-build で local build/apply/check を実行する。product install/enable/trust と commit/push/PR は別 user gate とする。

## 基本定義

- **対象**: `plugins/harness-creator` の既存 plugin 更新。
- **目的**: 有効化・信頼済みのリポジトリ capability を、Claude Code と Codex それぞれの公式 native surface へ手作業・推測投影なしに一貫公開し、片側だけ未反映・stale になる drift を build 完了ゲートと CI で検出・修復できるようにする。
- **観測済み問題**: (事実) Claude reflector は存在するが Makefile/CI/完了ゲートへ未配線で、現行 target hook event を未知として exit 3 になる。Codex native surface は `.agents/skills`・`.codex/{config.toml,hooks.json}`・`.codex-plugin/plugin.json`・`.agents/plugins/marketplace.json`・plugin hooks であり、plugin hook は install/enable 後も trust を要する。(判断) ゆえに `.agents` 全反映と推測 TOML merge を前提にした旧案は撤回し native-first を採る。
- **ゴール**: 上記5系統 (Claude reflector 互換修復と機械配線 / Codex dual manifest・repo marketplace・native hooks / supported-unsupported matrix / 競合安全な SessionStart / freshness gate) が4正本へ矛盾なく落ち、planner 決定論ゲートと elegant-review 4条件が全 PASS する1つの整合した plan にする。
- **非ゴール**: product 側 plugin install/enable/trust、public marketplace publish、commit/push/PR。local capability build・repo-owned apply/check・hook fixture 実行は handoff consumer の実装対象。
- **正本**: 要件=`goal-spec.json`、buildable component=`component-inventory.json`、routing=`handoff-run-plugin-dev-plan.json`、依存 graph=`task-graph.json`。

## ドメイン知識

### Native surface 対照表

| capability/surface | Claude Code | Codex | 本計画の扱い |
|---|---|---|---|
| repo skill | `.claude/skills` projection | `.agents/skills` または plugin `skills/` | confirmed |
| project hook | `.claude/settings.json` | `.codex/hooks.json` / `.codex/config.toml` | confirmed・project owner |
| plugin hook | `.claude-plugin/plugin.json` inline | `.codex-plugin/plugin.json` + `hooks/hooks.json` | confirmed・install/enable/trust 必須 |
| plugin discovery | Claude plugin manifest | `.agents/plugins/marketplace.json` → plugin install | confirmed |
| Claude-style agent | `.claude/agents` | 公式 plugin file mapping 未確認 | v1 unsupported/deferred |
| Claude-style command | `.claude/commands` | 公式 plugin file mapping 未確認 | v1 unsupported/deferred |

Codex は Claude の投影方式をコピーしない。native plugin が直接読む skills/hooks を `.agents` へ複製せず、unsupported kind は parity report に残す。

### State ownership

| state | owner | 自動書込 |
|---|---|---|
| `.claude` managed projection | repo generator | fingerprint 差分時のみ可 |
| `plugins/harness-creator/.codex-plugin` / `hooks` | plugin source | build/update 時のみ可 |
| `.agents/plugins/marketplace.json` | repo |明示された entry のみ可 |
| `.agents/skills/beads` | bd/tool | 禁止 |
| `~/.codex/config.toml` / trust store | user/product | 禁止 |
| worktree lock/log | worktree-local | bounded write 可 |

## インフラ

- **C02** `check-native-surface-parity.py`: authoritative surface、dual manifest、marketplace、trust、unsupported、artifact digest を read-only 検証。
- **C01** `sync-native-surfaces.py`: Claude apply/check と Codex native parity を単一 orchestration。lock/atomic replace/hash no-op を所有。
- **C03** `record-task-graph-knowledge.py`: TG-C08 に hooks settings / native surface parity gate を追加。
- **C05** `auto-sync-on-session-start`: install/enable/trust 後に C01 を1回呼ぶ薄い hook。failure は構造化 warning として保持。
- **C04** `capability-build`: build後 pre-step を C01/C02 へ集約。
- **repo integration task (P05 owner)**: `plugins/harness-creator/native-surfaces.toml` は共通 hook delivery と Codex discovery entry の意味論 SSOT、各 plugin manifest と root marketplace は capability/activation identity の正本とする。C01 がこれらを結合し、`scripts/build-claude-settings.py`、Codex project `.codex/hooks.json`/`.codex/config.toml` adapter、Makefile/全CI、dual manifest、`.agents/plugins/marketplace.json`、composition、native surface contract を単一 desired-set として生成・検査する。plugin hook と project hook は delivery owner を分け二重配線しない。plugin-root route ではなく phase singleton task として write scope を一意にする。

依存 DAG は `C02 → C01 → {C03,C05} → C04`。`couples_with` は使用せず、実依存だけを edge 化して graph 密度を抑える。

## 環境ポリシー

- **native-first**: 推測配置/推測 schema を実装しない。
- **activation boundary**: local projection は repo に source が実在し、project settings で正確な `plugin@marketplace` identity が enabled の source に限定する。install / current hook trust は repo から観測不可能な product runtime user gate として分離し、自動承認や検証済み推定をしない。
- **failure taxonomy**: generator 不在だけ `skipped_not_installed`。drift/conflict/parse/race/timeout は warning または completion blocked とし、成功へ畳まない。
- **concurrency**: reentrancy guard、process lock、atomic replace、content-hash no-op、timeout、同時2 session test を必須にする。
- **security**: secret/PII 非書込、global config/tool-owned namespace 非破壊、manual region preservation。
- **freshness**: goal/inventory/handoff/task-graph/findings の digest parity が崩れたら PASS を拒否する。
- **反復上限**: 4条件未達の改善は最大3周。超過時は user へ escalation。

## フェーズ一覧

1. P01 — requirements (要件定義) / 完了
2. P02 — design (設計) / 未実施
3. P03 — design-review (設計レビューゲート) / 未実施
4. P04 — test-design (テスト設計) / 未実施
5. P05 — implementation (実装) / 未実施
6. P06 — test-run (テスト実行) / 未実施
7. P07 — acceptance-criteria (受入基準判定) / 未実施
8. P08 — refactoring (リファクタリング) / 未実施
9. P09 — quality-assurance (品質保証) / 未実施
10. P10 — final-review (最終レビューゲート) / 未実施
11. P11 — evidence (手動テスト検証) / 未実施
12. P12 — documentation (ドキュメント) / 未実施
13. P13 — release (完了/PR・リリース) / 未実施

## 完了チェックリスト

- [ ] C1: authoritative native surface matrix が source/checked_at を持つ。
- [ ] C2: Claude reflector の current event compatibility が test-first で修復される。
- [ ] C3: Claude apply/check が Makefile・CI・dispatcher・TG-C08 に配線される。
- [ ] C4: Codex native manifest/hooks/repo marketplace が正本となり推測 projection が無い。
- [ ] C5: skills/hooks と unsupported agents/commands の mapping が silent skip なく報告される。
- [ ] C6: SessionStart が trust 前提・lock・atomicity・hash・timeout・structured warning を持つ。
- [ ] C7: negative/concurrency/trust/lifecycle regression tests が揃う。
- [ ] C8: ownership/security matrix により global config と beads を非破壊に保つ。
- [ ] C9: goal/inventory/handoff/task-graph/findings の digest freshness parity が PASS する。
- [ ] C10: elegant-review 4条件と planner validator が全 PASS する。
- [ ] 5 component と5 route が1:1で、依存 DAG が `C02 → C01 → {C03,C05} → C04` と一致する。
- [ ] P05 repo integration task が共通 TOML、Claude settings、Codex project hooks/config、Makefile、全CI、dual manifest、repo marketplace の owner/path/order/rollback/evidence を持つ。
- [ ] `.agents/plugins/marketplace.json` と `.agents/skills` 以外の推測 `.agents` runtime surface、非公式 TOML merge、plugin/project hook の二重配線が0件。
- [ ] install/enable/trust と runtime smoke は build 完了から分離され user-gated になる。
- [ ] SessionStart が lock/atomicity/hash/timeout/structured warning を持つ。
- [ ] stale `plan-findings` を PASS 根拠にできない freshness gate がある。
- [ ] planner 決定論 gate と elegant-review 4条件が全 PASS する。

## 受入確認

| 受入観点 | build後の確認 | 証跡 owner |
|---|---|---|
| Claude reflector compatibility | target unknown event preserve / managed source unknown event block / existing INV green | P05 + focused pytest |
| Claude mechanical wiring | Makefile・CI・dispatcher・TG-C08 の全4箇所で apply→check | C01/C03/C04 |
| Codex native discovery | repo marketplace が `.codex-plugin/plugin.json` を指し、skills/hooks parity が PASS | C02 + envelope |
| Codex trust boundary | 未trustでは hook非実行、trust後のみ SessionStart が発火 | P11 user-gated evidence |
| unsupported visibility | agents/commands が silent PASS せず report に unsupported と出る | C02 fixture |
| SessionStart safety | 二重実行/同時2session/no-diff/timeout/conflict で state破壊なし | C05 fixture |
| ownership/security | beads/global config/secret/PII 変更0 | C01/C02/C05 tests |
| evidence freshness | artifact digest 不一致時に review PASS 拒否 | C02 + plan validator |

上表を満たして初めて runtime-ready と判定する。今回の仕様レビュー完了は runtime-ready や build 完了を意味しない。
