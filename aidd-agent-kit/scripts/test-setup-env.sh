#!/bin/bash
# setup-env-mac.command の判定ロジックを、実機やネットワークなしで確かめる。
#
# この検査を作った理由:
#   setup-env-mac.command は「アーキの差がいちばん出る場所」(pnpm が CPU 別の
#   Node を取ってくる)でありながら、これまで一度も実行検査を受けていなかった。
#   通しで動かすには Node の入れ直しやネットワークが要るので、判定を担う関数
#   だけを切り出して評価する。切り出しに失敗したら黙って合格させず、落とす。
set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
KIT_DIR=$(cd "$SCRIPT_DIR/.." && pwd -P)
TARGET="${AIDD_TEST_TARGET:-$KIT_DIR/setup-env-mac.command}"
WINDOWS_TARGET="$KIT_DIR/setup-env-windows.bat"
INSTALLER_TARGET="$KIT_DIR/install-mac.command"
WINDOWS_INSTALLER_TARGET="$KIT_DIR/install-windows.bat"
BUILD_WORKFLOW_TARGET="$KIT_DIR/codex/workflow-skills/build-app/SKILL.md"
IMPROVE_WORKFLOW_TARGET="$KIT_DIR/codex/workflow-skills/improve-app/SKILL.md"

WORK=$(mktemp -d) || { echo "作業フォルダを作れません" >&2; exit 1; }
trap 'rm -rf "$WORK"' EXIT

FAILED=0
pass() { echo "  [OK] $1"; }
fail() { echo "  [NG] $1"; FAILED=1; }

extract() { # extract <開始行の正規表現> <終了行> <出力先>
  sed -n "/$1/,/$2/p" "$TARGET" > "$3"
  [ -s "$3" ] || { echo "  [NG] $1 を取り出せない" >&2; FAILED=1; return 1; }
  return 0
}

echo "=== setup-env-mac.command の判定 ==="

# --- 0. Node 最低版の正本 -----------------------------------------
SSOT="$KIT_DIR/NODE_MIN_MAJOR"
NODE_MIN_MAJOR=2
NODE_BELOW_MIN=1
if [ ! -f "$SSOT" ]; then
  fail "NODE_MIN_MAJOR が見つからない"
else
  NODE_MIN_MAJOR=$(tr -d ' \t\r\n' < "$SSOT")
  case "$NODE_MIN_MAJOR" in
    ''|*[!0-9]*|0|1)
      fail "NODE_MIN_MAJOR が境界検査に使える2以上の整数ではない (実際: ${NODE_MIN_MAJOR:-空})"
      NODE_MIN_MAJOR=2
      ;;
    *) pass "NODE_MIN_MAJOR の正本を読み込んだ ($NODE_MIN_MAJOR)" ;;
  esac
  NODE_BELOW_MIN=$((NODE_MIN_MAJOR - 1))
  if grep -Fq 'NODE_MIN_MAJOR=$(tr' "$TARGET" &&
     grep -Fq '"$KIT_DIR/NODE_MIN_MAJOR"' "$TARGET"; then
    pass "setup-env-mac.command が正本を読む"
  else
    fail "setup-env-mac.command が NODE_MIN_MAJOR の正本を読んでいない"
  fi
  if grep -Fq 'call :LOAD_NODE_MIN_MAJOR' "$WINDOWS_TARGET" &&
     grep -Fq '%AIDD_KIT_DIR%NODE_MIN_MAJOR' "$WINDOWS_TARGET" &&
     grep -Fq 'call :ENSURE_NODE_OK' "$WINDOWS_TARGET"; then
    pass "setup-env-windows.bat も正本を読み、最低版を検査する"
  else
    fail "setup-env-windows.bat の NODE_MIN_MAJOR 連携が不完全"
  fi
fi

