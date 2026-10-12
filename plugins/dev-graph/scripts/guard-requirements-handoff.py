#!/usr/bin/env python3
# /// script
# name: guard-requirements-handoff
# purpose: C04 の handoff gate。handoff 対象 node から参照 closure (depends_on/related_nodes/architecture_refs/parent_feature と package member) をたどり、C11 と同じ readiness 判定で incomplete/unknown/pending/fail/stale/draft/superseded/tombstoned/参照切れの node が1件でもあれば、全件の missing_sections と remediation owner を返して handoff を0件にする。何も書かない。
# inputs: ["argv: --repo-root PATH --node ID [--node ID]... [--config PATH] [--expect-graph-digest sha256:HEX]"]
# outputs: ["stdout: JSON handoff guard report {status, scope, graph{path, node_count, graph_revision, digest, expected_digest, digest_match}, handoff_count, handoff[], closure[], blocked[], missing_sections[], c11, write_count}", "exit: 0=handoff (closure 全件 ready) / 1=withheld (handoff 0件) / 2=snapshot_mismatch (graph.digest が --expect-graph-digest と違う。handoff 0件), usage, C24 or IO"]
# requires-python = ">=3.10"
# dependencies: [_common.py, resolve-repo-context.py, validate-graph-schema.py, register-package.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""C04 requirements handoff guard.

requirements は handoff 対象 node だけでなく、それが参照する node の内容から作られる。参照 closure は対象 node から
``depends_on``・``related_nodes``・``architecture_refs``・``parent_feature`` と、feature の package member
(``parent_feature`` がその feature の node) を推移的にたどったものとする。

closure の node は次をすべて満たすときだけ ready である。

- graph に存在し、``status`` が ``tombstoned`` でない。
- C11 (``validate-graph-schema.node_readiness``) が incomplete/unknown に数えず、``missing_sections`` が空。
- ``evaluation_status`` が ``pass``、``confirmation_status`` が ``confirmed``。
- C11 の violation がその node に無い。

1件でも ready でなければ、handoff は対象全体で0件にする (一部だけを handoff しない)。blocked の node はすべて、
理由・``missing_sections`` (C11 と同じ値をそのまま)・remediation owner (lineage の origin で決まる修復担当の skill
と node の owners) を持つ。graph に C11 の violation があるときも handoff は0件にする。

guard が読んだ graph の snapshot は ``graph.digest`` (C02 の ``register-package._canonical_digest`` で取った graph 全体の
digest。``validate-readiness-binding.py`` の ``graph.digest`` と同じ定義) と ``graph.graph_revision`` で返す。
``--expect-graph-digest`` に binding の ``graph.digest`` を渡すと、guard が見た graph が binding の見た graph と
違うとき (2つの script の間に graph が変わったとき) は ``snapshot_mismatch`` として handoff を0件にし、exit 2 で止まる。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, contained, dump, run

SCRIPTS = Path(__file__).resolve().parent
RESOLVE = SCRIPTS / "resolve-repo-context.py"
REFERENCE_FIELDS = ("depends_on", "related_nodes", "architecture_refs")
# origin_kind → (修復担当の skill, その上流)。外部 plugin が正本の node を dev-graph が直接直さない。
OWNERS = {
    "system-dev-planner": ("system-dev-planner:run-system-dev-plan", None),
    "system-spec-harness": ("run-dev-graph-system-spec", "system-spec-harness"),
}
DEFAULT_OWNER = ("run-dev-graph-node", None)


def _module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    if spec is None or spec.loader is None:
        raise ContractError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _context(repo_root: str, config: str) -> dict[str, Any]:
    cp = run([sys.executable, str(RESOLVE), "--repo-root", repo_root, "--config", config, "--mode", "read"], check=False)
    if cp.returncode:
        raise ContractError(f"resolve-repo-context failed: {(cp.stderr or cp.stdout).strip()}")
    receipt = json.loads(cp.stdout)
    root = Path(receipt["repo_root"]).resolve(strict=True)
    if Path(receipt["content_roots"]["repository"]).resolve(strict=True) != root:
        raise ContractError("resolve-repo-context repo_root differs from content_roots.repository")
    return receipt


def _references(node: dict[str, Any], children: dict[str, list[str]]) -> list[str]:
    refs = [ref for field in REFERENCE_FIELDS for ref in (node.get(field) or []) if isinstance(ref, str)]
    if isinstance(node.get("parent_feature"), str):
        refs.append(node["parent_feature"])
    return refs + children.get(str(node.get("graph_node_id")), [])


