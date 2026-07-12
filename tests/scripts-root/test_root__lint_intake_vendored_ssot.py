"""scripts/lint-intake-vendored-ssot.py (後方互換ラッパ) の機能テスト。

歴史的経緯: 本 lint は skill-intake へ vendoring した notion_config.py が harness-creator
正本と byte 一致するかを検証する専用 lint だった。検査ロジックは後継
scripts/lint-vendored-ssot.py に一般化され、本ファイルは notion_config ペアのみを抽出して
後継 check_pairs へ委譲する薄いシムになった。

本テストはラッパが (a) 実 repo で exit 0、(b) notion_config ペアのみを検査対象にし
feedback_contract_ssot ペアは後継側 lint の責務として扱う、ことを健全性確認する。
検査ロジック自体の網羅テストは test_root__lint_vendored_ssot.py が担う。

network: false, keychain: なし, 実ファイル書換: なし。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-intake-vendored-ssot.py"

SPEC = importlib.util.spec_from_file_location("lint_intake_vendored_ssot_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_main_ok_real_repo(capsys):
    """実 repo の notion_config vendored ペアが一致し exit 0 になること。"""
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out and "byte 一致" in out


def test_wrapper_only_checks_notion_config():
    """ラッパは notion_config ペアのみを検査対象とする (feedback_contract は後継側)。"""
    pairs = [p for p in MOD._mod.VENDORED_PAIRS if p[0].name == "notion_config.py"]
    assert pairs, "notion_config の vendored ペアが後継 VENDORED_PAIRS に存在すること"
    # feedback_contract_ssot ペアは後継 lint-vendored-ssot.py に存在するが、
    # ラッパの検査対象 (notion_config 限定) には含めない。
    assert all(c.name == "notion_config.py" for c, _ in pairs)


def test_delegates_to_successor_module():
    """ラッパが後継 lint-vendored-ssot.py の check_pairs / VENDORED_PAIRS を参照すること。"""
    assert hasattr(MOD._mod, "check_pairs")
    assert hasattr(MOD._mod, "VENDORED_PAIRS")


def test_cli_real_repo_exit_zero():
    res = subprocess.run([sys.executable, str(SCRIPT)], text=True, capture_output=True)
    assert res.returncode == 0, f"stderr={res.stderr}"
    assert "OK" in res.stdout
