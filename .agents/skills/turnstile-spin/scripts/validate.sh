#!/usr/bin/env bash
# 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。
# Validates a Turnstile siteverify integration end-to-end.
#
# Reads:
#   $TURNSTILE_SECRET      (required for the dummy-token check)
#   $CLOUDFLARE_API_TOKEN  (optional — when set, also runs the widget-domains
#                           sanity check; when unset, that check is skipped
#                           so the post-dashboard flow can validate without
#                           a manually-created token)
#
# Args:
#   --account-index <number>      Masked candidate number from auth-probe
#   --sitekey <key>               Widget sitekey
#   --expected-domains <a,b,c>    Comma-separated domains that must appear in the widget's domains array
#
# Outputs JSON. Exit 0 if all checks pass, 1 otherwise.
#   ok:    {"status":"ok","hostname_check":"ran"|"skipped"}
#   fail:  {"status":"error","check":"dummy_siteverify|hostname","detail":"<msg>"}

set -uo pipefail

script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=account-context.sh
# shellcheck disable=SC1091
. "$script_dir/account-context.sh"

ACCOUNT_INDEX="${CLOUDFLARE_ACCOUNT_INDEX:-}"
SITEKEY=""
EXPECTED_DOMAINS=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --account-index)    ACCOUNT_INDEX="$2"; shift 2 ;;
    --sitekey)          SITEKEY="$2"; shift 2 ;;
    --expected-domains) EXPECTED_DOMAINS="$2"; shift 2 ;;
    *) echo "validate: unknown arg $1" >&2; exit 2 ;;
  esac
done

: "${TURNSTILE_SECRET:?TURNSTILE_SECRET must be set (the secret captured in Step 8)}"
: "${SITEKEY:?--sitekey required}"

# Check 1: dummy-token siteverify against challenges.cloudflare.com.
# A valid secret + dummy token returns success:false with
# error-codes:["invalid-input-response"]. That confirms the secret is
# correctly bound to the widget; anything else is a real misconfiguration.
dummy=$(curl -sS -X POST "https://challenges.cloudflare.com/turnstile/v0/siteverify" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "secret=${TURNSTILE_SECRET}" \
  --data-urlencode "response=XXXX.DUMMY.TOKEN.XXXX" 2>/dev/null || echo "")

success=$(echo "$dummy" | (jq -r '.success // "missing"' 2>/dev/null || echo "missing"))
codes=$(echo "$dummy" | (jq -r '.["error-codes"] // [] | join(",")' 2>/dev/null || echo ""))

if [ "$success" != "false" ]; then
  echo "validate: siteverify returned unexpected shape for a dummy token: $dummy" >&2
  echo "{\"status\":\"error\",\"check\":\"dummy_siteverify\",\"detail\":\"expected success:false on a dummy token\"}"
  exit 1
fi

case ",$codes," in
  *,invalid-input-secret,*)
    echo "validate: siteverify rejected the secret. TURNSTILE_SECRET does not match the widget's secret." >&2
    echo "{\"status\":\"error\",\"check\":\"dummy_siteverify\",\"detail\":\"invalid-input-secret\"}"
    exit 1
    ;;
  *,invalid-input-response,*)
    : # Expected. Continue.
    ;;
  *)
    echo "validate: unexpected error codes from siteverify: $codes" >&2
    echo "{\"status\":\"error\",\"check\":\"dummy_siteverify\",\"detail\":\"unexpected codes: $codes\"}"
    exit 1
    ;;
esac

# Check 2: hostname / widget domains registered. Optional — requires a
# Cloudflare API token. When the token isn't available (e.g. post-dashboard
# success-card flow), skip this check and report `hostname_check: skipped`.
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ] || [ -z "$ACCOUNT_INDEX" ] || [ -z "$EXPECTED_DOMAINS" ]; then
  echo "validate: skipping hostname check (CLOUDFLARE_API_TOKEN, --account-index, or --expected-domains not provided)" >&2
  echo '{"status":"ok","hostname_check":"skipped"}'
  exit 0
fi

if ! turnstile_require_user_api_token; then
  echo "validate: hostname確認にはTurnstile専用User API Tokenを使ってください。" >&2
  echo '{"status":"error","check":"hostname","detail":"unsupported token type"}'
  exit 1
fi

if ! turnstile_resolve_account "$ACCOUNT_INDEX"; then
  echo "validate: Account候補番号を解決できません。auth-probeを再実行してください。" >&2
  echo '{"status":"error","check":"hostname","detail":"account selection unavailable"}'
  exit 1
fi
ACCOUNT_ID="$TURNSTILE_ACCOUNT_ID"

widget=$(curl -sS \
  "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/challenges/widgets/$SITEKEY" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" 2>/dev/null)
registered=$(echo "$widget" | (jq -r '.result.domains[]' 2>/dev/null || python3 -c "import sys,json; [print(d) for d in json.load(sys.stdin)['result']['domains']]"))

missing=""
IFS=',' read -ra DOMS <<< "$EXPECTED_DOMAINS"
for d in "${DOMS[@]}"; do
  if ! echo "$registered" | grep -qFx "$d"; then
    missing="${missing}${d} "
  fi
done

if [ -n "$missing" ]; then
  echo "validate: hostname check failed; domains not on widget: $missing" >&2
  echo "{\"status\":\"error\",\"check\":\"hostname\",\"detail\":\"missing domains: ${missing% }\"}"
  exit 1
fi

echo '{"status":"ok","hostname_check":"ran"}'
