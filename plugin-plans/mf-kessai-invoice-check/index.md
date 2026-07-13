---
id: IDX0
title: mf-kessai-invoice-check 改善計画 index (main)
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
    bundles: [xl-skills-full]
    marketplace: true
  pkg_contract:
    package_mode: bundle
    pkg: 002-008
  governance:
    applicable: false
    reason: 既存 plugin への component 追加改善であり新規 rubric governance runbook を要さない。既存の governance-check CI 配線と skill-governance-lint を継承する
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
---

# mf-kessai-invoice-check 改善計画 index (main)

> 既存プラグイン「マネーフォワード掛け払い 請求書発行チェック」への改善デルタを、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 運用サマリ (経理向け・平易版)

> **⚠ 本ページは「計画」です (実装状態バナー)。** 請求漏れレポートの Notion 出力は Design D として実装済みです。**明示 pin (config `report_database_id`) があればその DB へ確実に書き**、未設定時のみ指定ブロック/見出し周辺の既存レポート DB を探して更新します。**明示 pin なし かつ 既存 DB 未発見時は誤った DB (phantom) を作らず警告して止まります** (新規作成は明示 opt-in 時のみ)。年契約の非請求月 (金子金物型) の誤爆是正は `GAP-C05-ANNUAL-STOPPED`、2026-07-10 実運用フィードバック4要件 (継続発行=正常✓/出力先 pin/要マスタ登録=正常✓/両月なし安全網) は `GAP-2026-07-10-4REQ` として別途 build 対象です (現状コードは未反映)。
>
> この改善で「毎月・第2営業日以降に、前月と今月の請求書発行を並べて『請求漏れがないか』を一覧できる表」を作ります。読み方:
> - **1つの恒久レポート表 (Notion データベース) を使います。** まず設定で明示指定した DB (config `report_database_id`) があればその DB を使います。未設定なら指定ブロックがトグルならトグル配下の既存 DB、見出し2ならその見出し直下の既存 DB、次にページ直下の既存 DB を探します。見つかればその DB を上書き更新し、**明示指定なし かつ 見つからないときは誤った DB を作らず警告して止まります** (新規作成は明示的に許可したときだけ「請求書発行チェック」ページ直下に作ります)。
> - **出力先は「設定で指定した DB」へ確実に書きます (2026-07-10)。** 設定に DB を明示指定してあれば毎回そこへ書くので、チェック結果が別の表 (phantom) に散らばりません。指定が無く既存の表も見つからないときは、間違った表を新しく作らずに止めて知らせます〔build 後に有効・現状コードは未反映〕。
> - **なぜ新規作成はページ直下なの?** Notion API はデータベース作成時の親に block_id を指定できないため、見出し/トグル直下へ新規 DB を直接作ることはできません。ただし UI で見出し直下やトグル内に置かれた既存 DB は検出して更新できます。
> - **表の列は左から**「取引先名 / 対象月 / 漏れチェック / 商品名 / 先月の金額 / 今月の金額 / 先月と今月の比較 / コメント」の順 (各行は取引先名でページになる=Notion は title 列を最左に固定描画するため取引先名が先頭)。金額は税抜。
> - **同じ月に何度実行しても大丈夫。** 追加で取り込んだ請求書が日々足されるだけで、**前に書いた行は消えません** (上書きしても以前の情報が消えない)。同じ請求が二重に並ぶこともありません。
> - **「先月あって今月ない」でも異常とは限りません。** 年契約 (年1回だけ請求) / トライアル完了 / 契約完了 の3つは正常で、コメント欄に「なぜ問題ないか」の事情が書かれます。事情が説明できない差分だけが「漏れチェック」に赤 (要対応) で残ります。
> - **「先月も今月も請求あり」は月契約の継続発行=正常です。** 両月に金額があるものは定義上の月契約であり年契約ではありません。漏れチェックは必ず ✓ (正常) が付きます (前日 run で赤だった行も、今日 run で両月ありなら正常✓へ訂正されます)〔build 後に有効・現状コードは未反映=`GAP-2026-07-10-4REQ`〕。なお「請求はあるが金額がおかしい (過少請求など)」は正常✓のまま、コメント欄に確認メモ (REVIEW) を残す扱いです。
> - **「MF実績あり×請求確認シートに契約なし」(要マスタ登録) も正常です。** MF では発行済みでシート未登録なだけなので、漏れチェックは ✓ (正常)。コメント欄に「シートへ契約追加 or MF顧客ID登録で名寄せ恒久化」の対応方法が書かれます (漏れ=赤 にはしません)〔build 後に有効・現状コードは未反映=`GAP-2026-07-10-4REQ`〕。
> - **年契約かどうかは「商品名の文字」ではなく契約情報で見分けます。** 「商品名に年契約や期間が書いてあるか」を探すのではなく、契約マスタの『支払サイクル』設定 (年間一括更新など) と前月の年契約判定を根拠にします (商品名の期間表記は表記ゆれ・要約で消えやすく誤読の元になるため使いません。ただしトライアルだけは商品名の『トライアル』語を見ます)。これにより、**先月180万・今月空白の年契約 (例: 金子金物株式会社) を「要対応」と誤検知せず、正常な年契約周期として扱います**〔build 後に有効・現状コードは誤検知が残る〕(2026-07-08 実データで真因特定・是正要件を記録)。
> - **「先月なくて今月ある」**のは、12ヶ月前の年契約が1年経って月額へ自動で切り替わったケースが典型で、これもコメントで説明します。

