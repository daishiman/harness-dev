---
id: IDX0
title: mf-kessai-invoice-check 改善増分「発行漏れレポート根治(収集拡張/R1決定論化/NEW・取消分類/代理店collapse/顧客ID結合)」開発計画 index (main)
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
    pass_count: "13/18"
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

# mf-kessai-invoice-check 改善増分「発行漏れレポート根治」開発計画 index (main)

> 既存プラグイン `mf-kessai-invoice-check`(artifact_class=`existing-plugin-update`)への改善増分計画。前月↔今月比較 発行漏れレポート(`run-mf-invoice-report`)で発行済み取引先(2nd Community株式会社/HOSONO株式会社(細野)/paws有限会社等)の当月請求が「今月なし」「今月金額=null」「偽・発行漏れ(要対応☐)」に誤表示・誤判定される。前回 PR#85(0.4.0)は `scripts/mfk_period_report.py` の `_amount_of`/`_is_issued` を実額優先へ反転したが症状は継続した。2026-07-09 の**全段実データ調査**(実レポートDB=ユーザー提示URL・月スコープ忠実 reconcile(2606/2605)・両月 C03 通し・全段コードの三点突合)で、**C05/C03/reconcile は正しく動くのに下流の R1 が当月行を落とすため症状が続く**ことを実証し、当初仮説2つ(名寄せ英字/カナ境界ミスが主因・REVIEW_QTY_MISMATCH=54 の系統的期待明細数バグ)を実データで**否定**した。本計画は確定した**独立6要因**を同時に根治する — **C1 収集 billing-status フィルタ**(`reconcile_invoices.py:277` collect_mf が status=invoice_issued 限定で account_transfer_notified 等へ進んだ発行済み請求を落とす=paws)・**C2 R1-collect 非決定論[構造的主因]**(curr-verdicts を吐く決定論スクリプト不在の LLM 手組みが発行済み社の当月行を落とし curr=None にする=2nd Community/HOSONO)・**C3 STATE_NEW 過剰要対応**(`curr.verdict=MATCH_ANNUAL` を正常根拠に使わず lookback 未供給で全要対応化)・**C4 prev取消の継続性欠落**(prev=REVIEW_CANCELED を発行なしと同一視し継続契約を NEW 誤判定)・**C5 代理店/複数エンドクライアント同一商品**(compare_periods の (取引先,商品) setdefault が幻の NEW+STOPPED を生み C04 collapse が発行済み金額を隠す=HOSONO)・**C6 シート MF顧客ID 0%**(ID結合経路が未使用=名前依存の潜在脆さ・ユーザー要望の恒久解)。
>
> ライフサイクル軸(13 phase・本 index + phase-01..13.md)と成果物実体軸(`component-inventory.json`・N=7 component)の 2 軸直交で計画する。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない。`plugin-plans/mf-kessai-invoice-check-fidelity`(表示・判定層根治済みの別 plan)は温存し、本 plan は発行漏れレポート根治の増分に限定する。証跡正本は `improvement-handoff.json`。

