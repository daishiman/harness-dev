#!/usr/bin/env python3
# /// script
# name: lint-dependency-direction
# purpose: Detect DAG cycles and direction violations in skill dependencies.
# inputs:
#   - argv: --skills-dir or skill paths
# outputs:
#   - stdout: OK or report path
#   - stderr: dependency violations
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""Validate that skill dependency graph has no cycles and no upward references
(ref-* / references/ should NOT depend on run-* / assign-*).

patch: PF-G4-001 — DAG循環検証スクリプト実装

NOTE: pair: フィールドは所有関係の宣言であり、実行時依存ではない。
assign-* が pair: で run-* を宣言するのは「ペアワークフロー」の記録であって
依存方向違反ではない。依存は Skill() 呼び出しパターンのみを追跡する。

Usage:
  lint-dependency-direction.py --skills-dir .claude/skills [--out report.json]

Exit codes:
  0 -> no violations
  1 -> direction violations found (ref->run etc.)
  2 -> cycles detected
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path


# Skill layers: lower number = lower layer (depended upon)
LAYER = {
    "ref": 0,
    "assign": 1,
    "run": 2,
    "wrap": 2,
    "delegate": 2,
}


def skill_prefix(name: str) -> str:
    for prefix in LAYER:
        if name.startswith(prefix + "-"):
            return prefix
    return "unknown"


def parse_invocation_dependencies(skill_md: Path) -> list[str]:
    """Extract only Skill() invocation references from SKILL.md body.
    NOTE: pair: is ownership declaration, NOT runtime dependency — excluded.
    """
    text = skill_md.read_text(encoding="utf-8")
    deps: list[str] = []
    for m in re.finditer(r"Skill\(([a-z][a-z0-9-]+)", text):
        deps.append(m.group(1))
    return list(set(deps))


def build_graph(skills_dir: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Build dependency graph {skill_name: [dependency_names]}."""
    graph: dict[str, list[str]] = {}
    prefixes: dict[str, str] = {}
    for skill_md in skills_dir.rglob("SKILL.md"):
        skill_name = skill_md.parent.name
        graph[skill_name] = parse_invocation_dependencies(skill_md)
        prefixes[skill_name] = skill_prefix(skill_name)
    return graph, prefixes


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect cycles using iterative DFS with coloring (WHITE/GRAY/BLACK)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    cycles: list[list[str]] = []

    def dfs(start: str) -> None:
        stack = [(start, iter(graph.get(start, [])))]
        path = [start]
        color[start] = GRAY
        while stack:
            node, children = stack[-1]
            try:
                child = next(children)
                if child not in graph:
                    continue
                if color.get(child, WHITE) == GRAY:
                    # Found a back edge -> cycle
                    cycle_start = path.index(child)
                    cycles.append(path[cycle_start:] + [child])
                elif color.get(child, WHITE) == WHITE:
                    color[child] = GRAY
                    path.append(child)
                    stack.append((child, iter(graph.get(child, []))))
            except StopIteration:
                color[node] = BLACK
                stack.pop()
                if len(path) > 0 and path[-1] == node:
                    path.pop()

    for node in graph:
        if color[node] == WHITE:
            dfs(node)

    return cycles


def detect_direction_violations(
    graph: dict[str, list[str]], prefixes: dict[str, str]
) -> list[dict]:
    """Detect upward dependency violations (ref->run, ref->assign, etc.)."""
    violations = []
    for src, deps in graph.items():
        src_layer = LAYER.get(prefixes.get(src, ""), 99)
        for dep in deps:
            dep_layer = LAYER.get(prefixes.get(dep, ""), 99)
            if dep_layer > src_layer:
                violations.append({
                    "source": src,
                    "source_layer": prefixes.get(src, "unknown"),
                    "dependency": dep,
                    "dependency_layer": prefixes.get(dep, "unknown"),
                    "violation": f"{prefixes.get(src)} should not invoke {prefixes.get(dep)} via Skill()",
                })
    return violations


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", default=".claude/skills")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    skills_dir = Path(args.skills_dir)
    if not skills_dir.exists():
        print(f"ERROR: skills-dir not found: {skills_dir}", file=sys.stderr)
        return 2

    graph, prefixes = build_graph(skills_dir)
    invocation_graph = {k: v for k, v in graph.items() if v}
    cycles = detect_cycles(graph)
    violations = detect_direction_violations(graph, prefixes)

    report = {
        "skills_scanned": len(graph),
        "dependency_tracking": "Skill() invocations only (pair: excluded as ownership declaration)",
        "invocation_graph": invocation_graph,
        "cycles": cycles,
        "direction_violations": violations,
        "cycles_count": len(cycles),
        "violations_count": len(violations),
    }

    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if cycles:
        print(f"FAIL: {len(cycles)} cycle(s) detected", file=sys.stderr)
        return 2
    if violations:
        print(f"FAIL: {len(violations)} direction violation(s)", file=sys.stderr)
        return 1
    print(f"OK: no cycles, no direction violations ({len(graph)} skills scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
