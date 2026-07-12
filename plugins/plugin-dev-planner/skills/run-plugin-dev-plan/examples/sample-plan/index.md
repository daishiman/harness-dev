---
id: IDX0
title: notion-task-sync 開発計画 index (main)
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: AVAILABLE
      authentication: ON_INSTALL
      category: Productivity
    cachebuster_for_update: true
  distribution:
    distributable: true
    bundles: [harness-full]
    marketplace: true
  pkg_contract:
    pkg: 002-008
  governance:
    runbook: required
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    deploy: run-skill-feedback
    enabled: true
    notion_sink:
      config_key: improvement-request
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: vendored
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# notion-task-sync 開発計画 index (main)

> プラグイン構想「タスク台帳を Notion DB へ冪等同期する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `notion-task-sync` (plan_dir=`plugin-plans/notion-task-sync/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: タスク台帳を Notion DB へ冪等同期する。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1/C2)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、PR/配布登録。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=11 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=11 は buildable 実体数で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **冪等同期**: 同一台帳を二回同期しても二周目の追加/更新が 0 件になる性質 (purpose の中核受入観点)。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の 10 検査) / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す (詳細手順は焼かない)。
- **コンポーネント目録の所在**: buildable な実体 (skill×3 / sub-agent×3 / slash-command×2 / hook×1 / script×2 = 計 11) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required | `plugin_meta.ssot_dedup` |
  | notion_config | required | inventory `plugin_level_surfaces.notion_config` (DB キーのみ宣言・ID は設置先 `.notion-config.json` 供給) + `plugin_meta.feedback_deploy.notion_sink` |
  | MCP/app connector | omitted | component inventory の omitted_reason |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 3 周で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

## フェーズ一覧

1. P01 — requirements (要件定義) / 未実施
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
- [ ] 基本定義 (plugin slug / purpose / スコープ) が宣言されている。
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / 用語集) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: `component-inventory.json` が 5 component_kind の検討証跡と plugin-level surfaces の採否を記録し、全 11 component が build_target 非空・builder/build_kind 整合・依存 DAG 非循環で core 規律 (quality_gates + harness_coverage + skill loop の feedback_contract) を携帯する。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0 (goal-spec 要件の被覆は check-requirements-coverage が機械検査)。
- [ ] 要件 C2: `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「タスク台帳を Notion DB へ冪等同期する」。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 差分が正しく同期される | 同期実行後に同期レポートの追加/更新件数が台帳差分と一致 | 同期 skill (C01) の OUT criterion + harness criteria-test |
| 二重発行/重複しない (冪等) | 同一台帳を二回同期し二周目の追加/更新が 0 件 | 同期 skill (C01) の inner/outer criterion |
| 過去分が取りこぼしなく移行される | 初期一括投入後に台帳全件が Notion に存在 | backfill skill (C03) の OUT criterion |
| 発行漏れが網羅的に検出される | 既知の発行漏れを注入し reconcile が全件検出 | reconcile skill (C02) の OUT criterion |
| 破壊的操作で消えない | guard hook が物理削除を fail-closed で阻む | guard hook (C11) |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
