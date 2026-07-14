#!/usr/bin/env python3
# /// script
# name: parse-spec-diff
# purpose: C11 が集約した対象 issue の未triage 全 diff 集合 (最新1件固定でなく issue 単位の積層) を unified diff hunk 単位へ構造化パースする決定論変換。complete=true と diff_sha256 一致を証明できない入力は判定せず fail-closed (exit2) する。
# inputs:
#   - argv: (--diffs FILE | --stdin) で C11 stdout JSON ({entries:[{...,diff_sha256,complete,diff}], ...}) を受け取る。省略された spec-diff-history.md を既定入力にはしない。
# outputs:
#   - stdout: source_commit/base_commit/diff_sha256 を継承した hunks JSON 配列
#   - stderr: violation
#   - exit: 0=正常 / 1=一般エラー / 2=complete=false または digest 不一致 (fail-closed)
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""C11 の complete=true な正規化完全 diff 集合を unified diff hunk 単位へ構造化する決定論変換 (C08)。

C11 (aggregate-issue-diffs.py) の stdout JSON ``{entries:[{...,diff_sha256,complete,diff}]}`` を
受け取り、各 entry の diff テキストを unified diff の hunk 単位へパースして
``source_commit/base_commit/diff_sha256`` を継承した hunks JSON 配列を stdout へ emit する。

中核不変条件 (完全性ゲート): entry の ``complete`` が true でない、または diff テキストの
sha256 が ``diff_sha256`` と一致しない場合は判定せず exit2 (fail-closed)。これにより
80行で切られた truncated preview 由来の不完全 diff が下流 (C09/C01/C03) へ流れることを防ぐ。

hunk 順は入力 diff の出現順で安定 (entries 入力順 → file 出現順 → hunk 出現順)。
stdlib only・network=false・write-scope=none。git 呼び出しは行わない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# unified diff の hunk header: ``@@ -old_start[,old_lines] +new_start[,new_lines] @@ [section]``。
# count 省略時 (単一行 hunk) は git 慣習に従い 1 とみなす。
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


class InputError(Exception):
    """構造不正・入力不備 (exit1)。完全性ゲート外の一般エラー。"""


class GateError(Exception):
    """完全性ゲート違反 (exit2)。complete=false または digest 不一致で fail-closed。"""


