---
name: run-governance-adapters
description: governance出力adapterの利用可能性を確認したいとき、入出力契約と代替経路を安全に特定したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
effect: conversation-output
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-adapters
source-tier: internal
runtime_root_policy: host-skill-path
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 実在adapterだけを列挙しpath traversalを拒否したうえで選択adapterのhelpと入出力契約を実行前に確認している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: credentialや送信先を推測せず実行結果または未対応理由をexit codeとreceipt付きで報告している
      verify_by: evaluator
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
