#!/usr/bin/env python3
# /// script
# name: derive-task-graph
# purpose: 13 phase §5 完了チェックリスト項目 + component-inventory.json から task-graph.json (第3の射影) を決定論導出し canonical serialization で単一 writer として書き出す。graph_hash() と read-only サブコマンド --print-graph-hash <path> (FC-4) を提供し consumer=harness-creator の build 開始時 pin 用 hash 取得の唯一の経路とする。
# inputs:
#   - argv: <PLAN_DIR> | --print-graph-hash <task-graph.json path>
# outputs:
#   - stdout: (既定) 書込パス / (--print-graph-hash) sha256:<64hex>
#   - stderr: 導出/正準化エラー
#   - exit: 0=OK / 1=graph 不正で hash 算出不能 / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: <PLAN_DIR>/task-graph.json (既定経路のみ・--print-graph-hash は副作用なし)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""task-graph.json の決定論導出器 + canonicalizer + graph_hash (単一 writer)。

design: plugin-plans/plugin-dev-planner/phase-05-implementation.md (C2/C11/C16)。
canonicalize() が唯一の正準形を書き、validate-task-graph.py は同一ロジックを再適用して
非正準を拒否する (読み書き責務分離)。graph_hash() は canonical bytes の sha256 で、
--print-graph-hash が consumer 向け read-only 契約 (argv/stdout/exit を安定固定) を担う。

inventory が surface_build_projection を宣言する場合、plugin_level_surfaces の required:true
surface ごとに SURFACE-{surface_key} build node (one_required_surface_one_node) を射影し、
required surface の builder 未割当=構造的 build/gate 欠落 (build vs ship completeness の片翼)
を封じる。宣言不在の旧 inventory は従来出力と byte 同一 (既存 plan の graph_hash を壊さない)。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

CHECKLIST_SECTION = "## 完了チェックリスト"
# task node の固定 key 順 (canonical serialization 用)。required は全 node が携帯し、optional は
# node に present のときだけ出力する。C17 の execution_kind/route_ref/task_spec_ref は target shape
# だけが携帯するため present-gated 出力にして fixed-13-phase の従来出力を byte 不変に保つ。
_NODE_REQUIRED_KEYS = ("id", "title", "phase_ref", "entity_ref", "state", "write_scope")
_NODE_OPTIONAL_KEYS = ("acceptance_criterion", "execution_kind", "route_ref", "task_spec_ref")
_NODE_KEYS = _NODE_REQUIRED_KEYS + _NODE_OPTIONAL_KEYS
_EDGE_KEYS = ("type", "from", "to")
# チェックボックス付き行のみを task 候補にする (## 完了チェックリスト 節に内包される ### 受入例 の `- ` を除外)。
_CHECKBOX_RE = re.compile(r"^-\s+\[[ xX]\]\s+(.+)$")
_PHASE_REF_RE = re.compile(r"^P(0[1-9]|1[0-3])$")
_TARGET_SHAPE = "task-graph-derived"
_FIXED_SHAPE = "fixed-13-phase"


def _parse_checklist_items(section_body: str) -> list[str]:
    """`## 完了チェックリスト` 節本文からチェックボックス項目 (task node 候補) を抽出する。"""
    items: list[str] = []
    for line in section_body.splitlines():
        m = _CHECKBOX_RE.match(line.strip())
        if m:
            items.append(m.group(1).strip())
    return items


def _phase_files(plan_dir: Path) -> list[Path]:
    """plan_dir 直下の phase-NN-*.md を phase 番号順で返す。"""
    return sorted(plan_dir.glob("phase-*.md"), key=lambda p: p.name)


