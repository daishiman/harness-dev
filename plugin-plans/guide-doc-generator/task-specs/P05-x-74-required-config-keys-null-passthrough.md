---
id: "P05-x-74-required-config-keys-null-passthrough"
title: "必須フィールド検査が null を素通りする fail-open を塞ぐ"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/scripts/verify-handout-narrative.py"
acceptance_criterion: "REQUIRED_CONFIG_KEYS の各キーについて、キー不在と null 代入が同じ扱い (exit 2) になること。tests/verify-handout-narrative.py/test_nar07_demo_first.py::TestNar07CannotBeDisabledByNulling の 3 本が緑になること。空文字・空配列でも同型でないことを併せて確認すること"
objective: "verify-handout-narrative.py:558-560 が for key in REQUIRED_CONFIG_KEYS: if key not in config: で見ているため null はキーが存在する扱いで素通りする。素通りした null は NAR-07 で demo_first と一致せず SKIP へ落ちる。dispatcher が実際にテストを走らせて確認: 違反のある HTML (最初の本編セクション先頭が DIAGRAM) が presentation_order を null にするだけで exit 0 / NAR-07 SKIP order=None になり緑化する。キー削除なら exit 2。orange が P04-C22-01 で検出し赤 3 本で固定済み"
verify: "REQUIRED_CONFIG_KEYS の各キーについて、キー不在と null 代入が同じ扱い (exit 2) になること。tests/verify-handout-narrative.py/test_nar07_demo_first.py::TestNar07CannotBeDisabledByNulling の 3 本が緑になること。空文字・空配列でも同型でないことを併せて確認すること"
depends_on: ["P04-C22-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-74-required-config-keys-null-passthrough.md"]
consumes: []
---

# 必須フィールド検査が null を素通りする fail-open を塞ぐ

## 由来

build 実行中に `P04-C22-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: verify-handout-narrative.py:558-560 が for key in REQUIRED_CONFIG_KEYS: if key not in config: で見ているため null はキーが存在する扱いで素通りする。素通りした null は NAR-07 で demo_first と一致せず SKIP へ落ちる。dispatcher が実際にテストを走らせて確認: 違反のある HTML (最初の本編セクション先頭が DIAGRAM) が presentation_order を null にするだけで exit 0 / NAR-07 SKIP order=None になり緑化する。キー削除なら exit 2。orange が P04-C22-01 で検出し赤 3 本で固定済み

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/scripts/verify-handout-narrative.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-74-required-config-keys-null-passthrough.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

REQUIRED_CONFIG_KEYS の各キーについて、キー不在と null 代入が同じ扱い (exit 2) になること。tests/verify-handout-narrative.py/test_nar07_demo_first.py::TestNar07CannotBeDisabledByNulling の 3 本が緑になること。空文字・空配列でも同型でないことを併せて確認すること
