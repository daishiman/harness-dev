"""validate-route-build-reports.py の structured freshness 回帰テスト。"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills" / "run-build-skill" / "scripts" / "validate-route-build-reports.py"
)
_DERIVE_SCRIPT = (
    _SCRIPT.parents[4]
    / "plugin-dev-planner" / "skills" / "run-plugin-dev-plan" / "scripts" / "derive-task-graph.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("validate_route_build_reports", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vr = _load()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fixture(tmp_path: Path):
    root = tmp_path / "repo"
    plan_dir = root / "plugin-plans" / "demo-plan"
    target = root / "plugins" / "demo-plugin" / "scripts" / "build.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('ok')\n", encoding="utf-8")
    graph = {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "P05-C01-01",
                "title": "build",
                "phase_ref": "P05",
                "entity_ref": "C01",
                "state": "pending",
                "write_scope": "plugins/demo-plugin/scripts/build.py",
            },
            {
                "id": "P05-C02-01",
                "title": "other",
                "phase_ref": "P05",
                "entity_ref": "C02",
                "state": "pending",
                "write_scope": "plugins/demo-plugin/scripts/other.py",
            },
        ],
        "edges": [],
    }
    _write_json(plan_dir / "task-graph.json", graph)
    fixture_derive = (
        root / "plugins" / "plugin-dev-planner" / "skills" / "run-plugin-dev-plan"
        / "scripts" / "derive-task-graph.py"
    )
    fixture_derive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_DERIVE_SCRIPT, fixture_derive)
    shutil.copy2(_DERIVE_SCRIPT.with_name("specfm.py"), fixture_derive.with_name("specfm.py"))
    route = {
        "id": "C01",
        "component_kind": "script",
        "name": "build.py",
        "builder": "plugin-scaffold",
        "build_target": "plugins/demo-plugin/scripts/build.py",
        "depends_on": [],
    }
    handoff = {
        "target_plugin_slug": "demo-plugin",
        "task_graph_ref": {"path": "task-graph.json", "schema_version": "1.0"},
        "routes": [route],
    }
    _write_json(plan_dir / "handoff-run-plugin-dev-plan.json", handoff)
    report = {
        "schema_version": "1.0.0",
        "plugin_slug": "demo-plugin",
        "route_id": "C01",
        "component_kind": "script",
        "name": "build.py",
        "builder": "plugin-scaffold",
        "build_target": "plugins/demo-plugin/scripts/build.py",
        "status": "success",
        "summary": "build complete",
        "deviations": [],
        "evidence": ["focused tests passed"],
        "inputs_consumed": [],
        "handover": None,
        "artifact_sha256": vr._hash_target(target),
        "graph_hash": vr._producer_graph_hash(plan_dir / "task-graph.json", root)[0],
        "generated_at": "2026-07-13T00:00:02Z",
        "tool_versions": {"python": "3.12.10", "pytest": "8.4.1"},
        "covered_task_ids": ["P05-C01-01"],
        "test_evidence": [
            {
                "command": "pytest -q test_build.py",
                "exit_code": 0,
                "passed": 1,
                "failed": 0,
                "started_at": "2026-07-13T00:00:00Z",
                "completed_at": "2026-07-13T00:00:01Z",
            }
        ],
    }
    reports_dir = root / "eval-log" / "demo-plugin" / "build"
    _write_json(reports_dir / "route-C01.json", report)
    return root, plan_dir, reports_dir, handoff, report, target


def test_current_handoff_structured_evidence_passes(tmp_path):
    root, plan_dir, reports_dir, handoff, _report, _target = _fixture(tmp_path)
    assert vr.validate_route(handoff, reports_dir, "C01", root, plan_dir) == []


def test_current_handoff_missing_structured_fields_fails_closed(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    for field in ("artifact_sha256", "graph_hash", "test_evidence", "generated_at", "tool_versions"):
        report.pop(field)
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("artifact_sha256" in finding for finding in findings)
    assert any("graph_hash" in finding for finding in findings)
    assert any("test_evidence" in finding for finding in findings)
    assert any("generated_at" in finding for finding in findings)
    assert any("tool_versions" in finding for finding in findings)


def test_artifact_sha256_is_compared_to_current_target(tmp_path):
    root, plan_dir, reports_dir, handoff, _report, target = _fixture(tmp_path)
    target.write_text("print('changed')\n", encoding="utf-8")
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("current target hash" in finding for finding in findings)


def test_graph_hash_is_compared_to_current_graph(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    report["graph_hash"] = "sha256:" + "0" * 64
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("current task graph" in finding for finding in findings)


def test_covered_task_ids_must_exist_and_belong_to_route(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    report["covered_task_ids"] = ["P05-C02-01", "UNKNOWN"]
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("entity_ref" in finding for finding in findings)
    assert any("UNKNOWN" in finding for finding in findings)


def test_structured_test_evidence_rejects_failed_success(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    report["test_evidence"] = [
        {
            "command": "pytest -q",
            "exit_code": 1,
            "passed": 2,
            "failed": 1,
            "started_at": "2026-07-13T00:00:00Z",
            "completed_at": "2026-07-13T00:00:01Z",
        }
    ]
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("status=success" in finding for finding in findings)


def test_current_handoff_build_target_path_escape_rejected(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    handoff["routes"][0]["build_target"] = "../outside.py"
    report["build_target"] = "../outside.py"
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("path escape" in finding for finding in findings)


def test_legacy_handoff_keeps_structured_fields_optional(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    handoff.pop("task_graph_ref")
    for field in (
        "artifact_sha256", "graph_hash", "test_evidence", "generated_at", "tool_versions",
        "covered_task_ids",
    ):
        report.pop(field)
    _write_json(reports_dir / "route-C01.json", report)
    assert vr.validate_route(handoff, reports_dir, "C01", root, plan_dir) == []


def test_test_artifact_existence_and_hash_are_verified_when_present(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    artifact = root / "eval-log" / "demo-plugin" / "tests" / "pytest.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"passed": 1}\n', encoding="utf-8")
    report["test_evidence"][0].update({
        "artifact": "eval-log/demo-plugin/tests/pytest.json",
        "artifact_sha256": vr._hash_target(artifact),
    })
    _write_json(reports_dir / "route-C01.json", report)
    assert vr.validate_route(handoff, reports_dir, "C01", root, plan_dir) == []

    artifact.write_text('{"passed": 0}\n', encoding="utf-8")
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("current artifact hash" in finding for finding in findings)

    artifact.unlink()
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("実体が存在しない" in finding for finding in findings)


def test_test_artifact_fields_must_be_paired_and_repo_relative(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    report["test_evidence"][0]["artifact"] = "/tmp/outside.json"
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("ペア" in finding for finding in findings)
    assert any("repo-root 相対" in finding for finding in findings)


def test_test_timestamps_are_ordered_before_report_generation(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    report["test_evidence"][0].update({
        "started_at": "2026-07-13T00:00:03Z",
        "completed_at": "2026-07-13T00:00:02Z",
    })
    report["generated_at"] = "2026-07-13T00:00:01Z"
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("started_at が completed_at より後" in finding for finding in findings)
    assert any("completed_at が report.generated_at より後" in finding for finding in findings)


def test_current_test_timestamps_are_required(tmp_path):
    root, plan_dir, reports_dir, handoff, report, _target = _fixture(tmp_path)
    report["test_evidence"][0].pop("started_at")
    report["test_evidence"][0].pop("completed_at")
    _write_json(reports_dir / "route-C01.json", report)
    findings = vr.validate_route(handoff, reports_dir, "C01", root, plan_dir)
    assert any("started_at/completed_at が必須" in finding for finding in findings)


def test_schema_is_the_key_and_enum_source_of_truth():
    schema = json.loads(vr.SCHEMA_PATH.read_text(encoding="utf-8"))
    assert set(vr.REQUIRED_KEYS) | set(vr.OPTIONAL_KEYS) == set(schema["properties"])
    assert vr.COMPONENT_KINDS == set(schema["properties"]["component_kind"]["enum"])
    assert vr.BUILDERS == set(schema["properties"]["builder"]["enum"])
    assert vr.STATUSES == set(schema["properties"]["status"]["enum"])
