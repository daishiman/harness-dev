"""live-trial-verdict.py の scenario 契約ゲート (HarnessHub-dyxr)。

verdict は従来 scenario_id の一致しか見ておらず、scenario 正本が要求する
required_observations を一件も回収していない run でも PASS を書き出せた。ここでは
「未回収項目が受領書へ機械的に列挙されること」と「task_args_template と実 args の
乖離が verdict に現れること」を固定する。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = (
    REPO
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-skill-live-trial"
    / "scripts"
    / "live-trial-verdict.py"
)
DEV_GRAPH_SCENARIOS = (
    REPO / "plugins" / "dev-graph" / "tests" / "fixtures" / "live-trial-positive-scenarios.json"
)
C14_SCENARIO_ID = "C14-OUT1-positive-macro-decomposition-r15"


def _load_verdict_module():
    spec = importlib.util.spec_from_file_location("live_trial_verdict", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERDICT = _load_verdict_module()

SCENARIO_FIXTURE = {
    "schema_version": "1.0.0",
    "scenarios": [
        {
            "scenario_id": "CXX-OUT1-positive-fixture",
            "component_id": "CXX",
            "skill": "run-fixture-skill",
            "criterion_id": "OUT1",
            "mode": "positive",
            "resource_budget": {
                "max_wall_clock_s": 60,
                "max_total_tokens": 1000,
            },
            "task_args_template": "--repo-root <contained-fixture-repo> --binding beads",
            "task_contract": {
                "required_fragments": ["upsert-node.py --input", "promotion-patch.json"],
                "forbidden_fragments": ["--operation apply-lifecycle-request"],
            },
            "fixture_contract": "A contained repository exercises the publication gate.",
            "required_observations": [
                "the draft node is excluded from the publication candidate set",
                "the promoted node is admitted",
                "zero issue creation is attributable to the draft gate",
            ],
        }
    ],
}


def _undeclared_flags(skill: str, task_args_template: str) -> list[str]:
    """template が名指しする flag のうち、対象 SKILL.md の argument-hint に無いものを返す。"""
    skill_md = REPO / "plugins" / "dev-graph" / "skills" / skill / "SKILL.md"
    hint = next(
        line
        for line in skill_md.read_text(encoding="utf-8").splitlines()
        if line.startswith("argument-hint:")
    )
    declared = set(VERDICT._FLAG_PATTERN.findall(hint))
    used = set(VERDICT._FLAG_PATTERN.findall(task_args_template))
    return sorted(used - declared)


def _skill_dir(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "skills" / "run-fixture-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# fixture skill\n", encoding="utf-8")
    return skill_dir


def _scenario_file(tmp_path: Path) -> Path:
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps(SCENARIO_FIXTURE, ensure_ascii=False), encoding="utf-8")
    return path


def _run(
    tmp_path: Path,
    *extra: str,
    args: str,
    materialize_evidence: bool = True,
    task_text: str = "upsert-node.py --input promotion-patch.json\n",
) -> tuple[int, dict | None]:
    workdir = tmp_path / "trial"
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "task.md").write_text(task_text, encoding="utf-8")
    transcript = workdir / "source-transcript.jsonl"
    transcript.write_text(
        json.dumps({
            "type": "assistant",
            "message": {
                "id": "msg-budget-fixture",
                "model": "claude-test",
                "content": [{
                    "type": "tool_use",
                    "name": "Skill",
                    "input": {"skill": "dev-graph:run-fixture-skill"},
                }],
                "usage": {
                    "input_tokens": 10,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 30,
                    "output_tokens": 40,
                },
            },
        }) + "\n",
        encoding="utf-8",
    )
    goal_evaluation = workdir / "goal-evaluation.json"
    goal_evaluation.write_text(json.dumps({
        "result": "PASS",
        "blockers": [],
        "evaluator": {"mode": "fresh-independent-context", "id": "pytest-evaluator"},
        "transcript_sha256": VERDICT.sha256_file(transcript),
        "evidence_refs": ["task.md", "source-transcript.jsonl"],
    }), encoding="utf-8")
    poll_state = workdir / "poll-state.json"
    poll_state.write_text(json.dumps({
        "elapsed": 10,
        "started_at_unix": 100.0,
        "observed_at_unix": 110.0,
    }), encoding="utf-8")
    if materialize_evidence:
        for flag, value in zip(extra, extra[1:]):
            if flag != "--observation":
                continue
            _index, _separator, evidence_ref = value.partition("=")
            evidence_path = workdir / evidence_ref.partition("#")[0]
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text("{}\n", encoding="utf-8")
    argv = [
        "--workdir", str(workdir),
        "--target-skill", "dev-graph:run-fixture-skill",
        "--skill-dir", str(_skill_dir(tmp_path)),
        "--args", args,
        "--launch", "PASS",
        "--completion", "PASS",
        "--goal-result", "PASS",
        "--goal-evaluation", str(goal_evaluation),
        "--transcript", str(transcript),
        "--poll-state", str(poll_state),
        "--wall-clock-s", "10",
        *extra,
    ]
    code = VERDICT.main(argv)
    out = workdir / "verdict.json"
    doc = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
    return code, doc


# --------------------------------------------------------------------------- #
# 単体: scenario 解決と観測宣言の解釈
# --------------------------------------------------------------------------- #
def test_load_scenario_requires_a_unique_id_and_non_empty_observations(tmp_path: Path) -> None:
    path = _scenario_file(tmp_path)
    scenario = VERDICT.load_scenario(path, "CXX-OUT1-positive-fixture")
    assert len(scenario["required_observations"]) == 3

    with pytest.raises(ValueError, match="exactly one scenario"):
        VERDICT.load_scenario(path, "CXX-OUT1-does-not-exist")

    duplicated = tmp_path / "dup.json"
    duplicated.write_text(
        json.dumps({"scenarios": SCENARIO_FIXTURE["scenarios"] * 2}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="exactly one scenario"):
        VERDICT.load_scenario(duplicated, "CXX-OUT1-positive-fixture")

    empty = tmp_path / "empty.json"
    empty.write_text(
        json.dumps({"scenarios": [{"scenario_id": "X", "required_observations": []}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="required_observations"):
        VERDICT.load_scenario(empty, "X")


def test_observation_claims_reject_out_of_range_and_duplicate_indexes() -> None:
    assert VERDICT.parse_observation_claims(["1=a.json", "3=b.json"], 3) == {
        1: "a.json",
        3: "b.json",
    }
    with pytest.raises(ValueError, match="範囲外"):
        VERDICT.parse_observation_claims(["4=a.json"], 3)
    with pytest.raises(ValueError, match="重複"):
        VERDICT.parse_observation_claims(["1=a.json", "1=b.json"], 3)
    with pytest.raises(ValueError, match="N=<evidence ref>"):
        VERDICT.parse_observation_claims(["1"], 3)


def test_observation_evidence_must_exist_inside_the_run_directory(tmp_path: Path) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=missing.json#publication_gate",
        args="--repo-root /tmp/fixture-repo --binding beads",
        materialize_evidence=False,
    )
    assert code == 2
    assert doc is None

    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=../outside.json#publication_gate",
        args="--repo-root /tmp/fixture-repo --binding beads",
        materialize_evidence=False,
    )
    assert code == 2
    assert doc is None


def test_args_divergence_measures_flags_not_placeholders() -> None:
    same = VERDICT.args_divergence(
        "--repo-root <contained-fixture-repo> --binding beads",
        "--repo-root /tmp/fixture-repo --binding beads",
    )
    assert same["matches"] is True
    assert same["template_flags"] == ["--binding", "--repo-root"]

    weaker = VERDICT.args_divergence(
        "--repo-root <contained-fixture-repo> --binding beads",
        "--repo-root /tmp/fixture-repo --dry-run",
    )
    assert weaker["matches"] is False
    assert weaker["missing_flags"] == ["--binding"]
    assert weaker["extra_flags"] == ["--dry-run"]


def test_minimal_schema_validator_enforces_unique_items() -> None:
    schema = {"type": "array", "uniqueItems": True, "items": {"type": "string"}}
    assert VERDICT.validate_schema(["one", "two"], schema) == []
    assert any(
        "uniqueItems" in error
        for error in VERDICT.validate_schema(["one", "one"], schema)
    )


# --------------------------------------------------------------------------- #
# 受領書への機械列挙 (dyxr 受入条件 4)
# --------------------------------------------------------------------------- #
def test_scenario_id_without_scenario_file_is_a_usage_error(tmp_path: Path) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        args="--repo-root /tmp/fixture-repo --binding beads",
    )
    assert code == 2
    assert doc is None


def test_unobserved_required_observations_are_enumerated_and_fail_the_goal(
    tmp_path: Path,
) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=out/decompose-audit.json#publication_gate",
        args="--repo-root /tmp/fixture-repo --binding beads",
    )
    assert code == 0
    contract = doc["scenario_contract"]
    assert [item["index"] for item in contract["observed"]] == [1]
    assert [item["index"] for item in contract["unobserved"]] == [2, 3]
    assert contract["unobserved"][0]["observation"] == (
        "the promoted node is admitted"
    )
    assert doc["goal_verdict"]["result"] == "FAIL"
    assert any("required_observations 未回収 2/3 件" in b for b in doc["goal_verdict"]["blockers"])
    # 契約未充足の run が PASS を名乗れないこと (dyxr の構造的な穴)。
    assert doc["overall"]["verdict"] != "PASS"


def test_full_observation_coverage_keeps_the_verdict_pass(tmp_path: Path) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=out/decompose-audit.json#publication_gate",
        "--observation", "2=out/decompose-audit.json#publication_decisions",
        "--observation", "3=out/decompose-audit.json#binding_projections",
        args="--repo-root /tmp/fixture-repo --binding beads",
    )
    assert code == 0
    contract = doc["scenario_contract"]
    assert contract["unobserved"] == []
    assert contract["args_divergence"]["matches"] is True
    assert contract["task_contract"]["matches"] is True
    assert contract["resource_budget"] == {
        "max_wall_clock_s": 60,
        "max_total_tokens": 1000,
    }
    assert contract["resource_usage"]["tokens"]["total_tokens"] == 100
    assert contract["resource_usage"]["wall_clock_s"] == 10
    assert contract["resource_usage"]["poll_state_ref"] == "poll-state.json"
    assert len(contract["resource_usage"]["poll_state_sha256"]) == 64
    assert contract["resource_usage"]["violations"] == []
    assert doc["goal_verdict"] == {"result": "PASS", "blockers": []}
    assert doc["overall"]["verdict"] == "PASS"


def test_resource_budget_excess_prevents_pass(tmp_path: Path) -> None:
    fixture = json.loads(json.dumps(SCENARIO_FIXTURE))
    fixture["scenarios"][0]["resource_budget"]["max_total_tokens"] = 99
    scenario_file = tmp_path / "strict-scenarios.json"
    scenario_file.write_text(json.dumps(fixture), encoding="utf-8")
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(scenario_file),
        "--observation", "1=a.json",
        "--observation", "2=b.json",
        "--observation", "3=c.json",
        args="--repo-root /tmp/fixture-repo --binding beads",
    )
    assert code == 0
    assert doc["scenario_contract"]["resource_usage"]["violations"] == [
        "token-budget-exceeded:100>99"
    ]
    assert doc["overall"]["completion"] == "FAIL"
    assert doc["overall"]["verdict"] == "FAIL"


def test_missing_assistant_usage_is_unmeasured_and_prevents_pass(tmp_path: Path) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=a.json",
        "--observation", "2=b.json",
        "--observation", "3=c.json",
        args="--repo-root /tmp/fixture-repo --binding beads",
    )
    transcript = tmp_path / "trial" / "transcript.jsonl"
    record = json.loads(transcript.read_text())
    record["message"].pop("usage")
    transcript.write_text(json.dumps(record) + "\n", encoding="utf-8")
    usage = VERDICT.transcript_token_usage(transcript)
    assert usage["measured"] is False
    assert "tokens-unmeasured" in VERDICT.budget_violations(
        {"max_wall_clock_s": 60, "max_total_tokens": 1000},
        wall_clock_s=10,
        token_usage=usage,
    )


def test_token_usage_deduplicates_message_id_across_main_and_subagent(tmp_path: Path) -> None:
    main = tmp_path / "session.jsonl"
    record = {
        "type": "assistant",
        "message": {
            "id": "msg-shared",
            "usage": {"input_tokens": 3, "output_tokens": 7},
        },
    }
    main.write_text(json.dumps(record) + "\n", encoding="utf-8")
    subagents = tmp_path / "session" / "subagents"
    subagents.mkdir(parents=True)
    (subagents / "agent-a.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    usage = VERDICT.transcript_token_usage(main)
    assert usage["total_tokens"] == 10
    assert usage["assistant_messages"] == 1
    assert usage["assistant_message_ids"] == 1
    assert usage["transcript_files"] == 2
    assert usage["measured"] is True


def test_goal_pass_requires_digest_bound_fresh_evaluator_artifact(tmp_path: Path) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=a.json",
        "--observation", "2=b.json",
        "--observation", "3=c.json",
        args="--repo-root /tmp/fixture-repo --binding beads",
    )
    assert code == 0 and doc["overall"]["verdict"] == "PASS"
    assert doc["goal_evaluation"]["evaluator"]["mode"] == "fresh-independent-context"
    assert doc["goal_evaluation"]["transcript_sha256"] == doc["transcript_sha256"]


def test_task_contract_rejects_missing_and_forbidden_procedure(
    tmp_path: Path,
) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=a.json",
        "--observation", "2=b.json",
        "--observation", "3=c.json",
        args="--repo-root /tmp/fixture-repo --binding beads",
        task_text=(
            "upsert-node.py --operation apply-lifecycle-request "
            "--request lifecycle.json\n"
        ),
    )
    assert code == 0
    task_contract = doc["scenario_contract"]["task_contract"]
    assert task_contract["matches"] is False
    assert task_contract["missing_required_fragments"] == [
        "upsert-node.py --input",
        "promotion-patch.json",
    ]
    assert task_contract["present_forbidden_fragments"] == [
        "--operation apply-lifecycle-request"
    ]
    assert doc["goal_verdict"]["result"] == "FAIL"
    assert any(
        "task.md 手順契約が不一致" in blocker
        for blocker in doc["goal_verdict"]["blockers"]
    )
    assert doc["overall"]["verdict"] != "PASS"


def test_declared_task_contract_fails_when_task_file_is_absent(tmp_path: Path) -> None:
    scenario = VERDICT.load_scenario(
        _scenario_file(tmp_path), "CXX-OUT1-positive-fixture"
    )
    contract = VERDICT.validate_task_contract(scenario, tmp_path / "missing-task.md")
    assert contract["task_file_exists"] is False
    assert contract["matches"] is False


def test_forbidden_nested_skill_is_a_contract_blocker() -> None:
    scenario = {"forbidden_invoked_skills": ["expensive:full-regeneration"]}
    invocation = VERDICT.validate_invocation_contract(
        scenario,
        ["dev-graph:run-fixture-skill", "expensive:full-regeneration"],
    )
    contract = {
        "scenario_id": "bounded",
        "required_observations": ["done"],
        "observed": [{"index": 1, "observation": "done", "evidence_ref": "a.json"}],
        "unobserved": [],
        "args_divergence": VERDICT.args_divergence("", ""),
        "invocation_contract": invocation,
    }
    assert invocation["matches"] is False
    assert "full-regeneration" in VERDICT.scenario_contract_blockers(contract)[0]


# --------------------------------------------------------------------------- #
# args 乖離の開示と契約違反判定 (dyxr 受入条件 5)
# --------------------------------------------------------------------------- #
def test_args_divergence_is_recorded_in_the_verdict(tmp_path: Path) -> None:
    code, doc = _run(
        tmp_path,
        "--scenario-id", "CXX-OUT1-positive-fixture",
        "--scenario-file", str(_scenario_file(tmp_path)),
        "--observation", "1=a.json",
        "--observation", "2=b.json",
        "--observation", "3=c.json",
        args="--repo-root /tmp/fixture-repo --binding beads --dry-run",
    )
    assert code == 0
    divergence = doc["scenario_contract"]["args_divergence"]
    assert divergence["matches"] is False
    assert divergence["extra_flags"] == ["--dry-run"]
    assert divergence["missing_flags"] == []
    assert divergence["task_args_template"] == (
        "--repo-root <contained-fixture-repo> --binding beads"
    )
    # required_observations を全件回収していても、契約に無い --dry-run を足した run は
    # 「起票 0 件」が draft ゲートの作動か flag による抑止か切り分けられない。
    assert doc["goal_verdict"]["result"] == "FAIL"
    assert any("--dry-run" in blocker for blocker in doc["goal_verdict"]["blockers"])
    assert doc["overall"]["verdict"] != "PASS"


def test_total_args_divergence_is_a_contract_breach(tmp_path: Path) -> None:
    """scenario が要求する flag を落とし、代わりに別 flag で回した run。

    required_observations を全件回収していても、契約と違う args で回した run は
    その scenario の充足を意味しない。
    """
    contract = {
        "scenario_id": "CXX-OUT1-positive-fixture",
        "required_observations": SCENARIO_FIXTURE["scenarios"][0]["required_observations"],
        "observed": [
            {"index": index, "observation": text, "evidence_ref": "a.json"}
            for index, text in enumerate(
                SCENARIO_FIXTURE["scenarios"][0]["required_observations"], start=1
            )
        ],
        "unobserved": [],
        "args_divergence": VERDICT.args_divergence(
            "--repo-root <contained-fixture-repo> --binding beads",
            "--repo-root /tmp/fixture-repo --dry-run",
        ),
    }
    blockers = VERDICT.scenario_contract_blockers(contract)
    assert blockers, "scenario 契約と乖離した args が blocker として現れていない"


# --------------------------------------------------------------------------- #
# 実 scenario 正本との接続
# --------------------------------------------------------------------------- #
def test_the_real_c14_scenario_resolves_and_declares_observations() -> None:
    scenario = VERDICT.load_scenario(DEV_GRAPH_SCENARIOS, C14_SCENARIO_ID)
    assert scenario["skill"] == "run-dev-graph-decompose"
    assert scenario["criterion_id"] == "OUT1"
    assert len(scenario["required_observations"]) >= 4
    assert scenario["task_contract"]["required_fragments"]
    assert "--operation apply-lifecycle-request" in (
        scenario["task_contract"]["forbidden_fragments"]
    )


def test_scenario_templates_only_name_flags_the_target_skill_declares() -> None:
    """scenario が要求する flag が対象 skill に実在することを要求する。

    r2 の C14 は存在しない --binding を task_args_template に持っていた。args_divergence
    は「契約と実 run の乖離」を測るが、契約そのものが skill の interface から乖離して
    いる場合は測りようがなく、評価者は必ず契約を読み替えることになる (読み替えた瞬間に
    scenario は正本でなくなる)。ここは契約側を skill 定義へ接地させる上流ゲート。
    """
    suite = json.loads(DEV_GRAPH_SCENARIOS.read_text(encoding="utf-8"))
    for scenario in suite["scenarios"]:
        undeclared = _undeclared_flags(scenario["skill"], scenario["task_args_template"])
        assert not undeclared, (
            f"{scenario['scenario_id']}: task_args_template names flags the skill does not "
            f"declare: {undeclared}"
        )


def test_all_real_scenarios_declare_closed_resource_budgets() -> None:
    suite = json.loads(DEV_GRAPH_SCENARIOS.read_text(encoding="utf-8"))
    assert suite["scenarios"]
    for scenario in suite["scenarios"]:
        budget = VERDICT.resource_budget(scenario)
        assert set(budget) == {"max_wall_clock_s", "max_total_tokens"}


def test_the_undeclared_flag_gate_rejects_the_r2_c14_template() -> None:
    """上のゲートが実際に作動することを、既知の欠陥入力で確認する。

    r2 の C14 が持っていた --binding は run-dev-graph-decompose に存在しない。ゲートが
    死んでいれば全 scenario が通るだけなので、緑は無検査と区別がつかない。
    """
    assert _undeclared_flags(
        "run-dev-graph-decompose",
        "--repo-root <contained-fixture-repo> --binding none --dry-run",
    ) == ["--binding"]


def test_recorded_scenario_file_is_folded_to_repo_relative() -> None:
    """受領書へ記録する scenario_file は絶対パスで渡しても repo 相対へ畳まれる。

    verdict.json は clone 先で追試されるため、著者の作業機の絶対パスを残すと持ち主の
    環境でしか解決できない参照になる。C04/C19 の再実走で実際に絶対パスが記録され、
    下流の受領書検査 (tests/test_skill_criteria_evidence.py) が落ちた。
    """
    folded = "plugins/dev-graph/tests/fixtures/live-trial-positive-scenarios.json"
    assert VERDICT.repo_relative_scenario_file(str(DEV_GRAPH_SCENARIOS)) == folded
    # repo root から相対で渡した場合も同じ形に落ちる (呼び出し側の書き方で受領書が
    # 変わらない)。cwd 依存を排すため明示的に repo root へ移動して確かめる。
    cwd = os.getcwd()
    try:
        os.chdir(REPO)
        assert VERDICT.repo_relative_scenario_file(folded) == folded
    finally:
        os.chdir(cwd)


def test_scenario_file_outside_any_repo_is_left_as_given(tmp_path) -> None:
    """どの repo にも属さない scenario は畳む基準が無いので受け取った形のまま返す。

    畳めない入力を無理に相対化すると、解決できない参照を受領書へ書くことになる。
    ここが黙って壊れないことを固定する (fixture 検証経路が実際にこの形を通る)。
    """
    outside = tmp_path / "scenarios.json"
    outside.write_text("{}", encoding="utf-8")
    assert VERDICT.repo_relative_scenario_file(str(outside)) == str(outside)