# --- 0-b. setup state: 存在ではなく状態を記録する ---------
if extract '^record_setup_state() {' '^}$' "$WORK/setup-state.sh"; then
  state_file="$WORK/aidd-agent-kit.setup-env"
  state_failed=0
  for state in attempted registered auth_pending ready failed; do
    SETUP_STAMP="$state_file" MCP_REGISTERED=3 MCP_PENDING=1 MCP_READY=2 \
      MCP_FAILURES=0 MCP_SKIPPED=0 /bin/bash -c \
      ". '$WORK/setup-state.sh'; record_setup_state '$state'" || state_failed=1
    grep -Fxq "state=$state" "$state_file" || state_failed=1
  done
  if [ "$state_failed" -eq 0 ] &&
     grep -Fxq 'schema=2' "$state_file" &&
     ! grep -Eiq 'token|secret|account[_ -]?id' "$state_file"; then
    pass "setup state を5状態に分け、秘密をstampへ書かない"
  else
    fail "setup state の分類またはstamp内容が不正"
  fi
fi

# --- 0-c. installer: 旧stampと有効な状態を混同しない ---------
sed -n '/^print_mcp_status_and_offer() {/,/^}$/p' "$INSTALLER_TARGET" > "$WORK/installer-mcp-status.sh"
if [ -s "$WORK/installer-mcp-status.sh" ]; then
  legacy_stamp="$WORK/legacy.setup-env"
  printf '%s\n' 'setup-env=done' > "$legacy_stamp"
  legacy_out=$(SETUP_STAMP="$legacy_stamp" KIT_DIR="$WORK" \
    INSTALL_HOME="$WORK/project" HOME="$WORK/home" AIDD_NONINTERACTIVE=1 \
    /bin/bash -c ". '$WORK/installer-mcp-status.sh'; print_mcp_status_and_offer" 2>&1) || true
  ready_stamp="$WORK/ready.setup-env"
  printf '%s\n' 'schema=2' 'state=ready' > "$ready_stamp"
  ready_out=$(SETUP_STAMP="$ready_stamp" KIT_DIR="$WORK" \
    INSTALL_HOME="$WORK/project" HOME="$WORK/home" AIDD_NONINTERACTIVE=1 \
    /bin/bash -c ". '$WORK/installer-mcp-status.sh'; print_mcp_status_and_offer" 2>&1) || true
  if printf '%s' "$legacy_out" | grep -q '旧形式' &&
     ! printf '%s' "$legacy_out" | grep -q '前回の接続確認は ready' &&
     printf '%s' "$ready_out" | grep -q '前回の接続確認は ready'; then
    pass "installerは明示的な状態だけを有効扱いし、旧stampを誤認しない"
  else
    fail "installerがstampの存在だけでreadyを判定している"
  fi

  registered_stamp="$WORK/registered.setup-env"
  printf '%s\n' 'schema=2' 'state=registered' > "$registered_stamp"
  registered_out=$(SETUP_STAMP="$registered_stamp" KIT_DIR="$WORK" \
    INSTALL_HOME="$WORK/project" HOME="$WORK/home" AIDD_NONINTERACTIVE=1 \
    /bin/bash -c ". '$WORK/installer-mcp-status.sh'; print_mcp_status_and_offer" 2>&1) || true
  if printf '%s' "$registered_out" | grep -q 'user/global登録済み' &&
     ! printf '%s' "$registered_out" | grep -q '\[未完了\]'; then
    pass "installerはregisteredを最小権限の基本セットアップ完了として扱う"
  else
    fail "installerが未使用の変更系MCP認証を基本セットアップ完了条件にしている"
  fi

  # 対話経路をpseudo-terminalで通し、setup-envの非0を保つことを確かめる。
  fake_kit="$WORK/failing-kit"
  mkdir -p "$fake_kit"
  printf '%s\n' '#!/bin/bash' 'exit 7' > "$fake_kit/setup-env-mac.command"
  chmod +x "$fake_kit/setup-env-mac.command"
  # 疑似端末の作り方は script(1) の系統で異なる。
  #   BSD (Mac)         : script -q <保存先> <コマンド...>
  #   util-linux (CI)   : script -q -e -c "<コマンド>" <保存先>   (-e で子の終了コードを返す)
  # 引用の入れ子で壊さないよう、実行内容はファイルに落として渡す。
  printf '%s\n' '#!/bin/bash' '. "$AIDD_FN"' 'print_mcp_status_and_offer' > "$WORK/pty-body.sh"
  chmod +x "$WORK/pty-body.sh"
  if [ "$(uname -s)" = "Darwin" ]; then
    pty_argv=(script -q /dev/null "$WORK/pty-body.sh")
  else
    pty_argv=(script -q -e -c "$WORK/pty-body.sh" /dev/null)
  fi
  partial_status=0
  if partial_out=$(printf '\n' | env AIDD_FN="$WORK/installer-mcp-status.sh" \
    SETUP_STAMP="$WORK/no-state-yet" KIT_DIR="$fake_kit" \
    INSTALL_HOME="$WORK/home" HOME="$WORK/home" \
    "${pty_argv[@]}" 2>&1); then
    partial_status=0
  else
    partial_status=$?
  fi
  if [ "$partial_status" -eq 7 ] &&
     printf '%s' "$partial_out" | grep -q '部分成功' &&
     printf '%s' "$partial_out" | grep -q 'キット本体はそのまま保持'; then
    pass "installerは継続setup-envの非0を保ち、部分成功を明示する"
  else
    fail "installerが継続setup-envの失敗を成功として飲み込んでいる"
  fi
  if grep -Fq 'set "MCP_SETUP_STATUS=!errorlevel!"' "$KIT_DIR/install-windows.bat" &&
     grep -Fq 'set "SETUP_CONTINUE_STATUS=!errorlevel!"' "$KIT_DIR/install-windows.bat" &&
     grep -Fq 'exit /b !SETUP_CONTINUE_STATUS!' "$KIT_DIR/install-windows.bat"; then
    pass "Windows installerも継続setup-envの非0を終了コードへ反映する"
  else
    fail "Windows installerの継続setup-env失敗契約がMacと非対称"
  fi
