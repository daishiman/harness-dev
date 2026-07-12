---
id: IDX0
title: ubm-goal-setting 改善計画 index (main)
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
      authentication: ON_USE
      category: Productivity
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
  pkg_contract:
    applicable: false
    reason: 個人利用向け plugin (distributable:false) のためパッケージ契約 (pkg 番号帯) の対象外
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

# ubm-goal-setting 改善計画 index (main)

> 既存 plugin `ubm-goal-setting` へ、2-source対応YouTube取込 (提示済み『北原孝彦のコンサルティング』はrequired-primary・全量必須、第2sourceはpending)、scheduler起動の新着自動同期、根拠付きknowledge依存グラフ、harness実成果物グラフを追加する改善計画。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。本計画は artifact_class=`existing-plugin-update` であり、既存 capability A (`run-ubm-goal-setting`)/B (`run-ubm-knowledge-sync`) の契約を後退させない additive 拡張として設計する。

## 基本定義
- **プラグイン slug**: `ubm-goal-setting` (plan_dir=`plugin-plans/ubm-goal-setting/`・既存プラグインへの改善計画=同一 slug へ固定)。
- **最上位目的 (purpose)**: required-primaryの公開動画を漏れなくknowledge化し、新着を無人同期し、全knowledgeとharness実成果物を根拠付きgraphでgoal-settingへ自動consultすること。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C11)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成 (計画=L3 契約)。既存 capability A/B との接続点・非後退制約の明記。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill / plugin-scaffold へ委譲)、PR/配布登録、YouTube 取得技術手段の確定 (open_questions)。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase) と成果物実体軸 (N=11 component) を二重保持しない。
- **component_kind (5 種)**: skill×2 (C02,C09) / sub-agent×2 (C01,C08) / slash-command×2 (C04,C10) / script×5 (C03,C05,C06,C07,C11) / hook×0。C09 はC07 read-only consultとC11 validatorを再利用し、C10が明示入口を担う。
- **phase ≠ component**: 13 はフェーズ数、N=9 はbuildable実体数。
- **REQ 語彙**: REQ1a=URL単発取込 / REQ1b=required-primary厳格全量 / REQ1c=scheduler無人同期 / REQ2=harness surface適合 / REQ3=根拠付きknowledge依存graph / REQ4=harness実成果物graph / REQ5=目標設定以外も含む相談への非処方コーチング型consult (外ループ handback 2026-07-11・承認済で追加)。
- **既存 capability**: capability A=`run-ubm-goal-setting` (週報/月報/期報の目標設定対話・統一ハイブリッド構造21項目)。capability B=`run-ubm-knowledge-sync` (ナレッジソース差分検知→6カテゴリ抽出→knowledge/*.json 保存)。両者の既存契約は本計画で無改変。
- **C 番号 3 系統の対照**: 要件 C1-C12 / elegant-review C1-C4 / component C01-C11 は独立番号体系。C09は相談orchestrator、C10は明示command入口、C11はrole/source付きsession validator。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の 10 検査) / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す (詳細手順は焼かない)。既存 2 skill (`run-ubm-goal-setting`/`run-ubm-knowledge-sync`) は本 inventory の routes に含まれない (無改変のため build 対象外)。
- **コンポーネント目録の所在**: buildableな9実体は `component-inventory.json` が唯一のSSOT。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required | `plugin_meta.ssot_dedup` |
  | schemas | omitted | component inventory の omitted_reason (既存 knowledge/schema.json を流用し新設 schema なし) |
  | vendor | omitted | component inventory の omitted_reason (run-skill-feedback は commit 591e5ac で symlink 既配備済み・distributable:false 例外に正規該当のため新規 vendor 不要。維持確認は P09 検証専用ステップ) |
  | mcp_app_connector | omitted | component inventory の omitted_reason (YouTube 取得手段未確定のため MCP connector 新設なし) |
  | notion_config | omitted | component inventory の omitted_reason (新規 buildable component はいずれも domain DB を使用しない。既配備 run-skill-feedback の feedback 受け皿は `plugin_meta.feedback_deploy.notion_sink` が既に宣言済み) |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **非後退 change matrix**: runtime契約変更は2 workflow-manifest + `info-collector.md`/goal-setting resource mapのadditive wiring。surface変更はplugin.json/plugin-composition/package-contract/EVALS/tests/README/RUNBOOK/CHANGELOGのadditive parity更新。各ownerとexpected diffをP05/P09/P12に固定し、既存phase id/gate/21項目/6カテゴリ/既存schema fieldは回帰テストで維持する。
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
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / REQ 語彙 / 既存 capability) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / 非後退) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: `component-inventory.json` に REQ1a (URL単発共有→文字起こし取得→6カテゴリナレッジ抽出→保存) を実現する buildable component (C02) が含まれ、既存 run-ubm-knowledge-sync の Phase1-detect/Phase2-extract パイプラインとの接続点 (C01 が normalize した出力を既存 knowledge-extractor へ渡す) が明記されている。
- [ ] 要件 C2: required-primaryのauthoritative inventory全IDを分母に保持し、C03がcontent coverage 100%・未承認blocker 0を判定する。
- [ ] 要件 C3: C02の冪等one-shotをschedulerが無人起動し、cursor/lease/retry/alertを検証する。
- [ ] 要件 C4: YouTube 文字起こし・チャンネル動画一覧取得の技術手段が constraints/open_questions として明示され、確定仕様として断定されていない。
- [ ] 要件 C5: harness-creator 仕様適合ギャップ分析結果が記録されている。R4 evaluator の再検証 (plan-findings.json) により run-skill-feedback は commit 591e5ac で既に symlink 配備済み (distributable:false 例外に正規該当) と判明したため新規 buildable component 化はせず、既配備の維持確認 (symlink 存在 + `lint-feedback-protocol.py --strict` PASS) を P09 の検証専用ステップとして inventory/phase に明記している。再ギャップ分析の結果、REQ2 に残る真の未充足 buildable 項目は無い。
- [ ] 要件 C6: C08が根拠付き依存辺を生成し、C06がDAGを決定論構築・検証し、C07がconsultする。
- [ ] 要件 C7: 新規グラフ機構 (C06) と既存 router-registry パターン (router.json/registry.json) との関係 (併存・置換しない拡張) 、および plugin-dev-planner task-graph 契約からの参考要素 (nodes/depends_on/DAG非循環の概念のみ) と独自要素 (ナレッジエントリ粒度・6カテゴリ準拠) が明記されている。
- [ ] 要件 C8: C05がtask graphだけでなくstate/report/trace/composition/EVALS/実在pathをartifact graphへ正規化し、C07が実成果物をdereferenceする。
- [ ] 要件 C9: 新設11 component全てがcore規律とbinary acceptance contractを携帯する。
- [ ] 要件 C10: 13 phase + index + handoff が REQ1a/REQ1b/REQ1c/REQ2/REQ3/REQ4/REQ5 を漏れなく被覆し、goal-spec checklist C1-C12 の全 id が本チェックリストと「受入確認」章から引用されている。
- [ ] 要件 C11: 既存 capability A/B の既存契約を破壊しないことが constraints に明記され (P01/P10 の非後退確認)、非後退であることが記述されている。
- [ ] 要件 C12: C09/C10/C11 が、考え方中心の適応型協働契約、安全分岐、ユーザー発話 provenance、選択式closure、保存同意を持ち、既存 capability を非破壊 additive 拡張する。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0 (goal-spec 要件の被覆は check-requirements-coverage が機械検査)。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose (REQ1a/1b/1c/REQ2/REQ3/REQ4) を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| URL単発共有からナレッジ保存まで到達する (REQ1a) | 単発 URL を投入し knowledge/*.json に対応エントリが新規追加される | 取込 skill (C02) の OUT criterion |
| required-primaryが漏れなく全量backfillされる (REQ1b) | discovered全IDを分母にcontent coverage 100%、一時失敗/未承認取得不能0 | C03 + C02 IN1 |
| 新着動画が自動差分knowledge化される (REQ1c) | scheduler fixtureが無操作で1件反映、再実行0件、retry回復 | C02 OUT1 |
| harness-creator 仕様適合ギャップが解消される (REQ2・検証専用) | 既配備 run-skill-feedback (symlink) が build 前後で維持され、`lint-feedback-protocol.py --strict` が R1-R7 PASS する | P09 quality-assurance の検証専用ステップ (非 buildable) |
| knowledge依存graphが機能する (REQ3) | C08がevidence付きnon-zero edgeを生成、C06がDAG検証、C07が既知hitを返す | C08+C06+C07 |
| harness実成果物取得が機能する (REQ4) | C05がtask-state/route report/build trace/実在pathを突合し、C07がreal artifactを1件以上dereference | C05+C07 |
| 目標設定以外も含む相談でユーザーが解決策を組み立てられる (REQ5・C12) | 協働モード、安全/目標設定分岐、role=user provenance、action/reflection、保存同意を検証 | C09/C10/C11 の IN1/OUT1 + validator |
| 既存 capability A/B が非後退である (C11) | 契約非後退 (既存 phase id/gate/出力契約・21項目・6カテゴリ・knowledge schema 既存フィールド) を回帰テストで確認し、allowlist 外ファイルは build 前後 diff 空・allowlist 内は additive (既存 entry 無変更) | P10 final-gate の非後退確認 |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグイン改善が出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
