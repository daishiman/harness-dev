"""検証 obligation の3つの CLI が、形の不正な入力を traceback ではなく exit 2 で止めることを確かめる。

対象は record-verification-evidence.py・derive-route-build-obligations.py・
derive-verification-contract.py。各 test は独立レビューの指摘の再発防止で、
正常系の対照を1件ずつ置いて、検査が何も通さないだけの空振りでないことも確かめる。
"""
from __future__ import annotations

import hashlib
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


RECEIPT_NAME = f"build-x-{FINGERPRINT[:12]}.json"


def _link_receipt_name_outside(tmp_path: Path, existing: bool) -> tuple[Path, Path]:
    """receipt と同じ名前で --evidence-dir の外を指す symlink を置く (existing=False なら dangling)。"""
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "target.json"
    if existing:
        target.write_text("victim", encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / RECEIPT_NAME).symlink_to(target)
    return evidence, target


@pytest.mark.parametrize("existing", [False, True], ids=["dangling", "existing"])
def test_recorder_replaces_a_symlink_instead_of_writing_through_it(tmp_path: Path, existing: bool) -> None:
    # 以前は write_text がリンクをたどり、外のファイルを上書きするか (existing)、外に新しく作っていた (dangling)
    evidence, target = _link_receipt_name_outside(tmp_path, existing)
    assert _record(tmp_path, _plan()) == 0
    if existing:
        assert target.read_text(encoding="utf-8") == "victim"
    else:
        assert not target.exists()
    receipt = evidence / RECEIPT_NAME
    assert not receipt.is_symlink() and json.loads(receipt.read_text(encoding="utf-8"))["status"] == "PASS"
    assert os.listdir(evidence) == [RECEIPT_NAME]  # 一時ファイルを残さない


def test_recorder_keep_existing_non_pass_refuses_a_dangling_symlink(tmp_path: Path, capsys) -> None:
    evidence, target = _link_receipt_name_outside(tmp_path, existing=False)
    assert _record(tmp_path, _plan(), "--keep-existing-non-pass") == 3
    assert "PASS でない" in capsys.readouterr().err
    assert not target.exists() and os.listdir(evidence) == [RECEIPT_NAME]


def test_recorder_rechecks_keep_existing_non_pass_just_before_replacing(tmp_path: Path, capsys, monkeypatch) -> None:
    # 最初の確認の後、置き換えの前に別の手順が FAIL を書いた場合も上書きしない
    receipt = tmp_path / "evidence" / RECEIPT_NAME
    real_fsync = os.fsync

    def fsync_then_fail_appears(fd: int) -> None:
        real_fsync(fd)
        receipt.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")

    monkeypatch.setattr(RECORDER.os, "fsync", fsync_then_fail_appears)
    assert _record(tmp_path, _plan(), "--keep-existing-non-pass") == 3
    assert "status='FAIL'" in capsys.readouterr().err
    assert json.loads(receipt.read_text(encoding="utf-8")) == {"status": "FAIL"}
    assert os.listdir(receipt.parent) == [RECEIPT_NAME]


def test_recorder_leaves_the_previous_receipt_when_replace_fails(tmp_path: Path, capsys, monkeypatch) -> None:
    assert _record(tmp_path, _plan()) == 0
    receipt = tmp_path / "evidence" / RECEIPT_NAME
    before = receipt.read_bytes()

    def fail_replace(src: str, dst: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(RECORDER.os, "replace", fail_replace)
    assert _record(tmp_path, _plan(obligation={}), "--note", "second") == 2
    assert "receipt を書けない" in capsys.readouterr().err
    assert receipt.read_bytes() == before and os.listdir(receipt.parent) == [RECEIPT_NAME]


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


# build-conformance の checker は Step 4 と同じ mode で validate-build-plan.py を走らせる

CREATE_TAIL = ["--brief", "brief.md", "--check", "--skill-dir", "plugins/p/skills/s"]


def _derive_mode(tmp_path: Path, unit: dict, trace: object = None, *, trace_at: str = "eval-log/skill-build-trace.json",
                 plan_skill_name: str = "run-s") -> tuple[int, list[str] | None]:
    out = tmp_path / "contract.json"
    repo = _contract_repo(tmp_path, {"skill_name": plan_skill_name})
    if trace is not None:
        (repo / trace_at).parent.mkdir(parents=True, exist_ok=True)
        (repo / trace_at).write_text(json.dumps(trace), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"subject": "s", "units": [unit]}), encoding="utf-8")
    code = CONTRACT_DERIVER.main(["--repo-root", str(repo), "--unit-manifest", str(manifest_path), "--out", str(out)])
    return code, (_checker_argv(json.loads(out.read_text(encoding="utf-8")))[2:] if code == 0 else None)


