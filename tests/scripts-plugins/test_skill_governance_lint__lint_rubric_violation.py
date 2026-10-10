"""lint-rubric-violation.py の違反率の定義と連続 release の判定を確かめる。

対象 script:
  plugins/skill-governance-lint/scripts/lint-rubric-violation.py

違反率 = release のレコードのうち rule に違反したレコードの数 ÷ release のレコードの数。
評価器の findings は passed を持たないので、passed が無い finding を違反として数えることを固定する。
fixture は tmp_path に書き、repo の eval-log は読まない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-rubric-violation.py"


@pytest.fixture()
def MOD():
    spec = importlib.util.spec_from_file_location("lint_rubric_violation_uut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(release, *items, passed=None):
    findings = []
    for item in items:
        f = {"id": item, "rubric_item_id": item, "severity": "low"}
        if passed is not None:
            f["passed"] = passed
        findings.append(f)
    return {"release": release, "findings": findings}


def _write_log(d: Path, records, name="2026-10-10-score.jsonl"):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _run(log_dir: Path, out: Path, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--log-dir", str(log_dir), "--out", str(out), *extra],
        capture_output=True,
        text=True,
    )


def test_findings_without_passed_count_as_violations(MOD):
    # 評価器の出力の形 (passed なし)。4 レコード中 1 つが FM-005 に違反 → 0.25
    recs = [_rec("r1", "FM-005"), _rec("r1"), _rec("r1"), _rec("r1")]
    by_item, total = MOD.compute(recs)
    assert total == 4
    assert by_item["FM-005"] == [("r1", 0.25)]


def test_passed_true_is_not_a_violation(MOD):
    recs = [_rec("r1", "FM-005", passed=True), _rec("r1", "FM-005", passed=False)]
    by_item, _ = MOD.compute(recs)
    assert by_item["FM-005"] == [("r1", 0.5)]


def test_duplicate_findings_in_one_record_count_once(MOD):
    recs = [_rec("r1", "BD-001", "BD-001"), _rec("r1")]
    by_item, _ = MOD.compute(recs)
    assert by_item["BD-001"] == [("r1", 0.5)]


def test_release_without_finding_is_zero_and_breaks_streak(MOD):
    # r2 に FM-002 の finding が無い → 0.0 が入り、r1・r3・r4 の高い率は連続にならない
    recs = [_rec("r1", "FM-002"), _rec("r2"), _rec("r3", "FM-002"), _rec("r4", "FM-002")]
    by_item, _ = MOD.compute(recs)
    assert by_item["FM-002"] == [("r1", 1.0), ("r2", 0.0), ("r3", 1.0), ("r4", 1.0)]
    assert MOD.detect(by_item, 3, 0.2) == []
    assert MOD.detect(by_item, 2, 0.2)[0]["recent_releases"] == ["r3", "r4"]


def test_releases_are_ordered_numerically(MOD):
    recs = [_rec("2026.10.0", "FM-001"), _rec("2026.9.0", "FM-001"), _rec("2026.11.0", "FM-001")]
    by_item, _ = MOD.compute(recs)
    assert [r for r, _ in by_item["FM-001"]] == ["2026.9.0", "2026.10.0", "2026.11.0"]


def test_cli_breach_exits_2(tmp_path):
    recs = []
    for rel in ("2026.8.0", "2026.9.0", "2026.10.0"):
        recs += [_rec(rel, "FM-003"), _rec(rel), _rec(rel)]  # 各 release 1/3 ≒ 0.33 > 0.2
    _write_log(tmp_path / "logs" / "core", recs)
    out = tmp_path / "trigger.json"
    r = _run(tmp_path / "logs", out, "--bootstrap-threshold", "1")
    assert r.returncode == 2, r.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [b["rubric_item_id"] for b in data["breached"]] == ["FM-003"]
    assert data["breached"][0]["recent_releases"] == ["2026.8.0", "2026.9.0", "2026.10.0"]


def test_cli_single_release_never_breaches(tmp_path):
    # 今の eval-log と同じ形 (全レコードが release "local")。連続 3 release が無いので招集しない
    _write_log(tmp_path / "logs", [_rec("local", "FM-005")] * 5)
    out = tmp_path / "trigger.json"
    r = _run(tmp_path / "logs", out, "--bootstrap-threshold", "1")
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["breached"] == []


def test_cli_malformed_lines_are_skipped_not_traceback(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    (d / "x-score.jsonl").write_text('{not json\n[1, 2]\n' + json.dumps(_rec("r1", "FM-001")) + "\n", encoding="utf-8")
    out = tmp_path / "trigger.json"
    r = _run(d, out, "--bootstrap-threshold", "1")
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["total_records"] == 1
    assert [s.rsplit(":", 1)[1] for s in data["skipped_lines"]] == ["1", "2"]


def test_cli_bootstrap_and_missing_dir_exit_3(tmp_path):
    _write_log(tmp_path / "logs", [_rec("r1", "FM-001")])
    out = tmp_path / "trigger.json"
    assert _run(tmp_path / "logs", out).returncode == 3
    assert json.loads(out.read_text(encoding="utf-8"))["bootstrap"] is True
    assert _run(tmp_path / "ghost", out).returncode == 3


# ---------------------------------------------------------------------------
# 0.3.0: 番号の無い release の並び順と、入力の崩れ
# ---------------------------------------------------------------------------
def test_unnumbered_releases_sort_before_numbered(MOD):
    recs = [_rec("2026.10.0", "FM-001"), _rec("local", "FM-001"), _rec("2026.9.0", "FM-001"), {"findings": []}]
    by_item, _ = MOD.compute(recs)
    assert [r for r, _ in by_item["FM-001"]] == ["local", "unknown", "2026.9.0", "2026.10.0"]


def test_unnumbered_release_does_not_hide_a_breach(tmp_path):
    # 3 release 続けて違反率 50% のログに release の無いレコードを足しても、招集を見落とさない
    recs = []
    for rel in ("2026.8.0", "2026.9.0", "2026.10.0"):
        recs += [_rec(rel, "FM-003"), _rec(rel)]
    recs += [{"findings": []}, _rec("local")]
    _write_log(tmp_path / "logs", recs)
    out = tmp_path / "trigger.json"
    r = _run(tmp_path / "logs", out, "--bootstrap-threshold", "1")
    assert r.returncode == 2, r.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["breached"][0]["recent_releases"] == ["2026.8.0", "2026.9.0", "2026.10.0"]


def test_odd_rule_ids_do_not_traceback(MOD):
    recs = [
        {"release": "r1", "findings": [{"id": 5}, {"id": "FM-001"}, {"id": ["x"]}, {"rubric_item_id": {"a": 1}}]},
        {"release": "r1", "findings": []},
    ]
    by_item, total = MOD.compute(recs)
    assert total == 2
    assert by_item["5"] == [("r1", 0.5)]
    assert by_item["FM-001"] == [("r1", 0.5)]
    assert by_item["?"] == [("r1", 0.5)]


def test_cli_non_utf8_log_is_skipped(tmp_path):
    d = tmp_path / "logs"
    _write_log(d, [_rec("r1", "FM-001")])
    (d / "bad-score.jsonl").write_bytes(b"\xff\xfe{}\n")
    out = tmp_path / "trigger.json"
    r = _run(d, out, "--bootstrap-threshold", "1")
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["total_records"] == 1
    assert any("bad-score.jsonl: unreadable (UnicodeDecodeError)" in s for s in data["skipped_lines"])


def test_cli_out_parent_is_created(tmp_path):
    _write_log(tmp_path / "logs", [_rec("r1", "FM-001")])
    out = tmp_path / "nested" / "dir" / "trigger.json"
    r = _run(tmp_path / "logs", out, "--bootstrap-threshold", "1")
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["bootstrap"] is False


def test_cli_unwritable_out_exits_1_without_traceback(tmp_path):
    _write_log(tmp_path / "logs", [_rec("r1", "FM-001")])
    r = _run(tmp_path / "logs", tmp_path, "--bootstrap-threshold", "1")  # --out がディレクトリ
    assert r.returncode == 1
    assert "Traceback" not in r.stderr
    assert "cannot write" in r.stderr


@pytest.mark.parametrize("extra", [("--n", "0"), ("--threshold", "1.5"), ("--bootstrap-threshold", "-1")])
def test_cli_out_of_range_arguments_are_usage_errors(tmp_path, extra):
    _write_log(tmp_path / "logs", [_rec("r1", "FM-001")])
    out = tmp_path / "trigger.json"
    r = _run(tmp_path / "logs", out, *extra)
    assert r.returncode == 2
    assert "usage:" in r.stderr
    assert not out.exists()
