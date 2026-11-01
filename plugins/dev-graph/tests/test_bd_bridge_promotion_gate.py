"""decompose criteria:OUT1 on the Beads path: only a promoted node becomes a Beads issue.

bd-bridge ``--op create`` (single and ``--projection-manifest``) reads each target node from graph.json,
not from the caller's flags or manifest, and applies the same gate as build-github-projection.plan().
One unpromoted target stops the whole call before the first bd process (preflight included) with a
JSON list of node ids and reasons. The fake bd replaces the bridge's process runner, or is a script on
DEV_GRAPH_BD for the CLI cases, so neither the network nor a real bd is used.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

REASON = "not confirmed/pass/readiness complete"
PROMOTED = {"confirmation_status": "confirmed", "evaluation_status": "pass",
            "implementation_readiness": {"status": "complete"}}
# Each single-gate variant misses exactly one condition, so a gate that drops one check fails here.
UNPROMOTED = {
    "draft": {**PROMOTED, "confirmation_status": "draft"},
    "evaluation-pending": {**PROMOTED, "evaluation_status": "pending"},
    "evaluation-stale": {**PROMOTED, "evaluation_status": "stale"},
    "readiness-incomplete": {**PROMOTED, "implementation_readiness": {"status": "incomplete"}},
    "readiness-missing": {key: value for key, value in PROMOTED.items() if key != "implementation_readiness"},
    # The state build-graph-node.py add registers before any evaluation.
    "add-default": {"confirmation_status": "draft", "evaluation_status": "pending",
                    "implementation_readiness": {"status": "incomplete"}},
}
CHILD_IDS = [f"T{i:02d}" for i in range(1, 14)]


def load(script: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def node(node_id: str, kind: str, state: dict) -> dict:
    return {"graph_node_id": node_id, "artifact_kind": kind, "title": f"Node {node_id}", **state}


def package_nodes(states: dict[str, dict] | None = None) -> list[dict]:
    states = states or {}
    return [node("F", "feature", states.get("F", PROMOTED)),
            *[node(child, "task", states.get(child, PROMOTED)) for child in CHILD_IDS]]


def write_graph(root: Path, nodes: list[dict]) -> Path:
    path = root / ".dev-graph" / "state" / "graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    return path


def write_manifest(root: Path) -> Path:
    manifest = {
        "feature": {"graph_node_id": "F", "title": "Feature F"},
        "children": [{"graph_node_id": child, "parent_feature": "F", "phase_ref": f"P{i:02d}",
                      "title": f"Phase {i:02d}", "depends_on": [] if i == 1 else [CHILD_IDS[i - 2]]}
                     for i, child in enumerate(CHILD_IDS, 1)],
    }
    path = root / "projection.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class FakeBd:
    """Answers every bd process the bridge starts; ``calls`` keeps their argv without the bd binary."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.issues: dict[str, dict] = {}

    def __call__(self, argv, *, cwd=None, check=True):
        args = [str(value) for value in argv[1:]]
        self.calls.append(args)
        if args == ["version"]:
            out = "bd version 1.4.2"
        elif args == ["where", "--json"]:
            out = {"database_path": "/fake/.beads/beads.db", "prefix": "bd", "schema_version": "1"}
        elif args[0] in {"search", "list"}:
            out = []
        elif args[0] == "create":
            issue_id = f"B{len(self.issues) + 1:02d}"
            out = {"id": issue_id, "status": "open", "issue_type": args[args.index("--type") + 1],
                   "external_ref": args[args.index("--external-ref") + 1], "dependencies": []}
            if "--parent" in args:
                out["parent"] = args[args.index("--parent") + 1]
            self.issues[issue_id] = out
        elif args[0] == "show":
            out = self.issues[args[1]]
        elif args[:2] == ["dep", "add"]:
            self.issues[args[2]]["dependencies"].append({"id": args[3]})
            out = {"ok": True}
        else:
            raise AssertionError(args)
        return SimpleNamespace(returncode=0, stdout=out if isinstance(out, str) else json.dumps(out), stderr="")

    def creates(self) -> list[list[str]]:
        return [args for args in self.calls if args[0] == "create"]


