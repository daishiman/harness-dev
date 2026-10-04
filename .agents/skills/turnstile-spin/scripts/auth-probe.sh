#!/usr/bin/env bash
# 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。
# Probes Cloudflare API auth state for the Turnstile Spin agent.
#
# Reads:
#   $CLOUDFLARE_API_TOKEN  (required)
#   $CLOUDFLARE_ACCOUNT_INDEX (optional; 1-based selection from masked candidates)
#   $CLOUDFLARE_ACCOUNT_ID (optional internal compatibility input; never display raw)
#
# Outputs JSON to stdout, always exits 0. The agent reads `status`:
#   "ok"                ; selected account passed the Turnstile scope probe
#   "missing_token"     ; no token set, or wrangler whoami failed
#   "wrong_token_type"  ; account-owned/global token cannot be used for Turnstile
#   "missing_scope"     ; user-owned token lacks Account.Turnstile:Edit
#   "multiple_accounts" ; token covers >1 accounts and no account selection is set
#   "account_mismatch"  ; $CLOUDFLARE_ACCOUNT_ID is set but is not in the token's accounts list
#
# Human-readable diagnostics go to stderr.

set -uo pipefail

script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=account-context.sh
# shellcheck disable=SC1091
. "$script_dir/account-context.sh"

emit() {
  echo "$1"
  exit 0
}

token="${CLOUDFLARE_API_TOKEN:-}"
declared_account="${CLOUDFLARE_ACCOUNT_ID:-}"
declared_index="${CLOUDFLARE_ACCOUNT_INDEX:-}"

mask_id() {
  local value="$1"
  if [ "${#value}" -ge 8 ]; then
    printf '%s…%s' "${value:0:4}" "${value: -4}"
  else
    printf '****'
  fi
}

if [ -z "$token" ]; then
  echo "auth-probe: \$CLOUDFLARE_API_TOKEN is not set." >&2
  emit '{"status":"missing_token","reason":"no_env_var"}'
fi

case "$token" in
  cfat_*)
    echo "auth-probe: Account API TokenはTurnstile非対応です。Turnstile専用のUser API Tokenを使ってください。" >&2
    emit '{"status":"wrong_token_type","reason":"account_token_not_supported"}'
    ;;
  cfk_*)
    echo "auth-probe: Global API Keyは使用しません。Turnstile専用のUser API Tokenを使ってください。" >&2
    emit '{"status":"wrong_token_type","reason":"global_key_not_allowed"}'
    ;;
  cfut_*)
    # Current User API Token format. Continue to the scope probe.
    ;;
  *)
    # Unprefixed legacy user tokens remain valid and are verified below.
    ;;
esac

whoami_json=$(turnstile_run_wrangler_whoami 2>/dev/null || true)
if [ -z "$whoami_json" ] || [ "$(echo "$whoami_json" | head -c 1)" != "{" ]; then
  echo "auth-probe: project-local wrangler whoami returned no JSON. Token may be invalid, expired, or wrangler may be unavailable." >&2
  emit '{"status":"missing_token","reason":"whoami_failed"}'
fi

accounts_json=$(echo "$whoami_json" | (jq -c '.accounts' 2>/dev/null || python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['accounts']))"))
account_count=$(echo "$accounts_json" | (jq 'length' 2>/dev/null || python3 -c "import sys,json; print(len(json.load(sys.stdin)))"))
account_candidates=$(echo "$accounts_json" | (
  jq -c 'to_entries | map({index:(.key + 1), name:(.value.name // "Account"), masked_id:((.value.id[0:4]) + "…" + (.value.id[-4:]))})' 2>/dev/null ||
  python3 -c 'import sys,json; accounts=json.load(sys.stdin); print(json.dumps([{"index":i+1,"name":a.get("name","Account"),"masked_id":a.get("id","")[:4]+"…"+a.get("id","")[-4:]} for i,a in enumerate(accounts)]))'
))

if [ -z "$account_count" ] || [ "$account_count" = "0" ] || [ "$account_count" = "null" ]; then
  echo "auth-probe: wrangler whoami succeeded but no accounts found on the token." >&2
  emit '{"status":"missing_token","reason":"no_accounts"}'
