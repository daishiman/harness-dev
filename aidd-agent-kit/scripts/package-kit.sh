#!/bin/bash
# =====================================================
#  aidd-agent-kit.zip を作る
#
#  なぜこのスクリプトが必要か:
#    マニュアルは「aidd-agent-kit.zip を展開してください」と書いているのに、
#    その ZIP を作る手順がどこにも無かった。結果として配布物の品質
#    (実行権限・改行コード・BOM・隔離属性) が配布者ごとにバラつき、
#    macOS/Windows 実機でだけ壊れる不具合が繰り返し出荷されていた。
#
#    このスクリプトは「配布できる状態か」を検査し、通ったものだけを
#    ZIP にする。検査に落ちたら ZIP は作らない (fail-closed)。
#
#  使い方:
#    bash aidd-agent-kit/scripts/package-kit.sh            # dist/ に出力
#    bash aidd-agent-kit/scripts/package-kit.sh --check    # 一時ZIPを生成・展開して検査(distは更新しない)
# =====================================================
set -Eeuo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
KIT_DIR=$(cd "$SCRIPT_DIR/.." && pwd -P)
REPO_DIR=$(cd "$KIT_DIR/.." && pwd -P)
DIST_DIR="$REPO_DIR/dist"

CHECK_ONLY=0
case "${1:-}" in
  "") ;;
  --check) CHECK_ONLY=1 ;;
  *) echo "使い方: $0 [--check]" >&2; exit 2 ;;
esac

FAILED=0
fail() {
  printf '  [NG] %s\n' "$1" >&2
  FAILED=1
}
pass() { printf '  [OK] %s\n' "$1"; }

echo "=== 配布前チェック ==="

# --- 1. VERSION が空でないこと ---------------------------------------
# 空の VERSION は install-windows.bat / install-mac.command が書き出す
# version ファイルを空にし、以後のバージョン判定を無言で壊す。
VERSION=$(tr -d ' \t\r\n' < "$KIT_DIR/VERSION" 2>/dev/null || true)
if [ -z "$VERSION" ]; then
  fail "VERSION が空、または読めない"
  VERSION="unknown"
else
  pass "VERSION = $VERSION"
fi

# Node 最低版もキット直下の1ファイルだけを正本にする。
NODE_MIN_MAJOR=$(tr -d ' \t\r\n' < "$KIT_DIR/NODE_MIN_MAJOR" 2>/dev/null || true)
case "$NODE_MIN_MAJOR" in
  ''|*[!0-9]*|0)
    fail "NODE_MIN_MAJOR が空、または正の整数ではない"
    NODE_MIN_MAJOR="invalid"
    ;;
  *) pass "Node.js 最低版 = $NODE_MIN_MAJOR" ;;
esac
NODE_REQUIREMENT="Node.js $NODE_MIN_MAJOR 以上"

# UTF-8 として妥当かを、環境に左右されずに判定する。
#
# ここでは iconv を使ってはいけない。
#   * macOS 標準の /usr/bin/iconv は、全バイトを変換し切ったあとに
#     errno の取りこぼし (ENOTTY) をそのまま終了状態 1 として返すことがある。
#     同じファイルでも出力先が /dev/null か実ファイルかで結果が変わる。
#     つまり終了状態が「入力が UTF-8 か」を表していない。
#   * PATH に Homebrew や conda の GNU libiconv が入っていると、そちらは
#     正しく 0 を返す。結果として「開発者の手元では通り、CI では落ちる」
#     検査になる (実際にそうなった)。
# 判定の根拠を、どの iconv が先に見つかるかではなく、UTF-8 の規格そのものに置く。
if command -v python3 >/dev/null 2>&1; then
  UTF8_CHECKER=python3
else
  # 黙って検査を飛ばさない。判定できないことは合格ではない。
  echo "  [NG] python3 が無いため UTF-8 判定ができない" >&2
  exit 1
fi

utf8_ok() {
  "$UTF8_CHECKER" - "$1" <<'PY'
import sys
try:
    with open(sys.argv[1], 'rb') as f:
        f.read().decode('utf-8')
except Exception:
    sys.exit(1)
PY
}

