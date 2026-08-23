"""plan-dispatch-batch.py (TG-C10) の機能テスト — dispatch batch 機械導出器。

conftest 非依存で module-level に importlib ロードする自己完結テスト。束ね規則
(route 束ね / 決定論 validator 直実行判別 / conflict・file_ownership・max-workers 選抜 /
判別不能の fail-closed subagent 倒し) と TG-C01/TG-C03 subprocess 境界 (monkeypatch) を
網羅する。TG-C01 の ready-set 算出自体は test_dispatch_ready_set.py が正本。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), SCRIPTS / f"{stem}.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pdb = _load("plan-dispatch-batch")


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _node(nid, title="do work", entity_ref=None, phase_ref="P05", write_scope=None, **extra):
    return {"id": nid, "title": title, "phase_ref": phase_ref, "entity_ref": entity_ref,
            "state": "pending", "write_scope": write_scope or f"a/{nid}", **extra}


def _handoff(routes=None, plan_dir="plan"):
    return {"plan_dir": plan_dir, "target_plugin_slug": "x", "routes": routes or []}


def _write(path: Path, obj) -> str:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _fake_ready_set(ready, conflicts=None, blocked=None, pin=None, rc=0):
    payload = json.dumps({"ready_batch": ready, "conflicts": conflicts or [],
                          "blocked": blocked or [], "graph_hash_pin": pin,
                          "source": "compute-ready-set.py"})

    def _fake(task_graph, task_state, planner_root, repo_root):
        return subprocess.CompletedProcess(args=[], returncode=rc, stdout=payload, stderr="")

    return _fake


def _fake_inject_ok(task_graph, task_state, task_id):
    return subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout=json.dumps({"injected_inputs": [], "injected_notes": []}), stderr="")


def _run(tmp_path, monkeypatch, capsys, nodes, handoff, ready, conflicts=None,
         in_flight=None, max_workers=2, inject=_fake_inject_ok, repo_root=None):
    gp = _write(tmp_path / "task-graph.json", {"schema_version": "1.0", "nodes": nodes, "edges": []})
    sp = _write(tmp_path / "task-state.json", {"schema_version": "1.0", "graph_hash": None, "nodes": []})
    hp = _write(tmp_path / "handoff.json", handoff)
    monkeypatch.setattr(pdb, "invoke_ready_set", _fake_ready_set(ready, conflicts))
    monkeypatch.setattr(pdb, "invoke_inject", inject)
    argv = ["--task-graph", gp, "--task-state", sp, "--handoff", hp,
            "--max-workers", str(max_workers), "--repo-root", str(repo_root or tmp_path)]
    if in_flight is not None:
        argv += ["--in-flight", _write(tmp_path / "in-flight.json", in_flight)]
    rc = pdb.main(argv)
    out = capsys.readouterr().out
    return rc, (json.loads(out) if out.strip() else {})


def _make_validator(repo_root: Path, rel="plugins/x/scripts/validate-foo.py") -> str:
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return rel


# ─────────────────── resolve_validator_command (判別規則の単体) ───────────────────
def test_validator_command_resolved_for_deterministic_item(tmp_path):
    rel = _make_validator(tmp_path)
    node = _node("P05-x-01", title=f"`python3 {rel} --strict` が exit 0 で通る。")
    assert pdb.resolve_validator_command(node, str(tmp_path)) == f"python3 {rel} --strict"


def test_validator_command_fail_closed_cases(tmp_path):
    rel = _make_validator(tmp_path)
    cases = {
        "no-command": _node("T", title="設計意図が文書化されている。"),
        "two-commands": _node("T", title=f"`python3 {rel}` と `python3 {rel} --b` の両方。"),
        "shell-meta": _node("T", title=f"`python3 {rel} && rm -rf /` が通る。"),
        "not-validator-name": _node("T", title="`python3 plugins/x/scripts/build-thing.py` が通る。"),
        "missing-script": _node("T", title="`python3 plugins/x/scripts/validate-nope.py` が通る。"),
    }
    for label, node in cases.items():
        assert pdb.resolve_validator_command(node, str(tmp_path)) is None, label


# ─────────────────── (i) direct / subagent / delayed 振り分け ───────────────────
def test_ready_nodes_split_into_direct_subagent_delayed(tmp_path, monkeypatch, capsys):
    rel = _make_validator(tmp_path)
    nodes = [
        # 決定論 validator で閉じる checklist 項目 → direct (同一 phase+command で束ね)
        _node("P05-x-01", title=f"`python3 {rel}` が exit 0。"),
        _node("P05-x-02", title=f"`python3 {rel}` が exit 0。"),
        # route を消費する実装ノード 2 件 → 1 route batch へ束ね
        _node("B-C01-a", entity_ref="C01", write_scope="plugins/x/skills/run-x/a"),
        _node("B-C01-b", entity_ref="C01", write_scope="plugins/x/skills/run-x/b"),
        # 意味解釈が要る plan ノード → 単独 subagent batch
        _node("P03-x-01", phase_ref="P03", title="設計レビュー所見が記録されている。"),
        # max-workers=2 超過分 → delayed
        _node("P04-x-01", phase_ref="P04", title="受入テスト設計が揃っている。"),
    ]
    handoff = _handoff(routes=[{"id": "C01", "build_target": "plugins/x/skills/run-x/"}])
    ready = [n["id"] for n in nodes]
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, handoff, ready)
    assert rc == 0
    assert out["direct_validator_batch"] == [
        {"task_ids": ["P05-x-01", "P05-x-02"], "phase_ref": "P05", "command": f"python3 {rel}"}
    ]
    batches = out["subagent_batches"]
    assert [b["route_id"] for b in batches] == ["C01", None]
    assert batches[0]["task_ids"] == ["B-C01-a", "B-C01-b"]
    assert "plugins/x/skills/run-x/" in batches[0]["file_ownership"]  # route build_target を加算
    assert batches[1]["task_ids"] == ["P03-x-01"]
    assert out["delayed"] == [{"task_id": "P04-x-01", "reason": "max-workers"}]


# ─────────────────── (ii) conflict ペアは同時 batch に入らない ───────────────────
def test_conflict_pair_not_co_dispatched(tmp_path, monkeypatch, capsys):
    nodes = [_node("T1"), _node("T2")]
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, _handoff(),
                   ready=["T1", "T2"], conflicts=[["T1", "T2"]])
    assert rc == 0
    dispatched = [t for b in out["subagent_batches"] for t in b["task_ids"]]
    assert dispatched == ["T1"]  # 決定論順で先勝ち
    assert out["delayed"] == [{"task_id": "T2", "reason": "conflict:['T1', 'T2']"}]


def test_file_ownership_conflict_with_in_flight_delays(tmp_path, monkeypatch, capsys):
    nodes = [_node("T1", write_scope="plugins/x/skills/run-x/a"), _node("T2", write_scope="b/T2")]
    in_flight = [{"task_id": "RUN", "file_ownership": ["plugins/x/skills/run-x/"]}]
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, _handoff(),
                   ready=["T1", "T2"], in_flight=in_flight)
    assert rc == 0
    assert [t for b in out["subagent_batches"] for t in b["task_ids"]] == ["T2"]
    assert out["delayed"] == [{"task_id": "T1", "reason": "file-ownership-conflict"}]


def test_in_flight_consumes_worker_capacity(tmp_path, monkeypatch, capsys):
    nodes = [_node("T1"), _node("T2")]
    in_flight = [{"task_id": "RUN", "file_ownership": ["z/RUN"]}]
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, _handoff(),
                   ready=["T1", "T2"], in_flight=in_flight, max_workers=2)
    assert rc == 0
    assert [t for b in out["subagent_batches"] for t in b["task_ids"]] == ["T1"]
    assert out["delayed"] == [{"task_id": "T2", "reason": "max-workers"}]


# ─────────────────── (iii) 判別不能ノードは SubAgent 側へ倒れる ───────────────────
def test_indeterminate_nodes_fail_closed_to_subagent(tmp_path, monkeypatch, capsys):
    rel = _make_validator(tmp_path)
    nodes = [
        # command 2 件で曖昧 → direct に入れず subagent へ
        _node("T1", title=f"`python3 {rel}` と `python3 {rel} --b` の両方が exit 0。"),
        # entity_ref が handoff routes に不在 → route join 不能 → 単独 subagent へ
        _node("T2", entity_ref="C404"),
    ]
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, _handoff(), ready=["T1", "T2"])
    assert rc == 0
    assert out["direct_validator_batch"] == []
    assert [(b["route_id"], b["task_ids"]) for b in out["subagent_batches"]] == [
        (None, ["T1"]), (None, ["T2"]),
    ]
    assert out["delayed"] == []


# ─────────────────── 最小コンテキスト (③) と TG-C03 fail-closed ───────────────────
def test_context_files_carry_phase_file_and_injected_inputs(tmp_path, monkeypatch, capsys):
    plan = tmp_path / "plan"
    plan.mkdir()
    phase = plan / "phase-03-design-review.md"
    phase.write_text("# P03\n", encoding="utf-8")

    def _inject(task_graph, task_state, task_id):
        return subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"injected_inputs": [
                {"producer_task_id": "UP", "artifact_path": "artifacts/up.json"}
            ], "injected_notes": []}), stderr="")

    nodes = [_node("P03-x-01", phase_ref="P03")]
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, _handoff(plan_dir="plan"),
                   ready=["P03-x-01"], inject=_inject)
    assert rc == 0
    files = out["subagent_batches"][0]["context_files"]
    assert str(phase) in files
    assert "artifacts/up.json" in files


def test_inject_rejection_delays_batch(tmp_path, monkeypatch, capsys):
    def _inject_reject(task_graph, task_state, task_id):
        return subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout=json.dumps({"rejected": True, "reason": "producer not done"}), stderr="")

    nodes = [_node("T1")]
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, _handoff(),
                   ready=["T1"], inject=_inject_reject)
    assert rc == 0
    assert out["subagent_batches"] == []
    assert out["delayed"] == [{"task_id": "T1", "reason": "inject-rejected:T1"}]


# ─────────────────── TG-C01 境界 (pin mismatch / 失敗透過) ───────────────────
def test_graph_hash_pin_mismatch_exit1(tmp_path, monkeypatch, capsys):
    def _mismatch(task_graph, task_state, planner_root, repo_root):
        return subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout=json.dumps({"ready_batch": [], "conflicts": [], "blocked": [],
                               "graph_hash_pin": "mismatch"}), stderr="")

    gp = _write(tmp_path / "task-graph.json", {"nodes": [], "edges": []})
    sp = _write(tmp_path / "task-state.json", {"nodes": []})
    hp = _write(tmp_path / "handoff.json", _handoff())
    monkeypatch.setattr(pdb, "invoke_ready_set", _mismatch)
    rc = pdb.main(["--task-graph", gp, "--task-state", sp, "--handoff", hp])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["graph_hash_pin"] == "mismatch"
    assert out["subagent_batches"] == []


def test_ready_set_failure_exit1_without_dispatch(tmp_path, monkeypatch, capsys):
    def _boom(task_graph, task_state, planner_root, repo_root):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")

    gp = _write(tmp_path / "task-graph.json", {"nodes": [], "edges": []})
    sp = _write(tmp_path / "task-state.json", {"nodes": []})
    hp = _write(tmp_path / "handoff.json", _handoff())
    monkeypatch.setattr(pdb, "invoke_ready_set", _boom)
    assert pdb.main(["--task-graph", gp, "--task-state", sp, "--handoff", hp]) == 1


# ─────────────────── usage / IO ───────────────────
def test_missing_handoff_path_exit2(tmp_path):
    gp = _write(tmp_path / "task-graph.json", {"nodes": [], "edges": []})
    sp = _write(tmp_path / "task-state.json", {"nodes": []})
    assert pdb.main(["--task-graph", gp, "--task-state", sp,
                     "--handoff", str(tmp_path / "nope.json")]) == 2


def test_out_writes_same_payload(tmp_path, monkeypatch, capsys):
    nodes = [_node("T1")]
    gp = _write(tmp_path / "task-graph.json", {"nodes": nodes, "edges": []})
    sp = _write(tmp_path / "task-state.json", {"nodes": []})
    hp = _write(tmp_path / "handoff.json", _handoff())
    monkeypatch.setattr(pdb, "invoke_ready_set", _fake_ready_set(["T1"]))
    monkeypatch.setattr(pdb, "invoke_inject", _fake_inject_ok)
    outp = tmp_path / "batch.json"
    rc = pdb.main(["--task-graph", gp, "--task-state", sp, "--handoff", hp,
                   "--repo-root", str(tmp_path), "--out", str(outp)])
    assert rc == 0
    assert json.loads(outp.read_text(encoding="utf-8")) == json.loads(capsys.readouterr().out)


def test_route_batch_invokes_input_resolver_once(tmp_path, monkeypatch, capsys):
    calls = []

    def _inject(task_graph, task_state, task_ids):
        calls.append(task_ids)
        return subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"tasks": [
                {"task_id": task_id, "injected_inputs": [], "injected_notes": []}
                for task_id in task_ids
            ]}), stderr="",
        )

    nodes = [_node("A", entity_ref="C01"), _node("B", entity_ref="C01")]
    handoff = _handoff(routes=[{"id": "C01", "build_target": "plugins/x/c01"}])
    rc, out = _run(tmp_path, monkeypatch, capsys, nodes, handoff, ["A", "B"], inject=_inject)
    assert rc == 0 and len(out["subagent_batches"]) == 1
    assert calls == [["A", "B"]]


def test_execution_contract_classification_is_unit_atomic_and_projects_gate(tmp_path):
    graph = {"nodes": [
        _node("C1", execution_kind="verification-claim"),
        _node("C2", execution_kind="verification-claim"),
        _node("P01", execution_kind="phase-gate"),
    ], "edges": []}
    contract = {"obligations": [{
        "id": "unit:global:P01", "stage": "draft", "depends_on": [],
        "parameters": {"covered_task_ids": ["C1", "C2"], "execution_unit": {
            "id": "unit:global:P01", "phase_ref": "P01", "route_id": None,
            "covered_task_ids": ["C1", "C2"],
        }},
    }], "proof_projections": [{
        "task_id": "P01", "dispatch": "none", "required_claim_ids": ["C1", "C2"],
        "required_unit_ids": ["unit:global:P01"],
        "proof_policy": "all-claims-done-with-unique-evidence-report-ref",
    }]}
    pending = {"nodes": [_node("C1"), _node("C2"), _node("P01")]}
    candidates, projections = pdb.classify_execution_units(graph, pending, contract, {}, "draft")
    assert [(item["unit_id"], item["task_ids"]) for item in candidates] == [
        ("unit:global:P01", ["C1", "C2"]),
    ]
    assert projections == []
    done = {"nodes": [_node("C1", state="done"), _node("C2", state="done"), _node("P01")]}
    candidates, projections = pdb.classify_execution_units(graph, done, contract, {}, "draft")
    assert candidates == [] and [item["task_id"] for item in projections] == ["P01"]


def test_execution_contract_classification_fails_closed_on_duplicate_coverage():
    graph = {"nodes": [_node("C1", execution_kind="verification-claim")], "edges": []}
    contract = {"obligations": [
        {"id": "U1", "stage": "draft", "depends_on": [], "parameters": {"covered_task_ids": ["C1"],
            "execution_unit": {"id": "U1", "phase_ref": "P01", "covered_task_ids": ["C1"]}}},
        {"id": "U2", "stage": "draft", "depends_on": [], "parameters": {"covered_task_ids": ["C1"],
            "execution_unit": {"id": "U2", "phase_ref": "P01", "covered_task_ids": ["C1"]}}},
    ]}
    import pytest
    with pytest.raises(ValueError, match="重複割当"):
        pdb.classify_execution_units(graph, {"nodes": []}, contract, {}, "draft")


def test_execution_contract_classification_fails_closed_on_duplicate_unit_id():
    graph = {"nodes": [_node("C1", execution_kind="verification-claim"),
                       _node("C2", execution_kind="verification-claim")], "edges": []}
    contract = {"obligations": [
        {"id": "U", "stage": "draft", "depends_on": [], "parameters": {"covered_task_ids": ["C1"],
            "execution_unit": {"id": "U", "phase_ref": "P01", "covered_task_ids": ["C1"]}}},
        {"id": "U", "stage": "draft", "depends_on": [], "parameters": {"covered_task_ids": ["C2"],
            "execution_unit": {"id": "U", "phase_ref": "P01", "covered_task_ids": ["C2"]}}},
    ]}
    import pytest
    with pytest.raises(ValueError, match="unit id 重複"):
        pdb.classify_execution_units(graph, {"nodes": []}, contract, {}, "draft")


def test_execution_contract_classification_fails_closed_on_covered_copy_mismatch():
    graph = {"nodes": [_node("C1", execution_kind="verification-claim")], "edges": []}
    contract = {"obligations": [{
        "id": "U", "stage": "draft", "depends_on": [], "parameters": {"covered_task_ids": ["OTHER"],
            "execution_unit": {"id": "U", "phase_ref": "P01", "covered_task_ids": ["C1"]}},
    }]}
    import pytest
    with pytest.raises(ValueError, match="二重表現"):
        pdb.classify_execution_units(graph, {"nodes": []}, contract, {}, "draft")
