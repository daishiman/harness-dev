---
id: IDX0
title: plugin-dev-planner 残債解消計画 index (main)
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
      installation: NOT_AVAILABLE
      authentication: ON_USE
      category: Internal Tooling
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
  pkg_contract:
    applicable: false
    reason: "NEVER_DISTRIBUTE denylist (F3) 対象で PKG-001..015 の配布契約検査は非該当。plugin-scaffold envelope は contract-only builder が既に gap_ref 登録済みで、本 goal (C1-C3) はこの境界を変更しない"
  governance:
    applicable: false
    reason: "A10 が対象とする harness-creator 側の評価 rubric は所有/変更しないため非該当。assign-plugin-plan-evaluator 内部の plan-rubric.json は本 plugin 内の意味評価軸として加算変更するが、A10 Runbook 正本 (harness-creator/run-skill-rubric-governance) の変更には当たらない"
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

# plugin-dev-planner 残債解消計画 index (main)

> 本計画は新規プラグイン構想ではなく、既存プラグイン `plugin-dev-planner` (3 回の elegant-review で 4 条件 PASS 済み) の残債を解消する `existing-plugin-update` 計画であり、**対等な二本柱 (co-primary)** を重心に持つ。**第一の柱 (X: 機械残債解消)** は 3 つの機械検証可能性の残債 (target_plugin_slug 未束縛 / entry_points 未突合 / harness-coverage 12 軸自己適用ギャップ、C1-C3) を、既存 `run-plugin-dev-plan` skill 内部の決定論ゲートと CI の拡張として解消すること。**第二の柱 (Y: 生成物品質・「緑のパラドクス」解消)** は、機械ゲートが全緑でも生成される仕様書が汎用テンプレ埋めのまま残り下流ハーネスとして機能しない余地を断つことであり、ユーザーの外側ループ指示により、(層A: C6-C9) phase 本文の曖昧語彙・未カスタマイズのフォールバック文言を機械検出し下流実行着手可能な具体度を fork evaluator が genuine 判定する仕組みと、(層B: C10-C12) 各 phase 本文が下流 builder の受入例・事前解決済み判断を内包し仕様書=下流ハーネスとして実効性を持つかを機械検出+genuine 判定する仕組みを、run-plugin-dev-plan の生成フロー (R3) と assign-plugin-plan-evaluator の評価フロー (R4) へ組み込むこと。X (既知残債の機械化) と Y (評価パラダイムの新設) は主従でなく対等であり、goal-spec.background が重心とする Y (緑のパラドクス) を本 index も co-primary として並置する。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `plugin-dev-planner` (plan_dir=`plugin-plans/plugin-dev-planner/`・自己参照計画=対象 plugin と計画の生成元 plugin が同一)。
- **最上位目的 (purpose)**: plugin-dev-planner が harness-creator 仕様に漏れなく準拠する状態を保ちつつ、target_plugin_slug 未束縛 / entry_points 未突合 / harness-coverage 12 軸未適用の 3 残債 (C1-C3) を機械検証可能な形で解消し、加えて生成される 13 タスク仕様書の内容自体が下流 AI 実行者にとって曖昧でなく課題解決に資する具体度を持つか (層A) と、生成された仕様書自体が下流 builder のハーネスとして機能するか (層B) を検出・評価する機構を組み込む。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C12)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `envelope-draft/plugin.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実 `plugins/plugin-dev-planner/` への実装反映 (L4・後段 run-skill-create の Edit build へ委譲)、harness-creator 側の envelope executor 化 (constraints によりスコープ外)、改名 churn 残置ファイルの解消 (別タスク由来)。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=2 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。本計画は 5 種を全検討したうえで 2 skill component (C01=run-plugin-dev-plan mode=update・C02=assign-plugin-plan-evaluator 既存 skill の遡及的 component 化) へ収束した (derivation 参照・skill 偏重の既定選択ではなく検討済み帰結。同一 component_kind の複数実体はそれぞれ独立 component という原則の適用例)。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=2 は buildable 実体数で独立に決まる。phase は `entities_covered` の id 参照 (C01/C02) のみで component に紐づく。**entities_covered 付与規則**: component の build_target の**生成/検証を primary deliverable とする** phase のみが `entities_covered` に id を持つ。要件定義 (P01)・判定ゲート系 (P03/P07/P09/P10)・component 非依存の横断観点 (P08 refactoring)・**完了プロセス系 (P11 evidence / P12 documentation / P13 release)** は `entities_covered=[]` が正常である。完了プロセス系は build_target 内ファイルに触れても primary deliverable が検証記録・文書・PR であり component への横断参照に留まるため id を持たない (空は orphan ではなく非依存の明示。字義上の「build_target に触れる」ではなく「build_target の生成/検証が主成果物か」で判定する)。
- **3 残債の性質**: C1 (target_plugin_slug 束縛)・C2 (entry_points/inventory 突合)・C3 (harness-coverage 12 軸自己適用) はいずれも新規機能追加ではなく、既存決定論ゲート (check-runtime-portability.py / check-build-handoff.py) の検査範囲を狭く拡張する改修である。C4/C5 は退行防止条件。
- **層A/層B の二層分離 (anti-goodhart)**: 層A (C6-C9・生成時精度) は phase 本文の曖昧語彙 denylist 検出 (C6) と `_PHASE_SECTION_HINT` 完全一致 (未カスタマイズ) 検出 (C7) を機械層に留め、意味の正否 (下流実行着手可能な具体度) の最終判定は fork evaluator (C8) の意味評価に委ねる。C9 は C6-C8 追加後も既存決定論ゲート + pytest 全件が退行なく green のままである条件。層B (C10-C12・仕様書=下流ハーネス) は各 phase 本文への受入例・事前解決済み判断の存在検出 (C10/C11) を機械層に留め、その実効性 (下流実行者が追加質問なく構築に着手できるか) の genuine 判定は fork evaluator (C12) に委ねる。機械層=存在/語彙/文言一致の検出、意味層=fork evaluator の genuine 判定という既存 4 条件と同型の二層分離を維持する。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。**roster 12 本 vs plan-findings.json 証跡 10 本の乖離注記**: R4 evaluator が生成する `plan-findings.json` の `gate_results` には plan 構造ゲート 10 本 (G1-G10 = 上記 core 6 起動 + check-surface-inventory / check-build-handoff / check-requirements-coverage / check-runtime-portability) のみが記録される。残る 2 本は実行段が異なるため R4 の plan 構造 verdict とは別レーンで exit0 を確認する = `check-plugin-goal-spec` は R1 (goal-spec 検証段・phase 生成前。`prompts/R1-elicit-goal.md` で起動)、`check-plugin-surface-audit` は plugin-level surface 監査。したがって「roster 12 本」と「plan-findings 証跡 10 本」の差は実行段差に由来する整合であり、数の不整合ではない。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。C01/C02 いずれの route も build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影し、mode=update として `run-skill-create` へ渡す (既存 skill への Edit 差分のみ・全書き換え禁止)。C02 は depends_on:[C01] で C01 の後に消費される。
- **コンポーネント目録の所在**: buildable な実体 (skill×2 = 計 2: C01=run-plugin-dev-plan・C02=assign-plugin-plan-evaluator) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **評価器の二名の同一性 (C02)**: C8/C12 の意味判定を担う fork evaluator は、component/skill としては `assign-plugin-plan-evaluator` (inventory C02・handoff routes・plan-findings.json の evaluator.name)、envelope の entry_points.agents 上の agent としては `plugin-dev-plan-evaluator` として現れるが、両者は同一実体である (`prompts/R1-evaluate.md` が正本 SSOT・`agents/*.md` は薄いアダプタ)。C8/C12 の実行主体はこの単一実体であり、二名は物理配置面 (skill 資産 vs agent エントリ) の別名にすぎず、実行主体連鎖は途切れない。
- **C3 配線先の確定 (phase-02-design.md 参照)**: governance-check.yml の既存 plugin-dev-planner conformance block への 1 ステップ追加 + 新規 self-check script (`scripts/check-harness-coverage-selfcheck.py`) を run-plugin-dev-plan skill 内部に自己完結配置する組合せに確定した。scripts/validate-harness-coverage.py への roster/filter 追加 (候補 A) は共有インフラの無条件横断設計を壊し F8 (install-portability) に反するため不採用。
- **repo-level CI gap の扱い**: `.github/workflows/governance-check.yml` は component route 外の repo-level 編集だが、C3 の観測可能性を満たすため release 前に必ず解消する blocking issue として扱う。handoff の `open_issues` は「任意の申し送り」ではなく、P13 完了条件で解消確認する release gate である。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required (現状維持・entry_points/hooks 変更なし) | `plugin_meta.manifest` |
  | plugin-composition | required (現状維持) | `plugin-composition.yaml` |
  | harness/eval | required (C3 で自己適用状態を拡張) | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required (現状維持) | `plugin_meta.ssot_dedup` |
  | vendor | omitted | inventory `plugin_level_surfaces.vendor.omitted_reason` |
  | mcp_app_connector | omitted | inventory `plugin_level_surfaces.mcp_app_connector.omitted_reason` |
  | notion_config | omitted | inventory `plugin_level_surfaces.notion_config.omitted_reason` |

## 環境ポリシー
- **品質基準**: C01/C02 各々が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass。C01=loop 型・C02=assign=evaluator-verdict) を携帯する。C02 は skill_kind=assign のため feedback_contract は skip_reason で明示し (loop criteria 必須対象外)、goal_seek は対象外、prompt_layer:7layer は必須。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 3 周で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。
- **既存契約の非破壊**: C1-C3 は既存関数のシグネチャ拡張 (デフォルト引数・後方互換) のみで行い、既存呼び出し元・既存 fixture の挙動を変えない (C4/C5 の green 維持がこの制約の観測可能な証跡)。
- **C9 の重複回避**: C4/C5 は既存 pytest と 46 行マトリクスの基礎退行防止、C9 は C6-C8 追加差分を入れた後に同じ基礎ゲートを再実行して退行が無いことを確認する派生条件である。受入時は C9 を C4/C5 の再実行参照として扱い、別の品質軸として二重カウントしない。集合論的には **C4⊆C9・C5⊆C9** (C9 は C4/C5 と同一の基礎ゲート集合を層A/層B 追加差分の上で再実行する上位集合) であり、C9 は独立軸でなく C4/C5 の再実行派生ゆえ独立要件数には数えない (12 項目採番は追跡用の連番で、独立品質軸は C9 を除いた集合である)。

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
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種検討証跡 / 3 残債の性質) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / C3 配線先確定 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / 既存契約非破壊) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: check-runtime-portability.py が target_plugin_slug と異なる plugin 配下の build_target を検査したとき exit1 でその不整合を検出結果に含める。
- [ ] 要件 C2: check-build-handoff.py が entry_points と component-inventory.json の component 集合を突合し、未網羅の component を検出結果に含める。
- [ ] 要件 C3: plugin-dev-planner の harness-coverage 12 軸カバレッジ状態を governance-check.yml 経由の self-check が exit0 で検証する。
- [ ] 要件 C4: plugins/plugin-dev-planner 配下の pytest 全件が既存件数から退行なく exit0 で green のままである。
- [ ] 要件 C5: 46 行マトリクス整合 (check-spec-matrix-coverage.py --self-test) が exit0 のままである。
- [ ] 要件 C6: phase 本文・inventory component の goal/checklist/criterion 文字列に対する曖昧語彙 denylist 検出の仕組みが構造化結果 (WARN/FAIL) を報告する。
- [ ] 要件 C7: 生成された phase 本文の宣言型 8 節が `_PHASE_SECTION_HINT` の汎用フォールバック文言と完全一致 (未カスタマイズ) のケースを機械検出する。
- [ ] 要件 C8: assign-plugin-plan-evaluator (R4) が phase 本文の下流実行着手可能な具体度を genuine に判定し、判定結果と曖昧箇所の具体的指摘が plan-findings.json に記録される。
- [ ] 要件 C9: C6-C8 追加後も既存の決定論ゲート (check-build-handoff/detect-unassigned/check-spec-frontmatter/check-spec-gates/check-spec-matrix-coverage/check-surface-inventory/check-requirements-coverage/verify-index-topsort/check-runtime-portability) と pytest 全件が退行なく exit0/green のままである。
- [ ] 要件 C10: 各 phase ファイルの本文が下流実行者向けの受入例 (満たす例/満たさない例) を最低 1 組、機械検出可能な構造として持つ。
- [ ] 要件 C11: 各 phase ファイルが判断に迷いやすい曖昧分岐点の判断基準を機械検出可能な形で事前解決済みとして明示する。
- [ ] 要件 C12: assign-plugin-plan-evaluator (R4) が C10/C11 の受入例・事前解決済み判断の実効性を genuine に判定し、判定結果が plan-findings.json に記録される。
- [ ] C01/C02 がそれぞれ build_target 非空・builder/build_kind 整合・依存 DAG 非循環 (C02 は depends_on:[C01] のみで循環なし) で core 規律 (quality_gates + harness_coverage + feedback_contract/skip_reason) を携帯する。
- [ ] C01/C02 それぞれが >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が C01/C02 を builder/build_kind/build_args/build_target/depends_on 込みで後段 builder へルーティングする。
- [ ] `handoff-run-plugin-dev-plan.json` の `open_issues` (repo-level governance-check.yml 追記) が release blocking issue として P13 完了条件へ接続されている。

## 受入確認

> 計画 (上記) が満たすのは「C01/C02 が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった改修が当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test / assign-plugin-plan-evaluator の genuine 判定)。purpose の正本 = `goal-spec.purpose`「plugin-dev-planner が harness-creator 仕様に漏れなく準拠する状態を保ちつつ、機械検証可能性の残債解消 (C1-C3) に加え層A (C6-C9・生成時精度) と層B (C10-C12・仕様書=下流ハーネス) の品質機構を組み込む」。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| target_plugin_slug 不一致が exit1 で検出される (C1) | 別 plugin slug の build_target を含む fixture handoff で check-runtime-portability.py を実行し exit1 を確認 | C01 の feedback_contract.criteria IN1 + harness criteria-test |
| entry_points/inventory 未網羅が検出される (C2) | inventory に存在し envelope に未網羅の component を含む fixture で check-build-handoff.py を実行し検出結果を確認 | C01 の feedback_contract.criteria IN2 + harness criteria-test |
| harness-coverage 12 軸が自己適用される (C3) | check-harness-coverage-selfcheck.py と governance-check.yml の該当ステップを実行し exit0 かつ EVALS.json.threshold_note と矛盾しないことを確認 | C01 の feedback_contract.criteria OUT2 |
| 既存契約が非破壊 (C4/C5/C9) | plugins/plugin-dev-planner 配下の pytest 全件 + check-spec-matrix-coverage.py --self-test + core/拡張決定論ゲート全本を実行し既存件数から退行なく green を確認 | C01 の feedback_contract.criteria OUT1 |
| 曖昧語彙 denylist が検出される (C6) | 曖昧語彙を含む fixture phase 本文で check-generative-fidelity.py を実行し WARN/FAIL 結果を確認 | C01 の feedback_contract.criteria IN3 + harness criteria-test |
| `_PHASE_SECTION_HINT` 完全一致 (未カスタマイズ) が検出される (C7) | フォールバック文言そのままの fixture phase 本文で check-generative-fidelity.py を実行し検出結果を確認 | C01 の feedback_contract.criteria IN4 + harness criteria-test |
| 下流実行着手可能な具体度が genuine 判定される (C8) | assign-plugin-plan-evaluator を fork 実行し、phase 本文の具体度判定結果と曖昧箇所の指摘が plan-findings.json の findings[] に記録されることを確認 | R1-evaluate.md の C8 判定ステップ + plan-findings.json |
| 受入例が phase 本文に存在検出される (C10) | `## 完了チェックリスト` 直下の受入例サブ節を含む/含まない fixture phase 本文で check-downstream-harness.py を実行し検出結果を確認 | C01 の feedback_contract.criteria IN5 + harness criteria-test |
| 事前解決済み判断が phase 本文に存在検出される (C11) | 同サブ節 (事前解決済み判断) を含む/含まない fixture phase 本文で check-downstream-harness.py を実行し検出結果を確認 | C01 の feedback_contract.criteria IN6 + harness criteria-test |
| 仕様書=下流ハーネスとしての実効性が genuine 判定される (C12) | assign-plugin-plan-evaluator を fork 実行し、C10/C11 の受入例・事前解決済み判断が下流実行者にとって実効性を持つかの判定結果が plan-findings.json の findings[] に記録されることを確認 | R1-evaluate.md の C12 判定ステップ + plan-findings.json |

build 後、C01 の `feedback_contract.criteria` が criteria-test として実行され、C02 (assign-plugin-plan-evaluator) の C8/C12 判定が plan-findings.json へ記録され、上表の受入が PASS して初めて「purpose を満たす改修が出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
