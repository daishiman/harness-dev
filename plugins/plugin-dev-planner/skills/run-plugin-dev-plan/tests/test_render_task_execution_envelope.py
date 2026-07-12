"""render-task-execution-envelope.py の機能テスト (C17)。

conftest 非依存でローカルロード。build_envelope (合成 + fail-closed 群) と main() を網羅する。
正本の受入例は phase-04-test-design.md の C17 節。
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


RTE = _load("render-task-execution-envelope")


def _node(**over):
    base = {
        "id": "T2",
        "title": "derive-task-graph.py 設計確定",
        "phase_ref": "P05",
        "entity_ref": "C01",
        "state": "pending",
        "write_scope": "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/",
        "execution_kind": "component-build",
        "route_ref": "C01",
        "task_spec_ref": "task-specs/T2.md",
        "acceptance_criterion": "task spec 1件から実行可能leaf 1件を導出する",
    }
    base.update(over)
    return base


def _spec(**over):
    base = {
        "objective": "derive-task-graph.py の決定論導出ルールを設計する",
        "verify": "pytest tests/test_derive_task_graph.py",
        "acceptance_criteria": ["C2 上表と一致する task-graph を導出する"],
        "knowledge_refs": [],
    }
    base.update(over)
    return base


def _graph(node, edges=None):
    return {"schema_version": "1.0", "nodes": [node], "edges": edges or []}


# ─────────────────── build_envelope: 満たす例 ───────────────────
def test_component_build_envelope_complete():
    node = _node()
    graph = _graph(node, edges=[{"type": "consumes", "from": "A1", "to": "T2"}])
    env, viol = RTE.build_envelope(node, _spec(), graph)
    assert viol == []
    assert env["task_id"] == "T2"
    assert env["execution_kind"] == "component-build"
    assert env["phase_policy_ref"] == "P05"
    assert env["component_route"] == "C01"
    assert env["injected_inputs"] == ["A1"]
    # node.acceptance_criterion + spec.acceptance_criteria が統合される
    assert len(env["acceptance_criteria"]) == 2
    assert env["verify"] == "pytest tests/test_derive_task_graph.py"
    assert env["injected_notes"] == {"went_well": [], "friction_points": [], "downstream_watchouts": []}


def test_direct_task_has_null_route():
    node = _node(id="T1", execution_kind="direct-task", route_ref=None, entity_ref=None)
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert viol == []
    assert env["component_route"] is None


# ─────────────────── build_envelope: fail-closed 群 (phase-04 C17 負例) ───────────────────
def test_missing_execution_kind_rejected():
    node = _node()
    node.pop("execution_kind")
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert env is None and any("execution_kind 欠落" in v for v in viol)


def test_missing_task_spec_ref_rejected():
    node = _node(task_spec_ref=None)
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert env is None and any("task_spec_ref 欠落" in v for v in viol)


def test_component_build_missing_route_ref_rejected():
    node = _node(route_ref=None)
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert env is None and any("明示 route_ref 必須" in v for v in viol)


def test_component_build_route_missing_from_handoff_rejected():
    node = _node(route_ref="C99")
    env, viol = RTE.build_envelope(node, _spec(), _graph(node), route_ids={"C01", "C02"})
    assert env is None and any("routes[] に不在" in v for v in viol)


def test_entity_ref_implicit_route_rejected():
    # entity_ref はあるが route_ref 欠落 → 暗黙 route 推測を拒否する旨のヒントを含む
    node = _node(route_ref=None, entity_ref="C01")
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert env is None and any("暗黙 route 推測は禁止" in v for v in viol)


def test_title_only_prompt_rejected():
    node = _node()
    env, viol = RTE.build_envelope(node, _spec(objective=""), _graph(node))
    assert env is None and any("objective 欠落" in v for v in viol)


def test_phase_gate_is_non_dispatch():
    node = _node(id="P05", execution_kind="phase-gate", route_ref=None, task_spec_ref=None, entity_ref=None)
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert env is None and any("phase-gate は非 dispatch" in v for v in viol)


def test_full_13_phase_ref_rejected():
    # phase_ref が単一 P0N でない (全 13 phase 連結注入の代理) → 拒否
    node = _node(phase_ref="P01..P13")
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert env is None and any("単一 phase id" in v for v in viol)


def test_direct_task_with_route_ref_rejected():
    node = _node(id="T1", execution_kind="direct-task", route_ref="C01", entity_ref=None)
    env, viol = RTE.build_envelope(node, _spec(), _graph(node))
    assert env is None and any("direct-task は route_ref を持たない" in v for v in viol)


def test_missing_verify_rejected():
    node = _node()
    env, viol = RTE.build_envelope(node, _spec(verify=""), _graph(node))
    assert env is None and any("verify 欠落" in v for v in viol)


def test_empty_acceptance_rejected():
    node = _node(acceptance_criterion=None)
    env, viol = RTE.build_envelope(node, _spec(acceptance_criteria=[]), _graph(node))
    assert env is None and any("acceptance_criteria が空" in v for v in viol)


def test_invalid_knowledge_ref_rejected():
    node = _node()
    env, viol = RTE.build_envelope(
        node,
        _spec(knowledge_refs=[{
            "id": "K1",
            "source_ref": "knowledge/k1.json",
            "freshness_checked_at": "not-a-date",
            "decision": "adopted",
            "reason": "reuse",
        }]),
        _graph(node),
    )
    assert env is None and any("YYYY-MM-DD" in v for v in viol)


# ─────────────────── main() 統合 ───────────────────
def _write_plan(tmp_path, node, spec):
    (tmp_path / "task-graph.json").write_text(json.dumps(_graph(node)), encoding="utf-8")
    specs = tmp_path / "task-specs"
    specs.mkdir(exist_ok=True)
    lines = ["---"]
    for k, v in spec.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("本文 (envelope へ全文注入しない)")
    (specs / "T2.md").write_text("\n".join(lines), encoding="utf-8")


def test_main_emit_exit0(tmp_path, capsys):
    _write_plan(tmp_path, _node(), _spec())
    rc = RTE.main([str(tmp_path), "--task-id", "T2"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["task_id"] == "T2" and out["component_route"] == "C01"


def test_main_violation_exit1(tmp_path):
    _write_plan(tmp_path, _node(route_ref=None), _spec())
    assert RTE.main([str(tmp_path), "--task-id", "T2"]) == 1


def test_main_node_not_found_exit2(tmp_path):
    _write_plan(tmp_path, _node(), _spec())
    assert RTE.main([str(tmp_path), "--task-id", "ZZZ"]) == 2


def test_main_emit_to_file(tmp_path):
    _write_plan(tmp_path, _node(), _spec())
    rc = RTE.main([str(tmp_path), "--task-id", "T2", "--emit", "envelope.json"])
    assert rc == 0
    env = json.loads((tmp_path / "envelope.json").read_text(encoding="utf-8"))
    assert env["objective"].startswith("derive-task-graph")


def test_main_task_spec_ref_outside_plan_dir_rejected(tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    node = _node(task_spec_ref="../outside.md")
    (plan_dir / "task-graph.json").write_text(json.dumps(_graph(node)), encoding="utf-8")
    (tmp_path / "outside.md").write_text(
        "---\nobjective: outside\nverify: true\nacceptance_criteria:\n  - outside\n---\n",
        encoding="utf-8",
    )
    assert RTE.main([str(plan_dir), "--task-id", "T2"]) == 1
    out = capsys.readouterr().out
    assert "task_spec_ref" in out and "PLAN_DIR 外" in out


def test_main_emit_outside_plan_dir_rejected_without_write(tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_plan(plan_dir, _node(), _spec())
    escaped = tmp_path / "escaped.json"
    assert RTE.main([str(plan_dir), "--task-id", "T2", "--emit", "../escaped.json"]) == 1
    assert not escaped.exists()
    assert "PLAN_DIR 外" in capsys.readouterr().out


def test_main_handoff_route_must_exist_when_handoff_present(tmp_path, capsys):
    node = _node(route_ref="C99")
    _write_plan(tmp_path, node, _spec())
    (tmp_path / "handoff-run-plugin-dev-plan.json").write_text(
        json.dumps({"routes": [{"id": "C01"}]}), encoding="utf-8"
    )
    assert RTE.main([str(tmp_path), "--task-id", "T2"]) == 1
    assert "routes[] に不在" in capsys.readouterr().out


def test_main_no_handoff_preserves_legacy_standalone_route_behavior(tmp_path):
    _write_plan(tmp_path, _node(route_ref="LEGACY"), _spec())
    assert RTE.main([str(tmp_path), "--task-id", "T2"]) == 0
