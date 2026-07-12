"""check-build-handoff.py の task-graph 拡張 (_check_task_graph_ref / _check_cycle_id_parity) の検証。

C6: task_graph_ref の形状 + routes↔producer task 対応 + handoff.cycle_id↔goal-spec parity。
task-graph はデフォルト成果物 (§9) ゆえ task_graph_ref は必須 (未設定は violation)。
file 不在時は形状のみ検証 (実体 10 検査は validate-task-graph の責務) を固定する。
"""
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


CBH = _load("check-build-handoff")


# ─────────── _check_task_graph_ref ───────────
def test_tgr_absent_is_violation():
    """task-graph はデフォルト成果物ゆえ未設定は fail-closed で violation (旧: 後方互換スキップ)。"""
    errs = CBH._check_task_graph_ref({"routes": []}, Path("/nonexistent"))
    assert errs and "未設定" in errs[0]


def test_tgr_not_dict():
    errs = CBH._check_task_graph_ref({"task_graph_ref": "x", "routes": []}, Path("/x"))
    assert errs and "object でない" in errs[0]


def test_tgr_missing_fields(tmp_path):
    errs = CBH._check_task_graph_ref({"task_graph_ref": {}, "routes": []}, tmp_path)
    assert any("path" in e for e in errs)
    assert any("schema_version" in e for e in errs)


def test_tgr_file_absent_shape_only(tmp_path):
    data = {"task_graph_ref": {"path": "task-graph.json", "schema_version": "1.0"},
            "routes": [{"id": "C01"}]}
    # 実 task-graph.json が無くても形状が妥当なら violation なし (メタ循環 fixed-13-phase 救済)。
    assert CBH._check_task_graph_ref(data, tmp_path) == []


def test_tgr_file_present_producer_ok(tmp_path):
    graph = {"schema_version": "1.0",
             "nodes": [{"id": "T1", "entity_ref": "C01"}],
             "edges": [{"type": "produces", "from": "T1", "to": "A1"}]}
    (tmp_path / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    data = {"task_graph_ref": {"path": "task-graph.json", "schema_version": "1.0"},
            "routes": [{"id": "C01"}]}
    assert CBH._check_task_graph_ref(data, tmp_path) == []


def test_tgr_file_present_route_unmatched(tmp_path):
    graph = {"schema_version": "1.0",
             "nodes": [{"id": "T1", "entity_ref": "C01"}],
             "edges": [{"type": "produces", "from": "T1", "to": "A1"}]}
    (tmp_path / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    data = {"task_graph_ref": {"path": "task-graph.json", "schema_version": "1.0"},
            "routes": [{"id": "C99"}]}  # producer task に対応しない
    errs = CBH._check_task_graph_ref(data, tmp_path)
    assert errs and "C99" in errs[0]


def test_tgr_file_invalid_json(tmp_path):
    (tmp_path / "task-graph.json").write_text("{bad", encoding="utf-8")
    data = {"task_graph_ref": {"path": "task-graph.json", "schema_version": "1.0"},
            "routes": [{"id": "C01"}]}
    errs = CBH._check_task_graph_ref(data, tmp_path)
    assert errs


# ─────────── _check_cycle_id_parity ───────────
def test_cycle_parity_both_none(tmp_path):
    (tmp_path / "goal-spec.json").write_text(json.dumps({"cycle_id": None}), encoding="utf-8")
    assert CBH._check_cycle_id_parity({"cycle_id": None}, tmp_path) == []


def test_cycle_parity_no_goalspec(tmp_path):
    # goal-spec が無ければ fail-soft スキップ。
    assert CBH._check_cycle_id_parity({"cycle_id": None}, tmp_path) == []


def test_cycle_parity_match(tmp_path):
    (tmp_path / "goal-spec.json").write_text(json.dumps({"cycle_id": "20260705-x"}), encoding="utf-8")
    assert CBH._check_cycle_id_parity({"cycle_id": "20260705-x"}, tmp_path) == []


def test_cycle_parity_mismatch(tmp_path):
    (tmp_path / "goal-spec.json").write_text(json.dumps({"cycle_id": "20260705-x"}), encoding="utf-8")
    errs = CBH._check_cycle_id_parity({"cycle_id": None}, tmp_path)
    assert errs and "parity" in errs[0]


def test_cycle_parity_goalspec_absent_field(tmp_path):
    # goal-spec に cycle_id フィールドが無い (None) & handoff None → 一致。
    (tmp_path / "goal-spec.json").write_text(json.dumps({"target_plugin_slug": "x"}), encoding="utf-8")
    assert CBH._check_cycle_id_parity({}, tmp_path) == []
