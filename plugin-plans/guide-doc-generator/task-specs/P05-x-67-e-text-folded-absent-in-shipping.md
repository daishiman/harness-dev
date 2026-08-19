---
id: "P05-x-67-e-text-folded-absent-in-shipping"
title: "E-TEXT-FOLDED が設計にのみ存在し出荷コードに無い件を裁定して解消する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/scripts/validate-handout-config.py"
acceptance_criterion: "E-TEXT-FOLDED を出荷側に実装するか、設計側から幻の detection 名を撤回するかの裁定が下され、goal-spec C52 と C73 の矛盾も同時に解消していること。--normalize の有無で超過検出と畳み込みが排他になっている状態が解消されていること"
objective: "grep で E-TEXT-FOLDED は plugin-plans/ と eval-log/ に 20 件以上あるが plugins/ 配下は 0 件。script-brief-C12.json は C52 の detection として E-TEXT-FOLDED を名指しするが、出荷側の実体は fold_section() による変換であり detection ではない。さらに :1977 の check_text_bodies(cfg, report_overflow=not args.normalize) により --normalize 付きでは E-TEXT-OVERFLOW も出ないため、畳まれていない構成データを検証だけで落とす手段が実質存在しない"
verify: "E-TEXT-FOLDED を出荷側に実装するか、設計側から幻の detection 名を撤回するかの裁定が下され、goal-spec C52 と C73 の矛盾も同時に解消していること。--normalize の有無で超過検出と畳み込みが排他になっている状態が解消されていること"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-67-e-text-folded-absent-in-shipping.md"]
consumes: []
---

# E-TEXT-FOLDED が設計にのみ存在し出荷コードに無い件を裁定して解消する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: grep で E-TEXT-FOLDED は plugin-plans/ と eval-log/ に 20 件以上あるが plugins/ 配下は 0 件。script-brief-C12.json は C52 の detection として E-TEXT-FOLDED を名指しするが、出荷側の実体は fold_section() による変換であり detection ではない。さらに :1977 の check_text_bodies(cfg, report_overflow=not args.normalize) により --normalize 付きでは E-TEXT-OVERFLOW も出ないため、畳まれていない構成データを検証だけで落とす手段が実質存在しない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/scripts/validate-handout-config.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-67-e-text-folded-absent-in-shipping.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

E-TEXT-FOLDED を出荷側に実装するか、設計側から幻の detection 名を撤回するかの裁定が下され、goal-spec C52 と C73 の矛盾も同時に解消していること。--normalize の有無で超過検出と畳み込みが排他になっている状態が解消されていること
