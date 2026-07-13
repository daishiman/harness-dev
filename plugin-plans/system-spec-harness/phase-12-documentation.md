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
プラグインの使い方と設計判断を文書化する。中学生にも分かる Part1 概念説明と運用者向け Part2 技術詳細を含む 6 タスク雛形で、反映先を feedback_contract_ssot / lessons-learned / bundles.json に固定し、distribution/install の可用状態と手順を明記する。

## 背景
プラグインは再利用されるため、使い方 (install/概念/技術) と設計判断 (skill-intake 非再利用/出力形式/最新ドキュメント取得手段/command 採否) を残す必要がある。Part1は中学生にも分かる概念説明、Part2は運用者向け技術詳細とし、反映先 (README/lessons-learned/bundles.json/feedback_contract_ssot) を SSOT に固定することで、文書が散逸せず後続改善が追える。distributable:true は GAP-DISTRIBUTION-DECISION の resolution として確定済 (commit 00cf8f7・marketplace + xl-skills-full bundle 登録済) のため、marketplace 導入は AVAILABLE として記載する。

## 前提条件
- P11 の evidence が記録済み。
- README / lessons-learned / bundles.json / feedback_contract_ssot の反映先が定まっている。
- install surface ごとの状態 (`available`/`not-available`/`approval-pending`) と、利用可能なlocal/dev導入手順・必要トークン・初回設定を記述できる。

## ドメイン知識
- 反映先 4 点の役割分担: README=利用者向け導入 / lessons-learned=改善知見 / bundles.json=装備一覧 / feedback_contract_ssot=評価基準 (散逸防止のため固定)。
- feedback_deploy との関係: 利用者フィードバックの受け皿は Notion で、DB の論理キーは plan が宣言・実 DB ID は設置先の `.notion-config.json` が供給する二層 (README にはこの初回設定手順を含める)。
- 対象読者の床: Part1 は前提知識なし (中学生) で読める・Part2 は運用者向け技術詳細。
- Part1は「目的を先に決める」「迷ったらAIが根拠付き候補を案内する」「知識一覧は例で増やせる」を専門語なしで説明する。Part2はfoundation/decision/knowledge/prompt gateの契約と再現コマンドを記す。

## 成果物
- README + surface別install/distribution状態とlocal/dev導入手順 + 概念/技術ドキュメント。
- lessons-learned / bundles.json / feedback_contract_ssot への反映。

## スコープ外
- 配布・PR の実行 (P13 の soft note 対象)。
- コード変更 (文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] 6 タスク雛形が埋まり、local/dev導入手順が非空で存在する。marketplace/CLI/Desktopは状態を明示し、未承認surfaceは`NOT_AVAILABLE`または`approval-pending`+理由を記録する。
- [ ] Part1の中学生向け概念説明と、Part2の運用者向け技術詳細が非空で存在する。
- [ ] AI推奨は自動確定でないこと、無料案が不適合なら理由付きで低コスト案を選ぶこと、reference promotion条件が明記されている。
- [ ] lessons-learned / bundles.json / feedback_contract_ssot へ反映されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: README にlocal/dev導入とfeedback受け皿の初回設定があり、marketplace 導入手順が distributable:true 確定 (GAP-DISTRIBUTION-DECISION resolved) を反映して AVAILABLE として記載され、Part1は前提知識なし、Part2は運用者が再現可能な技術詳細になっている。
- 満たさない例: Part1 (概念) が専門用語の羅列で中学生に読めない / 設計判断が README へ複製され phase-02 の正本とドリフトする。

### 事前解決済み判断
- 分岐点: phase-02 の設計判断一式の文書化先 → 判断: 正本は phase-02 ドメイン知識とし README からは参照する (二重記述しない)。

## 参照情報
- install/distribution 手順、feedback_contract_ssot、bundles.json。
- 対象は plugin 全体 (特定 component へ紐づかない)。
- 後続 P13 (release)。
