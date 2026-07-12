"""validate-output-mode.py の網羅テスト。

関数 (validate_output_mode / run_preflight) の import 経路と、CLI の exit code 規約
(0=valid / 2=fail-closed / preflight 単独=0) の subprocess 経路の両方を検証する。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/validate-output-mode.py はハイフン入りファイル名のため importlib で読み込む。
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate-output-mode.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_output_mode_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()

REPORT_TYPES = [
    "internal-analysis",
    "client-proposal",
    "tech-doc",
    "learning",
]


# --- 正常系 -----------------------------------------------------------------

def test_slide_valid_without_report_type():
    r = mod.validate_output_mode("slide", None)
    assert r["valid"] is True
    assert r["errors"] == []
    assert r["mode"] == "slide"


@pytest.mark.parametrize("rtype", REPORT_TYPES)
def test_report_valid_for_each_report_type(rtype):
    r = mod.validate_output_mode("report", rtype)
    assert r["valid"] is True, r["errors"]
    assert r["report_type"] == rtype


# --- 異常系 (fail-closed) ---------------------------------------------------

@pytest.mark.parametrize("bad_mode", ["deck", "SLIDE", "", "presentation", None])
def test_invalid_mode_is_rejected(bad_mode):
    r = mod.validate_output_mode(bad_mode, None)
    assert r["valid"] is False
    assert any("invalid mode" in e for e in r["errors"])


def test_report_without_report_type_is_rejected():
    r = mod.validate_output_mode("report", None)
    assert r["valid"] is False
    assert any("requires --report-type" in e for e in r["errors"])


@pytest.mark.parametrize("bad_type", ["proposal", "internal", "TECH-DOC", "misc"])
def test_report_with_invalid_type_is_rejected(bad_type):
    r = mod.validate_output_mode("report", bad_type)
    assert r["valid"] is False
    assert any("invalid report_type" in e for e in r["errors"])


def test_slide_with_report_type_is_rejected():
    # slide に reportType は矛盾 (report-only)。fail-closed。
    r = mod.validate_output_mode("slide", "internal-analysis")
    assert r["valid"] is False
    assert any("does not accept --report-type" in e for e in r["errors"])


# --- preflight (fail-soft) --------------------------------------------------

def test_preflight_returns_expected_shape():
    r = mod.run_preflight()
    assert set(r.keys()) == {"ok", "detected", "warnings"}
    assert isinstance(r["ok"], bool)
    assert isinstance(r["warnings"], list)
    for key in ("node", "npm", "vendor_dir", "node_modules", "codex_cli"):
        assert key in r["detected"]


# --- CLI exit code 規約 (subprocess) ----------------------------------------

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_cli_slide_exit_0_and_json_stdout():
    proc = _run_cli("--mode", "slide")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["validation"]["valid"] is True


def test_cli_report_with_type_exit_0():
    proc = _run_cli("--mode", "report", "--report-type", "tech-doc")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["validation"]["valid"] is True


def test_cli_invalid_mode_exit_2():
    proc = _run_cli("--mode", "bogus")
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["validation"]["valid"] is False


def test_cli_report_missing_type_exit_2():
    proc = _run_cli("--mode", "report")
    assert proc.returncode == 2


def test_cli_slide_with_report_type_exit_2():
    proc = _run_cli("--mode", "slide", "--report-type", "learning")
    assert proc.returncode == 2


def test_cli_preflight_alone_exit_0():
    # preflight 単独は環境欠落があっても常に exit 0 (fail-soft)。
    proc = _run_cli("--preflight")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert "preflight" in payload
    assert set(payload["preflight"].keys()) == {"ok", "detected", "warnings"}


def test_cli_no_args_exit_2():
    # mode も preflight も無い呼び出しは使い方エラー (fail-closed)。
    proc = _run_cli()
    assert proc.returncode == 2


def test_cli_mode_with_preflight_mode_governs_exit_code():
    # mode 検証と preflight を同時指定した場合、exit code は mode 検証が支配する。
    proc = _run_cli("--mode", "bogus", "--preflight")
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert "preflight" in payload  # preflight 結果も併せて出る。
    assert payload["validation"]["valid"] is False


# --- in-process 経路 (main/run_preflight/_build_parser の coverage を honest に満たす。
#     CLI 挙動は subprocess で検証済だが pytest-cov は別プロセスを計数しないため in-process でも呼ぶ) ---

def test_inprocess_main_valid_slide(capsys):
    assert mod.main(["--mode", "slide"]) == 0
    assert json.loads(capsys.readouterr().out)["validation"]["valid"] is True


def test_inprocess_main_invalid_report_type(capsys):
    assert mod.main(["--mode", "report", "--report-type", "bogus"]) == 2
    assert json.loads(capsys.readouterr().out)["validation"]["valid"] is False


def test_inprocess_main_no_args_is_usage_error(capsys):
    assert mod.main([]) == 2
    assert json.loads(capsys.readouterr().out)["validation"]["valid"] is False


def test_inprocess_main_preflight_alone_exit_0(capsys):
    assert mod.main(["--preflight"]) == 0
    assert "preflight" in json.loads(capsys.readouterr().out)


def test_inprocess_run_preflight_shape():
    r = mod.run_preflight()
    assert {"ok", "detected", "warnings"}.issubset(r)
    assert isinstance(r["warnings"], list)


def test_inprocess_build_parser():
    ns = mod._build_parser().parse_args(["--mode", "report", "--report-type", "internal-analysis"])
    assert ns.mode == "report" and ns.report_type == "internal-analysis"
