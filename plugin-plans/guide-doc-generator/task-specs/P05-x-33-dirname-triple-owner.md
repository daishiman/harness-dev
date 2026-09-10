---
id: "P05-x-33-dirname-triple-owner"
title: "ディレクトリ命名を config 単一正本へ寄せる (C19/C18/C10 の三重焼きを同時に解消)"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "config/handout-output.json#dir_name_format を唯一の正本とし、C19/C18/C10 の 3 者がそこから読む。yyyy-mm-dd_日本語命名 で出力され C18 の日付ゲートと hook が同時に緑になる"
objective: "実測: dir_name_format は出荷ツリーに 0 件で C19 は読んでいない。route-handout-output.py:433 が {date}-{token}-{slug} を直接焼き、verify-handout-language.py:379 が dir_separator='-' を独立に持ち、hook が ^\\d{4}-\\d{2}-\\d{2}- を正規表現で持つ。config を足すだけでは何も変わらず、C19 単独修正は C18 DATE-03 を必ず落とす。3 者同時修正でなければ緑にならない"
verify: "config/handout-output.json#dir_name_format を唯一の正本とし、C19/C18/C10 の 3 者がそこから読む。yyyy-mm-dd_日本語命名 で出力され C18 の日付ゲートと hook が同時に緑になる"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-33-dirname-triple-owner.md"]
consumes: []
---

# ディレクトリ命名を config 単一正本へ寄せる (C19/C18/C10 の三重焼きを同時に解消)

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実測: dir_name_format は出荷ツリーに 0 件で C19 は読んでいない。route-handout-output.py:433 が {date}-{token}-{slug} を直接焼き、verify-handout-language.py:379 が dir_separator='-' を独立に持ち、hook が ^\d{4}-\d{2}-\d{2}- を正規表現で持つ。config を足すだけでは何も変わらず、C19 単独修正は C18 DATE-03 を必ず落とす。3 者同時修正でなければ緑にならない

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-33-dirname-triple-owner.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

config/handout-output.json#dir_name_format を唯一の正本とし、C19/C18/C10 の 3 者がそこから読む。yyyy-mm-dd_日本語命名 で出力され C18 の日付ゲートと hook が同時に緑になる
