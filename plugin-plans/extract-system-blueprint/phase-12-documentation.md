---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
プラグインの使い方と設計判断を文書化する。Part1/Part2の6タスク雛形に、visual formation全カテゴリの読み方、field gap/coverage、verbatimコピーfactとessence章(本質的問題JTBD/読者/価値提案/キーメッセージ/トーン/positioning)の読み方、tech_signals/named同定のレーン二層(シグナル=事実・命名=推測)とnonfunctional_baselineのobserved_scopeの読み方、低負荷取得、実名原則レンズprompt(C13 content/productレンズ含む)、ローカル品質verdict、任意のheadless Chrome(C15 browser-render・MCP非依存)によるrendered DOM/viewport screenshot取得と不在時(exit3=browser-unavailable)のobservation_gap縮退、自社適用レイヤ(C14 run-blueprint-apply)の使い方(自社コンテキスト入力→採用/回避/差別化のapply-recommendations・ローカルのみ)を明記する。加えてサイト全域被覆(full_siteモードの起動方法・per-run有界+multi-run resumeでの再開手順・scope分類の読み方=in_scope/excluded+reason)、feature_map(機能一覧)+user_journeys(推測ジャーニー)章の読み方、security_design章(OWASP観点・受動観測のみである限界の明記)、delivery_topology/CWV参考値章の読み方を記載する。

## 背景
プラグインは配布・再利用されるため、使い方 (install/概念/技術) と設計判断を残す必要がある。特に本プラグインの生成物は「事実」と「根拠+確度つき推測」を区別する schema を持つため、利用者 (人・AI) がその区別をどう読むかの説明が不可欠。中学生にも分かる 2 部構成 (Part1 概念 / Part2 技術) で書き、反映先 (README/lessons-learned/bundles.json/feedback_contract_ssot) を SSOT に固定することで、文書が散逸せず後続改善が追える。

## 前提条件
- P11 の evidence が記録済み。
- README / lessons-learned / bundles.json / feedback_contract_ssot の反映先が定まっている。
- install 手順 (marketplace/CLI/Desktop)・外部トークン不要 (MCP/Notion非依存)・任意のheadless Chrome導入 (browser-render用)・初回設定を記述できる。

## ドメイン知識
- 反映先 4 点の役割分担: README=利用者向け導入 / lessons-learned=改善知見 / bundles.json=装備一覧 / feedback_contract_ssot=評価基準 (散逸防止のため固定)。
- feedback_deploy との関係: 本 plugin は外部サービス連携 (MCP/Notion) を持たずローカル完結のため、利用者フィードバックの受け皿となる外部 DB は設けない (README には外部トークン不要・ローカル導入手順を含める)。
- 対象読者の床: Part1 は前提知識なし (中学生) で読める・Part2 は運用者向け技術詳細 (事実/推測確度スキーマの読み方を含む)。

## 成果物
- README + install/distribution 手順 + 概念/技術ドキュメント。
- lessons-learned / bundles.json / feedback_contract_ssot への反映。

## スコープ外
- 配布・PR の実行 (P13 の soft note 対象)。
- コード変更 (文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。

## 完了チェックリスト
- [x] 6 タスク雛形が埋まり、install 手順 (marketplace/CLI/Desktop) が非空で存在する。
- [x] 概念 (Part1) と技術 (Part2、事実/推測確度スキーマの読み方を含む) の中学生説明が非空で存在する。
- [x] lessons-learned / bundles.json / feedback_contract_ssot へ反映されている。
- [x] runbookにvisual formation field一覧/coverage/gap、content fact(verbatimコピー)とessence章の読み方・レンズ差替方法、静的観測(宣言CSS/DOM)中心の低負荷取得、実名Lens見出しと非模倣/非推薦guard、browser-render(headless Chrome)の起動と exit3(browser-unavailable)時のobservation_gap縮退、asset hash冪等、対象originへのRetry-Afterを記載する。
- [x] runbookにサイト全域被覆(full_site起動・scope分類の読み方・multi-run resume手順・瞬間負荷レバー不変)、feature_map/user_journeys章の読み方(fact集約とinferenceの区別)、security_design章の受動観測限界(侵入テスト/脆弱性スキャン非実施)、delivery_topology/CWV参考値(単一訪問scope_note)の読み方を記載する。

### 受入例
- README/runbookが13カテゴリ表、coverage/gapの読み方、inventory expert_lenses全件(現13名/組織)のLens見出し/guard、低負荷取得、browser-render(任意headless Chrome)の取得と不在時gap縮退を説明する。

### 事前解決済み判断
- 利用者向け概念説明と運用者向け技術契約を分け、DB ID/secretや一時download URLを文書へ直書きしない。

## 参照情報
- install/distribution 手順、feedback_contract_ssot、bundles.json。
- 対象は plugin 全体 (特定 component へ紐づかない)。
- 後続 P13 (release)。
