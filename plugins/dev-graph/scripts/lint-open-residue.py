#!/usr/bin/env python3
# /// script
# name: lint-open-residue
# purpose: 解決済み事象の open 残置 (md / graph node / beads の 3 表現の乖離) を fail-closed で検出する。
# inputs: ["argv: --repo-root PATH [--graph FILE] [--beads-export FILE] [--no-require-beads] [--node-id ID]... [--json-out FILE]"]
# outputs: ["stdout: JSON {lint, repo_root, beads_axis, beads_source, scanned, violations, violation_count, exit_code}", "exit: 0=違反 0 件 / 1=一般エラー / 2=違反検出または beads 解決不能 (fail-closed)"]
# requires-python = ">=3.10"
# dependencies: []
# contexts: [E]
# network: false
# write-scope: --json-out 指定時のみ
# ///
"""lifecycle close-loop の残置を機械検査する fail-closed lint。

正本契約: ``templates/task.md`` の「status の意味論 (二重正本の禁止)」。

意味論の分離 (no-dual-authority 制約):
  status                      文書ライフサイクル (draft/active/blocked/done/closed/tombstoned)
  completion_evidence.status  実行状態 (open/in_progress/blocked/done/not_applicable)
  beads issue status          課題トラッカー上の状態
「status=closed かつ completion_evidence.status=in_progress」は矛盾ではない
(文書は役割終了、実行の reconcile は未了)。したがって両者を別 rule で検査する。

検出 rule:
  OR-001  md frontmatter の status と graph node の status が不一致
  OR-002  md frontmatter の completion_evidence と graph node の completion_evidence が不一致
  OR-003  beads=closed なのに completion_evidence.status が done/not_applicable でない
          (= 解決済みの open 残置。本 lint の主目的)
  OR-004  completion_evidence.status=done なのに beads が closed でない (逆向き残置)

beads 状態の解決順序:
  1. --beads-export FILE
  2. PATH 上の bd による `bd export` (Dolt DB の live 状態)
  3. いずれも不可なら --require-beads (既定) で exit 2

`.beads/issues.jsonl` は通信・状態判定の正本ではないため暗黙には読みません。固定 snapshot
を検査する場合だけ、利用者が `--beads-export` で明示します。

保証境界: CI に beads (Dolt DB) が無い環境では --no-require-beads を用い、
git 追跡ファイルのみで完結する OR-001 / OR-002 のみを強制する。この場合
JSON の beads_axis に "unavailable" を記録し、未評価であることを明示する。

Exit codes:
  0  違反 0 件
  1  一般エラー
  2  違反検出 / beads 解決不能 (fail-closed)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LINT_NAME = "lint-open-residue"

# 実行が完了しているとみなせる completion_evidence.status。
_SETTLED_COMPLETION = frozenset({"done", "not_applicable"})

# frontmatter の 1 行を key と JSON 値へ割る。値は build-graph-node.py が
# json.dumps(sort_keys=True) で書くため JSON として読める。
_FRONTMATTER_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


class LintError(Exception):
    """検査を続行できない一般エラー (exit 1)。"""


def _read_frontmatter(path: Path) -> dict | None:
    """artifact md の YAML frontmatter を dict として読む。読めなければ None。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    result: dict = {}
    for line in text[4:end].splitlines():
        match = _FRONTMATTER_LINE.match(line)
        if not match:
            continue
        key, raw = match.group(1), match.group(2).strip()
        if not raw:
            continue
        try:
            result[key] = json.loads(raw)
        except json.JSONDecodeError:
            result[key] = raw.strip('"')
    return result


def _resolve_beads(root: Path, explicit: Path | None) -> tuple[dict[str, str] | None, str]:
    """beads issue id -> status の写像を解決する。(写像, 由来) を返す。解決不能なら (None, 理由)。"""
    if explicit is not None:
        try:
            mapping = _parse_beads_jsonl(explicit)
        except (OSError, json.JSONDecodeError) as exc:
            raise LintError(f"beads export を読めません: {explicit}: {exc}") from exc
        return mapping, f"--beads-export {explicit}"

    if shutil.which("bd"):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "issues.jsonl"
            try:
                subprocess.run(
                    ["bd", "export", "-o", str(out)],
                    cwd=str(root), capture_output=True, check=True, timeout=120,
                )
                return _parse_beads_jsonl(out), "bd export"
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
                return None, "bd export に失敗"

    return None, "beads export が見つからず bd も PATH 上にありません"


