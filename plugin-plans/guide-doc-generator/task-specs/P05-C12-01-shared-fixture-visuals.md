---
id: "P05-C12-01-shared-fixture-visuals"
title: "共有テストフィクスチャの最小構成データへ図解と画像を持たせる"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/tests/"
acceptance_criterion: "[要再定義] 発見時の記述から機械生成した暫定条件。着手前に実測可能な条件へ差し替えること。暫定: 「共有テストフィクスチャの最小構成データへ図解と画像を持たせる」を解消し、その根拠 (発見理由: R8 (図解と画像を毎回セクションごとに) で E-IMAGE-ABSENT / W-DIAGRAM-FEW を main セクション単位の error に上げた結果、plugins/guide-doc-generator/tests/validate-handout-config.py/_harness.py が組み立てる最小構成データが IMG も DIAGRAM も持たないため、密度検査と無関係な検査 (micro_copy / layering / normalize_date / r21_text_fold ほか) まで exit=0 の前提が崩れて赤になった。_harness.py の baseline 構成データへ IMG と DIAGRAM の部品および assets/diagrams の実体を足し、密度検査を意図的に検証するテストだけが欠落状態を作る形へ揃える。原因は 1 箇所 (共有フィクスチャ) であり、個々のテストの期待値ではない。) が再現しないことを実測で示す。"
objective: "R8 (図解と画像を毎回セクションごとに) で E-IMAGE-ABSENT / W-DIAGRAM-FEW を main セクション単位の error に上げた結果、plugins/guide-doc-generator/tests/validate-handout-config.py/_harness.py が組み立てる最小構成データが IMG も DIAGRAM も持たないため、密度検査と無関係な検査 (micro_copy / layering / normalize_date / r21_text_fold ほか) まで exit=0 の前提が崩れて赤になった。_harness.py の baseline 構成データへ IMG と DIAGRAM の部品および assets/diagrams の実体を足し、密度検査を意図的に検証するテストだけが欠落状態を作る形へ揃える。原因は 1 箇所 (共有フィクスチャ) であり、個々のテストの期待値ではない。"
verify: "[要再定義] 発見時の記述から機械生成した暫定条件。着手前に実測可能な条件へ差し替えること。暫定: 「共有テストフィクスチャの最小構成データへ図解と画像を持たせる」を解消し、その根拠 (発見理由: R8 (図解と画像を毎回セクションごとに) で E-IMAGE-ABSENT / W-DIAGRAM-FEW を main セクション単位の error に上げた結果、plugins/guide-doc-generator/tests/validate-handout-config.py/_harness.py が組み立てる最小構成データが IMG も DIAGRAM も持たないため、密度検査と無関係な検査 (micro_copy / layering / normalize_date / r21_text_fold ほか) まで exit=0 の前提が崩れて赤になった。_harness.py の baseline 構成データへ IMG と DIAGRAM の部品および assets/diagrams の実体を足し、密度検査を意図的に検証するテストだけが欠落状態を作る形へ揃える。原因は 1 箇所 (共有フィクスチャ) であり、個々のテストの期待値ではない。) が再現しないことを実測で示す。"
depends_on: ["P05-x-86"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-C12-01-shared-fixture-visuals.md"]
consumes: []
---

# 共有テストフィクスチャの最小構成データへ図解と画像を持たせる

## 由来

build 実行中に `P05-x-86` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: R8 (図解と画像を毎回セクションごとに) で E-IMAGE-ABSENT / W-DIAGRAM-FEW を main セクション単位の error に上げた結果、plugins/guide-doc-generator/tests/validate-handout-config.py/_harness.py が組み立てる最小構成データが IMG も DIAGRAM も持たないため、密度検査と無関係な検査 (micro_copy / layering / normalize_date / r21_text_fold ほか) まで exit=0 の前提が崩れて赤になった。_harness.py の baseline 構成データへ IMG と DIAGRAM の部品および assets/diagrams の実体を足し、密度検査を意図的に検証するテストだけが欠落状態を作る形へ揃える。原因は 1 箇所 (共有フィクスチャ) であり、個々のテストの期待値ではない。

**発見時の証跡**: `plugins/guide-doc-generator/tests/validate-handout-config.py/_harness.py`

## 作業

`plugins/guide-doc-generator/tests/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-C12-01-shared-fixture-visuals.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

[要再定義] 発見時の記述から機械生成した暫定条件。着手前に実測可能な条件へ差し替えること。暫定: 「共有テストフィクスチャの最小構成データへ図解と画像を持たせる」を解消し、その根拠 (発見理由: R8 (図解と画像を毎回セクションごとに) で E-IMAGE-ABSENT / W-DIAGRAM-FEW を main セクション単位の error に上げた結果、plugins/guide-doc-generator/tests/validate-handout-config.py/_harness.py が組み立てる最小構成データが IMG も DIAGRAM も持たないため、密度検査と無関係な検査 (micro_copy / layering / normalize_date / r21_text_fold ほか) まで exit=0 の前提が崩れて赤になった。_harness.py の baseline 構成データへ IMG と DIAGRAM の部品および assets/diagrams の実体を足し、密度検査を意図的に検証するテストだけが欠落状態を作る形へ揃える。原因は 1 箇所 (共有フィクスチャ) であり、個々のテストの期待値ではない。) が再現しないことを実測で示す。
