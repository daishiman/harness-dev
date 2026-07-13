#!/usr/bin/env bash
# install-bundle.sh — install a named harness plugin bundle via claude CLI.
#
# Usage:
#   bash scripts/install-bundle.sh skills-full
#
# Reads .claude-plugin/bundles.json plus the marketplace name from
# .claude-plugin/marketplace.json and installs each exact plugin identity.
# for each plugin in the bundle. After a complete install, C01 applies and verifies
# the repo-owned Claude/Codex/.agents native settings from their common contract.
# Idempotent — already-installed plugins and no-diff settings are no-ops.
#
# CLI fallback for users who prefer terminal over /harness-creator:install-bundle slash command.

set -euo pipefail

BUNDLE="${1:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLES_FILE="$ROOT/.claude-plugin/bundles.json"
MARKETPLACE_FILE="$ROOT/.claude-plugin/marketplace.json"

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

if [[ ! -f "$MARKETPLACE_FILE" ]]; then
  echo "ERROR: $MARKETPLACE_FILE not found. Exact plugin identity cannot be resolved." >&2
  exit 3
fi

if ! MARKETPLACE=$(python3 -c 'import json,sys; value=json.load(open(sys.argv[1]))["name"]; assert isinstance(value,str) and value; print(value)' "$MARKETPLACE_FILE"); then
  echo "ERROR: marketplace name is missing or invalid in $MARKETPLACE_FILE" >&2
  exit 3
fi
if [[ ! "$MARKETPLACE" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ERROR: unsafe marketplace name in $MARKETPLACE_FILE: $MARKETPLACE" >&2
  exit 3
fi

if ! PLUGINS=$(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
bundle_name = sys.argv[2]
for b in d["bundles"]:
    if b["name"] == bundle_name:
        for p in b["plugins"]:
            print(p)
        sys.exit(0)
sys.exit(4)
' "$BUNDLES_FILE" "$BUNDLE"); then
  echo "ERROR: bundle '$BUNDLE' not found in $BUNDLES_FILE" >&2
  exit 4
fi

if [[ -z "$PLUGINS" ]]; then
  echo "ERROR: bundle '$BUNDLE' not found in $BUNDLES_FILE" >&2
  exit 4
fi

echo "Installing bundle '$BUNDLE':"
echo "$PLUGINS" | sed 's/^/  - /'
echo ""

FAILED=()
while IFS= read -r plugin; do
  echo "→ claude plugin install $plugin@$MARKETPLACE"
  if ! claude plugin install "$plugin@$MARKETPLACE"; then
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

SYNC_SCRIPT="$ROOT/plugins/harness-creator/scripts/sync-native-surfaces.py"
if [[ ! -f "$SYNC_SCRIPT" ]]; then
  echo "ERROR: native surface synchronizer not found: $SYNC_SCRIPT" >&2
  exit 6
fi

echo "→ applying repo-owned Claude/Codex/.agents settings"
python3 "$SYNC_SCRIPT" --repo-root "$ROOT" --apply
echo "→ verifying repo-owned Claude/Codex/.agents settings"
python3 "$SYNC_SCRIPT" --repo-root "$ROOT" --check
echo "OK: bundle and native settings are synchronized. Product hook trust remains user-gated."