def test_contract_checker_keeps_create_argv_without_trace(tmp_path: Path) -> None:
    # create の argv は従来と同じ。create の fingerprint を変えない
    assert _derive_mode(tmp_path, UNIT) == (0, CREATE_TAIL)


def test_contract_checker_passes_mode_update_from_unit(tmp_path: Path) -> None:
    assert _derive_mode(tmp_path, {**UNIT, "mode": "update"}) == (0, CREATE_TAIL + ["--mode", "update"])


def test_contract_checker_reads_build_mode_from_matching_default_trace(tmp_path: Path) -> None:
    trace = {"skill_name": "run-s", "build_mode": "update"}
    assert _derive_mode(tmp_path, UNIT, trace) == (0, CREATE_TAIL + ["--mode", "update"])


def test_contract_checker_ignores_default_trace_of_another_skill(tmp_path: Path) -> None:
    # 既定の trace は最後に build した別の skill のものでありうる
    trace = {"skill_name": "run-other", "build_mode": "update"}
    assert _derive_mode(tmp_path, UNIT, trace) == (0, CREATE_TAIL)


def test_contract_checker_reads_explicit_trace_path(tmp_path: Path) -> None:
    trace = {"skill_name": "run-s", "build_mode": "update"}
    unit = {**UNIT, "trace": "work/trace.json"}
    assert _derive_mode(tmp_path, unit, trace, trace_at="work/trace.json") == (0, CREATE_TAIL + ["--mode", "update"])


@pytest.mark.parametrize(
    ("unit", "trace", "trace_at", "message"),
    [
        ({**UNIT, "mode": "patch"}, None, "eval-log/skill-build-trace.json", "mode は create か update"),
        ({**UNIT, "mode": "create"}, {"skill_name": "run-s", "build_mode": "update"},
         "eval-log/skill-build-trace.json", "trace の build_mode update と違う"),
        (UNIT, {"skill_name": "run-s", "build_mode": "rebuild"}, "eval-log/skill-build-trace.json", "mode は create か update"),
        (UNIT, ["run-s"], "eval-log/skill-build-trace.json", "trace が object でない"),
        ({**UNIT, "trace": "work/trace.json"}, {"skill_name": "run-other", "build_mode": "update"},
         "work/trace.json", "build plan の 'run-s' と違う"),
        ({**UNIT, "trace": "work/missing.json"}, None, "eval-log/skill-build-trace.json", "No such file"),
    ],
)
def test_contract_checker_rejects_bad_mode_or_trace_with_exit_2(tmp_path: Path, capsys, unit, trace, trace_at, message) -> None:
    code, argv = _derive_mode(tmp_path, unit, trace, trace_at=trace_at)
    assert (code, argv) == (2, None)
    err = capsys.readouterr().err
    assert message in err
    assert "Traceback" not in err


def test_contract_deriver_single_unit_args_accept_mode(tmp_path: Path) -> None:
    repo = _contract_repo(tmp_path, {"skill_name": "run-s"})
    out = tmp_path / "contract.json"
    argv = ["--repo-root", str(repo), "--build-plan", "build-plan.json", "--skill-dir", "plugins/p/skills/s",
            "--brief", "brief.md", "--mode", "update", "--out", str(out)]
    assert CONTRACT_DERIVER.main(argv) == 0
    assert _checker_argv(json.loads(out.read_text(encoding="utf-8")))[2:] == CREATE_TAIL + ["--mode", "update"]


def test_contract_deriver_rejects_mode_flag_with_unit_manifest(tmp_path: Path, capsys) -> None:
    # manifest の各 unit が別の mode を持ちうるので、全体へ掛かる --mode は受け付けない
    repo = _contract_repo(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"subject": "s", "units": [UNIT]}), encoding="utf-8")
    assert CONTRACT_DERIVER.main(["--repo-root", str(repo), "--unit-manifest", str(manifest), "--mode", "update"]) == 2
    assert "--unit-manifest では各 unit の mode" in capsys.readouterr().err