@pytest.fixture
def bridge(monkeypatch):
    module = load("bd-bridge.py", "bd_bridge_promotion_gate")
    fake = FakeBd()
    monkeypatch.setattr(module, "run", fake)
    return module, fake


def call(module, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", [str(module.__file__), *map(str, argv)])
    code = module.main()
    output = capsys.readouterr().out
    return code, json.loads(output) if output else None


def assert_blocked(code: int, payload: dict, fake: FakeBd, expected: list[str]) -> None:
    assert code != 0
    assert payload["status"] == "blocked" and payload["write_count"] == 0
    assert [row["graph_node_id"] for row in payload["blocked"]] == expected
    assert fake.calls == []  # no bd process at all: neither preflight nor search nor create


@pytest.mark.parametrize("kind,issue_type", [("feature", "epic"), ("task", "task")])
@pytest.mark.parametrize("variant", sorted(UNPROMOTED))
def test_single_create_of_an_unpromoted_node_never_calls_bd(bridge, tmp_path, monkeypatch, capsys,
                                                            kind, issue_type, variant):
    module, fake = bridge
    graph = write_graph(tmp_path, [node("G1", kind, UNPROMOTED[variant])])
    argv = ("--op", "create", "--repo-root", tmp_path, "--graph", graph, "--graph-node-id", "G1",
            "--title", "T", "--artifact-kind", kind)
    for extra in ((), ("--dry-run",)):
        code, payload = call(module, monkeypatch, capsys, *argv, *extra)
        assert_blocked(code, payload, fake, ["G1"])
        assert payload["blocked"][0]["reason"] == REASON

    # Promote the same node in graph.json: the identical call now creates exactly one issue of that type.
    write_graph(tmp_path, [node("G1", kind, PROMOTED)])
    code, payload = call(module, monkeypatch, capsys, *argv)
    assert code == 0 and payload["result"]["id"] == "B01"
    assert len(fake.creates()) == 1
    assert fake.issues["B01"]["issue_type"] == issue_type


def test_single_create_reads_the_state_from_the_configured_graph_not_the_caller(bridge, tmp_path,
                                                                               monkeypatch, capsys):
    module, fake = bridge
    graph = write_graph(tmp_path, [node("G1", "task", UNPROMOTED["draft"])])
    config = tmp_path / ".dev-graph" / "config.json"
    config.write_text(json.dumps({"local_state": {"graph": graph.relative_to(tmp_path).as_posix()}}))
    code, payload = call(module, monkeypatch, capsys, "--op", "create", "--repo-root", tmp_path,
                         "--graph-node-id", "G1", "--title", "T")
    assert_blocked(code, payload, fake, ["G1"])

    # A node the graph does not hold has no evaluated state, so it is not promoted either.
    code, payload = call(module, monkeypatch, capsys, "--op", "create", "--repo-root", tmp_path,
                         "--graph-node-id", "UNKNOWN", "--title", "T")
    assert_blocked(code, payload, fake, ["UNKNOWN"])
    assert payload["blocked"][0]["reason"] == "not in graph"


@pytest.mark.parametrize("target", ["F", "T01", "T07", "T13"])
@pytest.mark.parametrize("variant", sorted(UNPROMOTED))
def test_manifest_with_one_unpromoted_node_creates_nothing(bridge, tmp_path, monkeypatch, capsys, target, variant):
    module, fake = bridge
    graph = write_graph(tmp_path, package_nodes({target: UNPROMOTED[variant]}))
    manifest = write_manifest(tmp_path)
    argv = ("--op", "create", "--repo-root", tmp_path, "--graph", graph, "--projection-manifest", manifest)
    for extra in ((), ("--dry-run",)):
        code, payload = call(module, monkeypatch, capsys, *argv, *extra)
        assert_blocked(code, payload, fake, [target])
        assert payload["blocked"][0]["reason"] == REASON


def test_manifest_reports_every_unpromoted_node_and_then_projects_once_promoted(bridge, tmp_path,
                                                                                monkeypatch, capsys):
    module, fake = bridge
    graph = write_graph(tmp_path, package_nodes({"F": UNPROMOTED["add-default"], "T05": UNPROMOTED["draft"]})[:-1])
    manifest = write_manifest(tmp_path)
    argv = ("--op", "create", "--repo-root", tmp_path, "--graph", graph, "--projection-manifest", manifest)
    code, payload = call(module, monkeypatch, capsys, *argv)
    # All targets are checked before any write: the epic, the draft child and the child missing from the graph.
    assert_blocked(code, payload, fake, ["F", "T05", "T13"])
    assert [row["reason"] for row in payload["blocked"]] == [REASON, REASON, "not in graph"]
    assert payload["blocked"][0]["state"] == {"confirmation_status": "draft", "evaluation_status": "pending",
                                              "implementation_readiness": "incomplete"}

    write_graph(tmp_path, package_nodes())
    code, payload = call(module, monkeypatch, capsys, *argv)
    assert code == 0 and payload["result"]["applied_count"] == 13
    assert [args[args.index("--type") + 1] for args in fake.creates()] == ["epic", *["task"] * 13]


@pytest.mark.parametrize("variant", sorted(UNPROMOTED))
def test_github_and_beads_paths_share_one_gate(bridge, tmp_path, monkeypatch, capsys, variant):
    module, fake = bridge
    projection = load("build-github-projection.py", "build_github_projection_promotion_gate")
    github_node = {**node("G1", "task", UNPROMOTED[variant]), "tracker_binding": "github",
                   "github_publication": {"mode": "issue", "project_aliases": []}}
    targets, skipped = projection.plan([github_node], {"projects": []})
    assert targets == [] and skipped == [{"graph_node_id": "G1", "reason": REASON}]
    graph = write_graph(tmp_path, [github_node])
    code, payload = call(module, monkeypatch, capsys, "--op", "create", "--repo-root", tmp_path, "--graph", graph,
                         "--graph-node-id", "G1", "--title", "T")
    assert_blocked(code, payload, fake, ["G1"])
    assert payload["blocked"][0]["reason"] == skipped[0]["reason"]


def write_fake_bd(directory: Path) -> Path:
    script = directory / "fake-bd"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['FAKE_BD_LOG'], 'a', encoding='utf-8') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "args = sys.argv[1:]\n"
        "if args == ['version']: print('bd version 1.4.2')\n"
        "elif args == ['where', '--json']: print(json.dumps({'database_path': '/fake/beads.db', 'prefix': 'bd', 'schema_version': '1'}))\n"
        "elif args[0] in ('search', 'list'): print('[]')\n"
        "elif args[0] == 'create': print(json.dumps({'id': 'B01'}))\n"
        "else: sys.exit(9)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_cli_exits_nonzero_with_a_json_reason_and_no_bd_process(tmp_path):
    log = tmp_path / "bd-calls.jsonl"
    env = {**os.environ, "DEV_GRAPH_BD": str(write_fake_bd(tmp_path)), "FAKE_BD_LOG": str(log)}
    graph = write_graph(tmp_path, [node("G1", "feature", UNPROMOTED["draft"])])
    argv = [sys.executable, str(SCRIPTS / "bd-bridge.py"), "--op", "create", "--repo-root", str(tmp_path),
            "--graph", str(graph), "--graph-node-id", "G1", "--title", "T", "--artifact-kind", "feature"]
    blocked = subprocess.run(argv, text=True, capture_output=True, env=env, check=False)
    assert blocked.returncode != 0
    assert json.loads(blocked.stdout)["blocked"] == [{
        "graph_node_id": "G1", "reason": REASON,
        "state": {"confirmation_status": "draft", "evaluation_status": "pass", "implementation_readiness": "complete"},
    }]
    assert not log.exists()

    write_graph(tmp_path, [node("G1", "feature", PROMOTED)])
    created = subprocess.run(argv, text=True, capture_output=True, env=env, check=False)
    assert created.returncode == 0, created.stderr
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [args for args in calls if args[0] == "create"] == [[
        "create", "--title", "T", "--description", "", "--external-ref", "dev-graph:G1", "--type", "epic", "--json"]]
