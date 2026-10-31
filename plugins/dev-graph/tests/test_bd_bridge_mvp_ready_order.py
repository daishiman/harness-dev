"""MVP-first: bd-bridge ready_set の表示順テスト。

守る不変条件は 3 つ。
1. ready_set は (MVP_FIT_RANK, external_ref) 順で返り、MVP に直結する候補が先に見える。
   rank は schedule-graph の選定順と同じ定数で、両者の順は食い違わない。
2. manifest 行の mvp_fit はキー欠落 / null のみ未設定 rank へ tolerant fallback し、
   enum 外の非 null 値は per-candidate ContractError として conflicts[] へ転記する
   (他候補は落とさない)。
3. MVP_FIT_RANK の非 null key は manifest generator (build-parity-manifest.py) の受理集合と
   一致する。食い違うと、generator が通した値を C28 が conflicts へ落とす (またはその逆) ため。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
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


def bridge_with_issues(monkeypatch, issues: list[dict], name: str):
    module = load("bd-bridge.py", name)
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


def issue(issue_id: str, node_id: str) -> dict:
    return {"id": issue_id, "status": "open", "dependencies": [], "external_ref": f"dev-graph:{node_id}"}


def manifest_row(issue_id: str, node_id: str, **extra) -> dict:
    return {"graph_node_id": node_id, "bd_issue_id": issue_id,
            "graph_status": "active", "depends_on": [], **extra}


def ready_receipt(module, monkeypatch, capsys, tmp_path: Path, rows: list[dict]):
    manifest = tmp_path / "parity.json"
    # graph_node_ids は「snapshot 時点で graph に実在した node の全集合」。この fixture では
    # 投影対象 (`nodes`) がそのまま実在集合なので rows から導出する。
    manifest.write_text(json.dumps({
        **PROVENANCE, "nodes": rows,
        "graph_node_ids": sorted({row["graph_node_id"] for row in rows}),
    }), encoding="utf-8")
    return call_main(
        module, monkeypatch, capsys,
        "--op", "ready", "--repo-root", tmp_path, "--parity-manifest", manifest,
    )


def test_ready_set_sorted_by_mvp_rank_then_external_ref(tmp_path, monkeypatch, capsys):
    """external_ref 辞書順では deferred が先頭に来る配置でも rank が勝つ。"""
    issues = [issue("B-a", "node-a"), issue("B-b", "node-b"), issue("B-c", "node-c"), issue("B-d", "node-d")]
    module = bridge_with_issues(monkeypatch, issues, "mvp_bridge_sort")
    code, receipt = ready_receipt(module, monkeypatch, capsys, tmp_path, [
        manifest_row("B-a", "node-a", mvp_fit="deferred"),
        manifest_row("B-b", "node-b"),
        manifest_row("B-c", "node-c", mvp_fit="enabling"),
        manifest_row("B-d", "node-d", mvp_fit="direct"),
    ])
    assert code == 0
    assert [row["external_ref"] for row in receipt["ready_set"]] == [
        "node-d", "node-c", "node-b", "node-a"]
    assert [row["mvp_fit"] for row in receipt["ready_set"]] == [
        "direct", "enabling", None, "deferred"]
    assert receipt["conflicts"] == []


def test_missing_or_null_mvp_fit_falls_back_tolerantly(tmp_path, monkeypatch, capsys):
    """キー欠落 / null は未設定 rank (2) へ fallback し ContractError にしない。"""
    issues = [issue("B-a", "node-a"), issue("B-b", "node-b")]
    module = bridge_with_issues(monkeypatch, issues, "mvp_bridge_tolerant")
    code, receipt = ready_receipt(module, monkeypatch, capsys, tmp_path, [
        manifest_row("B-a", "node-a"),
        manifest_row("B-b", "node-b", mvp_fit=None),
    ])
    assert code == 0
    assert receipt["conflicts"] == []
    # 同 rank (未設定 2) 同士は external_ref 辞書順。
    assert [(row["external_ref"], row["mvp_fit"]) for row in receipt["ready_set"]] == [
        ("node-a", None), ("node-b", None)]


def test_invalid_mvp_fit_moves_candidate_to_conflicts(tmp_path, monkeypatch, capsys):
    """不正行のみ conflicts[] へ転記し、正常行は返す (per-candidate fail-closed)。"""
    issues = [issue("B-a", "node-a"), issue("B-b", "node-b"), issue("B-c", "node-c")]
    module = bridge_with_issues(monkeypatch, issues, "mvp_bridge_conflict")
    code, receipt = ready_receipt(module, monkeypatch, capsys, tmp_path, [
        manifest_row("B-a", "node-a", mvp_fit="invalid"),
        manifest_row("B-b", "node-b", mvp_fit="direct"),
        manifest_row("B-c", "node-c"),
    ])
    assert code == 0
    assert [row["external_ref"] for row in receipt["ready_set"]] == ["node-b", "node-c"]
    assert len(receipt["conflicts"]) == 1
    conflict = receipt["conflicts"][0]
    assert conflict["bd_issue_id"] == "B-a" and conflict["graph_node_id"] == "node-a"
    assert "unsupported mvp_fit" in conflict["reason"]


def test_rank_keys_match_the_manifest_generator_vocabulary():
    """C28 が受ける mvp_fit と generator が書く mvp_fit を同じ語彙に固定する。"""
    bridge = load("bd-bridge.py", "mvp_rank_bridge_side")
    generator = load("build-parity-manifest.py", "mvp_rank_generator_side")
    assert bridge.MVP_FIT_RANK == {"direct": 0, "enabling": 1, None: 2, "deferred": 3}
    for fit in (key for key in bridge.MVP_FIT_RANK if key is not None):
        node = {"graph_node_id": "node-a", "mvp_alignment": {"mvp_fit": fit}}
        assert generator._mvp_fit(node) == fit
    try:
        generator._mvp_fit({"graph_node_id": "node-a", "mvp_alignment": {"mvp_fit": "invalid"}})
    except generator.ContractError as exc:
        assert "unsupported mvp_fit" in str(exc)
    else:
        raise AssertionError("generator accepted an mvp_fit outside MVP_FIT_RANK")


def test_schedule_selects_in_the_same_rank_order_the_bridge_displays():
    """C16 の選定順と C28 の表示順は同じ rank で決まる (schedule-graph は定数を複製せず import する)。"""
    schedule = load("schedule-graph.py", "mvp_rank_schedule_side")
    bridge = load("bd-bridge.py", "mvp_rank_bridge_side_for_schedule")
    assert schedule.MVP_FIT_RANK == bridge.MVP_FIT_RANK
