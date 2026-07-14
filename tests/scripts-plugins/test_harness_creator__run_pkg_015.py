"""PKG-015 governance-lint adapter contract tests."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-plugin-package-check"
    / "scripts" / "run-pkg-015.py"
)
SPEC = importlib.util.spec_from_file_location("run_pkg_015_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _score_log(log_dir: Path, records: list[dict]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "release-score.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_bootstrap_is_explicit_not_applicable(tmp_path):
    result, rc = MOD.run("demo", tmp_path / "missing", tmp_path / "out.json")
    assert rc == 0
    assert result["status"] == "not_applicable"
    assert result["source_exit_code"] == 3
    assert "bootstrap" in result["skip_reason"]


def test_sufficient_clean_history_is_pass(tmp_path):
    log_dir = tmp_path / "logs"
    records = [
        {
            "release": f"r{i % 3}",
            "findings": [{"rubric_item_id": "R1", "passed": True}],
        }
        for i in range(20)
    ]
    _score_log(log_dir, records)
    result, rc = MOD.run("demo", log_dir, tmp_path / "out.json")
    assert rc == 0
    assert result["status"] == "pass"
    assert result["analysis"]["bootstrap"] is False


def test_sustained_breach_is_fail(tmp_path):
    log_dir = tmp_path / "logs"
    records = [
        {
            "release": f"r{i % 3}",
            "findings": [{"rubric_item_id": "R1", "passed": False}],
        }
        for i in range(20)
    ]
    _score_log(log_dir, records)
    result, rc = MOD.run("demo", log_dir, tmp_path / "out.json")
    assert rc == 1
    assert result["status"] == "fail"
    assert result["source_exit_code"] == 2
    assert result["findings"][0]["rubric_item_id"] == "R1"


def test_main_writes_normalized_pkg_result(tmp_path, capsys):
    output = tmp_path / "nested" / "pkg-015.json"
    rc = MOD.main([
        "--plugin", "demo",
        "--log-dir", str(tmp_path / "missing"),
        "--out", str(output),
    ])
    stdout = json.loads(capsys.readouterr().out)
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert stdout == stored
    assert stored["pkg_id"] == "PKG-015"
    assert stored["status"] == "not_applicable"
