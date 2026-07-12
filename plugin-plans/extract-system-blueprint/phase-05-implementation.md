---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 完了
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 buildable component を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす (Green) 状態にする。build routing は `component-inventory.json` の依存 top-sort 順に実行する (phase 順 ≠ build 順)。

## 背景
buildはphase順でなくcomponent依存top-sort順に走る。C12を先にbuildし、C09/C08/C15(browser-render)、C03、推測/統合、C01、C02、C07/C14へ進む。P05だけがcomponent taskを展開してbuild_targetをproduceし、他phaseの横断checklistはentity非依存nodeとしてtask-graphへ射影する。

## 前提条件
- P04 で C01 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` のroutesがinventory由来で用意されている (`C10/C11/C12 → C09,C08,C15 → C03 → C04,C05,C13 → C06 → C01 → C02 → C07, C14`)。
- 後段 builder (run-skill-create / run-build-skill / plugin-scaffold) が利用可能。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順 (依存先が常に先。phase 番号順ではない)。
- builder 3 種の実行実体差: `builder_status` が executor-backed (run-skill-create/run-build-skill・実行 skill 実在) / contract-only (plugin-scaffold・routing 語彙のみ・`gap_ref` 必須) を区別する (解決表は io-contract §9)。
- Green 判定の主体は P04 で固定した criteria (実装が判定基準を都合よく再定義しない)。

## 成果物
- 全15 componentがbuild_targetへ生成され、skill brief 3件とplugin-level surfacesのowner/statusがhandoffで解決可能な状態。
- `envelope-draft/plugin.json` を基にした plugin manifest (後段 scaffold owner)。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)・SSOT 重複整理 (P08)。
- builder 自体の改修 (harness-creator 側の責務・gap は `open_issues` へ起票)。

## 完了チェックリスト
- [x] 各 `entity_ref` component がinventory/handoffのdepends_on top-sort後に固有build_targetへ1回だけ生成され、当該componentのoutput contractとGreen条件を満たす。
- 全体確認: C09/C08→C12、C03→C09/C08、C07→C01/C02、C14→C01/C02/C11の依存が実体配線と一致し、依存導入をP08へ先送りしない。
- 全体確認: C03はvisual formation全カテゴリ+verbatim content fact+tech_signals/nonfunctional_baseline+coverage/field gapを生成し、C04はnamed stack同定(signal factへのevidence_refs+confidence)を導出し、C13はcontent-intent推測(価値提案/キーメッセージ/読者/トーン/CTA意図/JTBD仮説)を生成し、C06はessence章を統合し、rendered asset(viewport screenshot+rendered DOM)はC03がC15 browser-render(MCP非依存headless Chrome)取得時のみ確定し(ブラウザ不在時はobservation_gap)、C11はlayout.json+SVG overlay+site coverage manifest+--check-screens/--check-applyのテキスト演算(stdlib完結)を生成する。C03-C06/C13の実promptはinventoryの実名見出し/guardを含む。
- 全体確認: C14はC02 PASS済(draft_hash一致)blueprintと自社コンテキストから採用/回避/差別化のapply-recommendations(全項目evidence_refs+confidence付きinference)をローカルのみへ生成し、doc-emit.py --check-applyを通す(外部公開なし・対象origin非アクセス・blueprint本体非混入)。
- 全体確認: C07はC01 local draft→C02 draft-hash PASS(ローカル品質verdict)の順を強制し、FAIL時はruntime request budgetをリセットしないまま有界差し戻す(外部公開Stepなし)。
- 全体確認(R5被覆の深さ・広さ): C09はURL discovery(sitemap/robots/リンクグラフ)を生成し、C12はscope分類(in_scope/excluded+reason)+crawl_profile(single|full_siteモード・瞬間負荷レバー不変・per-run有界+multi-run resume)を発行する。C03は機能アフォーダンスfact(feature_map素材)/CWV参考実測fact/security観測fact(cookie属性・認証UI・CSP全文)/compliance表面factを生成し、C04はsecurity_design推測(OWASP観点・受動観測のみ)とdelivery_topology推測を導出し、C05はuser_journeys推測を導出する。C06はfeature_map+user_journeys+security_design+delivery_topology章をblueprintへ統合し、C11はsite coverage manifest(discovered/extracted/pending/excluded+reason)を生成する。

### 受入例
- P05だけが15 build_targetをproduceし、C03-C06/C13実promptにinventory expert_lenses全件(現13名/組織)のLens見出し、C11出力にSVG overlay(stdlib text演算)、C15 browser-render取得時のみviewport screenshot/rendered DOM、C06出力にessence章、C14出力にapply-recommendationsが実装される。

### 事前解決済み判断
- build順はinventory top-sortを正本とし、local draft→C02 PASS(ローカル品質verdict)の順序を変更しない(外部公開Stepなし)。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build routing) / `component-inventory.json` (依存 DAG)。
- 対象 component C01-C15。
- 後続 P06 (test-run)。
