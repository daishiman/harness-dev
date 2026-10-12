"""run-skill-rubric-governance の lint-rubric-violation.py が score ログだけを数えることを確かめる。

対象 script（skill-governance-lint の同名 script とは別物）:
  plugins/harness-creator/skills/run-skill-rubric-governance/scripts/lint-rubric-violation.py

以前は --logs 直下の *.jsonl をすべて読み、score の無いレコードも total に数えていた。
governance log（$SKILL_DIR/log）を渡すと by_rule が空になり「違反なし」に見えた。
ここでは次を固定する。

- score を持つレコードが 0 件なら exit 2（governance log だけのディレクトリ、空・存在しないディレクトリ）
- score ログ（*-score.jsonl を再帰で探す）の findings を rule ごとに数える
- score の無いレコードは total に入れず、skipped_no_score に件数を出す

fixture は tmp_path に書き、repo の eval-log は読まない。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-rubric-governance"
          / "scripts" / "lint-rubric-violation.py")


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=30)


def _write_jsonl(path: Path, records) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [r if isinstance(r, str) else json.dumps(r) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _score(score, *rules):
    return {"score": score, "passed": score >= 80,
            "findings": [{"id": r, "rubric_item_id": r, "severity": "low"} for r in rules]}


GOVERNANCE_RECORDS = [
    {"proposal_id": "PROP-1", "bump": "minor", "findings": [{"id": "PD-002"}]},
    {"proposal_id": "PROP-2", "bump": "patch"},
]


def test_governance_log_only_dir_exits_2(tmp_path):
    log_dir = tmp_path / "log"
    _write_jsonl(log_dir / "governance-log.jsonl", GOVERNANCE_RECORDS)
    proc = _run("--logs", str(log_dir), "--rule", "PD-002")
    assert proc.returncode == 2, proc.stdout
    assert proc.stdout == ""
    assert "score を持つレコードが無い" in proc.stderr


def test_empty_and_missing_dir_exit_2(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _run("--logs", str(empty)).returncode == 2
    # 以前は {"total": 0, ...} を出して exit 0 だった
    proc = _run("--logs", str(tmp_path / "missing"))
    assert proc.returncode == 2 and proc.stdout == ""


def test_counts_findings_by_rule_from_score_logs(tmp_path):
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-09-score.jsonl",
                 [_score(90, "PD-002", "FM-005"), _score(70, "PD-002")])
    _write_jsonl(log_dir / "other" / "nested" / "2026-10-10-score.jsonl",
                 [_score(100), {"score": 85, "findings": [{"rubric_item_id": "FM-005"}, "bad", {"id": 3}]}])
    # score ログでない jsonl は読まない
    _write_jsonl(log_dir / "transcript.jsonl", [_score(50, "PD-002")] * 5)
    proc = _run("--logs", str(log_dir))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["total"] == 4
    assert out["by_rule"] == {"PD-002": 2, "FM-005": 2, "3": 1}
    assert out["score_logs"] == 2

    proc = _run("--logs", str(log_dir), "--rule", "PD-002")
    assert json.loads(proc.stdout)["by_rule"] == {"PD-002": 2}


def test_records_without_score_are_not_counted(tmp_path):
    log_dir = tmp_path / "eval-log"
    _write_jsonl(log_dir / "core" / "2026-10-10-score.jsonl",
                 [_score(90, "PD-002")] + GOVERNANCE_RECORDS + [{"score": "90"}, {"score": False}, "not json"])
    proc = _run("--logs", str(log_dir), "--rule", "PD-002")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    # score の無いレコードの findings（PROP-1 の PD-002）も数えない
    assert (out["total"], out["by_rule"]) == (1, {"PD-002": 1})
    assert (out["skipped_no_score"], out["skipped_invalid"]) == (4, 1)
    assert "数えなかったレコード 5 件" in proc.stderr
