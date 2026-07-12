---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
全 component の harness coverage を ≥80% (kind 別・6 種別 × 二軸) まで拡充し、テストを実行して緑にする。計画段階では現状カバレッジ数値を焼かず、min=80 の閾値と kind_pass の見方のみを契約する。

## 背景
harness coverage は品質の最低ラインを機械保証する仕組み。計画段階で現状値を焼くと Goodhart 化する (数値合わせが目的化する) ため、min=80 の閾値と kind 別パス観点のみを契約し、実測は build 後に行う。この二層分離が「≥80% を満たす設計」を要件化しつつ数値水増しを防ぐ。

## 前提条件
- P05 で全 component が build_target に実体化されている。
- 各 component が harness_coverage ブロック (min/kind_pass) を携帯している。
- kind 別パス観点 (script→行カバレッジ / skill loop→criteria 検証+content-review / assign→evaluator-verdict / sub-agent・command・hook→機能テスト+content-review) を参照できる。

## ドメイン知識
- kind 別カバレッジ観点: script=行カバレッジ / skill(run)=criteria 検証+content-review / skill(assign)=evaluator-verdict / sub-agent・command・hook=機能テスト+content-review (正本は harness-coverage-spec)。
- Goodhart 回避の不変条件: 計画には閾値 (min=80) と観点のみを焼き、現状実測値は焼かない (数値合わせの目的化を防ぐ)。

## 成果物
- 全 component の harness テスト実行ログ (kind 別 ≥80%)。

## スコープ外
- purpose 受入の判定 (P07・カバレッジ緑≠受入充足)。
- criteria 自体の変更 (P04 へ差し戻し)。
- 閾値の変更 (harness-coverage-spec が正本・plan 側で上書きしない)。

## 完了チェックリスト
- [x] 全 component の harness_coverage.min≥80 が実測で満たされ、kind_pass の観点が緑になる。
- [x] 現状値を計画に焼かず、閾値と観点のみを契約として保持している。
- [x] C12/C08/C09/C03のdeny|unknown/期限切れ/予算超過/429/403/Retry-After/cache hitを含むdeny・負荷matrixが緑で、origin並列数1とbudget非リセットを実測する。
- [x] C03のstatic/SSR・browser-render(C15)有/無・blockedの各fixtureでfactとobservation_gapが混同されず、WebFetchだけでSPA成功扱いしない。
- [x] C03がvisual formation全カテゴリをfixtureで取得し、色/gradient/border/radius/shadow/font/media/SVG/icon/filter/transform/pseudo/state/motion/responsive/a11y/tokenの欠測を無言欠落させずfield単位gapにする。画面→region→主要element coverageと注釈番号1:1を検査する。computed-style採取で追加network 0、state操作はmax_interactions内、再読込はledger計上、鍵画面gapはC9 FAILとする。
- [x] 実名レンズ有効時もfactへ意見が混入せず、required prompt headings/非模倣/非推薦/cross-lens conflicts/neutral synthesisが存在する。名前だけのfixtureはFAIL、根拠付き推論はPASS、highは複数直接evidenceだけを許す。
- [x] content/essence fixtureで、verbatimコピーfact(見出し階層/CTA/microcopy/meta・OGP/構造化データ)の採取が追加network 0で行われ欠落が理由付きgapになること、C13推測が全てevidence_refs+confidenceで接地すること、C06 essence章(本質的問題JTBD/読者/価値提案/キーメッセージ/トーン/positioning)が明示されfactと区別されることを実測する。
- [x] browser-render fixtureでbrowser-unavailable(exit3)時のobservation_gap(reason=browser-unavailable)縮退、rendered DOM/viewport screenshot取得時のfact化、asset hash重複回避、C12認可境界の import 共有(fail-closed)、対象originへの429 Retry-After尊重を実測する。
- [x] tech/nonfunctional fixtureでtech_signals(header/generator/bundleパス/third-party domain/cookie名)とnonfunctional_baseline(転送byte/cache/圧縮/画像format/security headers)が追加network 0・observed_scope付きで採取され、named同定が全てsignal factへのevidence_refs+confidenceで接地することを実測する。apply fixtureでC02 verdict不在/hash不一致/FAILのfail-closed拒否、blueprint外の事実新規主張を--check-applyが拒否すること、出力がローカルのみ(network 0)であることを実測する。
- [x] サイト全域被覆fixtureで、discovered URLのin_scope/excluded分類(アフィリエイト/広告/外部SNS/トラッカー=excluded+reason・判定不能はexcluded)がfail-closedになること、full_siteモードでも瞬間負荷レバー(origin並列1・最小間隔2000ms)が緩まずper-run有界予算+cache/ledgerでmulti-run resumeし全in_scope URLへ到達すること、layout template hashによる同型ページ重複排除でscreenshot枚数が減ること、site coverage manifestのpendingが完全被覆と偽装されないことを実測する。
- [x] security観測fixtureで、cookie属性(Secure/HttpOnly/SameSite)・認証UI観測・CSP全文がfactとして採取され、security_design推測(OWASP観点)は受動観測のみを根拠とし侵入テスト/脆弱性スキャン/認証突破への言及・実行が0件であることを実測する。CWV fixtureでLCP/CLS/INP/TTFBが追加network 0・単一訪問scope_note付きで採取されること、compliance fixtureでprivacy/規約/特商法/cookieバナー・CMPの存在・URL・構成要約が採取されることを実測する。feature_map(C03 fact集約)とuser_journeys(C05 inference)が同一fixtureで混同されずevidence_refs+confidenceの有無で判別できることを実測する。

### 受入例
- 全13 visualカテゴリ、coverage、field gap、追加network 0、低負荷ledger、prompt anti-overfit、browser-render不在時のgap縮退のfixtureがGreenになる。

### 事前解決済み判断
- canvas/WebGL/closed shadow DOM等の非観測は失敗を隠さず理由付きgapにし、鍵画面gapはC9 FAILとする。

## 参照情報
- harness-coverage-spec (6 種別 × 二軸・kind 別パス)。
- 対象 component C01-C15。
- 後続 P07 (acceptance-criteria)。
