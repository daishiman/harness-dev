---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
capability (取得→分析→文書化→品質評価→自社適用) を 5 種の component_kind (skill/sub-agent/slash-command/hook/script) へ写像し、N=15 実体を `component-inventory.json` へ分解する。各 component の build_target・依存 DAG・品質機構を確定し、plugin envelope (`.claude-plugin/plugin.json`) の draft を設計する owner フェーズ。成果物はローカル完結で外部サービス(MCP/Notion)へは公開・接続しない。

## 背景
P01のgoal-specをbuild可能な実体へ落とす。C03=C09(fetch-snapshot.py=stdlib静的observer)の`static-observation.json`からvisual formation fact+verbatim content factを採取し、rendering必須fact(実行後DOM/viewport screenshot/computed幾何)は任意のC15(browser-render.py=MCP非依存のローカルheadless Chrome)取得時のみ加える、C11=layout.json/SVG overlay/site coverage manifestのstdlib text演算emit、C01=ローカルdraft生成、C02=ローカル品質verdict(completeness/prompt contract評価)へ既存責務を拡張する。JS実行後DOM・viewport screenshot取得のためのbrowser-render(C15)はMCP非依存のprogressive enhancementとして新設しtopology 14→15へ拡張し、ブラウザ不在時(exit3=browser-unavailable)は該当観測をobservation_gapへ縮退して静的観測で続行する。C03-C06/C13のstructured expert_lenses/prompt_contractは各agentへ吸収する(C13分はC13新設時に追加)。文字(コピー)の伝達意図と本質的問題(JTBD)の抽出層はユーザー承認の構造変更としてsub-agent C13(content-intent-analyzer)を新設し、topology 12→13へ拡張する(C13はC04/C05と同格のC03起点直交推測レンズ・統合はC06のessence章)。自社開発活用層(R4)は、tech_signals/nonfunctional_baseline=C03/C09のfact採取拡張+named stack同定=C04のinference拡張(レーン二層化)で既存責務へ吸収し、自社適用の最後の一歩だけはユーザー承認の構造変更としてskill C14(run-blueprint-apply)を新設してtopology 13→14へ拡張する(C14=C02 PASS済blueprint+自社コンテキスト→採用/回避/差別化のapply-recommendationsをローカルのみへ導出する下流skill・blueprint本体非混入)。被覆の深さ・広さ層(R5・topology 14不変)は全て既存component契約拡張で吸収する: C03=機能アフォーダンスfact(feature_map素材)/CWV参考実測fact/security観測fact(cookie属性・認証UI・CSP全文)/compliance表面factの採取拡張、C05=user_journeys推測拡張、C04=security_design推測(OWASPレンズ追加・受動観測のみ)とdelivery_topology推測拡張、C06=feature_map/user_journeys/security_design/delivery_topology章統合拡張、C09=URL discovery(sitemap/robots/リンクグラフ)拡張、C12=scope分類(in_scope/excluded+reason・fail-closed)とcrawl_profile(single|full_site)拡張、C11=site coverage manifest emit拡張。新規componentは追加しない。

## 前提条件
- P01 の `goal-spec.json` が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約 (`references/plugin-creator-contract.md`) を参照できる。
- 同一 kind の複数実体 (sub-agent×5 等) はそれぞれ独立 component として扱う前提を共有している。

