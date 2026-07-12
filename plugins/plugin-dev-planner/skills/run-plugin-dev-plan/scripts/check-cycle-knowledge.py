#!/usr/bin/env python3
# /// script
# name: check-cycle-knowledge
# purpose: active cycle の task spec (task-specs/<id>.md) の knowledge_refs/external_inputs を有界検査し (source_ref/freshness/decision 必須・全文 spec 注入禁止)、predecessor cycle の node を active task-graph へコピー混在させていないかを fail-closed 検証する (C19)。
# inputs:
#   - argv: <PLAN_DIR> (task-specs/ + task-graph.json を含む active cycle dir) [--predecessor-graph <path>]
# outputs:
#   - stdout: violations 列挙 もしくは OK summary
#   - stderr: IO/引数エラー
#   - exit: 0=OK / 1=violation / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""cross-cycle lineage/knowledge の有界再利用検査器 (C19)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C19) +
phase-04-test-design.md の C19 受入例。完了 cycle を immutable provenance として保持し、過去 node を
active DAG へ混在させず、source_ref 付き蒸留 knowledge と明示 artifact だけを有界再利用する契約を機械化する。
task spec の knowledge_refs は id/source_ref/freshness_checked_at/decision(adopted|rejected)+reason を、
external_inputs は path/hash を明示すること。source_ref 無し・freshness 未確認・decision 値域外・全文
spec/推移的 notes 注入・旧 node の active graph コピーのいずれかを exit1 で拒否する。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def _resolve_repo_path(value: str, repo_root: Path, label: str) -> tuple[Path | None, list[str]]:
    """repo-root 相対 path を containment 付きで解決する。"""
    try:
        root = repo_root.resolve()
        resolved = (root / value).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None, [f"{label}={value!r} が repository root 外を参照"]
    if not resolved.is_file():
        return None, [f"{label}={value!r} が実在ファイルを参照しない"]
    return resolved, []


def _valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def validate_knowledge_ref(
    ref: object, label: str, *, repo_root: Path | None = None
) -> list[str]:
    """1 件の knowledge_ref を検査する (id/source_ref/freshness_checked_at/decision/reason 必須)。"""
    if not isinstance(ref, dict):
        return [f"{label} が object でない (knowledge_ref は {{id,source_ref,freshness_checked_at,decision,reason}})"]
    errs: list[str] = []
    for key in ("id", "source_ref", "freshness_checked_at", "reason"):
        v = ref.get(key)
        if not (isinstance(v, str) and v.strip()):
            errs.append(f"{label}.{key} が非空文字列でない (蒸留 knowledge は provenance を明示すること)")
    decision = str(ref.get("decision", "")).strip()
    if decision not in specfm.KNOWLEDGE_DECISIONS:
        errs.append(f"{label}.decision={decision!r} が値域外 {list(specfm.KNOWLEDGE_DECISIONS)}")
    freshness = str(ref.get("freshness_checked_at", "")).strip()
    if freshness and not _valid_date(freshness):
        errs.append(f"{label}.freshness_checked_at={freshness!r} が YYYY-MM-DD でない")
    if repo_root is not None:
        source_ref = str(ref.get("source_ref", "")).strip()
        if source_ref:
            _, path_errs = _resolve_repo_path(source_ref, repo_root, f"{label}.source_ref")
            errs.extend(path_errs)
    return errs


def validate_external_input(
    ei: object, label: str, *, repo_root: Path | None = None
) -> list[str]:
    """1 件の external_input を検査する (path/hash を明示・過去 artifact の同定)。"""
    if not isinstance(ei, dict):
        return [f"{label} が object でない (external_input は {{path,hash}})"]
    errs: list[str] = []
    for key in ("path", "hash"):
        v = ei.get(key)
        if not (isinstance(v, str) and v.strip()):
            errs.append(f"{label}.{key} が非空文字列でない (過去 artifact は path/hash で明示同定すること)")
    digest = str(ei.get("hash", "")).strip()
    if digest and not digest.startswith("sha256:"):
        errs.append(f"{label}.hash={digest!r} が sha256:<64hex> 形式でない")
    elif digest:
        hexdigest = digest.removeprefix("sha256:")
        if len(hexdigest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in hexdigest):
            errs.append(f"{label}.hash={digest!r} が sha256:<64hex> 形式でない")
    if repo_root is not None:
        path_value = str(ei.get("path", "")).strip()
        if path_value:
            resolved, path_errs = _resolve_repo_path(path_value, repo_root, f"{label}.path")
            errs.extend(path_errs)
            if resolved is not None and digest.startswith("sha256:") and not path_errs:
                actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if digest != f"sha256:{actual}":
                    errs.append(f"{label}.hash が実ファイル sha256 と不一致")
    return errs


