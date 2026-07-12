#!/usr/bin/env bash
# post-publish-notify.sh
#
# Notion 公開成功直後に Slack incoming webhook へ最小ペイロードを通知する。
# Slack 責務を agent から hook に降ろし、permissions.deny と二段防御する。
#
# 前提:
#   - output/<hint>/notion-url.txt が存在する（公開済み）
#   - Slack Webhook URL は macOS Keychain に登録済み
#       service: slack-incoming-webhook
#       account: skill-intake
#   - Webhook 取得は scripts/keychain_get_secret.py 経由（security 直叩きは禁止）
#
# 動作モード:
#   - Webhook 未登録 (KEYCHAIN_NOT_FOUND): silent skip, exit 0
#   - Webhook 取得失敗 (その他): stderr に WARN 出力, exit 0 (公開フローは止めない)
#   - 通知成功: exit 0
#
# セキュリティ:
#   - Webhook URL を stdout に出さない (debug 出力は stderr のみ、URL は伏字)
#   - ペイロードは text 1行のみ。サマリ本文は含めない
#
# 終了コード:
#   0 = 正常 (通知成功 / silent skip / 非致命警告)
#   2 = 入力不正 (notion-url.txt が無いなど)
set -euo pipefail

HINT="${1:-}"
OUTPUT_ROOT="${INTAKE_OUTPUT_ROOT:-output}"

if [[ -z "$HINT" ]]; then
  # hint が省略された場合は output/ 配下の最新ディレクトリを探す
  if [[ -d "$OUTPUT_ROOT" ]]; then
    HINT=$(ls -1t "$OUTPUT_ROOT" 2>/dev/null | head -n1 || true)
  fi
fi

if [[ -z "$HINT" ]]; then
  echo "[post-publish-notify] skip: hint が解決できません" >&2
  exit 0
fi

URL_FILE="$OUTPUT_ROOT/$HINT/notion-url.txt"
if [[ ! -f "$URL_FILE" ]]; then
  echo "[post-publish-notify] skip: $URL_FILE が見つかりません" >&2
  exit 0
fi

NOTION_URL=$(tr -d '\n\r' < "$URL_FILE")
if [[ -z "$NOTION_URL" ]]; then
  echo "[post-publish-notify] skip: notion-url.txt が空" >&2
  exit 0
fi

# Webhook を keychain_get_secret.py 経由で取得。security 直叩きは行わない。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYCHAIN_PY="$SCRIPT_DIR/../scripts/keychain_get_secret.py"
SERVICE="${INTAKE_SLACK_KEYCHAIN_SERVICE:-slack-incoming-webhook}"
ACCOUNT="${INTAKE_SLACK_KEYCHAIN_ACCOUNT:-harness}"

if [[ ! -f "$KEYCHAIN_PY" ]]; then
  echo "[post-publish-notify] WARN: keychain_get_secret.py が見つからない: $KEYCHAIN_PY" >&2
  exit 0
fi

set +e
WEBHOOK=$(python3 "$KEYCHAIN_PY" --service "$SERVICE" --account "$ACCOUNT" --print-unsafe 2>/dev/null)
RC=$?
set -e

if [[ $RC -ne 0 || -z "$WEBHOOK" ]]; then
  # Keychain 未登録は silent skip (no-op)。Webhook 設定は任意機能。
  echo "[post-publish-notify] silent skip: webhook 未登録 (service=$SERVICE account=$ACCOUNT)" >&2
  exit 0
fi

# Webhook URL の形式チェック (https のみ許可、URL 本体は表示しない)
if [[ "$WEBHOOK" != https://* ]]; then
  echo "[post-publish-notify] WARN: webhook が https で始まらない。送信中止。" >&2
  exit 0
fi

PAYLOAD=$(printf '{"text":"intake published: %s -> %s"}' "$HINT" "$NOTION_URL")

set +e
HTTP_CODE=$(curl -sS -o /dev/null -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' \
  --data "$PAYLOAD" \
  "$WEBHOOK")
CURL_RC=$?
set -e

if [[ $CURL_RC -ne 0 ]]; then
  echo "[post-publish-notify] WARN: curl 失敗 (rc=$CURL_RC)" >&2
  exit 0
fi

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "[post-publish-notify] WARN: Slack 応答 HTTP $HTTP_CODE" >&2
  exit 0
fi

echo "[post-publish-notify] OK: Slack 通知送信 (hint=$HINT)" >&2
exit 0
