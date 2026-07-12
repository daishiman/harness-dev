"""render-task-graph-mermaid.py の機能テスト (C15・conftest 非依存)。

byte一致 render + graph 外要素非描画 (node id 集合の set 一致) + 4 線種割当 +
critical_path (depends_on 最長依存鎖・tie 辞書順) を網羅する。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rtm = _load("render-task-graph-mermaid")
dtg = _load("derive-task-graph")

_DECL_RE = re.compile(r'^ {4}(\S+)\["')


def _node(nid, entity, state="pending", title=None):
    return {
        "id": nid,
        "title": title or f"{nid} title",
        "phase_ref": "P05",
        "entity_ref": entity,
        "state": state,
        "write_scope": nid,
    }


def _c2_simple_graph():
    """C15 簡易版: T1=done / T2-T4=pending, depends_on のみ (produces/consumes なし)。"""
    nodes = [
        _node("T1", "C01", state="done", title="C01/C02 component-inventory 確定"),
        _node("T2", "C01", state="pending", title="derive-task-graph.py 設計確定"),
        _node("T3", "C02", state="pending", title="R1-evaluate.md C8判定ステップ設計確定"),
        _node("T4", "C01", state="pending", title="handoff task_graph_ref 検証設計確定"),
    ]
    edges = [{"type": "depends_on", "from": f, "to": t} for f, t in [("T2", "T1"), ("T3", "T1"), ("T4", "T2"), ("T4", "T3")]]
    return dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})


def _extract_decl_ids(mermaid: str) -> set:
    return {m.group(1) for line in mermaid.splitlines() if (m := _DECL_RE.match(line))}


# ─────────────────── header / classDef ───────────────────
def test_header_and_classdefs():
    out = rtm.render_mermaid(_c2_simple_graph())
    lines = out.splitlines()
    assert lines[0] == "graph TD"
    assert lines[1:5] == [
        "    classDef pending fill:#eee",
        "    classDef running fill:#bbf",
        "    classDef done fill:#bfb",
        "    classDef blocked fill:#fbb",
    ]


def test_node_declarations_with_state_class():
    out = rtm.render_mermaid(_c2_simple_graph())
    assert '    T1["C01/C02 component-inventory 確定"]:::done' in out
    assert '    T2["derive-task-graph.py 設計確定"]:::pending' in out


def test_depends_on_edge_uses_double_arrow():
    out = rtm.render_mermaid(_c2_simple_graph())
    # depends_on は ==>。canonical 順で T2 ==> T1 等が出る。
    assert "    T2 ==> T1" in out
    assert "    T4 ==> T2" in out


# ─────────────────── byte 一致 ───────────────────
def test_byte_identical_repeated_render():
    g = _c2_simple_graph()
    assert rtm.render_mermaid(g) == rtm.render_mermaid(g)


def test_byte_identical_with_state():
    g = _c2_simple_graph()
    st = {"nodes": [{"id": "T2", "state": "running"}]}
    assert rtm.render_mermaid(g, st) == rtm.render_mermaid(g, st)


# ─────────────────── graph 外要素非描画 ───────────────────
def test_declared_node_ids_match_graph():
    g = _c2_simple_graph()
    out = rtm.render_mermaid(g)
    assert _extract_decl_ids(out) == {n["id"] for n in g["nodes"]}


# ─────────────────── 4 線種割当 ───────────────────
def test_all_four_edge_styles():
    nodes = [_node("N1", "C01"), _node("N2", "C01")]
    edges = [
        {"type": "parent_of", "from": "N1", "to": "N2"},
        {"type": "depends_on", "from": "N2", "to": "N1"},
        {"type": "produces", "from": "N1", "to": "ART"},
        {"type": "consumes", "from": "ART", "to": "N2"},
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    out = rtm.render_mermaid(g)
    assert "    N1 --> N2" in out       # parent_of
    assert "    N2 ==> N1" in out       # depends_on
    assert "    N1 -.-> ART" in out     # produces
    assert "    ART --o N2" in out      # consumes


# ─────────────────── task_state override ───────────────────
def test_task_state_overrides_node_state():
    g = _c2_simple_graph()
    st = {"nodes": [{"id": "T2", "state": "running"}]}
    out = rtm.render_mermaid(g, st)
    assert '    T2["derive-task-graph.py 設計確定"]:::running' in out
    # 上書き対象外は graph の state のまま
    assert '    T1["C01/C02 component-inventory 確定"]:::done' in out


def test_task_state_none_uses_graph_state():
    g = _c2_simple_graph()
    a = rtm.render_mermaid(g, None)
    b = rtm.render_mermaid(g)
    assert a == b


def test_state_map_ignores_malformed_entries():
    assert rtm._state_map(None) == {}
    assert rtm._state_map({"nodes": [{"id": "T1"}, {"state": "done"}, {"id": "T2", "state": "done"}]}) == {"T2": "done"}


# ─────────────────── critical_path ───────────────────
def test_critical_path_longest_chain_tiebreak():
    g = _c2_simple_graph()
    # depends_on: T2→T1,T3→T1,T4→T2,T4→T3。最長鎖 T4-T2-T1 / T4-T3-T1 の tie を辞書順で T4-T2-T1。
    # critical_path は実行順 (dependency→dependent) で返す。
    assert rtm.critical_path(g) == ["T1", "T2", "T4"]


def test_longest_dep_chain_depends_on_order():
    g = _c2_simple_graph()
    assert rtm._longest_dep_chain(g) == ["T4", "T2", "T1"]


def test_critical_path_empty_when_no_depends_on():
    nodes = [_node("N1", "C01")]
    edges = [{"type": "produces", "from": "N1", "to": "A1"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    assert rtm.critical_path(g) == []


def test_critical_path_linkstyle_emitted():
    out = rtm.render_mermaid(_c2_simple_graph())
    # critical path 上の depends_on エッジ 2 本が linkStyle 強調される。
    assert out.count("linkStyle") == 2
    assert rtm._CRITICAL_LINKSTYLE in out


def test_no_linkstyle_without_depends_on():
    nodes = [_node("N1", "C01"), _node("N2", "C01")]
    edges = [{"type": "parent_of", "from": "N1", "to": "N2"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    out = rtm.render_mermaid(g)
    assert "linkStyle" not in out


# ─────────────────── main() CLI ───────────────────
def _write_graph(tmp_path, graph):
    (tmp_path / "task-graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")


def test_main_writes_mmd(tmp_path):
    g = _c2_simple_graph()
    _write_graph(tmp_path, g)
    assert rtm.main([str(tmp_path)]) == 0
    mmd = (tmp_path / "task-graph.mmd").read_text(encoding="utf-8")
    assert mmd == rtm.render_mermaid(g)


def test_main_with_task_state(tmp_path):
    g = _c2_simple_graph()
    _write_graph(tmp_path, g)
    st_path = tmp_path / "task-state.json"
    st = {"nodes": [{"id": "T2", "state": "running"}]}
    st_path.write_text(json.dumps(st), encoding="utf-8")
    assert rtm.main([str(tmp_path), "--task-state", str(st_path)]) == 0
    mmd = (tmp_path / "task-graph.mmd").read_text(encoding="utf-8")
    assert ":::running" in mmd


def test_main_usage_no_args():
    assert rtm.main([]) == 2


def test_main_usage_too_many_positional():
    assert rtm.main(["a", "b"]) == 2


def test_main_usage_dangling_task_state_flag(tmp_path):
    assert rtm.main([str(tmp_path), "--task-state"]) == 2


def test_main_not_a_directory(tmp_path):
    assert rtm.main([str(tmp_path / "missing")]) == 2


def test_main_bad_graph_json(tmp_path):
    (tmp_path / "task-graph.json").write_text("{ not json", encoding="utf-8")
    assert rtm.main([str(tmp_path)]) == 2


def test_main_bad_task_state_json(tmp_path):
    _write_graph(tmp_path, _c2_simple_graph())
    bad = tmp_path / "bad-state.json"
    bad.write_text("{ bad", encoding="utf-8")
    assert rtm.main([str(tmp_path), "--task-state", str(bad)]) == 2
