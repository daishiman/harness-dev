#!/bin/bash
# shellcheck disable=SC2329
# =====================================================
#  AI開発エージェントキット インストーラー (Mac用)
#  Claude Code と OpenAI Codex の両方へ同時導入します
#  バージョンは VERSION を正本とする
# =====================================================

set -Ee
cd "$(dirname "$0")"
KIT_DIR=$(pwd -P)

[ -f VERSION ] || { echo "[エラー] VERSION が見つかりません。" >&2; exit 1; }
KIT_VERSION=$(tr -d '\r\n' < VERSION)
case "$KIT_VERSION" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "[エラー] VERSION の形式が不正です。" >&2; exit 1 ;;
esac
INSTALL_HOME="${AIDD_TARGET_HOME:-$HOME}"
while case "$INSTALL_HOME" in *'//'*) true ;; *) false ;; esac; do
  INSTALL_HOME=${INSTALL_HOME//\/\//\/}
done
INSTALL_HOME=${INSTALL_HOME%/}
CLAUDE_DIR="$INSTALL_HOME/.claude"
CODEX_DIR="${AIDD_CODEX_TARGET:-${CODEX_HOME:-$INSTALL_HOME/.codex}}"
while case "$CODEX_DIR" in *'//'*) true ;; *) false ;; esac; do
  CODEX_DIR=${CODEX_DIR//\/\//\/}
done
CODEX_DIR=${CODEX_DIR%/}
CODEX_SKILLS_DIR="$INSTALL_HOME/.agents/skills"
# INV-14: 上書き前に backup、失敗時は manifest 単位で rollback、stale 削除は旧 manifest との差分だけ、HOME 外へ書かない
STAMP=$(date +%Y%m%d-%H%M%S)
CLAUDE_BACKUP_DIR="$CLAUDE_DIR/backup-$STAMP"
CODEX_BACKUP_DIR="$CODEX_DIR/backup-$STAMP"
CLAUDE_MANIFEST="$CLAUDE_DIR/aidd-agent-kit.manifest"
CLAUDE_VERSION_FILE="$CLAUDE_DIR/aidd-agent-kit.version"
CODEX_MANIFEST="$CODEX_DIR/aidd-agent-kit.manifest"
CODEX_VERSION_FILE="$CODEX_DIR/aidd-agent-kit.version"
# setup-env-mac.command が記録する最終確認状態。
# ファイルの存在だけで ready とは判定しない。
# MCP の登録先は常に user scope なので、この目印も $HOME 側に固定する
# (AIDD_TARGET_HOME で project scope へ入れる場合でも、MCP は共通)。
SETUP_STAMP="$HOME/.claude/aidd-agent-kit.setup-env"
LEGACY_PROMPTS=0
TRANSACTION_ACTIVE=0
WORK_DIR=""

finish() {
  status="${1:-0}"
  echo ""
  if [ "${AIDD_NONINTERACTIVE:-0}" != "1" ] && [ -t 0 ]; then
    read -r -p "Enterキーを押すとこのウィンドウを閉じられます..." _unused
  fi
  exit "$status"
}

cleanup() {
  if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
    rm -rf "$WORK_DIR"
  fi
}

# --- ファイルの指紋(SHA256)を取る -------------------------------------
# 入力: 標準入力に1行1パス / 出力: "<sha256>|<パス>"
#
# 1つの道具に賭けない理由: 以前は perl -MDigest::SHA だけを使っていたが、
# Apple は同梱スクリプト言語(perl / python)の廃止を予告している。
# 消えた時点でインストーラーが丸ごと動かなくなるので、
# macOS 標準で複数ある道具を順に試す。パスに空白が含まれても壊れないよう、
# 受け渡しは NUL 区切りにする。
hash_file_list() {
  if command -v shasum >/dev/null 2>&1; then
    # 出力: "<hash><空白2>path"
    tr '\n' '\0' | xargs -0 shasum -a 256 |
      sed 's/^\([0-9a-f][0-9a-f]*\)  /\1|/'
  elif command -v openssl >/dev/null 2>&1; then
    # 出力: "<hash><空白>*path" (-r は coreutils 互換形式)
    tr '\n' '\0' | xargs -0 openssl dgst -sha256 -r |
      sed 's/^\([0-9a-f][0-9a-f]*\) \*\{0,1\}/\1|/'
  elif command -v perl >/dev/null 2>&1; then
    perl -MDigest::SHA -e '
      while (<STDIN>) {
        chomp;
        open my $fh, "<", $_ or die "$!: $_\n";
        binmode $fh;
        my $sha = Digest::SHA->new(256);
        $sha->addfile($fh);
        print $sha->hexdigest, "|", $_, "\n";
      }
    '
  else
    echo "[エラー] ファイルの照合に必要なコマンドが見つかりません" >&2
    echo "        (shasum / openssl / perl のいずれも使えません)。" >&2
    return 1
  fi
}

# --- キットの自己修復 -------------------------------------------------
# 本体は scripts/lib/self-heal.sh (setup-env-mac.command と共通の正本)。
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

target_for() {
  client="$1"
  relative="$2"
  if [ "$client" = "C" ]; then
    printf '%s/%s\n' "$CLAUDE_DIR" "$relative"
  else
    case "$relative" in
      skills/*) printf '%s/%s\n' "$CODEX_SKILLS_DIR" "${relative#skills/}" ;;
      *) printf '%s/%s\n' "$CODEX_DIR" "$relative" ;;
    esac
  fi
}

backup_root_for() {
  if [ "$1" = "C" ]; then
    printf '%s\n' "$CLAUDE_BACKUP_DIR"
  else
    printf '%s\n' "$CODEX_BACKUP_DIR"
  fi
}

rollback() {
  [ "$TRANSACTION_ACTIVE" -eq 1 ] || return 0
  echo "[復元] 途中までの変更を元に戻しています..."
  _restore_failed=0
  while IFS='|' read -r client relative existed; do
    [ -n "$client" ] || continue
    target=$(target_for "$client" "$relative")
    backup_root=$(backup_root_for "$client")
    rm -rf "$target" 2>/dev/null || _restore_failed=$((_restore_failed + 1))
    if [ "$existed" = "1" ]; then
      mkdir -p "$(dirname "$target")" 2>/dev/null || true
      cp -pR "$backup_root/$relative" "$target" 2>/dev/null ||
        _restore_failed=$((_restore_failed + 1))
    fi
  done < "$WORK_DIR/rollback-items"
  TRANSACTION_ACTIVE=0

  # 復元の失敗を握りつぶして「戻しました」と言うのが、このスクリプトで
  # いちばん危ない振る舞いになる。利用者はその報告を信じ、中途半端に
  # 混ざった状態のまま使い続けてしまい、しかも原因を追う手がかりが無い。
  # 戻せなかったなら、戻せなかったと言い、退避先を必ず指し示す。
  if [ "$_restore_failed" -eq 0 ]; then
    echo "[復元] インストール前の状態へ戻しました。"
  else
    echo "[復元] $_restore_failed 件を元に戻せませんでした。"
    echo "       退避したファイルは消さずに残してあります:"
    # `[ -d x ] && echo` と書くと、偽のときに文全体が失敗扱いになり、
    # set -e / ERR トラップを踏む。復元中に更に中断するのは最悪なので if で書く。
    if [ -d "$CLAUDE_BACKUP_DIR" ]; then echo "         $CLAUDE_BACKUP_DIR"; fi
    if [ -d "$CODEX_BACKUP_DIR" ]; then echo "         $CODEX_BACKUP_DIR"; fi
    echo "       この画面のまま導入支援の担当者にお見せください。"
  fi
  unset _restore_failed
}

on_error() {
  # set -E により、ERR はコマンド置換 $(...) などのサブシェルでも発火しうる。
  # そこで rollback / cleanup が走ると、親がまだ使っている作業フォルダを
  # 消してしまい、インストールを途中で壊す。後始末は主シェルだけの仕事にする。
  #
  # 注意: この判定は bash 4 以降でしか効かない。macOS 標準の bash 3.2 には
  # BASHPID が無く、$$ はサブシェルでも主シェルと同じ値になるため素通りする。
  # 3.2 側の防御は「条件文の中でコマンド置換を使わない」ことで、
  # package-kit.sh がその構文の混入を検査している。
  [ "${BASHPID:-$$}" = "$$" ] || return 0
  trap - ERR INT TERM
  set +e
  rollback
  cleanup
  echo ""
  echo "[エラー] インストールを完了できなかったため中断しました。"
  echo "部分的な導入は残さず、可能な範囲で元の状態へ復元しました。"
  finish 1
}

trap on_error ERR INT TERM
trap cleanup EXIT

case "$CLAUDE_DIR|$CODEX_DIR|$CODEX_SKILLS_DIR" in
  /*'|'/*'|'/*) ;;
  *)
    echo "[エラー] AIDD_TARGET_HOME と AIDD_CODEX_TARGET（未指定時は HOME / CODEX_HOME）は絶対パスで指定してください。"
    finish 1
    ;;
esac

for arg in "$@"; do
  case "$arg" in
    --legacy-prompts) LEGACY_PROMPTS=1 ;;
    *)
      echo "[エラー] 未対応のオプションです: $arg"
      echo "使用可能: --legacy-prompts"
      finish 1
      ;;
  esac
done

self_heal_kit

echo ""
echo "==============================================="
echo "  AI開発エージェントキット インストーラー (Mac)"
echo "  Claude Code + OpenAI Codex / $KIT_VERSION"
echo "==============================================="
echo ""

# --- ステップ 1/6: コピー元と形式の事前検証 ----------------------
# `codex/workflow-skills` は配布元の分類名であり、実配置の `.codex/skills`
# ではない。Codex のスキルは常に `.agents/skills` へ配布する。
for required in skills agents commands codex/workflow-skills codex/agents; do
  if [ ! -d "$required" ]; then
    echo "[エラー] インストールに必要なフォルダが見つかりません: $required"
    echo "ZIPを展開後、その中の install-mac.command を実行してください。"
    finish 1
  fi
done
if [ "$LEGACY_PROMPTS" -eq 1 ] && [ ! -d "codex/prompts" ]; then
  echo "[エラー] legacy prompts のコピー元が見つかりません: codex/prompts"
  finish 1
fi
if [ ! -f "agents/app-orchestrator.md" ] || \
   [ ! -f "codex/app-orchestrator-openai.yaml" ]; then
  echo "[エラー] app-orchestrator のCodex用ファイルが揃っていません。"
  finish 1
fi

# Apache License 2.0 の 4(a) は「Work / Derivative Works の各コピーに
# ライセンスの写しを添える」ことを求める。このキットは cloudflare/skills
# 由来のファイルを含むため、配置物にもこの3点が必ず同行する必要がある。
# 揃っていないものを配るほうが問題なので、ここは警告ではなく停止させる。
for required_legal in LICENSE NOTICE ATTRIBUTION.md; do
  if [ ! -f "$required_legal" ]; then
    echo "[エラー] ライセンス関連ファイルが見つかりません: $required_legal"
    echo "配布物が不完全です。導入支援の担当者にお知らせください。"
    finish 1
  fi
  if [ -L "$required_legal" ]; then
    echo "[エラー] ライセンス関連ファイルがシンボリックリンクです: $required_legal"
    finish 1
  fi
done

WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/aidd-agent-kit.XXXXXX")
: > "$WORK_DIR/maps"
: > "$WORK_DIR/skill-names"
: > "$WORK_DIR/affected"
: > "$WORK_DIR/rollback-items"
: > "$WORK_DIR/check-paths"

validate_skill() {
  file="$1"
  expected="$2"
  actual=$(awk '
    NR == 1 && $0 != "---" { exit 20 }
    NR > 1 && $0 == "---" { closed=1; exit }
    NR > 1 && $1 == "name:" { sub(/^[[:space:]]*name:[[:space:]]*/, ""); name=$0 }
    NR > 1 && $1 == "description:" {
      sub(/^[[:space:]]*description:[[:space:]]*/, "")
      desc=$0
      if (desc ~ /^[>|][0-9+-]*[[:space:]]*$/) block=1
      next
    }
    block && $0 ~ /^[[:space:]]+[^[:space:]]/ { block_content=1 }
    END {
      if (!closed || name == "" || desc == "" || (block && !block_content)) exit 21
      print name
    }
  ' "$file") || {
    echo "[エラー] SKILL.md のfrontmatterが不正です: $file"
    return 1
  }
  if [ "$actual" != "$expected" ]; then
    echo "[エラー] スキル名と配布先名が一致しません: $file"
    echo "  name: $actual / 配布先: $expected"
    return 1
  fi
  case "$actual" in
    ''|*[!a-z0-9-]*|-*|*-) echo "[エラー] スキル名が不正です: $actual"; return 1 ;;
  esac
  if grep -Fx "$actual" "$WORK_DIR/skill-names" >/dev/null 2>&1; then
    echo "[エラー] Codexで同名になるスキルが重複しています: $actual"
    return 1
  fi
  printf '%s\n' "$actual" >> "$WORK_DIR/skill-names"
}

