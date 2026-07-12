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
量産パイプライン (intake→plan→build→改善) の使い方と設計判断を文書化する。中学生にも分かる説明 (Part1 概念 + Part2 技術) を含む 6 タスク雛形で、反映先を `pipeline-boundary-contract.md` (新設 SSOT) / harness-creator README / lessons-learned / feedback_contract_ssot に固定する。

## 背景
harness-creator/plugin-dev-planner はいずれも `distributable:false` (repo-bundled・marketplace 非掲載) だが、社内利用者が E1/E2/E3 の機械契約 (intake_json 配線・routes[] 消費・改善成果物受理) を正しく使うには、README の 6 ステップ手順 (harness-creator README:52-85) を更新し、パイプライン全体像を一元化した新設リファレンス `pipeline-boundary-contract.md` へ集約する必要がある。中学生にも分かる 2 部構成 (Part1 概念 / Part2 技術) で書き、反映先を SSOT に固定することで文書が散逸せず後続改善が追える。

## 前提条件
- P11 の evidence が記録済み。
- harness-creator README / `pipeline-boundary-contract.md` / lessons-learned / feedback_contract_ssot の反映先が定まっている。
- 両 plugin とも `distributable:false` のため marketplace 配布手順は対象外。install は repo-bundled 前提 (社内 clone/symlink 経路) で記述する。

## ドメイン知識
- 反映先の役割分担: harness-creator README=利用者向け 6 ステップ導入更新 / `pipeline-boundary-contract.md`=E1/E2/E3 producer/consumer/gate/provenance 対応表の一元 SSOT / lessons-learned=改善知見 / feedback_contract_ssot=評価基準 (散逸防止のため固定)。
- distributable:false の含意: marketplace 掲載手順は書かない。install 手順は repo-bundled 前提 (clone 済み repo 内での利用) のみ記述する。
- 対象読者の床: Part1 は前提知識なし (中学生) で読める・Part2 は運用者向け技術詳細 (routes[]/provenance chain/fail-closed hook の技術説明)。

## 成果物
- harness-creator README 更新 (6 ステップ→機械契約反映後の手順)。
- `plugins/harness-creator/references/pipeline-boundary-contract.md` (新設・E1/E2/E3 対応表・概念/技術 2 部構成)。
- lessons-learned / feedback_contract_ssot への反映。

## スコープ外
- 配布・PR の実行 (P13 の soft note 対象)。
- コード変更 (文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。
- marketplace 配布手順の記述 (両 plugin とも distributable:false のため対象外)。

## 完了チェックリスト
- [ ] 6 タスク雛形が埋まり、repo-bundled 前提の利用手順が非空で存在する (marketplace 手順は明示的に対象外と記載)。
- [ ] 概念 (Part1) と技術 (Part2) の中学生説明が `pipeline-boundary-contract.md` に非空で存在する。
- [ ] lessons-learned / feedback_contract_ssot へ反映されている。

## 参照情報
- `plugins/harness-creator/references/pipeline-boundary-contract.md` (新設)・harness-creator README・feedback_contract_ssot。
- 対象は plugin 全体 (特定 component へ紐づかない)。
- 後続 P13 (release)。
