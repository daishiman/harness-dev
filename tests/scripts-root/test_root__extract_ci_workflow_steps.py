"""scripts/extract-ci-workflow-steps.py と、それを使う run-ci-checks.sh の検査。

PR #83 では run-ci-checks.sh が CI の段を手で写した一覧だったため、
validate-plugin-packages.py (PKG-007) をローカルが持たず、push 後の CI で初めて落ちた。
本テストは「workflow の run 段が、書き出されるか理由付きで除外されるかのどちらかになる」
ことと、「run-ci-checks.sh が書き出した段を実行する」ことを固定する。
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shlex
import subprocess
import sys
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "extract-ci-workflow-steps.py"
WORKFLOWS = ROOT / ".github" / "workflows"
PKG_VALIDATOR = (
    ROOT / "plugins/harness-creator/skills/assign-plugin-package-evaluator/scripts/"
    "validate-plugin-package.py"
)


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # dataclass は文字列化された注釈を解決するため sys.modules から自 module を引く。
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load(SCRIPT, "_extract_ci_workflow_steps")


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


@pytest.fixture
def workflows(tmp_path: pathlib.Path) -> pathlib.Path:
    wf = tmp_path / "workflows"
    _write(wf / "pr.yml", """\
        name: pr
        on:
          pull_request:
        defaults:
          run:
            working-directory: plugins/x
        jobs:
          lint:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - name: plain
                run: |
                  python3 -m pip install --quiet -r requirements-dev.txt
                  python3 scripts/lint-a.py
              - name: soft
                run: python3 scripts/lint-b.py
                continue-on-error: true
              - name: explicit blocking
                run: python3 scripts/lint-c.py
                continue-on-error: false
              - name: conditional
                if: ${{ env.TOKEN != '' }}
                run: python3 scripts/remote.py
              - name: secret env
                env:
                  TOKEN: ${{ secrets.TOKEN }}
                run: python3 scripts/remote.py
              - name: pwsh
                shell: pwsh
                run: Write-Host hi
          heavy:
            runs-on: ubuntu-latest
            defaults:
              run:
                working-directory: .
            steps:
              - name: tests
                run: python3 -m pytest tests/
        """)
    _write(wf / "scheduled.yml", """\
        name: scheduled
        on:
          schedule:
            - cron: '0 0 * * 0'
        jobs:
          poll:
            runs-on: ubuntu-latest
            steps:
              - name: poll
                run: python3 scripts/poll.py
        """)
    return wf


def test_writes_blocking_and_soft_steps_and_skips_github_only(workflows):
    steps, skipped = MOD.build_steps(workflows)
    by_label = {s.label: s for s in steps}

    assert set(by_label) == {
        "pr.yml:lint: plain",
        "pr.yml:lint: soft",
        "pr.yml:lint: explicit blocking",
        "pr.yml:heavy: tests",
    }
    # pip install はローカル環境を書き換えないよう除く。
    assert by_label["pr.yml:lint: plain"].body == "python3 scripts/lint-a.py"
    assert by_label["pr.yml:lint: soft"].mode == "soft"
    assert by_label["pr.yml:lint: explicit blocking"].mode == "hard"
    # workflow の defaults を job の defaults が上書きする。
    assert by_label["pr.yml:lint: plain"].working_directory == "plugins/x"
    assert by_label["pr.yml:heavy: tests"].working_directory == "."

    reasons = dict(skipped)
    assert "if 条件" in reasons["pr.yml:lint: conditional"]
    assert "GitHub 式" in reasons["pr.yml:lint: secret env"]
    assert "shell=pwsh" in reasons["pr.yml:lint: pwsh"]
    # schedule だけの workflow は PR の合否に関わらないので段にも除外にも出ない。
    assert not any(label.startswith("scheduled.yml") for label in [*by_label, *reasons])


def test_skip_jobs_is_reported_not_silently_dropped(workflows):
    steps, skipped = MOD.build_steps(workflows, frozenset({"heavy"}))
    assert "pr.yml:heavy: tests" not in {s.label for s in steps}
    assert dict(skipped)["pr.yml:heavy: tests"] == "CI_CHECKS_SKIP_JOBS で利用者が除外した"


def test_render_step_header_and_cd(workflows):
    steps, _ = MOD.build_steps(workflows)
    text = MOD.render_step(next(s for s in steps if s.label == "pr.yml:lint: plain"))
    assert text.splitlines()[:4] == [
        "# label: pr.yml:lint: plain",
        "# mode: hard",
        "set -eo pipefail",
        "cd plugins/x",
    ]


def test_literal_env_is_merged_and_shell_quoted_when_executed(tmp_path):
    wf = tmp_path / "workflows"
    literal = "it's $HOME $(printf injected) with spaces"
    body = "import json, os; print(json.dumps({k: os.environ[k] for k in ['VALUE', 'LITERAL', 'NUMBER', 'BOOL']}))"
    _write(wf / "pr.yml", json.dumps({
        "on": "pull_request", "env": {"VALUE": "workflow", "LITERAL": literal},
        "jobs": {"lint": {
            "env": {"VALUE": "job", "NUMBER": 42, "BOOL": True},
            "steps": [{"env": {"VALUE": "step"},
                       "run": f"{shlex.quote(sys.executable)} -c {shlex.quote(body)}"}],
        }},
    }))
    steps, skipped = MOD.build_steps(wf)
    assert skipped == []
    env = dict(os.environ, VALUE="local")
    done = subprocess.run(["bash", "-c", MOD.render_step(steps[0])],
                          env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"VALUE": "step", "LITERAL": literal, "NUMBER": "42", "BOOL": "true"}


@pytest.mark.parametrize("name", ["BAD-NAME", "1VALUE", "VALUE; touch injected", ""])
def test_invalid_env_name_is_an_input_error(tmp_path, name, capsys):
    wf = tmp_path / "workflows"
    _write(wf / "pr.yml", json.dumps({
        "on": "pull_request", "jobs": {"lint": {"steps": [{"env": {name: "value"}, "run": "echo hi"}]}},
    }))
    assert MOD.main(["--out-dir", str(tmp_path / "out"), "--workflows-dir", str(wf)]) == 2
    assert "invalid env name" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("scope", ["workflow", "job", "step"])
def test_effective_working_directory_expression_is_skipped(tmp_path, scope):
    wf = tmp_path / "workflows"
    step = {"run": "echo hi"}
    job = {"steps": [step]}
    data = {"on": "pull_request", "jobs": {"lint": job}}
    target = {"workflow": data, "job": job, "step": step}[scope]
    if scope == "step":
        target["working-directory"] = "${{ github.workspace }}"
    else:
        target["defaults"] = {"run": {"working-directory": "${{ github.workspace }}"}}
    _write(wf / "pr.yml", json.dumps(data))
    steps, skipped = MOD.build_steps(wf)
    assert steps == []
    assert len(skipped) == 1 and "working-directory" in skipped[0][1] and "GitHub" in skipped[0][1]
    step["working-directory"] = "."
    _write(wf / "pr.yml", json.dumps(data))
    steps, skipped = MOD.build_steps(wf)
    assert skipped == [] and steps[0].working_directory == "."


def test_main_writes_files_and_skipped_tsv(workflows, tmp_path, capsys):
    out = tmp_path / "out"
    assert MOD.main(["--out-dir", str(out), "--workflows-dir", str(workflows)]) == 0
    assert sorted(p.name for p in out.glob("*.sh")) == ["001.sh", "002.sh", "003.sh", "004.sh"]
    assert len((out / "skipped.tsv").read_text(encoding="utf-8").splitlines()) == 3
    assert "4 steps, 3 skipped" in capsys.readouterr().out


def test_main_refuses_out_dir_with_existing_steps(workflows, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "001.sh").write_text("echo stale\n", encoding="utf-8")
    assert MOD.main(["--out-dir", str(out), "--workflows-dir", str(workflows)]) == 2


def test_main_fails_closed_when_no_pr_workflow(tmp_path):
    wf = tmp_path / "workflows"
    _write(wf / "scheduled.yml", """\
        on:
          schedule:
            - cron: '0 0 * * 0'
        jobs:
          poll:
            steps:
              - run: echo hi
        """)
    assert MOD.main(["--out-dir", str(tmp_path / "out"), "--workflows-dir", str(wf)]) == 1


def test_real_workflows_every_run_step_is_written_or_skipped_with_reason():
    """workflow に段を足せば、ローカルの一括検査にも自動で入る (手写しの一覧を持たない)。"""
    steps, skipped = MOD.build_steps(WORKFLOWS)
    total = 0
    for _, data in MOD.iter_pr_workflows(WORKFLOWS):
        for job in data["jobs"].values():
            total += sum(1 for step in job.get("steps") or [] if "run" in step)
    assert len(steps) + len(skipped) == total
    # 除外は GitHub 上でしか評価できない段だけ。
    for label, reason in skipped:
        assert "GitHub" in reason, (label, reason)


def test_real_workflows_include_plugin_package_check_as_blocking():
    """PR #83 で CI だけが持っていた PKG-007 の段が、ローカルでも blocking で走る。"""
    steps, _ = MOD.build_steps(WORKFLOWS)
    pkg = [s for s in steps if "python3 scripts/validate-plugin-packages.py" in s.body]
    assert pkg and all(s.mode == "hard" for s in pkg)