for dir in skills/*/ codex/workflow-skills/*/; do
  [ -d "$dir" ] || continue
  name=$(basename "$dir")
  [ -f "$dir/SKILL.md" ] || {
    echo "[エラー] SKILL.md がありません: $dir"
    finish 1
  }
  validate_skill "$dir/SKILL.md" "$name" || finish 1
done
validate_skill "agents/app-orchestrator.md" "app-orchestrator" || finish 1

# TOML の検査に python3 を使えるか。使えないなら下の awk 版で検査する。
#
# 注意: 判定に `command -v python3` だけを使ってはいけない。macOS の
# /usr/bin/python3 は Xcode コマンドラインツール未導入だと「実体はまだ無いが
# 存在はする」スタブで、実行した瞬間に『コマンドライン・デベロッパ・ツールを
# インストールしますか？』の GUI ダイアログが出る。非エンジニアの画面に
# インストーラーと無関係なダイアログを出さないため、実体の有無を先に見る。
PYTHON_TOML=0
if command -v python3 >/dev/null 2>&1; then
  PYTHON_TOML=1
  case "$(command -v python3)" in
    /usr/bin/python3)
      # Apple 標準の場所。CLT が入っていなければスタブなので触らない。
      xcode-select -p >/dev/null 2>&1 || PYTHON_TOML=0
      ;;
  esac
  if [ "$PYTHON_TOML" = "1" ] && ! python3 -c 'import tomllib' >/dev/null 2>&1; then
    # tomllib は Python 3.11 以降。古い python3 なら awk 版へ落とす。
    PYTHON_TOML=0
  fi
