# dev-graph prompt 共通層 (Layer 4〜7)

dev-graph の `skills/run-dev-graph-*/prompts/R*.md` が共有する Layer 4〜7 の定型部分の正本。各 prompt は層の見出しと、この reference の該当節を指す 1 行と、責務に固有の行だけを持つ。

## 読み方

- 各 prompt の Layer 4〜7 は、この reference の同名の節と prompt 側の固有行を合わせた内容とする。どちらも適用し、一方で他方を置き換えない。
- 節は prompt の見出しと同じ名前で引く (例: 「Layer 5」はこの reference の `## Layer 5: エージェント層 (l5-contract v2.0.0)`)。
- この reference は 9 skill の SKILL.md の `reference_refs` に入っており、skill の挙動閉包に含まれる。書き換えると 9 skill すべての live trial verdict が古くなる。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- 担当 agent は各 prompt の 5.1 に書く。重い判断または独立検証は `Agent` で分離 context に fork する。

### 5.2 ゴール定義

- 目的と達成ゴールは各 prompt の 5.2 に書く。
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

全責務に共通の項目。各 prompt の 5.3 の項目と合わせ、すべてが YES になったときにゴール到達とする。

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- 渡し先・返し先は各 prompt の Layer 6 に書く。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。
