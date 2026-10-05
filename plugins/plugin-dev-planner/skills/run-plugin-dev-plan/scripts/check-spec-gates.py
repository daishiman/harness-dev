#!/usr/bin/env python3
# /// script
# name: check-spec-gates
# purpose: component-inventory.json の各 component の quality_gates(p0_lint網羅/build_trace/elegant_review C1-C4/content_review verdict/evaluator>=80,high0) と harness_coverage(min>=80/kind_pass) を specfm で値域検証し、index.plugin_meta の plugin 階層規律 (Claude/Codex 両 platform への install 契約を含む) を値域検証する決定論ゲート。
# inputs:
#   - argv: <md ...> | --specs-dir DIR [--inventory FILE]
# outputs:
#   - stdout: OK サマリ
#   - stderr: component gates / harness / plugin_meta violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""inventory component の quality_gates/harness_coverage + index.plugin_meta を値域検証する。

per-phase 転換 (凍結契約 §4/§8): 旧 C*.md frontmatter の quality_gates/harness は
component-inventory.json の components[] へ載せ替わったため、値域検証を inventory 単位へ移す
(specfm.validate_component_quality_gates + validate_component_harness_coverage)。index の
plugin 階層規律 (plugin_meta) に加え、install 義務が既存 graph producer の P13 実行leafへ到達することを検査する。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def check_plugin_meta(pm: dict) -> list[str]:
    """index.plugin_meta の plugin 階層規律を値域検証する (F3/F4/F6 等・現状維持)。"""
    errs: list[str] = []
    manifest = pm.get("manifest")
    if not isinstance(manifest, dict):
        errs.append("plugin_meta.manifest が dict でない (.claude-plugin/plugin.json 契約必須)")
    else:
        if manifest.get("required") is not True:
            errs.append("manifest.required は true であること")
        if str(manifest.get("path", "")).strip() != ".claude-plugin/plugin.json":
            errs.append("manifest.path は .claude-plugin/plugin.json であること")
        if manifest.get("name_matches_folder") is not True:
            errs.append("manifest.name_matches_folder は true であること")
        if manifest.get("no_unresolved_placeholders") is not True:
            errs.append("manifest.no_unresolved_placeholders は true であること")
        if manifest.get("validate_plugin") is not True:
            errs.append("manifest.validate_plugin は true であること")

    marketplace = pm.get("marketplace")
    if not isinstance(marketplace, dict):
        errs.append("plugin_meta.marketplace が dict でない (marketplace policy 契約必須)")
    else:
        default_personal = marketplace.get("default_personal")
        if not isinstance(default_personal, bool):
            errs.append(f"marketplace.default_personal は bool であること (現値 {default_personal!r})")
        policy = marketplace.get("policy")
        if not isinstance(policy, dict):
            errs.append("marketplace.policy が dict でない")
        else:
            if policy.get("installation") not in {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}:
                errs.append(f"marketplace.policy.installation の値域違反: {policy.get('installation')!r}")
            if policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
                errs.append(f"marketplace.policy.authentication の値域違反: {policy.get('authentication')!r}")
            if not str(policy.get("category", "")).strip():
                errs.append("marketplace.policy.category が空")
        if marketplace.get("cachebuster_for_update") is not True:
            errs.append("marketplace.cachebuster_for_update は true であること")

    dist = pm.get("distribution")
    if not isinstance(dist, dict):
        errs.append("plugin_meta.distribution が dict でない (配布判定 F3 必須)")
    else:
        d = dist.get("distributable")
        if not isinstance(d, bool):
            errs.append(f"distribution.distributable は bool であること (現値 {d!r})")
        else:
            bundles = dist.get("bundles") or []
            mk = dist.get("marketplace")
            if d is False:
                if bundles:
                    errs.append(f"distributable:false なのに bundles 非空 {bundles!r} (非配布整合違反)")
                if mk not in (None, False):
                    errs.append(f"distributable:false なのに marketplace={mk!r} (false/不在であること)")
            else:
                if not bundles:
                    errs.append("distributable:true なのに bundles が空 (最低1件の bundle 登録が必要)")
    # core: 全 plugin で必須の非空 dict
    for key in specfm.PLUGIN_META_CORE_DICTS:
        v = pm.get(key)
        if not isinstance(v, dict) or not v:
            errs.append(f"plugin_meta.{key} が非空 dict でない (plugin 階層コア規律 {key} 未充足)")
    # conditional: 該当時は規律 dict、非該当は {applicable: false, reason: <非空>} で明示 N/A (A7 整合)
    for key in specfm.PLUGIN_META_CONDITIONAL_DICTS:
        v = pm.get(key)
        if not isinstance(v, dict) or not v:
            errs.append(
                f"plugin_meta.{key} が非空 dict でない (該当時は規律 dict、非該当は {{applicable: false, reason}} を明示)"
            )
        elif specfm.is_plugin_meta_na(v):
            reason = v.get("reason")
            if not (isinstance(reason, str) and reason.strip()):
                errs.append(f"plugin_meta.{key} が applicable:false だが reason が空 (N/A の根拠を明示すること)")

    # feedback_deploy 値域 (core 昇格・B4/B5): opt-out は enabled:false+reason の明示例外のみ。
    # 採用時は deploy=run-skill-feedback / notion_sink.config_key 非空 (DB キー宣言・ID は設置先
    # .notion-config.json 供給の二層) / portability∈{repo-bundled,vendored}、かつ配布プラグイン
    # (distributable:true) は単独 install 携帯性のため vendored を強制する (D6 symlink 禁止と同根)。
    fd = pm.get("feedback_deploy")
    if isinstance(fd, dict) and fd:
        if specfm.is_plugin_meta_na(fd):
            errs.append(
                "plugin_meta.feedback_deploy は core 規律 (applicable:false 形は不可)。"
                "opt-out は {enabled: false, reason: <非空>} で明示すること"
            )
        elif fd.get("enabled") is False:
            reason = fd.get("reason")
            if not (isinstance(reason, str) and reason.strip()):
                errs.append("feedback_deploy.enabled:false (opt-out) は reason 非空必須 (明示例外の根拠)")
        else:
            if str(fd.get("deploy", "")).strip() != "run-skill-feedback":
                errs.append(f"feedback_deploy.deploy は 'run-skill-feedback' であること (現値 {fd.get('deploy')!r})")
            ns = fd.get("notion_sink")
            if not isinstance(ns, dict) or not str(ns.get("config_key", "")).strip():
                errs.append("feedback_deploy.notion_sink.config_key が非空でない (Notion 受け皿 DB のキーを宣言)")
            else:
                if not str(ns.get("schema_ref", "")).strip():
                    errs.append("feedback_deploy.notion_sink.schema_ref が非空でない (受け皿 DB schema のパス参照)")
                if str(ns.get("resolution", "")).strip() != "notion_config":
                    errs.append(
                        "feedback_deploy.notion_sink.resolution は 'notion_config' であること"
                        f" (現値 {ns.get('resolution')!r}・解決器の名前参照・再実装禁止)"
                    )
            port = fd.get("portability")
            if port not in ("repo-bundled", "vendored"):
                errs.append(f"feedback_deploy.portability は repo-bundled|vendored のみ (現値 {port!r})")
            elif isinstance(dist, dict) and dist.get("distributable") is True and port != "vendored":
                errs.append("distributable:true は feedback_deploy.portability=vendored を要求 (単独 install 携帯性)")
    inst = pm.get("install")
    if isinstance(inst, dict) and inst:
        errs.extend(check_install(inst))
    return errs


