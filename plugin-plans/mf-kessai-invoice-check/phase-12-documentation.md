---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: [C01, C03]
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
C01 (`run-mf-invoice-report` skill) と C03 (`/run-mf-invoice-report` slash-command) の使い方と設計判断を文書化する。中学生にも分かる説明 (Part1 概念 + Part2 技術) を含む 6 タスク雛形で、反映先を feedback_contract_ssot / lessons-learned / bundles.json に固定し、distribution/install 手順を明記する。

## 背景
本改善は既存プラグインへの component 追加であるため、利用者 (経理担当) が新しい比較レポート機能 (2 営業日目以降の再実行・4 イレギュラー分類コメント) をどう使うかを README/概念文書で明確化する必要がある。反映先 (README=利用者向け導入/lessons-learned=改善知見/bundles.json=装備一覧/feedback_contract_ssot=評価基準) を SSOT に固定することで文書が散逸しない。

## 前提条件
- P11 の evidence が記録済み。
- README / lessons-learned / bundles.json / feedback_contract_ssot の反映先が定まっている。
- install 手順・Notion DB キー (`.notion-config.json`/`.mf-kessai-config.json`) の初回設定手順を記述できる。

## ドメイン知識
反映先 4 点の役割分担・feedback_deploy との関係は index を参照。本フェーズ固有の差分: README には「2 営業日目以降に何度でも再実行してよい (冪等上書き)」という運用ルールと、4 イレギュラー分類コメントの読み方 (年契約周期/年→月切替/トライアル完了/契約終了/真の発行漏れ) を経理担当向けに平易に説明する。

## 成果物
- README + install/distribution 手順 + 概念/技術ドキュメント (C01/C03 対象)。
- lessons-learned / bundles.json / feedback_contract_ssot への反映。

## スコープ外
- 配布・PR の実行 (P13 の soft note 対象)。
- コード変更 (文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] 6 タスク雛形が埋まり、install 手順 (marketplace/CLI/Desktop) が非空で存在する。
- [ ] 概念 (Part1・4 イレギュラー分類の読み方) と技術 (Part2・C01/C03 の運用) の中学生説明が非空で存在する。
- [ ] lessons-learned / bundles.json / feedback_contract_ssot へ反映されている。

## 参照情報
- install/distribution 手順、feedback_contract_ssot、bundles.json。
- 対象 component C01/C03。後続 P13 (release)。
