---
id: "P05-x-46-root-resolution-dedup"
title: "実体解決 4 段の手順文を 6 本の brief から参照形へ集約する"
phase_ref: "P03"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/"
acceptance_criterion: "4 段の完全手順文を持つ brief が C15 の 1 本のみになり、他は参照で成立する"
objective: "P03-x-02 で C17 / C09 を参照形へ寄せた結果、4 段の完全手順文を複製して持つのは C10:84 / C11:51 / C12:827 / C15:9,39,66 / C21:76 / C23:87 の 6 本。段数は全て一致しており矛盾ではなく冗長だが、4 段の内容を変えるとき 6 箇所を同時に直す必要がある。C15 を実装レベル正本として残し他 5 本を参照形へ寄せる"
verify: "4 段の完全手順文を持つ brief が C15 の 1 本のみになり、他は参照で成立する"
depends_on: ["P03-x-02"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-46-root-resolution-dedup.md"]
consumes: []
---

# 実体解決 4 段の手順文を 6 本の brief から参照形へ集約する

## 由来

build 実行中に `P03-x-02` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P03-x-02 で C17 / C09 を参照形へ寄せた結果、4 段の完全手順文を複製して持つのは C10:84 / C11:51 / C12:827 / C15:9,39,66 / C21:76 / C23:87 の 6 本。段数は全て一致しており矛盾ではなく冗長だが、4 段の内容を変えるとき 6 箇所を同時に直す必要がある。C15 を実装レベル正本として残し他 5 本を参照形へ寄せる

**発見時の証跡**: `plugin-plans/guide-doc-generator/briefs/`

## 作業

`plugin-plans/guide-doc-generator/briefs/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-46-root-resolution-dedup.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

4 段の完全手順文を持つ brief が C15 の 1 本のみになり、他は参照で成立する