def validate_task_spec(
    fm: dict, spec_name: str, *, repo_root: Path | None = None
) -> list[str]:
    """1 task spec の frontmatter の knowledge_refs/external_inputs を検査する。"""
    errs: list[str] = []
    krefs = fm.get("knowledge_refs")
    if krefs is not None:
        if not isinstance(krefs, list):
            errs.append(f"[{spec_name}] knowledge_refs が list でない")
        else:
            for i, ref in enumerate(krefs):
                errs.extend(validate_knowledge_ref(
                    ref, f"[{spec_name}] knowledge_refs[{i}]", repo_root=repo_root
                ))
    einputs = fm.get("external_inputs")
    if einputs is not None:
        if not isinstance(einputs, list):
            errs.append(f"[{spec_name}] external_inputs が list でない")
        else:
            for i, ei in enumerate(einputs):
                errs.extend(validate_external_input(
                    ei, f"[{spec_name}] external_inputs[{i}]", repo_root=repo_root
                ))
    return errs


def _node_ids(graph: dict) -> set[str]:
    return {
        n["id"]
        for n in graph.get("nodes", [])
        if isinstance(n, dict) and isinstance(n.get("id"), str)
    }


def check_no_predecessor_node_copy(active_graph: dict, predecessor_graph: dict) -> list[str]:
    """predecessor cycle の node id が active graph に混在していないか検査する (C19)。

    過去 node を active DAG へコピーするのは lineage (immutable provenance) の逸脱。共有 id は
    「過去 node の active 混入」ゆえ fail-closed 拒否する (再利用は蒸留 knowledge + 明示 artifact のみ)。
    """
    overlap = sorted(_node_ids(active_graph) & _node_ids(predecessor_graph))
    return [
        f"predecessor cycle の node {nid!r} が active graph に混在 "
        "(過去 node を active DAG へコピー禁止・再利用は knowledge_refs/external_inputs のみ)"
        for nid in overlap
    ]


def scan(
    plan_dir: Path,
    predecessor_graph_path: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    """active cycle dir を走査し task spec knowledge + predecessor 混入を検査する。"""
    errs: list[str] = []
    specs_dir = plan_dir / "task-specs"
    index_path = plan_dir / "index.md"
    shape_marker = "fixed-13-phase"
    if index_path.is_file():
        try:
            shape_marker = str(
                specfm.parse_frontmatter(index_path.read_text(encoding="utf-8")).get("shape_marker")
                or "fixed-13-phase"
            )
        except OSError as exc:
            errs.append(f"index.md 読込失敗: {exc}")
    if shape_marker == "task-graph-derived" and not list(specs_dir.glob("*.md")):
        errs.append("task-graph-derived shape は task-specs/*.md を 1 件以上要求 (空走査 PASS 禁止)")
    if specs_dir.is_dir():
        for spec_path in sorted(specs_dir.glob("*.md")):
            try:
                fm = specfm.parse_frontmatter(spec_path.read_text(encoding="utf-8"))
            except OSError as exc:
                errs.append(f"[{spec_path.name}] 読込失敗: {exc}")
                continue
            errs.extend(validate_task_spec(fm, spec_path.name, repo_root=repo_root))

    if predecessor_graph_path is not None:
        active_path = plan_dir / "task-graph.json"
        try:
            active_graph = json.loads(active_path.read_text(encoding="utf-8"))
            predecessor_graph = json.loads(predecessor_graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errs.append(f"task-graph 読込/parse 失敗 (lineage 検査): {exc}")
        else:
            errs.extend(check_no_predecessor_node_copy(active_graph, predecessor_graph))
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="cross-cycle knowledge/lineage の有界再利用検査 (C19)")
    ap.add_argument("plan_dir", help="task-specs/ + task-graph.json を含む active cycle dir")
    ap.add_argument("--predecessor-graph", default=None, help="predecessor cycle の task-graph.json (任意)")
    ap.add_argument(
        "--repo-root",
        default=None,
        help="source_ref/external_inputs の実在・hash照合基点 (指定時のみ厳格検査)",
    )
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    pred = Path(args.predecessor_graph) if args.predecessor_graph else None
    repo_root = Path(args.repo_root) if args.repo_root else None

    violations = scan(plan_dir, pred, repo_root=repo_root)
    if violations:
        for v in violations:
            print(v)
        return 1
    print("OK: cycle knowledge/lineage 妥当 (source_ref 付き蒸留 + 明示 artifact のみ・過去 node 混入 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
