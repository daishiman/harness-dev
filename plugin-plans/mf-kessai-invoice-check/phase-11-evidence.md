---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: [C01, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的
UBM のスクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。C01 (report skill)・C05 (分類エンジン)・C06 (冪等 sink) が受入を満たしたことを再現可能な形で記録する。

## 背景
本ドメイン (CLI/プラグイン・Notion レポート上書き) は GUI ランタイムを持たないため、UBM 固有のスクリーンショット検証を DROP し、第三者が受入充足を再現・確認できる Markdown evidence 5 要素へ写像する。DROP 読替の正本は phase-lifecycle.md §7。

## 前提条件
- P10 の final-gate を通過している。
- C01/C05/C06 の P0 lint / schema parity / build-trace / content-review / harness の各結果が取得可能。
- evidence は Markdown で残す (GUI スクショに依存しない)。

## ドメイン知識
再現可能性の要件・DROP 読替の正本は index/`references/phase-lifecycle.md` §7 を参照。本フェーズ固有の差分: C05 の evidence は分類テスト (年契約周期/年→月切替/トライアル完了/契約終了/真の漏れ) の各分岐を通したテストログを含める。C06 の evidence は (1) 指定見出し (`report_toggle_block`) に紐づく既存 report DB を確認し、トグル配下 DB (`db_location=in-block`)・プレーン見出し2直下 DB (`under-heading`)・ページ直下既存 DB (`page`)・未存在時の新規作成 (`page-created`) の各解決経路が fake-store で再現される観測ログ、(2) 同月内の upsert 主キー {対象月×取引先×商品} による create/update/skip 内訳と 2 回連続投入での主キー衝突ゼロ (重複行 0)、別月/以前 run 行の非破壊保持 (`deleted=0`) 観測ログを含める。C01 の evidence はその単一恒久 DB/月内冪等の結果を利用した最終レポートの整合観測ログを含める。

## 成果物
- C01/C05/C06 の evidence 5 要素 (P0 lint ログ / schema parity / build-trace coverage / content-review verdict / harness coverage JSON) を集約した Markdown 検証記録。

## スコープ外
- 新規の検証実施 (P06-P10 の結果を集約するのみ・ここで再テストしない)。
- 利用者向け文書化 (P12)。

## 完了チェックリスト
- [ ] C01/C05/C06 の evidence 5 要素が全て Markdown に記録されている。
- [ ] C05 の 4 イレギュラー分類 + 真の発行漏れの各分岐、C06 の Design D 出力先 DB 解決 (in-block/under-heading/page/page-created) + upsert 主キー衝突ゼロ (create/update/skip 内訳付き) が第三者に再現可能な形で記録されている。
- [ ] 明示 pin (`report_database_id`) を step0 で最優先する経路、`report_toggle_block` がトグル見出しでもプレーン見出し2でも同じ論理キーとして扱われ既存 DB があれば更新する経路、および明示 pin なし かつ 既存 DB 未発見時に phantom を作らず警告停止する経路(新規作成は明示 opt-in 時のみ・要件2)が fake-store で記録されている。実 Notion API evidence は read-only resolve または dry-run/apply 前確認の範囲で、設定済み `report_database_id`(pin 時)/ `report_parent_page` / `report_toggle_block` が想定 DB・ページ・見出しを指すことを記録する。

## 参照情報
- `references/phase-lifecycle.md` §7 (UBM スクショ→Markdown evidence の DROP 読替表)。
- evidence 5 要素 (lint/schema/build-trace/content-review/harness)。
- 対象 component C01/C05/C06。後続 P12 (documentation)。
