#!/usr/bin/env bash
# post-keychain-add.sh
#
# Keychain 登録直後に `security find-generic-password` で取得可否を検証する確認スクリプト。
# 配線: SessionStart hook ではなく、Keychain 登録時にユーザーが手動実行することを想定。
#
# 使い方:
#   bash plugins/skill-intake/hooks/post-keychain-add.sh
#
# 終了コード:
#   0 = 取得成功 (空でない文字列が返る)
#   1 = 取得失敗
set -euo pipefail

: "${HARNESS_KEYCHAIN_PREFIX:?HARNESS_KEYCHAIN_PREFIX is required}"
SERVICE="${INTAKE_KEYCHAIN_SERVICE:-notion-api-key.${HARNESS_KEYCHAIN_PREFIX}}"
ACCOUNT="${INTAKE_KEYCHAIN_ACCOUNT:-${HARNESS_KEYCHAIN_PREFIX}}"

echo "[skill-intake] Keychain 取得テスト: service=$SERVICE, account=$ACCOUNT"

if ! command -v security >/dev/null 2>&1; then
  echo "FAIL: /usr/bin/security が見つかりません。macOS でのみ動作します。" >&2
  exit 1
fi

TOKEN=$(security find-generic-password -s "$SERVICE" -a "$ACCOUNT" -w 2>/dev/null || true)
if [[ -z "$TOKEN" ]]; then
  cat >&2 <<EOF
FAIL: Keychain にトークンが登録されていません、もしくは取得できません。
  service=$SERVICE
  account=$ACCOUNT
plugins/skill-intake/references/keychain-setup.md の手順で登録してください。
EOF
  exit 1
fi

LEN=${#TOKEN}
PREFIX="${TOKEN:0:4}"
echo "OK: トークン取得成功 (長さ=$LEN, prefix=$PREFIX...)"
echo "    トークン本体は表示しません。"
exit 0
