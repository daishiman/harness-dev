---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
README/RUNBOOK/CHANGELOGへ2-source設定、provider/scheduler設定、全量ledger、relation/harness graph、retry/waiver/redaction運用を追記する。

## 背景
プラグインは配布・再利用されるため、使い方 (install/概念/技術) と設計判断を残す必要がある。本計画は既存 plugin への改善であるため、既存 README を上書きせず追記する形で反映先を SSOT に固定し、散逸を防ぐ。

## 前提条件
- P11 の evidence が記録済み。
- 既存 README / lessons-learned / bundles.json / feedback_contract_ssot の反映先が定まっている。
- YouTube 取得手段の技術詳細 (未確定・open_questions) を除いた利用手順を記述できる。

## ドメイン知識
- 反映先 4 点の役割分担: README=利用者向け導入 / lessons-learned=改善知見 / bundles.json=装備一覧 / feedback_contract_ssot=評価基準 (散逸防止のため固定)。
- feedback_deploy との関係: 利用者フィードバックの受け皿は Notion で、DB の論理キーは plan が宣言・実 DB ID は設置先の `.notion-config.json` が供給する二層 (README にはこの初回設定手順を含める)。
- 対象読者の床: Part1 は前提知識なし (中学生) で読める・Part2 は運用者向け技術詳細。

## 成果物
- README/RUNBOOK/CHANGELOGへのadditive追記とplugin-composition/package-contract/EVALSのsurface parity説明。
- 概念/技術ドキュメント (Part1/Part2)。
- lessons-learned / feedback_contract_ssotへの反映。distributable:falseのためbundlesは非登録維持を検証する。

## スコープ外
- 配布・PR の実行 (P13 の soft note 対象)。
- コード変更 (文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] 6 タスク雛形が埋まり、install 手順 (既存手順への追記) が非空で存在する。
- [ ] 概念 (Part1) と技術 (Part2) の中学生説明が非空で存在する。
- [ ] lessons/feedback SSOTへ反映され、bundles/marketplace非登録が維持されている。

### 受入例
READMEにprimary/pending source、scheduler、retry、waiver、graph query、redaction手順がある。

### 事前解決済み判断
distributable:falseを維持しbundles/marketplaceへ登録しない。

## 参照情報
- 既存 README、install/distribution 手順、feedback_contract_ssot、bundles.json。
- 対象は plugin 全体 (特定 component へ紐づかない)。
- 後続 P13 (release)。
