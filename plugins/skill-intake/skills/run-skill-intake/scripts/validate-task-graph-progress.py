#!/usr/bin/env python3
# /// script
# name: validate-task-graph-progress
# purpose: task-graph progressの依存順消費・消費完全性・中間成果物anchorをabsence-as-violationで検査する。
# inputs:
#   - argv: <progress_json_path> <intermediate_jsonl_path> <intake_trace_json_path>
# outputs:
#   - stdout: PASS summary
#   - stderr: contract violation
#   - exit: 0=PASS / 1=contract violation / 2=usage
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Recompute exact ready sets and verify task consumption and goal anchors."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_ANCHOR_KEYS = {
    "iteration",
    "original_goal",
    "current_goal_snapshot",
    "delta_from_original",
    "merged_directive_for_next",
    "drift_signal",
}
ID_NUMBER = re.compile(r"^C(\d+)$")


class ContractViolation(ValueError):
    """A fail-closed runtime-contract violation."""


def fail_unless(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


def id_sort_key(item_id: str) -> tuple[int, int, str]:
    match = ID_NUMBER.match(item_id)
    return (0, int(match.group(1)), item_id) if match else (1, 0, item_id)


def load_progress(path: Path) -> dict[str, Any]:
    fail_unless(path.is_file(), f"progress.json 不在: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    fail_unless(isinstance(value, dict), "progress.json が object でない")
    return value


def load_intermediate(path: Path) -> list[dict[str, Any]]:
    fail_unless(path.is_file(), f"intermediate.jsonl 未生成: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        fail_unless(isinstance(value, dict), f"intermediate[{line_number}] が object でない")
        rows.append(value)
    fail_unless(bool(rows), "intermediate.jsonl が空")
    return rows


def load_object(path: Path, label: str) -> dict[str, Any]:
    fail_unless(path.is_file(), f"{label} 不在: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    fail_unless(isinstance(value, dict), f"{label} が object でない")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_contract(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = load_object(path, "workflow-manifest.json")
    phases = manifest.get("phases")
    resources = manifest.get("resources")
    fail_unless(isinstance(phases, list) and bool(phases), "manifest.phases が空/配列でない")
    fail_unless(isinstance(resources, list), "manifest.resources が配列でない")

    phase_ids: list[str] = []
    phase_by_id: dict[str, dict[str, Any]] = {}
    for index, phase in enumerate(phases):
        fail_unless(isinstance(phase, dict), f"manifest.phases[{index}] が object でない")
        phase_id = phase.get("id")
        fail_unless(isinstance(phase_id, str) and bool(phase_id), f"manifest.phases[{index}].id 不正")
        fail_unless(phase_id not in phase_by_id, f"manifest phase id 重複: {phase_id}")
        fail_unless(phase.get("step") == index + 1, f"{phase_id}: step が配列順 {index + 1} と不一致")
        fail_unless(phase.get("delegateType") in {"skill", "agent"}, f"{phase_id}: delegateType 不正")
        fail_unless(isinstance(phase.get("delegateName"), str) and phase["delegateName"], f"{phase_id}: delegateName 不正")
        deps = phase.get("dependsOn", [])
        fail_unless(isinstance(deps, list) and all(isinstance(dep, str) for dep in deps), f"{phase_id}: dependsOn 不正")
        phase_ids.append(phase_id)
        phase_by_id[phase_id] = phase

    known_phases = set(phase_ids)
    for phase_id, phase in phase_by_id.items():
        deps = phase.get("dependsOn", [])
        fail_unless(set(deps) <= known_phases, f"{phase_id}: 未知 dependsOn {sorted(set(deps) - known_phases)}")
        fail_unless(all(phase_ids.index(dep) < phase_ids.index(phase_id) for dep in deps), f"{phase_id}: 前方/循環 dependsOn")
        retry_to = phase.get("retryTo")
        if retry_to is not None:
            fail_unless(retry_to in known_phases, f"{phase_id}: retryTo={retry_to!r} が不在")
            fail_unless(phase_ids.index(retry_to) < phase_ids.index(phase_id), f"{phase_id}: retryTo は前段 phase 必須")
            fail_unless(isinstance(phase.get("retryOn"), str) and phase["retryOn"], f"{phase_id}: retryOn 必須")
            max_retries = phase.get("maxRetries")
            fail_unless(isinstance(max_retries, int) and not isinstance(max_retries, bool) and max_retries >= 1, f"{phase_id}: maxRetries 不正")
        if "skipWhen" in phase or "skipReason" in phase:
            fail_unless(isinstance(phase.get("skipWhen"), str) and phase["skipWhen"], f"{phase_id}: skipWhen 必須")
            fail_unless(isinstance(phase.get("skipReason"), str) and phase["skipReason"], f"{phase_id}: skipReason 必須")

    resource_by_id: dict[str, dict[str, Any]] = {}
    for index, resource in enumerate(resources):
        fail_unless(isinstance(resource, dict), f"manifest.resources[{index}] が object でない")
        resource_id = resource.get("id")
        fail_unless(isinstance(resource_id, str) and resource_id, f"manifest.resources[{index}].id 不正")
        fail_unless(resource_id not in resource_by_id, f"manifest resource id 重複: {resource_id}")
        resource_path = resource.get("path")
        fail_unless(isinstance(resource_path, str) and resource_path, f"{resource_id}: path 不正")
        resolved = (path.parent / resource_path).resolve()
        fail_unless(resolved.is_file(), f"{resource_id}: resource path 不在: {resource_path}")
        bound_phases = resource.get("phaseIds", [])
        fail_unless(isinstance(bound_phases, list) and set(bound_phases) <= known_phases, f"{resource_id}: phaseIds 不正")
        resource_by_id[resource_id] = resource

    known_resources = set(resource_by_id)
    plugin_root = path.parent.parent.parent
    for phase_id, phase in phase_by_id.items():
        declared = phase.get("resourceIds", [])
        fail_unless(isinstance(declared, list) and set(declared) <= known_resources, f"{phase_id}: 未知 resourceIds")
        if phase["delegateType"] == "skill":
            delegate_path = plugin_root / "skills" / phase["delegateName"] / "SKILL.md"
        else:
            delegate_path = plugin_root / "agents" / f"{phase['delegateName']}.md"
        fail_unless(delegate_path.is_file(), f"{phase_id}: delegate 不在: {delegate_path}")
        output_schema_id = phase.get("outputSchemaId")
        if output_schema_id is not None:
            fail_unless(output_schema_id in declared, f"{phase_id}: outputSchemaId が resourceIds に未束縛")
            fail_unless(resource_by_id[output_schema_id].get("kind") == "schema", f"{phase_id}: outputSchemaId が schema resource でない")
        if phase.get("exitHook"):
            fail_unless(
                any(resource_by_id[resource_id].get("kind") == "script" for resource_id in declared),
                f"{phase_id}: exitHook に script resource がない",
            )
        for resource_id in declared:
            fail_unless(phase_id in resource_by_id[resource_id].get("phaseIds", []), f"{phase_id}/{resource_id}: phase↔resource 非対称")
    for resource_id, resource in resource_by_id.items():
        for phase_id in resource.get("phaseIds", []):
            fail_unless(resource_id in phase_by_id[phase_id].get("resourceIds", []), f"{resource_id}/{phase_id}: resource↔phase 非対称")
    return manifest, phases


def checklist_contract(
    progress: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, str], dict[str, int]]:
    checklist = progress.get("checklist")
    fail_unless(isinstance(checklist, list), "checklist が配列でない")
    fail_unless(bool(checklist), "task-graph checklist が空")
    ids: list[str] = []
    deps_of: dict[str, list[str]] = {}
    status_of: dict[str, str] = {}
    available_from: dict[str, int] = {}
    for index, item in enumerate(checklist):
        fail_unless(isinstance(item, dict), f"checklist[{index}] が object でない")
        item_id = item.get("id")
        fail_unless(isinstance(item_id, str) and bool(item_id), f"checklist[{index}] id 不正")
        fail_unless(item_id not in ids, f"checklist id 重複: {item_id}")
        deps = item.get("depends_on") or []
        fail_unless(isinstance(deps, list) and all(isinstance(dep, str) for dep in deps), f"{item_id}: depends_on 不正")
        status = item.get("status")
        fail_unless(status in {"pending", "done", "blocked"}, f"{item_id}: status 不正: {status}")
        created = item.get("created_iteration", 0)
        available = item.get("available_from_iteration", created)
        fail_unless(
            isinstance(created, int) and not isinstance(created, bool) and created >= 0,
            f"{item_id}: created_iteration 不正: {created}",
        )
        fail_unless(
            isinstance(available, int) and not isinstance(available, bool) and available >= created,
            f"{item_id}: available_from_iteration 不正: {available}",
        )
        ids.append(item_id)
        deps_of[item_id] = deps
        status_of[item_id] = status
        available_from[item_id] = available
    known = set(ids)
    for item_id, deps in deps_of.items():
        for dep in deps:
            fail_unless(dep in known, f"{item_id}: depends_on '{dep}' が checklist 内に不在")

    white, grey, black = 0, 1, 2
    color = {item_id: white for item_id in ids}
    for start in ids:
        if color[start] != white:
            continue
        stack = [(start, list(deps_of[start]))]
        color[start] = grey
        while stack:
            node, pending = stack[-1]
            if pending:
                dep = pending.pop()
                fail_unless(color[dep] != grey, f"depends_on cycle: {node} -> {dep}")
                if color[dep] == white:
                    color[dep] = grey
                    stack.append((dep, list(deps_of[dep])))
            else:
                color[node] = black
                stack.pop()
    return checklist, deps_of, status_of, available_from


def verify_manifest_projection(
    progress: dict[str, Any], phases: list[dict[str, Any]]
) -> None:
    checklist = progress["checklist"]
    fail_unless(len(checklist) >= len(phases), "checklist が manifest phase 数未満")
    phase_to_item = {phase["id"]: f"C{index}" for index, phase in enumerate(phases, 1)}
    for index, phase in enumerate(phases, 1):
        item = checklist[index - 1]
        expected_id = f"C{index}"
        expected_text = f"[{phase['id']}] {phase['title']}"
        expected_deps = [phase_to_item[dep] for dep in phase.get("dependsOn", [])]
        fail_unless(item.get("id") == expected_id, f"manifest projection id 不整合: {item.get('id')} != {expected_id}")
        fail_unless(item.get("text") == expected_text, f"{expected_id}: phase title projection 不整合")
        fail_unless((item.get("depends_on") or []) == expected_deps, f"{expected_id}: depends_on が manifest と不一致")
        fail_unless(item.get("created_iteration", 0) == 0, f"{expected_id}: initial item の created_iteration は 0")
        fail_unless(item.get("available_from_iteration", 0) == 0, f"{expected_id}: initial item の available_from_iteration は 0")
    for item in checklist[len(phases):]:
        match = ID_NUMBER.match(item["id"])
        fail_unless(match is not None and int(match.group(1)) > len(phases), f"dynamic item id 不正: {item['id']}")
        fail_unless("created_iteration" in item and "available_from_iteration" in item, f"{item['id']}: dynamic append provenance 不足")


def resolve_trace_path(trace_path: Path, raw: str) -> Path:
    candidate = Path(raw)
    return candidate.resolve() if candidate.is_absolute() else (trace_path.parent / candidate).resolve()


def verify_digest_ref(trace_path: Path, evidence: dict[str, Any], label: str) -> Path:
    raw = evidence.get("path")
    digest = evidence.get("sha256")
    fail_unless(isinstance(raw, str) and raw, f"{label}: path 不正")
    fail_unless(isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest) is not None, f"{label}: sha256 不正")
    resolved = resolve_trace_path(trace_path, raw)
    fail_unless(resolved.is_file(), f"{label}: evidence 不在: {raw}")
    fail_unless(sha256_file(resolved) == digest, f"{label}: evidence sha256 mismatch: {raw}")
    return resolved


def verify_trace(
    trace: dict[str, Any],
    trace_path: Path,
    phases: list[dict[str, Any]],
    progress_path: Path,
    intermediate_path: Path,
) -> str:
    records = trace.get("phases")
    fail_unless(isinstance(records, list) and len(records) >= len(phases), "intake-trace phases 不足")
    phase_by_id = {phase["id"]: phase for phase in phases}
    phase_index = {phase["id"]: index for index, phase in enumerate(phases)}
    attempts = {phase["id"]: 0 for phase in phases}
    retry_counts = {phase["id"]: 0 for phase in phases}
    expected_index = 0

    for record_index, record in enumerate(records):
        fail_unless(isinstance(record, dict), f"trace.phases[{record_index}] が object でない")
        fail_unless(expected_index < len(phases), f"trace.phases[{record_index}] は workflow 完了後の余分な record")
        expected_phase = phases[expected_index]
        phase_id = record.get("id")
        fail_unless(phase_id == expected_phase["id"], f"trace.phases[{record_index}] id={phase_id!r}, expected={expected_phase['id']!r}")
        attempts[phase_id] += 1
        fail_unless(record.get("attempt") == attempts[phase_id], f"{phase_id}: attempt 連番不整合")
        fail_unless(record.get("delegateType") == expected_phase["delegateType"], f"{phase_id}: delegateType drift")
        fail_unless(record.get("delegateName") == expected_phase["delegateName"], f"{phase_id}: delegateName drift")
        parsed_times: dict[str, datetime] = {}
        for key in ("started_at", "finished_at"):
            value = record.get(key)
            fail_unless(isinstance(value, str) and value, f"{phase_id}: {key} 必須")
            try:
                parsed_times[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ContractViolation(f"{phase_id}: {key} date-time 不正") from exc
        fail_unless(parsed_times["started_at"] <= parsed_times["finished_at"], f"{phase_id}: timestamp 逆転")

        status = record.get("status")
        fail_unless(status in {"PASS", "SKIP", "RETRY"}, f"{phase_id}: completed trace に status={status!r}")
        if status == "PASS":
            fail_unless(record.get("exit_code") == 0, f"{phase_id}: PASS だが exit_code != 0")
            handoff = {"path": record.get("handoff_path"), "sha256": record.get("handoff_sha256")}
            verify_digest_ref(trace_path, handoff, f"{phase_id} handoff")
            expected_index += 1
        elif status == "SKIP":
            fail_unless(isinstance(expected_phase.get("skipWhen"), str), f"{phase_id}: manifest に skipWhen がない")
            fail_unless(record.get("skip_reason") == expected_phase.get("skipReason"), f"{phase_id}: skip_reason が manifest と不一致")
            fail_unless(record.get("handoff_path") is None and record.get("handoff_sha256") is None, f"{phase_id}: SKIP に handoff を記録している")
            fail_unless(record.get("exit_code") == 0, f"{phase_id}: SKIP exit_code 不正")
            expected_index += 1
        else:
            retry_to = expected_phase.get("retryTo")
            fail_unless(isinstance(retry_to, str), f"{phase_id}: manifest に retryTo がない")
            fail_unless(record.get("retry_reason") == expected_phase.get("retryOn"), f"{phase_id}: retry_reason が manifest と不一致")
            retry_counts[phase_id] += 1
            fail_unless(retry_counts[phase_id] <= expected_phase.get("maxRetries", 0), f"{phase_id}: retry 上限超過")
            fail_unless(record.get("handoff_path") is None and record.get("handoff_sha256") is None, f"{phase_id}: RETRY に handoff を記録している")
            fail_unless(record.get("exit_code") == 0, f"{phase_id}: RETRY exit_code 不正")
            expected_index = phase_index[retry_to]

        hook_name = expected_phase.get("exitHook")
        hook = record.get("exit_hook")
        if hook_name and status == "PASS":
            fail_unless(isinstance(hook, dict), f"{phase_id}: exit_hook 証跡不足")
            fail_unless(hook.get("name") == hook_name, f"{phase_id}: exit_hook name drift")
            allowed_status = {"PASS", "RUNNING"} if phase_id == phases[-1]["id"] else {"PASS"}
            fail_unless(hook.get("status") in allowed_status, f"{phase_id}: exit_hook 未成功")
            evidence = hook.get("evidence")
            fail_unless(isinstance(evidence, list) and evidence, f"{phase_id}: exit_hook evidence 不足")
            resolved = [verify_digest_ref(trace_path, item, f"{phase_id} exit_hook") for item in evidence]
            if hook_name == "measure-and-preview-self-update-inline":
                fail_unless({path.name for path in resolved} >= {"self-update.json", "qb-candidates.json"}, f"{phase_id}: self-update hook 出力不足")
            if hook_name == "validate-task-graph-progress":
                fail_unless(progress_path.resolve() in resolved and intermediate_path.resolve() in resolved, f"{phase_id}: verifier 入力 evidence 不足")
        elif hook is not None:
            fail_unless(False, f"{phase_id}: manifest にない/非PASSの exit_hook 証跡")

    if expected_index != len(phases):
        raise ContractViolation(f"trace が workflow 終端未到達: next={phases[expected_index]['id']}")
    final_record = records[-1]
    fail_unless(final_record.get("id") == phases[-1]["id"], "trace 終端が final phase でない")
    final_hook_status = final_record["exit_hook"]["status"]
    expected_workflow_status = "in_progress" if final_hook_status == "RUNNING" else "completed"
    fail_unless(trace.get("workflow_status") == expected_workflow_status, "trace.workflow_status と final exitHook が不一致")
    return final_hook_status


def verify(
    progress: dict[str, Any],
    rows: list[dict[str, Any]],
    trace: dict[str, Any],
    trace_path: Path,
    manifest: dict[str, Any],
    phases: list[dict[str, Any]],
    progress_path: Path,
    intermediate_path: Path,
) -> None:
    checklist, deps_of, status_of, available_from = checklist_contract(progress)
    fail_unless(progress.get("engine") == "task-graph", "engine は task-graph 必須")
    fail_unless(progress.get("skill") == manifest.get("skill"), "progress.skill が manifest.skill と不一致")
    verify_manifest_projection(progress, phases)

    original_hash = progress.get("original_goal_hash")
    fail_unless(isinstance(original_hash, str) and bool(original_hash), "original_goal_hash 必須")
    iteration = progress.get("iteration")
    fail_unless(isinstance(iteration, int) and iteration >= 0, "progress.iteration 不正")
    fail_unless(len(rows) == iteration + 1, f"intermediate 行数 {len(rows)} != iteration+1 {iteration + 1}")

    selected_sequence: list[str] = []
    first_anchor: str | None = None
    for index, row in enumerate(rows):
        missing = REQUIRED_ANCHOR_KEYS - row.keys()
        fail_unless(not missing, f"intermediate[{index}] anchor 必須キー不足: {sorted(missing)}")
        fail_unless("ready_set" in row and "selected_item" in row, f"intermediate[{index}] ready_set/selected_item 不足")
        fail_unless(row["iteration"] == index, f"intermediate[{index}] iteration 不整合")
        anchor = row["original_goal"]
        fail_unless(isinstance(anchor, str) and bool(anchor.strip()), f"intermediate[{index}] original_goal が空")
        if first_anchor is None:
            first_anchor = anchor
            expected_hash = hashlib.sha256(anchor.encode()).hexdigest()
            fail_unless(original_hash == expected_hash, "original_goal_hash mismatch")
            fail_unless(progress.get("goal") == anchor, "progress.goal と original_goal anchor が不一致")
        fail_unless(anchor == first_anchor, f"intermediate[{index}] anchor 不変性違反")
        fail_unless(isinstance(row["current_goal_snapshot"], str) and row["current_goal_snapshot"], f"intermediate[{index}] current_goal_snapshot が空")
        fail_unless(isinstance(row["delta_from_original"], str), f"intermediate[{index}] delta_from_original 不正")
        fail_unless(isinstance(row["merged_directive_for_next"], str) and row["merged_directive_for_next"], f"intermediate[{index}] merged_directive_for_next が空")
        fail_unless(row["drift_signal"] in {"initial", "aligned", "compressing", "stagnant", "widening", "oscillating"}, f"intermediate[{index}] drift_signal 不正")

        ready = row["ready_set"]
        selected = row["selected_item"]
        fail_unless(isinstance(ready, list) and all(isinstance(value, str) for value in ready), f"intermediate[{index}] ready_set 不正")
        consumed = set(selected_sequence)
        computed_ready = sorted(
            (
                item_id
                for item_id, dependencies in deps_of.items()
                if item_id not in consumed
                and index >= available_from[item_id]
                and status_of[item_id] != "blocked"
                and all(dependency in consumed for dependency in dependencies)
            ),
            key=id_sort_key,
        )
        fail_unless(
            ready == computed_ready,
            f"intermediate[{index}] ready_set 不整合: declared={ready}, computed={computed_ready}",
        )
        if computed_ready:
            fail_unless(isinstance(selected, str) and bool(selected), f"intermediate[{index}] ready 非空だが selected_item 不在")
        else:
            fail_unless(selected in (None, ""), f"intermediate[{index}] ready 空だが selected_item={selected}")
        if selected:
            fail_unless(selected not in selected_sequence, f"intermediate[{index}] selected_item 重複: {selected}")
            minimum = computed_ready[0]
            fail_unless(selected == minimum, f"intermediate[{index}] selected_item={selected} != ready 最小 id {minimum}")
            for dep in deps_of[selected]:
                fail_unless(dep in selected_sequence, f"intermediate[{index}] {selected} の依存 {dep} が未消費")
            selected_sequence.append(selected)

    selected_set = set(selected_sequence)
    done_without_trace = [
        item["id"] for item in checklist
        if item.get("status") == "done" and item["id"] not in selected_set
    ]
    fail_unless(not done_without_trace, f"done だが消費証跡なし: {done_without_trace}")
    fail_unless(len(selected_sequence) == len(rows) == len(checklist), "no-op iteration または checklist 未消費")
    unfinished = [item["id"] for item in checklist if item.get("status") != "done"]
    fail_unless(not unfinished, f"P11 exitHook 実行時に未完了: {unfinished}")
    max_loops = progress.get("max_loops")
    fail_unless(isinstance(max_loops, int) and not isinstance(max_loops, bool) and max_loops >= len(checklist), "max_loops が checklist 消費数未満")
    final_hook_status = verify_trace(trace, trace_path, phases, progress_path, intermediate_path)
    if final_hook_status == "RUNNING":
        fail_unless(progress.get("status") == "in_progress", "P11 exitHook RUNNING だが progress.status != in_progress")
    else:
        fail_unless(progress.get("status") == "completed", "P11 exitHook PASS だが progress.status != completed")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: validate-task-graph-progress.py <progress.json> <intermediate.jsonl> <intake-trace.json>\n")
        return 2
    try:
        progress_path = Path(argv[0])
        intermediate_path = Path(argv[1])
        trace_path = Path(argv[2])
        manifest_path = Path(__file__).resolve().parent.parent / "workflow-manifest.json"
        progress = load_progress(progress_path)
        rows = load_intermediate(intermediate_path)
        trace = load_object(trace_path, "intake-trace.json")
        manifest, phases = manifest_contract(manifest_path)
        verify(progress, rows, trace, trace_path, manifest, phases, progress_path, intermediate_path)
    except (ContractViolation, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"task-graph contract violation: {exc}\n")
        return 1
    sys.stdout.write("task-graph progress PASS: manifest projection, dependency consumption, phase trace, exit hooks, anchor, hash\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
