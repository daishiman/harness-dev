"""C28 parity manifest の由来必須化と C16 stale 検出の回帰テスト。

守る不変条件は 2 つ。
1. parity manifest は「いつ・どの graph から作った snapshot か」を必ず持ち (C28 が fail-closed で
   検証する)、snapshot 生成後に graph が動いていれば schedule が停止する (silent な stale 推薦の禁止)。
2. ready 候補が manifest に載らなかった理由は対処 owner が分かる粒度で分離され、
   C28 で落ちた候補が C16 の report からも消えない (silent drop の禁止)。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    code = module.main()
    output = capsys.readouterr().out.strip()
    return code, json.loads(output) if output else None


PROVENANCE = {"generated_at": "2026-07-21T00:00:00Z", "source_graph_digest": "sha256:" + "d" * 64}


def bridge_with_issues(monkeypatch, issues: list[dict]):
    module = load("bd-bridge.py", "c28_parity_provenance")
    monkeypatch.setattr(
        module, "preflight",
        lambda root, expected=None: {"version": "1.1.0", "workspace_identity": {"workspace_id": "bdw_fixture"}},
    )
    by_id = {row["id"]: row for row in issues}

    def fake_bd(args, cwd, check=True):
        if args[0] == "ready":
            return issues
        if args[0] == "show":
            return by_id[args[1]]
        raise AssertionError(args)

    monkeypatch.setattr(module, "bd", fake_bd)
    return module


def test_c28_ready_rejects_parity_manifest_without_provenance(tmp_path, monkeypatch, capsys):
    module = bridge_with_issues(monkeypatch, [])
    manifest = tmp_path / "parity.json"

    manifest.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    with pytest.raises(module.ContractError, match="generated_at"):
        call_main(module, monkeypatch, capsys, "--op", "ready", "--repo-root", tmp_path, "--parity-manifest", manifest)

    manifest.write_text(json.dumps({"generated_at": "2026-07-21", "nodes": []}), encoding="utf-8")
    with pytest.raises(module.ContractError, match="RFC3339"):
        call_main(module, monkeypatch, capsys, "--op", "ready", "--repo-root", tmp_path, "--parity-manifest", manifest)

    manifest.write_text(json.dumps({**PROVENANCE, "source_graph_digest": "deadbeef", "nodes": []}), encoding="utf-8")
    with pytest.raises(module.ContractError, match="source_graph_digest"):
        call_main(module, monkeypatch, capsys, "--op", "ready", "--repo-root", tmp_path, "--parity-manifest", manifest)


def test_c28_ready_separates_unmapped_reasons_and_echoes_provenance(tmp_path, monkeypatch, capsys):
    issues = [
        {"id": "B-mapped", "status": "open", "dependencies": [], "external_ref": "dev-graph:node-a"},
        {"id": "B-drift", "status": "open", "dependencies": [], "external_ref": "dev-graph:node-b"},
        {"id": "B-orphan", "status": "open", "dependencies": [], "external_ref": "dev-graph:node-gone"},
        {"id": "B-native", "status": "open", "dependencies": [], "description": "hand written issue"},
    ]
    module = bridge_with_issues(monkeypatch, issues)
    manifest = tmp_path / "parity.json"
    manifest.write_text(json.dumps({
        **PROVENANCE,
        "nodes": [{
            "graph_node_id": "node-a", "bd_issue_id": "B-mapped",
            "graph_status": "active", "depends_on": [],
        }],
        # node-b は graph に実在するが投影から漏れた (= manifest 再生成の案件)。
        # node-gone は graph から消えている (= C02 案件) ので、この集合に載らない。
        "graph_node_ids": ["node-a", "node-b"],
    }), encoding="utf-8")

    code, receipt = call_main(
        module, monkeypatch, capsys,
        "--op", "ready", "--repo-root", tmp_path, "--parity-manifest", manifest,
    )
    assert code == 0
    assert [row["bd_issue_id"] for row in receipt["ready_set"]] == ["B-mapped"]
    reasons = {row["bd_issue_id"]: row["reason"] for row in receipt["unmapped"]}
    # 3 つの owner を混ぜない: 投影の取りこぼし (manifest 再生成) / graph から消えた参照 (C02) / graph 管理外。
    assert reasons == {
        "B-drift": "parity_manifest_missing",
        "B-orphan": "graph_node_missing",
        "B-native": "external_ref_absent",
    }
    assert receipt["unmapped_summary"] == {
        "external_ref_absent": 1, "graph_node_missing": 1, "parity_manifest_missing": 1,
    }
    assert receipt["parity_provenance"] == PROVENANCE


def test_c28_ready_rejects_parity_manifest_without_graph_node_ids(tmp_path, monkeypatch, capsys):
    """`graph_node_ids` 欠落を黙認すると、graph から消えた node への参照が投影の取りこぼしを装って常駐する。

    manifest は build-parity-manifest.py が毎回作り直す揮発 snapshot なので、欠落時の
    正しい回復は再生成であって従来の 1 つの札への丸め込みではない。
    """
    module = bridge_with_issues(monkeypatch, [])
    manifest = tmp_path / "parity.json"
    manifest.write_text(json.dumps({**PROVENANCE, "nodes": []}), encoding="utf-8")
    with pytest.raises(module.ContractError, match="graph_node_ids"):
        call_main(module, monkeypatch, capsys, "--op", "ready", "--repo-root", tmp_path, "--parity-manifest", manifest)


def schedule_workspace(tmp_path: Path, ready_payload: dict) -> tuple[Path, Path, Path]:
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": [{
        "graph_node_id": "beads-node", "artifact_kind": "task", "status": "active",
        "confirmation_status": "confirmed", "evaluation_status": "pass",
        "implementation_readiness": {"status": "complete"}, "depends_on": [],
        "tracker_binding": "beads", "resource_scope": ["a"],
    }]}), encoding="utf-8")
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps(ready_payload), encoding="utf-8")
    leases = tmp_path / "leases.json"
    leases.write_text(json.dumps({"leases": []}), encoding="utf-8")
    return graph, ready, leases


def test_c16_schedule_stops_on_stale_parity_provenance(tmp_path, monkeypatch, capsys):
    """由来の digest が現 graph と食い違えば、node 単位の parity が全て confirmed でも停止する。

    由来の有無そのものは C28 が manifest 受理時に fail-closed で検証する。C16 は C28 が receipt に
    載せた由来を graph 実体と突合する役で、manifest 生成後に足された/消された node を捕まえる。
    """
    schedule = load("schedule-graph.py", "c16_parity_provenance")
    entry = {
        "external_ref": "beads-node", "edge_parity": {"confirmed": True},
        "graph_status": "active", "graph_depends_on": [],
    }

    graph, ready, leases = schedule_workspace(tmp_path, {
        "parity_provenance": PROVENANCE, "ready_set": [entry],
    })
    with pytest.raises(schedule.ContractError, match="stale"):
        call_main(schedule, monkeypatch, capsys, "--graph", graph, "--ready-source", "bd-bridge",
                  "--ready-json", ready, "--leases", leases)


def test_c16_schedule_accepts_fresh_snapshot_and_surfaces_tracker_drift(tmp_path, monkeypatch, capsys):
    schedule = load("schedule-graph.py", "c16_parity_carry")
    graph, ready, leases = schedule_workspace(tmp_path, {})
    provenance = {
        "generated_at": "2026-07-21T00:00:00Z",
        "source_graph_digest": schedule._canonical_digest(json.loads(graph.read_text())),
    }
    ready.write_text(json.dumps({
        "parity_provenance": provenance,
        "ready_set": [{
            "external_ref": "beads-node", "edge_parity": {"confirmed": True},
            "graph_status": "active", "graph_depends_on": [],
        }],
        "unmapped": [{"bd_issue_id": "B-native", "external_ref": None, "reason": "external_ref_absent"}],
        "conflicts": [{"bd_issue_id": "B-conflict", "graph_node_id": "node-x", "reason": "Beads parity conflict"}],
    }), encoding="utf-8")

    code, plan = call_main(
        schedule, monkeypatch, capsys, "--graph", graph, "--ready-source", "bd-bridge",
        "--ready-json", ready, "--leases", leases,
    )
    assert code == 0 and plan["ready_set"]["tasks"] == ["beads-node"]
    assert plan["parity_provenance"] == provenance
    # C28 で落ちた候補は判定に使わないが、schedule report から消してはならない。
    carried = {row["bd_issue_id"]: row for row in plan["unmapped"] if row.get("source") == "bd-bridge"}
    assert set(carried) == {"B-native", "B-conflict"}
    assert carried["B-native"]["reason"] == "external_ref_absent"
    assert carried["B-conflict"]["reason"] == "Beads parity conflict"
