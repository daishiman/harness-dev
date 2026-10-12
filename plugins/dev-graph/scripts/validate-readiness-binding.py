#!/usr/bin/env python3
# /// script
# name: validate-readiness-binding
# purpose: C04 の三 gate 照合。validate-system-plan.py の validated_digest、C02 が保存した registration/promotion/receipt の source_digest と package member の implementation_readiness/evaluation_status/source_digest、C11 で検証した graph の readiness digest を同じ digest に束ね、1件でもずれれば fail-closed にする。何も書かない。
# inputs: ["argv: --repo-root PATH --package-dir REL --receipt REL [--config PATH] [--system-planner-root PATH]"]
# outputs: ["stdout: JSON binding report {status, validated_digest, feature_package_id, parent_feature, system_plan, c11, graph, readiness_digest{c11, c02}, members[], violations[], write_count}", "exit: 0=pass / 1=binding violation (violations[]) / 2=usage, C24, system-dev-planner resolution or IO"]
# requires-python = ">=3.10"
# dependencies: [_common.py, resolve-repo-context.py, validate-graph-schema.py, register-package.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""C04 readiness binding.

requirements の handoff は、次の3つが同じ digest と同じ readiness を指すときだけ許される。

1. system-dev-planner の ``validate-system-plan.py`` が published package を PASS し、``validated_digest`` を返す。
2. C02 が保存した値: registration manifest と promotion receipt と C02 receipt の ``source_digest``、receipt が封じた
   登録時点の graph (``graph_revision_after`` と ``graph_digest_after``)、登録した package member の
   ``implementation_readiness/evaluation_status/confirmation_status/source_lineage.source_digest/
   confirmation_evidence.evaluated_digest``。
3. C11 (``validate-graph-schema.validate``) を通した graph の bytes。この bytes の package member から作る
   readiness view の digest を「C11 の readiness validation digest」とする。

readiness view は member ごとの ``graph_node_id/phase_ref/status/confirmation_status/evaluation_status/
implementation_readiness{status, missing_sections}/source_digest/evaluated_digest`` を phase 順に並べたもので、
digest は C02 (register-package.py) の ``_canonical_digest`` と同じ定義で取る。C02 側の view は registration
manifest の nodes から同じ形で作る (C02 は tracker_binding と linkage だけを解決して graph へ入れるので、view の
値は C02 が書いた値そのもの)。graph の revision が receipt の ``graph_revision_after`` と同じなら graph 全体の
canonical digest も ``graph_digest_after`` と一致しなければならない (revision を上げない編集を拒む)。revision が
登録より古い graph も拒む。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from _common import ContractError, contained, dump, load_json, run

SCRIPTS = Path(__file__).resolve().parent
RESOLVE = SCRIPTS / "resolve-repo-context.py"
PHASES = [f"P{i:02d}" for i in range(1, 14)]
READY = ("active", "confirmed", "pass", "complete")
RECEIPT_KEYS = ("status", "feature_package_id", "parent_feature", "source_digest", "node_ids",
                "graph_revision_after", "graph_digest_after")
MISSING = object()


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


