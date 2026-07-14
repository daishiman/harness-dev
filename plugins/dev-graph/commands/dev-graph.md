---
name: dev-graph
description: dev-graph を操作したいとき、init/node/status/sync/spec/plan/requirements/render/decompose/next/worktree を正規 capability へ dispatch したいときに使う。
kind: command
version: 0.1.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C09
argument-hint: "<init|node|status|sync|spec|requirements|render|decompose|next|worktree> [args] | plan --feature-id ID --feature-context RELATIVE_JSON"
allowed-tools: [Read, Bash, Skill]
disable-model-invocation: false
---

# /dev-graph dispatcher

最初の token を verb として厳密に解釈する。未知 verb、依存 plugin/script 不在、root context 不正は候補一覧を返して停止し、近似実行しない。

| verb | dispatch |
|---|---|
| init | Skill `run-dev-graph-init` |
| node | Skill `run-dev-graph-node` |
| status | Skill `run-dev-graph-status` |
| sync | Skill `run-dev-graph-sync` |
| spec | Skill `run-dev-graph-system-spec` (system-spec-harness 引用) |
| plan | external Skill `run-system-dev-plan`。`--feature-id` と repo-relative `--feature-context` 必須 |
| requirements | Skill `run-dev-graph-requirements` |
| render | Skill `run-dev-graph-render` |
| decompose | Skill `run-dev-graph-decompose` (macro feature only) |
| next | Skill `run-dev-graph-schedule` |
| worktree | `scripts/manage-worktree-lease.py` |

`worktree` は `claim|heartbeat|park|release|list` だけを許可し、必ず `--repo-root "$CLAUDE_PROJECT_DIR"` を渡す。位置引数をscriptへそのまま渡さず、次の正準flagへ一度だけ変換する。

| public form | script form |
|---|---|
| `worktree list` | `manage-worktree-lease.py --op list` |
| `worktree claim <id> --branch <name> --session-id <session>` | `manage-worktree-lease.py --op claim --graph-node-id <id> --branch <name> --session-id <session>` |
| `worktree heartbeat <id> --session-id <session>` | `manage-worktree-lease.py --op heartbeat --graph-node-id <id> --session-id <session>` |
| `worktree park <id> --session-id <session>` | `manage-worktree-lease.py --op park --graph-node-id <id> --session-id <session>` |
| `worktree release <id> --session-id <session>` | `manage-worktree-lease.py --op release --graph-node-id <id> --session-id <session>` |

claim は graph node id、branch、session identity が必須。`plan` は大きな未分解構想を直接受けず、C14 が生成した ready feature を `--feature-id` と caller-repository 相対 JSON `--feature-context` で要求する。両者の id/digest が一致しなければ停止する。

引数は選択した Skill/script にそのまま引き継ぐが shell 文字列として再評価しない。dispatch 前に `resolve-repo-context.py --mode read` を実行する。
