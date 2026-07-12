---
id: IDX0
title: extract-system-blueprint 開発計画 index (main)
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
    bundles: []  # manual-user-gated: 登録時に [xl-skills-full] を復元 (plugin.json bundle_targets と同期)
    marketplace: true
  pkg_contract:
    applicable: false
    reason: "PKG番号の割当は実build時にteam-platformが決定する (plan段階では未確定)"
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
    local_sink:
      artifact: eval-log/extract-system-blueprint/improvement-request.jsonl
      note: 外部サービス連携なしのローカル追記sink(自己完結)
    portability: vendored
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# extract-system-blueprint 開発計画 index (main)

> プラグイン構想「参考システムのURLからフロント表層の事実とバックエンド/UIUX設計意図の根拠つき推測を明示区別し、md+json+Mermaidの章別ドキュメント群としてローカルへ生成する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `extract-system-blueprint` (plan_dir=`plugin-plans/extract-system-blueprint/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: 参考システムの公開URLを認可済み・低負荷budget内で調査し、provenance付きfact・根拠付きinference・observation gapを分離したblueprintをlocal draftへ生成し、独立verdict(ローカル品質評価)PASS後にAIが追加質問なしに自社版scaffoldへ着手できるようにする(外部サービス連携なしで自己完結)。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される。要件の正本は `goal-spec.json` の checklist (C1-C9)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、PR/配布登録、UBM機能開発固有物 (PR作成/Cloudflare/IPC)。ただし『分析対象システムのスクリーンショット(有界)+細かなレイアウト記録』は製品成果物として **in-scope (C9)**。UBM がDROPした『自プラグイン自身のGUIランタイム証跡スクショ』は別物で引き続き不要 (本 plugin 成果物は Markdown/CLI 主体=P11 evidence)。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=14 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **識別子3系統 (凡例・取り違え防止)**: 受入要件=`C1..C9` (goal-spec checklist) / buildable component=`C01..C14` (inventory・ゼロ埋め2桁) / elegant-review 条件=`C1..C4` (quality_gates)。文脈で読み分ける (例: 要件 C2=推測明示区別 / component C02=評価 skill / review C2=漏れなし)。特に**受入 C9 (=スクショ/レイアウト) と component C09 (=fetch-snapshot.py・JS非実行の静的snapshot+URL discovery) は別物**。section床の番号も同様に読み分ける: §9=index側の節床 (verify-index-topsort)・§5=phase本文の節床の契約参照 (io-contract)・実節数は8 (`specfm.PHASE_BODY_SECTIONS`)。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=14 は buildable 実体数で独立に決まる (phase と component は別軸)。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **task-graph 射影**: component実体をproduceするP05だけがC01-C14を`entities_covered`へ展開する。P01-P04/P06-P13の横断checklistはentity非依存nodeとして1回だけ射影し、phase checklist×全componentの直積・P02からbuild_targetをproduceする混線を禁止する。
- **事実 (fact) / 推測 (inference) の明示区別**: 事実=対象システムから観測可能なUI要素・画面遷移・DOM構造・通信・スクリーンショット・レイアウト。推測=表面から直接観測できないバックエンド機構・設計意図を、観測事実を根拠に確度つきで記録したもの。出力上で両者を明示区別する (本 plan の purpose 中核語)。
- **画面/visual formation (C9)**: 静的に観測できる content/機能アフォーダンス/tech_signals/nonfunctional/security/compliance/site_inventory を provenance 付き fact として取得する。viewport screenshot・computed style 由来の visual formation (色/typography/影/角丸/間隔/z-layer/breakpoint 等)・JS実行後DOM・画面遷移・interaction state はブラウザ実行を要するため取得せず、observation_status=`not_observed|blocked` の observation_gap として理由付きで記録する。画面→region→主要elementのcoverageを示し、各fieldは観測値または理由付き gap のどちらかにする。local には観測できた layout.json + 番号付き overlay SVG (テキスト演算) を残す。C11 は md/json/SVG/manifest のテキスト演算に限定する (stdlib_only)。静的に観測できた CSS 由来の色/サイズ/影/角丸/間隔を重複排除した**合成 design-token palette**(全カラーパレット=hard-coded 色も含み brand/primary/accent/bg/text/border/state 等の役割ラベル付 + type/spacing/radius/shadow(elevation)/breakpoint/z-layer scale + theme別 color set)を `design-tokens.json` へ出力する(合成=C06・emit=C11・孤児0検査=C02。computed style でしか得られない値は observation_gap)。
- **コンテンツ/伝達意図/本質 (essence)**: 文字(コピー)を形成する部分は C03 が verbatim な content fact (見出し階層 h1-h6・本文/CTA/microcopy/placeholder/alt/aria-label・meta/OGP/構造化データ・言語 locale) として読み込み済み DOM から追加 network なしで採取する (ハッシュでなく原文=意味が復元できる)。その意図・意味・伝えたいことは C13 (content-intent-analyzer) が価値提案・キーメッセージ・訴求の情報階層・想定読者・トーン&ボイス・CTA意図・**対象が解こうとする本質的問題 (JTBD) 仮説**として根拠+確度つき推測で導出し、C06 が essence 章 (本質的問題/読者/価値提案/キーメッセージ/トーン/positioning・差別化) へ統合する。コピー=fact / 伝達意図・JTBD=inference の区別を貫き、「見た目だけ再現した空の器」を禁止する (受入は C1/C2/C6 拡張・新 ID は component C10 との衝突回避のため作らない)。
- **技術スタック/非機能/自社適用 (own-dev leverage)**: 技術スタックはレーン二層で抽出する — 生シグナル (response header・meta generator・bundle/script src パス・third-party request domain・cookie 名) は C03/C09 が既取得 response/network trace から**追加 network 0** で採取する `tech_signals` fact、named 同定 (「これは Next.js/Vercel/Stripe だ」の命名) は C04 が signal fact への evidence_refs+confidence 付きで導出する inference (シグナル=事実・命名=推測)。非機能は `nonfunctional_baseline` fact (resource type 別転送 byte・request 数・cache policy・圧縮・画像 format・security headers=CSP/HSTS/XFO/Referrer-Policy/Permissions-Policy) として採取し、budget 内で訪問した範囲の baseline である旨を `observed_scope` で明示する (サイト全体の性能主張へ拡大しない)。自社適用は C14 (run-blueprint-apply) が担う: C02 PASS 済 (draft_hash 一致) blueprint + 自社コンテキストのみを入力に、採用 (adopt)/回避 (avoid)/差別化機会 (differentiate) の 3 分類 apply-recommendations を**ローカルのみ**へ導出する (全項目 blueprint 実在 anchor への evidence_refs+confidence 付き inference・blueprint 本体非混入・外部公開なし・対象 origin 非アクセス・機械の床=`doc-emit.py --check-apply`)。受入は C1/C2/C6 拡張 (新 ID は component C10-C14 との衝突回避のため作らない)。
- **被覆の深さ・広さ (R5・topology 14不変)**: 機能マップ+ユーザーフロー・セキュリティ設計・配信構成+CWV・コンプライアンス周辺表面・サイト全域被覆を全て既存 component 契約拡張で吸収する。fact/inference 区別を貫く — 機能アフォーダンス (C03 fact・feature_map素材)/security観測 (C03/C09 fact=cookie属性・認証UI・CSP全文)/CWV参考実測 (C03 fact・単一訪問scope_note付き)/compliance表面 (C03/C09 fact)/site URL台帳 (C09採取・C12分類のfact) は fact レーン、user_journeys (C05)/security_design (C04・OWASP観点)/delivery_topology (C04) は evidence_refs+confidence 必須の inference レーンで明示区別し、C06 が feature_map/user_journeys/security_design/delivery_topology の各章へ統合する。security観測は受動観測のみで侵入テスト・脆弱性スキャン・認証突破を一切行わない (C5不変)。サイト全域被覆は C09 の URL discovery (sitemap/robots/same-originリンクグラフ) → C12 の scope分類 (system関連=in_scope、アフィリエイト/広告/外部SNS/トラッカー=excluded+reason・fail-closed) → C12 crawl_profile の full_siteモードで実現し、瞬間負荷レバー (origin並列1・最小間隔2000ms・Retry-After・有界backoff) は一切緩めずper-run有界予算+cache/request ledger/site coverage manifestでmulti-run resumeして全in-scope URLへ到達する (『ゆっくり確実に全部』)。screenshotはlayout template hashで同型ページを重複排除し、coverage manifest (discovered/extracted/pending/excluded+reason) はpendingを無言欠落させず完全被覆と偽装しない (C02が判定)。受入は C1/C2/C6/C8/C9 拡張 (新IDは component id との衝突回避のため作らない)。
- **著名エンジニア原則レンズ**: C03-C06/C13 の実プロンプトへ実名付き `Lens — …` 見出し、`Cross-lens conflicts`、`Neutral synthesis` を明示する。C03=Abramov/You (観測誘導のみ)、C04=Kleppmann/Vogels/OWASP (security design・ASVS/Top10・受動観測のみ)、C05=Comeau/Drasner、C13=Yifrah/NN-g (content) + Cagan/Torres (product/JTBD)、C06=Fowler/Beck。本人/組織の口調模倣・レビュー/推薦の虚偽主張・名前だけでのPASSを禁止し、C04/C05/C13/C06の主張は evidence_refs+confidence 必須、fact lane は中立に保つ。構造化正本は inventory `expert_lenses/prompt_contract`。
- **proposer≠approver**: run-extract-blueprint (C01) が生成し、assign-blueprint-fidelity-evaluator (C02) が独立 context で忠実性を評価する非対称構造。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **静的観測 runtime**: 取得は静的 HTTP (WebFetch/stdlib urllib) のみで自己完結し、外部実行時connector(ブラウザランタイム等)へ依存しない。WebFetch は lossy な静的補助経路であり SPA の実行後 DOM/通信を保証しない。JS実行を要する観測 (実行後 DOM/interaction/screenshot/computed style) は取得せず、重要 fact に該当する場合は `observation_status=not_observed|blocked` を記録し C02 を FAIL、JS非依存で静的完結が実測で示せる場合は gap 記録つき PASS 可 (正本= inventory `plugin_level_surfaces.mcp_app_connector` の条件文)。
- **低負荷調査**: origin 単位で並列数1、request/byte/page/interaction budget、最小間隔、同一URL cache、`Retry-After`、有界backoffを適用し、429/403/robots拒否/予算超過/応答不安定時は停止する。再試行は予算をリセットしない。詳細layoutは読み込み済みDOM/同一sessionから採取し、viewport resizeも再読込なしを優先する。再読込が生じた場合は既存request budgetへ計上する。スクリーンショット取得は**瞬間負荷レバーを一切緩めず**、総取得 byte のみ専用 screenshot budget 分だけ有界に増やす。image 描画は専用passのみ、cache/reuseで再撮影を避ける。既定上限を引き上げる変更はユーザー承認対象。
- **独立品質評価**: C01 が固定した local draft に対し、C02 が同じ draft hash へ PASS/FAIL verdict を独立 context で発行する (proposer≠approver)。外部サービスへの公開はなく、成果物はローカルで自己完結し、PASS 後だけ自社適用 (C14) へ進む。C08 hook は fetch-authz の単一述語 (matcher=`Bash|WebFetch`) で認可外・期限切れ・予算外フェッチのみを exit2 で fail-closed 遮断する。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の検査) / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。ゲート成果物 `.gate/*.pass` (hash 1行) の再現検証は対応script (check-intake-consumption.py / check-provenance-chain.py) の再実行による。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す (詳細手順は焼かない)。
- **コンポーネント目録の所在**: buildable な実体 (skill×3 / sub-agent×5 / slash-command×1 / hook×1 / script×4 = 計 14) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required | `plugin_meta.ssot_dedup` + `references/expert-lens-roster.md` |
  | schemas (fact/inference/gap + blueprint) | required | `schemas/fact-inference-confidence.schema.json` + `schemas/system-blueprint.schema.json` |
  | vendor | omitted | component inventory の omitted_reason (plugin-root hoist で携帯性を満たすため不要) |
  | 外部runtime connector | omitted | 外部connectorは使わず静的HTTP(WebFetch/stdlib)のみで自己完結。JS実行を要する観測は observation_gap (正本=inventory `mcp_app_connector` 条件文) |

- **component roster (人間可読サマリ・正本は `component-inventory.json`)**: id/名前/一行役割/depends_on。SSOT は inventory であり本表は可読ダイジェスト。

  | id | 名前 | 一行役割 | depends_on |
  |---|---|---|---|
  | C09 | fetch-snapshot.py (script) | AuthzEvidence/budget内で静的/SSR HTTP snapshotを低負荷取得 (SPA実行時観測は対象外) | C12 |
  | C10 | mermaid-validate.py (script) | 製品出力の必須5図種の存在+構文検証ゲート | — |
  | C11 | doc-emit.py (script) | md+json整形+layout/注釈overlay(テキスト演算)生成+completeness検査 (screenshotはobservation_gap) | — |
  | C12 | authz-classify.py (script) | 根拠付きAuthzEvidence + request/byte budgetの単一SSOT (unknownはdeny) | — |
  | C08 | pre-fetch-authz-guard (hook) | 認可外・期限切れ・予算外フェッチの fail-closed 遮断 (matcher=Bash\|WebFetch) | C12 |
  | C03 | frontend-surface-analyzer (sub-agent) | 静的HTTP応答から content/tech/security fact を観測 (Abramov/Youレンズは観測誘導のみ・screenshot/実行後DOMはobservation_gap) | C09, C08 |
  | C04 | backend-inference-analyzer (sub-agent) | バックエンド機構+named stack同定+security_design(受動観測のみ)+delivery_topologyの根拠+確度つき推測(レンズ Kleppmann/Vogels/OWASP) | C03 |
  | C05 | uiux-rationale-analyzer (sub-agent) | UI/UX設計意図の根拠+確度つき推測 (C04と直交・UIUXレンズ Comeau/Drasner) | C03 |
  | C13 | content-intent-analyzer (sub-agent) | コピーの伝達意図=価値提案/キーメッセージ/想定読者/トーン&ボイス/CTA意図+本質的問題(JTBD)仮説の根拠+確度つき推測 (C04/C05と直交・contentレンズ Yifrah/NN-g + productレンズ Cagan/Torres) | C03 |
  | C06 | architecture-essence-synthesizer (sub-agent) | 本質/アーキ統合+essence章(本質的問題/読者/価値提案/キーメッセージ/トーン/positioning)+5種Mermaid生成+screen-flowへscreenshot/layout紐付け(アーキレンズ Fowler/Beck) | C03, C04, C05, C13, C10, C11 |
  | C01 | run-extract-blueprint (skill/run) | Authz→取得→分析→local draft→独立品質評価 | C12, C09, C08, C10, C11, C03, C04, C05, C13, C06 |
  | C02 | assign-blueprint-fidelity-evaluator (skill/assign) | 独立contextの忠実性 verdict (proposer≠approver)。mermaid-validate.py と doc-emit.py --check-screens を評価側の共有決定論ゲートとして併用 | C01, C10, C11 |
  | C07 | extract-blueprint (slash-command) | C01 draft→C02独立verdict(ローカル品質評価)を統括 | C01, C02 |
  | C14 | run-blueprint-apply (skill/run) | C02 PASS済blueprint+自社コンテキスト→採用/回避/差別化のapply-recommendationsをローカルのみへ導出 (全項目evidence_refs+confidence付きinference・blueprint非混入) | C01, C02, C11 |

  build 順 (依存 top-sort): `C10 / C11 / C12 → C09, C08 → C03 → C04, C05, C13 → C06 → C01 → C02 → C07, C14`。

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。生成 (C01) と評価 (C02) も skill レベルで非対称分離する。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **fail-closed 原則**: C12のAuthzEvidenceがdeny|unknown・期限切れ、またはrequest budget超過ならC08がexit2で遮断する。非fetch Bashは通過し、曖昧なfetch入力は安全側へ倒す。
- **独立評価ゲート**: C01はlocal draftを先に固定し、C02が同じdraft hashへPASS verdictを発行した場合だけ自社適用(C14)へ進む。FAIL成果物は下流へ渡さない(外部公開なし)。
- **ループ分離**: plan review (`goal-spec.max_loops=3`) はplan findings修正の上限、runtime goal-seek (`C01.goal_seek.max_loops=5`) は同一request budget内の抽出改善上限。runtime再試行で予算はリセットせず、各上限超過は別々にopen issue/FAILへ遷移する。

## フェーズ一覧

1. P01 — requirements (要件定義) / 完了
2. P02 — design (設計) / 完了
3. P03 — design-review (設計レビューゲート) / 完了
4. P04 — test-design (テスト設計) / 完了
5. P05 — implementation (実装) / 完了
6. P06 — test-run (テスト実行) / 完了
7. P07 — acceptance-criteria (受入基準判定) / 完了
8. P08 — refactoring (リファクタリング) / 完了
9. P09 — quality-assurance (品質保証) / 完了
10. P10 — final-review (最終レビューゲート) / 完了
11. P11 — evidence (手動テスト検証) / 完了
12. P12 — documentation (ドキュメント) / 完了
13. P13 — release (完了/PR・リリース) / 完了

## 完了チェックリスト
- [x] 基本定義 (plugin slug / purpose / スコープ) が宣言されている。
- [x] ドメイン知識 (2 軸直交 / component_kind 5 種 / 事実推測区別 / 用語集) が宣言されている。
- [x] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [x] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / fail-closed) が宣言されている。
- [x] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [x] `component-inventory.json` が 5 component_kind の検討証跡と plugin-level surfaces の採否を記録し、全 14 component が build_target 非空・builder/build_kind 整合・依存 DAG 非循環で core 規律 (quality_gates + harness_coverage + skill loop の feedback_contract) を携帯する。
- [x] 静的に観測できるfact (C9) が低負荷budget内で取得され、観測できたlayout.json+番号付きoverlay(テキスト演算)としてlocalへ残る設計がC03/C11/C01/C02へ紐づく (screenshot/JS実行後DOMはobservation_gap・外部公開なし)。C03-C06/C13の実名付き原則レンズprompt契約と非模倣/fact非混入guardも宣言済み。
- [x] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [x] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [x] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画が満たすのは「各componentが評価基準を携帯し決定論ゲートを通る」こと。実pluginのpurpose達成はbuild後に下表で確認する。purposeの正本は`goal-spec.purpose`、受入の正本はgoal-spec checklist C1-C9であり、認可・低負荷・欠測・独立承認・画面配置(スクショ/レイアウト)も含め全件を被覆する。

| 受入観点 (goal-spec checklist 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| C1 フロント事実抽出 | C09のHTTP snapshotとC03の静的HTTP観測により、UI要素・観測通信(実行後DOM/画面遷移はobservation_gap)に加え、文字(コピー)のverbatim content fact(見出し階層/本文/CTA/microcopy/meta・OGP/構造化データ/locale)、tech_signals fact(header/generator/bundleパス/third-party domain/cookie名)、nonfunctional_baseline fact(転送byte/cache/圧縮/画像format/security headers・observed_scope明示)、機能アフォーダンスfact(feature_map素材)、security観測fact(cookie属性/認証UI/CSP全文)、CWV参考実測fact(単一訪問scope_note付き)、compliance表面fact(privacy/規約/特商法/CMP)、site URL台帳fact(site_inventory=discovered/in_scope/excluded+reason)がprovenance付きfactとして追加network 0で抽出され、未観測はinferenceでなくgapとして明示済み | C12/C08/C09 + frontend-surface-analyzer (C03) + C01 IN1 |
| C2 根拠つき推測の明示区別 | C03-C06/C13の実promptに実名Lens見出し・cross-lens conflicts・neutral synthesis・非模倣/非推薦guardがあり、レンズ由来主張は evidence+confidence 必須で fact 非混入。名前だけでPASSしない。C13がコピーの伝達意図(価値提案/キーメッセージ/想定読者/トーン&ボイス/CTA意図)とJTBD仮説を、C04がtech_signals factを根拠とするnamed stack同定・security_design(OWASP観点・受動観測のみ)・delivery_topologyを、C05がuser_journeysを推測として導出。C14のapply-recommendationsも同一inference規律(blueprint anchorへのevidence_refs+confidence)に従う | C03-C06/C13 `expert_lenses/prompt_contract` + content-intent-analyzer (C13) + backend-inference-analyzer (C04) tech_stack.identified/security_design/delivery_topology + uiux-rationale-analyzer (C05) user_journeys + run-blueprint-apply (C14) + C02 anti-overfit |
| C3 5種Mermaid | 対象システム接地の5種図(①対象システム全体構成図/②事実↔推測区別レイヤ図/③画面遷移図(screen-flow)/④データフロー・リクエスト/レスポンスのシーケンス図/⑤主要エンティティのデータモデル図)が製品出力に含まれ、mermaid-validate.py が exit0。harness-meta図(as-is/Before-After/plugin責務分離)は本plan自身の可読図で製品出力契約外 | architecture-essence-synthesizer (C06) + mermaid-validate.py (C10) |
| C4 ローカル出力 | ローカルへmd+json+Mermaid+観測できたlayout.jsonが出力され、独立C02 verdictの評価対象として揃う(外部公開なし・screenshotはobservation_gap) | C11 emit + C01 OUT1 + C07 orchestration |
| C5 認可外アクセス無し | C12の根拠付きAuthzEvidenceがallowの範囲だけ取得し、deny|unknown・期限切れはC08が遮断したdeny matrix/ledgerを確認 | C12 AuthzEvidence + C08 guard + C09/C03 ledger |
| C6 AI入力粒度 | top-level blueprint schemaが満たされ、重要fact欠測0・未回答質問0で最小scaffold骨子を導出できる。essence章(本質的問題JTBD/想定読者/価値提案/キーメッセージ/トーン/positioning・差別化)が明示され、見た目(色/配置)だけでなく『何を・誰に・なぜ伝えるか』まで再構成できる(空の器の禁止)。feature_map(機能一覧・C03 fact集約)とuser_journeys(主要タスクの開始→完了フロー・C05推測)が明示区別され、AIが『どの画面で何ができ、ユーザーがどう目的を達するか』まで再構成できる。自社コンテキスト提供時はC14が採用/回避/差別化のapply-recommendationsをローカルへ導出でき、doc-emit.py --check-applyがexit0(未提供時はblueprint単体で完結) | architecture-essence-synthesizer (C06) essence章+feature_map+user_journeys + assign-blueprint-fidelity-evaluator (C02) のdraft-hash束縛独立 verdict + run-blueprint-apply (C14) |
| C7 責務分離 | plugin構成が確定したとき、取得・分析・生成・公開・自社適用の責務がcommand/skill/agentへ単一責務分解されている | `component-inventory.json` 全体 (C01-C14・5 component_kind 写像) |
| C8 低負荷調査 | origin並列数1・cache・request/byte/page/interaction予算・最小間隔・Retry-After・有界backoff・停止条件がrequest ledgerで確認でき、予算超過0。crawl_profile full_siteモードでも瞬間負荷レバーが緩まず、per-run有界予算+cache/request ledger/site coverage manifestによるmulti-run resumeで全in-scope URLへ到達すると確認できる | C12 budget/crawl_profile + C08 guard + C09/C03 request ledger + C02 verdict |
| C9 スクショ+visual formation | identity/geometry/layout/paint/typography/media/effects/pseudo/state/motion/responsive/a11y/tokensの全カテゴリ、coverage、field gap、redacted screenshot/layout.json/番号付きoverlayが揃い、色合いまで再形成できる。サイト全域被覆時は台帳の全in-scope画面がscreenshot対象でlayout template hashによる同型ページ重複排除が働き、site coverage manifest(discovered/extracted/pending/excluded+reason)が無言欠落なくpendingを完全被覆と偽装しない。screenshot/JS実行後DOMはobservation_gap | C03 static facts + C09 discovery + C12 scope分類 + C11 completeness/manifest + C02 verdict |

build 後、C01 の `feedback_contract.criteria` (IN1/OUT1) と C14 の criteria (IN1/OUT1) が criteria-test として実行され、C02 の独立 verdict と mermaid-validate.py (C10) の exit0 判定が上表の受入と合わせて PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
