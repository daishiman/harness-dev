from __future__ import annotations

# /// script
# name: test-run-extract-blueprint-criteria-coverage
# purpose: run-extract-blueprint の feedback_contract criteria (IN1/OUT1) を実ゲート起動で被覆検証する。
#   plugin 直下 tests/ の網羅テストとは別に、skill-local に criteria id を紐付けて LLM-coverage の
#   被覆源 (validate-llm-coverage が skills/<skill>/tests を走査) を genuine に成立させる。
# inputs:
#   - scripts/fetch-snapshot.py --self-test / hooks/pre-fetch-authz-guard.py --self-test (IN1 決定論ゲート)
#   - scripts/doc-emit.py --check-apply (OUT1 fact/inference 明示区別の機械強制)
# outputs:
#   - pytest assertions (実 exit code)
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///

import json
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft7Validator

PLUGIN_ROOT = Path(__file__).resolve().parents[3]  # skills/run-extract-blueprint/tests -> plugin root
REPO_ROOT = Path(__file__).resolve().parents[5]
SKILL_ROOT = Path(__file__).resolve().parents[1]


def _run(rel_path, *args):
    return subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / rel_path), *args],
        capture_output=True, text=True,
    )


def test_in1_authz_fetch_deterministic_gates_exit0():
    """IN1: authz/fetch/mermaid/doc の決定論チェックが exit0 になることを実起動で確認する。

    fetch-snapshot と pre-fetch-authz-guard の self-test を subprocess で走らせ exit0 を要求する
    (瞬間負荷レバー・fail-closed 認可境界・budget 会計の決定論性を機械層で担保する契約)。
    """
    fetch = _run("scripts/fetch-snapshot.py", "--self-test")
    assert fetch.returncode == 0, f"fetch-snapshot self-test failed: {fetch.stderr}"
    authz = _run("hooks/pre-fetch-authz-guard.py", "--self-test")
    assert authz.returncode == 0, f"pre-fetch-authz-guard self-test failed: {authz.stderr}"


def test_out1_fact_inference_distinction_is_machine_enforced(tmp_path):
    """OUT1: 生成物が根拠+確度つき推測として事実と明示区別され、雛形生成に着手できる粒度である
    ことを受入検証する (reconstruction-rehearsal)。

    共有 C11 ゲート doc-emit.py --check-apply が「kind=inference かつ evidence_refs が blueprint anchor
    へ 100% 解決するレコードのみ通す / kind=fact や anchor 未解決を落とす」ことを実起動で確認し、
    fact/inference の明示区別と根拠追跡性が機械強制されている (無言 fact 化 0) ことを担保する。
    """
    blueprint = tmp_path / "blueprint.json"
    blueprint.write_text(json.dumps({"anchors": ["hero"]}), encoding="utf-8")
    # 根拠+確度つき推測 = 事実と明示区別された reconstruction-ready なレコード。
    grounded = tmp_path / "grounded.json"
    grounded.write_text(json.dumps([{
        "kind": "inference", "category": "adopt", "claim": "backend uses a queue",
        "own_context_ref": "our-system",
        "confidence": {"level": "high", "rationale": "observed async response headers"},
        "evidence_refs": ["hero"],
    }]), encoding="utf-8")
    ok = _run("scripts/doc-emit.py", "--check-apply", str(grounded), "--blueprint", str(blueprint))
    assert ok.returncode == 0, f"grounded inference should pass: {ok.stderr}"
    # 事実と区別されない無根拠主張 (kind=fact / anchor 未解決) は落とされる。
    ungrounded = tmp_path / "ungrounded.json"
    ungrounded.write_text(json.dumps([{
        "kind": "fact", "category": "copy", "evidence_refs": ["missing"],
    }]), encoding="utf-8")
    rejected = _run("scripts/doc-emit.py", "--check-apply", str(ungrounded), "--blueprint", str(blueprint))
    assert rejected.returncode == 1, "ungrounded fact-claim must be rejected (fail-closed)"


