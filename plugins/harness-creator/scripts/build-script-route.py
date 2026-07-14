#!/usr/bin/env python3
# /// script
# name: build-script-route
# purpose: Execute script routes from handoff-run-plugin-dev-plan.json by creating or verifying the target Python script and writing a route-build-report.
# inputs:
#   - argv: --handoff <handoff-json> --route-id <Cxx> [--reports-dir DIR] [--dry-run]
# outputs:
#   - stdout: JSON summary
#   - stderr: validation/build errors
#   - exit: 0=executor completed / 1=validation or build failure / 2=usage or JSON error
# contexts: [C, E]
# network: false
# write-scope: repo script build_target + eval-log/<slug>/build/route-<id>.json
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Build executor for script routes in plugin-dev-planner handoff files.

This is intentionally narrow: it only handles routes whose build_kind is
``script`` and whose builder is ``plugin-scaffold`` or ``parent-skill-build``.
It does not try to synthesize domain logic. For new files it writes a minimal
portable Python scaffold with route metadata; for existing files it leaves the
file untouched and records the route as verified. In both cases it writes a
route-build-report so downstream routes can consume the result. When the
handoff carries a readable task_graph_ref, the report also records
covered_task_ids (task-graph node ids whose entity_ref equals the route id,
sorted ascending) so route completion can be traced back to graph nodes; if
the graph is absent or unreadable the field is omitted (backward compatible).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_BUILDERS = {"plugin-scaffold", "parent-skill-build"}
REPORT_SCHEMA_VERSION = "1.0.0"


def _resolve_handoff_path(path: Path) -> Path:
    if path.is_file():
        return path
    if not path.is_absolute():
        candidate = TOOL_ROOT / path
        if candidate.is_file():
            return candidate
    return path


def _repo_root(handoff_path: Path) -> Path:
    resolved = handoff_path.resolve()
    if "plugin-plans" in resolved.parts:
        idx = resolved.parts.index("plugin-plans")
        return Path(*resolved.parts[:idx]) if idx else Path("/")
    return TOOL_ROOT


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root is not an object")
    return data


def _route_by_id(handoff: dict, route_id: str) -> dict:
    for route in handoff.get("routes", []):
        if isinstance(route, dict) and route.get("id") == route_id:
            return route
    raise ValueError(f"route not found: {route_id}")


def _reports_dir(repo_root: Path, slug: str, override: str | None) -> Path:
    return Path(override) if override else repo_root / "eval-log" / slug / "build"


def _report_rel(slug: str, route_id: str) -> str:
    return f"eval-log/{slug}/build/route-{route_id}.json"


def _report_rel_dyn(reports_dir: Path, repo_root: Path, route_id: str) -> str:
    """実際の reports_dir から repo-root 相対の report パスを導出する。

    cycle_id 付き handoff では reports_dir が eval-log/<slug>/build/<cycle-id>/ へ
    分離されるため、inputs_consumed には flat 規約 (_report_rel) でなく実在場所を
    宣言する (flat 既定では同一 = 後方互換・validator の report_rel と対)。
    """
    p = reports_dir / f"route-{route_id}.json"
    try:
        rel = p.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel = p
    return rel.as_posix()


def _preflight_parity(handoff_path: Path) -> list[str]:
    parity = _load_module(TOOL_ROOT / "plugins/harness-creator/scripts/check-route-component-parity.py", "route_parity")
    data = _load_json(handoff_path)
    inv_path = parity.resolve_inventory(handoff_path.resolve(), data, None)
    inv = _load_json(inv_path)
    return parity.check_parity(data.get("routes"), inv.get("components"))


