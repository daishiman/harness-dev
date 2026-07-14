#!/usr/bin/env python3
# /// script
# name: check-build-handoff
# purpose: handoff-run-plugin-dev-plan.json が plan(L3) から build(L4) への実行可能ルーティング契約を満たすか検証する。
# inputs:
#   - argv: <handoff-json>
# outputs:
#   - stdout: OK summary
#   - stderr: schema/routing/top-sort/envelope violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""build handoff 契約を検証する。

run-plugin-dev-plan 自体は L4 実 build を行わない。代わりに、後段 build skill が
迷わず消費できる routing artifact を出すことをこの gate で保証する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

ALLOWED_BUILDERS = {
    "run-skill-create",
    "run-build-skill",
    "parent-skill-build",
    "plugin-scaffold",
    "manual-user-gated",
}
ENVELOPE_STATUSES = {"planned", "external_gap", "manual-user-gated", "not_applicable"}
TODO_RE = ("TODO", "TBD", "<TODO", "{{")
# inventory の surface component_kind → plugin manifest entry_points の該当リストキー。
# hook は entry_points でなく hooks ブロック・script は skill 内包物ゆえ entry_points に現れない
# (=突合対象外)。この写像に載る kind の component のみ entry_points 網羅を強制する。
ENTRY_POINT_KEY_BY_KIND = {"skill": "skills", "sub-agent": "agents", "slash-command": "commands"}


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc


def _require_str(obj: dict, key: str, errors: list[str], prefix: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}.{key} が非空 string でない")
        return ""
    return value.strip()


def _route_errors(route: dict, idx: int, ids: set[str], plan_dir: Path) -> list[str]:
    prefix = f"routes[{idx}]"
    errors: list[str] = []
    rid = _require_str(route, "id", errors, prefix)
    ck = _require_str(route, "component_kind", errors, prefix)
    _require_str(route, "name", errors, prefix)
    # per-phase 転換: route.spec は「参照する phase ファイル」で任意 (build は component 単位ゆえ
    # phase 参照は必須でない・推奨は phase-05-implementation.md)。存在時のみ実在検査する。
    spec_raw = route.get("spec")
    spec_rel = ""
    if spec_raw is not None:
        if not isinstance(spec_raw, str) or not spec_raw.strip():
            errors.append(f"{prefix}.spec は指定するなら非空 string であること")
        else:
            spec_rel = spec_raw.strip()
    builder = _require_str(route, "builder", errors, prefix)
    build_kind = _require_str(route, "build_kind", errors, prefix)
    _require_str(route, "build_target", errors, prefix)
    # handoff は planner-owned の routing 宣言であり、consumer の実行状態台帳ではない。
    # build 後も planned 据置とし、done/blocked 等は task-state.json と route report にのみ
    # 記録する (io-contract.md / pipeline-boundary-contract.md の単一 writer 境界)。
    status = route.get("status")
    if status != "planned":
        errors.append(
            f"{prefix}.status={status!r} は plan-time 宣言 'planned' でなければならない "
            "(実行状態は task-state.json / route-build-report が正本)"
        )

    ps = str(route.get("placement_scope", "skill")).strip() or "skill"
    if ck and ck not in specfm.COMPONENT_KINDS:
        errors.append(f"{prefix}.component_kind={ck!r} が enum 外 {list(specfm.COMPONENT_KINDS)}")
    if builder and builder not in ALLOWED_BUILDERS:
        errors.append(f"{prefix}.builder={builder!r} が enum 外 {sorted(ALLOWED_BUILDERS)}")
    if ck in specfm.BUILDER_BY_KIND and builder and builder != specfm.builder_for(ck, ps):
        errors.append(f"{prefix}: component_kind={ck} (placement={ps}) は builder={specfm.builder_for(ck, ps)} を要求 (現値 {builder})")
    if ck in specfm.BUILD_KIND_BY_KIND and build_kind and build_kind != specfm.BUILD_KIND_BY_KIND[ck]:
        errors.append(f"{prefix}: component_kind={ck} は build_kind={specfm.BUILD_KIND_BY_KIND[ck]} を要求 (現値 {build_kind})")
    build_args = route.get("build_args")
    if not isinstance(build_args, dict) or not build_args:
        errors.append(f"{prefix}.build_args が非空 object でない")
    elif builder == "run-build-skill" and build_args.get("kind") != build_kind:
        errors.append(f"{prefix}.build_args.kind={build_args.get('kind')!r} が build_kind={build_kind!r} と不一致")
    elif builder == "run-skill-create":
        if not str(build_args.get("skill_name", "")).strip():
            errors.append(f"{prefix}.build_args.skill_name が空")
        # brief_path は render-skill-brief.py 出力先の宣言 (plan_dir 相対・推奨
        # briefs/skill-brief-<id>.json)。実体は render で生成されるため実在検査せず、
        # 宣言時のみ非空 string を強制する。
        if "brief_path" in build_args and not (
            isinstance(build_args["brief_path"], str) and build_args["brief_path"].strip()
        ):
            errors.append(f"{prefix}.build_args.brief_path は宣言するなら非空 string であること")
    elif builder == "parent-skill-build":
        for key in ("parent_skill", "script_path"):
            if not str(build_args.get(key, "")).strip():
                errors.append(f"{prefix}.build_args.{key} が空")
    elif builder == "plugin-scaffold":
        # plugin-root へ hoist する共有 script は親 skill を持たず script_path のみ必須。
        if not str(build_args.get("script_path", "")).strip():
            errors.append(f"{prefix}.build_args.script_path が空 (plugin-root script は script_path 必須)")

    depends = route.get("depends_on")
    if not isinstance(depends, list):
        errors.append(f"{prefix}.depends_on が list でない")
    else:
        for dep in depends:
            if not isinstance(dep, str) or not dep.strip():
                errors.append(f"{prefix}.depends_on に非空 string でない値がある")
            elif dep not in ids:
                errors.append(f"{prefix}.depends_on={dep!r} は routes 内に存在しない")
    if spec_rel:
        spec_path = plan_dir / spec_rel
        if not spec_path.is_file():
            errors.append(f"{prefix}.spec が plan_dir 配下に存在しない: {spec_path}")
    if rid and not rid.startswith("C"):
        errors.append(f"{prefix}.id={rid!r} は component id (Cxx) 形式でない")
    return errors


