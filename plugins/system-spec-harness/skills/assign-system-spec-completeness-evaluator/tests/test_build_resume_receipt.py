"""build-resume-receipt.py (再利用 receipt の production writer) の振る舞いテスト。

writer は canonical PASS report・fork ledger・具体的 session・現在の artifact snapshot・
3 gate の再実行がすべて揃ったときだけ receipt を書く。ここでは正常系 1 件と、
拒否すべき 4 種 (canonical 以外の report / session "unknown" / snapshot 不一致 / gate 失敗)
を実プロセスで確かめる。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from completeness_test_support import SKILL_DIR, golden_report, write_ledger, write_matrix

WRITER = SKILL_DIR / "scripts" / "build-resume-receipt.py"
LEDGER = Path("eval-log/system-spec-harness/audit-fork-ledger.jsonl")
REPORT = Path("system-spec/completeness-report.json")
RECEIPT = Path("system-spec/resume-receipt.json")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WRITER), "--repo-root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _snapshot(root: Path) -> dict:
    process = _run(root, "--print-artifact-snapshot")
    assert process.returncode == 0, process.stdout + process.stderr
    return json.loads(process.stdout)


def _project(tmp_path: Path) -> Path:
    """writer が受理する最小の利用側 repo (完全な matrix・空の出典・PASS report・ledger)。"""
    root = tmp_path / "project"
    spec = root / "system-spec"
    spec.mkdir(parents=True)
    write_matrix(spec / "spec-state.json")
    (spec / "fetched-references.json").write_text(json.dumps({"references": []}), encoding="utf-8")
    (spec / "index.md").write_text("# index\n", encoding="utf-8")
    (spec / "00-requirements-definition.md").write_text("# 要件定義\n", encoding="utf-8")
    ledger = root / LEDGER
    ledger.parent.mkdir(parents=True)
    write_ledger(ledger)
    report = golden_report()
    report["artifact_snapshot"] = _snapshot(root)
    (root / REPORT).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return root


def _write_args(session: str = "sess-1", report: Path = REPORT) -> list[str]:
    return ["--report", str(report), "--fork-ledger", str(LEDGER), "--session", session, "--output", str(RECEIPT)]


def test_writer_builds_a_digest_bound_receipt_from_a_canonical_pass_report(tmp_path):
    root = _project(tmp_path)
    process = _run(root, *_write_args())
    assert process.returncode == 0, process.stdout + process.stderr
    receipt = json.loads((root / RECEIPT).read_text(encoding="utf-8"))
    assert receipt["verdict"] == "PASS"
    assert receipt["evaluator"]["session_id"] == "sess-1"
    assert receipt["evaluator"]["report_path"] == REPORT.as_posix()
    assert receipt["artifacts"][REPORT.as_posix()] == receipt["evaluator"]["report_sha256"]


def test_writer_rejects_a_report_outside_the_canonical_path(tmp_path):
    root = _project(tmp_path)
    other = root / "eval-log" / "completeness-report.json"
    other.write_text((root / REPORT).read_text(encoding="utf-8"), encoding="utf-8")
    process = _run(root, *_write_args(report=other.relative_to(root)))
    assert process.returncode == 2
    assert "canonical path" in json.loads(process.stdout)["error"]
    assert not (root / RECEIPT).exists()


def test_writer_rejects_the_unknown_session(tmp_path):
    root = _project(tmp_path)
    process = _run(root, *_write_args(session="unknown"))
    assert process.returncode == 2
    assert "concrete evaluator session" in json.loads(process.stdout)["error"]
    assert not (root / RECEIPT).exists()


def test_writer_rejects_inputs_changed_after_the_snapshot(tmp_path):
    root = _project(tmp_path)
    (root / "system-spec" / "index.md").write_text("# index (評価後に変更)\n", encoding="utf-8")
    process = _run(root, *_write_args())
    assert process.returncode == 2
    assert "artifact snapshot differs" in json.loads(process.stdout)["error"]
    assert not (root / RECEIPT).exists()


def test_writer_rejects_a_failing_gate_even_when_the_report_claims_pass(tmp_path):
    root = _project(tmp_path)
    write_matrix(root / "system-spec" / "spec-state.json", complete=False)
    report = json.loads((root / REPORT).read_text(encoding="utf-8"))
    report["artifact_snapshot"] = _snapshot(root)
    (root / REPORT).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    process = _run(root, *_write_args())
    assert process.returncode == 2
    assert "G-matrix failed" in json.loads(process.stdout)["error"]
    assert not (root / RECEIPT).exists()
