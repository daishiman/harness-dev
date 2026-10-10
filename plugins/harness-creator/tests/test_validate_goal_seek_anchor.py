from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    ROOT
    / "plugins/harness-creator/skills/run-build-skill/templates/goal-seek-runtime/scripts"
    / "validate-inline-goal-seek-anchor.py"
)
SPEC = importlib.util.spec_from_file_location("validate_goal_seek_anchor", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    goal = "初回のゴール"
    progress = tmp_path / "progress.json"
    intermediate = tmp_path / "intermediate.jsonl"
    progress.write_text(
        json.dumps({"original_goal_hash": hashlib.sha256(goal.encode()).hexdigest()}),
        encoding="utf-8",
    )
    row = {
        "iteration": 0,
        "original_goal": goal,
        "current_goal_snapshot": goal,
        "delta_from_original": "",
        "merged_directive_for_next": goal,
        "drift_signal": "initial",
    }
    intermediate.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return progress, intermediate, goal


def test_valid_anchor_passes(tmp_path: Path) -> None:
    progress, intermediate, _goal = _fixture(tmp_path)
    code, message = MODULE.validate(progress, intermediate)
    assert code == 0
    assert "PASS" in message


def test_missing_hash_fails_closed(tmp_path: Path) -> None:
    progress, intermediate, _goal = _fixture(tmp_path)
    progress.write_text("{}", encoding="utf-8")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "missing/drift" in message


def test_drift_and_missing_trace_fail_closed(tmp_path: Path) -> None:
    progress, intermediate, goal = _fixture(tmp_path)
    row = {
        "iteration": 1,
        "original_goal": goal + " drift",
        "current_goal_snapshot": "",
        "delta_from_original": "",
        "merged_directive_for_next": "",
        "drift_signal": "widening",
    }
    with intermediate.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    assert MODULE.validate(progress, intermediate)[0] == 1
    assert MODULE.validate(progress, tmp_path / "missing.jsonl")[0] == 1


def test_non_object_progress_fails_without_traceback(tmp_path: Path) -> None:
    progress, intermediate, _goal = _fixture(tmp_path)
    progress.write_text("[]", encoding="utf-8")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "object" in message


def test_non_utf8_and_deeply_nested_inputs_exit_2(tmp_path: Path) -> None:
    # UTF-16（Windows PowerShell 5 の > の既定）、0xff 始まり、極端に深い入れ子は、
    # 宣言どおり exit 2（IO/JSON error）で返し、traceback を出さない。
    progress, intermediate, _goal = _fixture(tmp_path)
    original = progress.read_text(encoding="utf-8")
    progress.write_text(original, encoding="utf-16")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 2
    assert "UnicodeDecodeError" in message

    progress.write_text(original, encoding="utf-8")
    intermediate.write_bytes(b"\xff" + intermediate.read_bytes())
    assert MODULE.validate(progress, intermediate)[0] == 2

    progress.write_text("[" * 200_000 + "]" * 200_000, encoding="utf-8")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 2
    assert "RecursionError" in message


def test_main_reports_decode_error_on_stderr(tmp_path: Path, capsys) -> None:
    progress, intermediate, _goal = _fixture(tmp_path)
    intermediate.write_bytes(b"\xff\xfe")
    assert MODULE.main([str(progress), str(intermediate)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "JSON を読めない" in captured.err


def _append_row(intermediate: Path, goal: str, iteration: object) -> None:
    row = {
        "iteration": iteration,
        "original_goal": goal,
        "current_goal_snapshot": goal,
        "delta_from_original": "",
        "merged_directive_for_next": goal,
        "drift_signal": "aligned",
    }
    with intermediate.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_iterations_must_be_consecutive_integers(tmp_path: Path) -> None:
    progress, intermediate, goal = _fixture(tmp_path)
    _append_row(intermediate, goal, 1)
    assert MODULE.validate(progress, intermediate)[0] == 0

    _append_row(intermediate, goal, 3)
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "連番でない" in message


def test_iteration_may_start_at_one_but_not_bool(tmp_path: Path) -> None:
    # 既存の記録には 1 始まりのものがあるため、始まりの値は固定しない。
    progress, intermediate, goal = _fixture(tmp_path)
    intermediate.write_text("", encoding="utf-8")
    _append_row(intermediate, goal, 1)
    _append_row(intermediate, goal, 2)
    assert MODULE.validate(progress, intermediate)[0] == 0

    intermediate.write_text("", encoding="utf-8")
    _append_row(intermediate, goal, True)
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "整数でない" in message


def test_non_string_original_goal_is_named(tmp_path: Path) -> None:
    progress, intermediate, _goal = _fixture(tmp_path)
    intermediate.write_text("", encoding="utf-8")
    _append_row(intermediate, ["not", "a", "string"], 0)  # type: ignore[arg-type]
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "文字列でない" in message


def test_lone_surrogate_goal_is_violation_without_traceback(tmp_path: Path, capsys) -> None:
    # JSON の "\ud800" は対になっていない surrogate として読まれ、UTF-8 で表せない。
    # hash を固定できないので契約違反 (exit 1) とし、UnicodeEncodeError の traceback を出さない。
    progress, intermediate, _goal = _fixture(tmp_path)
    row = json.loads(intermediate.read_text(encoding="utf-8"))
    row["original_goal"] = "\ud800"
    intermediate.write_text(json.dumps(row) + "\n", encoding="utf-8")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "surrogate" in message
    assert MODULE.main([str(progress), str(intermediate)]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_missing_file_is_contract_violation_not_io_error(tmp_path: Path) -> None:
    # 周回の証跡が無いことは違反 (exit 1)。header の exit 2 は「在るファイルを読めない」場合だけ。
    progress, intermediate, _goal = _fixture(tmp_path)
    assert MODULE.validate(tmp_path / "missing.json", intermediate)[0] == 1
    assert MODULE.validate(progress, tmp_path)[0] == 1
    header = SCRIPT.read_text(encoding="utf-8").split('"""', 1)[0]
    assert "どちらかが無い" in header


def test_progress_iteration_must_match_last_row(tmp_path: Path) -> None:
    progress, intermediate, goal = _fixture(tmp_path)
    _append_row(intermediate, goal, 1)
    data = json.loads(progress.read_text(encoding="utf-8"))

    data["iteration"] = 1
    progress.write_text(json.dumps(data), encoding="utf-8")
    assert MODULE.validate(progress, intermediate)[0] == 0

    data["iteration"] = 2  # 周回の記録漏れ
    progress.write_text(json.dumps(data), encoding="utf-8")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "一致しない" in message

    data["iteration"] = "1"
    progress.write_text(json.dumps(data), encoding="utf-8")
    code, message = MODULE.validate(progress, intermediate)
    assert code == 1
    assert "整数でない" in message


def test_progress_without_iteration_key_skips_count_check(tmp_path: Path) -> None:
    # run-skill-feedback の progress は iteration を持たないので、照合しない。
    progress, intermediate, goal = _fixture(tmp_path)
    _append_row(intermediate, goal, 1)
    assert "iteration" not in json.loads(progress.read_text(encoding="utf-8"))
    assert MODULE.validate(progress, intermediate)[0] == 0