# ── derive-verification-contract --evidence-dir: Step 4 の lint PASS の引き継ぎ ──────────
# Step 4 が同じ mode・同じ brief・同じ skill dir で validate-build-plan --check を通した unit を候補にし、
# derive がその場で contract の checker argv を走らせて exit 0 のときだけ receipt を書く。
# 1つでも食い違うか checker が通らなければ receipt を書かず、planner は check を返す。

PLANNER = _load("input_guard_planner_test", SCRIPTS / "plan-verification-obligations.py")
SSOT = _load("input_guard_ssot_test", ROOT / "scripts" / "feedback_contract_ssot.py")
MACHINE_ID = "machine:p:s:build-conformance"
UNSET = object()


@pytest.fixture
def checker_runs(monkeypatch) -> list[list[str]]:
    """derive が走らせる checker を exit 0 に差し替え、渡された argv を記録する。

    実物の validate-build-plan は最小の skill を通さないので、受け渡しだけを見るテストで使う。
    実物を走らせる経路は test_step4_receipt_needs_the_real_checker_to_pass で見る。
    """
    seen: list[list[str]] = []

    def passing(argv: list[str], repo_root: Path) -> tuple[int, str]:
        seen.append(list(argv))
        return 0, "PASS"

    monkeypatch.setattr(CONTRACT_DERIVER, "_run_checker", passing)
    return seen


def _step4_repo(tmp_path: Path, **trace_fields: object) -> Path:
    """Step 4 の lint が全て exit 0 になった直後の trace を持つ repo を作る。値に UNSET を渡すとその欄を消す。"""
    repo = _contract_repo(tmp_path, {"skill_name": "run-s"})
    skill = repo / "plugins" / "p" / "skills" / "s"
    (skill / "SKILL.md").write_text("---\nname: run-s\n---\n", encoding="utf-8")
    trace = {
        "skill_name": "run-s",
        "build_mode": "create",
        "reproducibility_gates": {"lint": "PASS", "evaluator": "N/A", "elegant_review": "N/A", "governance": "N/A"},
        "lint_target_sha256": SSOT.directory_content_sha256(skill),
        "lint_brief_sha256": hashlib.sha256((repo / "brief.md").read_bytes()).hexdigest(),
    }
    for key, value in trace_fields.items():
        if value is UNSET:
            trace.pop(key, None)
        else:
            trace[key] = value
    path = repo / "eval-log" / "skill-build-trace.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace), encoding="utf-8")
    return repo


def _derive_step4(repo: Path, evidence: Path | None, *extra: str) -> dict:
    out = repo.parent / "contract.json"
    argv = ["--repo-root", str(repo), "--build-plan", "build-plan.json", "--skill-dir", "plugins/p/skills/s",
            "--brief", "brief.md", "--out", str(out), *extra]
    if evidence is not None:
        argv += ["--evidence-dir", str(evidence)]
    assert CONTRACT_DERIVER.main(argv) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def _machine_action(contract: dict, repo: Path, evidence: Path) -> str:
    plan = PLANNER.build_plan(contract, repo, evidence)
    return next(record["action"] for record in plan["obligations"] if record["id"] == MACHINE_ID)


