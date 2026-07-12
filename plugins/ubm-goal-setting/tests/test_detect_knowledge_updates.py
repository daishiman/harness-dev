"""detect-knowledge-updates.py (C02) の差分検知テスト。

registry.json との MD5 照合による NEW/MODIFIED 検知・--all 強制・--since フィルタ・
source_type 分類・registry キー再構成 (05_Project/UBM 相対) を検証する。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DETECT = PLUGIN_ROOT / "skills/run-ubm-knowledge-sync/scripts/detect-knowledge-updates.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DETECT), *args],
        capture_output=True, text=True,
    )


def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def make_vault(tmp_path: Path) -> Path:
    """<tmp>/vault/05_Project/UBM/ 配下に .md を配置し UBM ディレクトリを返す。"""
    ubm = tmp_path / "vault" / "05_Project" / "UBM"
    (ubm / "YouTube").mkdir(parents=True)
    (ubm / "合宿").mkdir(parents=True)
    (ubm / "YouTube" / "2025-05-25 - test.md").write_text("content A", encoding="utf-8")
    (ubm / "合宿" / "2026-02-07 - camp.md").write_text("content B", encoding="utf-8")
    return ubm


def write_registry(tmp_path: Path, entries: list[dict]) -> Path:
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"total_processed": len(entries), "files": entries}), encoding="utf-8")
    return reg


def test_new_when_unregistered(tmp_path: Path):
    ubm = make_vault(tmp_path)
    # YouTube のみ登録済み(hash一致) → 合宿は NEW
    reg = write_registry(tmp_path, [
        {"file_path": "05_Project/UBM/YouTube/2025-05-25 - test.md", "file_hash": md5("content A")},
    ])
    r = run("--registry", str(reg), "--sources", str(ubm))
    assert r.returncode == 0
    assert "NEW|camp|" in r.stdout
    assert "05_Project/UBM/合宿/2026-02-07 - camp.md" in r.stdout
    # 登録済み一致は検知されない
    assert "NEW|youtube|" not in r.stdout
    assert "MODIFIED|youtube|" not in r.stdout


def test_modified_when_hash_differs(tmp_path: Path):
    ubm = make_vault(tmp_path)
    # YouTube を古いhashで登録 → 内容変更ありとして MODIFIED
    reg = write_registry(tmp_path, [
        {"file_path": "05_Project/UBM/YouTube/2025-05-25 - test.md", "file_hash": "stale0000"},
        {"file_path": "05_Project/UBM/合宿/2026-02-07 - camp.md", "file_hash": md5("content B")},
    ])
    r = run("--registry", str(reg), "--sources", str(ubm))
    assert r.returncode == 0
    assert "MODIFIED|youtube|" in r.stdout


def test_all_forces_new(tmp_path: Path):
    ubm = make_vault(tmp_path)
    reg = write_registry(tmp_path, [
        {"file_path": "05_Project/UBM/YouTube/2025-05-25 - test.md", "file_hash": md5("content A")},
        {"file_path": "05_Project/UBM/合宿/2026-02-07 - camp.md", "file_hash": md5("content B")},
    ])
    r = run("--registry", str(reg), "--sources", str(ubm), "--all")
    assert r.returncode == 0
    assert r.stdout.count("NEW|") == 2  # 登録済みでも全件 NEW


def test_no_change_when_all_match(tmp_path: Path):
    ubm = make_vault(tmp_path)
    reg = write_registry(tmp_path, [
        {"file_path": "05_Project/UBM/YouTube/2025-05-25 - test.md", "file_hash": md5("content A")},
        {"file_path": "05_Project/UBM/合宿/2026-02-07 - camp.md", "file_hash": md5("content B")},
    ])
    r = run("--registry", str(reg), "--sources", str(ubm))
    assert r.returncode == 0
    assert "更新はありません" in r.stdout
    assert "NEW|" not in r.stdout
    assert "MODIFIED|" not in r.stdout


def test_source_type_classification(tmp_path: Path):
    ubm = make_vault(tmp_path)
    reg = write_registry(tmp_path, [])
    r = run("--registry", str(reg), "--sources", str(ubm), "--all")
    # YouTube → youtube, 合宿 → camp
    assert "NEW|youtube|" in r.stdout
    assert "NEW|camp|" in r.stdout


def test_missing_sources_returns_empty_success(tmp_path: Path):
    reg = write_registry(tmp_path, [])
    r = run("--registry", str(reg), "--sources", str(tmp_path / "nope"))
    assert r.returncode == 0
    assert "未接続" in r.stdout
    assert "スキャン: 0 件" in r.stdout
    assert "処理対象合計: 0 件" in r.stdout


def test_missing_registry_is_input_error(tmp_path: Path):
    ubm = make_vault(tmp_path)
    r = run("--registry", str(tmp_path / "nope.json"), "--sources", str(ubm))
    assert r.returncode == 1


def test_missing_args_usage():
    r = run()
    assert r.returncode == 2