fi

for toml in codex/agents/*.toml; do
  [ -f "$toml" ] || continue
  if [ "$PYTHON_TOML" = "1" ]; then
    python3 - "$toml" <<'PY' || {
import re
import sys
import tomllib

with open(sys.argv[1], "rb") as source:
    data = tomllib.load(source)
required = {"name", "description", "developer_instructions"}
if not required.issubset(data):
    raise SystemExit(1)
if not re.fullmatch(r"[a-z][a-z0-9_]*", data["name"]):
    raise SystemExit(1)
if any(not isinstance(data[key], str) or not data[key].strip() for key in required):
    raise SystemExit(1)
PY
      echo "[エラー] CodexカスタムエージェントのTOML構文または必須形式が不正です: $toml"
      finish 1
    }
  elif ! awk '
    BEGIN { top=1 }
    function fail() { bad=1 }
    inblock {
      if ($0 ~ /^[[:space:]]*"""[[:space:]]*$/) { inblock=0; closed=1; next }
      if ($0 ~ /[^[:space:]]/) content=1
      next
    }
    /^[[:space:]]*($|#)/ { next }
    /^[[:space:]]*\[/ { top=0; next }
    top && /^[[:space:]]*name[[:space:]]*=[[:space:]]*"[a-z][a-z0-9_]*"[[:space:]]*$/ {
      if (name++) fail(); next
    }
    top && /^[[:space:]]*description[[:space:]]*=[[:space:]]*"[^"\r\n]+"[[:space:]]*$/ {
      if (description++) fail(); next
    }
    top && /^[[:space:]]*developer_instructions[[:space:]]*=[[:space:]]*"[^"\r\n]+"[[:space:]]*$/ {
      if (instructions++) fail(); content=1; closed=1; next
    }
    top && /^[[:space:]]*developer_instructions[[:space:]]*=[[:space:]]*"""[[:space:]]*$/ {
      if (instructions++) fail(); inblock=1; next
    }
    { next }
    END { if (bad || inblock || !closed || !content || name != 1 || description != 1 || instructions != 1) exit 1 }
  ' "$toml"; then
    echo "[エラー] Codexカスタムエージェントの必須形式が不正です: $toml"
    finish 1
  fi
done

SOURCE_LINK_ROOTS="skills agents commands codex/workflow-skills codex/agents"
if [ "$LEGACY_PROMPTS" -eq 1 ]; then
  SOURCE_LINK_ROOTS="$SOURCE_LINK_ROOTS codex/prompts"
fi
# shellcheck disable=SC2086
if find $SOURCE_LINK_ROOTS -type l -print -quit | grep . >/dev/null 2>&1 || \
   [ -L "codex/app-orchestrator-openai.yaml" ]; then
  echo "[エラー] コピー元にシンボリックリンクが含まれています。"
  finish 1
fi

append_tree() {
  client="$1"
  source_root="$2"
  relative_root="$3"
  find "$source_root" -type f -print | LC_ALL=C sort | while IFS= read -r source; do
    suffix=${source#"$source_root"/}
    printf '%s|%s|%s/%s\n' "$client" "$source" "$relative_root" "$suffix"
  done >> "$WORK_DIR/maps"
}

append_tree C skills skills
append_tree C agents agents
append_tree C commands commands
append_tree X skills skills
append_tree X codex/workflow-skills skills
printf '%s\n' 'X|agents/app-orchestrator.md|skills/app-orchestrator/SKILL.md' >> "$WORK_DIR/maps"
printf '%s\n' 'X|codex/app-orchestrator-openai.yaml|skills/app-orchestrator/agents/openai.yaml' >> "$WORK_DIR/maps"
append_tree X codex/agents agents
# Claude 側と Codex 側は別の manifest で管理されるため、両方へ配る。
# 名前を `aidd-agent-kit.` で始めるのは、利用者自身が置いた LICENSE と
# 取り違えないため、かつ既存の manifest / version と同じ平置きに揃えるため。
for legal_pair in 'LICENSE|aidd-agent-kit.LICENSE' \
                  'NOTICE|aidd-agent-kit.NOTICE' \
                  'ATTRIBUTION.md|aidd-agent-kit.ATTRIBUTION.md'; do
  printf 'C|%s\n' "$legal_pair" >> "$WORK_DIR/maps"
  printf 'X|%s\n' "$legal_pair" >> "$WORK_DIR/maps"
  # .agents/skills は .codex とは別のツリーで、Apache-2.0 由来の再頒布物を
  # 含む。§4(a) は「頒布物にライセンス本文を添えること」を求めるので、
  # ここにも同じ3点を置く。ディレクトリではなくファイルなので、
  # skill探索(<名前>/SKILL.md を探す)には拾われない。
  printf 'X|%s|skills/%s\n' "${legal_pair%%|*}" "${legal_pair#*|}" >> "$WORK_DIR/maps"
done
if [ "$LEGACY_PROMPTS" -eq 1 ]; then
  append_tree X codex/prompts prompts
fi

if awk -F'|' '{ print $1 "|" $3 }' "$WORK_DIR/maps" | LC_ALL=C sort | uniq -d | grep . >/dev/null 2>&1; then
  echo "[エラー] 複数のコピー元が同じ配布先を使用しています。"
  finish 1
fi

valid_relative() {
  relative="$1"
  case "$relative" in
    ''|/*|*'|'*|*\\*) return 1 ;;
  esac
  case "/$relative/" in
    */../*|*/./*) return 1 ;;
  esac
  case "$relative" in
    skills/*|agents/*|commands/*|prompts/*|aidd-agent-kit.manifest|aidd-agent-kit.version) return 0 ;;
    aidd-agent-kit.LICENSE|aidd-agent-kit.NOTICE|aidd-agent-kit.ATTRIBUTION.md) return 0 ;;
    *) return 1 ;;
  esac
}

top_item() {
  relative="$1"
  case "$relative" in
    skills/*/*) rest=${relative#skills/}; printf 'skills/%s\n' "${rest%%/*}" ;;
    *) printf '%s\n' "$relative" ;;
  esac
}

