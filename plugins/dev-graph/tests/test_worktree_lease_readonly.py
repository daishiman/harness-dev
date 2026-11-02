"""C27 read-only observations must work when native sandbox protects .git."""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load():
    spec = importlib.util.spec_from_file_location("readonly_worktree_lease", SCRIPTS / "manage-worktree-lease.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path, monkeypatch):
    module = load()
    common = tmp_path / ".git"
    common.mkdir()
    context = {"repo_root": str(tmp_path), "git_common_dir": str(common),
               "repository_id": "local:sha256:fixture", "worktree_id": "fixture", "branch": "main",
               "base_branch": "main", "head_sha": "1" * 40}
    monkeypatch.setattr(module, "context", lambda *args: context)
    return module, common / "dev-graph"


def seed(coord):
    coord.mkdir()
    (coord / "leases.lock").touch()
    (coord / "leases.json").write_text(json.dumps({"schema_version":"1.1", "workspace_identity":"workspace-fixture",
        "leases":[{"graph_node_id":"old", "state":"claimed", "expires_at":"2000-01-01T00:00:00Z"}]}))
    (coord / "events.json").write_text(json.dumps({"schema_version":"1.0", "events":[{"type":"lease.reserved", "graph_node_id":"old"}]}))


@pytest.mark.parametrize("op", ["context", "list"])
def test_missing_coordination_observation_creates_nothing(tmp_path, monkeypatch, capsys, op):
    module, coord = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", [str(module.__file__), "--repo-root", str(tmp_path), "--op", op])
    assert module.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["repo_root"] == str(tmp_path)
    if op == "list": assert result["leases"] == result["events"] == []
    assert not coord.exists()


def test_list_reads_readonly_pair_under_shared_lock_without_any_writes(tmp_path, monkeypatch, capsys):
    module, coord = fixture(tmp_path, monkeypatch)
    seed(coord)
    before = {p.name:p.read_bytes() for p in coord.iterdir()}
    for path in coord.iterdir(): path.chmod(0o444)
    coord.chmod(0o555)
    original_open, original_flock = Path.open, fcntl.flock
    locks = []
    def read_open(path, mode="r", *args, **kwargs):
        if path == coord or coord in path.parents:
            assert not any(flag in mode for flag in "wax+"), "observation attempted a writable open"
        return original_open(path, mode, *args, **kwargs)
    def shared_lock(fd, operation):
        locks.append(operation)
        return original_flock(fd, operation)
    monkeypatch.setattr(Path, "open", read_open)
    monkeypatch.setattr(module.fcntl, "flock", shared_lock)
    monkeypatch.setattr(sys, "argv", [str(module.__file__), "--repo-root", str(tmp_path), "--op", "list"])
    try:
        assert module.main() == 0
        result = json.loads(capsys.readouterr().out)
        assert result["workspace_identity"] == "workspace-fixture"
        assert result["leases"][0]["state"] == "expired"  # projection only
        assert result["events"][0]["graph_node_id"] == "old"
        assert locks == [fcntl.LOCK_SH]
        assert {p.name:p.read_bytes() for p in coord.iterdir()} == before
    finally:
        coord.chmod(0o755)
        for path in coord.iterdir(): path.chmod(0o644)


@pytest.mark.parametrize("failure", ["invalid_json", "bad_leases", "bad_events", "missing_lock"])
def test_corrupted_coordination_is_rejected_without_repair_writes(tmp_path, monkeypatch, failure):
    module, coord = fixture(tmp_path, monkeypatch)
    seed(coord)
    if failure == "invalid_json": (coord/"leases.json").write_text("{")
    elif failure == "bad_leases": (coord/"leases.json").write_text('{"leases":"invalid"}')
    elif failure == "bad_events": (coord/"events.json").write_text('{"events":["invalid"]}')
    else: (coord/"leases.lock").unlink()
    before = {p.name:p.read_bytes() for p in coord.iterdir()}
    with pytest.raises(module.ContractError): module.read_only_snapshot(coord)
    assert {p.name:p.read_bytes() for p in coord.iterdir()} == before


def test_shared_reader_waits_for_exclusive_writer_to_finish_both_ledgers(tmp_path, monkeypatch):
    module, coord = fixture(tmp_path, monkeypatch)
    seed(coord)
    attempted = threading.Event()
    original = fcntl.flock
    def observe(fd, operation):
        if operation == fcntl.LOCK_SH: attempted.set()
        return original(fd, operation)
    monkeypatch.setattr(module.fcntl, "flock", observe)
    with (coord/"leases.lock").open("a+") as writer, ThreadPoolExecutor(max_workers=1) as pool:
        original(writer, fcntl.LOCK_EX)
        (coord/"leases.json").write_text('{"leases":[{"graph_node_id":"new"}]}')
        reading = pool.submit(module.read_only_snapshot, coord)
        try:
            assert attempted.wait(2)
            assert not reading.done()
            (coord/"events.json").write_text('{"events":[{"graph_node_id":"new"}]}')
        finally:
            original(writer, fcntl.LOCK_UN)
        ledger, events = reading.result(timeout=2)
        assert ledger["leases"][0]["graph_node_id"] == events["events"][0]["graph_node_id"] == "new"


def test_c26_real_backfill_producer_events_only_is_read_without_creating_lease_storage(tmp_path, monkeypatch, capsys):
    module, coord = fixture(tmp_path, monkeypatch)
    spec = importlib.util.spec_from_file_location("readonly_c26_producer", SCRIPTS/"reconcile-github-lifecycle.py")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    task = tmp_path/"tasks/G.md";task.parent.mkdir()
    task.write_text('---\ngraph_node_id: "G"\nstatus: "done"\n---\n# Done task\n')
    node = {"graph_node_id":"G", "artifact_kind":"task", "file_path":"tasks/G.md", "status":"done", "tracker_binding":"none",
            "completion_evidence":{"status":"done", "policy":"linked_pr_merged_all"},
            "pull_request_linkages":[{"repo":"o/r", "pr_number":1, "merge_commit_sha":"a"*40, "state":"merged",
                "merged_at":"2026-01-01T00:00:00Z", "closing_reference_verified":True, "base_branch":"main"}]}
    graph = tmp_path/"graph.json";graph.write_text(json.dumps({"graph_revision":1,"nodes":[node]}))
    ctx = module.context(tmp_path)
    produced = producer._backfill_done(root=tmp_path, context=ctx, coord=coord,
        events_path=coord/"events.json", events={"schema_version":"1.0","events":[]},
        graph_path=graph, graph=json.loads(graph.read_text()), node=node,
        task_artifact={"sha256":hashlib.sha256(task.read_bytes()).hexdigest()},
        requested_repo=None, requested_pr=None, bd_bridge=SCRIPTS/"bd-bridge.py", expected_workspace_id=None)
    assert produced["completion_event"]["backfilled_from_durable_completion"] is True
    assert not (coord/"leases.json").exists() and not (coord/"leases.lock").exists()
    before = {str(p.relative_to(coord)):p.read_bytes() for p in coord.rglob("*") if p.is_file()}
    monkeypatch.setattr(sys,"argv",[str(module.__file__),"--repo-root",str(tmp_path),"--op","list"])
    assert module.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["leases"]==[] and result["events"]==[produced["completion_event"]]
    assert {str(p.relative_to(coord)):p.read_bytes() for p in coord.rglob("*") if p.is_file()}==before


@pytest.mark.parametrize("change",["events","new_lock","new_ledger"])
def test_unlocked_c26_snapshot_rejects_concurrent_changes(tmp_path,monkeypatch,change):
    module,coord=fixture(tmp_path,monkeypatch);coord.mkdir()
    events_path=coord/"events.json"
    events_path.write_text('{"schema_version":"1.0","events":[{"type":"completion"}]}')
    original=module.load_json
    def concurrent_update(path):
        result=original(path)
        if change=="events": module.atomic_json(events_path,{"schema_version":"1.0","events":[]})
        elif change=="new_lock": (coord/"leases.lock").touch()
        else: (coord/"leases.json").write_text('{"leases":[]}')
        return result
    monkeypatch.setattr(module,"load_json",concurrent_update)
    with pytest.raises(module.ContractError,match="changed while reading"):
        module.read_only_snapshot(coord)