def closure(scope: list[str], by_id: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """scope から参照をたどった node id → 参照元 id の一覧 (scope 自身の参照元は空)。"""
    children: dict[str, list[str]] = {}
    for node in by_id.values():
        if isinstance(node.get("parent_feature"), str):
            children.setdefault(node["parent_feature"], []).append(str(node["graph_node_id"]))
    referenced_by: dict[str, list[str]] = {node_id: [] for node_id in scope}
    queue = list(scope)
    while queue:
        node_id = queue.pop(0)
        node = by_id.get(node_id)
        if node is None:
            continue
        for ref in _references(node, children):
            if ref not in referenced_by:
                referenced_by[ref] = []
                queue.append(ref)
            if node_id not in referenced_by[ref] and ref != node_id:
                referenced_by[ref].append(node_id)
    return {node_id: sorted(sources) for node_id, sources in referenced_by.items()}


def _reasons(node: dict[str, Any] | None, readiness: dict[str, Any] | None, c11_codes: list[str]) -> list[str]:
    if node is None:
        return ["reference_missing"]
    reasons = []
    if node.get("status") == "tombstoned":
        reasons.append("tombstoned")
    if readiness is not None:
        reasons.append(f"readiness_{readiness['status']}")
    elif (node.get("implementation_readiness") or {}).get("missing_sections"):
        reasons.append("missing_sections")
    if node.get("evaluation_status") != "pass":
        reasons.append(f"evaluation_{node.get('evaluation_status') or 'missing'}")
    if node.get("confirmation_status") != "confirmed":
        reasons.append(f"confirmation_{node.get('confirmation_status') or 'missing'}")
    reasons += [f"c11:{code}" for code in c11_codes]
    return reasons


def _remediation(node: dict[str, Any] | None, referenced_by: list[str]) -> dict[str, Any]:
    origin = ((node or {}).get("source_lineage") or {}).get("origin_kind")
    owner, upstream = OWNERS.get(origin, DEFAULT_OWNER)
    return {"owner": owner, "upstream": upstream, "origin_kind": origin,
            "owners": list((node or {}).get("owners") or []), "referenced_by": referenced_by}


def guard(receipt: dict[str, Any], scope: list[str], expected_digest: str | None = None) -> tuple[int, dict[str, Any]]:
    root = Path(receipt["repo_root"]).resolve(strict=True)
    graph_path = contained(Path(receipt["local_state_paths"]["graph"]), root)
    vgs = _module("dev_graph_c04_guard_validate_graph_schema", "validate-graph-schema.py")
    rp = _module("dev_graph_c04_guard_register_package", "register-package.py")
    graph = json.loads(graph_path.read_bytes().decode("utf-8"))
    nodes = vgs.nodes_of(graph)
    # binding (validate-readiness-binding.py) と同じ定義の snapshot。一度だけ parse した graph から取る。
    digest = rp._canonical_digest(graph)
    revision = graph.get("graph_revision") if isinstance(graph, dict) else None
    c11 = vgs.validate(nodes, repo_root=vgs._repo_root_for(graph_path, str(root)))
    by_id = {str(node["graph_node_id"]): node for node in nodes if isinstance(node, dict) and node.get("graph_node_id")}
    reach = closure(scope, by_id)
    present = [by_id[node_id] for node_id in reach if node_id in by_id]
    readiness = {item["graph_node_id"]: item for item in vgs.node_readiness(present)["incomplete_nodes"]}

    rows, blocked = [], []
    for node_id in sorted(reach):
        node = by_id.get(node_id)
        reasons = _reasons(node, readiness.get(node_id), sorted({item["code"] for item in c11 if item.get("node") == node_id}))
        missing = list(((node or {}).get("implementation_readiness") or {}).get("missing_sections") or [])
        if node_id in readiness:
            missing = readiness[node_id]["missing_sections"]
        row = {"graph_node_id": node_id, "artifact_kind": (node or {}).get("artifact_kind"), "in_scope": node_id in scope,
               "referenced_by": reach[node_id], "verdict": "blocked" if reasons else "ready", "reasons": reasons,
               "missing_sections": missing}
        rows.append(row)
        if reasons:
            blocked.append({**row, "remediation": _remediation(node, reach[node_id])})

    mismatch = expected_digest is not None and expected_digest != digest
    withheld = bool(blocked or c11 or mismatch)
    report = {
        "schema_version": "1.0.0",
        "status": "snapshot_mismatch" if mismatch else "withheld" if withheld else "handoff",
        "scope": scope,
        "graph": {"path": graph_path.relative_to(root).as_posix(), "node_count": len(nodes), "graph_revision": revision,
                  "digest": digest, "expected_digest": expected_digest,
                  "digest_match": None if expected_digest is None else not mismatch},
        "c11": {"status": "fail" if c11 else "pass", "violation_count": len(c11), "violations": c11},
        "closure": rows,
        "blocked": blocked,
        "missing_sections": [{"graph_node_id": row["graph_node_id"], "missing_sections": row["missing_sections"]} for row in blocked],
        "handoff": [] if withheld else scope,
        "handoff_count": 0 if withheld else len(scope),
        "write_count": 0,
    }
    return (2 if mismatch else 1 if withheld else 0), report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo-root", required=True)
    p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--node", action="append", required=True, help="handoff target graph_node_id (repeatable)")
    p.add_argument("--expect-graph-digest", help="validate-readiness-binding.py の graph.digest。違えば handoff 0件で exit 2")
    a = p.parse_args(argv)
    code, report = guard(_context(a.repo_root, a.config), sorted(set(a.node)), a.expect_graph_digest)
    dump(report)
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