while IFS='|' read -r client source relative; do
  case "$source" in *'|'*)
    echo "[エラー] コピー元パスに使用できない文字があります: $source"
    finish 1
    ;;
  esac
  valid_relative "$relative" || {
    echo "[エラー] 安全でない配布先です: $relative"
    finish 1
  }
  printf '%s|%s\n' "$client" "$(top_item "$relative")" >> "$WORK_DIR/affected"
  printf '%s|%s\n' "$client" "$relative" >> "$WORK_DIR/check-paths"
done < "$WORK_DIR/maps"

collect_old_manifest() {
  client="$1"
  manifest="$2"
  [ -f "$manifest" ] || return 0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    case "$line" in *'|'*) relative=${line#*|} ;; *) relative=$line ;; esac
    valid_relative "$relative" || continue
    printf '%s|%s\n' "$client" "$(top_item "$relative")" >> "$WORK_DIR/affected"
    printf '%s|%s\n' "$client" "$relative" >> "$WORK_DIR/check-paths"
  done < "$manifest"
}

collect_old_manifest C "$CLAUDE_MANIFEST"
collect_old_manifest X "$CODEX_MANIFEST"
printf '%s\n' \
  'C|aidd-agent-kit.manifest' 'C|aidd-agent-kit.version' \
  'X|aidd-agent-kit.manifest' 'X|aidd-agent-kit.version' >> "$WORK_DIR/affected"
