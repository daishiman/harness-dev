---
# Command Skeleton (kind: command)
#
# CapabilityManifest schema: definitions/kindCommand
# 用途: SlashCommand (commands/*.md) frontmatter。
# 規約: command は薄いラッパ。通常は実体ロジックを entrypoint で指す Skill に置く。
# 例外: セットアップ doctor など「スキルではなく同梱 script を直接叩く」command は
# entrypoint を空にし、実行コードを fallback 形
# `${CLAUDE_PLUGIN_ROOT:-plugins/<plugin-name>}/...` で書く。script 自体は
# `$CLAUDE_PLUGIN_ROOT` に依存せず `__file__` 相対で plugin root / lib を自己解決する。
# 書式は install-bundle.md 等の既存 command に準拠。
#
# TODO: build-skill が以下プレースホルダを置換する
#   {{CAPABILITY_NAME}}    command 名 (kebab-case, slash 後の identifier)
#   {{OWNER}}              governance 担当
#   {{ARGUMENT_HINT}}      /{{name}} <hint> の <hint>
#   {{ALLOWED_TOOLS_JSON}} ["Read", "Bash(git *)", ...]
#   {{ENTRYPOINT_SKILL}}   実体ロジックを持つ Skill name。direct-script command は空/N/A。
---
name: {{CAPABILITY_NAME}}
description: {{TRIGGERS}}
kind: command
version: 0.1.0
owner: {{OWNER}}
since: {{DATE}}
argument-hint: {{ARGUMENT_HINT}}
allowed-tools: {{ALLOWED_TOOLS_JSON}}
entrypoint: {{ENTRYPOINT_SKILL}}
contract:
  intent: {{COMMAND_INTENT}}
  interface:
    args: {{ARGS_SCHEMA}}
    delegates_to: {{ENTRYPOINT_SKILL}}
  invariant:
    - command 自体にビジネスロジックを書かない (entrypoint または同梱 script へ委譲)
    - allowed-tools を最小集合に保つ
    - direct-script command は README の一次導線に裸 $CLAUDE_PLUGIN_ROOT を出さず、bash 例は fallback 形 `${CLAUDE_PLUGIN_ROOT:-plugins/<plugin-name>}` にする
    - direct-script command の同梱 script は `$CLAUDE_PLUGIN_ROOT` 未設定でも `__file__` 相対で自己解決する
---

# /{{CAPABILITY_NAME}}

## 振る舞い
本コマンドは `{{ENTRYPOINT_SKILL}}` を起動する薄いラッパである。
direct-script 型の場合は、同梱 script を実行するだけに留め、判定ロジックは script 側へ置く。
{{BEHAVIOR_SUMMARY}}

## 引数
- `{{ARGUMENT_HINT}}`: {{ARG_DESCRIPTION}}
- 省略時: {{ARG_DEFAULT_BEHAVIOR}}

## 実行フロー
1. 引数 `{{ARGUMENT_HINT}}` を parse する
2. `{{ENTRYPOINT_SKILL}}` に payload を渡して起動する。direct-script 型は fallback 形の script path を Bash で実行する
3. 結果を user に提示する

## 失敗時
- 引数 parse error: usage を表示し exit
- entrypoint skill が存在しない: 設定ミスを通知
- {{ADDITIONAL_FAILURE_CASE}}

## 注意
- 本 command は副作用を伴う可能性がある。`permissions.deny` で破壊的操作を静的に禁止すること
- allowed-tools に列挙していないツールは entrypoint からも呼べない
- セットアップ疎通確認 command は `ref-cross-platform-runtime/references/runtime-portability.md` 層2に従い、doctor script + README チャット委譲 + `scripts/lint-readme-plugin-root-portability.py` exit0 を満たすこと
- {{ADDITIONAL_NOTE}}
