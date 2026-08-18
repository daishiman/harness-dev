#!/usr/bin/env python3
"""guard-handout-external-ref — PostToolUse (Write|Edit) の水際ガード。

正本:
  - plugin-plans/guide-doc-generator/briefs/hook-brief-C10.json
  - plugin-plans/guide-doc-generator/briefs/script-brief-C16.json (CR-EXT / CR-EMOJI)

設計の中心は「判定規則を 1 行も持たない」ことである。外部参照 (D1) と絵文字
(D2) の判定は C16 verify-handout-selfcontained.py を module として読み込み、
その scan_external_references / scan_emoji をそのまま呼んで結果を受け取る
(rule_delegation.canonical_owner)。本 hook の責務は次の 3 つだけ:

  1. 適用対象の同定 (applies_to の 5 条件)
  2. C16 module の実体解決と読み込み
  3. C16 が返した違反の exit code と stderr への写像

この分業により C10 と C16 は同一入力に対し必ず同一判定になる
(rule_delegation.invariant)。片方だけが FAIL/PASS になったらそれは実装バグ。

PostToolUse は書込そのものを止められない。ここでの fail-closed は「書込を
取り消す」意味ではなく「違反があるとき exit 2 が必ず立ち、後段が無検査で
先へ進めない」意味である (event_rationale)。ファイルの削除・ロールバック・
書換は一切行わない (write-scope: none)。

fail-closed にしない範囲 (fail_closed_scope):
  (a) 適用対象と同定できない / 判定 module を解決できない → exit 0
  (b) 対象ファイルを読めない (削除済み・権限不足・復号不能) → exit 0
  (c) 予算 (時間・サイズ) を超えて検査を完走できない → exit 0
  いずれも見逃しは C16 の完成物ゲートで捕まる二重防御の内側にある。ただし
  (a) の module 解決不能と (c) の打ち切りは、黙って合格に見せないために
  stdout へ systemMessage の JSON を 1 行出して可視化する。
"""

from __future__ import annotations

import html
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------
# 契約定数 (hook-brief-C10.json)
# --------------------------------------------------------------------------

#: applies_to (1) matcher。MultiEdit を含まないのは inventory の宣言に従うため
WATCHED_TOOLS = ("Write", "Edit")

#: input_contract: 書込先パスのキーはこの順で最初の非空 str を採る
PATH_KEYS = ("file_path", "filePath", "path")

#: applies_to (3)
TARGET_SUFFIX = ".html"

#: applies_to (4) 同階層マーカー
MARKER_FILENAME = "handout-config.json"

#: applies_to (5) C19 の命名規則 (日付接頭)。種別語彙は一切参照しない
DATED_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")

#: output_contract.block
LABEL = "guard-handout-external-ref"
BLOCK_PREFIX = "[guard-handout-external-ref] BLOCKED:"
D1 = "D1-external-url-attr"
D2 = "D2-emoji"

#: fail_closed_scope (c)
SIZE_LIMIT_BYTES = 8 * 1024 * 1024
TIME_BUDGET_SECONDS = 3.0

# --------------------------------------------------------------------------
# 実体解決 (index.md の実行時可搬性方針。絶対パスを直書きしない)
# --------------------------------------------------------------------------

ROOT_ENV_VARS = ("HB_ROOT", "CLAUDE_PLUGIN_ROOT")
MANIFEST_RELPATH = ".claude-plugin/plugin.json"
MANIFEST_NAME = "guide-doc-generator"
NAME_KEY = "name"

#: rule_delegation.canonical_owner
CANONICAL_MODULE_RELPATH = "scripts/verify-handout-selfcontained.py"
CANONICAL_MODULE_ALIAS = "hb_selfcontained"
EXTERNAL_SCAN_EXPORT = "scan_external_references"
EMOJI_SCAN_EXPORT = "scan_emoji"


def _script_root() -> Path:
    """.claude/ 平置き projection でも効く自己解決 (hooks/ の親)。"""
    return Path(__file__).resolve().parent.parent


def _manifest_matches(root: Path) -> bool:
    manifest = Path(root) / MANIFEST_RELPATH
    try:
        if not manifest.is_file():
            return False
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get(NAME_KEY) == MANIFEST_NAME


def candidate_roots() -> list:
    """plugin 実体の候補 root を 4 段の順で並べる (C15 と同じ解決順)。"""
    entries = []
    seen = set()

    def add(path):
        try:
            key = str(Path(path).resolve())
        except OSError:
            key = str(path)
        if key in seen:
            return
        seen.add(key)
        entries.append(Path(path))

    for env_name in ROOT_ENV_VARS:
        value = os.environ.get(env_name)
        if value:
            add(Path(value))
    try:
        cwd = Path.cwd().resolve()
    except OSError:
        cwd = None
    if cwd is not None:
        for base in (cwd, *cwd.parents):
            if _manifest_matches(base):
                add(base)
    script_root = _script_root()
    if _manifest_matches(script_root):
        add(script_root)
    add(script_root)
    return entries


