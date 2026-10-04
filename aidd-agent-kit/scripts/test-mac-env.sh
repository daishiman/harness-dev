#!/bin/bash
# =====================================================
#  setup-env-mac.command の環境差吸収(augment_path)を検証する
#
#  なぜ必要か:
#    利用者の PC は Intel と Apple Silicon で Homebrew の位置が違い、
#    Node の入れ方(pnpm / nvm / volta / asdf / mise)でも置き場所が違う。
#    ここを間違えると「既に入っているのに見つからない」「入れたのに
#    使えない」という、利用者からは原因の分からない失敗になる。
#
#    Intel の実機も、GitHub の Intel ランナーも当てにできない。
#    そこで実機を用意する代わりに、環境そのものを注入して検証する。
#    ログインシェルを偽物に差し替えれば、どの CPU の上でも
#    「Intel の利用者に見えている世界」を再現できる。
#
#  使い方:
#    bash aidd-agent-kit/scripts/test-mac-env.sh
# =====================================================
set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
KIT_DIR=$(cd "$SCRIPT_DIR/.." && pwd -P)
# 既定は本物。AIDD_TEST_TARGET を渡せば別ファイルを検査できる
# (「この検査は壊れた実装をちゃんと落とすか」を確かめるために使う)。
TARGET="${AIDD_TEST_TARGET:-$KIT_DIR/setup-env-mac.command}"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

FAILED=0
ok()   { printf '  [OK] %s\n' "$1"; }
ng()   { printf '  [NG] %s\n' "$1" >&2; FAILED=1; }

# 検証対象の関数だけを取り出す。本体を走らせると
# 実際に pnpm を入れに行ってしまうため、関数単位で確かめる。
sed -n '/^augment_path() {/,/^}$/p' "$TARGET" > "$WORK/fn.sh"
if [ ! -s "$WORK/fn.sh" ]; then
  echo "[NG] setup-env-mac.command から augment_path を取り出せない" >&2
  exit 1
fi

# 偽のログインシェルを立てて augment_path を走らせ、結果の PATH を返す。
# env -i で実環境の PNPM_HOME / NVM_BIN などを遮断する。
run_case() {
  _body="$1"
  _home="$WORK/home"
  rm -rf "$_home"; mkdir -p "$_home"
  if [ -n "$_body" ]; then
    printf '%s\n' "$_body" > "$WORK/shell"
    chmod +x "$WORK/shell"
    _shell="$WORK/shell"
  else
    _shell="$WORK/no-such-shell"
  fi
  env -i HOME="$_home" SHELL="$_shell" PATH="/usr/bin:/bin" \
    /bin/bash -c ". '$WORK/fn.sh'; augment_path; printf '%s' \"\$PATH\"" 2>/dev/null
}

echo "=== Mac 環境差の検証 ==="

# --- 1. Apple Silicon: Homebrew が /opt/homebrew ---------------------
result=$(run_case '#!/bin/bash
printf "\nAIDD_PATH=%s\n" "/opt/homebrew/bin:/usr/bin:/bin"')
case ":$result:" in
  *:/opt/homebrew/bin:*) ok "Apple Silicon: /opt/homebrew/bin を拾える" ;;
  *) ng "Apple Silicon: /opt/homebrew/bin を拾えない ($result)" ;;
esac

# --- 2. Intel: Homebrew が /usr/local --------------------------------
result=$(run_case '#!/bin/bash
printf "\nAIDD_PATH=%s\n" "/usr/local/bin:/usr/bin:/bin"')
case ":$result:" in
  *:/usr/local/bin:*) ok "Intel: /usr/local/bin を拾える" ;;
  *) ng "Intel: /usr/local/bin を拾えない ($result)" ;;
esac

# --- 3. ログインシェルにしか無い場所(nvm / mise / asdf 相当) -----------
# これが本命。こちらが個別に知らない置き場所でも拾えることを示す。
# 実在しないパスを使うので、「候補リストに書いてあったから通った」
# のではないことが確定する。
NVMISH="/opt/aidd-test/only-known-to-login-shell/bin"
result=$(run_case "#!/bin/bash
printf \"\\nAIDD_PATH=%s\\n\" \"$NVMISH:/usr/bin:/bin\"")
case ":$result:" in
  *":$NVMISH:"*) ok "ログインシェルにしか無い場所も拾える (nvm/mise/asdf 相当)" ;;
  *) ng "ログインシェルにしか無い場所を拾えない ($result)" ;;
esac

# --- 4. シェルが壊れている -------------------------------------------
# 過去に「Terminal の設定が /opt/homebrew/bin/zsh を指しているのに
# 実体が無い」事例があった。落ちずに保険側へ倒れること。
result=$(run_case '')
case ":$result:" in
  *:/usr/bin:*) ok "シェルが壊れていても PATH を壊さない" ;;
  *) ng "シェルが壊れていると PATH まで壊れる ($result)" ;;
esac

# --- 5. シェルが応答しない -------------------------------------------
# 入力待ちや重い設定で固まっても、インストールを止めないこと。
start=$(date +%s)
result=$(run_case '#!/bin/bash
sleep 60
printf "\nAIDD_PATH=%s\n" "/never/reached"')
elapsed=$(( $(date +%s) - start ))
if [ "$elapsed" -le 15 ] && [ -n "$result" ]; then
  ok "応答しないシェルを ${elapsed} 秒で打ち切れる"
else
  ng "応答しないシェルで止まる (${elapsed} 秒 / 結果=$result)"
fi

# --- 6. シェルが余計な出力をする -------------------------------------
# 設定ファイルが挨拶や警告を表示しても、値を取り違えないこと。
result=$(run_case '#!/bin/bash
echo "Last login: ..."
echo "AIDD_PATH=これは絶対パスではない偽物"
printf "\nAIDD_PATH=%s\n" "/opt/homebrew/bin:/usr/bin:/bin"')
case "$result" in
  *偽物*) ng "シェルの余計な出力を PATH に取り込んでいる ($result)" ;;
  *) ok "シェルが余計な出力をしても取り違えない" ;;
esac

# --- 7. 重複が潰れていること -----------------------------------------
result=$(run_case '#!/bin/bash
printf "\nAIDD_PATH=%s\n" "/usr/bin:/bin:/usr/bin:/bin"')
dup=$(printf '%s' "$result" | tr ':' '\n' | LC_ALL=C sort | uniq -d | grep -c . || true)
if [ "$dup" = "0" ]; then
  ok "PATH に重複が無い"
else
  ng "PATH に重複が $dup 件ある ($result)"
fi

echo ""
if [ "$FAILED" != "0" ]; then
  echo "Mac 環境差の検証に失敗しました。"
  exit 1
fi
echo "Mac 環境差の検証: すべて合格"