def shape_marker(plan_dir: Path) -> str:
    """index frontmatter の shape marker を返す。未指定だけを legacy fixed shape とする。

    未知値を fixed shape へ黙って縮退させると、task-spec を正本として書いた plan が旧 checklist
    射影へ化けるため fail-closed にする。これは target shape の producer/consumer join の入口 SSOT。
    """
    index_path = Path(plan_dir) / "index.md"
    if not index_path.is_file():
        return _FIXED_SHAPE
    try:
        fm = specfm.parse_frontmatter(index_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"index.md を読めない: {exc}") from exc
    marker = fm.get("shape_marker", _FIXED_SHAPE)
    if marker not in (_FIXED_SHAPE, _TARGET_SHAPE):
        raise ValueError(
            f"unknown shape_marker={marker!r}; expected {_FIXED_SHAPE!r} or {_TARGET_SHAPE!r}"
        )
    return marker


def _nonempty_string(value, field: str, spec_path: Path) -> str:
    if not (isinstance(value, str) and value.strip()):
        raise ValueError(f"{spec_path.name}: {field} は非空文字列必須")
    return value.strip()


def _string_list(value, field: str, spec_path: Path) -> list[str]:
    """task spec の graph relation list を非空文字列 list として厳格に読む。"""
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"{spec_path.name}: {field} は非空文字列の配列でなければならない")
    return [v.strip() for v in value]


def _phase_titles(plan_dir: Path) -> dict[str, str]:
    """phase_ref → phase_name。target shape では phase 文書を policy label にだけ使う。"""
    titles: dict[str, str] = {}
    for path in _phase_files(plan_dir):
        try:
            fm = specfm.parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"{path.name} を読めない: {exc}") from exc
        phase_ref = fm.get("id")
        if isinstance(phase_ref, str) and phase_ref:
            title = fm.get("phase_name")
            titles[phase_ref] = title.strip() if isinstance(title, str) and title.strip() else phase_ref
    return titles


