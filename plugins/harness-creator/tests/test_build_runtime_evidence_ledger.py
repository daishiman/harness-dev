"""build-runtime-evidence-ledger.py (runtime-evidence-ledger.json の書き手) の機能テスト。

網羅対象:
- 書き手が書いた ledger を TG-C08 (record-task-graph-knowledge.py) がそのまま受理する (書いて読む往復)
- sha256・graph_hash・generated_at・schema_version を書き手が機械で埋める
- 検証に落ちたら何も書かない (既存 ledger も置き換えない)・--dry-run は書かない
- 入力の読込/parse 失敗は exit 2
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


writer = _load("build-runtime-evidence-ledger")
rec = _load("record-task-graph-knowledge")

_GRAPH_HASH = "sha256:" + "a" * 64
_LEDGER = "runtime-evidence-ledger.json"
_ARTIFACTS = {
    "local_build": ("route-C01.json", b"c01\n"),
    "native_parity": ("route-C02.json", b"c02\n"),
    "rollback": ("rollback-evidence.json", b"rollback\n"),
}


def _write(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def _build(tmp_path: Path) -> tuple[Path, Path, Path]:
    """plan (P12 local + P13 trust node)・task-state・local 証跡を置いた build dir を作る。"""
    plan = tmp_path / "plan"
    plan.mkdir()
    _write(plan / "task-graph.json", {"nodes": [
        {"id": "T1", "phase_ref": "P12", "title": "local docs"},
        {"id": "P13-x-02", "phase_ref": "P13", "title": "C02 native parity/freshness PASS。"},
        {"id": "P13-x-03", "phase_ref": "P13",
         "title": "R2 trust前 non-run / trust後 SessionStart run"},
    ]})
    build = tmp_path / "build"
    build.mkdir()
    state = _write(build / "task-state.json", {
        "graph_hash": _GRAPH_HASH,
        "nodes": [{"id": "T1", "state": "done"}, {"id": "P13-x-02", "state": "done"}],
    })
    for name, payload in _ARTIFACTS.values():
        (build / name).write_bytes(payload)
    return plan, build, state


def _gates(tmp_path: Path, **task_ids: list[str]) -> Path:
    ids = task_ids or {"trust": ["P13-x-03"], "new_session": ["P13-x-03"]}
    gates = {}
    for gate_id in ("install", "enable", "trust", "new_session", "uninstall", "pr"):
        gates[gate_id] = {
            "state": "not_applicable" if gate_id == "pr" else "pending_user_gate",
            "task_ids": ids.get(gate_id, []),
            "artifact_refs": ["rollback"] if gate_id == "uninstall" else [],
            "reason": f"{gate_id} は利用者が明示的に行う",
        }
    return _write(tmp_path / "gates.json", gates)


def _artifact_args() -> list[str]:
    args: list[str] = []
    for purpose, (name, _payload) in _ARTIFACTS.items():
        args += ["--artifact", f"{purpose}={name}"]
    return args


def _run_writer(state: Path, plan: Path, gates: Path, *extra: str) -> int:
    return writer.main(["--task-state", str(state), "--plan-dir", str(plan),
                        "--gates", str(gates), *_artifact_args(), *extra])


def _completion_evidence(tmp_path: Path) -> Path:
    (tmp_path / "coverage.json").write_text("{}", encoding="utf-8")
    return _write(tmp_path / "completion-evidence.json", {
        "schema_version": "1.0.0",
        "target_plugin_slug": "acme",
        "overall_status": "pass",
        "gates": [{"id": "coverage", "status": "pass", "evidence": ["coverage.json"],
                   "findings": []}],
        "invalidated_task_ids": [],
        "invalidated_phase_refs": [],
    })


def _tg_c08(tmp_path: Path, state: Path, plan: Path, *extra: str) -> int:
    inbox = tmp_path / "discovered-tasks"
    inbox.mkdir(exist_ok=True)
    return rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "ev.jsonl"),
                     "--task-state", str(state), "--plan-dir", str(plan),
                     "--completion-evidence", str(_completion_evidence(tmp_path)),
                     "--dry-run", *extra])


# ─────────────────────────── 書いて読む往復 ───────────────────────────
def test_written_ledger_is_accepted_by_tg_c08(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    assert _run_writer(state, plan, _gates(tmp_path)) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "written" and report["violations"] == []
    assert Path(report["path"]) == build / _LEDGER

    rc = _tg_c08(tmp_path, state, plan)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["completion_gate"] == "ok"
    gate = out["runtime_pending_user_gate"]
    assert gate["status"] == "accepted" and gate["deferred_task_ids"] == ["P13-x-03"]
    assert gate["path"] == str(build / _LEDGER)


def test_writer_fills_mechanical_fields(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    assert _run_writer(state, plan, _gates(tmp_path)) == 0
    capsys.readouterr()
    ledger = json.loads((build / _LEDGER).read_text(encoding="utf-8"))
    assert ledger["schema_version"] == "2.0.0"
    assert ledger["graph_hash"] == _GRAPH_HASH
    assert rec._valid_utc(ledger["generated_at"])
    assert {a["purpose"]: a["sha256"] for a in ledger["artifacts"]} == {
        purpose: hashlib.sha256(payload).hexdigest()
        for purpose, (_name, payload) in _ARTIFACTS.items()
    }
    assert ledger["boundary"].strip()
    # 一時ファイルを残さない
    assert sorted(p.name for p in build.iterdir() if p.name.startswith(".")) == []


def test_writer_out_path_round_trips_with_runtime_ledger_arg(tmp_path, capsys):
    """--out と TG-C08 --runtime-ledger を同じ path にすれば task-state と別の名前でも往復できる。"""
    plan, build, state = _build(tmp_path)
    out_path = build / "ledger-alt.json"
    assert _run_writer(state, plan, _gates(tmp_path), "--out", str(out_path)) == 0
    capsys.readouterr()
    assert not (build / _LEDGER).exists()
    rc = _tg_c08(tmp_path, state, plan, "--runtime-ledger", str(out_path))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["runtime_pending_user_gate"]["status"] == "accepted"


def test_writer_accepts_absolute_artifact_path_inside_build_dir(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    args = ["--task-state", str(state), "--plan-dir", str(plan), "--gates", str(_gates(tmp_path))]
    for purpose, (name, _payload) in _ARTIFACTS.items():
        args += ["--artifact", f"{purpose}={build / name}"]
    assert writer.main(args) == 0
    capsys.readouterr()
    ledger = json.loads((build / _LEDGER).read_text(encoding="utf-8"))
    assert sorted(a["path"] for a in ledger["artifacts"]) == sorted(
        name for name, _payload in _ARTIFACTS.values())


# ─────────────────────────── 検証してから書く ───────────────────────────
def test_writer_refuses_local_node_as_user_gate_and_writes_nothing(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    rc = _run_writer(state, plan, _gates(tmp_path, trust=["P13-x-02"]))
    report = json.loads(capsys.readouterr().out)
    assert rc == 1 and report["status"] == "invalid"
    assert any("明示 user-gated P13 node でない" in v for v in report["violations"])
    assert not (build / _LEDGER).exists()


def test_writer_invalid_input_keeps_existing_ledger(tmp_path, capsys):
    """検証に落ちた書き直しは、前に書けた ledger を置き換えない。"""
    plan, build, state = _build(tmp_path)
    assert _run_writer(state, plan, _gates(tmp_path)) == 0
    capsys.readouterr()
    before = (build / _LEDGER).read_bytes()
    (build / "route-C01.json").unlink()
    assert _run_writer(state, plan, _gates(tmp_path)) == 1
    report = json.loads(capsys.readouterr().out)
    assert any("artifact 不在: route-C01.json" in v for v in report["violations"])
    assert (build / _LEDGER).read_bytes() == before


def test_writer_requires_all_local_artifacts(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    rc = writer.main(["--task-state", str(state), "--plan-dir", str(plan),
                      "--gates", str(_gates(tmp_path)),
                      "--artifact", "local_build=route-C01.json"])
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("local artifact 欠落" in v for v in report["violations"])
    assert not (build / _LEDGER).exists()


def test_writer_rejects_artifact_outside_build_dir(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    args = ["--task-state", str(state), "--plan-dir", str(plan), "--gates", str(_gates(tmp_path)),
            "--artifact", f"local_build={outside}",
            "--artifact", "native_parity=route-C02.json",
            "--artifact", "rollback=rollback-evidence.json"]
    assert writer.main(args) == 1
    report = json.loads(capsys.readouterr().out)
    assert any("confinement" in v for v in report["violations"])
    assert not (build / _LEDGER).exists()


def test_writer_without_task_state_graph_hash_fails(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    _write(state, {"nodes": [{"id": "T1", "state": "done"}]})
    assert _run_writer(state, plan, _gates(tmp_path)) == 1
    report = json.loads(capsys.readouterr().out)
    assert any("task-state.graph_hash が無い/不正" in v for v in report["violations"])
    assert not (build / _LEDGER).exists()


def test_writer_dry_run_validates_without_writing(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    assert _run_writer(state, plan, _gates(tmp_path), "--dry-run") == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"
    assert not (build / _LEDGER).exists()


@pytest.mark.parametrize("breakage", ["gates", "task_state", "artifact_arg"])
def test_writer_input_errors_exit2(tmp_path, capsys, breakage):
    plan, build, state = _build(tmp_path)
    gates = _gates(tmp_path)
    extra: list[str] = []
    if breakage == "gates":
        gates.write_text("{ not json", encoding="utf-8")
    elif breakage == "task_state":
        state.write_text("{ not json", encoding="utf-8")
    else:
        extra = ["--artifact", "local_build"]
    assert _run_writer(state, plan, gates, *extra) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert not (build / _LEDGER).exists()


# ─────────────────────────── 入力の形・書く先・証跡の実体 ───────────────────────────
@pytest.mark.parametrize("out_name", ["../elsewhere.json", "ledger.txt", ".hidden.json"])
def test_writer_out_outside_build_dir_or_odd_name_is_input_error(tmp_path, capsys, out_name):
    """--out は build dir (task-state の dir) の中の .json だけ。外へ書けると証跡の相対 path の意味が変わる。"""
    plan, build, state = _build(tmp_path)
    out = build / out_name
    assert _run_writer(state, plan, _gates(tmp_path), "--out", str(out)) == 2
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["status"] == "input_error" and report["violations"]
    assert "Traceback" not in captured.err
    assert not out.exists() and not (build / _LEDGER).exists()


def test_writer_out_symlink_is_input_error(tmp_path, capsys):
    plan, build, state = _build(tmp_path)
    target = tmp_path / "outside.json"
    target.write_text("{}", encoding="utf-8")
    link = build / "ledger-link.json"
    link.symlink_to(target)
    assert _run_writer(state, plan, _gates(tmp_path), "--out", str(link)) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "input_error"
    assert target.read_text(encoding="utf-8") == "{}"


def test_writer_non_utf8_stdin_gates_is_input_error(tmp_path, capsys, monkeypatch):
    import io
    plan, build, state = _build(tmp_path)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"\xff\xfe{}"), encoding="utf-8"))
    rc = writer.main(["--task-state", str(state), "--plan-dir", str(plan), "--gates", "-",
                      *_artifact_args()])
    captured = capsys.readouterr()
    assert rc == 2 and "Traceback" not in captured.err
    assert json.loads(captured.out)["status"] == "input_error"
    assert not (build / _LEDGER).exists()


_STATE_BREAKAGES = {
    "task_state_array": [{"id": "T1"}],
    "task_state_duplicate_id": {"graph_hash": _GRAPH_HASH, "nodes": [
        {"id": "T1", "state": "done"}, {"id": "T1", "state": "pending"}]},
    "task_state_nodes_scalar": {"graph_hash": _GRAPH_HASH, "nodes": 5},
    "task_state_nodes_missing": {"graph_hash": _GRAPH_HASH},
}
_GRAPH_BREAKAGES = {
    "graph_nodes_object": {"nodes": {"T1": {}}},
    "graph_array": [],
    "graph_nodes_has_scalar": {"nodes": [{"id": "T1", "phase_ref": "P12"}, 5]},
    "graph_duplicate_id": {"nodes": [{"id": "T1", "phase_ref": "P12"},
                                     {"id": "T1", "phase_ref": "P13"}]},
}


@pytest.mark.parametrize("breakage", [*_STATE_BREAKAGES, *_GRAPH_BREAKAGES])
def test_writer_wrong_shaped_inputs_exit2_without_traceback(tmp_path, capsys, breakage):
    """TG-C08 が拒む形の入力は、書く側でも exit 2 で止める (受理の範囲を揃える)。"""
    plan, build, state = _build(tmp_path)
    if breakage in _STATE_BREAKAGES:
        _write(state, _STATE_BREAKAGES[breakage])
    else:
        _write(plan / "task-graph.json", _GRAPH_BREAKAGES[breakage])
    assert _run_writer(state, plan, _gates(tmp_path)) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert json.loads(captured.out)["status"] == "input_error"
    assert not (build / _LEDGER).exists()


def test_writer_refuses_artifact_symlinked_outside_build_dir(tmp_path, capsys):
    """名前が build dir 相対でも、symlink で外を指す証跡は build dir の証跡と認めない。"""
    plan, build, state = _build(tmp_path)
    outside = tmp_path / "outside-c01.json"
    outside.write_bytes(b"c01\n")
    (build / "route-C01.json").unlink()
    (build / "route-C01.json").symlink_to(outside)
    assert _run_writer(state, plan, _gates(tmp_path)) == 1
    report = json.loads(capsys.readouterr().out)
    assert any("symlink で build dir の外を指す: route-C01.json" in v for v in report["violations"])
    assert not (build / _LEDGER).exists()


def test_tg_c08_refuses_artifact_swapped_for_outside_symlink_after_writing(tmp_path, capsys):
    """書いた後に証跡を同じ中身の外部 symlink へ差し替えても、読む側 (TG-C08) が通さない。"""
    plan, build, state = _build(tmp_path)
    assert _run_writer(state, plan, _gates(tmp_path)) == 0
    capsys.readouterr()
    outside = tmp_path / "outside-c01.json"
    outside.write_bytes(b"c01\n")  # sha256 は一致する
    (build / "route-C01.json").unlink()
    (build / "route-C01.json").symlink_to(outside)
    rc = _tg_c08(tmp_path, state, plan)
    out = json.loads(capsys.readouterr().out)
    assert rc != 0 or out["runtime_pending_user_gate"]["status"] != "accepted"
    assert "symlink で build dir の外を指す" in json.dumps(out, ensure_ascii=False)


def test_writer_unreadable_artifact_is_reported_not_raised(tmp_path, capsys):
    import os
    plan, build, state = _build(tmp_path)
    victim = build / "route-C01.json"
    victim.chmod(0)
    try:
        if os.access(victim, os.R_OK):
            pytest.skip("root などで権限を外しても読めてしまう環境")
        rc = _run_writer(state, plan, _gates(tmp_path))
    finally:
        victim.chmod(0o644)
    captured = capsys.readouterr()
    assert rc == 1 and "Traceback" not in captured.err
    assert not (build / _LEDGER).exists()


def test_written_ledger_is_world_readable_under_umask(tmp_path, capsys):
    import os
    plan, build, state = _build(tmp_path)
    old = os.umask(0o022)
    try:
        assert _run_writer(state, plan, _gates(tmp_path)) == 0
    finally:
        os.umask(old)
    capsys.readouterr()
    assert (build / _LEDGER).stat().st_mode & 0o777 == 0o644


def test_select_ledger_graph_nodes_ignores_non_list_nodes():
    assert rec.select_ledger_graph_nodes({"nodes": [{"id": "T1"}]}, {"nodes": {"T1": {}}}) == []
    assert rec.select_ledger_graph_nodes({"nodes": "T1"}, None) == []
    assert rec.select_ledger_graph_nodes(None, {"nodes": [{"id": "P13"}]}) == [{"id": "P13"}]