def _check_builder_status(routes: list[dict], open_issue_ids: set[str]) -> list[str]:
    """builder の実行実体有無 (specfm.BUILDER_STATUS) を routes へ fail-closed 強制する。

    contract-only builder (planner 上の routing 語彙で run-build-skill の 7 kind ではない) の route は
    `builder_status: contract-only` の明示宣言 + open_issues 内の gap id への `gap_ref` を必須に
    する (routing 解決先の無音隠蔽を防ぐ)。executor-backed は builder_status 省略可 (宣言時は
    一致必須)。manual-user-gated 等 写像外 builder は本検査の対象外。
    """
    errors: list[str] = []
    for idx, route in enumerate(routes):
        prefix = f"routes[{idx}]"
        builder = str(route.get("builder", "")).strip()
        declared = route.get("builder_status")
        if declared is not None and declared not in specfm.BUILDER_STATUSES:
            errors.append(f"{prefix}.builder_status={declared!r} が enum 外 {list(specfm.BUILDER_STATUSES)}")
            continue
        expected = specfm.BUILDER_STATUS.get(builder)
        if expected is None:
            continue
        if declared is not None and declared != expected:
            errors.append(f"{prefix}: builder={builder} は builder_status={expected!r} を要求 (現値 {declared!r})")
        if expected == "contract-only":
            if declared != "contract-only":
                errors.append(
                    f"{prefix}: builder={builder} は contract-only routing 語彙。"
                    "builder_status: contract-only を明示宣言すること"
                )
            gap_ref = str(route.get("gap_ref", "")).strip()
            if not gap_ref:
                errors.append(f"{prefix}: contract-only route は gap_ref (open_issues の gap id) 必須")
            elif gap_ref not in open_issue_ids:
                errors.append(f"{prefix}.gap_ref={gap_ref!r} が open_issues[].id に存在しない")
    return errors


def _check_toposort(routes: list[dict]) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for idx, route in enumerate(routes):
        rid = str(route.get("id", "")).strip()
        for dep in route.get("depends_on", []) if isinstance(route.get("depends_on"), list) else []:
            if dep not in seen:
                errors.append(f"routes[{idx}] {rid}: depends_on={dep} が先行 route に無い (top-sort 違反)")
        if rid:
            seen.add(rid)
    return errors


