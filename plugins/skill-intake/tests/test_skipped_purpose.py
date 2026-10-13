"""P5 skip 経路で purpose.json を作り、P11 decide-mode.py まで止まらずに通る契約。"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUILD_SKIPPED = PLUGIN_ROOT / "skills" / "run-skill-intake" / "scripts" / "build-skipped-purpose.py"
PURPOSE_SCHEMA = PLUGIN_ROOT / "skills" / "run-skill-intake" / "schemas" / "phase5-purpose.schema.json"
INTERVIEW_SCHEMA = PLUGIN_ROOT / "skills" / "run-intake-interview" / "schemas" / "output.schema.json"
VALIDATE_INTERVIEW = PLUGIN_ROOT / "skills" / "run-intake-interview" / "scripts" / "validate-interview-json.py"
DECIDE_MODE = PLUGIN_ROOT / "skills" / "run-intake-next-action" / "scripts" / "decide-mode.py"

SLOTS = [
    "input_spec.sources", "input_spec.trigger", "input_spec.frequency", "input_spec.raw_materials",
    "output_spec.sink", "output_spec.format", "output_spec.granularity", "output_spec.audience", "output_spec.cadence",
]


def concrete_interview() -> dict:
    """needs_excavation=false (抽象回答なし) の interview.json。"""
    return {
        "filled_ratio": 1.0,
        "five_axes_complete": True,
        "unresolved": [],
        "needs_excavation": False,
        "abstract_answers": [],
        "five_axes": {
            "rows": [
                {"name": "出力先", "content": "Slack #sales", "depth": "standard"},
                {"name": "情報源", "content": "kintone 商談アプリ", "depth": "standard"},
                {"name": "共有相手", "content": "営業チーム", "depth": "standard"},
                {"name": "真の課題", "content": "商談の停滞に週明けまで誰も気づかない", "depth": "standard"},
                {"name": "ナレッジ資産", "content": "過去の失注理由メモ", "depth": "shallow"},
            ],
            "pipeline": {
                "ingest": "kintone API",
                "analysis": "14日以上更新のない商談を抽出",
                "storage": "なし",
                "retrieval": "Slack 投稿",
                "update": "daily",
            },
        },
        "intent_contract": {
            "input_spec": {
                "sources": ["kintone 商談アプリ"],
                "trigger": "毎朝 9 時",
                "frequency": "daily",
                "raw_materials": ["商談レコード"],
            },
            "output_spec": {
                "sink": "Slack #sales",
                "format": "bullet",
                "granularity": "商談 1 件 1 行",
                "audience": "営業チーム",
                "cadence": "daily",
            },
            "slot_status": {slot: {"filled": True, "source": "direct_answer"} for slot in SLOTS},
        },
        "pending_probes": [],
        "qa_log": [
            {
                "qid": "Q01", "axis": "output", "question_text": "結果をどこに出しますか?",
                "selected_option": "Slack", "raw_answer": "Slack の #sales", "normalized_answer": "Slack #sales",
            },
            {
                "qid": "Q04", "axis": "true-pain", "question_text": "いちばん困っていることは?",
                "selected_option": "その他", "raw_answer": "止まった商談に月曜まで気づけない",
                "normalized_answer": "停滞商談の発見が遅れる",
            },
        ],
    }


def build(tmp_path: Path, interview: dict) -> tuple[subprocess.CompletedProcess[str], Path]:
    interview_path = tmp_path / "interview.json"
    purpose_path = tmp_path / "purpose.json"
    interview_path.write_text(json.dumps(interview, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(BUILD_SKIPPED), str(interview_path), "--out", str(purpose_path)],
        capture_output=True, text=True, check=False,
    )
    return result, purpose_path


def test_fixture_is_a_valid_skip_path_interview(tmp_path: Path) -> None:
    interview = concrete_interview()
    Draft7Validator(json.loads(INTERVIEW_SCHEMA.read_text(encoding="utf-8"))).validate(interview)
    path = tmp_path / "interview.json"
    path.write_text(json.dumps(interview, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATE_INTERVIEW), str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_skipped_purpose_is_schema_valid_and_deterministic(tmp_path: Path) -> None:
    result, purpose_path = build(tmp_path, concrete_interview())
    assert result.returncode == 0, result.stderr
    first = purpose_path.read_bytes()
    purpose = json.loads(first)
    Draft7Validator(json.loads(PURPOSE_SCHEMA.read_text(encoding="utf-8"))).validate(purpose)
    assert purpose["techniques_used"] == ["skip:needs_excavation=false"]
    assert purpose["agreement_loop_detected"] is False
    assert purpose["true_purpose"] == {
        "verb_object": "商談レコードを営業チーム向けにSlack #salesへ出力する",
        "underlying_motivation": "商談の停滞に週明けまで誰も気づかない",
    }
    assert [r["answer"] for r in purpose["rounds"]] == ["停滞商談の発見が遅れる"]

    again, _ = build(tmp_path, concrete_interview())
    assert again.returncode == 0, again.stderr
    assert purpose_path.read_bytes() == first


def test_rounds_fall_back_to_whole_qa_log_without_true_pain_row(tmp_path: Path) -> None:
    interview = concrete_interview()
    interview["qa_log"] = interview["qa_log"][:1]
    result, purpose_path = build(tmp_path, interview)
    assert result.returncode == 0, result.stderr
    assert [r["question"] for r in json.loads(purpose_path.read_text(encoding="utf-8"))["rounds"]] == ["結果をどこに出しますか?"]


@pytest.mark.parametrize("violation", ["needs-excavation", "abstract-left", "no-true-pain-row", "empty-sink"])
def test_rejects_interview_that_cannot_skip_p5(tmp_path: Path, violation: str) -> None:
    interview = copy.deepcopy(concrete_interview())
    if violation == "needs-excavation":
        interview["needs_excavation"] = True
    elif violation == "abstract-left":
        interview["abstract_answers"] = [{"axis": "true-pain", "answer": "いい感じに", "reason": "抽象語"}]
    elif violation == "no-true-pain-row":
        interview["five_axes"]["rows"] = [r for r in interview["five_axes"]["rows"] if r["name"] != "真の課題"]
    else:
        interview["intent_contract"]["output_spec"]["sink"] = " "
    result, purpose_path = build(tmp_path, interview)
    assert result.returncode == 1
    assert "violation" in result.stderr
    assert not purpose_path.exists()


@pytest.mark.parametrize("rows", [{"真の課題": "停滞商談"}, "真の課題", None])
def test_rejects_rows_that_are_not_a_list(tmp_path: Path, rows) -> None:
    interview = copy.deepcopy(concrete_interview())
    interview["five_axes"]["rows"] = rows
    result, purpose_path = build(tmp_path, interview)
    assert result.returncode == 1
    assert "violation" in result.stderr
    assert "Traceback" not in result.stderr
    assert not purpose_path.exists()


def test_non_utf8_interview_is_io_error(tmp_path: Path) -> None:
    interview_path = tmp_path / "interview.json"
    interview_path.write_bytes(json.dumps(concrete_interview(), ensure_ascii=False).encode("cp932"))
    purpose_path = tmp_path / "purpose.json"
    result = subprocess.run(
        [sys.executable, str(BUILD_SKIPPED), str(interview_path), "--out", str(purpose_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert not purpose_path.exists()


def test_help_exits_zero(tmp_path: Path) -> None:
    result = subprocess.run([sys.executable, str(BUILD_SKIPPED), "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "--out" in result.stdout


def test_next_action_reads_skipped_purpose_without_exit_3(tmp_path: Path) -> None:
    result, purpose_path = build(tmp_path, concrete_interview())
    assert result.returncode == 0, result.stderr
    inputs = {
        "kickoff": {"pattern": "A"},
        "options": {"selected_integrations": [], "rejected": []},
        "summary": {"gate_a": "approved"},
    }
    for name, payload in inputs.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "next-action.json"
    decided = subprocess.run(
        [
            sys.executable, str(DECIDE_MODE),
            "--kickoff", str(tmp_path / "kickoff.json"),
            "--purpose", str(purpose_path),
            "--options", str(tmp_path / "options.json"),
            "--summary", str(tmp_path / "summary.json"),
            "--out", str(out),
            "--allow-skip",
        ],
        capture_output=True, text=True, check=False,
        env={**os.environ, "INTAKE_ALLOW_SKIP_PUBLISH_GATE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert decided.returncode == 0, decided.stderr
    # verb_object が空なら mode=E (判定不能) に落ちる。skip 経路でも kickoff の pattern が保たれる。
    assert json.loads(out.read_text(encoding="utf-8"))["mode"] == "A"
