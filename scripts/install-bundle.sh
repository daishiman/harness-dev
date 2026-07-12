#!/usr/bin/env bash
# install-bundle.sh — install a named harness plugin bundle via claude CLI.
#
# Usage:
#   bash scripts/install-bundle.sh harness-full
#
# Reads .claude-plugin/bundles.json and runs `claude plugin install <name>@harness`
# for each plugin in the bundle. Idempotent — already-installed plugins skip silently.
#
# CLI fallback for users who prefer terminal over /harness-creator:install-bundle slash command.

set -euo pipefail

BUNDLE="${1:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLES_FILE="$ROOT/.claude-plugin/bundles.json"

if [[ -z "$BUNDLE" ]]; then
  echo "Usage: $0 <bundle-name>" >&2
  echo "Available bundles:" >&2
  python3 -c "import json; d=json.load(open('$BUNDLES_FILE')); [print(f'  - {b[\"name\"]}: {b[\"description\"]}') for b in d['bundles']]" >&2
  exit 2
fi

if [[ ! -f "$BUNDLES_FILE" ]]; then
  echo "ERROR: $BUNDLES_FILE not found. Run from harness repository root." >&2
  exit 3
fi

PLUGINS=$(python3 -c "
import json, sys
d = json.load(open('$BUNDLES_FILE'))
for b in d['bundles']:
    if b['name'] == '$BUNDLE':
        for p in b['plugins']:
            print(p)
        sys.exit(0)
sys.exit(4)
")

if [[ -z "$PLUGINS" ]]; then
  echo "ERROR: bundle '$BUNDLE' not found in $BUNDLES_FILE" >&2
  exit 4
fi

echo "Installing bundle '$BUNDLE':"
echo "$PLUGINS" | sed 's/^/  - /'
echo ""

FAILED=()
while IFS= read -r plugin; do
  echo "→ claude plugin install $plugin@harness"
  if ! claude plugin install "$plugin@harness"; then
    FAILED+=("$plugin")
  fi
done <<< "$PLUGINS"

echo ""
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "OK: bundle '$BUNDLE' fully installed."
else
  echo "FAIL: ${#FAILED[@]} plugin(s) failed to install:" >&2
  printf '  - %s\n' "${FAILED[@]}" >&2
  exit 5
fi
