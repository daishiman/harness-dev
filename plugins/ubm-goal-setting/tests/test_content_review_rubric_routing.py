"""Prove domain injection and rejection at the real review routing boundary."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

PLUGIN = Path(__file__).resolve().parents[1]
ROOT = PLUGIN.parent.parent
SCRIPT = PLUGIN / "scripts/validate-design-rubric.py"
REGISTRY = "plugins/skill-governance-config/config/rubric-registry.json"
L1 = "plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/references/rubric.json"
L0 = "plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"
EVALUATOR = "plugins/harness-creator/skills/assign-skill-design-evaluator"
L2 = f"{EVALUATOR}/references/rubric.json"
RENDERER = f"{EVALUATOR}/scripts/render-findings-score.py"


def load_module(path):
    spec = importlib.util.spec_from_file_location("review_routing_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("skill", sorted(p.name for p in (PLUGIN / "skills").glob("run-ubm-*")))
def test_actual_entrypoints_inject_the_registered_domain(skill):
    source = PLUGIN / "skills" / skill / "SKILL.md"
    command = load_module(SCRIPT).evaluation_command(ROOT, source)
    refs = command[command.index("--rubric-refs") + 1:command.index("--target")]
    assert len(refs) == 3
    assert [json.loads(Path(p).read_text())["layer"] for p in refs] == ["L0", "L1", "L2"]
    assert refs[1] == str(ROOT / L1)
    fm = yaml.safe_load(source.read_text().split("---", 2)[1])
    assert fm["domain"] == "ubm-goal-setting"
    assert (source.parent / fm["rubric_refs"][0]).resolve() == ROOT / L1
    assert "../../references/content-review-rubric.md" in fm["reference_refs"]


@pytest.fixture
def routing_fixture(tmp_path):
    script = tmp_path / "plugins/ubm-goal-setting/scripts/validate-design-rubric.py"
    script.parent.mkdir(parents=True)
    script.write_bytes(SCRIPT.read_bytes())
    for relative in [REGISTRY, L1, L0, L2, RENDERER, "plugins/ubm-goal-setting/.claude-plugin/plugin.json"]:
        out = tmp_path / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((ROOT / relative).read_bytes())
    source = tmp_path / "plugins/ubm-goal-setting/skills/run-ubm-example/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("fixture\n")
    return load_module(script), tmp_path, source


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "wrong-owner", "wrong-domain", "wrong-layer", "wrong-policy"])
def test_invalid_registration_never_falls_back_to_l0(routing_fixture, corruption):
    module, root, source = routing_fixture
    path = root / REGISTRY
    registry = json.loads(path.read_text())
    entry = next(item for item in registry["rubrics"] if item["domain"] == "ubm-goal-setting")
    if corruption == "missing":
        registry["rubrics"].remove(entry)
    elif corruption == "duplicate":
        registry["rubrics"].append(entry.copy())
    elif corruption == "wrong-owner":
        alternate = root / "alternate.json"
        alternate.write_bytes((root / L1).read_bytes())
        entry["rubric"] = str(alternate)
    elif corruption == "wrong-policy":
        entry["conflict_policy"] = "error"
    else:
        l1 = json.loads((root / L1).read_text())
        l1["domain" if corruption == "wrong-domain" else "layer"] = "other-domain" if corruption == "wrong-domain" else "L0"
        (root / L1).write_text(json.dumps(l1))
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError):
        module.evaluation_command(root, source)


def test_foreign_target_and_symlink_escape_are_rejected(routing_fixture):
    module, root, source = routing_fixture
    foreign = root / "plugins/another/skills/run-ubm-example/SKILL.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("foreign\n")
    with pytest.raises(ValueError):
        module.evaluation_command(root, foreign)
    source.unlink()
    source.symlink_to(foreign)
    with pytest.raises(ValueError):
        module.evaluation_command(root, source)


@pytest.mark.parametrize("ancestor", [False, True])
def test_owner_rubric_symlink_cannot_inject_foreign_rules(routing_fixture, ancestor):
    module, root, source = routing_fixture
    owner = root / L1
    foreign = root / "foreign"
    foreign.mkdir()
    replacement = foreign / "rubric.json"
    replacement.write_bytes(owner.read_bytes())
    owner.unlink()
    if ancestor:
        owner.parent.rmdir()
        owner.parent.symlink_to(foreign, target_is_directory=True)
    else:
        owner.symlink_to(replacement)
    with pytest.raises(ValueError):
        module.evaluation_command(root, source)


def test_same_id_delta_changes_only_background_check():
    composer = load_module(ROOT / "plugins/skill-governance-automation/scripts/compose-rubrics.py")
    l0 = ROOT / "plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"
    l2 = ROOT / "plugins/harness-creator/skills/assign-skill-design-evaluator/references/rubric.json"
    base = composer.compose([str(l0), str(l2)], "deep-merge", "most-specific-wins")
    actual = composer.compose([str(l0), str(ROOT / L1), str(l2)], "deep-merge", "most-specific-wins")
    before = {r["id"]: r for r in base["rules"]}
    after = {r["id"]: r for r in actual["rules"]}
    assert len(after) == len(actual["rules"]) == len(before)
    assert set(before) == set(after)
    for rid in before:
        if rid == "KL-002":
            assert before[rid]["check"] != after[rid]["check"]
            assert {k: v for k, v in before[rid].items() if k != "check"} == {
                k: v for k, v in after[rid].items() if k != "check"}
        else:
            assert before[rid] == after[rid]
    assert "All current entries" in after["KL-002"]["check"]
    assert "mere added length is insufficient" in after["KL-002"]["check"]


@pytest.mark.parametrize(("relative", "raw"), [
    (REGISTRY, "[]"),
    (REGISTRY, '{"rubrics": {"domain": "ubm-goal-setting"}}'),
    (REGISTRY, '{"rubrics": ["ubm-goal-setting"]}'),
    ("plugins/ubm-goal-setting/.claude-plugin/plugin.json", '"ubm-goal-setting"'),
    (L1, "[]"),
])
def test_non_object_json_fails_closed_without_attribute_error(routing_fixture, relative, raw):
    module, root, source = routing_fixture
    (root / relative).write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        module.evaluation_command(root, source)


def run_main(module, monkeypatch, capsys, root, source):
    monkeypatch.setattr(module.sys, "argv", ["validate-design-rubric.py", "--repo-root", str(root), "--target", str(source)])
    code = module.main()
    return code, capsys.readouterr().err


def run_with_child(module, monkeypatch, capsys, root, source, child_code):
    """evaluator の代わりに実プロセスの子 (python -c) を起動し、runner の終了コード・stdout・stderr を返す。"""
    monkeypatch.setattr(module, "evaluation_command", lambda repo_root, target: [sys.executable, "-c", child_code])
    monkeypatch.setattr(module.sys, "argv", ["validate-design-rubric.py", "--repo-root", str(root), "--target", str(source)])
    code = module.main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_routing_failures_exit_2_with_routing_marker(routing_fixture, monkeypatch, capsys):
    module, root, source = routing_fixture
    (root / REGISTRY).write_text("[" * 200000, encoding="utf-8")
    code, err = run_main(module, monkeypatch, capsys, root, source)
    assert code == 2
    assert err.startswith("UBM_REVIEW_ROUTING_INVALID: ")
    assert "UBM_REVIEW_EVALUATOR_EXIT" not in err


@pytest.mark.parametrize("child_exit", [0, 1, 2])
def test_child_exit_is_passed_through_with_its_source(routing_fixture, monkeypatch, capsys, child_exit):
    # 子は契約どおりに終わる: 0 は passed を持つ JSON を出し、1/2 は stdout に何も出さない。
    module, root, source = routing_fixture
    child = 'print(\'{"passed": true}\')' if child_exit == 0 else f"raise SystemExit({child_exit})"
    code, out, err = run_with_child(module, monkeypatch, capsys, root, source, child)
    assert code == child_exit
    assert "UBM_REVIEW_ROUTING_INVALID" not in err
    assert "UBM_REVIEW_EVALUATOR_CRASHED" not in err
    if child_exit:
        assert err.startswith(f"UBM_REVIEW_EVALUATOR_EXIT={child_exit} ")
        assert out == ""
    else:
        assert err == ""
        assert json.loads(out) == {"passed": True}


def test_signal_killed_child_exits_2_not_256_minus_signal(routing_fixture, monkeypatch, capsys):
    # SystemExit(-9) は exit 247 になり、0/1/2 の契約から外れる。判定が無いので 2 にする
    module, root, source = routing_fixture
    code, _out, err = run_with_child(module, monkeypatch, capsys, root, source,
                                     "import os, signal; os.kill(os.getpid(), signal.SIGKILL)")
    assert code == 2
    assert err.startswith("UBM_REVIEW_EVALUATOR_EXIT=-9 ")
    assert "UBM_REVIEW_EVALUATOR_CRASHED: killed by signal 9" in err.splitlines()


def test_repo_root_without_this_runner_is_a_routing_failure(routing_fixture, monkeypatch, capsys, tmp_path):
    module, root, source = routing_fixture
    other = tmp_path / "other-root"
    (other / "plugins" / "ubm-goal-setting").mkdir(parents=True)
    code, err = run_main(module, monkeypatch, capsys, other, source)
    assert code == 2
    assert err.startswith("UBM_REVIEW_ROUTING_INVALID: ")


@pytest.mark.parametrize("relative", [L0, L2, RENDERER])
def test_missing_evaluator_input_is_a_routing_failure(routing_fixture, monkeypatch, capsys, relative):
    # 子を起動してから「ファイルが無い」で exit 2 になると、評価の結果と区別できない。起動前に止める。
    module, root, source = routing_fixture
    (root / relative).unlink()
    with pytest.raises(ValueError, match="evaluator inputs are missing"):
        module.evaluation_command(root, source)
    code, err = run_main(module, monkeypatch, capsys, root, source)
    assert code == 2
    assert err.startswith("UBM_REVIEW_ROUTING_INVALID: ")


def test_evaluator_start_failure_exits_2_with_routing_marker(routing_fixture, monkeypatch, capsys):
    module, root, source = routing_fixture

    def cannot_start(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(module.subprocess, "run", cannot_start)
    code, err = run_main(module, monkeypatch, capsys, root, source)
    assert code == 2
    assert err.startswith("UBM_REVIEW_ROUTING_INVALID: evaluator could not start")


@pytest.mark.parametrize(("argv", "expected", "marked"), [
    (["--target", "x"], 2, True),  # --repo-root の欠落
    (["--help"], 0, False),
])
def test_usage_error_is_marked_but_help_is_not(argv, expected, marked):
    proc = subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True)
    assert proc.returncode == expected
    assert ("UBM_REVIEW_ROUTING_INVALID" in proc.stderr) is marked


def test_real_evaluator_runs_on_an_actual_entrypoint():
    source = PLUGIN / "skills/run-ubm-challenge/SKILL.md"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(ROOT), "--target", str(source)],
                          capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert proc.returncode in (0, 1), proc.stderr
    result = json.loads(proc.stdout)
    assert result["rubric_refs"][1] == str(ROOT / L1)


def test_child_exit_outside_contract_is_normalized_to_2(routing_fixture, monkeypatch, capsys):
    # 子の exit 3 をそのまま返すと、runner の 0/1/2 の契約から外れる。
    module, root, source = routing_fixture
    code, out, err = run_with_child(module, monkeypatch, capsys, root, source, "raise SystemExit(3)")
    assert code == 2 and out == ""
    lines = err.splitlines()
    assert "UBM_REVIEW_EVALUATOR_EXIT=3 (render-findings-score.py)" in lines
    assert any(line.startswith("UBM_REVIEW_EVALUATOR_CRASHED: exit 3 ") for line in lines)


def test_child_traceback_is_a_crash_not_the_contract_exit_1(routing_fixture, monkeypatch, capsys):
    # 未捕捉例外も exit 1 になる。契約の exit 1 (L0 の順序違反) と同じ値で返すと区別できない。
    module, root, source = routing_fixture
    code, out, err = run_with_child(module, monkeypatch, capsys, root, source, "raise RuntimeError('renderer broke')")
    assert code == 2 and out == ""
    assert "RuntimeError: renderer broke" in err  # 子の stderr は消さずに流す
    assert "UBM_REVIEW_EVALUATOR_CRASHED: uncaught exception (Traceback)" in err.splitlines()


def test_contract_exit_1_without_traceback_stays_1(routing_fixture, monkeypatch, capsys):
    module, root, source = routing_fixture
    child = "import sys; print('rubric-refs must start with L0', file=sys.stderr); raise SystemExit(1)"
    code, out, err = run_with_child(module, monkeypatch, capsys, root, source, child)
    assert code == 1 and out == ""
    assert err.splitlines() == ["rubric-refs must start with L0", "UBM_REVIEW_EVALUATOR_EXIT=1 (render-findings-score.py)"]


@pytest.mark.parametrize("stdout", ["", "not json", "[]", '{"passed": "yes"}', '{"rubric_hash": "x"}'])
def test_exit_0_without_a_json_verdict_is_a_crash(routing_fixture, monkeypatch, capsys, stdout):
    # exit 0 でも判定 (passed) が読めなければ、採点できたことにしない。
    module, root, source = routing_fixture
    code, out, err = run_with_child(module, monkeypatch, capsys, root, source,
                                    f"import sys; sys.stdout.write({stdout!r})")
    assert code == 2 and out == ""
    assert "UBM_REVIEW_EVALUATOR_EXIT" not in err
    assert any(line.startswith("UBM_REVIEW_EVALUATOR_CRASHED: exit 0 ") for line in err.splitlines())


def test_non_utf8_child_output_is_a_crash_without_traceback(routing_fixture, monkeypatch, capsys):
    module, root, source = routing_fixture
    child = "import sys; sys.stdout.buffer.write(b'\\xff'); sys.stderr.buffer.write(b'\\xfe\\n')"
    code, out, err = run_with_child(module, monkeypatch, capsys, root, source, child)
    assert code == 2 and out == ""
    assert "Traceback" not in err
    assert "UBM_REVIEW_EVALUATOR_CRASHED: exit 0 without a JSON verdict on stdout" in err.splitlines()
