---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 完了
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的
機械品質5要素に加え、認可済みfixture URLのE2E runtime evidenceをMarkdownへ集約し、goal-spec checklist C1-C9を再現可能に証明するevidence gate。

## 背景
UBM 固有の『自プラグイン自身の GUI ランタイム証跡スクリーンショット』は本 plugin 成果物が Markdown/CLI 主体で GUI ランタイムを持たないため写像できず DROP し、再現可能な Markdown evidence 5 要素へ写像する。**ただしこれは『分析対象システムのレイアウト/browser-render 取得時のスクリーンショット (C9・製品成果物)』とは別物**であり、後者は evidence にその hash・provenance・browser-render 取得時fact/ブラウザ不在時 observation_gap(browser-unavailable) 化・低負荷budget遵守を含めて記録する (自プラグインの視覚証跡は不要=Markdown、対象システムの視覚成果物は必要=C9)。第三者が受入充足 (事実/推測の明示区別・5種Mermaid・ローカル出力・認可外アクセス防止・画面レイアウト/browser-render取得時スクショ) を再現・確認できる形で記録することが evidence gate の目的で、DROP 読替の正本は phase-lifecycle.md §7。

## 前提条件
- P10 の final-gate を通過している。
- P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す (GUI スクショに依存しない)。

## ドメイン知識
- 再現可能性の要件: 第三者が evidence 記載のコマンド/入力URL (認可範囲内のもの) を再実行して同じ合否へ到達できること (ログ貼付だけでは不足)。
- DROP 読替の正本は `phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence 5 要素)。他の plan 全体用語は index `## ドメイン知識` 参照。

## 成果物
- 機械品質5要素に、AuthzEvidence/deny matrix、snapshot hash、fact/inference/gap schema、5図、visual formationカテゴリ別coverage/field gap、layout/overlay asset hash(browser-render取得時のrendered/screenshot hash含む)、prompt contract、request ledger、C02 verdict(ローカル品質)を加えたMarkdown検証記録。
- site coverage manifest(discovered/extracted/pending/excluded+reason)、security観測記録(cookie属性/認証UI/CSP・受動観測のみ)、CWV参考値(scope_note付き)、compliance表面記録(privacy/規約/特商法/CMP)を加えたR5被覆記録。

## スコープ外
- 新規の検証実施 (P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化 (P12)。

## 完了チェックリスト
- [x] evidence 5 要素が全て Markdown に記録されている。
- [x] 認可済みfixture URL、snapshot/draft hash、AuthzEvidence、deny matrix、request ledger、fact/inference/gap、5図、visual formation coverage/field gap、verbatimコピーfactとessence章(本質的問題JTBD/読者/価値提案/キーメッセージ/トーン/positioning)の記録、tech_signals/nonfunctional_baseline(observed_scope付き)とnamed同定のevidence接地、(自社コンテキスト提供時)apply-recommendationsのdoc-emit.py --check-apply exit0記録、layout/overlay asset hash(browser-render取得時のrendered/screenshot hash含む)、prompt guard、C02 verdict(ローカル品質)が揃う。
- [x] site coverage manifest(discovered/extracted/pending/excluded+reason)がfull_siteモードの到達状況を無言欠落なく示し、security観測記録が受動観測のみ(侵入テスト/脆弱性スキャン非実行)であることを明記し、CWV参考値(scope_note付き)とcompliance表面記録(privacy/規約/特商法/CMPの存在・URL・構成要約)が揃う。
- [x] 第三者が記録から受入充足 (C1-C9) を再現でき、secret/個人情報/対象側の機微な応答本文・スクリーンショット内の機微はredactされている。

### 受入例
- Markdown evidenceからsnapshot/draft hash、13カテゴリcoverage、field gap、request ledger、prompt guard、layout/overlay(browser-render取得時のrendered/screenshot含む) asset hashを第三者が追跡できる。

### 事前解決済み判断
- 自plugin GUI証跡は不要だが対象画面visual成果物(browser-render取得時のscreenshot/rendered)のhash/provenanceは必要とし、未redact画像は証跡へ残さない(成果物はローカル完結・外部公開URLを持たない)。

## 参照情報
- `references/phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence の DROP 読替表)。
- 機械品質5要素 + runtime acceptance evidence inventory。
- 後続 P12 (documentation)。