def _derive_task_spec_shape(plan_dir: Path) -> dict:
    """task-specs/*.md を正本に 1 spec = 1 dispatchable leaf として graph を導出する。

    phase 文書は leaf の作成元ではなく単一 phase policy。各 phase_ref には非 dispatch の
    phase-gate root を 1 個だけ作り、明示 depends_on/produces/consumes は task spec から写す。
    component-build の builder join は route_ref の明示値だけを使い entity_ref から推測しない。
    """
    specs_dir = plan_dir / "task-specs"
    spec_paths = sorted(specs_dir.glob("*.md"), key=lambda p: p.name) if specs_dir.is_dir() else []
    if not spec_paths:
        raise ValueError("shape_marker=task-graph-derived には task-specs/*.md が 1 件以上必要")

    leaves: list[dict] = []
    relations: dict[str, dict[str, list[str]]] = {}
    seen_ids: set[str] = set()
    phase_leaves: dict[str, list[str]] = {}

    for path in spec_paths:
        try:
            fm = specfm.parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"{path.name} を読めない: {exc}") from exc
        task_id = _nonempty_string(fm.get("id"), "id", path)
        if task_id != path.stem:
            raise ValueError(f"{path.name}: id={task_id!r} は filename stem={path.stem!r} と一致必須")
        if task_id in seen_ids:
            raise ValueError(f"task id が重複: {task_id}")
        seen_ids.add(task_id)

        phase_ref = _nonempty_string(fm.get("phase_ref"), "phase_ref", path)
        if not _PHASE_REF_RE.match(phase_ref):
            raise ValueError(f"{path.name}: phase_ref={phase_ref!r} は P01..P13 必須")
        execution_kind = _nonempty_string(fm.get("execution_kind"), "execution_kind", path)
        if execution_kind not in ("direct-task", "component-build"):
            raise ValueError(
                f"{path.name}: execution_kind は direct-task|component-build のみ "
                "(phase-gate は producer が phase root として導出する)"
            )

        raw_route = fm.get("route_ref")
        route_ref = raw_route.strip() if isinstance(raw_route, str) and raw_route.strip() else None
        if execution_kind == "component-build" and route_ref is None:
            raise ValueError(f"{path.name}: component-build は明示 route_ref 必須")
        if execution_kind == "direct-task" and route_ref is not None:
            raise ValueError(f"{path.name}: direct-task は route_ref を持てない")

        acceptance = fm.get("acceptance_criterion")
        if not (isinstance(acceptance, str) and acceptance.strip()):
            criteria = fm.get("acceptance_criteria")
            if isinstance(criteria, list) and criteria and isinstance(criteria[0], str):
                acceptance = criteria[0]
        acceptance = _nonempty_string(acceptance, "acceptance_criterion", path)
        write_scope = _nonempty_string(fm.get("write_scope"), "write_scope", path)
        title = _nonempty_string(fm.get("title"), "title", path)
        entity = fm.get("entity_ref")
        entity_ref = entity.strip() if isinstance(entity, str) and entity.strip() else None

        leaves.append({
            "id": task_id,
            "title": title,
            "phase_ref": phase_ref,
            "entity_ref": entity_ref,
            "state": "pending",
            "write_scope": write_scope,
            "acceptance_criterion": acceptance,
            "execution_kind": execution_kind,
            "route_ref": route_ref,
            "task_spec_ref": f"task-specs/{path.name}",
        })
        produces = _string_list(fm.get("produces"), "produces", path)
        if not produces:
            raise ValueError(f"{path.name}: produces は 1 件以上必須 (1 spec = 1 検証可能成果物)")
        relations[task_id] = {
            "depends_on": _string_list(fm.get("depends_on"), "depends_on", path),
            "produces": produces,
            "consumes": _string_list(fm.get("consumes"), "consumes", path),
        }
        phase_leaves.setdefault(phase_ref, []).append(task_id)

    phase_ids = set(phase_leaves)
    collisions = seen_ids & phase_ids
    if collisions:
        raise ValueError(f"task id が phase root id と衝突: {', '.join(sorted(collisions))}")
    for task_id, rel in relations.items():
        missing = sorted(set(rel["depends_on"]) - seen_ids)
        if missing:
            raise ValueError(f"{task_id}: depends_on が未知 task を参照: {', '.join(missing)}")

    titles = _phase_titles(plan_dir)
    roots = [{
        "id": phase_ref,
        "title": titles.get(phase_ref, phase_ref),
        "phase_ref": phase_ref,
        "entity_ref": None,
        "state": "pending",
        "write_scope": phase_ref,
        "execution_kind": "phase-gate",
        "route_ref": None,
        "task_spec_ref": None,
    } for phase_ref in sorted(phase_leaves, key=_phase_order)]

    edge_keys: set[tuple[str, str, str]] = set()
    for phase_ref, task_ids in phase_leaves.items():
        for task_id in task_ids:
            edge_keys.add(("parent_of", phase_ref, task_id))
            edge_keys.add(("depends_on", phase_ref, task_id))  # root done = 全 leaf 完了
    for task_id, rel in relations.items():
        edge_keys.update(("depends_on", task_id, dep) for dep in rel["depends_on"])
        edge_keys.update(("produces", task_id, artifact) for artifact in rel["produces"])
        edge_keys.update(("consumes", artifact, task_id) for artifact in rel["consumes"])
    edges = [{"type": typ, "from": src, "to": dst} for typ, src, dst in sorted(edge_keys)]
    return {"schema_version": "1.0", "nodes": roots + leaves, "edges": edges}


def _inventory_build_targets(plan_dir: Path) -> dict[str, str]:
    """component id → build_target マップ (write_scope 解決用・欠落時は空)。"""
    inv_path = plan_dir / "component-inventory.json"
    if not inv_path.exists():
        return {}
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    for comp in inv.get("components", []):
        cid = comp.get("id")
        bt = comp.get("build_target")
        if isinstance(cid, str) and isinstance(bt, str) and bt:
            out[cid] = bt
    return out


def _inventory_depends(plan_dir: Path) -> dict[str, list[str]]:
    """component id → depends_on (component 粒度) マップ (task depends_on 反映用)。"""
    inv_path = plan_dir / "component-inventory.json"
    if not inv_path.exists():
        return {}
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, list[str]] = {}
    for comp in inv.get("components", []):
        cid = comp.get("id")
        deps = comp.get("depends_on", [])
        if isinstance(cid, str) and isinstance(deps, list):
            out[cid] = [d for d in deps if isinstance(d, str)]
    return out


