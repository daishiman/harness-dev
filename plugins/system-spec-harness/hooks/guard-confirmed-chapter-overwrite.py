#!/usr/bin/env python3
# /// script
# name: guard-confirmed-chapter-overwrite
# version: 0.1.0
# purpose: 確定済み仕様章 (system-spec/ の status:confirmed 章 かつ 正本 spec-state.json の
#          対応セルが『確定』・非再オープン) と 正本 spec-state.json 自身への Write/Edit/Bash 動的書換を
#          PreToolUse で遮断する defense-in-depth の層別 fail-closed hook (要件 C3 の派生安全要件)。
#          Bash はコマンド文字列の字面ではなく書込み先の実パスで判定する。
#          正本防御は C01/C03 の単一 writer/transition gate。本 hook は二重化の補助防御。
#          正本位置は spec-state-contract.md「正本位置」節で確定した
#          $CLAUDE_PROJECT_DIR/system-spec/spec-state.json の 1 経路のみ (配下 rglob 探索は持たない)。
# inputs:
#   - stdin: PreToolUse hook JSON ({tool_name, tool_input{file_path|command}})
#   - env: CLAUDE_PROJECT_DIR (正本 system-spec/spec-state.json の探索起点。未設定時は cwd)
# outputs:
#   - exit: 0=許可 / 2=ブロック(stderr に理由)。判定は層別:
#           (1) 正本 spec-state.json への直接/動的書換は fail-closed (確定巻き戻し防御)。
#           (2) status:confirmed 章 Write/Edit かつ 正本 spec-state 解決不能は confirmed 章限定で fail-closed。
#           (3) それ以外の章判定は誤爆回避優先 (明確に protected でないものは通す)。
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""PreToolUse(Write|Edit|Bash) 確定章 / 正本 spec-state.json 保護ガード。

判定ソース (章保護 = 2 系統の論理積・章粒度の集約):
  1. system-spec/ 配下の章 Markdown の frontmatter 確定マーカー `status: confirmed`
     (対象パス自身を load して判定する。別ファイルの内容には依存しない)
  2. C03 実出力 frontmatter の `spec_cells:[<cat>.<pf>, ...]` (後方互換で単一
     `cell`/`cell_id`/`spec_cell` や `category`+`platform` も可) が指す全対応セルが
     正本 spec-state.json 上で終端状態 (確定 or 対象外) かつ再オープン対象を含まないこと

正本位置 (SSOT): `spec-state.json` の判定ソースは `<root>/system-spec/spec-state.json` の 1 経路のみ。
  配下 rglob フォールバックは持たない (同梱 fixture 等を判定ソースに拾う交差汚染を構造的に排除)。

Write|Edit:
  (a) file_path が正本 spec-state.json (実パス一致) かつ確定 (非再オープン) セルを含むなら exit2
      (Bash 経路と同格の直接書換/確定巻き戻し防御)。別位置の同名 spec-state.json は正本でなく通す。
  (b) file_path が status:confirmed 章 かつ 上記 2 条件を満たす確定章なら exit2。
  (c) file_path が status:confirmed 章 だが 正本 spec-state を解決できない (load 不能) ときは
      confirmed 章限定で安全側 exit2 (F3 層別 fail-closed。誤爆範囲は confirmed 章に限定)。
  それ以外 (通常ファイル・未確定/再オープン章・新規章・確定セルなき spec-state) は exit0 で素通し。

Bash:
  コマンド文字列に保護パスが現れるかではなく、書込み先の実パスで判定する。書込み先として集めるのは
  出力リダイレクト先、変更系コマンド (sed -i/tee/cp/mv/rm/dd/truncate/install/ln) の対象引数
  (cp/mv/install/ln の宛先がディレクトリなら <宛先>/<元の basename>)、python (-c と heredoc の本文) の
  open(...,'w'|'a'|'x'|'+')・Path.write_text・os.remove・shutil.move 等の対象引数。
  bash -c / eval は中身を同じ規則で再帰的に解析する。heredoc の本文はコードとして実行される
  (python/bash の stdin) ときだけ解析し、cat > f <<EOF のようなデータ本文は書込み先にしない。
    - 書込み先が 正本 spec-state.json (system-spec/spec-state.json) か、実パス (symlink 解決後) が
      確定章なら exit2。
    - 書込み先を静的に特定できない (変数/glob/コマンド置換/find -exec/xargs 経由) 書込みがあり、
      かつコマンドが保護領域 (system-spec/ 配下・パス境界一致) を参照するときは安全側で exit2。
      ただし書込み先の basename が静的に読め、.md でも spec-state.json でもなければ保護対象に
      なりえないので曖昧扱いしない ("$OUT/progress.json" や rm -rf **/__pycache__ は通す)。
    - それ以外 (読み取りのみ・保護領域外への書込み・再オープン章・新規章への具体的書込) は exit0。
  診断のために system-spec/ のパスをデータや読み取り元として書き、書込み先は eval-log/ 等の保護領域外、
  というコマンドは通す (C19 live trial f11 の誤検知)。`system-spec/` はパス境界 (完全なパスセグメント)
  として扱い、自plugin パスの `system-spec-harness/` 等を部分文字列で誤検出しない。
  引用が閉じない等で shell として解析できないときは、書込み指標があれば書込み先不明として扱う。

