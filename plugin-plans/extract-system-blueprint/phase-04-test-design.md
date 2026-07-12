---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 完了
gate_type: tdd-red
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component (C01=run-extract-blueprint, C14=run-blueprint-apply) の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達 (Red) であることを確認する tdd-red gate。C02 (assign kind) は評価者責務のため loop criteria 対象外。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。汎用ゲートの言い換え (lint exit0 / 4 条件 PASS) に退化した criteria は purpose を一度も受入検証しないため、goal/checklist 語彙由来であることを設計時に担保する (`criteria_purpose_traceability` が機械検出する退化を未然に防ぐ)。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C01/C14 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約 (inner/outer 各 1 件以上・id/verify_by enum) を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点、outer=build 後の受入観点 (各 1 件以上が契約)。
- OUT1 の逆テスト: 生成blueprintから最小scaffold骨子を試導出し、visual formation全カテゴリ/coverage/field gapから色・文字(verbatimコピー)・box model・layout・asset・state・motion・responsive差分まで再形成できるか、essence章(本質的問題JTBD/想定読者/価値提案/キーメッセージ/トーン/positioning)から『何を・誰に・なぜ伝えるか』を復元できるか、原則レンズ主張の根拠、低負荷ledgerを確認する。
- Red = 実装前に criteria が未達であること (実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が goal/checklist の語彙を参照していること (汎用ゲートの言い換え退化を `check-spec-frontmatter.py` が機械検出)。
- C02 (assign kind) は FEEDBACK_LOOP_SKILL_KINDS (run/wrap/delegate) 対象外のため `feedback_contract.skip_reason` で明示し、本フェーズの test-design 対象に含めない (評価者としての合否は evaluator.threshold で担保する)。

## 成果物
- C01 の `feedback_contract.criteria` (inner=IN1 + outer=OUT1) と C14 の criteria (inner=IN1 + outer=OUT1) が inventory に確定した状態。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの設計・実行 (P06・kind 別観点はそちらで扱う)。
- 非 skill component の受入 (output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [x] C01 の criteria が purpose 由来で inner (IN1) + outer (OUT1) を各 1 件以上持つ (汎用ゲート言い換えに退化していない)。
- [x] C14 の criteria が purpose 由来で inner (IN1=doc-emit.py --check-apply exit0+C02 verdict事前検証+network 0) + outer (OUT1=自社コンテキスト接地・blueprint外の無根拠主張0・evidence_refs+confidenceで判断追跡可能) を持ち、apply-recommendationsがblueprintに無い事実を新規主張する敵対fixtureを--check-applyが拒否する設計になっている。
- [x] OUT1はvisual formationカテゴリ別fixture、field単位gap、verbatimコピーfact被覆とessence章明示、実名prompt guard、低負荷ledgerを逆テストする。rendering必須観測(viewport screenshot/rendered DOM/computed幾何)はC15 browser-render取得時のみfact・ブラウザ不在時はobservation_gap(browser-unavailable)へ縮退し静的観測で続行することを検証する(成果物はローカル完結・外部公開なし)。
- [x] persona-non-contamination の敵対テストを criteria/fixture として設計: lens由来の意見を妥当なfactレコード形式へ偽装した敵対例を1件以上含み、schema/C02がそれをfactとして受理せずinferenceへ落とすかFAILする。lens由来inferenceのconfidence.level=highは複数の直接evidenceがある場合のみ通す(confidence校正)。評価はpersona名の出現でなくfact/inference分離と根拠品質で行う(anti-overfit)。
- [x] 実装前は criteria が未達 (Red) であることが確認できる。

### 受入例
- color/gradient/border/font/SVG/state/motion/responsive等のfixture、field gap、名前だけではFAILするprompt fixture、browser-render不在時のgap縮退fixtureがRedで先に定義される。

### 事前解決済み判断
- 静的観測は宣言CSS/DOM中心で追加network 0、rendering必須観測はC15 browser-render取得時のみ(state操作はmax_interactions=5内)、対象originへの429は`Retry-After`を尊重する。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2 (criteria の purpose-traceability・test-first 導出)。
- `schemas/fact-inference-confidence.schema.json` / `schemas/system-blueprint.schema.json` / `EVALS.json` の reconstruction-rehearsal LLM-eval。
- 対象 component C01 (抽出本体)・C14 (自社適用)。
- 後続 P05 (implementation)。
