"""verify-index-topsort.py の shape_marker 拡張 (_shape_marker / _verify_task_graph_derived) の検証。

C10: 既定 fixed-13-phase は従来ロジック不変、task-graph-derived のみ動的算出。
未知値/非 dict は fixed-13-phase へ fail-soft fallback する。
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


VIT = _load("verify-index-topsort")


def test_shape_marker_default():
    assert VIT._shape_marker({}) == "fixed-13-phase"


def test_shape_marker_derived():
    assert VIT._shape_marker({"shape_marker": "task-graph-derived"}) == "task-graph-derived"


def test_shape_marker_unknown_fallback():
    assert VIT._shape_marker({"shape_marker": "bogus"}) == "fixed-13-phase"


def test_shape_marker_non_dict():
    assert VIT._shape_marker("x") == "fixed-13-phase"


def test_derived_no_file_falls_back_to_13(tmp_path):
    # task-graph.json 不在 → verify_phase_enumeration へ fallback (13 phase 期待で欠落 → errors)。
    errs = VIT._verify_task_graph_derived(tmp_path, [], False)
    assert errs


def test_derived_with_file_ok(tmp_path):
    graph = {"nodes": [{"phase_ref": "P01"}, {"phase_ref": "P02"}]}
    (tmp_path / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    assert VIT._verify_task_graph_derived(tmp_path, ["P01", "P02"], True) == []


def test_derived_with_file_missing_phase(tmp_path):
    graph = {"nodes": [{"phase_ref": "P01"}, {"phase_ref": "P02"}]}
    (tmp_path / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    errs = VIT._verify_task_graph_derived(tmp_path, ["P01"], True)  # P02 が index 列挙に欠落
    assert errs and "P02" in errs[0]


def test_derived_no_section_flag(tmp_path):
    graph = {"nodes": [{"phase_ref": "P01"}]}
    (tmp_path / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    errs = VIT._verify_task_graph_derived(tmp_path, ["P01"], False)
    assert any("section" in e for e in errs)


def test_derived_invalid_json_falls_back(tmp_path):
    (tmp_path / "task-graph.json").write_text("{bad", encoding="utf-8")
    errs = VIT._verify_task_graph_derived(tmp_path, [], False)
    assert errs  # JSON 不正 → 13 phase fallback で欠落検出
