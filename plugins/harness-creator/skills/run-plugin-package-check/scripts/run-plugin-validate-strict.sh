#!/usr/bin/env bash
# PKG-001: claude plugin validate --strict ラッパー
# exit 0: pass / 1: fail / 2: claude CLI not found (skip 扱い)
set -euo pipefail

PLUGIN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin) PLUGIN="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$PLUGIN" ]]; then
  echo "error: --plugin required" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
PLUGIN_DIR="$REPO_ROOT/plugins/$PLUGIN"

if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "error: plugin not found: $PLUGIN_DIR" >&2
  exit 2
fi

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ! command -v claude >/dev/null 2>&1; then
  cat <<EOF
{
  "pkg_id": "PKG-001",
  "status": "skip",
  "skip_reason": "claude CLI not found in PATH",
  "last_run_at": "$NOW"
}
EOF
  exit 2
fi

OUTPUT_TMP="$(mktemp)"
if claude plugin validate --strict "$PLUGIN_DIR" >"$OUTPUT_TMP" 2>&1; then
  cat <<EOF
{
  "pkg_id": "PKG-001",
  "status": "pass",
  "last_run_at": "$NOW",
  "stdout": $(cat "$OUTPUT_TMP" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
}
EOF
  rm -f "$OUTPUT_TMP"
  exit 0
else
  if grep -q "unknown option '--strict'" "$OUTPUT_TMP"; then
    if claude plugin validate "$PLUGIN_DIR" >"$OUTPUT_TMP" 2>&1; then
      cat <<EOF
{
  "pkg_id": "PKG-001",
  "status": "pass",
  "last_run_at": "$NOW",
  "strict_fallback": "claude plugin validate --strict is not supported by this CLI; used claude plugin validate",
  "stdout": $(cat "$OUTPUT_TMP" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
}
EOF
      rm -f "$OUTPUT_TMP"
      exit 0
    fi
  fi
  cat <<EOF
{
  "pkg_id": "PKG-001",
  "status": "fail",
  "last_run_at": "$NOW",
  "stdout": $(cat "$OUTPUT_TMP" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
}
EOF
  rm -f "$OUTPUT_TMP"
  exit 1
fi