printf '%s\n' \
  'C|aidd-agent-kit.manifest' 'C|aidd-agent-kit.version' \
  'X|aidd-agent-kit.manifest' 'X|aidd-agent-kit.version' >> "$WORK_DIR/check-paths"
LC_ALL=C sort -u "$WORK_DIR/affected" -o "$WORK_DIR/affected"
LC_ALL=C sort -u "$WORK_DIR/check-paths" -o "$WORK_DIR/check-paths"

# manifestは実配置の所有契約。バックアップ前に生成し、
# 完全なno-opなら書き込みとバックアップを一切行わない。
awk -F'|' '{ print $2 }' "$WORK_DIR/maps" | LC_ALL=C sort -u > "$WORK_DIR/sources"
hash_file_list < "$WORK_DIR/sources" > "$WORK_DIR/source-hashes"
# 道具が途中で落ちても、行数が合わなければここで止まる。
# ハッシュが欠けた manifest は「変更なし」の誤判定を生み、
# 更新が黙って反映されない状態を作るため、必ず検算する。
SRC_COUNT=$(wc -l < "$WORK_DIR/sources" | tr -d ' ')
HASH_COUNT=$(wc -l < "$WORK_DIR/source-hashes" | tr -d ' ')
if [ "$SRC_COUNT" != "$HASH_COUNT" ]; then
  echo "[エラー] ファイルの照合に失敗しました ($SRC_COUNT 件中 $HASH_COUNT 件)。" >&2
  echo "この画面のまま導入支援の担当者にお見せください。" >&2
  finish 1
fi

awk -F'|' '
  NR == FNR { hash[$2]=$1; next }
  $1 == "C" { print hash[$2] "|" $3 }
' "$WORK_DIR/source-hashes" "$WORK_DIR/maps" | LC_ALL=C sort -u > "$WORK_DIR/claude.manifest"
awk -F'|' '
  NR == FNR { hash[$2]=$1; next }
  $1 == "X" { print hash[$2] "|" $3 }
' "$WORK_DIR/source-hashes" "$WORK_DIR/maps" | LC_ALL=C sort -u > "$WORK_DIR/codex.manifest"
printf '%s\n' "$KIT_VERSION" > "$WORK_DIR/version"

NOOP=1
while IFS='|' read -r client source relative; do
  target=$(target_for "$client" "$relative")
  if [ ! -f "$target" ] || ! cmp -s "$source" "$target"; then
    NOOP=0
    break
  fi
done < "$WORK_DIR/maps"
cmp -s "$WORK_DIR/claude.manifest" "$CLAUDE_MANIFEST" || NOOP=0
cmp -s "$WORK_DIR/codex.manifest" "$CODEX_MANIFEST" || NOOP=0
cmp -s "$WORK_DIR/version" "$CLAUDE_VERSION_FILE" || NOOP=0
cmp -s "$WORK_DIR/version" "$CODEX_VERSION_FILE" || NOOP=0

if [ -d "$CODEX_DIR/skills" ]; then
  echo "[情報] $CODEX_DIR/skills はAIDDキットの配布先ではありません。"
  echo "  AIDD Skillの配置先: $CODEX_SKILLS_DIR"
  echo "  Codex組込installer等が管理する既存ファイルは変更しません。"
  echo ""
fi

