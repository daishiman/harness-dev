from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts/validate-system-spec-delegation.py"
WRITER = PLUGIN / "scripts/register-package.py"
SKILL_DIR = PLUGIN / "skills/run-dev-graph-system-spec"
ENTRYPOINTS = [
    "system-spec-harness:run-system-spec-elicit",
    "system-spec-harness:run-system-spec-doc-fetch",
    "system-spec-harness:run-system-spec-compile",
    "system-spec-harness:assign-system-spec-completeness-evaluator",
]


def test_inline_responsibility_prompts_do_not_request_agent_fork() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "fork: inline" in skill_text
    assert "allowed-tools: [Read, Bash, Skill, AskUserQuestion]" in skill_text

    prompts = sorted((SKILL_DIR / "prompts").glob("*.md"))
    assert len(prompts) == 4
    for prompt in prompts:
        body = prompt.read_text(encoding="utf-8")
        assert "この responsibility は main context で実行し" in body
        assert "`Agent` fork は行わない" in body
        assert (
            "qualified `system-spec-harness:assign-system-spec-completeness-evaluator` "
            "Skill 内の責務"
        ) in body
        assert "`Agent` で分離 context に fork する" not in body


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(
    root: Path,
    *,
    omit: str | None = None,
    evaluator_result: str = "PASS",
) -> tuple[Path, Path]:
    evidence_paths = [
        root / "system-spec/spec-state.json",
        root / "system-spec/fetched-references.json",
        root / "system-spec/index.md",
        root / "eval-log/completeness-findings.json",
    ]
    for index, path in enumerate(evidence_paths[:-1], 1):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"evidence-{index}\n", encoding="utf-8")
    write_json(
        evidence_paths[-1],
        {
            "evaluator": {
                "name": "assign-system-spec-completeness-evaluator",
                "version": "0.1.0",
                "context": "fork",
            },
            "verdict": evaluator_result,
            "aspects": {
                name: {
                    "verdict": evaluator_result,
                    "auditor": "fixture-auditor",
                    "component": "C05",
                    "summary": "fixture evidence",
                }
                for name in (
                    "foundation_trace",
                    "decision_guidance",
                    "matrix_coverage",
                    "design_knowledge_reflection",
                    "doc_freshness",
                    "prompt_quality",
                )
            },
            "findings": [{"severity": "info", "bucket": "fixture", "observation": "checked"}],
            "gaps": [] if evaluator_result == "PASS" else ["fixture failure"],
        },
    )
    rows = []
    for entrypoint, path in zip(ENTRYPOINTS, evidence_paths):
        if entrypoint == omit:
            continue
        rows.append(
            {
                "sequence": len(rows) + 1,
                "qualified_entrypoint": entrypoint,
                "call_status": "no-op" if entrypoint.endswith("doc-fetch") else "completed",
                "result_status": evaluator_result if entrypoint.endswith("evaluator") else "PASS",
                "evidence_ref": path.relative_to(root).as_posix(),
                "evidence_sha256": digest(path),
            }
        )
    receipt = root / "eval-log/run-dev-graph-system-spec-delegation.json"
    write_json(receipt, {"schema_version": "1.0.0", "invocations": rows})
    progress = root / "eval-log/run-dev-graph-system-spec-progress.json"
    write_json(
        progress,
        {
            "delegation": {
                "required_entrypoints": ENTRYPOINTS,
                "completed_entrypoints": [row["qualified_entrypoint"] for row in rows],
                "completed_count": len(rows),
                "status": "PASS",
                "receipt_ref": receipt.relative_to(root).as_posix(),
                "receipt_sha256": digest(receipt),
            }
        },
    )
    return receipt, progress


