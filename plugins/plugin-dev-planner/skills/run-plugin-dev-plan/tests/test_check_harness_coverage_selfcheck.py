"""check-harness-coverage-selfcheck.py の機能テスト (C3・12軸自己適用 dogfooding)。

6 種別 × 2 軸 = 12 軸が report に宣言されている構造検証のみを行い、達成率 (met) は判定外
(Goodhart 回避)。validator 不在 (repo 外) は skip する。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load(stem: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS_DIR / f"{stem}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def selfcheck() -> ModuleType:
    return _load("check-harness-coverage-selfcheck")


def _complete(selfcheck) -> dict:
    return {"axes_met": 8, "sections": [
        {"type": t, "mechanical": {"instrumented": True, "met": True},
         "llm_eval": {"instrumented": True, "met": False}}
        for t in selfcheck.EXPECTED_TYPES
    ]}


# ─────────────────── check_report_structure (単体) ───────────────────
def test_complete_report_passes(selfcheck):
    assert selfcheck.check_report_structure(_complete(selfcheck)) == []


def test_missing_type_detected(selfcheck):
    rep = _complete(selfcheck)
    rep["sections"] = [s for s in rep["sections"] if s["type"] != "docs"]
    assert any("docs" in e and "断線" in e for e in selfcheck.check_report_structure(rep))


def test_missing_axis_key_detected(selfcheck):
    rep = _complete(selfcheck)
    del rep["sections"][0]["llm_eval"]
    assert any("scripts/llm_eval" in e for e in selfcheck.check_report_structure(rep))


def test_low_achievement_not_flagged(selfcheck):
    """達成率が低い (met=False) だけでは軸が揃っていれば violation にしない (率は判定外)。"""
    rep = _complete(selfcheck)
    for s in rep["sections"]:
        s["mechanical"]["met"] = False
        s["llm_eval"]["met"] = False
    assert selfcheck.check_report_structure(rep) == []


def test_non_dict_report_is_error(selfcheck):
    assert selfcheck.check_report_structure([]) != []
    assert selfcheck.check_report_structure(None) != []


def test_expected_axes_are_twelve(selfcheck):
    assert len(selfcheck.EXPECTED_TYPES) == 6
    assert selfcheck.AXES == ("mechanical", "llm_eval")


# ─────────────────── self-test / run / main ───────────────────
def test_self_test_passes(selfcheck):
    code, msgs = selfcheck._self_test()
    assert code == 0, msgs


def test_main_self_test(selfcheck, capsys):
    assert selfcheck.main(["--self-test"]) == 0
    assert "C3" in capsys.readouterr().out


def test_run_repo_context_declares_twelve_axes(selfcheck):
    """repo 文脈では validator が在り 12 軸が全て宣言済で exit0 になる (実 subprocess)。"""
    code, errors, summary = selfcheck.run()
    if selfcheck.find_validator() is None:
        pytest.skip("validator 不在 (repo 外)")
    assert code == 0, errors
    assert "宣言 12" in summary


def test_main_repo_context_exit0(selfcheck):
    if selfcheck.find_validator() is None:
        pytest.skip("validator 不在 (repo 外)")
    assert selfcheck.main([]) == 0