fail-closed 方針 (層別): 書込み先を静的に特定できず保護領域を参照する Bash 書換 と、正本 spec-state 解決不能な
confirmed 章 Write/Edit のみ安全側で拒否する (計画 C11 exit_semantics=fail-closed-exit2)。それ以外の章判定は
「明確に protected と判定できないなら通す」を基本にする (誤爆回避優先)。全書換経路の正本防御は
C01/C03 の単一 writer/transition gate が担う。本 hook は補助 (二重化)。

block ゲートとの相補関係 (C16/C14): required-info-catalog.json の missing_effect=block item が未充足の
間は、上流 C01 R2/R5 が confirm を含む writer apply/chunk に --required-info を付け、
候補 state を既存 validate_required_info で検査してからだけ公開する。確定前の元 state に
確定接地を要求せず、候補の qa_ref/qa_refs -> qa_log.required_info_items で接地を確認する。すなわち
「未収集の必須情報を残したまま確定させない」のは上流の収集ゲート側の責務。本 hook はその結果 confirmed になった章の
事後的な上書き/巻き戻しを防ぐ層であり、block ゲートとは前段 (確定させない) / 後段 (確定を保護) の
相補的な二層をなす。本 hook 側で block 未充足を再判定・遮断することはしない (責務境界の明確化)。
"""
from __future__ import annotations

import ast
import json
import os
import re
import shlex
import sys
from pathlib import Path

CONFIRMED = "確定"
GUARD_NAME = "guard-confirmed-chapter-overwrite"
# 正本位置 (spec-state-contract.md「正本位置」節): <root>/system-spec/spec-state.json の 1 経路のみ。
SPEC_DIR = "system-spec"
SPEC_STATE_NAME = "spec-state.json"
# Bash コマンド内で正本 spec-state を参照しているかの判定に使う末尾構造 (system-spec/spec-state.json)。
_CANONICAL_SUFFIX = f"{SPEC_DIR}/{SPEC_STATE_NAME}"
# 章保護の終端セル状態 (確定 or 対象外)。両者とも settled であり確定章に含まれ得る
# (例: security 章 = web/mobile/tablet 確定 + desktop×3 対象外 の混在でも status:confirmed)。
TERMINAL_STATES = {"確定", "対象外"}
# writer (apply-spec-transition.py apply_cell_op reopen) が確定巻き戻し時に付す正本キー
# (reopened_from/reopen_reason) + 後方互換キー。いずれかがあれば当該セルは R4-reopen 済み。
_REOPEN_KEYS = ("reopened_from", "reopen_reason", "reopened", "reopen", "reopened_at", "reopened_by")

# shell として解析できないときの字面の書込み指標 (in-place 変更を行うツール群)。
_MUTATION_TOOLS = (
    (re.compile(r"\bsed\s+(?:-[a-zA-Z]*i|--in-place)\b"), "sed -i"),
    (re.compile(r"\btee\b"), "tee"),
    (re.compile(r"\bcp\b"), "cp"),
    (re.compile(r"\bmv\b"), "mv"),
    (re.compile(r"\brm\b"), "rm"),
    (re.compile(r"\bdd\b"), "dd"),
    (re.compile(r"\btruncate\b"), "truncate"),
    (re.compile(r"\binstall\b"), "install"),
    (re.compile(r"\bln\b"), "ln"),
)
# python のコードを構文解析できないときの字面の書込み指標。
_PY_WRITE = re.compile(
    r"""open\s*\([^)]*['"][wax]\+?b?['"]"""
    r"""|write_text\s*\("""
    r"""|\.write\s*\("""
    r"""|json\.dump\s*\("""
    r"""|os\.(?:remove|unlink|rename|replace)\s*\("""
    r"""|shutil\.(?:copy|move|rmtree)\s*\("""
)
# 出力リダイレクト (`>`/`>>`) の対象トークン。`2>&1` 等の fd 複製は (?!&) で除外。
_REDIRECT = re.compile(r"""\d*>>?\s*(?!&)("[^"]*"|'[^']*'|[^\s;|&>]+)""")
# 書込み先トークンが静的に決まらない (変数/コマンド置換/glob/brace 展開) ことを示す文字。
_DYN_CHARS = re.compile(r"[$`*?\[\]{}]")
# 保護領域 (system-spec/ ディレクトリ) をパス境界 (完全なパスセグメント) で参照しているか。
# 前後をデリミタ/末尾で束ねるため、自plugin パスの `system-spec-harness` (直後が '-') には発火しない。
_PROTECTED_SEG = re.compile(r"""(?:^|[\s;|&<>()'"=/])system-spec(?:/|[\s;|&<>()'"]|$)""")

