"""index-harness-artifact-graph.py (C05) の read-only 突合 + 決定論 index 挙動テスト。

task-graph の produces 辺 / handoff の route / task-state の graph_hash / route report /
build trace / 実在 build_target を突合し planned/built/verified/stale を二値判定する。fixture は
tmp_path 内に最小 plan/build/plugin ツリーを自作し実 eval-log/ を汚さない。

被覆:
  - 正常 (real artifact を 1 件以上 dereference・planned/built/verified 判定)     -> exit0
  - 壊れた突合 (route report が success を主張するが build_target 不在)             -> exit1
  - redaction (secret 様文字列を混入 -> 出力に平文で出ない・redacted 件数>0)
  - 決定論 (2 回実行で byte-identical)
  - stale 判定 (artifact mtime > report mtime / graph_hash 不一致)
  - usage (必須フラグ欠落 / plugin-root 不在)                                        -> exit2
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/index-harness-artifact-graph.py"
SLUG = "ubm-goal-setting"

# derive-task-graph.py と同一の canonical graph_hash アルゴリズム (SSOT 契約の複製)。
_NODE_KEYS = ("id", "title", "phase_ref", "entity_ref", "state", "write_scope", "acceptance_criterion")
_EDGE_KEYS = ("type", "from", "to")


def _canon(graph: dict) -> dict:
    nodes = []
    for n in graph.get("nodes", []):
        out = {}
        for k in _NODE_KEYS:
            if k == "acceptance_criterion":
                if k in n and n[k] is not None:
                    out[k] = n[k]
            else:
                out[k] = n.get(k)
        nodes.append(out)
    edges = [{k: e.get(k) for k in _EDGE_KEYS} for e in graph.get("edges", [])]
    nodes.sort(key=lambda n: str(n.get("id")))
    edges.sort(key=lambda e: (str(e.get("type")), str(e.get("from")), str(e.get("to"))))
    return {"schema_version": graph.get("schema_version", "1.0"), "nodes": nodes, "edges": edges}


def graph_hash(graph: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(_canon(graph), ensure_ascii=False, indent=2).encode("utf-8")
    ).hexdigest()


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def route(cid: str, kind: str, name: str, target: str, depends_on=None, builder="plugin-scaffold", build_kind="script") -> dict:
    return {
        "id": cid,
        "component_kind": kind,
        "name": name,
        "depends_on": depends_on or [],
        "builder": builder,
        "build_kind": build_kind,
        "build_target": target,
        "status": "planned",
    }


def build_tree(tmp_path: Path, *, secret: str | None = None, break_reconcile: bool = False,
               stale: bool = False, hash_mismatch: bool = False) -> dict:
    """repo_root=tmp_path に plugins/<slug>, eval-log/<slug>/build, plan/ を敷く。

    component 構成:
      C_BUILT  : script  present + route report success + trace + evidence -> verified
      C_PLAN   : sub-agent 不在 route report なし                          -> planned
      C_STALE  : script  present + route report success (mtime 制御で stale)
    """
    repo = tmp_path
    slug = SLUG
    plugin_root = repo / "plugins" / slug
    scripts_dir = plugin_root / "scripts"
    agents_dir = plugin_root / "agents"
    knowledge_dir = plugin_root / "knowledge"
    build_dir = repo / "eval-log" / slug / "build"
    plan_dir = repo / "plan"
    for d in (scripts_dir, agents_dir, knowledge_dir, build_dir, plan_dir):
        d.mkdir(parents=True, exist_ok=True)

    built_target = f"plugins/{slug}/scripts/built.py"
    plan_target = f"plugins/{slug}/agents/planned.md"
    stale_target = f"plugins/{slug}/scripts/stale.py"

    # 実在成果物 (dereference 対象)
    (repo / built_target).write_text("# built\n", encoding="utf-8")
    (repo / stale_target).write_text("# stale\n", encoding="utf-8")
    # plan_target はわざと作らない (planned = 実体なし)

    built_name = "built.py"
    if secret is not None:
        # secret 様文字列を route name に混入し出力へ流し込む
        built_name = f"built {secret} .py"

    routes = [
        route("C_BUILT", "script", built_name, built_target, builder="plugin-scaffold", build_kind="script"),
        route("C_PLAN", "sub-agent", "planned-agent", plan_target, depends_on=["C_BUILT"], builder="run-build-skill", build_kind="agent"),
        route("C_STALE", "script", "stale.py", stale_target, depends_on=["C_BUILT"], build_kind="script"),
    ]
    handoff = {"plan_dir": "plan", "target_plugin_slug": slug, "mode": "update", "routes": routes}
    write_json(plan_dir / "handoff-run-plugin-dev-plan.json", handoff)

    # task-graph: produces 辺で task_node -> build_target を張る
    tg_nodes = [
        {"id": "P02-CB-01", "title": "build built", "phase_ref": "P02", "entity_ref": "C_BUILT",
         "state": "pending", "write_scope": built_target},
        {"id": "P02-CP-01", "title": "build planned", "phase_ref": "P02", "entity_ref": "C_PLAN",
         "state": "pending", "write_scope": plan_target},
        {"id": "P02-CS-01", "title": "build stale", "phase_ref": "P02", "entity_ref": "C_STALE",
         "state": "pending", "write_scope": stale_target},
    ]
    tg_edges = [
        {"type": "produces", "from": "P02-CB-01", "to": built_target},
        {"type": "produces", "from": "P02-CP-01", "to": plan_target},
        {"type": "produces", "from": "P02-CS-01", "to": stale_target},
        {"type": "depends_on", "from": "P02-CP-01", "to": "P02-CB-01"},
    ]
    task_graph = {"schema_version": "1.0", "nodes": tg_nodes, "edges": tg_edges}
    write_json(plan_dir / "task-graph.json", task_graph)

    # task-state: graph_hash と done ノードで stale/verified の材料
    th = graph_hash(task_graph)
    if hash_mismatch:
        th = "sha256:" + "0" * 64
    task_state = {
        "schema_version": "1.0",
        "graph_hash": th,
        "nodes": [
            {"id": "P02-CB-01", "state": "done", "route_report": f"eval-log/{slug}/build/route-C_BUILT.json"},
            {"id": "P02-CS-01", "state": "done", "route_report": f"eval-log/{slug}/build/route-C_STALE.json"},
        ],
    }
    write_json(build_dir / "task-state.json", task_state)

    # route reports
    def report(cid: str, kind: str, target: str, status: str = "success", evidence=None) -> None:
        write_json(build_dir / f"route-{cid}.json", {
            "schema_version": "1.0.0", "plugin_slug": slug, "route_id": cid,
            "component_kind": kind, "build_target": target, "status": status,
            "evidence": evidence if evidence is not None else ["lint exit0", "pytest 3 passed"],
        })

    built_report_target = built_target
    if break_reconcile:
        # 壊れた突合: route report は success だが指す build_target を実在させない
        built_report_target = f"plugins/{slug}/scripts/ghost.py"
    report("C_BUILT", "script", built_report_target)
    report("C_STALE", "script", stale_target)
    # C_PLAN には route report を作らない (planned)

    # build trace (agent/script いずれの verified 証跡にもなる)
    write_json(build_dir / "skill-build-trace-C_BUILT.json", {"skill_name": "built", "build_mode": "create"})

    # plugin surfaces
    (plugin_root / "plugin-composition.yaml").write_text(
        "name: {}\nkind: plugin-composition\ncapabilities:\n  - {{ kind: script, ref: scripts/built.py, tier: core }}\n".format(slug),
        encoding="utf-8",
    )
    write_json(plugin_root / "EVALS.json", {"plugin": slug, "version": "0.1.0", "harness": {"mechanical": []}})

    # mtime 制御: report を artifact より新しく (built=not stale)。stale 指定時は stale artifact を report より新しく。
    t0 = 1_700_000_000
    os.utime(repo / built_target, (t0, t0))
    os.utime(build_dir / "route-C_BUILT.json", (t0 + 100, t0 + 100))
    os.utime(build_dir / "skill-build-trace-C_BUILT.json", (t0 + 100, t0 + 100))
    if stale:
        os.utime(build_dir / "route-C_STALE.json", (t0, t0))
        os.utime(repo / stale_target, (t0 + 100, t0 + 100))  # artifact newer than report -> stale
    else:
        os.utime(repo / stale_target, (t0, t0))
        os.utime(build_dir / "route-C_STALE.json", (t0 + 100, t0 + 100))

    return {
        "repo": repo,
        "plugin_root": plugin_root,
        "plan_glob": str(plan_dir / "*.json"),
        "out": knowledge_dir / "harness-artifact-graph.json",
    }


def invoke(ctx: dict) -> subprocess.CompletedProcess:
    return run("--plan-glob", ctx["plan_glob"], "--plugin-root", str(ctx["plugin_root"]), "--out", str(ctx["out"]))


# ---- 正常系 ----------------------------------------------------------------

def test_normal_reconcile_exit0_real_dereference(tmp_path: Path):
    ctx = build_tree(tmp_path)
    r = invoke(ctx)
    assert r.returncode == 0, r.stdout + r.stderr
    assert ctx["out"].exists()
    g = json.loads(ctx["out"].read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g["nodes"]}
    # real artifact を 1 件以上 dereference できている
    assert nodes["C_BUILT"]["freshness"]["artifact_present"] is True
    assert nodes["C_PLAN"]["freshness"]["artifact_present"] is False
    # 状態判定
    assert nodes["C_BUILT"]["state"] == "verified"
    assert nodes["C_PLAN"]["state"] == "planned"
    # provenance: produces 辺 / task-state ノード / route report を参照
    assert nodes["C_BUILT"]["provenance"]["produces_task_node"] == "P02-CB-01"
    assert nodes["C_BUILT"]["provenance"]["route_report"].endswith("route-C_BUILT.json")
    assert nodes["C_BUILT"]["provenance"]["build_trace"].endswith("skill-build-trace-C_BUILT.json")
    # depends_on 辺 (component 間) が張られる
    assert {"from": "C_PLAN", "to": "C_BUILT", "type": "depends_on"} in g["edges"]
    # graph_hash 一致
    assert g["graph_hash"]["match"] is True
    assert g["counts"]["redacted"] == 0


def test_stdout_summary(tmp_path: Path):
    ctx = build_tree(tmp_path)
    r = invoke(ctx)
    assert r.returncode == 0
    assert "OK: harness-artifact-graph indexed" in r.stdout
    assert "nodes=3" in r.stdout


# ---- 壊れた突合 ------------------------------------------------------------

def test_broken_reconcile_report_points_to_missing_target_exit1(tmp_path: Path):
    ctx = build_tree(tmp_path, break_reconcile=True)
    r = invoke(ctx)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "VIOLATION" in r.stderr
    # 壊れた突合時は graph を書かない
    assert not ctx["out"].exists()


# ---- redaction -------------------------------------------------------------

def test_redaction_secret_not_persisted(tmp_path: Path):
    secret = "ghp_" + "A1b2C3d4E5f6G7h8I9j0" + "KLMNOP"
    ctx = build_tree(tmp_path, secret=secret)
    r = invoke(ctx)
    assert r.returncode == 0, r.stdout + r.stderr
    raw = ctx["out"].read_text(encoding="utf-8")
    assert secret not in raw
    assert "[REDACTED]" in raw
    g = json.loads(raw)
    assert g["counts"]["redacted"] >= 1


def test_redaction_preserves_sha256_hash(tmp_path: Path):
    # sha256:<64hex> は正当な値であり redact してはならない
    ctx = build_tree(tmp_path)
    r = invoke(ctx)
    assert r.returncode == 0
    g = json.loads(ctx["out"].read_text(encoding="utf-8"))
    assert g["graph_hash"]["recomputed"].startswith("sha256:")
    assert "[REDACTED]" not in g["graph_hash"]["recomputed"]


# ---- 決定論 ----------------------------------------------------------------

def test_deterministic_byte_identical(tmp_path: Path):
    ctx = build_tree(tmp_path)
    r1 = invoke(ctx)
    b1 = ctx["out"].read_bytes()
    r2 = invoke(ctx)
    b2 = ctx["out"].read_bytes()
    assert r1.returncode == 0 and r2.returncode == 0
    assert b1 == b2


# ---- stale -----------------------------------------------------------------

def test_stale_artifact_newer_than_report(tmp_path: Path):
    ctx = build_tree(tmp_path, stale=True)
    r = invoke(ctx)
    assert r.returncode == 0, r.stdout + r.stderr
    g = json.loads(ctx["out"].read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["C_STALE"]["state"] == "stale"
    assert "artifact_newer_than_report" in nodes["C_STALE"]["freshness"]["stale_reasons"]


def test_stale_graph_hash_mismatch(tmp_path: Path):
    ctx = build_tree(tmp_path, hash_mismatch=True)
    r = invoke(ctx)
    assert r.returncode == 0, r.stdout + r.stderr
    g = json.loads(ctx["out"].read_text(encoding="utf-8"))
    assert g["graph_hash"]["match"] is False
    nodes = {n["id"]: n for n in g["nodes"]}
    # graph_hash 不一致 + task-state done -> stale 化
    assert nodes["C_BUILT"]["state"] == "stale"
    assert "graph_hash_mismatch" in nodes["C_BUILT"]["freshness"]["stale_reasons"]


# ---- usage -----------------------------------------------------------------

def test_usage_missing_flag_exit2(tmp_path: Path):
    r = run("--plugin-root", str(tmp_path))
    assert r.returncode == 2


def test_usage_plugin_root_absent_exit2(tmp_path: Path):
    ctx = build_tree(tmp_path)
    r = run("--plan-glob", ctx["plan_glob"], "--plugin-root", str(tmp_path / "nope"), "--out", str(ctx["out"]))
    assert r.returncode == 2


def test_usage_plan_glob_no_taskgraph_exit2(tmp_path: Path):
    ctx = build_tree(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    r = run("--plan-glob", str(empty / "*.json"), "--plugin-root", str(ctx["plugin_root"]), "--out", str(ctx["out"]))
    assert r.returncode == 2