def _inventory_couples(plan_dir: Path) -> set[frozenset[str]]:
    """component 間の couples_with 宣言を無向ペア集合へ正規化する (接合密度の直列化根拠)。

    couples_with は対称関係 (A couples_with B ⇔ B couples_with A) ゆえ frozenset で
    重複排除し、片側宣言でもペアを拾う。自己結合 (A in A.couples_with) は無意味ゆえ除外。
    depends_on と違い成果物ハード依存ではなく「同時 build で統合 finding が先送りされる密結合」
    の宣言で、derive はこれを同一 phase 兄弟の直列化 depends_on へ機械展開する。
    """
    inv_path = plan_dir / "component-inventory.json"
    if not inv_path.exists():
        return set()
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    pairs: set[frozenset[str]] = set()
    for comp in inv.get("components", []):
        cid = comp.get("id")
        cw = comp.get("couples_with", [])
        if not isinstance(cid, str) or not isinstance(cw, list):
            continue
        for other in cw:
            if isinstance(other, str) and other and other != cid:
                pairs.add(frozenset((cid, other)))
    return pairs


def _transitive_closure(comp_depends: dict[str, list[str]]) -> dict[str, set[str]]:
    """component depends_on の推移閉包 (cid -> 推移的に依存する上流 cid 集合) を返す。

    coupling の直列化向き (id 昇順) が既存の推移依存と逆走して cycle 化するのを防ぐため、
    直接ペアだけでなく推移順序 (A→C→B) を検出する土台。comp_depends 自体が循環していても
    seen で終端する (防御的)。validate-task-graph.py が (j) で import 再利用する SSOT。
    """
    reach: dict[str, set[str]] = {}

    def _visit(node: str, acc: set[str], seen: set[str]) -> None:
        for up in comp_depends.get(node, []):
            if up in seen:
                continue
            seen.add(up)
            acc.add(up)
            _visit(up, acc, seen)

    for cid in comp_depends:
        acc: set[str] = set()
        _visit(cid, acc, set())
        reach[cid] = acc
    return reach


def _phase_order(phase_ref: str) -> int:
    """P01..P13 を数値順へ写す。未知形式は末尾扱いにして既存後方互換を保つ。"""
    m = re.match(r"^P(\d+)$", str(phase_ref))
    return int(m.group(1)) if m else 10_000


class SurfaceProjectionError(ValueError):
    """surface_build_projection の required_fields 欠落 (missing_required_field: projection-fail)。"""


def _dotted_get(d: dict, path: str):
    """'quality_gates.path_existence' 形のドット path を辿って値を返す (欠落は None)。"""
    cur = d
    for part in str(path).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _inventory_surface_projection(plan_dir: Path) -> tuple[dict, dict[str, dict]] | None:
    """surface_build_projection 宣言と required:true な plugin_level_surfaces を返す。

    宣言は plugin_level_surfaces 内 (実配置) または top-level を探す。宣言不在の旧 inventory
    では None を返し、derive は射影を一切行わない (従来出力と byte 同一 = 後方互換)。
    required surface の選択は source_selector 契約 `plugin_level_surfaces.*[required=true]`
    (宣言 entry 自身は required を持たず自然に除外される)。
    """
    inv_path = plan_dir / "component-inventory.json"
    if not inv_path.exists():
        return None
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pls = inv.get("plugin_level_surfaces")
    pls = pls if isinstance(pls, dict) else {}
    decl = inv.get("surface_build_projection") or pls.get("surface_build_projection")
    if not isinstance(decl, dict):
        return None
    surfaces = {
        key: sf for key, sf in pls.items()
        if isinstance(sf, dict) and sf.get("required") is True
    }
    return decl, surfaces


