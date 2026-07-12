#!/usr/bin/env bash
set -euo pipefail
cp eval-log/task/08/settings.before.json .claude/settings.json
rm -rf .claude/skills .claude/agents
mv eval-log/task/08/claude-skills.before .claude/skills
mv eval-log/task/08/claude-agents.before .claude/agents
rm -rf plugins/skill-creator