def _dependency_inputs(handoff: dict, route: dict, reports_dir: Path, slug: str, repo_root: Path) -> tuple[list[str], list[str]]:
    validator = _load_module(
        TOOL_ROOT / "plugins/harness-creator/skills/run-build-skill/scripts/validate-route-build-reports.py",
        "route_report_validator",
    )
    findings: list[str] = []
    consumed: list[str] = []
    route_ids = {r.get("id") for r in handoff.get("routes", []) if isinstance(r, dict)}
    for dep_id in route.get("depends_on", []) or []:
        if dep_id not in route_ids:
            findings.append(f"dependency route is not in handoff: {dep_id}")
            continue
        dep_findings = validator.validate_route(handoff, reports_dir, dep_id, repo_root)
        if dep_findings:
            findings.extend(f"dependency {dep_id}: {f}" for f in dep_findings)
            continue
        dep_report_path = reports_dir / f"route-{dep_id}.json"
        dep_report = _load_json(dep_report_path)
        dep_status = dep_report.get("status")
        if dep_status != "success":
            findings.append(f"dependency {dep_id}: status={dep_status}")
        consumed.append(_report_rel_dyn(reports_dir, repo_root, dep_id))
    return consumed, findings


def _target_path(route: dict, repo_root: Path) -> Path:
    raw = str(route.get("build_target", "")).strip()
    if not raw:
        raise ValueError("route.build_target is empty")
    path = Path(raw)
    if path.is_absolute():
        raise ValueError("route.build_target must be repo-relative")
    if ".." in path.parts:
        raise ValueError("route.build_target must not contain '..'")
    if path.parts[:1] != ("plugins",):
        raise ValueError("route.build_target must start with plugins/")
    if path.suffix != ".py":
        raise ValueError("script route build_target must end with .py")
    return repo_root / path


def _route_map(handoff: dict) -> dict[str, dict]:
    return {str(r.get("id")): r for r in handoff.get("routes", []) if isinstance(r, dict)}