def _project_surface_nodes(decl: dict, surfaces: dict[str, dict],
                           final_phase_root: str | None) -> tuple[list[dict], list[dict]]:
    """required surface ごとに SURFACE-{surface_key} node を射影する (one_required_surface_one_node)。

    write_scope / produces (build_target) は宣言の node 契約に従う。phase_ref は surface 宣言の
    phase_ref、無ければ decl.node_kind (pseudo-phase。P\\d+ 非該当ゆえ phase 逆走検査 (i) の対象外)。
    依存 (projection_rule.dependencies = surface gate が参照する component build nodes) は決定論
    近似として最終 phase marker への depends_on で実現する (全 component build 完了後に surface を
    build/gate する保守的上位集合。build completeness → ship completeness の順序)。
    required_fields (ドット path) の欠落は missing_required_field 契約どおり projection-fail
    (SurfaceProjectionError) とし、欠落 surface を黙って落とさない (fail-closed)。
    """
    template = str(decl.get("node_id_template") or "SURFACE-{surface_key}")
    required_fields = decl.get("required_fields") or []
    done_when = (decl.get("projection_rule") or {}).get("done_when") or []
    nodes: list[dict] = []
    edges: list[dict] = []
    for key in sorted(surfaces):
        sf = surfaces[key]
        missing = [f for f in required_fields if _dotted_get(sf, f) is None]
        if missing:
            raise SurfaceProjectionError(
                f"required surface {key!r} が required_fields を欠く (projection-fail): {missing}"
            )
        node_id = template.replace("{surface_key}", key)
        criterion = (
            f"builder={sf['builder']} (build_kind={sf['build_kind']}) が "
            f"{sf['build_target']} を build し quality_gates all_pass を満たす"
        )
        if done_when:
            criterion += f" (done_when: {', '.join(str(d) for d in done_when)})"
        nodes.append({
            "id": node_id,
            "title": f"required plugin surface build: {key}",
            "phase_ref": str(sf.get("phase_ref") or decl.get("node_kind") or "plugin-surface-build"),
            "entity_ref": None,
            "state": "pending",
            "write_scope": sf["write_scope"],
            "acceptance_criterion": criterion,
        })
        edges.append({"type": "produces", "from": node_id, "to": sf["build_target"]})
        if final_phase_root is not None:
            edges.append({"type": "depends_on", "from": node_id, "to": final_phase_root})
    return nodes, edges


