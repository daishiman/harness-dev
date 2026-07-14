#!/usr/bin/env python3
# /// script
# name: map-field-impact
# purpose: C09 決定論マッパ。C08 が出力した unified diff hunk を artifact kind/path と name/type/required/enum/semantics 各軸の before/after/evidence を持つ影響候補へ写像する。写像規則は references/field-impact-map から読み込み code に hardcode しない (guardian 自身が drift 源になるのを防ぐ)。
# inputs:
#   - argv: (--hunks FILE | --stdin) で C08 出力の hunks JSON を受け取る
#   - argv: --map FILE で写像表を上書き (既定は script 位置からの self-relative)
# outputs:
#   - stdout: artifact_kind/artifact_path/axis/name/type/required/enum/semantics/before/after/evidence を持つ影響候補 JSON 配列
#   - stderr: violation
#   - exit: 0=OK / 1=violation (構造不正 hunk あり) / 2=usage/IO/写像表 error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""diff hunk を harness-creator rubric/schema/template の影響候補へ決定論写像する。

写像規則 (どの path が何 kind か / どの行本文が何 axis か) は本 script に一切
hardcode せず、references/field-impact-map/field-impact-map.json を読んで適用する
だけに留める。これにより harness-creator の規約が変わっても写像表の更新のみで追従
でき、C09 のコードが drift 源になることを防ぐ (C2)。

判定手順:
  1. hunk の file_path を各 kind の path_globs (fnmatch) で照合し artifact_kind を
     決める (JSON 順で最初に一致した kind。どれにも一致しなければ other)。
  2. hunk の追加/削除行本文 (先頭 +/- マーカ除去後) を、その kind の rules の
     match_any (Python re) 群へ全て照合し、一致した rule の axis を全て採る
     (1 hunk が複数軸を同時に変えうるため先勝ちで打ち切らない)。primary は rules 順で最初。
  3. before=削除行由来の値 / after=追加行由来の値 / evidence=一致 hunk 抜粋+file_path。
  表に無い pattern は semantics へフォールバックする。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

# 影響軸。output オブジェクトはこの 5 キーを bool フラグとして持ち、一致した全軸が true
# (one-hot ではない。`axis` フィールドは primary 1 軸なのでフラグ側を正とする)。
AXES = ("name", "type", "required", "enum", "semantics")
# axis 未一致時のフォールバック軸 (レビューへ委ねる)。
FALLBACK_AXIS = "semantics"
FALLBACK_KIND = "other"
# evidence に載せる変更行の上限 (evidence を有界に保つ)。
_EVIDENCE_MAX_LINES = 12

# 写像表の既定パス: scripts/ から見た self-relative。--map で上書き可能。
DEFAULT_MAP = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "field-impact-map"
    / "field-impact-map.json"
)


