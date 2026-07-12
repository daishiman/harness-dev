"""check-shape-non-regression.py の機能テスト (C14 (a) 精度携帯率 / (c) 再現性)。

conftest 非依存でスクリプトを file-path ロードし、P04 C14 受入例 (旧shape 携帯率 0% を
基準線とし新shape がこれを下回らないこと / 検証不能自然文 "がんばる" の除外 / derive 2 回
byte 一致) を tmp_path fixture で検証する。
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


csnr = _load("check-shape-non-regression")

# 新shape 受入例 (P04 C14) の acceptance_criterion (検証可能な事前解決判断を内包)。
_REAL_CRITERION = (
    "phase 各完了チェックリスト項目 1 件を task node 候補とし node.phase_ref/entity_ref を"
    "仮想ルートへ parent_of で連結する導出ルールが確定し、C2 受入例の 4 node に対し"
    "derive-task-graph.py を実行した出力が当該テーブルと一致する"
)


# ─────────────────── acceptance_attachment_rate (精度・C14 a) ───────────────────
def test_new_shape_node_with_criterion_and_produces_is_attached():
    """acceptance_criterion (検証可能) + produces を携帯する node は 1 とカウント (1/1=1.0)。"""
    node = {"id": "T2", "title": "derive-task-graph.py 設計確定", "acceptance_criterion": _REAL_CRITERION,
            "produces": ["A2=derive-task-graph 設計節"]}
    assert csnr.acceptance_attachment_rate([node]) == 1.0


def test_removing_criterion_drops_rate_to_zero():
    """acceptance_criterion を削ると携帯率 0/1=0.0 (旧基準線 0% と同値=境界・劣化ではない)。"""
    node = {"id": "T2", "title": "x", "produces": ["A2"]}
    assert csnr.acceptance_attachment_rate([node]) == 0.0


def test_unverifiable_natural_text_criterion_excluded():
    """検証不能な自然文 (がんばる) のみの acceptance_criterion は携帯カウントから除外 (0/1=0.0)。"""
    node = {"id": "T2", "title": "x", "acceptance_criterion": "がんばる", "produces": ["A2"]}
    assert csnr.acceptance_attachment_rate([node]) == 0.0


def test_produces_via_edges_counts():
    """edges に produces エッジ (from=node id) があれば inline produces field 無しでも携帯扱い。"""
    nodes = [{"id": "T1", "acceptance_criterion": _REAL_CRITERION}]
    edges = [{"type": "produces", "from": "T1", "to": "A1"}]
    assert csnr.acceptance_attachment_rate(nodes, edges=edges) == 1.0


def test_no_produces_with_edges_given_is_not_attached():
    """edges 指定時は produces 要件を課す: produces を指さない node は非携帯 (0.0)。"""
    nodes = [{"id": "T1", "acceptance_criterion": _REAL_CRITERION}]
    edges = [{"type": "depends_on", "from": "T1", "to": "T0"}]
    assert csnr.acceptance_attachment_rate(nodes, edges=edges) == 0.0


def test_edges_none_and_no_produces_field_uses_criterion_only():
    """edges 未指定かつ produces field 無しなら acceptance_criterion 非空 (検証可能) のみで判定。"""
    nodes = [{"id": "T1", "acceptance_criterion": _REAL_CRITERION}]
    assert csnr.acceptance_attachment_rate(nodes, edges=None) == 1.0


def test_empty_nodes_rate_is_zero():
    assert csnr.acceptance_attachment_rate([]) == 0.0


def test_non_dict_node_skipped():
    node = {"id": "T2", "acceptance_criterion": _REAL_CRITERION, "produces": ["A2"]}
    assert csnr.acceptance_attachment_rate([node, "not-a-node"]) == 1.0


def test_phase_gate_is_excluded_from_attachment_denominator():
    leaf = {
        "id": "T2",
        "execution_kind": "direct-task",
        "acceptance_criterion": _REAL_CRITERION,
        "produces": ["A2"],
    }
    root = {"id": "P05", "execution_kind": "phase-gate"}
    assert csnr.acceptance_attachment_rate([root, leaf]) == 1.0


def test_is_verifiable_criterion_helper():
    assert csnr._is_verifiable_criterion("がんばる") is False
    assert csnr._is_verifiable_criterion("") is False
    assert csnr._is_verifiable_criterion("exit0 で一致") is True  # 具体語
    assert csnr._is_verifiable_criterion("あ" * 25) is True  # 20 文字以上


# ─────────────────── legacy_baseline_rate (基準線) ───────────────────
def _write_phase(dir_path, name, phase_id, entities, checklist_items):
    fm_entities = "[" + ", ".join(entities) + "]"
    lines = [
        "---",
        f"id: {phase_id}",
        f"entities_covered: {fm_entities}",
        "---",
        "",
        f"# {phase_id}",
        "",
        "## 完了チェックリスト",
    ]
    for it in checklist_items:
        lines.append(f"- [ ] {it}")
    (dir_path / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_legacy_baseline_prose_action_item_is_zero(tmp_path):
    """旧shape §5 は暗黙の受入単位なので散文でも基準線は1.0。"""
    _write_phase(tmp_path, "phase-05-implementation.md", "P05", [],
                 ["derive-task-graph.py の決定論導出ルールを実装する。"])
    files = sorted(tmp_path.glob("phase-*.md"))
    assert csnr.legacy_baseline_rate(files) == 1.0


def test_legacy_baseline_outcome_item_is_one(tmp_path):
    """outcome 表現 (一致) を携帯する項目は検証可能 → 1.0。"""
    _write_phase(tmp_path, "phase-05-implementation.md", "P05", [],
                 ["derive-task-graph.py の出力が上表と一致する。"])
    files = sorted(tmp_path.glob("phase-*.md"))
    assert csnr.legacy_baseline_rate(files) == 1.0


def test_legacy_baseline_no_items_is_zero(tmp_path):
    _write_phase(tmp_path, "phase-01-requirements.md", "P01", [], [])
    files = sorted(tmp_path.glob("phase-*.md"))
    assert csnr.legacy_baseline_rate(files) == 0.0


def test_legacy_baseline_missing_file_tolerated(tmp_path):
    """存在しないパスは走査対象外として無視され例外にならない。"""
    assert csnr.legacy_baseline_rate([tmp_path / "does-not-exist.md"]) == 0.0


# ─────────────────── check_reproducibility (再現性・C14 c) ───────────────────
def _minimal_plan(tmp_path):
    _write_phase(tmp_path, "phase-01-requirements.md", "P01", [], ["X する"])
    (tmp_path / "component-inventory.json").write_text(
        json.dumps({"components": [{"id": "C01", "build_target": "scripts/x.py", "depends_on": []}]}),
        encoding="utf-8",
    )


def _write_target_task_spec(tmp_path):
    specs = tmp_path / "task-specs"
    specs.mkdir(exist_ok=True)
    (specs / "T2.md").write_text(
        "---\n"
        "id: T2\n"
        "title: 設計確定\n"
        "phase_ref: P05\n"
        "execution_kind: direct-task\n"
        "objective: 決定論導出を実装する\n"
        "verify: pytest tests/test_shape.py\n"
        f"acceptance_criterion: {_REAL_CRITERION}\n"
        "write_scope: scripts/x.py\n"
        "produces: [A2]\n"
        "---\n",
        encoding="utf-8",
    )


def test_reproducibility_no_violations(tmp_path):
    """最小 plan で derive 2 回が canonical byte 一致 + node id 集合一致 → violations 空。"""
    _minimal_plan(tmp_path)
    assert csnr.check_reproducibility(tmp_path) == []


# ─────────────────── main (exit 判定) ───────────────────
def _satisfying_plan(tmp_path):
    """baseline=1.0 かつ 新shape 携帯率 1.0 の非劣化 fixture。"""
    _minimal_plan(tmp_path)
    (tmp_path / "index.md").write_text(
        "---\nshape_marker: task-graph-derived\n---\n", encoding="utf-8"
    )
    _write_target_task_spec(tmp_path)
    graph = {
        "schema_version": "1.0",
        "nodes": [{"id": "T2", "title": "設計確定", "acceptance_criterion": _REAL_CRITERION}],
        "edges": [{"type": "produces", "from": "T2", "to": "A2"}],
    }
    (tmp_path / "task-graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")


def test_main_exit0_on_satisfying_fixture(tmp_path, capsys):
    _satisfying_plan(tmp_path)
    assert csnr.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""


def test_main_exit0_without_task_graph(tmp_path):
    """fixed-13-phase は adoption gate 非適用で再現性のみ確認して exit0。"""
    _minimal_plan(tmp_path)
    assert csnr.main([str(tmp_path)]) == 0


def _regressing_plan(tmp_path):
    """baseline=1.0 (outcome 項目) かつ 新shape 携帯率 0.0 → 劣化 fixture。"""
    _write_phase(tmp_path, "phase-05-implementation.md", "P05", [],
                 ["derive-task-graph.py の出力が上表と一致する。"])
    (tmp_path / "component-inventory.json").write_text(
        json.dumps({"components": [{"id": "C01", "build_target": "scripts/x.py", "depends_on": []}]}),
        encoding="utf-8",
    )
    (tmp_path / "index.md").write_text(
        "---\nshape_marker: task-graph-derived\n---\n", encoding="utf-8"
    )
    _write_target_task_spec(tmp_path)
    graph = {
        "schema_version": "1.0",
        "nodes": [{"id": "T2", "title": "設計確定"}],  # acceptance_criterion 欠落 → 携帯率 0
        "edges": [{"type": "produces", "from": "T2", "to": "A2"}],
    }
    (tmp_path / "task-graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")


def test_main_exit1_on_regression(tmp_path, capsys):
    _regressing_plan(tmp_path)
    assert csnr.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "携帯率劣化" in out


def test_main_recommend_fallback_appends_marker(tmp_path, capsys):
    _regressing_plan(tmp_path)
    assert csnr.main([str(tmp_path), "--recommend-fallback"]) == 1
    out = capsys.readouterr().out
    assert "shape_marker: fixed-13-phase" in out


def test_main_usage_error_no_arg():
    assert csnr.main([]) == 2


def test_main_usage_error_unknown_option(tmp_path):
    assert csnr.main([str(tmp_path), "--bogus"]) == 2


def test_main_not_a_directory(tmp_path):
    assert csnr.main([str(tmp_path / "nope")]) == 2


def test_main_bad_task_graph_json(tmp_path):
    _minimal_plan(tmp_path)
    (tmp_path / "index.md").write_text(
        "---\nshape_marker: task-graph-derived\n---\n", encoding="utf-8"
    )
    _write_target_task_spec(tmp_path)
    (tmp_path / "task-graph.json").write_text("{ not json", encoding="utf-8")
    assert csnr.main([str(tmp_path)]) == 2
