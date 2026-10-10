"""detect-knowledge-updates.py (C02) の差分検知テスト。

registry.json との MD5 照合による NEW/MODIFIED 検知・--all 強制・--since の追加再処理条件・
source_type 分類・registry キー再構成 (05_Project/UBM 相対)・利用者の記録の除外
(EXCLUDED_SUBDIRS) を検証する。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
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


def test_user_records_are_excluded_at_detection(tmp_path: Path):
    """目標設定/ と 挑戦宣言/ の下の .md は検知の段階で除き、他は検知する。"""
    ubm = make_vault(tmp_path)
    (ubm / "目標設定").mkdir()
    (ubm / "挑戦宣言" / "過去").mkdir(parents=True)
    (ubm / "目標設定" / "UBM - 1-週報 - 2026-01-05〜2026-01-11.md").write_text("goal", encoding="utf-8")
    (ubm / "挑戦宣言" / "UBM - 挑戦宣言 - 2026-10-01.md").write_text("declare", encoding="utf-8")
    (ubm / "挑戦宣言" / "過去" / "UBM - 挑戦宣言 - 2026-09-01.md").write_text("old", encoding="utf-8")
    (ubm / "UBM - 成果報告会.md").write_text("event", encoding="utf-8")
    reg = write_registry(tmp_path, [])
    for extra in ((), ("--all",)):
        r = run("--registry", str(reg), "--sources", str(ubm), *extra)
        assert r.returncode == 0
        assert "05_Project/UBM/目標設定/" not in r.stdout
        assert "05_Project/UBM/挑戦宣言/" not in r.stdout
        assert "05_Project/UBM/YouTube/2025-05-25 - test.md" in r.stdout
        assert "05_Project/UBM/合宿/2026-02-07 - camp.md" in r.stdout
        assert "05_Project/UBM/UBM - 成果報告会.md" in r.stdout
        assert r.stdout.count("NEW|") == 3
        assert "スキャン: 3 件" in r.stdout
        assert "除外: 3 件" in r.stdout


def test_missing_sources_returns_empty_success(tmp_path: Path):
    reg = write_registry(tmp_path, [])
    r = run("--registry", str(reg), "--sources", str(tmp_path / "nope"))
    assert r.returncode == 0
    assert "未接続" in r.stdout
    assert "スキャン: 0 件" in r.stdout
    assert "除外: 0 件" in r.stdout
    assert "処理対象合計: 0 件" in r.stdout


def test_missing_registry_is_input_error(tmp_path: Path):
    ubm = make_vault(tmp_path)
    r = run("--registry", str(tmp_path / "nope.json"), "--sources", str(ubm))
    assert r.returncode == 1


def test_missing_args_usage():
    r = run()
    assert r.returncode == 2


def test_since_reprocesses_only_matching_hash_strictly_after_date(tmp_path: Path):
    ubm = make_vault(tmp_path)
    youtube = ubm / "YouTube" / "2025-05-25 - test.md"
    camp = ubm / "合宿" / "2026-02-07 - camp.md"
    for file, day in [(youtube, "2026-10-08"), (camp, "2026-10-09")]:
        stamp = datetime.strptime(day, "%Y-%m-%d").timestamp()
        os.utime(file, (stamp, stamp))
    reg = write_registry(tmp_path, [
        {"file_path": "05_Project/UBM/YouTube/2025-05-25 - test.md", "file_hash": md5("content A")},
        {"file_path": "05_Project/UBM/合宿/2026-02-07 - camp.md", "file_hash": md5("content B")},
    ])
    result = run("--registry", str(reg), "--sources", str(ubm), "--since", "2026-10-08")
    assert result.returncode == 0
    assert "MODIFIED|camp|" in result.stdout
    assert "MODIFIED|youtube|" not in result.stdout


def test_since_does_not_drop_older_unregistered_or_changed_sources(tmp_path: Path):
    ubm = make_vault(tmp_path)
    stamp = datetime(2020, 1, 1).timestamp()
    for file in ubm.rglob("*.md"):
        os.utime(file, (stamp, stamp))
    reg = write_registry(tmp_path, [
        {"file_path": "05_Project/UBM/YouTube/2025-05-25 - test.md", "file_hash": "stale"},
    ])
    result = run("--registry", str(reg), "--sources", str(ubm), "--since", "2026-10-08")
    assert result.returncode == 0
    assert "MODIFIED|youtube|" in result.stdout
    assert "NEW|camp|" in result.stdout


def test_invalid_since_is_input_error_even_when_vault_disconnected(tmp_path: Path):
    reg = write_registry(tmp_path, [])
    for invalid in ["2026-02-30", "2026-2-01", "not-a-date"]:
        result = run("--registry", str(reg), "--sources", str(tmp_path / "missing"), "--since", invalid)
        assert result.returncode == 1
        assert "--since" in result.stderr


def test_all_user_record_output_directories_are_excluded(tmp_path: Path):
    import importlib.util
    import re
    spec = importlib.util.spec_from_file_location("detect_exclusions", DETECT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # A new vault writer outside this pair cannot silently become a knowledge source.
    output_roots = set()
    for skill in (PLUGIN_ROOT / "skills").glob("run-ubm-*/SKILL.md"):
        text = skill.read_text(encoding="utf-8")
        output_roots.update(re.findall(r"(?:保存先|出力契約)[^\n]*05_Project/UBM/([^/`]+?)/", text))
    assert output_roots
    assert output_roots <= set(module.EXCLUDED_SUBDIRS)
    # Daily lives outside --sources and therefore needs no extra detector exclusion.
    assert "Daily" not in module.EXCLUDED_SUBDIRS
