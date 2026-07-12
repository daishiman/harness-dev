"""dispatch-ready-set.py (TG-C01) の機能テスト — task-graph + task-state 配信器。

conftest 非依存で module-level に importlib ロードする (共有 fixture に依存しない
自己完結テスト)。merge_state 純関数 / graph_hash pin (一致・不一致・未設定) /
compute-ready-set subprocess (monkeypatch と実 producer script の両方) / ready_batch +
blocked 出力 / exit codes を網羅する。producer compute-ready-set / derive-task-graph を
実 subprocess 起動する統合ケースを含め実インターフェース整合を担保する。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
# producer=plugin-dev-planner scripts (実 subprocess 呼出先 + hash 計算のため module ロード)。
PLANNER_SCRIPTS = (
    Path(__file__).resolve().parent.parent.parent
    / "plugin-dev-planner" / "skills" / "run-plugin-dev-plan" / "scripts"
)
sys.path.insert(0, str(SCRIPTS))


def _load(scripts_dir: Path, stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), scripts_dir / f"{stem}.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


disp = _load(SCRIPTS, "dispatch-ready-set")
derive = _load(PLANNER_SCRIPTS, "derive-task-graph")


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _graph() -> dict:
    """T1 -> T2 (depends_on) + 独立 T3。distinct write_scope で write_scope 衝突なし。"""
    return {
        "schema_version": "1.0",
        "nodes": [
            {"id": "T1", "state": "pending", "write_scope": "a/T1"},
            {"id": "T2", "state": "pending", "write_scope": "a/T2"},
            {"id": "T3", "state": "pending", "write_scope": "a/T3"},
        ],
        "edges": [{"type": "depends_on", "from": "T2", "to": "T1"}],
    }


def _task_state(graph_hash=None, **states) -> dict:
    nodes = [{"id": nid, "state": st} for nid, st in states.items()]
    return {"schema_version": "1.0", "graph_hash": graph_hash, "nodes": nodes}


def _write(path: Path, obj: dict) -> str:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _fake_ready_set(ready, conflicts=None):
    """invoke_ready_set の差替え: 与えた ready_set/conflicts を stdout に返す CompletedProcess。"""
    payload = json.dumps({"ready_set": ready, "conflicts": conflicts or []})

    def _fake(planner_root, plan_dir, repo_root):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=payload, stderr="")

    return _fake


# ─────────────────────────── planner root 既定 (TG-C02 SSOT) ───────────────────────────
def test_planner_root_default_is_c02_ssot():
    # 既定 planner root はローカル導出でなく TG-C02 resolve_planner_root() の SSOT 再利用。
    sts = _load(SCRIPTS, "sync-task-state")
    assert disp._PLANNER_ROOT_DEFAULT == str(sts.resolve_planner_root())
    assert Path(disp._PLANNER_ROOT_DEFAULT).name == "plugin-dev-planner"


# ─────────────────────────── merge_state (純関数) ───────────────────────────
def test_merge_state_overrides_from_state():
    graph = _graph()
    state_by_id = {"T1": {"state": "done"}, "T3": {"state": "blocked"}}
    out = disp.merge_state(graph, state_by_id)
    by = {n["id"]: n for n in out["nodes"]}
    assert by["T1"]["state"] == "done"
    assert by["T3"]["state"] == "blocked"
    assert by["T2"]["state"] == "pending"  # 未 override は graph の既存 state


def test_merge_state_falls_back_to_graph_state_when_absent():
    graph = {"nodes": [{"id": "T1", "state": "running"}], "edges": []}
    out = disp.merge_state(graph, {})  # state 空 → graph 既存 state を保持
    assert out["nodes"][0]["state"] == "running"


def test_merge_state_defaults_pending_when_neither():
    graph = {"nodes": [{"id": "T1"}], "edges": []}  # graph に state キー無し
    out = disp.merge_state(graph, {})
    assert out["nodes"][0]["state"] == "pending"


def test_merge_state_does_not_mutate_input():
    graph = _graph()
    disp.merge_state(graph, {"T1": {"state": "done"}})
    # 入力 graph の node は不変 (浅コピー)。
    assert graph["nodes"][0]["state"] == "pending"


# ─────────────────────────── verify_graph_hash_pin (実 derive subprocess) ───
def test_verify_graph_hash_pin_match(tmp_path):
    graph = _graph()
    gp = _write(tmp_path / "task-graph.json", graph)
    pinned = derive.graph_hash(graph)  # derive は canonicalize してから hash 化
    assert disp.verify_graph_hash_pin(gp, pinned, disp._PLANNER_ROOT_DEFAULT) is True


def test_verify_graph_hash_pin_mismatch(tmp_path):
    gp = _write(tmp_path / "task-graph.json", _graph())
    wrong = "sha256:" + "0" * 64
    assert disp.verify_graph_hash_pin(gp, wrong, disp._PLANNER_ROOT_DEFAULT) is False


def test_verify_graph_hash_pin_bad_path_returns_false(tmp_path):
    # derive が読込不能 (exit2) → 照合不能ゆえ fail-closed で False。
    missing = str(tmp_path / "nope.json")
    assert disp.verify_graph_hash_pin(missing, "sha256:" + "a" * 64, disp._PLANNER_ROOT_DEFAULT) is False


# ─────────────────────── main(): 実 producer 統合 (subprocess 起動) ───────────────────────
def test_main_integration_real_compute_ready_set(tmp_path, capsys):
    """実 compute-ready-set.py を subprocess 起動し ready_batch/blocked を検証 (実 IF 整合)。"""
    gp = _write(tmp_path / "task-graph.json", _graph())
    sp = _write(tmp_path / "task-state.json", _task_state(T1="done", T3="blocked"))
    # --planner-root 省略 → 既定 (__file__ 由来の実 plugin-dev-planner) が解決することも検証。
    rc = disp.main(["--task-graph", gp, "--task-state", sp])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # T1 done → 除外 / T2 は depends_on T1(done) 充足 → ready / T3 blocked → 除外。
    assert out["ready_batch"] == ["T2"]
    assert out["conflicts"] == []
    assert out["blocked"] == ["T3"]
    assert out["graph_hash_pin"] is None
    assert out["source"] == "compute-ready-set.py"


# ─────────────────────── main(): --repo-root 伝搬 (M-02) ───────────────────────
def test_main_integration_repo_root_resolves_relative_artifact(tmp_path, capsys):
    """--repo-root が実 compute-ready-set へ伝搬し、相対 write_scope の consumes 成果物が
    repo root 基点で実在判定される (cwd 非依存の実 subprocess 統合)。"""
    root = tmp_path / "repo"
    (root / "artifacts").mkdir(parents=True)
    (root / "artifacts" / "a1.txt").write_text("x", encoding="utf-8")
    graph = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "T1", "state": "pending", "write_scope": "artifacts/a1.txt"},
            {"id": "T2", "state": "pending", "write_scope": "a/T2"},
        ],
        "edges": [
            {"type": "produces", "from": "T1", "to": "A1"},
            {"type": "depends_on", "from": "T2", "to": "T1"},
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    gp = _write(tmp_path / "task-graph.json", graph)
    sp = _write(tmp_path / "task-state.json", _task_state(T1="done"))
    rc = disp.main(["--task-graph", gp, "--task-state", sp, "--repo-root", str(root)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ready_batch"] == ["T2"]  # repo root 基点で成果物実在 → ready


def test_main_consumes_without_artifact_producer_fails_closed(tmp_path, capsys, monkeypatch):
    graph = {
        "schema_version": "1.0",
        "nodes": [{"id": "T2", "state": "pending", "write_scope": "a/T2"}],
        "edges": [{"type": "consumes", "from": "A404", "to": "T2"}],
    }
    gp = _write(tmp_path / "task-graph.json", graph)
    sp = _write(tmp_path / "task-state.json", _task_state())

    def _must_not_run(planner_root, plan_dir, repo_root):
        raise AssertionError("invalid consumes graph must fail before compute-ready-set")

    monkeypatch.setattr(disp, "invoke_ready_set", _must_not_run)
    assert disp.main(["--task-graph", gp, "--task-state", sp]) == 1
    assert "has no producer" in capsys.readouterr().err


def test_main_repo_root_default_and_override_reach_invoke(tmp_path, capsys, monkeypatch):
    """--repo-root 省略時は _REPO_ROOT_DEFAULT (script 位置由来の repo root)、指定時は
    その値が invoke_ready_set へ届く (伝搬経路の単体検証)。"""
    gp = _write(tmp_path / "task-graph.json", _graph())
    sp = _write(tmp_path / "task-state.json", _task_state())
    seen: list[str] = []

    def _capture(planner_root, plan_dir, repo_root):
        seen.append(repo_root)
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"ready_set": [], "conflicts": []}), stderr=""
        )

    monkeypatch.setattr(disp, "invoke_ready_set", _capture)
    assert disp.main(["--task-graph", gp, "--task-state", sp]) == 0
    assert disp.main(["--task-graph", gp, "--task-state", sp, "--repo-root", "/custom/root"]) == 0
    capsys.readouterr()
    assert seen == [disp._REPO_ROOT_DEFAULT, "/custom/root"]


# ─────────────────────── main(): 出力整形 (invoke_ready_set monkeypatch) ───────────────────────
def test_main_ready_batch_and_blocked_output(tmp_path, capsys, monkeypatch):
    graph = {
        "schema_version": "1.0",
        "nodes": [{"id": f"T{i}", "state": "pending", "write_scope": f"a/T{i}"} for i in (1, 2, 3, 4)],
        "edges": [],
    }
    gp = _write(tmp_path / "task-graph.json", graph)
    sp = _write(tmp_path / "task-state.json", _task_state(T2="blocked", T4="blocked"))
    monkeypatch.setattr(disp, "invoke_ready_set", _fake_ready_set(["T1"], conflicts=[]))
    rc = disp.main(["--task-graph", gp, "--task-state", sp])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ready_batch"] == ["T1"]          # producer ready_set を verbatim 透過
    assert out["blocked"] == ["T2", "T4"]         # merged 上 blocked を昇順で付与
    assert out["graph_hash_pin"] is None


def test_main_passes_conflicts_through(tmp_path, capsys, monkeypatch):
    gp = _write(tmp_path / "task-graph.json", _graph())
    sp = _write(tmp_path / "task-state.json", _task_state())
    monkeypatch.setattr(disp, "invoke_ready_set", _fake_ready_set(["T1"], conflicts=[["T2", "T3"]]))
    rc = disp.main(["--task-graph", gp, "--task-state", sp])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["conflicts"] == [["T2", "T3"]]


# ─────────────────────── main(): graph_hash pin 分岐 ───────────────────────
def test_main_graph_hash_pin_verified(tmp_path, capsys, monkeypatch):
    graph = _graph()
    gp = _write(tmp_path / "task-graph.json", graph)
    pinned = derive.graph_hash(graph)
    sp = _write(tmp_path / "task-state.json", _task_state(graph_hash=pinned, T1="done"))
    # verify は実 derive subprocess で走らせ、ready-set のみ差替えて pin 分岐を isolate。
    monkeypatch.setattr(disp, "invoke_ready_set", _fake_ready_set(["T2"]))
    rc = disp.main(["--task-graph", gp, "--task-state", sp])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["graph_hash_pin"] == "verified"
    assert out["ready_batch"] == ["T2"]


def test_main_graph_hash_pin_mismatch_exit1(tmp_path, capsys, monkeypatch):
    gp = _write(tmp_path / "task-graph.json", _graph())
    sp = _write(tmp_path / "task-state.json", _task_state(graph_hash="sha256:" + "0" * 64, T1="done"))

    def _must_not_run(planner_root, plan_dir, repo_root):  # mismatch は ready-set 前に fail-closed
        raise AssertionError("mismatch 時は compute-ready-set を呼ばない")

    monkeypatch.setattr(disp, "invoke_ready_set", _must_not_run)
    rc = disp.main(["--task-graph", gp, "--task-state", sp])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["graph_hash_pin"] == "mismatch"
    assert out["ready_batch"] == []


def test_main_graph_hash_pin_unset_skips(tmp_path, capsys, monkeypatch):
    gp = _write(tmp_path / "task-graph.json", _graph())
    sp = _write(tmp_path / "task-state.json", _task_state(graph_hash=None, T1="done"))
    monkeypatch.setattr(disp, "invoke_ready_set", _fake_ready_set(["T2"]))
    rc = disp.main(["--task-graph", gp, "--task-state", sp])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["graph_hash_pin"] is None


# ─────────────────────── main(): エラー系 exit codes ───────────────────────
def test_main_compute_ready_set_nonzero_exit1(tmp_path, monkeypatch):
    gp = _write(tmp_path / "task-graph.json", _graph())
    sp = _write(tmp_path / "task-state.json", _task_state())

    def _fail(planner_root, plan_dir, repo_root):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(disp, "invoke_ready_set", _fail)
    assert disp.main(["--task-graph", gp, "--task-state", sp]) == 1


def test_main_ready_set_bad_json_exit1(tmp_path, monkeypatch):
    gp = _write(tmp_path / "task-graph.json", _graph())
    sp = _write(tmp_path / "task-state.json", _task_state())

    def _garbage(planner_root, plan_dir, repo_root):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr="")

    monkeypatch.setattr(disp, "invoke_ready_set", _garbage)
    assert disp.main(["--task-graph", gp, "--task-state", sp]) == 1


def test_main_bad_task_graph_path_exit2(tmp_path):
    sp = _write(tmp_path / "task-state.json", _task_state())
    assert disp.main(["--task-graph", str(tmp_path / "nope.json"), "--task-state", sp]) == 2


def test_main_bad_task_state_path_exit2(tmp_path):
    gp = _write(tmp_path / "task-graph.json", _graph())
    assert disp.main(["--task-graph", gp, "--task-state", str(tmp_path / "nope.json")]) == 2


def test_main_missing_required_arg_exit2(tmp_path):
    gp = _write(tmp_path / "task-graph.json", _graph())
    assert disp.main(["--task-graph", gp]) == 2  # --task-state 欠落
