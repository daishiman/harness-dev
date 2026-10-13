"""run-plugin-package-check/scripts/aggregate-pkg-findings.py の集約テスト。

eval-log/<plugin>/pkg-*/<run>.json に各 PKG script と evaluator の出力を tmp_path で置き、PKG ID ごとの
status・verdict・exit code を確かめる。集約は --run の run のログだけを読み、phase の required_pkg のうち
その run のログが無い ID と status を読めないログは fail と数える (fail-closed)。
実 repo の eval-log と .claude/logs には書かない (REPO_ROOT を tmp_path に差し替える)。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = (
    Path(__file__).resolve().parents[2]
    / "plugins" / "harness-creator" / "skills" / "run-plugin-package-check"
)
SCRIPT = SKILL_DIR / "scripts" / "aggregate-pkg-findings.py"
SPEC = importlib.util.spec_from_file_location("aggregate_pkg_findings_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

MANIFEST = MOD.load_manifest()
RUN = "2026-10-10-001"
OLD_RUN = "2026-10-09-001"
ALL_IDS = [f"PKG-{n:03d}" for n in range(1, 16)]
EVALUATOR_IDS = ["PKG-002", "PKG-003", "PKG-004", "PKG-005", "PKG-006", "PKG-007", "PKG-008"]


def _report_key_pattern() -> re.Pattern:
    schema = json.loads((SKILL_DIR / "schemas" / "run-report.schema.json").read_text(encoding="utf-8"))
    (pattern,) = schema["properties"]["pkg_checks"]["patternProperties"]
    return re.compile(pattern)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "plugins").mkdir()
    monkeypatch.setattr(MOD, "REPO_ROOT", tmp_path)
    return tmp_path


def _log(repo: Path, pkg_dir: str, data, run: str = RUN, mtime: float | None = None) -> Path:
    path = repo / "eval-log" / "demo" / pkg_dir / f"{run}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _evaluator_output(package_mode: str = "bundle", **statuses: str) -> dict:
    """validate-plugin-package.py の出力 (top-level の status は無い)。"""
    checks = {
        pkg_id.replace("_", "-"): {"status": status, "findings": [{"id": "F"}] if status == "fail" else []}
        for pkg_id, status in statuses.items()
    }
    return {"run_id": "pkg-validate-demo-20261010-001", "target_plugin": "demo", "package_mode": package_mode,
            "pkg_checks": checks, "verdict": {"total": len(checks)}}


def _agg(required: list[str], run: str = RUN, phase: str = "all") -> dict:
    return MOD.aggregate("demo", run, phase, required, MANIFEST)


def _statuses(summary: dict) -> dict:
    return {k: v["status"] for k, v in summary["pkg_checks"].items()}


# --- 数える PKG ID (manifest の completion_signals) ---------------------------

def test_required_ids_follow_includes_and_fold_013():
    phase0 = [f"PKG-{n:03d}" for n in range(1, 10)]
    assert MOD.required_ids(MANIFEST, "0") == phase0
    assert MOD.required_ids(MANIFEST, "1") == phase0 + ["PKG-010"]
    assert MOD.required_ids(MANIFEST, "2") == ALL_IDS
    assert MOD.required_ids(MANIFEST, "all") == ALL_IDS


def test_parse_pkg_folds_013_sub_ids_and_rejects_unknown():
    assert MOD.parse_pkg("PKG-013a, pkg-013d,PKG-006") == ["PKG-006", "PKG-013"]
    for bad in ("PKG-016", "PKG-BATCH", "", "PKG-013e"):
        with pytest.raises(MOD.InputError):
            MOD.parse_pkg(bad)


def test_output_dirs_map_to_manifest_ids():
    dirs = MOD.ids_by_output_dir(MANIFEST)
    assert dirs["pkg-batch"] == EVALUATOR_IDS
    assert dirs["pkg-013"] == ["PKG-013"]
    assert dirs["pkg-014"] == ["PKG-014"]


# --- ログの形 ------------------------------------------------------------------

def test_pkg_batch_is_expanded_per_pkg_id(repo):
    _log(repo, "pkg-batch", _evaluator_output(PKG_002="pass", PKG_006="fail", PKG_014="not_applicable"))
    summary = _agg(["PKG-002", "PKG-006", "PKG-014"])
    checks = summary["pkg_checks"]
    assert _statuses(summary) == {"PKG-002": "pass", "PKG-006": "fail", "PKG-014": "not_applicable"}
    assert checks["PKG-006"]["findings_count"] == 1
    assert checks["PKG-006"]["source_log"] == f"eval-log/demo/pkg-batch/{RUN}.json"
    assert summary["verdict"] == {"pass": 1, "fail": 1, "skip": 0, "not_applicable": 1, "total": 3}
    assert (summary["run"], summary["phase"]) == (RUN, "all")


def test_reviewer_repro_batch_014_and_raw_009_are_not_skipped(repo):
    # pkg-batch/・pkg-014/ (evaluator 出力) と pkg-009/ (lint --json の生出力) で exit 0・全部 skip になっていた
    _log(repo, "pkg-batch", _evaluator_output(PKG_003="fail"))
    _log(repo, "pkg-014", _evaluator_output(PKG_014="fail"))
    _log(repo, "pkg-009", {"skills_scanned": 1, "external_ref_count": 2, "contract_errors": [], "reports": []})
    summary = _agg(["PKG-003", "PKG-009", "PKG-014"])
    assert _statuses(summary) == {"PKG-003": "fail", "PKG-009": "fail", "PKG-014": "fail"}
    assert summary["verdict"]["skip"] == 0
    assert summary["pkg_checks"]["PKG-009"]["status_note"].startswith("status なし")


def test_raw_009_without_external_refs_is_pass(repo):
    _log(repo, "pkg-009", {"external_ref_count": 0, "contract_errors": [], "reports": []})
    assert _agg(["PKG-009"])["pkg_checks"]["PKG-009"]["status"] == "pass"


def test_pkg_result_format_is_used_as_is(repo):
    _log(repo, "pkg-015", {"pkg_id": "PKG-015", "status": "not_applicable", "findings": []})
    _log(repo, "pkg-009", {"pkg_id": "PKG-009", "status": "pass", "findings": []})
    _log(repo, "pkg-013", {"pkg_id": "PKG-013", "status": "pass", "sub_checks": {}})
    checks = _agg(["PKG-009", "PKG-013", "PKG-015"])["pkg_checks"]
    assert {k: v["status"] for k, v in checks.items()} == {
        "PKG-009": "pass", "PKG-013": "pass", "PKG-015": "not_applicable"}
    assert "status_note" not in checks["PKG-015"]


@pytest.mark.parametrize("data, note", [
    ({"pkg_id": "PKG-010", "findings": []}, "status を読めない"),
    ({"pkg_id": "PKG-010", "status": "ok"}, "未知の status"),
    ({"status": "pass"}, None),  # pkg_id の無い単発ログは出力先の ID で数える
    ({"pkg_id": "PKG-999", "status": "pass"}, "pkg_id が PKG-001〜015 でない"),
    ("{broken", "ログを読めない"),
    ("[1, 2]", "JSON object でない"),
    ({"pkg_checks": {}}, "pkg_checks に PKG ID が無い"),
    ({"pkg_checks": {"PKG-010": {"findings": []}}}, "pkg_checks.PKG-010.status を読めない"),
])
def test_unreadable_status_is_fail_closed(repo, data, note):
    _log(repo, "pkg-010", data)
    summary = _agg(["PKG-010"])
    entry = summary["pkg_checks"]["PKG-010"]
    if note is None:
        assert entry["status"] == "pass"
        return
    assert entry["status"] == "fail"
    assert note in entry["status_note"]
    assert summary["verdict"]["fail"] == 1


def test_unreadable_pkg_batch_fails_every_evaluator_id(repo):
    # 読めない pkg-batch の ID が「PKG-BATCH」になり run-report.schema に違反していた
    _log(repo, "pkg-batch", "{broken")
    summary = _agg(ALL_IDS, phase="all")
    pattern = _report_key_pattern()
    assert all(pattern.fullmatch(k) for k in summary["pkg_checks"])
    for pkg_id in EVALUATOR_IDS:
        assert summary["pkg_checks"][pkg_id]["status"] == "fail"
        assert summary["pkg_checks"][pkg_id]["status_note"].startswith("ログを読めない")


def test_broken_symlink_log_is_fail_not_traceback(repo):
    path = repo / "eval-log" / "demo" / "pkg-009" / f"{RUN}.json"
    path.parent.mkdir(parents=True)
    path.symlink_to(repo / "nowhere.json")
    entry = _agg(["PKG-009"])["pkg_checks"]["PKG-009"]
    assert entry["status"] == "fail"
    assert "ログを読めない" in entry["status_note"]


def test_pkg_summary_is_not_read_back(repo):
    _log(repo, "pkg-summary", {"pkg_id": "PKG-001", "status": "pass"})
    entry = _agg(["PKG-001"])["pkg_checks"]["PKG-001"]
    assert entry["status"] == "fail"
    assert "ログが無い" in entry["status_note"]


# --- run を見る (別の run のログは使わない) --------------------------------------

def test_other_run_pass_does_not_fill_missing_log(repo):
    # 修正前の r2 (false green): この run に PKG-010 のログが無いのに、前の run の pass で緑になっていた
    _log(repo, "pkg-010", {"pkg_id": "PKG-010", "status": "pass"}, run=OLD_RUN, mtime=9_000)
    entry = _agg(["PKG-010"])["pkg_checks"]["PKG-010"]
    assert entry["status"] == "fail"
    assert f"この run ({RUN}) のログが無い" == entry["status_note"]


def test_newer_other_run_does_not_override_this_run(repo):
    # 修正前は run を見ずに mtime の新しいログを採っていた。前の run のログを後から触ると結果が入れ替わる
    _log(repo, "pkg-batch", _evaluator_output(PKG_006="fail"), mtime=1_000)
    _log(repo, "pkg-batch", _evaluator_output(PKG_006="pass"), run=OLD_RUN, mtime=2_000)
    assert _agg(["PKG-006"])["pkg_checks"]["PKG-006"]["status"] == "fail"  # r2: false green だった
    _log(repo, "pkg-014", _evaluator_output(PKG_014="pass"), mtime=1_000)
    _log(repo, "pkg-014", _evaluator_output(PKG_014="fail"), run=OLD_RUN, mtime=2_000)
    assert _agg(["PKG-014"])["pkg_checks"]["PKG-014"]["status"] == "pass"  # r3: false red だった


def test_same_run_conflict_takes_heavier_status(repo):
    _log(repo, "pkg-batch", _evaluator_output(PKG_006="pass"))
    _log(repo, "pkg-006", _evaluator_output(PKG_006="fail"))
    assert _agg(["PKG-006"])["pkg_checks"]["PKG-006"]["status"] == "fail"


def test_ids_outside_required_are_not_counted(repo):
    _log(repo, "pkg-014", _evaluator_output(PKG_014="fail"))
    _log(repo, "pkg-batch", _evaluator_output(**{i.replace("-", "_"): "pass" for i in EVALUATOR_IDS}))
    summary = _agg(EVALUATOR_IDS, phase="0")
    assert "PKG-014" not in summary["pkg_checks"]
    assert summary["verdict"]["fail"] == 0


def test_no_logs_at_all_is_not_green(repo):
    summary = _agg(MOD.required_ids(MANIFEST, "0"), phase="0")
    assert summary["verdict"]["fail"] == 9
    assert summary["verdict"]["total"] == 9
    assert summary["verdict_note"] == f"この run ({RUN}) のログが 1 件も無い"


# --- package_mode=skill-only --------------------------------------------------

def test_skill_only_missing_logs_are_not_applicable(repo):
    na = {i.replace("-", "_"): "not_applicable" for i in EVALUATOR_IDS if i not in ("PKG-002", "PKG-004")}
    _log(repo, "pkg-batch", _evaluator_output("skill-only", PKG_002="pass", PKG_004="pass", **na))
    summary = _agg(ALL_IDS)
    assert summary["verdict"] == {"pass": 2, "fail": 0, "skip": 0, "not_applicable": 13, "total": 15}
    assert "skill-only" in summary["pkg_checks"]["PKG-013"]["status_note"]


def test_skill_only_does_not_excuse_applicable_ids(repo):
    _log(repo, "pkg-batch", _evaluator_output("skill-only", PKG_003="not_applicable"))
    statuses = _statuses(_agg(["PKG-001", "PKG-002", "PKG-003", "PKG-004"]))
    assert statuses == {"PKG-001": "not_applicable", "PKG-002": "fail", "PKG-003": "not_applicable",
                        "PKG-004": "fail"}


def test_mixed_package_mode_is_not_skill_only(repo):
    _log(repo, "pkg-batch", _evaluator_output("skill-only", PKG_002="pass"))
    _log(repo, "pkg-014", _evaluator_output("bundle", PKG_014="pass"))
    assert _agg(["PKG-001"])["pkg_checks"]["PKG-001"]["status"] == "fail"


def test_report_keys_match_schema_for_full_run(repo):
    _log(repo, "pkg-batch", _evaluator_output(**{i.replace("-", "_"): "pass" for i in EVALUATOR_IDS}))
    _log(repo, "pkg-013", {"pkg_id": "PKG-013a", "status": "pass"})
    summary = _agg(ALL_IDS)
    pattern = _report_key_pattern()
    assert sorted(summary["pkg_checks"]) == ALL_IDS
    assert all(pattern.fullmatch(k) for k in summary["pkg_checks"])
    assert summary["pkg_checks"]["PKG-013"]["status"] == "pass"


# --- CLI ------------------------------------------------------------------------

def _run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(SCRIPT), "--plugin", "demo", *args],
                          capture_output=True, text=True, env=env, check=False)


def test_cli_fail_writes_report_and_one_observable(repo):
    _log(repo, "pkg-batch", _evaluator_output(PKG_002="pass", PKG_006="fail"))
    _log(repo, "pkg-009", {"external_ref_count": 1, "contract_errors": [], "reports": []})
    proc = _run_cli(repo, "--run", RUN, "--phase", "0", "--pkg", "PKG-002,PKG-006,PKG-009",
                    "--out", f"eval-log/demo/pkg-summary/{RUN}.json")
    assert proc.returncode == 1, proc.stderr
    report = json.loads((repo / f"eval-log/demo/pkg-summary/{RUN}.json").read_text(encoding="utf-8"))
    assert report["verdict"]["fail"] == 2
    events = (repo / ".claude/logs/meta-harness.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(events) == 1
    assert json.loads(events[0])["failed_pkg_ids"] == ["PKG-006", "PKG-009"]


def test_cli_all_pass_exit0_without_observable(repo):
    _log(repo, "pkg-batch", _evaluator_output(PKG_002="pass"))
    proc = _run_cli(repo, "--run", RUN, "--phase", "0", "--pkg", "PKG-002", "--out", "eval-log/demo/pkg-summary/x.json")
    assert proc.returncode == 0, proc.stderr
    assert not (repo / ".claude/logs/meta-harness.jsonl").exists()


def test_cli_phase_without_logs_is_exit1(repo):
    proc = _run_cli(repo, "--run", RUN, "--phase", "0", "--out", "eval-log/demo/pkg-summary/x.json")
    assert proc.returncode == 1, proc.stderr
    assert json.loads(proc.stdout)["verdict"]["fail"] == 9


@pytest.mark.parametrize("args, message", [
    (["--phase", "0", "--out", "x.json"], "--run"),
    (["--run", RUN, "--out", "x.json"], "--phase"),
    (["--run", "../2026-10-10-001", "--phase", "0", "--out", "x.json"], "--run が"),
    (["--run", RUN, "--phase", "0", "--pkg", "PKG-099", "--out", "x.json"], "--pkg に"),
])
def test_cli_bad_arguments_are_exit2(repo, args, message):
    proc = _run_cli(repo, *args)
    assert proc.returncode == 2
    assert message in proc.stderr
    assert "Traceback" not in proc.stderr
    assert not (repo / "x.json").exists()


def test_cli_unwritable_out_is_exit2(repo):
    _log(repo, "pkg-batch", _evaluator_output(PKG_002="pass"))
    blocker = repo / "eval-log" / "blocker"
    blocker.write_text("x", encoding="utf-8")
    proc = _run_cli(repo, "--run", RUN, "--phase", "0", "--pkg", "PKG-002", "--out", str(blocker / "x.json"))
    assert proc.returncode == 2
    assert "Traceback" not in proc.stderr
    assert "書けない" in proc.stderr


def test_manifest_aggregate_step_passes_run_and_phase():
    manifest = json.loads((SKILL_DIR / "workflow-manifest.json").read_text(encoding="utf-8"))
    (step,) = [s for s in manifest["phases"] if s["id"] == "aggregate"]
    args = step["args"]
    assert args[args.index("--run") + 1] == "${date}-${run}"
    assert args[args.index("--phase") + 1] == "${phase}"