def _get(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value


def readiness_view(node: dict[str, Any]) -> dict[str, Any]:
    """C02 と C11 で比べる値。欠けた key は ``<missing>`` として view に残し、digest を必ずずらす。"""
    def value(*keys: str) -> Any:
        found = _get(node, *keys)
        return "<missing>" if found is MISSING else found
    return {"graph_node_id": value("graph_node_id"), "phase_ref": value("phase_ref"), "status": value("status"),
            "confirmation_status": value("confirmation_status"), "evaluation_status": value("evaluation_status"),
            "implementation_readiness": {"status": value("implementation_readiness", "status"),
                                         "missing_sections": value("implementation_readiness", "missing_sections")},
            "source_digest": value("source_lineage", "source_digest"),
            "evaluated_digest": value("confirmation_evidence", "evaluated_digest")}


def _views(nodes: list[Any]) -> list[dict[str, Any]]:
    views = [readiness_view(node) for node in nodes if isinstance(node, dict)]
    return sorted(views, key=lambda item: (str(item["phase_ref"]), str(item["graph_node_id"])))


def _system_plan(sdp_root: Path, root: Path, config: str, package_dir: str) -> tuple[int, dict[str, Any]]:
    validator = sdp_root / "scripts" / "validate-system-plan.py"
    if not validator.is_file():
        raise ContractError(f"validate-system-plan.py is missing under {sdp_root}")
    cp = run([sys.executable, str(validator), "--repo-root", str(root), "--config", config, "--staging", package_dir], check=False)
    try:
        report = json.loads(cp.stdout)
    except ValueError:
        report = {"status": "fail", "violations": [(cp.stderr or cp.stdout).strip()], "validated_digest": None}
    return cp.returncode, report


def bind(args: argparse.Namespace) -> dict[str, Any]:
    ctx = _context(args.repo_root, args.config)
    root = Path(ctx["repo_root"]).resolve(strict=True)
    rp = _module("dev_graph_c04_register_package", "register-package.py")
    vgs = _module("dev_graph_c04_validate_graph_schema", "validate-graph-schema.py")
    package_dir = contained(root / args.package_dir, root)
    package_rel = package_dir.relative_to(root).as_posix()
    registration_path = contained(package_dir / "dev-graph-registration.json", root)
    registration = load_json(registration_path)
    receipt = load_json(contained(root / args.receipt, root))
    promotion_rel = registration.get("promotion_receipt")
    if not isinstance(promotion_rel, str):
        raise ContractError("registration manifest has no promotion_receipt path")
    promotion = load_json(contained(root / promotion_rel, root))
    sdp_root = Path(args.system_planner_root).resolve(strict=True) if args.system_planner_root else rp._default_system_root()

    violations: list[dict[str, Any]] = []

    def fail(code: str, detail: str, node: str | None = None) -> None:
        violations.append({"code": code, **({"node": node} if node else {}), "detail": detail})

    # gate 1: system-dev-planner の validator が published package を PASS し、validated_digest を出す。
    plan_exit, plan = _system_plan(sdp_root, root, args.config, package_rel)
    if plan_exit or plan.get("status") != "pass" or plan.get("violations"):
        fail("system_plan_failed", f"validate-system-plan exit {plan_exit}: {plan.get('violations')}")
    validated = plan.get("validated_digest")
    if not isinstance(validated, str):
        fail("validated_digest_missing", "validate-system-plan returned no validated_digest")

    # gate 2: C02 が保存した digest と identity が validated_digest と同じ package を指す。
    for key in RECEIPT_KEYS:
        if key not in receipt:
            fail("missing_required_key", f"C02 receipt lacks {key}")
    if receipt.get("status") != "registered":
        fail("receipt_not_registered", f"C02 receipt status is {receipt.get('status')!r}")
    if promotion.get("status") != "promoted":
        fail("promotion_not_promoted", f"promotion receipt status is {promotion.get('status')!r}")
    manifest = promotion.get("registration_manifest")
    if isinstance(manifest, str) and contained(root / manifest, root, must_exist=False) != registration_path:
        fail("promotion_manifest_mismatch", f"promotion receipt points to {manifest}, not {package_rel}/dev-graph-registration.json")
    if isinstance(validated, str):
        for code, label, value in (("registration_digest_mismatch", "registration.source_digest", registration.get("source_digest")),
                                   ("promotion_digest_mismatch", "promotion.published_digest", promotion.get("published_digest")),
                                   ("receipt_digest_mismatch", "receipt.source_digest", receipt.get("source_digest"))):
            if value != validated:
                fail(code, f"{label} {value} != validated_digest {validated}")
    package_id, parent = plan.get("feature_package_id"), plan.get("parent_feature")
    for label, source in (("registration", registration), ("receipt", receipt)):
        if (source.get("feature_package_id"), source.get("parent_feature")) != (package_id, parent):
            fail("package_identity_mismatch", f"{label} names {source.get('feature_package_id')}/{source.get('parent_feature')}, "
                                              f"validate-system-plan names {package_id}/{parent}")

    # gate 3: C11 が graph の bytes を検証し、その bytes の member から readiness digest を作る。
    graph_path = contained(Path(ctx["local_state_paths"]["graph"]), root)
    graph = json.loads(graph_path.read_bytes().decode("utf-8"))
    nodes = vgs.nodes_of(graph)
    c11 = vgs.validate(nodes, repo_root=vgs._repo_root_for(graph_path, str(root)))
    if c11:
        fail("c11_failed", f"C11 reports {len(c11)} violation(s)")
    revision = graph.get("graph_revision") if isinstance(graph, dict) else None
    graph_digest = rp._canonical_digest(graph)
    registered_revision, registered_digest = receipt.get("graph_revision_after"), receipt.get("graph_digest_after")
    if not isinstance(revision, int) or not isinstance(registered_revision, int) or revision < registered_revision:
        relation = "older_than_registration"
        fail("graph_older_than_registration", f"graph_revision {revision} precedes the C02 registration revision {registered_revision}")
    elif revision == registered_revision:
        relation = "registered_snapshot"
        if graph_digest != registered_digest:
            fail("graph_snapshot_mismatch", f"graph at revision {revision} is not the snapshot C02 registered "
                                            f"({graph_digest} != {registered_digest})")
    else:
        relation = "later_revision"

    members = [node for node in nodes if isinstance(node, dict) and node.get("feature_package_id") == receipt.get("feature_package_id")]
    member_views = _views(members)
    if [view["phase_ref"] for view in member_views] != PHASES or \
            sorted(str(view["graph_node_id"]) for view in member_views) != sorted(map(str, receipt.get("node_ids") or [])):
        fail("members_not_exact_13", f"graph holds {len(members)} member(s) of {receipt.get('feature_package_id')}; "
                                     f"phases {[view['phase_ref'] for view in member_views]} must be exactly P01..P13 with the receipt node_ids")
    expected_hex = validated.removeprefix("sha256:") if isinstance(validated, str) else None
    for node in members:
        node_id = str(node.get("graph_node_id"))
        view = readiness_view(node)
        absent = [key for key in ("phase_ref", "status", "confirmation_status", "evaluation_status")
                  if view[key] == "<missing>"]
        absent += [f"implementation_readiness.{key}" for key, item in view["implementation_readiness"].items() if item == "<missing>"]
        absent += [label for label, key in (("source_lineage.source_digest", "source_digest"),
                                            ("confirmation_evidence.evaluated_digest", "evaluated_digest")) if view[key] == "<missing>"]
        for key in absent:
            fail("missing_required_key", f"{node_id} lacks {key}", node_id)
        if node.get("parent_feature") != parent:
            fail("parent_feature_mismatch", f"parent_feature {node.get('parent_feature')} != {parent}", node_id)
        if expected_hex is not None and view["source_digest"] != expected_hex:
            fail("stale_source_digest", f"source_lineage.source_digest {view['source_digest']} != {expected_hex}", node_id)
        if expected_hex is not None and view["evaluated_digest"] != expected_hex:
            fail("stale_evaluated_digest", f"confirmation_evidence.evaluated_digest {view['evaluated_digest']} != {expected_hex}", node_id)
        state = (view["status"], view["confirmation_status"], view["evaluation_status"], view["implementation_readiness"]["status"])
        if state != READY or view["implementation_readiness"]["missing_sections"] != []:
            fail("node_not_ready", f"status/confirmation/evaluation/readiness {list(state)} must be {list(READY)} with no "
                                   f"missing_sections; missing_sections {view['implementation_readiness']['missing_sections']}", node_id)

    saved_views = _views(registration.get("nodes") or [])
    c11_digest, c02_digest = rp._canonical_digest(member_views), rp._canonical_digest(saved_views)
    if c11_digest != c02_digest:
        saved = {str(view["graph_node_id"]): view for view in saved_views}
        drifted = sorted(str(view["graph_node_id"]) for view in member_views if saved.get(str(view["graph_node_id"])) != view)
        drifted += sorted(set(saved) - {str(view["graph_node_id"]) for view in member_views})
        fail("readiness_digest_mismatch", f"C11 readiness digest {c11_digest} != C02 saved readiness digest {c02_digest}; "
                                          f"drifted nodes {drifted}")

    return {
        "schema_version": "1.0.0",
        "status": "fail" if violations else "pass",
        "validated_digest": validated,
        "feature_package_id": package_id,
        "parent_feature": parent,
        "system_plan": {"exit": plan_exit, "status": plan.get("status"), "violations": plan.get("violations")},
        "c11": {"status": "fail" if c11 else "pass", "violation_count": len(c11), "violations": c11},
        "graph": {"path": graph_path.relative_to(root).as_posix(), "graph_revision": revision, "digest": graph_digest,
                  "registered_revision": registered_revision, "registered_digest": registered_digest, "relation": relation},
        "readiness_digest": {"c11": c11_digest, "c02": c02_digest},
        "members": member_views,
        "violations": violations,
        "write_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo-root", required=True)
    p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--package-dir", required=True, help="repository-relative published feature package directory")
    p.add_argument("--receipt", required=True, help="repository-relative C02 registration receipt")
    p.add_argument("--system-planner-root")
    report = bind(p.parse_args(argv))
    dump(report)
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