def run(root: Path, receipt: Path, progress: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(root),
            "--receipt",
            str(receipt),
            "--progress",
            str(progress),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_accepts_four_ordered_digest_backed_calls_including_doc_fetch_noop(tmp_path: Path) -> None:
    receipt, progress = fixture(tmp_path)
    result = run(tmp_path, receipt, progress)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["valid"] is True
    assert output["completed_count"] == 4
    assert output["required_entrypoints"] == ENTRYPOINTS


def test_rejects_progress_claim_when_doc_fetch_was_not_invoked(tmp_path: Path) -> None:
    receipt, progress = fixture(tmp_path, omit=ENTRYPOINTS[1])
    value = json.loads(progress.read_text(encoding="utf-8"))
    value["delegation"]["completed_entrypoints"] = ENTRYPOINTS
    value["delegation"]["completed_count"] = 4
    write_json(progress, value)
    result = run(tmp_path, receipt, progress)
    assert result.returncode == 1
    assert "exactly 4 invocations" in result.stderr


def test_rejects_out_of_order_invocations(tmp_path: Path) -> None:
    receipt, progress = fixture(tmp_path)
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["invocations"][1]["qualified_entrypoint"], value["invocations"][2]["qualified_entrypoint"] = (
        value["invocations"][2]["qualified_entrypoint"],
        value["invocations"][1]["qualified_entrypoint"],
    )
    write_json(receipt, value)
    progress_value = json.loads(progress.read_text(encoding="utf-8"))
    progress_value["delegation"]["receipt_sha256"] = digest(receipt)
    write_json(progress, progress_value)
    result = run(tmp_path, receipt, progress)
    assert result.returncode == 1
    assert f"expected {ENTRYPOINTS[1]}" in result.stderr


def test_rejects_stale_evidence_digest(tmp_path: Path) -> None:
    receipt, progress = fixture(tmp_path)
    (tmp_path / "system-spec/fetched-references.json").write_text("changed\n", encoding="utf-8")
    result = run(tmp_path, receipt, progress)
    assert result.returncode == 1
    assert "evidence digest mismatch" in result.stderr


def test_rejects_evaluator_fail_before_progress_can_pass(tmp_path: Path) -> None:
    receipt, progress = fixture(tmp_path, evaluator_result="FAIL")
    result = run(tmp_path, receipt, progress)
    assert result.returncode == 1
    assert "result_status must be PASS before delegation progress can PASS" in result.stderr


def test_rejects_progress_file_outside_repo_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    receipt, progress = fixture(root)
    outside = tmp_path / "outside-progress.json"
    outside.write_bytes(progress.read_bytes())
    result = run(root, receipt, outside)
    assert result.returncode == 1
    assert "--progress escapes repo root" in result.stderr


def headings(path: Path) -> list[str]:
    return [match.group(1) for match in re.finditer(r"^#{1,4} (.+)$", path.read_text(), re.M)]


def rendered_body(kind: str, subtypes: list[str], contract: dict[str, object]) -> str:
    artifact_contract = contract["artifacts"][kind]  # type: ignore[index]
    required = artifact_contract["required_sections"]  # type: ignore[index]
    lines: list[str] = []
    for index, heading in enumerate(required):
        lines.extend([f"{'#' if index == 0 else '##'} {heading}", "", "Verified content.", ""])
    if kind == "architecture":
        subtype_templates = artifact_contract["subtype_templates"]  # type: ignore[index]
        for subtype in subtypes:
            overlay = headings(PLUGIN / "templates" / subtype_templates[subtype])  # type: ignore[index]
            lines.extend([f"### {overlay[0]}", "", "Verified architecture.", ""])
            for heading in overlay[1:]:
                lines.extend([f"#### {heading}", "", "Verified architecture detail.", ""])
    return "\n".join(lines).rstrip() + "\n"


def system_spec_import_fixture(
    tmp_path: Path,
    *,
    evaluator_result: str = "PASS",
    cycle: bool = False,
) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    for directory in ("specs", "architecture"):
        (root / directory).mkdir()
    shutil.copytree(PLUGIN / "templates", root / ".dev-graph/templates")
    write_json(
        root / ".dev-graph/config.json",
        {
            "schema_version": "1.0.0",
            "local_state": {
                "graph": ".dev-graph/graph.json",
                "templates": ".dev-graph/templates",
            },
            "execution_tracker": {"mode": "none"},
        },
    )
    graph = root / ".dev-graph/graph.json"
    write_json(graph, {"schema_version": "1.0.0", "graph_revision": 0, "nodes": []})

    sources = [
        root / "system-spec/00-requirements-definition.md",
        root / "system-spec/10-architecture.md",
    ]
    for source, body in zip(sources, ("# Requirements\n\nConfirmed.\n", "# Architecture\n\nConfirmed.\n")):
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(body, encoding="utf-8")
    artifacts = [
        {"title": "Confirmed system requirements", "body": sources[0].read_text()},
        {"title": "Confirmed system architecture", "body": sources[1].read_text()},
    ]
    input_path = root / "eval-log/system-spec-import-input.json"
    write_json(input_path, {"batch_id": "system-spec-import", "artifacts": artifacts})
    contract = json.loads((PLUGIN / "templates/template-contract.json").read_text())
    decisions = []
    for index, (kind, subtypes) in enumerate(
        (("specification", []), ("architecture", ["backend"]))
    ):
        other_title = artifacts[1 - index]["title"]
        decisions.append(
            {
                "input_index": index,
                "artifact_kind": kind,
                "artifact_subtypes": subtypes,
                "project_id": "system-spec-project",
                "domain": "system",
                "owners": ["system-team"],
                "tags": ["system-spec"],
                "priority": None,
                "resource_scope": ["system-spec"],
                "classification_confidence": 0.95,
                "classification_reason": "Explicit system-spec import fixture.",
                "classification_candidates": [{"artifact_kind": "document", "confidence": 0.05}],
                "decision_source": "automatic",
                "tracker_binding": "none",
                "depends_on_titles": [other_title] if cycle else [],
                "related_node_titles": [],
                "architecture_ref_titles": [artifacts[1]["title"]] if kind == "specification" else [],
                "rendered_body": rendered_body(kind, subtypes, contract),
            }
        )
    plan_path = root / "eval-log/system-spec-import-plan.json"
    write_json(
        plan_path,
        {"schema_version": "1.0.0", "observed_at": "2026-08-25T03:00:00Z", "decisions": decisions},
    )
    receipt, progress = fixture(root, evaluator_result=evaluator_result)
    attestation = root / "eval-log/system-spec-import-attestation.json"
    write_json(
        attestation,
        {
            "schema_version": "1.0.0",
            "source_plugin": "system-spec-harness",
            "source_version": "0.1.11",
            "delegation_receipt_ref": receipt.relative_to(root).as_posix(),
            "delegation_receipt_sha256": digest(receipt),
            "delegation_progress_ref": progress.relative_to(root).as_posix(),
            "delegation_progress_sha256": digest(progress),
            "artifacts": [
                {
                    "input_index": index,
                    "source_ref": source.relative_to(root).as_posix(),
                    "source_sha256": digest(source),
                }
                for index, source in enumerate(sources)
            ],
        },
    )
    return root, graph, input_path, plan_path


def run_import(
    root: Path,
    input_path: Path,
    plan_path: Path,
    *,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(WRITER),
        "artifacts",
        "--repo-root",
        str(root),
        "--input",
        str(input_path),
        "--plan",
        str(plan_path),
        "--system-spec-attestation",
        str(root / "eval-log/system-spec-import-attestation.json"),
    ]
    if dry_run:
        argv.append("--dry-run")
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_c02_attested_import_is_dry_run_then_atomic_confirmed_pass(tmp_path: Path) -> None:
    root, graph, input_path, plan_path = system_spec_import_fixture(tmp_path)
    before = graph.read_bytes()
    preview = run_import(root, input_path, plan_path, dry_run=True)
    assert preview.returncode == 0, preview.stdout + preview.stderr
    preview_report = json.loads(preview.stdout)
    assert preview_report["write_count"] == 0
    assert preview_report["c11_staged"]["valid"] is True
    assert graph.read_bytes() == before
    assert not list((root / "specs").glob("*.md"))
    assert not list((root / "architecture").glob("*.md"))

    applied = run_import(root, input_path, plan_path)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    report = json.loads(applied.stdout)
    assert report["system_spec_attestation"] == "eval-log/system-spec-import-attestation.json"
    nodes = json.loads(graph.read_text())["nodes"]
    assert len(nodes) == 2
    assert {node["status"] for node in nodes} == {"active"}
    assert {node["confirmation_status"] for node in nodes} == {"confirmed"}
    assert {node["evaluation_status"] for node in nodes} == {"pass"}
    assert {node["source_lineage"]["origin_kind"] for node in nodes} == {"system-spec-harness"}
    assert {node["source_lineage"]["source_plugin"] for node in nodes} == {"system-spec-harness"}
    assert {node["source_lineage"]["source_version"] for node in nodes} == {"0.1.11"}
    assert all(node["confirmation_evidence"]["evaluated_digest"] == node["source_lineage"]["source_digest"] for node in nodes)
    stable = graph.read_bytes()
    rerun = run_import(root, input_path, plan_path)
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    rerun_report = json.loads(rerun.stdout)
    assert rerun_report["applied"] == []
    assert len(rerun_report["unchanged"]) == 2
    assert rerun_report["write_count"] == 0
    assert graph.read_bytes() == stable


def test_evaluator_fail_leaves_graph_and_artifacts_unchanged(tmp_path: Path) -> None:
    root, graph, input_path, plan_path = system_spec_import_fixture(
        tmp_path, evaluator_result="FAIL"
    )
    before = graph.read_bytes()
    result = run_import(root, input_path, plan_path)
    assert result.returncode == 2
    assert "result_status must be PASS" in result.stdout
    assert graph.read_bytes() == before
    assert not list((root / "specs").glob("*.md"))
    assert not list((root / "architecture").glob("*.md"))


def test_c11_failure_leaves_attested_import_partial_zero(tmp_path: Path) -> None:
    root, graph, input_path, plan_path = system_spec_import_fixture(tmp_path, cycle=True)
    before = graph.read_bytes()
    result = run_import(root, input_path, plan_path)
    assert result.returncode == 2
    assert "C11 validation failed" in result.stdout
    assert graph.read_bytes() == before
    assert not list((root / "specs").glob("*.md"))
    assert not list((root / "architecture").glob("*.md"))
