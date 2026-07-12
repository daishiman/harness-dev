"""consult-harness-artifact-graph.py (C07) の read-only デュアルグラフ探索テスト。

C06 の knowledge-graph.json と C05 の harness-artifact-graph.json を跨いで
local / global / relationship の 3 query を実行し、hits を source refs/path/graph hash
付きで返す。fixture は tmp_path 内に最小グラフを自作し実 knowledge/ を汚さない。

被覆:
  - known-hit (local: 既知 knowledge edge>=1 + 実在 harness artifact>=1)   -> exit0
  - 正しい zero-hit (topic 不一致 -> 空 hits + zero_hit フラグ)             -> exit0
  - 壊れた index (スキーマ不正 / dangling edge) を zero-hit と区別          -> exit2
  - path traversal 拒否 (グラフ引数の '..')                                 -> exit2
  - secret 本文非返却 (redaction)                                          -> exit0
  - depth 上限 (遠方ノードは depth を上げないと出ない)                     -> exit0
  - global (カテゴリ/state クラスタ要約)                                    -> exit0
  - relationship (2 概念間 path 探索・区切り必須)                          -> exit0 / exit2
  - harness graph 省略 (knowledge 単独 consult・harness=absent)             -> exit0
  - knowledge 辺 0 本の退化グラフ (warnings に graph-edges-empty)           -> exit0
  - usage (knowledge-graph 欠落 / query-type 不正 / depth 範囲外 / graph 不在) -> exit2
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/consult-harness-artifact-graph.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def knowledge_graph(*, secret: str | None = None, dangling: bool = False) -> dict:
    """C06 スキーマの最小 knowledge-graph。

    ノード: PR-001(alpha growth principle) - PR-002(beta principle) -
            PR-003(delta principle) - PR-004(epsilon) の supports 鎖 +
            CP-010(gamma consultation) が PR-001 へ depends_on。
    """
    title1 = "alpha growth principle"
    if secret is not None:
        title1 = f"alpha growth {secret} principle"
    nodes = [
        {"id": "PR-001", "category": "principles", "subcategory": "growth", "title": title1},
        {"id": "PR-002", "category": "principles", "subcategory": "growth", "title": "beta principle"},
        {"id": "PR-003", "category": "principles", "subcategory": "habit", "title": "delta principle"},
        {"id": "PR-004", "category": "principles", "subcategory": "habit", "title": "epsilon"},
        {"id": "CP-010", "category": "consultation", "subcategory": "sales", "title": "gamma consultation"},
    ]
    tgt = "PR-999-missing" if dangling else "PR-001"
    edges = [
        {"source_id": "PR-001", "target_id": "PR-002", "relation_type": "supports",
         "evidence": ["alpha を支える逐語引用"], "source_ref": "principles-growth.json#PR-001",
         "confidence": 0.9, "review_status": "reviewed"},
        {"source_id": "PR-002", "target_id": "PR-003", "relation_type": "supports",
         "evidence": ["beta が delta を支える"], "source_ref": "principles-growth.json#PR-002",
         "confidence": 0.8, "review_status": "reviewed"},
        {"source_id": "PR-003", "target_id": "PR-004", "relation_type": "supports",
         "evidence": ["delta が epsilon を支える"], "source_ref": "principles-habit.json#PR-003",
         "confidence": 0.7, "review_status": "reviewed"},
        {"source_id": "CP-010", "target_id": tgt, "relation_type": "depends_on",
         "evidence": ["gamma は alpha に依存"], "source_ref": "consultation-sales.json#CP-010",
         "confidence": 0.85, "review_status": "reviewed"},
    ]
    associations = [{"a": "CP-010", "b": "PR-001", "kind": "related"}]
    return {
        "schema_version": "1.0.0",
        "generator": "validate-knowledge-graph.py",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "association_count": len(associations),
        "nodes": nodes,
        "edges": edges,
        "associations": associations,
    }


def harness_graph(*, drop_nodes: bool = False, dangling: bool = False) -> dict:
    """C05 スキーマの最小 harness-artifact-graph。alpha-collector(C01) が topic 'alpha' に一致。"""
    nodes = [
        {"id": "C01", "component_kind": "sub-agent", "name": "alpha-collector",
         "build_target": "plugins/x/agents/alpha-collector.md", "state": "verified",
         "provenance": {"route": "handoff#routes[id=C01]", "builder": "run-build-skill",
                        "route_report": "eval-log/x/build/route-C01.json",
                        "build_trace": "eval-log/x/build/skill-build-trace-C01.json"},
         "freshness": {"artifact_present": True, "state": "verified", "stale_reasons": []}},
        {"id": "C05", "component_kind": "script", "name": "index-harness-artifact-graph.py",
         "build_target": "plugins/x/scripts/index-harness-artifact-graph.py", "state": "built",
         "provenance": {"route": "handoff#routes[id=C05]", "builder": "plugin-scaffold",
                        "route_report": "eval-log/x/build/route-C05.json", "build_trace": None},
         "freshness": {"artifact_present": True, "state": "built", "stale_reasons": []}},
        {"id": "C07", "component_kind": "script", "name": "consult-harness-artifact-graph.py",
         "build_target": "plugins/x/scripts/consult-harness-artifact-graph.py", "state": "planned",
         "provenance": {"route": "handoff#routes[id=C07]", "builder": "plugin-scaffold",
                        "route_report": None, "build_trace": None},
         "freshness": {"artifact_present": False, "state": "planned", "stale_reasons": []}},
    ]
    edges = [
        {"from": "C01", "to": "C05", "type": "depends_on"},
        {"from": "C07", "to": ("C99-missing" if dangling else "C05"), "type": "depends_on"},
    ]
    g = {
        "schema_version": "1.0.0",
        "generator": "index-harness-artifact-graph.py",
        "plugin_slug": "x",
        "graph_hash": {"task_state": "sha256:" + "a" * 64, "recomputed": "sha256:" + "a" * 64, "match": True},
        "counts": {"node_count": len(nodes), "edge_count": len(edges),
                   "state_planned": 1, "state_built": 1, "state_verified": 1, "state_stale": 0, "redacted": 0},
        "sources": {},
        "nodes": nodes,
        "edges": edges,
    }
    if drop_nodes:
        del g["nodes"]
    return g


def _setup(tmp_path: Path, *, secret=None, kg_dangling=False, hg_drop=False, hg_dangling=False) -> dict:
    kg = tmp_path / "knowledge-graph.json"
    hg = tmp_path / "harness-artifact-graph.json"
    write_json(kg, knowledge_graph(secret=secret, dangling=kg_dangling))
    write_json(hg, harness_graph(drop_nodes=hg_drop, dangling=hg_dangling))
    return {"kg": str(kg), "hg": str(hg)}


def consult(ctx: dict, topic: str, query_type: str = "local", depth: str = "2",
            *, with_harness: bool = True) -> subprocess.CompletedProcess:
    args = ["--topic", topic, "--knowledge-graph", ctx["kg"]]
    if with_harness:
        args += ["--harness-artifact-graph", ctx["hg"]]
    args += ["--query-type", query_type, "--depth", depth]
    return run(*args)


# ---- known-hit (local) -----------------------------------------------------

def test_local_known_hit_returns_knowledge_edge_and_harness_artifact(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "local", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["zero_hit"] is False
    # 既知 knowledge edge >= 1
    assert out["counts"]["knowledge_edges"] >= 1
    assert len(out["hits"]["knowledge"]["edges"]) >= 1
    # 実在 harness artifact >= 1 (topic 'alpha' が C01 alpha-collector に一致)
    assert out["counts"]["harness_nodes"] >= 1
    h_ids = {n["id"] for n in out["hits"]["harness"]["nodes"]}
    assert "C01" in h_ids
    # source refs / path / graph hash が付く
    assert out["sources"]["knowledge_graph"]["sha256"].startswith("sha256:")
    assert out["sources"]["harness_artifact_graph"]["sha256"].startswith("sha256:")
    for n in out["hits"]["knowledge"]["nodes"]:
        assert "source_ref" in n and n["source_ref"]


def test_local_edges_are_pointers_not_verbatim_evidence(tmp_path: Path):
    # hit の evidence は id/path/hash まで (逐語 evidence 本文は返さない)
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "local", "1")
    out = json.loads(r.stdout)
    for e in out["hits"]["knowledge"]["edges"]:
        assert "evidence_count" in e
        assert "evidence" not in e  # 逐語本文は載せない
        assert e["source_ref"]


def test_local_harness_nodes_carry_report_refs(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "local", "1")
    out = json.loads(r.stdout)
    c01 = next(n for n in out["hits"]["harness"]["nodes"] if n["id"] == "C01")
    assert c01["state"] == "verified"
    assert c01["build_target"].endswith("alpha-collector.md")
    assert c01["refs"]["route_report"].endswith("route-C01.json")


# ---- zero-hit --------------------------------------------------------------

def test_zero_hit_topic_mismatch_exit0_empty(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "zzz-no-such-topic", "local", "2")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["zero_hit"] is True
    assert out["hits"]["knowledge"]["nodes"] == []
    assert out["hits"]["harness"]["nodes"] == []
    assert out["counts"]["knowledge_edges"] == 0


# ---- broken index (schema invalid / dangling) -> exit2 ---------------------

def test_broken_index_missing_nodes_exit2(tmp_path: Path):
    ctx = _setup(tmp_path, hg_drop=True)
    r = consult(ctx, "alpha", "local", "1")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "broken" in (r.stderr.lower() + r.stdout.lower())


def test_broken_index_dangling_knowledge_edge_exit2(tmp_path: Path):
    ctx = _setup(tmp_path, kg_dangling=True)
    r = consult(ctx, "alpha", "local", "1")
    assert r.returncode == 2, r.stdout + r.stderr


def test_broken_index_dangling_harness_edge_exit2(tmp_path: Path):
    ctx = _setup(tmp_path, hg_dangling=True)
    r = consult(ctx, "alpha", "local", "1")
    assert r.returncode == 2, r.stdout + r.stderr


def test_broken_index_distinguished_from_zero_hit(tmp_path: Path):
    # 壊れた index は exit2、正しい zero-hit は exit0 — 明確に区別される
    broken = _setup(tmp_path / "b", hg_drop=True)
    ok = _setup(tmp_path / "o")
    assert consult(broken, "alpha", "local", "1").returncode == 2
    assert consult(ok, "zzz", "local", "1").returncode == 0


# ---- path traversal --------------------------------------------------------

def test_path_traversal_rejected_exit2(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = run("--topic", "alpha", "--knowledge-graph", "../../../etc/passwd",
            "--harness-artifact-graph", ctx["hg"], "--query-type", "local", "--depth", "1")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "traversal" in (r.stderr.lower()) or "usage" in r.stderr.lower()


def test_path_traversal_rejected_in_harness_arg_exit2(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = run("--topic", "alpha", "--knowledge-graph", ctx["kg"],
            "--harness-artifact-graph", "graphs/../../secret.json", "--query-type", "local", "--depth", "1")
    assert r.returncode == 2, r.stdout + r.stderr


# ---- redaction (secret 本文非返却) -----------------------------------------

def test_secret_not_returned(tmp_path: Path):
    secret = "ghp_" + "A1b2C3d4E5f6G7h8I9j0" + "KLMNOP"
    ctx = _setup(tmp_path, secret=secret)
    r = consult(ctx, "alpha", "local", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert secret not in r.stdout
    out = json.loads(r.stdout)
    assert "[REDACTED]" in r.stdout
    assert out["counts"]["redacted"] >= 1


# ---- depth 上限 ------------------------------------------------------------

def test_depth_bounds_traversal(tmp_path: Path):
    ctx = _setup(tmp_path)
    # PR-001(alpha) --supports--> PR-002 --supports--> PR-003 --supports--> PR-004
    d1 = json.loads(consult(ctx, "alpha", "local", "1").stdout)
    ids1 = {n["id"] for n in d1["hits"]["knowledge"]["nodes"]}
    assert "PR-002" in ids1  # 1 hop
    assert "PR-003" not in ids1  # 2 hop は depth=1 で出ない
    d2 = json.loads(consult(ctx, "alpha", "local", "2").stdout)
    ids2 = {n["id"] for n in d2["hits"]["knowledge"]["nodes"]}
    assert "PR-003" in ids2  # depth=2 で到達


# ---- global ----------------------------------------------------------------

def test_global_category_cluster_summary(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "principle", "global", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["zero_hit"] is False
    g = out["hits"]["global"]
    cats = {c["category"]: c["count"] for c in g["knowledge"]["by_category"]}
    # 'principle' は principles カテゴリの複数ノード title に一致
    assert cats.get("principles", 0) >= 2


def test_global_harness_by_state(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "harness", "global", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    states = {s["state"] for s in out["hits"]["global"]["harness"]["by_state"]}
    # index/consult 両 script が name に 'harness' を含む -> built/planned をクラスタ化
    assert states  # 非空クラスタ


# ---- relationship ----------------------------------------------------------

def test_relationship_path_between_two_concepts(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha -> gamma", "relationship", "3")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["zero_hit"] is False
    assert out["query"]["endpoints"] == ["alpha", "gamma"]
    paths = out["hits"]["paths"]
    assert any(p["graph"] == "knowledge" for p in paths)
    kpath = next(p for p in paths if p["graph"] == "knowledge")
    # alpha(PR-001) と gamma(CP-010) は depends_on/association で 1 hop
    assert kpath["nodes"][0] in ("PR-001", "CP-010")
    assert kpath["nodes"][-1] in ("PR-001", "CP-010")


def test_relationship_no_path_zero_hit(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha -> zzz-nomatch", "relationship", "3")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["zero_hit"] is True
    assert out["hits"]["paths"] == []


def test_relationship_requires_separator_exit2(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "relationship", "3")
    assert r.returncode == 2, r.stdout + r.stderr


# ---- edges=0 退化グラフの warnings ------------------------------------------

def test_knowledge_edges_empty_recorded_in_warnings(tmp_path: Path):
    # knowledge graph の辺 0 本は zero-hit 同様に正常 (exit0) のまま warnings へ表面化する。
    kg_path = tmp_path / "knowledge-graph.json"
    g = knowledge_graph()
    g["edges"] = []
    g["edge_count"] = 0
    g["associations"] = []
    g["association_count"] = 0
    write_json(kg_path, g)
    r = run("--topic", "alpha", "--knowledge-graph", str(kg_path), "--query-type", "local", "--depth", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert "graph-edges-empty" in out["warnings"]


def test_warnings_empty_when_knowledge_edges_present(tmp_path: Path):
    # 辺が載っている graph では warnings は空 (誤検知しない)。
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "local", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["warnings"] == []


# ---- 決定論 ----------------------------------------------------------------

def test_deterministic_stdout(tmp_path: Path):
    ctx = _setup(tmp_path)
    a = consult(ctx, "alpha", "local", "2").stdout
    b = consult(ctx, "alpha", "local", "2").stdout
    assert a == b


# ---- harness graph 省略 (knowledge 単独 consult) ---------------------------

def test_harness_absent_knowledge_only_consult_exit0(tmp_path: Path):
    # --harness-artifact-graph を省略しても knowledge graph 単独で consult できる
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "local", "2", with_harness=False)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    # knowledge 側は通常どおり hit する
    assert out["zero_hit"] is False
    assert out["counts"]["knowledge_edges"] >= 1
    k_ids = {n["id"] for n in out["hits"]["knowledge"]["nodes"]}
    assert "PR-001" in k_ids
    # harness 側は空で absent が明示される
    assert out["sources"]["harness_artifact_graph"]["status"] == "absent"
    assert out["hits"]["harness"]["nodes"] == []
    assert out["counts"]["harness_nodes"] == 0


def test_harness_absent_zero_hit_still_exit0(tmp_path: Path):
    # harness 省略かつ topic 不一致でも zero-hit は正常 (exit0)
    ctx = _setup(tmp_path)
    r = consult(ctx, "zzz-no-such-topic", "local", "2", with_harness=False)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["zero_hit"] is True
    assert out["sources"]["harness_artifact_graph"]["status"] == "absent"


def test_harness_absent_global_and_relationship_exit0(tmp_path: Path):
    # global / relationship も harness 省略で成立する (knowledge 側のみ)
    ctx = _setup(tmp_path)
    g = consult(ctx, "principle", "global", "1", with_harness=False)
    assert g.returncode == 0, g.stdout + g.stderr
    assert json.loads(g.stdout)["hits"]["global"]["harness"]["by_state"] == []
    rel = consult(ctx, "alpha -> gamma", "relationship", "3", with_harness=False)
    assert rel.returncode == 0, rel.stdout + rel.stderr
    paths = json.loads(rel.stdout)["hits"]["paths"]
    # harness 側 path は無く knowledge path のみ
    assert all(p["graph"] == "knowledge" for p in paths)


def test_knowledge_graph_still_required_when_harness_absent_exit2(tmp_path: Path):
    # harness を optional 化しても knowledge-graph は必須のまま
    r = run("--topic", "alpha", "--query-type", "local", "--depth", "1")
    assert r.returncode == 2, r.stdout + r.stderr


# ---- usage -----------------------------------------------------------------

def test_usage_missing_knowledge_graph_exit2(tmp_path: Path):
    # 今も必須の --knowledge-graph 欠落は argparse が exit2
    ctx = _setup(tmp_path)
    r = run("--topic", "alpha", "--harness-artifact-graph", ctx["hg"], "--query-type", "local")
    assert r.returncode == 2


def test_usage_bad_query_type_exit2(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "sideways", "1")
    assert r.returncode == 2


def test_usage_depth_out_of_range_exit2(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = consult(ctx, "alpha", "local", "9")
    assert r.returncode == 2


def test_usage_graph_absent_exit2(tmp_path: Path):
    ctx = _setup(tmp_path)
    r = run("--topic", "alpha", "--knowledge-graph", str(tmp_path / "nope.json"),
            "--harness-artifact-graph", ctx["hg"], "--query-type", "local", "--depth", "1")
    assert r.returncode == 2