def check_install(inst: dict) -> list[str]:
    """plugin_meta.install (Claude/Codex 両 platform への install 契約) を値域検証する。

    plan が「作れば install できる」と黙って仮定しないよう、登録先・strict 検証・release 順序・
    隔離/実環境 install 検証を宣言させる。opt-out は platform 除外と実環境 install 省略だけで、
    どちらも理由の明示を要する (feedback_deploy の enabled:false+reason と同型)。
    """
    errs: list[str] = []
    platforms = inst.get("platforms")
    if not isinstance(platforms, list) or not all(isinstance(x, str) for x in platforms):
        errs.append(f"install.platforms は platform 名の list であること (現値 {platforms!r})")
        platforms = []
    unknown = sorted(set(platforms) - set(specfm.INSTALL_PLATFORMS))
    if unknown:
        errs.append(f"install.platforms に未知の platform {unknown!r} (許容 {list(specfm.INSTALL_PLATFORMS)!r})")
    for req in specfm.INSTALL_REQUIRED_PLATFORMS:
        if req not in platforms:
            errs.append(f"install.platforms は {req} を含むこと (manifest 正本の platform は除外不可)")
    excluded = inst.get("excluded_platforms") or {}
    if not isinstance(excluded, dict):
        errs.append("install.excluded_platforms は {platform: 除外理由} の dict であること")
        excluded = {}
    for plat in specfm.INSTALL_PLATFORMS:
        if plat in platforms:
            if plat in excluded:
                errs.append(f"install.platforms と excluded_platforms の両方に {plat} がある (どちらか一方に決める)")
            continue
        if plat in specfm.INSTALL_REQUIRED_PLATFORMS:
            continue
        reason = excluded.get(plat)
        if not (isinstance(reason, str) and reason.strip()):
            errs.append(
                f"install.platforms に {plat} が無いのに excluded_platforms.{plat} の理由が無い"
                " (両 platform への install が既定。外すなら理由を明示する)"
            )

    if str(inst.get("codex_manifest", "")).strip() != specfm.INSTALL_CODEX_MANIFEST:
        errs.append(
            f"install.codex_manifest は {specfm.INSTALL_CODEX_MANIFEST} であること"
            f" (現値 {inst.get('codex_manifest')!r}・sync-plugin-platforms.py が .claude-plugin から投影する)"
        )
    registries = inst.get("registries")
    if not isinstance(registries, list):
        errs.append(f"install.registries は登録先の list であること (現値 {registries!r})")
        registries = []
    # Runtime opt-out never removes either product package/catalog.
    for plat in specfm.INSTALL_PLATFORMS:
        reg = specfm.INSTALL_REGISTRY_BY_PLATFORM.get(plat)
        if reg and reg not in registries:
            errs.append(f"install.registries に {reg} が無い ({plat} へ install する経路の登録先)")

    if inst.get("strict_validate") is not True:
        errs.append(
            "install.strict_validate は true であること (claude plugin validate --strict を通す。"
            'hook command の plugin root は "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/..." とクォートする)'
        )
    if str(inst.get("release", "")).strip() != specfm.INSTALL_RELEASE_ORDER:
        errs.append(
            f"install.release は {specfm.INSTALL_RELEASE_ORDER!r} であること"
            f" (現値 {inst.get('release')!r}・CHANGELOG を先に書き build-plugin-release.py --only <slug> で bump する)"
        )

    verify = inst.get("verify")
    if not isinstance(verify, dict):
        errs.append("install.verify が dict でない (隔離 install と実環境 install の検証宣言が必須)")
    else:
        if verify.get("isolated") is not True:
            errs.append(
                "install.verify.isolated は true であること (install-local-plugins.py を"
                " --claude-config-dir/--codex-home 付きで回し verified=true を確認する)"
            )
        live = verify.get("live")
        if live is False:
            reason = verify.get("live_skip_reason")
            if not (isinstance(reason, str) and reason.strip()):
                errs.append("install.verify.live:false は live_skip_reason 非空必須 (実環境 install を省く根拠)")
        elif live is not True:
            errs.append(
                f"install.verify.live は bool であること (現値 {live!r}・既定 true。autoUpdate は"
                " 新規 plugin を入れないため install-local-plugins.py --plugin <slug> で実環境へ入れる)"
            )
    return errs


