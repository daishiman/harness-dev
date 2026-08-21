# Prompt: R1-read-only-intake-status

> 7層の正本に従い、1 prompt = 1責務でintake進捗のread-only集計を行う。

## Layer 1: 基本定義層

- 対象は`output/<hint>/`、または引数なしの場合の`output/*/`とする。
- 状態確認はread-onlyとし、生成・修復・公開を行わない。

## Layer 2: ドメイン層

### 入力契約

- `hint` (任意): 対象output名。
- 実在証拠 (出力表6列と1:1): `kickoff.json`、`profile.json`、`intake.json` (5軸)、`visuals/*.{svg,png}`、`notion-url.txt`、`notion-log.json`。

### 出力契約

`hint | kickoff | profile | 5 axes | visuals | notion`のMarkdown表を返す。欠落は未完了、JSON parse不能は理由付きerrorとし、成功に変換しない。

## Layer 3: インフラ層

- 使用は`Read`と`Glob`に限定する。
- 外部API、network、shell、write toolを使用しない。

## Layer 4: 共通ポリシー層

- 実在しない対象やファイルは推測しない。
- ログに機密値が含まれる場合は状態フィールドだけを読み、値を出力しない。
- 同じ証拠の再集計で結果が変わらなければ停止する。

## Layer 5: エージェント層

### ゴール定義

- 目的: 現在のintake進捗と欠落証拠を、書き込みなしで判定する。
- 背景: 中断後の再開時に状態を推測すると、未完了を成功と誤認する。
- 達成ゴール: 全対象が1行ずつ報告され、各列が実在証拠へ追跡できる。

### 完了チェックリスト

- [ ] 対象hintの集合を確定した。
- [ ] kickoff/profile/5軸/visual/Notionの証拠を対象ごとに再集計した。
- [ ] 欠落・parse不能・状態不明を成功に変換していない。
- [ ] 対象ごとにMarkdown表の1行が存在する。
- [ ] ファイルを生成・修復・更新していない。

### 実行方式

未充足のチェックを1つ選び、必要な証拠だけを読み、再集計する。全項目が充足するか、実在証拠の不足で進めないと確定するまで反復する。

## Layer 6: オーケストレーション層

- 上流: `run-skill-intake`が作成した`output/<hint>/`。
- 下流: ユーザーによる次アクション判断。本責務から他skillを自動実行しない。
- 複数hintの読取りは独立だが、出力順はhintで安定sortする。

## Layer 7: UI / 提示層

- 最初にMarkdown表を提示し、続けて欠落・errorの根拠を簡潔に列挙する。
- 日本語で返し、成功は実在証拠がある場合だけ`✓`と表示する。

## Output Contract

`{{hint_or_empty}}`を対象にread-only集計を実行し、契約準拠のMarkdown表と未完了根拠だけを出力する。