def test_step4_lint_pass_becomes_build_conformance_receipt(tmp_path: Path, capsys, checker_runs) -> None:
    repo = _step4_repo(tmp_path)
    evidence = tmp_path / "evidence"
    plain = _derive_step4(repo, None)
    assert not evidence.exists() and checker_runs == []
    contract = _derive_step4(repo, evidence)
    # contract は --evidence-dir の有無で変わらない。create の argv も fingerprint もそのまま
    assert contract == plain
    assert _checker_argv(contract)[2:] == CREATE_TAIL
    # receipt の前に、agent に渡すのと同じ argv を derive 自身が1回走らせている
    assert checker_runs == [_checker_argv(contract)]
    receipts = sorted(evidence.glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["obligation_id"] == MACHINE_ID and receipt["status"] == "PASS"
    assert receipt["verifier"] == {"kind": "deterministic", "id": CONTRACT_DERIVER.STEP4_VERIFIER_ID}
    assert [item["path"] for item in receipt["evidence"]] == ["eval-log/skill-build-trace.json"]
    # Step 12 の planner は validate-build-plan を走らせ直さずに使い回す
    assert _machine_action(contract, repo, evidence) == "reuse"
    first = receipts[0].read_bytes()
    capsys.readouterr()
    # 2回目は今の PASS があるので書き直さない
    _derive_step4(repo, evidence)
    assert "planner の action='reuse'" in capsys.readouterr().err
    assert sorted(evidence.glob("*.json")) == receipts and receipts[0].read_bytes() == first
    assert len(checker_runs) == 1  # 今の PASS を使い回すときは走らせ直さない


def test_step4_receipt_follows_update_mode(tmp_path: Path, checker_runs) -> None:
    repo = _step4_repo(tmp_path, build_mode="update")
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, evidence)
    assert _checker_argv(contract)[2:] == CREATE_TAIL + ["--mode", "update"]
    assert checker_runs == [_checker_argv(contract)]
    assert _machine_action(contract, repo, evidence) == "reuse"


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        ((1, "missing deliverable: agents/x.md"), "checker が今 exit 1: missing deliverable: agents/x.md"),
        (FileNotFoundError(2, "No such file"), "checker を起動できない: FileNotFoundError"),
        (subprocess.TimeoutExpired(["python3"], 120), "checker を起動できない: TimeoutExpired"),
    ],
)
def test_step4_receipt_needs_the_checker_to_pass_now(
    tmp_path: Path, capsys, monkeypatch, outcome: object, message: str
) -> None:
    """trace と digest が一致しても、skill dir の外 (pair skill・agents・templates・checker) が変われば今は通らない。"""

    def checker(argv: list[str], repo_root: Path) -> tuple[int, str]:
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(CONTRACT_DERIVER, "_run_checker", checker)
    repo = _step4_repo(tmp_path)
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, evidence)
    assert message in capsys.readouterr().err
    assert not list(evidence.glob("*.json"))
    assert _machine_action(contract, repo, evidence) == "check"


def test_step4_receipt_needs_the_real_checker_to_pass(tmp_path: Path, capsys) -> None:
    """差し替えない実物の validate-build-plan は、trace が PASS と言っても空の build plan を通さない。"""
    repo = _step4_repo(tmp_path)
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, evidence)
    assert "checker が今 exit" in capsys.readouterr().err
    assert not list(evidence.glob("*.json"))
    assert _machine_action(contract, repo, evidence) == "check"


def test_run_checker_runs_the_argv_in_the_repo_with_this_interpreter(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import os, sys\nprint('noise')\nprint(os.getcwd(), sys.executable, *sys.argv[1:])\nsys.exit(int(sys.argv[2]))\n",
        encoding="utf-8",
    )
    assert CONTRACT_DERIVER._run_checker(["python3", str(probe), "x", "0"], repo) == (
        0, f"{os.path.realpath(repo)} {sys.executable} x 0")
    assert CONTRACT_DERIVER._run_checker(["python3", str(probe), "y", "4"], repo)[0] == 4


def test_step4_receipt_is_not_written_when_only_the_brief_changed(tmp_path: Path, capsys) -> None:
    repo = _step4_repo(tmp_path)
    (repo / "brief.md").write_text("brief changed after Step 4", encoding="utf-8")
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, evidence)
    assert "brief が変わった" in capsys.readouterr().err
    assert not list(evidence.glob("*.json"))
    assert _machine_action(contract, repo, evidence) == "check"


def test_step4_receipt_is_not_written_when_only_the_skill_dir_changed(tmp_path: Path, capsys) -> None:
    repo = _step4_repo(tmp_path)
    (repo / "plugins" / "p" / "skills" / "s" / "prompts").mkdir()
    (repo / "plugins" / "p" / "skills" / "s" / "prompts" / "R9.md").write_text("added after Step 4", encoding="utf-8")
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, evidence)
    assert "skill dir が変わった" in capsys.readouterr().err
    assert not list(evidence.glob("*.json"))
    assert _machine_action(contract, repo, evidence) == "check"


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"lint_brief_sha256": UNSET}, "lint_brief_sha256 が無い"),
        ({"lint_target_sha256": UNSET}, "lint_target_sha256 が無い"),
        ({"reproducibility_gates": {"lint": "N/A"}}, "lint が PASS でない"),
        ({"reproducibility_gates": {"lint": "pass"}}, "lint が PASS でない"),
        ({"build_mode": UNSET}, "build_mode None"),
        ({"skill_name": "run-other"}, "skill_name の一致する trace が無い"),
        ({"lint_brief_sha256": "B" * 64}, "lint_brief_sha256 が無い"),
    ],
)
def test_step4_receipt_fails_closed_to_check(tmp_path: Path, capsys, fields: dict, reason: str) -> None:
    # lint_brief_sha256 を持たない古い trace を含め、1つでも欠ければ今までどおり check
    repo = _step4_repo(tmp_path, **fields)
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, evidence)
    err = capsys.readouterr().err
    assert reason in err and "check のまま" in err
    assert not list(evidence.glob("*.json"))
    assert _machine_action(contract, repo, evidence) == "check"


