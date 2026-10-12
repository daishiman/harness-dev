# Rubric Rationale

各ルールの why。条文番号と設計書章への参照付き。rubric 1.6.0（41 rule）に対応する。

check 式の正本は `rubric.json`。この文書は人が読むための理由の説明で、食い違ったときは `rubric.json` を正とする。

**適用する kind**: 各 rule の `applies_to_kinds` に従う。見出しに kind を書いていない rule は kind=skill だけに適用する。`*` と書いた rule は全 kind に適用する。

## FM-001 name kebab + prefix（high）
- **Why**: prefix が無いと invocation layer (run/ref/assign/wrap/delegate) を判別できず、誤発動・誤権限割当の原因となる。
- **Source**: 第1〜5,7条 / 06章 / 24章

## FM-002 description の発動句（medium）
- **Why**: 検索/トリガ一致のアンカー句。フォーマット統一でtrigger精度が上がる。
- **発動句**: 英語の `Use when` / `Read when`。1.1.0 から日本語の 〜とき/〜場合/〜際/〜時 も認める。末尾は `.` か `。`。
- **Source**: 08章

## FM-003 trigger 2-3（medium）
- **Why**: 1だと取りこぼし、4以上だと誤発動&token浪費。経験則のスイートスポット。
- **Source**: 08章

## FM-004 動作詳細混入なし（medium）
- **Why**: description は invocation 判定のためにモデルが必ず読む箇所。動作詳細を書くとtoken浪費 + Goodhart(invocation詳細でスコア稼ぎ)を誘発。
- **Source**: 08, 09章

## FM-005 動詞始まり（low）
- **Why**: 何をするか冒頭で読める。Build / Score / Read / Wrap / Delegate / Generate / Rubric / Naming / Claude。1.1.0 から日本語の動詞（する/行う/実行/生成/採点/評価/構築/参照/読み取り/レビュー/管理）も認める。
- **Source**: 08章

## BD-001 Output Contract（high）
- **Why**: 入出力契約が無いとtestability=0。28章のscript実行モデルとも噛み合わない。
- **見出し**: 英語の `## Purpose & Output Contract` は従来の部分一致。1.4.0 から日本語の正規形 `## 目的と出力契約`（行全体の一致）も認める。
- **Source**: 28章

## BD-002 Gotchas（medium）
- **Why**: 反パターン提示 = 失敗回避の最短経路。
- **見出し**: `## Gotchas`。1.4.0 から日本語の正規形 `## つまずきやすい点`（行全体の一致）も認める。
- **Source**: 08章

## BD-003 <=300行（high、`*`）
- **Why**: SKILL.md本文の300行制約は Less is More 原則の機械的下限。agent・command などの本文にも同じ上限をかける。
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

## PD-001 100行 or references/（low、`*`）
- **Why**: Progressive Disclosure。本文は要約、長文は references/。
- **Source**: 07章

## PD-002 冒頭の目的・契約・禁則（medium）
- **Why**: 02章 §設計判断4 の「冒頭30行に目的・出力契約・禁則を集約する」規則を機械検査する。冒頭で読むのをやめても、何を返し何をしてはいけないかが伝わる。
- **BD-001 との関係**: BD-001 は契約節の存在だけを見る。PD-002 はその位置（冒頭30行）と禁則の有無を見るので、互いに独立している。31行目以降の契約節や、冒頭の禁則の欠落は PD-002 だけが落とす。
- **見出し**: 英語の目的見出しは従来の部分一致、日本語の `## 目的と出力契約` は行全体の一致（1.4.0）。禁則は MUST・NEVER・禁止・禁則・必ず・Key Rule のいずれか、または行全体が一致する `## 守ること`（1.5.0）。本文の単語「守ること」だけでは合格にしない。
- **Source**: 02章 / 07章

## RG-001 rubric_hash（low、`*`）
- **Why**: 採点結果の再現性。rubric改正(27章)時にもどの版で採点したか復元可能。
- **Source**: 27章