def _load_json_text(text: str, label: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise UsageError(f"{label} JSON parse error: {exc}") from exc


class UsageError(Exception):
    """exit 2 (usage/IO/写像表 error) を表す例外。"""


def load_map(map_path: Path) -> dict:
    """写像表を読み込み、各 rule の match_any を precompile した構造を返す。

    構造不正 (artifact_kinds 欠落, rules 不正, regex compile 失敗) は UsageError。
    """
    if not map_path.is_file():
        raise UsageError(f"field-impact-map not found: {map_path}")
    data = _load_json_text(map_path.read_text(encoding="utf-8"), "field-impact-map")
    if not isinstance(data, dict):
        raise UsageError("field-impact-map root が object でない")
    kinds = data.get("artifact_kinds")
    if not isinstance(kinds, dict) or not kinds:
        raise UsageError("field-impact-map.artifact_kinds が object でない/空")

    compiled: dict[str, dict] = {}
    for kind, spec in kinds.items():
        if not isinstance(spec, dict):
            raise UsageError(f"artifact_kinds.{kind} が object でない")
        globs = spec.get("path_globs")
        if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
            raise UsageError(f"artifact_kinds.{kind}.path_globs が string list でない")
        rules_in = spec.get("rules")
        if not isinstance(rules_in, list):
            raise UsageError(f"artifact_kinds.{kind}.rules が list でない")
        rules_out = []
        for idx, rule in enumerate(rules_in):
            if not isinstance(rule, dict):
                raise UsageError(f"artifact_kinds.{kind}.rules[{idx}] が object でない")
            axis = rule.get("axis")
            if axis not in AXES:
                raise UsageError(
                    f"artifact_kinds.{kind}.rules[{idx}].axis={axis!r} が不正 (期待: {AXES})"
                )
            patterns = rule.get("match_any")
            if not isinstance(patterns, list) or not patterns:
                raise UsageError(
                    f"artifact_kinds.{kind}.rules[{idx}].match_any が非空 list でない"
                )
            compiled_patterns = []
            for pat in patterns:
                if not isinstance(pat, str):
                    raise UsageError(
                        f"artifact_kinds.{kind}.rules[{idx}].match_any に非文字列"
                    )
                try:
                    compiled_patterns.append(re.compile(pat))
                except re.error as exc:
                    raise UsageError(
                        f"artifact_kinds.{kind}.rules[{idx}] の regex {pat!r} が不正: {exc}"
                    ) from exc
            rules_out.append({"axis": axis, "patterns": compiled_patterns})
        compiled[kind] = {"path_globs": list(globs), "rules": rules_out}
    return compiled


def detect_kind(file_path: str, kinds: dict) -> str:
    """file_path を各 kind の path_globs (fnmatch) で照合し artifact_kind を決める。

    JSON 順で最初に一致した kind を採る。どれにも一致しなければ FALLBACK_KIND。
    """
    for kind, spec in kinds.items():
        for glob in spec["path_globs"]:
            if fnmatch.fnmatch(file_path, glob):
                return kind
    return FALLBACK_KIND


def _strip_marker(line: str) -> str:
    """先頭の単一 +/- マーカを除去する (+++/--- のファイルヘッダは対象外)。"""
    if line[:3] in ("+++", "---"):
        return line
    if line[:1] in ("+", "-"):
        return line[1:]
    return line


def _as_bodies(value: object) -> list[str]:
    """added_lines/removed_lines を本文 list へ正規化する (単一マーカを除去)。"""
    if not isinstance(value, list):
        return []
    return [_strip_marker(v) for v in value if isinstance(v, str)]


def extract_changes(hunk: dict) -> tuple[list[str], list[str], list[str]]:
    """hunk から (追加行本文, 削除行本文, 変更行抜粋) を取り出す。

    lines (raw unified diff 行の list) があればそれを最優先で使い、無ければ
    added_lines / removed_lines を使う。抜粋はマーカ付きの原文行 (有界)。
    """
    lines = hunk.get("lines")
    if isinstance(lines, list) and any(isinstance(x, str) for x in lines):
        added: list[str] = []
        removed: list[str] = []
        excerpt: list[str] = []
        for ln in lines:
            if not isinstance(ln, str):
                continue
            if ln.startswith("+++") or ln.startswith("---"):
                continue  # ファイルヘッダは変更行でない
            if ln.startswith("+"):
                added.append(ln[1:])
                excerpt.append(ln)
            elif ln.startswith("-"):
                removed.append(ln[1:])
                excerpt.append(ln)
        return added, removed, excerpt

    added = _as_bodies(hunk.get("added_lines"))
    removed = _as_bodies(hunk.get("removed_lines"))
    excerpt = ["-" + b for b in removed] + ["+" + b for b in added]
    return added, removed, excerpt


def match_axes(
    rules: list[dict], added: list[str], removed: list[str]
) -> list[tuple[str, str | None, str | None]]:
    """kind の rules を**全て**照合し、一致した (axis, before, after) を rules 順で列挙する。

    1 hunk が複数軸を同時に変えること (例: `"type": "string"`→`"integer"` と同じ hunk 内で
    description を更新 = type + semantics) は実 schema 編集の典型形。最初の一致で打ち切ると
    残りの軸を構造的に見逃すため、全 rule を照合する。
    before は各 rule で最初に一致した削除行、after は最初に一致した追加行 (無ければ None)。
    どの rule も一致しなければ FALLBACK_AXIS 単独を返し、before/after は先頭変更行由来。
    """
    matched: list[tuple[str, str | None, str | None]] = []
    for rule in rules:
        patterns = rule["patterns"]
        before = next((b for b in removed if any(p.search(b) for p in patterns)), None)
        after = next((a for a in added if any(p.search(a) for p in patterns)), None)
        if before is not None or after is not None:
            matched.append((rule["axis"], before, after))
    if matched:
        return matched
    # フォールバック: 表に無い pattern は semantics 影響としてレビューへ委ねる。
    before = removed[0] if removed else None
    after = added[0] if added else None
    return [(FALLBACK_AXIS, before, after)]



def build_evidence(file_path: str, excerpt: list[str]) -> str:
    """判定根拠文字列を組み立てる (file_path + 変更 hunk 抜粋)。"""
    lines = [f"path: {file_path}"]
    lines.extend(excerpt[:_EVIDENCE_MAX_LINES])
    if len(excerpt) > _EVIDENCE_MAX_LINES:
        lines.append(f"... ({len(excerpt) - _EVIDENCE_MAX_LINES} more lines)")
    return "\n".join(lines)


def build_candidate(
    kind: str,
    file_path: str,
    axis: str,
    before: str | None,
    after: str | None,
    evidence: str,
    matched_axes: list[str] | None = None,
) -> dict:
    """出力契約どおりのキー順で影響候補オブジェクトを組み立てる。

    `axis` は primary (rules 順で最初に一致した軸)。軸フラグは matched_axes に含まれる
    全軸を true にする (1 hunk が複数軸を同時に変えうるため one-hot に固定しない)。
    matched_axes 省略時は axis 単独。
    """
    axes = set(matched_axes) if matched_axes else {axis}
    candidate = {
        "artifact_kind": kind,
        "artifact_path": file_path,
        "axis": axis,
    }
    for a in AXES:
        candidate[a] = a in axes  # 一致した全軸を true (複数軸の同時変更を落とさない)
    candidate["before"] = before
    candidate["after"] = after
    candidate["evidence"] = evidence
    return candidate


def _hunk_file_path(hunk: dict) -> str | None:
    """hunk から対象ファイルパスを取り出す (file_path 優先, path/new_path も許容)。"""
    for key in ("file_path", "path", "new_path"):
        value = hunk.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def collect_hunks(root: object) -> list:
    """入力 JSON から hunks 配列を取り出す (list そのまま / {"hunks": [...]} 両対応)。"""
    if isinstance(root, list):
        return root
    if isinstance(root, dict):
        hunks = root.get("hunks")
        if isinstance(hunks, list):
            return hunks
        raise UsageError("入力 object に hunks 配列が無い")
    raise UsageError("入力 JSON が hunks 配列 (または {\"hunks\": [...]}) でない")


def map_impacts(root: object, kinds: dict) -> tuple[list[dict], list[str]]:
    """hunks を影響候補 list へ写像する。構造不正 hunk は violations へ記録。"""
    candidates: list[dict] = []
    violations: list[str] = []
    for idx, hunk in enumerate(collect_hunks(root)):
        if not isinstance(hunk, dict):
            violations.append(f"hunks[{idx}] が object でない")
            continue
        file_path = _hunk_file_path(hunk)
        if file_path is None:
            violations.append(f"hunks[{idx}] に file_path が無い")
            continue
        added, removed, excerpt = extract_changes(hunk)
        if not added and not removed:
            # 変更行が無い hunk は影響なし (context のみ)。violation ではない。
            continue
        kind = detect_kind(file_path, kinds)
        rules = kinds.get(kind, {}).get("rules", [])
        matched = match_axes(rules, added, removed)
        axis, before, after = matched[0]  # primary は rules 順で最初に一致した軸
        evidence = build_evidence(file_path, excerpt)
        candidates.append(
            build_candidate(kind, file_path, axis, before, after, evidence,
                            matched_axes=[a for a, _, _ in matched])
        )
    return candidates, violations


def _read_input(args: argparse.Namespace) -> str:
    if args.hunks and args.stdin:
        raise UsageError("--hunks と --stdin は同時指定できない")
    if args.hunks:
        path = Path(args.hunks)
        if not path.is_file():
            raise UsageError(f"hunks file not found: {path}")
        return path.read_text(encoding="utf-8")
    if args.stdin:
        return sys.stdin.read()
    raise UsageError("--hunks FILE か --stdin のいずれかを指定してください")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "C08 の hunks JSON を artifact kind/path と "
            "name/type/required/enum/semantics 各軸の影響候補へ決定論写像する"
        )
    )
    src = ap.add_argument_group("input source")
    src.add_argument("--hunks", help="C08 出力の hunks JSON ファイル")
    src.add_argument(
        "--stdin", action="store_true", help="hunks JSON を標準入力から読む"
    )
    ap.add_argument(
        "--map",
        default=str(DEFAULT_MAP),
        help="写像表 field-impact-map.json (既定は script 位置からの self-relative)",
    )
    args = ap.parse_args(argv)

    try:
        kinds = load_map(Path(args.map))
        raw = _read_input(args)
        root = _load_json_text(raw, "hunks")
        candidates, violations = map_impacts(root, kinds)
    except UsageError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    sys.stdout.write(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n")
    if violations:
        for v in violations:
            sys.stderr.write(v + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
