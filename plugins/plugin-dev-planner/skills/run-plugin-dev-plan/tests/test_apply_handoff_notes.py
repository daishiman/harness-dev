"""apply-handoff-notes.py (C12) の機能テスト — 分類・有界性・直接先行限定伝播。

conftest 非依存でローカルロードする (共有 fixture に依存しない自己完結テスト)。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"
sys.path.insert(0, str(SCRIPTS))


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


apply_mod = _load("apply-handoff-notes")


def _write(path: Path, obj: dict) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


# T4 -> depends_on T2,T3 / T2 -> depends_on T1 / T4 -> consumes artifact-x
def _graph() -> dict:
    return {
        "schema_version": "1.0",
        "nodes": [
            {"id": n, "title": n, "phase_ref": "P01", "entity_ref": None,
             "state": "pending", "write_scope": n}
            for n in ("T1", "T2", "T3", "T4")
        ],
        "edges": [
            {"type": "depends_on", "from": "T4", "to": "T2"},
            {"type": "depends_on", "from": "T4", "to": "T3"},
            {"type": "depends_on", "from": "T2", "to": "T1"},
            {"type": "consumes", "from": "T4", "to": "artifact-x"},
        ],
    }


# ─────────────────────────── classify() ───────────────────────────
def test_classify_actionable():
    assert apply_mod.classify("検証ロジックを追加する") == "actionable"


def test_classify_advisory():
    assert apply_mod.classify("導出は安定していた") == "advisory"


def test_classify_more_actionable_forms():
    assert apply_mod.classify("エッジ検査を修正する。") == "actionable"
    assert apply_mod.classify("schema を分離すべき") == "actionable"


def test_classify_state_stays_advisory():
    # 動詞語幹を含まない「する」語 (存在する) は advisory
    assert apply_mod.classify("producer が実在する") == "advisory"
    assert apply_mod.classify("並列 dispatch は問題なく完了した") == "advisory"


# ─────────────────────── validate_notes_bounds() ───────────────────────
def test_bounds_ok_exact_limits():
    notes = {
        "went_well": ["a", "b", "c"],           # 3 件ちょうど
        "friction_points": ["x" * 200],         # 200 文字ちょうど
        "downstream_watchouts": [],
    }
    assert apply_mod.validate_notes_bounds(notes) == []


def test_bounds_maxitems_exceeded():
    notes = {"went_well": ["a", "b", "c", "d"]}  # 4 件
    violations = apply_mod.validate_notes_bounds(notes)
    assert any("went_well" in v and "maxItems" in v for v in violations)


def test_bounds_maxlength_exceeded():
    notes = {"friction_points": ["y" * 201]}  # 201 文字
    violations = apply_mod.validate_notes_bounds(notes)
    assert any("friction_points" in v and "maxLength" in v for v in violations)


def test_bounds_non_list_detected():
    notes = {"downstream_watchouts": "not-a-list"}
    violations = apply_mod.validate_notes_bounds(notes)
    assert any("downstream_watchouts" in v for v in violations)


# ─────────────────────────── propagate() ───────────────────────────
def test_propagate_limits_to_direct_predecessors():
    notes = {"went_well": ["導出は安定していた"], "friction_points": [], "downstream_watchouts": []}
    result = apply_mod.propagate(notes, _graph(), "T4")
    # 直接先行 = T2, T3 (+consumes 先 artifact-x)。間接先行 T1 は含まれない。
    assert set(result["predecessors"]) == {"T2", "T3", "artifact-x"}
    assert "T1" not in result["predecessors"]


def test_propagate_depends_on_only_excludes_indirect():
    # T2 の直接先行は T1 のみ (T4 は下流なので含まれない)。
    notes = {"went_well": [], "friction_points": [], "downstream_watchouts": []}
    result = apply_mod.propagate(notes, _graph(), "T2")
    assert result["predecessors"] == ["T1"]


def test_propagate_injects_classified_notes():
    notes = {
        "went_well": ["導出は安定していた"],
        "friction_points": ["検証ロジックを追加する"],
        "downstream_watchouts": [],
    }
    result = apply_mod.propagate(notes, _graph(), "T4")
    classes = {n["text"]: n["class"] for n in result["injected_notes"]}
    assert classes["導出は安定していた"] == "advisory"
    assert classes["検証ロジックを追加する"] == "actionable"


# ─────────────────────────── main() / CLI ───────────────────────────
def test_cli_happy_exit0(tmp_path, capsys):
    notes = {"went_well": ["導出は安定していた"], "friction_points": [], "downstream_watchouts": []}
    notes_p = _write(tmp_path / "notes.json", notes)
    graph_p = _write(tmp_path / "graph.json", _graph())
    rc = apply_mod.main(["--notes", str(notes_p), "--graph", str(graph_p), "--task-id", "T4"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["task_id"] == "T4"
    assert set(out["predecessors"]) == {"T2", "T3", "artifact-x"}


def test_cli_bounds_violation_exit1(tmp_path, capsys):
    notes = {"went_well": ["a", "b", "c", "d"]}  # 4 件 → 違反
    notes_p = _write(tmp_path / "notes.json", notes)
    graph_p = _write(tmp_path / "graph.json", _graph())
    rc = apply_mod.main(["--notes", str(notes_p), "--graph", str(graph_p), "--task-id", "T4"])
    assert rc == 1
    assert "maxItems" in capsys.readouterr().err


def test_cli_missing_arg_usage_exit2():
    assert apply_mod.main(["--graph", "x.json", "--task-id", "T4"]) == 2  # --notes 欠落


def test_cli_bad_path_exit2(tmp_path):
    graph_p = _write(tmp_path / "graph.json", _graph())
    rc = apply_mod.main(["--notes", str(tmp_path / "nope.json"), "--graph", str(graph_p),
                         "--task-id", "T4"])
    assert rc == 2


# ─────────────────────── schema 準拠 (handoff-notes) ───────────────────────
def test_notes_schema_bounds_match_script_constants():
    schema = json.loads((SCHEMAS / "handoff-notes.schema.json").read_text(encoding="utf-8"))
    for cat in apply_mod.CATEGORIES:
        prop = schema["properties"][cat]
        assert prop["maxItems"] == apply_mod.MAX_ITEMS
        assert prop["items"]["maxLength"] == apply_mod.MAX_LEN