## 基本定義
- **プラグイン slug**: `mf-kessai-invoice-check`(既存プラグイン・plan_dir=`plugin-plans/mf-kessai-invoice-check-matching-rootcause/`)。
- **最上位目的 (purpose)**: 発行漏れレポートの症状「今月なし/今月金額=null/偽・発行漏れ」を、収集(C1)・入力生成(C2)・分類(C3/C4)・出力collapse(C5)・顧客ID結合(C6)の各段の確定根本原因から根治し、発行済み取引先の当月請求が正しく取得・表示・判定される状態を確定する(`goal-spec.purpose`)。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される。要件の正本は `goal-spec.json` の checklist(C1〜C14)、仕様書(本 index + 13 phase)はその被覆であり、実装との乖離が出たら仕様を先に更新してから build へ戻す(spec-first)。証拠の正本は `improvement-handoff.json`(実データ調査 findings/retractions)。
- **C番号の3系統 (混同注意)**: 本 plan には接頭辞 "C" の番号が3系統ある — ①要因=`improvement-handoff.json` の C1-C6(実データ確定6要因) ②受入 checklist=`goal-spec.json` の C1-C14 ③build component=`component-inventory.json` の C01-C07。文脈で読み分け、id 間の写像は本節「受入確認」テーブルを唯一の正本とする。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json`(N=7 component)+ `handoff-run-plugin-dev-plan.json` の生成(計画=L3 契約)。C1 収集拡張(C01)・C2 R1決定論化(C05[第一級])・C3 NEW/年契約分類 + C4 取消継続性 + C5 代理店突合(C04 classify側)・C5 collapse保全(C03 sink側)・C6 MF顧客ID結合(C02)・検証軸追加(C06)・skill配線(C07)の設計。
- **スコープ (含まない)**: 実プラグイン/実コードの build(L4・後段 `run-skill-create`/`run-build-skill`/`build-script-route.py` へ委譲)、PR/配布登録。`_is_issued` の canceled/pending/none guard(既存不変則・意図的にスコープ外)、R4-render の冪等upsert骨格(collapse保全 C03 以外は不変)、`plugin-plans/mf-kessai-invoice-check-fidelity` の再変更。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸(13 phase・人間可読)と成果物実体軸(N=7 component・機械 SSOT)を二重に持たない。
- **component_kind (5 種のうち3種使用)**: script×5(C01 収集是正/C02 顧客ID解決/C03 collapse保全/C04 分類是正/C05 R1決定論producer)/ sub-agent×1(C06 検証軸)/ skill×1(C07 配線)。hook は既存 `guard-mfk-readonly`/`guard-mfk-no-reinvent` を再利用し新規 component 化しない。
- **症状の多段性(単一バグでない)**: 「今月なし/今月金額=null」は収集(C1 billing-status)・入力生成(C2 curr=None)・出力collapse(C5)の3段で独立に生じる。「偽・発行漏れ(要対応☐)」は加えて分類(C3 NEW過剰・C4 取消誤NEW)から生じる。実レポートで今月金額=null かつ要対応は13件、うち7件は忠実 reconcile では発行済み(C2/C5 由来の偽・発行漏れ)。
- **billing lifecycle status(C1)**: MF /billings/qualified の status は invoice_issued の後に account_transfer_notified 等へ進む。collect_mf が invoice_issued 限定で取得するため後続 status の発行済み請求を落とす(paws 6月=account_transfer_notified・実在)。transaction.status=passed の月帰属 active 判定(build_mf_index)は別レイヤで温存する。
- **carrier(4種)+ 決定論ブリッジ(C2)**: `actual_amount`(MF実額)/`reliable_issued`(信頼できる発行済フラグ)/`supply_state`(`active`/`inactive_canceled`/`inactive_pending`/`none`)/`canceled_at`。reconcile() の各行(GAP/SUPPRESS 含む全 rec)を R1 が無損失に直列化し curr=None を出さないのが根治の核。curr-verdicts を吐く決定論スクリプトは現状**不在**で LLM 手組みが carrier/行を落とす=C2 の根。
- **STATE_NEW と MATCH_ANNUAL(C3)**: compare_periods の 前月なし今月あり=STATE_NEW は 12ヶ月lookback で年→月切替を裏付ける設計だが、`curr.verdict=MATCH_ANNUAL`(reconcile が年契約と判定済)を正常根拠に使わず lookback 未供給で全要対応化する。curr.verdict=MATCH_ANNUAL を dispositive な正常シグナルとして扱い、STATE_NEW 該当社へ lookback を必ず供給する。
- **取消の継続性(C4)**: prev=REVIEW_CANCELED(supply_state=inactive_canceled+canceled_at=前月発行→取消)を `_is_issued(prev)=False` で「発行なし」と同一視すると継続契約が STATE_NEW→要対応 になる(2nd Community 5月分7/3取消)。継続性判定では「前月に一度発行された」取消行を prev_issued 相当に扱い、真の未発行(supply_state=none)と区別する。
- **代理店/複数エンドクライアント(C5)**: 1商品(例『チイキズカン業務委託費』)に複数契約(（○○様）異額)を持つ代理店で、compare_periods の (取引先,商品) setdefault が1件しか残さず幻の NEW+STOPPED を生成し、notion_report_sink の (対象月,取引先名,商品名) collapse が要対応優先で発行済み実額を隠す。突合を endclient/契約ID 粒度へ下げ、collapse で発行済み実額を保全する。
- **MF顧客ID主キー(C6)**: 請求確認シート665行全ての MF顧客ID が空(0%)で `_boundary_customers` の ID優先経路が未使用=全契約が normalize(会社名)依存。mf_index から会社名→ID を解決し一意確定分を backfill して名前ドリフト耐性を得る(ユーザー要望の恒久解)。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ(新規外部依存を追加しない)。共有 script(C01-C05)は plugin-root(`plugins/mf-kessai-invoice-check/scripts/`)へ hoist し単一 skill 配下に退化させない。
- **同梱決定論ゲート**: verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage / check-surface-inventory / check-build-handoff / validate-task-graph / check-runtime-portability / check-requirements-coverage / check-plugin-goal-spec(機械正本=`specfm.GATE_SCRIPTS`)。
- **build の始め方**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順(C01→C02→C04→C03→C05→C06→C07)に消費する。mode=`update`(既存プラグインへの増分適用)。C01(収集 billing-status 是正)と C04(分類是正)と C02(顧客ID解決)は独立土台、C03(collapse保全)は C04 を、C05(R1決定論producer=構造的主因)は C01 を consume する。C06(検証軸)は C04/C05 を、C07(skill配線)が全てを統合し STATE_NEW 該当社への lookback 供給まで閉じる。
- **コンポーネント目録の所在**: buildable な実体(script×5 / sub-agent×1 / skill×1 = 計 7)は `component-inventory.json` が唯一の SSOT。既存 `lib/mfk_reconcile.py` / `lib/mfk_api.py` / `hooks/guard-mfk-no-reinvent.py` / `scripts/mfk_actuals.py` / `lib/notion_sheet_writeback.py` は独立 component 化しないが、各 route の `required_file_edits` としてブロッキング成果物に含める。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest`(handoff.envelope は既存 entry_points に変更を伴わないため `not_applicable`。詳細は handoff `open_issues` の `GAP-INVENTORY-C06-NAME-SUFFIX` 参照) |
  | composition | omitted | 既存プラグインは plugin-composition.yaml 不在・新設しない |
  | harness_eval | omitted | 既存プラグインは EVALS.json 不在・ゴールデン fixture 回帰(C12・paws/2nd Community/HOSONO 再現)で受入担保 |
  | references_config_assets | required | `plugin_meta.ssot_dedup` |
  | schemas | omitted | 既存 skill の schema 群は本改善スコープ外で温存 |
  | vendor | omitted | cross-plugin SSOT を持たず、共有 script(C01-C05)は plugin-root hoist のみで携帯性を満たす |
  | mcp_app_connector | omitted | MF/Notion 連携は既存 Bash/Skill 経路で扱う |
  | notion_config | omitted | Notion 書込みは既存 write 経路(notion_report_sink 冪等upsert・notion_sheet_writeback 片方向ミラー)を再利用し新規 write surface を作らない(C02 backfill/C03 collapse は additive 差分) |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates(p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0)+ harness_coverage(min≥80/kind_pass)を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する(design-gate/final-gate)。C06(検証subagent)は偽発行漏れ(curr脱落)/collapse隠蔽/MATCH_ANNUAL過剰要対応を独立contextで裏取りする。
