#!/usr/bin/env bash
set -euo pipefail
set +x

PROJECT="$(pwd)"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "不明な引数: $1" >&2; exit 2 ;;
  esac
done

cd "$PROJECT"
TARGET="$(pwd)/.dev.vars"

if [[ ! -f "$TARGET" ]]; then
  echo ".dev.varsが見つかりません: $TARGET" >&2
  echo "先にsetup-local-vars.mjsで初期化してください。" >&2
  exit 2
fi

if [[ ! -f .gitignore ]] || ! grep -Eq '(^|/)[.]dev[.]vars([.]\*|$)' .gitignore; then
  echo ".dev.varsが.gitignoreで除外されていないため中止しました。" >&2
  exit 3
fi

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] Google Client IDとClient Secretを非表示で受け取り、${TARGET}だけを更新します。"
  echo "[dry-run] 値は画面、引数、ログへ表示しません。"
  exit 0
fi

if [[ ! -r /dev/tty ]]; then
  echo "対話ターミナルが必要です。Terminalアプリから実行してください。" >&2
  exit 3
fi

printf 'Google Client IDを貼り付けてEnterを押してください（画面には表示されません）: '
IFS= read -r -s GOOGLE_CLIENT_ID_VALUE </dev/tty
printf '\n'

printf 'Google Client Secretを貼り付けてEnterを押してください（画面には表示されません）: '
IFS= read -r -s GOOGLE_CLIENT_SECRET_VALUE </dev/tty
printf '\n'

if [[ -z "$GOOGLE_CLIENT_ID_VALUE" || "$GOOGLE_CLIENT_ID_VALUE" != *.apps.googleusercontent.com ]]; then
  unset GOOGLE_CLIENT_SECRET_VALUE
  echo "Client IDの形式が正しくありません。ファイルは変更していません。" >&2
  exit 4
fi
if [[ -z "$GOOGLE_CLIENT_SECRET_VALUE" ]]; then
  unset GOOGLE_CLIENT_ID_VALUE
  echo "Client Secretが空です。ファイルは変更していません。" >&2
  exit 4
fi

umask 077
TEMP_FILE="$(mktemp "${TARGET}.tmp.XXXXXX")"
cleanup() {
  rm -f "$TEMP_FILE"
  unset GOOGLE_CLIENT_ID_VALUE GOOGLE_CLIENT_SECRET_VALUE
}
trap cleanup EXIT INT TERM

FOUND_ID=0
FOUND_SECRET=0
while IFS= read -r LINE || [[ -n "$LINE" ]]; do
  case "$LINE" in
    GOOGLE_CLIENT_ID=*)
      printf 'GOOGLE_CLIENT_ID=%s\n' "$GOOGLE_CLIENT_ID_VALUE" >>"$TEMP_FILE"
      FOUND_ID=1
      ;;
    GOOGLE_CLIENT_SECRET=*)
      printf 'GOOGLE_CLIENT_SECRET=%s\n' "$GOOGLE_CLIENT_SECRET_VALUE" >>"$TEMP_FILE"
      FOUND_SECRET=1
      ;;
    *) printf '%s\n' "$LINE" >>"$TEMP_FILE" ;;
  esac
done <"$TARGET"

[[ $FOUND_ID -eq 1 ]] || printf 'GOOGLE_CLIENT_ID=%s\n' "$GOOGLE_CLIENT_ID_VALUE" >>"$TEMP_FILE"
[[ $FOUND_SECRET -eq 1 ]] || printf 'GOOGLE_CLIENT_SECRET=%s\n' "$GOOGLE_CLIENT_SECRET_VALUE" >>"$TEMP_FILE"

chmod 600 "$TEMP_FILE"
mv "$TEMP_FILE" "$TARGET"
chmod 600 "$TARGET"
trap - EXIT INT TERM
unset GOOGLE_CLIENT_ID_VALUE GOOGLE_CLIENT_SECRET_VALUE

echo "完了: .dev.varsへ2項目を安全に保存しました。値は表示していません。"
