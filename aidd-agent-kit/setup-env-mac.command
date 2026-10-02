#!/bin/bash
# =====================================================
#  開発環境セットアップ (Mac用)
#  Node.js と pnpm をインストールし、Claude Code / Codex と
#  Cloudflare の連携(MCP)も設定します
#  ダブルクリックするだけでOKです
#  v1.11.0
# =====================================================

# 起動時のカレントディレクトリ。この後 cd してしまうと分からなくなるが、
# 「利用者がどのプロジェクトの中でこれを実行したか」は .mcp.json の残骸を
# 見に行くときに必要になるので、書き換える前に控えておく。
INVOKE_DIR=$(pwd -P 2>/dev/null || pwd)

cd "$(dirname "$0")"
KIT_DIR=$(pwd -P)

# セットアップの最終確認状態。存在だけで ready とは扱わず、
# state=attempted / registered / auth_pending / ready / failed を記録する。
#
# 置き場所を AIDD_TARGET_HOME に追従させないのは、MCP の登録先が常に
# user scope(そのパソコンの利用者ひとりに1つ)だから。キット本体を
# project scope へ入れることはあっても、MCP はそれとは独立している。
SETUP_STAMP="$HOME/.claude/aidd-agent-kit.setup-env"

# 「最後まで到達したか」を持っておき、そうでない終了だけを異常として扱う。
COMPLETED=0

# stamp には状態と件数だけを記録する。OAuth token、Account ID、
# secret、CLI出力は決して書かない。原子的に更新し、読み途中の誤判定を避ける。
record_setup_state() {
  state="$1"
  case "$state" in
    attempted|registered|auth_pending|ready|failed) ;;
    *) return 0 ;;
  esac
  state_dir=$(dirname "$SETUP_STAMP")
  state_tmp="$SETUP_STAMP.tmp.$$"
  mkdir -p "$state_dir" 2>/dev/null || return 0
  (
    umask 077
    {
      echo "schema=2"
      echo "state=$state"
      echo "attempted=1"
      echo "registered=${MCP_REGISTERED:-0}"
      echo "auth_pending=${MCP_PENDING:-0}"
      echo "ready=${MCP_READY:-0}"
      echo "failed=${MCP_FAILURES:-0}"
      echo "skipped=${MCP_SKIPPED:-0}"
      echo "date=$(date '+%Y-%m-%d %H:%M:%S')"
    } > "$state_tmp" && mv -f "$state_tmp" "$SETUP_STAMP"
  ) 2>/dev/null || rm -f "$state_tmp" 2>/dev/null || true
  unset state state_dir state_tmp
  return 0
}

finish() {
  status="${1:-0}"
  # finish が呼ばれた＝理由を表示したうえで意図的に終わる場合。
  # 重ねて「予期しない問題」と言わないよう、ここで完了扱いにする。
  COMPLETED=1
  if [ "$status" -ne 0 ]; then
    record_setup_state failed
  fi
  echo ""
  # 端末が無い状況(CI・パイプ経由)で read を待つと固まる。install-mac.command と同じ判定にする。
  if [ "${AIDD_NONINTERACTIVE:-0}" != "1" ] && [ -t 0 ]; then
    read -r -p "Enterキーを押すとこのウィンドウを閉じられます..." _unused
  fi
  exit "$status"
}

# --- キットの自己修復 -------------------------------------------------
# 本体は scripts/lib/self-heal.sh (install-mac.command と共通の正本)。
# ZIP を展開したフォルダをそのまま使う前提なので、lib が無いのは
# 「ファイルを個別にコピーした」「展開が途中で止まった」など、キットが
# 欠けた状態を意味する。黙って続けると他のファイルも欠けている可能性が
# 高いため、ここで理由を示して止める。
if [ -f "$KIT_DIR/scripts/lib/self-heal.sh" ]; then
  . "$KIT_DIR/scripts/lib/self-heal.sh"
else
  echo "[エラー] キットの一部 (scripts/lib/self-heal.sh) が見つかりません。" >&2
  echo "  ZIP を展開したフォルダを、中身を移動せずそのまま使ってください。" >&2
  echo "  それでも直らない場合は、ZIP を展開し直してください。" >&2
  finish 1
fi