## 基本定義
- **プラグイン slug**: `mf-kessai-invoice-check` (plan_dir=`plugin-plans/mf-kessai-invoice-check/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: MF 掛け払いの前月↔今月の発行状況を 2 営業日目以降に何度でも冪等再実行して比較し、年契約/年→月切替/トライアル完了/契約終了のイレギュラーをコメント説明した請求漏れレポートを、明示 pin (config `report_database_id`) を第一級 (step0) とし未設定時のみ指定ブロック/見出し周辺の既存 Notion レポート DB へ上書き更新する。明示 pin なし かつ 既存 DB 未発見時は phantom を作らず警告停止し、新規作成 (指定ページ『請求書発行チェック』直下への単一恒久 DB) は明示 opt-in 時のみ行い、`対象月` 列つきで月別履歴を同一 DB 内に非破壊保持する。
- **改善デルタ (existing-plugin-update)**: 既存 `run-mf-invoice-reconcile` (当月双方向照合) は保持したまま、前月↔今月の**時間軸比較**という新次元を足す。既存 `lib/mfk_reconcile.py` (照合エンジン)・`lib/mfk_api.py` (参照専用 GET)・請求確認シートを土台に再利用しゼロから作り直さない。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1〜C12)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、PR/配布登録、既存 reconcile/check スキルの再設計。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=6 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。本改善は「改善デルタが要する機能クラスタ (収集/分類/検証/冪等 sink/再発明遮断)」を先に列挙し新規 or 既存改修でラベリングしてから 5 種へ写像する (対称性でなく必要性で分解)。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=6 は改善デルタの buildable 実体数で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **月帰属は取引日基準**: レポートの月帰属は `transaction.date` (取引日) 基準で、既存照合と同一の月軸に揃える (発行日=翌月月初でなく取引日締め月)。
- **今月/先月の業務定義**: 本レポートの「今月」は実行日カレンダー月ではなく、月初 2 営業日目以降に確認する直近締め済みの請求対象月を指す。例: 2026-07-02 にチェックする場合、今月=2026-06分請求、先月=2026-05分請求。`--target YYMM` 指定時は target=今月(請求対象月)、target の 1 ヶ月前=先月として扱う。
- **前月↔今月のイレギュラー4分類 (本改善の中核用語)**:
  - **年契約周期** (前月あり今月なし): 年 1 回のみ請求ゆえ翌月以降は請求無しが正常。既存 verdict `SUPPRESS_ANNUAL`/`MATCH_ANNUAL` (elapsed 判定) を一次源とし、**差分に現れた該当取引先のみ** 12 ヶ月遡る判定は既存判定を上書きせずコメント根拠を補強する用途に限定する (全件遡りでない・precedence 明記で二源ドリフト防止)。
  - **年→月自動切替** (前月なし今月あり): 12 ヶ月前の年契約が満了し月額へ自動切替したため今月から請求が始まる (正常)。該当取引先の 12 ヶ月前同月を確認して判定。
  - **トライアル完了** (前月あり今月なし): 商品名に「トライアル」を含む契約が終了したため請求無し (正常)。前月だけでなく数ヶ月前まで遡って商品名トライアルを確認。判定は既存 `shohin_canon` の4値正規化後では信号が消えるため **canon 前の生商品名/MF 明細 desc** を参照する。
  - **契約終了** (前月あり今月なし): 請求確認シート『確認内容』の `請求ナシ(YYMM 終了)` 等の終了注記を既存 engine `mfk_reconcile.has_end_basis`/`_END_BASIS_PAT` が検出→ verdict `SUPPRESS_ENDED` を一次情報源とする (C05 は既存 per-月 verdict を消費し自由文を再パースしない=ユーザー『既存の仕組みを使う』指示に合致。構造化列『契約終了月』は has_end_basis と cross-check される二次情報で、根拠なき終了月は `REVIEW_ENDED_NO_BASIS` として抑制せず漏れ隠蔽を防ぐ既存安全弁を保全。`sheet_to_master._end_yymm` が自由文を意図的に不採用とする既存規律も保つ)。
  - **真の発行漏れ**: 上記 4 分類のいずれにも該当しない前月あり今月なし。漏れチェックに残す。
- **状態遷移判定フロー (ユーザー提供フローチャート=分類の SSOT・2026-07-10)**: 取引先×商品を前月集合と今月集合で突合する。今月あり×前月あり=正常:継続発行(=月契約。両月に請求があるものは定義上の月契約であり年契約ではない・漏れチェックは必ず正常✓)、今月あり×前月なし=12 ヶ月前の年契約が自動月額切替した可能性を確認(裏付けあり正常✓/裏付けなし要確認)、今月なし×前月なし=対象外(元々請求なし・原則 SKIP)、今月なし×前月あり=年契約期間内/商品名トライアル完了/契約完了(請求ナシ(YYMM 終了)等)を確認し、該当なしは発行漏れ候補(要対応)として漏れチェックに残す。加えて『先月・今月・12 ヶ月以内』での請求問題確認の**安全網**として、両月なしでも 月払い×アクティブ×2 ヶ月以上未発行(年契約/契約完了/トライアル/対象外を除外)は要対応として surface する。**要マスタ登録(MF実績あり×シート契約なし)は正常✓**として emit する(漏れ扱いしない)。
- **分類 SSOT (C05) と report DB sink (C06) の分離**: 前月↔今月の状態遷移分類は既存 per-月 verdict を入力に取る薄い差分エンジン C05 に、単一恒久 DB の解決/配置/非破壊冪等 upsert は sink C06 に分離する (既存 lib/mfk_reconcile.py と lib/notion_reconcile_sink.py の分離パターンと同型)。
- **単一恒久 report DB の解決 (Design D + 明示 pin・2026-07-10)**: C06 は **(step 0) 明示 DB pin (config `report_database_id`・ビュー/DB URL 許容) を第一級で最優先**し、未設定時のみ `report_toggle_block` を「出力先ブロック/見出し」として扱う構造的同定へ fallback する。fallback 解決順は (1) トグル内の既存 report DB (`in-block`)、(2) プレーン見出し2直下の既存 report DB (`under-heading`)、(3) ページ直下の既存 report DB (`page`)、(4) 明示 opt-in 時のみ親ページ直下へ新規 report DB 作成 (`page-created`)。**明示 pin なし かつ 既存 report DB 未発見時は phantom DB を作らず警告して停止する**(構造同定のズレで別 DB へ書き込み、チェックが本来 DB に反映されない『出力先が指定先でない』の根治)。トグル内 link_to_page 索引方式は採用しない。
- **DB の一意性 + 行の冪等**: 同一 run で毎月新しい DB を増やさず、単一 report DB に `対象月` 列を持たせる。行キーは `(対象月, 取引先名, 商品名)` とし、同一対象月の再実行では既存行を上書き更新して重複行を作らない。別月の行や過去 run の行は非破壊保持する。
- **冪等上書き (月内=日々追加 / 月跨ぎ=同一 DB 内に共存)**: 2 営業日目・3 営業日目以降に追加取り込みされる請求書を、その都度 report DB へ upsert し同月 2 回実行で重複行が出ない。**上書きは非破壊マージで以前 run の行を消さない** (全情報保持=以前の情報が消えない・手動追記の運用は無いため frozen 列は設けず単純非破壊上書き)。継続発行(今月あり×前月あり)も全 emit し全請求書を一覧する。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は `$CLAUDE_PLUGIN_ROOT`/self-relative 参照で install 位置非依存。
- **参照専用の二層維持**: MF 掛け払い API は既存 `hooks/guard-mfk-readonly.py` (Bash 変更系遮断) + `lib/mfk_api.py` (GET 専用設計) の二層で参照専用を維持する。本改善の書き込みは Notion/請求確認シート側のみ。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の 8 検査) / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す。
- **コンポーネント目録の所在**: buildable な実体 (skill×1 / sub-agent×1 / slash-command×1 / hook×1 / script×2 = 計 6) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。依存: C05←C04 (guard の SANCTIONED 拡張を先行させ C05 エンジン生成が既存 guard に遮断されないため)、C01←[C05, C06]。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` (既存 .claude-plugin/plugin.json) |
  | plugin-composition | omitted | inventory `plugin_level_surfaces.composition.omitted_reason` (単一 plugin) |
  | harness/eval | omitted | inventory `plugin_level_surfaces.harness_eval.omitted_reason` (pytest tests/ で担保・EVALS.json 非新設) |
  | references/config/assets | required | `plugin_meta.ssot_dedup` |
  | notion_config | required | inventory `plugin_level_surfaces.notion_config` (DB キーのみ宣言・ID は設置先 `.notion-config.json` / `.mf-kessai-config.json` 供給) + `plugin_meta.feedback_deploy.notion_sink` |
  | MCP/app connector | omitted | inventory `plugin_level_surfaces.mcp_app_connector.omitted_reason` |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。二段確認 sub-agent (C02) も独立 context で誤検出を排除する。
- **C02 の依存方向**: `C02.depends_on=[C01]` は build 順の依存であり、C02 が C01 の出力契約を読んで verifier prompt を生成するためのもの。C01 の runtime flow は「全 component build 後に C02 を呼ぶ」契約で、C01 build が C02 実体を前提にするという意味ではない。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **分類 SSOT**: 前月↔今月のイレギュラー分類は report 固有の script C05 (`mfk_period_report.py`) 1 箇所に集約する。C05 は既存 reconcile の per-月 verdict を入力に取るが、既存 `verdict-mapping.json` や reconcile schema へ新 4 分類を焼かず、reconcile 側が C05 を消費する前提も置かない。
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
- [ ] 基本定義 (plugin slug / purpose / 改善デルタ / スコープ) が宣言されている。
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / 月帰属 / イレギュラー4分類 / 冪等上書き) が宣言されている。
- [ ] インフラ (実行環境 / 参照専用二層 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 分類 SSOT / 現状値非焼込) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] `component-inventory.json` が 5 component_kind の検討証跡と plugin-level surfaces の採否を記録し、全 6 component (C01〜C06) が build_target 非空・builder/build_kind 整合・依存 DAG 非循環で core 規律 (quality_gates + harness_coverage + skill loop の feedback_contract) を携帯する。
- [ ] 各 component (C01〜C06) が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0 (goal-spec 要件の被覆は check-requirements-coverage が機械検査)。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target + `task_graph_ref` を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`。requirement id (C1〜C12) は `goal-spec.json` checklist と 1:1 対応 (RTM)。**id 凡例: `Cn` (C1〜C12)=要件 id / `C0n` (C01〜C06)=component id — ゼロ埋め有無で区別する (C1 要件 ≠ C01 component)。** **要件↔要件 id 写像 (2026-07-10 4要件): 要件1 (継続発行=権威ある正常✓)=C7 / 要件2 (出力先=明示 DB pin)=C10 / 要件3 (要マスタ登録=正常✓)=C12 / 要件4 (フローチャート SSOT+安全網)=C6。**

| 受入観点 (要件 id ← goal-spec) | 確認の見方 (build 後) | 焼き先 component |
|---|---|---|
| **C1**: 前月↔今月比較レポートが取引先名/対象月/漏れチェック/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの8列を『この順で』持ち title=取引先名 | 実行後レポートに 8 列が指定の左→右順で全行埋まり(先月・今月の金額並置・税抜)、title プロパティ=取引先名(列順1番目=Notion title 最左固定で取引先名を先頭)・比較列=テキスト説明 | report skill (C01) IN + sink (C06 列定義 SSOT) |
| **C2**: 差分該当取引先のみ 12 ヶ月遡って年契約周期を判定し前月あり今月なしを正常抑制 | 年契約顧客が発行漏れに出ず「年契約周期」コメントが付く | engine (C05) + report skill (C01) |
| **C3**: 前月なし今月ありを年→月自動切替として分類しコメント明記 | 12 ヶ月前が年契約の顧客に「年→月切替」コメントが付く | engine (C05) |
| **C4**: 商品名トライアルのトライアル完了 (前月あり今月なし) を検出しコメント明記 | 商品名にトライアルを含む契約に「トライアル完了」コメントが付く | engine (C05) |
| **C5**: 確認内容の `請求ナシ(YYMM 終了)` 等の終了注記(既存 has_end_basis→SUPPRESS_ENDED)を根拠に契約終了として分類しコメント明記 | 確認内容に終了注記のある契約に「契約終了」コメントが付き、根拠なき終了月は抑制されない(REVIEW_ENDED_NO_BASIS 保全) | engine (C05・既存 mfk_reconcile verdict 消費) |
| **C6**: 各イレギュラー行に事情コメントを焼き分類不能な差分は真の漏れとして残す | イレギュラー行にコメント有・分類不能行だけが漏れチェック赤 | report skill (C01) + engine (C05) |
| **C7**: 2 営業日目以降に何度でも冪等上書き(日々追加)再生成 (同月 2 回実行で重複行 0・継続発行含む全請求書 emit)。継続発行(両月あり)は権威ある月契約正常として必ず正常✓ (cross-run guard/reliable_issued 未確定に妨げられない) | 同一月で連続実行しても report DB 内の行が upsert 主キー {対象月×取引先×商品} で上書きされ重複行が出ず、継続発行も含む全請求書が並ぶ。前 run で赤だった継続発行行も今 run で両月ありなら正常✓へ訂正される(『金額あるのにチェックが入らない』の根治) | report skill (C01) の OUT criterion + report sink (C06 が period_diff『継続発行』を構造的正常マーカーへ) |
| **C8**: 独立 context の sub-agent が真の漏れを問題ないと隠していないか二段確認 | verifier が誤分類 (漏れ→対象外) を差し戻す | report verifier (C02) |
| **C9**: MF 参照専用維持 + 新規比較/分類ロジックの再実装を機械遮断 | guard hook が新規 classify/compare の Write を exit2 で遮断 | guard hook (C04) |
| **C10**: 明示 DB pin (config `report_database_id`) を step 0 で最優先し、未設定時のみ指定ブロック/見出し周辺の既存 report DB を構造同定で優先更新する。明示 pin なし+未発見時は phantom DB を作らず警告停止 (新規作成は明示 opt-in 時のみ) | 明示 pin 時はその DB へ確実に着地。未設定時のみ トグル内 DB (`in-block`) / 見出し直下 DB (`under-heading`) / ページ直下 DB (`page`) の順に既存確認し更新。対象月列により月別履歴は同一 DB 内に残る (『出力先が指定先でない』の根治) | report sink (C06) の report DB 解決 (step 0 pin + fallback) + 非破壊 upsert |
| **C11**: 上書きは非破壊マージで以前 run の行が消えず全情報を出力 | run-1={A,B}→run-2={A,C} 後も report DB が {A,B,C} を保持し clear-then-insert でない | report sink (C06) の非破壊 upsert |
| **C12**: MF実績あり×請求確認シートに契約なし=要マスタ登録 を正常✓で emit (漏れ扱いしない) | 要マスタ登録行の漏れチェック=✓ (正常)、コメントに「シートへ契約追加 or MF顧客ID登録で名寄せ恒久化」が付き、赤 (要対応) にならない | engine (C05 `_orphan_rows` を GAP_OK) + report sink (C06) |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たす改善が出来た」と確定する。EVALS.json は新設せず、per-skill の pytest tests (test_mfk_period_report ほか) + content-review verdict で受入が評価系に配線されていることを担保する。
