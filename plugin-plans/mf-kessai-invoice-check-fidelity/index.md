---
id: IDX0
title: mf-kessai-invoice-check 改善増分「MF実績起点の発行漏れ確認」開発計画 index (main)
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
      installation: INSTALLED_BY_DEFAULT
      authentication: ON_USE
      category: Finance
    cachebuster_for_update: true
  distribution:
    distributable: true
    bundles: [xl-skills-full]
    marketplace: true
  pkg_contract:
    ref: references/package-contract.json
    pass_count: "12/15"
    time_boxed_debt: [PKG-001, PKG-010, PKG-011, PKG-012, PKG-015]
    next_audit_by: "2026-09-30"
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
      config_key: report_parent_page
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: vendored
---

# mf-kessai-invoice-check 改善増分「MF実績起点の発行漏れ確認」開発計画 index (main)

> 既存プラグイン `mf-kessai-invoice-check`(artifact_class=`existing-plugin-update`)への改善増分計画。前月・今月の MF(マネーフォワード)実績金額を第一級の真実(source of truth)として発行漏れ確認レポート(`run-mf-invoice-report`)の「漏れチェック☑」「金額」列を駆動し、契約(請求確認シート)突合は「なぜ漏れか」を説明するオーバーレイへ格下げする。ただし契約は amount/issued の**判定駆動源からは降格するが D2 行母集合(row-source)としては契約在籍を必須保持**する(`goal-spec` constraint)。builder がシートを row-source から落とすと今月MF無しの契約在籍行が emit されず症状②が「行が出ない」形で逆に消えるため、行母集合=MF実績issued ∪ 契約在籍 の和集合を保つ。
> ライフサイクル軸(13 phase・本 index + phase-01..13.md)と成果物実体軸(`component-inventory.json`・N=7 component)の 2 軸直交で計画する。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない。

