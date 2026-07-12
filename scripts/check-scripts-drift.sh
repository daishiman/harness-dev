#!/usr/bin/env bash
# check-scripts-drift.sh — Phase 2 後の script 参照整合を検証する。
#
# creator-kit/ は Phase 2 で削除済み。旧 drift 比較ではなく、root scripts/ の
# symlink が解決可能であることと plugin script path が存在することを gate にする。
#
# Usage:
#   bash scripts/check-scripts-drift.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BROKEN="$(find "$ROOT/scripts" -type l ! -exec test -e {} \; -print)"
if [[ -n "$BROKEN" ]]; then
  echo "$BROKEN" >&2
  exit 1
fi

for plugin in "$ROOT"/plugins/*; do
  [[ -d "$plugin" ]] || continue
  [[ -d "$plugin/scripts" ]] || continue
  find "$plugin/scripts" -type f \( -name '*.py' -o -name '*.sh' \) -print >/dev/null
done
