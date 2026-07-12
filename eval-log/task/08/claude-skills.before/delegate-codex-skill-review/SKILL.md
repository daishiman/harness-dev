---
name: delegate-codex-skill-review
description: 自セッションで評価せず外部LLMに委譲したいとき、Sycophancyを避けたいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools:
  - Read
  - Bash(codex *)
kind: delegate
effect: external-mutation
delegate_agent: codex-cli
owner: team-platform
since: 2026-05-18
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
hierarchy_level: L1
# delegate-* prefix の最小実例。Skill レビューを外部 codex CLI に委譲する。
---

# delegate-codex-skill-review

## Purpose & Output Contract

評価対象 Skill (SKILL.md) を外部 `codex` CLI に渡し、Sycophancy を避けた第三者レビューを得る。

**入力**: target_skill_path (SKILL.md への絶対パス)
**出力**: `eval-log/delegate-codex-<timestamp>.json` (codex の review コメント)

**完了条件**: codex CLI が exit 0 で返り、JSON が書き出されている。

## Key Rules

1. **委譲先固定**: `delegate_agent: codex-cli` を frontmatter で宣言。
2. **入力のみ転送**: SKILL.md 本文と rubric を渡すが、自セッションで採点しない。
3. **結果は読み取り専用**: codex の返答を加工・反論せず、そのまま eval-log/ に保存。

## Steps

### Step 0: codex 存在確認 (決定論)

```bash
bash creator-kit/skills/delegate-codex-skill-review/scripts/check-codex-installed.sh
```
exit 2 が返ったら BLOCK。インストール手順を案内して停止。

### Step 1: target 検証

`target_skill_path` が存在し SKILL.md であることを確認。

### Step 2: codex 起動

```bash
codex review --input "$TARGET_PATH" --rubric creator-kit/skills/ref-skill-design-rubric/rubric.json \
  > eval-log/delegate-codex-$(date +%s).json
```

### Step 3: 結果提示

書き出した JSON のサマリをユーザーに返す。修正判断は委ねる。

## Gotchas

- **委譲結果を再評価しない**: 自セッションでスコア改竄をしない (09章 Sycophancy 防止)。
- **codex 未インストール時**: BLOCK して installation 手順を案内。
- **L1 階層**: codex CLI 抽象 (L1)。プロジェクト固有の review 観点は L2 で wrap する。

## Additional Resources

- 設計書: `06-classification-and-naming.md` (delegate-* prefix), `09-evaluation-orchestration.md`
- 委譲先: codex CLI (https://github.com/openai/codex 等、要別途インストール)