## ドメイン知識
- 正規化原則: build_target/depends_on は `component-inventory.json` のみが保持し、phase ファイルは `entities_covered` の id 参照だけで紐づく (二重保持は drift 源)。
- kind 写像の判定核: 独立 context で事実/推測/根拠/本質を分離検証する必要→sub-agent、認可外フェッチの機械遮断→hook、決定論検査 (fetch/mermaid構文/schema整形)→script (5 種の定義は index `## ドメイン知識` 参照)。
- `placement_scope`: C09-C12はplugin-rootへhoistする。C09/C08はC12へdepends_onし、C03はC09/C08へdepends_onする。C12は根拠付きAuthzEvidenceと共有budget、C03はC15 browser-render(MCP非依存headless Chrome)取得時のrendered factまたは明示gapを出す。
- visual formation取得: C03がC09の静的DOM(宣言CSS/accessibility semantic)から追加networkなしで採取し、画面→region→主要elementへ限定してclient CPU負荷も抑える。computed style/viewport screenshotはC15 browser-render取得時のみ加わる(不在時はobservation_gap)。C11がlayout.json/番号付きoverlay(stdlib text演算)を生成し、C01がローカルdraftへ束ねる。実名レンズpromptは非模倣/非推薦guardとneutral synthesisを必須化する。
- proposer≠approver: run-extract-blueprint (C01, kind=run) が生成し、assign-blueprint-fidelity-evaluator (C02, kind=assign) が独立 context で忠実性を評価する非対称構造。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 15 component)。
- `envelope-draft/plugin.json` (manifest draft)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [x] 全 15 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [x] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces (manifest/composition/harness_eval/references_config_assets/schemas/vendor) の採否が明示されている(外部サービス連携surface=MCP/Notionは非依存で不採用)。
- [x] `envelope-draft/plugin.json` に manifest draft (entry_points / hooks 配線 / distribution) が設計されている。
- [x] schemaがvisual formation全カテゴリ、coverage manifest、field単位gap、layout/overlay asset refs(browser-render取得時のrendered/screenshot refs含む)を持ち、full_site multi-run resumeが横断契約として確定している。
- [x] C03-C06/C13のstructured expert_lenses/prompt_contract、C13 content-intent契約(verbatim copy fact入力→価値提案/キーメッセージ/読者/トーン/CTA意図/JTBD仮説のinference出力)、C06 essence章契約、C11 completeness、C01 ローカルdraft生成、C02 anti-overfit品質評価が確定し、topology 12→13の構造変更はユーザー承認済である。
- [x] tech_signals/nonfunctional_baseline(C03/C09のfact・追加network 0・observed_scope明示)とnamed stack同定(C04のinference・signal factへのevidence_refs+confidence必須)のレーン二層化、C14 apply契約(C02 PASS済blueprint+自社コンテキスト入力→採用/回避/差別化のinference出力・ローカルのみ・doc-emit.py --check-apply)が確定し、topology 13→14の構造変更はユーザー承認済である。
- [x] R5(被覆の深さ・広さ)契約が確定している: C03/C09=機能アフォーダンス/CWV/security観測/compliance表面fact、C05=user_journeys推測、C04=security_design(OWASPレンズ・受動観測のみ)/delivery_topology推測、C06=feature_map+user_journeys+security_design+delivery_topology章統合、C09=URL discovery、C12=scope分類(in_scope/excluded+reason)+crawl_profile(single|full_siteモード・瞬間負荷レバー不変・per-run有界+multi-run resume)、C11=site coverage manifest emit。全て既存component契約拡張でtopology 14不変。

### 受入例
- inventoryにC03 visual formation+content fact+tech_signals/nonfunctional_baseline、C04 named stack同定、C13 content-intent、C06 essence章、C11 layout/overlay/site coverage manifest+--check-apply、C15 browser-render(rendered/screenshot取得・不在時gap縮退)、C01 ローカルdraft生成、C02 completeness/prompt品質評価、C14 apply-recommendationsがあり、15-component DAGが非循環で閉じる。

### 事前解決済み判断
- C13(content-intent-analyzer)とC14(run-blueprint-apply)の新設はユーザー承認済の構造変更で、それ以外(tech_signals/nonfunctional_baseline/named同定含む)は既存責務の拡張に留める。visual formation正本はschema、実名prompt正本は`expert_lenses/prompt_contract`へ置く。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md`。
- 対象 component C01-C15 (`component-inventory.json`)。
- 後続 P03 (この設計を design-gate で審査する)。