# --- 「どこに何が入ったか」を必ず見せる -------------------------------
# 利用者からいちばん多い誤解が「このキットはプロジェクトの中に入るのでは?」
# というもの。実際は既定で $HOME 配下(ユーザー全体)に入っている。
# 入った実パスと件数をその場で見せれば、この誤解は1画面で解ける。
# 変更なしで終わるときも表示する。「何も出ないと何も入っていないように見える」
# ためで、ここを黙ると誤解が残ったままになる。
print_placement_summary() {
  _skills=$(find "$CLAUDE_DIR/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  _agents=$(find "$CLAUDE_DIR/agents" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  _commands=$(find "$CLAUDE_DIR/commands" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  _codex_skills=$(find "$CODEX_SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  _codex_agents=$(find "$CODEX_DIR/agents" -maxdepth 1 -type f -name '*.toml' 2>/dev/null | wc -l | tr -d ' ')

  echo ""
  echo "配置先(実際に入った場所と件数):"
  echo "  $CLAUDE_DIR/skills"
  echo "      スキル ${_skills}個"
  echo "  $CLAUDE_DIR/agents"
  echo "      エージェント ${_agents}個"
  echo "  $CLAUDE_DIR/commands"
  echo "      コマンド ${_commands}個"
  echo "  $CODEX_SKILLS_DIR"
  echo "      Codex スキル ${_codex_skills}個"
  echo "  $CODEX_DIR/agents"
  echo "      Codex custom agent (.toml) ${_codex_agents}個"
  echo "  ※ AIDDキットは .codex/skills へ配布しません。"
  echo ""
  # 既定は $HOME(ユーザー全体)。AIDD_TARGET_HOME で project scope へ入れた
  # ときにまで「グローバルです」と言うと、今度は逆向きの嘘になる。
  # 実際の置き場所から判定して、言い分を切り替える。
  echo "-----------------------------------------------"
  if [ "$INSTALL_HOME" = "$HOME" ]; then
    echo "  これはグローバル(ユーザー全体)に入りました。"
    echo "  どのフォルダからでも使えます。"
    echo "  プロジェクトごとに入れ直す必要はありません。"
    echo "-----------------------------------------------"
    echo "  置き場所はあなたのホームフォルダ($INSTALL_HOME)の中です。"
    echo "  特定のプロジェクトの中には入れていません。"
  else
    echo "  これはプロジェクト限定(project scope)に入りました。"
    echo "  このフォルダの中で作業しているときだけ使えます。"
    echo "-----------------------------------------------"
    echo "  置き場所: $INSTALL_HOME"
    echo "  ユーザー全体で使いたい場合は、AIDD_TARGET_HOME を指定せずに"
    echo "  install-mac.command を実行してください。"
  fi
  echo ""
  unset _skills _agents _commands _codex_skills _codex_agents
}

# --- MCP(Cloudflare 連携)が未設定のままかを見る -----------------------
# インストーラーはファイルを配るだけで、MCP は1つも登録しない。
# 登録するのは setup-env-mac.command のほうなので、それを実行していない人は
# 「入れ終わった」と思ったまま、連携が何も無い状態で使い始めてしまう。
#
# 自動で続けて実行してしまう案は採らなかった。setup-env は Node.js の導入、
# MCPのuser/global登録・接続確認で数分かかる。このインストーラーは数秒で終わる
# 冪等な処理として設計されており(途中失敗はロールバックする)、性質が違う。
# 代わりに「未実行を検出して明示し、対話中なら本人の同意を得てその場で実行する」。
print_mcp_status_and_offer() {
  _setup_state=""
  _setup_date=""
  if [ -f "$SETUP_STAMP" ]; then
    _setup_state=$(sed -n 's/^state=//p' "$SETUP_STAMP" 2>/dev/null | tail -n 1) || _setup_state=""
    case "$_setup_state" in
      attempted|registered|auth_pending|ready|failed) ;;
      *) _setup_state="" ;;
    esac
    _setup_date=$(sed -n 's/^date=//p' "$SETUP_STAMP" 2>/dev/null | tail -n 1) || _setup_date=""
  fi

  case "$_setup_state" in
    ready)
      echo "Cloudflare 連携(MCP): 前回の接続確認は ready です。"
      [ -z "$_setup_date" ] || echo "  確認日時: $_setup_date"
      echo "  (現在状態を再確認するときは setup-env-mac.command を実行)"
      echo ""
      unset _setup_state _setup_date
      return 0
      ;;
    auth_pending)
      echo "Cloudflare 連携(MCP): 現在の作業で必要な対象がOAuth認証待ちです。"
      echo "  エージェントが示した対象1件だけへ必要最小限の権限を認可してください。"
      echo ""
      unset _setup_state _setup_date
      return 0
      ;;
    registered)
      echo "Cloudflare 連携(MCP): user/global登録済みです。"
      echo "  docsは利用可能です。変更系MCPは、その機能を初めて使う時だけ認証します。"
      echo ""
      unset _setup_state _setup_date
      return 0
      ;;
    failed)
      echo "Cloudflare 連携(MCP): 前回のセットアップは失敗しました。"
      ;;
    attempted)
      echo "Cloudflare 連携(MCP): セットアップ開始済み / 登録・ready未確認です。"
      ;;
    "")
      if [ -f "$SETUP_STAMP" ]; then
        echo "Cloudflare 連携(MCP): 旧形式の記録のため ready とは判定できません。"
      fi
      ;;
  esac

  echo "==============================================="
  echo "  [未完了] Cloudflare 連携(MCP)は ready ではありません"
  echo "==============================================="
  echo ""
  echo "このインストーラーはキット本体を配っただけです。"
  echo "アプリの公開やログ確認に必要な連携は、次のスクリプトで設定します。"
  echo "  $KIT_DIR/setup-env-mac.command"
  echo ""

  # project scope への反映(sync-project 経由の管理作業)では聞かない。
  # 目的が「リポジトリへの反映」であって、環境構築ではないため。
  if [ "${AIDD_NONINTERACTIVE:-0}" = "1" ] || [ ! -t 0 ] ||
     [ "$INSTALL_HOME" != "$HOME" ]; then
    echo "続けて setup-env-mac.command を実行してください。"
    echo ""
    unset _setup_state _setup_date
    return 0
  fi

  printf '続けて開発環境セットアップ(Node.js・pnpm・Cloudflare連携)を実行しますか? [Y/n]: '
  read -r _answer || _answer=""
  case "$_answer" in
    [nN]|[nN][oO])
      echo ""
      echo "分かりました。あとで setup-env-mac.command をダブルクリックしてください。"
      echo "(実行するまで Cloudflare 連携は使えません)"
      echo ""
      unset _setup_state _setup_date
      ;;
    *)
      echo ""
      _setup_status=0
      if [ -x "$KIT_DIR/setup-env-mac.command" ]; then
        "$KIT_DIR/setup-env-mac.command" || _setup_status=$?
      else
        bash "$KIT_DIR/setup-env-mac.command" || _setup_status=$?
      fi
      if [ "$_setup_status" -ne 0 ]; then
        echo "==============================================="
        echo "  [部分成功] キット導入済み / 開発環境・MCP未完了"
        echo "==============================================="
        echo "キット本体はそのまま保持します。上の原因を解消後、"
        echo "setup-env-mac.command を再実行してください。"
        unset _answer _setup_state _setup_date
        return "$_setup_status"
      fi
      ;;
  esac
  unset _answer _setup_state _setup_date _setup_status
}