def _parse_beads_jsonl(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            mapping[record["id"]] = str(record.get("status", ""))
    return mapping


def _violation(rule: str, node: dict, detail: str, bd_issue_id: str | None = None) -> dict:
    return {
        "rule": rule,
        "path": str(node.get("file_path") or ""),
        "graph_node_id": str(node.get("graph_node_id") or ""),
        "bd_issue_id": bd_issue_id,
        "detail": detail,
    }


def _inspect(root: Path, node: dict, beads: dict[str, str] | None) -> list[dict]:
    """1 node を 4 rule で検査する。"""
    violations: list[dict] = []
    linkage = node.get("beads_linkage") if isinstance(node.get("beads_linkage"), dict) else {}
    bd_issue_id = linkage.get("bd_issue_id") if isinstance(linkage.get("bd_issue_id"), str) else None

    front = _read_frontmatter(root / str(node.get("file_path") or ""))
    if front is not None:
        if front.get("status") != node.get("status"):
            violations.append(_violation(
                "OR-001", node,
                f"md status={front.get('status')!r} と graph status={node.get('status')!r} が不一致",
                bd_issue_id,
            ))
        if front.get("completion_evidence") != node.get("completion_evidence"):
            violations.append(_violation(
                "OR-002", node,
                "md completion_evidence と graph completion_evidence が不一致",
                bd_issue_id,
            ))

    if beads is None or bd_issue_id is None:
        return violations

    beads_status = beads.get(bd_issue_id)
    if beads_status is None:
        return violations  # graph が指す beads issue が export に無い (別 workspace) — 対象外
    evidence = node.get("completion_evidence") if isinstance(node.get("completion_evidence"), dict) else {}
    completion = evidence.get("status")

    if beads_status == "closed" and completion not in _SETTLED_COMPLETION:
        violations.append(_violation(
            "OR-003", node,
            f"beads={beads_status} だが completion_evidence.status={completion!r} "
            "(解決済み事象が open のまま残置)",
            bd_issue_id,
        ))
    if completion == "done" and beads_status != "closed":
        violations.append(_violation(
            "OR-004", node,
            f"completion_evidence.status=done だが beads={beads_status!r} (逆向き残置)",
            bd_issue_id,
        ))
    return violations


def decide_exit_code(violations: list[dict], beads_axis: str, require_beads: bool) -> int:
    """検出結果から exit code を決める fail-closed 判定。

    Args:
        violations: 検出された違反のリスト。
        beads_axis: "resolved" (OR-003/OR-004 を評価済み) または "unavailable" (未評価)。
        require_beads: --require-beads が有効かどうか (既定 True)。

    Returns:
        exit code (0 または 2)。
    """
    # 違反が 1 件でもあれば遮断する (fail-closed-lint 制約)。
    if violations:
        return 2
    # live Beads 軸を要求したのに解決できなければ、JSON 証跡を出した上で遮断する。
    if beads_axis == "unavailable" and require_beads:
        return 2
    return 0


def lint(
    root: Path,
    graph_path: Path,
    beads: dict[str, str] | None,
    beads_source: str,
    node_ids: set[str] | None,
    require_beads: bool,
) -> dict:
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        nodes = graph["nodes"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise LintError(f"graph を読めません: {graph_path}: {exc}") from exc
    if not isinstance(nodes, list):
        raise LintError("graph の nodes[] が配列ではありません")

    violations: list[dict] = []
    scanned = 0
    for node in sorted(
        (n for n in nodes if isinstance(n, dict)),
        key=lambda n: str(n.get("graph_node_id", "")),
    ):
        if node.get("artifact_kind") not in ("issue", "task"):
            continue
        if node.get("tracker_binding") != "beads":
            continue
        if node_ids and str(node.get("graph_node_id")) not in node_ids:
            continue
        scanned += 1
        violations.extend(_inspect(root, node, beads))

    beads_axis = "resolved" if beads is not None else "unavailable"
    violations.sort(key=lambda v: (v["rule"], v["graph_node_id"]))
    return {
        "lint": LINT_NAME,
        "repo_root": ".",
        "beads_axis": beads_axis,
        "beads_source": beads_source,
        "scanned": scanned,
        "violations": violations,
        "violation_count": len(violations),
        "exit_code": decide_exit_code(violations, beads_axis, require_beads),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--beads-export", type=Path, default=None)
    parser.add_argument("--no-require-beads", dest="require_beads",
                        action="store_false", default=True,
                        help="beads 不可用時に OR-003/OR-004 を未評価として続行する")
    parser.add_argument("--node-id", action="append", default=[],
                        help="対象 node を絞る (反復指定可)")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        root = args.repo_root.resolve(strict=True)
        graph_path = args.graph or root / ".dev-graph" / "state" / "graph.json"
        beads, beads_source = _resolve_beads(root, args.beads_export)
        result = lint(
            root, graph_path, beads, beads_source,
            set(args.node_id) or None, args.require_beads,
        )
    except (LintError, OSError) as exc:
        print(f"[{LINT_NAME}] ERROR: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")

    if result["violation_count"]:
        print(
            f"[{LINT_NAME}] FAIL: open 残置 {result['violation_count']} 件 "
            f"({result['scanned']} node 走査 / beads_axis={result['beads_axis']})",
            file=sys.stderr,
        )
    elif result["beads_axis"] == "unavailable":
        level = "FAIL" if args.require_beads else "NOTE"
        print(f"[{LINT_NAME}] {level}: beads 未解決のため OR-003/OR-004 は未評価です "
              f"({result['beads_source']})", file=sys.stderr)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
