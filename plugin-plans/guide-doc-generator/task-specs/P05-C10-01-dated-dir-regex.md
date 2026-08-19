---
id: "P05-C10-01-dated-dir-regex"
title: "出荷 hook の DATED_DIR_RE を区切り文字非依存へ rebuild する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/hooks/guard-handout-external-ref.py"
acceptance_criterion: "hooks/guard-handout-external-ref.py の適用対象判定が先頭 ISO 日付のみを見る形 (例 ^\\\\d{4}-\\\\d{2}-\\\\d{2}(?!\\\\d)) になり、2026-08-18_日本語名 と 2026-08-18-ascii-slug の両方に発火し、非日付ディレクトリには発火しないこと。区切り文字の正本は config/handout-output.json#dir_name_format であり hook はそれを複製しないこと"
objective: "実測: 出荷正規表現 r'^\\\\d{4}-\\\\d{2}-\\\\d{2}-' は末尾ハイフン固定で、利用者指定の出力先 05_Project/説明資料/yyyy-mm-dd_日本語命名 に一切マッチしない。外部参照ガードが恒久沈黙する"
verify: "hooks/guard-handout-external-ref.py の適用対象判定が先頭 ISO 日付のみを見る形 (例 ^\\\\d{4}-\\\\d{2}-\\\\d{2}(?!\\\\d)) になり、2026-08-18_日本語名 と 2026-08-18-ascii-slug の両方に発火し、非日付ディレクトリには発火しないこと。区切り文字の正本は config/handout-output.json#dir_name_format であり hook はそれを複製しないこと"
depends_on: ["P02-C10-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-C10-01-dated-dir-regex.md"]
consumes: []
---

# 出荷 hook の DATED_DIR_RE を区切り文字非依存へ rebuild する

## 由来

build 実行中に `P02-C10-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実測: 出荷正規表現 r'^\\d{4}-\\d{2}-\\d{2}-' は末尾ハイフン固定で、利用者指定の出力先 05_Project/説明資料/yyyy-mm-dd_日本語命名 に一切マッチしない。外部参照ガードが恒久沈黙する

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C10-01.json`

## 作業

`plugins/guide-doc-generator/hooks/guard-handout-external-ref.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-C10-01-dated-dir-regex.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

hooks/guard-handout-external-ref.py の適用対象判定が先頭 ISO 日付のみを見る形 (例 ^\\d{4}-\\d{2}-\\d{2}(?!\\d)) になり、2026-08-18_日本語名 と 2026-08-18-ascii-slug の両方に発火し、非日付ディレクトリには発火しないこと。区切り文字の正本は config/handout-output.json#dir_name_format であり hook はそれを複製しないこと
