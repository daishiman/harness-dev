#!/usr/bin/env python3
# /// script
# name: guard-confirmed-chapter-overwrite
# version: 0.1.0
# purpose: 確定済み仕様章 (system-spec/ の status:confirmed 章 かつ 正本 spec-state.json の
#          対応セルが『確定』・非再オープン) と 正本 spec-state.json 自身への Write/Edit/Bash 動的書換を
#          PreToolUse で遮断する defense-in-depth の層別 fail-closed hook (要件 C3 の派生安全要件)。
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
  読み取り専用コマンド (cat/grep/ls 等・書込指標なし) は保護パス参照でも exit0。
  書込コマンド (リダイレクト/sed -i/tee/cp/mv/rm/dd/truncate/python の open(...,'w') 等) が
    - 正本 spec-state.json (system-spec/spec-state.json) を書換対象にする
    - 解決可能な確定章を書換対象にする
    - 保護領域 (system-spec/ 配下・パス境界一致) を参照する曖昧な動的書換 (glob/変数/find 経由) である
  いずれかなら安全側で exit2。再オープン章・新規章への具体的書込は通す。
  判定は `system-spec/` をパス境界 (完全なパスセグメント) として扱い、自plugin パスの
  `system-spec-harness/` 等を部分文字列で誤検出しない。

fail-closed 方針 (層別): 正本 spec-state を参照する危険な動的 Bash 書換 と、正本 spec-state 解決不能な
confirmed 章 Write/Edit のみ安全側で拒否する (計画 C11 exit_semantics=fail-closed-exit2)。それ以外の章判定は
「明確に protected と判定できないなら通す」を基本にする (誤爆回避優先)。全書換経路の正本防御は
C01/C03 の単一 writer/transition gate が担う。本 hook は補助 (二重化)。

