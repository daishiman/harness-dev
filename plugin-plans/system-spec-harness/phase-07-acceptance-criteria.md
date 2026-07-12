---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準 (AC) を build 後の受け入れとして判定する。purpose「システム構築に必要な仕様情報をヒアリングで漏れなく収集し1つの仕様書へまとめる」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが仕様収集の網羅性という purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と skill loop の criteria が確定している。
- purpose「システム構築仕様をヒアリングで漏れなく収集し仕様書へまとめる」を受入観点の正本 (`goal-spec.purpose`) として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証 (両方必要・相互代替不可)。
- 網羅性の観測方法: カテゴリ×プラットフォームのマトリクスに未収集セルが残っていないことを observe する (C01/C12 の outer criterion)。
- fail-closed: 判定不能・異常時に安全側 (拒否/上書き阻止) へ倒す性質 (C11 hook の受入観点)。

## 成果物
- 全 component の AC 判定結果 (PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C01: 6周超fixtureで5周目に未完了状態+next_questionが保存され、resume後にカテゴリ×canonical platform id 6種の全セルが確定/対象外理由付きで埋まっていると判定できる。
- [ ] C02/C13/C08: 対象target_id全件が公式publisher/host、versionまたはlast_updated、retrieved_at/latest_checked_at、参照元を持ち、C08の公式サイト再照合で現行版と判定できる。
- [ ] C03/C05: 生成された仕様書ドキュメントセットが章立て複数 Markdown+index の形式でマトリクス確定状態・設計知識反映・出典を含み、独立評価が合格と判定できる。
- [ ] C11: confirmed章Write/Edit、protected path/spec-state参照Bash、曖昧な動的Bashが阻まれ、正本writer=C01、C03/C11=read-only委譲で直接巻き戻しを拒否すると判定できる。
- [ ] C11: 非対象パス (仕様章以外) への Write|Edit と明らかなread-only Bashは exit0 で即通過し誤爆しない。
- [ ] C05 評価は /spec-compile (C10) 完了後に自動連鎖して起動する。
- [ ] 残り component の output_contract が満たされ受入テストが二値で PASS している。
- [ ] C01/C12/C03: U1-U9が値または明示N/A理由で確定し、具体意図/確定セル/生成章のgoal traceがdanglingなし。
- [ ] C01 R5/C02/C13: needs_guidanceから最新公式根拠付き2〜3案（無料/低コスト案を含む）を比較し、AI推奨理由/注意点/confidenceを提示するがユーザー確認前はconfirmedにしない。
- [ ] C04/C05: seed外knowledge candidateを扱え、全curated referenceがdeep knowledge contractを満たしpointer-only資産を拒否する。
- [ ] 全prompt: prompt-creator `verify-completeness.py`/`validate-prompt.py`と独立C1-C4 design reviewがPASSする。
- [ ] C14: knowledge profileのprecedence DAG/型則/root到達性、required-info profileの最低形状/domain被覆/block 0/coverage certificate、doctrine profileのconcern一意性/category全射/未承認例外0を判定できる。
- [ ] C01/C03: 知識案内 (R5-decision-guide) と章内知識反映 (R2-render) がC14の位相順 (上位概念→下位概念) に従って知識を消費していると判定できる (goal-spec C14)。
- [ ] C04/C03: 4 design concern authorityが1 concern 1正本で固定され、全categoryが必要concernへ写像され、未承認例外なしで上流指針として生成章へ反映される。
- [ ] C01: required-info最低形状・全domain被覆・missing_effect block 0を満たし、依存順とcoverage certificateが質問順/spec-stateへ反映される。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 6周超のサンプルヒアリング応答セット投入後、5周目のresume tokenを経てマトリクスの未収集セル0 + 対象外理由付与を判定でき、citation fixtureの非公式host/旧version/target欠落はそれぞれFAILになる。
- 満たさない例: lint/coverage が緑であることを根拠に AC を PASS 扱いする (品質ゲートと受入の混同) / 判定にスコアの中間値を許し二値にならない。

### 事前解決済み判断
- 分岐点: AC FAIL 時の戻し先 → 判断: P05 へ差し戻す (受入観点の再定義はしない・正本は goal-spec.purpose)。

## 参照情報
- `goal-spec.purpose` / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C14。
- 後続 P08 (refactoring)。
