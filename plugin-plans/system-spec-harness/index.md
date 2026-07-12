---
id: IDX0
title: system-spec-harness 開発計画 index (main)
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
      authentication: ON_USE
      category: Productivity
    cachebuster_for_update: true
  distribution:
    distributable: true
    bundles: [xl-skills-full]
  pkg_contract:
    applicable: true
    audit_status: pending
    reason: "ユーザー承認により marketplace 配布 (distributable:true) 確定。xl-skills-full bundle + marketplace へ登録。PKG-001..015 の完全な package-contract 監査は time-boxed debt (config=0 の Markdown 生成 plugin のため配布契約チェックの多くは非該当・次回監査で package-contract.json を生成)"
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
      config_key: system-spec-improvement-request
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: vendored
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# system-spec-harness 開発計画 index (main)

> プラグイン構想「システム構築 (Web/モバイル/タブレット/デスクトップ横断) に必要な仕様情報を、ユーザーとのヒアリングを通じて漏れなく収集し1つの仕様書へまとめるハーネス plugin」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `system-spec-harness` (plan_dir=`plugin-plans/system-spec-harness/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: システム構築 (Web/モバイル/タブレット/デスクトップ横断) に必要な仕様情報を、ユーザーとのヒアリングを通じて漏れなく収集し1つの仕様書へまとめる。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C16)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill / plugin-scaffold へ委譲)、PR/配布登録。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=14 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=14 は buildable 実体数で独立に決まる (両者が一致する規約はなく、値が乖離すること自体が2軸直交の証跡)。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **カテゴリは一例、マトリクスが本質**: 構想文中の DB/認証/UI-UX/セキュリティ/インフラ/バックエンド/フロントエンド/保守運用管理は「一例」。要件の核はシステム構成カテゴリ×canonical platform id (`web`/`mobile`/`tablet`/`desktop-windows`/`desktop-linux`/`desktop-macos`) の**網羅マトリクス機構**が全マス「未収集/対象外/確定」で埋まっていることの機械検証 (goal-spec C7・component C12)。
- **マトリクスの状態機械 (正本)**: セル状態 3 値 (未収集/対象外/確定) が正本。goal-spec C1 のカテゴリ表示 4 値は、全セル未収集=`未着手`、未収集混在=`収集中`、全セル対象外=`対象外`、それ以外で未収集0=`確定`の優先順位で導出する。検証は inner=loop 中 enum/軸/真理値表の妥当性検証 / outer=終局の未収集セル 0 の二層 (C01 の IN1/OUT1 と対応)。
- **ヒアリング loop と planner loop の分離**: goal-spec の `max_loops=5` は plan改善周回、C01 の `max_loops=5` は1 invocationの対話チャンク上限。C01 は上限時に未完了状態と `next_question` を保存して resume を返し、未収集セルを完了扱いしない。
- **checklist done の live 正本**: `run-plugin-dev-plan-progress.json` (goal-spec.checklist.done は R1 初期宣言で以後更新しない)。
- **番号名前空間**: C01-C14=component id / C1-C16=goal-spec 要件 / C1-C4 (elegant)=レビュー 4 条件 — 別名前空間 (混同しない)。2 桁域 (C10 以上) は名前空間間で番号が衝突するため、必ず「component C13」「goal-spec C13」のように限定子を付して参照する。
- **上位概念 anchor**: C01 は matrix を技術ヒアリングする前に U1-U9 を値または明示 N/A 理由で確定し、各具体意図・確定セルを `serves_goals` で goal へ結ぶ。要件定義章はこの anchor を先頭に置く。
- **意思決定支援**: 未決定事項は `needs_guidance` として保存し、最新公式情報を根拠に2〜3案を比較する。無料/低コスト案を必ず含めるが最安を自動採用せず、goal fit / TCO / security / operations / lock-in で推奨し、AI推奨はユーザー確認前に確定しない。
- **open-world knowledge**: C04 の既存referenceはseed examplesで上限ではない。未知領域は discover→qualify→deepen→goal map→project candidate→curated promotion→freshness audit で扱い、目的・背景・解決問題・適用/非適用・trade-offまで持たない浅いpointer-only資産は昇格させない。
- **prompt-creator準拠**: 全responsibility promptはC1-C4、L7→L1、l5-contract v2.0、客観的停止条件、Pass 3深度を満たし、`verify-completeness.py` と `validate-prompt.py` の結果をbuild evidenceへ記録する。
- **skill-intake との関係**: 既存 skill-intake plugin のヒアリング機構は再利用せず独立実装とする (段階ゲート/承認の設計流儀のみ着想を借用)。根拠は phase-02-design.md に明記。
- **出力形式**: 章立ての複数 Markdown ファイル + index (`system-spec/` 配下) を既定とする (単一ファイル集約は不採用)。
- **最新ドキュメント取得手段**: WebSearch/WebFetchを既定とし、C01→C02→C01のrequest_id/resume_token handshakeで取得する。compile開始時またはversion signal時に再照合し、失敗/不一致はpending_evidenceとしてconfirmedを禁止する。
- **確定状態の書込保護**: C01所有apply-spec-transition.pyだけがspec-state writer。C03/C11はread-onlyで再オープンをC01へ委譲する。C11はconfirmed章Write/Editとspec-state動的Bashを補助遮断する。
- **知識依存グラフ (goal-spec C13/C14)**: `A depends_on B` はBが前提でBをAより先に出すprecedence DAGとする。refinesは有向精緻化、conflicts_withは対称な非順序制約で、位相順には参加しない。同順位はknowledge_id昇順。C14 knowledge profileが循環/dangling/root到達性/孤立node/型則を検証し、C01/C03が同じJSON位相順を消費する。
- **doctrine anchor (goal-spec C15)**: 正本単位はsystem categoryでなくdesign concern。presentation/ui-ux=Apple HIG、application-architecture/data-access=Clean Architecture、security/authentication/secrets/APIキー=OWASP、reliability/infrastructure/operations=Google SREを1 concern 1正本で固定し、各categoryを必要concernへ全件写像する。未帰属はowner/reason/approval_state付きpending例外としてcompileを止める。C14 doctrine profileが形状と全射、content-reviewが意味反映を検証する。
- **ドメイン別必須情報カタログ (goal-spec C16)**: C01所有の各itemはitem_id/domain/concern/question/required_reason/evidence_required/depends_on/required_when/completion_rule/missing_effect/serves_goalsを必須とする。全in-scope domainを1件以上または承認済N/Aで被覆し、空catalog・未回答required item・trace欠落を拒否する。C14 required-info profileの収集順とcoverage certificateをspec-stateへ保存し、missing_effect=blockはconfirmedを禁止する。
- **公式証拠ハンドシェイク**: C01はrequest_id/resume_token付きevidence_requestを発行し、C02は同IDのresultを返す。compile開始時またはversion signal時に再照合し、失敗/不一致はpending_evidenceとしてC01が保持する。C03はstateを書き換えずpendingがあればconfirmed出力を拒否する。
- **実行時 artifact の所在正本**: 実行時 artifact (spec-state.json / fetched-references.json / system-spec/) の所在正本 = C01 の spec-state contract (project cwd 相対・構想毎ディレクトリ分離)。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の 10 検査) / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の preflight で blocking gap の owner/実行手段を解決してから routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す (詳細手順は焼かない)。
- **コンポーネント目録の所在**: buildable な実体 (skill×5 / sub-agent×3 / slash-command×2 / hook×1 / script×3 = 計 14) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` (owner=`run-build-skill`, kind=`plugin-composition`) |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` (owner=`plugin-scaffold`, gap=`GAP-PLUGIN-SURFACE-BUILDER`) |
  | references/config/assets | required | `plugin_meta.ssot_dedup` + C04 references (owner=C04) |
  | governance runbook (`plugin_meta`) | required | `RUNBOOK.md` (owner=`plugin-scaffold`) |
  | CI workflow (`plugin_meta`) | required | `.github/workflows/governance-check.yml` wiring (owner=`plugin-scaffold`) |
  | schemas | omitted | component inventory の omitted_reason (共有 script 内で検証し独立 schema 不要) |
  | vendor | omitted | component inventory の omitted_reason (plugin-root hoist で携帯性充足) |
  | MCP/app connector | omitted | component inventory の omitted_reason (WebSearch/WebFetch のみで完結・GAP-MCP-DOCFETCH へ保留) |
  | notion_config | omitted | component inventory の omitted_reason (成果物は Markdown ドキュメントセットでプロジェクト固有 DB 読み書きを持たない) |

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
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / カテゴリ例示とマトリクス本質の区別 / skill-intake 非再利用等の設計判断) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: 生成される仕様書がデータベース/認証(ログイン)/UI-UX/セキュリティ/インフラ/バックエンド/フロントエンド/保守運用管理を含むシステム構成カテゴリの一覧を持ち、各カテゴリの収集状態(未着手/収集中/確定/対象外+理由)を明示する仕組みが C01/C03/C12 として定義されている。
- [ ] 要件 C2: canonical platform id (`web`/`mobile`/`tablet`/`desktop-windows`/`desktop-linux`/`desktop-macos`) ごとに仕様収集項目が存在するか対象外の判断根拠が明示される仕組みが、C01 (R1-init の必須プラットフォーム行初期化+全存在検証) と C12 (必須プラットフォーム行の全存在+カテゴリ軸床の検証) として定義されている。
- [ ] 要件 C3: 往復ヒアリングがC01としてcomponent化され、5 loop到達時も状態保存+resumeで継続する。正本writerはC01のみ、C03/C11はread-only、再オープンはC01 R4経由。
- [ ] 要件 C4: クリーンアーキテクチャ/デザインパターン/API デザインパターン/セキュアバイデザイン/DDD/クリーンコードの各知識領域を参照できる reference 資産が C04 (ref-system-design-knowledge) として component-inventory に含まれている。
- [ ] 要件 C5: ツール/インフラ/フレームワーク等の最新公式ドキュメントを target_id/公式host/versionまたは更新日/取得・確認時刻/参照元記録付きで反映する C02/C13/C08 が定義されている。
- [ ] 要件 C6: 収集した仕様情報を章立て複数 Markdown ファイル+index としてまとめる出力仕様が C03 (run-system-spec-compile) として確定している。
- [ ] 要件 C7: カテゴリ×プラットフォームの収集マトリクスの全マスが未収集/対象外/確定のいずれかで埋まっていることを検証する網羅性検証の仕組みが C12 (validate-coverage-matrix.py) として component 定義されている。
- [ ] 要件 C8: `component-inventory.json` + 13 phase ファイル + `handoff-run-plugin-dev-plan.json` が plugin.json manifest / marketplace policy / cachebuster 等の packaging 契約を満たして生成されている (`check-spec-gates.py` / `check-build-handoff.py` が機械検査)。
- [ ] 要件 C9: U1-U9 の上位概念が技術マトリクス前に確定し、具体意図・確定セル・生成章が goal へトレースする。
- [ ] 要件 C10: `needs_guidance` から最新公式根拠付き2〜3案、無料/低コスト案、AI推奨理由・注意点・confidenceを生成し、ユーザー確認のみが決定を `confirmed` にする。
- [ ] 要件 C11: C04がseed例に閉じず、深いknowledge card契約とopen-world discovery/promotion lifecycleを持つ。
- [ ] 要件 C12: 全promptがprompt-creator C1-C4/L5契約の機械検証と独立評価を通過する。
- [ ] 要件 C13: depends_on precedence DAGとrefines/conflicts_with型則、循環/dangling/root到達性/孤立nodeを検証するC14 knowledge profileが定義されている。
- [ ] 要件 C14: 仕様のelicit (C01 R5-decision-guide) /compile (C03 R2-render) が知識グラフの位相順 (上位概念→下位概念) でC04知識を消費する。
- [ ] 要件 C15: 4 design concernのanchorが1 concern 1正本で固定され、全category→concern写像がC04 registryからC03へ反映される。
- [ ] 要件 C16: required-info最低形状・domain被覆・不足時効果・完了条件をC01/C14が検証し、決定論的収集順とcoverage certificateを導出できる。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0 (goal-spec 要件の被覆は check-requirements-coverage が機械検査)。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「システム構築に必要な仕様情報をヒアリングを通じて漏れなく収集し1つの仕様書へまとめる」。

| 受入観点 (purpose 由来 / 要件 id) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| カテゴリ一覧+収集状態明示 (C1) | 生成された仕様書の各章にカテゴリ別の収集状態(未着手/収集中/確定/対象外+理由)が明示される | compile skill (C03) の OUT criterion + evaluator (C05) |
| プラットフォーム別収集/対象外根拠 (C2) | canonical platform id 6種の各行がマトリクスに存在し対象外セルに理由が付く | elicit skill (C01) の OUT criterion + マトリクス検証 (C12) |
| 往復ヒアリングで停止しない (C3) | 6周超のサンプル対話で、5周目に未完了状態+next_questionが保存されresume後に継続する | elicit skill (C01) の R3-reask responsibility + hearing auditor (C06) |
| 設計知識反映 (C4) | 仕様書の該当章がクリーンアーキテクチャ等の設計知識ポインタを参照している | ref skill (C04) の output_contract + content-review |
| 最新ドキュメント出典記録 (C5) | target_id全件が公式host/versionまたは更新日/取得・確認時刻/参照元を持ち、C08が現行版と再照合する | doc-fetch skill (C02) + citation gate (C13) + doc freshness auditor (C08) |
| 出力ドキュメントセットの確定 (C6) | system-spec/ 配下に章別 Markdown + index が生成される | compile skill (C03) の output_contract |
| 網羅マトリクス検証 (C7) | 最終時: 未収集セル 0 + 対象外理由付与を validate-coverage-matrix.py が exit0 で確認する (loop 中は enum 妥当性検証) | script C12 + matrix auditor (C07) |
| packaging 契約充足 (C8) | plugin.json manifest / marketplace policy / cachebuster が検証済み | `check-spec-gates.py` / `check-build-handoff.py` |
| 上位概念 anchor (C9) | U1-U9 が値または明示N/A理由で確定し、goal-objective-intent-cell-chapter trace がdanglingなし | C01 R0 + C12 `--require-foundation` + C03要件定義章 |
| AI意思決定支援 (C10) | 未決定事項に最新公式根拠付き2〜3案・無料/低コスト案・goal fit/TCO/security/operations/lock-in比較・推奨理由/注意点があり、ユーザー確認前は未確定 | C01 R5 + C02/C13証拠 + C03 decision table |
| 深いopen-world知識 (C11) | seed外の未知領域を候補化でき、pointer-only referenceをdepth gateが拒否する | C04 knowledge lifecycle/schema/tests + C05 content review |
| prompt-creator準拠 (C12) | 全responsibility promptが機械validatorと独立C1-C4評価をPASS | prompt-creator validators + route report design findings |
| 知識グラフ意味/DAG機械検証 (C13) | depends_on precedence DAGの循環/dangling/root到達性/孤立nodeとrefines/conflicts_with型則をC14 knowledge profileが確認する | script C14 + C04 knowledge-catalog |
| 知識の位相順消費 (C14) | C01/C03がC14 knowledge profileのJSON topo_order (B before dependent A、同順位ID昇順) を同一消費する | C01 + C03 + C14 |
| doctrine concern反映 (C15) | 4 concern authorityが一意で全categoryが必要concernへ写像され、未承認例外0で生成章へ上流指針として反映される | C04 doctrine registry + C14 doctrine profile + C03 + content-review |
| 必須情報coverageと収集順序 (C16) | required-info最低形状・domain被覆・block 0を満たし、coverage certificateと決定論順がspec-stateへ保存される | C01 + C14 required-info profile + C06 |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。

## 残課題 (open_issues)

> 正本 = `handoff-run-plugin-dev-plan.json` の `open_issues[]`。ここでは確定判断に影響する据え置き課題のみ要約する (全文はハンドオフを参照)。

- **C4 未達 = `GAP-TASKGRAPH-P02-PROJECTION` (status: acknowledged-deferred)**: 4条件のうち C1(矛盾なし)/C2(漏れなし)/C3(整合性あり) は PASS。C4(依存関係整合) のみ未達で、原因は本 plan の内容 (知識依存グラフ C13/C14・doctrine anchor C15・必須情報カタログ C16) ではなく **planner (`run-plugin-dev-plan`) 共通の task-graph 射影構造** (phase checklist を entities_covered 全件へ直積射影し他 owner の作業を無関係 component の write_scope へ複製する) にある。ユーザー承認 (2026-07-12) により、改善要望の反映は完了と確認のうえ、planner 出力形状の構造変更は別案件として据え置き、本 plan は open_issue 明記で確定する。task-graph mode で L4 build する際の影響と回避策はハンドオフ `build_impact` を参照。