def check_inventory(inventory_path: Path) -> tuple[list[str], str | None]:
    """component-inventory.json の各 component の gates/harness を値域検証する (errors, fatal)。"""
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], f"component-inventory JSON parse error: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return [], "component-inventory.json に components[] list が無い"
    errors: list[str] = []
    for comp in data["components"]:
        if not isinstance(comp, dict):
            errors.append("inventory: component が object でない")
            continue
        cid = str(comp.get("id", "")).strip() or "?"
        for e in specfm.validate_component_quality_gates(comp):
            errors.append(f"inventory[{cid}]: {e}")
        for e in specfm.validate_component_harness_coverage(comp):
            errors.append(f"inventory[{cid}]: {e}")
    return errors, None


def resolve_install_slug(plan_dir: Path) -> tuple[str | None, dict, list[str]]:
    """install 義務の target_plugin_slug を解決する (slug, handoff, errors)。

    slug の正本は R1 が固定する goal-spec で、handoff はその派生。goal-spec を優先し、
    handoff にも slug があれば一致を要求する (handoff の生成順序への暗黙依存と別経路の drift を塞ぐ)。
    goal-spec に slug が無い旧形 plan だけ handoff へ fallback する。
    """
    loaded: dict[str, dict] = {}
    for name in ("goal-spec.json", "handoff-run-plugin-dev-plan.json"):
        path = plan_dir / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return None, {}, [f"install 義務の target_plugin_slug を {name} から読めない: {exc}"]
        loaded[name] = data if isinstance(data, dict) else {}
    handoff = loaded.get("handoff-run-plugin-dev-plan.json", {})
    goal_slug = loaded.get("goal-spec.json", {}).get("target_plugin_slug")
    handoff_slug = handoff.get("target_plugin_slug")
    if goal_slug is not None and handoff_slug is not None and goal_slug != handoff_slug:
        return None, handoff, [
            f"target_plugin_slug が goal-spec ({goal_slug!r}) と handoff ({handoff_slug!r}) で不一致"
            " (goal-spec が正本。handoff を goal-spec から再生成する)"
        ]
    slug = goal_slug if goal_slug is not None else handoff_slug
    if not isinstance(slug, str):
        return None, handoff, ["install 義務の target_plugin_slug を goal-spec からも handoff からも解決できない"]
    return slug, handoff, []


