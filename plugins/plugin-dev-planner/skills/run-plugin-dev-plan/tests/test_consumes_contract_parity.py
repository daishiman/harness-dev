"""consumes=artifact→consumer task の cross-component 契約パリティ。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CRS = _load("compute-ready-set")
RTE = _load("render-task-execution-envelope")


def test_missing_artifact_blocks_ready_and_same_edge_injects_artifact(tmp_path):
    """validator の C2 fixture と同じ向きで、欠落 artifact を両 consumer が認識する。"""
    producer = {
        "id": "T1",
        "title": "producer",
        "phase_ref": "P05",
        "entity_ref": "C00",
        "state": "done",
        "write_scope": str(tmp_path / "missing-artifact"),
    }
    consumer = {
        "id": "T2",
        "title": "consumer",
        "phase_ref": "P05",
        "entity_ref": "C01",
        "state": "pending",
        "write_scope": "plugins/example/",
        "execution_kind": "component-build",
        "route_ref": "C01",
        "task_spec_ref": "task-specs/T2.md",
        "acceptance_criterion": "artifact input is explicit",
    }
    graph = {
        "schema_version": "1.0",
        "nodes": [producer, consumer],
        "edges": [
            {"type": "produces", "from": "T1", "to": "A1"},
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    ready, _ = CRS.ready_set(graph)
    assert "T2" not in ready

    spec = {
        "objective": "consume A1",
        "verify": "test -e A1",
        "acceptance_criteria": ["A1 is consumed"],
        "knowledge_refs": [],
    }
    envelope, violations = RTE.build_envelope(consumer, spec, graph, route_ids={"C01"})
    assert violations == []
    assert envelope["injected_inputs"] == ["A1"]
