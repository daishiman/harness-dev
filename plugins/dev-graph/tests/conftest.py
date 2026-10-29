"""dev-graph plugin テストの共有 fixture。

lint-orphan-external-ref の 2 ファイルは同じ疑似 repo 構築を必要とするため、ヘルパを複製せず
ここへ置く。

  test_lint_orphan_external_ref.py      -> lib/orphan_external_ref.py          (検査ロジック)
  test_lint_orphan_external_ref_cli.py  -> scripts/lint-orphan-external-ref.py (CLI 契約)
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]

# baseline 検証で共有する疑似 node id。tmp 側にだけ置き、repo の実データには依存しない。
BASELINED = "issue-known-orphan-fixture"


class OrphanLintHarness:
    """lint-orphan-external-ref の path 解決・lib 読込・疑似 repo 構築をまとめる。"""

    script = PLUGIN / "scripts" / "lint-orphan-external-ref.py"
    lib = PLUGIN / "lib" / "orphan_external_ref.py"
    plugin = PLUGIN
    baselined = BASELINED

    def __init__(self) -> None:
        # 検査ロジックを持つ lib を直接読む。CLI (script) は argv 解釈と出力しか持たない
        # ため、ロジックの不変条件は lib に対して固定する。CLI の挙動 (exit code /
        # --json-out / 引数エラー) は subprocess 経由で別ファイルが検証する。
        spec = importlib.util.spec_from_file_location("orphan_external_ref", self.lib)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module

    def md(self, node_id: str) -> str:
        """build-graph-node.py が書く frontmatter と同じ形 (値は JSON) の artifact md。"""
        return f'---\ngraph_node_id: "{node_id}"\nartifact_kind: "issue"\n---\n\n# body\n'

    def repo(
        self,
        tmp_path: Path,
        node_ids: list[str],
        beads: list[dict],
        md_ids: tuple[str, ...] = (),
        baseline: tuple[str, ...] | None = (),
    ) -> tuple[Path, Path]:
        """tmp の疑似 repo を組む。baseline=None なら baseline ファイルを置かない (欠損検証用)。"""
        root = tmp_path / "repo"
        (root / ".dev-graph" / "state").mkdir(parents=True)
        (root / ".dev-graph" / "state" / "graph.json").write_text(
            json.dumps({"schema_version": "1", "nodes": [
                {"graph_node_id": node_id, "artifact_kind": "issue"} for node_id in node_ids
            ]}),
            encoding="utf-8",
        )
        issues_dir = root / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        for node_id in md_ids:
            (issues_dir / f"{node_id}.md").write_text(self.md(node_id), encoding="utf-8")
        if baseline is not None:
            baseline_path = root / self.module._BASELINE_RELPATH
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(
                json.dumps({self.module._BASELINE_KEY: list(baseline)}), encoding="utf-8",
            )
        export = root / "beads.jsonl"
        export.write_text("\n".join(json.dumps(row) for row in beads), encoding="utf-8")
        return root, export

    def issue(
        self,
        issue_id: str,
        node_id: str | None,
        status: str = "open",
        prefix: str = "dev-graph:",
    ) -> dict:
        row = {"id": issue_id, "status": status, "title": f"title of {issue_id}"}
        if node_id is not None:
            row["external_ref"] = f"{prefix}{node_id}"
        return row

    def run(self, root: Path, export: Path | None, *extra: str) -> tuple[int, dict]:
        """CLI を subprocess で実行し (exit code, JSON) を返す。"""
        args = [sys.executable, "-B", str(self.script), "--repo-root", str(root)]
        if export is not None:
            args += ["--beads-export", str(export)]
        args += list(extra)
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
        assert proc.stdout, proc.stderr
        return proc.returncode, json.loads(proc.stdout)

    def git(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )


@pytest.fixture(scope="session")
def orphan_lint() -> OrphanLintHarness:
    return OrphanLintHarness()
