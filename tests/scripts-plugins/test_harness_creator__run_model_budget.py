"""One run-level model-action budget: declared once, checked against every loop bound, reserved once per action."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "plugins/harness-creator/skills"
SCRIPT = SKILLS / "run-build-skill/scripts/validate-run-model-budget.py"
POLICY = SKILLS / "run-elegant-review/references/convergence-policy.json"
# collect_bound_sources が読むファイル。これを tmp に写せば、1 か所だけ書き換えた世界を作れる。
SOURCE_FILES = (
    "run-elegant-review/references/convergence-policy.json",
    "run-build-skill/schemas/build-flags.schema.json",
    "run-build-skill/references/improvement-levels.json",
    "run-build-skill/SKILL.md",
    "run-build-skill/scripts/build-improvement-gate.py",
    "run-build-skill/scripts/plan-verification-obligations.py",
    "run-skill-create/workflow-manifest.json",
    "run-skill-create/SKILL.md",
    "run-skill-create/prompts/R2-gate-review.md",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_run_model_budget", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _mirror(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    for rel in SOURCE_FILES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SKILLS / rel, dest)
    return root


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_policy_budget_matches_every_loop_bound_and_the_formula(mod):
    budget = mod.load_budget(POLICY)
    sources = mod.collect_bound_sources(SKILLS)
    assert mod.budget_mismatches(budget, sources) == []
    # 8 つの上限すべてに、少なくとも 1 つの実在する宣言がある
    assert {key for key, _, _ in sources} == set(mod.BOUND_KEYS)
    expected = mod.compute_worst_case(budget["bounds"])
    assert expected["total"] == sum(expected["components"].values()) == budget["total"]


def test_worst_case_grows_when_any_loop_bound_grows(mod):
    bounds = mod.load_budget(POLICY)["bounds"]
    base = mod.compute_worst_case(bounds)["total"]
    for key in ("gate_deny_cycles", "build_rerun_cycles", "initial_diagnosis_contexts", "improvement_rounds", "verification_actions"):
        grown = dict(bounds, **{key: bounds[key] + 1})
        assert mod.compute_worst_case(grown)["total"] > base, f"{key} を増やしても予算が増えない"


@pytest.mark.parametrize(
    ("rel", "old", "new", "bound"),
    [
        ("run-skill-create/prompts/R2-gate-review.md", "最大 3 周", "最大 4 周", "gate_deny_cycles"),
        ("run-skill-create/workflow-manifest.json", '"max_iterations": 3', '"max_iterations": 4', "gate_deny_cycles"),
        ("run-build-skill/SKILL.md", "release で最大3周", "release で最大4周", "build_rerun_cycles"),
        ("run-build-skill/scripts/build-improvement-gate.py", '"evaluator_context_limit": 1', '"evaluator_context_limit": 2', "initial_diagnosis_contexts"),
        ("run-build-skill/scripts/plan-verification-obligations.py", "DEFAULT_INCREMENTAL_MODEL_ACTIONS = 4", "DEFAULT_INCREMENTAL_MODEL_ACTIONS = 5", "verification_actions"),
        ("run-build-skill/references/improvement-levels.json", '"max_rounds": 3', '"max_rounds": 4', "improvement_rounds"),
    ],
)
def test_changing_one_loop_bound_without_the_budget_fails(mod, tmp_path: Path, rel, old, new, bound):
    root = _mirror(tmp_path)
    _replace_once(root / rel, old, new)
    problems = mod.budget_mismatches(mod.load_budget(POLICY), mod.collect_bound_sources(root))
    assert any(problem.startswith(f"bounds.{bound}=") for problem in problems), problems


def test_hand_edited_total_or_components_disagreeing_with_the_formula_fails(mod):
    budget = mod.load_budget(POLICY)
    sources = mod.collect_bound_sources(SKILLS)
    inflated = dict(budget, total=budget["total"] + 1)
    assert any(problem.startswith("total") for problem in mod.budget_mismatches(inflated, sources))
    first = next(iter(budget["components"]))
    shifted = dict(budget, components=dict(budget["components"], **{first: budget["components"][first] + 1}))
    assert any(problem.startswith("components") for problem in mod.budget_mismatches(shifted, sources))


def test_missing_bound_declaration_fails_closed(mod, tmp_path: Path):
    root = _mirror(tmp_path)
    skill = root / "run-build-skill/SKILL.md"
    # 宣言を全部消すと、上限の写しを持つ箇所が無くなったことを黙って見逃さない
    skill.write_text(re.sub(r"release\s*で?\s*最大\s*\d+\s*周", "release でも打ち切る", skill.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(mod.BudgetError, match="pattern not found"):
        mod.collect_bound_sources(root)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda b: b.pop("total"), "total"),
        (lambda b: b.update(total=None), "total"),
        (lambda b: b.update(components=None), "components"),
        (lambda b: b["bounds"].pop("goal_seek_loops"), "bounds"),
        (lambda b: b["bounds"].update(goal_seek_loops=True), "goal_seek_loops"),
        (lambda b: b.update(total=b["total"] + 1), "sum of components"),
    ],
)
def test_load_budget_rejects_malformed_definitions(mod, tmp_path: Path, mutate, match):
    doc = json.loads(POLICY.read_text(encoding="utf-8"))
    mutate(doc["run_model_action_budget"])
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(mod.BudgetError, match=match):
        mod.load_budget(path)


def test_reserve_is_idempotent_per_action_and_refuses_overflow(mod, tmp_path: Path):
    first = mod.reserve(tmp_path, "run-1", action_id="IRC-a", component="initial_diagnosis", count=1, total=3)
    again = mod.reserve(tmp_path, "run-1", action_id="IRC-a", component="initial_diagnosis", count=1, total=3)
    assert first == {"reserved": True, "action_id": "IRC-a", "held": 1, "total": 3, "consumed": 1, "remaining": 2}
    assert again["reserved"] is False and again["consumed"] == 1
    with pytest.raises(mod.BudgetExhausted):
        mod.reserve(tmp_path, "run-1", action_id="improve:x", component="bounded_improvement", count=3, total=3)
    # 台帳外の消費 (検証用 model action) も上限判定に効く
    with pytest.raises(mod.BudgetExhausted):
        mod.reserve(tmp_path, "run-1", action_id="improve:y", component="bounded_improvement", count=1, total=3, external_consumed=2)
    assert mod.ledger_consumed(mod.read_ledger(tmp_path, "run-1")) == 1
    # 別 run の台帳は独立
    assert mod.ledger_consumed(mod.read_ledger(tmp_path, "run-2")) == 0
    with pytest.raises(mod.BudgetError, match="different component or count"):
        mod.reserve(tmp_path, "run-1", action_id="IRC-a", component="initial_diagnosis", count=2, total=3)


def _policy_with(tmp_path: Path, mutate) -> Path:
    doc = json.loads(POLICY.read_text(encoding="utf-8"))
    mutate(doc["run_model_action_budget"])
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def test_runtime_load_refuses_a_self_consistent_but_inflated_budget(mod, tmp_path: Path):
    # components と total の合計は揃っていても、bounds からの計算と違えば実行時に動かない
    def inflate(budget):
        budget["components"]["bounded_improvement"] += 1000
        budget["total"] = sum(budget["components"].values())

    path = _policy_with(tmp_path, inflate)
    with pytest.raises(mod.BudgetError, match="compute_worst_case"):
        mod.load_budget(path)
    # CLI 用の読み方では落とさず、MISMATCH として並べられる
    loose = mod.load_budget(path, check_formula=False)
    problems = mod.budget_mismatches(loose, mod.collect_bound_sources(SKILLS, path))
    assert any(problem.startswith("components") for problem in problems)
    cli = subprocess.run([sys.executable, str(SCRIPT), "--policy", str(path)], capture_output=True, text=True, check=False)
    assert cli.returncode == 1 and "[MISMATCH] components" in cli.stdout


def test_at_least_reuses_a_larger_reservation_and_tops_up_a_smaller_one(mod, tmp_path: Path):
    # 深さを選び直しても止まらず、二重にも引かない
    kwargs = {"component": "bounded_improvement", "total": 10, "at_least": True}
    first = mod.reserve(tmp_path, "run-u", action_id="improve:c", count=3, **kwargs)
    assert first["reserved"] is True and first["consumed"] == 3
    smaller = mod.reserve(tmp_path, "run-u", action_id="improve:c", count=1, **kwargs)
    assert smaller["reserved"] is False and smaller["held"] == 3 and smaller["consumed"] == 3
    larger = mod.reserve(tmp_path, "run-u", action_id="improve:c", count=5, **kwargs)
    assert larger["reserved"] is True and larger["held"] == 5 and larger["consumed"] == 5
    again = mod.reserve(tmp_path, "run-u", action_id="improve:c", count=5, **kwargs)
    assert again["reserved"] is False and again["consumed"] == 5
    ledger = mod.read_ledger(tmp_path, "run-u")
    assert [(e["action_id"], e["count"]) for e in ledger["entries"]] == [("improve:c", 3), ("improve:c#topup-5", 2)]
    # 足りない差分が上限を超えるなら、差分を要求として拒否する
    with pytest.raises(mod.BudgetExhausted) as exhausted:
        mod.reserve(tmp_path, "run-u", action_id="improve:c", count=11, **kwargs)
    assert (exhausted.value.consumed, exhausted.value.requested, exhausted.value.total) == (5, 6, 10)
    # at_least でない呼び出しは従来どおり count の食い違いを拒否する
    with pytest.raises(mod.BudgetError, match="different component or count"):
        mod.reserve(tmp_path, "run-u", action_id="improve:c", count=1, component="bounded_improvement", total=10)
    with pytest.raises(mod.BudgetError, match="another component"):
        mod.reserve(tmp_path, "run-u", action_id="improve:c", count=5, component="initial_diagnosis", total=10, at_least=True)
    with pytest.raises(mod.BudgetError, match="topup"):
        mod.reserve(tmp_path, "run-u", action_id="improve:c#topup-9", count=1, **kwargs)


@pytest.mark.parametrize("bad", ["", "  ", " IRC-a", None, 7])
def test_reserve_refuses_a_malformed_action_or_run_id_before_writing(mod, tmp_path: Path, bad):
    with pytest.raises(mod.BudgetError, match="action_id"):
        mod.reserve(tmp_path, "run-v", action_id=bad, component="initial_diagnosis", count=1, total=3)
    with pytest.raises(mod.BudgetError, match="run_id"):
        mod.reserve(tmp_path, bad, action_id="IRC-a", component="initial_diagnosis", count=1, total=3)
    assert list(tmp_path.iterdir()) == []


def test_ledger_binds_the_total_it_was_opened_with(mod, tmp_path: Path):
    mod.reserve(tmp_path, "run-b", action_id="IRC-a", component="initial_diagnosis", count=1, total=5)
    assert json.loads(mod.ledger_path(tmp_path, "run-b").read_text(encoding="utf-8"))["budget_total"] == 5
    with pytest.raises(mod.BudgetError, match="opened with total 5"):
        mod.reserve(tmp_path, "run-b", action_id="IRC-b", component="initial_diagnosis", count=1, total=50)
    # 壊れた・使い過ぎの台帳は読むだけでも落とす
    path = mod.ledger_path(tmp_path, "run-b")
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["entries"][0]["count"] = 6
    path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(mod.BudgetError, match="overdrawn"):
        mod.read_ledger(tmp_path, "run-b")
    ledger["entries"][0]["count"] = 1
    ledger["budget_total"] = 0
    path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(mod.BudgetError, match="budget_total"):
        mod.read_ledger(tmp_path, "run-b")


def test_unwritable_state_dir_is_a_budget_error_not_a_traceback(mod, tmp_path: Path):
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(mod.BudgetError, match="cannot lock"):
        mod.reserve(blocker / "state", "run-w", action_id="IRC-a", component="initial_diagnosis", count=1, total=3)


def test_cli_reads_the_policy_under_the_given_skills_root(mod, tmp_path: Path):
    # --skills-root だけを差し替えたら、その下の policy と照合する (repo の policy と混ぜない)
    root = _mirror(tmp_path)
    policy = root / "run-elegant-review/references/convergence-policy.json"
    doc = json.loads(policy.read_text(encoding="utf-8"))
    doc["run_model_action_budget"]["bounds"]["gate_deny_cycles"] += 1
    doc["run_model_action_budget"].update(mod.compute_worst_case(doc["run_model_action_budget"]["bounds"]))
    policy.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r2 = root / "run-skill-create/prompts/R2-gate-review.md"
    r2.write_text(re.sub(r"(最大|否認) 3 周", r"\1 4 周", r2.read_text(encoding="utf-8")), encoding="utf-8")
    _replace_once(root / "run-skill-create/workflow-manifest.json", '"max_iterations": 3', '"max_iterations": 4')
    synced = subprocess.run([sys.executable, str(SCRIPT), "--skills-root", str(root)], capture_output=True, text=True, check=False)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # 同じ skills を repo の policy と照合させると、上限の食い違いとして出る
    mixed = subprocess.run([sys.executable, str(SCRIPT), "--skills-root", str(root), "--policy", str(POLICY)], capture_output=True, text=True, check=False)
    assert mixed.returncode == 1 and "gate_deny_cycles=3" in mixed.stdout
    printed = subprocess.run([sys.executable, str(SCRIPT), "--skills-root", str(root), "--print-expected"], capture_output=True, text=True, check=False)
    assert json.loads(printed.stdout)["total"] == doc["run_model_action_budget"]["total"]


def test_cli_status_and_malformed_levels_are_input_errors(mod, tmp_path: Path):
    mod.reserve(tmp_path / "state", "run-s", action_id="IRC-a", component="initial_diagnosis", count=1, total=mod.load_budget(POLICY)["total"])
    status = subprocess.run([sys.executable, str(SCRIPT), "--run-id", "run-s", "--state-dir", str(tmp_path / "state")], capture_output=True, text=True, check=False)
    assert status.returncode == 0 and json.loads(status.stdout)["consumed"] == 1
    root = _mirror(tmp_path)
    (root / "run-build-skill/references/improvement-levels.json").write_text('{"levels": []}', encoding="utf-8")
    broken = subprocess.run([sys.executable, str(SCRIPT), "--skills-root", str(root)], capture_output=True, text=True, check=False)
    assert broken.returncode == 2 and "levels must be an object" in broken.stderr


def test_concurrent_reservations_never_exceed_the_total(mod, tmp_path: Path):
    def attempt(index: int) -> bool:
        try:
            mod.reserve(tmp_path, "run-c", action_id=f"IRC-{index}", component="initial_diagnosis", count=1, total=5)
            return True
        except mod.BudgetExhausted:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        granted = sum(pool.map(attempt, range(20)))
    assert granted == 5
    assert mod.ledger_consumed(mod.read_ledger(tmp_path, "run-c")) == 5


def test_reserve_verification_holds_at_least_the_required_count_per_subject(mod, tmp_path: Path):
    first = mod.reserve_verification(tmp_path, "run-v", required={"a": 2, "b": 1}, total=10)
    assert first == {"reserved": True, "added": 3, "total": 10, "consumed": 3, "remaining": 7}
    # planner と gate は同じ plan から同じ量を出すので、2 回目は何も足さない
    again = mod.reserve_verification(tmp_path, "run-v", required={"a": 2, "b": 1}, total=10)
    assert again["reserved"] is False and again["added"] == 0 and again["consumed"] == 3
    # 少ない要求は予約済みで足り、多い要求は差分だけを top-up で足す
    grown = mod.reserve_verification(tmp_path, "run-v", required={"a": 4, "b": 0}, total=10)
    assert grown["added"] == 2 and grown["consumed"] == 5
    ledger = mod.read_ledger(tmp_path, "run-v")
    assert [(e["action_id"], e["component"], e["count"]) for e in ledger["entries"]] == [
        ("verification:a", "verification", 2),
        ("verification:b", "verification", 1),
        ("verification:a#topup-4", "verification", 2),
    ]
    # 差分の合計が上限を超えるなら、どの subject も書かない
    with pytest.raises(mod.BudgetExhausted) as exhausted:
        mod.reserve_verification(tmp_path, "run-v", required={"a": 5, "c": 5}, total=10)
    assert (exhausted.value.consumed, exhausted.value.requested) == (5, 6)
    assert mod.ledger_consumed(mod.read_ledger(tmp_path, "run-v")) == 5
    # 検証の action を別 component で予約し直すことはできない
    with pytest.raises(mod.BudgetError, match="another component"):
        mod.reserve(tmp_path, "run-v", action_id="verification:a", component="bounded_improvement", count=2, total=10)


@pytest.mark.parametrize("required, match", [
    ({"a": -1}, "non-negative"),
    ({"a": True}, "non-negative"),
    ({"": 1}, "subject"),
    ({"a#topup-3": 1}, "topup"),
    ([("a", 1)], "map subject"),
])
def test_reserve_verification_refuses_malformed_requests_before_writing(mod, tmp_path: Path, required, match):
    with pytest.raises(mod.BudgetError, match=match):
        mod.reserve_verification(tmp_path, "run-m", required=required, total=10)
    assert list(tmp_path.iterdir()) == []


def test_concurrent_verification_reservations_never_exceed_the_total(mod, tmp_path: Path):
    # 2 つの検証が lock の外で同じ残りを読んでも、合わせて上限を超えない
    def attempt(index: int) -> bool:
        try:
            mod.reserve_verification(tmp_path, "run-cv", required={f"s{index}": 2}, total=7)
            return True
        except mod.BudgetExhausted:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        granted = sum(pool.map(attempt, range(12)))
    assert granted == 3
    assert mod.ledger_consumed(mod.read_ledger(tmp_path, "run-cv")) == 6

    # 同じ subject を同時に予約しても、二重には引かない
    def same(_: int) -> int:
        return mod.reserve_verification(tmp_path, "run-cs", required={"x": 3}, total=7)["added"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        added = list(pool.map(same, range(8)))
    assert sorted(added) == [0] * 7 + [3]
    assert mod.ledger_consumed(mod.read_ledger(tmp_path, "run-cs")) == 3


def test_ledger_tampering_fails_closed(mod, tmp_path: Path):
    mod.reserve(tmp_path, "run-t", action_id="IRC-a", component="initial_diagnosis", count=1, total=3)
    path = mod.ledger_path(tmp_path, "run-t")
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["entries"][0]["count"] = -1
    path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(mod.BudgetError, match="malformed"):
        mod.read_ledger(tmp_path, "run-t")
    ledger["entries"][0]["count"] = 1
    ledger["run_id"] = "run-other"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(mod.BudgetError, match="another run"):
        mod.read_ledger(tmp_path, "run-t")


def test_cli_ok_mismatch_and_print_expected(tmp_path: Path):
    ok = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    expected = subprocess.run([sys.executable, str(SCRIPT), "--print-expected"], capture_output=True, text=True, check=False)
    assert expected.returncode == 0, expected.stderr
    budget = json.loads(POLICY.read_text(encoding="utf-8"))["run_model_action_budget"]
    assert json.loads(expected.stdout) == {"components": budget["components"], "total": budget["total"]}

    root = _mirror(tmp_path)
    _replace_once(root / "run-skill-create/prompts/R2-gate-review.md", "最大 3 周", "最大 4 周")
    drift = subprocess.run([sys.executable, str(SCRIPT), "--skills-root", str(root)], capture_output=True, text=True, check=False)
    assert drift.returncode == 1
    assert "gate_deny_cycles" in drift.stdout
