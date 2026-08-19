---
id: "P05-x-72-criterion-proxy-trio"
title: "C46(b) / C51(a) / C54 が criterion をプロキシで代替している件を裁定する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/goal-spec.json"
acceptance_criterion: "3 件それぞれについて、プロキシで妥協するのか criterion を実装可能な文へ書き直すのかの裁定が記録され、プロキシを採る場合は criterion 側にその旨が明記されていること"
objective: "C46(b) は row.sub の有無だけを見るため行本文へ手順を書けば通る。C51(a) の 機能名から始まる説明の禁止 は slot ラベルの順序検査では見ておらず C18 LANG-07 の HTML 面へ割れている。C54 は宣言 attainment_level と各節の自己申告 attainment_step を同じ index で比較するだけで criterion の 内容範囲 を見ていない。いずれもラベルが正しければ中身は問わない型で、checklist を緑にしたまま criterion を破れる。orange と cyan が独立に同じ 3 件を検出"
verify: "3 件それぞれについて、プロキシで妥協するのか criterion を実装可能な文へ書き直すのかの裁定が記録され、プロキシを採る場合は criterion 側にその旨が明記されていること"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-72-criterion-proxy-trio.md"]
consumes: []
---

# C46(b) / C51(a) / C54 が criterion をプロキシで代替している件を裁定する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C46(b) は row.sub の有無だけを見るため行本文へ手順を書けば通る。C51(a) の 機能名から始まる説明の禁止 は slot ラベルの順序検査では見ておらず C18 LANG-07 の HTML 面へ割れている。C54 は宣言 attainment_level と各節の自己申告 attainment_step を同じ index で比較するだけで criterion の 内容範囲 を見ていない。いずれもラベルが正しければ中身は問わない型で、checklist を緑にしたまま criterion を破れる。orange と cyan が独立に同じ 3 件を検出

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugin-plans/guide-doc-generator/goal-spec.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-72-criterion-proxy-trio.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

3 件それぞれについて、プロキシで妥協するのか criterion を実装可能な文へ書き直すのかの裁定が記録され、プロキシを採る場合は criterion 側にその旨が明記されていること