else
  fail "install-mac.command からMCP状態関数を取り出せない"
fi

# --- 0-d. `/sse` 互換aliasを legacy transport と誤判定しない ----
sed -n '/^warn_stale_project_mcp_json() {/,/^}$/p' "$TARGET" > "$WORK/warn-stale-mcp.sh"
if [ -s "$WORK/warn-stale-mcp.sh" ]; then
  mkdir -p "$WORK/mcp-alias" "$WORK/mcp-legacy"
  printf '%s\n' '{"type":"http","url":"https://docs.mcp.cloudflare.com/sse"}' > "$WORK/mcp-alias/.mcp.json"
  printf '%s\n' '{"type":"sse","url":"https://docs.mcp.cloudflare.com/sse"}' > "$WORK/mcp-legacy/.mcp.json"
  alias_out=$(MCP_JSON_WARNED=0 MCP_JSON_SEEN='' /bin/bash -c ". '$WORK/warn-stale-mcp.sh'; warn_stale_project_mcp_json '$WORK/mcp-alias'" 2>&1)
  legacy_out=$(MCP_JSON_WARNED=0 MCP_JSON_SEEN='' /bin/bash -c ". '$WORK/warn-stale-mcp.sh'; warn_stale_project_mcp_json '$WORK/mcp-legacy'" 2>&1)
  if [ -z "$alias_out" ] && printf '%s' "$legacy_out" | grep -q 'type=sse'; then
    pass "/sse互換aliasは許容し、legacy type=sseだけ警告する"
  else
    fail "互換/sseとlegacy type=sseの判定が混同されている"
  fi
  if grep -Fq '/c:"/sse\""' "$WINDOWS_TARGET"; then
    fail "Windows側が/sse URLだけをlegacy transport扱いしている"
  else
    pass "Windows側もlegacy type=sseだけを警告する"
  fi
else
  fail "setup-env-mac.command からMCP警告関数を取り出せない"
fi

if grep -Fq '明示的な legacy `type:sse`' "$BUILD_WORKFLOW_TARGET" &&
   grep -Fq '`/sse` URLがStreamable HTTP互換aliasとして動作しているだけなら移行しない' "$BUILD_WORKFLOW_TARGET" &&
   grep -Fq '明示的な legacy `type:sse`' "$IMPROVE_WORKFLOW_TARGET"; then
  pass "build/improve入口はlegacy transportだけを移行対象にする"
else
  fail "build/improve入口で/sse aliasとlegacy type=sseが混同されている"
fi

