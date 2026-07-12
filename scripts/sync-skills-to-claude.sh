#!/usr/bin/env bash
# sync-skills-to-claude.sh — plugin skills を正本として .claude/skills/ に同期する。
#
# Phase 2 後は scripts/build-claude-symlinks.py が正規の生成器である。
#
# Usage:
#   bash scripts/sync-skills-to-claude.sh [--check|--apply]
#     --check  : 差分があれば exit 1 (CI gate 用)
#     --apply  : .claude/skills/ を plugins/*/skills/ に合わせて更新 (default)

set -euo pipefail

MODE="${1:---apply}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$MODE" in
  --check)
    python3 "$ROOT/scripts/build-claude-symlinks.py" --plugins-dir "$ROOT/plugins" --target-dir "$ROOT/.claude" --check
    ;;
  --apply)
    python3 "$ROOT/scripts/build-claude-symlinks.py" --plugins-dir "$ROOT/plugins" --target-dir "$ROOT/.claude"
    ;;
  *)
    echo "Usage: $0 [--check|--apply]" >&2
    exit 2
    ;;
esac
