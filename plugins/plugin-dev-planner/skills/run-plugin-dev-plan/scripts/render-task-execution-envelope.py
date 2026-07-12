#!/usr/bin/env python3
# /// script
# name: render-task-execution-envelope
# purpose: dispatch 対象 task node + 可変 task spec + 単一 phase policy から TaskExecutionEnvelope を決定論合成する (C17)。title 単独 prompt / entity_ref 暗黙 route / component-build の route 欠落 / phase-gate の dispatch / P01..P13 全文注入を fail-closed 拒否する。
# inputs:
#   - argv: <PLAN_DIR> --task-id <id> [--notes <handoff-notes.json>] [--emit <out.json>]
# outputs:
#   - stdout: envelope JSON (--emit 未指定時) もしくは violations 列挙
#   - stderr: usage/IO error
#   - exit: 0=OK (envelope 合成成功) / 1=violation (合成拒否) / 2=usage/IO error/node 不在
# contexts: [C, E]
# network: false
# write-scope: <PLAN_DIR>/<--emit path> (--emit 指定時のみ・既定は stdout で副作用なし)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""TaskExecutionEnvelope の決定論合成器 (C17)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C17) +
phase-04-test-design.md の C17 受入例。task-graph leaf node の execution_kind/route_ref/
task_spec_ref と可変 task spec (task-specs/<id>.md frontmatter) と node.phase_ref が指す単一
phase policy から、consumer=harness-creator が SubAgent へ渡す唯一の入力 packet を合成する。
title 単独・entity_ref 暗黙 route・route 欠落・phase-gate dispatch・13 phase 全文注入を
fail-closed で拒否し、schema (task-execution-envelope.schema.json) 完全性を満たす envelope のみ返す。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

_PHASE_ID_RE = re.compile(r"^P(0[1-9]|1[0-3])$")
_HANDOFF_NAME = "handoff-run-plugin-dev-plan.json"


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CYCLE_KNOWLEDGE = _load_sibling("check-cycle-knowledge")


def _resolve_within_plan_dir(plan_dir: Path, ref: str) -> Path | None:
    """ref を PLAN_DIR 内の解決済み path にする。外部・symlink escape は None。"""
    try:
        root = plan_dir.resolve()
        candidate = (root / ref).resolve()
    except (OSError, RuntimeError):
        return None
    return candidate if candidate.is_relative_to(root) else None


def load_task_spec(plan_dir: Path, task_spec_ref: str) -> dict:
    """task-specs/<id>.md の frontmatter を dict で返す (不在/parse 不能は空 dict)。

    objective/verify/acceptance_criteria/knowledge_refs を担う可変 task spec。全文本文は
    envelope へ埋め込まず frontmatter の宣言だけを合成材料にする (title 単独 prompt/全文注入回避)。
    """
    p = _resolve_within_plan_dir(plan_dir, task_spec_ref)
    if p is None or not p.is_file():
        return {}
    try:
        return specfm.parse_frontmatter(p.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _consumes_artifacts(graph: dict, task_id: str) -> list[str]:
    """graph の consumes エッジのうち to==task_id の from (artifact id) を昇順で返す。"""
    arts = {
        e.get("from")
        for e in graph.get("edges", [])
        if isinstance(e, dict) and e.get("type") == "consumes" and e.get("to") == task_id
    }
    return sorted(a for a in arts if isinstance(a, str) and a)


def _as_str_list(v) -> list[str]:
    """scalar/list を非空文字列の list へ正規化する。"""
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str) and x.strip()]
    return []


