---
id: IDX0
title: slide-report-generator 責務再均衡 (v2) 開発計画 index (main)
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
      category: Productivity
    cachebuster_for_update: true
    note: distribution.distributable:false / marketplace:false により現在は配布を抑止するため installation=NOT_AVAILABLE。authentication:ON_INSTALL / default_personal:true / category は将来配布する場合の既定値であり、配布の正本は distribution ブロック。
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
    vendor: byte-parity
  feedback_deploy:
    enabled: false
    reason: 本 plugin はローカル HTML 出力のみで Notion 連携を持たず (notion_config surface=false)、改善要望の Notion 受け皿を設けない (D6 opt-out・v1 から不変)
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# slide-report-generator 責務再均衡 (v2) 開発計画 index (main)

> プラグイン構想「既存 build 済 `plugins/slide-report-generator/`(23 component・289 files)の 16 sub-agent に集中した手続き知識・HTML/CSS規範・評価rubricの過重を解消し、skill 配下 references/scripts または plugin-root SSOT へ責務を再配置した後継設計を、既存機能を変えずに計画として確定する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。
> 本計画は機能追加ではない。既存 `plugin-plans/slide-report-generator/` (13 phase・build 完了済・温存対象) の後継として独立生成した responsibility rebalance (責務再均衡) 計画であり、既存 plugin/plan のいずれも削除・改変しない。

## 基本定義
- **プラグイン slug**: `slide-report-generator-v2` (parallel_slug=D1 確定・build_target=`plugins/slide-report-generator-v2/`・plan_dir=`plugin-plans/slide-report-generator-v2/`)。v2 は v1 (`plugins/slide-report-generator/`) と別の独立成果物として build する。v1 は破壊せず温存し、byte コピー元テンプレート兼比較 golden 源とする (in-place 上書きしない)。
- **最上位目的 (purpose)**: 16 sub-agent に過重した手続き知識・HTML/CSS規範・評価rubricを skill 配下 references/scripts または plugin-root SSOT へ委譲し、既存機能を変えずに責務再均衡を実現する。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C7)、仕様書 (本 index + 13 phase) はその被覆であり、乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `handoff` + `envelope-draft` の生成 (計画=L3 契約)。agent⇔skill 間の情報配置境界の再設計のみ。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、PR/配布登録、既存 `plugins/slide-report-generator/` の削除・改変、**vendor Node engine (byte維持) と意匠/技術コア SSOT (schemas/vendor 共通コア) の再設計** (goal-spec C7・本計画は一切変更しない)。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=24 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **placement_scope (論理オーナーシップ)**: 物理配置ではなく**論理的な所有境界**を表す属性。`skill`=単一 skill のワークフローに帰属する (sub-agent/hook/command は build_target が plugin-root の `agents/`・`hooks/`・`commands/` でも、論理的にはある skill の起動系に属するため `skill`)。`plugin-root`=複数 skill から共有される実体 (>=2 consumer の共有 script のみ・`plugins/<slug>/scripts/` へ hoist)。物理パス (build_target) と混同しない (build_target の plugins/ 始まりは check-runtime-portability が別途検査する)。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=24 は buildable 実体数 (温存23 + 新設1) で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **responsibility rebalance (責務再均衡)**: 機能追加ではなく、既存の procedural knowledge/rubric/帰属情報の「置き場所」を repo 配置原則 (SSOT 正本=prompts/references・agents=薄いアダプタ) に沿って是正すること。
- **no-split threshold**: 分離 (sub-agent→skill) を無条件の善としない。第一判定基準は行数でなく、(a) 抽出対象が複数 component から参照される単一 SSOT を成すか (consumers[]≥2) と (b) 抽出により agent 本文が役割・起動条件・I/O契約へ純化し検証面積が縮小するか の 2 軸。D2一本化で各抽出 reference は薄化 agent 本体 + delegation_target skill の≥2 component から参照され consumers≥2 が成立する。実測行数の超過 (baseline 328-342行 vs 過重 410-990行) は**抽出候補を洗い出す起点シグナル**に過ぎず、閾値をずらすと分類が反転する行数 Goodhart を避けるため disposition の主軸にしない (5件 maintain・11件 thin-adapter の確定は 2 軸で判断)。実測アンカー: `component-inventory.json` `no_split_threshold.measured_at` (2026-07-05 09:31 JST) 参照。
- **rebalance_disposition / rebalance_rationale / delegation_target / extracted_reference**: 16 sub-agent 全件が持つ再配置区分フィールド。thin-adapter agent は論理的な委譲先 skill (delegation_target) と抽出先 reference ファイル (extracted_reference) を明示する。抽出先は D2一本化により **plugin-root references/ 一層** (既存46件と同層) であり、agent は既存 `../references/` 慣用で読む (skill 私有 references/ 階層は新設しない)。
- **progressive_disclosure**: 3 skill (C01/C02/C03) が持つ、SKILL.md 単体構成から「plugin-root references/ への index/ポインタ + scripts/」構成への移行方針フィールド (skill_md_scope/references_new/scripts_new/no_split_reason)。D2一本化のため references の実体は plugin-root に置き、skill・agent の双方が同一 SSOT へ `../references/` 慣用で到達する。
- **references 帰属マップ再構成**: 旧 resource-map.md (散文・機械検証不能) を resource-map.yaml (owner_component/consumers[]/category の構造化宣言) へ置換し、新設 C24 (lint-reference-attribution.py) が機械検証する。thin-adapter から抽出した 11 手続き知識も plugin-root references/ 一層 (既存46件と同層) へ昇格する (D2一本化)。
- **elegant-review C1-C4**: 矛盾なし/漏れなし/整合性/依存整合 の設計審査 4 条件 (design-gate/final-gate 共通)。
- **vendor Node engine・schemas 共通コアの不可侵**: goal-spec constraints/C7 により、既存 vendor(byte維持)・schemas(意匠/技術コア)の設計は本計画の変更対象外。再設計対象は agent⇔skill 間の情報配置境界のみ。

