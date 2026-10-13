"""P5 を SKIP した経路の intake.json が schema と P10 の公開前 hook を通り、深掘りした経路では通らない契約。"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate_intake_schema.py"
P10_HOOK = PLUGIN_ROOT / "hooks" / "pre-publish-schema-validate.py"
BASE_INTAKE = PLUGIN_ROOT / "fixtures" / "example-team-onboarding" / "intake.json"
SKIP_MARK = "skip:needs_excavation=false"


def _env() -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return env


def write_output(tmp_path: Path, *, techniques, needs_excavation=False, interview=True) -> Path:
    """output/<hint>/ に intake.json と interview.json を並べ、intake.json のパスを返す。"""
    out = tmp_path / "output" / "team-onboarding"
    out.mkdir(parents=True)
    intake = json.loads(BASE_INTAKE.read_text(encoding="utf-8"))
    section = intake["sections"]["3_purpose_excavator"]
    if techniques is not None:
        section["techniques_used"] = copy.deepcopy(techniques)
    if techniques == [SKIP_MARK]:
        section["rounds"] = 3  # SKIP 経路の rounds は interview.json の rounds[] の件数
    (out / "intake.json").write_text(json.dumps(intake, ensure_ascii=False), encoding="utf-8")
    if interview:
        payload = {"needs_excavation": needs_excavation, "abstract_answers": []}
        (out / "interview.json").write_text(json.dumps(payload), encoding="utf-8")
    return out / "intake.json"


def validate(intake_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(intake_path)],
        capture_output=True, text=True, env=_env(), check=False,
    )


def run_p10_hook(intake_path: Path) -> subprocess.CompletedProcess:
    command = f"python3 {PLUGIN_ROOT}/scripts/intake_publish_pipeline.py --intake {intake_path} --dry-run"
    payload = {"tool_input": {"command": command}, "cwd": str(intake_path.parent)}
    return subprocess.run(
        [sys.executable, str(P10_HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, env=_env(), check=False,
    )


def test_skip_path_intake_passes_schema_and_p10_hook(tmp_path):
    intake_path = write_output(tmp_path, techniques=[SKIP_MARK], needs_excavation=False)

    result = validate(intake_path)
    assert result.returncode == 0, result.stderr

    hook = run_p10_hook(intake_path)
    assert hook.returncode == 0, hook.stderr
    assert "PASS" in hook.stderr


def test_deep_path_with_real_techniques_still_passes(tmp_path):
    intake_path = write_output(tmp_path, techniques=None, needs_excavation=True)

    assert validate(intake_path).returncode == 0
    assert run_p10_hook(intake_path).returncode == 0


@pytest.mark.parametrize(
    ("case", "techniques", "needs_excavation", "interview", "message"),
    [
        ("deep-interview", [SKIP_MARK], True, True, "excavation_skip_matches_interview"),
        ("needs-excavation-as-int", [SKIP_MARK], 0, True, "excavation_skip_matches_interview"),
        ("no-interview", [SKIP_MARK], False, False, "fail-closed"),
        ("mixed-with-technique", [SKIP_MARK, "5whys"], False, True, "techniques_used"),
        ("empty", [], False, True, "techniques_used"),
        ("unknown-mark", ["skip:other"], False, True, "techniques_used"),
    ],
)
def test_skip_mark_outside_skip_path_is_rejected(tmp_path, case, techniques, needs_excavation, interview, message):
    intake_path = write_output(
        tmp_path, techniques=techniques, needs_excavation=needs_excavation, interview=interview
    )

    result = validate(intake_path)
    assert result.returncode == 1, (case, result.stderr)
    assert message in result.stderr, (case, result.stderr)

    hook = run_p10_hook(intake_path)
    assert hook.returncode == 2, (case, hook.stderr)
    assert "BLOCK" in hook.stderr