fi

if [ -n "$declared_account" ]; then
  in_list=$(echo "$accounts_json" | (jq --arg id "$declared_account" 'map(.id) | index($id) != null' 2>/dev/null || python3 -c "import sys,json; print('true' if any(a['id']==sys.argv[1] for a in json.load(sys.stdin)) else 'false')" "$declared_account"))
  if [ "$in_list" != "true" ]; then
    declared_masked=$(mask_id "$declared_account")
    echo "auth-probe: the masked CLOUDFLARE_ACCOUNT_ID ($declared_masked) is not one of the token's accounts." >&2
    emit "{\"status\":\"account_mismatch\",\"declared_masked\":\"$declared_masked\",\"account_candidates\":$account_candidates}"
  fi
  account_id="$declared_account"
  account_index=$(echo "$accounts_json" | (jq --arg id "$declared_account" 'to_entries | map(select(.value.id == $id))[0].key + 1' 2>/dev/null || python3 -c "import sys,json; print(next(i+1 for i,a in enumerate(json.load(sys.stdin)) if a['id']==sys.argv[1]))" "$declared_account"))
elif [ -n "$declared_index" ]; then
  case "$declared_index" in
    *[!0-9]*|0)
      echo "auth-probe: CLOUDFLARE_ACCOUNT_INDEX must be a 1-based candidate number." >&2
      emit "{\"status\":\"account_mismatch\",\"declared_index\":\"$declared_index\",\"account_candidates\":$account_candidates}"
      ;;
  esac
  if [ "$declared_index" -gt "$account_count" ]; then
    echo "auth-probe: CLOUDFLARE_ACCOUNT_INDEX is outside the candidate range." >&2
    emit "{\"status\":\"account_mismatch\",\"declared_index\":\"$declared_index\",\"account_candidates\":$account_candidates}"
  fi
  account_index="$declared_index"
  account_id=$(echo "$accounts_json" | (jq -r --argjson index "$declared_index" '.[$index - 1].id' 2>/dev/null || python3 -c "import sys,json; print(json.load(sys.stdin)[int(sys.argv[1])-1]['id'])" "$declared_index"))
elif [ "$account_count" = "1" ]; then
  account_id=$(echo "$accounts_json" | (jq -r '.[0].id' 2>/dev/null || python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])"))
  account_index=1
else
  echo "auth-probe: token covers $account_count accounts; present only the masked candidates and re-run with CLOUDFLARE_ACCOUNT_INDEX." >&2
  emit "{\"status\":\"multiple_accounts\",\"account_candidates\":$account_candidates}"
fi

selected_name=$(echo "$accounts_json" | (jq -r --argjson index "$account_index" '.[$index - 1].name // "Account"' 2>/dev/null || python3 -c "import sys,json; print(json.load(sys.stdin)[int(sys.argv[1])-1].get('name','Account'))" "$account_index"))
masked_account_id=$(mask_id "$account_id")

# Probe Turnstile scope on the selected account.
tmp=$(mktemp)
http_code=$(curl -sS -w "%{http_code}" -o "$tmp" \
  "https://api.cloudflare.com/client/v4/accounts/$account_id/challenges/widgets" \
  -H "Authorization: Bearer $token" 2>/dev/null || echo "000")
body=$(cat "$tmp"); rm -f "$tmp"
success=$(echo "$body" | (jq -r '.success' 2>/dev/null || echo "false"))

if [ "$success" != "true" ]; then
  echo "auth-probe: token cannot read /challenges/widgets on account $masked_account_id (HTTP $http_code). Missing Account.Turnstile:Edit." >&2
  emit "{\"status\":\"missing_scope\",\"account_index\":$account_index,\"account_name\":$(printf '%s' "$selected_name" | (jq -Rs . 2>/dev/null || python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')),\"masked_account_id\":\"$masked_account_id\",\"http_code\":$http_code}"
fi

emit "{\"status\":\"ok\",\"account_index\":$account_index,\"account_name\":$(printf '%s' "$selected_name" | (jq -Rs . 2>/dev/null || python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')),\"masked_account_id\":\"$masked_account_id\"}"
