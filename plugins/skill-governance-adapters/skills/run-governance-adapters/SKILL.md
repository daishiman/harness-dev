---
name: run-governance-adapters
description: governance出力adapterを選択し、利用可能性と入出力契約を安全に確認したいときに使う。
allowed-tools: Bash, Read, Glob
runtime_root_policy: host-skill-path
---

# run-governance-adapters

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

`scripts/adapters/`のadapterを列挙し、選択したadapterのhelpと契約を確認してから明示入力で実行する。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- adapter名を実在一覧から選び、path traversalを許可しない。
- credentialや送信先を推測しない。外部書込はユーザー確認後だけ行う。

## ゴールシーク実行

対象adapter、入力、期待出力、dry-run可否を確定し、`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/adapters/<adapter>.py" --help`で契約を確認する。未解決入力がなくなった場合だけ実行する。

## 検証

exit codeと生成receiptを報告し、未対応adapterは理由付きで停止する。