def _covered_task_ids(handoff: dict, handoff_path: Path, route_id: str) -> list[str] | None:
    """task-graph.json から entity_ref == route_id の node id 一覧 (id 昇順) を引く。

    task_graph_ref.path は plan_dir (絶対のときのみ) か handoff の所在ディレクトリ基準で解決する
    (check-route-component-parity の inventory 解決と同方針)。graph 不在/読込不能は None を返し
    report へ field を書かない (task_graph_ref を持たない旧 handoff への後方互換)。
    """
    tgr = handoff.get("task_graph_ref")
    if not isinstance(tgr, dict):
        return None
    rel = str(tgr.get("path", "")).strip()
    if not rel:
        return None
    plan_dir_raw = str(handoff.get("plan_dir", "")).strip()
    base = Path(plan_dir_raw) if plan_dir_raw and Path(plan_dir_raw).is_absolute() else handoff_path.parent
    try:
        graph = json.loads((base / rel).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(graph, dict):
        return None
    return sorted(
        str(n["id"]) for n in graph.get("nodes", [])
        if isinstance(n, dict) and n.get("id") and n.get("entity_ref") == route_id
    )


def _posix_relative(child: str, parent: str) -> str | None:
    child_path = Path(child)
    parent_path = Path(parent)
    try:
        return child_path.relative_to(parent_path).as_posix()
    except ValueError:
        return None


def _validate_script_contract(handoff: dict, route: dict, repo_root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    parent_scaffolds: list[str] = []
    if route.get("builder_status") != "contract-only":
        errors.append("script route builder_status must be contract-only")
    gap_ref = str(route.get("gap_ref", "")).strip()
    issue_ids = {str(i.get("id")) for i in handoff.get("open_issues", []) if isinstance(i, dict)}
    if not gap_ref:
        errors.append("script route gap_ref is required")
    elif issue_ids and gap_ref not in issue_ids:
        errors.append(f"script route gap_ref is not in open_issues: {gap_ref}")

    args = route.get("build_args")
    if not isinstance(args, dict):
        return errors + ["script route build_args must be an object"], parent_scaffolds
    script_path = str(args.get("script_path", "")).strip()
    if not script_path:
        errors.append("script route build_args.script_path is required")
    if Path(script_path).is_absolute() or ".." in Path(script_path).parts:
        errors.append("script route build_args.script_path must be relative and must not contain '..'")

    build_target = str(route.get("build_target", "")).strip()
    builder = route.get("builder")
    if script_path and build_target:
        if builder == "plugin-scaffold":
            slug = str(handoff.get("target_plugin_slug") or "").strip()
            expected = f"plugins/{slug}/{script_path}" if slug else ""
            if expected and build_target != expected:
                errors.append(f"plugin-scaffold script_path does not match build_target: expected {expected}")
        elif builder == "parent-skill-build":
            parent_id = str(route.get("requires_parent_scaffold", "")).strip()
            if not parent_id:
                errors.append("parent-skill-build script route requires requires_parent_scaffold")
            routes = _route_map(handoff)
            parent = routes.get(parent_id)
            if not parent:
                errors.append(f"requires_parent_scaffold route not found: {parent_id}")
            else:
                if parent.get("component_kind") != "skill":
                    errors.append(f"requires_parent_scaffold must point to a skill route: {parent_id}")
                parent_target = str(parent.get("build_target", "")).rstrip("/")
                rel = _posix_relative(build_target, parent_target)
                if rel != script_path:
                    errors.append(
                        f"parent-skill-build script_path does not match build_target under parent: expected {parent_target}/{script_path}"
                    )
                parent_skill = str(args.get("parent_skill", "")).strip()
                if parent_skill and parent_skill != str(parent.get("name", "")).strip():
                    errors.append(f"build_args.parent_skill does not match parent route name: {parent_skill} != {parent.get('name')}")
                parent_dir = repo_root / parent_target
                if not parent_dir.exists():
                    parent_scaffolds.append(parent_target)
    return errors, parent_scaffolds


def _scaffold_text(route: dict, handoff_path: Path) -> str:
    route_id = route.get("id", "")
    name = route.get("name", "")
    summary = f"Generated scaffold for script route {route_id} ({name})."
    return (
        "#!/usr/bin/env python3\n"
        "# /// script\n"
        f"# name: {name}\n"
        f"# purpose: {summary}\n"
        f"# source-handoff: {handoff_path.as_posix()}\n"
        f"# source-route-id: {route_id}\n"
        "# network: false\n"
        "# dependencies: []\n"
        "# requires-python: \">=3.10\"\n"
        "# ///\n"
        "from __future__ import annotations\n\n"
        "import json\n"
        "import sys\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    argv = list(sys.argv[1:] if argv is None else argv)\n"
        "    payload = {\"ok\": True, \"argv\": argv}\n"
        "    print(json.dumps(payload, ensure_ascii=False))\n"
        "    return 0\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    raise SystemExit(main())\n"
    )


def _write_report(
    *,
    reports_dir: Path,
    slug: str,
    route: dict,
    status: str,
    summary: str,
    deviations: list[str],
    evidence: list[str],
    inputs_consumed: list[str],
    handover: str | None,
    skip_reason: str | None = None,
    covered_task_ids: list[str] | None = None,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "plugin_slug": slug,
        "route_id": route["id"],
        "component_kind": route["component_kind"],
        "name": route["name"],
        "builder": route["builder"],
        "build_target": route["build_target"],
        "status": status,
        "summary": summary,
        "deviations": deviations,
        "evidence": evidence,
        "inputs_consumed": inputs_consumed,
        "handover": handover,
    }
    if skip_reason:
        report["skip_reason"] = skip_reason
    if covered_task_ids is not None:
        report["covered_task_ids"] = covered_task_ids
    out = reports_dir / f"route-{route['id']}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def build_script_route(
    *,
    handoff_path: Path,
    route_id: str,
    reports_dir_arg: str | None = None,
    dry_run: bool = False,
) -> tuple[int, dict]:
    handoff_path = _resolve_handoff_path(handoff_path)
    parity_errors = _preflight_parity(handoff_path)
    if parity_errors:
        return 1, {"ok": False, "errors": parity_errors}

    handoff = _load_json(handoff_path)
    repo_root = _repo_root(handoff_path)
    slug = str(handoff.get("target_plugin_slug") or "").strip()
    route = _route_by_id(handoff, route_id)
    errors: list[str] = []
    if route.get("component_kind") != "script" or route.get("build_kind") != "script":
        errors.append("route is not a script route")
    if route.get("builder") not in SCRIPT_BUILDERS:
        errors.append(f"script route builder must be one of {sorted(SCRIPT_BUILDERS)}")
    contract_errors, parent_scaffolds = _validate_script_contract(handoff, route, repo_root)
    errors.extend(contract_errors)
    if errors:
        return 1, {"ok": False, "route_id": route_id, "errors": errors}

    reports_dir = _reports_dir(repo_root, slug, reports_dir_arg)
    inputs_consumed, dep_errors = _dependency_inputs(handoff, route, reports_dir, slug, repo_root)
    if dep_errors:
        return 1, {"ok": False, "route_id": route_id, "errors": dep_errors}

    target = _target_path(route, repo_root)
    target_rel = target.relative_to(repo_root).as_posix()
    deviations: list[str] = []
    for parent_target in parent_scaffolds:
        if dry_run:
            deviations.append(f"would create parent skill scaffold directory: {parent_target}")
        else:
            (repo_root / parent_target).mkdir(parents=True, exist_ok=True)
            deviations.append(f"created parent skill scaffold directory: {parent_target}")
    evidence: list[str] = []
    status = "success"
    skip_reason = None
    if target.exists():
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        summary = f"既存 script route ファイルの存在を確認した: {target_rel}"
        evidence.append(f"{target_rel} exists sha256={digest}")
    else:
        status = "skipped"
        skip_reason = "minimal scaffold generated; domain implementation still required before dependent routes may proceed"
        deviations.append(skip_reason)
        evidence.append(f"{target_rel} created")
        summary = f"script route の最小 scaffold を新規作成した: {target_rel}"
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_scaffold_text(route, handoff_path), encoding="utf-8")

    if dry_run:
        return 0, {
            "ok": True,
            "dry_run": True,
            "route_id": route_id,
            "repo_root": repo_root.as_posix(),
            "build_target": target_rel,
            "would_create": not target.exists(),
            "would_report_status": status,
        }

    report_path = _write_report(
        reports_dir=reports_dir,
        slug=slug,
        route=route,
        status=status,
        summary=summary,
        deviations=deviations,
        evidence=evidence,
        inputs_consumed=inputs_consumed,
        handover=f"script route {route_id} is available at {target_rel}",
        skip_reason=skip_reason,
        covered_task_ids=_covered_task_ids(handoff, handoff_path.resolve(), route_id),
    )

    validator = _load_module(
        TOOL_ROOT / "plugins/harness-creator/skills/run-build-skill/scripts/validate-route-build-reports.py",
        "route_report_validator_after",
    )
    findings = validator.validate_route(handoff, reports_dir, route_id, repo_root)
    if findings:
        return 1, {"ok": False, "route_id": route_id, "report": str(report_path), "errors": findings}
    return 0, {"ok": True, "route_id": route_id, "status": status, "build_target": target_rel, "report": str(report_path)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a script route from handoff-run-plugin-dev-plan.json")
    ap.add_argument("--handoff", required=True)
    ap.add_argument("--route-id", required=True)
    ap.add_argument("--reports-dir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    handoff_path = _resolve_handoff_path(Path(args.handoff))
    if not handoff_path.is_file():
        sys.stderr.write(f"handoff not found: {handoff_path}\n")
        return 2
    try:
        rc, payload = build_script_route(
            handoff_path=handoff_path,
            route_id=args.route_id,
            reports_dir_arg=args.reports_dir,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
