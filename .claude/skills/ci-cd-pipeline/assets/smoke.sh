#!/usr/bin/env bash
# デプロイ後のスモークテスト。`.github/scripts/smoke.sh` に置いて使う。
#
# deploy.yml から2回呼ばれる（デプロイの30秒後と、そのさらに90秒後）。
# Cloudflare Workers は配布後も古いプロセスがしばらく残るため、
# 2回とも成功して初めてデプロイ成功とみなす。
#
# 手元でも同じものを流せる:
#   APP_URL=https://example.workers.dev bash .github/scripts/smoke.sh

set -euo pipefail

: "${APP_URL:?APP_URL が設定されていません（リポジトリの Variables に登録してください）}"

echo "対象: $APP_URL"

# 応答が返ってくるまで待てる上限。応答はあるが極端に遅い状態は失敗として扱う。
# 「落ちてはいないが使えない」を成功と呼ばないため。
TIMEOUT=15
NG=0

# 確認するページ。「期待するステータス」を一緒に書く。
#   200 = 誰でも見られるページ
#   30x = ログインが必要で、ログイン画面へ送られるのが正常なページ
#
#   ログインが要るページを 200 期待にすると必ず落ちる。逆に「30x でも 200 でも
#   通す」ようにすると、全ページがログイン画面に飛ぶ壊れ方を見逃す。
#   ページごとに期待を決めるのが要点。
CHECKS=(
  "/|200,30x"          # トップ
  "/login|200"         # ログイン画面（ここが出れば、アプリは起動している）
)

for entry in "${CHECKS[@]}"; do
  path="${entry%%|*}"
  expect="${entry##*|}"
  url="${APP_URL}${path}"

  # -o は本文の保存先。ステータスと本文の両方を見たいので捨てずに残す。
  body=$(mktemp)
  code=$(curl -s --max-time "$TIMEOUT" -o "$body" -w "%{http_code}" "$url" || echo "000")

  ok=0
  case "$expect" in
    *200*) [ "$code" = "200" ] && ok=1 ;;
  esac
  case "$expect" in
    *30x*) case "$code" in 301|302|303|307|308) ok=1 ;; esac ;;
  esac

  # ステータスだけでは足りない。Next.js はアプリ内部が壊れていても
  # エラー画面を 200 で返すことがある。本文も見る。
  if [ "$ok" = "1" ] && [ "$code" = "200" ]; then
    if grep -qE "Application error|Internal Server Error|エラーが発生|no such (column|table)" "$body"; then
      ok=0
      code="$code（本文にエラー表示あり）"
    fi
  fi

  if [ "$ok" = "1" ]; then
    printf '%s\t%s\t期待 %s\n' "OK" "$path" "$expect"
  else
    printf '%s\t%s\t期待 %s / 実際 %s\n' "NG" "$path" "$expect" "$code"
    NG=$((NG + 1))
  fi
  rm -f "$body"
done

if [ "$NG" -ne 0 ]; then
  echo "スモークテスト: 失敗 ${NG}件"
  # 0 以外で終わらないとワークフローが緑のままになる。確認していないのと同じになる。
  exit 1
fi

echo "スモークテスト: 成功"

# 育てかた
#
# 上の CHECKS はどのアプリでも使える最小限。動き出したら、そのアプリで
# 「壊れたら困る画面」を足していく。判断の目安:
#
#   - 認証が要るページの中身まで確認したい場合
#       ログインしてセッションを取り、そのクッキーで叩く。ただし本番のIDと
#       パスワードが要るのでシークレット管理が増える。まずはここまでで運用し、
#       必要になってから足す
#   - ロールごとの出し分けを守りたい場合
#       「本人の画面に配点が出ていないこと」のような、出てはいけないものの
#       検査を入れる。壊れても 200 が返るため、本文を見ないと気づけない
#   - データベースまで生きているか見たい場合
#       DBを読む軽いページを1枚足す。トップが静的だと、DBが死んでいても通る
#
# 増やしすぎない。ここが遅く不安定になると、本当の異常が埋もれる。
