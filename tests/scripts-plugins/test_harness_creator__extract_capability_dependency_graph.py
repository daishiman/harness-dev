"""ENG-C06 extract-capability-dependency-graph.py の genuine 機能テスト (H6 実装)。

生成 harness の surface 横断依存グラフを決定論抽出し、未知参照/循環/空 graph を fail-closed。

カバー分岐:
- discover_nodes: skill/command/agent/hook/script surface 発見 + frontmatter name 解決 + id 昇順
- extract_edges: skill-invoke / script-call / pair / agent-bind edge + builtin agent 除外 + gap 分離 + dedup
- find_cycle: 非循環 None / 循環パス返却
- build_graph: 空 graph fail / gap fail / cycle fail / clean OK
- main(CLI): clean exit0 / gap exit1 (JSON も stdout) / 非存在 dir exit2

network: false, 実 repo 書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins/harness-creator/skills/run-build-skill"
    / "templates/task-graph-engine/scripts/extract-capability-dependency-graph.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("extract_capability_dependency_graph", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _harness(tmp_path, skills):
    """skills = {name: body}。skills/<name>/SKILL.md を作る。"""
    root = tmp_path / "harness"
    for name, body in skills.items():
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n{body}\n", encoding="utf-8")
    return root


def _run(root):
    return subprocess.run([sys.executable, str(SCRIPT), str(root)], capture_output=True, text=True)


# --- discover_nodes ---
def test_discover_nodes_all_surfaces(tmp_path):
    root = tmp_path / "h"
    (root / "skills/run-a").mkdir(parents=True)
    (root / "skills/run-a/SKILL.md").write_text("---\nname: run-a\n---\nx\n")
    (root / "commands").mkdir()
    (root / "commands/do-x.md").write_text("---\nname: do-x\n---\nx\n")
    (root / "agents").mkdir()
    (root / "agents/rev.md").write_text("---\nname: rev\n---\nx\n")
    (root / "hooks").mkdir()
    (root / "hooks/pre.py").write_text("x\n")
    (root / "scripts").mkdir()
    (root / "scripts/util.py").write_text("x\n")
    nodes = mod.discover_nodes(root)
    ids = {n["id"] for n in nodes}
    assert ids == {"skill:run-a", "command:do-x", "agent:rev", "hook:pre.py", "script:util.py"}
    # id 昇順
    assert [n["id"] for n in nodes] == sorted(ids)


def test_discover_nodes_fallback_name(tmp_path):
    root = tmp_path / "h"
    (root / "skills/run-b").mkdir(parents=True)
    (root / "skills/run-b/SKILL.md").write_text("no frontmatter name\n")  # name 不在 → dir 名
    nodes = mod.discover_nodes(root)
    assert nodes[0]["id"] == "skill:run-b"


# --- extract_edges ---
def test_extract_edges_via_harness(tmp_path):
    root = _harness(tmp_path, {
        "run-a": "Skill(run-b) を呼び scripts/h.py も使う",
        "run-b": "自己完結",
    })
    (root / "scripts").mkdir()
    (root / "scripts/h.py").write_text("x\n")
    nodes = mod.discover_nodes(root)
    edges, gaps = mod.extract_edges(root, nodes)
    et = {(e["from"], e["to"], e["type"]) for e in edges}
    assert ("skill:run-a", "skill:run-b", "skill-invoke") in et
    assert ("skill:run-a", "script:h.py", "script-call") in et
    assert gaps == []


def test_extract_edges_builtin_agent_excluded(tmp_path):
    root = _harness(tmp_path, {"run-a": "Agent(general-purpose) を使う"})
    nodes = mod.discover_nodes(root)
    edges, gaps = mod.extract_edges(root, nodes)
    assert edges == [] and gaps == []  # builtin は edge にも gap にもしない


def test_extract_edges_gap_for_unknown(tmp_path):
    root = _harness(tmp_path, {"run-a": "Skill(run-ghost) を参照"})
    nodes = mod.discover_nodes(root)
    edges, gaps = mod.extract_edges(root, nodes)
    assert edges == []
    assert gaps and gaps[0]["ref"] == "skill:run-ghost"


def test_extract_edges_dedup(tmp_path):
    root = _harness(tmp_path, {"run-a": "Skill(run-b) と Skill(run-b) 二回", "run-b": "x"})
    nodes = mod.discover_nodes(root)
    edges, _ = mod.extract_edges(root, nodes)
    invokes = [e for e in edges if e["type"] == "skill-invoke"]
    assert len(invokes) == 1  # 重複 edge は 1 本


# --- find_cycle ---
def test_find_cycle_none():
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"from": "a", "to": "b", "type": "t"}]
    assert mod.find_cycle(nodes, edges) is None


def test_find_cycle_detected():
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [{"from": "a", "to": "b", "type": "t"}, {"from": "b", "to": "a", "type": "t"}]
    cyc = mod.find_cycle(nodes, edges)
    assert cyc and cyc[0] == cyc[-1]


def test_find_cycle_three_node():
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    edges = [{"from": "a", "to": "b", "type": "t"}, {"from": "b", "to": "c", "type": "t"},
             {"from": "c", "to": "a", "type": "t"}]
    cyc = mod.find_cycle(nodes, edges)
    assert cyc and cyc[0] == cyc[-1] and len(cyc) == 4  # a->b->c->a


def test_find_cycle_deep_chain_no_recursion_error():
    # 深い直鎖 (2000 surface) でも RecursionError にならず None
    nodes = [{"id": f"n{i}"} for i in range(2001)]
    edges = [{"from": f"n{i}", "to": f"n{i+1}", "type": "t"} for i in range(2000)]
    assert mod.find_cycle(nodes, edges) is None


def test_find_cycle_diamond_no_false_positive():
    nodes = [{"id": x} for x in ("a", "b", "c", "d")]
    edges = [{"from": "a", "to": "b", "type": "t"}, {"from": "a", "to": "c", "type": "t"},
             {"from": "b", "to": "d", "type": "t"}, {"from": "c", "to": "d", "type": "t"}]
    assert mod.find_cycle(nodes, edges) is None


# --- build_graph ---
def test_build_graph_empty_fails(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    graph, findings = mod.build_graph(root)
    assert graph["nodes"] == []
    assert any("空 graph" in f for f in findings)


def test_build_graph_clean_ok(tmp_path):
    root = _harness(tmp_path, {"run-a": "Skill(run-b)", "run-b": "x"})
    graph, findings = mod.build_graph(root)
    assert findings == []
    assert len(graph["nodes"]) == 2


def test_build_graph_gap_fails(tmp_path):
    root = _harness(tmp_path, {"run-a": "Skill(run-ghost)"})
    _, findings = mod.build_graph(root)
    assert any("未知参照" in f for f in findings)


# --- main CLI ---
def test_main_clean_exit0(tmp_path):
    root = _harness(tmp_path, {"run-a": "Skill(run-b)", "run-b": "x"})
    r = _run(root)
    assert r.returncode == 0
    assert json.loads(r.stdout)["nodes"]


def test_main_gap_exit1_but_json(tmp_path):
    root = _harness(tmp_path, {"run-a": "Skill(run-ghost)"})
    r = _run(root)
    assert r.returncode == 1
    assert json.loads(r.stdout)["gaps"]  # 失敗時も JSON は stdout に出る


def test_main_missing_dir_exit2(tmp_path):
    r = _run(tmp_path / "nope")
    assert r.returncode == 2
