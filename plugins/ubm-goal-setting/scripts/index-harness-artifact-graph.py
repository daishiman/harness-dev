#!/usr/bin/env python3
# /// script
# name: index-harness-artifact-graph
# version: 0.1.0
# purpose: task-graph / handoff / task-state / route-build-report / build-trace / plugin-composition /
#          EVALS / 実在 build_target を read-only 突合し、planned/built/verified/stale 状態と
#          provenance/freshness を持つ knowledge/harness-artifact-graph.json を決定論生成する (C05)。
#          plan の task graph を実成果物と誤同定しないための正規化 index であり、C07
#          (consult-harness-artifact-graph.py) がこの nodes/edges を read-only 探索する。
# inputs:
#   - argv: --plan-glob PLAN_GLOB --plugin-root DIR --out FILE
#   - file: <plan-dir>/task-graph.json (produces 辺 = task_node -> build_target)
#   - file: <plan-dir>/handoff-run-plugin-dev-plan.json (routes[].build_target/depends_on/builder)
#   - file: eval-log/<slug>/build/task-state.json (graph_hash・nodes[].state)
#   - file: eval-log/<slug>/build/route-<id>.json (route-build-report)
#   - file: eval-log/<slug>/build/skill-build-trace-<id>.json (build trace 証跡)
#   - file: <plugin-root>/plugin-composition.yaml / EVALS.json
#   - file: 実在 build_target (repo-root 相対 path を stat/存在確認)
# outputs:
#   - stdout: OK + node/edge/planned/built/verified/stale/redacted 件数・out パス
#   - stderr: VIOLATION 一覧 (壊れた突合) / usage error
#   - file: --out (harness-artifact-graph.json) ※突合 PASS 時のみ書込
#   - exit: 0=OK / 1=violation(壊れた突合) / 2=usage
# contexts: [E, C]
# network: false
# write-scope: --out (knowledge/harness-artifact-graph.json) のみ
# dependencies: []
# requires-python: ">=3.9"
# ///
"""harness 実成果物グラフの read-only 突合 index (C05)。

plan の task-graph は「これから作る計画」であって実成果物ではない。本 script は計画側
(task-graph/handoff) と実行側 (task-state/route-report/build-trace/実在 build_target) を
突合し、各 component を以下の二値検証可能な状態へ写像する:

  planned  : route 定義あり & 実体 build_target なし (まだ materialize されていない)
  built    : build_target 実在 & route report status=success (証跡は未添付)
  verified : built に加え build trace か route report evidence の証跡 PASS かつ非 stale
  stale    : 証跡が実体より古い (report mtime < artifact mtime) か graph_hash 不一致で done ノードが陳腐化

決定論: タイムスタンプは焼込まず mtime 比較結果 (boolean) のみ保存し、path は repo-root 相対
posix へ正規化する。同一入力に対し byte-identical な出力を生成する (sort_keys+indent2+末尾改行)。

redaction: 出力へ載る全 str 葉を走査し token/api key 様の値 (sk-/ntn_/ghp_/AKIA 等) を
[REDACTED] へ置換する。値は path/id/hash/状態のみで secret/PII 本文は保存しない。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
GENERATOR = "index-harness-artifact-graph.py"
OUT_FILENAME = "harness-artifact-graph.json"

TASK_GRAPH_FILENAME = "task-graph.json"
HANDOFF_FILENAME = "handoff-run-plugin-dev-plan.json"
INVENTORY_FILENAME = "component-inventory.json"
TASK_STATE_FILENAME = "task-state.json"
COMPOSITION_FILENAME = "plugin-composition.yaml"
EVALS_FILENAME = "EVALS.json"

STATE_PLANNED = "planned"
STATE_BUILT = "built"
STATE_VERIFIED = "verified"
STATE_STALE = "stale"

# derive-task-graph.py (plugin-dev-planner) の graph_hash SSOT を byte 単位で複製する。
# 差異があると常時 graph_hash 不一致 = 全 done ノード誤 stale 化を招くため厳密一致させる。
_NODE_KEYS = ("id", "title", "phase_ref", "entity_ref", "state", "write_scope", "acceptance_criterion")
_EDGE_KEYS = ("type", "from", "to")

# secret/api key 様 token の prefix パターン。sha256:<64hex> は hex のみで prefix 非該当のため誤爆しない。
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}"
    r"|ntn_[A-Za-z0-9]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[A-Za-z0-9_-]{20,})"
)
REDACTION_TOKEN = "[REDACTED]"


# ---- graph_hash (task-state pin との突合用) ---------------------------------

def _canonicalize_task_graph(graph: dict) -> dict:
    nodes = []
    for n in graph.get("nodes", []):
        out: dict = {}
        for k in _NODE_KEYS:
            if k == "acceptance_criterion":
                if k in n and n[k] is not None:
                    out[k] = n[k]
            else:
                out[k] = n.get(k)
        nodes.append(out)
    edges = [{k: e.get(k) for k in _EDGE_KEYS} for e in graph.get("edges", [])]
    nodes.sort(key=lambda n: str(n.get("id")))
    edges.sort(key=lambda e: (str(e.get("type")), str(e.get("from")), str(e.get("to"))))
    return {"schema_version": graph.get("schema_version", "1.0"), "nodes": nodes, "edges": edges}


def recompute_graph_hash(graph: dict) -> str:
    canonical = json.dumps(_canonicalize_task_graph(graph), ensure_ascii=False, indent=2)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---- redaction --------------------------------------------------------------

def _redact_str(value: str) -> tuple[str, int]:
    count = 0

    def _sub(_m: "re.Match[str]") -> str:
        nonlocal count
        count += 1
        return REDACTION_TOKEN

    return _SECRET_RE.sub(_sub, value), count


def redact_tree(obj):
    """出力木を再帰走査し全 str 葉から secret 様 token を除去する。(redacted_obj, count) を返す。"""
    if isinstance(obj, str):
        return _redact_str(obj)
    if isinstance(obj, list):
        total = 0
        out = []
        for item in obj:
            red, c = redact_tree(item)
            out.append(red)
            total += c
        return out, total
    if isinstance(obj, dict):
        total = 0
        out = {}
        for k, v in obj.items():
            red, c = redact_tree(v)
            out[k] = red
            total += c
        return out, total
    return obj, 0


# ---- I/O helpers ------------------------------------------------------------

class UsageError(Exception):
    """exit2 に写像する環境/引数エラー。"""


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path, repo_root: Path) -> str:
    """repo-root 相対 posix path へ正規化する (絶対 path を焼かず決定論/移植性を保つ)。"""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_plan_dir(plan_glob: str) -> Path:
    """--plan-glob から task-graph.json を含む plan_dir を同定する。"""
    matches = sorted(glob.glob(plan_glob, recursive=True))
    for m in matches:
        p = Path(m)
        if p.name == TASK_GRAPH_FILENAME:
            return p.parent
        if p.is_dir() and (p / TASK_GRAPH_FILENAME).exists():
            return p
    # glob がディレクトリ内 json を列挙した場合の共通親も試す
    for m in matches:
        parent = Path(m).parent
        if (parent / TASK_GRAPH_FILENAME).exists():
            return parent
    raise UsageError(f"--plan-glob に {TASK_GRAPH_FILENAME} が見つからない: {plan_glob}")


# ---- reconciliation ---------------------------------------------------------

def build_produces_index(task_graph: dict) -> dict[str, str]:
    """produces 辺から build_target -> task_node の写像を作る。"""
    index: dict[str, str] = {}
    for e in task_graph.get("edges", []):
        if e.get("type") == "produces":
            tgt = e.get("to")
            src = e.get("from")
            if isinstance(tgt, str) and isinstance(src, str):
                index.setdefault(tgt, src)
    return index


def build_task_state_index(task_state: dict) -> dict[str, str]:
    """task-state nodes[] から task_node -> state の写像を作る。"""
    index: dict[str, str] = {}
    for n in task_state.get("nodes", []):
        nid = n.get("id")
        st = n.get("state")
        if isinstance(nid, str):
            index[nid] = st if isinstance(st, str) else None
    return index


def load_composition_refs(plugin_root: Path) -> set[str]:
    """plugin-composition.yaml の `ref:` 値 (plugin-root 相対 path) を stdlib のみで抽出する。"""
    refs: set[str] = set()
    path = plugin_root / COMPOSITION_FILENAME
    if not path.exists():
        return refs
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return refs
    for m in re.finditer(r"ref:\s*([^,}\s]+)", text):
        refs.add(m.group(1).strip().rstrip("/"))
    return refs


def classify(
    *,
    artifact_present: bool,
    report_status,
    report_present: bool,
    artifact_newer_than_report,
    has_verification_evidence: bool,
    graph_hash_match,
    task_state,
) -> tuple[str, list[str]]:
    """二値シグナルから (state, stale_reasons) を決定する。"""
    report_success = report_present and report_status == "success"

    stale_reasons: list[str] = []
    if report_success and artifact_present and artifact_newer_than_report:
        stale_reasons.append("artifact_newer_than_report")
    if graph_hash_match is False and task_state == "done":
        stale_reasons.append("graph_hash_mismatch")
    stale_reasons.sort()

    if not artifact_present:
        return STATE_PLANNED, stale_reasons
    if not report_success:
        # 実体はあるがパイプラインが success を記録していない (scaffold/skip 等) → 未確定
        return STATE_PLANNED, stale_reasons
    if stale_reasons:
        return STATE_STALE, stale_reasons
    if has_verification_evidence:
        return STATE_VERIFIED, stale_reasons
    return STATE_BUILT, stale_reasons


def reconcile(
    routes: list[dict],
    *,
    repo_root: Path,
    plan_dir: Path,
    eval_build_dir: Path | None,
    task_graph: dict,
    task_state: dict | None,
    composition_refs: set[str],
    plugin_root: Path,
) -> tuple[list[dict], list[dict], list[str]]:
    """route 群を実行側成果物と突合し (nodes, edges, violations) を返す。"""
    violations: list[str] = []

    produces_index = build_produces_index(task_graph)
    route_targets = {r.get("build_target") for r in routes if r.get("build_target")}

    # orphan produces: task-graph が routes 外の build_target を produces している = 壊れた突合
    for tgt in sorted(produces_index):
        if tgt not in route_targets:
            violations.append(f"produces 辺の build_target が route 未定義 (orphan artifact): {tgt}")

    task_state_index = build_task_state_index(task_state) if task_state else {}
    recomputed_hash = recompute_graph_hash(task_graph)
    stored_hash = task_state.get("graph_hash") if task_state else None
    graph_hash_match = None
    if isinstance(stored_hash, str):
        graph_hash_match = stored_hash == recomputed_hash

    handoff_rel = _rel(plan_dir / HANDOFF_FILENAME, repo_root)
    task_graph_rel = _rel(plan_dir / TASK_GRAPH_FILENAME, repo_root)

    nodes: list[dict] = []
    seen_ids: set[str] = set()

    for route in routes:
        cid = route.get("id")
        target = route.get("build_target")
        if not isinstance(cid, str) or not cid:
            violations.append("route に有効な id が無い")
            continue
        if cid in seen_ids:
            violations.append(f"route id 重複: {cid}")
            continue
        seen_ids.add(cid)
        if not isinstance(target, str) or not target:
            violations.append(f"route {cid}: build_target 欠落")
            continue

        # 実在 build_target の dereference (dir 末尾 '/' は is_dir 判定)
        abs_target = (repo_root / target)
        if target.endswith("/"):
            artifact_present = abs_target.is_dir()
        else:
            artifact_present = abs_target.is_file()

        # route report (規約 path: eval-log/<slug>/build/route-<id>.json)
        report = None
        report_path = None
        report_status = None
        report_evidence: list = []
        if eval_build_dir is not None:
            rp = eval_build_dir / f"route-{cid}.json"
            if rp.exists():
                report_path = rp
                try:
                    report = _load_json(rp)
                except (json.JSONDecodeError, OSError) as exc:
                    violations.append(f"route {cid}: route report 解析不能: {exc}")
                    report = None
                if isinstance(report, dict):
                    report_status = report.get("status")
                    ev = report.get("evidence")
                    report_evidence = ev if isinstance(ev, list) else []
                    # 突合: report の build_target が handoff の route と一致するか
                    rep_target = report.get("build_target")
                    if isinstance(rep_target, str) and rep_target != target:
                        rep_abs = repo_root / rep_target
                        rep_present = rep_abs.is_dir() if rep_target.endswith("/") else rep_abs.is_file()
                        if not rep_present:
                            violations.append(
                                f"route {cid}: route report の build_target が実在せず handoff と不一致 "
                                f"(report={rep_target} != route={target})"
                            )
                    # route_id 整合
                    rep_id = report.get("route_id")
                    if isinstance(rep_id, str) and rep_id != cid:
                        violations.append(f"route {cid}: route report の route_id 不一致 (report={rep_id})")

        report_present = report_path is not None
        report_success = report_present and report_status == "success"

        # 壊れた突合: report が success を主張するが build_target 実在せず
        if report_success and not artifact_present:
            violations.append(
                f"route {cid}: route report status=success だが build_target 不在 (壊れた突合): {target}"
            )

        # build trace 証跡
        trace_path = None
        if eval_build_dir is not None:
            tp = eval_build_dir / f"skill-build-trace-{cid}.json"
            if tp.exists():
                trace_path = tp
        has_verification_evidence = trace_path is not None or bool(report_evidence)

        # freshness: mtime 比較結果のみ (絶対時刻は焼込まない)
        artifact_newer_than_report = None
        if artifact_present and report_present:
            try:
                artifact_newer_than_report = abs_target.stat().st_mtime > report_path.stat().st_mtime
            except OSError:
                artifact_newer_than_report = None

        produces_task_node = produces_index.get(target)
        task_state_val = task_state_index.get(produces_task_node) if produces_task_node else None

        state, stale_reasons = classify(
            artifact_present=artifact_present,
            report_status=report_status,
            report_present=report_present,
            artifact_newer_than_report=artifact_newer_than_report,
            has_verification_evidence=has_verification_evidence,
            graph_hash_match=graph_hash_match,
            task_state=task_state_val,
        )

        plugin_rel_target = target
        try:
            plugin_rel_target = Path(target).relative_to(_rel_prefix(plugin_root, repo_root)).as_posix()
        except (ValueError, RuntimeError):
            plugin_rel_target = target
        composition_declared = plugin_rel_target.rstrip("/") in composition_refs

        nodes.append({
            "id": cid,
            "component_kind": route.get("component_kind", ""),
            "name": route.get("name", ""),
            "build_target": target,
            "state": state,
            "provenance": {
                "route": f"{handoff_rel}#routes[id={cid}]",
                "builder": route.get("builder", ""),
                "build_kind": route.get("build_kind", ""),
                "produces_task_node": produces_task_node,
                "produces_edge": f"{task_graph_rel}#produces:{produces_task_node}" if produces_task_node else None,
                "task_state_node": produces_task_node if produces_task_node in task_state_index else None,
                "route_report": _rel(report_path, repo_root) if report_path else None,
                "build_trace": _rel(trace_path, repo_root) if trace_path else None,
                "composition_declared": composition_declared,
            },
            "freshness": {
                "artifact_present": artifact_present,
                "report_status": report_status,
                "artifact_newer_than_report": artifact_newer_than_report,
                "has_verification_evidence": has_verification_evidence,
                "task_state": task_state_val,
                "graph_hash_match": graph_hash_match,
                "stale_reasons": stale_reasons,
            },
        })

    # component 間 depends_on 辺 (consumes 方向 = 各 component は依存先の成果物を消費する)
    node_ids = {n["id"] for n in nodes}
    edges: list[dict] = []
    for route in routes:
        cid = route.get("id")
        if cid not in node_ids:
            continue
        for dep in route.get("depends_on", []) or []:
            if not isinstance(dep, str):
                continue
            if dep not in node_ids:
                violations.append(f"route {cid}: depends_on 先が route 未定義 (dangling): {dep}")
                continue
            edges.append({"from": cid, "to": dep, "type": "depends_on"})

    nodes.sort(key=lambda n: n["id"])
    edges.sort(key=lambda e: (e["from"], e["to"], e["type"]))
    return nodes, edges, violations


def _rel_prefix(plugin_root: Path, repo_root: Path) -> str:
    """build_target を plugin 相対に落とすための prefix (例 plugins/ubm-goal-setting)。"""
    return _rel(plugin_root, repo_root)


# ---- assembly ---------------------------------------------------------------

def assemble_graph(
    *,
    plugin_slug: str,
    stored_hash,
    recomputed_hash: str,
    graph_hash_match,
    nodes: list[dict],
    edges: list[dict],
    sources: dict,
) -> dict:
    counts = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "state_planned": sum(1 for n in nodes if n["state"] == STATE_PLANNED),
        "state_built": sum(1 for n in nodes if n["state"] == STATE_BUILT),
        "state_verified": sum(1 for n in nodes if n["state"] == STATE_VERIFIED),
        "state_stale": sum(1 for n in nodes if n["state"] == STATE_STALE),
        "redacted": 0,  # redaction walk 後に更新
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "plugin_slug": plugin_slug,
        "graph_hash": {
            "task_state": stored_hash if isinstance(stored_hash, str) else None,
            "recomputed": recomputed_hash,
            "match": graph_hash_match,
        },
        "counts": counts,
        "sources": sources,
        "nodes": nodes,
        "edges": edges,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="index-harness-artifact-graph.py",
        description="harness 実成果物グラフの read-only 突合 index (C05)",
    )
    parser.add_argument("--plan-glob", required=True, help="plan 成果物 (task-graph.json 等) を含む glob")
    parser.add_argument("--plugin-root", required=True, help="plugin ルート (例 plugins/ubm-goal-setting)")
    parser.add_argument("--out", required=True, help="出力先 knowledge/harness-artifact-graph.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)  # 引数不正は argparse が exit2

    try:
        plugin_root = Path(args.plugin_root)
        if not plugin_root.is_dir():
            raise UsageError(f"--plugin-root がディレクトリでない: {plugin_root}")
        plugin_slug = plugin_root.resolve().name

        # repo_root: plugins/<slug> 構造から導出 (build_target の repo 相対 path 解決基点)
        pr = plugin_root.resolve()
        repo_root = pr.parent.parent if pr.parent.name == "plugins" else pr.parent

        plan_dir = resolve_plan_dir(args.plan_glob)
        task_graph_path = plan_dir / TASK_GRAPH_FILENAME
        handoff_path = plan_dir / HANDOFF_FILENAME
        if not handoff_path.exists():
            raise UsageError(f"handoff が見つからない: {handoff_path}")

        try:
            task_graph = _load_json(task_graph_path)
        except (json.JSONDecodeError, OSError) as exc:
            raise UsageError(f"{TASK_GRAPH_FILENAME} 解析不能: {exc}")
        try:
            handoff = _load_json(handoff_path)
        except (json.JSONDecodeError, OSError) as exc:
            raise UsageError(f"{HANDOFF_FILENAME} 解析不能: {exc}")

        routes = handoff.get("routes")
        if not isinstance(routes, list) or not routes:
            raise UsageError("handoff に routes[] が無い")

        eval_build_dir = repo_root / "eval-log" / plugin_slug / "build"
        if not eval_build_dir.is_dir():
            eval_build_dir = None

        task_state = None
        if eval_build_dir is not None:
            ts_path = eval_build_dir / TASK_STATE_FILENAME
            if ts_path.exists():
                try:
                    task_state = _load_json(ts_path)
                except (json.JSONDecodeError, OSError) as exc:
                    # 破損 task-state は壊れた突合 (exit1) 相当だが、reconcile 前に判定できるよう violation 化
                    print(f"VIOLATION: {TASK_STATE_FILENAME} 解析不能: {exc}", file=sys.stderr)
                    return 1

        composition_refs = load_composition_refs(plugin_root)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    nodes, edges, violations = reconcile(
        routes,
        repo_root=repo_root,
        plan_dir=plan_dir,
        eval_build_dir=eval_build_dir,
        task_graph=task_graph,
        task_state=task_state,
        composition_refs=composition_refs,
        plugin_root=plugin_root,
    )

    if violations:
        print(f"VIOLATION: harness artifact 突合失敗 ({len(violations)} 件)", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    stored_hash = task_state.get("graph_hash") if task_state else None
    recomputed_hash = recompute_graph_hash(task_graph)
    graph_hash_match = None
    if isinstance(stored_hash, str):
        graph_hash_match = stored_hash == recomputed_hash

    sources = {
        "task_graph": _rel(task_graph_path, repo_root),
        "handoff": _rel(handoff_path, repo_root),
        "component_inventory": _rel(plan_dir / INVENTORY_FILENAME, repo_root)
        if (plan_dir / INVENTORY_FILENAME).exists() else None,
        "task_state": _rel(eval_build_dir / TASK_STATE_FILENAME, repo_root)
        if (eval_build_dir and (eval_build_dir / TASK_STATE_FILENAME).exists()) else None,
        "eval_build_dir": _rel(eval_build_dir, repo_root) if eval_build_dir else None,
        "plugin_composition": _rel(plugin_root / COMPOSITION_FILENAME, repo_root)
        if (plugin_root / COMPOSITION_FILENAME).exists() else None,
        "evals": _rel(plugin_root / EVALS_FILENAME, repo_root)
        if (plugin_root / EVALS_FILENAME).exists() else None,
    }

    graph = assemble_graph(
        plugin_slug=plugin_slug,
        stored_hash=stored_hash,
        recomputed_hash=recomputed_hash,
        graph_hash_match=graph_hash_match,
        nodes=nodes,
        edges=edges,
        sources=sources,
    )

    # redaction: 出力前に全 str 葉から secret 様 token を除去し件数を記録
    graph, redacted = redact_tree(graph)
    graph["counts"]["redacted"] = redacted

    out_path = Path(args.out)
    payload = json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    except OSError as exc:
        print(f"usage error: --out 書込失敗: {out_path}: {exc}", file=sys.stderr)
        return 2

    c = graph["counts"]
    if graph_hash_match is False:
        print("note: task-state の graph_hash が現行 task-graph.json と不一致 (plan drift)", file=sys.stderr)
    if redacted:
        print(f"note: secret 様 token を {redacted} 件 redact した", file=sys.stderr)
    print(
        "OK: harness-artifact-graph indexed "
        f"(nodes={c['node_count']} edges={c['edge_count']} "
        f"planned={c['state_planned']} built={c['state_built']} "
        f"verified={c['state_verified']} stale={c['state_stale']} "
        f"redacted={c['redacted']}) -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
