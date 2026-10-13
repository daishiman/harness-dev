"""検証 obligation の3つの CLI が、形の不正な入力を traceback ではなく exit 2 で止めることを確かめる。

対象は record-verification-evidence.py・derive-route-build-obligations.py・
derive-verification-contract.py。各 test は独立レビューの指摘の再発防止で、
正常系の対照を1件ずつ置いて、検査が何も通さないだけの空振りでないことも確かめる。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "run-build-skill" / "scripts"
FINGERPRINT = "a" * 64


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECORDER = _load("input_guard_recorder_test", SCRIPTS / "record-verification-evidence.py")
ROUTE_DERIVER = _load("input_guard_route_deriver_test", SCRIPTS / "derive-route-build-obligations.py")
CONTRACT_DERIVER = _load("input_guard_contract_deriver_test", SCRIPTS / "derive-verification-contract.py")


def _files(root: Path) -> set[Path]:
    return {path for path in root.rglob("*") if path.is_file()}


def _header(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("# ///", 2)[1]


# ── record-verification-evidence ─────────────────────────────────────────────


def _record(tmp_path: Path, plan: object, *extra: str, obligation_id: str = "build:x") -> int:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    (tmp_path / "artifact.txt").write_text("built", encoding="utf-8")
    return RECORDER.main([
        "--plan", str(plan_path),
        "--obligation-id", obligation_id,
        "--status", "PASS",
        "--verifier-kind", "deterministic",
        "--verifier-id", "fixture",
        "--repo-root", str(tmp_path),
        "--evidence-dir", str(tmp_path / "evidence"),
        *extra,
    ])


def _plan(**overrides: object) -> dict:
    obligation = {"id": "build:x", "fingerprint_sha256": FINGERPRINT, "expected_evidence_paths": ["artifact.txt"]}
    obligation.update(overrides.pop("obligation", {}))
    plan = {"schema_version": 1, "subject": "fixture", "obligations": [obligation]}
    plan.update(overrides)
    return plan


def test_recorder_writes_receipt_named_by_fingerprint(tmp_path: Path) -> None:
    assert _record(tmp_path, _plan()) == 0
    assert _files(tmp_path / "evidence") == {tmp_path / "evidence" / f"build-x-{FINGERPRINT[:12]}.json"}


@pytest.mark.parametrize(
    "fingerprint",
    ["/../../../zz" + "0" * 52, "A" * 64, "a" * 63, "a" * 65, 123, None],
)
def test_recorder_rejects_malformed_fingerprint_without_writing(tmp_path: Path, capsys, fingerprint) -> None:
    # fingerprint はファイル名に入る。形を確かめないと --evidence-dir の外へ書けてしまう
    before = _files(tmp_path)
    assert _record(tmp_path, _plan(obligation={"fingerprint_sha256": fingerprint})) == 2
    assert "fingerprint_sha256" in capsys.readouterr().err
    assert _files(tmp_path) - before == {tmp_path / "plan.json", tmp_path / "artifact.txt"}


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        ([_plan()], "plan が object でない"),
        (_plan(obligations={"build:x": {}}), "plan.obligations が配列でない"),
        (_plan(subject=None), "plan.subject"),
        (_plan(subject=["fixture"]), "plan.subject"),
        (_plan(subject="  "), "plan.subject"),
    ],
)
def test_recorder_rejects_malformed_plan_with_exit_2(tmp_path: Path, capsys, plan, message) -> None:
    assert _record(tmp_path, plan) == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "evidence").exists()


def test_recorder_names_the_missing_obligation_id(tmp_path: Path, capsys) -> None:
    # 以前は KeyError の空のメッセージだけが出て、何が無いのか分からなかった
    assert _record(tmp_path, _plan(), obligation_id="missing:id") == 2
    assert "obligation id が plan に無い: missing:id" in capsys.readouterr().err


@pytest.mark.parametrize("cost", ["nan", "inf", "-inf", "-1"])
def test_recorder_rejects_non_finite_or_negative_cost(tmp_path: Path, capsys, cost) -> None:
    # NaN と inf は receipt を strict JSON でなくし、費用の集計も壊す
    assert _record(tmp_path, _plan(), f"--estimated-cost-usd={cost}") == 2
    assert "finite and non-negative" in capsys.readouterr().err
    assert not (tmp_path / "evidence").exists()


def test_recorder_reports_unwritable_evidence_dir_with_exit_2(tmp_path: Path, capsys) -> None:
    (tmp_path / "evidence").write_text("not a directory", encoding="utf-8")
    assert _record(tmp_path, _plan()) == 2
    assert "receipt を書けない" in capsys.readouterr().err


# ── derive-route-build-obligations ───────────────────────────────────────────


def _route_repo(tmp_path: Path, handoff: object, graph: object | None = None) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    plan_dir = repo / "plan"
    plan_dir.mkdir(parents=True)
    if graph is not None:
        (plan_dir / "task-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    handoff_path = plan_dir / "handoff.json"
    handoff_path.write_text(handoff if isinstance(handoff, str) else json.dumps(handoff), encoding="utf-8")
    return repo, handoff_path


def _derive_routes(tmp_path: Path, handoff: object, graph: object | None = None, out: Path | None = None) -> int:
    repo, handoff_path = _route_repo(tmp_path, handoff, graph)
    argv = ["--handoff", str(handoff_path), "--repo-root", str(repo)]
    if out is not None:
        argv += ["--out", str(out)]
    return ROUTE_DERIVER.main(argv)


def _route(route_id: object = "a", **extra: object) -> dict:
    return {"id": route_id, "build_target": f"plugins/p/{route_id}", **extra}


def test_route_deriver_accepts_well_formed_handoff(tmp_path: Path) -> None:
    out = tmp_path / "contract.json"
    handoff = {"routes": [_route("a"), _route("b", depends_on=["a"])], "task_graph_ref": "task-graph.json"}
    assert _derive_routes(tmp_path, handoff, {"nodes": [], "edges": []}, out=out) == 0
    ids = [item["id"] for item in json.loads(out.read_text(encoding="utf-8"))["obligations"]]
    assert ids == ["build:a", "build:b"]


@pytest.mark.parametrize("absolute", [False, True])
def test_route_deriver_refuses_task_graph_outside_repo(tmp_path: Path, capsys, absolute: bool) -> None:
    outside = tmp_path / "outside" / "task-graph.json"
    outside.parent.mkdir()
    outside.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    ref = str(outside) if absolute else "../../outside/task-graph.json"
    assert _derive_routes(tmp_path, {"routes": [_route()], "task_graph_ref": {"path": ref}}) == 2
    assert "task_graph_ref is outside repo" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("handoff", "graph", "message"),
    [
        ([{"routes": [_route()]}], None, "handoff が object でない"),
        ({"routes": [{"build_target": "plugins/p/a"}]}, None, "空でない id"),
        ({"routes": [_route("")]}, None, "空でない id"),
        ({"routes": [_route(True)]}, None, "空でない id"),
        ({"routes": [_route(depends_on=5)]}, None, "depends_on は id の配列"),
        ({"routes": [_route(depends_on=[{"id": "b"}])]}, None, "depends_on は id の配列"),
        (
            {"routes": [_route()], "task_graph_ref": "task-graph.json"},
            {"nodes": [{"id": "T1", "execution_kind": "direct-task", "phase_ref": "P05"}], "edges": 5},
            "task graph の edges が配列でない",
        ),
        ({"routes": [_route()], "task_graph_ref": "task-graph.json"}, {"nodes": {"T1": {}}}, "task graph の nodes が配列でない"),
        ({"routes": [_route("a/b"), _route("a-b")]}, None, "obligation id が衝突する"),
    ],
)
def test_route_deriver_rejects_malformed_input_with_exit_2(tmp_path: Path, capsys, handoff, graph, message) -> None:
    assert _derive_routes(tmp_path, handoff, graph) == 2
    err = capsys.readouterr().err
    assert message in err
    assert "Traceback" not in err


def test_route_deriver_rejects_deeply_nested_json(tmp_path: Path, capsys) -> None:
    assert _derive_routes(tmp_path, "[" * 200_000 + "]" * 200_000) == 2
    assert "RecursionError" in capsys.readouterr().err


def test_route_deriver_reports_unwritable_out_with_exit_2(tmp_path: Path, capsys) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not a directory", encoding="utf-8")
    assert _derive_routes(tmp_path, {"routes": [_route()]}, out=blocker / "contract.json") == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("[ERROR]")
    assert captured.out == ""


# ── derive-verification-contract ─────────────────────────────────────────────


def _contract_repo(tmp_path: Path, plan_doc: object = None) -> Path:
    repo = tmp_path / "repo"
    (repo / "plugins" / "p" / "skills" / "s").mkdir(parents=True)
    (repo / "brief.md").write_text("brief", encoding="utf-8")
    (repo / "build-plan.json").write_text(json.dumps({} if plan_doc is None else plan_doc), encoding="utf-8")
    return repo


UNIT = {"build_plan": "build-plan.json", "skill_dir": "plugins/p/skills/s", "brief": "brief.md"}


def _derive_contract(tmp_path: Path, manifest: object, plan_doc: object = None, out: Path | None = None) -> int:
    repo = _contract_repo(tmp_path, plan_doc)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    argv = ["--repo-root", str(repo), "--unit-manifest", str(manifest_path)]
    if out is not None:
        argv += ["--out", str(out)]
    return CONTRACT_DERIVER.main(argv)


def test_contract_deriver_accepts_well_formed_manifest(tmp_path: Path) -> None:
    out = tmp_path / "contract.json"
    assert _derive_contract(tmp_path, {"subject": "s", "units": [UNIT]}, out=out) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["subject"] == "s"


@pytest.mark.parametrize(
    ("manifest", "plan_doc", "message"),
    [
        ([UNIT], None, "unit manifest が object でない"),
        ({"subject": "s", "units": {"u": UNIT}}, None, "units が配列でない"),
        ({"subject": "s", "units": [5]}, None, "build unit が object でない"),
        ({"subject": "s", "units": [{**UNIT, "build_plan": 5}]}, None, "path は文字列でなければならない"),
        ({"subject": "s", "units": [UNIT]}, ["static"], "build plan が object でない"),
        ({"subject": {"name": "s"}, "units": [UNIT]}, None, "subject が文字列でない"),
        ({"subject": 5, "units": [UNIT]}, None, "subject が文字列でない"),
    ],
)
def test_contract_deriver_rejects_malformed_input_with_exit_2(tmp_path: Path, capsys, manifest, plan_doc, message) -> None:
    assert _derive_contract(tmp_path, manifest, plan_doc) == 2
    err = capsys.readouterr().err
    assert message in err
    assert "Traceback" not in err


def _checker_argv(contract: dict) -> list[str]:
    machine = [item for item in contract["obligations"] if item["kind"] == "deterministic"]
    assert len(machine) == 1
    return machine[0]["checker"]["argv"]


def test_contract_checker_uses_repo_relative_path_inside_the_harness_repo() -> None:
    # harness 自身の repo では従来と同じ repo 相対のパスになり、既存の fingerprint を変えない
    repo_root = ROOT.parents[1]
    assert CONTRACT_DERIVER._checker_script(repo_root) == (
        "plugins/harness-creator/skills/run-build-skill/scripts/validate-build-plan.py"
    )


def test_contract_checker_points_at_the_installed_validator_outside_the_repo(tmp_path: Path) -> None:
    # harness-creator を同梱しない repo では、repo に無い固定パスではなく実物の絶対パスを指す
    out = tmp_path / "contract.json"
    assert _derive_contract(tmp_path, {"subject": "s", "units": [UNIT]}, out=out) == 0
    argv = _checker_argv(json.loads(out.read_text(encoding="utf-8")))
    validator = Path(argv[1])
    assert validator.is_absolute()
    assert validator == (SCRIPTS / "validate-build-plan.py").resolve()
    assert validator.is_file()
    assert not (tmp_path / "repo" / "plugins" / "harness-creator").exists()


def test_contract_deriver_without_sibling_validator_exits_2(tmp_path: Path) -> None:
    # 写し先に validate-build-plan.py が無ければ、存在しない checker を契約に書かず exit 2 で止める
    lone = tmp_path / "lone"
    lone.mkdir()
    shutil.copy2(SCRIPTS / "derive-verification-contract.py", lone / "derive-verification-contract.py")
    repo = _contract_repo(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"subject": "s", "units": [UNIT]}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(lone / "derive-verification-contract.py"),
         "--repo-root", str(repo), "--unit-manifest", str(manifest)],
        capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 2
    assert "validate-build-plan.py が見つからない" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_contract_deriver_reports_unwritable_out_with_exit_2(tmp_path: Path, capsys) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not a directory", encoding="utf-8")
    assert _derive_contract(tmp_path, {"subject": "s", "units": [UNIT]}, out=blocker / "contract.json") == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("[ERROR]")
    assert captured.out == ""


# ── header と実行ビット ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    [
        "derive-route-build-obligations.py",
        "derive-verification-contract.py",
        "record-verification-evidence.py",
        "build-review-launch.py",
        "build-usable-draft-proof.py",
        "build-external-intelligence.py",
        "build-external-intelligence-runtime.py",
    ],
)
def test_scripts_called_by_parent_declare_context_a(name: str) -> None:
    # SKILL.md の手順で親 (A) が Bash から直接呼ぶ script は contexts に A を持つ
    contexts = re.search(r"^# contexts: \[(.*)\]$", _header(SCRIPTS / name), re.MULTILINE)
    assert contexts and "A" in [item.strip() for item in contexts.group(1).split(",")]


@pytest.mark.parametrize("name", ["build-external-intelligence.py", "build-external-intelligence-runtime.py"])
def test_historical_forwarders_are_executable(name: str) -> None:
    path = SCRIPTS / name
    assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n")
    assert os.access(path, os.X_OK)


def test_build_trace_shim_requires_the_same_python_as_its_source() -> None:
    # shim は validate-build-trace.py を実行するので、それより古い Python を名乗れない
    shim = re.search(r'^# requires-python: "(.*)"$', _header(SCRIPTS / "validate_build_trace_shim.py"), re.MULTILINE)
    source = re.search(r'^# requires-python = "(.*)"$', (SCRIPTS / "validate-build-trace.py").read_text(encoding="utf-8"), re.MULTILINE)
    assert shim and source and shim.group(1) == source.group(1)