def test_task_graph_runtime_profile_matches_inventory_and_template_ssot():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "engine: task-graph" in skill
    assert "engine_profile: checklist-graph" in skill
    assert "full_task_spec_graph: false" in skill
    assert "fork: agent-team" in skill

    inventory = json.loads(
        (REPO_ROOT / "plugin-plans/extract-system-blueprint/component-inventory.json").read_text(encoding="utf-8")
    )
    component = next(item for item in inventory["components"] if item["id"] == "C01")
    assert component["goal_seek"] == {
        "activation_state": "semantic_evaluator_started",
        "engine": "task-graph",
        "engine_profile": "checklist-graph",
        "full_task_spec_graph": False,
        "fork": "agent-team",
        "spec": "eval-log/goal-spec.json",
        "progress": "eval-log/run-extract-blueprint-progress.json",
        "intermediate": "eval-log/run-extract-blueprint-intermediate.jsonl",
        "max_loops": 5,
    }
    template_root = REPO_ROOT / "plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts"
    for name in (
        "extract-ready-set-from-checklist.py",
        "build-self-reflection-entry.py",
        "extract-capability-dependency-graph.py",
        "build-capability-graph-knowledge-entry.py",
    ):
        assert (SKILL_ROOT / "scripts" / name).read_bytes() == (template_root / name).read_bytes()


def test_self_reflect_item_is_accepted_by_plugin_goal_seek_schema():
    schema = json.loads((PLUGIN_ROOT / "schemas/goal-seek-loop.schema.json").read_text(encoding="utf-8"))
    instance = {
        "skill": "run-extract-blueprint",
        "goal": "blueprint completion",
        "iteration": 1,
        "max_loops": 5,
        "engine": "task-graph",
        "fork_context": "agent-team",
        "checklist": [{
            "id": "C4",
            "text": "self-reflect task",
            "status": "pending",
            "depends_on": ["C1"],
            "created_iteration": 1,
            "available_from_iteration": 2,
        }, {
            "id": "C1",
            "text": "precondition",
            "status": "done",
        }],
        "status": "in_progress",
    }
    Draft7Validator(schema).validate(instance)


def _task_graph_verifier() -> str:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", skill, re.DOTALL)
    block = next(item for item in blocks if "task-graph consumption OK" in item)
    return re.search(r"<<'PY'\n(.*?)\nPY", block, re.DOTALL).group(1)


def test_task_graph_consumption_verifier_accepts_order_and_rejects_untraced_done(tmp_path):
    progress = tmp_path / "progress.json"
    intermediate = tmp_path / "intermediate.jsonl"
    data = {
        "engine": "task-graph",
        "max_loops": 5,
        "status": "completed",
        "checklist": [
            {"id": "C1", "status": "done"},
            {"id": "C2", "status": "done", "depends_on": ["C1"]},
        ],
    }
    progress.write_text(json.dumps(data), encoding="utf-8")
    intermediate.write_text("\n".join((
        json.dumps({"iteration": 0, "ready_set": ["C1"], "selected_item": "C1"}),
        json.dumps({"iteration": 1, "ready_set": ["C2"], "selected_item": "C2"}),
    )) + "\n", encoding="utf-8")
    accepted = subprocess.run(
        [sys.executable, "-", str(progress), str(intermediate)],
        input=_task_graph_verifier(), capture_output=True, text=True,
    )
    assert accepted.returncode == 0, accepted.stderr

    intermediate.write_text(
        json.dumps({"iteration": 0, "ready_set": ["C2"], "selected_item": "C2"}) + "\n",
        encoding="utf-8",
    )
    rejected = subprocess.run(
        [sys.executable, "-", str(progress), str(intermediate)],
        input=_task_graph_verifier(), capture_output=True, text=True,
    )
    assert rejected.returncode != 0