def test_real_workflow_steps_run_on_macos_default_bash():
    """run-ci-checks.sh は macOS の bash 3.2 で段を実行するので、bash 4 の構文を使わない。"""
    steps, _ = MOD.build_steps(WORKFLOWS)
    for step in steps:
        code = "\n".join(
            line for line in step.body.splitlines() if not line.lstrip().startswith("#")
        )
        for token in ("mapfile", "readarray", "declare -A"):
            assert token not in code, (step.label, token)


def test_run_ci_checks_executes_extracted_steps():
    text = (ROOT / "scripts" / "run-ci-checks.sh").read_text(encoding="utf-8")
    assert "python3 scripts/extract-ci-workflow-steps.py --out-dir" in text
    assert 'run "$label" bash "$step"' in text
    assert 'run_soft "$label" bash "$step"' in text
    # 除外した段はサマリに出す (黙って捨てない)。
    assert 'skipped.tsv' in text and "Skipped CI steps" in text


def test_pkg_007_blocks_shebang_script_without_exec_bit(tmp_path):
    """新規 script が 100644 のまま入ると PKG-007 で止まる (blocking 扱い)。"""
    validator = _load(PKG_VALIDATOR, "_validate_plugin_package")
    wrapper = _load(ROOT / "scripts" / "validate-plugin-packages.py", "_validate_plugin_packages")
    script = tmp_path / "plugin" / "scripts" / "new-tool.py"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env python3\nprint('hi')\n", encoding="utf-8")

    os.chmod(script, 0o644)
    findings = validator.check_pkg_007(tmp_path / "plugin")
    assert [f for f in findings if "+x" in str(f)]
    assert "PKG-007" not in wrapper.ADVISORY_PKG

    os.chmod(script, 0o755)
    assert validator.check_pkg_007(tmp_path / "plugin") == []