def check_install_release(plan_dir: Path, inst: dict) -> list[str]:
    """Require canonical P13 install claims in the existing producer's execution leaves."""
    phase = plan_dir / "phase-13-release.md"
    if not phase.is_file():
        return ["install 契約の実行義務を持つ phase-13-release.md が無い"]
    slug, data, slug_errors = resolve_install_slug(plan_dir)
    if slug_errors:
        return slug_errors
    try:
        obligations = specfm.install_release_obligations(inst, slug)
    except ValueError as exc:
        return [f"install 義務の target_plugin_slug が不正: {exc}"]
    try:
        # Ask the existing producer what the consumer actually executes. In fixed
        # shape this is P13's checklist; target shape consumes task-specs instead.
        loader = importlib.util.spec_from_file_location(
            "install_obligation_producer", Path(__file__).with_name("derive-task-graph.py")
        )
        producer = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(producer)
        graph = producer.derive(plan_dir)
    except (OSError, ValueError) as exc:
        return [f"install release obligations を実行 graph へ導出できない: {exc}"]
    leaves = [
        node for node in graph["nodes"]
        if node.get("phase_ref") == "P13"
        and node.get("execution_kind") in {"verification-claim", "direct-task"}
    ]
    clauses = {node.get("acceptance_criterion") for node in leaves}
    errors = [
        f"P13 install obligation {key} が欠落または契約と不一致 (render-spec-skeleton.py --phase 13 --plugin-slug {slug} で正本から生成): {clause}"
        for key, clause in obligations.items() if clause not in clauses
    ]
    # install 義務は plugin 単位。fixed-13-phase は P13 の entities_covered ごとに条項を複製するため、
    # component に帰属した leaf は N 重の実行と route_ref の誤帰属になる。集合包含では見逃すので拒否する。
    attributed = sorted({
        key for key, clause in obligations.items()
        for node in leaves
        if node.get("acceptance_criterion") == clause and node.get("entity_ref") is not None
    })
    errors.extend(
        f"P13 install obligation {key} が component に帰属している (plugin 単位の義務。"
        "P13 の entities_covered は [] にし、task-spec には entity_ref を付けない)"
        for key in attributed
    )
    # Generation may not have emitted the artifact yet. When it exists, also
    # check the handoff's consumer input so a stale graph cannot hide new claims.
    graph_ref = data.get("task_graph_ref")
    graph_rel = graph_ref.get("path", "task-graph.json") if isinstance(graph_ref, dict) else "task-graph.json"
    if not isinstance(graph_rel, str) or not graph_rel.strip():
        return errors + ["install 義務の handoff.task_graph_ref.path が非空stringでない"]
    graph_path = plan_dir / graph_rel
    if graph_path.is_file():
        try:
            stored = json.loads(graph_path.read_text(encoding="utf-8"))
            if not isinstance(stored, dict) or not isinstance(stored.get("nodes"), list):
                raise ValueError("task graph must contain nodes[]")
            stored_clauses = set()
            for node in stored["nodes"]:
                if not isinstance(node, dict) or node.get("phase_ref") != "P13":
                    continue
                kind = node.get("execution_kind")
                if kind not in (None, "verification-claim", "direct-task"):
                    continue
                clause = node.get("acceptance_criterion")
                # Legacy fixed graphs carry the claim in title until migration.
                if kind is None:
                    clause = node.get("title")
                if isinstance(clause, str):
                    stored_clauses.add(clause)
            errors.extend(
                f"task-graph install obligation {key} が欠落または古い (derive-task-graph.py で再生成): {graph_path}"
                for key, clause in obligations.items() if clause not in stored_clauses
            )
        except (OSError, ValueError) as exc:
            errors.append(f"install 義務の task graph を読めない: {exc}")
    return errors


