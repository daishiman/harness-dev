"""project-task-status.py (TG-C09) の機能テスト — live 状態の plan dir 投影。

task-graph.json (構造) + task-state.json (live 状態) を merge した派生ビュー
(task-graph-status.json + task-progress.md + task-execution-report.html) が完了を反映し、task-graph.json/task-state.json を
書き換えないこと (単一 writer 不変条件温存)、discovered inbox の未処理タスクが載ることを固定する。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pts = _load("project-task-status")


def _plan(tmp_path: Path):
    """P05 の 2 node graph (C05/C06) + task-state (C05 done / C06 pending)。"""
    graph = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "P05-C05-01", "title": "C05 実装", "phase_ref": "P05",
             "entity_ref": "C05", "state": "pending", "write_scope": "plugins/x/c05.py"},
            {"id": "P05-C06-01", "title": "C06 実装", "phase_ref": "P05",
             "entity_ref": "C06", "state": "pending", "write_scope": "plugins/x/c06.py"},
        ],
        "edges": [{"type": "depends_on", "from": "P05-C06-01", "to": "P05-C05-01"}],
    }
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    build = tmp_path / "build"
    build.mkdir()
    state = {
        "schema_version": "1.0", "graph_hash": "sha256:" + "a" * 64,
        "nodes": [
            {"id": "P05-C05-01", "state": "done", "started_at": None, "lease_expires_at": None},
            {"id": "P05-C06-01", "state": "running", "started_at": None, "lease_expires_at": None},
        ],
    }
    state_path = build / "task-state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return graph_path, state_path


def test_projection_reflects_live_state(tmp_path):
    graph_path, state_path = _plan(tmp_path)
    rc = pts.main(["--task-graph", str(graph_path), "--task-state", str(state_path)])
    assert rc == 0
    status = json.loads((tmp_path / "task-graph-status.json").read_text(encoding="utf-8"))
    by_id = {n["id"]: n["state"] for n in status["nodes"]}
    # task-graph.json は pending だが投影は task-state を overlay して done/running を反映。
    assert by_id["P05-C05-01"] == "done"
    assert by_id["P05-C06-01"] == "running"
    assert status["summary"]["by_state"]["done"] == 1


def test_projection_does_not_mutate_sources(tmp_path):
    graph_path, state_path = _plan(tmp_path)
    before_graph = graph_path.read_text(encoding="utf-8")
    before_state = state_path.read_text(encoding="utf-8")
    pts.main(["--task-graph", str(graph_path), "--task-state", str(state_path)])
    # 単一 writer 不変条件: task-graph.json / task-state.json は不変。
    assert graph_path.read_text(encoding="utf-8") == before_graph
    assert state_path.read_text(encoding="utf-8") == before_state


def test_progress_md_generated_with_icons(tmp_path):
    graph_path, state_path = _plan(tmp_path)
    pts.main(["--task-graph", str(graph_path), "--task-state", str(state_path)])
    md = (tmp_path / "task-progress.md").read_text(encoding="utf-8")
    assert "✓ `P05-C05-01`" in md          # done アイコン
    assert "▶ `P05-C06-01`" in md          # running アイコン
    assert "## P05" in md
    assert "凡例:" in md                     # アイコン凡例行 (人間可読性)
    assert "✗=blocked" in md                # docstring と _STATE_ICON が blocked=✗ で一致


def test_html_report_is_self_contained_structured_and_accessible(tmp_path):
    graph_path, state_path = _plan(tmp_path)
    rc = pts.main(["--task-graph", str(graph_path), "--task-state", str(state_path)])
    assert rc == 0
    html = (tmp_path / "task-execution-report.html").read_text(encoding="utf-8")
    assert '<html lang="ja">' in html
    assert 'data-report-mode="report"' in html
    assert 'id="overview-title"' in html
    assert 'id="routes-title"' in html
    assert 'id="tasks-title"' in html
    assert '<svg class="donut"' in html
    assert 'aria-label="タスク仕様書からHTML実行記録までの流れ"' in html
    assert 'class="flow-scroll" tabindex="0"' in html
    assert "overflow-x:auto" in html           # 狭幅は図だけを横スクロールし body overflow を防ぐ
    assert "https://" not in html            # 外部 CDN / 外部 runtime なし
    assert "@media print" in html
    assert "task-progress.md" in html         # Markdown 原本への導線を維持


def test_html_report_escapes_task_and_route_content(tmp_path):
    graph_path, state_path = _plan(tmp_path)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["nodes"][0]["title"] = '<script>alert("task")</script>'
    graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    route = {
        "route_id": "C05", "component_kind": "skill", "name": "run-safe",
        "build_target": "plugins/x/<unsafe>", "status": "success",
        "summary": '<img src=x onerror=alert("route")>',
        "evidence": ["pytest <ok>"], "deviations": [], "covered_task_ids": ["P05-C05-01"],
    }
    (state_path.parent / "route-C05.json").write_text(
        json.dumps(route, ensure_ascii=False), encoding="utf-8",
    )
    pts.main(["--task-graph", str(graph_path), "--task-state", str(state_path)])
    html = (tmp_path / "task-execution-report.html").read_text(encoding="utf-8")
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;alert" in html
    assert "&lt;img src=x" in html


def test_html_report_includes_build_summary_route_evidence_and_is_deterministic(tmp_path):
    graph_path, state_path = _plan(tmp_path)
    route = {
        "route_id": "C05", "component_kind": "skill", "name": "run-build-safe",
        "build_target": "plugins/x/skills/run-build-safe/", "status": "success",
        "summary": "安全な build を完了", "evidence": ["pytest 12 passed"],
        "deviations": ["なし"], "covered_task_ids": ["P05-C05-01"],
    }
    (state_path.parent / "route-C05.json").write_text(
        json.dumps(route, ensure_ascii=False), encoding="utf-8",
    )
    (state_path.parent / "build-summary.json").write_text(json.dumps({
        "completion_gate": {"completion_gate": "ok"},
        "outer_loop_rounds": [{"round": 1, "origin": "仕様差分", "result": "再導出済"}],
    }, ensure_ascii=False), encoding="utf-8")

    args = ["--task-graph", str(graph_path), "--task-state", str(state_path)]
    assert pts.main(args) == 0
    first = (tmp_path / "task-execution-report.html").read_bytes()
    assert pts.main(args) == 0
    second = (tmp_path / "task-execution-report.html").read_bytes()
    assert first == second                       # 時刻等を埋め込まない決定論投影
    html = first.decode("utf-8")
    assert "C05 · run-build-safe" in html
    assert "pytest 12 passed" in html
    assert "completion gate ok" in html
    assert "仕様差分" in html and "再導出済" in html
    status = json.loads((tmp_path / "task-graph-status.json").read_text(encoding="utf-8"))
    assert status["route_reports"][0]["route_id"] == "C05"
    assert status["build_summary"]["completion_gate"]["completion_gate"] == "ok"


def test_discovered_pending_listed(tmp_path):
    graph_path, state_path = _plan(tmp_path)
    inbox = tmp_path / "discovered-tasks"
    inbox.mkdir()
    (inbox / "d1.json").write_text(json.dumps({
        "discovering_task_id": "P05-C05-01", "reason": "契約の欠落列を発見",
        "discovered_at_artifact": "x", "change_level": "additive", "status": "pending",
        "proposed_node": {"id": "P05-C07-01", "title": "欠落列を補う", "phase_ref": "P05",
                          "entity_ref": "C07", "state": "pending", "write_scope": "plugins/x/c07.py"},
    }), encoding="utf-8")
    # accepted は載せない (terminal)。
    (inbox / "d2.json").write_text(json.dumps({
        "discovering_task_id": "P05-C05-01", "reason": "済", "discovered_at_artifact": "x",
        "change_level": "additive", "status": "accepted",
        "proposed_node": {"id": "P05-C08-01", "title": "済", "phase_ref": "P05",
                          "entity_ref": "C08", "state": "pending", "write_scope": "plugins/x/c08.py"},
    }), encoding="utf-8")
    pts.main(["--task-graph", str(graph_path), "--task-state", str(state_path),
              "--discovered-inbox", str(inbox)])
    status = json.loads((tmp_path / "task-graph-status.json").read_text(encoding="utf-8"))
    ids = [d["proposed_id"] for d in status["discovered_pending"]]
    assert "P05-C07-01" in ids
    assert "P05-C08-01" not in ids          # accepted は除外


def test_summary_uses_full_graph_denominator_on_sparse_state(tmp_path):
    # バグ回帰: task-state は build 中 sparse (遷移 node のみ)。3 node graph + done 1件のみの
    # task-state で、完了率は full graph 分母 (1/3) になり sparse な task-state 件数 (1/1=100%) に
    # ならない (同一文書内のチェックリスト母集団と矛盾させない)。
    graph = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "P05-C05-01", "title": "a", "phase_ref": "P05", "entity_ref": "C05",
             "state": "pending", "write_scope": "x"},
            {"id": "P05-C06-01", "title": "b", "phase_ref": "P05", "entity_ref": "C06",
             "state": "pending", "write_scope": "y"},
            {"id": "P05-C07-01", "title": "c", "phase_ref": "P05", "entity_ref": "C07",
             "state": "pending", "write_scope": "z"},
        ],
        "edges": [],
    }
    graph_path = tmp_path / "task-graph.json"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    build = tmp_path / "build"
    build.mkdir()
    state = {"schema_version": "1.0", "graph_hash": None,
             "nodes": [{"id": "P05-C05-01", "state": "done", "started_at": None, "lease_expires_at": None}]}
    state_path = build / "task-state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    pts.main(["--task-graph", str(graph_path), "--task-state", str(state_path)])
    status = json.loads((tmp_path / "task-graph-status.json").read_text(encoding="utf-8"))
    assert status["summary"]["total"] == 3                       # full graph 分母
    assert status["summary"]["by_state"] == {"done": 1, "pending": 2, "running": 0, "blocked": 0}
    assert abs(status["summary"]["completion_rate"] - (1 / 3)) < 1e-9
    md = (tmp_path / "task-progress.md").read_text(encoding="utf-8")
    assert "(1/3)" in md                                         # md も 1/3 表示 (100% と誤らない)


def test_usage_error_missing_required(tmp_path):
    assert pts.main([]) == 2
