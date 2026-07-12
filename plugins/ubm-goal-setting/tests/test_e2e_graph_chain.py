"""E2E graph チェーン疎通テスト (S9 の反証器)。

正規化ソース(.md) → C08 が返す辺候補の materialize → validate-knowledge-graph.py --merge-relations
(C06) で永続化 + 決定論 graph 再生成 → index-harness-artifact-graph.py (C05) で harness グラフ生成 →
consult-harness-artifact-graph.py (C07) が known-hit を返す、までを一度も断裂なく通す。

このチェーンが緑であることは、C08 出力に永続化 owner が存在し (S1/S5)、その永続化が実際に
knowledge-graph へ反映され (edge_count>0)、C07 から引けること (S4) の直接の反証になる。

C08 (knowledge-relation-extractor) は LLM であり本テストでは fixture の辺候補 JSON で代替する
(呼び出し側が eval-log 等へ materialize する成果物と同形状)。他ノード (C05/C06/C07) は実 script を実行する。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = PLUGIN_ROOT / "scripts/validate-knowledge-graph.py"
INDEX = PLUGIN_ROOT / "scripts/index-harness-artifact-graph.py"
CONSULT = PLUGIN_ROOT / "scripts/consult-harness-artifact-graph.py"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True,
    )


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _build_knowledge_fixture(kdir: Path, source_md: Path) -> None:
    """正規化ソース(.md) と、それ由来の knowledge entry (2カテゴリ) を用意する。"""
    source_md.parent.mkdir(parents=True, exist_ok=True)
    source_md.write_text(
        "# 正規化ソース (fixture)\n\n"
        "関係構築こそが土台であり、信頼のマインドセットがそれを支える。\n",
        encoding="utf-8",
    )
    src_rel = source_md.name
    _write_json(kdir / "principles-relationship.json", {
        "category": "principles",
        "subcategory": "relationship",
        "entries": [
            {"id": "PR-001", "title": "関係構築の原則",
             "content": "関係構築こそが土台", "related": ["MS-001"],
             "source": {"file": src_rel}},
        ],
    })
    _write_json(kdir / "mindset-trust.json", {
        "category": "mindset",
        "subcategory": "trust",
        "entries": [
            {"id": "MS-001", "title": "信頼のマインドセット",
             "content": "信頼が関係を支える", "related": ["PR-001"],
             "source": {"file": src_rel}},
        ],
    })


def _materialize_c08_candidate(path: Path, source_md_name: str) -> None:
    """C08 (LLM) が返す辺候補を fixture で代替 materialize する。呼び出し側成果物と同形状。"""
    _write_json(path, {
        "edges": [
            {
                "source_id": "MS-001",
                "target_id": "PR-001",
                "relation_type": "supports",
                "evidence": ["信頼が関係を支える"],
                "source_ref": f"MS-001:{source_md_name} / PR-001:{source_md_name}",
                "confidence": 0.82,
                "review_status": "pending_review",
            }
        ]
    })


def _build_harness_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """index-harness-artifact-graph.py (C05) を実走させるための最小 plan を用意し実行する。"""
    plugin_root = tmp_path / "plugins" / "ubm-e2e"
    plugin_root.mkdir(parents=True)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_json(plan_dir / "task-graph.json", {
        "schema_version": "1.0",
        "nodes": [{
            "id": "T-C99", "title": "知識グラフ検証", "phase_ref": "graph",
            "entity_ref": "C99", "state": "pending", "write_scope": "knowledge/",
            "acceptance_criterion": "validate-knowledge-graph exit0",
        }],
        "edges": [],
    })
    _write_json(plan_dir / "handoff-run-plugin-dev-plan.json", {
        "routes": [{
            "id": "C99",
            "component_kind": "script",
            "name": "知識グラフ検証",
            "build_target": "plugins/ubm-e2e/scripts/validate-knowledge-graph.py",
            "builder": "run-build-skill",
            "depends_on": [],
        }],
    })
    harness_out = tmp_path / "harness-artifact-graph.json"
    r = _run(INDEX,
             "--plan-glob", str(plan_dir / "task-graph.json"),
             "--plugin-root", str(plugin_root),
             "--out", str(harness_out))
    assert r.returncode == 0, "index (C05) failed:\n" + r.stdout + r.stderr
    assert harness_out.is_file()
    return plugin_root, harness_out


def test_e2e_graph_chain_known_hit(tmp_path: Path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    source_md = tmp_path / "sources" / "kitahara-relationship.md"
    _build_knowledge_fixture(kdir, source_md)

    # (b) C08 が返す辺候補を materialize (LLM の代替)
    candidate = tmp_path / "eval-log" / "relations-candidate.json"
    _materialize_c08_candidate(candidate, source_md.name)

    # (c) C06: 候補を merge し永続化 + graph 決定論再生成 (exit0)
    kgraph = kdir / "knowledge-graph.json"
    r_merge = _run(VALIDATE,
                   "--knowledge-dir", str(kdir),
                   "--merge-relations", str(candidate),
                   "--graph-out", str(kgraph))
    assert r_merge.returncode == 0, "merge/validate (C06) failed:\n" + r_merge.stdout + r_merge.stderr
    # 永続ストアが書かれ、graph に辺が載った (S1/S4 反証: 候補が実際に消費・永続化された)
    relations = json.loads((kdir / "knowledge-relations.json").read_text(encoding="utf-8"))
    assert len(relations["edges"]) == 1
    graph = json.loads(kgraph.read_text(encoding="utf-8"))
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1

    # harness グラフ (C05) を実走生成
    _plugin_root, harness_out = _build_harness_fixture(tmp_path)

    # (d) C07: 生成された knowledge-graph に対し known-hit を返す
    r_consult = _run(CONSULT,
                     "--topic", "関係構築",
                     "--knowledge-graph", str(kgraph),
                     "--harness-artifact-graph", str(harness_out),
                     "--query-type", "local",
                     "--depth", "1")
    assert r_consult.returncode == 0, "consult (C07) failed:\n" + r_consult.stdout + r_consult.stderr
    result = json.loads(r_consult.stdout)
    assert result["zero_hit"] is False  # known-hit
    knode_ids = [n["id"] for n in result["hits"]["knowledge"]["nodes"]]
    assert "PR-001" in knode_ids
    # C07 が引く source graph が生成物と一致する (チェーンが同一 graph を通っている)
    assert result["sources"]["knowledge_graph"]["edge_count"] == 1


def test_e2e_zero_hit_is_not_error(tmp_path: Path):
    # 反対側: topic 不一致は zero-hit (exit0)。known-hit テストが常に真になっていないことの対照。
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    source_md = tmp_path / "sources" / "kitahara-relationship.md"
    _build_knowledge_fixture(kdir, source_md)
    candidate = tmp_path / "eval-log" / "relations-candidate.json"
    _materialize_c08_candidate(candidate, source_md.name)
    kgraph = kdir / "knowledge-graph.json"
    assert _run(VALIDATE, "--knowledge-dir", str(kdir),
                "--merge-relations", str(candidate), "--graph-out", str(kgraph)).returncode == 0
    _plugin_root, harness_out = _build_harness_fixture(tmp_path)
    r = _run(CONSULT,
             "--topic", "存在しないトピックzzz",
             "--knowledge-graph", str(kgraph),
             "--harness-artifact-graph", str(harness_out),
             "--query-type", "local", "--depth", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["zero_hit"] is True
