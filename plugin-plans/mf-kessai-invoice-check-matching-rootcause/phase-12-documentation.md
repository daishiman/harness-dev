---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: [C07]
applicability:
  applicable: true
  reason: 
---

# P12 — documentation (文書)

## 目的
確定6要因根治 (収集拡張・R1決定論化・NEW/取消/代理店分類・collapse保全・MF顧客ID結合) の仕様変更を、既存プラグイン doc (README/skill doc) へ反映し、運用者が MF顧客ID backfill 運用や偽発行漏れ0件の期待挙動を理解できる状態にする。

## 背景
旧「ドキュメント 6 タスク」を keep+replace し、反映先を `feedback_contract_ssot.py`/`lessons-learned`/`bundles.json` へ写像する (aiworkflow 連携 DROP、phase-lifecycle.md §7 P12行)。本 plan 固有の反映対象は C07 (run-mf-invoice-report skill) のみで、C01-C06 (script/sub-agent) 自体は doc 更新の直接対象を持たない (README/skill-level doc は親 skill C07 が集約する)。

## 前提条件
C07 の `required_file_edits` (R1-collect.md/R2-classify.md の配線更新) が確定済み。名寄せドリフト耐性の恒久根拠は C02 の MF顧客ID(請求確認シート MF顧客ID列)であり、個社会社名のコードハードコードは禁止(C14)。alias JSON を運用データ資産として使う場合はコードハードコードの代替でなく C02 未解決社の補助に限定する(幻の `mfk_name_aliases.json` を恒久根拠として要件化しない)。

## ドメイン知識
中学生説明 Part1 (概念) + Part2 (技術) の 6 タスク雛形は keep するが、本 plan 固有の追加観点として「MF顧客ID未設定の取引先は請求確認シートの MF顧客ID列(C02 backfill)へ登録することで名前ドリフトに依らず境界解決できる。個社名をコードへ書かない」運用手順の明記を要件化する。distribution/install 手順は既存プラグイン更新のため新規セットアップ不要である。

## 成果物
(1) README/skill doc (run-mf-invoice-report) への 6要因根治 (収集status拡張・R1決定論化で今月金額欠落0・MF顧客ID運用・要マスタ登録可視化) の説明追記。(2) MF顧客ID登録運用手順 (個社名ハードコード禁止) の明記。(3) 既存プラグイン更新のため新規セットアップ手順は不要である旨の宣言。

## スコープ外
実 doc 編集の実行は L4 build (`run-skill-create`) へ委譲する。本フェーズは documentation 要件の確定に留まる。

## 完了チェックリスト
- [ ] C07 の doc 反映要件 (収集status拡張・R1決定論化で今月金額欠落0・MF顧客ID運用・要マスタ登録可視化の説明) が明記されている
- [ ] MF顧客ID登録の運用者向け手順 (請求確認シート MF顧客ID列・個社名ハードコード禁止) が明記されている
- [ ] 6 タスク雛形の反映先 (`feedback_contract_ssot.py`/`lessons-learned`/`bundles.json`) が既存プラグイン更新の枠内で整合している

## 参照情報
component-inventory.json C07 / phase-lifecycle.md §8 P12 セル / 既存 `plugins/mf-kessai-invoice-check/` README
