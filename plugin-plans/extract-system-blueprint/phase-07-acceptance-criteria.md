---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
plugin全体の二値ACをbuild後に判定する。goal-spec checklist C1-C9が、安全な取得→観測(レイアウト・browser-render取得時のスクショ含む)→推測(役割レンズ)→local draft→独立品質承認(ローカル完結・外部公開なし)の価値連鎖として満たされるかを固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが事実/推測明示区別・5種Mermaid・ローカル出力・認可外アクセス防止という purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と C01 の criteria が確定している。
- goal-spec checklist C1-C9 を受入観点の正本として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証 (両方必要・相互代替不可)。
- 事実/推測の観測方法: 生成された json で事実フィールドと推測フィールド (根拠+確度) が分離されているかを目視/schema で確認する (C02 の verdict と対応)。
- fail-closed: 判定不能・異常時に安全側 (拒否) へ倒す性質 (C08 hook の受入観点)。

## 成果物
- 全 component の AC 判定結果 (PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.checklist`・ここでは判定のみ)。

## 完了チェックリスト
- [x] C12/C08/C09/C03/C01: HTTP snapshotと低負荷browser観測からUI要素・限定画面遷移・実行後DOM・観測通信、tech_signals(header/generator/bundleパス/third-party domain/cookie名)とnonfunctional_baseline(転送byte/cache/圧縮/画像format/security headers・observed_scope明示)、機能アフォーダンスfact(feature_map素材)・security観測fact(cookie属性/認証UI/CSP全文)・CWV参考実測fact(単一訪問scope_note付き)・compliance表面fact(privacy/規約/特商法/CMP)・site URL台帳fact(site_inventory=discovered/in_scope/excluded+reason)がprovenance付きfactとして追加network 0で抽出され、欠測がinferenceへ昇格していない (C1)。
- [x] C04/C05/C13/C14/C01: バックエンド機構・設計意図に加え、コピーの伝達意図(価値提案/キーメッセージ/想定読者/トーン&ボイス/CTA意図)と本質的問題(JTBD)仮説、tech_signals factを根拠とする技術スタックnamed同定(framework/hosting/CDN/analytics/SaaS)、主要タスクのuser_journeys推測、security_design推測(認証方式/セッション管理/CSRF・XSS対策/CSP評価/攻撃面をOWASP観点で・受動観測のみ)、delivery_topology推測(CDN/edge/origin構成・static|SSR|ISR判定・キャッシュ階層)、および自社コンテキスト提供時のapply-recommendationsが根拠+確度つき推測として事実と明示区別され json へ記録済みと判定できる。推測は著名エンジニア役割レンズで深めるがレンズ由来主張もevidence_refs+confidence必須でfactへ非混入(persona-non-contamination)と判定できる (goal-spec 要件 C2)。
- [x] C06/C10: 対象システム接地の5種Mermaid図(①対象システム全体構成図/②事実↔推測区別レイヤ図/③画面遷移図(screen-flow)/④データフロー・リクエスト/レスポンスのシーケンス図/⑤主要エンティティのデータモデル図)が製品出力に含まれると判定できる。harness-meta図(as-is/Before-After/plugin責務分離)は本plan自身の可読図で製品出力契約外 (goal-spec 要件 C3)。
- [x] C01/C02/C07/C11: local draft hashへC02 PASS(ローカル品質verdict)が束縛され、md+json+Mermaid+layout.json/番号付きoverlay(browser-render取得時のrendered DOM/screenshot含む)がローカルへ揃い、外部公開Stepが存在しない (C4)。
- [x] C12/C08/C09/C03: deny|unknown/期限切れをfail-closedに遮断し、無断アクセス・認可外スクレイピング0をAuthzEvidence/deny ledgerで示す (C5)。
- [x] C02: top-level schema必須項目・重要fact欠測0・未回答質問0・最小scaffold骨子導出に加え、essence章(本質的問題JTBD/想定読者/価値提案/キーメッセージ/トーン/positioning・差別化)の明示とverbatimコピーfactの被覆、feature_map(C03機能アフォーダンスfact集約)とuser_journeys(C05推測)の明示区別された被覆を同一draft hashへの独立verdictでPASSする=見た目だけの空の器を禁止 (C6)。
- [x] C14: 自社コンテキストを与えたときC02 PASS済blueprintから採用/回避/差別化の3分類apply-recommendationsがローカルへ導出され、全項目がblueprint実在anchorへのevidence_refs+confidence付きinference・blueprint外の無根拠主張0件・doc-emit.py --check-apply exit0と判定できる(未提供時はblueprint単体で完結) (C6)。
- [x] component-inventory.json: 取得・分析・生成・品質評価・自社適用の責務がcommand/skill/agentへ単一責務分解されていると判定できる (goal-spec 要件 C7)。
- [x] C12/C08/C09/C03: origin並列数1・cache再利用・request/byte/page/interaction budget・最小間隔・Retry-After・有界backoff・停止条件がrequest ledgerで満たされ、予算超過0。crawl_profile full_siteモードでも瞬間負荷レバーが緩まず、per-run有界予算+cache/ledger/site coverage manifestによるmulti-run resumeで全in_scope URLへ到達すると判定できる (C8)。
- [x] C03/C11/C02: visual formation全カテゴリ、coverage、field gap、layout.json、番号付きoverlayが揃い(viewport screenshot/rendered DOM/computed幾何はC15 browser-render取得時のみfact・不在時はobservation_gap)、AIが色合い・文字・box model・配置・asset・state・motion・responsive差分を再形成できる。合成design-tokens.json(カラーパレット+type/spacing/radius/shadow(elevation)/breakpoint/z-layer scale+theme別color set+document brand色)が観測色を漏れなく被覆(孤児0)しlight/dark両テーマが揃い色値が正準表現で保持され、AIが色合いを一貫再現できる。サイト全域被覆時は台帳の全in-scope画面が観測対象でlayout template hashによる同型ページ重複排除が働き、site coverage manifest(discovered/extracted/pending/excluded+reason)が無言欠落なく保持されpendingを完全被覆と偽装しない。成果物はローカル完結で外部公開はしない。取得不能は理由付きgap (C9)。

### 受入例
- AIがblueprintから色・文字(verbatimコピー)・box model・配置・asset・state・motion・responsive差分・技術スタック(シグナルfact+named同定)・非機能水準に加え、essence章から『何を・誰に・なぜ伝えるか』まで再構成でき、自社コンテキストを与えれば採用/回避/差別化の適用推奨まで導出でき、成果物はローカル完結で確認できる。

### 事前解決済み判断
- 受入正本はgoal-spec C1-C9、名前の出現数ではなくfact/inference分離・根拠品質・visual coverageで判定する。

## 参照情報
- `goal-spec.checklist` (C1-C9) / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C15。
- 後続 P08 (refactoring)。
