"""ENG-C07 record-capability-graph-knowledge.py の genuine 機能テスト (H6 実装)。

ENG-C06 graph + discovered task を Loop A/B knowledge へ source_ref 付きで append/merge (既存不変)。

カバー分岐:
- _slug: 非英数を - へ正規化・切詰
- build_entries: summary entry / gap entry / discovered task entry / 各 entry の source_ref + 6必須
- merge_into_store: 新規作成 / append / id 既存 skip (既存 entry 不変) / dry-run で非書込
- main(CLI): Loop A のみ / Loop A+B / discovered-json / 不正 graph JSON exit2 / 不正 discovered exit2

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
    / "templates/task-graph-engine/scripts/record-capability-graph-knowledge.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("record_capability_graph_knowledge", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()

GRAPH = {
    "nodes": [{"id": "skill:run-a", "kind": "skill", "path": "a"}],
    "edges": [{"from": "skill:run-a", "to": "script:h.py", "type": "script-call", "source_ref": "a"}],
    "gaps": [{"from": "skill:run-a", "ref": "skill:ghost", "type": "skill-invoke", "source_ref": "a"}],
}


def _write_graph(tmp_path, graph=GRAPH):
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(graph), encoding="utf-8")
    return p


def _run(graph_path, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(graph_path), *args],
                          capture_output=True, text=True)


# --- _slug ---
def test_slug_normalizes():
    assert mod._slug("Skill:Run-A/Ghost") == "skill-run-a-ghost"


# --- build_entries ---
def test_build_entries_has_summary_gap_and_refs():
    entries = mod.build_entries(GRAPH, "graph.json", [])
    ids = {e["id"] for e in entries}
    assert "cdg-summary" in ids
    assert any(i.startswith("cdg-gap-") for i in ids)
    for e in entries:
        assert e["source_ref"]  # 全 entry が source_ref を持つ
        for req in ("id", "title", "intent", "background", "keywords", "source"):
            assert req in e  # 6必須 (knowledge-loop schema 準拠)


def test_build_entries_discovered_task():
    entries = mod.build_entries(GRAPH, "g", [{"id": "C9", "text": "未網羅"}])
    assert any(e["id"] == "cdg-task-c9" for e in entries)


def test_build_entries_sorted():
    entries = mod.build_entries(GRAPH, "g", [])
    ids = [e["id"] for e in entries]
    assert ids == sorted(ids)


# --- merge_into_store ---
def test_merge_creates_and_appends(tmp_path):
    entries = mod.build_entries(GRAPH, "g", [])
    kdir = tmp_path / "knowA"
    res = mod.merge_into_store(kdir, entries, dry_run=False)
    assert res["added"] and (kdir / "knowledge-capability-graph.json").exists()


def test_merge_idempotent_skip(tmp_path):
    entries = mod.build_entries(GRAPH, "g", [])
    kdir = tmp_path / "knowA"
    mod.merge_into_store(kdir, entries, dry_run=False)
    res2 = mod.merge_into_store(kdir, entries, dry_run=False)
    assert res2["added"] == [] and set(res2["skipped"]) == {e["id"] for e in entries}


def test_merge_preserves_existing(tmp_path):
    kdir = tmp_path / "knowA"
    kdir.mkdir()
    store = kdir / "knowledge-capability-graph.json"
    store.write_text(json.dumps({"items": [{"id": "cdg-summary", "custom": "keep"}]}), encoding="utf-8")
    entries = mod.build_entries(GRAPH, "g", [])
    mod.merge_into_store(kdir, entries, dry_run=False)
    data = json.loads(store.read_text())
    existing = [i for i in data["items"] if i["id"] == "cdg-summary"]
    assert existing[0].get("custom") == "keep"  # 既存 entry を上書きしない


def test_merge_dry_run_no_write(tmp_path):
    entries = mod.build_entries(GRAPH, "g", [])
    kdir = tmp_path / "knowA"
    mod.merge_into_store(kdir, entries, dry_run=True)
    assert not (kdir / "knowledge-capability-graph.json").exists()
    assert not (kdir / "knowledge-index.json").exists()


def test_merge_registers_category_in_index(tmp_path):
    # 記録済み knowledge が index-search consult から発見可能になる (category 登録)
    entries = mod.build_entries(GRAPH, "g", [])
    kdir = tmp_path / "knowA"
    res = mod.merge_into_store(kdir, entries, dry_run=False)
    assert res["category_registered"] is True
    index = json.loads((kdir / "knowledge-index.json").read_text())
    cats = {c["id"] for c in index["categories"]}
    assert "capability-graph" in cats


def test_index_registration_idempotent(tmp_path):
    entries = mod.build_entries(GRAPH, "g", [])
    kdir = tmp_path / "knowA"
    mod.merge_into_store(kdir, entries, dry_run=False)
    res2 = mod.merge_into_store(kdir, entries, dry_run=False)
    assert res2["category_registered"] is False  # 既登録なら no-op
    index = json.loads((kdir / "knowledge-index.json").read_text())
    assert len([c for c in index["categories"] if c["id"] == "capability-graph"]) == 1


# --- main CLI ---
def test_main_loop_a_only(tmp_path):
    gp = _write_graph(tmp_path)
    kdir = tmp_path / "knowA"
    r = _run(gp, "--target-knowledge-dir", str(kdir))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["loop_a_status"]["added"] and out["loop_b_status"] is None


def test_main_loop_a_and_b(tmp_path):
    gp = _write_graph(tmp_path)
    r = _run(gp, "--target-knowledge-dir", str(tmp_path / "A"),
             "--harness-knowledge-dir", str(tmp_path / "B"))
    out = json.loads(r.stdout)
    assert out["loop_b_status"]["added"]


def test_main_discovered_json(tmp_path):
    gp = _write_graph(tmp_path)
    dj = tmp_path / "disc.json"
    dj.write_text(json.dumps([{"id": "C9", "text": "t"}]), encoding="utf-8")
    r = _run(gp, "--target-knowledge-dir", str(tmp_path / "A"), "--discovered-json", str(dj))
    out = json.loads(r.stdout)
    assert any(e["id"] == "cdg-task-c9" for e in out["entries"])


def test_main_bad_graph_exit2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{broken", encoding="utf-8")
    r = _run(p, "--target-knowledge-dir", str(tmp_path / "A"))
    assert r.returncode == 2


def test_main_bad_discovered_exit2(tmp_path):
    gp = _write_graph(tmp_path)
    dj = tmp_path / "disc.json"
    dj.write_text(json.dumps({"not": "list"}), encoding="utf-8")
    r = _run(gp, "--target-knowledge-dir", str(tmp_path / "A"), "--discovered-json", str(dj))
    assert r.returncode == 2
