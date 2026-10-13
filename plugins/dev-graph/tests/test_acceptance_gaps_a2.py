"""受入ギャップ A2: run-dev-graph-status IN1/OUT2 と run-dev-graph-sync OUT3/OUT8 を、script を実際に起動して確かめる。

- status: extract-graph-status.py (中で C24 resolve-repo-context --mode read と C11 validate-graph-schema を通す) を、
  実際の C02 writer (build-graph-node) が作った graph に対して起動する。検索の行・必須キー欠落 0 件・C02 の状態遷移への
  追従・診断付きの失敗・書込み 0 を、script の出力と手で書いた期待値の照合で確かめる。
- sync OUT3: diff-github-issues が fake gh (DEV_GRAPH_GH) から Issue を読み、その計画を C02 update と gh-bridge で適用する。
  削除 (number が解決しない) は C02 update の status=tombstoned の計画になり、当てた後の再計画が収束する。一時的な失敗
  (rate limit・5xx) は retry、権限や repository の失敗は investigate として残り、どちらも tombstone にしない。
- sync OUT8: register-package が昇格させた exact-13 task に対し、権限・rate limit・field 削除・option 改名・ページ分割を
  注入する fake gh で build-github-projection (C14) を起動する。C03 の Projects planner は pending_retry と壊れた
  field を書かずに残すことも確かめる。

実際の GitHub・Beads・network は使わない。fixture はすべて一時ディレクトリに作る。
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_build_graph_node as nodes_base
import test_register_package as package_base
from test_build_github_projection import GITHUB as PROJECTION_GITHUB, PROJECT as PROJECTION_PROJECT, mutations

SCRIPTS = nodes_base.PLUGIN / "scripts"
RESOLVE = SCRIPTS / "resolve-repo-context.py"
VALIDATOR = SCRIPTS / "validate-graph-schema.py"
WRITER = SCRIPTS / "build-graph-node.py"
ISSUES = SCRIPTS / "diff-github-issues.py"
FIELDS = SCRIPTS / "diff-github-project-fields.py"
BRIDGE = SCRIPTS / "gh-bridge.py"
PROJECTION = SCRIPTS / "build-github-projection.py"
EARLIER, LATER = nodes_base.EARLIER, nodes_base.LATER
NO_MUTATION = {"issue-create": 0, "project-item-add": 0, "project-item-edit": 0}
PERMISSION = "GraphQL: Resource not accessible by integration (HTTP 403)"
RATE_LIMIT = "GraphQL: API rate limit exceeded for user ID 1. (HTTP 429)"
STATUS = SCRIPTS / "extract-graph-status.py"
# run-dev-graph-status の report の列。script の REPORT_KEYS を読まず、SKILL.md の列から独立に書く。
STATUS_COLUMNS = {"graph_node_id", "artifact_kind", "title", "project_id", "domain", "tags", "file_path", "status",
                  "closed_at", "depends_on", "dependents", "parent_feature", "feature_package_id", "tracker_binding",
                  "issue_linkage", "beads_linkage", "github_project_linkages"}


def tree_digest(root: Path) -> dict[str, tuple[str, int]]:
    """root 以下 (.git を含む) の全 entry の内容 hash と mtime。同じ bytes の書き直しも mtime で見分ける。"""
    entries: dict[str, tuple[str, int]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries[relative] = ("link:" + os.readlink(path), 0)
        elif path.is_dir():
            entries[relative] = ("dir", 0)
        else:
            entries[relative] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
    return entries


def freeze(root: Path) -> dict[Path, int]:
    """root 以下の書込み権限を外す。書込みを試みる script は黙って成功できず、失敗として表に出る。"""
    modes = {path: path.stat().st_mode for path in (root, *root.rglob("*")) if not path.is_symlink()}
    for path, mode in modes.items():
        path.chmod(mode & ~0o222)
    return modes


def thaw(modes: dict[Path, int]) -> None:
    for path, mode in modes.items():
        path.chmod(mode)


def stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


class C02Fixture:
    """test_build_graph_node の C02 fixture (git repo・config・graph) と helper を、その test を再実行せずに借りる。"""

    _base = nodes_base.BuildGraphNodeTest
    write_input = _base.write_input
    pinned = _base.pinned
    run_cli = _base.run_cli
    graph_state = _base.graph_state
    validate = _base.validate
    set_tracker_mode = _base.set_tracker_mode
    mark_passed = _base.mark_passed
    published_issue = _base.published_issue
    linked_issue = _base.linked_issue
    pub_node = _base.pub_node
    reconcile = _base.reconcile
    apply_plan = _base.apply_plan

    def setUp(self) -> None:
        self._base.setUp(self)
        self.outside = tempfile.TemporaryDirectory()  # stub と fake gh の置き場所 (repo の digest に入れない)
        self.side = Path(self.outside.name).resolve()

    def tearDown(self) -> None:
        self.outside.cleanup()
        self._base.tearDown(self)

    def node(self, graph_node_id: str) -> dict:
        return next(item for item in self.graph_state()["nodes"] if item["graph_node_id"] == graph_node_id)

    def assert_valid(self) -> None:
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# --------------------------------------------------------------------------------------------- run-dev-graph-status


class StatusReadOnlyTest(C02Fixture, unittest.TestCase):
    """IN1 と OUT2: status skill の script 閉包を、C02 だけで作った graph に対して起動する。"""

    def setUp(self) -> None:
        super().setUp()
        self.calls = self.side / "calls.log"
        bin_dir = self.side / "bin"
        bin_dir.mkdir()
        for name in ("gh", "bd"):  # 呼ばれたら argv を残して失敗する。status は GitHub も Beads も呼ばない。
            stub(bin_dir / name, f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "{self.calls}"\nexit 97\n')
        self.tool_env = {**self.env, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                         "DEV_GRAPH_GH": str(bin_dir / "gh")}

    def build_status_graph(self) -> None:
        """GitHub に link 済みの issue、close した issue、tombstone にした document、その 2 つの issue に依存する task。"""
        self.linked_issue()  # issue-pub: tracker_binding=github, acme/web#12
        artifacts = [
            {**nodes_base.BASE, "artifact_kind": "issue", "slug": "login-timeout", "title": "Login timeout",
             "classification": nodes_base.candidates("issue"), "sections": nodes_base.filled("issue")},
            {**nodes_base.BASE, "artifact_kind": "task", "slug": "fix-timeout", "title": "Fix timeout",
             "tags": ["auth", "timeout"], "classification": nodes_base.candidates("task")},
            {**nodes_base.BASE, "artifact_kind": "document", "slug": "runbook", "title": "Runbook",
             "classification": nodes_base.candidates("document")},
        ]
        code, report = self.run_cli("add", {"artifacts": artifacts})
        self.assertEqual(code, 0, report)
        code, report = self.run_cli("update", {"updates": [
            {"graph_node_id": "task-fix-timeout", "node_patch": {"depends_on": ["issue-login-timeout", "issue-pub"]}},
            {"graph_node_id": "issue-login-timeout", "node_patch": {"status": "closed"}},
            {"graph_node_id": "doc-runbook", "node_patch": {"status": "tombstoned"}}]})
        self.assertEqual(code, 0, report)

    def read_status(self, *filters: str) -> tuple[int, dict]:
        """skill の配線どおり extract-graph-status.py を起動する。C24 と C11 は script の中で通る。"""
        cp = subprocess.run([sys.executable, str(STATUS), "--repo-root", str(self.root), *filters],
                            text=True, capture_output=True, env=self.tool_env, cwd=self.root, check=False)
        return cp.returncode, (json.loads(cp.stdout) if cp.stdout.strip() else {"stderr": cp.stderr})

    def ids(self, *filters: str) -> list[str]:
        code, report = self.read_status(*filters)
        self.assertEqual(code, 0, report)
        return [row["graph_node_id"] for row in report["rows"]]

    def test_in1_status_rows_carry_every_column_with_missing_keys_0_and_follow_the_c02_state(self) -> None:
        self.build_status_graph()
        code, report = self.read_status()
        self.assertEqual(code, 0, report)
        self.assertEqual((report["validation"]["status"], report["validation"]["violations"], report["missing_required_keys"]),
                         ("pass", [], []))
        self.assertEqual((report["result"], report["count"], report["read_only"]["changed"]), ("matched", 4, []))
        rows = {row["graph_node_id"]: row for row in report["rows"]}
        self.assertEqual(list(rows), ["doc-runbook", "issue-login-timeout", "issue-pub", "task-fix-timeout"])
        for row in rows.values():  # 全行が report の全列を持つ (欠落 0 件)
            self.assertEqual(set(row), STATUS_COLUMNS, row["graph_node_id"])
            self.assertTrue((self.root / row["file_path"]).is_file(), row["graph_node_id"])
        closed, tombstoned = rows["issue-login-timeout"], rows["doc-runbook"]
        task, published = rows["task-fix-timeout"], rows["issue-pub"]
        # close と tombstone は C02 が付けた closed_at と一緒に残り、依存先からは dependents として逆引きできる。
        self.assertEqual((closed["artifact_kind"], closed["status"], closed["file_path"], closed["dependents"]),
                         ("issue", "closed", "issues/login-timeout.md", ["task-fix-timeout"]))
        self.assertEqual((tombstoned["artifact_kind"], tombstoned["status"], tombstoned["dependents"]), ("document", "tombstoned", []))
        self.assertTrue(closed["closed_at"] and tombstoned["closed_at"])
        self.assertEqual((task["status"], task["closed_at"], task["depends_on"], task["tags"], task["dependents"]),
                         ("draft", None, ["issue-login-timeout", "issue-pub"], ["auth", "timeout"], []))
        self.assertEqual((published["tracker_binding"], published["issue_linkage"]["repo"],
                          published["issue_linkage"]["issue_number"], published["dependents"]),
                         ("github", "acme/web", 12, ["task-fix-timeout"]))
        self.assertEqual({(row["project_id"], row["domain"], row["parent_feature"], row["feature_package_id"]) for row in rows.values()},
                         {("web", "auth", None, None)})
        # 検索: filter はすべて AND、同じ filter の繰り返しは OR、複数 tag は明示の match mode に従う。該当なしは空の成功。
        self.assertEqual(self.ids("--kind", "issue"), ["issue-login-timeout", "issue-pub"])
        self.assertEqual(self.ids("--kind", "issue", "--status", "closed"), ["issue-login-timeout"])
        self.assertEqual(self.ids("--status", "closed", "--status", "tombstoned"), ["doc-runbook", "issue-login-timeout"])
        self.assertEqual(self.ids("--project", "web", "--domain", "auth", "--kind", "task"), ["task-fix-timeout"])
        self.assertEqual(self.ids("--id", "issue-pub", "--id", "doc-runbook"), ["doc-runbook", "issue-pub"])
        self.assertEqual(self.ids("--keyword", "RUNBOOK"), ["doc-runbook"])
        self.assertEqual(self.ids("--tag", "timeout", "--tag", "billing", "--tag-mode", "any"), ["task-fix-timeout"])
        self.assertEqual(self.ids("--tag", "timeout", "--tag", "auth", "--tag-mode", "all"), ["task-fix-timeout"])
        code, empty = self.read_status("--tag", "timeout", "--tag", "billing", "--tag-mode", "all")
        self.assertEqual((code, empty["result"], empty["rows"], empty["count"]), (0, "empty", [], 0))
        self.assertEqual(self.read_status("--kind", "issue", "--domain", "billing")[1]["result"], "empty")
        code, usage = self.read_status("--tag", "timeout", "--tag", "auth")  # match mode を推測しない
        self.assertEqual(code, 2)
        self.assertIn("--tag-mode", usage["stderr"])
        # 表示は cache ではなく graph の実状態に追従する: C02 で task を blocked にした後の再読込はその値を返し、他の行は動かない。
        code, applied = self.run_cli("update", {"updates": [{"graph_node_id": "task-fix-timeout", "node_patch": {"status": "blocked"}}]})
        self.assertEqual(code, 0, applied)
        code, after = self.read_status()
        self.assertEqual(code, 0, after)
        moved = {row["graph_node_id"]: row for row in after["rows"]}
        self.assertEqual(moved["task-fix-timeout"], {**task, "status": "blocked"})
        self.assertEqual({key: row for key, row in moved.items() if key != "task-fix-timeout"},
                         {key: row for key, row in rows.items() if key != "task-fix-timeout"})
        self.assertNotEqual(after["graph"]["digest"], report["graph"]["digest"])
        self.assertFalse(self.calls.exists())

    def test_in1_missing_key_dangling_dependency_and_outside_path_fail_with_diagnostics_and_no_rows(self) -> None:
        self.build_status_graph()
        valid = self.graph.read_bytes()

        def escape_by_symlink(node: dict) -> None:
            """kind の root 配下に見えるが、実体は repo の外にある Markdown を指す。"""
            inside = self.root / node["file_path"]
            outside = self.side / "outside.md"
            outside.write_bytes(inside.read_bytes())
            link = inside.with_name("escape.md")
            link.symlink_to(outside)
            node["file_path"] = link.relative_to(self.root).as_posix()

        cases = {
            "required key missing": ("task-fix-timeout", lambda node: node.pop("status")),
            "linkage key missing": ("issue-pub", lambda node: node.pop("issue_linkage")),
            "dangling dependency": ("task-fix-timeout", lambda node: node.update(depends_on=["issue-ghost"])),
            "file_path with ..": ("doc-runbook", lambda node: node.update(file_path="../outside/runbook.md")),
            "file_path escaping by symlink": ("doc-runbook", escape_by_symlink),
        }
        found = {}
        for name, (graph_node_id, damage) in cases.items():
            with self.subTest(name):
                graph = json.loads(valid)
                damage(next(node for node in graph["nodes"] if node["graph_node_id"] == graph_node_id))
                self.graph.write_text(json.dumps(graph), encoding="utf-8")
                code, report = self.read_status()
                self.assertEqual(code, 1, report)
                self.assertEqual((report["result"], report["rows"], report["count"], report["validation"]["status"]),
                                 ("rejected", [], 0, "fail"))
                found[name] = (report, {(item["node"], item["code"]) for item in report["validation"]["violations"]})
        self.graph.write_bytes(valid)
        report, codes = found["required key missing"]
        self.assertIn(("task-fix-timeout", "invalid_status"), codes)
        self.assertEqual(report["missing_required_keys"], [{"graph_node_id": "task-fix-timeout", "key": "status"}])
        self.assertEqual(found["linkage key missing"][0]["missing_required_keys"], [{"graph_node_id": "issue-pub", "key": "issue_linkage"}])
        self.assertIn(("task-fix-timeout", "dangling_dependency"), found["dangling dependency"][1])
        self.assertIn(("doc-runbook", "path_parity_error"), found["file_path with .."][1])
        self.assertIn(("doc-runbook", "artifact_path_invalid"), found["file_path escaping by symlink"][1])
        self.assertFalse(self.calls.exists())

    def test_out2_status_closure_writes_nothing_and_calls_no_github_or_beads_even_when_it_fails(self) -> None:
        self.build_status_graph()
        issue_before = self.node("issue-pub")
        for name, graph_bytes, expected in (("valid graph", None, 0), ("dangling dependency", "issue-ghost", 1)):
            with self.subTest(name):
                if graph_bytes is not None:
                    graph = self.graph_state()
                    next(node for node in graph["nodes"] if node["graph_node_id"] == "task-fix-timeout")["depends_on"] = [graph_bytes]
                    self.graph.write_text(json.dumps(graph), encoding="utf-8")
                before = tree_digest(self.root)
                modes = freeze(self.root)  # 書込みを試みれば PermissionError として失敗に出る
                try:
                    code, report = self.read_status()
                finally:
                    thaw(modes)
                self.assertEqual(code, expected, report)
                self.assertEqual(report["read_only"]["changed"], [])
                self.assertEqual(tree_digest(self.root), before)  # graph・config・content・.git の bytes と mtime が同じ
                self.assertFalse(self.calls.exists())  # gh (Issue 側) と bd は一度も呼ばれていない
        self.assertEqual(self.node("issue-pub")["issue_linkage"], issue_before["issue_linkage"])
        for script in (STATUS, RESOLVE, VALIDATOR):  # 閉包の宣言も同じ: network なし、書込み先なし
            header = script.read_text(encoding="utf-8").split("# ///", 2)[1]
            self.assertIn("# network: false", header)
            self.assertIn("# write-scope: none", header)


# ------------------------------------------------------------------------------------------ run-dev-graph-sync OUT3

FAKE_ISSUE_GH = r'''
import json, os, sys
argv = sys.argv[1:]
path = os.environ["FAKE_GH_STATE"]
state = json.load(open(path))
state["calls"].append(argv)
def save(): json.dump(state, open(path, "w"))
issue = state["issues"].get(argv[2]) if len(argv) > 2 else None
if argv[:2] == ["issue", "view"]:
    save()
    if argv[2] in state.get("fail", {}):  # 削除以外の失敗 (rate limit・5xx・権限) を gh の stderr のまま注入する
        sys.stderr.write(state["fail"][argv[2]] + "\n"); sys.exit(1)
    if issue is None:
        sys.stderr.write(f"GraphQL: Could not resolve to an issue or pull request with the number of {argv[2]}. (repository.issue)\n"); sys.exit(1)
    print(json.dumps({"id": f"I_{argv[2]}", "number": int(argv[2]), "url": f"https://github.com/acme/web/issues/{argv[2]}", **issue})); sys.exit(0)
if argv[:2] == ["issue", "close"] and issue is not None:
    issue.update(state="CLOSED", updatedAt=state["clock"]); save(); sys.exit(0)
save(); sys.stderr.write(f"unexpected gh call: {argv}\n"); sys.exit(9)
'''


class SyncIssueTombstoneTest(C02Fixture, unittest.TestCase):
    """OUT3: Issue の close / 削除と local の close / tombstone を、実際の C03 Issue planner・C02 update・gh-bridge で往復させる。"""

    def setUp(self) -> None:
        super().setUp()
        self.linked_issue()  # issue-pub (title "I") は acme/web#12 に link 済み
        self.state_path = self.side / "issues.json"
        fake = self.side / "fake_gh.py"
        fake.write_text(FAKE_ISSUE_GH, encoding="utf-8")
        gh = stub(self.side / "gh", f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
        self.gh_env = {**self.env, "DEV_GRAPH_GH": str(gh), "FAKE_GH_STATE": str(self.state_path)}
        self.remote({"12": {"title": "I", "state": "OPEN", "updatedAt": EARLIER}})

    def remote(self, issues: dict, fail: dict | None = None) -> None:
        self.state_path.write_text(json.dumps({"issues": issues, "fail": fail or {}, "clock": LATER, "calls": []}),
                                   encoding="utf-8")

    def remote_state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def sync_plan(self) -> dict:
        """--remote を渡さず、planner 自身に gh-bridge issue-fetch で Issue を読ませる。"""
        cp = subprocess.run([sys.executable, str(ISSUES), "--repo-root", str(self.root)],
                            text=True, capture_output=True, env=self.gh_env, check=False)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        return json.loads(cp.stdout)

    def assert_kept(self, status: str) -> dict:
        """node は物理削除されず、同じ id・同じ file・同じ Issue link のまま status と closed_at だけが動く。"""
        graph = self.graph_state()
        self.assertEqual(sorted(node["graph_node_id"] for node in graph["nodes"]), ["issue-pub"])
        node = graph["nodes"][0]
        self.assertEqual((node["status"], node["issue_linkage"]["repo"], node["issue_linkage"]["issue_number"]),
                         (status, "acme/web", 12))
        self.assertTrue(node["closed_at"])
        self.assertTrue((self.root / node["file_path"]).is_file())
        self.assert_valid()
        return node

    def test_out3_github_close_is_imported_as_status_closed_and_the_node_is_kept(self) -> None:
        self.remote({"12": {"title": "I", "state": "CLOSED", "updatedAt": LATER}})
        plan = self.sync_plan()
        self.assertEqual([(row["field"], row["kind"], row["node_patch"]) for row in plan["imports"]],
                         [("state", "remote-newer", {"status": "closed"})])
        self.assertEqual((plan["exports"], plan["missing_issues"]), ([], []))
        self.apply_plan(plan)  # C02 update
        self.assert_kept("closed")
        again = self.sync_plan()
        self.assertEqual((again["converged"], again["changes"], again["next"]), (True, 0, "converged"))
        self.assertEqual({tuple(call[:2]) for call in self.remote_state()["calls"]}, {("issue", "view")})  # 計画は読むだけ

    def test_out3_local_tombstone_is_exported_as_issue_close_and_both_sides_converge(self) -> None:
        code, report = self.run_cli("update", {"updates": [{"graph_node_id": "issue-pub", "node_patch": {"status": "tombstoned"}}]})
        self.assertEqual(code, 0, report)
        plan = self.sync_plan()
        self.assertEqual([(row["field"], row["kind"], row["local"], row["bridge_args"]) for row in plan["exports"]],
                         [("state", "local-newer", "closed", ["--op", "issue-close", "--repo", "acme/web", "--number", "12"])])
        self.assertEqual((plan["imports"], plan["update_input"]), ([], None))
        for row in plan["exports"]:  # 計画の bridge_args をそのまま gh-bridge に渡す (dry-run ではない)
            cp = subprocess.run([sys.executable, str(BRIDGE), *row["bridge_args"]], text=True, capture_output=True,
                                env=self.gh_env, check=False)
            self.assertEqual(cp.returncode, 0, cp.stderr)
        remote = self.remote_state()
        self.assertEqual(remote["issues"]["12"]["state"], "CLOSED")
        self.assertIn(["issue", "close", "12", "--repo", "acme/web"], remote["calls"])
        self.assert_kept("tombstoned")
        again = self.sync_plan()
        self.assertEqual((again["converged"], again["changes"], again["next"]), (True, 0, "converged"))

    def test_out3_deleted_issue_is_planned_as_a_c02_tombstone_and_the_replan_converges(self) -> None:
        self.remote({})  # Issue #12 は GitHub から削除された (gh は "Could not resolve to an issue ... number of 12" で失敗する)
        graph = self.graph.read_bytes()
        plan = self.sync_plan()
        # 削除は再試行ではなく、既存の C02 update で status=tombstoned にする計画になる。node は消さない。
        self.assertEqual([(row["graph_node_id"], row["kind"], row["local"], row["remote"], row["node_patch"])
                          for row in plan["imports"]],
                         [("issue-pub", "remote-deleted", "draft", "deleted", {"status": "tombstoned"})])
        self.assertIn("Could not resolve to an issue", plan["imports"][0]["error"])
        self.assertEqual(plan["update_input"]["updates"], [{"graph_node_id": "issue-pub", "node_patch": {"status": "tombstoned"}}])
        self.assertEqual((plan["exports"], plan["missing_issues"], plan["counts"]["tombstones"], plan["converged"], plan["next"]),
                         ([], [], 1, False, "apply exports and imports, then plan again"))
        self.assertEqual(self.graph.read_bytes(), graph)  # 計画は何も書かない
        # C02 には物理削除の動詞が無い。削除相当は update の status=tombstoned で表す (R4-tombstone)。
        delete = subprocess.run([sys.executable, str(WRITER), "delete", "--repo-root", str(self.root), "--input", "x.json"],
                                text=True, capture_output=True, env=self.env, check=False)
        self.assertEqual(delete.returncode, 2)
        self.assertIn("invalid choice", delete.stderr)
        self.apply_plan(plan)  # 計画の update_input をそのまま C02 update に渡す
        self.assert_kept("tombstoned")
        # tombstone を当てた後の再計画は、missing を残さずに収束する。Issue を作り直したり close したりもしない。
        graph = self.graph.read_bytes()
        again = self.sync_plan()
        self.assertEqual((again["missing_issues"], again["imports"], again["exports"], again["conflicts"], again["update_input"]),
                         ([], [], [], [], None))
        self.assertEqual((again["unresolved_count"], again["changes"], again["converged"], again["next"]), (0, 0, True, "converged"))
        self.assertEqual([(row["graph_node_id"], row["issue_number"], row["status"]) for row in again["deleted_issues"]],
                         [("issue-pub", 12, "tombstoned")])
        self.assertEqual(self.graph.read_bytes(), graph)
        self.assertEqual({tuple(call[:2]) for call in self.remote_state()["calls"]}, {("issue", "view")})

    def test_out3_rate_limit_and_server_errors_are_retried_and_never_tombstone(self) -> None:
        transient = {"rate limit (HTTP 429)": RATE_LIMIT,
                     "rate limit (HTTP 403)": "HTTP 403: API rate limit exceeded for installation ID 7. (https://api.github.com/graphql)",
                     "bad gateway (HTTP 502)": "HTTP 502: Bad Gateway (https://api.github.com/graphql)",
                     "service unavailable (HTTP 503)": "HTTP 503: Service Unavailable (https://api.github.com/graphql)"}
        graph = self.graph.read_bytes()
        for name, message in transient.items():
            with self.subTest(name):
                self.remote({"12": {"title": "I", "state": "OPEN", "updatedAt": EARLIER}}, fail={"12": message})
                plan = self.sync_plan()
                self.assertEqual([(row["graph_node_id"], row["issue_number"], row["error_class"], row["action"])
                                  for row in plan["missing_issues"]], [("issue-pub", 12, "transient", "retry")])
                self.assertIn(message, plan["missing_issues"][0]["error"])
                self.assertEqual((plan["imports"], plan["exports"], plan["update_input"], plan["deleted_issues"]), ([], [], None, []))
                self.assertEqual((plan["converged"], plan["next"]), (False, "retry missing Issues, then plan again"))
                self.assertEqual(self.graph.read_bytes(), graph)
        # 回復した後の再試行は、node を tombstone にせずそのまま収束する。
        self.remote({"12": {"title": "I", "state": "OPEN", "updatedAt": EARLIER}})
        again = self.sync_plan()
        self.assertEqual((again["missing_issues"], again["converged"], again["next"]), ([], True, "converged"))
        self.assertEqual((self.node("issue-pub")["status"], self.graph.read_bytes()), ("draft", graph))

    def test_out3_permission_and_unresolved_repository_errors_are_never_read_as_deletion(self) -> None:
        unclassified = {"permission (HTTP 403)": PERMISSION,
                        "unresolved repository": "GraphQL: Could not resolve to a Repository with the name 'acme/web'. (repository)",
                        "REST not found (HTTP 404)": "HTTP 404: Not Found (https://api.github.com/repos/acme/web/issues/12)",
                        "another Issue number": "GraphQL: Could not resolve to an issue or pull request with the number of 120. (repository.issue)"}
        graph = self.graph.read_bytes()
        for name, message in unclassified.items():
            with self.subTest(name):
                self.remote({"12": {"title": "I", "state": "OPEN", "updatedAt": EARLIER}}, fail={"12": message})
                plan = self.sync_plan()
                self.assertEqual([(row["graph_node_id"], row["error_class"], row["action"]) for row in plan["missing_issues"]],
                                 [("issue-pub", "unclassified", "investigate")])
                self.assertEqual((plan["imports"], plan["update_input"], plan["converged"], plan["next"]),
                                 ([], None, False, "check access to the missing Issues (R6), then plan again"))
                self.assertEqual(self.graph.read_bytes(), graph)

    def test_out3_deleted_issue_of_a_package_member_stays_a_local_authority_conflict(self) -> None:
        """C02 update は exact-13 package member を拒否するので、削除は tombstone 計画ではなく conflict として止まる。"""
        planner = importlib.util.module_from_spec(spec := importlib.util.spec_from_file_location("dev_graph_issues_a2", ISSUES))
        sys.path.insert(0, str(SCRIPTS))
        try:
            spec.loader.exec_module(planner)
        finally:
            sys.path.remove(str(SCRIPTS))
        node = {**self.node("issue-pub"), "feature_package_id": "FEATURE-1"}
        deleted = {"issues": {}, "errors": {"acme/web#12": "GraphQL: Could not resolve to an issue or pull request with the number of 12. (repository.issue)"}}
        plan = planner.plan({"graph_revision": 3, "nodes": [node]}, {}, deleted, {})
        self.assertEqual([(row["graph_node_id"], row["kind"], row["cause"]) for row in plan["conflicts"]],
                         [("issue-pub", "remote-deleted", "local-authority")])
        self.assertEqual((plan["imports"], plan["update_input"], plan["missing_issues"], plan["converged"]), ([], None, [], False))


# ------------------------------------------------------------------------------------------ run-dev-graph-sync OUT8

FAKE_PROJECT_GH = r'''
import json, os, sys
argv = sys.argv[1:]
path = os.environ["FAKE_GH_STATE"]
state = json.load(open(path))
state["calls"].append(argv)
def save(): json.dump(state, open(path, "w"))
def opt(flag): return argv[argv.index(flag) + 1]
def out(value): save(); print(json.dumps(value)); sys.exit(0)
def fail_if(op, key="*"):
    for rule in state["fail"]:
        if rule["op"] == op and rule["key"] in (key, "*") and rule["times"] > 0:
            rule["times"] -= 1; save(); sys.stderr.write(rule["message"] + "\n"); sys.exit(1)
if argv[:2] == ["issue", "list"]:
    fail_if("issue-list"); out(state["issues"])
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
        item = next(i for i in state["items"] if i["id"] == var["item"])
        fail_if("project-item-edit", item["content"])
        item["fields"][var["field"]] = var["option"]
        out({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": var["item"]}}}})
    if "items(first:100" in query:
        fail_if("project-item-find")
        nodes = [{"id": i["id"], "content": {"id": i["content"]}} for i in state["items"] if i["project"] == var["id"]]
        start, size = int(var.get("cursor") or 0), state["page_size"]
        more = start + size < len(nodes)
        out({"data": {"node": {"items": {"nodes": nodes[start:start + size],
                                         "pageInfo": {"hasNextPage": more, "endCursor": str(start + size) if more else None}}}}})
    if "projectV2(number" in query:
        fail_if("project-resolve")
        out({"data": {"user": {"projectV2": state["project"]}, "organization": None}})
sys.stderr.write(f"unexpected gh call: {argv}\n"); sys.exit(9)
'''


class ProjectionFailureRetryTest(unittest.TestCase):
    """OUT8 (C14): exact-13 promotion の後で Project write が途中失敗しても、graph は動かず、pending の write だけが再実行される。"""

    write = staticmethod(package_base.RegisterPackageTest.write)
    invoke = package_base.RegisterPackageTest.invoke
    tearDown = package_base.RegisterPackageTest.tearDown

    def setUp(self) -> None:
        package_base.RegisterPackageTest.setUp(self)
        registration = json.loads(self.registration.read_text())
        for node in registration["nodes"]:
            node["github_publication"].update(mode="issue_and_projects", project_aliases=[])
        self.write(self.registration, registration)
        self.write(self.config, {"execution_tracker": {"mode": "github"}, "github": PROJECTION_GITHUB,
                                 "local_state": {"graph": self.output.name, "cache": "cache", "locks": "locks"}})
        registered = self.invoke()  # C02 register-package: local の task promotion
        self.assertEqual(registered.returncode, 0, registered.stdout + registered.stderr)
        self.state_path = self.root / "fake-gh-state.json"
        # page_size 2: 13 item は 7 page に分かれ、後ろの page を読まなければ既存 item を見落として二重 add する。
        self.write(self.state_path, {"issues": [], "items": [], "project": PROJECTION_PROJECT, "fail": [], "calls": [], "page_size": 2})
        fake = self.root / "fake_gh.py"
        fake.write_text(FAKE_PROJECT_GH, encoding="utf-8")
        self.gh = stub(self.root / "gh", f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')

    def state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def change_state(self, **values: object) -> None:
        state = self.state()
        state.update(values)
        self.write(self.state_path, state)

    def project(self, *extra: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "DEV_GRAPH_GH": str(self.gh), "FAKE_GH_STATE": str(self.state_path)}
        return subprocess.run([sys.executable, str(PROJECTION), "--repo-root", str(self.root), *extra],
                              text=True, capture_output=True, check=False, env=env)

    def assert_promotion_kept(self, graph: bytes) -> None:
        """C14 は graph を書かない: exact-13 task の bytes も package key も binding も promotion 直後のまま。"""
        self.assertEqual(self.output.read_bytes(), graph)
        tasks = [node for node in json.loads(graph)["nodes"] if node["artifact_kind"] == "task"]
        self.assertEqual(sorted(node["phase_ref"] for node in tasks), package_base.PHASES)
        self.assertEqual({(node["parent_feature"], node["feature_package_id"], node["tracker_binding"]) for node in tasks},
                         {("feature-1", "feature-package/demo", "github")})

    def test_out8_failures_keep_the_promotion_and_only_pending_project_writes_are_retried(self) -> None:
        graph = self.output.read_bytes()
        # 途中失敗: P03 の item-add が権限不足、P07 の Status 編集が rate limit で落ちる。
        self.change_state(fail=[{"op": "project-item-add", "key": "I_3", "times": 1, "message": PERMISSION},
                                {"op": "project-item-edit", "key": "I_7", "times": 1, "message": RATE_LIMIT}])
        first = self.project("--report", "projection-report.json")
        self.assertEqual(first.returncode, 3, first.stdout + first.stderr)
        report = json.loads(first.stdout)
        self.assertEqual([(row["graph_node_id"], row["project_alias"], row["operation"], row["last_error_code"])
                          for row in report["pending_retry"]],
                         [("task-P03", "roadmap", "project-item-add", "gh_bridge_exit_1"),
                          ("task-P07", "roadmap", "project-item-edit", "gh_bridge_exit_1")])
        self.assertIn("HTTP 403", report["pending_retry"][0]["detail"])
        self.assertIn("HTTP 429", report["pending_retry"][1]["detail"])
        self.assertEqual(mutations(self.state()["calls"]), {"issue-create": 13, "project-item-add": 13, "project-item-edit": 12})
        links = {entry["graph_node_id"]: entry["linkage_proposal"]["github_project_linkages"][0] for entry in report["projected"]}
        self.assertEqual((links["task-P03"]["sync_state"], links["task-P03"]["item_id"]), ("pending_retry", None))
        self.assertEqual(links["task-P07"]["sync_state"], "pending_retry")
        self.assertTrue(links["task-P07"]["item_id"])
        self.assertEqual(sorted(node for node, link in links.items() if link["sync_state"] == "linked"),
                         [f"task-{phase}" for phase in package_base.PHASES if phase not in {"P03", "P07"}])
        self.assertFalse(report["graph_written"])
        self.assert_promotion_kept(graph)
        saved = (self.root / "projection-report.json").read_bytes()

        # retry の前段 (読取りと Project 構造の検証) で止まる失敗: mutation 0 件、graph 不変、pending は次の retry へ残る。
        fields = PROJECTION_PROJECT["fields"]["nodes"]
        without_status = {**PROJECTION_PROJECT, "fields": {"nodes": [field for field in fields if field["name"] != "Status"]}}
        renamed = copy.deepcopy(PROJECTION_PROJECT)
        next(option for field in renamed["fields"]["nodes"] for option in field.get("options", [])
             if option["name"] == "In Progress")["name"] = "Doing"
        cases = (
            ("issue list permission", {"fail": [{"op": "issue-list", "key": "*", "times": 1, "message": PERMISSION}]}, "HTTP 403"),
            ("project resolve rate limit", {"fail": [{"op": "project-resolve", "key": "*", "times": 1, "message": RATE_LIMIT}]}, "HTTP 429"),
            ("Status field deleted", {"project": without_status}, "has no Status option In Progress"),
            ("Status option renamed", {"project": renamed}, "has no Status option In Progress"),
        )
        for name, change, expected in cases:
            with self.subTest(name):
                self.change_state(**change)
                before = len(self.state()["calls"])
                retry = self.project("--retry-from", "projection-report.json", "--report", "retry-report.json")
                self.assertEqual(retry.returncode, 2, retry.stdout + retry.stderr)
                self.assertIn(expected, retry.stderr)
                self.assertEqual(mutations(self.state()["calls"][before:]), NO_MUTATION)
                self.assertFalse((self.root / "retry-report.json").exists())
                self.assertEqual((self.root / "projection-report.json").read_bytes(), saved)
                self.assert_promotion_kept(graph)
                self.change_state(fail=[], project=PROJECTION_PROJECT)

        # 復旧後の retry は pending の 2 node だけを動かす: P03 は find → add → edit、P07 は既存 item の edit だけ。
        before = len(self.state()["calls"])
        retry = self.project("--retry-from", "projection-report.json", "--report", "retry-report.json")
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        retried = json.loads(retry.stdout)
        self.assertEqual([(row["graph_node_id"], row["operation"]) for row in retried["mutations"]],
                         [("task-P03", "project-item-add"), ("task-P03", "project-item-edit"), ("task-P07", "project-item-edit")])
        self.assertEqual((retried["pending_retry"], [entry["graph_node_id"] for entry in retried["projected"]]),
                         ([], ["task-P03", "task-P07"]))
        p07 = next(entry for entry in retried["projected"] if entry["graph_node_id"] == "task-P07")
        self.assertEqual(p07["projects"][0]["item_id"], links["task-P07"]["item_id"])
        calls = self.state()["calls"][before:]
        self.assertEqual(mutations(calls), {"issue-create": 0, "project-item-add": 1, "project-item-edit": 2})
        cursors = [call[call.index("-F") + 1:] for call in calls if "items(first:100" in " ".join(call)]
        self.assertEqual(len(cursors), 6 + 7)  # P03 は 12 item を 6 page、P07 は 13 item を 7 page 辿る
        self.assert_promotion_kept(graph)

        # 通常の再実行は、後ろの page にある item も見つけるので何も書かない。各 Issue に item は 1 つだけ。
        before = len(self.state()["calls"])
        rerun = self.project()
        self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
        self.assertEqual(mutations(self.state()["calls"][before:]), NO_MUTATION)
        final = self.state()
        self.assertEqual(sorted(item["content"] for item in final["items"]), sorted(issue["id"] for issue in final["issues"]))
        self.assertEqual((len(final["items"]), {item["fields"].get("PVTSSF_status") for item in final["items"]}),
                         (13, {"opt_progress"}))
        self.assert_promotion_kept(graph)


class SyncProjectFieldFailureTest(C02Fixture, unittest.TestCase):
    """OUT8 (C03): sync の Projects planner は pending_retry を C14 に任せ、field 削除・option 改名・読取り失敗では何も書かない。"""

    def failing_gh(self, message: str) -> dict[str, str]:
        gh = stub(self.side / "gh", f'#!/bin/sh\nprintf "%s\\n" "{message}" >&2\nexit 1\n')
        return {**self.env, "DEV_GRAPH_GH": str(gh)}

    def test_out8_sync_planner_leaves_pending_retry_to_c14_and_writes_nothing_for_broken_fields(self) -> None:
        self.published_issue()  # issue-pub: github 束縛、roadmap に投影対象、local status draft / priority high
        # C14 の linkage_proposal を C02 link-github でそのまま記録する: item-add の権限不足 (item なし) と、
        # item はできたが Status 編集が rate limit で落ちた場合 (item あり、snapshot 空)。
        for name, item_id in (("item-add failed", None), ("item-edit failed", "PVTI_1")):
            with self.subTest(name):
                pending = nodes_base.roadmap_link(item_id=item_id, sync_state="pending_retry", field_snapshot={},
                                                  linked_at=None, last_synced_at=None, last_error_code="gh_bridge_exit_1")
                code, report = self.run_cli("link-github", {"links": [{"graph_node_id": "issue-pub", "github_project_linkages": [pending]}]})
                self.assertEqual(code, 0, report)
                graph = self.graph.read_bytes()
                plan = self.reconcile(nodes_base.roadmap_remote())
                self.assertEqual([(row["project_alias"], row["reason"]) for row in plan["skipped"]],
                                 [("roadmap", "sync_state=pending_retry: C14 retry owns it")])
                self.assertEqual((plan["exports"], plan["imports"], plan["update_input"], plan["link_input"], plan["converged"]),
                                 ([], [], None, None, False))
                self.assertEqual(self.graph.read_bytes(), graph)
        # C14 の retry が通った後の linkage を記録すると、同じ planner が通常どおり扱う (初回は synced へ進めるだけ)。
        linked = nodes_base.roadmap_link(field_snapshot={"status": "Todo", "priority": "P1"})
        code, report = self.run_cli("link-github", {"links": [{"graph_node_id": "issue-pub", "github_project_linkages": [linked]}]})
        self.assertEqual(code, 0, report)
        plan = self.reconcile(nodes_base.roadmap_remote())
        self.assertEqual((plan["skipped"], plan["conflicts"], plan["exports"], plan["imports"]), ([], [], [], []))
        self.assertEqual([(link["item_id"], link["sync_state"]) for row in plan["link_input"]["links"]
                          for link in row["github_project_linkages"]], [("PVTI_1", "synced")])
        self.apply_plan(plan)
        plan = self.reconcile(nodes_base.roadmap_remote())
        self.assertEqual((plan["converged"], plan["changes"]), (True, 0))

        graph = self.graph.read_bytes()
        without_status = nodes_base.roadmap_remote()
        project = without_status["projects"]["roadmap"]
        project["fields"]["nodes"] = [field for field in project["fields"]["nodes"] if field["name"] != "Status"]
        renamed = nodes_base.roadmap_remote(status="To do", priority="Low")
        for field in renamed["projects"]["roadmap"]["fields"]["nodes"]:
            for option in field["options"]:
                option["name"] = {"Todo": "To do", "P3": "Low"}.get(option["name"], option["name"])
        cases = (("Status field deleted", without_status, [("status", "remote-field-missing")]),
                 ("options renamed", renamed, [("priority", "unmapped_remote_value"), ("status", "unsupported-export")]))
        for name, remote, expected in cases:
            with self.subTest(name):
                plan = self.reconcile(remote)
                self.assertEqual(sorted((row["local_field"], row["kind"]) for row in plan["conflicts"]), expected)
                self.assertEqual((plan["exports"], plan["imports"], plan["update_input"], plan["converged"]), ([], [], None, False))
                self.assertEqual(self.graph.read_bytes(), graph)

        # 読取り自体が権限不足・rate limit で失敗しても、planner は推測で埋めずに止まるか未取得として残す。
        cp = subprocess.run([sys.executable, str(FIELDS), "--repo-root", str(self.root)], text=True, capture_output=True,
                            env=self.failing_gh(PERMISSION), check=False)
        self.assertEqual((cp.returncode, cp.stdout), (2, ""))
        self.assertIn("HTTP 403", cp.stderr)
        code, report = self.run_cli("link-github", {"links": [{"graph_node_id": "issue-pub", "issue_linkage": {
            "issue_number": 12, "repo": "acme/web", "linked_at": nodes_base.STAMP}}]})
        self.assertEqual(code, 0, report)
        graph = self.graph.read_bytes()
        cp = subprocess.run([sys.executable, str(ISSUES), "--repo-root", str(self.root)], text=True, capture_output=True,
                            env=self.failing_gh(RATE_LIMIT), check=False)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        plan = json.loads(cp.stdout)
        self.assertEqual((len(plan["missing_issues"]), plan["imports"], plan["exports"], plan["update_input"]), (1, [], [], None))
        self.assertIn("HTTP 429", plan["missing_issues"][0]["error"])
        self.assertEqual(self.graph.read_bytes(), graph)
        self.assert_valid()


if __name__ == "__main__":
    unittest.main()