# --- 開発ツールの置き場所を吸収する ------------------------------------
# node / pnpm / claude / codex がどこに入っているかは利用者ごとに違う。
#   CPU         : Apple Silicon の Homebrew は /opt/homebrew、Intel は /usr/local
#   Node の入れ方 : pnpm / nvm / volta / asdf / mise / npm -g / bun
#   起動のしかた  : ダブルクリックとターミナル実行とで見える PATH が違う
#
# 「ありそうな場所」を数え上げる方式は必ず数え漏れる。そこで順番を逆にして、
#   (1) 利用者のログインシェルが実際に見ている PATH を借りる  ← 本命
#   (2) そのうえで標準的な置き場所を後ろに足す                ← (1) が空振りしたときの保険
# とする。(1) なら nvm や mise のように「設定ファイルを読んで初めて PATH に
# 載る」仕組みまで、こちらが個別に知らなくても拾える。
augment_path() {
  _extra=""

  # CI やオフラインfixtureは、渡された PATH だけを信頼境界にする。
  # このモードではログインシェルや標準的な追加先を探さない。
  # 通常実行のダブルクリックUXには影響させない明示的なテスト契約。
  if [ "${AIDD_PATH_MODE:-}" = "isolated" ]; then
    export PATH
    unset _extra
    return 0
  fi

  # (1) ログインシェルへ PATH を尋ねる。
  #     利用者のシェル設定が壊れている(過去に /opt/homebrew/bin/zsh が
  #     存在しない事例があった)、あるいは入力待ちで止まることがあるため、
  #     結果は目印つきで受け取り、5秒で打ち切る。
  if [ -n "${SHELL:-}" ] && [ -x "${SHELL:-}" ]; then
    # mktemp の引数は BSD(Mac) と GNU(CI の Linux) で作法が違う。
    # Mac は雛形か -t が要り、GNU は引数なしで作れる。両方を順に試す。
    _out=$(mktemp 2>/dev/null || mktemp -t aidd-path 2>/dev/null) || _out=""
    if [ -n "$_out" ]; then
      "$SHELL" -lc 'printf "\nAIDD_PATH=%s\n" "$PATH"' >"$_out" 2>/dev/null </dev/null &
      _pid=$!
      _n=0
      while kill -0 "$_pid" 2>/dev/null && [ "$_n" -lt 50 ]; do
        sleep 0.1
        _n=$((_n + 1))
      done
      if kill -0 "$_pid" 2>/dev/null; then
        kill -9 "$_pid" 2>/dev/null || true
      fi
      wait "$_pid" 2>/dev/null || true
      # 目印の行だけを採る。シェル設定が何か表示していても混ざらない。
      _login_path=$(sed -n 's/^AIDD_PATH=//p' "$_out" 2>/dev/null | tail -n 1) || _login_path=""
      rm -f "$_out"
      case "$_login_path" in
        /*) _extra="$_extra:$_login_path" ;;
      esac
    fi
  fi

  # (2) 標準的な置き場所。Homebrew は両方の prefix を並べる
  #     (Rosetta 併用で Intel 版と Apple Silicon 版が同居することがある)。
  #     実在するものだけ足して、PATH が読めなくなるのを防ぐ。
  for _d in \
    /opt/homebrew/bin /opt/homebrew/sbin \
    /usr/local/bin /usr/local/sbin \
    "${PNPM_HOME:-}" "$HOME/Library/pnpm" "$HOME/.local/share/pnpm" \
    "$HOME/.volta/bin" "$HOME/.bun/bin" "$HOME/.asdf/shims" \
    "$HOME/.local/bin" "$HOME/.npm-global/bin" "${NVM_BIN:-}"
  do
    if [ -n "$_d" ] && [ -d "$_d" ]; then
      _extra="$_extra:$_d"
    fi
  done

  # 重複を潰す。害は無いが、不具合報告で PATH を見せてもらうときに読めなくなる。
  _new=""
  _seen=":"
  _oldifs=$IFS
  IFS=":"
  for _d in $PATH$_extra; do
    [ -n "$_d" ] || continue
    case "$_seen" in
      *":$_d:"*) continue ;;
    esac
    _seen="$_seen$_d:"
    if [ -z "$_new" ]; then _new="$_d"; else _new="$_new:$_d"; fi
  done
  IFS=$_oldifs
  PATH="$_new"
  export PATH

  unset _extra _out _pid _n _login_path _d _new _seen _oldifs
  return 0
}

# 異常終了の検知に ERR トラップを使わない理由:
#   ERR を関数の中まで届かせるには set -E が要る。ところが macOS 標準の
#   bash 3.2 では、条件文の中で失敗したコマンド置換
#   (例: `if existing=$(claude mcp get ...); then`) の ERR が、
#   本来は無視されるはずなのに後から関数内で発火する。
#   このスクリプトは MCP の状態確認でその書き方を多用するため、
#   「実際には処理が続くのに『中断しました』と表示される」ことになる。
#
#   そこで EXIT トラップで「最後まで到達したか」を見る方式にした。
#   コマンド置換のサブシェルは EXIT トラップを実行しないので誤爆せず、
#   関数の中で予期しない失敗が起きた場合(set -e で即終了する)は確実に拾える。
on_exit() {
  status=$?
  if [ "$COMPLETED" != "1" ] && [ "$status" != "0" ]; then
    record_setup_state failed
    echo ""
    echo "[エラー] 予期しない問題が発生したため中断しました。"
    echo "この画面のまま導入支援の担当者にお見せください。"
    COMPLETED=1
  fi
  exit "$status"
}

trap on_exit EXIT
set -e

# 起動した事実を先に残す。中断されても過去の ready が残らない。
record_setup_state attempted

self_heal_kit

echo ""
echo "==============================================="
echo "  開発環境セットアップ (Mac)"
echo "  Node.js と pnpm を準備します"
echo "==============================================="
echo ""

# --- ステップ 1/4: pnpm のインストール -------------------------
export PNPM_HOME="${PNPM_HOME:-$HOME/Library/pnpm}"
# 既に入っている node / pnpm を「見つけられなくて入れ直す」ことがないよう、
# 判定の前に PATH を整える。CPU や Node の入れ方の違いはここで吸収する。
augment_path

PNPM_VERSION=""
if command -v pnpm >/dev/null 2>&1; then
  if ! PNPM_VERSION=$(pnpm --version 2>/dev/null) || [ -z "${PNPM_VERSION//[[:space:]]/}" ]; then
    echo "[エラー] pnpm コマンドは見つかりましたが、正常に実行できません。"
    echo "pnpm のインストールを修復してから、もう一度実行してください。"
    finish 1
  fi
  echo "(1/4) pnpm はインストール済みです ($PNPM_VERSION)"
else
  echo "(1/4) pnpm をインストールしています(1〜2分)..."
  # ネットワークから取得したスクリプトを直接pipe実行しない。pnpm公式repoの
  # immutable commitへ固定し、内容を照合してから実行する。公式installer自身も
  # npm registry署名とpackage integrityを検証するため、取得の両段をfail-closedにする。
  PNPM_INSTALLER_COMMIT="11faaa4bb062a5cdac4c22d1a36645d6a3692b82"
  PNPM_INSTALLER_SHA256="3a6b531bfa164f5cac7c8db261cb2eb7bf929d7b8efb3a4eae82425507050e91"
  PNPM_INSTALLER_URL="https://raw.githubusercontent.com/pnpm/get.pnpm.io/$PNPM_INSTALLER_COMMIT/install.sh"
  PNPM_INSTALLER_TMP=$(mktemp "${TMPDIR:-/tmp}/aidd-pnpm-install.XXXXXX") || {
    echo "[エラー] pnpm installer用の一時ファイルを作れませんでした。"
    finish 1
  }
  if ! curl -fsSL "$PNPM_INSTALLER_URL" -o "$PNPM_INSTALLER_TMP"; then
    rm -f "$PNPM_INSTALLER_TMP"
    echo "[エラー] pnpm公式installerを取得できませんでした。"
    finish 1
  fi
  PNPM_INSTALLER_ACTUAL=$(shasum -a 256 "$PNPM_INSTALLER_TMP" | awk '{print $1}')
  if [ "$PNPM_INSTALLER_ACTUAL" != "$PNPM_INSTALLER_SHA256" ]; then
    rm -f "$PNPM_INSTALLER_TMP"
    echo "[エラー] pnpm公式installerの完全性を確認できないため、実行しません。"
    finish 1
  fi
  if ! sh "$PNPM_INSTALLER_TMP"; then
    rm -f "$PNPM_INSTALLER_TMP"
    echo "[エラー] 検証済みpnpm installerの実行に失敗しました。"
    finish 1
  fi
  rm -f "$PNPM_INSTALLER_TMP"
  unset PNPM_INSTALLER_COMMIT PNPM_INSTALLER_SHA256 PNPM_INSTALLER_URL
  unset PNPM_INSTALLER_TMP PNPM_INSTALLER_ACTUAL
  # 入れた直後の場所を PATH に載せる(pnpm 本体・pnpm 管理の node の両方)。
  augment_path
  PNPM_VERSION=""
  if ! command -v pnpm >/dev/null 2>&1 ||
     ! PNPM_VERSION=$(pnpm --version 2>/dev/null) ||
     [ -z "${PNPM_VERSION//[[:space:]]/}" ]; then
    echo "[エラー] pnpm のインストールに失敗しました。"
    echo "インターネット接続を確認して、もう一度実行してください。"
    echo "社内ネットワークの通信制限が原因の場合があります。"
    echo "解決しないときは、この画面のままIT担当者にお見せください。"
    finish 1
  fi
  echo "      pnpm $PNPM_VERSION をインストールしました"
fi

# --- Node.js が「使える状態か」を見る ----------------------------------
# 「コマンドが在る」と「使える」は別。ここを分けないと、v12 が入った機で
# 判定だけ通り、後段の wrangler や Claude Code が意味不明に失敗する。
# 失敗する場所と原因の場所が離れるほど、非エンジニアには手が出せなくなる。
# 最低バージョンは Mac / Windows で別々に持たず、キット直下の
# NODE_MIN_MAJOR だけを正本にする。読めない・数値でない場合は、古い
# 既定値で黙って続けず配布物の欠落として停止する。
NODE_MIN_MAJOR=$(tr -d ' \t\r\n' < "$KIT_DIR/NODE_MIN_MAJOR" 2>/dev/null) || NODE_MIN_MAJOR=""
case "$NODE_MIN_MAJOR" in
  ''|*[!0-9]*|0)
    echo "[エラー] キットの NODE_MIN_MAJOR が無いか、正しい数値ではありません。"
    echo "キットを再度ダウンロードしてから、もう一度実行してください。"
    finish 1
    ;;
esac

node_major() {
  # "v22.3.1" -> "22"。数字以外が来たら空を返す(呼び出し側で弾く)。
  _v="${1#v}"
  _v="${_v%%.*}"
  case "$_v" in
    ''|*[!0-9]*) printf '' ;;
    *) printf '%s' "$_v" ;;
  esac
  unset _v
}

# CPU と Node のアーキが食い違っていないか。
# Apple Silicon 機で x64 の Node が使われている状態は、実際に起きる:
#   - Rosetta 下のターミナルで入れた
#   - Volta の toolchain が x64 のまま引き継がれた
# Rosetta があれば動いてしまうため誰も気づかず、あとから速度や
# ネイティブモジュールの不整合として出る。動くので止めはしないが、必ず言う。
warn_arch_mismatch() {
  _cpu=$(uname -m 2>/dev/null) || _cpu=""
  _node_arch=$(node -p 'process.arch' 2>/dev/null) || _node_arch=""
  if [ "$_cpu" = "arm64" ] && [ "$_node_arch" = "x64" ]; then
    echo "      [注意] この Mac は Apple Silicon ですが、Node.js は Intel 版です。"
    echo "             動きますが遅くなり、一部の部品が入らないことがあります。"
    echo "             使用中の Node.js: $(command -v node)"
    echo "             作り直す場合: pnpm env use --global lts"
  fi
  unset _cpu _node_arch
}

# 古すぎるなら、黙って通さず、その場で入れ直しを試みる。
ensure_node_ok() {
  _major=$(node_major "$NODE_VERSION")
  if [ -n "$_major" ] && [ "$_major" -ge "$NODE_MIN_MAJOR" ]; then
    warn_arch_mismatch
    unset _major
    return 0
  fi

  echo "      Node.js $NODE_VERSION は古すぎます (v$NODE_MIN_MAJOR 以上が必要)。"
  echo "      新しい Node.js を入れています(2〜3分)..."
  pnpm env use --global lts || true
  augment_path
  NODE_VERSION=$(node --version 2>/dev/null) || NODE_VERSION=""
  _major=$(node_major "$NODE_VERSION")
  if [ -z "$_major" ] || [ "$_major" -lt "$NODE_MIN_MAJOR" ]; then
    echo ""
    echo "[エラー] Node.js を v$NODE_MIN_MAJOR 以上にできませんでした"
    echo "        (現在: ${NODE_VERSION:-判定できません})。"
    # どの道具が管理している node なのかが分かれば、支援側は即座に判断できる。
    echo "        使用中の Node.js: $(command -v node 2>/dev/null || echo 見つかりません)"
    echo "        nvm / Volta / asdf などで固定されている可能性があります。"
    echo "        この画面のまま導入支援の担当者にお見せください。"
    finish 1
  fi
  echo "      Node.js $NODE_VERSION に更新しました"
  warn_arch_mismatch
  unset _major
  return 0
}

# --- ステップ 2/4: Node.js のインストール ----------------------
echo "(2/4) Node.js を確認しています..."
NODE_VERSION=""
if command -v node >/dev/null 2>&1; then
  if ! NODE_VERSION=$(node --version 2>/dev/null) || [ -z "${NODE_VERSION//[[:space:]]/}" ]; then
    echo "[エラー] Node.js コマンドは見つかりましたが、正常に実行できません。"
    echo "Node.js のインストールを修復してから、もう一度実行してください。"
    finish 1
  fi
  echo "      Node.js はインストール済みです ($NODE_VERSION)"
  ensure_node_ok
else
  echo "      Node.js をインストールしています(2〜3分)..."
  pnpm env use --global lts
  # 入れた直後の場所を PATH に載せる(pnpm 本体・pnpm 管理の node の両方)。
  augment_path
  NODE_VERSION=""
  if ! command -v node >/dev/null 2>&1 ||
     ! NODE_VERSION=$(node --version 2>/dev/null) ||
     [ -z "${NODE_VERSION//[[:space:]]/}" ]; then
    echo "[エラー] Node.js のインストールに失敗しました。"
    echo "この画面のまま導入支援の担当者にお見せください。"
    finish 1
  fi
  echo "      Node.js $NODE_VERSION をインストールしました"
  # 入れた直後でも確認する。pnpm が LTS を入れたつもりでも、PATH の先頭に
  # 別の道具(Volta 等)が管理する古い node が居れば、そちらが使われる。
  ensure_node_ok
fi

# --- ステップ 3/4: AI開発ツールと Cloudflare の連携(MCP) ---------
echo "(3/4) Claude Code / Codex と Cloudflare の連携を設定しています..."

MCP_FAILURES=0
MCP_PENDING=0
MCP_REGISTERED=0
MCP_READY=0
# CLI が見つからず設定を飛ばした数。これを数えないと「何も設定していないのに
# 完全に完了しました」と表示してしまう(下の最終判定で使う)。
# 名前を1つの変数に連ねて for で回すと "Claude Code" が空白で割れる。
# 対象は2つと決まっているので、素直に別々のフラグで持つ。
MCP_SKIPPED=0
CLAUDE_SKIPPED=0
CODEX_SKIPPED=0

echo "      MCPの user scope(どのフォルダから使うか)と"
echo "      Cloudflare OAuth権限(Account/read/write)は別物です。"
echo "      docsは認証不要。それ以外は必要時に最小権限だけ認可してください。"

report_claude_mcp_status() {
  server_name="$1"
  server_url="$2"
  status_output="$3"
  action="$4"

  if ! printf '%s\n' "$status_output" | grep -Fq "Scope: User config" ||
     ! printf '%s\n' "$status_output" | grep -Fq "Type: http" ||
     ! printf '%s\n' "$status_output" | grep -Fq "URL: $server_url"; then
    return 1
  fi

  MCP_REGISTERED=$((MCP_REGISTERED + 1))

  if printf '%s\n' "$status_output" | grep -Eq 'Status:.*Connected'; then
    echo "      Claude Code / $server_name: $action(接続ready)"
    MCP_READY=$((MCP_READY + 1))
    return 0
  fi

  if printf '%s\n' "$status_output" | grep -Eiq 'Status:.*(Needs authentication|Authentication required|Needs auth)'; then
    echo "      Claude Code / $server_name: 設定済み・認証待ち"
    MCP_PENDING=$((MCP_PENDING + 1))
    return 0
  fi

  echo "      Claude Code / $server_name: 失敗(接続状態がreadyではありません)"
  printf '%s\n' "$status_output"
  MCP_FAILURES=$((MCP_FAILURES + 1))
  return 0
}

configure_claude_mcp() {
  server_name="$1"
  server_url="$2"
  existing=""

  if existing=$(claude mcp get "$server_name" 2>&1); then
    if printf '%s\n' "$existing" | grep -Fq "Scope: User config" &&
       printf '%s\n' "$existing" | grep -Fq "Type: http" &&
       printf '%s\n' "$existing" | grep -Fq "URL: $server_url"; then
      report_claude_mcp_status "$server_name" "$server_url" "$existing" "スキップ"
      return
    fi

    echo "      Claude Code / $server_name: 古い設定を更新します"
    if ! claude mcp remove "$server_name"; then
      echo "      Claude Code / $server_name: 失敗(古い設定を削除できませんでした)"
      MCP_FAILURES=$((MCP_FAILURES + 1))
      return
    fi
  elif ! printf '%s\n' "$existing" | grep -Eq 'No MCP server (named|found with name)'; then
    echo "      Claude Code / $server_name: 失敗(現在の設定を確認できませんでした)"
    printf '%s\n' "$existing"
    MCP_FAILURES=$((MCP_FAILURES + 1))
    return
  fi

  add_status=0
  claude mcp add --transport http --scope user "$server_name" "$server_url" || add_status=$?

  existing=""
  if existing=$(claude mcp get "$server_name" 2>&1) &&
     report_claude_mcp_status "$server_name" "$server_url" "$existing" "成功"; then
    if [ "$add_status" -ne 0 ]; then
      echo "      Claude Code / $server_name: 失敗(CLI終了コード $add_status)"
      MCP_FAILURES=$((MCP_FAILURES + 1))
    fi
  else
    echo "      Claude Code / $server_name: 失敗(設定後の確認NG、CLI終了コード $add_status)"
    printf '%s\n' "$existing"
    MCP_FAILURES=$((MCP_FAILURES + 1))
  fi
}

get_codex_auth_status() {
  server_name="$1"
  list_output=""
  auth_status=""

  if ! list_output=$(codex mcp list --json 2>&1); then
    printf '%s\n' "$list_output"
    return 1
  fi

  if ! auth_status=$(printf '%s\n' "$list_output" | node -e '
    let input = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", chunk => { input += chunk; });
    process.stdin.on("end", () => {
      const server = JSON.parse(input).find(item => item.name === process.argv[1]);
      if (!server || typeof server.auth_status !== "string") process.exit(2);
      process.stdout.write(server.auth_status);
    });
  ' "$server_name" 2>/dev/null); then
    return 1
  fi

  printf '%s' "$auth_status"
}

report_codex_mcp_status() {
  server_name="$1"
  auth_status=""

  if ! auth_status=$(get_codex_auth_status "$server_name"); then
    echo "      OpenAI Codex / $server_name: 失敗(認証状態を確認できませんでした)"
    MCP_FAILURES=$((MCP_FAILURES + 1))
    return
  fi

  case "$auth_status" in
    o_auth|bearer_token)
      echo "      OpenAI Codex / $server_name: 設定済み・認証済み(接続ready)"
      MCP_REGISTERED=$((MCP_REGISTERED + 1))
      MCP_READY=$((MCP_READY + 1))
      ;;
    unsupported)
      echo "      OpenAI Codex / $server_name: 設定済み・認証不要(接続ready)"
      MCP_REGISTERED=$((MCP_REGISTERED + 1))
      MCP_READY=$((MCP_READY + 1))
      ;;
    not_logged_in)
      echo "      OpenAI Codex / $server_name: 設定済み・認証待ち"
      MCP_REGISTERED=$((MCP_REGISTERED + 1))
      MCP_PENDING=$((MCP_PENDING + 1))
      ;;
    *)
      echo "      OpenAI Codex / $server_name: 失敗(未確認の認証状態: $auth_status)"
      MCP_FAILURES=$((MCP_FAILURES + 1))
      ;;
  esac
}

run_codex_mcp_add() {
  server_name="$1"
  server_url="$2"
  add_status=0
  # mcp add の責務はuser/global登録だけ。OAuthは対象capabilityを実際に
  # 使う時に codex mcp login で行い、ここでは未使用MCPの権限を求めない。
  codex mcp add "$server_name" --url "$server_url" || add_status=$?
  CODEX_ADD_STATUS=$add_status
}

configure_codex_mcp() {
  server_name="$1"
  server_url="$2"
  existing=""

  if existing=$(codex mcp get "$server_name" --json 2>&1); then
    if printf '%s\n' "$existing" | grep -Fq 'streamable_http' &&
       printf '%s\n' "$existing" | grep -Fq "$server_url"; then
      report_codex_mcp_status "$server_name"
      return
    fi

    echo "      OpenAI Codex / $server_name: 古い設定を更新します"
    if ! codex mcp remove "$server_name"; then
      echo "      OpenAI Codex / $server_name: 失敗(古い設定を削除できませんでした)"
      MCP_FAILURES=$((MCP_FAILURES + 1))
      return
    fi
  elif ! printf '%s\n' "$existing" | grep -Eq 'No MCP server (named|found with name)'; then
    echo "      OpenAI Codex / $server_name: 失敗(現在の設定を確認できませんでした)"
    printf '%s\n' "$existing"
    MCP_FAILURES=$((MCP_FAILURES + 1))
    return
  fi

  CODEX_ADD_STATUS=0
  run_codex_mcp_add "$server_name" "$server_url"

  existing=""
  if existing=$(codex mcp get "$server_name" --json 2>&1) &&
     printf '%s\n' "$existing" | grep -Fq 'streamable_http' &&
     printf '%s\n' "$existing" | grep -Fq "$server_url"; then
    report_codex_mcp_status "$server_name"
  else
    echo "      OpenAI Codex / $server_name: 失敗(設定後の確認NG、CLI終了コード $CODEX_ADD_STATUS)"
    printf '%s\n' "$existing"
    MCP_FAILURES=$((MCP_FAILURES + 1))
  fi
}

if command -v claude >/dev/null 2>&1; then
  configure_claude_mcp cloudflare-bindings https://bindings.mcp.cloudflare.com/mcp
  configure_claude_mcp cloudflare-docs https://docs.mcp.cloudflare.com/mcp
  configure_claude_mcp cloudflare-observability https://observability.mcp.cloudflare.com/mcp
else
  # 「見つからない」の理由は1つではない。未導入のほかに、導入済みだが PATH に
  # 載っていない・別シェルの alias としてしか存在しない、という状態がある。
  # どれなのかをこちらは決められないので、断定せず両方の道を示す。
  echo "      Claude Code: スキップ(コマンド claude が見つかりません)"
  echo "        未導入なら Claude Code をインストールしてください。"
  echo "        導入済みのはずなら、ターミナルを開き直してから再実行してください。"
  MCP_SKIPPED=$((MCP_SKIPPED + 1))
  CLAUDE_SKIPPED=1
fi

if command -v codex >/dev/null 2>&1; then
  configure_codex_mcp cloudflare-bindings https://bindings.mcp.cloudflare.com/mcp
  configure_codex_mcp cloudflare-docs https://docs.mcp.cloudflare.com/mcp
  configure_codex_mcp cloudflare-observability https://observability.mcp.cloudflare.com/mcp
else
  echo "      OpenAI Codex: スキップ(コマンド codex が見つかりません)"
  echo "        未導入なら Codex CLI をインストールしてください。"
  echo "        導入済みのはずなら、ターミナルを開き直してから再実行してください。"
  MCP_SKIPPED=$((MCP_SKIPPED + 1))
  CODEX_SKIPPED=1
fi
echo "      (変更系MCPの権限は、その機能を初めて使う時だけ認証します)"

# --- project scope の .mcp.json 残骸を見つけて知らせる -----------------
# このキットは MCP を user scope(ユーザー全体)にだけ登録する。ところが
# プロジェクト直下に古い `.mcp.json` が残っていると、Claude Code はそちらを
# 優先候補として拾い、`claude mcp list` が [Conflicting scopes] を出す。
# `"type": "sse"`(legacy sse)は 410 Gone になる。/sse URL との違いと4分岐
# (未登録 / 不通 / legacy sse / scope 衝突)の裁定は
# skills/wrangler/references/mcp-vs-cli-routing.md が正本。
#
# ここでは絶対に自動削除・書き換えをしない。git 管理下ならリポジトリの変更として
# PR で直し、未追跡なら利用者本人が直す。見つけたことと直し方だけを伝える。
MCP_JSON_WARNED=0
warn_stale_project_mcp_json() {
  target_dir="$1"
  [ -n "$target_dir" ] || return 0
  mcp_json="$target_dir/.mcp.json"
  [ -f "$mcp_json" ] || return 0
  # 同じファイルを2回警告しない(起動元とキットの親が同じ場合がある)。
  case " $MCP_JSON_SEEN " in *" $mcp_json "*) return 0 ;; esac
  MCP_JSON_SEEN="$MCP_JSON_SEEN $mcp_json"

  grep -Eq '"type"[[:space:]]*:[[:space:]]*"sse"' "$mcp_json" || return 0

  if [ "$MCP_JSON_WARNED" -eq 0 ]; then
    echo ""
    echo "-----------------------------------------------"
    echo "  [注意] 古い形式の MCP 設定が見つかりました"
    echo "-----------------------------------------------"
    MCP_JSON_WARNED=1
  fi
  echo "  $mcp_json"
  echo "    このファイルに deprecated transport を強制する type=sse があります。"
  echo "    この形式(legacy sse)は 410 Gone になります。"
  echo "    (/sse URL と type=sse の違いは skills/wrangler/references/mcp-vs-cli-routing.md)"
  echo "    また、このプロジェクト用の設定がユーザー全体の設定より優先されるため、"
  echo "    キットが登録した正しい設定が隠れます([Conflicting scopes] の原因)。"
  echo "    直し方(どちらか):"
  echo "      - URL を https://<名前>.mcp.cloudflare.com/mcp に書き換え、\"type\" を \"http\" にする"
  echo "      - そのエントリを .mcp.json から削除する(キットの user scope 設定が使われます)"
  echo "    ※ この script は .mcp.json を変更しません。git 管理下ならリポジトリの変更として"
  echo "       PR で直し、未追跡なら利用者本人が直してください(AI エージェントは差分を提示できます)。"
}
MCP_JSON_SEEN=""
warn_stale_project_mcp_json "$INVOKE_DIR"
warn_stale_project_mcp_json "$(dirname "$KIT_DIR")"
[ -z "${AIDD_PROJECT_DIR:-}" ] || warn_stale_project_mcp_json "$AIDD_PROJECT_DIR"
if [ "$MCP_JSON_WARNED" -eq 1 ]; then
  echo ""
fi

# --- ステップ 4/4: 確認 ---------------------------------------
echo "(4/4) 動作確認をしています..."
echo ""
echo "  Node.js: $NODE_VERSION"
echo "  pnpm:    $PNPM_VERSION"
echo ""
if [ "$MCP_FAILURES" -gt 0 ]; then
  record_setup_state failed
  echo "[エラー] Cloudflare MCP の設定または確認に $MCP_FAILURES 件失敗しました。"
  echo "上の失敗内容を確認してから、もう一度実行してください。"
  finish 1
fi
# CLI が1つでも見つからなければ、その分の連携は設定できていない。
# ここを見ずに「完全に完了しました」と出すと、Claude Code をデスクトップアプリ
# だけで使っている利用者(CLI 未導入)には、何も設定していないのに完了と伝わる。
# 表示は必ず、実際にやれたことの範囲までにとどめる。
if [ "$MCP_SKIPPED" -gt 0 ]; then
  record_setup_state attempted
  echo "==============================================="
  echo "  基本セットアップ完了 / 一部の連携は未設定"
  echo "==============================================="
  echo ""
  echo "Node.js と pnpm の準備は終わりました。"
  echo "次のツールが見つからなかったため、Cloudflare 連携は設定していません:"
  if [ "$CLAUDE_SKIPPED" -eq 1 ]; then echo "  - Claude Code (claude)"; fi
  if [ "$CODEX_SKIPPED" -eq 1 ]; then echo "  - OpenAI Codex (codex)"; fi
  echo ""
  echo "そのツールを使う予定があるなら、導入してからこのセットアップを"
  echo "もう一度実行してください。使わないのであれば、このままで問題ありません。"
  echo ""
  echo "開いているターミナルがあれば、一度閉じて開き直してください。"
  finish 0
fi
if [ "$MCP_PENDING" -gt 0 ]; then
  record_setup_state registered
  echo "==============================================="
  echo "  基本セットアップ完了 / 変更系MCPは必要時に認証"
  echo "==============================================="
  echo ""
  echo "Cloudflare MCPのuser/global登録と、認証不要のdocs接続は完了しました。"
  echo "bindings変更やobservability調査を初めて行う時に、"
  echo "エージェントが必要な対象1件だけの認証を案内します。今は認証不要です。"
  finish 0
fi
record_setup_state ready
echo "==============================================="
echo "  セットアップが完全に完了しました！"
echo "==============================================="
echo ""
echo "次にやること:"
echo "  開いているターミナルがあれば、一度閉じて開き直してください。"
echo "  (新しい設定を読み込むためです)"
finish 0
