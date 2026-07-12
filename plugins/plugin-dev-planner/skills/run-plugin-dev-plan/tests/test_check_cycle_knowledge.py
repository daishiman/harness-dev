"""check-cycle-knowledge.py の機能テスト (C19)。

conftest 非依存でローカルロード。validate_knowledge_ref/validate_external_input (有界検査) +
check_no_predecessor_node_copy (過去 node 混入禁止) + scan/main を網羅する。
正本の受入例は phase-04-test-design.md の C19 節。
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


CCK = _load("check-cycle-knowledge")


def _kref(**over):
    base = {
        "id": "K1",
        "source_ref": "eval-log/mf-kessai-invoice-check/finding-3.json",
        "freshness_checked_at": "2026-07-10",
        "decision": "adopted",
        "reason": "過去 cycle の照合ロジックを蒸留し再利用",
    }
    base.update(over)
    return base


# ─────────────────── validate_knowledge_ref ───────────────────
def test_knowledge_ref_valid():
    assert CCK.validate_knowledge_ref(_kref(), "L") == []


def test_knowledge_ref_missing_source_ref():
    errs = CCK.validate_knowledge_ref(_kref(source_ref=""), "L")
    assert any("source_ref" in e for e in errs)


def test_knowledge_ref_missing_freshness():
    ref = _kref()
    ref.pop("freshness_checked_at")
    errs = CCK.validate_knowledge_ref(ref, "L")
    assert any("freshness_checked_at" in e for e in errs)


def test_knowledge_ref_invalid_freshness_date():
    errs = CCK.validate_knowledge_ref(_kref(freshness_checked_at="not-a-date"), "L")
    assert any("YYYY-MM-DD" in e for e in errs)


def test_knowledge_ref_decision_out_of_range():
    errs = CCK.validate_knowledge_ref(_kref(decision="maybe"), "L")
    assert any("decision" in e and "値域外" in e for e in errs)


def test_knowledge_ref_rejected_decision_valid():
    assert CCK.validate_knowledge_ref(_kref(decision="rejected"), "L") == []


# ─────────────────── validate_external_input ───────────────────
def test_external_input_valid():
    assert CCK.validate_external_input({"path": "a/b.json", "hash": "sha256:" + "a" * 64}, "L") == []


def test_external_input_missing_hash():
    errs = CCK.validate_external_input({"path": "a/b.json"}, "L")
    assert any("hash" in e for e in errs)


def test_external_input_bad_hash_format():
    errs = CCK.validate_external_input({"path": "a/b.json", "hash": "sha256:deadbeef"}, "L")
    assert any("64hex" in e for e in errs)


def test_source_ref_must_exist_when_repo_root_is_given(tmp_path):
    errs = CCK.validate_knowledge_ref(_kref(source_ref="missing.json"), "L", repo_root=tmp_path)
    assert any("実在ファイル" in e for e in errs)


# ─────────────────── check_no_predecessor_node_copy ───────────────────
def _graph(ids):
    return {"schema_version": "1.0",
            "nodes": [{"id": i, "title": i, "phase_ref": "P05", "entity_ref": None,
                       "state": "pending", "write_scope": i} for i in ids],
            "edges": []}


def test_no_node_copy_when_disjoint():
    assert CCK.check_no_predecessor_node_copy(_graph(["B1", "B2"]), _graph(["A1", "A2"])) == []


def test_node_copy_detected():
    errs = CCK.check_no_predecessor_node_copy(_graph(["A1", "B2"]), _graph(["A1", "A2"]))
    assert any("A1" in e and "混在" in e for e in errs)


# ─────────────────── scan / main ───────────────────
def _write_spec(plan_dir, name, krefs=None, einputs=None):
    specs = plan_dir / "task-specs"
    specs.mkdir(exist_ok=True)
    lines = ["---", "task_id: " + name.replace(".md", "")]
    if krefs is not None:
        lines.append("knowledge_refs:")
        for k in krefs:
            items = list(k.items())
            lines.append(f"  - {items[0][0]}: {items[0][1]}")
            for kk, vv in items[1:]:
                lines.append(f"    {kk}: {vv}")
    if einputs is not None:
        lines.append("external_inputs:")
        for e in einputs:
            items = list(e.items())
            lines.append(f"  - {items[0][0]}: {items[0][1]}")
            for kk, vv in items[1:]:
                lines.append(f"    {kk}: {vv}")
    lines.append("---")
    lines.append("本文")
    (specs / name).write_text("\n".join(lines), encoding="utf-8")


def test_scan_valid_spec(tmp_path):
    _write_spec(tmp_path, "T1.md", krefs=[_kref()],
                einputs=[{"path": "eval-log/x.json", "hash": "sha256:" + "a" * 64}])
    assert CCK.scan(tmp_path) == []


def test_scan_no_specs_dir_ok(tmp_path):
    assert CCK.scan(tmp_path) == []


def test_scan_target_shape_without_specs_fails(tmp_path):
    (tmp_path / "index.md").write_text(
        "---\nshape_marker: task-graph-derived\n---\n", encoding="utf-8"
    )
    errs = CCK.scan(tmp_path)
    assert any("空走査 PASS 禁止" in e for e in errs)


def test_scan_bad_knowledge_ref(tmp_path):
    _write_spec(tmp_path, "T1.md", krefs=[_kref(source_ref="")])
    errs = CCK.scan(tmp_path)
    assert any("source_ref" in e for e in errs)


def test_main_valid_exit0(tmp_path):
    _write_spec(tmp_path, "T1.md", krefs=[_kref()])
    assert CCK.main([str(tmp_path)]) == 0


def test_main_predecessor_copy_exit1(tmp_path):
    _write_spec(tmp_path, "T1.md", krefs=[_kref()])
    (tmp_path / "task-graph.json").write_text(json.dumps(_graph(["A1", "B2"])), encoding="utf-8")
    pred = tmp_path / "pred-graph.json"
    pred.write_text(json.dumps(_graph(["A1", "A2"])), encoding="utf-8")
    assert CCK.main([str(tmp_path), "--predecessor-graph", str(pred)]) == 1


def test_main_not_a_dir_exit2(tmp_path):
    assert CCK.main([str(tmp_path / "missing")]) == 2
