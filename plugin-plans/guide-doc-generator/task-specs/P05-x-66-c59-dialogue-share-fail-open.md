---
id: "P05-x-66-c59-dialogue-share-fail-open"
title: "C59 の下限割合検査が dialogue 不在で発火しない fail-open を塞ぐ"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/scripts/validate-handout-config.py"
acceptance_criterion: "min_duration_share を持つ section_kind が構成データに 1 件も無いとき、continue で検査を飛ばさず必須性違反として落ちること。dialogue を削るだけで C59 が無効化できないことを回帰テストで固定する"
objective: "validate-handout-config.py:1349 の if slug not in used: continue により、dialogue セクションを 1 つも置かなければ share 検査に入らない。必須性は C23 プリセット側にしかないため、プリセット外の構成データでは節を消すだけで C59 が無効化される。C49/C56 と同型の fail-open。orange が検出し dispatcher が該当行を直読みして確認 (cyan は同じ criterion を full と判定しており、判定が割れた)"
verify: "min_duration_share を持つ section_kind が構成データに 1 件も無いとき、continue で検査を飛ばさず必須性違反として落ちること。dialogue を削るだけで C59 が無効化できないことを回帰テストで固定する"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-66-c59-dialogue-share-fail-open.md"]
consumes: []
---

# C59 の下限割合検査が dialogue 不在で発火しない fail-open を塞ぐ

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: validate-handout-config.py:1349 の if slug not in used: continue により、dialogue セクションを 1 つも置かなければ share 検査に入らない。必須性は C23 プリセット側にしかないため、プリセット外の構成データでは節を消すだけで C59 が無効化される。C49/C56 と同型の fail-open。orange が検出し dispatcher が該当行を直読みして確認 (cyan は同じ criterion を full と判定しており、判定が割れた)

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/scripts/validate-handout-config.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-66-c59-dialogue-share-fail-open.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

min_duration_share を持つ section_kind が構成データに 1 件も無いとき、continue で検査を飛ばさず必須性違反として落ちること。dialogue を削るだけで C59 が無効化できないことを回帰テストで固定する
