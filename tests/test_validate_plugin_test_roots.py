"""per-test-root pytest runner の並列性・全被覆・優先順契約。"""
from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "validate-plugin-test-roots.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_plugin_test_roots", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changed_test_root_and_plugin_are_prioritized_deterministically():
    runner = _load_runner()
    groups = {
        "plugins/zeta": ["tests/test_z.py"],
        "plugins/alpha/skills/run-a": ["tests/test_a.py"],
        "plugins/alpha/skills/run-b": ["tests/test_b.py"],
        "plugins/beta": ["tests/test_b.py"],
    }
    changed = {
        "plugins/alpha/skills/run-b/SKILL.md",  # exact test_root 影響
        "plugins/beta/hooks/hooks.json",  # plugin root 影響
    }

    ordered = runner.prioritize_groups(groups, changed)

    assert [item.test_root for item in ordered] == [
        "plugins/alpha/skills/run-b",
        "plugins/beta",
        "plugins/alpha/skills/run-a",
        "plugins/zeta",
    ]
    assert [item.priority for item in ordered] == [0, 0, 1, 2]


def test_bounded_parallel_runner_executes_every_root_and_aggregates_failures(tmp_path):
    runner = _load_runner()
    groups = {
        f"plugins/p{i}": [f"tests/test_{i}.py"]
        for i in range(6)
    }
    plan = runner.prioritize_groups(groups, set())
    lock = threading.Lock()
    active = 0
    peak = 0
    executed: list[str] = []

    def fake_run(item, *, repo_root, log_dir):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            executed.append(item.test_root)
        time.sleep(0.02)
        with lock:
            active -= 1
        return runner.TestResult(
            item=item,
            returncode=1 if item.test_root.endswith("p2") else 0,
            seconds=0.02,
            log_path=log_dir / f"{item.index}.log",
        )

    results = runner.run_groups(
        plan,
        repo_root=tmp_path,
        log_dir=tmp_path / "logs",
        max_workers=2,
        run_one=fake_run,
    )

    assert sorted(executed) == sorted(groups)
    assert 1 < peak <= 2
    assert len(results) == len(groups)
    assert [result.item.test_root for result in results if result.returncode] == ["plugins/p2"]
    # 集約結果は完了順でなく deterministic plan 順で返す。
    assert [result.item.index for result in results] == list(range(len(groups)))


def test_each_test_root_gets_an_isolated_log_and_its_own_cwd(tmp_path):
    runner = _load_runner()
    test_root = tmp_path / "plugins" / "sample"
    tests_dir = test_root / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_cwd.py").write_text(
        "from pathlib import Path\n"
        "def test_cwd():\n"
        "    assert Path.cwd().name == 'sample'\n",
        encoding="utf-8",
    )
    plan = runner.prioritize_groups(
        {"plugins/sample": ["tests/test_cwd.py"]},
        {"plugins/sample/tests/test_cwd.py"},
    )
    log_dir = tmp_path / "logs"

    result = runner.run_test_root(plan[0], repo_root=tmp_path, log_dir=log_dir)

    assert result.returncode == 0
    assert result.log_path.parent == log_dir
    assert result.log_path.is_file()
    assert "1 passed" in result.log_path.read_text(encoding="utf-8")


def test_workflow_runs_governance_and_plugin_tests_in_parallel_then_aggregates():
    workflow_path = ROOT / ".github" / "workflows" / "harness-creator-kit-ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    assert "needs" not in jobs["governance"]
    assert "needs" not in jobs["plugin-tests"]
    assert set(jobs["verify"]["needs"]) == {"governance", "plugin-tests"}
    assert jobs["verify"]["if"] == "always()"

    plugin_runs = [
        step.get("run", "") for step in jobs["plugin-tests"]["steps"]
    ]
    assert any("validate-plugin-test-roots.py --workers 4" in run for run in plugin_runs)