## AG-001〜004 Agent（kind=agent）
- **AG-001 tools の明示 allowlist（high）**: tools 未指定だと全 tool を継承し、権限境界が消える。明示の allowlist で最小権限を担保する（23章）。
- **AG-002 Isolation・Context Boundary 節（high）**: 何を触らないかを宣言すると、親 agent が安全に委譲できる。
- **AG-003 phase の一意 id（medium）**: phase id の衝突は orchestrator の振り分けを壊す（23章）。
- **AG-004 Handoff・Output Contract 節（medium）**: 出力契約が無いと、親 agent が結果を集約できない。

## HK-001〜004 Hook（kind=hook）
- **HK-001 event の enum（high）**: 未対応の event 名は Claude Code で no-op になり、hook が永久に発火しない。候補は実際に配線している event と capability manifest の schema の enum に揃える（1.6.0 で `PostToolUseFailure` を追加。3つの一致は `test_hook_event_vocabulary_parity.py` が検査する）。
- **HK-002 matcher の具体性（high）**: 全 tool に当たる matcher は noise を増やす。PreToolUse・PostToolUse では最小の範囲で宣言する。
- **HK-003 timeout の上限（medium）**: hook が止まるとセッション全体が止まる。
- **HK-004 副作用の明記（medium）**: hook は宣言外の副作用を持ちやすく、追いにくい。`## Side Effects` に書いて監査できるようにする。

## CM-001〜003 Command（kind=command）
- **CM-001 argument-hint（medium）**: 引数のヒントが無いと、利用者が使い方を思い出せない。
- **CM-002 allowed-tools の最小 allowlist（high）**: wildcard は権限拡張の温床になる。
- **CM-003 entrypoint skill の実在（high）**: command は薄い wrapper（24章）。呼ぶ skill が無いと dead command になる。

## PC-001〜004 Plugin Composition（kind=plugin-composition）
- **PC-001 capabilities[] の列挙（high）**: 能力の一覧は依存解決と監査の起点（29章）。
- **PC-002 依存の DAG（high）**: 循環依存は loader を壊す。
- **PC-003 rubric 参照の解決（medium）**: rubric のリンク切れは、採点のときに runtime error を起こす。
- **PC-004 hook の配線（medium）**: 宣言だけで配線されていない hook は技術的負債。

## PR-001〜003 Prompt（kind=prompt）
- **PR-001 7層構造（high）**: 7層の prompt 設計の正本構造。層の数がずれるのは構造の逸脱。
- **PR-002 Self-Evaluation・自己採点 節（medium）**: 自己採点の層は prompt の品質保証の契約（24章）。
- **PR-003 Output Format・Output Contract 節（high）**: 出力契約の無い prompt は再現性が無い。

## WF-001〜003 Workflow（kind=workflow）
- **WF-001 phase の順序番号（high）**: 順序が曖昧だと、orchestrator の状態機械を定義できない。
- **WF-002 遷移の gate 条件（high）**: gate の無い遷移は、無限ループや早すぎる終了の原因になる。
- **WF-003 max_iterations の安全弁（medium）**: 発散を止める安全弁。run-elegant-review の convergence-policy と整合する。

## KL-001〜005 Knowledge Loop（`*`、1.3.0）
- **存在ゲート**: knowledge/ ディレクトリか frontmatter.knowledge_loop があるときだけ検査する。knowledge-loop を組み込まないものは無条件 PASS（誤った減点を防ぐ）。
- **KL-001 索引とデータの分離（high）**: knowledge-index.json か router.json が知識ループの基盤。空のストアは運用できない。
- **KL-002 6つの必須フィールド（medium）**: 誰が書いても同じ品質になる再現性の要。欠けると検索の精度と AI の意味解釈が壊れる。
- **KL-003 決定論の段と AI の段の分離（medium）**: 再現できる決定論の段と、意味を解釈する AI の段を分けるのが精度の前提。全文検索だけでは出現頻度の noise で精度が落ちる。
- **KL-004 §12 feedback の配線（medium）**: 「使うほど良くなる」ループの実体。活用ログが無いと改善が回らず、蓄積が古びる。
- **KL-005 分割の閾値とライフサイクル（low）**: 500行・25エントリの分割と更新の記録で、無制限の肥大と古いエントリの滞留を防ぐ。
- **Source**: `ref-knowledge-loop/references/`
