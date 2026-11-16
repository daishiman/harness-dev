#!/usr/bin/env python3
# /// script
# name: record-codex-audit
# purpose: actor書込外でCodex独立監査の原rolloutを固定し正式台帳を発行する。
# inputs: [Python API: cfg, state, native rollouts]
# outputs: [protected native audit ledger and exact snapshots]
# contexts: [C, E]
# network: false
# write-scope: config.private_dir/codex-audit
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Host observer only. Never call this writer from a trial actor or auditor."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path


def verifier(cfg):
    fixture = cfg.get("codex_audit_fixture")
    if fixture is None:
        return None
    if not isinstance(fixture, dict) or set(fixture) != {"plugin_root", "verifier_sha256"}:
        raise ValueError("invalid Codex audit fixture contract")
    root = Path(fixture["plugin_root"]).resolve(strict=True)
    if json.loads((root / ".claude-plugin/plugin.json").read_text())["name"] != "system-spec-harness":
        raise ValueError("Codex audit provider identity mismatch")
    path = root / "skills/assign-system-spec-completeness-evaluator/scripts/validate-codex-audit.py"
    spec = importlib.util.spec_from_file_location("codex_audit_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.sha(path.read_bytes()) != fixture["verifier_sha256"]:
        raise ValueError("Codex audit verifier source changed")
    return module, root


def environment(cfg):
    if cfg.get("codex_audit_fixture") is None:
        return {}
    return {"SYSTEM_SPEC_AUDIT_FORK_LEDGER": str(Path(cfg["private_dir"]).resolve() / "codex-audit/audit-fork-ledger.jsonl"),
            "SYSTEM_SPEC_AUDIT_RUNTIME": "codex"}


def initialize(cfg, state):
    found = verifier(cfg)
    if found is None:
        return
    module, root = found
    directory = Path(cfg["private_dir"]).resolve() / "codex-audit"
    directory.mkdir(exist_ok=False)
    config_path = Path(cfg["_config_file"]).resolve(strict=True)
    binding = {"schema_version": "codex-audit-host-binding/v1", "producer": module.PRODUCER,
        "config_path": str(config_path), "config_sha256": module.sha(config_path.read_bytes()),
        "run_id": cfg["run_id"], "started_at_unix": state["started_at_unix"],
        "native_session_root": str((Path.home() / ".codex/sessions").resolve()),
        "writable_roots": state["writable_roots"],
        "sources": module.source_pins(root)}
    module.verify_binding(binding, directory, root)
    raw = (json.dumps(binding, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    with (directory / "host-binding.json").open("xb") as stream:
        stream.write(raw)
    (directory / "audit-fork-ledger.jsonl").touch(exist_ok=False)
    state["codex_audit_binding_sha256"] = module.sha(raw)
    state["codex_audit_policy"] = {"proof_ref": "codex-audit", "runtime": "codex", "schema_version": module.SCHEMA,
                                    "producer": module.PRODUCER}


def observe(cfg, state, rollouts):
    found = verifier(cfg)
    if found is None:
        return
    module, root = found
    directory = Path(cfg["private_dir"]).resolve() / "codex-audit"
    binding_raw = (directory / "host-binding.json").read_bytes()
    binding = json.loads(binding_raw)
    if module.sha(binding_raw) != state.get("codex_audit_binding_sha256"):
        raise ValueError("Codex audit host binding changed")
    module.verify_binding(binding, directory, root)
    ledger = directory / "audit-fork-ledger.jsonl"
    existing = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    seen = {(row["session_id"], row["tool_use_id"]) for row in existing}
    by_id = {}
    for path in rollouts:
        path = Path(path).resolve(strict=True)
        path.relative_to(Path(binding["native_session_root"]))
        raw = path.read_bytes()
        # An in-flight JSONL row is not an observation until its newline exists.
        raw = raw[:raw.rfind(b"\n") + 1]
        values = module.rows(raw)
        identity = values[0]["payload"]["id"]
        if identity in by_id:
            raise ValueError("native audit duplicate thread source")
        by_id[identity] = (path, raw, values)
    for child_id, (child_path, child_raw, child_rows) in by_id.items():
        meta = child_rows[0]["payload"]
        origin = meta.get("source", {}).get("subagent", {}).get("thread_spawn", {}) if isinstance(meta.get("source"), dict) else {}
        if origin.get("agent_path", "").split("/")[-1] not in module.TASK_AUDITORS:
            continue
        parent_id = origin.get("parent_thread_id")
        if parent_id not in by_id:
            raise ValueError("native auditor parent rollout not collected")
        if not any(row["type"] == "event_msg" and row["payload"].get("type") == "task_complete" for row in child_rows):
            continue
        parent_path, parent_raw, _ = by_id[parent_id]
        result = module.reconstruct(parent_raw, child_raw, binding, root)
        key = (result["session_id"], result["tool_use_id"])
        if key in seen:
            previous = [r for r in existing if (r["session_id"], r["tool_use_id"]) == key]
            if len(previous) != 1 or any(previous[0].get(k) != v for k, v in result.items()):
                raise ValueError("native audit observation changed after publication")
            continue
        record = {**result, "host_binding_sha256": module.sha(binding_raw)}
        for kind, path, raw in (("parent", parent_path, parent_raw), ("child", child_path, child_raw)):
            relative = "snapshots/" + module.sha((result["tool_use_id"] + kind).encode()) + ".jsonl"
            snapshot = directory / relative
            snapshot.parent.mkdir(exist_ok=True)
            with snapshot.open("xb") as stream:
                stream.write(raw)
            record[kind] = {"snapshot_ref": relative, "native_source": str(path), "sha256": module.sha(raw), "bytes": len(raw)}
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
        seen.add(key)
