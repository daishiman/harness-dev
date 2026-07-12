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
プラグインの使い方と設計判断を文書化する。中学生にも分かる説明 (Part1 概念 + Part2 技術) を含む 6 タスク雛形で、反映先を feedback_contract_ssot / lessons-learned / bundles.json に固定し、distribution/install 手順を明記する。

## 背景
プラグインは配布・再利用されるため、使い方 (install/概念/技術) と設計判断を残す必要がある。中学生にも分かる 2 部構成 (Part1 概念 / Part2 技術) で書き、反映先 (README/lessons-learned/bundles.json/feedback_contract_ssot) を SSOT に固定することで、文書が散逸せず後続改善が追える。

## 前提条件
- P11 の evidence が記録済み。
- README / lessons-learned / bundles.json / feedback_contract_ssot の反映先が定まっている。
- install 手順 (marketplace/CLI/Desktop)・必要トークン・初回設定を記述できる。

## ドメイン知識
- 反映先 4 点の役割分担: README=利用者向け導入 / lessons-learned=改善知見 / bundles.json=装備一覧 / feedback_contract_ssot=評価基準 (散逸防止のため固定)。
- feedback_deploy との関係: 利用者フィードバックの受け皿は Notion で、DB の論理キーは plan が宣言・実 DB ID は設置先の `.notion-config.json` が供給する二層 (README にはこの初回設定手順を含める)。
- 対象読者の床: Part1 は前提知識なし (中学生) で読める・Part2 は運用者向け技術詳細。

## 成果物
- README + install/distribution 手順 + 概念/技術ドキュメント。
- lessons-learned / bundles.json / feedback_contract_ssot への反映。

## スコープ外
- 配布・PR の実行 (P13 の soft note 対象)。
- コード変更 (文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] 6 タスク雛形が埋まり、install 手順 (marketplace/CLI/Desktop) が非空で存在する。
- [ ] 概念 (Part1) と技術 (Part2) の中学生説明が非空で存在する。
- [ ] lessons-learned / bundles.json / feedback_contract_ssot へ反映されている。

## 参照情報
- install/distribution 手順、feedback_contract_ssot、bundles.json。
- 対象は plugin 全体 (特定 component へ紐づかない)。
- 後続 P13 (release)。