if grep -Fq '基本セットアップ完了 / 変更系MCPは必要時に認証' "$TARGET" &&
   grep -Fq '基本セットアップ完了 / 変更系MCPは必要時に認証' "$WINDOWS_TARGET" &&
   ! grep -Fq '次に認証してください:' "$TARGET" &&
   ! grep -Fq '次に認証してください:' "$WINDOWS_TARGET" &&
   ! grep -Eq 'ブラウザ認証.*完了を待つ|OAuth 認証も挟む' "$TARGET" "$WINDOWS_TARGET" "$INSTALLER_TARGET" "$WINDOWS_INSTALLER_TARGET"; then
  pass "両OSの基本セットアップは未使用MCPの即時認証を要求しない"
else
  fail "基本セットアップと変更系MCPのオンデマンド認証が分離されていない"
fi

# --- 0-e. pnpm installerを固定・照合してから実行する ----------
PNPM_INSTALLER_COMMIT='11faaa4bb062a5cdac4c22d1a36645d6a3692b82'
if grep -Fq "$PNPM_INSTALLER_COMMIT" "$TARGET" &&
   grep -Fq 'shasum -a 256' "$TARGET" &&
   ! grep -Eq 'get\.pnpm\.io/install\.sh[[:space:]]*\|[[:space:]]*sh' "$TARGET"; then
  pass "Macは固定したpnpm公式installerをSHA-256照合後に実行する"
else
  fail "Macのpnpm installerが固定・完全性検証されていない"
fi
if grep -Fq "$PNPM_INSTALLER_COMMIT" "$WINDOWS_TARGET" &&
   grep -Fq 'Get-FileHash' "$WINDOWS_TARGET" &&
   ! grep -Eiq 'get\.pnpm\.io/install\.ps1.*\|[[:space:]]*iex' "$WINDOWS_TARGET"; then
  pass "Windowsは固定したpnpm公式installerをSHA-256照合後に実行する"
else
  fail "Windowsのpnpm installerが固定・完全性検証されていない"
fi

# --- 1. isolated PATH: 隔離fixtureは外側のPATHを取り込まない ------
if extract '^augment_path() {' '^}$' "$WORK/augment_path.sh"; then
  marker="$WORK/login-shell-was-called"
  fake_shell="$WORK/login-shell"
  printf '#!/bin/bash\n: > "$AIDD_MARKER"\nexit 97\n' > "$fake_shell"
  chmod +x "$fake_shell"
  isolated_out=$(env -i PATH="/usr/bin:/bin" SHELL="$fake_shell" \
    AIDD_PATH_MODE=isolated AIDD_MARKER="$marker" /bin/bash -c \
    ". '$WORK/augment_path.sh'; augment_path; printf '%s' \"\$PATH\"" 2>&1) ||
    isolated_out="<異常終了>"
  if [ -e "$marker" ]; then
    fail "isolated PATH でログインシェルを呼んでいる"
  elif [ "$isolated_out" != "/usr/bin:/bin" ]; then
    fail "isolated PATH に外部PATHを追加している (実際: $isolated_out)"
  else
    pass "isolated PATH はログインシェルと外部PATHを参照しない"
  fi
fi

# --- 2. node_major: バージョン文字列の解釈 ------------------------------
if extract '^node_major() {' '^}$' "$WORK/node_major.sh"; then
  check_major() { # check_major <入力> <期待>
    got=$(/bin/bash -c ". '$WORK/node_major.sh'; node_major '$1'" 2>/dev/null) || got="<異常終了>"
    if [ "$got" = "$2" ]; then
      pass "node_major '$1' -> '$2'"
    else
      fail "node_major '$1' -> '$got' (期待 '$2')"
    fi
  }
  check_major "v${NODE_MIN_MAJOR}.3.1" "$NODE_MIN_MAJOR"
  check_major "v${NODE_BELOW_MIN}.9.0" "$NODE_BELOW_MIN"
  check_major "v8.17.0" "8"
  # 数字でないものを通すと、後段の数値比較が構文エラーで落ちる。
  check_major "" ""
  check_major "不明" ""
  check_major "vX.Y.Z" ""
fi

# --- 2-b. 最低版の境界: min-1 NG / min OK --------------------------
major_meets_minimum() {
  major=$1
  minimum=$2
  [ -n "$major" ] && [ "$major" -ge "$minimum" ]
}
if major_meets_minimum "$NODE_BELOW_MIN" "$NODE_MIN_MAJOR"; then
  fail "Node.js $NODE_BELOW_MIN を最低要件 $NODE_MIN_MAJOR に合格させている"
