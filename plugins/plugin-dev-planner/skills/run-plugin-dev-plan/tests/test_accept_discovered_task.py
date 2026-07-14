"""accept-discovered-task.py (C5) の機能テスト — additive/structural 二段受理・冪等・schema 準拠。

conftest 非依存でローカルロードする (共有 fixture に依存しない自己完結テスト)。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"
sys.path.insert(0, str(SCRIPTS))


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


accept_mod = _load("accept-discovered-task")


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _base_graph() -> dict:
    """有効な producer 形状 graph (全 node が edge に現れ orphan 0・DAG・canonical)。

    drain の fail-closed validate ゲート (MD-2) を通過する現実的 fixture。phase root P01 を
    node として含め parent_of で全 task を連結する (derive-task-graph の実出力形状)。
    """
    dtg = _load("derive-task-graph")
    return dtg.canonicalize({
        "schema_version": "1.0",
        "nodes": [
            {"id": "P01", "title": "P01", "phase_ref": "P01", "entity_ref": None,
             "state": "pending", "write_scope": ""},
            {"id": "T1", "title": "T1", "phase_ref": "P01", "entity_ref": None,
             "state": "pending", "write_scope": "T1"},
            {"id": "T2", "title": "T2", "phase_ref": "P01", "entity_ref": None,
             "state": "pending", "write_scope": "T2"},
        ],
        "edges": [
            {"type": "parent_of", "from": "P01", "to": "T1"},
            {"type": "parent_of", "from": "P01", "to": "T2"},
        ],
    })


def _proposed_node(node_id: str = "T9") -> dict:
    return {
        "id": node_id, "title": f"{node_id} title", "phase_ref": "P02",
        "entity_ref": None, "state": "pending", "write_scope": node_id,
    }


def _form(change_level: str = "additive", discovering: str = "T1", node_id: str = "T9",
          with_provenance: bool = False) -> dict:
    form = {
        "discovering_task_id": discovering,
        "reason": "plan 未網羅タスクを発見した",
        "discovered_at_artifact": "eval-log/x/build/route-1.json",
        "proposed_node": _proposed_node(node_id),
        "change_level": change_level,
    }
    if with_provenance:
        form["provenance"] = {"route_id": "route-1"}
    return form


def _write(path: Path, obj: dict) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


# ─────────────────────────── accept() 単体 ───────────────────────────
def test_additive_adds_node_and_canonicalizes():
    graph = _base_graph()
    out = accept_mod.accept(_form("additive"), graph)
    ids = [n["id"] for n in out["nodes"]]
    assert "T9" in ids
    # canonical = id 昇順
    assert ids == sorted(ids)
    # 入力 graph を破壊していない (浅いコピー)
    assert "T9" not in [n["id"] for n in graph["nodes"]]


def test_additive_is_idempotent():
    graph = _base_graph()
    once = accept_mod.accept(_form("additive"), graph)
    twice = accept_mod.accept(_form("additive"), once)
    t9_count = sum(1 for n in twice["nodes"] if n["id"] == "T9")
    assert t9_count == 1
    # 冪等: 2 回目の出力は 1 回目と一致
    assert once == twice


def test_missing_required_field_raises_valueerror():
    form = _form("additive")
    del form["reason"]
    with pytest.raises(ValueError):
        accept_mod.accept(form, _base_graph())


def test_spec_gap_upstream_adds_no_reverse_edge_and_stays_acyclic():
    """F4: proposed が discovering の *上流* (既存 {from=discovering,to=proposed} の dangling が
    spec-gap 停滞していた) 場合、逆向き辺を張らず 2-循環を作らない (drain 自動受理が可能)。"""
    vtg = _load("validate-task-graph")
    graph = accept_mod._dtg.canonicalize({
        "schema_version": "1.0",
        "nodes": [
            {"id": "P01", "title": "P01", "phase_ref": "P01", "entity_ref": None,
             "state": "pending", "write_scope": ""},
            {"id": "T1", "title": "T1", "phase_ref": "P01", "entity_ref": None,
             "state": "pending", "write_scope": "T1"},
        ],
        "edges": [
            {"type": "parent_of", "from": "P01", "to": "T1"},
            {"type": "depends_on", "from": "T1", "to": "Tgap"},  # Tgap 不在 = spec-gap dangling
        ],
    })
    form = {
        "discovering_task_id": "T1",
        "reason": "spec-gap: 欠落上流 Tgap を追加",
        "discovered_at_artifact": "eval-log/x/build/route-1.json",
        "proposed_node": {"id": "Tgap", "title": "gap", "phase_ref": "P01", "entity_ref": None,
                          "state": "pending", "write_scope": "Tgap"},
        "change_level": "structural",
    }
    out = accept_mod.accept(form, graph, approved=True)
    assert "Tgap" in [n["id"] for n in out["nodes"]]
    # 逆向き辺は張られない (循環回避)
    assert {"type": "depends_on", "from": "Tgap", "to": "T1"} not in out["edges"]
    # 既存の依存方向は保持され Tgap 追加で dangling 解消
    assert {"type": "depends_on", "from": "T1", "to": "Tgap"} in out["edges"]
    # 循環なし・dangling なしで valid (drain の fail-closed ゲートを通過できる)
    assert vtg.validate(out, {}) == []


def test_additive_downstream_still_adds_default_follow_up_edge():
    """additive follow-up (proposed が discovering の下流) は従来どおり {from=proposed,to=discovering}。"""
    graph = _base_graph()
    out = accept_mod.accept(_form("additive", discovering="T1", node_id="T9"), graph)
    assert {"type": "depends_on", "from": "T9", "to": "T1"} in out["edges"]


def _couple_graph():
    dtg = _load("derive-task-graph")
    return dtg.canonicalize({
        "schema_version": "1.0",
        "nodes": [
            {"id": "P02", "title": "P02", "phase_ref": "P02", "entity_ref": None,
             "state": "pending", "write_scope": ""},
            {"id": "T0", "title": "T0", "phase_ref": "P02", "entity_ref": None,
             "state": "pending", "write_scope": "T0"},
            {"id": "P02-C05-01", "title": "C05", "phase_ref": "P02", "entity_ref": "C05",
             "state": "running", "write_scope": "x"},
        ],
        "edges": [
            {"type": "parent_of", "from": "P02", "to": "T0"},
            {"type": "parent_of", "from": "P02", "to": "P02-C05-01"},
        ],
    })


def test_additive_couples_with_serializes_after_existing_sibling():
    # 外ループ追記でも盲目並列を防ぐ: proposed_node.couples_with の同一 phase 既存兄弟 (C05) の
    # *後* へ直列化 (from=新ノード to=兄弟)。新ノードは leaf ゆえ cycle を作らない。
    vtg = _load("validate-task-graph")
    graph = _couple_graph()
    proposed = {"id": "P02-C06-01", "title": "C06", "phase_ref": "P02", "entity_ref": "C06",
                "state": "pending", "write_scope": "y", "couples_with": ["C05"]}
    form = {"discovering_task_id": "T0", "reason": "接合が密な新タスクを発見",
            "discovered_at_artifact": "x", "proposed_node": proposed, "change_level": "additive"}
    out = accept_mod.accept(form, graph)
    assert {"type": "depends_on", "from": "P02-C06-01", "to": "P02-C05-01"} in out["edges"]  # 兄弟の後へ直列化
    assert {"type": "depends_on", "from": "P02-C06-01", "to": "T0"} in out["edges"]           # discovering auto-edge も維持
    assert vtg._check_dag(out["edges"]) == []                                                 # cycle なし


def test_additive_couples_with_only_same_phase_sibling():
    # couples_with 対象兄弟が別 phase なら直列化しない (同一 phase のみ・盲目並列 risk は同一 phase)。
    dtg = _load("derive-task-graph")
    graph = dtg.canonicalize({
        "schema_version": "1.0",
        "nodes": [
            {"id": "P01", "title": "P01", "phase_ref": "P01", "entity_ref": None,
             "state": "pending", "write_scope": ""},
            {"id": "P01-C05-01", "title": "C05", "phase_ref": "P01", "entity_ref": "C05",
             "state": "done", "write_scope": "x"},
        ],
        "edges": [{"type": "parent_of", "from": "P01", "to": "P01-C05-01"}],
    })
    proposed = {"id": "P02-C06-01", "title": "C06", "phase_ref": "P02", "entity_ref": "C06",
                "state": "pending", "write_scope": "y", "couples_with": ["C05"]}
    form = {"discovering_task_id": "P01-C05-01", "reason": "x", "discovered_at_artifact": "x",
            "proposed_node": proposed, "change_level": "additive"}
    out = accept_mod.accept(form, graph)
    # C05 は P01・proposed は P02 ゆえ coupling 直列化は張らない (phase 順序が担う)。
    assert {"type": "depends_on", "from": "P02-C06-01", "to": "P01-C05-01"} in out["edges"]  # これは discovering auto-edge
    # 追加の coupling edge は 1 本のみ (discovering) で、兄弟専用の別 edge は無い
    dep_to_c05 = [e for e in out["edges"] if e["type"] == "depends_on" and e["to"] == "P01-C05-01"]
    assert len(dep_to_c05) == 1


def test_discovering_task_id_absent_raises_valueerror():
    form = _form("additive", discovering="ZZZ")
    with pytest.raises(ValueError):
        accept_mod.accept(form, _base_graph())


def test_invalid_change_level_raises_valueerror():
    form = _form("additive")
    form["change_level"] = "bogus"
    with pytest.raises(ValueError):
        accept_mod.accept(form, _base_graph())


def test_structural_unapproved_raises_permissionerror():
    with pytest.raises(PermissionError):
        accept_mod.accept(_form("structural"), _base_graph(), approved=False)


def test_structural_approved_succeeds():
    out = accept_mod.accept(_form("structural"), _base_graph(), approved=True)
    assert "T9" in [n["id"] for n in out["nodes"]]


def test_provenance_is_optional_and_accepted():
    out = accept_mod.accept(_form("additive", with_provenance=True), _base_graph())
    assert "T9" in [n["id"] for n in out["nodes"]]


# ─────────────────────── schema 準拠 (positive fixture) ───────────────────────
def test_form_satisfies_discovered_task_schema_required_keys():
    schema = json.loads((SCHEMAS / "discovered-task.schema.json").read_text(encoding="utf-8"))
    form = _form("additive", with_provenance=True)
    for key in schema["required"]:
        assert key in form, key
    # proposed_node の必須キーも満たす
    node_required = schema["properties"]["proposed_node"]["required"]
    for key in node_required:
        assert key in form["proposed_node"], key
    # discovered_at_artifact は top-level (provenance へネストしない)
    assert "discovered_at_artifact" in form
    assert "discovered_at_artifact" not in form["provenance"]


# ─────────────────────────── main() / CLI ───────────────────────────
def test_cli_additive_writes_and_exit0(tmp_path, capsys):
    form_p = _write(tmp_path / "form.json", _form("additive"))
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    out_p = tmp_path / "out.json"
    rc = accept_mod.main(["--form", str(form_p), "--graph", str(graph_p), "-o", str(out_p)])
    assert rc == 0
    written = json.loads(out_p.read_text(encoding="utf-8"))
    assert "T9" in [n["id"] for n in written["nodes"]]
    # 末尾 newline を付けて書き込む
    assert out_p.read_text(encoding="utf-8").endswith("\n")
    summary = json.loads(capsys.readouterr().out)
    assert summary["accepted"] is True
    assert summary["added_node"] == "T9"


def test_cli_default_out_overwrites_graph(tmp_path):
    form_p = _write(tmp_path / "form.json", _form("additive"))
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--form", str(form_p), "--graph", str(graph_p)])
    assert rc == 0
    written = json.loads(graph_p.read_text(encoding="utf-8"))
    assert "T9" in [n["id"] for n in written["nodes"]]


def test_cli_structural_unapproved_exit1(tmp_path, capsys):
    form_p = _write(tmp_path / "form.json", _form("structural"))
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--form", str(form_p), "--graph", str(graph_p)])
    assert rc == 1
    assert "rejected" in capsys.readouterr().err


def test_cli_structural_approved_exit0(tmp_path):
    form_p = _write(tmp_path / "form.json", _form("structural"))
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--form", str(form_p), "--graph", str(graph_p), "--approved"])
    assert rc == 0
    assert "T9" in [n["id"] for n in json.loads(graph_p.read_text(encoding="utf-8"))["nodes"]]


def test_cli_discovering_absent_exit1(tmp_path):
    form_p = _write(tmp_path / "form.json", _form("additive", discovering="ZZZ"))
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--form", str(form_p), "--graph", str(graph_p)])
    assert rc == 1


def test_cli_missing_required_exit1(tmp_path):
    form = _form("additive")
    del form["proposed_node"]
    form_p = _write(tmp_path / "form.json", form)
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--form", str(form_p), "--graph", str(graph_p)])
    assert rc == 1


def test_cli_missing_arg_usage_exit2():
    assert accept_mod.main(["--graph", "x.json"]) == 2  # --form 欠落


def test_cli_bad_path_exit2(tmp_path):
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--form", str(tmp_path / "nope.json"), "--graph", str(graph_p)])
    assert rc == 2


def test_cli_form_and_inbox_mutually_exclusive_exit2(tmp_path):
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    form_p = _write(tmp_path / "form.json", _form("additive"))
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    # --form と --inbox の同時指定は argparse が排他エラー → exit2
    rc = accept_mod.main(["--form", str(form_p), "--inbox", str(inbox), "--graph", str(graph_p)])
    assert rc == 2


# ─────────────────────── drain_inbox() 外ループ入口 (FC-6 帰路) ───────────────────────
def _inbox(tmp_path) -> Path:
    d = tmp_path / "discovered-tasks"
    d.mkdir()
    return d


def test_drain_additive_accepts_and_writes_status_back(tmp_path):
    inbox = _inbox(tmp_path)
    f = _write(inbox / "a.json", _form("additive", node_id="T9"))
    graph, results = accept_mod.drain_inbox(inbox, _base_graph())
    assert "T9" in [n["id"] for n in graph["nodes"]]
    assert results["accepted"] == [{"form": "a.json", "node": "T9"}]
    # form へ status=accepted + resulting_graph_hash が書き戻る
    written = json.loads(f.read_text(encoding="utf-8"))
    assert written["status"] == "accepted"
    assert written["resulting_graph_hash"].startswith("sha256:")


def test_drain_structural_unapproved_needs_approval_stays_pending(tmp_path):
    inbox = _inbox(tmp_path)
    f = _write(inbox / "s.json", _form("structural", node_id="T9"))
    graph, results = accept_mod.drain_inbox(inbox, _base_graph(), approved=False)
    # graph は未変更・needs_approval に計上・status は書き戻さない (pending 据置で C08 block 継続)
    assert "T9" not in [n["id"] for n in graph["nodes"]]
    assert results["needs_approval"] == [{"form": "s.json", "node": "T9"}]
    assert "status" not in json.loads(f.read_text(encoding="utf-8"))


def test_drain_structural_approved_accepts(tmp_path):
    inbox = _inbox(tmp_path)
    _write(inbox / "s.json", _form("structural", node_id="T9"))
    graph, results = accept_mod.drain_inbox(inbox, _base_graph(), approved=True)
    assert "T9" in [n["id"] for n in graph["nodes"]]
    assert len(results["accepted"]) == 1


def test_drain_target_shape_rejects_incomplete_discovered_leaf(tmp_path):
    """Target-shape validation must not silently downgrade to legacy shape."""
    inbox = _inbox(tmp_path)
    _write(inbox / "s.json", _form("structural", discovering="T1", node_id="T9"))
    graph = accept_mod._dtg.canonicalize({
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "P01", "title": "P01", "phase_ref": "P01", "entity_ref": None,
                "state": "pending", "write_scope": "", "execution_kind": "phase-gate",
                "route_ref": None, "task_spec_ref": None,
            },
            {
                "id": "T1", "title": "T1", "phase_ref": "P01", "entity_ref": None,
                "state": "pending", "write_scope": "out/T1.json",
                "acceptance_criterion": "T1 passes", "execution_kind": "direct-task",
                "route_ref": None, "task_spec_ref": "task-specs/T1.md",
            },
        ],
        "edges": [
            {"type": "parent_of", "from": "P01", "to": "T1"},
            {"type": "produces", "from": "T1", "to": "out/T1.json"},
        ],
    })

    unchanged, results = accept_mod.drain_inbox(inbox, graph, approved=True)

    assert unchanged == graph
    assert results["accepted"] == []
    assert results["validation_failed"]
    assert any("executable leaf T9" in finding for finding in results["validation_failed"])
    assert results["needs_approval"][0]["reason"] == "graph validation failed"


def test_drain_skips_already_processed(tmp_path):
    inbox = _inbox(tmp_path)
    done = _form("additive", node_id="T9")
    done["status"] = "accepted"
    f = _write(inbox / "done.json", done)
    graph, results = accept_mod.drain_inbox(inbox, _base_graph())
    assert "T9" not in [n["id"] for n in graph["nodes"]]  # 再受理しない
    assert results["skipped"] == [{"form": "done.json", "status": "accepted"}]


def test_drain_invalid_form_rejected_and_written_back(tmp_path):
    inbox = _inbox(tmp_path)
    bad = _form("additive", discovering="ZZZ", node_id="T9")  # discovering_task_id 不在
    f = _write(inbox / "bad.json", bad)
    graph, results = accept_mod.drain_inbox(inbox, _base_graph())
    assert "T9" not in [n["id"] for n in graph["nodes"]]
    assert len(results["rejected"]) == 1
    written = json.loads(f.read_text(encoding="utf-8"))
    assert written["status"] == "rejected"
    assert "rejected_reason" in written


def test_drain_multiple_additive_accumulate_deterministic_order(tmp_path):
    inbox = _inbox(tmp_path)
    _write(inbox / "b.json", _form("additive", node_id="T8"))
    _write(inbox / "a.json", _form("additive", node_id="T9"))
    graph, results = accept_mod.drain_inbox(inbox, _base_graph())
    ids = [n["id"] for n in graph["nodes"]]
    assert "T8" in ids and "T9" in ids
    # filename 昇順で処理 (a.json → b.json)
    assert [r["form"] for r in results["accepted"]] == ["a.json", "b.json"]


def test_cli_inbox_exit0_even_with_needs_approval(tmp_path, capsys):
    inbox = _inbox(tmp_path)
    _write(inbox / "add.json", _form("additive", node_id="T9"))
    _write(inbox / "struct.json", _form("structural", node_id="T8"))
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--inbox", str(inbox), "--graph", str(graph_p)])
    assert rc == 0  # ドレイン正常完了 (needs_approval 残存は exit0・C08 が別途 block)
    summary = json.loads(capsys.readouterr().out)
    assert summary["mode"] == "inbox"
    assert len(summary["accepted"]) == 1
    assert len(summary["needs_approval"]) == 1
    assert summary["graph_hash"].startswith("sha256:")
    # graph へ additive のみ反映
    written = json.loads(graph_p.read_text(encoding="utf-8"))
    assert "T9" in [n["id"] for n in written["nodes"]]
    assert "T8" not in [n["id"] for n in written["nodes"]]


def test_cli_inbox_missing_dir_exit2(tmp_path):
    graph_p = _write(tmp_path / "graph.json", _base_graph())
    rc = accept_mod.main(["--inbox", str(tmp_path / "nope"), "--graph", str(graph_p)])
    assert rc == 2


def test_accept_wires_depends_on_edge_no_orphan(tmp_path):
    """MD-2: additive accept は新ノードに depends_on(新→discovering) を自動配線し孤立させない。"""
    vtg = _load("validate-task-graph")
    out = accept_mod.accept(_form("additive", discovering="T1", node_id="T9"), _base_graph())
    dep = {"type": "depends_on", "from": "T9", "to": "T1"}
    assert dep in out["edges"]
    # producer validate-task-graph の orphan-0 不変条件を破らない
    assert vtg.validate(out, {}) == []


def test_drain_stamps_uniform_final_hash(tmp_path):
    """MD-8: 複数 additive 受理時、全 accepted form の resulting_graph_hash は *最終* graph_hash で統一。"""
    inbox = _inbox(tmp_path)
    fa = _write(inbox / "a.json", _form("additive", node_id="T8"))
    fb = _write(inbox / "b.json", _form("additive", node_id="T9"))
    graph, results = accept_mod.drain_inbox(inbox, _base_graph())
    final_hash = accept_mod._dtg.graph_hash(graph)
    ha = json.loads(fa.read_text())["resulting_graph_hash"]
    hb = json.loads(fb.read_text())["resulting_graph_hash"]
    # 先に処理された a.json も中間 hash でなく最終 hash を焼く (C07 再 pin 認可述語の突合可能性)
    assert ha == hb == final_hash


def test_drain_validate_gate_rejects_invalid_graph(tmp_path):
    """MD-2: drain の最終 graph が不変条件を破るなら graph も status も一切コミットしない (fail-closed)。"""
    # 事前に orphan を含む不正 base graph (T_orphan がどの edge にも現れない)
    bad_base = _base_graph()
    bad_base["nodes"].append({"id": "T_orphan", "title": "orphan", "phase_ref": "P01",
                              "entity_ref": None, "state": "pending", "write_scope": "x"})
    bad_base = _load("derive-task-graph").canonicalize(bad_base)
    inbox = _inbox(tmp_path)
    f = _write(inbox / "a.json", _form("additive", node_id="T9"))
    graph, results = accept_mod.drain_inbox(inbox, bad_base)
    # validation_failed で accepted は空・graph は元のまま (T9 未反映)・form status 未書戻し
    assert results.get("validation_failed")
    assert results["accepted"] == []
    assert "T9" not in [n["id"] for n in graph["nodes"]]
    assert "status" not in json.loads(f.read_text())


def test_diff_proposed_vs_existing_unit():
    """B1: 既存不在=None / 同一=[] / 差分=フィールド名昇順 list。"""
    graph = _base_graph()
    assert accept_mod.diff_proposed_vs_existing(_proposed_node("T9"), graph) is None
    same = next(n for n in graph["nodes"] if n["id"] == "T1")
    assert accept_mod.diff_proposed_vs_existing(dict(same), graph) == []
    changed = dict(same)
    changed["title"] = "T1 改題"
    changed["acceptance_criterion"] = "新規追加の受入基準"
    diff = accept_mod.diff_proposed_vs_existing(changed, graph)
    assert diff == ["acceptance_criterion", "title"]


def test_drain_idempotent_skip_with_field_diff_writes_reflected_partial(tmp_path):
    """B1: 冪等 skip (id 既存) で field 差分あり → form へ reflected=partial+差分一覧を書き戻し graph は不変。"""
    base = _base_graph()
    base_hash = accept_mod._dtg.graph_hash(base)
    inbox = _inbox(tmp_path)
    form = _form("additive", discovering="T2", node_id="T1")  # T1 は既存 (title/phase_ref が異なる)
    f = _write(inbox / "re-emit.json", form)
    graph, results = accept_mod.drain_inbox(inbox, base)
    # graph は無追加・bytes/hash 不変 (冪等 skip)
    assert accept_mod._dtg.graph_hash(graph) == base_hash
    written = json.loads(f.read_text(encoding="utf-8"))
    assert written["status"] == "accepted"
    assert written["reflected"] == "partial"
    assert written["reflected_diff_fields"] == sorted(written["reflected_diff_fields"])
    assert "title" in written["reflected_diff_fields"]
    assert results["accepted"][0]["reflected"] == "partial"
    # schema 妥当性: 書き戻し後 form が additionalProperties:false 下で許可キーのみ
    schema = json.loads((SCHEMAS / "discovered-task.schema.json").read_text(encoding="utf-8"))
    assert set(written.keys()) <= set(schema["properties"].keys())


def test_drain_idempotent_skip_without_diff_no_reflected(tmp_path):
    """B1: 冪等 skip でも field 差分なしなら reflected は書かない (ノイズ抑制)。"""
    base = _base_graph()
    inbox = _inbox(tmp_path)
    form = _form("additive", discovering="T2", node_id="T1")
    form["proposed_node"] = dict(next(n for n in base["nodes"] if n["id"] == "T1"))  # 完全同一
    f = _write(inbox / "same.json", form)
    _graph, results = accept_mod.drain_inbox(inbox, base)
    written = json.loads(f.read_text(encoding="utf-8"))
    assert written["status"] == "accepted"
    assert "reflected" not in written and "reflected_diff_fields" not in written
    assert "reflected" not in results["accepted"][0]


def test_drain_written_back_form_stays_schema_valid(tmp_path):
    """status/resulting_graph_hash が discovered-task.schema.json の additive field として妥当。"""
    schema = json.loads((SCHEMAS / "discovered-task.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    assert "status" in props and props["status"]["enum"] == ["pending", "accepted", "rejected", "superseded"]
    assert "resulting_graph_hash" in props
    assert schema["additionalProperties"] is False
    # 書き戻し後の form が additionalProperties:false 下で許可キーのみを持つ
    inbox = _inbox(tmp_path)
    f = _write(inbox / "a.json", _form("additive", node_id="T9", with_provenance=True))
    accept_mod.drain_inbox(inbox, _base_graph())
    written = json.loads(f.read_text(encoding="utf-8"))
    allowed = set(props.keys())
    assert set(written.keys()) <= allowed, set(written.keys()) - allowed
