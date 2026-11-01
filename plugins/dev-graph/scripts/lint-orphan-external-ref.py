#!/usr/bin/env python3
# /// script
# name: lint-orphan-external-ref
# purpose: bd issue の external_ref から graph node への逆方向突合で、GC/削除により宙に浮いた参照を fail-closed 検出する。
# inputs: ["argv: --repo-root PATH [--graph FILE] [--beads-export FILE] [--baseline FILE] [--scan-refs] [--no-require-beads] [--issue-id ID]... [--json-out FILE]"]
# outputs: ["stdout: JSON {lint, beads_axis, baseline_source, scanned, orphans, violations, violation_count, exit_code}", "exit: 0=違反 0 件 / 1=一般エラー / 2=違反検出または beads 解決不能 (fail-closed)"]
# requires-python = ">=3.10"
# dependencies: ["../lib/orphan_external_ref.py"]
# contexts: [E]
# network: false
# write-scope: --json-out 指定時のみ
# ///
"""graph node の消失が bd issue へ伝播しなかった残置を機械検査する fail-closed lint の CLI。

入力解決 (baseline / beads / graph) と突合・分類の決定論ロジックは
``../lib/orphan_external_ref.py`` に分離し、本ファイルは引数解釈・JSON 出力・要約 stderr・
exit code の受け渡しのみに責務を限定する。検査 rule (OE-001 / OE-002) と分類の根拠は
lib 側の docstring が正本。

Exit codes:
  0  違反 0 件
  1  一般エラー
  2  違反検出 / beads 解決不能 (fail-closed)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない。
sys.dont_write_bytecode = True

LIB_DIR = str(Path(__file__).resolve().parents[1] / "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from orphan_external_ref import (  # noqa: E402
    LINT_NAME,
    LintError,
    _load_baseline,
    _resolve_beads,
    lint,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--beads-export", type=Path, default=None)
    parser.add_argument("--baseline", type=Path, default=None,
                        help="既知 orphan の baseline JSON (既定は repo-root 相対の規約 path)")
    parser.add_argument(
        "--scan-refs",
        action="store_true",
        help="他 branch / remote ref の graph を走査し、並列 worktree の node を merge_pending に分離する",
    )
    parser.add_argument("--no-require-beads", dest="require_beads",
                        action="store_false", default=True,
                        help="bd 不可用時に未評価として続行する (graph 単独 CI 用)")
    parser.add_argument("--issue-id", action="append", default=[],
                        help="対象 bd issue を絞る (反復指定可)")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        root = args.repo_root.resolve(strict=True)
        graph_path = args.graph or root / ".dev-graph" / "state" / "graph.json"
        baseline, baseline_source = _load_baseline(root, args.baseline)
        beads_rows, beads_source = _resolve_beads(root, args.beads_export)
        result = lint(
            graph_path, root, beads_rows, beads_source,
            set(args.issue_id) or None, args.require_beads,
            baseline, baseline_source, args.scan_refs,
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
            f"[{LINT_NAME}] FAIL: 新規 orphan external_ref {result['violation_count']} 件 "
            f"({result['scanned']} issue 走査 / うち dev-graph 参照 "
            f"{result['devgraph_ref_count']} / graph {result['graph_node_count']} node)",
            file=sys.stderr,
        )
    elif result["beads_axis"] == "unavailable":
        level = "FAIL" if args.require_beads else "NOTE"
        print(f"[{LINT_NAME}] {level}: beads 未解決のため逆方向突合は未評価です "
              f"({result['beads_source']})", file=sys.stderr)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
