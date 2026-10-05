from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "validate-source-lineage.py"


def imported(node_id: str, path: str, digest: str) -> dict:
    return {"graph_node_id": node_id, "source_lineage": {
        "origin_kind": "system-spec-harness", "source_plugin": "system-spec-harness", "source_path": path,
        "source_version": "1.0.0", "source_digest": digest, "imported_at": "2026-10-01T00:00:00Z"}}


class ValidateSourceLineageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "system-spec").mkdir()
        self.source = self.root / "system-spec" / "auth.md"
        self.source.write_text("# 認証仕様\n", encoding="utf-8")
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.graph = self.root / ".dev-graph" / "state" / "graph.json"
        self.graph.parent.mkdir(parents=True)
        self.env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_graph(self, nodes: list[dict]) -> None:
        self.graph.write_text(json.dumps({"graph_revision": 1, "nodes": nodes}), encoding="utf-8")

    def run_cli(self, *extra: str) -> tuple[int, dict]:
        cp = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(self.root), *extra],
                            text=True, capture_output=True, env=self.env, check=False)
        return cp.returncode, json.loads(cp.stdout)

    def test_resolving_lineage_passes_and_other_origins_are_not_checked(self) -> None:
        manual = {"graph_node_id": "doc-x", "source_lineage": {"origin_kind": "manual", "source_path": None}}
        self.write_graph([imported("spec-auth", "system-spec/auth.md", self.digest), manual])
        code, report = self.run_cli()
        self.assertEqual((code, report["status"], report["checked"], report["checked_node_ids"], report["violations"]),
                         (0, "pass", 1, ["spec-auth"], []))
        self.assertEqual(report["graph"], ".dev-graph/state/graph.json")

    def test_each_unresolvable_lineage_is_a_violation(self) -> None:
        outside = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
        outside.close()
        self.addCleanup(os.unlink, outside.name)
        (self.root / "system-spec" / "link.md").symlink_to(outside.name)
        cases = {"spec-mismatch": ("system-spec/auth.md", "0" * 64, "lineage_digest_mismatch"),
                 "spec-missing": ("system-spec/gone.md", self.digest, "lineage_source_missing"),
                 "spec-escape": ("../auth.md", self.digest, "lineage_source_path_invalid"),
                 "spec-outside": ("system-spec/link.md", self.digest, "lineage_source_outside_repository"),
                 "spec-short": ("system-spec/auth.md", "abc", "lineage_digest_invalid")}
        nodes = [imported("spec-auth", "system-spec/auth.md", self.digest)]
        nodes += [imported(node_id, path, digest) for node_id, (path, digest, _) in cases.items()]
        self.write_graph(nodes)
        code, report = self.run_cli()
        self.assertEqual((code, report["status"], report["checked"]), (1, "fail", 6))
        self.assertEqual({item["node"]: item["code"] for item in report["violations"]},
                         {node_id: expected for node_id, (_, _, expected) in cases.items()})
        code, report = self.run_cli("--node-id", "spec-auth")
        self.assertEqual((code, report["status"], report["checked_node_ids"]), (0, "pass", ["spec-auth"]))
        code, report = self.run_cli("--node-id", "spec-mismatch", "--graph", str(self.graph))
        self.assertEqual((code, [item["node"] for item in report["violations"]]), (1, ["spec-mismatch"]))

    def test_usage_and_input_errors_exit_2(self) -> None:
        self.write_graph([imported("spec-auth", "system-spec/auth.md", self.digest)])
        code, report = self.run_cli("--node-id", "ghost")
        self.assertEqual((code, report["status"], report["checked"]), (2, "error", 0))
        self.assertIn("ghost", report["error"])
        code, report = self.run_cli("--graph", ".dev-graph/state/absent.json")
        self.assertEqual((code, report["status"]), (2, "error"))
        self.graph.write_text(json.dumps({"nodes": "x"}), encoding="utf-8")
        self.assertEqual(self.run_cli()[0], 2)


if __name__ == "__main__":
    unittest.main()
