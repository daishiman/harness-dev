"""check-knowledge-split.py (C03) の決定論ゲート挙動テスト。

閾値500行の超過検知・管理ファイル除外・usage を検証する。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SPLIT = PLUGIN_ROOT / "skills/run-ubm-knowledge-sync/scripts/check-knowledge-split.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SPLIT), *args],
        capture_output=True, text=True,
    )


def test_under_threshold_ok(tmp_path: Path):
    (tmp_path / "principles-mindset.json").write_text("x\n" * 100, encoding="utf-8")
    r = run("--dir", str(tmp_path))
    assert r.returncode == 0
    assert "分割不要" in r.stdout


def test_over_threshold_fails(tmp_path: Path):
    (tmp_path / "principles-huge.json").write_text("x\n" * 501, encoding="utf-8")
    r = run("--dir", str(tmp_path))
    assert r.returncode == 1
    assert "要分割" in r.stdout
    assert "principles-huge.json" in r.stderr  # 超過一覧は stderr


def test_management_files_excluded(tmp_path: Path):
    # 管理・生成ファイル (graph/relations/quarantine は C05/C06 の運用時生成・永続ストア) は500超でも対象外
    for name in (
        "schema.json",
        "router.json",
        "registry.json",
        "knowledge-graph.json",
        "harness-artifact-graph.json",
        "knowledge-relations.json",
        "knowledge-relations-quarantine.json",
    ):
        (tmp_path / name).write_text("x\n" * 999, encoding="utf-8")
    (tmp_path / "principles-ok.json").write_text("x\n" * 10, encoding="utf-8")
    r = run("--dir", str(tmp_path))
    assert r.returncode == 0
    assert "要分割" not in r.stdout


def test_boundary_500_ok(tmp_path: Path):
    # 500行ちょうどは OK (>500 で FAIL)
    (tmp_path / "principles-500.json").write_text("x\n" * 500, encoding="utf-8")
    r = run("--dir", str(tmp_path))
    assert r.returncode == 0


def test_missing_dir_usage(tmp_path: Path):
    r = run("--dir", str(tmp_path / "nope"))
    assert r.returncode == 2


def test_no_dir_arg_usage():
    r = run()
    assert r.returncode == 2


def test_vendored_knowledge_passes():
    # 同梱 knowledge は全 category ≤500 行で OK であること
    kdir = PLUGIN_ROOT / "knowledge"
    r = run("--dir", str(kdir))
    assert r.returncode == 0, r.stdout + r.stderr