def _derive_fixed_13_phase(plan_dir: Path) -> dict:
    """13 phase §5 タスク項目 + component-inventory.json から task-graph (未正準の生形) を導出する。

    1 チェックボックス項目 = 1 task node。entities_covered が複数なら各 entity ごとに node を生成し、
    空なら entity_ref=null の component 非依存タスクとする。parent_of で phase 仮想ルートへ連結し、
    component-inventory の depends_on を entity_ref 一致 node 集合間の depends_on エッジへ反映する。
    加えて couples_with 宣言 (接合が密な兄弟ペア) を同一 phase 兄弟の直列化 depends_on へ展開し、
    盲目並列による統合 finding 先送りを封じる (既存順序ペアは skip・id 昇順で decisive・phase 非逆走)。
    """
    plan_dir = Path(plan_dir)
    build_targets = _inventory_build_targets(plan_dir)
    comp_depends = _inventory_depends(plan_dir)
    couples = _inventory_couples(plan_dir)

    nodes: list[dict] = []
    edges: list[dict] = []
    # entity_ref -> その entity に属する node id 群 (depends_on 反映で使用)。
    nodes_by_entity: dict[str, list[str]] = {}
    phase_by_node: dict[str, int] = {}
    # couples 直列化の「同一 phase」等値判定は raw phase_ref 文字列で行う (下記 couples ブロック)。
    # _phase_order の int 等値は未知形式を全て 10_000 へ潰し validate(j)/accept の文字列等値と乖離するため。
    raw_phase_by_node: dict[str, str] = {}
    produced_entities: set[str] = set()
    # phase ライフサイクル順序 edge 導出用: phase marker (root) を出現順に、
    # 各 phase の leaf node 群を root ごとに記録する。
    phase_roots: list[str] = []
    leaves_by_root: dict[str, list[str]] = {}

    for pf in _phase_files(plan_dir):
        text = pf.read_text(encoding="utf-8")
        fm = specfm.parse_frontmatter(text)
        phase_ref = str(fm.get("id") or pf.stem)
        entities = fm.get("entities_covered") or []
        if not isinstance(entities, list):
            entities = []
        sections = specfm.phase_body_sections(text)
        items = _parse_checklist_items(sections.get(CHECKLIST_SECTION, ""))
        if not items:
            continue
        # phase 仮想ルート node (parent_of の親 + phase 完了集約 marker)。
        root_id = phase_ref
        nodes.append({
            "id": root_id,
            "title": str(fm.get("phase_name") or phase_ref),
            "phase_ref": phase_ref,
            "entity_ref": None,
            "state": "pending",
            "write_scope": root_id,
        })
        phase_roots.append(root_id)
        leaves_by_root.setdefault(root_id, [])
        # entities が空なら [None] で 1 系列だけ生成。
        entity_slots = entities if entities else [None]
        for e_idx, entity in enumerate(entity_slots):
            for i_idx, title in enumerate(items):
                ent_tag = entity if isinstance(entity, str) else "x"
                node_id = f"{phase_ref}-{ent_tag}-{i_idx + 1:02d}"
                write_scope = build_targets.get(entity, node_id) if isinstance(entity, str) else node_id
                nodes.append({
                    "id": node_id,
                    "title": title,
                    "phase_ref": phase_ref,
                    "entity_ref": entity if isinstance(entity, str) else None,
                    "state": "pending",
                    "write_scope": write_scope,
                })
                phase_by_node[node_id] = _phase_order(phase_ref)
                raw_phase_by_node[node_id] = phase_ref
                leaves_by_root[root_id].append(node_id)
                edges.append({"type": "parent_of", "from": root_id, "to": node_id})
                if isinstance(entity, str) and entity in build_targets and entity not in produced_entities:
                    edges.append({"type": "produces", "from": node_id, "to": build_targets[entity]})
                    produced_entities.add(entity)
                if isinstance(entity, str):
                    nodes_by_entity.setdefault(entity, []).append(node_id)

    # component 粒度 depends_on を entity_ref 一致 node 集合間の task depends_on へ反映。
    for cid, deps in comp_depends.items():
        downstream = nodes_by_entity.get(cid, [])
        for dep in deps:
            upstream = nodes_by_entity.get(dep, [])
            for dn in downstream:
                for up in upstream:
                    # phase ライフサイクル軸を逆走させない。component 依存は「同一または過去
                    # phase の prerequisite」にだけ展開し、P02 が P10 を待つような未来依存を
                    # task-graph へ焼かない。
                    if phase_by_node.get(up, 10_000) > phase_by_node.get(dn, 10_000):
                        continue
                    edges.append({"type": "depends_on", "from": dn, "to": up})

    # --- 接合が密な兄弟ペアの直列化 (couples_with → serialization depends_on) ---
    # 並列 task-graph が depends_on 無しの兄弟を盲目的に同一 ready-set へ同時 dispatch すると、
    # 接合が密なペア (共有 contract を挟む producer↔consumer 等) では統合 finding が両方 build
    # 後まで先送りされる (実観測された代償: 出力キー↔読取キー不一致で実 pipe が壊れる)。architect が
    # couples_with で宣言した密結合ペアを直列化し、先発の done=統合面が観測済みになってから後発を
    # build させる。直列化の機構は既存 depends_on を流用する (consumer=compute-ready-set が depends_on
    # を直列化するため追加 edge type/機構が不要・生成ハーネスの checklist へも depends_on として伝播)。
    # 規則: (1) 既に component depends_on の**推移閉包**で順序付いたペアは skip (直接 A→B だけでなく
    #           推移依存 A→C→B も含む。id 昇順向きと逆走すると cycle 化するため直列化済とみなし介入しない)。
    #       (2) 向きは entity id 昇順で決定論固定 (小さい id を prereq=先発)。
    #       (3) **同一 phase 兄弟のみ**直列化する (盲目並列の risk は同一 phase に限る。異 phase ペアは
    #           phase 順序 edge が既に直列化するため無介入=redundant edge/(j) 偽陽性を避ける)。
    comp_reach = _transitive_closure(comp_depends)
    existing_dep_edges = {
        (e["from"], e["to"]) for e in edges if e.get("type") == "depends_on"
    }
    cross_phase_declared: list[tuple[str, str]] = []
    for pair in couples:
        if len(pair) != 2:
            continue
        a, b = sorted(pair)
        # a→…→b もしくは b→…→a の推移順序が既にあれば直列化済 (逆走 cycle を封じ介入しない)。
        if b in comp_reach.get(a, set()) or a in comp_reach.get(b, set()):
            continue
        prereq, dependent = a, b  # id 昇順: 小さい id を先発 (prereq)
        dep_nodes = nodes_by_entity.get(dependent, [])
        pre_nodes = nodes_by_entity.get(prereq, [])
        serialized_any = False
        for dn in dep_nodes:
            for up in pre_nodes:
                if up == dn:
                    continue
                # 同一 phase のみ直列化。等値は **raw phase_ref 文字列**で判定し validate(j)/accept と
                # 同一述語へ揃える (int 化 _phase_order は未知形式を潰し writer/checker を乖離させる)。
                if raw_phase_by_node.get(up) != raw_phase_by_node.get(dn):
                    continue  # cross-phase は phase 順序 edge が直列化する (無介入)
                serialized_any = True
                if (dn, up) in existing_dep_edges:
                    continue
                edges.append({"type": "depends_on", "from": dn, "to": up})
                existing_dep_edges.add((dn, up))
        # 宣言されたが同一 phase 兄弟対が無く直列化 edge が 1 本も焼かれなかった couples は
        # cross-phase の silent no-op。宣言者が「直列化した」と誤認しないよう advisory を集める
        # (graph 出力は不変・stderr のみ)。因果順序が要るなら depends_on を使う旨を促す。
        if dep_nodes and pre_nodes and not serialized_any:
            cross_phase_declared.append((a, b))
    for a, b in cross_phase_declared:
        print(
            f"advisory: couples_with {a}<->{b} は異 phase 宣言のため直列化 edge を焼きません "
            f"(phase 順序 edge に委譲)。build 順序の因果依存が必要なら depends_on を使ってください。",
            file=sys.stderr,
        )

    # --- phase ライフサイクル順序を task-graph へ焼く (event 駆動チェーンの graph 保証) ---
    # ユーザー要件「1 task が完了 → done と記述される → それが次 task の発火条件になる」を
    # 構造で保証する。既存の x-node (entity_ref=null) は depends_on を一切持たず t=0 で全 ready に
    # なるため、final-review が実装 phase 完了前に done 化する順序逆転が起きていた。以下 2 規則で封じる:
    #   (1) phase marker は自 phase の全 leaf に depends_on する (marker done = phase 完了の集約点)。
    #       from=marker/to=leaf は parent_of と同じ marker→leaf 向きなので DAG 閉路を作らない。
    #   (2) 各 phase の leaf は直前 phase marker に depends_on する (前 phase 完了記述が発火条件)。
    # これで「前 phase の全 leaf done → marker ready→done → 次 phase leaf ready」の直列チェーンになる。
    # compute-ready-set は readiness を depends_on のみで判定し parent_of を無視するため
    # marker↔leaf の parent_of は readiness に干渉しない (デッドロックしない)。
    for root_id in phase_roots:
        for leaf in leaves_by_root.get(root_id, []):
            edges.append({"type": "depends_on", "from": root_id, "to": leaf})
    for prev_root, cur_root in zip(phase_roots, phase_roots[1:]):
        for leaf in leaves_by_root.get(cur_root, []):
            edges.append({"type": "depends_on", "from": leaf, "to": prev_root})

    # --- required plugin_level_surfaces の build node 射影 (surface_build_projection 宣言時のみ) ---
    # components[] だけが build/gate を駆動し required surface (manifest/schemas/composition 等) が
    # builder 未割当で構造的に射影対象外になる片翼を封じる (lesson-surfaces-must-be-builder-assigned)。
    # 宣言不在の旧 inventory では本ブロックは no-op で従来出力と byte 同一 (graph_hash 不変)。
    surface_proj = _inventory_surface_projection(plan_dir)
    if surface_proj is not None:
        decl, surfaces = surface_proj
        s_nodes, s_edges = _project_surface_nodes(
            decl, surfaces, phase_roots[-1] if phase_roots else None)
        nodes.extend(s_nodes)
        edges.extend(s_edges)

    return {"schema_version": "1.0", "nodes": nodes, "edges": edges}


