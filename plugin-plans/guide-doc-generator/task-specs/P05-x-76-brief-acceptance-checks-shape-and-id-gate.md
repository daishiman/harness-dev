---
id: "P05-x-76-brief-acceptance-checks-shape-and-id-gate"
title: "brief の acceptance_checks の形と id 一意性を機械検査するゲートを置く"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/"
acceptance_criterion: "全 brief の acceptance_checks について (a) id が brief 内で一意、(b) 要素の形が brief 間で統一されている、のいずれも機械検査するゲートが存在し exit0 であること。統一しない判断を採る場合はその根拠が記録されていること"
objective: "dispatcher が 23 brief を横断実測したところ acceptance_checks の形が 3 種類に割れている: dict + id を持つ 17 brief (計 302 件)、id を持たない文字列配列 2 brief (hook-brief-C10 が 23 件・script-brief-C19 が 27 件)、acceptance_checks 自体が 0 件の 4 brief (skill-brief-C01..C04)。id 一意性を検査する gate が存在しないため P05-x-75 の id 重複が誰にも検出されなかった。文字列配列の 2 brief は id を持たないため参照も差分追跡もできない"
verify: "全 brief の acceptance_checks について (a) id が brief 内で一意、(b) 要素の形が brief 間で統一されている、のいずれも機械検査するゲートが存在し exit0 であること。統一しない判断を採る場合はその根拠が記録されていること"
depends_on: ["P04-C22-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-76-brief-acceptance-checks-shape-and-id-gate.md"]
consumes: []
---

# brief の acceptance_checks の形と id 一意性を機械検査するゲートを置く

## 由来

build 実行中に `P04-C22-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: dispatcher が 23 brief を横断実測したところ acceptance_checks の形が 3 種類に割れている: dict + id を持つ 17 brief (計 302 件)、id を持たない文字列配列 2 brief (hook-brief-C10 が 23 件・script-brief-C19 が 27 件)、acceptance_checks 自体が 0 件の 4 brief (skill-brief-C01..C04)。id 一意性を検査する gate が存在しないため P05-x-75 の id 重複が誰にも検出されなかった。文字列配列の 2 brief は id を持たないため参照も差分追跡もできない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugin-plans/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-76-brief-acceptance-checks-shape-and-id-gate.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

全 brief の acceptance_checks について (a) id が brief 内で一意、(b) 要素の形が brief 間で統一されている、のいずれも機械検査するゲートが存在し exit0 であること。統一しない判断を採る場合はその根拠が記録されていること
