"""qa-069 MVP-first スケジューリングの回帰テスト (C1 ソート / C2 冪等 / C3 後方互換 / C4 receipt)。

文中の design §N / AC-N は HarnessHub の docs/features/feat-mvp-first-scheduling/design.md を指す。

守る不変条件は 3 つ。
1. 着手候補の順序は MVP 適合 rank (direct→enabling→未設定→deferred) 第一・node_id 辞書順
   tie-break で決まり、順序決定点は schedule-graph.py の candidates 構築 1 箇所のみ。
2. enum 外の mvp_fit / dict・null 以外の mvp_alignment は rank 2 へ丸めず plan 全体を
   fail-closed で停止する (黙って丸めると不正 metadata が通る)。
3. mvp_alignment 未設定 graph の順序は従来実装 (node_id 辞書順) と完全一致し、
   selection_receipt は additive 追加のみで既存 plan キーへ触れない。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    code = module.main()
    output = capsys.readouterr().out.strip()
    return code, json.loads(output) if output else None


def alignment(fit: str, *, purpose="目的テキスト", background="背景テキスト", rationale="根拠テキスト") -> dict:
    return {"mvp_fit": fit, "purpose": purpose, "background": background, "rationale": rationale}


def node(node_id: str, *, kind: str = "task", mvp=None, status: str = "active",
         parent: str | None = None, evaluation: str = "pass") -> dict:
    """schedule-graph が読む最小 node。resource_scope は node 固有にして batch 干渉を避ける。"""
    data = {
        "graph_node_id": node_id, "artifact_kind": kind, "status": status,
        "confirmation_status": "confirmed", "evaluation_status": evaluation,
        "implementation_readiness": {"status": "complete"}, "depends_on": [],
        "tracker_binding": "none", "resource_scope": [f"scope/{node_id}"],
        "parent_feature": parent,
    }
    if mvp is not None:
        data["mvp_alignment"] = mvp
    return data


def workspace(tmp_path: Path, nodes: list[dict]) -> tuple[Path, Path]:
    graph = tmp_path / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    leases = tmp_path / "leases.json"
    leases.write_text(json.dumps({"leases": []}), encoding="utf-8")
    return graph, leases


def run(module, monkeypatch, capsys, tmp_path: Path, nodes: list[dict]):
    graph, leases = workspace(tmp_path, nodes)
    return call_main(module, monkeypatch, capsys, "--graph", graph, "--leases", leases)


# --- C1: MVP-first ソート (AC-1) ---


def test_mvp_sort_orders_candidates_by_rank_before_node_id(tmp_path, monkeypatch, capsys):
    """TC-MVP-SORT-01: node_id 辞書順では deferred が先に来る配置でも rank が勝つ。"""
    module = load("schedule-graph.py", "mvp_sort_rank")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        node("t-a", mvp=alignment("deferred")),
        node("t-b"),
        node("t-c", mvp=alignment("enabling")),
        node("t-d", mvp=alignment("direct")),
    ])
    assert code == 0
    assert plan["ready_set"]["tasks"] == ["t-d", "t-c", "t-b", "t-a"]
    assert [entry["sort_rank"] for entry in plan["selection_receipt"]["entries"]] == [0, 1, 2, 3]


def test_mvp_sort_tie_breaks_same_rank_by_node_id(tmp_path, monkeypatch, capsys):
    """TC-MVP-SORT-02: 同 rank (direct) は node_id 辞書順で tie-break (design §3 INV-1)。"""
    module = load("schedule-graph.py", "mvp_sort_tie")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        node("t-c", mvp=alignment("direct")),
        node("t-a", mvp=alignment("direct")),
        node("t-b", mvp=alignment("direct")),
    ])
    assert code == 0
    assert plan["ready_set"]["tasks"] == ["t-a", "t-b", "t-c"]


def test_mvp_sort_applies_to_feature_batches(tmp_path, monkeypatch, capsys):
    """TC-MVP-SORT-03: features batch の並びにも同じ MVP_FIT_RANK が適用される (design §2)。"""
    module = load("schedule-graph.py", "mvp_sort_feature")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        node("f-a", kind="feature", mvp=alignment("deferred")),
        node("f-b", kind="feature", mvp=alignment("direct")),
        node("t-x", mvp=alignment("enabling")),
    ])
    assert code == 0
    assert plan["ready_set"]["features"] == ["f-b", "f-a"]
    assert plan["ready_set"]["tasks"] == ["t-x"]


def test_mvp_sort_fails_closed_on_unknown_mvp_fit(tmp_path, monkeypatch, capsys):
    """TC-MVP-SORT-04: enum 外の非 null mvp_fit は rank 2 へ丸めず plan 全体を fail する。"""
    module = load("schedule-graph.py", "mvp_sort_bad_enum")
    with pytest.raises(module.ContractError, match="unsupported mvp_fit"):
        run(module, monkeypatch, capsys, tmp_path, [
            node("t-ok", mvp=alignment("direct")),
            node("t-bad", mvp=alignment("urgent")),
        ])


def test_mvp_sort_fails_closed_on_non_object_alignment(tmp_path, monkeypatch, capsys):
    """TC-MVP-SORT-05: mvp_alignment が dict でも null でもない型は ContractError。"""
    module = load("schedule-graph.py", "mvp_sort_bad_type")
    broken = node("t-bad")
    broken["mvp_alignment"] = "direct"
    with pytest.raises(module.ContractError, match="mvp_alignment must be an object or null"):
        run(module, monkeypatch, capsys, tmp_path, [broken])


# --- C2: 冪等性 (AC-2) ---


def test_mvp_idempotent_plan_between_runs(tmp_path, monkeypatch, capsys):
    """TC-MVP-IDEM-01: 同一入力 2 回で batches・順序・selection_receipt が完全一致する。"""
    module = load("schedule-graph.py", "mvp_idem")
    nodes = [
        node("t-a", mvp=alignment("deferred")),
        node("t-b"),
        node("t-c", mvp=alignment("enabling")),
        node("t-d", mvp=alignment("direct")),
    ]
    code_first, first = run(module, monkeypatch, capsys, tmp_path, nodes)
    code_second, second = run(module, monkeypatch, capsys, tmp_path, nodes)
    assert code_first == code_second == 0
    for key in ("ready_set", "batches", "selection_receipt"):
        assert first[key] == second[key]


# --- C3: 後方互換 (MVP metadata 未設定 node の fallback) ---


def test_mvp_compat_unset_graph_keeps_lexicographic_order(tmp_path, monkeypatch, capsys):
    """TC-MVP-COMPAT-01: 全 node 未設定 (現行資産と同型) は従来の node_id 辞書順と一致する。"""
    module = load("schedule-graph.py", "mvp_compat_order")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [node("t-b"), node("t-a"), node("t-c")])
    assert code == 0
    assert plan["ready_set"]["tasks"] == ["t-a", "t-b", "t-c"]


def test_mvp_compat_existing_plan_keys_unchanged(tmp_path, monkeypatch, capsys):
    """TC-MVP-COMPAT-02: 既存 plan キーは不変で、追加は selection_receipt のみ (additive)。"""
    module = load("schedule-graph.py", "mvp_compat_keys")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [node("t-b"), node("t-a"), node("t-c")])
    assert code == 0
    existing_keys = {
        "ready_set", "batches", "conflicts", "conflict_pairs", "excluded", "assignment_hints",
        "unmapped", "parity_provenance", "ready_source", "scope", "max_parallel",
        "graph_digest", "read_only",
        "graph_sha256_before", "graph_sha256_after",
        "tracker_sha256_before", "tracker_sha256_after",
        "lease_sha256_before", "lease_sha256_after",
    }
    assert existing_keys <= set(plan)
    assert set(plan) - existing_keys == {"selection_receipt"}
    assert plan["batches"] == {"features": [], "tasks": [["t-a", "t-b", "t-c"]]}
    assert plan["conflicts"] == [] and plan["read_only"] is True
    # 未設定 node も receipt からは silent drop されない (rank 2 で必ず記録)。
    assert [entry["sort_rank"] for entry in plan["selection_receipt"]["entries"]] == [2, 2, 2]


# --- C4: 選定 receipt 出力 (AC-4) ---


def test_mvp_receipt_transcribes_alignment_with_order_index(tmp_path, monkeypatch, capsys):
    """TC-MVP-RCPT-01: 逐語転写 + features/tasks 分割前の通し order_index + artifact_kind。"""
    module = load("schedule-graph.py", "mvp_rcpt_verbatim")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        node("f-x", kind="feature", mvp=alignment(
            "direct", purpose="機能の目的", background="機能の背景", rationale="機能の根拠")),
        node("t-y", mvp=alignment(
            "enabling", purpose="taskの目的", background="taskの背景", rationale="taskの根拠")),
    ])
    assert code == 0
    entries = plan["selection_receipt"]["entries"]
    assert [entry["order_index"] for entry in entries] == [0, 1]
    assert [(entry["graph_node_id"], entry["artifact_kind"]) for entry in entries] == [
        ("f-x", "feature"), ("t-y", "task"),
    ]
    assert (entries[0]["purpose"], entries[0]["background"], entries[0]["rationale"]) == (
        "機能の目的", "機能の背景", "機能の根拠")
    assert (entries[1]["purpose"], entries[1]["background"], entries[1]["rationale"]) == (
        "taskの目的", "taskの背景", "taskの根拠")


def test_mvp_receipt_records_unset_nodes_without_silent_drop(tmp_path, monkeypatch, capsys):
    """TC-MVP-RCPT-02: 未設定 node は null 4 点 + sort_rank 2 で必ず記録される。"""
    module = load("schedule-graph.py", "mvp_rcpt_unset")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        node("t-set", mvp=alignment("direct")),
        node("t-unset"),
    ])
    assert code == 0
    unset = next(e for e in plan["selection_receipt"]["entries"] if e["graph_node_id"] == "t-unset")
    assert (unset["mvp_fit"], unset["purpose"], unset["background"], unset["rationale"]) == (
        None, None, None, None)
    assert unset["sort_rank"] == 2 and unset["deferral_reason"] is None


def test_mvp_receipt_deferral_reason_variants(tmp_path, monkeypatch, capsys):
    """TC-MVP-RCPT-03: deferral_reason は design §5 の状況別固定文字列 (未成立/未定義/parent なし)。"""
    module = load("schedule-graph.py", "mvp_rcpt_deferral")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        # (a) parent の MVP 未成立: direct 子は graph に居るが未完 (candidates 外でも集計対象)。
        node("t-def-a", mvp=alignment("deferred"), parent="f-a"),
        node("t-direct-open", mvp=alignment("direct"), parent="f-a", evaluation="pending"),
        # (b) parent に direct task が 1 件も無い (MVP 未定義)。
        node("t-def-b", mvp=alignment("deferred"), parent="f-b"),
        # (c) parent feature なし。
        node("t-def-c", mvp=alignment("deferred")),
    ])
    assert code == 0
    reasons = {
        entry["graph_node_id"]: entry["deferral_reason"]
        for entry in plan["selection_receipt"]["entries"]
    }
    assert reasons["t-def-a"] == (
        "quality-after-mvp: parent feature の MVP (direct 全件 done) が未成立のため繰り延べ")
    assert reasons["t-def-b"] == (
        "quality-after-mvp: MVP 未定義 (direct task 0 件) のため繰り延べ順序のみ適用")
    assert reasons["t-def-c"] == (
        "quality-after-mvp: parent feature なしのため mvp_established 判定対象外、繰り延べ順序のみ適用")


def test_mvp_receipt_mvp_established_true_false_null(tmp_path, monkeypatch, capsys):
    """TC-MVP-RCPT-04: mvp_established は direct 全件 done=true / 未完あり=false / 0 件=null。"""
    module = load("schedule-graph.py", "mvp_rcpt_established")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        # f-true: direct 全件 done (done node は candidates 外だが集計には効く)。
        node("t-ft-done", mvp=alignment("direct"), parent="f-true", status="done"),
        node("t-ft-next", mvp=alignment("deferred"), parent="f-true"),
        # f-false: direct に未完が残る。
        node("t-ff-open", mvp=alignment("direct"), parent="f-false", evaluation="pending"),
        node("t-ff-task", mvp=alignment("enabling"), parent="f-false"),
        # f-null: direct 0 件。
        node("t-fn-task", parent="f-null"),
    ])
    assert code == 0
    receipt = plan["selection_receipt"]
    # map の掲載対象は entries に現れる parent_feature 集合のみ (design §5)。
    assert receipt["mvp_established"] == {"f-true": True, "f-false": False, "f-null": None}
    established_reason = next(
        entry["deferral_reason"] for entry in receipt["entries"]
        if entry["graph_node_id"] == "t-ft-next"
    )
    assert established_reason == (
        "quality-after-mvp: parent feature の MVP 成立済み。deferred rank による繰り延べ順序のみ適用")


def test_mvp_receipt_present_on_stdout_without_eval_log(tmp_path, monkeypatch, capsys):
    """TC-MVP-RCPT-05: receipt は保存先を持たず、stdout の plan だけで読める。"""
    module = load("schedule-graph.py", "mvp_rcpt_stdout")
    code, plan = run(module, monkeypatch, capsys, tmp_path, [
        node("t-a", mvp=alignment("direct")),
        node("t-b"),
    ])
    assert code == 0
    receipt = plan["selection_receipt"]
    assert receipt["policy"] == "mvp-first/v1"
    assert len(receipt["entries"]) == 2