block ゲートとの相補関係 (C16/C14): required-info-catalog.json の missing_effect=block item が未充足の
間は、そもそも当該セルの confirmed 遷移自体が上流の C01 R5 収集ゲート (elicit 時の prose ゲート) で
禁止される (validate-knowledge-graph.py --profile required-info は coverage certificate に blocking_items を
列挙するのみで runtime 施行はせず、C01 R5 がその certificate を消費して施行する。決定論 writer 施行 =
apply-spec-transition への block 検査組込は required-info 回答スキーマ拡張を要する follow-up)。すなわち
「未収集の必須情報を残したまま確定させない」のは上流の収集ゲート側の責務。本 hook はその結果 confirmed になった章の
事後的な上書き/巻き戻しを防ぐ層であり、block ゲートとは前段 (確定させない) / 後段 (確定を保護) の
相補的な二層をなす。本 hook 側で block 未充足を再判定・遮断することはしない (責務境界の明確化)。
"""
from __future__ import annotations

import json
import os
import re
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

# system-spec/ を参照する書込で in-place 変更を行うツール群 (対象ファイルを引数で受ける)。
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
# python ワンライナ等での書込操作。
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
# 曖昧な動的書換 (target を静的に列挙できない) を示す指標。
_DYNAMIC = re.compile(r"[*?\[]|\$|`|\bfind\b|\bxargs\b")
# 保護領域 (system-spec/ ディレクトリ) をパス境界 (完全なパスセグメント) で参照しているか。
# 前後をデリミタ/末尾で束ねるため、自plugin パスの `system-spec-harness` (直後が '-') には発火しない。
_PROTECTED_SEG = re.compile(r"""(?:^|[\s;|&<>()'"=/])system-spec(?:/|[\s;|&<>()'"]|$)""")


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
    return root / SPEC_DIR / SPEC_STATE_NAME


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
def _is_canonical_spec_state(p: Path, root: Path) -> bool:
    """対象が正本 spec-state.json (<root>/system-spec/spec-state.json) 自身か。

    実パス一致でのみ True。別位置の同名 spec-state.json (テスト fixture 等) は正本でないため
    False (交差汚染回避)。判定対象と判定ソースが常に同一ファイルになる。
    """
    canon = canonical_spec_state_path(root)
    try:
        return p.resolve() == canon.resolve()
    except OSError:
        return False


def _token_is_canonical_spec_state(token: str) -> bool:
    """Bash トークンが正本 spec-state.json (system-spec/spec-state.json) を末尾構造で指すか。"""
    p = Path(token)
    return p.name == SPEC_STATE_NAME and len(p.parts) >= 2 and p.parts[-2] == SPEC_DIR


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


# ── Bash 解析 ───────────────────────────────────────────────────────────────
def _redirect_targets(cmd: str) -> list[str]:
    out = []
    for m in _REDIRECT.finditer(cmd):
        t = m.group(1).strip().strip('"').strip("'")
        if t:
            out.append(t)
    return out


def _system_spec_md_tokens(cmd: str) -> list[str]:
    """コマンド中の system-spec/ 配下 .md らしきトークンを抽出 (パス境界判定)。

    system-spec を完全なパスセグメントとして持つトークンのみを拾い、自plugin パスの
    `system-spec-harness/...md` (system-spec が独立セグメントでない) は拾わない。
    """
    toks = []
    for raw in re.split(r"[\s;|&<>()'\"]+", cmd):
        if not raw or not raw.endswith(".md"):
            continue
        if SPEC_DIR in Path(raw).parts:
            toks.append(raw)
    return toks


def _token_is_protected_chapter(token: str, root: Path) -> bool:
    return chapter_protected(Path(token), root)


def _refs_canonical_spec_state(cmd: str) -> bool:
    """コマンドが正本 spec-state (system-spec/spec-state.json) を参照するか。"""
    return _CANONICAL_SUFFIX in cmd


def _refs_protected_area(cmd: str) -> bool:
    """コマンドが保護領域 (system-spec/ ディレクトリ) をパス境界付きで参照するか。

    `system-spec-harness/` 等の自plugin パス部分文字列では発火しない (パスセグメント境界一致)。
    """
    return bool(_PROTECTED_SEG.search(cmd))


def bash_decision(cmd: str, root: Path) -> tuple[int, str]:
    """Bash コマンドの許可 (0) / 遮断 (2) を判定する。"""
    redirects = _redirect_targets(cmd)
    mutation = any(pat.search(cmd) for pat, _ in _MUTATION_TOOLS)
    py_write = bool(_PY_WRITE.search(cmd))
    is_write = bool(redirects) or mutation or py_write
    if not is_write:
        # 書込指標なし = read-only。保護パス参照でも通す (cat/grep/ls 等)。
        return 0, ""

    refs_spec_state = _refs_canonical_spec_state(cmd)

    # 1) リダイレクト先が保護対象 (正本 spec-state / 確定章)
    for t in redirects:
        if _token_is_canonical_spec_state(t):
            return 2, f"正本 spec-state.json への出力リダイレクト ('{t}') を遮断"
        if _token_is_protected_chapter(t, root):
            return 2, f"確定章への出力リダイレクト ('{t}') を遮断"

    # 2) in-place / python 書込が正本 spec-state.json を対象
    if refs_spec_state and (mutation or py_write):
        return 2, "正本 spec-state.json への動的書換 (in-place/python) を遮断"

    # 3) in-place / python 書込が解決可能な確定章を対象
    if mutation or py_write:
        for t in _system_spec_md_tokens(cmd):
            if _token_is_protected_chapter(t, root):
                return 2, f"確定章 '{t}' への動的書換を遮断"

    # 4) 曖昧な動的書換が保護領域 (system-spec/ 配下・パス境界一致) を参照 → 安全側で遮断
    if (_refs_protected_area(cmd) or refs_spec_state) and _DYNAMIC.search(cmd):
        return 2, "保護領域 (system-spec/ 配下 または 正本 spec-state.json) を参照する曖昧な動的書換を安全側で遮断"

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
        path = Path(fp)
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
