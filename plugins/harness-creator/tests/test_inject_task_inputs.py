"""inject-task-inputs.py (TG-C03) の機能テスト — task-graph consumer 入力解決器。

conftest 非依存で module-level に importlib ロードする (自己完結)。実 producer=plugin-dev-planner
の graph 形状 (成果物パスは producer node.write_scope、edge は depends_on/produces/consumes) と
TG-C02 (sync-task-state.py) が state node へ書く handoff_notes (dict) を平坦化集約する経路で緑化し、
fail-closed の 5 種拒否 (unknown task-id / producer 未 done / artifact producer 不在 /
成果物欠落 / notes 上限超過=schema 由来数値・producer 単位適用) と、正常注入・複数 producer・
consumes artifact 逆引き・非パス
write_scope の F5 skip・依存なし・main() CLI・実 derive-task-graph.py 統合を網羅する。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

# 実 producer=plugin-dev-planner の derive-task-graph.py (統合テスト用)。
PLANNER_SCRIPTS = (
    Path(__file__).resolve().parents[2]
    / "plugin-dev-planner"
    / "skills"
    / "run-plugin-dev-plan"
    / "scripts"
)


def _load(scripts_dir: Path, stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), scripts_dir / f"{stem}.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


iji = _load(SCRIPTS, "inject-task-inputs")


# ─────────────────────────── helpers ───────────────────────────
def _dep(consumer: str, producer: str) -> dict:
    return {"type": "depends_on", "from": consumer, "to": producer}


def _consume(artifact: str, consumer: str) -> dict:
    # canonical consumes: artifact -> consumer task。producer task は produces で逆引きする。
    return {"type": "consumes", "from": artifact, "to": consumer}


def _prod(producer: str, artifact: str) -> dict:
    # forward-compat の produces エッジ (実 producer graph は出さない副経路)。
    return {"type": "produces", "from": producer, "to": artifact}


def _gnode(node_id: str, write_scope: str | None = None) -> dict:
    """実 producer graph 形状の task node (成果物パスは write_scope に持つ)。"""
    node: dict = {"id": node_id, "title": node_id, "phase_ref": "P01",
                  "entity_ref": None, "state": "pending"}
    if write_scope is not None:
        node["write_scope"] = write_scope
    return node


def _graph(*edges: dict, nodes=None) -> dict:
    """graph を組む。実 producer graph は consumer を含む全 task node を持つため、
    依存 edge の from (consumer) が nodes に無ければ bare node で補完する
    (unknown-task-id fail-closed 検査と衝突させない)。"""
    node_list = list(nodes or [])
    ids = {n.get("id") for n in node_list}
    for e in edges:
        endpoint = e.get("from") if e.get("type") == "depends_on" else e.get("to")
        if e.get("type") in ("depends_on", "consumes") and endpoint not in ids:
            node_list.append(_gnode(endpoint))
            ids.add(endpoint)
    return {"schema_version": "1.0", "nodes": node_list, "edges": list(edges)}


def _pstate(state="done", went_well=None, friction_points=None,
            downstream_watchouts=None, notes=None) -> dict:
    """producer の state node (TG-C02 が書く handoff_notes dict を持つ実形状)。"""
    node: dict = {"state": state}
    handoff: dict = {}
    if went_well is not None:
        handoff["went_well"] = went_well
    if friction_points is not None:
        handoff["friction_points"] = friction_points
    if downstream_watchouts is not None:
        handoff["downstream_watchouts"] = downstream_watchouts
    if handoff:
        node["handoff_notes"] = handoff
    if notes is not None:  # 後方互換 flat notes
        node["notes"] = notes
    return node


def _artifact(tmp_path, name: str) -> str:
    p = tmp_path / name
    p.write_text("x", encoding="utf-8")
    return str(p)


# ─────────────────────────── read_notes_bounds (F8 SSOT) ───────────────────────────
def test_read_notes_bounds_from_producer_schema():
    # 平坦化後の件数上限 = Σ per-category maxItems (3+3+3=9)・要素長 = max maxLength (200)。
    max_notes, max_chars = iji.read_notes_bounds(iji.DEFAULT_NOTES_SCHEMA)
    assert (max_notes, max_chars) == (9, 200)


def test_default_notes_schema_path_exists():
    assert Path(iji.DEFAULT_NOTES_SCHEMA).is_file()


# ─────────────────────────── (2) producer 未 done fail-closed ───────────────────────────
def test_producer_pending_rejected(tmp_path):
    art = _artifact(tmp_path, "a.txt")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate(state="pending")}, "T2")
    assert out == {"rejected": True, "reason": "producer T1 not done",
                   "blocking_producer_task_id": "T1"}


def test_producer_running_rejected(tmp_path):
    art = _artifact(tmp_path, "a.txt")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate(state="running")}, "T2")
    assert out["rejected"] is True and out["blocking_producer_task_id"] == "T1"


def test_producer_absent_from_state_rejected(tmp_path):
    # state に登録すら無い producer は done でない → 拒否。
    art = _artifact(tmp_path, "a.txt")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {}, "T2")
    assert out["rejected"] is True and out["blocking_producer_task_id"] == "T1"


def test_first_incomplete_producer_short_circuits(tmp_path):
    # T2 は T1(done, 成果物あり) と TX(pending) に依存。fail-closed は最初の未完了で打ち切る。
    art = _artifact(tmp_path, "a1.txt")
    artx = _artifact(tmp_path, "ax.txt")
    graph = _graph(
        _dep("T2", "T1"), _dep("T2", "TX"),
        nodes=[_gnode("T1", write_scope=art), _gnode("TX", write_scope=artx)],
    )
    out = iji.resolve_inputs(graph, {"T1": _pstate(), "TX": _pstate(state="pending")}, "T2")
    assert out["rejected"] is True and out["blocking_producer_task_id"] == "TX"
    # 成果物欠落理由ではなく not done 理由が優先される。
    assert out["reason"] == "producer TX not done"


# ─────────────────────────── (3) 成果物実在検査 (F5・write_scope) ───────────────────────────
def test_artifact_missing_rejected():
    missing = "/no/such/dir/artifact.json"
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=missing)])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out == {"rejected": True, "reason": "producer artifact missing",
                   "blocking_producer_task_id": "T1", "missing_artifact": missing}


def test_done_but_write_scope_missing_still_rejected(tmp_path):
    # done state は成果物存在の保証にならない (F5: 代理述語に依存しない)。
    art = _artifact(tmp_path, "exists.txt")
    gone = str(tmp_path / "never-created.txt")
    graph = _graph(
        _dep("T3", "T1"), _dep("T3", "T2"),
        nodes=[_gnode("T1", write_scope=art), _gnode("T2", write_scope=gone)],
    )
    out = iji.resolve_inputs(graph, {"T1": _pstate(), "T2": _pstate()}, "T3")
    assert out["rejected"] is True and out["missing_artifact"] == gone
    assert out["blocking_producer_task_id"] == "T2"


# ─────────────────────────── 正常注入 (write_scope 主経路) ───────────────────────────
def test_normal_injection_single_producer(tmp_path):
    art = _artifact(tmp_path, "out.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out == {"injected_inputs": [{"producer_task_id": "T1", "artifact_path": art}],
                   "injected_notes": []}


def test_multiple_producers_all_injected(tmp_path):
    a1 = _artifact(tmp_path, "p1.json")
    a2 = _artifact(tmp_path, "p2.json")
    graph = _graph(
        _dep("T3", "T1"), _dep("T3", "T2"),
        nodes=[_gnode("T1", write_scope=a1), _gnode("T2", write_scope=a2)],
    )
    out = iji.resolve_inputs(graph, {"T1": _pstate(), "T2": _pstate()}, "T3")
    assert out["injected_inputs"] == [
        {"producer_task_id": "T1", "artifact_path": a1},
        {"producer_task_id": "T2", "artifact_path": a2},
    ]


def test_write_scope_and_produces_edge_both_injected(tmp_path):
    # forward-compat: write_scope (主) を先頭に、produces エッジ先 (副) を続けて併用。
    a1 = _artifact(tmp_path, "m1.json")
    a2 = _artifact(tmp_path, "m2.json")
    graph = _graph(_dep("T2", "T1"), _prod("T1", a2), nodes=[_gnode("T1", write_scope=a1)])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out["injected_inputs"] == [
        {"producer_task_id": "T1", "artifact_path": a1},
        {"producer_task_id": "T1", "artifact_path": a2},
    ]


def test_produces_edge_only_forward_compat(tmp_path):
    # write_scope を持たない node でも produces エッジがあれば副経路で注入される。
    a = _artifact(tmp_path, "pe.json")
    graph = _graph(_dep("T2", "T1"), _prod("T1", a), nodes=[_gnode("T1")])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out["injected_inputs"] == [{"producer_task_id": "T1", "artifact_path": a}]


def test_consumes_artifact_resolves_producer_and_injects(tmp_path):
    """consumes artifact→consumer を produces producer→artifact で task へ逆引きする。"""
    # consumes producer 未 done → fail-closed 拒否。
    art = _artifact(tmp_path, "consumed.json")
    graph = _graph(_prod("T1", "A1"), _consume("A1", "T2"),
                   nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate(state="pending")}, "T2")
    assert out["rejected"] is True and out["blocking_producer_task_id"] == "T1"

    # consumes producer done + 成果物実在 → 正常注入 (producer ready-set「consumes 成果物実在」と対称)。
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out == {"injected_inputs": [{"producer_task_id": "T1", "artifact_path": art}],
                   "injected_notes": []}

    # depends_on + consumes 混在は重複排除で 1 producer に束ねられる。
    mixed = _graph(_dep("T2", "T1"), _prod("T1", "A1"), _consume("A1", "T2"),
                   nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(mixed, {"T1": _pstate()}, "T2")
    assert out["injected_inputs"] == [{"producer_task_id": "T1", "artifact_path": art}]


def test_consumes_producer_artifact_missing_rejected():
    # consumes 先の成果物欠落も F5 fail-closed (done の代理述語に依存しない)。
    missing = "/no/such/dir/consumed.json"
    graph = _graph(_prod("T1", "A1"), _consume("A1", "T2"),
                   nodes=[_gnode("T1", write_scope=missing)])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out == {"rejected": True, "reason": "producer artifact missing",
                   "blocking_producer_task_id": "T1", "missing_artifact": missing}


def test_consumes_artifact_without_producer_rejected_fail_closed():
    graph = _graph(_consume("A404", "T2"), nodes=[_gnode("T2")])
    out = iji.resolve_inputs(graph, {}, "T2")
    assert out["rejected"] is True
    assert out["missing_artifact"] == "A404"
    assert "has no producer" in out["reason"]


def test_no_dependencies_yields_empty(tmp_path):
    # depends_on エッジが無い task (node は graph に実在) は注入対象なし・拒否もされない。
    graph = _graph(nodes=[_gnode("T9", write_scope=_artifact(tmp_path, "irrelevant.json")),
                          _gnode("T1")])
    out = iji.resolve_inputs(graph, {}, "T1")
    assert out == {"injected_inputs": [], "injected_notes": []}


# ─────────────────────────── (1) unknown task-id fail-closed ───────────────────────────
def test_unknown_task_id_rejected(tmp_path):
    # nodes に不在の task-id は fail-closed 拒否 (C04 discovering_task_id 検証と同型)。
    graph = _graph(nodes=[_gnode("T1", write_scope=_artifact(tmp_path, "a.txt"))])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "TX")
    assert out["rejected"] is True
    assert "unknown-task-id" in out["reason"] and "TX" in out["reason"]


def test_main_unknown_task_id_exit1(tmp_path, capsys):
    graph = _graph(nodes=[_gnode("T1")])
    gp = _write(tmp_path, "g.json", graph)
    sp = _write(tmp_path, "s.json", {})
    rc = iji.main(["--task-graph", gp, "--task-state", sp, "--task-id", "ZZ"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["rejected"] is True and "unknown-task-id" in payload["reason"]


def test_producer_without_write_scope_injects_nothing():
    # done producer だが write_scope も produces も無い → artifact 無く拒否されず inputs は空。
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1")])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out == {"injected_inputs": [], "injected_notes": []}


def test_non_path_write_scope_skips_artifact_check():
    # 非パス write_scope (plan ノードの id トークン・"/" 非含有) は F5 実在検査の対象外。
    # 成果物なし producer として偽拒否せず notes のみ注入する。
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope="C01")])
    out = iji.resolve_inputs(graph, {"T1": _pstate(went_well=["token ok"])}, "T2")
    assert out == {"injected_inputs": [], "injected_notes": ["token ok"]}


def test_non_path_produces_edge_target_skipped(tmp_path):
    # produces エッジ先の非パス token (artifact node id) も同じ理由で skip し、
    # パス形状の write_scope のみ F5 検査+注入対象になる。
    art = _artifact(tmp_path, "real.json")
    graph = _graph(_dep("T2", "T1"), _prod("T1", "A1"),
                   nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate()}, "T2")
    assert out["injected_inputs"] == [{"producer_task_id": "T1", "artifact_path": art}]


# ─────────────────────────── notes 集約 (handoff_notes 平坦化) ───────────────────────────
def test_handoff_notes_flattened_in_category_order(tmp_path):
    art = _artifact(tmp_path, "h.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    state = {"T1": _pstate(went_well=["w1", "w2"], friction_points=["f1"],
                           downstream_watchouts=["d1"])}
    out = iji.resolve_inputs(graph, state, "T2")
    # 固定カテゴリ順 went_well → friction_points → downstream_watchouts。
    assert out["injected_notes"] == ["w1", "w2", "f1", "d1"]


def test_flat_notes_backward_compat(tmp_path):
    # handoff_notes 不在でも後方互換の flat notes を読む。
    art = _artifact(tmp_path, "h.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate(notes=["legacy1", "legacy2"])}, "T2")
    assert out["injected_notes"] == ["legacy1", "legacy2"]


def test_notes_aggregated_across_producers(tmp_path):
    a1 = _artifact(tmp_path, "a1.json")
    a2 = _artifact(tmp_path, "a2.json")
    graph = _graph(
        _dep("T3", "T1"), _dep("T3", "T2"),
        nodes=[_gnode("T1", write_scope=a1), _gnode("T2", write_scope=a2)],
    )
    state = {"T1": _pstate(went_well=["w1"]), "T2": _pstate(friction_points=["f2"])}
    out = iji.resolve_inputs(graph, state, "T3")
    assert out["injected_notes"] == ["w1", "f2"]


# ─────────────────────────── notes 有界性 (schema 由来数値) ───────────────────────────
def test_notes_at_schema_count_bound_ok(tmp_path):
    # 1 producer が全 3 カテゴリ maxItems まで埋める = 9 件 = 上限ちょうどは許容。
    max_notes, _ = iji.read_notes_bounds(iji.DEFAULT_NOTES_SCHEMA)  # == 9
    art = _artifact(tmp_path, "b.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    state = {"T1": _pstate(went_well=["a", "b", "c"], friction_points=["d", "e", "f"],
                           downstream_watchouts=["g", "h", "i"])}
    out = iji.resolve_inputs(graph, state, "T2")
    assert len(out["injected_notes"]) == max_notes == 9


def test_notes_count_exceeds_schema_bound_rejected(tmp_path):
    # 平坦化後の合計が Σ maxItems (9) を超えると拒否 (handoff 9 + flat 1 = 10)。
    max_notes, _ = iji.read_notes_bounds(iji.DEFAULT_NOTES_SCHEMA)  # == 9
    art = _artifact(tmp_path, "b.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    state = {"T1": _pstate(went_well=["a", "b", "c"], friction_points=["d", "e", "f"],
                           downstream_watchouts=["g", "h", "i"], notes=["overflow"])}
    assert 9 + 1 > max_notes
    out = iji.resolve_inputs(graph, state, "T2")
    assert out == {"rejected": True, "reason": "notes bound exceeded"}


def test_notes_length_exceeds_schema_bound_rejected(tmp_path):
    _, max_chars = iji.read_notes_bounds(iji.DEFAULT_NOTES_SCHEMA)  # == 200
    art = _artifact(tmp_path, "b.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    state = {"T1": _pstate(went_well=["a" * (max_chars + 1)])}  # maxLength +1
    out = iji.resolve_inputs(graph, state, "T2")
    assert out == {"rejected": True, "reason": "notes bound exceeded"}


def test_notes_length_at_schema_bound_ok(tmp_path):
    _, max_chars = iji.read_notes_bounds(iji.DEFAULT_NOTES_SCHEMA)  # == 200
    art = _artifact(tmp_path, "b.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    note = "a" * max_chars  # 上限ちょうどは許容 (> のみ拒否)
    out = iji.resolve_inputs(graph, {"T1": _pstate(went_well=[note])}, "T2")
    assert out["injected_notes"] == [note]


def test_notes_bound_is_per_producer_diamond_full_ok(tmp_path):
    # 件数上限は producer 単位 (schema は 1 node 分を制約)。ダイヤモンド依存で 2 producer が
    # 各々満杯 (9 件ずつ・合計 18 > 9) でも各 producer は正当ゆえ偽拒否しない。
    max_notes, _ = iji.read_notes_bounds(iji.DEFAULT_NOTES_SCHEMA)  # == 9
    a1 = _artifact(tmp_path, "dia1.json")
    a2 = _artifact(tmp_path, "dia2.json")
    graph = _graph(
        _dep("T3", "T1"), _dep("T3", "T2"),
        nodes=[_gnode("T1", write_scope=a1), _gnode("T2", write_scope=a2)],
    )
    full = dict(went_well=["a", "b", "c"], friction_points=["d", "e", "f"],
                downstream_watchouts=["g", "h", "i"])  # 9 = Σ maxItems ちょうど
    out = iji.resolve_inputs(graph, {"T1": _pstate(**full), "T2": _pstate(**full)}, "T3")
    assert "rejected" not in out
    assert len(out["injected_notes"]) == 2 * max_notes == 18  # 全体は len(producers)×Σ maxItems


def test_notes_bound_single_producer_exceeds_in_diamond_rejected(tmp_path):
    # 複数 producer 中 1 つでも単体で Σ maxItems を超えれば拒否 (producer 単位判定)。
    max_notes, _ = iji.read_notes_bounds(iji.DEFAULT_NOTES_SCHEMA)  # == 9
    a1 = _artifact(tmp_path, "agg1.json")
    a2 = _artifact(tmp_path, "agg2.json")
    graph = _graph(
        _dep("T3", "T1"), _dep("T3", "T2"),
        nodes=[_gnode("T1", write_scope=a1), _gnode("T2", write_scope=a2)],
    )
    over = _pstate(went_well=["a", "b", "c"], friction_points=["d", "e", "f"],
                   downstream_watchouts=["g", "h", "i"], notes=["overflow"])  # 10 > 9
    small = _pstate(went_well=["ok"])  # 1 件 (合算でなく単体判定であることの対照)
    out = iji.resolve_inputs(graph, {"T1": over, "T2": small}, "T3")
    assert out == {"rejected": True, "reason": "notes bound exceeded"}


def test_max_notes_override_beats_schema_default(tmp_path):
    # 明示 --max-notes/引数上書きは schema 既定 (9) より優先される。
    art = _artifact(tmp_path, "o.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate(went_well=["a", "b"])}, "T2", max_notes=1)
    assert out == {"rejected": True, "reason": "notes bound exceeded"}


def test_max_note_chars_override_beats_schema_default(tmp_path):
    art = _artifact(tmp_path, "o.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    out = iji.resolve_inputs(graph, {"T1": _pstate(went_well=["abcd"])}, "T2", max_note_chars=3)
    assert out == {"rejected": True, "reason": "notes bound exceeded"}


# ─────────────────────────── purity (read-only) ───────────────────────────
def test_resolve_inputs_does_not_mutate_state(tmp_path):
    art = _artifact(tmp_path, "pure.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    state = {"T1": _pstate(went_well=["keep"])}
    snapshot = json.loads(json.dumps(state))
    iji.resolve_inputs(graph, state, "T2")
    assert state == snapshot


# ─────────────────────────── main() CLI ───────────────────────────
def _write(tmp_path, name: str, obj) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_main_normal_exit0(tmp_path, capsys):
    art = _artifact(tmp_path, "cli-out.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    gp = _write(tmp_path, "task-graph.json", graph)
    sp = _write(tmp_path, "task-state.json", {"T1": _pstate(went_well=["ok"])})
    rc = iji.main(["--task-graph", gp, "--task-state", sp, "--task-id", "T2"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["injected_inputs"] == [{"producer_task_id": "T1", "artifact_path": art}]
    assert payload["injected_notes"] == ["ok"]


def test_main_rejected_exit1(tmp_path, capsys):
    art = _artifact(tmp_path, "cli.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    gp = _write(tmp_path, "g.json", graph)
    sp = _write(tmp_path, "s.json", {"T1": _pstate(state="pending")})
    rc = iji.main(["--task-graph", gp, "--task-state", sp, "--task-id", "T2"])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["rejected"] is True


def test_main_bad_task_graph_path_exit2(tmp_path):
    sp = _write(tmp_path, "s.json", {})
    rc = iji.main(["--task-graph", str(tmp_path / "nope.json"), "--task-state", sp, "--task-id", "T2"])
    assert rc == 2


def test_main_missing_required_arg_exit2(tmp_path):
    gp = _write(tmp_path, "g.json", _graph())
    rc = iji.main(["--task-graph", gp])  # --task-state / --task-id 欠落
    assert rc == 2


def test_main_normalizes_c02_nodes_list(tmp_path, capsys):
    # TG-C02 task-state.schema.json shape ({"nodes":[{"id","state","handoff_notes"}]}) を id で keying。
    art = _artifact(tmp_path, "n.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    gp = _write(tmp_path, "task-graph.json", graph)
    task_state = {"schema_version": "1.0", "graph_hash": None,
                  "nodes": [{"id": "T1", "state": "done",
                             "handoff_notes": {"went_well": ["ok"], "friction_points": ["care"]}}]}
    sp = _write(tmp_path, "task-state.json", task_state)
    rc = iji.main(["--task-graph", gp, "--task-state", sp, "--task-id", "T2"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["injected_inputs"] == [{"producer_task_id": "T1", "artifact_path": art}]
    assert payload["injected_notes"] == ["ok", "care"]


def test_main_schema_derived_notes_bound_exit1(tmp_path, capsys):
    # main() 経由でも schema 由来 (Σ maxItems=9) を超える notes は拒否。
    art = _artifact(tmp_path, "c.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    gp = _write(tmp_path, "g.json", graph)
    over = _pstate(went_well=["a", "b", "c"], friction_points=["d", "e", "f"],
                   downstream_watchouts=["g", "h", "i"], notes=["overflow"])  # 10 > 9
    sp = _write(tmp_path, "s.json", {"T1": over})
    rc = iji.main(["--task-graph", gp, "--task-state", sp, "--task-id", "T2"])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "notes bound exceeded"


def test_main_max_notes_override_via_cli(tmp_path):
    art = _artifact(tmp_path, "o.json")
    graph = _graph(_dep("T2", "T1"), nodes=[_gnode("T1", write_scope=art)])
    gp = _write(tmp_path, "g.json", graph)
    sp = _write(tmp_path, "s.json", {"T1": _pstate(went_well=["a", "b"])})
    rc = iji.main(["--task-graph", gp, "--task-state", sp, "--task-id", "T2", "--max-notes", "1"])
    assert rc == 1


# ─────────────────────────── 実 producer graph 統合 (derive-task-graph.py) ─────────
@pytest.mark.skipif(
    not (PLANNER_SCRIPTS / "derive-task-graph.py").is_file(),
    reason="producer derive-task-graph.py 不在 (単独配布時)",
)
def test_integration_real_derived_graph_injects_write_scope(tmp_path):
    """実 derive-task-graph.py が出す graph (write_scope 成果物・depends_on エッジ) で
    injected_inputs/injected_notes が非空になることを固定する (契約 realized)。"""
    dtg = _load(PLANNER_SCRIPTS, "derive-task-graph")

    # producer C01 の成果物 (実在ファイル) と consumer C02 の成果物。
    producer_artifact = _artifact(tmp_path, "producer-artifact.py")
    consumer_artifact = _artifact(tmp_path, "consumer-artifact.py")

    # 1 phase・1 checklist 項目・entities_covered=[C01, C02]。C02 depends_on C01。
    phase = (
        "---\n"
        "id: P01\n"
        "phase_name: implementation\n"
        "entities_covered: [C01, C02]\n"
        "---\n"
        "# phase\n\n"
        "## 完了チェックリスト\n"
        "- [ ] 成果物を実装する\n"
    )
    (tmp_path / "phase-01-implementation.md").write_text(phase, encoding="utf-8")
    (tmp_path / "component-inventory.json").write_text(
        json.dumps({"components": [
            {"id": "C01", "depends_on": [], "build_target": producer_artifact},
            {"id": "C02", "depends_on": ["C01"], "build_target": consumer_artifact},
        ]}),
        encoding="utf-8",
    )

    graph = dtg.derive(tmp_path)

    # 実グラフの形状を確認: depends_on エッジが C02 node → C01 node に張られ、
    # producer node は write_scope と produces の双方で成果物パスを持つ。
    dep_edges = [e for e in graph["edges"] if e["type"] == "depends_on"]
    assert dep_edges, "depends_on エッジが生成されていない"
    consumer_id = dep_edges[0]["from"]
    producer_id = dep_edges[0]["to"]
    producer_node = next(n for n in graph["nodes"] if n["id"] == producer_id)
    assert producer_node["write_scope"] == producer_artifact
    assert {"type": "produces", "from": producer_id, "to": producer_artifact} in graph["edges"]

    # producer done + handoff_notes を持つ実形状 state (TG-C02 shape: nodes list)。
    task_state = {
        "schema_version": "1.0", "graph_hash": None,
        "nodes": [{
            "id": producer_id, "state": "done",
            "handoff_notes": {
                "went_well": ["生成器を決定論化した"],
                "downstream_watchouts": ["canonical 順序に依存"],
            },
        }],
    }

    out = iji.resolve_inputs(graph, iji._keyed_state(task_state), consumer_id)
    assert out.get("injected_inputs") == [
        {"producer_task_id": producer_id, "artifact_path": producer_artifact}
    ]
    assert out.get("injected_notes") == ["生成器を決定論化した", "canonical 順序に依存"]
