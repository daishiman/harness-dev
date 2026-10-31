"""validate-task-graph.py の bootstrap→target shape 移行 gate 回帰テスト。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_base_tests():
    path = Path(__file__).with_name("test_validate_task_graph.py")
    spec = importlib.util.spec_from_file_location("validate_task_graph_base_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_base_tests()
vtg = BASE.vtg
dtg = BASE.dtg
_node = BASE._node
_target_graph = BASE._target_graph
_write_target_spec = BASE._write_target_spec


def _kinded(node, kind, route=None, spec="task-specs/x.md"):
    node = dict(node)
    node.update({"execution_kind": kind, "route_ref": route, "task_spec_ref": spec})
    return node


def test_l_full_target_shape_no_migration_violation():
    """全 node が target shape 契約を満たす場合は移行違反を出さない。"""
    nodes = [
        _kinded(_node("P05", None), "phase-gate", spec=None),
        _kinded(
            _node("P05-C01-01", "C01"),
            "component-build",
            route="route/build-C01",
        ),
        _kinded(_node("P05-x-01", None), "direct-task"),
    ]
    assert vtg._check_migration_gate(nodes, "task-graph-derived") == []


def test_l_partial_adoption_fails_closed():
    """target shape の部分導入は legacy node を名指しして拒否する。"""
    nodes = [
        _kinded(
            _node("P05-C01-01", "C01"),
            "component-build",
            route="route/build-C01",
        ),
        _node("P05-C02-01", "C02"),
    ]
    violations = vtg._check_migration_gate(nodes, "fixed-13-phase")
    assert any(
        violation.startswith("(l)")
        and "P05-C02-01" in violation
        and "execution_kind" in violation
        for violation in violations
    )


def test_l_bootstrap_all_absent_non_firing():
    """fixed-13-phase で execution_kind 全不在なら後方互換で非発火。"""
    nodes = [
        _node("P05-C01-01", "C01"),
        _node("P09-C02-01", "C02"),
        _node("P05", None),
    ]
    assert vtg._check_migration_gate(nodes, "fixed-13-phase") == []


def test_l_task_graph_derived_marker_without_execution_kind_fails():
    nodes = [_node("P05-C01-01", "C01")]
    violations = vtg._check_migration_gate(nodes, "task-graph-derived")
    assert any(
        violation.startswith("(l)") and "execution_kind" in violation
        for violation in violations
    )


def test_l_component_build_missing_route_ref_fails():
    nodes = [
        _kinded(
            _node("P05-C01-01", "C01"),
            "component-build",
            route=None,
        )
    ]
    violations = vtg._check_migration_gate(nodes, "task-graph-derived")
    assert any(
        violation.startswith("(l)") and "route_ref" in violation
        for violation in violations
    )


def test_l_direct_task_with_entity_ref_allowed():
    nodes = [
        _kinded(
            _node("P05-C01-01", "C01"),
            "direct-task",
            route=None,
        )
    ]
    assert vtg._check_migration_gate(nodes, "task-graph-derived") == []


def test_l_validate_integration_flags_partial_under_fixed_marker():
    migrated = _kinded(
        _node("P05-C01-01", "C01"),
        "component-build",
        route="route/build-C01",
        spec="task-specs/P05-C01-01.md",
    )
    legacy = _node("P05-C02-01", "C02")
    graph = dtg.canonicalize(
        {
            "schema_version": "1.0",
            "nodes": [migrated, legacy],
            "edges": [
                {"type": "produces", "from": "P05-C01-01", "to": "A1"},
                {"type": "produces", "from": "P05-C02-01", "to": "A2"},
            ],
        }
    )
    violations = vtg.validate(
        graph,
        {"components": []},
        marker="fixed-13-phase",
    )
    assert any(
        violation.startswith("(l)") and "P05-C02-01" in violation
        for violation in violations
    )


def test_l_validate_integration_full_target_no_l_violation(tmp_path):
    _write_target_spec(tmp_path)
    violations = vtg.validate(
        _target_graph(),
        {"components": []},
        marker="task-graph-derived",
        plan_dir=tmp_path,
    )
    assert not any(violation.startswith("(l)") for violation in violations)


_BOOTSTRAP_PLAN_DIRS = [
    "plugin-dev-planner",
    "harness-creator",
    "mf-kessai-invoice-check",
    "mf-kessai-invoice-check-fidelity",
    "mf-kessai-invoice-check-matching-rootcause",
    "with-task-graph-goalseek",
]


def test_l_bootstrap_plans_migration_gate_non_firing():
    """既存 bootstrap plan の migration gate 非発火を実配置で確認する。"""
    repo_root = Path(__file__).resolve().parents[5]
    plans_root = repo_root / "plugin-plans"
    if not plans_root.is_dir():
        pytest.skip("plugin-plans/ 不在: bootstrap plan 実配置なし (対象なし)")
    for name in _BOOTSTRAP_PLAN_DIRS:
        plan_dir = plans_root / name
        graph = json.loads(
            (plan_dir / "task-graph.json").read_text(encoding="utf-8")
        )
        marker = dtg.shape_marker(plan_dir)
        violations = vtg._check_migration_gate(vtg._nodes(graph), marker)
        assert violations == [], (
            f"{name}: 移行 gate は bootstrap plan で非発火であるべき: "
            f"{violations[:3]}"
        )
