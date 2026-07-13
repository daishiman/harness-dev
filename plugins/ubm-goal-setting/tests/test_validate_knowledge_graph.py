"""validate-knowledge-graph.py (C06) の決定論再生成 + 検証ゲート挙動テスト。

self-loop・depends_on 循環・evidence 欠落・confidence 範囲外・review_status 欠落を exit1、
正しい non-zero fixture を exit0 にし、同一入力で byte-identical な graph を生成することを
検証する。dangling (endpoint 不在) は hard-fail でなく knowledge-relations-quarantine.json への
冪等退避 + WARN の縮退 (exit0)。edges=0 の退化グラフは exit0 のまま stderr WARN で表面化する。
fixture は tmp_path 内で自作し実 knowledge/ を汚さない。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/validate-knowledge-graph.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def make_entry_file(kdir: Path, name: str, category: str, entries: list[dict]) -> None:
    write_json(kdir / name, {"category": category, "subcategory": "sub", "entries": entries})


def base_knowledge(tmp_path: Path) -> Path:
    """3 entry・related 連想付きの正常 knowledge-dir を作る。"""
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    make_entry_file(kdir, "principles.json", "principles", [
        {"id": "PR-001", "title": "原則1", "related": ["MS-001"]},
        {"id": "PR-002", "title": "原則2", "related": []},
    ])
    make_entry_file(kdir, "mindset.json", "mindset", [
        {"id": "MS-001", "title": "マインド1", "related": ["PR-001"]},
    ])
    return kdir


def valid_edge(src: str, tgt: str, rel: str = "depends_on") -> dict:
    return {
        "source_id": src,
        "target_id": tgt,
        "relation_type": rel,
        "evidence": ["逐語引用の根拠テキスト"],
        "source_ref": f"{src}:a.json / {tgt}:b.json",
        "confidence": 0.8,
        "review_status": "pending_review",
    }


def write_relations(kdir: Path, edges: list[dict], container: str = "edges") -> None:
    write_json(kdir / "knowledge-relations.json", {container: edges})


# ---- 正常系 ------------------------------------------------------------

def test_valid_nonzero_fixture_exit0(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001"), valid_edge("MS-001", "PR-001", "supports")])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK: knowledge-graph validated" in r.stdout
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["node_count"] == 3
    assert graph["edge_count"] == 2
    # related 連想 (PR-001<->MS-001) が無方向1件に畳まれる
    assert graph["association_count"] == 1
    assert graph["associations"][0] == {"a": "MS-001", "b": "PR-001", "kind": "related"}


def test_relations_absent_empty_graph_exit0(tmp_path: Path):
    kdir = base_knowledge(tmp_path)  # relations ファイル無し
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "空辺として扱った" in r.stdout
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["edge_count"] == 0
    assert graph["node_count"] == 3


def test_edges_zero_degenerate_graph_warns_on_stderr_exit0(tmp_path: Path):
    # 退化グラフ (edges=0) は exit0 のまま stderr WARN で表面化する (JSON/graph 出力は不変)。
    kdir = base_knowledge(tmp_path)  # relations 無し → edges=0
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARN" in r.stderr and "edges=0" in r.stderr


def test_edges_nonzero_no_degenerate_warn(tmp_path: Path):
    # 辺が載っていれば edges=0 WARN は出ない (誤検知しない)。
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001")])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARN" not in r.stderr


def test_relations_as_bare_list_accepted(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    write_json(kdir / "knowledge-relations.json", [valid_edge("PR-002", "PR-001")])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["edge_count"] == 1


def test_graph_out_override(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001")])
    out = tmp_path / "custom-graph.json"
    r = run("--knowledge-dir", str(kdir), "--graph-out", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.exists()
    assert not (kdir / "knowledge-graph.json").exists()


# ---- dangling 辺は quarantine 縮退 (hard-fail にしない) -----------------

def test_dangling_edge_quarantined_exit0(tmp_path: Path):
    # endpoint 不在の辺は violation でなく quarantine へ退避し、残辺で graph 生成が継続する。
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001"), valid_edge("PR-002", "PR-999")])  # PR-999 は不在
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARN" in r.stderr and "quarantine" in r.stderr
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["edge_count"] == 1  # 残辺のみで生成
    q = json.loads((kdir / "knowledge-relations-quarantine.json").read_text(encoding="utf-8"))
    assert [e["target_id"] for e in q["edges"]] == ["PR-999"]
    # quarantine された辺は knowledge-relations.json から除去される
    relations = json.loads((kdir / "knowledge-relations.json").read_text(encoding="utf-8"))
    assert [e["target_id"] for e in relations["edges"]] == ["PR-001"]


def test_entry_deletion_moves_edge_to_quarantine_and_regenerates(tmp_path: Path):
    # entry 削除で dangling 化した既存辺が quarantine へ移り、graph 再生成が成功する (恒久ブロック解消)。
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001"), valid_edge("MS-001", "PR-001", "supports")])
    assert run("--knowledge-dir", str(kdir)).returncode == 0
    (kdir / "mindset.json").unlink()  # MS-001 の entry を削除 → MS-001 起点の辺が dangling 化
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1
    q = json.loads((kdir / "knowledge-relations-quarantine.json").read_text(encoding="utf-8"))
    assert [e["source_id"] for e in q["edges"]] == ["MS-001"]


def test_quarantine_idempotent_rerun_byte_identical(tmp_path: Path):
    # quarantine 発生後の再実行は追加退避なしで relations/quarantine/graph とも byte-identical (冪等)。
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-999")])
    r1 = run("--knowledge-dir", str(kdir))
    assert r1.returncode == 0, r1.stdout + r1.stderr
    q1 = (kdir / "knowledge-relations-quarantine.json").read_bytes()
    rel1 = (kdir / "knowledge-relations.json").read_bytes()
    g1 = (kdir / "knowledge-graph.json").read_bytes()
    r2 = run("--knowledge-dir", str(kdir))
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert (kdir / "knowledge-relations-quarantine.json").read_bytes() == q1
    assert (kdir / "knowledge-relations.json").read_bytes() == rel1
    assert (kdir / "knowledge-graph.json").read_bytes() == g1


def test_quarantine_not_written_when_other_violation_fails(tmp_path: Path):
    # dangling (quarantine 対象) と self-loop (violation) の同居 → exit1 で quarantine 含め何も書かない
    # (fail-closed は quarantine 後の残グラフに対して維持される)。
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-999"), valid_edge("PR-001", "PR-001")])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "self-loop" in r.stderr
    assert not (kdir / "knowledge-relations-quarantine.json").exists()
    assert not (kdir / "knowledge-graph.json").exists()


# ---- 違反系 (exit1) ----------------------------------------------------

def test_self_loop_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-001", "PR-001")])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "self-loop" in r.stderr


def test_depends_on_cycle_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [
        valid_edge("PR-001", "PR-002"),
        valid_edge("PR-002", "MS-001"),
        valid_edge("MS-001", "PR-001"),
    ])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "循環検出" in r.stderr


def test_supports_cycle_allowed_exit0(tmp_path: Path):
    # supports は無方向扱いで cycle 対象外 → 相互辺でも OK
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [
        valid_edge("PR-001", "PR-002", "supports"),
        valid_edge("PR-002", "PR-001", "supports"),
    ])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr


def test_missing_evidence_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    e = valid_edge("PR-002", "PR-001")
    e["evidence"] = []
    write_relations(kdir, [e])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "evidence" in r.stderr


def test_confidence_out_of_range_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    e = valid_edge("PR-002", "PR-001")
    e["confidence"] = 1.5
    write_relations(kdir, [e])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "confidence" in r.stderr


def test_missing_review_status_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    e = valid_edge("PR-002", "PR-001")
    del e["review_status"]
    write_relations(kdir, [e])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "review_status" in r.stderr


def test_missing_source_ref_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    e = valid_edge("PR-002", "PR-001")
    del e["source_ref"]
    write_relations(kdir, [e])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "source_ref" in r.stderr


def test_bad_relation_type_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001", "unknown_rel")])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "relation_type" in r.stderr


def test_malformed_relations_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    (kdir / "knowledge-relations.json").write_text("{ not json", encoding="utf-8")
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "relations file" in r.stderr


# ---- dangling related は非致命 -----------------------------------------

def test_dangling_related_dropped_not_fatal(tmp_path: Path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    make_entry_file(kdir, "principles.json", "principles", [
        {"id": "PR-001", "title": "原則1", "related": ["PR-999"]},  # PR-999 は不在
    ])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "related 参照を 1 件 drop" in r.stdout
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["association_count"] == 0


# ---- 決定論 ------------------------------------------------------------

def test_deterministic_byte_identical(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    # 入力順を変えても同一 graph になることも兼ねる
    write_relations(kdir, [
        valid_edge("MS-001", "PR-001", "supports"),
        valid_edge("PR-002", "PR-001"),
    ])
    out1 = tmp_path / "g1.json"
    out2 = tmp_path / "g2.json"
    r1 = run("--knowledge-dir", str(kdir), "--graph-out", str(out1))
    r2 = run("--knowledge-dir", str(kdir), "--graph-out", str(out2))
    assert r1.returncode == 0 and r2.returncode == 0
    assert out1.read_bytes() == out2.read_bytes()


def test_deterministic_input_order_independent(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    edges = [valid_edge("PR-002", "PR-001"), valid_edge("MS-001", "PR-001", "supports")]
    write_relations(kdir, edges)
    r1 = run("--knowledge-dir", str(kdir), "--graph-out", str(tmp_path / "a.json"))
    write_relations(kdir, list(reversed(edges)))
    r2 = run("--knowledge-dir", str(kdir), "--graph-out", str(tmp_path / "b.json"))
    assert r1.returncode == 0 and r2.returncode == 0
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


# ---- --merge-relations (C08 候補の冪等 merge = 永続化 owner) ------------

def write_candidate(path: Path, edges: list[dict], container: str | None = "edges") -> None:
    """C08 が返し呼び出し側が materialize した辺候補ファイルを書く (list か dict どちらでも)。"""
    write_json(path, edges if container is None else {container: edges})


def test_merge_new_edge_persists_and_generates_graph(tmp_path: Path):
    # knowledge-relations.json 不在 + 候補1辺 → merge で relations 永続化 + graph 生成 (一気通貫)。
    kdir = base_knowledge(tmp_path)
    cand = tmp_path / "candidate.json"
    write_candidate(cand, [valid_edge("PR-002", "PR-001")])
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "辺候補を merge した (added=1 kept=0)" in r.stdout
    # 永続ストアが実際に書かれた (S1 反証: C08 出力に永続化 owner が存在する)
    relations = json.loads((kdir / "knowledge-relations.json").read_text(encoding="utf-8"))
    assert len(relations["edges"]) == 1
    # graph も同時に再生成され辺が載る (edge_count>0 = 候補が消費された証拠)
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["edge_count"] == 1


def test_merge_candidate_as_bare_list(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    cand = tmp_path / "candidate.json"
    write_candidate(cand, [valid_edge("PR-002", "PR-001")], container=None)  # bare list 形式
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads((kdir / "knowledge-relations.json").read_text(encoding="utf-8"))["edges"]


def test_merge_idempotent_byte_identical(tmp_path: Path):
    # 同じ候補を二度 merge → knowledge-relations.json も knowledge-graph.json も byte-identical。
    kdir = base_knowledge(tmp_path)
    cand = tmp_path / "candidate.json"
    write_candidate(cand, [valid_edge("PR-002", "PR-001"), valid_edge("MS-001", "PR-001", "supports")])
    r1 = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r1.returncode == 0, r1.stdout + r1.stderr
    rel1 = (kdir / "knowledge-relations.json").read_bytes()
    graph1 = (kdir / "knowledge-graph.json").read_bytes()
    r2 = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "added=0 kept=2" in r2.stdout  # 二度目は新規追加ゼロ (冪等)
    assert (kdir / "knowledge-relations.json").read_bytes() == rel1
    assert (kdir / "knowledge-graph.json").read_bytes() == graph1


def test_merge_appends_only_unknown_key(tmp_path: Path):
    # 既存1辺 + 候補2辺 (うち1辺は既存と同一 key) → 未知の1辺だけ追加される。
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001")])  # 永続ストアに既存1辺
    cand = tmp_path / "candidate.json"
    write_candidate(cand, [
        valid_edge("PR-002", "PR-001"),                 # 既存と同一 key → 保持 (append しない)
        valid_edge("MS-001", "PR-001", "supports"),     # 未知 key → append
    ])
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "added=1 kept=1" in r.stdout
    relations = json.loads((kdir / "knowledge-relations.json").read_text(encoding="utf-8"))
    assert len(relations["edges"]) == 2


def test_merge_preserves_existing_review_status(tmp_path: Path):
    # 既存辺の review_status=approved を、同一 key の候補 (pending_review) で上書きしない (first-write-wins)。
    kdir = base_knowledge(tmp_path)
    approved = valid_edge("PR-002", "PR-001")
    approved["review_status"] = "approved"
    write_relations(kdir, [approved])
    cand = tmp_path / "candidate.json"
    override = valid_edge("PR-002", "PR-001")
    override["review_status"] = "pending_review"
    write_candidate(cand, [override])
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r.returncode == 0, r.stdout + r.stderr
    relations = json.loads((kdir / "knowledge-relations.json").read_text(encoding="utf-8"))
    assert len(relations["edges"]) == 1
    assert relations["edges"][0]["review_status"] == "approved"  # 既存を保持


def test_merge_missing_candidate_file_exit2(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(tmp_path / "nope.json"))
    assert r.returncode == 2
    assert "存在しない" in r.stderr


def test_merge_dangling_candidate_quarantined_not_persisted_in_store(tmp_path: Path):
    # 候補に dangling 辺 → hard-fail せず quarantine へ退避し、正常辺だけが relations/graph へ載る。
    kdir = base_knowledge(tmp_path)
    cand = tmp_path / "candidate.json"
    write_candidate(cand, [valid_edge("PR-002", "PR-001"), valid_edge("PR-002", "PR-999")])  # PR-999 不在
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARN" in r.stderr and "quarantine" in r.stderr
    relations = json.loads((kdir / "knowledge-relations.json").read_text(encoding="utf-8"))
    assert [e["target_id"] for e in relations["edges"]] == ["PR-001"]  # dangling は store に入らない
    q = json.loads((kdir / "knowledge-relations-quarantine.json").read_text(encoding="utf-8"))
    assert [e["target_id"] for e in q["edges"]] == ["PR-999"]
    graph = json.loads((kdir / "knowledge-graph.json").read_text(encoding="utf-8"))
    assert graph["edge_count"] == 1


def test_merge_bad_candidate_leaves_existing_store_untouched(tmp_path: Path):
    # 既存 relations が正常・候補に壊れた辺 → 検証 FAIL でも既存ストアは書き換えられない。
    kdir = base_knowledge(tmp_path)
    write_relations(kdir, [valid_edge("PR-002", "PR-001")])
    before = (kdir / "knowledge-relations.json").read_bytes()
    cand = tmp_path / "candidate.json"
    write_candidate(cand, [valid_edge("PR-001", "PR-001")])  # self-loop
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r.returncode == 1
    assert "self-loop" in r.stderr
    assert (kdir / "knowledge-relations.json").read_bytes() == before  # 既存ストア不変


def test_merge_malformed_candidate_exit1(tmp_path: Path):
    kdir = base_knowledge(tmp_path)
    cand = tmp_path / "candidate.json"
    cand.write_text("{ not json", encoding="utf-8")
    r = run("--knowledge-dir", str(kdir), "--merge-relations", str(cand))
    assert r.returncode == 1
    assert "merge 候補ファイル" in r.stderr


# ---- usage (exit2) -----------------------------------------------------

def test_missing_dir_usage_exit2(tmp_path: Path):
    r = run("--knowledge-dir", str(tmp_path / "nope"))
    assert r.returncode == 2


def test_no_args_usage_exit2():
    r = run()
    assert r.returncode == 2


# ---- 実 knowledge に対する非後退確認 ----------------------------------

def test_real_knowledge_relations_absent_exit0(tmp_path: Path):
    # 実 knowledge/ を relations 無しで検証 → dangling related があっても非致命 exit0。
    # 出力は tmp_path へ逃がし正本 knowledge/ を汚さない。
    real = PLUGIN_ROOT / "knowledge"
    out = tmp_path / "real-graph.json"
    r = run("--knowledge-dir", str(real), "--graph-out", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    graph = json.loads(out.read_text(encoding="utf-8"))
    assert graph["node_count"] == 215  # 実データ entry 総数