## インフラ
- **実行環境**: harness glue script は Python 標準ライブラリのみ (validate-output-mode.py / 新設 lint-reference-attribution.py)。レンダリング/画像/印刷/検証は vendor Node engine を `Bash(node *)` で起動する (byte 携行・Python 化しない・v1 から不変)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative / `$CLAUDE_PLUGIN_ROOT` 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。check-plugin-surface-audit は build 後 (plugins/ 実体前提) のみ実行可能で本計画 (dogfood scope) には適用しない。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。初見 builder quickstart: 読む順 = 本 index → `handoff-run-plugin-dev-plan.json` → `component-inventory.json`。既存 build 済 plugin との対比参照は `plugin-plans/slide-report-generator/component-inventory.json`(read-only テンプレート)。
- **コンポーネント目録の所在**: buildable な実体 (skill×3 / sub-agent×16 / slash-command×2 / hook×1 / script×2 = 計 24) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract・rebalance フィールドを目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` + `envelope-draft/plugin.json` |
  | composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` (C24 帰属検査を mechanical へ追加配線) |
  | schemas | required | inventory `plugin_level_surfaces.schemas` (**既存設計を無変更で温存・goal-spec C7**) |
  | references/config/assets | required | `plugin_meta.ssot_dedup` (plugin-root references/ 一層=D2一本化: content 61件 [既存50=直下45+feedback/5・v1 不変 + 新設11=thin-adapter 昇格] + resource-map.yaml 帰属メタ1件 (content 外の別勘定) = 総62 files。skill 私有 references/ 階層は新設しない) |
  | vendor | required | inventory `plugin_level_surfaces.vendor` (**既存設計を無変更で温存・goal-spec C7**・whole-tree byte 携行) |
  | MCP/app connector | omitted | inventory の omitted_reason (画像生成は codex exec Bash 経由・v1 から不変) |
  | notion_config | omitted | inventory の omitted_reason (ローカル HTML 出力のみ・Notion 不使用・v1 から不変) |

