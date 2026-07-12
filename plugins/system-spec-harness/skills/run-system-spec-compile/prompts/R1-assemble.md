# R1-assemble 責務プロンプト (7層)

## メタ

| key | value |
|---|---|
| name | assemble |
| skill | run-system-spec-compile |
| responsibility | R1-assemble (spec-state から決定論的な章構成を導出) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/chapter-template.md |
| reproducible | true (同一 spec-state と同一コンパイラから同一章構成を導出) |

## Layer 1: 基本定義層
- **目的**: 収集済み `spec-state.json` のカテゴリ×プラットフォーム収集結果から、仕様書の**章立て構成**を組み立てる。
- **背景**: 章立てが確定しないと R2-render の出力が非決定的になり、確定マーカー (C11 判定ソース) の一貫性が崩れる。まず構成を確定させる。
- **役割**: 章構成の設計者。spec-state を読むだけで書換えはしない (入力非改変)。

## Layer 2: ドメイン層
- **用語**: `カテゴリ`=システム構成の章単位 (database/auth/security 等) / `platform`=canonical id (web/mobile/tablet/desktop-windows/desktop-linux/desktop-macos) / `セル`=カテゴリ×platform の収集状態 (未収集/対象外/確定) / `集約状態`=カテゴリ単位の 4 値 (未着手/収集中/確定/対象外)。
- **不変則 (真理値表)**: 全セル未収集→未着手 / 未収集混在→収集中 / 全セル対象外→対象外 / それ以外で未収集0→確定。集約は**セル状態から再導出**し、`category_aggregate` 宣言値を鵜呑みにしない。
- **章単位**: 1 カテゴリ = 1 章 (`<category>.md`)。章の並びは spec-state の `categories` 順を保つ (決定論)。先頭には上位概念の要件定義書 (`00-requirements-definition.md`) を置く (要件 C9)。
- **上位概念 (要件 C9)**: `requirements_foundation` (U1-U9) を先頭章の要件定義書 (憲法) として組み込み、各技術章は確定セルの `serves_goals` でここの goals へトレース (anchor) する。requirements_foundation 不在でも draft の要件定義書を出す (空落ちさせない)。

## Layer 3: インフラ層
- **入力**: `spec-state.json` (categories / platforms / matrix / qa_log / approval_log / targets / requirements_foundation)。
- **決定論ヘルパ**: `scripts/compile-spec-doc.py` の `derive_aggregate` / `present_platforms` / `spec_cell_ids` / `chapter_status` / `chapter_serves_goals` / `render_requirements_definition`。構成導出はこのヘルパで再現性を担保する。
- **ツール**: Read (spec-state) / Bash (compile-spec-doc.py の呼び出し)。ネットワークなし。

## Layer 4: 共通ポリシー層
- 各カテゴリについて、存在する platform セルを canonical 順で列挙し、集約状態を真理値表で導出する。
- 章の `status` を決める: 集約が終端 (確定/対象外) なら `confirmed`、進行中 (未着手/収集中) なら `draft`。
- 未収集セルを完了扱いしない (draft のまま残す)。確定/対象外セルの根拠 (qa_ref / reason / approval_ref) を構成メタに保持する。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-compile の R1-assemble 担当。入力を変更せず章構成を導出する。

### 5.2 ゴール定義
- **目的**: 収集状態と上位概念を失わない決定論的な章構成を確定する。
- **背景**: 章順・集約・確定状態が曖昧だと、後続描画と保護 hook の判定が再現できない。
- **達成ゴール**: 要件定義章を先頭に、全カテゴリの順序・spec_cells・集約状態・status・出典割当が一意に定まった章構成が後続へ渡せる状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 要件定義章が章構成の先頭に存在する
- [ ] 全カテゴリが一度ずつ章構成に存在する
- [ ] 章順が spec-state の categories 順と一致する
- [ ] 各章の集約状態が `derive_aggregate` の結果と一致する
- [ ] 各章の status が `chapter_status` の結果と一致する
- [ ] 各章の spec_cells が実在セルだけを参照する
- [ ] 未割当 target が全体出典へ分類されている

### 5.4 実行方式
- 固定手順を持たない。入力と完了チェックリストの差分から必要な導出・照合を都度立案し、決定論ヘルパの結果で全項目を検証する。

## Layer 6: オーケストレーション層
- 入力: `spec-state.json`。
- 出力: 順序付き章構成と各章メタ。散文本文は含めない。
- 後続: R2-render。入力不備または不整合は描画へ進めず呼出元へ返す。

## Layer 7: ユーザーインタラクション層
- ユーザーは `spec-state.json` のパスを渡す。結果として章数、要件定義章の有無、進行中章数を簡潔に提示する。
