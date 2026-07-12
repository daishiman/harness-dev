# 命名規約 全文（第1〜16条）

設計書 06章を圧縮。ref-* 配下のため 300行制約対象外。

## 第1条（形式）
Skill 名は kebab-case とする。英小文字 (a-z)、数字 (0-9)、ハイフン (-) のみ。
先頭は英小文字。連続ハイフンは禁止。

正: `run-build-skill`, `ref-skill-design-rubric`
誤: `RunBuildSkill`, `run--build`, `1-skill`

## 第2条（prefix）
以下 5 prefix のいずれかを必ず持つ:

- `run-` … workflow / 実行可能
- `ref-` … reference / 参照辞書
- `assign-` … 委任 / forked agent（generator or evaluator）
- `wrap-` … 外部ツール/CLIラッパ
- `delegate-` … subagent への委譲 thin wrapper

## 第3条（role-suffix 推奨）
役割を suffix で明示:

- `-evaluator`, `-generator`, `-runbook`, `-spec`, `-rubric`, `-convention`, `-governance`

## 第4条（動詞 / 名詞）
- run / assign 系は動詞ベースを推奨: `run-build-skill`, `assign-...-evaluator`
- ref / wrap / delegate 系は名詞ベース: `ref-skill-naming-convention`

## 第5条（長さ）
prefix を含む合計 60 文字以下。

## 第6条（予約語）
単独使用禁止: `skill`, `claude`, `anthropic`。
複合は可: `ref-claude-code-skill-spec`。

## 第7条（ディレクトリ名 == frontmatter.name）
不一致は loader が解決不能。

## 第8条（templates/）
`templates/<kind>.md` 形式。ファイル名は kebab-case。

## 第9条（references/）
`references/<topic>.md` または `references/<topic>.yaml`。
本文 100 行超のSkillは必須。

## 第10条（scripts/）
`scripts/<verb>-<object>.py` 形式。`.py` または `.sh` のみ。stdlib only。

## 第11条（examples/）
`examples/<scenario>.md`。完成例を1つ以上。

## 第12条（hooks/）
任意。`hooks/<event>.sh`。

## 第13条（フラットツリー）
`templates/sub/foo.md` のような2階層深いネストは原則禁止。深くする場合は別Skillに分割。

## 第14条（多言語）
description は英語。本文 は日本語可。frontmatter キーは英語固定。

## 第15条（改名）
破壊的変更。旧名は `aliases: [old-name]` で猶予期間最低14日。

## 第16条（禁則 prefix）
本番投入禁止: `test-`, `tmp-`, `wip-`, `experimental-`。
スクラッチ用は `.claude/skills/_scratch/` 配下のみ可。
