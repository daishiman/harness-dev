"""extract-recurring-findings.py (学習ラチェット運用口) の機能テスト。

conftest 非依存で module-level に importlib ロードする (自己特結)。
網羅: 同一 key 2 回で候補入り・1 回では非候補・閾値可変・壊れた JSONL 行の
行単位 fail-soft (skip + 警告 + 他行続行)・壊れた JSON ファイルの skip・
fail-closed (全候補 status=unreviewed)・key 正規化 (大文字小文字)・--out 出力。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


det = _load("extract-recurring-findings")


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _finding(bucket: str, observation: str = "obs", severity: str = "warn") -> dict:
    return {"bucket": bucket, "observation": observation, "severity": severity}


def _write_plan(root: Path, plan: str, findings: list[dict]) -> None:
    d = root / "plugin-plans" / plan
    d.mkdir(parents=True)
    (d / "plan-findings.json").write_text(
        json.dumps({"plan_dir": plan, "verdict": "PASS", "findings": findings}),
        encoding="utf-8",
    )


def _candidates(report: dict) -> dict[str, dict]:
    return {c["key"]: c for c in report["automation_candidates"]}


# ─────────────────────────── 反復検知の基本 ───────────────────────────
def test_same_key_twice_becomes_candidate(tmp_path):
    _write_plan(tmp_path, "p1", [_finding("dup-key", "first")])
    _write_plan(tmp_path, "p2", [_finding("dup-key", "second")])
    report = det.aggregate(tmp_path, threshold=2)
    cands = _candidates(report)
    assert "dup-key" in cands
    c = cands["dup-key"]
    assert c["count"] == 2
    assert sorted(c["sources"]) == [
        "plugin-plans/p1/plan-findings.json",
        "plugin-plans/p2/plan-findings.json",
    ]
    assert set(c["observations"]) == {"first", "second"}


def test_single_occurrence_is_not_candidate(tmp_path):
    _write_plan(tmp_path, "p1", [_finding("once-key")])
    report = det.aggregate(tmp_path, threshold=2)
    assert "once-key" not in _candidates(report)
    assert report["keys_seen"] == 1  # 見えてはいるが閾値未満


def test_threshold_is_configurable(tmp_path):
    _write_plan(tmp_path, "p1", [_finding("k")])
    assert "k" in _candidates(det.aggregate(tmp_path, threshold=1))
    assert "k" not in _candidates(det.aggregate(tmp_path, threshold=2))


def test_key_normalization_case_insensitive(tmp_path):
    _write_plan(tmp_path, "p1", [_finding("Dup-Key")])
    _write_plan(tmp_path, "p2", [_finding("dup-key")])
    report = det.aggregate(tmp_path, threshold=2)
    assert _candidates(report)["dup-key"]["count"] == 2


def test_finding_code_takes_priority_over_bucket(tmp_path):
    entry = {"finding_code": "fc-1", "bucket": "b-1", "observation": "x"}
    _write_plan(tmp_path, "p1", [entry])
    _write_plan(tmp_path, "p2", [entry])
    cands = _candidates(det.aggregate(tmp_path, threshold=2))
    assert "fc-1" in cands and cands["fc-1"]["key_field"] == "finding_code"
    assert "b-1" not in cands


# ─────────────────────────── fail-soft (行単位) ───────────────────────────
def test_broken_jsonl_line_skipped_with_warning(tmp_path, capsys):
    log = tmp_path / "eval-log"
    log.mkdir()
    lines = [
        json.dumps({"findings": [_finding("jl-key", "line1")]}),
        "{broken json !!!",
        json.dumps({"findings": [_finding("jl-key", "line3")]}),
    ]
    (log / "queue.jsonl").write_text("\n".join(lines), encoding="utf-8")
    report = det.aggregate(tmp_path, threshold=2)
    assert _candidates(report)["jl-key"]["count"] == 2  # 壊れ行以外は処理継続
    assert len(report["skipped"]) == 1
    assert report["skipped"][0]["line"] == 2
    assert "broken JSON line skipped" in capsys.readouterr().err


def test_broken_json_file_skipped_others_processed(tmp_path, capsys):
    log = tmp_path / "eval-log"
    log.mkdir()
    (log / "findings-bad.json").write_text("not json", encoding="utf-8")
    _write_plan(tmp_path, "p1", [_finding("ok-key")])
    _write_plan(tmp_path, "p2", [_finding("ok-key")])
    report = det.aggregate(tmp_path, threshold=2)
    assert "ok-key" in _candidates(report)
    assert len(report["skipped"]) == 1
    assert "broken JSON file skipped" in capsys.readouterr().err


# ─────────────────────────── fail-closed / 出力契約 ───────────────────────────
def test_all_candidates_are_unreviewed(tmp_path):
    _write_plan(tmp_path, "p1", [_finding("a"), _finding("b")])
    _write_plan(tmp_path, "p2", [_finding("a"), _finding("b")])
    report = det.aggregate(tmp_path, threshold=2)
    assert report["automation_candidates"]
    assert all(c["status"] == "unreviewed" for c in report["automation_candidates"])
    assert all(c["carrier"] in ("machine", "unknown") for c in report["automation_candidates"])


def test_main_writes_out_and_exits_zero(tmp_path, capsys):
    _write_plan(tmp_path, "p1", [_finding("m-key")])
    _write_plan(tmp_path, "p2", [_finding("m-key")])
    out = tmp_path / "report" / "candidates.json"
    rc = det.main(["--repo-root", str(tmp_path), "--out", str(out)])
    assert rc == 0
    stdout_report = json.loads(capsys.readouterr().out)
    assert "m-key" in {c["key"] for c in stdout_report["automation_candidates"]}
    assert json.loads(out.read_text(encoding="utf-8")) == stdout_report


def test_usage_error_exit2(tmp_path):
    assert det.main(["--repo-root", str(tmp_path), "--threshold", "0"]) == 2
    assert det.main(["--repo-root", str(tmp_path / "missing")]) == 2
