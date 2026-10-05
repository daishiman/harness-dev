"""C14 binding=github publication: one Issue and one Project item per task, failures retried from pending_retry only.

The graph is registered by the real C02 register-package (the local batch), then build-github-projection runs
against a stateful fake gh (DEV_GRAPH_GH) that logs every call and can fail one mutation on demand.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import test_register_package as base

PROJECTION = base.PLUGIN / "scripts" / "build-github-projection.py"
PROJECT = {"id": "PVT_roadmap", "title": "Roadmap", "fields": {"nodes": [
    {"id": "PVTF_title", "name": "Title"},
    {"id": "PVTSSF_status", "name": "Status", "options": [{"id": "opt_todo", "name": "Todo"},
                                                         {"id": "opt_progress", "name": "In Progress"}]},
]}}
GITHUB = {
    "enabled": True, "issue_repository": "o/r",
    "projects": [{
        "alias": "roadmap", "owner_type": "user", "owner_login": "o", "project_number": 7, "default": True,
        "auto_add": {"artifact_kinds": ["task"], "confirmation_status": "confirmed", "evaluation_status": "pass",
                     "implementation_readiness": "complete"},
        "field_mappings": [{"local_field": "status", "project_field_name": "Status", "value_type": "single_select",
                            "direction": "local_to_project", "option_map": {"active": "In Progress"}}],
    }],
}
FAKE_GH = r'''
import json, os, sys
argv = sys.argv[1:]
path = os.environ["FAKE_GH_STATE"]
state = json.load(open(path))
state["calls"].append(argv)
def save(): json.dump(state, open(path, "w"))
def opt(flag): return argv[argv.index(flag) + 1]
def out(value): save(); print(json.dumps(value)); sys.exit(0)
def fail_if(op, key):
    for rule in state["fail"]:
        if rule["op"] == op and rule["key"] == key and rule["times"] > 0:
            rule["times"] -= 1; save(); sys.stderr.write(f"injected {op} failure for {key}\n"); sys.exit(1)
if argv[:2] == ["issue", "list"]:
    out(state["issues"])
if argv[:2] == ["issue", "create"]:
    fail_if("issue-create", opt("--title"))
    n = len(state["issues"]) + 1
    state["issues"].append({"id": f"I_{n}", "number": n, "title": opt("--title"), "body": opt("--body"),
                            "state": "OPEN", "url": f"https://github.com/o/r/issues/{n}", "updatedAt": "2026-10-05T00:00:00Z"})
    save(); print(f"https://github.com/o/r/issues/{n}"); sys.exit(0)
if argv[:2] == ["issue", "view"]:
    out(next(i for i in state["issues"] if i["number"] == int(argv[2].rsplit("/", 1)[-1])))
if argv[:2] == ["api", "graphql"]:
    query = opt("-f").removeprefix("query=")
    var = dict(argv[i + 1].split("=", 1) for i, a in enumerate(argv) if a == "-F")
    if "addProjectV2ItemById" in query:
        fail_if("project-item-add", var["content"])
        item = {"id": f"PVTI_{len(state['items']) + 1}", "project": var["project"], "content": var["content"], "fields": {}}
        state["items"].append(item)
        out({"data": {"addProjectV2ItemById": {"item": {"id": item["id"]}}}})
    if "updateProjectV2ItemFieldValue" in query:
        fail_if("project-item-edit", var["item"])
        next(i for i in state["items"] if i["id"] == var["item"])["fields"][var["field"]] = var["option"]
        out({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": var["item"]}}}})
    if "items(first:100" in query:
        nodes = [{"id": i["id"], "content": {"id": i["content"]}} for i in state["items"] if i["project"] == var["id"]]
        out({"data": {"node": {"items": {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}}})
    if "projectV2(number" in query:
        out({"data": {"user": {"projectV2": state["project"]}, "organization": None}})
sys.stderr.write(f"unexpected gh call: {argv}\n"); sys.exit(9)
'''


def mutations(calls: list[list[str]]) -> dict[str, int]:
    graphql = [" ".join(call) for call in calls if call[:2] == ["api", "graphql"]]
    return {"issue-create": sum(call[:2] == ["issue", "create"] for call in calls),
            "project-item-add": sum("addProjectV2ItemById" in call for call in graphql),
            "project-item-edit": sum("updateProjectV2ItemFieldValue" in call for call in graphql)}


class GithubProjectionTest(unittest.TestCase):
    """Reuses the register-package fixture (feature + exact-13 package) without re-running its tests."""

    write = staticmethod(base.RegisterPackageTest.write)
    invoke = base.RegisterPackageTest.invoke
    tearDown = base.RegisterPackageTest.tearDown

    def setUp(self) -> None:
        base.RegisterPackageTest.setUp(self)
        registration = json.loads(self.registration.read_text())
        for node in registration["nodes"]:
            node["github_publication"].update(mode="issue_and_projects", project_aliases=[])
        self.write(self.registration, registration)
        self.write(self.config, {"execution_tracker": {"mode": "github"}, "github": GITHUB,
                                 "local_state": {"graph": self.output.name, "cache": "cache", "locks": "locks"}})
        registered = self.invoke()
        self.assertEqual(registered.returncode, 0, registered.stdout + registered.stderr)
        self.state_path = self.root / "fake-gh-state.json"
        self.write(self.state_path, {"issues": [], "items": [], "project": PROJECT, "fail": [], "calls": []})
        fake = self.root / "fake_gh.py"
        fake.write_text(FAKE_GH, encoding="utf-8")
        self.gh = self.root / "gh"
        self.gh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n', encoding="utf-8")
        self.gh.chmod(0o755)

    def state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def project(self, *extra: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "DEV_GRAPH_GH": str(self.gh), "FAKE_GH_STATE": str(self.state_path)}
        return subprocess.run([sys.executable, str(PROJECTION), "--repo-root", str(self.root), *extra],
                              text=True, capture_output=True, check=False, env=env)

    def test_out2_out5_failed_item_add_retries_alone_and_reruns_keep_one_issue_and_item(self) -> None:
        """OUT5: local batch 成功後に P05 の item-add だけ失敗 → graph 不変・pending_retry 1 件 → retry は add/edit 各 1 回だけ。
        OUT2: 3 回目の通常実行は mutation 0 件で、marker ごとの Issue と content ごとの item が各 1 つのまま。"""
        graph = self.output.read_bytes()
        state = self.state()
        state["fail"] = [{"op": "project-item-add", "key": "I_5", "times": 1}]
        self.write(self.state_path, state)

        first = self.project("--report", "projection-report.json")
        self.assertEqual(first.returncode, 3, first.stdout + first.stderr)
        report = json.loads(first.stdout)
        self.assertEqual([(r["graph_node_id"], r["project_alias"], r["operation"]) for r in report["pending_retry"]],
                         [("task-P05", "roadmap", "project-item-add")])
        self.assertEqual(mutations(self.state()["calls"]), {"issue-create": 13, "project-item-add": 13, "project-item-edit": 12})
        p05 = next(e for e in report["projected"] if e["graph_node_id"] == "task-P05")
        self.assertEqual(p05["linkage_proposal"]["issue_linkage"]["issue_number"], 5)
        self.assertEqual(p05["linkage_proposal"]["github_project_linkages"][0]["sync_state"], "pending_retry")
        self.assertEqual(self.output.read_bytes(), graph)
        self.assertFalse(report["graph_written"])

        before = len(self.state()["calls"])
        retry = self.project("--retry-from", "projection-report.json", "--report", "retry-report.json")
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        retry_calls = self.state()["calls"][before:]
        self.assertEqual(mutations(retry_calls), {"issue-create": 0, "project-item-add": 1, "project-item-edit": 1})
        finds = [c for c in retry_calls if c[:2] == ["api", "graphql"] and "items(first:100" in " ".join(c)]
        self.assertEqual(len(finds), 1)
        self.assertEqual([r["graph_node_id"] for r in json.loads(retry.stdout)["projected"]], ["task-P05"])

        before = len(self.state()["calls"])
        rerun = self.project()
        self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
        self.assertEqual(mutations(self.state()["calls"][before:]), {"issue-create": 0, "project-item-add": 0, "project-item-edit": 0})
        final = self.state()
        markers = [line for issue in final["issues"] for line in issue["body"].splitlines() if line.startswith("<!-- dev-graph:")]
        self.assertEqual(sorted(markers), sorted(f"<!-- dev-graph:task-{p} -->" for p in base.PHASES))
        self.assertEqual(sorted(i["content"] for i in final["items"]), sorted(i["id"] for i in final["issues"]))
        self.assertEqual({i["fields"].get("PVTSSF_status") for i in final["items"]}, {"opt_progress"})
        self.assertEqual(self.output.read_bytes(), graph)

    def test_out3_dry_run_previews_every_projection_without_a_write(self) -> None:
        graph = self.output.read_bytes()
        result = self.project("--dry-run", "--report", "dry-report.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        planned = [row["operation"] for row in json.loads(result.stdout)["planned_mutations"]]
        self.assertEqual({op: planned.count(op) for op in set(planned)},
                         {"issue-create": 13, "project-item-add": 13, "project-item-edit": 13})
        self.assertEqual(mutations(self.state()["calls"]), {"issue-create": 0, "project-item-add": 0, "project-item-edit": 0})
        self.assertEqual(self.output.read_bytes(), graph)
        self.assertFalse((self.root / "dry-report.json").exists())

    def test_out4_conflicts_and_duplicate_markers_fail_closed_before_any_gh_write(self) -> None:
        """OUT4 (投影段): github+local_only・beads+Issue publication は gh を一度も呼ばず、marker 重複は mutation 0 件で止まる。"""
        original = self.output.read_bytes()
        for name, binding, mode in (("github+local_only", "github", "local_only"), ("beads+Issue publication", "beads", "issue")):
            with self.subTest(name):
                graph = json.loads(original)
                graph["nodes"][1].update(tracker_binding=binding)
                graph["nodes"][1]["github_publication"]["mode"] = mode
                self.write(self.output, graph)
                result = self.project()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("publication authority conflict", result.stderr)
                self.assertEqual(self.state()["calls"], [])
        self.output.write_bytes(original)
        state = self.state()
        state["issues"] = [{"id": f"I_{n}", "number": n, "title": "dup", "body": "<!-- dev-graph:task-P01 -->",
                            "state": "OPEN", "url": f"https://github.com/o/r/issues/{n}", "updatedAt": None} for n in (1, 2)]
        self.write(self.state_path, state)
        result = self.project()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("2 Issues carry the same dev-graph marker", result.stderr)
        self.assertEqual(mutations(self.state()["calls"]), {"issue-create": 0, "project-item-add": 0, "project-item-edit": 0})


if __name__ == "__main__":
    unittest.main()
