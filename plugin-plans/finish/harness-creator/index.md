---
id: IDX0
title: harness-creator パイプライン境界契約 開発計画 index (main)
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
      installation: NOT_AVAILABLE
      authentication: ON_INSTALL
      category: Developer Tools
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
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
    portability: repo-bundled
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# harness-creator パイプライン境界契約 開発計画 index (main)

> プラグイン構想「skill-intake→plugin-dev-planner→harness-creator build→改善 という量産パイプラインの 3 境界断線 (E1: intake→goal-spec、E2: plan→build、E3: 改善→plan) を解消する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。対象 (`target_plugin_slug`) は harness-creator だが、パイプラインのエッジは必ず 2 plugin (plugin-dev-planner/harness-creator) にまたがるため、component の build_target は所有 plugin 側へ cross-plugin routing する。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `harness-creator` (plan_dir=`plugin-plans/harness-creator/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: skill-intake→plugin-dev-planner→harness-creator build→改善という量産パイプラインの各段境界 (E1/E2/E3) における producer/consumer 機械契約・検証ゲート・provenance の欠落を解消し、新規作成フローと改善フローの双方が依存関係を保って回るタスク仕様書を計画する。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C12)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `handoff-run-plugin-dev-plan.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill / parent-skill-build / plugin-scaffold へ委譲)、PR/配布登録、各段実行の自動連鎖 orchestrator の新設 (各段の実行は分離維持がユーザー方針)。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=11 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。本 plan は skill×2 (更新) / slash-command×2 (更新) / script×4 (新設) + script×1 (既存更新=C03) / sub-agent×1 (新設) / hook×1 (新設) = 計 11。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=11 は buildable 実体数で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **ID 名前空間**: 要件 checklist は `C1`..`C12`、component は `C01`..`C11`、elegant-review 4 条件は機械フィールド上 `C1`..`C4` だが本文では「4 条件 (矛盾なし/漏れなし/整合性あり/依存関係整合)」と併記して混同を避ける。加えて golden fixture (`fixtures/c8-new-flow/`) 内の route id も `C01`/`C02` を採るが、これは demo プラグイン `demo-boundary-skill` のローカル route 名前空間であり本 plan の component `C01`..`C11` とは別軸である (P07 の `--route C02` は demo fixture の route=`demo-boundary-check` script を指し、本 plan の component C02=`plugin-dev-plan` command ではない)。
- **E1/E2/E3 用語集**: E1=intake→goal-spec 境界 (skill-intake の intake.json 消費契約欠落)、E2=plan→build 境界 (routes[] 消費経路欠落)、E3=改善→plan 境界 (改善成果物の構造化入力契約欠落)。provenance chain = intake.json→goal-spec(source_intake)→plan→build handoff→改善成果物(source_improvement)→次サイクル goal-spec の 5 ノード追跡可能性。
- **cross-plugin routing**: E1 consumer→`plugins/plugin-dev-planner/`、E2 consumer→`plugins/harness-creator/`、E3 emit→`plugins/harness-creator/`、E3 consume→`plugins/plugin-dev-planner/`。両 plugin とも repo-bundled `distributable:false` であり、`check-runtime-portability.py` (plugins/ 始まり・`..` 禁止) を満たすため build_target のパス形状は install 携帯性を毀損しない。**ただし携帯性ゲートは build_target のパス接頭辞のみを検査し、実行時に別 plugin 配下のファイルを読む cross-plugin runtime 参照は検査しない**。具体的に `improvement-handoff.schema.json` は consumer skill `run-plugin-dev-plan` の schemas/ に凝集配置され (検証者近接: plugin-goal-spec/phase-spec と同居)、producer (C09=harness-creator) が cross-plugin 参照する。producer は schema を import せず stdlib 自己検証ゆえ共置コストは 0 で、全 consumer C01/C05/C10/C11 と producer が単一 SSOT を参照するため schema parity の二重化は発生しない (P09 parity 安全弁は SSOT 単一化により不要化)。健全性は「両 plugin が常に共在する不変条件 (双方 `distributable:false`・repo-bundled・NEVER_DISTRIBUTE denylist で片方のみ配布しない)」が担保する。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。plan の C12 判定では `specfm.GATE_SCOPE=plan-scoped` のゲートを対象にし、`input-gate` (check-plugin-goal-spec) は R1 入力確定時の証跡、`dogfood` (check-plugin-surface-audit) は plugin-dev-planner 現物監査として分ける。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes 配列を正本として消費する。skill 付随 script (C03/C04/C05) は `requires_parent_scaffold: C01` で親 skill scaffold 内へ二相 build する (`requires_parent_scaffold` は `depends_on` DAG 辺ではなく配置境界指示であり、topsort が表現しない親 scaffold→child script→本体上書きの順序は `/capability-build --handoff ... --route-id ...` と `build-script-route.py` の route report が正本)。plugin-root 共有 script (C08/C09) は `plugin-scaffold` (contract-only・`gap_ref: GAP-SCRIPT-BUILDER`) の routing 語彙を維持しつつ、L4 実行では `build-script-route.py` が実体化する (詳細手順と順序列挙は routes[] へ寄せ、本文へ重複保持しない)。
- **mode 語彙の分離**: `handoff-run-plugin-dev-plan.json` top-level と C01/C06 の `build_args.mode:update` は builder の**既存ファイル更新ビルドモード** (artifact_class=existing-plugin-update) を指し、run-plugin-dev-plan 自身の `--mode update` (E3 改善フロー再生成・C11 hook が provenance pass marker を要求する破壊的再生成) とは別語彙である。前者に C11 の pass marker 要求は適用されない。本 plan 自身の goal-spec が `source_intake/source_improvement:null` なのは from-scratch 起票 (改善フロー由来でない) ゆえであり、handoff の `mode:update` (=既存 plugin 更新ビルド) と矛盾しない。
- **コンポーネント目録の所在**: buildable な実体 (skill×2 / sub-agent×1 / slash-command×2 / hook×1 / script×5 = 計 11) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` (harness-creator 側は無変更 mirror、plugin-dev-planner 側 entry_points/hooks 追加は C10/C11 の build スコープ) |
  | plugin-composition | omitted | inventory `plugin_level_surfaces.composition.omitted_reason` (build 時 /plugin-compose が定常処理) |
  | harness/eval | omitted | inventory `plugin_level_surfaces.harness_eval.omitted_reason` (component 単位の quality_gates/harness_coverage で既に規定) |
  | references/config/assets | required | inventory `plugin_level_surfaces.references_config_assets` (新設 `pipeline-boundary-contract.md`) |
  | schemas | required | inventory `plugin_level_surfaces.schemas` (`improvement-handoff.schema.json` 新設 + goal-spec schema へ provenance フィールド追加) |
  | notion_config | omitted | inventory `plugin_level_surfaces.notion_config.omitted_reason` (改善還流はローカル repo artifact 既定・Notion read-back を避ける) |
  | MCP/app connector | omitted | inventory `plugin_level_surfaces.mcp_app_connector.omitted_reason` |

## 環境ポリシー
- **品質基準**: 全 11 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **実行分離の不変条件**: intake/plan/build/改善の各段実行は分離したまま維持する。本計画は producer/consumer 機械契約・検証ゲート・provenance の整備に留め、自動連鎖 orchestrator は新設しない。
- **regenerate-exempt**: plan_dir 内の `fixtures/` と `.gate/` は `--mode update` 再生成の対象外 (golden fixture と pass marker を再生成で破壊しない)。
- **エスカレーション**: ゲート未達は最大 3 周で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。この「最大 3 周」はゲート外周のエスカレーション予算であり、component 内部の goal-seek ループ (`goal_seek.max_loops=5`・skill 精緻化の内周) とは別スコープ。両者を混同しない (fixture の demo plan `max_loops:3` は demo 独自値)。

## フェーズ一覧

build_status: realized (2026-07-05 build 完了 + commit。証跡=build-evidence.md / 状態正本=component-inventory.json 直下 build_status)

1. P01 — requirements (要件定義) / 実施済 (2026-07-05)
2. P02 — design (設計) / 実施済 (2026-07-05)
3. P03 — design-review (設計レビューゲート) / 実施済 (2026-07-05)
4. P04 — test-design (テスト設計) / 実施済 (2026-07-05)
5. P05 — implementation (実装) / 実施済 (2026-07-05)
6. P06 — test-run (テスト実行) / 実施済 (2026-07-05)
7. P07 — acceptance-criteria (受入基準判定) / 実施済 (2026-07-05)
8. P08 — refactoring (リファクタリング) / 実施済 (2026-07-05)
9. P09 — quality-assurance (品質保証) / 実施済 (2026-07-05)
10. P10 — final-review (最終レビューゲート) / 実施済 (2026-07-05)
11. P11 — evidence (手動テスト検証) / 実施済 (2026-07-05)
12. P12 — documentation (ドキュメント) / 実施済 (2026-07-05)
13. P13 — release (完了/PR・リリース) / 実施済 (2026-07-05)

## 完了チェックリスト
- [ ] 基本定義 (plugin slug / purpose / スコープ) が宣言されている。
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / E1-E2-E3 用語集 / cross-plugin routing) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / 実行分離不変条件) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: intake.json 消費 producer→consumer 配線契約 (C01/C02) が適用例・非適用例の両方を伴って定義されている。
- [ ] 要件 C2: intake.json/next-action.json の情報漏れ検出ゲート (C04) が検出例 (未反映あり/なし) 付きで定義されている。
- [ ] 要件 C3: routes[] を読み込み check-build-handoff.py 通過後に実行する具体消費経路 (C06/C07) が定義され、contract-only builder (C08 が突合する plugin-scaffold/parent-skill-build) が明示区別されている。
- [ ] 要件 C4: routes[]↔component-inventory.json の突合ゲート (C08) が一致例・不一致検出例の両方を伴って定義されている。
- [ ] 要件 C5: --mode update が改善成果物をローカル repo artifact 経由で受理する入力契約 (C01・改善成果物は C09 emit) が定義されている。
- [ ] 要件 C6: 改善フローで再生成される goal-spec/plan の provenance フィールド (C01/C09) が定義されている。
- [ ] 要件 C7: provenance chain 検証ゲート (C05) が受入例・断裂検出例付きで定義されている。
- [ ] 要件 C8: 新規作成フロー一巡受入例 (P07 参照) が下流実行者の追加質問なしに再現できる具体度で定義されている。
- [ ] 要件 C9: 改善フロー一巡受入例 (P07 参照) が下流実行者の追加質問なしに再現できる具体度で定義されている。
- [ ] 要件 C10: 全 build_target が所有 plugin 側へ正しく routing され `plugins/` 始まり・`..` 禁止を満たすことが `component-inventory.json`/`handoff-run-plugin-dev-plan.json` で確認できる。
- [ ] 要件 C11: いずれの build_target にも `plugin-plans/plugin-dev-planner/`・`plugin-plans/skill-intake/` 配下が含まれない。
- [ ] 要件 C12: 同梱決定論ゲートのうち plan-scoped 集合 (core + plan 対象の拡張・機械正本=`specfm.GATE_SCOPE`) が全 exit0。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった 2 plugin (plugin-dev-planner/harness-creator) が当初 purpose (E1/E2/E3 断線解消) を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| E1: intake.json が purpose/background へ反映される (適用例/非適用例) | intake.json 提供時に C01 が §0/§3 を反映し `source_intake` を記録・未提供時は従来 fallback | C01 の OUT criterion + C02 の起動経路 |
| E1: 未反映項目が検出される | intake.json の未反映項目を注入し C04 が WARN/FAIL で検出 | C04 の受入テスト |
| E1/E3: 再生成 goal-spec の provenance フィールドが検証される | check-plugin-goal-spec.py (C03) が source_intake/source_improvement の実在+schema_version を検査 (フィールド欠落の既存 goal-spec は WARN 受理) | C03 の受入テスト |
| E2: routes[] が直接消費される | brief_path/routes 付き呼び出しで C06/C07 が再ヒアリングなしに build 開始 | C06 の OUT criterion + C07 の受入テスト |
| E2: routes↔inventory 不一致が検出される | 意図的に不一致な route を注入し C08 が検出 | C08 の受入テスト |
| E3: 改善成果物が受理される | run-elegant-review 等の出力から C09 が improvement-handoff.json を emit し、C01 が `--mode update` で受理・`source_improvement` を記録 | C01 の OUT criterion + C09 の受入テスト |
| E3: provenance chain の断裂が検出される | 意図的に provenance フィールドを欠落させ C05 が検出 | C05 の受入テスト |
| E3: 改善反映が意味的に忠実か | C10 が独立 context で改善成果物と再生成 plan の意味的整合をレビュー | C10 の content-review verdict |
| 破壊的な --mode update が未検証で走らない | C11 hook が `run-plugin-dev-plan --mode update` の PreToolUse で C04/C05 pass marker を確認し、欠落時は exit2 block | C11 の受入テスト |
| C8: 新規作成フロー一巡 | P07 の `demo-boundary-skill` fixture で intake → C01 → C02 → C07 → C08 preflight → C06 build dispatch が追加質問なしに一巡できる | P07 の C8 判定 + evidence (P11) |
| C9: 改善フロー一巡 | P07 の `demo-boundary-skill` fixture で C09 → C04/C05 pass marker 生成 → C11 preflight → C01 update → C03/C05 → C10 → build 再実行が追加質問なしに一巡できる | P07 の C9 判定 + evidence (P11) |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose (E1/E2/E3 断線解消) を満たす量産パイプラインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