def derive(plan_dir: Path) -> dict:
    """shape marker で producer を分岐する。未指定=fixed は既存 bytes/behavior を維持。"""
    plan_dir = Path(plan_dir)
    marker = shape_marker(plan_dir)
    if marker == _TARGET_SHAPE:
        return _derive_task_spec_shape(plan_dir)
    return _derive_fixed_13_phase(plan_dir)


def _canon_node(n: dict) -> dict:
    out: dict = {}
    for k in _NODE_REQUIRED_KEYS:
        out[k] = n.get(k)
    for k in _NODE_OPTIONAL_KEYS:
        # acceptance_criterion は歴史的に None を省く (既存出力不変)。C17 の 3 キーは present なら
        # null も出力する (direct-task の route_ref=null は「明示的に route を持たない」意味を担い
        # 省略と区別するため)。fixed-13-phase の node はどの optional キーも持たず出力が byte 不変。
        if k == "acceptance_criterion":
            if k in n and n[k] is not None:
                out[k] = n[k]
        elif k in n:
            out[k] = n[k]
    return out


def _canon_edge(e: dict) -> dict:
    return {k: e.get(k) for k in _EDGE_KEYS}


def canonicalize(graph: dict) -> dict:
    """graph を正準形へ整える (nodes=id 昇順 / edges=(type,from,to) 昇順 / 固定 key 順)。冪等。"""
    nodes = [_canon_node(n) for n in graph.get("nodes", [])]
    edges = [_canon_edge(e) for e in graph.get("edges", [])]
    nodes.sort(key=lambda n: str(n.get("id")))
    edges.sort(key=lambda e: (str(e.get("type")), str(e.get("from")), str(e.get("to"))))
    return {"schema_version": graph.get("schema_version", "1.0"), "nodes": nodes, "edges": edges}


