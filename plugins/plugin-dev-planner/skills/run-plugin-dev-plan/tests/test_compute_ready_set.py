"""compute-ready-set.py の機能テスト (C4)。

conftest 非依存でローカルロードする (SCRIPTS を sys.path へ載せ file-path import)。
C4 受入 5 ケース (直列 / ダイヤモンド / blocked 伝播 / write_scope 衝突 / 成果物欠落) +
main() の JSON 出力 / usage / 読込不能 を網羅する。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CRS = _load("compute-ready-set")


def _node(nid, state="pending", write_scope=None):
    return {
        "id": nid,
        "title": nid,
        "phase_ref": "P05",
        "entity_ref": None,
        "state": state,
        "write_scope": write_scope if write_scope is not None else f"ws/{nid}",
    }


def _dep(frm, to):
    return {"type": "depends_on", "from": frm, "to": to}


# ─────────────────── C4 受入 5 ケース ───────────────────
def test_case1_serial_chain():
    """T1(done)→T2(pending,dep=[T1])→T4(pending,dep=[T2])。ready={T2}。"""
    graph = {
        "nodes": [_node("T1", "done"), _node("T2", "pending"), _node("T4", "pending")],
        "edges": [_dep("T2", "T1"), _dep("T4", "T2")],
    }
    ready, conflicts = CRS.ready_set(graph)
    assert ready == {"T2"}
    assert conflicts == []


def test_case2_diamond():
    """T1(done)→{T2,T3}(pending・write_scope 相異)→T4(dep=[T2,T3])。ready={T2,T3}。"""
    graph = {
        "nodes": [
            _node("T1", "done"),
            _node("T2", "pending", "ws/a"),
            _node("T3", "pending", "ws/b"),
            _node("T4", "pending"),
        ],
        "edges": [_dep("T2", "T1"), _dep("T3", "T1"), _dep("T4", "T2"), _dep("T4", "T3")],
    }
    ready, conflicts = CRS.ready_set(graph)
    assert ready == {"T2", "T3"}
    assert conflicts == []


def test_case3_blocked_propagation():
    """ケース2 で T2.state=blocked。ready={T3} (T2 除外・T4 は T2 未 done で対象外)。"""
    graph = {
        "nodes": [
            _node("T1", "done"),
            _node("T2", "blocked", "ws/a"),
            _node("T3", "pending", "ws/b"),
            _node("T4", "pending"),
        ],
        "edges": [_dep("T2", "T1"), _dep("T3", "T1"), _dep("T4", "T2"), _dep("T4", "T3")],
    }
    ready, conflicts = CRS.ready_set(graph)
    assert ready == {"T3"}
    assert conflicts == []


def test_case4_write_scope_conflict_serialized():
    """T1(done)→{T2,T5}(共に dep=[T1]・write_scope 同一)。単一許可: 先頭 T2 のみ ready・T5 は
    deferred で conflicts=(T2,T5) に記録 (fail-closed 全除外でなく決定論直列化)。"""
    graph = {
        "nodes": [
            _node("T1", "done"),
            _node("T2", "pending", "ws/shared"),
            _node("T5", "pending", "ws/shared"),
        ],
        "edges": [_dep("T2", "T1"), _dep("T5", "T1")],
    }
    ready, conflicts = CRS.ready_set(graph)
    assert ready == {"T2"}          # id 昇順先頭のみ許可 (直列化)
    assert ("T2", "T5") in conflicts  # 後続 T5 は winner T2 の背後へ deferred


def test_case4b_conflict_winner_done_frees_scope():
    """winner T2 が done 化すると次周回で write_scope が解放され deferred T5 が ready 化する
    (直列化が 1 周回 1 node で必ず進行する裏取り・デッドロック非再現)。"""
    graph = {
        "nodes": [
            _node("T1", "done"),
            _node("T2", "done", "ws/shared"),     # 前周回で done
            _node("T5", "pending", "ws/shared"),
        ],
        "edges": [_dep("T2", "T1"), _dep("T5", "T1")],
    }
    ready, conflicts = CRS.ready_set(graph)
    assert ready == {"T5"}          # scope 解放後に deferred が昇格
    assert conflicts == []


def test_case5_done_but_artifact_missing(tmp_path):
    """T1(done,produces A1,write_scope=欠落)→T2(pending,dep=[T1],consumes A1)。ready={}。"""
    missing = str(tmp_path / "does-not-exist.txt")
    graph = {
        "nodes": [
            _node("T1", "done", missing),
            _node("T2", "pending", "ws/t2"),
        ],
        "edges": [
            {"type": "produces", "from": "T1", "to": "A1"},
            _dep("T2", "T1"),
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    ready, conflicts = CRS.ready_set(graph)
    assert ready == set()
    assert conflicts == []


def test_case5_artifact_present_makes_ready(tmp_path):
    """ケース5 の producer write_scope を実在パスにすると T2 が ready 化する (True 分岐)。"""
    present = tmp_path / "artifact.txt"
    present.write_text("x", encoding="utf-8")
    graph = {
        "nodes": [
            _node("T1", "done", str(present)),
            _node("T2", "pending", "ws/t2"),
        ],
        "edges": [
            {"type": "produces", "from": "T1", "to": "A1"},
            _dep("T2", "T1"),
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    ready, _ = CRS.ready_set(graph)
    assert ready == {"T2"}


# ─────────────────── --repo-root (M-02: cwd anchoring 解消) ───────────────────
def test_repo_root_resolves_relative_write_scope(tmp_path):
    """相対 write_scope の成果物実在検査は repo_root 指定で repo_root 基点に解決される。
    未指定 (cwd 基点) では同じ graph が not-ready になる (cwd anchoring の再現と解消)。"""
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "a1.txt").write_text("x", encoding="utf-8")
    graph = {
        "nodes": [
            _node("T1", "done", "artifacts/a1.txt"),   # 相対 write_scope
            _node("T2", "pending", "ws/t2"),
        ],
        "edges": [
            {"type": "produces", "from": "T1", "to": "A1"},
            _dep("T2", "T1"),
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    ready_without, _ = CRS.ready_set(graph)                            # cwd 基点 → 欠落扱い
    assert ready_without == set()
    ready_with, _ = CRS.ready_set(graph, repo_root=str(tmp_path))      # repo_root 基点 → 実在
    assert ready_with == {"T2"}


def test_repo_root_does_not_affect_absolute_write_scope(tmp_path):
    """絶対パス write_scope は repo_root に依らずそのまま検査される (join しない)。"""
    present = tmp_path / "artifact.txt"
    present.write_text("x", encoding="utf-8")
    graph = {
        "nodes": [
            _node("T1", "done", str(present)),          # 絶対 write_scope
            _node("T2", "pending", "ws/t2"),
        ],
        "edges": [
            {"type": "produces", "from": "T1", "to": "A1"},
            _dep("T2", "T1"),
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    # 無関係な repo_root を与えても絶対パスは影響を受けない。
    ready, _ = CRS.ready_set(graph, repo_root=str(tmp_path / "unrelated"))
    assert ready == {"T2"}


# ─────────────────── 追加分岐カバレッジ ───────────────────
def test_consumes_with_missing_producer_node():
    """consumes 先 artifact の producer node が node_by_id に不在なら実在扱いしない。"""
    graph = {
        "nodes": [_node("T2", "pending", "ws/t2")],
        "edges": [
            {"type": "produces", "from": "GHOST", "to": "A1"},
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    ready, _ = CRS.ready_set(graph)
    assert ready == set()


def test_empty_graph_ready_empty():
    ready, conflicts = CRS.ready_set({})
    assert ready == set() and conflicts == []


def test_ignores_non_dict_nodes_and_edges():
    graph = {"nodes": [_node("T1", "done"), "junk"], "edges": ["junk", {"type": "x"}]}
    ready, conflicts = CRS.ready_set(graph)
    assert ready == set() and conflicts == []


# ─────────────────── main() ───────────────────
def _write_graph(tmp_path, graph):
    (tmp_path / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")


def test_main_outputs_json(tmp_path, capsys):
    graph = {
        "nodes": [_node("T1", "done"), _node("T2", "pending")],
        "edges": [_dep("T2", "T1")],
    }
    _write_graph(tmp_path, graph)
    rc = CRS.main([str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"ready_set": ["T2"], "conflicts": []}


def test_main_conflict_serialization(tmp_path, capsys):
    graph = {
        "nodes": [
            _node("T1", "done"),
            _node("T2", "pending", "ws/shared"),
            _node("T5", "pending", "ws/shared"),
        ],
        "edges": [_dep("T2", "T1"), _dep("T5", "T1")],
    }
    _write_graph(tmp_path, graph)
    rc = CRS.main([str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ready_set"] == ["T2"]           # 単一許可: 先頭のみ ready (旧: 全除外で [])
    assert out["conflicts"] == [["T2", "T5"]]   # 後続は winner の背後へ直列化


def test_main_repo_root_flag(tmp_path, capsys):
    """main の --repo-root 指定が ready_set の成果物実在検査基点へ届く (CLI 経路)。"""
    root = tmp_path / "repo"
    (root / "artifacts").mkdir(parents=True)
    (root / "artifacts" / "a1.txt").write_text("x", encoding="utf-8")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    graph = {
        "nodes": [
            _node("T1", "done", "artifacts/a1.txt"),
            _node("T2", "pending", "ws/t2"),
        ],
        "edges": [
            {"type": "produces", "from": "T1", "to": "A1"},
            _dep("T2", "T1"),
            {"type": "consumes", "from": "A1", "to": "T2"},
        ],
    }
    _write_graph(plan_dir, graph)
    rc = CRS.main([str(plan_dir), "--repo-root", str(root)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ready_set"] == ["T2"]


def test_main_usage_error():
    assert CRS.main([]) == 2
    assert CRS.main(["a", "b"]) == 2
    assert CRS.main(["a", "--repo-root"]) == 2  # --repo-root 値欠落は usage error


def test_main_read_error(tmp_path):
    # task-graph.json が存在しない → 読込不能 exit1
    assert CRS.main([str(tmp_path)]) == 1
