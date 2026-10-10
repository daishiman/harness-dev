---
name: ubm-journal
description: 今日の振り返りを会話しながら日次ジャーナルを作成したいときに使う。
argument-hint: "[YYYY-MM-DD]"
allowed-tools: Read, Bash, Skill
disable-model-invocation: false
kind: command
version: 0.1.0
owner: harness-maintainers
---

# 日次ジャーナル作成

その日やったことを会話で振り返り、`02_Configs/Daily/{YYYY-MM-DD}.md` へ構造化された
ジャーナルを生成する入口コマンド。通し番号は `Daily/` 配下の既存ジャーナルの最大値から自動で +1 される（前回ファイル+1 ではない。欠番があっても番号は重複しない）。同じ日のジャーナルが既にあるときは作り直し（regenerate）になり、番号はそのまま維持する。番号はスキルの `build-journal-context.py` が決める。

## 実行

`run-ubm-journal` スキルを `Skill` ツールで起動し、その指示に従って実行する。

- 引数 `$ARGUMENTS` に `YYYY-MM-DD` が指定されていればその日を対象日にする。
- 引数がなければ今日を対象日にする（ファイル名の日付＝見出しの日付＝振り返る日）。

## 引数

- `YYYY-MM-DD`: 振り返る対象日を明示する（前日分を書く場合など）
- 引数なし: 今日分を作成する

## 会話の進め方（スキル側で強制）

会話の進め方は `run-ubm-journal` が持ち、本コマンドには写さない。開き方と目標4階層・残日数の自動の埋め方は同スキルの「Phase1-3: 対話」、1ターンの問いの数・掘る順番・固有名詞の拾い方は同スキルの `references/interview-map.md` が正本。
