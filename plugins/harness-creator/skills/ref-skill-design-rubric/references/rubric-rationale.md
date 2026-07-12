# Rubric Rationale

各ルールの why。条文番号と設計書章への参照付き。

## FM-001 name kebab + prefix（high）
- **Why**: prefix が無いと invocation layer (run/ref/assign/wrap/delegate) を判別できず、誤発動・誤権限割当の原因となる。
- **Source**: 第1〜5,7条 / 06章 / 24章

## FM-002 description "Use when"（medium）
- **Why**: 検索/トリガ一致のアンカー句。フォーマット統一でtrigger精度が上がる。
- **Source**: 08章

## FM-003 trigger 2-3（medium）
- **Why**: 1だと取りこぼし、4以上だと誤発動&token浪費。経験則のスイートスポット。
- **Source**: 08章

## FM-004 動作詳細混入なし（medium）
- **Why**: description は invocation 判定のためにモデルが必ず読む箇所。動作詳細を書くとtoken浪費 + Goodhart(invocation詳細でスコア稼ぎ)を誘発。
- **Source**: 08, 09章

## FM-005 動詞始まり（low）
- **Why**: 何をするか冒頭で読める。Build / Score / Read / Wrap / Delegate / Generate / Rubric / Naming / Claude。
- **Source**: 08章

## BD-001 Output Contract（high）
- **Why**: 入出力契約が無いとtestability=0。28章のscript実行モデルとも噛み合わない。
- **Source**: 28章

## BD-002 Gotchas（medium）
- **Why**: 反パターン提示 = 失敗回避の最短経路。
- **Source**: 08章

## BD-003 <=300行（high）
- **Why**: SKILL.md本文の300行制約は Less is More 原則の機械的下限。
- **Source**: 24章

## BD-004 description↔body 整合（medium, LLM judge）
- **Why**: description は Claude が『いつ呼ぶか』を判断する契約 (08章)。body が trigger を満たさないと Skill は呼ばれても約束を履行できず、Goodhart 罠 (描いただけで採点を通す) に陥る。BD-001..003 が『節の存在』を見るのに対し BD-004 は『description ↔ body の整合』を見るため直交する。
- **Note**: 旧版は `TODO(human)` の空欄スロットだったが、1.2.0 で AI 起案 + governance 承認により実ルール化（[[feedback-no-todo-human]] / proposer≠approver 整合）。
- **Source**: 08, 09章

## NM-001 dirname == name（high）
- **Why**: Skill loader が name 解決に失敗。第7条。
- **Source**: 06章

## NM-002 命名規約条文1〜5（medium）
- **Source**: 06章

## NM-003 構造条文8〜13（low）
- **Source**: 06章

## PD-001 100行 or references/（low）
- **Why**: Progressive Disclosure。本文は要約、長文は references/。
- **Source**: 07章

## RG-001 rubric_hash（low）
- **Why**: 採点結果の再現性。rubric改正(27章)時にもどの版で採点したか復元可能。
- **Source**: 27章