def validate_dispatchable(node: dict, route_ids: set[str] | None = None) -> list[str]:
    """node が dispatch 対象 (envelope 化可能) の前提を満たすか検査する (C17 fail-closed 群)。"""
    errs: list[str] = []
    if not isinstance(node, dict):
        return ["node が object でない"]
    nid = str(node.get("id", "")).strip() or "?"

    ek = node.get("execution_kind")
    if ek is None or not str(ek).strip():
        errs.append(f"[{nid}] execution_kind 欠落 (dispatch には execution_kind 必須)")
    elif ek not in specfm.EXECUTION_KINDS:
        errs.append(f"[{nid}] execution_kind={ek!r} が enum 外 {list(specfm.EXECUTION_KINDS)}")
    elif ek == "phase-gate":
        errs.append(f"[{nid}] execution_kind=phase-gate は非 dispatch 集約点ゆえ envelope 化しない")

    tsr = node.get("task_spec_ref")
    if not (isinstance(tsr, str) and tsr.strip()):
        errs.append(f"[{nid}] task_spec_ref 欠落 (title 単独 prompt を防ぐため可変 task spec 必須)")

    if ek == "component-build":
        rr = node.get("route_ref")
        if not (isinstance(rr, str) and rr.strip()):
            ent = node.get("entity_ref")
            hint = (
                f" (entity_ref={ent!r} からの暗黙 route 推測は禁止・明示 route_ref を宣言すること)"
                if isinstance(ent, str) and ent.strip() else ""
            )
            errs.append(f"[{nid}] component-build は明示 route_ref 必須{hint}")
        elif route_ids is not None and rr not in route_ids:
            errs.append(
                f"[{nid}] route_ref={rr!r} が {_HANDOFF_NAME} routes[] に不在"
            )
    elif ek == "direct-task":
        rr = node.get("route_ref")
        if isinstance(rr, str) and rr.strip():
            errs.append(f"[{nid}] direct-task は route_ref を持たない (route_ref={rr!r} は component-build 専用)")

    pr = node.get("phase_ref")
    if not (isinstance(pr, str) and _PHASE_ID_RE.match(str(pr))):
        errs.append(
            f"[{nid}] phase_ref={pr!r} が単一 phase id (P01..P13) でない "
            "(P01..P13 全文の連結注入は phase_policy_ref 単一参照で拒否する)"
        )
    return errs


def build_envelope(
    node: dict,
    spec: dict,
    graph: dict,
    notes: dict | None = None,
    route_ids: set[str] | None = None,
) -> tuple[dict | None, list[str]]:
    """node/spec/graph/notes から envelope を合成する。violations 非空なら (None, violations)。"""
    errs = validate_dispatchable(node, route_ids=route_ids)
    if errs:
        return None, errs

    nid = str(node["id"])
    objective = str(spec.get("objective", "")).strip()
    if not objective:
        return None, [
            f"[{nid}] objective 欠落 (task spec の objective が空・title 単独 prompt は不可)"
        ]

    verify = str(spec.get("verify", "")).strip()
    if not verify:
        return None, [f"[{nid}] verify 欠落 (task spec に検証方法が無い・done 判定不能)"]

    acceptance: list[str] = []
    node_ac = node.get("acceptance_criterion")
    if isinstance(node_ac, str) and node_ac.strip():
        acceptance.append(node_ac.strip())
    for item in _as_str_list(spec.get("acceptance_criteria")):
        if item not in acceptance:
            acceptance.append(item)
    if not acceptance:
        return None, [
            f"[{nid}] acceptance_criteria が空 (node.acceptance_criterion も task spec も未携帯)"
        ]

    write_scope = str(node.get("write_scope", "")).strip()
    if not write_scope:
        return None, [f"[{nid}] write_scope が空 (並列衝突判定キー欠落)"]

    ek = str(node["execution_kind"])
    route_ref = node.get("route_ref")
    component_route = route_ref if (ek == "component-build" and isinstance(route_ref, str)) else None

    knowledge = spec.get("knowledge_refs")
    knowledge_refs = [k for k in knowledge if isinstance(k, dict)] if isinstance(knowledge, list) else []
    if isinstance(knowledge, list) and len(knowledge_refs) != len(knowledge):
        return None, [f"[{nid}] knowledge_refs は object 配列でなければならない"]
    for idx, ref in enumerate(knowledge_refs):
        knowledge_errs = _CYCLE_KNOWLEDGE.validate_knowledge_ref(
            ref, f"[{nid}] knowledge_refs[{idx}]"
        )
        if knowledge_errs:
            return None, knowledge_errs

    default_notes = {"went_well": [], "friction_points": [], "downstream_watchouts": []}
    injected_notes = notes if isinstance(notes, dict) else default_notes

    envelope = {
        "task_id": nid,
        "execution_kind": ek,
        "objective": objective,
        "phase_policy_ref": str(node["phase_ref"]),
        "component_route": component_route,
        "acceptance_criteria": acceptance,
        "write_scope": write_scope,
        "injected_inputs": _consumes_artifacts(graph, nid),
        "injected_notes": injected_notes,
        "knowledge_refs": knowledge_refs,
        "verify": verify,
    }
    return envelope, []