- **秘匿情報非焼込**: API キー/トークンや Notion DB の具体 ID は plan 成果物に書かず、Keychain/`.notion-config.json`/`.mf-kessai-config.json` 等の実行時 config が供給する論理キー(`report_parent_page`)参照のみを宣言する。
- **既存ロジック再発明禁止**: `mfk_reconcile.py` の `normalize`/`_company_match`/`find_mf_match`/`classify`/`reconcile`/`build_mf_index` と `mfk_actuals.resolve_actual`・`mfk_period_report.py`(compare_periods/classify_period_transition)を再利用し、ゼロから作り直さない(`hooks/guard-mfk-no-reinvent.py` が機械的に遮断)。新規 script(C02/C05)は当該 hook への sanctioned basename 登録を `required_file_edits` に伴う。
- **MF API 参照専用維持**: `lib/mfk_api.py` は GET のみを維持し POST/PATCH/DELETE を実装しない(`hooks/guard-mfk-readonly.py` が機械的に遮断)。C1〜C7 のいずれも書込み系呼び出しを追加しない(C8)。
- **evidence据え置き**: `find_mf_match` の evidence は書き換えず、`reconcile_invoices.build_sink_rows` 経由の DB2 `matched_amount` 温存境界を割らない。actual/carrier のみ additive に拡張する(C9)。
- **既存成果の非後退**: PR#85(0.4.0)で確立した MF実績第一級(`_amount_of`/`_is_issued` の実額優先)・`mfk_fetch_audit` の fetch fidelity fail-closed ゲートを、各段根治後も回帰させない(C10/C11)。C1 収集拡張は status別件数を fidelity report で開示する。
- **過少報告/漏れ隠蔽を作らない**: C2 は全 rec(SUPPRESS_* 含む)persist で curr-present 化し真の月次漏れを隠さない。C5 collapse 是正は発行済み実額保全 ∧ 要対応 severity 保持を両立し片方向へ倒さない。
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
- [ ] ドメイン知識(2 軸直交 / component_kind 3 種使用 / 症状の多段性 / billing status / carrier+決定論ブリッジ / STATE_NEW+MATCH_ANNUAL / 取消継続性 / 代理店collapse / MF顧客ID)が宣言されている。
- [ ] インフラ(実行環境 / 決定論ゲート / build順序 / 目録所在 / surface 採否)が宣言されている。
- [ ] 環境ポリシー(品質基準 / proposer≠approver / 秘匿情報非焼込 / 既存ロジック再発明禁止 / MF API GET専用 / evidence据え置き / 非後退 / 漏れ隠蔽なし)が宣言されている。
- [ ] 13 フェーズ(P01..P13)が phase_number 昇順で全存在し、各 phase 本文が `specfm.PHASE_BODY_SECTIONS` の宣言型 8 節を満たす。
- [ ] `component-inventory.json` が goal-spec checklist の以下を被覆する: **C1**(C01 収集 billing-status 拡張で paws がMATCH)、**C2**(C05 R1-collect決定論producer で curr=None を出さず carrier無損失直列化=構造的主因)、**C3**(C05/C07 の seam test で carrier貫通・偽発行漏れ0件)、**C4**(C04 の STATE_NEW×MATCH_ANNUAL 正常化+lookback配線)、**C5**(C04 の prev取消継続性)、**C6**(C04 代理店突合粒度+C03 collapse発行済み保全)、**C7**(C02 MF顧客ID backfill)、**C8**(MF API GET専用維持の非破壊)、**C9**(evidence据え置き)、**C10**(MF実績第一級の非後退)、**C11**(fetch fidelity fail-closedの非後退)、**C12**(paws/2nd Community/HOSONO再現ゴールデンfixture+偽発行漏れ7社→0件回帰)、**C13**(本タスクは計画のみ生成・実コード非生成)、**C14**(C02/C12/C06 個社会社名リテラル0件の静的検査+`_COMPANY_ALIAS_GROUPS`を一般解へ吸収撤去+非ハードコードname-drift社の回帰=対症療法禁止)。
- [ ] 各 component(C01-C07)が >=1 phase の `entities_covered` に出現する(orphan 0 件)。
- [ ] 同梱決定論ゲート(核 + 拡張)が全 exit0(例外なし)。
- [ ] `handoff-run-plugin-dev-plan.json` の routes(mode=`update`)が inventory 由来で builder/build_kind/build_args/build_target を持ち、top-sort 順(C01→C02→C04→C03→C05→C06→C07)で各 component を後段 builder へルーティングする。