else
  pass "Node.js $NODE_BELOW_MIN は最低要件 $NODE_MIN_MAJOR に不合格"
fi
if major_meets_minimum "$NODE_MIN_MAJOR" "$NODE_MIN_MAJOR"; then
  pass "Node.js $NODE_MIN_MAJOR は最低要件 $NODE_MIN_MAJOR に合格"
else
  fail "Node.js $NODE_MIN_MAJOR を最低要件 $NODE_MIN_MAJOR に不合格にしている"
fi

# --- 3. warn_arch_mismatch: CPU と Node のアーキ食い違い ----------------
# uname と node を偽物に差し替えて、4通りの組み合わせを作る。
if extract '^warn_arch_mismatch() {' '^}$' "$WORK/arch.sh"; then
  arch_case() { # arch_case <uname の返す値> <node の process.arch> <警告が出るか:1/0>
    b="$WORK/archbin"; rm -rf "$b"; mkdir -p "$b"
    printf '#!/bin/bash\necho %s\n' "$1" > "$b/uname"
    printf '#!/bin/bash\nif [ "$1" = "-p" ]; then echo %s; else echo v%s.0.0; fi\n' \
      "$2" "$NODE_MIN_MAJOR" > "$b/node"
    chmod +x "$b/uname" "$b/node"
    out=$(env -i PATH="$b:/usr/bin:/bin" /bin/bash -c \
      ". '$WORK/arch.sh'; warn_arch_mismatch" 2>&1) || out="<異常終了>"
    if printf '%s' "$out" | grep -q 'Intel 版'; then got=1; else got=0; fi
    if [ "$got" = "$3" ]; then
      pass "CPU=$1 / Node=$2 -> 警告$([ "$3" = 1 ] && echo あり || echo なし)"
    else
      fail "CPU=$1 / Node=$2 -> 警告が想定と違う (出力: $out)"
    fi
  }
  arch_case arm64  x64   1   # Apple Silicon に Intel 版 Node = 言うべき場面
  arch_case arm64  arm64 0
  arch_case x86_64 x64   0   # Intel 機の Intel 版は正常。誤警告しないこと
  arch_case x86_64 arm64 0
fi

# --- 4. MCP を飛ばしたときに「完全に完了」と言わないこと ----------------
if extract '^# CLI が1つでも見つからなければ' '^fi$' "$WORK/verdict.sh"; then
  verdict() { # verdict <MCP_SKIPPED> <CLAUDE_SKIPPED> <CODEX_SKIPPED>
    env -i /bin/bash -c "
      finish() { exit \$1; }
      record_setup_state() { :; }
      MCP_SKIPPED=$1; CLAUDE_SKIPPED=$2; CODEX_SKIPPED=$3; MCP_REGISTERED=0
      . '$WORK/verdict.sh'
      echo '到達:完全に完了'
    " 2>&1 || true
  }
  o=$(verdict 0 0 0)
  if printf '%s' "$o" | grep -q '到達:完全に完了'; then
    pass "両方設定できたときは、従来どおり完了と表示する"
  else
    fail "正常時に完了と表示できていない"
  fi

  o=$(verdict 2 1 1)
  if printf '%s' "$o" | grep -q '到達:完全に完了'; then
    fail "1つも設定していないのに『完全に完了』と表示する"
  elif printf '%s' "$o" | grep -q 'Claude Code (claude)' &&
       printf '%s' "$o" | grep -q 'OpenAI Codex (codex)'; then
    pass "CLI が両方無いときは、未設定であることを名指しで伝える"
  else
    fail "未設定の告知が不十分 (出力: $o)"
  fi

  o=$(verdict 1 0 1)
  if printf '%s' "$o" | grep -q 'Claude Code (claude)'; then
    fail "設定できた方まで未設定として挙げている"
  elif printf '%s' "$o" | grep -q 'OpenAI Codex (codex)'; then
    pass "飛ばした分だけを名指しできている"
  else
    fail "片方だけ欠けた場合の表示が不正 (出力: $o)"
  fi
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "setup-env-mac.command の判定: すべて合格"
  exit 0
fi
echo "setup-env-mac.command の判定: 失敗があります"
exit 1
