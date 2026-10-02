#!/usr/bin/env bash
set -euo pipefail
set +x

PROJECT="$(pwd)"
ENVIRONMENT=""
WORKER_NAME=""
ROTATE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --env) ENVIRONMENT="$2"; shift 2 ;;
    --name) WORKER_NAME="$2"; shift 2 ;;
    --rotate) ROTATE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "不明な引数: $1" >&2; exit 2 ;;
  esac
done

cd "$PROJECT"
if [[ ! -f wrangler.jsonc && ! -f wrangler.json && ! -f wrangler.toml ]]; then
  echo "Wrangler設定が見つかりません: $PROJECT" >&2
  exit 2
fi
command -v node >/dev/null || { echo "nodeが必要です" >&2; exit 2; }
command -v openssl >/dev/null || { echo "opensslが必要です" >&2; exit 2; }

WRANGLER=(npx wrangler)
COMMON=()
[[ -n "$ENVIRONMENT" ]] && COMMON+=(--env "$ENVIRONMENT")
[[ -n "$WORKER_NAME" ]] && COMMON+=(--name "$WORKER_NAME")

echo "Cloudflare認証状態を確認します。Secret値は表示しません。"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] npx wrangler whoami"
  echo "[dry-run] BETTER_AUTH_SECRETは未登録時のみ自動生成"
  echo "[dry-run] GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRETは未登録時のみ対話入力"
  exit 0
fi

"${WRANGLER[@]}" whoami >/dev/null
SECRET_LIST=$("${WRANGLER[@]}" secret list "${COMMON[@]}" --format json 2>/dev/null || printf '[]')

has_secret() {
  SECRET_LIST_JSON="$SECRET_LIST" node -e '
    const key = process.argv[1];
    let rows = [];
    try { rows = JSON.parse(process.env.SECRET_LIST_JSON || "[]"); } catch {}
    process.exit(rows.some((row) => row && row.name === key) ? 0 : 1);
  ' "$1"
}

put_generated_secret() {
  local key="$1"
  if [[ $ROTATE -eq 0 ]] && has_secret "$key"; then
    echo "✓ $key は登録済み（変更しません）"
    return
  fi
  echo "→ $key を安全に生成して登録します（値は表示しません）"
  openssl rand -base64 48 | "${WRANGLER[@]}" secret put "$key" "${COMMON[@]}"
}

put_interactive_secret() {
  local key="$1"
  if [[ $ROTATE -eq 0 ]] && has_secret "$key"; then
    echo "✓ $key は登録済み（変更しません）"
    return
  fi
  echo "→ $key をWranglerの非表示プロンプトへ貼り付けてください"
  "${WRANGLER[@]}" secret put "$key" "${COMMON[@]}"
}

echo "注意: wrangler secret put はWorkerの新しいversionを作成し、直ちに反映します。"
put_generated_secret BETTER_AUTH_SECRET
put_interactive_secret GOOGLE_CLIENT_ID
put_interactive_secret GOOGLE_CLIENT_SECRET

echo "登録されたSecret名を確認します（値は表示されません）。"
"${WRANGLER[@]}" secret list "${COMMON[@]}" --format pretty
echo "完了: BETTER_AUTH_SECRET / GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET"