# --- 2. Windows 向けファイルの改行コードと BOM -------------------------
# cmd.exe はバッチをバイトオフセットで読むため、LF のみだと goto / call :LABEL /
# ( ... ) ブロックが壊れる。PowerShell 5.1 は BOM なしを CP932 として読むため、
# UTF-8 の日本語リテラルが文字化けする。どちらも macOS 上では再現しない。
check_win_file() {
  path="$1"; want_bom="$2"; label="${path#"$KIT_DIR"/}"
  [ -f "$path" ] || { fail "$label が見つからない"; return; }
  # 行末に CR が無い行が1つでもあれば、そこは LF のみ = cmd.exe が壊れる。
  # (grep は \n を剥がすので、CRLF の行は末尾に \r が残る)
  if LC_ALL=C grep -q -v $'\r$' "$path"; then
    fail "$label に CRLF でない改行がある"
    return
  fi
  has_bom=0
  if [ "$(head -c 3 "$path" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then
    has_bom=1
  fi
  if [ "$has_bom" != "$want_bom" ]; then
    if [ "$want_bom" = "1" ]; then
      fail "$label に UTF-8 BOM が無い (PowerShell 5.1 が文字化けする)"
    else
      fail "$label に UTF-8 BOM がある (cmd.exe が BOM を実行しようとする)"
    fi
    return
  fi
  if ! utf8_ok "$path"; then
    fail "$label が UTF-8 として読めない"
    return
  fi
  pass "$label (CRLF / BOM=$has_bom)"
}

for f in "$KIT_DIR"/*.bat; do
  [ -f "$f" ] && check_win_file "$f" 0
done
for f in "$KIT_DIR"/scripts/*.ps1; do
  [ -f "$f" ] && check_win_file "$f" 1
done

# --- 3. Unix 向けファイルの改行コードと実行権限 ------------------------
# CR が混ざった .command は `bash: \r: command not found` で即死する。
#
# 検査は2層に分ける:
#   全ファイル共通 … CR が無いこと、shell 構文が通ること
#   条件付き       … 実行権限。source される共通ライブラリや、利用者の
#                    リポジトリへコピーして使う素材には不要なので、
#                    「どう呼ばれるか」で要否が変わる。
check_unix_file() {
  f="$1"; require_exec="$2"; label="${f#"$KIT_DIR"/}"
  if LC_ALL=C grep -q $'\r' "$f"; then
    fail "$label に CR が混ざっている"
    return 1
  fi
  if ! bash -n "$f" 2>/dev/null; then
    fail "$label の shell 構文が不正"
    return 1
  fi
  if [ "$require_exec" = "1" ] && [ ! -x "$f" ]; then
    fail "$label に実行権限が無い (chmod +x してください)"
    return 1
  fi
  return 0
}

for f in "$KIT_DIR"/*.command "$KIT_DIR"/*.sh; do
  [ -f "$f" ] || continue
  label="${f#"$KIT_DIR"/}"
  # キット直下は利用者が直接叩く入口なので、実行権限を必須にする。
  check_unix_file "$f" 1 || continue
  # ERR トラップは -E (errtrace) が無いと関数の中へ引き継がれない。
  # その状態で関数内が失敗すると、何も表示しないまま画面が閉じ、
  # 利用者には「ダブルクリックしても何も起きない」としか見えない。
  if grep -q 'trap .* ERR' "$f" && ! grep -qE '^set -[A-Za-z]*E' "$f"; then
    fail "$label は ERR トラップを使っているのに set -E が無い (関数内の失敗が無言になる)"
    continue
  fi
  # 逆に set -E を使うなら、条件文の中のコマンド置換を書いてはいけない。
  # macOS 標準の bash 3.2 では、そこで失敗したコマンド置換の ERR が
  # 「無視されるはず」なのに後から関数内で発火する。実害は2つ:
  #   - 実際には処理が続くのに「中断しました」と誤って表示される
  #   - 後始末(rollback / rm -rf)が親の作業中に走る
  # BASHPID が無い 3.2 では実行時に主シェルとサブシェルを見分けられないため、
  # 構文そのものを禁止することでしか防げない。
  # 代わりに `x=$(cmd) || true` と書き、その後で $? や中身を見ること。
  if grep -qE '^set -[A-Za-z]*E' "$f" &&
     grep -nE '^[[:space:]]*(if|elif|while)[[:space:]]+!?[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=\$\(' "$f" |
       grep -q .; then
    fail "$label は set -E と『条件文の中のコマンド置換』を併用している (bash 3.2 で ERR が誤発火する)"
    grep -nE '^[[:space:]]*(if|elif|while)[[:space:]]+!?[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=\$\(' "$f" |
      sed 's/^/       /' >&2
    continue
  fi
  pass "$label (LF / 構文OK / 実行可)"
done

# --- 3-b. 下の階層の .sh (skills/ と scripts/) --------------------------
# これらも ZIP に入って利用者の手元へ渡るのに、これまで一度も検査して
# いなかった。CR が1本混ざれば利用者の環境で初めて壊れる。
#
# 実行権限の要否は「除外リスト」ではなく規則で決める。名前を並べた
# 除外リストは、対象が増えたときに黙って腐るため。
#   assets/ 配下          … 利用者のリポジトリへ cp して使う素材。不要
#   他から source される   … `. path/to/x.sh` で読み込む共通処理。不要
#   それ以外              … 単体で起動する想定なので必須
is_sourced_somewhere() {
  base=$(basename "$1")
  # `. <何か>/x.sh` または `source <何か>/x.sh` の形で参照されているか。
  # 自分自身の中の shellcheck ディレクティブは行頭が # なので当たらない。
  grep -rhE "(^|[[:space:]])(\.|source)[[:space:]]+[^[:space:]]*${base}([[:space:]]|\"|$)" \
    "$KIT_DIR" --include='*.sh' --include='*.command' 2>/dev/null | grep -q .
}

# `find | while` はパイプなのでサブシェルになり、中で FAILED=1 を立てても
# 親へ伝わらない(= 検査に落ちても ZIP ができてしまう)。IFS を改行にして
# 主シェルの for で回す。
SKILL_SH_LIST=$(find "$KIT_DIR" -mindepth 2 -name '*.sh' -type f 2>/dev/null | LC_ALL=C sort || true)
OLD_IFS=$IFS
IFS='
'
for f in $SKILL_SH_LIST; do
  IFS=$OLD_IFS
  [ -f "$f" ] || continue
  label="${f#"$KIT_DIR"/}"
  need_exec=1
  reason="単体起動"
  case "$f" in
    */assets/*) need_exec=0; reason="素材" ;;
  esac
  if [ "$need_exec" = "1" ] && is_sourced_somewhere "$f"; then
    need_exec=0
    reason="source専用"
  fi
  check_unix_file "$f" "$need_exec" || { IFS='
'; continue; }
  if [ "$need_exec" = "1" ]; then
    pass "$label (LF / 構文OK / 実行可)"
  else
    pass "$label (LF / 構文OK / 実行権限は不要: $reason)"
  fi
  IFS='
'
done
IFS=$OLD_IFS

# --- 4. 自己修復ロジックの正本が1つで、両 .command がそれを読んでいること ----
# 以前は両 .command に同じ関数を複製し byte 一致を検査していた。それは
# 「重複していること」を契約にする検査で、複製を減らす変更が必ずここで
# 落ちた。正本を scripts/lib/self-heal.sh の1か所にし、検査は
#   (a) 正本に self_heal_kit が定義されている
#   (b) 両 .command がその正本を source している (パスの綴りも含めて)
# の2点に置き換える。複製が無いので一致検査そのものが不要になる。
SELF_HEAL_LIB="$KIT_DIR/scripts/lib/self-heal.sh"
SELF_HEAL_SOURCE_LINE='. "$KIT_DIR/scripts/lib/self-heal.sh"'
if [ ! -f "$SELF_HEAL_LIB" ]; then
  fail "scripts/lib/self-heal.sh が無い (self_heal_kit の正本)"
elif ! grep -q '^self_heal_kit() {' "$SELF_HEAL_LIB"; then
  fail "scripts/lib/self-heal.sh に self_heal_kit の定義が無い"
else
  pass "self_heal_kit の正本: scripts/lib/self-heal.sh"
fi
for f in install-mac.command setup-env-mac.command; do
  if grep -q '^self_heal_kit() {' "$KIT_DIR/$f"; then
    fail "$f が self_heal_kit を自前で定義している (正本は scripts/lib/self-heal.sh)"
  elif ! grep -Fq "$SELF_HEAL_SOURCE_LINE" "$KIT_DIR/$f"; then
    fail "$f が scripts/lib/self-heal.sh を source していない"
  elif ! grep -q '^self_heal_kit$' "$KIT_DIR/$f"; then
    fail "$f が self_heal_kit を呼んでいない"
  else
    pass "$f は self_heal_kit を正本から読んでいる"
  fi
done

# --- 5. バッチのラベル整合性と、リダイレクト前置 -------------------------
# `echo %VER%> file` は VER 末尾の数字をファイルハンドル番号と解釈され、
# 空ファイルを作る。しかも install 自体は成功するので無症状で出荷される。
for f in "$KIT_DIR"/*.bat; do
  [ -f "$f" ] || continue
  label="${f#"$KIT_DIR"/}"
  if grep -n '^[^:r]*[^ ]%>' "$f" | grep -v '^\s*[0-9]*:rem' | grep -q .; then
    fail "$label に変数展開直後のリダイレクト (%>) がある。>\"file\" echo(... と前置すること"
  else
    pass "$label リダイレクト前置OK"
  fi
done

# --- 5-b. PowerShell の param 既定値が起動のされ方に依存しないこと --------
# param の既定式は「その引数を実際に使うか」に関係なく、束縛時に必ず評価される。
# そこで $PSScriptRoot などを計算していると、引数を明示的に渡していて既定値が
# 不要な呼び出しでも、その計算の失敗だけでスクリプトが本体に入る前に落ちる。
# しかも $PSScriptRoot は起動のされ方 (-File / dot-source / スクリプトブロック
# 経由) で空になりうるので、失敗は環境依存で、手元では再現しない。
PS1_LIST=$(find "$KIT_DIR" -name '*.ps1' -type f 2>/dev/null | LC_ALL=C sort || true)
OLD_IFS=$IFS
IFS='
'
for f in $PS1_LIST; do
  IFS=$OLD_IFS
  [ -f "$f" ] || { IFS='
'; continue; }
  label="${f#"$KIT_DIR"/}"
  # 注意すべきなのは実行される既定式だけ。コメントで名前に言及しただけの行を
  # 落とすと、理由を書けなくなる (実際にこの検査を書いた時に自分で踏んだ)。
  # 見るのはスクリプト自身の param だけ。範囲指定を字下げ込みで書くと、
  # 関数の param まで拾い、その範囲が本体のコードを飲み込んで誤検出する。
  # 桁0の param( から最初の桁0の ) までに限る。
  block=$(awk '/^param\(/ {inside=1} inside {print} inside && /^\)/ {exit}' "$f" |
    sed 's/#.*//')
  if printf '%s' "$block" |
     grep -q '\$PSScriptRoot\|\$PSCommandPath\|\$MyInvocation'; then
    fail "$label の param 既定値が \$PSScriptRoot 等に依存している (本体で解決すること)"
  else
    pass "$label param 既定値は起動方法に依存しない"
  fi
  IFS='
'
done
IFS=$OLD_IFS

# --- 5-c. ファイルの読み方が Windows の言語設定に依存しないこと -----------
# Windows PowerShell 5.1 の Get-Content は、BOM の無いファイルを ANSI コード
# ページ (英語 Windows なら 1252、日本語 Windows なら 932) で読む。UTF-8 で
# 書かれた日本語はそこで別の文字に化ける。
#   - 日本語の有無を見る検査は「書かれていない」と誤って落ちる
#   - 日本語を含むパスの一覧は壊れ、存在しない場所を指す。安全確認は
#     Get-Item が null を返して静かに素通りする(何も調べていないのに合格)
# どちらも利用者の Windows の言語設定次第で結果が変わる。-Encoding UTF8 か
# [IO.File]::ReadAllText を明示すること。
WINDOWS_SCRIPT_LIST=$(find "$KIT_DIR" \( -name '*.ps1' -o -name '*.bat' \) -type f \
  2>/dev/null | LC_ALL=C sort || true)
OLD_IFS=$IFS
IFS='
'
for f in $WINDOWS_SCRIPT_LIST; do
  IFS=$OLD_IFS
  [ -f "$f" ] || { IFS='
'; continue; }
  label="${f#"$KIT_DIR"/}"
  # コメント行は対象外。理由を書けなくなる。
  if grep -v '^\s*#' "$f" | grep -o 'Get-Content[^;){]*' |
     grep -qv '\-Encoding'; then
    fail "$label に -Encoding を付けない Get-Content がある (ANSI で読まれる)"
  else
    pass "$label ファイルの読み方は言語設定に依存しない"
  fi
  IFS='
'
done
IFS=$OLD_IFS

# --- 5-d. cmd.exe の括弧ブロックの中で文が切られていないこと ---------------
# cmd.exe は if ( ... ) else ( ... ) や for ... do ( ... ) を、実行前にブロック
# ごと解析する。その中に生の ) があるとそこがブロックの終わりとして解釈され、
# 続く語が文の先頭になって「xxx was unexpected at this time.」で即死する。
#   例: echo (1/4) pnpm はインストール済みです   -> pnpm was unexpected...
# 同じ文字列でもブロックの外なら壊れるため、文字列だけを見ても判定できない。
# 括弧の深さを数えながら見る必要がある。macOS では一切再現しない。
paren_report=$(python3 - "$KIT_DIR" <<'PY'
import glob
import os
import re
import sys

kit = sys.argv[1]


def strip_noise(line):
    """深さの計算から外すもの。"""
    if re.match(r'(?i)^\s*rem\b', line):
        return ''
    s = re.sub(r'\^.', '', line)          # ^( ^) は文字であって括弧ではない
    s = re.sub(r'"[^"]*"', '', s)         # 引用符の中は解析されない
    # echo( は「空文字や記号でも安全に出す」ための定型で、ブロックを開かない。
    # ここを括弧として数えると深さが以後ずっとずれ、正常な行を大量に NG にする。
    # 行頭とは限らない (& で連結された後にも出る) ので \b で拾い、ECHO( も見る。
    # 除外はこの形だけに絞る。この検査は落ちると ZIP を作らないため、
    # 誤検出のコストは「配れない」であり、緩めに倒す方が安全側になる。
    s = re.sub(r'(?i)\becho\(', 'echo ', s)
    return s


for path in sorted(glob.glob(os.path.join(kit, '**', '*.bat'), recursive=True)):
    depth = 0
    with open(path, encoding='utf-8', newline='') as f:
        lines = f.read().splitlines()
    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if depth > 0 and re.match(r'(?i)^(echo|set)\b', line):
            bare = re.sub(r'\^.', '', line)
            bare = re.sub(r'"[^"]*"', '', bare)
            bare = re.sub(r'(?i)^echo\(', 'echo ', bare)
            if '(' in bare or ')' in bare:
                print('%s:%d: %s' % (os.path.relpath(path, kit), i, line))
        s = strip_noise(raw)
        depth = max(0, depth + s.count('(') - s.count(')'))
PY
)
if [ -n "$paren_report" ]; then
  printf '%s\n' "$paren_report" | while IFS= read -r line; do
    fail "括弧ブロックの中に生の ( ) がある -> $line"
  done
  FAILED=1
else
  pass "cmd.exe の括弧ブロックの中で文が切られていない"
fi

# --- 6. Mac の環境差(Intel / Apple Silicon / Node の入れ方) --------------
# 静的検査では「PATH の組み立てが正しいか」までは分からない。
# 実機を用意する代わりに環境を注入して確かめる。
if [ -f "$SCRIPT_DIR/test-mac-env.sh" ]; then
  echo ""
  if bash "$SCRIPT_DIR/test-mac-env.sh"; then
    :
  else
    fail "Mac の環境差の検証に失敗した"
  fi
else
  fail "scripts/test-mac-env.sh が見つからない"
fi

# --- 7. setup-env-mac.command の判定 -------------------------------------
# Node のバージョン・アーキの食い違い・MCP を飛ばしたときの表示。
# いずれも「動くけれど間違ったことを伝える」種類の欠陥で、静的検査では
# 捕まらない。通し実行はネットワークと Node の入れ直しを伴うため、
# 判定を担う関数だけを取り出して評価する。
if [ -f "$SCRIPT_DIR/test-setup-env.sh" ]; then
  echo ""
  if bash "$SCRIPT_DIR/test-setup-env.sh"; then
    :
  else
    fail "setup-env-mac.command の判定の検証に失敗した"
  fi
else
  fail "scripts/test-setup-env.sh が見つからない"
fi

# --- 8. マニュアルの主要意味要素 ---------------------------------------
# 利用者の行動を変える重要な文言が、マニュアルの正本 (Markdown) に
# 存在することを機械的に担保する。
#
# 以前は同じ語句を md と html の両方に要求していた。それは「2形式が
# 重複して存在すること」を契約にする検査で、html を md から生成する、
# あるいは片方を畳む変更が必ずここで落ちた。契約は md の1か所に縮約し、
# html は md から派生する表示形式として扱う (生成に切り替えた時点で
# 「生成物 == コミット済み html」の1行検査を足せばよい)。
#
# 終了状態の文言だけは setup-env-mac.command の出力が正本なので、
# 「スクリプトが実際に出す文言がマニュアルにも書いてある」という向きで見る。
check_doc_phrase() { # check_doc_phrase <md> <phrase> <label>
  md=$1; phrase=$2; label=$3
  if grep -Fq "$phrase" "$md"; then
    pass "$label"
  else
    fail "$label が ${md#"$KIT_DIR"/} に無い"
  fi
}

check_doc_file_phrase() { # check_doc_file_phrase <file> <phrase> <label>
  check_doc_phrase "$1" "$2" "$3"
}

# Mac の第一経路はダブルクリック。ターミナルは「開けなかったとき」の
# 退避経路であり、順序が入れ替わると利用者が最初につまずく。
check_doc_phrase "$KIT_DIR/manual-mac.md" \
  '開けなかったときだけ、ターミナルから実行します' 'Mac のターミナル退避経路'
check_doc_phrase "$KIT_DIR/manual-mac.md" \
  "$NODE_REQUIREMENT" 'Mac の Node.js 要件が正本と一致'
check_doc_phrase "$KIT_DIR/manual-windows.md" \
  '展開前に「ブロックの解除」をするのが最も簡単です。' 'Windows の展開前解除'
check_doc_phrase "$KIT_DIR/manual-windows.md" \
  '展開後でも、インストーラーが自動解除を試みます。' 'Windows の展開後回復'
check_doc_phrase "$KIT_DIR/manual-windows.md" \
  "$NODE_REQUIREMENT" 'Windows の Node.js 要件が正本と一致'
check_doc_file_phrase "$KIT_DIR/README.md" "$NODE_REQUIREMENT" 'README の Node.js 要件が正本と一致'

# インストール先がグローバルであること、MCP が別ステップであること、
# 残骸 .mcp.json の対処、observability の登録は、いずれも
# 「これが書かれていないと利用者が詰まる」性質の文言。
for _os in mac windows; do
  check_doc_phrase "$KIT_DIR/manual-$_os.md" \
    'どのフォルダで作業していても使えます' "$_os のグローバル配置の明示"
  check_doc_phrase "$KIT_DIR/manual-$_os.md" \
    'プロジェクトごとに入れ直す必要はありません' "$_os の再導入不要の明示"
  check_doc_phrase "$KIT_DIR/manual-$_os.md" \
    '古い形式の MCP 設定が見つかりました' "$_os の残骸 .mcp.json 対処"
  check_doc_phrase "$KIT_DIR/manual-$_os.md" \
    'cloudflare-observability' "$_os の observability 連携"
  check_doc_phrase "$KIT_DIR/manual-$_os.md" \
    '管理者専用の手段です。通常は使いません。' "$_os の sync-project 管理者限定"
done
check_doc_file_phrase "$KIT_DIR/README.md" 'cloudflare-observability' \
  'README の observability 連携'

# 終了表示は実装の3状態をそのまま利用者へ伝える。正本はスクリプトの出力。
for state in \
  'セットアップが完全に完了しました！' \
  '基本セットアップ完了 / 変更系MCPは必要時に認証' \
  '基本セットアップ完了 / 一部の連携は未設定'
do
  check_doc_file_phrase "$KIT_DIR/setup-env-mac.command" \
    "$state" "終了状態の正本 (setup-env-mac.command): $state"
  check_doc_phrase "$KIT_DIR/manual-mac.md" \
    "$state" "Mac の終了状態: $state"
  check_doc_phrase "$KIT_DIR/manual-windows.md" \
    "$state" "Windows の終了状態: $state"
done

# --- 8-b. manual html が md の生成結果と一致していること -----------------
# html は scripts/gen-manual-html.mjs が md から機械生成する表示形式。
# 手で直した html や、md だけ直して生成し忘れた html を配らないよう、
# 「生成物 == コミット済み html」を1行で検査する。node が無い環境では
# 判定できないので、見逃さず fail にする (Node.js はキットの前提条件)。
GEN_MANUAL="$KIT_DIR/scripts/gen-manual-html.mjs"
if ! command -v node >/dev/null 2>&1; then
  fail "node が無いため manual html の生成一致を検査できない"
elif node "$GEN_MANUAL" --check >/dev/null 2>&1; then
  pass "manual-*.html は manual-*.md の生成結果と一致"
else
  fail "manual-*.html が manual-*.md と一致しない (node scripts/gen-manual-html.mjs で再生成する)"
fi

# --- 9. 配布対象を Git の可視ファイルだけに固定 -------------------
# ソースディレクトリを丸ごと ZIP にすると、ignored のローカル設定や
# secret が混入する。tracked + nonignored untracked を NUL 区切りで受け、
# 日本語・空白を含むパスもそのまま一時 stage へ複製する。
PACKAGE_WORK=$(mktemp -d) || { echo "作業フォルダを作れません" >&2; exit 1; }
VERIFY_DIR=""
cleanup() {
  rm -rf "$PACKAGE_WORK"
  [ -z "$VERIFY_DIR" ] || rm -rf "$VERIFY_DIR"
}
trap cleanup EXIT

KIT_REL=${KIT_DIR#"$REPO_DIR"/}
GIT_LIST="$PACKAGE_WORK/git-visible-files"
if ! git -C "$REPO_DIR" ls-files -z --cached --others --exclude-standard -- \
     "$KIT_REL" > "$GIT_LIST"; then
  fail "Git から配布対象を取得できない"
fi

STAGE_ROOT="$PACKAGE_WORK/$(basename "$KIT_DIR")"
mkdir -p "$STAGE_ROOT"
PACKAGE_FILE_COUNT=0
while IFS= read -r -d '' rel; do
  case "$rel" in
    "$KIT_REL"/*) ;;
    *) fail "配布対象がキット外を指している: $rel"; continue ;;
  esac
  case "$rel" in
    *$'\n'*|*$'\r'*|*$'\t'*)
      fail "inventory に表現できない制御文字付きパス: $rel"
      continue
      ;;
  esac
  source_path="$REPO_DIR/$rel"
  stage_rel=${rel#"$KIT_REL"/}
  stage_path="$STAGE_ROOT/$stage_rel"
  if [ ! -e "$source_path" ]; then
    fail "Git に見えるが作業ツリーに無い: $rel"
    continue
  fi
  if [ -L "$source_path" ]; then
    fail "配布対象のシンボリックリンクは未対応: $rel"
    continue
  fi
  mkdir -p "$(dirname "$stage_path")"
  if cp -pP "$source_path" "$stage_path"; then
    PACKAGE_FILE_COUNT=$((PACKAGE_FILE_COUNT + 1))
  else
    fail "stage へ複製できない: $rel"
  fi
done < "$GIT_LIST"

if [ "$PACKAGE_FILE_COUNT" -eq 0 ]; then
  fail "配布対象が 0 件"
else
  pass "Git で可視な配布対象: $PACKAGE_FILE_COUNT ファイル"
fi

# Apache License 2.0 の 4(a) は「Work / Derivative Works の各コピーに
# ライセンスの写しを添える」ことを求める。ZIP は利用者へ渡る「コピー」
# そのものなので、この3点が stage に入らないまま配ることはできない。
# `git ls-files --others --exclude-standard` は未追跡でも拾うが、
# .gitignore の変更ひとつで静かに落ちるため、明示的に検算する。
# 両 .command が起動時に source する共通処理。stage に入っていなければ
# 展開直後の最初のダブルクリックで止まる。git ls-files 経由で拾われる
# 前提だが、.gitignore や配置換えで静かに落ちないよう明示的に検算する。
if [ -s "$STAGE_ROOT/scripts/lib/self-heal.sh" ]; then
  pass "配布物に共通処理を同梱: scripts/lib/self-heal.sh"
else
  fail "配布物に scripts/lib/self-heal.sh が入っていない (両 .command が起動できない)"
fi

for legal in LICENSE NOTICE ATTRIBUTION.md; do
  if [ -s "$STAGE_ROOT/$legal" ]; then
    pass "配布物にライセンス表記を同梱: $legal"
  else
    fail "配布物に $legal が入っていない (Apache-2.0 4(a) 違反)"
  fi
done

# 利用者が最初に開く入口と、ダブルクリックで読める手引き。README は
# エージェント・開発者向けに縮約したので、非エンジニアの導線はこの
# 4 ファイルに依存する。stage に無ければ「展開したが何をすればよいか
# 分からない」状態で届くため明示的に検算する。
for entry in START-HERE.md manual-mac.html manual-windows.html CHANGELOG.md; do
  if [ -s "$STAGE_ROOT/$entry" ]; then
    pass "配布物に利用者向け文書を同梱: $entry"
  else
    fail "配布物に $entry が入っていない"
  fi
done

# stage の html を md から生成し直す。8-b で一致を確認済みなので通常は
# 同じ内容になるが、配る html が必ず md 由来であることを生成側でも担保する。
if command -v node >/dev/null 2>&1 && [ -s "$STAGE_ROOT/manual-mac.md" ]; then
  if node "$GEN_MANUAL" --out-dir "$STAGE_ROOT" >/dev/null 2>&1; then
    pass "stage の manual-*.html を md から生成"
  else
    fail "stage の manual-*.html を生成できない"
  fi
fi

file_mode() {
  # GNU stat の -f は「ファイルシステム情報」を表示して成功するため、
  # BSD/macOS 形式を先に試すとLinuxでもフォールバックされない。
  # GNU形式を先にし、未対応のmacOSだけBSD形式へ切り替える。
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null
}

write_inventory() { # write_inventory <root> <output>
  root=$1; output=$2
  list="$PACKAGE_WORK/inventory-files-$$"
  (
    cd "$root"
    find . -type f ! -name '.aidd-package-inventory' -print |
      sed 's#^\./##' | LC_ALL=C sort
  ) > "$list"
  : > "$output"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    hash=$(shasum -a 256 "$root/$rel" | awk '{print $1}')
    mode=$(file_mode "$root/$rel")
    printf '%s\t%s\t%s\n' "$hash" "$mode" "$rel" >> "$output"
  done < "$list"
  rm -f "$list"
}

INVENTORY="$STAGE_ROOT/.aidd-package-inventory"
if write_inventory "$STAGE_ROOT" "$INVENTORY"; then
  pass "配布 inventory を作成"
else
  fail "配布 inventory を作成できない"
fi

if [ "$FAILED" != "0" ]; then
  echo ""
  echo "配布前チェックに失敗しました。ZIP は作成していません。"
  exit 1
fi

echo ""
echo "配布前チェック: すべて合格"

# --- 10. ZIP 作成 ------------------------------------------------------
echo ""
if [ "$CHECK_ONLY" = "1" ]; then
  echo "=== 一時ZIPを生成して再検証 ==="
  ZIP_PATH="$PACKAGE_WORK/aidd-agent-kit.check.zip"
else
  echo "=== ZIP 作成 ==="
  mkdir -p "$DIST_DIR"
  ZIP_PATH="$DIST_DIR/aidd-agent-kit.zip"
fi
rm -f "$ZIP_PATH"

# 隔離属性は作業ツリーからは外さない。配布用 stage だけを整えることで、
# 開発者のローカルファイルに破壊的な副作用を出さない。
xattr -cr "$STAGE_ROOT" 2>/dev/null || true

# -X: macOS 固有の付加属性を入れない (Windows 側で __MACOSX が散らからない)
# zip は Unix のパーミッションを外部属性として保持するため、実行権限が残る。
(
  cd "$PACKAGE_WORK"
  zip -r -X -q "$ZIP_PATH" "$(basename "$STAGE_ROOT")"
)
if [ "$CHECK_ONLY" = "1" ]; then
  pass "検査用の一時ZIPを作成 ($(du -h "$ZIP_PATH" | cut -f1))"
else
  pass "作成: $ZIP_PATH ($(du -h "$ZIP_PATH" | cut -f1))"
fi

# --- 11. 作成後の検証: 展開し直して壊れていないか確認 ---------------------
# 「作れた」と「展開したら使える」は別物。ここを確認しないと、
# 実行権限の欠落が利用者の手元で初めて発覚する。
echo ""
echo "=== 展開して再検証 ==="
VERIFY_DIR=$(mktemp -d)
unzip -q "$ZIP_PATH" -d "$VERIFY_DIR"
EX="$VERIFY_DIR/$(basename "$KIT_DIR")"

# ZIP に入れたファイル集合・内容・実行権限が、stage で固定した
# inventory と完全に一致することを確かめる。
ACTUAL_INVENTORY="$VERIFY_DIR/actual-inventory"
if [ ! -f "$EX/.aidd-package-inventory" ]; then
  fail "展開結果に .aidd-package-inventory が無い"
else
  write_inventory "$EX" "$ACTUAL_INVENTORY"
  if diff -u "$EX/.aidd-package-inventory" "$ACTUAL_INVENTORY" >/dev/null; then
    pass "展開結果が配布 inventory と一致"
  else
    fail "展開結果が配布 inventory と不一致"
    diff -u "$EX/.aidd-package-inventory" "$ACTUAL_INVENTORY" >&2 || true
  fi
fi

for f in "$EX"/*.command "$EX"/*.sh; do
  [ -f "$f" ] || continue
  if [ -x "$f" ]; then
    pass "実行権限を保持: ${f#"$EX"/}"
  else
    fail "実行権限が失われた: ${f#"$EX"/}"
  fi
done
for f in "$EX"/*.bat; do
  [ -f "$f" ] || continue
  if LC_ALL=C grep -q -v $'\r$' "$f"; then
    fail "改行が壊れた: ${f#"$EX"/}"
  else
    pass "CRLF を保持: ${f#"$EX"/}"
  fi
done

if [ "$FAILED" != "0" ]; then
  echo ""
  echo "展開後の検証に失敗しました。この ZIP は配布しないでください。"
  rm -f "$ZIP_PATH"
  exit 1
fi

if [ "$CHECK_ONLY" = "1" ]; then
  echo ""
  echo "配布前チェック: 一時ZIPの生成・展開再検証まで、すべて合格"
  exit 0
fi

echo ""
echo "==============================================="
echo "  配布物ができました (v$VERSION)"
echo "  $ZIP_PATH"
echo "==============================================="
echo ""
echo "Windows へ渡すときの注意:"
echo "  ZIP を受け取った人は、展開する前に ZIP を右クリック →"
echo "  プロパティ → 「ブロックの解除」にチェック → OK を実行してください。"
echo "  展開前の解除が最も簡単です。展開後でもインストーラーが自動解除を試み、"
echo "  失敗時は記録と手動解除手順を表示します。"
