from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "render-graph-html.py"
FEATURE = "LT-FEATURE-001"
DIGEST = "d85dfa3dc8b643020a2f9c37d897d34a71e63a6e8198c599794b3cc791aa7e84"
CHILD_IDS = [f"{FEATURE}-P{n:02d}" for n in range(1, 14)]
# receipt を渡さないときの HTML の sha256。--receipt を足す前の render-graph-html.py
# (32c92c84) で下の graph を描いた値で、receipt なしの出力が1バイトも変わらないことの基準にする。
BASELINE_HTML_SHA256 = "02bee735d87fa04af82e94fd904b236dcf2a69951b538443671afbbd27d88b3c"
BASELINE_STDOUT_KEYS = {"ok", "out", "nodes", "edges", "input_sha256", "output_sha256", "feature_progress"}


def child(node_id: str, index: int, digest: str = DIGEST) -> dict:
    return {
        "graph_node_id": node_id, "title": f"Phase <{index:02d}>", "artifact_kind": "task",
        "status": "done" if index <= 5 else "active", "parent_feature": FEATURE,
        "feature_package_id": f"feature-package/{FEATURE}",
        "depends_on": [] if index == 1 else [CHILD_IDS[index - 2]],
        "source_lineage": {"origin_kind": "system-dev-planner", "source_digest": digest},
    }


def graph_nodes() -> list[dict]:
    feature = {"graph_node_id": FEATURE, "title": "Feature", "artifact_kind": "feature", "status": "active", "depends_on": []}
    return [feature, *(child(node_id, index) for index, node_id in enumerate(CHILD_IDS, start=1))]


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def receipt(**overrides: object) -> dict:
    base = {
        "schema_version": "1.0.0", "status": "registered", "registered_at": "2026-09-07T06:16:26Z",
        "feature_package_id": f"feature-package/{FEATURE}", "parent_feature": FEATURE,
        "source_digest": f"sha256:{DIGEST}", "expected_count": 13, "applied_count": 13,
        "phase_refs": [f"P{n:02d}" for n in range(1, 14)], "node_ids": list(CHILD_IDS),
        "graph_revision_before": 1, "graph_revision_after": 2,
        "graph_digest_after": "sha256:" + "0" * 64, "output_path": ".dev-graph/state/graph.json",
    }
    return {**base, **overrides}


def render(graph: Path, out: Path, *receipts: Path) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(SCRIPT), "--graph", str(graph), "--out", str(out)]
    for path in receipts:
        argv += ["--receipt", str(path)]
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def mismatches(result: subprocess.CompletedProcess[str]) -> list[dict]:
    assert result.returncode == 1, result.stderr
    assert result.stdout == ""
    report = json.loads(result.stderr)
    assert report["ok"] is False and report["error"] == "receipt_mismatch"
    return report["receipt_mismatches"]


def test_render_receipt_match_writes_same_html_and_reports_checks(tmp_path: Path) -> None:
    graph = write_json(tmp_path / "graph.json", {"graph_revision": 2, "nodes": graph_nodes()})
    plain, checked = tmp_path / "plain.html", tmp_path / "checked.html"
    assert render(graph, plain).returncode == 0

    result = render(graph, checked, write_json(tmp_path / "receipt.json", receipt()))

    assert result.returncode == 0, result.stderr
    assert checked.read_bytes() == plain.read_bytes()
    assert "active · feature · 5/13" in checked.read_text(encoding="utf-8")
    out = json.loads(result.stdout)
    assert out["feature_progress"]["by_feature"][FEATURE] == {"done": 5, "total": 13}
    assert out["receipt_checks"] == [{
        "receipt": str(tmp_path / "receipt.json"), "feature": FEATURE, "problems": [],
        "expected_count": 13, "actual_count": 13, "missing_ids": [], "extra_ids": [],
        "source_digest": f"sha256:{DIGEST}", "digest_mismatch_ids": [],
    }]


def test_render_receipt_node_set_mismatch_stops_without_html(tmp_path: Path) -> None:
    nodes = graph_nodes()
    nodes[-1] = {**nodes[-1], "graph_node_id": f"{FEATURE}-P13-rogue"}
    graph = write_json(tmp_path / "graph.json", {"graph_revision": 2, "nodes": nodes})
    out = tmp_path / "index.html"

    [report] = mismatches(render(graph, out, write_json(tmp_path / "receipt.json", receipt())))

    assert not out.exists()
    assert report["feature"] == FEATURE and report["problems"] == ["node_ids"]
    assert report["missing_ids"] == [f"{FEATURE}-P13"]
    assert report["extra_ids"] == [f"{FEATURE}-P13-rogue"]
    assert (report["expected_count"], report["actual_count"]) == (13, 13)


def test_render_receipt_count_mismatch_stops_without_html(tmp_path: Path) -> None:
    graph = write_json(tmp_path / "graph.json", {"graph_revision": 2, "nodes": graph_nodes()[:-1]})
    out = tmp_path / "index.html"

    [report] = mismatches(render(graph, out, write_json(tmp_path / "receipt.json", receipt())))

    assert not out.exists()
    assert report["problems"] == ["expected_count", "node_ids"]
    assert (report["expected_count"], report["actual_count"]) == (13, 12)
    assert report["missing_ids"] == [f"{FEATURE}-P13"] and report["extra_ids"] == []


def test_render_receipt_source_digest_mismatch_stops_without_html(tmp_path: Path) -> None:
    nodes = graph_nodes()
    nodes[3] = child(CHILD_IDS[2], 3, digest="f" * 64)
    graph = write_json(tmp_path / "graph.json", {"graph_revision": 2, "nodes": nodes})
    out = tmp_path / "index.html"
    out.write_text("previous render", encoding="utf-8")

    [report] = mismatches(render(graph, out, write_json(tmp_path / "receipt.json", receipt())))

    assert out.read_text(encoding="utf-8") == "previous render"
    assert report["problems"] == ["source_digest"]
    assert report["digest_mismatch_ids"] == [CHILD_IDS[2]]
    assert report["source_digest"] == f"sha256:{DIGEST}"


def test_render_without_receipt_output_is_byte_identical_to_baseline(tmp_path: Path) -> None:
    graph = write_json(tmp_path / "graph.json", {"graph_revision": 2, "nodes": graph_nodes()})
    out = tmp_path / "index.html"

    result = render(graph, out)

    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(out.read_bytes()).hexdigest() == BASELINE_HTML_SHA256
    stdout = json.loads(result.stdout)
    assert set(stdout) == BASELINE_STDOUT_KEYS
    assert stdout["output_sha256"] == BASELINE_HTML_SHA256
