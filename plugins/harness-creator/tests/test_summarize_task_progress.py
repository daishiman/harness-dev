"""summarize-task-progress.py (TG-C05) の機能テスト — 進捗集計 + 実行時停滞検出。

conftest 非依存で module-level に importlib ロードする (自己完結テスト)。
網羅: by_state 集計 / completion_rate (total=0 含む) / blocked_tasks / route-*.json 件数 /
detect_stall の停滞判定条件 (ready_batch 空・running 0・未完了残存) /
kind 3 分類 (spec-gap=エッジ先不在 / build-failure=producer blocked / origin-failure=自身が
失敗起点) と has_spec_gap (spec-gap のみ true) / 非停滞は evaluated=true+stalled=false の
構造化 (ready_batch 非空 / running 有 / 全 done)・入力不足は evaluated=false /
blocked_reason 併記 (F9 連鎖) /
main() end-to-end (read-only・stall キー・resolve_build_dir 既定パス・exit2)。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


stp = _load("summarize-task-progress")


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _node(nid, state="pending", **extra) -> dict:
    base = {"id": nid, "state": state, "started_at": None, "lease_expires_at": None}
    base.update(extra)
    return base


def _state(*nodes) -> dict:
    return {"schema_version": "1.0", "graph_hash": None, "nodes": [dict(n) for n in nodes]}


def _write_route_report(build_dir: Path, name: str, covered=None) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    payload = {"route_id": name}
    if covered is not None:
        payload["covered_task_ids"] = covered
    (build_dir / name).write_text(json.dumps(payload), encoding="utf-8")


def _graph(nodes, edges) -> dict:
    return {
        "schema_version": "1.0",
        "nodes": [{"id": n} for n in nodes],
        "edges": list(edges),
    }


# ─────────────────────────── summarize: by_state ───────────────────────────
def test_summarize_by_state_counts(tmp_path):
    st = _state(_node("T1", "done"), _node("T2", "running"),
                _node("T3", "pending"), _node("T4", "blocked", blocked_reason="origin-failure"))
    out = stp.summarize(st, tmp_path)
    assert out["by_state"] == {"pending": 1, "running": 1, "done": 1, "blocked": 1}
    assert out["total"] == 4


def test_summarize_ignores_unknown_state(tmp_path):
    st = _state(_node("T1", "done"), _node("T2", "weird"))
    out = stp.summarize(st, tmp_path)
    assert out["by_state"] == {"pending": 0, "running": 0, "done": 1, "blocked": 0}
    assert out["total"] == 2  # total は node 数 (未知 state も含む)


# ─────────────────────────── summarize: completion_rate ───────────────────────────
def test_summarize_completion_rate(tmp_path):
    st = _state(_node("T1", "done"), _node("T2", "done"), _node("T3", "pending"), _node("T4", "running"))
    out = stp.summarize(st, tmp_path)
    assert out["completion_rate"] == pytest.approx(0.5)


def test_summarize_completion_rate_zero_total(tmp_path):
    out = stp.summarize(_state(), tmp_path)
    assert out["completion_rate"] == 0.0
    assert out["total"] == 0
    assert out["by_state"] == {"pending": 0, "running": 0, "done": 0, "blocked": 0}


# ─────────────────────────── summarize: blocked_tasks ───────────────────────────
def test_summarize_blocked_tasks(tmp_path):
    st = _state(_node("T1", "blocked", blocked_reason="origin-failure"),
                _node("T2", "pending"),
                _node("T3", "blocked", blocked_reason="propagated"))
    out = stp.summarize(st, tmp_path)
    assert out["blocked_tasks"] == ["T1", "T3"]


# ─────────────────────────── summarize: route-*.json 件数 ───────────────────────────
def test_summarize_route_report_count(tmp_path):
    _write_route_report(tmp_path, "route-r1.json")
    _write_route_report(tmp_path, "route-r2.json", covered=["T1", "T2"])
    (tmp_path / "task-state.json").write_text("{}", encoding="utf-8")  # route-* 以外は無視
    out = stp.summarize(_state(_node("T1")), tmp_path)
    assert out["route_report_count"] == 2
    assert out["route_reports"] == ["route-r1.json", "route-r2.json"]


def test_summarize_route_count_zero_when_none(tmp_path):
    out = stp.summarize(_state(_node("T1")), tmp_path)
    assert out["route_report_count"] == 0
    assert out["route_reports"] == []


def test_summarize_route_count_zero_when_build_dir_absent(tmp_path):
    out = stp.summarize(_state(_node("T1")), tmp_path / "does-not-exist")
    assert out["route_report_count"] == 0


# ─────────────────────────── summarize: purity ───────────────────────────
def test_summarize_does_not_mutate_input(tmp_path):
    st = _state(_node("T1", "done"))
    snapshot = json.dumps(st, sort_keys=True)
    stp.summarize(st, tmp_path)
    assert json.dumps(st, sort_keys=True) == snapshot


# ─────────────────────────── detect_stall: 停滞条件 ───────────────────────────
# 非停滞は None でなく評価済み構造 (evaluated=true・stalled=false) — 「評価して非停滞」を
# 「未評価 ({"evaluated": false})」から区別する。
_NOT_STALLED = {"evaluated": True, "stalled": False, "diagnosis": [], "has_spec_gap": False}


def test_detect_stall_not_stalled_when_ready_batch_nonempty():
    by = {"pending": 2, "running": 0, "done": 0, "blocked": 0}
    assert stp.detect_stall(by, ["T1"], _graph(["T1"], []), _state(_node("T1"))) == _NOT_STALLED


def test_detect_stall_not_stalled_when_running_present():
    by = {"pending": 1, "running": 1, "done": 0, "blocked": 0}
    assert stp.detect_stall(by, [], _graph(["T1", "T2"], []), _state()) == _NOT_STALLED


def test_detect_stall_not_stalled_when_all_done():
    by = {"pending": 0, "running": 0, "done": 3, "blocked": 0}
    assert stp.detect_stall(by, [], _graph(["T1"], []), _state()) == _NOT_STALLED


# ─────────────────────────── detect_stall: spec-gap ───────────────────────────
def test_detect_stall_spec_gap_kind():
    # T2 は task-graph 上に存在しない T4 を depends_on → spec-gap。
    graph = _graph(["T1", "T2", "T3"], [{"type": "depends_on", "from": "T2", "to": "T4"}])
    st = _state(_node("T1", "done"), _node("T2", "pending"), _node("T3", "pending"))
    by = {"pending": 2, "running": 0, "done": 1, "blocked": 0}
    out = stp.detect_stall(by, [], graph, st)
    assert out["evaluated"] is True and out["stalled"] is True
    assert out["has_spec_gap"] is True
    diag = [d for d in out["diagnosis"] if d["task_id"] == "T2"]
    assert len(diag) == 1
    assert diag[0]["kind"] == "spec-gap"
    assert "T4" in diag[0]["message"] and "task-graph 上に不在" in diag[0]["message"]


def test_detect_stall_spec_gap_carries_structured_emit_fields():
    """spec-gap 診断が emit-discovered-task 引数を機械導出できる構造化フィールドを携帯する。"""
    graph = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "T1"},
            {"id": "T2", "phase_ref": "P05", "write_scope": "plugins/acme/scripts/foo.py"},
        ],
        "edges": [{"type": "depends_on", "from": "T2", "to": "T4"}],  # T4 不在 → spec-gap
    }
    st = _state(_node("T1", "done"), _node("T2", "pending"))
    by = {"pending": 1, "running": 0, "done": 1, "blocked": 0}
    out = stp.detect_stall(by, [], graph, st)
    diag = [d for d in out["diagnosis"] if d["task_id"] == "T2"][0]
    # discovering_task_id=task_id / 欠落上流 / proposed_node の phase_ref・write_scope 既定供給元
    assert diag["missing_dependency_id"] == "T4"
    assert diag["stalled_task_phase_ref"] == "P05"
    assert diag["stalled_task_write_scope"] == "plugins/acme/scripts/foo.py"


# ─────────────────────────── detect_stall: build-failure ───────────────────────────
def test_detect_stall_build_failure_kind():
    # T2(pending) の producer T1 が blocked(origin-failure) → build-failure。
    graph = _graph(["T1", "T2"], [{"type": "depends_on", "from": "T2", "to": "T1"}])
    st = _state(_node("T1", "blocked", blocked_reason="origin-failure"), _node("T2", "pending"))
    by = {"pending": 1, "running": 0, "done": 0, "blocked": 1}
    out = stp.detect_stall(by, [], graph, st)
    assert out["stalled"] is True
    assert out["has_spec_gap"] is False
    diag = [d for d in out["diagnosis"] if d["task_id"] == "T2"]
    assert len(diag) == 1
    assert diag[0]["kind"] == "build-failure"
    assert "T1" in diag[0]["message"]


# ─────────────────────────── detect_stall: origin-failure (第3分類) ───────────────────────────
def test_detect_stall_origin_failure_kind_even_when_producers_done():
    # T2 自身が blocked(origin-failure)。producer T1 は done で依存経路の診断は出ないが、
    # 失敗起点そのものを diagnosis から直接特定できる (route_report 併記)。
    graph = _graph(["T1", "T2"], [{"type": "depends_on", "from": "T2", "to": "T1"}])
    st = _state(_node("T1", "done"),
                _node("T2", "blocked", blocked_reason="origin-failure",
                      route_report="route-r7.json"))
    by = {"pending": 0, "running": 0, "done": 1, "blocked": 1}
    out = stp.detect_stall(by, [], graph, st)
    assert out["stalled"] is True
    diag = [d for d in out["diagnosis"] if d["kind"] == "origin-failure"]
    assert len(diag) == 1
    assert diag[0]["task_id"] == "T2"
    assert diag[0]["route_report"] == "route-r7.json"
    assert "origin-failure" in diag[0]["message"]
    # has_spec_gap の意味は不変 (spec-gap のみ true)。
    assert out["has_spec_gap"] is False


def test_detect_stall_origin_failure_without_route_report_omits_key():
    # route_report を持たない state node では key 自体を出さない (optional)。
    graph = _graph(["T1"], [])
    st = _state(_node("T1", "blocked", blocked_reason="origin-failure"))
    by = {"pending": 0, "running": 0, "done": 0, "blocked": 1}
    out = stp.detect_stall(by, [], graph, st)
    diag = [d for d in out["diagnosis"] if d["kind"] == "origin-failure"]
    assert len(diag) == 1 and diag[0]["task_id"] == "T1"
    assert "route_report" not in diag[0]


def test_detect_stall_propagated_self_reason_gets_no_origin_entry():
    # 自身が blocked(propagated) は起点でないため origin-failure 診断は出ない。
    graph = _graph(["T1", "T2"], [{"type": "depends_on", "from": "T2", "to": "T1"}])
    st = _state(_node("T1", "blocked", blocked_reason="origin-failure"),
                _node("T2", "blocked", blocked_reason="propagated"))
    by = {"pending": 0, "running": 0, "done": 0, "blocked": 2}
    out = stp.detect_stall(by, [], graph, st)
    origin = [d for d in out["diagnosis"] if d["kind"] == "origin-failure"]
    assert [d["task_id"] for d in origin] == ["T1"]


def test_detect_stall_build_failure_via_consumes_edge():
    # artifact->consumer を produces で producer task へ逆引きする。
    graph = _graph(["T1", "T2"], [
        {"type": "produces", "from": "T1", "to": "A1"},
        {"type": "consumes", "from": "A1", "to": "T2"},
    ])
    st = _state(_node("T1", "blocked", blocked_reason="origin-failure"), _node("T2", "pending"))
    by = {"pending": 1, "running": 0, "done": 0, "blocked": 1}
    out = stp.detect_stall(by, [], graph, st)
    diag = [d for d in out["diagnosis"] if d["task_id"] == "T2"]
    assert len(diag) == 1 and diag[0]["kind"] == "build-failure"


def test_detect_stall_consumes_without_artifact_producer_is_spec_gap():
    graph = _graph(["T2"], [
        {"type": "consumes", "from": "A404", "to": "T2"},
    ])
    st = _state(_node("T2", "pending"))
    by = {"pending": 1, "running": 0, "done": 0, "blocked": 0}
    out = stp.detect_stall(by, [], graph, st)
    assert out["has_spec_gap"] is True
    diag = [d for d in out["diagnosis"] if d["task_id"] == "T2"]
    assert len(diag) == 1
    assert diag[0]["kind"] == "spec-gap"
    assert diag[0]["missing_artifact_id"] == "A404"
    assert "has no producer" in diag[0]["message"]


# ─────────────────────────── detect_stall: has_spec_gap 分岐 ───────────────────────────
def test_detect_stall_has_spec_gap_false_without_spec_gap():
    # spec-gap 以外 (build-failure 巻添え + origin-failure 起点) だけなら has_spec_gap=False。
    graph = _graph(["T1", "T2"], [{"type": "depends_on", "from": "T2", "to": "T1"}])
    st = _state(_node("T1", "blocked", blocked_reason="origin-failure"), _node("T2", "pending"))
    by = {"pending": 1, "running": 0, "done": 0, "blocked": 1}
    out = stp.detect_stall(by, [], graph, st)
    assert out["has_spec_gap"] is False
    assert {d["kind"] for d in out["diagnosis"]} == {"build-failure", "origin-failure"}


def test_detect_stall_mixed_has_spec_gap_true():
    # T2: producer T1 blocked (build-failure)。T3: 依存先 TX 不在 (spec-gap)。混在で has_spec_gap=True。
    graph = _graph(["T1", "T2", "T3"], [
        {"type": "depends_on", "from": "T2", "to": "T1"},
        {"type": "depends_on", "from": "T3", "to": "TX"},
    ])
    st = _state(_node("T1", "blocked", blocked_reason="origin-failure"),
                _node("T2", "pending"), _node("T3", "pending"))
    by = {"pending": 2, "running": 0, "done": 0, "blocked": 1}
    out = stp.detect_stall(by, [], graph, st)
    kinds = {d["task_id"]: d["kind"] for d in out["diagnosis"]}
    assert kinds["T2"] == "build-failure" and kinds["T3"] == "spec-gap"
    assert out["has_spec_gap"] is True


# ─────────────────────────── detect_stall: F9 blocked_reason 併記 / 連鎖 ───────────────────────────
def test_detect_stall_blocked_reason_in_message_chain():
    # T1(origin-failure) → T2(propagated) → T3(propagated) の伝播鎖。
    # 各診断が producer の blocked_reason を併記し起点 origin-failure を辿れる (F9)。
    graph = _graph(["T1", "T2", "T3"], [
        {"type": "depends_on", "from": "T2", "to": "T1"},
        {"type": "depends_on", "from": "T3", "to": "T2"},
    ])
    st = _state(
        _node("T1", "blocked", blocked_reason="origin-failure"),
        _node("T2", "blocked", blocked_reason="propagated"),
        _node("T3", "blocked", blocked_reason="propagated"),
    )
    by = {"pending": 0, "running": 0, "done": 0, "blocked": 3}
    out = stp.detect_stall(by, [], graph, st)
    msgs = {d["task_id"]: d["message"] for d in out["diagnosis"]}
    # T2 の診断は producer T1 の origin-failure を併記 (起点特定)。
    assert "origin-failure" in msgs["T2"]
    # T3 の診断は producer T2 の propagated を併記 (連鎖の中間)。
    assert "propagated" in msgs["T3"]
    assert out["has_spec_gap"] is False


def test_detect_stall_diagnosis_empty_when_no_dep_issue():
    # 停滞条件は満たすが producer が全て done → 診断は空 (has_spec_gap=False)。
    graph = _graph(["T1", "T2"], [{"type": "depends_on", "from": "T2", "to": "T1"}])
    st = _state(_node("T1", "done"), _node("T2", "pending"))
    by = {"pending": 1, "running": 0, "done": 1, "blocked": 0}
    out = stp.detect_stall(by, [], graph, st)
    assert out["stalled"] is True and out["diagnosis"] == [] and out["has_spec_gap"] is False


# ─────────────────────────── main() CLI ───────────────────────────
def test_main_reports_summary_and_stall(tmp_path, capsys):
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(
        _node("T1", "blocked", blocked_reason="origin-failure"), _node("T2", "pending"))),
        encoding="utf-8")
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(
        _graph(["T1", "T2"], [{"type": "depends_on", "from": "T2", "to": "T1"}])), encoding="utf-8")
    rc = stp.main([
        "--task-state", str(state_path), "--build-dir", str(tmp_path),
        "--ready-batch", "[]", "--task-graph", str(graph_path),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["by_state"]["blocked"] == 1
    assert out["stall"]["evaluated"] is True
    assert out["stall"]["stalled"] is True
    assert out["stall"]["has_spec_gap"] is False


def test_main_is_read_only(tmp_path):
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(_node("T1", "done"))), encoding="utf-8")
    before = {p.name: p.stat().st_mtime_ns for p in tmp_path.iterdir()}
    before_bytes = state_path.read_bytes()
    rc = stp.main(["--task-state", str(state_path), "--build-dir", str(tmp_path)])
    assert rc == 0
    after = {p.name: p.stat().st_mtime_ns for p in tmp_path.iterdir()}
    assert set(after) == set(before)  # 新規ファイルを一切書かない
    assert state_path.read_bytes() == before_bytes  # task-state を書き換えない


def test_main_stall_unevaluated_without_ready_batch(tmp_path, capsys):
    # 入力不足 (--ready-batch/--task-graph 欠落) は null でなく未評価マーカー
    # {"evaluated": false} — 「評価して非停滞」と区別できる。
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(_node("T1", "pending"))), encoding="utf-8")
    rc = stp.main(["--task-state", str(state_path), "--build-dir", str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stall"] == {"evaluated": False}


def test_main_default_path_from_resolve_build_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    build_dir = tmp_path / "eval-log/acme/build/20260706-x"
    build_dir.mkdir(parents=True)
    (build_dir / "task-state.json").write_text(
        json.dumps(_state(_node("T1", "done"), _node("T2", "pending"))), encoding="utf-8")
    _write_route_report(build_dir, "route-r1.json")
    rc = stp.main(["--target-plugin-slug", "acme", "--cycle-id", "20260706-x"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total"] == 2 and out["route_report_count"] == 1


def test_main_missing_task_state_exit2(tmp_path):
    rc = stp.main(["--task-state", str(tmp_path / "nope.json"), "--build-dir", str(tmp_path)])
    assert rc == 2


def test_main_requires_a_path_source_exit2():
    assert stp.main([]) == 2


def test_main_invalid_ready_batch_json_exit2(tmp_path):
    state_path = tmp_path / "task-state.json"
    state_path.write_text(json.dumps(_state(_node("T1", "pending"))), encoding="utf-8")
    rc = stp.main([
        "--task-state", str(state_path), "--build-dir", str(tmp_path),
        "--ready-batch", "not-json",
    ])
    assert rc == 2