def test_step4_receipt_never_overwrites_a_current_fail(tmp_path: Path, capsys, checker_runs) -> None:
    repo = _step4_repo(tmp_path)
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, None)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(PLANNER.build_plan(contract, repo, evidence)), encoding="utf-8")
    assert RECORDER.main([
        "--plan", str(plan_path), "--obligation-id", MACHINE_ID, "--status", "FAIL",
        "--verifier-kind", "deterministic", "--verifier-id", "validate-build-plan",
        "--evidence-path", "brief.md", "--evidence-dir", str(evidence), "--repo-root", str(repo),
    ]) == 0
    before = {path: path.read_bytes() for path in evidence.glob("*.json")}
    capsys.readouterr()
    _derive_step4(repo, evidence)
    assert "planner の action='remediate'" in capsys.readouterr().err
    assert {path: path.read_bytes() for path in evidence.glob("*.json")} == before
    assert _machine_action(contract, repo, evidence) == "remediate"


@pytest.mark.parametrize("change", ["rewrite", "move", "corrupt"])
def test_step4_receipt_never_overwrites_a_fail_the_planner_no_longer_matches(
    tmp_path: Path, capsys, change: str, checker_runs
) -> None:
    """証跡が変わった・消えた・receipt が壊れた FAIL は planner の一致から外れるが、derive は上書きしない。"""
    repo = _step4_repo(tmp_path)
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, None)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(PLANNER.build_plan(contract, repo, evidence)), encoding="utf-8")
    (repo / "fail-log.txt").write_text("validate-build-plan FAILED: missing deliverable", encoding="utf-8")
    assert RECORDER.main([
        "--plan", str(plan_path), "--obligation-id", MACHINE_ID, "--status", "FAIL",
        "--verifier-kind", "deterministic", "--verifier-id", "validate-build-plan",
        "--evidence-path", "fail-log.txt", "--evidence-dir", str(evidence), "--repo-root", str(repo),
    ]) == 0
    (fail,) = evidence.glob("*.json")
    if change == "rewrite":
        (repo / "fail-log.txt").write_text("log rotated", encoding="utf-8")
    elif change == "move":
        (repo / "fail-log.txt").rename(repo / "moved.txt")
    else:
        fail.write_text("{ broken", encoding="utf-8")
    before = fail.read_bytes()
    capsys.readouterr()
    _derive_step4(repo, evidence)
    assert "既存の receipt が PASS でない" in capsys.readouterr().err
    assert sorted(evidence.glob("*.json")) == [fail] and fail.read_bytes() == before
    assert _machine_action(contract, repo, evidence) != "reuse"


def test_recorder_keep_existing_non_pass_still_refreshes_a_pass(tmp_path: Path) -> None:
    repo = _step4_repo(tmp_path)
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, None)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(PLANNER.build_plan(contract, repo, evidence)), encoding="utf-8")
    argv = ["--plan", str(plan_path), "--obligation-id", MACHINE_ID, "--status", "PASS",
            "--verifier-kind", "deterministic", "--verifier-id", "validate-build-plan",
            "--evidence-path", "brief.md", "--evidence-dir", str(evidence), "--repo-root", str(repo),
            "--keep-existing-non-pass"]
    assert RECORDER.main(argv) == 0
    assert RECORDER.main(argv) == 0  # 今ある PASS は書き直してよい
    assert RECORDER.main([*argv[:5], "FAIL", *argv[6:-1]]) == 0  # 利用者の FAIL は flag 無しで書ける
    assert RECORDER.main(argv) == 3


def test_step4_receipt_is_skipped_when_the_digest_ssot_is_unavailable(tmp_path: Path, capsys, monkeypatch) -> None:
    def missing() -> None:
        raise ValueError("feedback_contract_ssot.py が見つからない")

    monkeypatch.setattr(CONTRACT_DERIVER, "_load_directory_digest", missing)
    repo = _step4_repo(tmp_path)
    evidence = tmp_path / "evidence"
    contract = _derive_step4(repo, evidence)
    assert "[WARN]" in capsys.readouterr().err
    assert not list(evidence.glob("*.json"))
    assert _machine_action(contract, repo, evidence) == "check"


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