## 環境ポリシー
- **品質基準**: 全 24 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **無条件分割の禁止**: sub-agent→skill 間の情報移動は no-split threshold (分離コスト<分離便益) の実測根拠を伴わない限り実行しない (goal-spec C3)。
- **既存機能非回帰**: 責務再均衡は procedural knowledge/rubric の置き場所是正であり、既存の入出力契約・生成/修正/横断検証の機能そのものは変更しない。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 5 周 (goal-spec.max_loops) で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。
- **状態語彙の分離**: フェーズ一覧の `未実施` は後段 build lifecycle の実行状態を示す。`plan-findings.json` の PASS は plan artifact の検証状態であり、実プラグインの build/受入完了を意味しない。
- **open_issues の扱い**: plan 段階では既知 gap として non-blocking に記録できるが、build 段階では `handoff-run-plugin-dev-plan.json` の `build_readiness` に従い、stage 別に close または waiver を記録するまで該当 stage を通過しない。

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
- [ ] 基本定義 (plugin slug / purpose / スコープ含む・含まない) が宣言されている。
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / responsibility rebalance / no-split threshold / progressive_disclosure / 用語集) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / 無条件分割の禁止 / 既存機能非回帰 / proposer≠approver / 現状値非焼込) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: 全16 sub-agent component について、既存実装との対比で「本文薄化」「手続き知識/rubricの委譲先」の再配置区分 (rebalance_disposition/rebalance_rationale) が明示されている。
- [ ] 要件 C2: 3 skill それぞれについて、SKILL.md単体構成から references/+scripts/ を伴う progressive disclosure 構成への移行方針が明示されている。
- [ ] 要件 C3: 分離判断が no-split threshold (分離コスト<分離便益) 観点で各 component ごとに実測行数根拠を伴い、無条件分割になっていない。
- [ ] 要件 C4: 各 component が placement_scope 宣言を持ち、check-runtime-portability.py の自己完結性検査 (build_targetがplugins/始まり) を満たす。
- [ ] 要件 C5: 13 phase ファイル + index + component-inventory.json が core 5 scripts で決定論検証可能になっている。
- [ ] 要件 C6: handoff-run-plugin-dev-plan.json の routes が薄化後 sub-agent 16件・再配置後 skill 3件・新設 references/scripts を含む buildable component について builder/build_kind/build_args/build_target を持つ。
- [ ] 要件 C7: 既存 vendor Node engine (byte維持) と意匠/技術コア SSOT の設計は変更対象外である旨が constraints または index のスコープ節に明示されている。
- [ ] 全 24 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose(責務再均衡)を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「16 sub-agent に過重した手続き知識・HTML/CSS規範・評価rubricを skill 配下 references/scripts または plugin-root SSOT へ委譲し、既存機能を変えずに責務再均衡を実現する」。要件 C1-C7 の被覆は本章と上記完了チェックリストで宣言する。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 既存機能が壊れていない (非回帰) | C01/C02/C03 の生成/修正/横断検証機能が v1 build 済 plugin と同等の入出力契約で動作する | 各 skill の outer criterion OUT1 |
| 16 sub-agent の過重が解消されている (C1) | 11 thin-adapter agent の本文が役割・起動条件・I/O契約へ薄化され、対応する references_new が plugin-root references/ (D2一本化・既存46件と同層) に実在する | rebalance_disposition/rebalance_rationale + P08 evidence (行数 before/after) |
| 3 skill が progressive disclosure 構成になっている (C2) | SKILL.md が起動条件・I/O契約のみを保持し、references/+scripts/ が実在する | 各 skill の progressive_disclosure フィールド + build 後ディレクトリ構成 |
| 分離判断が無条件分割でない (C3) | 各 component の rebalance_rationale が実測行数 (baseline 328-342行 vs 過重410-990行・measured_at参照) と抽出可能な procedural knowledge の所在を根拠にしている | no_split_threshold ブロック + human review |
| references 帰属が機械検証可能になっている | resource-map.yaml が plugin-root content references 61件 (直下45+feedback/5+新設11) の owner_component/consumers を宣言し (自身は content 外の帰属メタ)、lint-reference-attribution.py(C24) が exit0 | C24 + references_config_assets surface |
| vendor/schemas が不可侵である (C7) | P02-P10 を通じて vendor(byte維持)・schemas(共通コア)の値が一切変更されていない | plugin_level_surfaces.vendor/schemas の derivation 記録 |

> **C24 帰属機械検証の前提 (F-05/F-06・GAP-SCRIPT-BUILDER)**: 上表「references 帰属が機械検証可能になっている」は C24 (lint-reference-attribution.py) の実生成に依存する。C24 は現在 contract-only であり、`handoff-run-plugin-dev-plan.json` の `build_readiness.must_run_before_routes` で routes 前ブロッキングへ格上げ済 (run-build-skill の fallback_builder で実生成し build trace 取得が routes の前提条件)。**waiver を選択して C23/C24 を実生成しないまま build する場合は、この受入観点を「帰属機械検証は未成立 (resource-map.yaml は人手確認どまり・機械検証可能主張は取り下げ)」へ降格して記載する**こと。

build 後、各 skill component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose(責務再均衡)を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入(既存機能非回帰+rebalance達成)が評価系に配線されていることを宣言する。
