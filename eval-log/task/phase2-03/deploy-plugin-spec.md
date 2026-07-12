# Phase2 deploy-plugin CLI Specification

Generated at: 2026-05-20T14:45:00+09:00

## Command

`scripts/phase2/deploy-plugin.sh <plugin-name>`

## Purpose

Deploy exactly one plugin from the Phase2 partition plan into `plugins/<plugin-name>/` using the frozen per-plugin playbook in `eval-log/task/phase2-03/migration-procedure.md`.

## Arguments

| Argument | Required | Description |
|---|---:|---|
| `$1 = plugin-name` | yes | Name must exist in `eval-log/task/phase2-02/partition-plan.json` and `eval-log/task/phase2-03/migration-order.json`. |

No additional positional arguments are part of the frozen contract.

## Inputs

| Path | Role |
|---|---|
| `eval-log/task/phase2-02/partition-plan.json` | Source of plugin membership and dependencies |
| `eval-log/task/phase2-03/migration-order.json` | Frozen deployment order |
| `eval-log/task/phase2-03/plugin.json.template` | Source template for `plugins/<plugin-name>/.claude-plugin/plugin.json` |
| `eval-log/task/phase2-03/migration-procedure.md` | Step P-1 through P-9 playbook |

## Outputs

All plugin-specific evidence must be written under `eval-log/task/phase2-06/<plugin-name>/`.

| Output | Required | Description |
|---|---:|---|
| `scope.json` | yes | Frozen partition record before file moves |
| `settings-user.before.sha256` | yes | User section hash before deployment |
| `settings-user.after.sha256` | yes | User section hash after deployment |
| `moved-files.txt` | yes | Sorted list of files moved into the plugin |
| `rollback-<plugin-name>.sh` | yes | Rollback script generated before any `git mv` |
| `deploy-result.json` | yes | Final command outputs, invariant results, and validation status |

## Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Success; all Step P-1 through P-9 checks and `INV-Mid-*` invariants passed |
| 1 | Verification failure, including symlink drift, settings drift, schema failure, or missing evidence |
| 2 | Configuration or ordering inconsistency, including unknown plugin, dependency gate failure, invalid partition plan, or user-section hash drift |

## stdout Contract

stdout must emit one progress line per step:

```text
[P-1] resolve-scope: PASS
[P-2] dependency-gate: PASS
[P-3] create-layout: PASS
[P-4] move-files: PASS
[P-5] move-assets: PASS
[P-6] plugin-json: PASS
[P-7] symlink-check: PASS
[P-8] settings-check: PASS
[P-9] evidence: PASS
```

Failures must include the failed step id and a short reason on stdout or stderr.

## Invariants

The script must enforce `INV-Mid-1` through `INV-Mid-5` from `migration-procedure.md` for the deployed plugin and record the result in `deploy-result.json`.

## Non-goals

The script does not delete legacy files for undeployed plugins, does not prune `creator-kit/`, and does not publish or install marketplace plugins.
