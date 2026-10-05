# Prompt: R5-hooks

> C25のplugin hookを共有既定とする。project fallbackはplain-symlink導入時だけ許可し、effective plugin hookが見えれば拒否する。C24で検証した`.claude/dev-graph-plugin`からC10/C25全eventを既存settingsへpreview付きdeep-mergeし、override/二重登録を診断してrollback manifestを残す

## Layer 1: 基本定義層

- `responsibility_id`: `R5-hooks`
- `skill`: `run-dev-graph-init`
- 不変目的: C25のplugin hookを共有既定とする。project fallbackはplain-symlink導入時だけ許可し、effective plugin hookが見えれば拒否する。C24で検証した`.claude/dev-graph-plugin`からC10/C25全eventを既存settingsへpreview付きdeep-mergeし、override/二重登録を診断してrollback manifestを残す
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- C24 receipt、effective plugin hook検出、既存settings、C10/C25 event contract。

### 出力契約

- plugin-managed判定、fallback deep-merge preview、適用receipt、rollback manifestまたは拒否診断。

### 責務境界

- fallbackはplain-symlinkかつeffective plugin hook不在時のみ許可し既存key上書き/二重登録をしない。

### 受入条件

- 全eventが一経路だけに配線され既存key/hash変更0、rollbackで完全復元できる。

## Layer 3: インフラ層

- 使用資産: `../../scripts/build-project-hook-fallback.py --repo-root <path> --mode preview|apply|rollback [--manifest <path>]` (skill root 起点) と Claude hook contract の Read。`.claude/settings.json` を Write/Edit や heredoc で直接書かず、この script に委譲する。plugin hook 既定 (`hook_source=plugin`) では script を起動せず、settings に触れない。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-init/R5-hooks`

### 5.2 ゴール定義

- 目的: C25のplugin hookを共有既定とする。project fallbackはplain-symlink導入時だけ許可し、effective plugin hookが見えれば拒否する。C24で検証した`.claude/dev-graph-plugin`からC10/C25全eventを既存settingsへpreview付きdeep-mergeし、override/二重登録を診断してrollback manifestを残す
- 達成ゴール: plugin-managed判定、fallback deep-merge preview、適用receipt、rollback manifestまたは拒否診断が生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 全eventが一経路だけに配線され既存key/hash変更0、rollbackで完全復元できる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- hook 診断は R5 の適用 receipt と rollback manifest として返す。manifest は `build-project-hook-fallback.py` が `.dev-graph/state/receipts/hook-fallback-<UTC>.json` へ create-only で書き、拒否診断は同 script の `status=rejected` の `findings` をそのまま返す。init receipt は `build-init-scaffold.py` が create-only で書き、hook については選んだ `hook_source` だけを記録する。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

