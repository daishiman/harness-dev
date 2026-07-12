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
再配置後のプラグインの使い方と設計判断を文書化する。中学生にも分かる説明(Part1 概念 + Part2 技術)に加え、責務再均衡の設計意図(なぜ 11 agent を薄化したか・resource-map.yaml の読み方・今後 agent へ手続き知識を書き足したくなった時の判断基準=no-split threshold)を明記する。反映先を feedback_contract_ssot / lessons-learned / bundles.json に固定する。

## 背景
プラグインは配布・再利用されるため、使い方(install/概念/技術)と設計判断を残す必要がある。責務再均衡は「なぜこの置き場所になったか」という設計意図が失われると将来また同じ過重が再発する(agent へ procedural knowledge を書き戻してしまう)ため、no-split threshold の判断基準そのものを文書として残し、将来の変更者が同じ基準で判断できるようにする。

## 前提条件
- P11 の evidence が記録済み。
- README / lessons-learned / bundles.json / feedback_contract_ssot の反映先が定まっている。
- 11 thin-adapter agent の rebalance_rationale(実測行数根拠)が P02 で確定済み。

## ドメイン知識
- 反映先 4 点の役割分担: README=利用者向け導入 / lessons-learned=改善知見(責務再均衡の設計意図を含む) / bundles.json=装備一覧(24 component) / feedback_contract_ssot=評価基準。
- 再発防止の明記: no-split threshold(分離コスト<分離便益)の判断基準を README または references/ に明記し、将来 agent へ procedural knowledge を書き足す際の判断材料として残す。
- 対象読者の床: Part1 は前提知識なし(中学生)で読める・Part2 は運用者向け技術詳細(responsibility rebalance の設計判断・resource-map.yaml の読み方)。

## 成果物
- README + 概念/技術ドキュメント(責務再均衡の設計意図・no-split threshold 判断基準・resource-map.yaml の読み方)。
- lessons-learned / bundles.json / feedback_contract_ssot への反映。

## スコープ外
- 配布・PR の実行(P13 の soft note 対象)。
- コード変更(文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] 概念(Part1)と技術(Part2・責務再均衡の設計意図/no-split threshold 判断基準/resource-map.yaml の読み方)の中学生説明が非空で存在する。
- [ ] lessons-learned / bundles.json / feedback_contract_ssot へ反映されている。
- [ ] 将来の変更者が no-split threshold と同じ基準で判断できる形で判断根拠が文書化されている。

## 参照情報
- install/distribution 手順、feedback_contract_ssot、bundles.json。
- 対象は plugin 全体(特定 component へ紐づかない)。
- 後続 P13(release)。