## 基本定義
- **プラグイン slug**: `mf-kessai-invoice-check`(既存プラグイン・plan_dir=`plugin-plans/mf-kessai-invoice-check-fidelity/`)。
- **最上位目的 (purpose)**: MF実績を第一級の真実として取得・表示・突合し、発行漏れ確認レポートの判定入力をMF実績由来へ切替える(`goal-spec.purpose`)。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される。要件の正本は `goal-spec.json` の checklist(C1〜C13)、仕様書(本 index + 13 phase)はその被覆であり、実装との乖離が出たら仕様を先に更新してから build へ戻す(spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成(計画=L3 契約)。既存 2 script(C03/C04 modify)+ 新規 2 script(C05/C06)+ 1 skill(C01)+ 1 sub-agent(C02)+ 1 slash-command(C07)の改善設計。
- **スコープ (含まない)**: 実プラグイン/実コードの build(L4・後段 run-skill-create/run-build-skill/`harness-creator/scripts/build-script-route.py` へ委譲)、PR/配布登録。既存 `run-mf-invoice-reconcile`・年間前払い抑制・契約終了最終請求判定ロジックの変更(温存)。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸(13 phase・人間可読)と成果物実体軸(N=7 component・機械 SSOT)を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。本改善では hook は既存 `guard-mfk-readonly`/`guard-mfk-no-reinvent` を再利用し新規 component 化しない。
- **根本原因は多層(単一原因への一般化はしない)**: 症状①〜⑦は単一の設計偏りが全てを生んでいるのではなく、主因の **R-a amount-gate**(症状①③⑥⑦=契約期待額駆動で evidence 欠落時に金額列が空白/継続発行が誤分類)に加え、**R-b ライフサイクル残置**(症状②=D2欠落・正常事情の行が残っていない)、**新規ルール(D1)**(症状④=バグでなく判断分岐の欠落)、**R-c fetch完全性**(症状⑤=evidence-gate由来とfetch欠落由来の多層)が並存する。新規 SSOT C05(`scripts/mfk_actuals.py`)が取引先×商品粒度で実額を常時抽出し、既存 `lib/mfk_reconcile.py`(find_mf_match/classify)がこれを consume して全 status に MF実績 evidence(実額)を必須添付する amount-gate 根治(R-a)を行い、契約突合を説明オーバーレイへ格下げする。R-c は C06 単体では成立しないため、`lib/mfk_api.py`/R1 collect が pagination_trace を保存して C06 に渡す。R-b/R-c は D2(C03/C04)・fetch fidelity(C06)がそれぞれ担う。
- **D1/D2/D3(ユーザー確定事項)**: D1=新規(前月なし今月あり)は12ヶ月ルックバック裏取りでgap_checkをgate。D2=今月MF供給なしは年契約周期/契約終了/トライアル完了/対象外月なら正常事情☑で行を残す。D3=金額列はMF実績を常時表示し期待額との差分をフラグ開示する。flowchart の構造・分類自体は不変。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ(新規外部依存禁止)。共有 script(C03/C04/C05/C06)は plugin-root(`plugins/mf-kessai-invoice-check/scripts/`)へ hoist し単一 skill 配下に退化させない。
- **同梱決定論ゲート**: verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage / check-surface-inventory / check-build-handoff / validate-task-graph / check-runtime-portability / check-requirements-coverage(機械正本=`specfm.GATE_SCRIPTS`)。
- **build の始め方**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順(C05→C06→C03→C04→C01→C02、C07 は C06 依存)に消費する。mode=`update`(既存プラグインへの増分適用)。
- **コンポーネント目録の所在**: buildable な実体(skill×1 / sub-agent×1 / slash-command×1 / script×4 = 計 7)は `component-inventory.json` が唯一の SSOT。C05 は amount-gate 根治のため新規切り出した純関数モジュール `scripts/mfk_actuals.py` であり、4 script 全てが plugin-root script の build_target 形式ゲート(`/scripts/` 包含要件)を例外なく満たす。既存 `lib/mfk_reconcile.py` / `lib/mfk_api.py` / `hooks/guard-mfk-no-reinvent.py` / R1-R4 prompt は独立 component 化しないが、C05/C06/C01 routes の `required_file_edits` としてブロッキング成果物に含める。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | composition | omitted | 既存プラグインは plugin-composition.yaml 不在・新設しない |
  | harness_eval | omitted | 既存プラグインは EVALS.json 不在・ゴールデン fixture 回帰(C01 criteria)で受入担保 |
  | references_config_assets | required | `plugin_meta.ssot_dedup` |
  | schemas | omitted | 既存 skill の schema は本改善スコープ外で温存 |
  | vendor | omitted | plugin-root hoist のみで携帯性を満たす |
  | mcp_app_connector | omitted | 既存 Bash/Skill 経路で扱う |
  | notion_config | required | inventory `plugin_level_surfaces.notion_config`(論理キー `report_parent_page`)+ `plugin_meta.feedback_deploy.notion_sink` |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates(p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0)+ harness_coverage(min≥80/kind_pass)を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する(design-gate/final-gate)。
- **秘匿情報非焼込**: API キー/トークンや Notion DB の具体 ID は plan 成果物に書かず、Keychain/.notion-config.json/.mf-kessai-config.json 等の実行時 config が供給する論理キー(`report_parent_page`)参照のみを宣言する。
- **既存ロジック再発明禁止**: `mfk_reconcile.py` の `find_mf_match`/`classify`/`normalize`/`extract_names`/`has_end_basis`/`_classify_stopped`/`build_mf_index` を再利用し、ゼロから作り直さない(hooks/guard-mfk-no-reinvent.py が機械的に遮断)。
- **MF API 参照専用維持**: `lib/mfk_api.py` は GET のみを維持し POST/PATCH/DELETE を実装しない(hooks/guard-mfk-readonly.py が機械的に遮断)。
- **エスカレーション**: ゲート未達は最大 5 周(`goal-spec.max_loops`)で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

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
- [ ] 基本定義(プラグイン slug / purpose / スコープ)が宣言されている。
- [ ] ドメイン知識(2 軸直交 / component_kind 5 種 / D1・D2・D3)が宣言されている。
- [ ] インフラ(実行環境 / 決定論ゲート / 目録所在 / surface 採否)が宣言されている。
- [ ] 環境ポリシー(品質基準 / proposer≠approver / 秘匿情報非焼込 / 既存ロジック再発明禁止 / MF API GET専用)が宣言されている。
- [ ] 13 フェーズ(P01..P13)が phase_number 昇順で全存在し、各 phase 本文が `specfm.PHASE_BODY_SECTIONS` の宣言型 8 節を満たす。
- [ ] `component-inventory.json` が goal-spec checklist の以下を被覆する: **C1**(C05(mfk_actuals)由来の実額が lib/mfk_reconcile.py 経由で全 status に evidence 必須添付され amount-gate 根治)、**C2**(C06 の fetch fidelity 監査・fail-closed。`lib/mfk_api.py`/R1 collect の pagination_trace 生成を含む)、**C3**(C03 の flowchart 判定入力を MF実績へ置換)、**C4**(C03 の D1=12ヶ月ルックバック裏取り gate)、**C5**(C03 の D2=正常事情判定で行残置)、**C6**(C03 の D3=既存8列の金額欄へ MF実額常時表示+比較/コメント欄で差分フラグ)、**C7**(症状①〜⑦のゴールデン fixture 回帰)、**C8**(C02 の偽陽性/偽陰性検出)、**C9**(C04 の Notion 8列互換の冪等 sink)、**C10**(C07 の fetch fidelity 診断コマンド)、**C11**(lib/mfk_api.py・既存 hook の MF API GET専用維持)、**C12**(hooks/guard-mfk-no-reinvent.py の allowlist 登録・C05/C06 新規シグネチャ含む)、**C13**(本タスクは計画のみで実コード・実プラグインを生成しない)。
- [ ] 各 component(C01-C07)が >=1 phase の `entities_covered` に出現する(orphan 0 件)。
- [ ] 同梱決定論ゲート(核 + 拡張)が全 exit0(例外なし)。
- [ ] `handoff-run-plugin-dev-plan.json` の routes(mode=`update`)が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画(上記)が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった改善済みプラグインが当初 purpose を満たすか**は build 後に下記で確認する。purpose の正本 = `goal-spec.purpose`「MF実績を第一級の真実として発行漏れ確認レポートを正しく駆動する」。goal-spec checklist の各 id(C1〜C13)は以下の component/phase で受入判定する。

| goal-spec checklist id | 受入観点 | 確認の見方 (build 後) | 焼き先 |
|---|---|---|---|
| C1 | 全 status で evidence(実額)必須添付・amount-gate 根治 | 金額不一致/no_supply でも金額列が空白にならないと確認 | C05(mfk_actuals)の quality_gates(lib/mfk_reconcile.py 統合配線含む)+ harness criteria-test |
| C2 | fetch fidelity 監査が NG で fail-closed | pagination/total件数/issue_date/stale 検証を意図的に壊し停止を確認 | C06 の quality_gates |
| C3 | flowchart 判定入力を MF実績へ置換 | 契約突合ゲートを経由せず MF実績のみで判定されることを確認 | C03 の quality_gates |
| C4 | D1: 新規は12ヶ月ルックバックで gate | 年契約→月切替の裏付けあり/なしで gap_check が分岐すると確認 | C03 の OUT criterion |
| C5 | D2: 正常事情は行残置+コメント | 年契約周期/契約終了/トライアル完了で☑残置、非該当で要対応☐を確認 | C03 の quality_gates |
| C6 | D3: 実額常時表示+差分フラグ | 期待額と実績が異なる行で既存8列の金額欄にMF実額が入り、比較/コメントに金額差が出ることを確認 | C03/C04 の quality_gates |
| C7 | 症状①〜⑦ゴールデン fixture 回帰 | tests/ に凍結した fixture が pytest で全件 PASS | C01 の OUT criterion(harness criteria-test) |
| C8 | 偽陽性/偽陰性の独立検出 | 意図的に両ケースを注入し C02 が検出すると確認 | C02 の output_contract |
| C9 | Notion 冪等 sink | 同月内で複数回再実行し重複行 0 件・stale 整理を確認。新物理列を足さず既存8列互換であることも確認 | C04 の quality_gates |
| C10 | fetch fidelity 診断の単独実行 | `run-mf-invoice-doctor` を単独実行し診断結果が得られると確認 | C07 の output_contract |
| C11 | MF API GET専用維持 | POST/PATCH/DELETE 呼び出しが hook で拒否されると確認 | lib/mfk_api.py + hooks/guard-mfk-readonly.py |
| C12 | guard-mfk-no-reinvent allowlist 登録 | 自作 compare/classify 相当が PreToolUse で遮断されると確認 | hooks/guard-mfk-no-reinvent.py |
| C13 | 計画のみ生成・実コード非生成 | 本 plan の成果物一覧に実プラグインコードが含まれないと確認 | 本 index + `handoff-run-plugin-dev-plan.json` |

build 後、各 component の `feedback_contract.criteria`(C01)がcriteria-test として実行され、上表の受入が PASS して初めて「purpose を満たす改善」が確定する。

### 症状 → 根本原因分類 → component → fixture 対応表

> 症状①〜⑦は単一原因ではなく、R-a(amount-gate)/R-b(ライフサイクル)/R-c(fetch完全性)の多層原因である(前掲「根本原因は多層」参照)。以下は各症状の根治責任 component と回帰 fixture の対応。

| 症状 | 根本原因分類 | 担当component | fixture |
|---|---|---|---|
| ①今月金額空白 | R-a amount-gate | C05(evidence実額)+ C03(`_amount_of`優先順位反転) | OUT1(症状①ゴールデンfixture) |
| ②MF無し情報のDB残存 | R-b ライフサイクル残置(D2欠落) | C03(正常事情判定)+ C04(残置理由付き整理) | OUT1(症状②)※対象外月partial注 |
| ③金額一致なのに未☑ | R-a amount-gate | C05 | OUT1(症状③) |
| ④先月空白今月ありの新規判断 | 新規ルール(D1・バグでない) | C03(12ヶ月ルックバック裏取りgate) | OUT1(症状④) |
| ⑤請求ありなのに今月金額空白 | R-a(evidence-gate由来)+ R-c(fetch欠落由来)の多層 | C05(evidence)+ C06(fetch欠落・fail-closed) | OUT1(症状⑤・2ケース凍結)※対象外月partial注 |
| ⑥今月金額相違を追えない | R-a amount-gate(D3) | C03(実額常時表示+差分フラグ) | OUT1(症状⑥) |
| ⑦会社名だけ取得 | R-a amount-gate | C05 | OUT1(症状⑦) |

> ※**対象外月partial注**(②/⑤ 行): 対象外月(隔月/分割/単発)は curr-present(取引先×商品の今月内訳行が存在しない curr=None ケース)実装まで **partial**: 安全側 over-report(要確認☐)で扱い、**真の月次漏れは隠さない**。C05/R1直列化は actual_amount/reliable-issued を既存 verdict 行へ注入するが curr=None には行を生成しないため、この残制約を `GAP-R1-COLLECT-CURR-PRESENT`(`handoff.open_issues`/`goal-spec.open_questions`)で分離追跡する。D1(12ヶ月ルックバック裏取り)・C06 per_customer_diff・C02 過少報告カテゴリが安全網となる。

既存 verdict(`SUPPRESS_ANNUAL`/`MATCH_ENDED_FINAL`/J1名寄せ)の不変性は上表と別観点の OUT2(characterization回帰・phase-04/phase-05 参照)で凍結する。