def _check_parent_scaffold(routes: list[dict]) -> list[str]:
    """二相 skill build (scaffold→fill) の順序制約を機械可読契約として強制する。

    placement_scope=skill の script (builder=parent-skill-build) は build_target が親 skill の
    build_target ディレクトリ配下に置かれるため、toposort 上は script が親 skill より先に build
    されるのに物理ディレクトリは親 skill scaffold 内という順序逆転が生じる。この逆転を後段
    consumer が routes 配列順でなく守れるよう、当該 script route は `requires_parent_scaffold` で
    自身を内包する親 skill の id を機械可読に宣言しなければならない (散文 build_sequencing_notes
    依存の解消)。plugin-root へ hoist した共有 script (builder=plugin-scaffold) は親 skill 配下に
    置かれず逆転が起きないため対象外。"""
    errors: list[str] = []
    skill_targets: dict[str, str] = {}
    for route in routes:
        if not isinstance(route, dict):
            continue
        if str(route.get("component_kind", "")).strip() != "skill":
            continue
        bt = str(route.get("build_target", "")).strip().rstrip("/")
        rid = str(route.get("id", "")).strip()
        if bt and rid:
            skill_targets[rid] = bt + "/"
    for idx, route in enumerate(routes):
        if not isinstance(route, dict):
            continue
        if str(route.get("component_kind", "")).strip() != "script":
            continue
        if str(route.get("builder", "")).strip() != "parent-skill-build":
            continue
        bt = str(route.get("build_target", "")).strip()
        if not bt:
            continue
        parents = sorted(sid for sid, st in skill_targets.items() if bt.startswith(st))
        if not parents:
            continue  # 親 skill 配下でない = 順序逆転なし (対象外)
        prefix = f"routes[{idx}]"
        rps = str(route.get("requires_parent_scaffold", "")).strip()
        if not rps:
            errors.append(
                f"{prefix}: parent-skill-build script の build_target が親 skill 配下 {parents} にあり "
                "二相 build (scaffold→fill) の順序逆転が生じるため requires_parent_scaffold (親 skill id) "
                "を機械可読に明示すること (散文 build_sequencing_notes 依存の解消)"
            )
        elif rps not in parents:
            errors.append(
                f"{prefix}.requires_parent_scaffold={rps!r} が build_target を内包する親 skill "
                f"{parents} のいずれでもない"
            )
    return errors


def _check_inventory_provenance(routes: list[dict], plan_dir: Path) -> list[str]:
    """routes が component-inventory.json 由来 (§9 build handoff 契約) であることを検証する。

    plan_dir 直下に component-inventory.json が在るときのみ活性化する (孤立 handoff fixture は
    スキップ)。routes id 集合 == inventory component id 集合 (漏れ/余分 0) かつ各 route の
    主要 route フィールドが対応 component と一致することを検査する (§13-C4)。
    """
    inv_path = plan_dir / "component-inventory.json"
    if not inv_path.is_file():
        return []
    try:
        data = json.loads(inv_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"component-inventory JSON parse error: {exc}"]
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return ["component-inventory.json に components[] list が無い (routes 由来検証不能)"]
    comps = {str(c.get("id", "")).strip(): c for c in data["components"]
             if isinstance(c, dict) and str(c.get("id", "")).strip()}
    route_map = {str(r.get("id", "")).strip(): r for r in routes
                 if isinstance(r, dict) and str(r.get("id", "")).strip()}
    errors: list[str] = []
    for missing in sorted(set(comps) - set(route_map)):
        errors.append(f"inventory component {missing} に対応する route が無い (全 component を routing すること)")
    for extra in sorted(set(route_map) - set(comps)):
        errors.append(f"route {extra} が component-inventory.json に存在しない (routes は inventory 由来)")
    for rid in sorted(set(route_map) & set(comps)):
        route = route_map[rid]
        comp = comps[rid]
        for key in ("component_kind", "name", "builder", "build_kind", "build_target", "placement_scope"):
            r_val = route.get(key)
            c_val = comp.get(key)
            if isinstance(r_val, str):
                r_val = r_val.strip()
            if isinstance(c_val, str):
                c_val = c_val.strip()
            if r_val and c_val and r_val != c_val:
                errors.append(f"route {rid} の {key}={r_val!r} が inventory の {c_val!r} と不一致")
        r_dep = route.get("depends_on")
        c_dep = comp.get("depends_on")
        if isinstance(r_dep, list) and isinstance(c_dep, list) and r_dep != c_dep:
            errors.append(f"route {rid} の depends_on={r_dep!r} が inventory の {c_dep!r} と不一致")
        r_args = route.get("build_args")
        c_args = comp.get("build_args")
        if isinstance(c_args, dict) and c_args and r_args != c_args:
            errors.append(f"route {rid} の build_args が inventory と不一致")
    return errors