def _find_node(graph: dict, task_id: str) -> dict | None:
    for n in graph.get("nodes", []):
        if isinstance(n, dict) and n.get("id") == task_id:
            return n
    return None


def _load_handoff_route_ids(plan_dir: Path) -> tuple[set[str] | None, str | None]:
    """handoff があれば route id 集合を返す。不在は legacy 互換として None。"""
    handoff_path = plan_dir / _HANDOFF_NAME
    if not handoff_path.exists():
        return None, None
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"handoff 読込/parse 失敗: {exc}"
    routes = handoff.get("routes") if isinstance(handoff, dict) else None
    if not isinstance(routes, list):
        return None, "handoff routes[] が配列でない"
    route_ids = {
        route.get("id")
        for route in routes
        if isinstance(route, dict) and isinstance(route.get("id"), str) and route["id"].strip()
    }
    return route_ids, None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TaskExecutionEnvelope を合成する (C17)")
    ap.add_argument("plan_dir", help="task-graph.json / task-specs/ を含む PLAN_DIR")
    ap.add_argument("--task-id", required=True, help="dispatch 対象 task node の id")
    ap.add_argument("--notes", default=None, help="有界 handoff notes JSON (任意)")
    ap.add_argument("--emit", default=None, help="envelope 書込先 (未指定は stdout)")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    plan_dir = Path(args.plan_dir)
    graph_path = plan_dir / "task-graph.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"task-graph 読込/parse 失敗: {exc}\n")
        return 2

    node = _find_node(graph, args.task_id)
    if node is None:
        sys.stderr.write(f"task-id={args.task_id!r} が task-graph 上に不在\n")
        return 2

    emit_path = None
    if args.emit:
        emit_path = _resolve_within_plan_dir(plan_dir, args.emit)
        if emit_path is None:
            print(f"[{args.task_id}] --emit={args.emit!r} が PLAN_DIR 外を指す")
            return 1

    notes = None
    if args.notes:
        try:
            notes = json.loads(Path(args.notes).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"notes 読込/parse 失敗: {exc}\n")
            return 2

    tsr = node.get("task_spec_ref")
    if isinstance(tsr, str) and tsr.strip() and _resolve_within_plan_dir(plan_dir, tsr) is None:
        print(f"[{args.task_id}] task_spec_ref={tsr!r} が PLAN_DIR 外を指す")
        return 1
    spec = load_task_spec(plan_dir, tsr) if isinstance(tsr, str) and tsr.strip() else {}

    route_ids, handoff_error = _load_handoff_route_ids(plan_dir)
    if handoff_error:
        sys.stderr.write(handoff_error + "\n")
        return 2

    envelope, violations = build_envelope(node, spec, graph, notes, route_ids=route_ids)
    if violations:
        for v in violations:
            print(v)
        return 1

    payload = json.dumps(envelope, ensure_ascii=False, indent=2)
    if emit_path is not None:
        try:
            emit_path.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"envelope 書込失敗: {exc}\n")
            return 2
        print(str(emit_path))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