def collect_md(specs_dir: Path) -> list[Path]:
    return sorted(specs_dir.glob("*.md"))


def run(md_paths: list[Path], inventory_path: Path | None) -> tuple[int, list[str]]:
    errors: list[str] = []
    for p in md_paths:
        fm = specfm.parse_frontmatter(p.read_text(encoding="utf-8"))
        if isinstance(fm.get("plugin_meta"), dict):
            pm = fm["plugin_meta"]
            for e in check_plugin_meta(pm):
                errors.append(f"{p.name}: {e}")
            inst = pm.get("install")
            if isinstance(inst, dict) and not check_install(inst):
                errors.extend(f"{p.name}: {e}" for e in check_install_release(p.parent, inst))
        # phase ファイル等 (plugin_meta 無し) は本 gate 対象外 (frontmatter は check-spec-frontmatter が担う)
    if inventory_path is not None and inventory_path.is_file():
        inv_errors, fatal = check_inventory(inventory_path)
        if fatal:
            return 2, [fatal]
        errors.extend(inv_errors)
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="inventory component gates/harness + index.plugin_meta を検証する")
    ap.add_argument("specs", nargs="*", help="対象 .md (index の plugin_meta 検査用)")
    ap.add_argument("--specs-dir", default=None, help="plan ディレクトリ")
    ap.add_argument("--inventory", default=None, help="component-inventory.json (既定 <specs-dir>/component-inventory.json)")
    args = ap.parse_args(argv)

    paths: list[Path] = [Path(s) for s in args.specs]
    inventory_path: Path | None = Path(args.inventory) if args.inventory else None
    if args.specs_dir:
        d = Path(args.specs_dir)
        if not d.is_dir():
            sys.stderr.write(f"not a directory: {d}\n")
            return 2
        paths.extend(collect_md(d))
        if inventory_path is None:
            inventory_path = d / "component-inventory.json"
    if not paths and inventory_path is None:
        sys.stderr.write("usage: check-spec-gates.py <md ...> | --specs-dir DIR\n")
        return 2
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            sys.stderr.write(f"not found: {p}\n")
        return 2
    if args.inventory and not inventory_path.is_file():
        sys.stderr.write(f"inventory not found: {inventory_path}\n")
        return 2
    code, errors = run(paths, inventory_path)
    if code == 2:
        for e in errors:
            sys.stderr.write(e + "\n")
        return 2
    if code == 0:
        sys.stdout.write("OK: inventory component gates/harness + index.plugin_meta 規律を機械強制で満たす\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