def canonical_json(graph: dict) -> str:
    """canonical graph の JSON 文字列 (末尾 newline なし・graph_hash とファイル書込の共通担体)。"""
    return json.dumps(canonicalize(graph), ensure_ascii=False, indent=2)


def graph_hash(graph: dict) -> str:
    """canonical bytes の sha256 (`sha256:<64hex>`)。単一 writer の canonicalize 出力から導出。"""
    return "sha256:" + hashlib.sha256(canonical_json(graph).encode("utf-8")).hexdigest()


def _usage() -> int:
    print("usage: derive-task-graph.py <PLAN_DIR> | --print-graph-hash <task-graph.json>", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return _usage()

    if argv[0] == "--print-graph-hash":
        if len(argv) < 2:
            return _usage()
        path = Path(argv[1])
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"read/parse error: {exc}", file=sys.stderr)
            return 2
        try:
            h = graph_hash(graph)
        except (TypeError, AttributeError, KeyError) as exc:
            print(f"graph invalid, cannot hash: {exc}", file=sys.stderr)
            return 1
        print(h)
        return 0

    # 既定経路: PLAN_DIR から derive → canonicalize → task-graph.json 書込 (唯一の writer)。
    plan_dir = Path(argv[0])
    if not plan_dir.is_dir():
        print(f"not a directory: {plan_dir}", file=sys.stderr)
        return 2
    try:
        graph = derive(plan_dir)
    except SurfaceProjectionError as exc:
        # missing_required_field: projection-fail — 欠落 surface を黙って落とした graph を書かない。
        print(f"surface projection failed: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"derive error: {exc}", file=sys.stderr)
        return 1
    out_path = plan_dir / "task-graph.json"
    out_path.write_text(canonical_json(graph) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
