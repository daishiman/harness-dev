"""condition ↔ condition_signal 対応検査が CI 経路 (--phase-order) で実際に発火するか固定する。

このゲートは一度 fail-open していた: `--strict-signal` は main() で argv から剥がされる
だけで --phase-order 分岐へ渡らず、しかも check_phase_order_tree は condition_signal を
一切読まなかった。つまり CI に旗を足しても no-op で、検査があるように見えて何も検査して
いなかった (elegant-review run-20260809-remnants の LS-05)。

「旧 run を遡及 fail させない」ための WARN 既定は正しい配慮だが、終了条件が無いと検査が
恒久的に骨抜きになる (同 SS-02)。そこで run ディレクトリ名の日付を境界に strict へ昇格
させた。本テストは (a) 境界以降の run で error になる (b) 境界より前は WARN 止まり
(c) --strict-signal で日付に関わらず error になる、の 3 点を実測で固定する。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/run-elegant-review/scripts/validate-paradigm-coverage.py"
)

# condition と condition_signal が対応しない issue と、smell に便宜値 condition が残る issue。
# どちらも二重帳簿バグクラスの実体で、検査が生きていれば strict run で error になる。
MISMATCHED_FINDINGS = {
    "paradigm_findings": [
        {
            "paradigm_id": 1,
            "issues": [
                {"condition": "C3", "condition_signal": "contradiction"},
                {"condition": "C1", "condition_signal": "smell"},
            ],
        }
    ]
}

CLEAN_FINDINGS = {
    "paradigm_findings": [
        {
            "paradigm_id": 1,
            "issues": [
                {"condition": "C1", "condition_signal": "contradiction"},
                {"condition_signal": "smell"},
            ],
        }
    ]
}


def make_run(tmp_path: Path, run_name: str, findings: dict) -> Path:
    run_dir = tmp_path / "eval-log/probe/elegant-review" / run_name
    run_dir.mkdir(parents=True)
    (run_dir / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    (run_dir / "shared_state.md").write_text("probe\n", encoding="utf-8")
    return run_dir


def run_gate(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra, "--phase-order", str(target)],
        capture_output=True,
        text=True,
    )


def test_strict_run_fails_on_signal_mismatch(tmp_path: Path) -> None:
    """境界以降の run 名なら対応不一致は error (exit 1) になる。"""
    run_dir = make_run(tmp_path, "run-20260810-strict", MISMATCHED_FINDINGS)
    result = run_gate(run_dir)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "condition_signal=contradiction が対応しない" in result.stderr
    assert "condition_signal=smell に 便宜値" in result.stderr.replace("\n", " ")


def test_legacy_run_only_warns(tmp_path: Path) -> None:
    """境界より前の run は同じ欠陥でも WARN 止まり (遡及免除)。"""
    run_dir = make_run(tmp_path, "run-20260701-legacy", MISMATCHED_FINDINGS)
    result = run_gate(run_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN:" in result.stderr


def test_strict_signal_flag_overrides_date_boundary(tmp_path: Path) -> None:
    """--strict-signal は --phase-order 経路にも届く (旗が no-op だった回帰の固定)。"""
    run_dir = make_run(tmp_path, "run-20260701-legacy", MISMATCHED_FINDINGS)
    result = run_gate(run_dir, "--strict-signal")
    assert result.returncode == 1, result.stdout + result.stderr


def test_clean_strict_run_passes_and_reports_checked_count(tmp_path: Path) -> None:
    """検査が実際に走ったことを checked 件数で示す (exit 0 と未検査を混同しない)。"""
    run_dir = make_run(tmp_path, "run-20260810-strict", CLEAN_FINDINGS)
    result = run_gate(run_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "signal consistency checked in 1 findings file(s)" in result.stdout
    assert "1 run(s) under strict mode" in result.stdout


def test_tree_mode_checks_every_run(tmp_path: Path) -> None:
    """tree を渡したとき、strict run の欠陥だけが error になり legacy は WARN に落ちる。"""
    make_run(tmp_path, "run-20260810-strict", CLEAN_FINDINGS)
    make_run(tmp_path, "run-20260701-legacy", MISMATCHED_FINDINGS)
    result = run_gate(tmp_path / "eval-log")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "signal consistency checked in 2 findings file(s)" in result.stdout

    make_run(tmp_path, "run-20260811-broken", MISMATCHED_FINDINGS)
    result = run_gate(tmp_path / "eval-log")
    assert result.returncode == 1, result.stdout + result.stderr


def test_verdict_drift_fails_in_strict_run(tmp_path: Path) -> None:
    """verdict.json が findings.json の導出値と食い違えば strict run で error になる。

    verdict.json は長らく生成器が無く手書きで、findings.json を 28→34 件へ更新しても
    追随せず二重帳簿になった (SS-09)。その再発を CI 経路で押さえる。
    """
    run_dir = make_run(tmp_path, "run-20260810-strict", CLEAN_FINDINGS)
    stale = {
        "plugin": "probe",
        "skill": "probe-skill",
        "scope_mode": "repo",
        "verdict": {"矛盾なし": "PASS", "漏れなし": "PASS", "整合性あり": "PASS", "依存関係整合": "PASS"},
        "fail_counts": {"contradiction": 0, "omission": 0, "inconsistency": 0, "dependency_break": 0, "smell": 0},
        "iteration_count": 0,
        "status": "complete",
    }
    (run_dir / "verdict.json").write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
    result = run_gate(run_dir)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "findings.json からの導出値と一致しない" in result.stderr
    # CLEAN_FINDINGS は contradiction 1 件なので、矛盾なし=FAIL が正しい導出。
    assert "fail_counts" in result.stderr


def test_verdict_matching_derivation_passes(tmp_path: Path) -> None:
    """build-verdict.py で生成した verdict は検査を通り、検査件数が 1 と報告される。"""
    run_dir = make_run(tmp_path, "run-20260810-strict", CLEAN_FINDINGS)
    builder = SCRIPT.with_name("build-verdict.py")
    built = subprocess.run(
        [
            sys.executable, str(builder),
            "--findings", str(run_dir / "findings.json"),
            "--verdict", str(run_dir / "verdict.json"),
            "--plugin", "probe", "--skill", "probe-skill", "--scope-mode", "repo",
        ],
        capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    result = run_gate(run_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verdict derivation checked in 1 run(s)" in result.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
