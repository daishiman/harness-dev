---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 完了
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02の設計をdesign-gateとして審査し、fact/inference/gap分離、C12→C09/C08→C03の安全DAG、C15 browser-render(MCP非依存headless Chrome)の取得/縮退能力、低負荷budget、local draft→C02品質verdictの因果鎖を実装前に止めるgateフェーズ。成果物はローカル完結で外部公開Stepを持たない。

## 背景
設計段階の欠陥を実装後に発見すると手戻りが大きい。特に本プラグインは C5 (認可外アクセス禁止) が fail-closed で機能することが不可欠であり、C08 hook と C09 script の認可分類述語が乖離していないかを実装前に検証する必要がある。提案者と承認者を分離 (proposer≠approver) することで、単一 skill への退化や sub-agent 4 分割の水増しといった設計の歪みも同時に検出する。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- elegant-review 4 条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みを参照できる。
- レビュアは提案者と別 context で評価する (構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4 を設計スコープ (inventory+envelope draft) に適用したもの (C1-C4 の定義は index `## ドメイン知識` 参照)。
- proposer≠approver: 設計した主体と承認する主体を context ごと分離する不変条件 (自己承認は無効)。
- 単一 skill 退化 = 事実抽出・推測・文書化・品質評価が 1 skill に畳まれ、事実/推測の明示区別責務が構造的に失われた状態 (本 plan では 4 sub-agent 分離の妥当性が判定対象)。

## 成果物
- design-gate の判定記録 (C1-C4 全 PASS / 差し戻し理由)。

## スコープ外
- 指摘の修正そのもの (P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計 (P04)・実装 (P05)。
- 機械 lint の実行 (P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [x] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [x] 単一 skill への退化が無く、C09/C08がC12へdepends_onし、C03がC09/C08へdepends_onする安全DAGがhandoffと1:1一致する。
- [x] C12はURL文字列だけでallowを推測せず根拠付きAuthzEvidenceと低負荷budgetを発行し、unknown/期限切れ/予算超過をfail-closedにする。
- [x] C03はWebFetchをSPA browserとして扱わず、C15 browser-render(headless Chrome)取得時のrendered factか明示gapを出し、C07がC01 draft→C02品質verdict(公開Stepなし)を強制する。
- [x] delta設計を審査済み: (a)瞬間負荷レバー非緩和、静的観測(宣言CSS/DOM)中心・主要element限定、(b)C08のfail-closed、(c)C11がvisual formation全カテゴリ/coverage/field gap/redaction/overlayを検査、(d)C03-C06/C13 promptに実名見出し+非模倣/非推薦+neutral synthesis、(d2)C13 content-intent契約(verbatimコピーfact入力→伝達意図/JTBD仮説のinference出力・C06 essence章統合・topology 12→13承認済)、(e)viewport screenshot/rendered DOM/computed幾何はC15 browser-render(MCP非依存)取得時のみfactで、ブラウザ不在時はobservation_gap(browser-unavailable)へ縮退し静的観測で続行する(成果物はローカル完結・外部公開なし・topology 14→15承認済)、(f)tech_signals/nonfunctional_baseline=C03/C09のfact(追加network 0・observed_scope明示)・named stack同定=C04のinference(signal factへのevidence_refs+confidence必須)のレーン二層化、(g)C14(run-blueprint-apply)がC02 PASS済(draft_hash一致)blueprintのみをfail-closedに消費しapply-recommendationsをローカルのみへ導出する(外部公開なし・対象origin非アクセス・blueprint本体非混入・doc-emit.py --check-apply決定論検査・topology 13→14承認済)、(h)R5被覆の深さ・広さ: C09のURL discovery→C12のscope分類(system関連=in_scope、アフィリエイト/広告/外部SNS/トラッカー=excluded+reason)がfail-closedで、crawl_profile full_siteモードでも瞬間負荷レバー(origin並列1・最小間隔2000ms・Retry-After・有界backoff)を一切緩めずper-run有界+cache/ledger/site coverage manifestでmulti-run resumeし、C03のfeature_map素材(fact)とC05のuser_journeys(inference)が明示区別され、C04のsecurity_design推測は受動観測のみ(侵入テスト・脆弱性スキャン・認証突破を行わない)である、が成立している。
- [x] 差し戻しが解消され後続フェーズへ進める状態になっている。

### 受入例
- 独立approverが低負荷、13カテゴリ無言欠落禁止、prompt guard、redaction、browser-render取得時fact/不在時gap縮退、ローカル完結(外部公開なし)を全てPASSと判定する。

### 事前解決済み判断
- browser-render取得画像のasset hash冪等、対象origin再取得なし、外部サービス非公開(ローカル完結)を設計不変条件とする。

## 参照情報
- P02 成果物 (`component-inventory.json` / `envelope-draft/plugin.json`)。
- `assign-plugin-plan-evaluator` (評価ロジックの正本・proposer≠approver)。
- 後続 P04 (test-design)。
