"""Provider-neutral normal-runtime adapter contract for external intelligence."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[2]
HC_PLUGIN = ROOT / "plugins/harness-creator"
PLUGIN = ROOT / "plugins/skill-governance-adapters"
ENGINE = PLUGIN / "scripts/build-external-intelligence.py"
ADAPTER = PLUGIN / "scripts/build-external-intelligence-runtime.py"
SCHEMA = PLUGIN / "schemas/external-intelligence-runtime.schema.json"
CONTRACT = PLUGIN / "references/external-intelligence-runtime-contract.md"
CONTRACT_ID = "external-intelligence-runtime-v1"
COMPOSITION = HC_PLUGIN / "plugin-composition.yaml"
RUN_RESOURCE_MAP = HC_PLUGIN / "skills/run-build-skill/references/resource-map.yaml"
KNOWLEDGE_RESOURCE_MAP = HC_PLUGIN / "skills/ref-knowledge-loop/references/resource-map.yaml"
HC_ENGINE = HC_PLUGIN / "skills/run-build-skill/scripts/build-external-intelligence.py"
HC_ADAPTER = HC_PLUGIN / "skills/run-build-skill/scripts/build-external-intelligence-runtime.py"
TRACE_VALIDATOR = HC_PLUGIN / "skills/run-build-skill/scripts/validate-build-trace.py"


def _load_adapter():
    spec = importlib.util.spec_from_file_location("external_intelligence_runtime", ADAPTER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _run_engine(project: Path, *args: str):
    return subprocess.run(
        [
            sys.executable,
            str(ENGINE),
            "--scope",
            "project",
            "--project-root",
            str(project),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _capture(project: Path, index: int, *, summary: str | None = None):
    topics = (
        ("Database migration rollback safety", "Back up relational schemas before destructive migrations."),
        ("Stable prompt prefix ordering", "Place invariant instructions before variable prompt content."),
        ("Plugin runtime state isolation", "Keep mutable runtime state outside versioned plugin packages."),
        ("Concurrent writer lease recovery", "Reclaim a write lease only after its recorded owner is dead."),
        ("Evidence digest provenance", "Bind verification claims to exact evidence file digests."),
        ("Bounded semantic retrieval", "Fetch only scored summaries and selected detail records."),
        ("Fail-soft optional memory", "Continue artifact generation when optional memory is unavailable."),
    )
    title, rule = topics[index % len(topics)]
    return _run_engine(
        project,
        "--agent",
        "codex",
        "capture",
        "--title",
        title,
        "--summary",
        summary or f"Reusable summary for deterministic runtime task {index}.",
        "--rule",
        rule,
        "--context-id",
        f"fixture/context-{index}",
        "--evidence-ref",
        f"fixture:evidence-{index}",
        "--evidence-source",
        f"fixture:source-{index}",
    )


def _request(project: Path, operation: str, **extra) -> dict:
    value = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "operation": operation,
        "runtime": "codex",
        "run_id": "runtime-test-001",
        "project_root": str(project.resolve()),
        "context_id": "fixture/current-task",
    }
    value.update(extra)
    return value


def _invoke(tmp_path: Path, request: dict, *, env: dict[str, str] | None = None):
    request_path = tmp_path / f"{request['operation']}-{request['runtime']}.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(ADAPTER), "--request", str(request_path)],
        capture_output=True,
        text=True,
        env=merged_env,
        check=False,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc, payload


def _normalise_runtime(payload: dict) -> dict:
    value = json.loads(json.dumps(payload))
    value["runtime"] = "provider-neutral"
    return value


def _assert_schema(value: dict) -> None:
    Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(value)


def test_schema_and_contract_publish_one_canonical_request_state_output_surface():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    assert set(schema["definitions"]) >= {"request", "state", "output"}
    text = CONTRACT.read_text(encoding="utf-8")
    assert CONTRACT_ID in text
    assert "Claude Code" in text and "Codex" in text
    assert "warning-continue" in text
    assert "user scope" in text
    assert "token" in text


def test_central_adapter_schema_and_contract_are_registered_without_engine_copies():
    composition = yaml.safe_load(COMPOSITION.read_text(encoding="utf-8"))
    adapter_ref = "skills/run-build-skill/scripts/build-external-intelligence-runtime.py"
    engine_ref = "skills/run-build-skill/scripts/build-external-intelligence.py"
    assert {"kind": "script", "ref": adapter_ref, "tier": "core"} in composition["capabilities"]
    assert {"kind": "script", "ref": engine_ref, "tier": "core"} in composition["capabilities"]
    assert all(
        not edge["from"].startswith("plugins/")
        and not edge["to"].startswith("plugins/")
        for edge in composition["dependencies"]
    ), "internal capability DAG must not impersonate cross-plugin resources"
    provider = composition["external_dependencies"]["skill-governance-adapters"]
    assert provider == {
        "version": ">=0.1.1 <1.0.0",
        "relation": "external-intelligence-runtime-provider",
        "required_runtime_scripts": [
            "hooks/build-external-intelligence-context.py",
            "scripts/build-external-intelligence-runtime.py",
            "scripts/build-external-intelligence.py",
        ],
        "required_runtime_resources": [
            "schemas/external-intelligence-runtime.schema.json",
            "references/external-intelligence-runtime-contract.md",
        ],
    }

    run_map = yaml.safe_load(RUN_RESOURCE_MAP.read_text(encoding="utf-8"))
    assert "skill-governance-adapters" not in {
        item["name"] for item in run_map["bundles"]
    }, "a runtime provider without plugin-composition must not be a bundle-map target"
    assert "../schemas/external-intelligence-runtime.schema.json" not in run_map["local_artifacts"]["schemas"]
    runtime_category = next(
        item for item in run_map["resources"] if item["category"] == "external-intelligence-runtime"
    )
    assert runtime_category["max_docs"] == 1
    assert runtime_category["local_reference"] == [
        "plugins/skill-governance-adapters/references/external-intelligence-runtime-contract.md"
    ]
    assert (ROOT / runtime_category["local_reference"][0]).resolve() == CONTRACT.resolve()

    knowledge_map = yaml.safe_load(KNOWLEDGE_RESOURCE_MAP.read_text(encoding="utf-8"))
    assert knowledge_map["categories"]["external_intelligence_runtime"]["file"] == (
        "external-intelligence-runtime-contract.md"
    )


def test_public_bundle_validator_accepts_harness_composition_with_external_provider():
    proc = subprocess.run(
        [sys.executable, str(TRACE_VALIDATOR), "--bundle", str(COMPOSITION)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout) == {
        "findings": [],
        "kind": "plugin-composition",
        "valid": True,
    }


def test_harness_creator_forwarders_preserve_cli_and_import_compatibility(tmp_path: Path):
    assert HC_ENGINE.stat().st_size < 3_000
    assert HC_ADAPTER.stat().st_size < 3_000
    project = tmp_path / "harness-consumer"
    project.mkdir()
    proc = subprocess.run(
        [
            sys.executable,
            str(HC_ENGINE),
            "--scope",
            "project",
            "--project-root",
            str(project),
            "init",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "ok"

    spec = importlib.util.spec_from_file_location("hc_runtime_forwarder", HC_ADAPTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.CONTRACT_ID == CONTRACT_ID
    assert callable(module.execute_request)


def test_search_is_thin_scored_byte_bounded_and_provider_parity(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    for index in range(7):
        result = _capture(
            project,
            index,
            summary="Stable runtime deterministic artifact summary. " + "要" * 2_000,
        )
        assert result.returncode == 0, result.stderr

    request = _request(
        project,
        "search",
        query="stable runtime deterministic artifact",
        limit=5,
    )
    codex_proc, codex = _invoke(tmp_path, request)
    request["runtime"] = "claude-code"
    claude_proc, claude = _invoke(tmp_path, request)

    assert codex_proc.returncode == claude_proc.returncode == 0
    _assert_schema(codex)
    _assert_schema(claude)
    assert codex["status"] == claude["status"] == "continue"
    assert 0 < len(codex["candidates"]) <= 5
    assert all(item["score"] >= codex["policy"]["score_threshold"] for item in codex["candidates"])
    assert all(len(item["summary"].encode("utf-8")) <= 512 for item in codex["candidates"])
    assert len(json.dumps(codex["candidates"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= 4_096
    assert codex["state"]["candidate_ids"] == [item["id"] for item in codex["candidates"]]
    assert _normalise_runtime(codex) == _normalise_runtime(claude)


def test_adopt_shows_only_selected_ids_and_records_reuse(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    for index in range(3):
        assert _capture(project, index).returncode == 0
    _, searched = _invoke(
        tmp_path,
        _request(project, "search", query="reusable summary deterministic runtime task", limit=5),
    )
    selected = searched["state"]["candidate_ids"][1]
    proc, adopted = _invoke(
        tmp_path,
        _request(
            project,
            "adopt",
            state=searched["state"],
            selection=[{"id": selected, "outcome": "helpful"}],
            evidence_ref="artifact:current",
            evidence_source="test-suite:runtime-adapter",
        ),
    )

    assert proc.returncode == 0, proc.stderr
    _assert_schema(adopted)
    assert [item["id"] for item in adopted["details"]] == [selected]
    assert adopted["state"]["selected_ids"] == [selected]
    assert adopted["reuses"] == [{"id": selected, "outcome": "helpful", "recorded": True}]
    assert len(json.dumps(adopted["details"][0], ensure_ascii=False).encode("utf-8")) <= 4_096
    shown = _run_engine(project, "show", "--id", selected)
    assert shown.returncode == 0
    detail = json.loads(shown.stdout)["entry"]
    assert detail["helpful_reuse_count"] == 1
    assert detail["reuses"][0]["agent"] == "codex"


def test_finish_captures_at_most_one_and_semantic_duplicate_merges(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    first = _capture(project, 1)
    assert first.returncode == 0
    original_id = json.loads(first.stdout)["entry"]["id"]
    _, searched = _invoke(
        tmp_path,
        _request(project, "search", query="stable prompt prefix ordering", limit=5),
    )
    capture = {
        "title": "Stable prompt prefix ordering!",
        "summary": "A second observation of the same reusable structure.",
        "rule": "Place invariant instructions before variable prompt content!",
        "evidence_ref": "artifact:finish",
        "evidence_source": "review:finish",
        "tags": ["runtime", "artifact"],
        "countercondition": "Do not apply when the runtime is intentionally isolated.",
    }
    proc, finished = _invoke(
        tmp_path,
        _request(project, "finish", state=searched["state"], capture=capture),
    )
    assert proc.returncode == 0, proc.stderr
    _assert_schema(finished)
    assert finished["capture"]["id"] == original_id
    assert finished["capture"]["action"] == "merged"
    metrics = _run_engine(project, "metrics")
    assert json.loads(metrics.stdout)["entry_count"] == 1

    invalid = _request(project, "finish", state=searched["state"], capture=[capture, capture])
    rejected, payload = _invoke(tmp_path, invalid)
    assert rejected.returncode == 2
    assert payload["status"] == "invalid_request"


def test_corrupt_or_missing_memory_and_timeout_warn_but_continue_without_token_estimates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project = tmp_path / "consumer"
    project.mkdir()
    state = project / ".harness/external-intelligence/v1"
    state.mkdir(parents=True)
    (state / "events.jsonl").write_text("not-json\n", encoding="utf-8")
    request = _request(project, "search", query="anything", limit=5)
    proc, corrupt = _invoke(tmp_path, request)
    assert proc.returncode == 0
    _assert_schema(corrupt)
    assert corrupt["status"] == "continue"
    assert corrupt["warnings"][0]["code"] == "memory_corrupt"
    assert corrupt["candidates"] == []
    assert corrupt["token_telemetry"] == {
        "status": "unavailable",
        "estimated": False,
        "input_tokens": None,
        "reused_input_tokens": None,
    }

    adapter = _load_adapter()
    missing = adapter.execute_request(request, engine_path=tmp_path / "missing-engine.py")
    assert missing["status"] == "continue"
    assert missing["warnings"][0]["code"] == "memory_unavailable"

    def timeout_runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=kwargs["timeout"])

    timed_out = adapter.execute_request(request, runner=timeout_runner)
    assert timed_out["status"] == "continue"
    assert timed_out["warnings"][0]["code"] == "memory_timeout"


def test_adapter_forces_project_scope_and_never_auto_mixes_user_state(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    user_state = tmp_path / "user-state"
    env = {
        "HARNESS_INTELLIGENCE_HOME": str(user_state),
        "PLUGIN_DATA": str(tmp_path / "plugin-data"),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "claude-plugin-data"),
        "XDG_STATE_HOME": str(tmp_path / "xdg-state"),
    }
    proc, result = _invoke(
        tmp_path,
        _request(project, "search", query="project only", limit=5),
        env=env,
    )

    assert proc.returncode == 0
    _assert_schema(result)
    assert result["memory"]["scope"] == "project"
    assert result["memory"]["user_scope_used"] is False
    assert result["warnings"][0]["code"] == "memory_absent"
    assert not user_state.exists()
    assert result["state"]["project_root"] == str(project.resolve())


def test_adopt_rejects_ids_not_returned_by_prior_thin_search(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    assert _capture(project, 1).returncode == 0
    _, searched = _invoke(
        tmp_path,
        _request(project, "search", query="stable runtime", limit=5),
    )
    request = _request(
        project,
        "adopt",
        state=searched["state"],
        selection=[{"id": "ei-aaaaaaaaaaaa", "outcome": "neutral"}],
        evidence_ref="artifact:current",
        evidence_source="test-suite:runtime-adapter",
    )
    proc, result = _invoke(tmp_path, request)
    assert proc.returncode == 2
    assert result["status"] == "invalid_request"
    assert "candidate" in result["error"]


def test_cli_accepts_explicit_request_json_without_treating_it_as_a_path(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    request = _request(project, "search", query="bounded retrieval", limit=5)

    proc = subprocess.run(
        [sys.executable, str(ADAPTER), "--request-json", json.dumps(request)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    _assert_schema(result)
    assert result["operation"] == "search"


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "ok", "state_dir": "/tmp/state", "query": "q", "results": None},
        {"status": "ok", "state_dir": "/tmp/state", "query": "q", "results": [], "extra": True},
        {"status": "ok", "state_dir": 7, "query": "q", "results": []},
    ],
)
def test_search_engine_success_shape_drift_is_schema_valid_warning_continue(
    tmp_path: Path, payload: dict
):
    project = tmp_path / "consumer"
    project.mkdir()
    adapter = _load_adapter()

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, json.dumps(payload), "")

    result = adapter.execute_request(
        _request(project, "search", query="q", limit=5), runner=runner
    )

    _assert_schema(result)
    assert result["status"] == "continue"
    assert result["memory"]["status"] == "unavailable"
    assert result["warnings"][0]["code"] == "memory_unavailable"
    assert result["candidates"] == []


def test_adopt_empty_show_entry_is_schema_valid_warning_continue(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    adapter = _load_adapter()
    entry_id = "ei-0123456789ab"
    state = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "run_id": "runtime-test-001",
        "project_root": str(project.resolve()),
        "query": "q",
        "candidate_ids": [entry_id],
        "selected_ids": [],
        "phase": "searched",
        "memory_status": "available",
    }

    def runner(*args, **kwargs):
        payload = {"status": "ok", "state_dir": str(project / ".harness"), "entry": {}}
        return subprocess.CompletedProcess(args[0], 0, json.dumps(payload), "")

    result = adapter.execute_request(
        _request(
            project,
            "adopt",
            state=state,
            selection=[{"id": entry_id, "outcome": "helpful"}],
            evidence_ref="artifact:current",
            evidence_source="test-suite:drift",
        ),
        runner=runner,
    )

    _assert_schema(result)
    assert result["warnings"][0]["code"] == "memory_unavailable"
    assert result["details"] == []
    assert result["reuses"] == []


def test_finish_empty_capture_entry_is_schema_valid_warning_continue(tmp_path: Path):
    project = tmp_path / "consumer"
    project.mkdir()
    adapter = _load_adapter()
    state = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "run_id": "runtime-test-001",
        "project_root": str(project.resolve()),
        "query": "q",
        "candidate_ids": [],
        "selected_ids": [],
        "phase": "searched",
        "memory_status": "available",
    }
    capture = {
        "title": "Retry safety",
        "summary": "Bound retry loops.",
        "rule": "Bound retry loops and preserve terminal errors.",
        "evidence_ref": "artifact:finish",
        "evidence_source": "test-suite:drift",
        "tags": ["retry"],
        "countercondition": "Do not apply to a single non-retriable operation.",
    }

    def runner(*args, **kwargs):
        payload = {
            "status": "ok",
            "action": "created",
            "state_dir": str(project / ".harness"),
            "entry": {},
        }
        return subprocess.CompletedProcess(args[0], 0, json.dumps(payload), "")

    result = adapter.execute_request(
        _request(project, "finish", state=state, capture=capture), runner=runner
    )

    _assert_schema(result)
    assert result["warnings"][0]["code"] == "memory_unavailable"
    assert result["capture"] is None
    assert result["state"]["phase"] == "finished"
