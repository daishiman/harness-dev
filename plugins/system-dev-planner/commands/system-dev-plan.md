---
description: caller repositoryを初期化したいとき、明示した1 featureからexact 13 system development tasksを生成・検証・promotionしたいときに使う。
argument-hint: "init [--repo-root DIR] [--config PATH] | plan --feature-id ID --feature-context RELATIVE_JSON [--repo-root DIR] [--config PATH]"
allowed-tools: Read, Bash(python3 *), Skill
entrypoint: run-system-dev-plan
name: system-dev-plan
kind: command
version: 0.1.0
owner: team-platform
---

# /system-dev-plan

`$ARGUMENTS` の先頭を `init|plan` として解釈する。それ以外や引数欠落は usage を表示し停止する。

- `init`: `python3 $CLAUDE_PLUGIN_ROOT/scripts/init-project-layout.py` へ `--repo-root` / `--config` を渡す。
- `plan`: `--feature-id` と repo-relative `--feature-context` を必須とし、`run-system-dev-plan` Skill へそのまま渡す。どちらか欠落、feature id 不一致、absolute/traversal path は停止する。C09/C08/C13/C14 を迂回しない。

`init` には feature 引数を要求しない。`plan` の absolute/traversal path を自前で正規化して通さず、必ず下流の C09 に判定させる。