# ── Bash 書込み先の抽出に使う表 ──
# heredoc の開始 (`<<EOF` / `<<-'EOF'` / `<<"EOF"`)。here-string `<<<` は除く。
_HEREDOC_OP = re.compile(r"""(?<!<)<<(-?)[ \t]*(?:'([^'\n]+)'|"([^"\n]+)"|\\?([A-Za-z_][A-Za-z0-9_]*))""")
_HEREDOC_MARK = re.compile(r"__HEREDOC_(\d+)__")
_SHELL_PUNCT = "();<>|&\n"
# 出力リダイレクト演算子 (`>`/`>>`/`&>`/`>|`/`>&`/`<>`)。
_OUT_REDIRECT_OP = re.compile(r"(?:>>?|>\||>&|<>)$")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PYTHON = re.compile(r"^(?:python|pypy)[0-9.]*$")
_WRAPPERS = {"sudo", "env", "command", "nohup", "time", "exec", "nice"}
# コマンドの前に置かれる予約語 (`for ...; do sed -i ...` の sed をコマンドとして読むため飛ばす)。
_KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{"}
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
# 対象ファイルを引数で受けて変更するコマンド (find -exec / xargs 経由の検出にも使う)。
_MUTATORS = {"sed", "tee", "cp", "mv", "rm", "dd", "truncate", "install", "ln", "unlink", "shred"}
# 値を取るオプション (その次のトークンは書込み先ではない)。
_VALUE_OPTS = {
    "cp": {"-S"}, "mv": {"-S"}, "ln": {"-S"}, "install": {"-m", "-o", "-g", "-S"},
    "truncate": {"-s", "-r"},
}
# python: builtin open と同じ引数順の open。
_PY_OPENERS = {"open", "io.open", "codecs.open", "gzip.open", "bz2.open", "lzma.open"}
# python: 関数名 -> 書込み先になる位置引数の番号。
_PY_FUNC_WRITERS = {
    "os.remove": (0,), "os.unlink": (0,), "os.rename": (0, 1), "os.replace": (0, 1),
    "shutil.copy": (1,), "shutil.copy2": (1,), "shutil.copyfile": (1,),
    "shutil.move": (0, 1), "shutil.rmtree": (0,),
}
_PY_MODE = re.compile(r"^[rwaxbtU+]+$")
# 入れ子の bash -c / eval を解析する深さの上限 (超えたら書込み先不明として扱う)。
_MAX_DEPTH = 3


# ── パス種別判定 ────────────────────────────────────────────────────────────
def _is_system_spec_md(p: Path) -> bool:
    """system-spec/ 配下の .md か (system-spec を完全なパスセグメントとして判定)。"""
    return p.suffix == ".md" and SPEC_DIR in p.parts


def project_root() -> Path:
    """正本 system-spec/spec-state.json の探索起点。env 優先・無ければ cwd。"""
    env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    return Path.cwd()


# ── frontmatter / spec-state 読み取り ───────────────────────────────────────
def parse_frontmatter(text: str) -> dict:
    """章 Markdown の YAML 風 frontmatter (--- ... ---) をスカラ辞書へ。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    for raw in parts[1].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    return fm


def _parse_spec_cells(raw) -> list[tuple[str, str]]:
    """frontmatter の spec_cells を (category, platform) 列へ。

    C03 実出力は `spec_cells: [database.web, database.mobile, ...]` (`.` 区切り list)。
    parse_frontmatter はこれをスカラ文字列 '[database.web, ...]' として渡すため
    文字列/リスト双方を受け、各要素を最初の '.' で category/platform に分割する
    (category・platform とも '.' を含まないため一意)。
    """
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        items = [x.strip() for x in s.split(",")]
    elif isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw]
    else:
        return []
    out: list[tuple[str, str]] = []
    for it in items:
        cat, sep, pf = it.partition(".")
        if sep and cat.strip() and pf.strip():
            out.append((cat.strip(), pf.strip()))
    return out


def _extract_cell_refs(fm: dict) -> list[tuple[str, str]]:
    """frontmatter から spec-state 対応セル (category, platform) 群を得る。

    C03 実出力 (`category` + `spec_cells:[<cat>.<pf>, ...]`) を第一に解釈し、後方互換で
    単一 `cell`/`cell_id`/`spec_cell` (区切り /:|) や `category`+`platform` (単数) も解釈する。
    重複は排除し frontmatter 出現順を保つ。
    """
    refs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(cat: str, plat: str) -> None:
        key = (cat.strip(), plat.strip())
        if key[0] and key[1] and key not in seen:
            seen.add(key)
            refs.append(key)

    # C03 実形状: spec_cells list
    for cat, plat in _parse_spec_cells(fm.get("spec_cells")):
        _add(cat, plat)
    # 後方互換: 単一 cell 系キー
    for key in ("cell", "cell_id", "spec_cell"):
        v = fm.get(key)
        if isinstance(v, str) and v:
            for sep in ("/", ":", "|"):
                if sep in v:
                    cat, _, plat = v.partition(sep)
                    _add(cat, plat)
                    break
    # 後方互換: category + platform (単数)
    cat, plat = fm.get("category"), fm.get("platform")
    if cat and plat:
        _add(cat, plat)
    return refs


def canonical_spec_state_path(root: Path) -> Path:
    """正本 spec-state.json の絶対想定パス (<root>/system-spec/spec-state.json)。"""
    return root.absolute() / SPEC_DIR / SPEC_STATE_NAME


def load_spec_state(root: Path) -> dict | None:
    """正本位置 <root>/system-spec/spec-state.json のみを判定ソースに読む。

    配下 rglob フォールバックは持たない (同梱 fixture 等の別 spec-state.json を
    判定ソースに拾う交差汚染を構造的に排除する。spec-state-contract.md「正本位置」節)。
    """
    p = canonical_spec_state_path(root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_cell(spec: dict, category: str, platform: str):
    if not isinstance(spec, dict):
        return None
    row = (spec.get("matrix") or {}).get(category)
    if not isinstance(row, dict):
        return None
    return row.get(platform)


def _cell_reopened(cell: dict) -> bool:
    """セルが R4-reopen 済みか。writer 正本キー reopened_from/reopen_reason を第一に見る。

    apply-spec-transition.py の reopen は確定巻き戻し時に
    {"state":"未収集","reopened_from":"確定","reopen_reason":...} を書く。従来 hook が見ていた
    reopened/reopen/reopened_at/reopened_by は writer 実出力に存在せず死んでいたため正本キーへ整合。
    """
    return any(cell.get(k) for k in _REOPEN_KEYS)


def _cell_terminal(cell) -> bool:
    """セルが終端状態 (確定 or 対象外) かつ再オープンされていない (=保護対象) か。

    R4-reopen 済み (state が 未収集 へ戻る / reopen 正本キー付与) のセルは保護しない (通す)。
    """
    if not isinstance(cell, dict):
        return False
    if _cell_reopened(cell):
        return False
    return cell.get("state") in TERMINAL_STATES


# ── 確定章の層別判定 ────────────────────────────────────────────────────────
# chapter_verdict の戻り値 enum。
_V_PASS = "pass"                       # 明確に protected でない → 通す (誤爆回避優先)
_V_PROTECTED = "protected"             # status:confirmed かつ全対応セル終端・非再オープン → exit2
_V_CONFIRMED_UNRESOLVED = "confirmed_unresolved"  # confirmed だが正本 spec-state 解決不能 → 安全側 exit2


def chapter_verdict(p: Path, root: Path) -> str:
    """章ファイル p の確定章判定を層別に返す (対象パス自身を load して判定)。

    - `pass`: system-spec 外 / 新規 (ファイル不在) / draft / 再オープン・未終端セルを含む章。
       誤爆回避優先で通す。
    - `protected`: status:confirmed かつ対応セルが 1 つ以上解決でき、その全てが正本 spec-state 上で
       終端状態 (確定 or 対象外) かつ再オープン対象を含まない。security 章のような 確定+対象外 混在も
       status:confirmed なら (全セル終端ゆえ) 保護する。
    - `confirmed_unresolved`: status:confirmed だが 正本 spec-state を load できない (F3 層別
       fail-closed)。誤爆範囲は confirmed 章に限定される。

    章の確定マーカー (status:confirmed) は対象パス自身の frontmatter から読む。spec-state は
    再オープン/未終端で保護を「緩める」ためだけに参照する (保護を作り出すのは章自身の confirmed)。
    """
    if not _is_system_spec_md(p):
        return _V_PASS
    fpath = p if p.is_absolute() else (root / p)
    if not fpath.is_file():
        return _V_PASS  # 新規 Write
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _V_PASS
    fm = parse_frontmatter(text)
    if fm.get("status") != "confirmed":
        return _V_PASS  # draft 等
    # ここから status:confirmed。正本 spec-state が解決できないなら confirmed 章限定で fail-closed。
    spec = load_spec_state(root)
    if spec is None:
        return _V_CONFIRMED_UNRESOLVED
    refs = _extract_cell_refs(fm)
    if not refs:
        return _V_PASS  # 対応セル不明 (00-requirements 等) は誤爆回避で通す
    # 章粒度の集約: 全対応セルが終端かつ非再オープンのときだけ保護。1 つでも
    # 非終端 / 再オープン / 解決不能セルがあれば「明確に protected」でない → 通す。
    for cat, plat in refs:
        if not _cell_terminal(_resolve_cell(spec, cat, plat)):
            return _V_PASS
    return _V_PROTECTED


def chapter_protected(p: Path, root: Path) -> bool:
    """章 p が確定章 (全対応セル終端で保護対象) か。Bash 経路の確定章遮断に使う。

    Write/Edit 経路の層別 fail-closed (`confirmed_unresolved`) は `chapter_verdict` を直接使う。
    """
    return chapter_verdict(p, root) == _V_PROTECTED


# ── 正本 spec-state.json 直接書換ガード ─────────────────────────────────────
def _resolve_target_path(p: Path, root: Path) -> Path:
    """全 tool 共通: 相対 target は project root 起点、authority は symlink 解決後。"""
    p = p.expanduser()
    absolute = p if p.is_absolute() else root / p
    try:
        return absolute.resolve()
    except (OSError, RuntimeError):
        return absolute


def _is_canonical_spec_state(p: Path, root: Path) -> bool:
    """対象が正本 spec-state.json (<root>/system-spec/spec-state.json) 自身か。

    実パス一致でのみ True。別位置の同名 spec-state.json (テスト fixture 等) は正本でないため
    False (交差汚染回避)。判定対象と判定ソースが常に同一ファイルになる。
    """
    return _resolve_target_path(p, root) == _resolve_target_path(canonical_spec_state_path(root), root)


def spec_state_has_confirmed_cell(root: Path) -> bool:
    """正本 spec-state.json に確定 (非再オープン) セルが 1 つでもあるか。

    True のとき正本 spec-state.json は確定巻き戻しの温床になり得るため直接 Write/Edit を遮断する。
    確定セルなし (init 直後・全 未収集/対象外) は通す (新規作成/初期化を妨げない)。
    """
    spec = load_spec_state(root)
    if not isinstance(spec, dict):
        return False
    matrix = spec.get("matrix")
    if not isinstance(matrix, dict):
        return False
    for row in matrix.values():
        if not isinstance(row, dict):
            continue
        for cell in row.values():
            if isinstance(cell, dict) and not _cell_reopened(cell) and cell.get("state") == CONFIRMED:
                return True
    return False


# ── Bash 解析 (書込み先の実パスで判定) ─────────────────────────────────────
# 書込み先候補の列は str (書込み先のパス) と None (書込みはあるが書込み先を静的に特定できない) からなる。
def _redirect_targets(cmd: str) -> list[str]:
    """字面の出力リダイレクト先 (shell として解析できないときの代替経路)。"""
    out = []
    for m in _REDIRECT.finditer(cmd):
        t = m.group(1).strip().strip('"').strip("'")
        if t:
            out.append(t)
    return out


def _split_heredocs(cmd: str) -> tuple[str, list[str]]:
    """heredoc の本文を shell 部から切り離す。

    区切り語を __HEREDOC_<n>__ に置き換え、本文は n 番目に返す (どのコマンドの stdin かを対応付けるため)。
    終端行が見つからない `<<` (引用内の演算子など) は heredoc とみなさずそのまま残す。
    """
    lines = cmd.split("\n")
    shell: list[str] = []
    bodies: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        for m in list(_HEREDOC_OP.finditer(line)):
            delim = m.group(2) or m.group(3) or m.group(4)
            for j in range(i, len(lines)):
                end = lines[j].lstrip("\t") if m.group(1) else lines[j]
                if end.rstrip() == delim:
                    bodies.append("\n".join(lines[i:j]))
                    line = line.replace(m.group(0), f"<< __HEREDOC_{len(bodies) - 1}__", 1)
                    i = j + 1
                    break
            else:
                break
        shell.append(line)
    return "\n".join(shell), bodies


def _shell_tokens(text: str) -> list[str] | None:
    """shell 部を引用解除済みのトークン列へ。演算子 (; | & 改行 リダイレクト) は独立トークンになる。

    引用が閉じない等で解析できなければ None。`#` はコメントとして扱わない (`${#x}` や URL を
    切り落として後続の書込みを見逃さないため)。
    """
    lex = shlex.shlex(text.replace("\\\n", " "), posix=True, punctuation_chars=_SHELL_PUNCT)
    lex.whitespace_split = True
    lex.whitespace = " \t\r"
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:
        return None


def _nonopt_args(args: list[str], value_opts: set[str] = frozenset()) -> list[str]:
    """オプションとその値を除いた引数 (`--` 以降は全て引数)。"""
    out: list[str] = []
    skip = False
    for idx, a in enumerate(args):
        if skip:
            skip = False
            continue
        if a == "--":
            out.extend(args[idx + 1:])
            break
        if a in value_opts:
            skip = True
            continue
        if a.startswith("-") and a != "-":
            continue
        out.append(a)
    return out


def _is_dir_target(token: str, root: Path) -> bool:
    if token.endswith("/"):
        return True
    p = Path(token).expanduser()
    try:
        return (p if p.is_absolute() else root / p).is_dir()
    except OSError:
        return False


def _copy_like_targets(name: str, args: list[str], root: Path) -> list[str]:
    """cp/mv/install/ln の書込み先。宛先がディレクトリなら <宛先>/<元の basename>。mv は元も消える。"""
    dest = None
    for idx, a in enumerate(args):
        if a == "-t" and idx + 1 < len(args):
            dest = args[idx + 1]
        elif a.startswith("--target-directory="):
            dest = a.split("=", 1)[1]
    pos = [a for a in _nonopt_args(args, _VALUE_OPTS.get(name, set()) | {"-t"}) if a != dest]
    if dest is None:
        if len(pos) < 2:
            return pos  # `ln -s x` のように宛先が cwd になる形。引数自体を候補にしておく
        dest, pos = pos[-1], pos[:-1]
        if not _is_dir_target(dest, root):
            return pos + [dest] if name == "mv" else [dest]
    joined = [f"{dest.rstrip('/')}/{Path(s).name}" for s in pos]
    return pos + joined if name == "mv" else joined


def _sed_targets(args: list[str]) -> list[str]:
    """sed の in-place 書込み先 (-i が無ければ stdout へ出すだけなので書込みなし)。"""
    inplace = False
    script_given = False
    files: list[str] = []
    idx = 0
    while idx < len(args):
        a = args[idx]
        if a in ("-e", "--expression", "-f", "--file"):
            script_given = True
            idx += 2
            continue
        if a.startswith(("--expression=", "--file=")):
            script_given = True
        elif a == "--in-place" or a.startswith("--in-place="):
            inplace = True
        elif a.startswith("-") and not a.startswith("--") and len(a) > 1:
            if "i" in a[1:]:
                inplace = True
                # BSD の `sed -i '' ...` は次の空トークンが拡張子。
                if a == "-i" and idx + 1 < len(args) and args[idx + 1] == "":
                    idx += 1
        else:
            files.append(a)
        idx += 1
    if not inplace:
        return []
    return files if script_given else files[1:]


def _uses_mutator(args: list[str]) -> bool:
    """xargs / find -exec が起動するコマンドが変更系か (sed は -i を伴うときだけ)。"""
    names = [os.path.basename(a) for a in args]
    if any(n in _MUTATORS - {"sed"} or n in _SHELLS or _PYTHON.match(n) for n in names):
        return True
    return "sed" in names and any(a.startswith(("--in-place", "-i")) for a in args)


def _py_callee(call: ast.Call) -> str:
    """呼び出し先の dotted 名 (open / os.remove / shutil.move 等)。決まらなければ空文字。"""
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        return f"{f.value.id}.{f.attr}"
    return ""


def _py_path_pattern(node: ast.AST) -> str:
    """書込み先の式を文字列へ。静的に決まらない部分は `$` に置く (後段で書込み先不明として扱う)。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "$" for v in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return f"{_py_path_pattern(node.left)}/{_py_path_pattern(node.right)}"
    if isinstance(node, ast.Call) and _py_callee(node) in ("Path", "PurePath", "pathlib.Path") and node.args:
        return "/".join(_py_path_pattern(a) for a in node.args)
    return "$"


def _py_mode_writes(mode: ast.AST | None, *, unknown: bool) -> bool:
    """open の mode が書込み (w/a/x/+) か。mode が式で決まらないときは unknown を返す。"""
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return bool(_PY_MODE.match(mode.value)) and any(c in mode.value for c in "wax+")
    return unknown


def _py_kwarg(call: ast.Call, name: str) -> ast.AST | None:
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _python_write_targets(code: str) -> list[str | None]:
    """python コードの書込み先。file handle の .write/json.dump は open 側で捉える。"""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return [None] if _PY_WRITE.search(code) else []
    out: list[str | None] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _py_callee(node)
        f = node.func
        if callee in _PY_OPENERS:
            mode = node.args[1] if len(node.args) > 1 else _py_kwarg(node, "mode")
            if node.args and _py_mode_writes(mode, unknown=True):
                out.append(_py_path_pattern(node.args[0]))
        elif callee in _PY_FUNC_WRITERS:
            out.extend(_py_path_pattern(node.args[k]) for k in _PY_FUNC_WRITERS[callee] if k < len(node.args))
        elif isinstance(f, ast.Attribute) and f.attr == "open":  # Path(...).open('w')
            mode = node.args[0] if node.args else _py_kwarg(node, "mode")
            if _py_mode_writes(mode, unknown=False):
                out.append(_py_path_pattern(f.value))
        elif isinstance(f, ast.Attribute) and f.attr in ("write_text", "write_bytes", "unlink"):
            out.append(_py_path_pattern(f.value))
    return out


def _command_write_targets(
    args: list[str], stdin_bodies: list[str], root: Path, depth: int
) -> list[str | None]:
    """単純コマンド 1 つの書込み先 (リダイレクトは呼び出し側で集める)。"""
    idx = 0
    wrapped = False
    while idx < len(args) and (
        args[idx] in _WRAPPERS or args[idx] in _KEYWORDS or _ASSIGNMENT.match(args[idx])
        or (wrapped and args[idx].startswith("-"))
    ):
        wrapped = wrapped or args[idx] in _WRAPPERS
        idx += 1
    if idx >= len(args):
        return []
    name = os.path.basename(args[idx])
    rest = args[idx + 1:]
    if _PYTHON.match(name):
        if "-c" in rest:
            pos = rest.index("-c") + 1
            return _python_write_targets(rest[pos]) if pos < len(rest) else []
        # `python3 -` か script 指定なしなら heredoc 本文がコード。script 指定時は本文はデータ。
        if "-" in rest or not _nonopt_args(rest):
            return [t for body in stdin_bodies for t in _python_write_targets(body)]
        return []
    if name in _SHELLS or name == "eval":
        if depth >= _MAX_DEPTH:
            return [None]
        if name == "eval":
            return _bash_write_targets(" ".join(rest), root, depth + 1)
        if "-c" in rest:
            pos = rest.index("-c") + 1
            return _bash_write_targets(rest[pos], root, depth + 1) if pos < len(rest) else []
        if not _nonopt_args(rest):
            return [t for body in stdin_bodies for t in _bash_write_targets(body, root, depth + 1)]
        return []
    if name == "sed":
        return _sed_targets(rest)
    if name in ("cp", "mv", "install", "ln"):
        return _copy_like_targets(name, rest, root)
    if name in ("tee", "rm", "truncate", "unlink", "shred"):
        return _nonopt_args(rest, _VALUE_OPTS.get(name, set()))
    if name == "dd":
        return [a[3:] for a in rest if a.startswith("of=")]
    if name == "xargs":
        return [None] if _uses_mutator(rest) else []
    if name == "find":
        if "-delete" in rest:
            return [None]
        for opt in ("-exec", "-execdir", "-ok", "-okdir"):
            if opt in rest and _uses_mutator(rest[rest.index(opt) + 1:]):
                return [None]
    return []


def _bash_write_targets(cmd: str, root: Path, depth: int = 0) -> list[str | None]:
    """Bash コマンドの書込み先候補を集める。"""
    shell, bodies = _split_heredocs(cmd)
    toks = _shell_tokens(shell)
    if toks is None:
        # shell として解析できない → 字面のリダイレクト先を拾い、書込み指標があれば書込み先不明とする。
        out: list[str | None] = list(_redirect_targets(shell))
        if any(pat.search(cmd) for pat, _ in _MUTATION_TOOLS) or _PY_WRITE.search(cmd):
            out.append(None)
        return out
    out = []
    args: list[str] = []
    heredocs: list[str] = []

    def flush() -> None:
        if args:
            out.extend(_command_write_targets(list(args), list(heredocs), root, depth))
        args.clear()
        heredocs.clear()

    idx = 0
    while idx < len(toks):
        t = toks[idx]
        if not t or any(c not in _SHELL_PUNCT for c in t):
            args.append(t)
            idx += 1
            continue
        if any(c in t for c in ";|\n()") or "&&" in t or t == "&":
            flush()
        nxt = toks[idx + 1] if idx + 1 < len(toks) else ""
        if _OUT_REDIRECT_OP.search(t):
            if args and args[-1].isdigit():
                args.pop()  # `2>` の fd 番号
            if not (t.endswith(">&") and (nxt.isdigit() or nxt == "-")):  # `2>&1` は fd 複製
                out.append(nxt)
            idx += 2
            continue
        if t.endswith("<"):  # `<` / `<<` / `<<<` の次は入力元
            m = _HEREDOC_MARK.fullmatch(nxt)
            if m and int(m.group(1)) < len(bodies):
                heredocs.append(bodies[int(m.group(1))])
            idx += 2
            continue
        idx += 1
    flush()
    return out


def _protected_target_reason(token: str, root: Path) -> str:
    """静的に決まった書込み先 1 件が保護対象なら遮断理由、そうでなければ空文字。

    相対パスは root 起点で解決し、symlink を辿った実パスでも確定章 / 正本 spec-state を判定する。
    """
    real = _resolve_target_path(Path(token), root)
    if _is_canonical_spec_state(real, root):
        return f"正本 spec-state.json への書込み ('{token}' の実パス) を遮断"
    if chapter_protected(real, root):
        return f"確定章への書込み ('{token}') を遮断"
    # rm/mv/shutil.rmtree 等は directory 自体でなく配下の実体も変更する。
    # cp/install の directory 宛先は抽出側で実ファイルへ展開済みである。
    if real.is_dir():
        canon = _resolve_target_path(canonical_spec_state_path(root), root)
        if canon.is_file() and canon.is_relative_to(real):
            return f"正本 spec-state.json を含むディレクトリ ('{token}') の変更を遮断"
        for chapter in real.rglob("*.md"):
            if chapter_protected(chapter, root):
                return f"確定章を含むディレクトリ ('{token}') の変更を遮断"
    return ""


def _may_hit_protected(token: str) -> bool:
    """静的に決まらない書込み先が保護対象 (章 .md / spec-state.json) でありうるか。

    basename が静的に読めて .md でも spec-state.json でもなければ、変数部分が何であれ保護対象にならない。
    """
    base = token.rstrip("/").rsplit("/", 1)[-1]
    return bool(_DYN_CHARS.search(base)) or base.endswith(".md") or base == SPEC_STATE_NAME


def _refs_canonical_spec_state(cmd: str) -> bool:
    """コマンドが正本 spec-state (system-spec/spec-state.json) を参照するか。"""
    return _CANONICAL_SUFFIX in cmd


def _refs_protected_area(cmd: str) -> bool:
    """コマンドが保護領域 (system-spec/ ディレクトリ) をパス境界付きで参照するか。

    `system-spec-harness/` 等の自plugin パス部分文字列では発火しない (パスセグメント境界一致)。
    """
    return bool(_PROTECTED_SEG.search(cmd))


def bash_decision(cmd: str, root: Path) -> tuple[int, str]:
    """Bash コマンドの許可 (0) / 遮断 (2) を書込み先の実パスで判定する。

    保護パスがコマンド中に現れても、書込み先でなければ通す (読み取り元・診断データとしての言及)。
    """
    try:
        targets = _bash_write_targets(cmd, root)
    except Exception:
        targets = [None]  # 解析器の想定外の失敗は書込み先不明として扱う (保護領域を参照するときだけ遮断)
    ambiguous = False
    for t in targets:
        if t is None or _DYN_CHARS.search(t):
            ambiguous = ambiguous or t is None or _may_hit_protected(t)
            continue
        if t:
            reason = _protected_target_reason(t, root)
            if reason:
                return 2, reason
    # 書込み先を静的に特定できず、保護領域を参照する → 安全側で遮断 (層別 fail-closed)。
    if ambiguous and (_refs_protected_area(cmd) or _refs_canonical_spec_state(cmd)):
        return 2, (
            "保護領域 (system-spec/ 配下 または 正本 spec-state.json) を参照し、"
            "書込み先を静的に特定できない書換を安全側で遮断"
        )
    return 0, ""


# ── 中核ディシジョン ───────────────────────────────────────────────────────
def decide(payload: dict, root: Path) -> tuple[int, str]:
    """PreToolUse ペイロードから許可 (0) / 遮断 (2) と理由を返す。"""
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    if tool in ("Write", "Edit"):
        fp = ti.get("file_path") or ti.get("path") or ""
        if not fp:
            return 0, ""
        path = _resolve_target_path(Path(fp), root)
        # (a) 正本 spec-state.json 自身への直接書換 (確定セルあり) は Bash 経路と同格に遮断。
        #     別位置の同名 spec-state.json (fixture 等) は正本でなく通す (交差汚染回避)。
        if _is_canonical_spec_state(path, root) and spec_state_has_confirmed_cell(root):
            return 2, (
                f"正本 spec-state.json '{fp}' への直接 {tool} を遮断 "
                "(確定セルを含む。確定変更は apply-spec-transition の R4-reopen 経由のみ)"
            )
        # (b)(c) 確定章判定 (層別 fail-closed)。
        verdict = chapter_verdict(path, root)
        if verdict == _V_PROTECTED:
            return 2, f"確定済み仕様章 '{fp}' への {tool} を遮断 (再オープン経由でのみ変更可)"
        if verdict == _V_CONFIRMED_UNRESOLVED:
            return 2, (
                f"status:confirmed 章 '{fp}' への {tool} を遮断 "
                "(正本 spec-state.json を解決できず確定状態を確認不能。confirmed 章限定の層別 fail-closed)"
            )
        return 0, ""
    if tool == "Bash":
        cmd = ti.get("command") or ""
        return bash_decision(cmd, root)
    return 0, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # 解釈不能な入力は対象を特定できず「明確に protected」でない → 素通し (誤爆回避)。
        return 0
    code, reason = decide(payload, project_root())
    if code == 2:
        sys.stderr.write(
            f"[{GUARD_NAME}] BLOCKED: {reason}。\n"
            "  確定済み仕様章 / 正本 spec-state.json は C01/C03 の単一 writer (根拠付き R4-reopen) 経由でのみ変更してください。\n"
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
