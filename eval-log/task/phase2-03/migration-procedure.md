# Phase2-03 per-plugin Migration Procedure

Generated at: 2026-05-20T14:45:00+09:00

Source plan: `eval-log/task/phase2-02/partition-plan.json`

## Purpose

This playbook freezes the repeatable per-plugin procedure used by Phase2-06 to move each partition under `plugins/<name>/` while keeping every intermediate state buildable.

## Preconditions

| ID | Requirement | Verification |
|---|---|---|
| PRE-1 | phase2-02 DoD is PASS | `eval-log/task/phase2-02/dod-verification.md` records DoD-1 through DoD-12 as PASS |
| PRE-2 | partition plan exists and is valid JSON | `python3 -m json.tool eval-log/task/phase2-02/partition-plan.json` |
| PRE-3 | proven plugin schema source exists | `test -f plugins/skill-creator/.claude-plugin/plugin.json` |
| PRE-4 | generated symlinks are stable before migration | `scripts/build-claude-symlinks.py --check` |
| PRE-5 | generated settings are stable before migration | `scripts/build-claude-settings.py --check` |

## Migration Order Criteria

1. Dependencies before dependents: every `depends_on` target from `partition-plan.json` must have a lower rank than the plugin that depends on it.
2. Depended-first: shared support plugins are introduced before orchestration plugins that consume them.
3. Responsibility class: non-skill governance assets use the stable order `adapter`, `hook`, `lint`, `migration`, `secrets`, `config`, `automation`.
4. Alphabetical fallback: if all prior criteria tie, sort by plugin name.

Frozen order: `eval-log/task/phase2-03/migration-order.json`.

## Intermediate Invariants

| ID | Invariant | Verification |
|---|---|---|
| INV-Mid-1 | After every plugin deployment, `scripts/build-claude-symlinks.py --check` exits 0. | Run after Step P-6 and Step P-9 |
| INV-Mid-2 | After every plugin deployment, `scripts/build-claude-settings.py --check` exits 0 and preserves INV-1 through INV-12. | Run after Step P-7 and Step P-9 |
| INV-Mid-3 | Files for plugins not yet deployed remain in their original `creator-kit/` or root locations. | Compare `partition-plan.json` undeployed file list with working tree |
| INV-Mid-4 | `.claude/settings.json` user-managed section hash does not change. | `scripts/build-claude-settings.py --print-user-section-hash` before and after |
| INV-Mid-5 | `plugins/skill-creator/` remains intact and its `.claude-plugin/plugin.json` stays valid. | `jq . plugins/skill-creator/.claude-plugin/plugin.json` |

## Per-plugin Playbook

### Step P-1. Resolve plugin record and freeze scope
verify: `python3 -c "import json; p=json.load(open('eval-log/task/phase2-02/partition-plan.json')); assert any(x['name']=='$PLUGIN' for x in p['partitions'])"`

Load the partition record for `$PLUGIN` from `partition-plan.json`. Record its `files`, `skills`, `agents`, `commands`, `hooks`, `depends_on`, and `external_ref_exceptions` into `eval-log/task/phase2-06/$PLUGIN/scope.json` before moving anything.

### Step P-2. Check dependency gate
verify: `python3 -c "import json; o=json.load(open('eval-log/task/phase2-03/migration-order.json'))['order']; r={x['plugin']:x['rank'] for x in o}; assert all(r[d] < r['$PLUGIN'] for x in o if x['plugin']=='$PLUGIN' for d in x['depends_on'])"`

Confirm every dependency has already been deployed or is the current plugin's preserved source path. Stop if a dependency rank is missing or greater than the current rank.

### Step P-3. Create plugin directory layout
verify: `test -d plugins/$PLUGIN/.claude-plugin`

Create `plugins/$PLUGIN/.claude-plugin` and only the subdirectories required by the partition record: `skills`, `agents`, `commands`, `hooks`, `scripts`, `config`, `references`, or other recorded file-kind roots.

### Step P-4. Move partition files into plugin root
verify: `python3 -c "import pathlib; assert pathlib.Path('plugins/$PLUGIN').exists()"`

Use `git mv` for each file listed in the partition record. Preserve relative paths below the plugin root, for example `scripts/foo.py` becomes `plugins/$PLUGIN/scripts/foo.py`. Do not move files belonging to undeployed plugins.

### Step P-5. Move partition skills, agents, commands, and hooks
verify: `find plugins/$PLUGIN -maxdepth 3 -type f | sort > eval-log/task/phase2-06/$PLUGIN/moved-files.txt`

Move each recorded skill from `creator-kit/skills/<skill>/` to `plugins/$PLUGIN/skills/<skill>/`, each agent to `plugins/$PLUGIN/agents/`, each command to `plugins/$PLUGIN/commands/`, and each hook to `plugins/$PLUGIN/hooks/`. Empty categories are skipped, not fabricated.

### Step P-6. Generate plugin.json from the frozen template
verify: `jq -e '.name == "'$PLUGIN'" and .version and .description and .keywords' plugins/$PLUGIN/.claude-plugin/plugin.json && ! grep -q '{{' plugins/$PLUGIN/.claude-plugin/plugin.json`

Copy `eval-log/task/phase2-03/plugin.json.template` to `plugins/$PLUGIN/.claude-plugin/plugin.json`, then substitute **all four placeholders** (`{{plugin_name}}`, `{{version}}`, `{{description}}`, `{{keywords}}`) using values from the partition record. The substitution must leave **zero** `{{...}}` tokens in the resulting file (verify with `! grep -q '{{' plugins/$PLUGIN/.claude-plugin/plugin.json`). Do **not** reuse the skill-creator description literal for other plugins.

### Step P-7. Run symlink build check
verify: `scripts/build-claude-symlinks.py --check`

The command must exit 0. If it reports conflict, restore the plugin from the pre-step record and resolve namespace collision before continuing.

### Step P-8. Run settings build check
verify: `scripts/build-claude-settings.py --check`

The command must exit 0. Record `--print-user-section-hash` before and after the deployment and fail if the hash changes.

### Step P-9. Validate plugin schema and write deployment evidence
verify: `test -f eval-log/task/phase2-06/$PLUGIN/deploy-result.json`

Run `claude plugin validate plugins/$PLUGIN` when available. If unavailable, record `claude_plugin_validate_available=false` and use `jq` schema validation plus build checks as the fallback. Write command outputs, hashes, moved-file list, rollback script path, and final invariant verdicts into `eval-log/task/phase2-06/$PLUGIN/deploy-result.json`.

## Rollback Requirement

For each plugin, Phase2-06 must generate `eval-log/task/phase2-06/$PLUGIN/rollback-$PLUGIN.sh` before Step P-4. The rollback script must restore moved files to their original paths, restore `.claude/settings.json` from the recorded pre-state when necessary, and pass `bash -n`.

## Required Per-plugin Evidence

| Evidence | Path |
|---|---|
| Scope snapshot | `eval-log/task/phase2-06/<plugin>/scope.json` |
| Pre user-section hash | `eval-log/task/phase2-06/<plugin>/settings-user.before.sha256` |
| Post user-section hash | `eval-log/task/phase2-06/<plugin>/settings-user.after.sha256` |
| Moved file list | `eval-log/task/phase2-06/<plugin>/moved-files.txt` |
| Rollback script | `eval-log/task/phase2-06/<plugin>/rollback-<plugin>.sh` |
| Final deployment result | `eval-log/task/phase2-06/<plugin>/deploy-result.json` |

## Completion Gate

The current plugin is complete only when all Step P-1 through Step P-9 verification commands pass and every `INV-Mid-*` invariant is recorded as PASS.
