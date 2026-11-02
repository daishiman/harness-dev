"""実行基盤の異なる証跡を再利用しないことを確認する。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/harness-creator/skills/run-skill-live-trial/scripts"


def _planner():
    spec = importlib.util.spec_from_file_location("runtime_trial_plan", SCRIPTS / "plan-live-trials.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evidence(tmp_path, runtime):
    trial = tmp_path / "demo/run-demo/live-trial/20261102T000000"
    trial.mkdir(parents=True)
    transcript = trial / "transcript.jsonl"
    transcript.write_text('{"native":true}\n')
    doc = {
        "target_skill": "demo:run-demo", "tier": "live",
        "overall": {"verdict": "PASS"}, "skill_dir_tree_sha": "same-source",
        "scenario_id": "same-business-goal", "environment": {},
        "transcript_sha256": hashlib.sha256(transcript.read_bytes()).hexdigest(),
    }
    if runtime is not None:
        doc["environment"]["runtime"] = runtime
    verdict = trial / "verdict.json"
    verdict.write_text(json.dumps(doc))
    return verdict


def test_codex_request_does_not_reuse_legacy_claude_pass(tmp_path):
    _evidence(tmp_path, None)
    module = _planner()
    validator = SimpleNamespace(validate_schema=lambda *_: [])
    path, reason, drift, evidence_runtime = module._valid_reusable_evidence(
        validator, {}, tmp_path, "demo", "run-demo", "same-source",
        {"same-business-goal"}, runtime="codex",
    )
    assert path is None
    assert reason == "runtime-mismatch"
    assert drift is None
    assert evidence_runtime is None


def test_matching_runtime_still_requires_native_verification(tmp_path):
    _evidence(tmp_path, "codex")
    module = _planner()
    validator = SimpleNamespace(
        validate_schema=lambda *_: [],
        validate_runtime_evidence=lambda *_: ["native activation missing"],
    )
    path, reason, drift, evidence_runtime = module._valid_reusable_evidence(
        validator, {}, tmp_path, "demo", "run-demo", "same-source",
        {"same-business-goal"}, runtime="codex",
    )
    assert path is None
    assert reason == "invalid-runtime-evidence"
    assert drift is None
    assert evidence_runtime is None


def test_legacy_claude_remains_the_default(tmp_path):
    expected = _evidence(tmp_path, None)
    module = _planner()
    validator = SimpleNamespace(validate_schema=lambda *_: [])
    path, reason, drift, evidence_runtime = module._valid_reusable_evidence(
        validator, {}, tmp_path, "demo", "run-demo", "same-source",
        {"same-business-goal"},
    )
    assert path == expected
    assert reason == "current-pass"
    assert drift is None
    assert evidence_runtime is None


def test_receipt_reports_its_own_runtime_when_plan_runtime_differs(tmp_path):
    """受領書があるとき、計画 runtime ではなく証跡の runtime を返す。"""
    plugin, skill = "demo", "run-demo"
    eval_root = tmp_path / "eval-log"
    trial = eval_root / plugin / skill / "live-trial" / "20261102T000000"
    trial.mkdir(parents=True)
    transcript = trial / "transcript.jsonl"
    transcript.write_text('{"native":true}\n')
    verdict = trial / "verdict.json"
    verdict.write_text(json.dumps({
        "target_skill": f"{plugin}:{skill}", "tier": "live",
        "overall": {"verdict": "PASS"}, "skill_dir_tree_sha": "same-source",
        "scenario_id": "same-business-goal",
        "environment": {"runtime": "codex"},
        "transcript_sha256": hashlib.sha256(transcript.read_bytes()).hexdigest(),
    }))
    receipt = eval_root / plugin / skill / "criteria-test" / "scenario-verdict.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({
        "criteria_results": {
            "OUT1": {
                "verify_by": "live-trial",
                "live_trial_verdict_ref": (
                    f"eval-log/{plugin}/{skill}/live-trial/20261102T000000/verdict.json"
                ),
            },
        },
    }))
    module = _planner()
    validator = SimpleNamespace(
        validate_schema=lambda *_: [],
        validate_runtime_evidence=lambda *_: [],
    )
    path, reason, drift, evidence_runtime = module._valid_reusable_evidence(
        validator, {}, eval_root, plugin, skill, "same-source",
        {"same-business-goal"}, runtime="claude",
    )
    assert path == verdict
    assert reason == "current-pass"
    assert drift is None
    assert evidence_runtime == "codex"
