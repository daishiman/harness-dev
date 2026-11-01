"""lint-open-residue.py の検証。

OR-D* (MUST_DETECT) / OR-P* (MUST_PASS) / OR-C* (契約) を実行する。
beads は --beads-export の JSONL で注入し、bd を持つ dir を PATH から外して起動するので live の
Dolt DB には触れない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lint-open-residue.py"


def _env_without_bd() -> dict[str, str]:
    """bd の live export へ落ちないよう、bd を含む dir を PATH から除く。"""
    dirs = os.environ.get("PATH", "").split(os.pathsep)
    return {**os.environ, "PATH": os.pathsep.join(d for d in dirs if d and not (Path(d) / "bd").exists())}


def _fm(node: dict) -> str:
    keys = sorted(node.keys())
    lines = ["---"]
    for k in keys:
        lines.append(f"{k}: {json.dumps(node[k], ensure_ascii=False, sort_keys=True)}")
    lines += ["---", "", "# body", ""]
    return "\n".join(lines)


def _node(node_id: str, *, status="closed", ce_status="done", bd_id="proj-x",
          kind="issue", file_rel=None, policy="manual") -> dict:
    return {
        "graph_node_id": node_id,
        "artifact_kind": kind,
        "status": status,
        "tracker_binding": "beads",
        "beads_linkage": {"bd_issue_id": bd_id, "linked_at": "2026-07-22T00:00:00Z", "sync_state": "linked"},
        "completion_evidence": {
            "policy": policy, "status": ce_status, "source": None,
            "completed_at": None, "reconciled_at": None, "evidence_refs": [],
        },
        "file_path": file_rel or f"issues/{node_id}.md",
    }


def _repo(tmp_path: Path, nodes: list[dict], beads: dict[str, str]) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / ".dev-graph" / "state").mkdir(parents=True)
    (root / ".dev-graph" / "config.json").write_text("{}", encoding="utf-8")
    (root / ".dev-graph" / "state" / "graph.json").write_text(
        json.dumps({"schema_version": "1.0.0", "graph_revision": 1, "nodes": nodes}), encoding="utf-8")
    for n in nodes:
        fp = root / n["file_path"]
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(_fm(n), encoding="utf-8")
    export = tmp_path / "beads.jsonl"
    export.write_text("\n".join(json.dumps({"id": k, "status": v}) for k, v in beads.items()), encoding="utf-8")
    return root, export


def _proc(root: Path, export: Path | None, *extra: str) -> subprocess.CompletedProcess:
    args = [sys.executable, "-B", str(SCRIPT), "--repo-root", str(root)]
    if export is not None:
        args += ["--beads-export", str(export)]
    args += list(extra)
    return subprocess.run(args, capture_output=True, text=True, check=False, env=_env_without_bd())


def _run(root: Path, export: Path | None, *extra: str) -> tuple[int, dict]:
    proc = _proc(root, export, *extra)
    return proc.returncode, json.loads(proc.stdout)


# --- MUST_DETECT ---

def test_or_d01_status_mismatch(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="active", ce_status="done")]
    # md status を graph と食い違わせる
    root, export = _repo(tmp_path, nodes, {"proj-x": "closed"})
    front = nodes[0].copy(); front["status"] = "closed"
    (root / nodes[0]["file_path"]).write_text(_fm(front), encoding="utf-8")
    code, out = _run(root, export)
    assert code == 2 and any(v["rule"] == "OR-001" for v in out["violations"])


def test_or_d02_completion_evidence_mismatch(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="open")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "open"})
    front = json.loads(json.dumps(nodes[0]))
    front["completion_evidence"]["status"] = "done"
    (root / nodes[0]["file_path"]).write_text(_fm(front), encoding="utf-8")
    code, out = _run(root, export)
    assert code == 2 and any(v["rule"] == "OR-002" for v in out["violations"])


def test_or_d03_resolved_open_residue(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="open")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "closed"})
    code, out = _run(root, export)
    assert code == 2 and any(v["rule"] == "OR-003" for v in out["violations"])


def test_or_d04_reverse_residue(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="done", ce_status="done")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "open"})
    code, out = _run(root, export)
    assert code == 2 and any(v["rule"] == "OR-004" for v in out["violations"])


def test_or_d05_beads_unavailable_fail_closed(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="done")]
    root, _ = _repo(tmp_path, nodes, {"proj-x": "closed"})
    # export を渡さず、bd も PATH に無い → require_beads (既定) で exit 2。
    proc = _proc(root, None)
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    assert out["beads_axis"] == "unavailable" and out["exit_code"] == 2
    assert "FAIL" in proc.stderr


def test_or_d06_combined_status_and_residue_detection(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="active", ce_status="open")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "closed"})
    front = json.loads(json.dumps(nodes[0])); front["status"] = "closed"
    (root / nodes[0]["file_path"]).write_text(_fm(front), encoding="utf-8")
    code, out = _run(root, export)
    assert code == 2
    assert {v["rule"] for v in out["violations"]} == {"OR-001", "OR-003"}


# --- MUST_PASS ---

def test_or_p01_all_consistent(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="done")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "closed"})
    code, out = _run(root, export)
    assert code == 0 and out["violation_count"] == 0


def test_or_p02_closed_doc_inprogress_execution_not_violation(tmp_path: Path) -> None:
    # status=closed かつ ce=in_progress かつ beads も未 close → 矛盾ではない
    nodes = [_node("issue-a", status="closed", ce_status="in_progress")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "open"})
    code, out = _run(root, export)
    assert code == 0, out["violations"]


def test_or_p03_non_beads_node_is_not_scanned(tmp_path: Path) -> None:
    node = _node("issue-a", status="closed", ce_status="open")
    node["tracker_binding"] = "github"
    root, export = _repo(tmp_path, [node], {"proj-x": "closed"})
    code, out = _run(root, export)
    assert code == 0 and out["scanned"] == 0


def test_or_p04_no_require_beads(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="open")]
    root, _ = _repo(tmp_path, nodes, {"proj-x": "closed"})
    code, out = _run(root, None, "--no-require-beads")
    assert code == 0  # OR-003 は未評価
    assert out["beads_axis"] == "unavailable"


def test_or_p05_not_applicable_settled(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="not_applicable")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "closed"})
    code, out = _run(root, export)
    assert code == 0


def test_or_p06_local_only_manual_policy_settles_after_close_loop(tmp_path: Path) -> None:
    """local_only 運用 (PR 0件) の node が close-loop を完走した終状態を残置にしない。

    PR を持たない node に `linked_pr_merged_all|any` を残すと graph-node.schema.json が
    `status=done` に merged な pull_request_linkages を 1 件以上要求するため、
    completion_evidence が永久に done へ到達できず beads だけ closed になって OR-003 が
    構造的に再発する。`policy=manual` なら到達でき、その終状態は残置ではない。
    """
    node = _node("issue-local-only", status="closed", ce_status="done", policy="manual")
    node["github_publication"] = {
        "mode": "local_only",
        "project_aliases": [],
        "labels": [],
        "milestone": None,
    }
    node["pull_request_linkages"] = []
    node["completion_evidence"]["source"] = "manual"
    node["completion_evidence"]["completed_at"] = "2026-07-26T00:00:00Z"
    node["completion_evidence"]["reconciled_at"] = "2026-07-26T00:00:00Z"
    root, export = _repo(tmp_path, [node], {"proj-x": "closed"})
    code, out = _run(root, export)
    assert code == 0 and out["violation_count"] == 0
    # 走査から外して緑にする逃げ (偽の解決) を塞ぐ: 検査されたうえで違反 0 であること。
    assert out["scanned"] == 1


# --- 契約 ---

def test_or_c02_deterministic_across_node_order(tmp_path: Path) -> None:
    a = _node("issue-a", status="closed", ce_status="open", bd_id="proj-a")
    b = _node("issue-b", status="closed", ce_status="open", bd_id="proj-b")
    root1, e1 = _repo(tmp_path / "1", [a, b], {"proj-a": "closed", "proj-b": "closed"})
    root2, e2 = _repo(tmp_path / "2", [b, a], {"proj-a": "closed", "proj-b": "closed"})
    _, o1 = _run(root1, e1)
    _, o2 = _run(root2, e2)
    assert o1["violations"] == o2["violations"]


def test_or_c04_repeated_stdout_is_byte_identical(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="open")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "closed"})
    first = _proc(root, export).stdout
    second = _proc(root, export).stdout
    assert first == second


def test_or_c01_c03_common_shape_and_relative_paths(tmp_path: Path) -> None:
    nodes = [_node("issue-a", status="closed", ce_status="open")]
    root, export = _repo(tmp_path, nodes, {"proj-x": "closed"})
    _, out = _run(root, export)
    assert {"lint", "repo_root", "scanned", "violations", "violation_count", "exit_code"} <= set(out)
    assert out["repo_root"] == "."
    assert all(not Path(v["path"]).is_absolute() for v in out["violations"])
