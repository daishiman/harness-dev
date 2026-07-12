#!/usr/bin/env python3
# /// script
# name: check-spec-gates
# purpose: component-inventory.json の各 component の quality_gates(p0_lint網羅/build_trace/elegant_review C1-C4/content_review verdict/evaluator>=80,high0) と harness_coverage(min>=80/kind_pass) を specfm で値域検証し、index.plugin_meta の plugin 階層規律を値域検証する決定論ゲート。
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
plugin 階層規律 (plugin_meta) 検査は現状維持。
"""
from __future__ import annotations

import argparse
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


def collect_md(specs_dir: Path) -> list[Path]:
    return sorted(specs_dir.glob("*.md"))


def run(md_paths: list[Path], inventory_path: Path | None) -> tuple[int, list[str]]:
    errors: list[str] = []
    for p in md_paths:
        fm = specfm.parse_frontmatter(p.read_text(encoding="utf-8"))
        if isinstance(fm.get("plugin_meta"), dict):
            for e in check_plugin_meta(fm["plugin_meta"]):
                errors.append(f"{p.name}: {e}")
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
