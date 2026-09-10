"""Post-finalize measurement, question-bank, and task-graph runtime contracts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, ValidationError


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MEASURE = PLUGIN_ROOT / "scripts" / "measure_value_realized.py"
UPDATE_BANK = PLUGIN_ROOT / "scripts" / "update_question_bank.py"
VERIFY_GRAPH = PLUGIN_ROOT / "skills" / "run-skill-intake" / "scripts" / "validate-task-graph-progress.py"
INTAKE_DIR = PLUGIN_ROOT / "skills" / "run-skill-intake"
INTAKE_MANIFEST = INTAKE_DIR / "workflow-manifest.json"
TRACE_SCHEMA = INTAKE_DIR / "schemas" / "output.schema.json"
REQUEST_SCHEMA = INTAKE_DIR / "schemas" / "intake-request.schema.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "fixture_name",
    ["example-data-quality-survey", "example-team-onboarding", "info-collector-agent"],
)
def test_measure_reads_current_v2_axes_and_open_questions(fixture_name: str) -> None:
    intake = json.loads(
        (PLUGIN_ROOT / "fixtures" / fixture_name / "intake.json").read_text(encoding="utf-8")
    )
    module = load_module(MEASURE, f"measure_{fixture_name.replace('-', '_')}")
    result = module.score(intake, None)
    open_count = len(intake["sections"]["8_open_questions"]["questions"])
    expected_penalty = max(0.0, 1 - open_count * 0.05)
    expected_score = round(0.55 + 0.10 * expected_penalty, 3)
    assert result["axes_filled"] == 5
    assert result["components"]["axisScore"] == 1.0
    assert result["components"]["openPenalty"] == expected_penalty
    assert result["score"] == expected_score
    assert result["value_realized_score"] == expected_score


def test_question_candidates_are_derived_by_existing_updater(tmp_path: Path) -> None:
    intake = {
        "sections": {
            "10_self_updater": {
                "question_bank_additions": [
                    {"category": "goal", "technique": "why", "question_text": "最後に誰が使いますか？"},
                    {"category": "empty", "question_text": ""},
                ]
            }
        }
    }
    intake_path = tmp_path / "intake.json"
    output_path = tmp_path / "qb-candidates.json"
    intake_path.write_text(json.dumps(intake, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(UPDATE_BANK), "--derive-from-intake", str(intake_path), "--out", str(output_path), "--hint", "demo"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == {
        "session_id": "intake-demo",
        "hint": "demo",
        "questions": [{"text": "最後に誰が使いますか？", "tags": ["goal", "why"]}],
    }


def test_question_bank_dry_run_uses_plugin_default_and_writes_nothing(tmp_path: Path) -> None:
    session = tmp_path / "session.json"
    session.write_text(json.dumps({"session_id": "dry", "hint": "dry", "questions": ["new?"]}), encoding="utf-8")
    bank = PLUGIN_ROOT / "references" / "question-bank.md"
    before = hashlib.sha256(bank.read_bytes()).hexdigest()
    result = subprocess.run(
        [sys.executable, str(UPDATE_BANK), "--diff", str(session), "--hint", "dry"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert hashlib.sha256(bank.read_bytes()).hexdigest() == before
    assert not (tmp_path / "output" / "dry" / "question-bank.snapshot.md").exists()


def graph_payload() -> tuple[dict, list[dict]]:
    goal = "Create a complete intake handoff"
    phases = json.loads(INTAKE_MANIFEST.read_text(encoding="utf-8"))["phases"]
    phase_to_item = {phase["id"]: f"C{index}" for index, phase in enumerate(phases, 1)}
    progress = {
        "skill": "run-skill-intake",
        "goal": goal,
        "engine": "task-graph",
        "iteration": len(phases) - 1,
        "original_goal_hash": hashlib.sha256(goal.encode()).hexdigest(),
        "status": "in_progress",
        "max_loops": 17,
        "checklist": [
            {
                "id": f"C{index}",
                "text": f"[{phase['id']}] {phase['title']}",
                "status": "done",
                "depends_on": [phase_to_item[dep] for dep in phase.get("dependsOn", [])],
            }
            for index, phase in enumerate(phases, 1)
        ],
    }
    base = {
        "original_goal": goal,
        "current_goal_snapshot": goal,
        "delta_from_original": "none",
        "merged_directive_for_next": "continue",
        "drift_signal": "aligned",
    }
    rows = [
        {**base, "iteration": index - 1, "ready_set": [f"C{index}"], "selected_item": f"C{index}"}
        for index in range(1, len(phases) + 1)
    ]
    return progress, rows


def _write_artifact(path: Path, text: str) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _phase_record(tmp_path: Path, phase: dict, attempt: int = 1, status: str = "PASS") -> dict:
    stamp = f"2026-08-24T00:{phase['step']:02d}:00Z"
    record = {
        "id": phase["id"],
        "attempt": attempt,
        "status": status,
        "delegateType": phase["delegateType"],
        "delegateName": phase["delegateName"],
        "delegateSkill": phase.get("delegateSkill"),
        "started_at": stamp,
        "finished_at": stamp,
        "handoff_path": None,
        "handoff_sha256": None,
        "exit_code": 0,
    }
    if status == "PASS":
        handoff = _write_artifact(tmp_path / f"{phase['id']}-attempt-{attempt}.json", "{}\n")
        record["handoff_path"] = handoff["path"]
        record["handoff_sha256"] = handoff["sha256"]
    return record


def build_trace(
    tmp_path: Path,
    progress_path: Path,
    intermediate_path: Path,
    *,
    skip_p5: bool = False,
    retry_p8: bool = False,
) -> dict:
    phases = json.loads(INTAKE_MANIFEST.read_text(encoding="utf-8"))["phases"]
    records: list[dict] = []
    for phase in phases:
        if skip_p5 and phase["id"] == "P5-excavation":
            record = _phase_record(tmp_path, phase, status="SKIP")
            record["skip_reason"] = phase["skipReason"]
            records.append(record)
            continue
        if retry_p8 and phase["id"] == "P8-summary":
            record = _phase_record(tmp_path, phase, status="RETRY")
            record["retry_reason"] = phase["retryOn"]
            records.append(record)
            retry_start = next(index for index, item in enumerate(phases) if item["id"] == phase["retryTo"])
            for retried in phases[retry_start : phase["step"]]:
                records.append(_phase_record(tmp_path, retried, attempt=2))
            continue
        records.append(_phase_record(tmp_path, phase))

    p9 = next(record for record in records if record["id"] == "P9-finalize" and record["status"] == "PASS")
    p9["exit_hook"] = {
        "name": "measure-and-preview-self-update-inline",
        "status": "PASS",
        "evidence": [
            _write_artifact(tmp_path / "self-update.json", "{}\n"),
            _write_artifact(tmp_path / "qb-candidates.json", "{}\n"),
        ],
    }
    p11 = next(record for record in records if record["id"] == "P11-next-action")
    p11["exit_hook"] = {
        "name": "validate-task-graph-progress",
        "status": "RUNNING",
        "evidence": [
            {"path": progress_path.name, "sha256": hashlib.sha256(progress_path.read_bytes()).hexdigest()},
            {"path": intermediate_path.name, "sha256": hashlib.sha256(intermediate_path.read_bytes()).hexdigest()},
        ],
    }
    intake_md = _write_artifact(tmp_path / "intake.md", "# intake\n")
    intake_json = _write_artifact(tmp_path / "intake.json", "{}\n")
    return {
        "session_id": "test-session",
        "workflow_status": "in_progress",
        "phases": records,
        "artifacts": {"intake_md": intake_md["path"], "intake_json": intake_json["path"]},
    }


def run_graph_verifier(
    tmp_path: Path,
    progress: dict,
    rows: list[dict] | None,
    *,
    skip_p5: bool = False,
    retry_p8: bool = False,
    trace_mutator=None,
    write_trace: bool = True,
) -> subprocess.CompletedProcess[str]:
    progress_path = tmp_path / "progress.json"
    intermediate_path = tmp_path / "intermediate.jsonl"
    trace_path = tmp_path / "intake-trace.json"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    if rows is not None:
        intermediate_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    if write_trace and rows is not None:
        trace = build_trace(tmp_path, progress_path, intermediate_path, skip_p5=skip_p5, retry_p8=retry_p8)
        if trace_mutator:
            trace_mutator(trace)
        trace_path.write_text(json.dumps(trace), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(VERIFY_GRAPH), str(progress_path), str(intermediate_path), str(trace_path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_task_graph_verifier_accepts_complete_consumption(tmp_path: Path) -> None:
    progress, rows = graph_payload()
    result = run_graph_verifier(tmp_path, progress, rows)
    assert result.returncode == 0, result.stderr


def test_task_graph_verifier_accepts_idempotent_post_hook_rerun(tmp_path: Path) -> None:
    progress, rows = graph_payload()
    progress["status"] = "completed"

    def mark_pass(trace: dict) -> None:
        next(record for record in trace["phases"] if record["id"] == "P11-next-action")["exit_hook"]["status"] = "PASS"
        trace["workflow_status"] = "completed"

    result = run_graph_verifier(tmp_path, progress, rows, trace_mutator=mark_pass)
    assert result.returncode == 0, result.stderr


def independent_graph_payload() -> tuple[dict, list[dict]]:
    progress, rows = graph_payload()
    for item_id in ("C12", "C13"):
        progress["checklist"].append(
            {
                "id": item_id,
                "text": f"dynamic {item_id}",
                "status": "done",
                "depends_on": ["C11"],
                "created_iteration": 10,
                "available_from_iteration": 11,
            }
        )
    rows.append({**rows[-1], "iteration": 11, "ready_set": ["C12", "C13"], "selected_item": "C12"})
    rows.append({**rows[-1], "iteration": 12, "ready_set": ["C13"], "selected_item": "C13"})
    progress["iteration"] = 12
    return progress, rows


def dynamic_append_graph_payload() -> tuple[dict, list[dict]]:
    progress, rows = graph_payload()
    progress["checklist"].append(
        {
            "id": "C12",
            "text": "dynamic C12",
            "status": "done",
            "depends_on": ["C11"],
            "created_iteration": 10,
            "available_from_iteration": 11,
        }
    )
    rows.append({**rows[-1], "iteration": 11, "ready_set": ["C12"], "selected_item": "C12"})
    progress["iteration"] = 11
    return progress, rows


def test_task_graph_verifier_accepts_legal_dynamic_append(tmp_path: Path) -> None:
    progress, rows = dynamic_append_graph_payload()
    result = run_graph_verifier(tmp_path, progress, rows)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("violation", ["omitted-when-available", "selected-before-available"])
def test_task_graph_verifier_rejects_dynamic_append_availability_violations(
    tmp_path: Path, violation: str
) -> None:
    progress, rows = dynamic_append_graph_payload()
    if violation == "omitted-when-available":
        rows[-1]["ready_set"] = []
        rows[-1]["selected_item"] = None
    else:
        progress["checklist"][-1]["available_from_iteration"] = 12
        rows[-1]["ready_set"] = ["C12"]
        rows[-1]["selected_item"] = "C12"
    result = run_graph_verifier(tmp_path, progress, rows)
    assert result.returncode == 1
    assert "ready_set 不整合" in result.stderr


def test_task_graph_verifier_rejects_omitted_lower_ready_counterexample(tmp_path: Path) -> None:
    progress, rows = independent_graph_payload()
    rows[-2]["ready_set"] = ["C13"]
    rows[-2]["selected_item"] = "C13"
    rows[-1]["ready_set"] = ["C12"]
    rows[-1]["selected_item"] = "C12"
    result = run_graph_verifier(tmp_path, progress, rows)
    assert result.returncode == 1
    assert "computed=['C12', 'C13']" in result.stderr


@pytest.mark.parametrize("violation", ["missing", "extra", "order"])
def test_task_graph_verifier_requires_exact_stably_ordered_ready_set(
    tmp_path: Path, violation: str
) -> None:
    progress, rows = independent_graph_payload()
    if violation == "missing":
        rows[-2]["ready_set"] = ["C12"]
    elif violation == "extra":
        rows[-2]["ready_set"] = ["C12", "C13", "C14"]
    else:
        rows[-2]["ready_set"] = ["C13", "C12"]
    result = run_graph_verifier(tmp_path, progress, rows)
    assert result.returncode == 1
    assert "ready_set 不整合" in result.stderr


@pytest.mark.parametrize(
    "violation",
    ["missing-trace", "missing-trace-keys", "missing-hash", "wrong-selection", "done-without-trace", "anchor-drift"],
)
def test_task_graph_verifier_rejects_absence_and_contract_violations(tmp_path: Path, violation: str) -> None:
    progress, rows = graph_payload()
    if violation == "missing-trace":
        rows = None
    elif violation == "missing-trace-keys":
        rows[0].pop("ready_set")
    elif violation == "missing-hash":
        progress.pop("original_goal_hash")
    elif violation == "wrong-selection":
        rows[0]["selected_item"] = "C2"
    elif violation == "done-without-trace":
        rows[-1]["ready_set"] = []
        rows[-1]["selected_item"] = None
    else:
        rows[1]["original_goal"] = "drifted"
    result = run_graph_verifier(tmp_path, progress, rows, write_trace=violation != "missing-trace")
    assert result.returncode == 1
    assert "contract violation" in result.stderr


@pytest.mark.parametrize("violation", ["phase-id", "depends-on", "title"])
def test_task_graph_verifier_binds_initial_checklist_to_manifest(tmp_path: Path, violation: str) -> None:
    progress, rows = graph_payload()
    if violation == "phase-id":
        progress["checklist"][0]["id"] = "C99"
    elif violation == "depends-on":
        progress["checklist"][5]["depends_on"] = []
    else:
        progress["checklist"][0]["text"] = "generic first"
    result = run_graph_verifier(tmp_path, progress, rows)
    assert result.returncode == 1
    assert "contract violation" in result.stderr


def test_task_graph_verifier_accepts_manifest_declared_skip_and_retry(tmp_path: Path) -> None:
    for name, kwargs in (("skip", {"skip_p5": True}), ("retry", {"retry_p8": True})):
        case = tmp_path / name
        case.mkdir()
        progress, rows = graph_payload()
        result = run_graph_verifier(case, progress, rows, **kwargs)
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("violation", ["skip-reason", "retry-limit", "missing-hook", "hook-digest", "hook-state"])
def test_task_graph_verifier_rejects_phase_and_exit_hook_drift(tmp_path: Path, violation: str) -> None:
    progress, rows = graph_payload()
    kwargs = {}

    def mutate(trace: dict) -> None:
        if violation == "skip-reason":
            p5 = next(record for record in trace["phases"] if record["id"] == "P5-excavation")
            p5["skip_reason"] = "because"
        elif violation == "retry-limit":
            p8 = next(record for record in trace["phases"] if record["id"] == "P8-summary")
            p8["attempt"] = 4
        elif violation == "missing-hook":
            next(record for record in trace["phases"] if record["id"] == "P9-finalize").pop("exit_hook")
        elif violation == "hook-digest":
            next(record for record in trace["phases"] if record["id"] == "P9-finalize")["exit_hook"]["evidence"][0]["sha256"] = "0" * 64
        else:
            next(record for record in trace["phases"] if record["id"] == "P11-next-action")["exit_hook"]["status"] = "PASS"

    if violation == "skip-reason":
        kwargs["skip_p5"] = True
    elif violation == "retry-limit":
        kwargs["retry_p8"] = True
    result = run_graph_verifier(tmp_path, progress, rows, trace_mutator=mutate, **kwargs)
    assert result.returncode == 1
    assert "contract violation" in result.stderr


def test_generated_trace_is_schema_valid_after_exit_hook_pass(tmp_path: Path) -> None:
    progress, rows = graph_payload()
    progress_path = tmp_path / "progress.json"
    intermediate_path = tmp_path / "intermediate.jsonl"
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    intermediate_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    trace = build_trace(tmp_path, progress_path, intermediate_path, retry_p8=True)
    next(record for record in trace["phases"] if record["id"] == "P11-next-action")["exit_hook"]["status"] = "PASS"
    trace["workflow_status"] = "completed"
    schema = json.loads(TRACE_SCHEMA.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    Draft7Validator(schema, format_checker=Draft7Validator.FORMAT_CHECKER).validate(trace)


def test_pre_choice_request_snapshot_is_distinct_from_final_intake() -> None:
    schema = json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    sample = {
        "schema_version": "1.0.0",
        "status": "request-snapshot",
        "initial_utterance": "問い合わせ受付を簡単にしたい",
        "notion_target": None,
        "workflow_manifest_sha256": hashlib.sha256(INTAKE_MANIFEST.read_bytes()).hexdigest(),
    }
    Draft7Validator(schema).validate(sample)
    with pytest.raises(ValidationError):
        Draft7Validator(schema).validate({**sample, "status": "final-intake"})
