"""validate-task-graph.py の機能テスト (C2/C3/C11・conftest 非依存)。

10 検査 (a)DAG非循環 / (b)orphan0 / (c)producer一意 / (d)inventory矛盾0 /
(e)consumes producer実在 / (f)非正準拒否 / (g)node.state永続4値 / (h)dangling edge端点0 /
(i)phase非逆走 / (j)couples_with直列化実現 を、P04 C2
受入例 (満たす例=exit0 / 満たさない例=inventory矛盾 exit1) を含めて網羅する。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


vtg = _load("validate-task-graph")
dtg = _load("derive-task-graph")


# ─────────────────── fixtures ───────────────────
INVENTORY = {"components": [{"id": "C01", "depends_on": []}, {"id": "C02", "depends_on": ["C01"]}]}


def _node(nid, entity, phase="P05", state="pending"):
    return {
        "id": nid,
        "title": f"{nid} title",
        "phase_ref": phase,
        "entity_ref": entity,
        "state": state,
        "write_scope": nid,
    }


def _c2_graph():
    """P04 C2 受入例: 4 node + depends_on/produces/consumes 各 4 本 (canonical 化して返す)。"""
    nodes = [
        _node("T1", "C01", phase="P02"),
        _node("T2", "C01"),
        _node("T3", "C02"),
        _node("T4", "C01"),
    ]
    edges = []
    # depends_on: from=dependent, to=dependency
    for f, t in [("T2", "T1"), ("T3", "T1"), ("T4", "T2"), ("T4", "T3")]:
        edges.append({"type": "depends_on", "from": f, "to": t})
    # produces: from=node, to=artifact
    for f, t in [("T1", "A1"), ("T2", "A2"), ("T3", "A3"), ("T4", "A4")]:
        edges.append({"type": "produces", "from": f, "to": t})
    # consumes: from=artifact, to=node (検査 (e) は consumes.from を artifact とみなす)
    for f, t in [("A1", "T2"), ("A1", "T3"), ("A2", "T4"), ("A3", "T4")]:
        edges.append({"type": "consumes", "from": f, "to": t})
    return dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})


# ─────────────────── 満たす例 (exit0) ───────────────────
def test_c2_accept_example_no_violations():
    assert vtg.validate(_c2_graph(), INVENTORY) == []


def test_c2_graph_is_canonical_idempotent():
    g = _c2_graph()
    assert dtg.canonicalize(g) == g  # (f) を踏まないこと


# ─────────────────── (a) DAG 非循環 ───────────────────
def test_a_cycle_detected_depends_on():
    nodes = [_node("X", "C01"), _node("Y", "C01")]
    edges = [
        {"type": "depends_on", "from": "X", "to": "Y"},
        {"type": "depends_on", "from": "Y", "to": "X"},
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(a)") for msg in v)


def test_a_cycle_via_parent_of():
    nodes = [_node("X", None), _node("Y", None)]
    edges = [
        {"type": "parent_of", "from": "X", "to": "Y"},
        {"type": "parent_of", "from": "Y", "to": "X"},
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    assert any(msg.startswith("(a)") for msg in vtg.validate(g, {}))


# ─────────────────── (h) dangling edge 端点実在 (F5) ───────────────────
def test_h_dangling_depends_on_endpoint_is_violation():
    """depends_on の to が nodes に不在 (dangling) → (h) violation で plan-time 拒否。"""
    nodes = [_node("X", "C01")]
    edges = [{"type": "depends_on", "from": "X", "to": "MISSING"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(h)") and "MISSING" in msg for msg in v)


def test_h_produces_consumes_artifact_endpoints_not_flagged():
    """produces/consumes は artifact 端点ゆえ (h) の対象外 (誤検出しない)。"""
    assert not any(msg.startswith("(h)") for msg in vtg.validate(_c2_graph(), INVENTORY))


# ─────────────────── (i) phase 依存方向 ───────────────────
def test_i_future_phase_dependency_is_violation():
    nodes = [_node("EARLY", "C02", phase="P02"), _node("LATE", "C01", phase="P10")]
    edges = [{"type": "depends_on", "from": "EARLY", "to": "LATE"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {"components": []})
    assert any(msg.startswith("(i)") and "EARLY" in msg and "LATE" in msg for msg in v)


def test_i_same_or_past_phase_dependency_is_allowed():
    nodes = [_node("EARLY", "C01", phase="P02"), _node("LATE", "C02", phase="P10")]
    edges = [{"type": "depends_on", "from": "LATE", "to": "EARLY"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    assert not any(msg.startswith("(i)") for msg in vtg.validate(g, {"components": []}))


# ─────────────────── (b) orphan ───────────────────
def test_b_orphan_node_detected():
    nodes = [_node("T1", "C01"), _node("ORPH", "C01")]
    edges = [{"type": "depends_on", "from": "T1", "to": "T1"}]  # ORPH がどの edge にも現れない
    # cycle を避けるため self-loop は使わず、別 node へ。
    edges = [
        {"type": "produces", "from": "T1", "to": "A1"},
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(b)") and "ORPH" in msg for msg in v)
    assert not any("T1" in msg and msg.startswith("(b)") for msg in v)


# ─────────────────── (c) producer 一意 ───────────────────
def test_c_duplicate_producer_detected():
    nodes = [_node("T1", "C01"), _node("T2", "C01")]
    edges = [
        {"type": "produces", "from": "T1", "to": "A1"},
        {"type": "produces", "from": "T2", "to": "A1"},  # 同一 artifact を 2 node が produce
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(c)") and "A1" in msg for msg in v)


# ─────────────────── (d) inventory 矛盾 ───────────────────
def test_d_inventory_contradiction_when_realizing_edge_removed():
    """P04 満たさない例: T3→T1 (C02 depends C01 の実現) を削除すると inventory 矛盾 1 件で exit1。"""
    g = _c2_graph()
    edges = [e for e in g["edges"] if not (e["type"] == "depends_on" and e["from"] == "T3" and e["to"] == "T1")]
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": g["nodes"], "edges": edges})
    v = vtg.validate(g2, INVENTORY)
    dviol = [msg for msg in v if msg.startswith("(d)")]
    assert len(dviol) == 1
    assert v == dviol  # inventory 矛盾のみ (他検査は緑)


def test_d_reversed_only_edge_detected():
    """逆向き edge のみ (正方向欠落) も (d) で捕捉する。"""
    nodes = [_node("A", "C01"), _node("B", "C02")]
    # inventory: C02 depends_on C01 だが edge は C01(A)→C02(B) の逆向きのみ
    edges = [{"type": "depends_on", "from": "A", "to": "B"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, INVENTORY)
    assert any(msg.startswith("(d)") for msg in v)


def test_d_no_nodes_for_component_skips():
    """component の node が graph に無ければ (d) は発火しない。"""
    nodes = [_node("A", "C01")]  # C02 の node なし
    edges = [{"type": "produces", "from": "A", "to": "X1"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, INVENTORY)
    assert not any(msg.startswith("(d)") for msg in v)


# ─────────────────── (e) consumes producer 不在 ───────────────────
def test_e_consumes_missing_producer():
    g = _c2_graph()
    edges = list(g["edges"]) + [{"type": "consumes", "from": "A99", "to": "T4"}]
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": g["nodes"], "edges": edges})
    v = vtg.validate(g2, INVENTORY)
    assert any(msg.startswith("(e)") and "A99" in msg for msg in v)


def test_e_rejects_reversed_consumes_direction():
    g = _c2_graph()
    edges = list(g["edges"]) + [{"type": "consumes", "from": "T4", "to": "A1"}]
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": g["nodes"], "edges": edges})
    v = vtg.validate(g2, INVENTORY)
    assert any(msg.startswith("(e)") and "T4" in msg and "no producer" in msg for msg in v)


# ─────────────────── (f) 非正準拒否 ───────────────────
def test_f_non_canonical_rejected():
    g = _c2_graph()
    # nodes を id 降順に並べ替え (非正準)
    scrambled = {"schema_version": "1.0", "nodes": list(reversed(g["nodes"])), "edges": g["edges"]}
    v = vtg.validate(scrambled, INVENTORY)
    assert any(msg.startswith("(f)") for msg in v)


def test_f_extra_toplevel_key_rejected():
    g = _c2_graph()
    g2 = dict(g)
    g2["extra"] = "hand-added"
    assert any(msg.startswith("(f)") for msg in vtg.validate(g2, INVENTORY))


# ─────────────────── (g) canonical node.state=pending seed ───────────────────
def test_g_ready_state_rejected():
    g = _c2_graph()
    nodes = [dict(n) for n in g["nodes"]]
    nodes[0]["state"] = "ready"
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": g["edges"]})
    v = vtg.validate(g2, INVENTORY)
    assert any(msg.startswith("(g)") and "ready" in msg for msg in v)


def test_g_done_state_rejected_from_canonical_graph():
    g = _c2_graph()
    nodes = [dict(n) for n in g["nodes"]]
    nodes[0]["state"] = "done"
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": g["edges"]})
    v = vtg.validate(g2, INVENTORY)
    assert any(msg.startswith("(g)") and "task-state.json" in msg for msg in v)


# ─────────────────── main() CLI ───────────────────
def _write_plan(tmp_path, graph, inventory=None):
    (tmp_path / "task-graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    if inventory is not None:
        (tmp_path / "component-inventory.json").write_text(
            json.dumps(inventory, ensure_ascii=False), encoding="utf-8"
        )


def test_main_exit0_on_valid_graph(tmp_path):
    _write_plan(tmp_path, _c2_graph(), INVENTORY)
    assert vtg.main([str(tmp_path)]) == 0


def test_main_exit1_on_violation(tmp_path, capsys):
    g = _c2_graph()
    edges = [e for e in g["edges"] if not (e["type"] == "depends_on" and e["from"] == "T3" and e["to"] == "T1")]
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": g["nodes"], "edges": edges})
    _write_plan(tmp_path, g2, INVENTORY)
    assert vtg.main([str(tmp_path)]) == 1
    assert "(d)" in capsys.readouterr().out


def test_main_exit0_without_inventory(tmp_path):
    """component-inventory.json 欠落時は inventory 空扱いで (d) をスキップ。"""
    _write_plan(tmp_path, _c2_graph(), inventory=None)
    assert vtg.main([str(tmp_path)]) == 0


def test_main_usage_error_no_args():
    assert vtg.main([]) == 2


def test_main_usage_error_too_many_args():
    assert vtg.main(["a", "b"]) == 2


def test_main_not_a_directory(tmp_path):
    assert vtg.main([str(tmp_path / "missing")]) == 2


def test_main_bad_graph_json(tmp_path):
    (tmp_path / "task-graph.json").write_text("{ not json", encoding="utf-8")
    assert vtg.main([str(tmp_path)]) == 2


def test_main_bad_inventory_json(tmp_path):
    _write_plan(tmp_path, _c2_graph(), inventory=None)
    (tmp_path / "component-inventory.json").write_text("{ bad", encoding="utf-8")
    assert vtg.main([str(tmp_path)]) == 2


# ─────────────────── (j) couples_with 直列化実現 ───────────────────
def _couple_inventory(couples=("C06",)):
    return {"components": [
        {"id": "C05", "depends_on": [], "couples_with": list(couples)},
        {"id": "C06", "depends_on": []},
    ]}


def _couple_graph(serialized: bool):
    """C05/C06 同一 phase 兄弟 + phase marker。serialized=True なら直列化 depends_on を含む。"""
    nodes = [_node("P05-C05-01", "C05"), _node("P05-C06-01", "C06"), _node("P05", None)]
    edges = [{"type": "parent_of", "from": "P05", "to": "P05-C05-01"},
             {"type": "parent_of", "from": "P05", "to": "P05-C06-01"}]
    if serialized:
        edges.append({"type": "depends_on", "from": "P05-C06-01", "to": "P05-C05-01"})
    return dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})


def test_j_couples_realized_passes():
    g = _couple_graph(True)
    assert vtg._check_couples(vtg._nodes(g), vtg._edges(g), _couple_inventory()) == []


def test_j_couples_unrealized_flagged():
    g = _couple_graph(False)
    v = vtg._check_couples(vtg._nodes(g), vtg._edges(g), _couple_inventory())
    assert any(x.startswith("(j)") and "C05<->C06" in x for x in v)


def test_j_couples_unknown_reference_flagged():
    inv = {"components": [{"id": "C05", "depends_on": [], "couples_with": ["C99"]}]}
    g = _couple_graph(True)
    v = vtg._check_couples(vtg._nodes(g), vtg._edges(g), inv)
    assert any("unknown component" in x and "C99" in x for x in v)


def test_j_couples_skipped_when_component_ordered():
    # C05 depends_on C06 で既に順序付き → (d) が担い (j) は対象外 (直列化 edge 不在でも非 violation)。
    inv = {"components": [
        {"id": "C05", "depends_on": ["C06"], "couples_with": ["C06"]},
        {"id": "C06", "depends_on": []},
    ]}
    g = _couple_graph(False)
    v = vtg._check_couples(vtg._nodes(g), vtg._edges(g), inv)
    assert not any(x.startswith("(j)") for x in v)


# ─────────────────── (k) task-graph-derived target shape ───────────────────
def _target_leaf(nid="T1", *, phase="P05", kind="direct-task", route=None):
    node = _node(nid, "C01" if kind == "component-build" else None, phase=phase)
    node.update({
        "acceptance_criterion": f"{nid} の成果物が verify で一致する",
        "execution_kind": kind,
        "route_ref": route,
        "task_spec_ref": f"task-specs/{nid}.md",
    })
    return node


def _write_target_spec(plan_dir: Path, nid="T1"):
    specs = plan_dir / "task-specs"
    specs.mkdir(exist_ok=True)
    (specs / f"{nid}.md").write_text(
        "---\n"
        f"id: {nid}\n"
        f"title: {nid} title\n"
        "objective: 成果物を生成する\n"
        "verify: pytest tests/test_target.py\n"
        "---\n",
        encoding="utf-8",
    )


def _target_graph():
    leaf = _target_leaf()
    root = _node("P05", None, phase="P05")
    root.update({"execution_kind": "phase-gate", "route_ref": None, "task_spec_ref": None})
    return dtg.canonicalize({
        "schema_version": "1.0",
        "nodes": [root, leaf],
        "edges": [
            {"type": "parent_of", "from": "P05", "to": "T1"},
            {"type": "depends_on", "from": "P05", "to": "T1"},
            {"type": "produces", "from": "T1", "to": "A1"},
        ],
    })


def test_k_target_shape_renderer_prerequisites_pass(tmp_path):
    _write_target_spec(tmp_path)
    assert vtg.validate(
        _target_graph(), {"components": []}, marker="task-graph-derived", plan_dir=tmp_path
    ) == []


def test_k_target_leaf_missing_acceptance_is_violation(tmp_path):
    _write_target_spec(tmp_path)
    graph = _target_graph()
    leaf = next(n for n in graph["nodes"] if n["id"] == "T1")
    leaf.pop("acceptance_criterion")
    graph = dtg.canonicalize(graph)
    violations = vtg.validate(
        graph, {"components": []}, marker="task-graph-derived", plan_dir=tmp_path
    )
    assert any(v.startswith("(k)") and "acceptance_criterion" in v for v in violations)


def test_k_target_leaf_without_produces_is_violation(tmp_path):
    _write_target_spec(tmp_path)
    graph = _target_graph()
    graph["edges"] = [e for e in graph["edges"] if e["type"] != "produces"]
    graph = dtg.canonicalize(graph)
    violations = vtg.validate(
        graph, {"components": []}, marker="task-graph-derived", plan_dir=tmp_path
    )
    assert any(v.startswith("(k)") and "produces artifact" in v for v in violations)


def test_k_component_build_requires_route_ref(tmp_path):
    _write_target_spec(tmp_path)
    graph = _target_graph()
    leaf = next(n for n in graph["nodes"] if n["id"] == "T1")
    leaf["execution_kind"] = "component-build"
    graph = dtg.canonicalize(graph)
    violations = vtg.validate(
        graph, {"components": []}, marker="task-graph-derived", plan_dir=tmp_path
    )
    assert any(v.startswith("(k)") and "route_ref" in v for v in violations)


def test_main_unknown_shape_fails_closed(tmp_path, capsys):
    (tmp_path / "index.md").write_text(
        "---\nid: IDX0\nshape_marker: future-shape\n---\n", encoding="utf-8"
    )
    _write_plan(tmp_path, _target_graph(), {"components": []})
    assert vtg.main([str(tmp_path)]) == 1
    assert "unknown shape_marker" in capsys.readouterr().out


# ─────────────────── (l) bootstrap→target shape 移行 gate ───────────────────
# GAP-BOOTSTRAP-TARGET-SHAPE-001: fixed-13-phase bootstrap は execution_kind 全不在で
# legacy join (entity_ref→route 暗黙推測)。target shape は明示 route_ref parity を必須化し、
# 「一部だけ移行した中途半端 shape」を fail-closed で拒否する marker 非依存 additive 層。
def _kinded(node, kind, route=None, spec="task-specs/x.md"):
    node = dict(node)
    node.update({"execution_kind": kind, "route_ref": route, "task_spec_ref": spec})
    return node


def test_l_full_target_shape_no_migration_violation():
    """entity_ref 全 node が execution_kind 携帯・component-build に明示 route_ref → (l) 無し。"""
    nodes = [
        _kinded(_node("P05", None), "phase-gate", spec=None),
        _kinded(_node("P05-C01-01", "C01"), "component-build", route="route/build-C01"),
        _kinded(_node("P05-x-01", None), "direct-task"),
    ]
    assert vtg._check_migration_gate(nodes, "task-graph-derived") == []


def test_l_partial_adoption_fails_closed():
    """execution_kind 携帯 node が居るのに entity_ref node の一部が非携帯 → (l1) で拒否。"""
    nodes = [
        _kinded(_node("P05-C01-01", "C01"), "component-build", route="route/build-C01"),
        _node("P05-C02-01", "C02"),  # execution_kind 非携帯の legacy 残骸
    ]
    v = vtg._check_migration_gate(nodes, "fixed-13-phase")
    assert any(x.startswith("(l)") and "P05-C02-01" in x and "execution_kind" in x for x in v)


def test_l_bootstrap_all_absent_non_firing():
    """fixed-13-phase + execution_kind 全不在 (entity_ref node 多数あり) → 非発火 (後方互換)。"""
    nodes = [_node("P05-C01-01", "C01"), _node("P09-C02-01", "C02"), _node("P05", None)]
    assert vtg._check_migration_gate(nodes, "fixed-13-phase") == []


def test_l_task_graph_derived_marker_without_execution_kind_fails():
    """task-graph-derived marker で dispatchable node が execution_kind 非携帯 → (l1) で拒否。"""
    nodes = [_node("P05-C01-01", "C01")]
    v = vtg._check_migration_gate(nodes, "task-graph-derived")
    assert any(x.startswith("(l)") and "execution_kind" in x for x in v)


def test_l_component_build_missing_route_ref_fails():
    """execution_kind=component-build で route_ref 空 → (l2) 明示 route parity 違反。"""
    nodes = [_kinded(_node("P05-C01-01", "C01"), "component-build", route=None)]
    v = vtg._check_migration_gate(nodes, "task-graph-derived")
    assert any(x.startswith("(l)") and "route_ref" in x for x in v)


def test_l_direct_task_with_entity_ref_allowed():
    """direct-task は entity_ref を持ち route_ref=null でも schema 通りで (l2) 対象外 → 非違反。"""
    nodes = [_kinded(_node("P05-C01-01", "C01"), "direct-task", route=None)]
    assert vtg._check_migration_gate(nodes, "task-graph-derived") == []


def test_l_validate_integration_flags_partial_under_fixed_marker():
    """marker=fixed-13-phase でも execution_kind が混入すれば validate() 全体が (l) を返す
    (移行 gate が marker 非依存の additive 層であることの integration 証明)。"""
    migrated = _kinded(_node("P05-C01-01", "C01"), "component-build", route="route/build-C01",
                       spec="task-specs/P05-C01-01.md")
    legacy = _node("P05-C02-01", "C02")  # execution_kind 非携帯の legacy 残骸
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": [migrated, legacy], "edges": [
        {"type": "produces", "from": "P05-C01-01", "to": "A1"},
        {"type": "produces", "from": "P05-C02-01", "to": "A2"},
    ]})
    v = vtg.validate(g, {"components": []}, marker="fixed-13-phase")
    assert any(x.startswith("(l)") and "P05-C02-01" in x for x in v)


def test_l_validate_integration_full_target_no_l_violation(tmp_path):
    """完全 target shape (phase-gate + direct-task leaf) は validate() 全体でも (l) を出さない。"""
    _write_target_spec(tmp_path)
    v = vtg.validate(
        _target_graph(), {"components": []}, marker="task-graph-derived", plan_dir=tmp_path
    )
    assert not any(x.startswith("(l)") for x in v)


_BOOTSTRAP_PLAN_DIRS = [
    "plugin-dev-planner",
    "harness-creator",
    "mf-kessai-invoice-check",
    "mf-kessai-invoice-check-fidelity",
    "mf-kessai-invoice-check-matching-rootcause",
    "with-task-graph-goalseek",
]


def test_l_bootstrap_plans_migration_gate_non_firing():
    """既存 6 bootstrap plan は execution_kind 全不在=移行 gate 非発火 (exit code 不変で後方互換)。

    task-graph.json/index.md を実配置から読み、_check_migration_gate が空を返すことを固定する。
    他検査 (i)/(g) 等の状態に依存せず「移行 gate が bootstrap plan へ violation を 1 件も追加しない」
    という additive 非回帰を直接証明する (plugin-plans/ は本 skill から read-only)。
    """
    repo_root = Path(__file__).resolve().parents[5]
    for name in _BOOTSTRAP_PLAN_DIRS:
        plan_dir = repo_root / "plugin-plans" / name
        graph = json.loads((plan_dir / "task-graph.json").read_text(encoding="utf-8"))
        marker = dtg.shape_marker(plan_dir)
        v = vtg._check_migration_gate(vtg._nodes(graph), marker)
        assert v == [], f"{name}: 移行 gate は bootstrap plan で非発火であるべき: {v[:3]}"
