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
改善の使い方(何が変わったか)と設計判断(なぜMF実績を第一級の真実に格上げしたか)を文書化する。反映先を README / lessons-learned / bundles.json / feedback_contract_ssot に固定する。

## 背景
既存プラグインへの改善であるため、利用者が「レポートの見え方が何故変わったか(実額常時表示・金額差フラグ・D1/D2/D3 の正常事情判定)」を理解できる説明が必要。反映先を SSOT に固定することで、文書が散逸せず後続改善が追える。

## 前提条件
- P11 の evidence が記録済み。
- README / lessons-learned / bundles.json / feedback_contract_ssot の反映先が定まっている。
- 既存 version 0.3.0 の改善説明として、判定権威の移行・fetch fidelity監査の新設・既存8列の金額欄を MF実額へ意味変更する点を記述できる。

## ドメイン知識
- 反映先の役割分担: README=利用者向け導入・変更点説明 / lessons-learned=改善知見(単一設計偏り→根治の教訓) / bundles.json=装備一覧 / feedback_contract_ssot=評価基準。
- feedback_deploy との関係: 改善要望の受け皿は既存 `/run-skill-feedback mf-kessai-invoice-check` を維持する(README にこの経路を明記)。
- 対象読者の床: 利用者向け説明は「なぜ今月金額が空白でなくなったか」等、症状解消の観点で書く。
- 素人可読性: 非技術読者(経理担当)が README のみを読んで症状①〜⑦の解消を理解できるよう、用語を平易化する(例:「実額=MFが実際に発行した金額」「fidelity監査=データ取りこぼしが無いかの機械チェック」)。
- 症状⑥(金額相違)の再発防止はスコープ外だが放置しない: 根本原因はシート側の現行単価の陳腐化(値上げ後の単価未更新等)であり、本改善は金額差フラグ/コメントによる**差分ログの開示**に留める。シート側の値更新還流(既存 `lib/notion_sheet_writeback.py` 等)は本 plan のスコープ外だが、差分ログが残るため見落とし放置にはならない。

## 成果物
- README への変更点(D1/D2/D3・実額常時表示・既存8列の比較/コメント欄での金額差フラグ・fetch fidelity診断コマンド)追記。
- lessons-learned / bundles.json / feedback_contract_ssot への反映。

## スコープ外
- 配布・PR の実行(P13 の soft note 対象)。
- コード変更(文書化フェーズは実装へ触れない・不備発見時は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] README に version 0.3.0 の改善内容(判定権威の移行・D1/D2/D3・fetch fidelity診断・既存8列互換)が非空で記述されている。
- [ ] lessons-learned に「契約起点→MF実績起点への根治」の教訓が反映されている。
- [ ] bundles.json / feedback_contract_ssot への反映が確認できる。
- [ ] 非技術読者(経理)が README のみから症状①〜⑦の解消を説明できる(human verify・用語平易化済み)。
- [ ] 症状⑥再発防止(シート単価陳腐化)はスコープ外である旨と、差分ログ開示により放置しない旨が明記されている。
- [ ] Notion DB は新物理列を追加せず既存8列を維持し、`先月の金額`/`今月の金額` を MF実額として扱い、金額差フラグ/残置理由は `先月と今月の比較`/`コメント` に出す旨が明記されている(C04整合)。

## 参照情報
- README(`plugins/mf-kessai-invoice-check/README.md`)、feedback_contract_ssot、bundles.json。
- 対象は plugin 全体(特定 component へ紐づかない)。
- 後続 P13(release)。