# ─────────────────── 完全性ゲート ───────────────────
def compute_sha256(text: str) -> str:
    """diff テキスト (utf-8) の sha256 hexdigest を返す (C11 の diff_sha256 と同一規約)。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_completeness(entry: dict, idx: int) -> str:
    """entry の完全性 (complete=true かつ digest 一致) を検証し diff テキストを返す。

    証明できない場合は GateError を送出する (exit2)。これが C08 の中核不変条件。
    """
    if entry.get("complete") is not True:
        raise GateError(
            f"entries[{idx}]: complete=true ではないため判定せず fail-closed します "
            f"(complete={entry.get('complete')!r})"
        )
    diff = entry.get("diff")
    if not isinstance(diff, str):
        raise GateError(
            f"entries[{idx}]: diff テキストが無く完全性を検証できないため fail-closed します"
        )
    declared = entry.get("diff_sha256")
    if not isinstance(declared, str) or not declared.strip():
        raise GateError(
            f"entries[{idx}]: diff_sha256 が無く digest を照合できないため fail-closed します"
        )
    actual = compute_sha256(diff)
    if actual != declared.strip().lower():
        raise GateError(
            f"entries[{idx}]: diff_sha256 が不一致のため fail-closed します "
            f"(declared={declared.strip().lower()} actual={actual})"
        )
    return diff


# ─────────────────── unified diff パーサ ───────────────────
def _strip_path(raw: str) -> str | None:
    """diff の path トークンから ``a/`` / ``b/`` prefix を除去する。/dev/null は None。"""
    raw = raw.split("\t", 1)[0].strip()
    if raw == "/dev/null":
        return None
    if raw.startswith(("a/", "b/")):
        return raw[2:] or None
    return raw or None


def _git_header_path(line: str) -> str | None:
    """``diff --git a/foo b/foo`` から fallback の path を取り出す (+++/--- を優先)。"""
    parts = line.split(" ", 3)
    if len(parts) >= 4:
        return _strip_path(parts[3])
    return None


def _change_type(old_lines: int, new_lines: int) -> str:
    """hunk 単位の変更種別。old_lines==0 で add、new_lines==0 で delete、他は modify。"""
    if old_lines == 0:
        return "add"
    if new_lines == 0:
        return "delete"
    return "modify"


def parse_unified_diff(diff_text: str) -> list[dict]:
    """1 entry の unified diff テキストを hunk dict の配列へ構造化する (出現順で安定)。

    hunk body の消費数を old_lines/new_lines の残数で追跡することで、content 行の
    ``-``/``+`` を file header (``--- ``/``+++ ``) と誤認しない。
    """
    hunks: list[dict] = []
    old_path: str | None = None
    new_path: str | None = None
    git_path: str | None = None
    hunk: dict | None = None
    rem_old = 0
    rem_new = 0

    for line in diff_text.splitlines():
        # 1) hunk body の途中 (残 budget あり) は content 行として解釈する。
        if hunk is not None and (rem_old > 0 or rem_new > 0):
            if line.startswith("\\"):
                # "\ No newline at end of file" マーカーは budget を消費しない。
                continue
            head = line[:1]
            if head == "+":
                hunk["added_lines"].append(line[1:])
                rem_new -= 1
                continue
            if head == "-":
                hunk["removed_lines"].append(line[1:])
                rem_old -= 1
                continue
            if head == " " or line == "":
                # context 行 (空行は " " prefix。念のため空文字列も context 扱い)。
                rem_old -= 1
                rem_new -= 1
                continue
            # 想定外の行: hunk を打ち切り header 解釈へ落とす (truncated 耐性)。
            hunk = None
            rem_old = rem_new = 0

        # 2) file header / hunk header / metadata の解釈。
        if line.startswith("diff --git "):
            hunk = None
            rem_old = rem_new = 0
            old_path = new_path = None
            git_path = _git_header_path(line)
            continue
        if line.startswith("--- "):
            hunk = None
            rem_old = rem_new = 0
            old_path = _strip_path(line[4:])
            continue
        if line.startswith("+++ "):
            hunk = None
            rem_old = rem_new = 0
            new_path = _strip_path(line[4:])
            continue
        m = _HUNK_RE.match(line)
        if m:
            old_start = int(m.group(1))
            old_lines = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_lines = int(m.group(4)) if m.group(4) is not None else 1
            hunk = {
                "file_path": new_path or old_path or git_path,
                "change_type": _change_type(old_lines, new_lines),
                "old_start": old_start,
                "old_lines": old_lines,
                "new_start": new_start,
                "new_lines": new_lines,
                "added_lines": [],
                "removed_lines": [],
                "header": line,
            }
            hunks.append(hunk)
            rem_old = old_lines
            rem_new = new_lines
            continue
        # その他 (index / mode / rename / similarity 等の metadata) は無視する。
    return hunks


# ─────────────────── 変換本体 ───────────────────
def _entries(data: object) -> list:
    if not isinstance(data, dict):
        raise InputError("入力 JSON の root が object ではありません (C11 stdout {entries:[...]} を期待)")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise InputError("入力 JSON に entries 配列がありません (C11 stdout 形状ではありません)")
    return entries


def transform(data: object) -> list[dict]:
    """C11 stdout JSON から hunks JSON 配列を生成する。ゲート違反は GateError (exit2)。"""
    entries = _entries(data)
    all_hunks: list[dict] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise InputError(f"entries[{idx}] が object ではありません")
        diff_text = check_completeness(entry, idx)
        inherited = {
            "source_commit": entry.get("source_commit"),
            "base_commit": entry.get("base_commit"),
            "diff_sha256": entry.get("diff_sha256"),
        }
        for hunk in parse_unified_diff(diff_text):
            all_hunks.append({**inherited, **hunk})
    return all_hunks


def _read_input(args: argparse.Namespace) -> str:
    if args.stdin:
        return sys.stdin.read()
    path = Path(args.diffs)
    if not path.is_file():
        raise InputError(f"--diffs ファイルが見つかりません: {path}")
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="parse-spec-diff.py",
        description=(
            "C11 の complete=true な正規化完全 diff 集合を unified diff hunk 単位へ"
            "構造化パースする決定論変換 (C08)"
        ),
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--diffs", metavar="FILE", help="C11 stdout JSON ファイル ({entries:[...]})")
    src.add_argument("--stdin", action="store_true", help="C11 stdout JSON を標準入力から読む")
    args = ap.parse_args(argv)

    try:
        raw = _read_input(args)
    except InputError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"入力 JSON の parse に失敗しました: {exc}\n")
        return 1

    try:
        hunks = transform(data)
    except GateError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    except InputError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1

    json.dump(hunks, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
