---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
「参考システムの公開URLを認可・低負荷budget内で調査し、観測fact・根拠つきinference・欠測を分離したblueprintをローカルへ生成する(外部サービス公開なし・ローカル完結)」という構想を目的ドリブンに要件化する。独立品質verdict PASSはlocal draftの完成扱いで、外部公開Stepは持たない。画面再形成情報はvisual formation全カテゴリを対象にし、静的に観測できる範囲(宣言色/DOM構造/layout宣言/font token/a11y semantic)はfact、rendering必須の実測(viewport screenshot/computed幾何/interaction state/motion/responsive実測)は任意のローカルheadless Chrome(browser-render・MCP非依存)取得時のみfact・不在時はobservation_gapとし、各fieldを観測値または理由付きgapにして無言欠落を許さない。成果物は参考/学習目的限定でローカルのみへ残す。C03-C06/C13の著名エンジニア原則レンズは実名prompt見出しを持つが、本人の模倣/承認主張をせずfactへ混入させない。加えて被覆の深さ・広さ(R5)として、エントリURLから連なるsystem関連URL群のサイト全域被覆(in_scope/excluded分類・fail-closed)、各画面の機能アフォーダンスfact(feature_map素材)とユーザージャーニー推測、security観測fact(受動観測のみ)とセキュリティ設計推測、配信構成推測+CWV参考実測fact、コンプライアンス周辺表面factを要件化する。

## 背景
現状は対象URLをブラウザで開き目視確認し検証ツール(F12)でHTML/CSS/通信を確認する手作業3ステップで、分析・仕様書作成・自社構築の前段作業に週2.5回×平均90分規模のコストがかかっている。深層課題(D2採択)は「URL解析結果から自社実装の雛形・設計ドキュメントを即生成し自社構築の着手を速くする」ことであり、単なるURLスクレイピングとの差別化は事実と根拠つき推測を明示区別しAI入力として機能する構造化文書を生成する点にある。本フェーズはこの目的ドリブン要件を `goal-spec.json` として固定し、以降の全フェーズが参照する不変のアンカーにする。

## 前提条件
- プラグイン構想1件 (自然文 + skill-intake の url-system-blueprint-extract intake) が入力として与えられている。
- 汎用の `run-goal-elicit` (harness-creator) が利用可能で、purpose/background/goal/checklist を `goal-spec.schema.json` で抽出できる (再実装しない)。
- このフェーズは特定 component へ紐づかない (責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- 事実 (fact) = C09(fetch-snapshot.py=stdlib静的observer)の`static-observation.json`とC03で実測しprovenanceを持つUI/宣言遷移/静的DOM/tech_signals/visual formation。rendering必須のfact(実行後DOM/viewport screenshot/computed幾何/state)は任意のheadless Chrome(C15 browser-render.py)取得時のみ加わる。visual formationはgeometry/layout/paint/typography/media/effects/pseudo-elements/state/motion/responsive/a11y/tokensを含み、原則レンズ解釈を含めない。
- 推測 (inference) = 表面から直接観測できないバックエンド機構・設計意図を、観測事実を根拠に確度つきで記録したもの (事実と出力上で明示区別する)。
- 欠測 (observation_gap) = 取得不能・認可遮断・budget停止で観測できなかった状態。inferenceへ昇格せず`not_observed|blocked`と理由を持つ。
- goal-spec は全 goal-seek 周回で不変のアンカー (target_plugin_slug/plan_dir を含め以降のフェーズが書き換えない)。
- その他の plan 全体用語 (component_kind/2軸直交等) は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist C1-C9/constraints/open_questions/source_intake)。
- target_plugin_slug=`extract-system-blueprint` と plan_dir=`plugin-plans/extract-system-blueprint` の確定値。

## スコープ外
- component 分解・envelope 設計 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [x] `goal-spec.json` が purpose を非空で保持し、受入観点 (checklist C1-C9) が purpose 語彙から導出されている。
- [x] C8として並列数1・cache・request/byte/page/interaction budget・Retry-After・有界backoff・停止条件が明文化され、再試行でbudgetをリセットしない。
- [x] target_plugin_slug が ASCII kebab (`extract-system-blueprint`) で確定し以降のフェーズがそれを参照できる。
- [x] 「成果物は参考/学習目的限定」の制約が constraints へ明文化され、C11 doc-emit の利用目的限定注記へ紐づいている (スクリーンショットにも適用)。
- [x] C9として主要画面のvisual formation全カテゴリ、coverage manifest、field単位gap、ローカル注釈asset(layout.json+overlay.svgのテキスト演算)が明文化され、既定budget非緩和が宣言されている。viewport screenshot/rendered DOMは任意のheadless Chrome(browser-render)取得時のみfact・不在時はobservation_gapとし、screenshot専用budgetは発行しない。
- [x] C03-C06/C13のstructured expert_lenses/prompt_contract、実名見出し、cross-lens conflicts、neutral synthesis、非模倣/非推薦guard、evidence_refs+confidenceが明文化されている。
- [x] C1として機能アフォーダンスfact(feature_map素材)・security観測fact(cookie属性/認証UI/CSP全文)・CWV参考実測fact(単一訪問scope_note付き)・compliance表面fact(privacy/規約/特商法/CMP)・site URL台帳fact(discovered/in_scope/excluded+reason)が明文化されている。
- [x] サイト全域被覆(full_siteモード)がscope分類(system関連=in_scope、アフィリエイト/広告/外部SNS/トラッカー=excluded+reason)のfail-closed判定と、瞬間負荷レバー不変・per-run有界+multi-run resumeで要件化され、security観測は受動観測のみ(侵入テスト・脆弱性スキャン・認証突破を行わない)と明記されている。
- [x] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。

### 受入例
- `goal-spec.json` がC1-C9を持ち、C9はvisual formation 13カテゴリ・coverage・field単位gap・ローカル可視化(layout.json+overlay.svg・browser-render取得時のrendered/screenshot)を明記する。C2はinventory expert_lenses全件(現13名/組織)の実名原則レンズと非模倣/非推薦guardを明記する(数はroundで増減しうるため正本=inventory)。

### 事前解決済み判断
- 対象originは並列1/既定budget非緩和、成果物はローカル完結(外部公開なし)、ロスター構造化正本はinventory C03-C06/C13とする。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `plugins/skill-intake/output/url-system-blueprint-extract/intake.json` (design materials の一次資料)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02 (この goal-spec を component 分解の入力とする)。