if [ "$NOOP" -eq 1 ]; then
  echo "[OK] 配布先はキット $KIT_VERSION と一致しています。"
  echo "     変更がないため、バックアップと書き込みは行いません。"
  print_placement_summary
  SETUP_CONTINUE_STATUS=0
  print_mcp_status_and_offer || SETUP_CONTINUE_STATUS=$?
  if [ "$SETUP_CONTINUE_STATUS" -ne 0 ]; then
    finish "$SETUP_CONTINUE_STATUS"
  fi
  finish 0
fi

# --- ステップ 2/6: 上書き先と祖先リンクの安全確認 ---------------
echo "Claude Code: $CLAUDE_DIR"
echo "Codex skills: $CODEX_SKILLS_DIR"
echo "Codex custom agents: $CODEX_DIR/agents"
if [ "$LEGACY_PROMPTS" -eq 1 ]; then
  echo "Codex legacy prompts: 有効"
fi
echo ""

check_path_chain() {
  path="$1"
  boundary="$2"
  current="$path"
  while [ -n "$current" ]; do
    if [ -L "$current" ]; then
      echo "[確認] 上書き対象またはその祖先がリンクになっています。"
      echo "  対象: $path"
      echo "  リンク: $current -> $(readlink "$current")"
      return 1
    fi
    [ "$current" = "$boundary" ] && return 0
    [ "$current" = "/" ] && break
    case "$current" in
      */*) current=${current%/*}; [ -n "$current" ] || current="/" ;;
      *) current="" ;;
    esac
  done
  echo "[エラー] 上書き対象が想定したインストール先の外にあります: $path"
  return 1
}

check_path_chain "$CLAUDE_BACKUP_DIR" "$INSTALL_HOME" || finish 1
check_path_chain "$CODEX_BACKUP_DIR" "$CODEX_DIR" || finish 1

while IFS='|' read -r client relative; do
  target=$(target_for "$client" "$relative")
  if [ "$client" = "C" ]; then
    boundary="$INSTALL_HOME"
  else
    case "$relative" in
      skills/*) boundary="$INSTALL_HOME" ;;
      *) boundary="$CODEX_DIR" ;;
    esac
  fi
  check_path_chain "$target" "$boundary" || finish 1
done < "$WORK_DIR/check-paths"

# --- ステップ 3/6: 全変更対象のバックアップ ----------------------
backup_item() {
  client="$1"
  relative="$2"
  target=$(target_for "$client" "$relative")
  backup_root=$(backup_root_for "$client")
  if [ -e "$target" ]; then
    mkdir -p "$backup_root/$(dirname "$relative")"
    cp -pR "$target" "$backup_root/$relative"
    diff -qr "$target" "$backup_root/$relative" >/dev/null
    printf '%s|%s|1\n' "$client" "$relative" >> "$WORK_DIR/rollback-items"
  else
    printf '%s|%s|0\n' "$client" "$relative" >> "$WORK_DIR/rollback-items"
  fi
}

while IFS='|' read -r client relative; do
  backup_item "$client" "$relative"
done < "$WORK_DIR/affected"
TRANSACTION_ACTIVE=1

if [ -d "$CLAUDE_BACKUP_DIR" ]; then
  echo "Claude Code の変更対象を検証付きでバックアップしました: $CLAUDE_BACKUP_DIR"
fi
if [ -d "$CODEX_BACKUP_DIR" ]; then
  echo "Codex の変更対象を検証付きでバックアップしました: $CODEX_BACKUP_DIR"
fi

# --- ステップ 4/6: 旧manifest所有ファイルの整理 -------------------

new_has_relative() {
  client="$1"
  relative="$2"
  awk -F'|' -v c="$client" -v r="$relative" '$1 == c && $3 == r { found=1 } END { exit !found }' "$WORK_DIR/maps"
}

new_has_prefix() {
  client="$1"
  relative="$2"
  awk -F'|' -v c="$client" -v p="$relative/" \
    '$1 == c && index($3, p) == 1 { found=1 } END { exit !found }' \
    "$WORK_DIR/maps"
}

STALE_DIRS="$WORK_DIR/stale-dirs"
: > "$STALE_DIRS"

clean_stale() {
  client="$1"
  manifest="$2"
  [ -f "$manifest" ] || return 0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    old_hash=""
    case "$line" in
      *'|'*) old_hash=${line%%|*}; relative=${line#*|} ;;
      *) relative=$line ;;
    esac
    valid_relative "$relative" || continue
    new_has_relative "$client" "$relative" && continue
    target=$(target_for "$client" "$relative")
    [ -e "$target" ] || continue

    if [ -n "$old_hash" ] && [ -f "$target" ]; then
      # hash付きmanifestに掲載された廃止ファイルは、内容が利用者により
      # 変更されていても旧キット所有。変更版も事前バックアップ済みなので
      # liveから除去して標準状態へ収束させる。
      rm -f "$target"
      dirname "$target" >> "$STALE_DIRS"
      continue
    fi

    if [ -f "$target" ]; then
      rm -f "$target"
      dirname "$target" >> "$STALE_DIRS"
    elif [ -d "$target" ]; then
      if new_has_prefix "$client" "$relative"; then
        # 現役skillは上書き対象の配布ファイルだけを更新し、knowledge等は残す。
        echo "[保持] 現役スキル内の追加ファイル: $target"
      else
        # v1 manifestが所有していた廃止skill。ディレクトリ全体は事前に
        # 検証済みバックアップ済みなので、liveから安全に整理できる。
        rm -rf "$target"
        dirname "$target" >> "$STALE_DIRS"
      fi
    fi
  done < "$manifest"
}

clean_stale C "$CLAUDE_MANIFEST"
clean_stale X "$CODEX_MANIFEST"

# --- ステップ 5/6: ファイル単位コピー ----------------------------
echo "Claude Code と Codex へファイルをコピーしています..."
while IFS='|' read -r client source relative; do
  target=$(target_for "$client" "$relative")
  mkdir -p "$(dirname "$target")"
  cp -p "$source" "$target"
done < "$WORK_DIR/maps"

# 廃止ファイルを消した結果、中身が空になった旧ディレクトリを片付ける。
# コピー後に実行することで、現役ファイルが入り直したディレクトリは
# 「空でない」ため対象外になる。空のものだけを下から上へ辿って削除し、
# 管理ルート自身には到達しない。ls -A で空と確認できたものだけを消すため、
# 利用者が置いたファイルを巻き込まない。
if [ -s "$STALE_DIRS" ]; then
  while IFS= read -r stale_dir; do
    d="$stale_dir"
    while [ -n "$d" ] && [ -d "$d" ] && [ -z "$(ls -A "$d")" ]; do
      case "$d" in
        "$CLAUDE_DIR"|"$CODEX_DIR"|"$CODEX_SKILLS_DIR"|"$INSTALL_HOME"|/|.) break ;;
      esac
      rmdir "$d" 2>/dev/null || break
      d=$(dirname "$d")
    done
  done < "$STALE_DIRS"
fi

# --- ステップ 6/6: 内容・形式検証とmanifestの原子的更新 -----------
while IFS='|' read -r client source relative; do
  target=$(target_for "$client" "$relative")
  if [ ! -f "$target" ] || ! cmp -s "$source" "$target"; then
    echo "[エラー] コピー元と配布先が一致しません: $target"
    false
  fi
done < "$WORK_DIR/maps"

install_record() {
  source="$1"
  target="$2"
  mkdir -p "$(dirname "$target")"
  cp -p "$source" "$target.new.$$"
  cmp -s "$source" "$target.new.$$"
  mv -f "$target.new.$$" "$target"
  cmp -s "$source" "$target"
}

install_record "$WORK_DIR/claude.manifest" "$CLAUDE_MANIFEST"
install_record "$WORK_DIR/codex.manifest" "$CODEX_MANIFEST"
install_record "$WORK_DIR/version" "$CLAUDE_VERSION_FILE"
install_record "$WORK_DIR/version" "$CODEX_VERSION_FILE"

# コピー後のSKILL/TOML形式も、同じ内容であることに加えて再確認する。
while IFS= read -r name; do
  validate_target=$(target_for X "skills/$name/SKILL.md")
  awk 'NR==1 && $0=="---" { ok=1 } END { exit !ok }' "$validate_target"
done < "$WORK_DIR/skill-names"
for toml in codex/agents/*.toml; do
  [ -f "$toml" ] || continue
  cmp -s "$toml" "$CODEX_DIR/agents/$(basename "$toml")"
done

CLAUDE_SKILLS=$(find skills -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
CODEX_COMMAND_SKILLS=$(find codex/workflow-skills -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
CODEX_SKILLS=$((CLAUDE_SKILLS + CODEX_COMMAND_SKILLS + 1))
CLAUDE_AGENTS=$(find agents -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')
CLAUDE_COMMANDS=$(find commands -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')
CODEX_AGENTS=$(find codex/agents -maxdepth 1 -type f -name '*.toml' | wc -l | tr -d ' ')
LEGACY_PROMPT_COUNT=0
if [ "$LEGACY_PROMPTS" -eq 1 ]; then
  LEGACY_PROMPT_COUNT=$(find codex/prompts -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')
fi

TRANSACTION_ACTIVE=0
echo ""
echo "==============================================="
echo "  両方へのインストールが完了しました！"
echo "==============================================="
echo ""
echo "  Claude Code: スキル ${CLAUDE_SKILLS}個 / エージェント${CLAUDE_AGENTS}個 / コマンド${CLAUDE_COMMANDS}個"
echo "  OpenAI Codex: スキル ${CODEX_SKILLS}個 / カスタムエージェント${CODEX_AGENTS}個"
if [ "$LEGACY_PROMPTS" -eq 1 ]; then
  echo "  Codex legacy prompts: ${LEGACY_PROMPT_COUNT}個"
fi
print_placement_summary
SETUP_CONTINUE_STATUS=0
print_mcp_status_and_offer || SETUP_CONTINUE_STATUS=$?
if [ "$SETUP_CONTINUE_STATUS" -ne 0 ]; then
  finish "$SETUP_CONTINUE_STATUS"
fi
echo "次にやること:"
echo "  1. Claude Code と Codex を終了して起動し直す"
echo "  2. Claude Code: /build-app 作りたいものの説明"
echo "  3. Codex: \$build-app 作りたいものの説明"
finish 0