def _load_inventory_components(plan_dir: Path) -> list[dict]:
    """<plan_dir>/component-inventory.json の components[] を fail-soft に返す。

    ファイル不在・parse error・OSError・components[] 非 list はいずれも空 list を返し例外を
    投げない (inventory を伴わない孤立 handoff fixture の検証を壊さない=既存動作の後方互換)。
    空 list を受けた突合器は entry_points 検査を no-op にするため、既存呼び出し元の挙動は不変。
    """
    inv_path = plan_dir / "component-inventory.json"
    if not inv_path.is_file():
        return []
    try:
        data = json.loads(inv_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return []
    return [c for c in data["components"] if isinstance(c, dict)]


def _check_manifest_entry_points_coverage(entry_points: object, comps: list[dict], prefix: str) -> list[str]:
    """inventory の surface component が manifest の entry_points 該当リストへ宣言済みか検査する。

    ENTRY_POINT_KEY_BY_KIND に載る kind (skill/sub-agent/slash-command) の component について、
    その name/skill_name が entry_points.<key> リストに含まれることを必須にする。build 後に
    「生成されたが manifest に未宣言で LLM から発見不能」という無音欠落を plan 段階で fail-closed
    にする (inventory=作る物 と manifest=宣言 の 2 SSOT 突合)。hook/script は entry_points に
    現れない (hooks 別ブロック・script は skill 内包物) ため対象外。entry_points が dict でない
    (未宣言) 場合は全 surface を未網羅として報告する。
    """
    errors: list[str] = []
    ep = entry_points if isinstance(entry_points, dict) else {}
    for comp in comps:
        ck = str(comp.get("component_kind", "")).strip()
        ep_key = ENTRY_POINT_KEY_BY_KIND.get(ck)
        if ep_key is None:
            continue  # hook/script は entry_points 対象外
        cid = str(comp.get("id", "")).strip()
        name = str(comp.get("name") or comp.get("skill_name") or "").strip()
        if not name:
            errors.append(f"{prefix}: component {cid} (kind={ck}) に name/skill_name が無く entry_points 突合不能")
            continue
        listed = ep.get(ep_key)
        listed = listed if isinstance(listed, list) else []
        if name not in listed:
            errors.append(
                f"{prefix}: component {cid} ({ck} {name!r}) が manifest entry_points.{ep_key} に未宣言 "
                "(inventory の surface component は entry_points へ漏れなく登録すること)"
            )
    return errors


def _check_manifest_draft(
    path: Path, target_plugin_slug: str, prefix: str, comps: list[dict] | None = None
) -> list[str]:
    """manifest draft の placeholder 不在・name 一致・(comps 指定時) entry_points 網羅を検査する。

    comps は既定 None (既存呼び出し元の後方互換=name/placeholder のみ検査)。非空 list を渡した
    ときだけ _check_manifest_entry_points_coverage を発火し inventory との突合を追加する。
    """
    errors: list[str] = []
    if not path.is_file():
        return [f"{prefix}.draft_path が存在しない: {path}"]
    text = path.read_text(encoding="utf-8")
    for token in TODO_RE:
        if token in text:
            errors.append(f"{prefix}.draft_path に placeholder {token!r} が残っている")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{prefix}.draft_path JSON parse error: {exc}")
        return errors
    if data.get("name") != target_plugin_slug:
        errors.append(f"{prefix}.draft_path name={data.get('name')!r} != target_plugin_slug={target_plugin_slug!r}")
    if comps:
        errors.extend(_check_manifest_entry_points_coverage(data.get("entry_points"), comps, prefix))
    return errors


def _check_envelope(envelope: object, plan_dir: Path, target_plugin_slug: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(envelope, dict) or not envelope:
        return ["envelope が非空 dict でない"]
    for key, item in envelope.items():
        prefix = f"envelope.{key}"
        if not isinstance(item, dict):
            errors.append(f"{prefix} が dict でない")
            continue
        status = item.get("status")
        if status not in ENVELOPE_STATUSES:
            errors.append(f"{prefix}.status={status!r} が enum 外 {sorted(ENVELOPE_STATUSES)}")
        owner = item.get("owner")
        if status not in ("not_applicable",) and not (isinstance(owner, str) and owner.strip()):
            errors.append(f"{prefix}.owner が非空 string でない")
        if status in ("external_gap", "manual-user-gated"):
            reason = item.get("gap_reason") or item.get("approval_reason")
            if not (isinstance(reason, str) and reason.strip()):
                errors.append(f"{prefix}: status={status} は gap_reason/approval_reason が必要")
        if key == "manifest" and status != "not_applicable":
            draft_path = item.get("draft_path")
            if not isinstance(draft_path, str) or not draft_path.strip():
                errors.append(f"{prefix}.draft_path が非空 string でない")
            else:
                errors.extend(_check_manifest_draft(
                    plan_dir / draft_path, target_plugin_slug, prefix,
                    comps=_load_inventory_components(plan_dir)))
    return errors


def _check_task_graph_ref(data: dict, plan_dir: Path) -> list[str]:
    """handoff.task_graph_ref (C6) の形状と routes↔producer task 対応を検証する。

    task-graph はデフォルト成果物 (§9) ゆえ `task_graph_ref` は**常時付与が必須** (未設定は
    fail-closed で violation)。設定時は {path, schema_version} 形状を検証し、path が指す
    task-graph.json が実在する場合のみ producer task (produces エッジを持つ node) の entity_ref
    集合と routes[].id 集合の 1:1 以上対応を検証する。file 不在時は形状のみ検証する
    (task-graph.json 実体の 10 検査は validate-task-graph.py が別ゲートで担う・責務分離)。
    """
    tgr = data.get("task_graph_ref")
    if tgr is None:
        return ["handoff.task_graph_ref が未設定 (task-graph はデフォルト成果物ゆえ常時付与が必須・§9・build を task-graph mode で駆動する)"]
    errors: list[str] = []
    if not isinstance(tgr, dict):
        return ["handoff.task_graph_ref が object でない"]
    path_v = tgr.get("path")
    sv = tgr.get("schema_version")
    if not (isinstance(path_v, str) and path_v.strip()):
        errors.append("handoff.task_graph_ref.path が非空文字列でない")
    if not (isinstance(sv, str) and sv.strip()):
        errors.append("handoff.task_graph_ref.schema_version が非空文字列でない")
    if errors or not isinstance(path_v, str):
        return errors
    tg_path = plan_dir / path_v
    if not tg_path.is_file():
        # メタ循環分離: 契約宣言のみで実 task-graph.json を持たない fixed-13-phase plan は形状検証で足りる。
        return errors
    try:
        graph = _load_json(tg_path)
    except ValueError as exc:
        return [f"handoff.task_graph_ref.path の task-graph.json が JSON として不正: {exc}"]
    if not isinstance(graph, dict):
        return ["task-graph.json root が object でない"]
    node_entity: dict[str, object] = {}
    for n in graph.get("nodes", []):
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            node_entity[n["id"]] = n.get("entity_ref")
    producer_entities: set[str] = set()
    for e in graph.get("edges", []):
        if isinstance(e, dict) and e.get("type") == "produces":
            ent = node_entity.get(e.get("from"))
            if isinstance(ent, str) and ent:
                producer_entities.add(ent)
    # C17: target shape の component-build node は明示 route_ref で route と対応する
    # (entity_ref 暗黙 route でなく)。producer_entities (fixed-13-phase の produces 経路) に
    # 明示 route_ref を additive 合算し、どちらかで対応が取れれば充足とする (後方互換)。
    explicit_routes: set[str] = set()
    for n in graph.get("nodes", []):
        if not isinstance(n, dict) or n.get("execution_kind") != "component-build":
            continue
        rr = n.get("route_ref")
        if isinstance(rr, str) and rr.strip():
            explicit_routes.add(rr.strip())
    covered = producer_entities | explicit_routes
    route_ids = {
        str(r.get("id", "")).strip()
        for r in data.get("routes", [])
        if isinstance(r, dict) and str(r.get("id", "")).strip()
    }
    for rid in sorted(rid for rid in route_ids if rid not in covered):
        errors.append(
            f"route {rid} が task-graph 上の producer task (produces を持つ node) にも "
            "component-build の明示 route_ref にも対応しない"
        )
    return errors


def _check_cycle_id_parity(data: dict, plan_dir: Path) -> list[str]:
    """handoff.cycle_id (C13・additive) と goal-spec.json の cycle_id の一致を検証する。

    両者不在 (None) は一致とみなす (後方互換・既存 handoff は無改修で妥当)。goal-spec が
    読めない場合はスキップ (fail-soft)。consumer は cycle-id を本フィールドから読み plan_dir
    パス末尾解析は禁止 (レイアウト判断の consumer 側二重実装を防ぐ)。
    """
    handoff_cid = data.get("cycle_id")
    gs_path = plan_dir / "goal-spec.json"
    if not gs_path.is_file():
        return []
    try:
        goal_spec = _load_json(gs_path)
    except ValueError:
        return []
    gs_cid = goal_spec.get("cycle_id") if isinstance(goal_spec, dict) else None
    if handoff_cid != gs_cid:
        return [f"handoff.cycle_id={handoff_cid!r} が goal-spec.cycle_id={gs_cid!r} と不一致 (parity)"]
    return []


def validate_handoff(data: object, handoff_path: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["handoff root が object でない"]
    plan_dir_raw = _require_str(data, "plan_dir", errors, "handoff")
    _require_str(data, "target_plugin_slug", errors, "handoff")
    target_plugin_slug = str(data.get("target_plugin_slug", "")).strip()
    mode = data.get("mode")
    if mode not in ("create", "update"):
        errors.append(f"handoff.mode={mode!r} は create|update のみ")
    # per-phase 転換: 本数固定/カウント/pin の各機構は 13 フェーズ固定で削除した。
    # routes[] は component-inventory.json の components[] 由来ゆえ本数強制ブロックは撤廃した。

    # spec / build_target の解決は cwd 非依存にする。handoff は必ず <PLAN_DIR> 直下に
    # 書かれる (handoff_path.parent == PLAN_DIR) ため、相対 plan_dir フィールド (repo-root
    # 相対の metadata) を Path.cwd() で再構成せず handoff ファイルの所在を基準にする。
    # cwd を基準にすると skill dir から実行された CI 等で plan_dir が二重化して spec を
    # 見失う (cwd 依存バグ)。絶対パス plan_dir のみ明示値を尊重する。
    if plan_dir_raw and Path(plan_dir_raw).is_absolute():
        plan_dir = Path(plan_dir_raw)
    else:
        plan_dir = handoff_path.parent

    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        errors.append("handoff.routes が非空 list でない")
        routes = []
    ids = {str(r.get("id", "")).strip() for r in routes if isinstance(r, dict) and str(r.get("id", "")).strip()}
    if len(ids) != len(routes):
        errors.append("handoff.routes の id が欠落または重複している")
    for idx, route in enumerate(routes):
        if not isinstance(route, dict):
            errors.append(f"routes[{idx}] が object でない")
            continue
        errors.extend(_route_errors(route, idx, ids, plan_dir))
    errors.extend(_check_toposort([r for r in routes if isinstance(r, dict)]))
    errors.extend(_check_parent_scaffold([r for r in routes if isinstance(r, dict)]))
    open_issues = data.get("open_issues")
    open_issue_ids = {
        str(i.get("id", "")).strip()
        for i in (open_issues if isinstance(open_issues, list) else [])
        if isinstance(i, dict) and str(i.get("id", "")).strip()
    }
    errors.extend(_check_builder_status([r for r in routes if isinstance(r, dict)], open_issue_ids))
    errors.extend(_check_inventory_provenance(routes, plan_dir))
    errors.extend(_check_envelope(data.get("envelope"), plan_dir, target_plugin_slug))
    errors.extend(_check_task_graph_ref(data, plan_dir))
    errors.extend(_check_cycle_id_parity(data, plan_dir))
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="build handoff JSON を検証する")
    ap.add_argument("handoff", help="handoff-run-plugin-dev-plan.json")
    args = ap.parse_args(argv)

    path = Path(args.handoff)
    if not path.is_file():
        sys.stderr.write(f"handoff not found: {path}\n")
        return 2
    try:
        data = _load_json(path)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    errors = validate_handoff(data, path.resolve())
    if not errors:
        routes = data.get("routes", [])
        sys.stdout.write(f"OK: build handoff が {len(routes)} routes と envelope 契約を満たす\n")
        return 0
    for err in errors:
        sys.stderr.write(err + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