## 受入確認

> 計画(上記)が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった改善済みプラグインが当初 purpose を満たすか**は build 後に下記で確認する。purpose の正本 = `goal-spec.purpose`「発行漏れレポートの症状を収集・入力生成・分類・collapse・顧客ID結合の各段の根本原因から根治する」。goal-spec checklist の各 id(C1〜C14)は以下の component/phase で受入判定する。

| goal-spec checklist id | 受入観点 | 確認の見方 (build 後) | 焼き先 |
|---|---|---|---|
| C1 | 収集 billing-status 拡張 | paws 6月(account_transfer_notified)が mf_index に載り MATCH し、status別件数が fidelity report で開示されると確認 | C01 の quality_gates + harness criteria-test |
| C2 | R1-collect 決定論化(curr=None根治・構造的主因) | 2nd Community/HOSONO の当月 MATCH_MONTHLY 行が curr-verdicts へ carrier込みで直列化され今月金額=50000/210000 で出る(curr=None にならない)と確認 | C05 の quality_gates + feedback_contract |
| C3 | carrier 貫通 + 偽発行漏れ0件 | C05出力→C04消費まで carrier が欠落なく貫通し、実レポートで「今月金額=null かつ忠実発行済み」の偽発行漏れ7社が0件になると seam/回帰で確認 | C05/C07 の feedback_contract.criteria |
| C4 | STATE_NEW×MATCH_ANNUAL 正常化 + lookback配線 | MATCH_ANNUAL の新規行が lookback 無しでも正常☑になり、STATE_NEW 該当社へ --lookback-12mo が必ず供給されると確認 | C04/C07 の quality_gates |
| C5 | prev取消の継続性 | prev=REVIEW_CANCELED(発行後取消)の 2nd Community が STATE_NEW でなく継続発行として今月金額=50000 で出ると確認 | C04 の quality_gates |
| C6 | 代理店突合粒度 + collapse発行済み保全 | HOSONO の複数エンドクライアント発行が幻遷移なく突合され、collapse が発行済み実額を要対応null行で隠さないと確認 | C04/C03 の quality_gates |
| C7 | MF顧客ID backfill | 一意確定できる契約へ MF顧客ID が backfill され、_boundary_customers が ID優先で名前ドリフト耐性を得ると確認 | C02 の quality_gates |
| C8 | MF API GET専用維持 | POST/PATCH/DELETE呼び出しがhookで拒否されると確認 | hooks/guard-mfk-readonly.py |
| C9 | evidence据え置き | find_mf_matchのevidence・DB2 matched_amount温存境界が割れていないと確認 | C04/C05 の quality_gates |
| C10 | MF実績第一級の非後退 | `_amount_of`/`_is_issued`のactual_amount/reliable_issued優先順位がgolden fixture回帰で維持されると確認 | C07 の OUT2 criterion |
| C11 | fetch fidelity fail-closedの非後退 | mfk_fetch_auditのpagination/総件数/issue_date/stale検証が意図的破壊で停止し、C1収集拡張後もstatus別件数を開示すると確認 | C01/C07 の quality_gates |
| C12 | ゴールデンfixture回帰 | paws(C1)/2nd Community(C2+C5)/HOSONO(C2+C6)再現fixtureと偽発行漏れ7社→0件がpytestで全件PASSすると確認 | C07 の feedback_contract.criteria(OUT1/OUT2) |
| C13 | 計画のみ生成・実コード非生成 | 本 plan の成果物一覧に実プラグインコードが含まれないと確認 | 本 index + `handoff-run-plugin-dev-plan.json` |
| C14 | 対症療法(個社会社名ハードコード)禁止 | 照合コードに会社名リテラルが0件で静的検査が通り、`_COMPANY_ALIAS_GROUPS`(2nd Community/細野/paws)がC02のMF顧客ID一般解へ吸収・撤去され、ハードコード非対象のname-drift社がID経路のみでMATCHし「偽発行漏れ0件」がハードコード除去状態で保たれると確認 | C02/C12/C06 の quality_gates + feedback_contract |

build 後、各 component の `feedback_contract.criteria`(C07)がcriteria-test として実行され、上表の受入が PASS して初めて「purpose を満たす改善」が確定する。実行者は組み上がった実プラグインで `run-mf-invoice-report` を dry-run 実行し、2nd Community株式会社/HOSONO株式会社/paws有限会社の当月金額が正しく取得・表示され漏れチェックが正しく入ること、および「今月金額=null かつ忠実発行済み」の偽発行漏れが0件であることを目視でも確認する(trace: C07 の `feedback_contract.criteria.OUT1` が同一命題を機械回帰する)。

> **cross-plan 注記**: `plugin-plans/mf-kessai-invoice-check-fidelity` の未解決 open_issue `GAP-R1-COLLECT-CURR-PRESENT`(curr=None行のcurr-present未実装)は、本 plan C05(`reconcile()` 全rows直列化)が根治領域として引き取り副次効果で解消するが、fidelity plan 側では tracked=true・blocking=false のまま残す(二重実装回避)。証拠の正本は本 plan の `improvement-handoff.json`。