def resolve_canonical_module_path():
    """C16 の実体を求める。見つからなければ None (独自判定へは退避しない)。"""
    for root in candidate_roots():
        candidate = Path(root) / CANONICAL_MODULE_RELPATH
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def load_canonical_scanners():
    """C16 を module として読み込み (scan_external_references, scan_emoji) を返す。

    rule_delegation.how の作法どおり importlib.util.spec_from_file_location で
    verify-handout-selfcontained.py を読む。読めないときは None を返し、
    呼び出し側が if_import_fails (exit 0 + systemMessage) へ落とす。
    """
    path = resolve_canonical_module_path()
    if path is None:
        return None
    spec = importlib.util.spec_from_file_location(CANONICAL_MODULE_ALIAS, str(path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    external = getattr(module, EXTERNAL_SCAN_EXPORT, None)
    emoji = getattr(module, EMOJI_SCAN_EXPORT, None)
    if not callable(external) or not callable(emoji):
        return None
    return external, emoji


# --------------------------------------------------------------------------
# 入力 (input_contract)
# --------------------------------------------------------------------------


def read_payload():
    """stdin の hook ペイロードを dict で返す。読めなければ None。"""
    try:
        raw = sys.stdin.read()
    except (OSError, UnicodeDecodeError):
        return None
    if not raw or not raw.strip():
        return None
    try:
        obj = json.loads(raw)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def extract_path(payload):
    """tool_input から書込先パスを取り出す (最初に見つかった非空 str)。"""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def resolve_target(payload, raw_path):
    """cwd 相対のパスでも書込先を同定する。"""
    path = Path(raw_path)
    if path.is_absolute():
        return path
    base = payload.get("cwd")
    if not isinstance(base, str) or not base.strip():
        try:
            base = os.getcwd()
        except OSError:
            return path
    return Path(base) / path


def is_in_scope(payload, target: Path) -> bool:
    """applies_to.rule の (1)(3)(4)(5) を上から評価する ((2) は extract_path)。"""
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or tool_name not in WATCHED_TOOLS:
        return False
    if target.suffix.lower() != TARGET_SUFFIX:
        return False
    parent = target.parent
    try:
        if not (parent / MARKER_FILENAME).is_file():
            return False
    except OSError:
        return False
    return bool(DATED_DIR_RE.match(parent.name))


# --------------------------------------------------------------------------
# 出力 (output_contract)
# --------------------------------------------------------------------------


def emit_abort(reason: str) -> int:
    """output_contract.abort: exit 0 + stdout へ systemMessage の JSON 1 行。"""
    sys.stdout.write(json.dumps({"systemMessage": reason}, ensure_ascii=False) + "\n")
    return 0


def format_line(detection_id: str, violation) -> str:
    """違反 1 件を 1 行へ (検出規則 id / 行番号 / 抜粋)。抜粋は C16 が 120 字へ整形済み。"""
    canonical_id = getattr(violation, "detection_id", "")
    line = getattr(violation, "line", 0)
    col = getattr(violation, "col", 0)
    evidence = getattr(violation, "evidence", "") or ""
    return "{} [{}] line {} col {}: {}".format(
        detection_id, canonical_id, line, col, evidence)


def emit_block(target: Path, rows) -> int:
    """output_contract.block: exit 2 + stderr。stdout へは何も書かない。"""
    out = [
        "{} {} に自己完結性を破る混入がある ({} 件)".format(
            BLOCK_PREFIX, target, len(rows))
    ]
    out.extend(rows)
    sys.stderr.write("\n".join(out) + "\n")
    return 2


# --------------------------------------------------------------------------
# 本体
# --------------------------------------------------------------------------


def inspect(target: Path, deadline: float) -> int:
    """適用対象と同定済みのファイルを C16 の判定へ掛けて exit code を返す。"""
    try:
        if not target.is_file():
            return 0
        size = target.stat().st_size
    except OSError:
        return 0
    if size > SIZE_LIMIT_BYTES:
        return emit_abort(
            "{}: {} はサイズ上限を超えるため未検査で打ち切った "
            "(完成物の検査は C16 {} に委ねる)".format(
                LABEL, target, CANONICAL_MODULE_RELPATH))
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        return 0

    scanners = load_canonical_scanners()
    if scanners is None:
        return emit_abort(
            "{}: 判定モジュール解決不能のため未検査 "
            "({} を実体解決できない)".format(LABEL, CANONICAL_MODULE_RELPATH))
    scan_external_references, scan_emoji = scanners

    if time.monotonic() > deadline:
        return emit_abort(
            "{}: 検査予算を超えたため未検査で打ち切った: {}".format(LABEL, target))

    rows = []
    try:
        for violation in scan_external_references(text):
            rows.append(format_line(D1, violation))
    except Exception:
        return 0

    if time.monotonic() > deadline:
        return emit_abort(
            "{}: 検査予算を超えたため未検査で打ち切った: {}".format(LABEL, target))

    try:
        for violation in scan_emoji(html.unescape(text)):
            rows.append(format_line(D2, violation))
    except Exception:
        return 0

    if not rows:
        return 0
    return emit_block(target, rows)


def run() -> int:
    deadline = time.monotonic() + TIME_BUDGET_SECONDS
    payload = read_payload()
    if payload is None:
        return 0
    raw_path = extract_path(payload)
    if raw_path is None:
        return 0
    target = resolve_target(payload, raw_path)
    if not is_in_scope(payload, target):
        return 0
    return inspect(target, deadline)


def main() -> int:
    try:
        return run()
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
