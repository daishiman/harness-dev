"""run-skill-live-trial harness の機械検証 (tmux 非依存)。

- live-trial-status: transcript JSONL の 4 状態分類 + interrupt 例外 + subagents bytes 合算
- live-trial-poll: 終端 4 分岐 (DONE/STALL/GATE/HARD_CAP) + state-file JSON 永続化
- live-trial-verdict: schema 自己検証 / skill_dir_tree_sha 決定論 / proof 機械 gate /
  nudge 降格 / denylist 拒否
- live-trial-backend/boot/send: オフライン検査 (tmux 呼出は BLOCKED/fallback 側のみ)

合成 fixture は references/transcript-jsonl.md の実測スキーマに従う。
"""
import importlib.util
import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial" / "scripts"
SCHEMA = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-live-trial"
    / "schemas" / "live-trial-verdict.schema.json"
)


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"), SCRIPTS / f"{stem}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


status_mod = _load("live-trial-status")
poll_mod = _load("live-trial-poll")
verdict_mod = _load("live-trial-verdict")
planner_mod = _load("plan-live-trials")
backend_mod = _load("live-trial-backend")
boot_mod = _load("live-trial-boot")
send_mod = _load("live-trial-send")


# ---- 合成 transcript fixture -------------------------------------------------

def _write_jsonl(path: Path, entries: list[dict]) -> Path:
    for i, e in enumerate(entries):
        e.setdefault("timestamp", f"2026-07-02T00:00:{i:02d}Z")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return path


def _prompt(text="run the task"):
    return {"type": "user", "message": {"content": text}}


def _turn_end():
    return {"type": "system", "subtype": "turn_duration"}


def _tool_use(tid, name):
    return {"type": "assistant", "message": {
        "model": "claude-opus-4-8",
        "content": [{"type": "tool_use", "id": tid, "name": name}]}}


def _tool_result(tid):
    return {"type": "user", "message": {
        "content": [{"type": "tool_result", "tool_use_id": tid}]}}


FIXTURES = {
    "waiting": [_prompt(), _tool_use("t1", "AskUserQuestion")],
    "busy_tool": [_prompt(), _tool_use("t2", "Bash")],
    "busy_gen": [_prompt()],
    "idle": [_prompt(), _tool_use("t3", "Bash"), _tool_result("t3"), _turn_end()],
}


# ---- live-trial-status: 4 状態分類 -------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("waiting", "WAITING_USER_INPUT"),
    ("busy_tool", "BUSY_TOOL_RUNNING"),
    ("busy_gen", "BUSY_GENERATING"),
    ("idle", "IDLE_TURN_COMPLETE"),
])
def test_status_four_states(tmp_path, name, expected):
    p = _write_jsonl(tmp_path / f"{name}.jsonl", [dict(e) for e in FIXTURES[name]])
    result = status_mod.classify(p)
    assert result["state"] == expected


def test_status_interrupt_is_turn_end(tmp_path):
    entries = [_prompt(), {"type": "user",
                           "message": {"content": "[Request interrupted by user]"}}]
    p = _write_jsonl(tmp_path / "int.jsonl", entries)
    assert status_mod.classify(p)["state"] == "IDLE_TURN_COMPLETE"


def test_status_missing_or_empty_returns_none(tmp_path):
    assert status_mod.classify(tmp_path / "nope.jsonl") is None
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert status_mod.classify(empty) is None
    # 全行 parse 不能も None (TUI fallback へ)
    garbage = tmp_path / "garbage.jsonl"
    garbage.write_text("not json at all\n", encoding="utf-8")
    assert status_mod.classify(garbage) is None


def test_status_subagent_bytes_aggregated(tmp_path):
    """fork 内長時間実行の STALL 誤報対策: subagents/*.jsonl bytes を合算する。"""
    p = _write_jsonl(tmp_path / "s.jsonl", [_prompt()])
    base = status_mod.transcript_bytes(p)
    sub = tmp_path / "s" / "subagents"
    sub.mkdir(parents=True)
    (sub / "a.jsonl").write_text("x" * 100, encoding="utf-8")
    assert status_mod.transcript_bytes(p) == base + 100


def test_status_cli_exit3_on_missing(tmp_path, capsys):
    assert status_mod.main([str(tmp_path / "none.jsonl")]) == 3
    p = _write_jsonl(tmp_path / "idle.jsonl", [dict(e) for e in FIXTURES["idle"]])
    assert status_mod.main([str(p)]) == 0
    out = capsys.readouterr().out
    assert "STATE:IDLE_TURN_COMPLETE" in out and "BYTES:" in out


# ---- live-trial-poll: 終端 4 分岐 + state-file --------------------------------

def _poll_env(monkeypatch, tmp_path, session_id="u-1", **env):
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setenv("SESSION_ID", session_id)
    defaults = {"INTERVAL": "0", "STABLE_TICKS": "2",
                "STALL_LIMIT": "600", "HARD_CAP": "7200"}
    defaults.update({k: str(v) for k, v in env.items()})
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)
    return projects


def test_poll_done(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text('{"status":"PASS"}', encoding="utf-8")
    rc = poll_mod.main([str(marker), "lt-test"])
    assert rc == poll_mod.EXIT_DONE
    assert "via jsonl" in capsys.readouterr().out


def test_poll_gate_after_two_ticks_and_resets(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["waiting"]])
    state_file = tmp_path / "state.json"
    rc = poll_mod.main(["--state-file", str(state_file),
                        str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_GATE
    assert "AskUserQuestion" in capsys.readouterr().out
    # 応答後の再 poll が即 GATE 再発しないよう gate_ticks=0 で永続化される
    assert json.loads(state_file.read_text())["gate_ticks"] == 0


def test_poll_stall_no_artifact(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1", STALL_LIMIT="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    rc = poll_mod.main([str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_STALL
    assert "成果物なし" in capsys.readouterr().out


def test_poll_hard_cap(monkeypatch, tmp_path, capsys):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1", HARD_CAP="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["busy_gen"]])
    rc = poll_mod.main([str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_HARD_CAP
    out = capsys.readouterr().out
    assert "HARD_CAP" in out


def test_poll_state_file_persists_counters(monkeypatch, tmp_path):
    projects = _poll_env(monkeypatch, tmp_path, INTERVAL="1")
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["busy_gen"]])
    state_file = tmp_path / "state.json"
    rc = poll_mod.main(["--state-file", str(state_file), "--max-ticks", "2",
                        str(tmp_path / "out" / "status.json"), "lt-test"])
    assert rc == poll_mod.EXIT_TICK_BUDGET
    st = json.loads(state_file.read_text())
    assert st["elapsed"] == 1  # 呼び越しで 0 に戻らない (STALL/HARD_CAP 実効の前提)
    assert st["prev"].startswith("jsonl:")
    # 同一 state-file の再呼びで elapsed が引き継がれ DONE に到達する
    # (trial 完了を模して jsonl を idle へ更新 — busy のままだと DONE 条件を満たさない)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text('{"status":"PASS"}', encoding="utf-8")
    monkeypatch.setenv("INTERVAL", "0")
    monkeypatch.setenv("STABLE_TICKS", "1")
    rc2 = poll_mod.main(["--state-file", str(state_file),
                         str(marker), "lt-test"])
    assert rc2 == poll_mod.EXIT_DONE
    assert json.loads(state_file.read_text())["elapsed"] >= 1


def test_poll_corrupt_state_file_recovers(monkeypatch, tmp_path):
    projects = _poll_env(monkeypatch, tmp_path)
    _write_jsonl(projects / "u-1.jsonl", [dict(e) for e in FIXTURES["idle"]])
    state_file = tmp_path / "state.json"
    state_file.write_text("{broken", encoding="utf-8")
    marker = tmp_path / "out" / "status.json"
    marker.parent.mkdir()
    marker.write_text("{}", encoding="utf-8")
    assert poll_mod.main(["--state-file", str(state_file),
                          str(marker), "lt-test"]) == poll_mod.EXIT_DONE


# ---- live-trial-verdict: schema / tree sha / gate ----------------------------

def _fake_skill_dir(tmp_path: Path) -> Path:
    d = tmp_path / "fake-skill"
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: fake\n---\nbody\n", encoding="utf-8")
    (d / "scripts" / "a.py").write_text("print('a')\n", encoding="utf-8")
    return d


def _run_verdict(tmp_path, transcript: Path, extra: list[str]) -> tuple[int, Path]:
    workdir = tmp_path / "workdir"
    skill_dir = _fake_skill_dir(tmp_path)
    argv = [
        "--workdir", str(workdir),
        "--target-skill", "some-plugin:run-something",
        "--skill-dir", str(skill_dir),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS",
        "--poll-exit", "DONE",
    ] + extra
    rc = verdict_mod.main(argv)
    return rc, workdir / "verdict.json"


@pytest.fixture()
def transcript(tmp_path):
    entries = [dict(_prompt()), dict(_tool_use("t9", "Bash")),
               dict(_tool_result("t9")), dict(_turn_end())]
    entries[1]["version"] = "2.1.173"
    return _write_jsonl(tmp_path / "src" / "u-9.jsonl", entries)


def test_verdict_pass_and_schema_valid(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--goal-result", "PASS"])
    assert rc == 0
    doc = json.loads(out.read_text())
    schema = json.loads(SCHEMA.read_text())
    assert verdict_mod.validate_schema(doc, schema) == []
    assert doc["overall"]["verdict"] == "PASS"
    assert doc["actual_model"] == ["claude-opus-4-8"]
    assert doc["environment"]["claude_version"] == "2.1.173"
    assert doc["environment"]["transcript_layer"] == "jsonl"
    assert doc["transcript_sha256"] and len(doc["transcript_sha256"]) == 64
    assert (tmp_path / "workdir" / "transcript.jsonl").is_file()


def test_verdict_goal_fail_degrades(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "FAIL", "--blocker", "成果物が目的を満たさない"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "goal-proxy" in doc["downgrade_reason"]


def test_verdict_nudge_degrades(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--nudge-count", "1"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "DEGRADED"
    assert "自走未達" in doc["downgrade_reason"]


def test_verdict_proof_model_gate(tmp_path, transcript):
    # transcript の actual は claude-opus-4-8 — requested と不一致なら proof は FAIL
    rc, out = _run_verdict(tmp_path, transcript,
                           ["--goal-result", "PASS", "--proof",
                            "--requested-model", "claude-sonnet-5"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "FAIL"
    assert "proof" in doc["downgrade_reason"]
    # 一致すれば PASS
    rc2, out2 = _run_verdict(tmp_path, transcript,
                             ["--goal-result", "PASS", "--proof",
                              "--requested-model", "claude-opus-4-8"])
    assert json.loads(out2.read_text())["overall"]["verdict"] == "PASS"


def test_verdict_blocked_fail_closed(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--blocked"])
    doc = json.loads(out.read_text())
    assert doc["overall"]["verdict"] == "BLOCKED"
    assert doc["overall"]["goal_fit"] == "NOT_EVALUATED"
    assert doc["goal_verdict"]["blockers"]  # 未実施の blocker が自動記録される


def test_verdict_denylist_rejected(tmp_path, transcript, capsys):
    workdir = tmp_path / "wd"
    rc = verdict_mod.main([
        "--workdir", str(workdir),
        "--target-skill", "harness-creator:run-skill-live-trial",
        "--skill-dir", str(_fake_skill_dir(tmp_path)),
        "--transcript", str(transcript),
        "--launch", "PASS", "--completion", "PASS",
    ])
    assert rc == 2
    assert "DENYLIST" in capsys.readouterr().err


def test_tree_sha_deterministic_and_content_sensitive(tmp_path):
    d1 = _fake_skill_dir(tmp_path / "a")
    d2 = _fake_skill_dir(tmp_path / "b")
    sha1 = verdict_mod.skill_dir_tree_sha(d1)
    assert sha1 == verdict_mod.skill_dir_tree_sha(d1)  # 決定論
    assert sha1 == verdict_mod.skill_dir_tree_sha(d2)  # 同内容 → 同 sha
    (d2 / "scripts" / "a.py").write_text("print('b')\n", encoding="utf-8")
    assert sha1 != verdict_mod.skill_dir_tree_sha(d2)  # 内容変更で変わる


def _write_package_contract(
    plugin_dir: Path, depends_on: list[str], *, skills: list[str] | None = None,
    skill_dependencies: dict[str, list[str]] | None = None,
) -> Path:
    path = plugin_dir / "references" / "package-contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "plugin_name": plugin_dir.name,
        "depends_on": depends_on,
        "entry_points": {
            "skills": skills or [],
            "agents": [],
            "commands": [],
            "hooks": [],
        },
    }
    if skill_dependencies is not None:
        document["skill_dependencies"] = skill_dependencies
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _behavior_closure_fixture(tmp_path: Path) -> tuple[Path, Path]:
    plugin_dir = _write_trial_plugin(
        tmp_path, "dev-graph", "dev-graph", skill_name="run-behavior"
    )
    dependency = _write_trial_plugin(
        tmp_path, "system-spec-harness", "system-spec-harness", skill_name="run-delegate"
    )
    _write_package_contract(plugin_dir, ["system-spec-harness"])
    _write_package_contract(dependency, [], skills=["run-delegate"])
    skill_dir = plugin_dir / "skills" / "run-behavior"
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "local.py").write_text("print('local')\n", encoding="utf-8")
    (skill_dir / "prompts").mkdir()
    (skill_dir / "prompts" / "R0.md").write_text("prompt-v1\n", encoding="utf-8")
    (plugin_dir / "scripts").mkdir()
    (plugin_dir / "scripts" / "shared.py").write_text("print('shared')\n", encoding="utf-8")
    (plugin_dir / "references" / "contract.md").write_text("contract-v1\n", encoding="utf-8")
    (plugin_dir / "hooks").mkdir()
    (plugin_dir / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
    (dependency / "hooks").mkdir()
    (dependency / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: run-behavior\n"
        "script_refs: [../../scripts/shared.py]\n"
        "reference_refs:\n"
        "  - ../../references/contract.md\n"
        "responsibility_refs: [prompts/R0.md]\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    return plugin_dir, skill_dir


@pytest.mark.parametrize("relative_path", [
    "prompts/R0.md",
    "../../scripts/shared.py",
    "../../references/contract.md",
    "../../hooks/hooks.json",
    "../../.claude-plugin/plugin.json",
])
def test_tree_sha_binds_declared_behavior_closure(tmp_path, relative_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    path = (skill_dir / relative_path).resolve()
    if path.name == "plugin.json":
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["version"] = "0.1.1"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        path.write_text(path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_binds_declared_dependency_manifest_and_hooks(tmp_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    dependency = tmp_path / "plugins" / "system-spec-harness"
    (dependency / "hooks" / "hooks.json").write_text('{"changed":true}\n', encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_binds_declared_dependency_skill_behavior(tmp_path):
    _plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    dependency_skill = (
        tmp_path / "plugins" / "system-spec-harness" / "skills"
        / "run-delegate" / "SKILL.md"
    )
    dependency_skill.write_text("---\nname: run-delegate\n---\nchanged\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) != before


def test_tree_sha_ignores_dependency_outside_skill_scope(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-behavior"],
        skill_dependencies={},
    )
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    dependency_skill = (
        tmp_path / "plugins" / "system-spec-harness" / "skills"
        / "run-delegate" / "SKILL.md"
    )
    dependency_skill.write_text("---\nname: run-delegate\n---\nchanged\n", encoding="utf-8")
    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before


def test_tree_sha_ignores_other_skills_package_contract_projection(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-behavior", "run-other"],
        skill_dependencies={"run-behavior": []},
    )
    before = verdict_mod.skill_dir_tree_sha(skill_dir)
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-behavior", "run-other"],
        skill_dependencies={
            "run-behavior": [],
            "run-other": ["system-spec-harness"],
        },
    )
    assert verdict_mod.skill_dir_tree_sha(skill_dir) == before


def test_tree_sha_rejects_missing_and_symlink_escape_refs(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\nscript_refs: [scripts/missing.py]\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing"):
        verdict_mod.skill_dir_tree_sha(skill_dir)

    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("unsafe\n", encoding="utf-8")
    (plugin_dir / "scripts" / "escape.py").symlink_to(outside)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\nscript_refs: [../../scripts/escape.py]\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="escapes repository"):
        verdict_mod.skill_dir_tree_sha(skill_dir)

    (plugin_dir / "scripts" / "escape.py").unlink()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\nscript_refs: [../../scripts/shared.py]\n---\n",
        encoding="utf-8",
    )
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-dir"
    outside_dir.mkdir()
    (plugin_dir / "hooks" / "escape-dir").symlink_to(
        outside_dir, target_is_directory=True
    )
    with pytest.raises(ValueError, match="escapes repository"):
        verdict_mod.skill_dir_tree_sha(skill_dir)


def test_tree_sha_rejects_undeclared_cross_plugin_ref(tmp_path):
    plugin_dir, skill_dir = _behavior_closure_fixture(tmp_path)
    extra = _write_trial_plugin(tmp_path, "undeclared", "undeclared", skill_name="run-x")
    (extra / "references").mkdir()
    (extra / "references" / "behavior.md").write_text("external\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: run-behavior\n"
        "reference_refs: [../../../undeclared/references/behavior.md]\n"
        "---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not declared"):
        verdict_mod.skill_dir_tree_sha(skill_dir)
    _write_package_contract(extra, [], skills=["run-x"])
    _write_package_contract(plugin_dir, ["system-spec-harness", "undeclared"])
    assert len(verdict_mod.skill_dir_tree_sha(skill_dir)) == 64


def test_schema_rejects_additional_properties(tmp_path, transcript):
    rc, out = _run_verdict(tmp_path, transcript, ["--goal-result", "PASS"])
    doc = json.loads(out.read_text())
    schema = json.loads(SCHEMA.read_text())
    doc["extra_key"] = 1
    errs = verdict_mod.validate_schema(doc, schema)
    assert any("additionalProperties" in e for e in errs)
    del doc["extra_key"]
    del doc["timeline"]
    errs = verdict_mod.validate_schema(doc, schema)
    assert any("timeline" in e for e in errs)


# ---- plan-live-trials: incremental evidence reuse / bounded dispatch ---------

def _planner_plugin(tmp_path: Path, skills: list[str]) -> Path:
    plugin_dir = tmp_path / "plugins" / "sample-plugin"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "sample-plugin"}), encoding="utf-8"
    )
    for skill in skills:
        skill_dir = plugin_dir / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill}\nkind: run\nallowed-tools: [Read, Skill]\n---\nbody\n",
            encoding="utf-8",
        )
    _write_package_contract(plugin_dir, [], skills=skills, skill_dependencies={})
    return plugin_dir


def _write_reusable_verdict(eval_root: Path, plugin_dir: Path, skill: str) -> Path:
    run_dir = eval_root / plugin_dir.name / skill / "live-trial" / "20260713T000000"
    run_dir.mkdir(parents=True)
    transcript = run_dir / "transcript.jsonl"
    transcript.write_text('{"type":"system","subtype":"turn_duration"}\n', encoding="utf-8")
    transcript_sha = planner_mod._sha256(transcript)
    behavior_sha = verdict_mod.skill_dir_tree_sha(plugin_dir / "skills" / skill)
    verdict = {
        "target_skill": f"{plugin_dir.name}:{skill}",
        "args": "",
        "requested_model": "",
        "actual_model": ["claude-test"],
        "nudge_count": 0,
        "gate_response_count": 0,
        "goal_verdict": {"result": "PASS", "blockers": []},
        "overall": {
            "launch": "PASS", "completion": "PASS", "goal_fit": "PASS",
            "verdict": "PASS",
        },
        "skill_dir_tree_sha": behavior_sha,
        "transcript_sha256": transcript_sha,
        "scenario_origin": "synthetic",
        "scenario_id": f"{skill}-positive",
        "environment": {
            "claude_version": "test", "tmux": True,
            "transcript_layer": "jsonl", "permissions_mode": "test",
        },
        "tier": "live",
        "downgrade_reason": None,
        "timeline": {"boot_s": 1, "poll_exit": "DONE", "wall_clock_s": 2},
    }
    path = run_dir / "verdict.json"
    path.write_text(json.dumps(verdict), encoding="utf-8")
    return path


def test_incremental_plan_reuses_current_pass_and_bounds_new_runs(tmp_path):
    skills = ["run-a", "run-b", "run-c"]
    plugin_dir = _planner_plugin(tmp_path, skills)
    eval_root = tmp_path / "eval-log"
    evidence = _write_reusable_verdict(eval_root, plugin_dir, "run-a")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental",
        max_live_trials=1, max_concurrency=2,
    )
    actions = {record["skill"]: record["action"] for record in plan["skills"]}
    assert actions == {"run-a": "reuse", "run-b": "run", "run-c": "defer"}
    assert plan["live_batches"] == [["run-b"]]
    assert plan["counts"] == {"static": 0, "fork": 0, "reuse": 1, "run": 1, "defer": 1}
    assert plan["skills"][0]["reused_evidence"] == str(evidence)


def test_incremental_plan_invalidates_evidence_on_behavior_change(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")
    with (plugin_dir / "skills" / "run-a" / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("changed\n")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="incremental",
        max_live_trials=1, max_concurrency=1,
    )
    assert [record["action"] for record in plan["skills"]] == ["run", "defer"]
    assert plan["skills"][0]["reason"] == "behavior-changed"


def test_exhaustive_plan_explicitly_reruns_current_evidence(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="exhaustive",
        max_live_trials=0, max_concurrency=1,
    )
    assert [record["action"] for record in plan["skills"]] == ["run", "run"]
    assert plan["policy"]["max_live_trials"] is None
    assert plan["live_batches"] == [["run-a"], ["run-b"]]


def test_build_only_plan_never_schedules_live_session(tmp_path):
    plugin_dir = _planner_plugin(tmp_path, ["run-a", "run-b"])
    eval_root = tmp_path / "eval-log"
    _write_reusable_verdict(eval_root, plugin_dir, "run-a")

    plan = planner_mod.build_plan(
        plugin_dir, eval_root, profile="build-only",
        max_live_trials=9, max_concurrency=9,
    )
    assert [record["action"] for record in plan["skills"]] == ["defer", "defer"]
    assert {record["reason"] for record in plan["skills"]} == {
        "not-run(profile=build-only)"
    }
    assert plan["live_batches"] == []
    assert plan["policy"]["max_live_trials"] == 0


# ---- backend / boot / send: オフライン検査 ------------------------------------

def test_backend_denylist_and_session_names():
    assert backend_mod.deny_target_skill("run-skill-live-trial")
    assert backend_mod.deny_target_skill("harness-creator:run-skill-iter-improve")
    assert not backend_mod.deny_target_skill("harness-creator:run-goal-seek")
    assert backend_mod.valid_session_name("lt-20260702T000000-x")
    assert not backend_mod.valid_session_name("../evil")
    assert not backend_mod.valid_session_name("a/b")


def test_backend_blocked_without_tmux(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    with pytest.raises(SystemExit) as exc:
        backend_mod.require_tmux()
    assert exc.value.code == 3


def test_backend_self_test_cli():
    assert backend_mod.main(["--self-test"]) == 0
    assert backend_mod.main(["deny-check", "harness-creator:run-goal-seek"]) == 0
    assert backend_mod.main(["deny-check", "run-skill-live-trial"]) == 2


def test_boot_denylist_and_validation(tmp_path, capsys):
    assert boot_mod.main(["--self-test"]) == 0
    rc = boot_mod.main(["lt-x", str(tmp_path),
                        "--target-skill", "run-skill-iter-improve"])
    assert rc == 2
    assert "DENYLIST" in capsys.readouterr().err
    assert boot_mod.main(["../evil", str(tmp_path)]) == 2
    assert boot_mod.main(["lt-x", str(tmp_path / "missing")]) == 2
    assert boot_mod.main(["lt-x", str(tmp_path), "--model", "bad model;rm"]) == 2
    assert boot_mod.main([
        "lt-x", str(tmp_path), "--session-id", "bad; touch /tmp/injected"
    ]) == 2


def _write_trial_plugin(
    root: Path, directory_name: str, manifest_name: str,
    skill_name: str = "run-dev-graph-init",
) -> Path:
    plugin_dir = root / "plugins" / directory_name
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": manifest_name}), encoding="utf-8"
    )
    skill_dir = plugin_dir / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\ndescription: fixture\n---\n", encoding="utf-8")
    return plugin_dir


def test_boot_qualified_target_pins_cwd_plugin_dir(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    resolved = boot_mod.resolve_target_plugin_dir(
        str(tmp_path), "dev-graph:run-dev-graph-init"
    )
    assert resolved == plugin_dir.resolve()
    argv = boot_mod.build_claude_argv("u-1", "", resolved)
    assert argv[-2:] == ("--plugin-dir", str(plugin_dir.resolve()))
    assert argv[argv.index("--setting-sources") + 1] == "local"
    assert boot_mod.resolve_target_plugin_dir(str(tmp_path), "plain-skill") is None
    assert "--plugin-dir" not in boot_mod.build_claude_argv("u-1", "")


def test_boot_qualified_target_loads_only_declared_dependencies(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    dep_b = _write_trial_plugin(tmp_path, "system-spec-harness", "system-spec-harness")
    dep_a = _write_trial_plugin(tmp_path, "system-dev-planner", "system-dev-planner")
    undeclared = _write_trial_plugin(tmp_path, "other-plugin", "other-plugin")
    _write_package_contract(plugin_dir, ["system-spec-harness", "system-dev-planner"])

    resolved = boot_mod.resolve_target_plugin_dirs(
        str(tmp_path), "dev-graph:run-dev-graph-init"
    )
    assert resolved == (plugin_dir.resolve(), dep_a.resolve(), dep_b.resolve())
    assert undeclared.resolve() not in resolved
    argv = boot_mod.build_claude_argv("u-1", "", resolved)
    loaded = [argv[index + 1] for index, value in enumerate(argv) if value == "--plugin-dir"]
    assert loaded == [str(path) for path in resolved]


def test_boot_qualified_target_honors_per_skill_dependency_scope(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    second = plugin_dir / "skills" / "run-dev-graph-system-spec"
    second.mkdir(parents=True)
    (second / "SKILL.md").write_text("---\ndescription: fixture\n---\n", encoding="utf-8")
    dependency = _write_trial_plugin(
        tmp_path, "system-spec-harness", "system-spec-harness"
    )
    _write_package_contract(
        plugin_dir,
        ["system-spec-harness"],
        skills=["run-dev-graph-init", "run-dev-graph-system-spec"],
        skill_dependencies={
            "run-dev-graph-system-spec": ["system-spec-harness"],
        },
    )

    init_dirs = boot_mod.resolve_target_plugin_dirs(
        str(tmp_path), "dev-graph:run-dev-graph-init"
    )
    system_spec_dirs = boot_mod.resolve_target_plugin_dirs(
        str(tmp_path), "dev-graph:run-dev-graph-system-spec"
    )
    assert init_dirs == (plugin_dir.resolve(),)
    assert system_spec_dirs == (plugin_dir.resolve(), dependency.resolve())


def test_boot_rejects_skill_dependency_outside_package_allow_list(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    _write_package_contract(
        plugin_dir,
        [],
        skills=["run-dev-graph-init"],
        skill_dependencies={"run-dev-graph-init": ["undeclared-plugin"]},
    )
    with pytest.raises(ValueError, match="subset of depends_on"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


def test_boot_declared_dependency_fails_closed_on_missing_or_manifest_mismatch(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    _write_package_contract(plugin_dir, ["system-spec-harness"])
    with pytest.raises(ValueError, match="directory not found"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )
    _write_trial_plugin(tmp_path, "system-spec-harness", "wrong-name")
    with pytest.raises(ValueError, match="manifest name mismatch"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


def test_boot_declared_dependency_rejects_symlink_escape(tmp_path):
    plugin_dir = _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    _write_package_contract(plugin_dir, ["system-spec-harness"])
    outside = _write_trial_plugin(
        tmp_path / "outside-root", "system-spec-harness", "system-spec-harness"
    )
    (tmp_path / "plugins" / "system-spec-harness").symlink_to(
        outside, target_is_directory=True
    )
    with pytest.raises(ValueError, match="escapes cwd/plugins"):
        boot_mod.resolve_target_plugin_dirs(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


@pytest.mark.parametrize("target", [
    "../evil:run-safe",
    "Dev_Graph:run-safe",
    "dev-graph:../run-safe",
    "dev-graph:run-safe:extra",
])
def test_boot_qualified_target_rejects_invalid_slug_or_path(tmp_path, target):
    with pytest.raises(ValueError):
        boot_mod.resolve_target_plugin_dir(str(tmp_path), target)


def test_boot_qualified_target_rejects_symlink_escape(tmp_path):
    outside = _write_trial_plugin(tmp_path / "outside-root", "outside", "escape")
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes cwd/plugins"):
        boot_mod.resolve_target_plugin_dir(str(tmp_path), "escape:run-safe")


def test_boot_qualified_target_rejects_manifest_name_mismatch(tmp_path):
    _write_trial_plugin(tmp_path, "dev-graph", "different-plugin")
    with pytest.raises(ValueError, match="manifest name mismatch"):
        boot_mod.resolve_target_plugin_dir(
            str(tmp_path), "dev-graph:run-dev-graph-init"
        )


def test_boot_qualified_target_rejects_missing_plugin(tmp_path):
    with pytest.raises(ValueError, match="directory not found"):
        boot_mod.resolve_target_plugin_dir(
            str(tmp_path), "missing-plugin:run-safe"
        )


def test_boot_qualified_target_rejects_missing_skill_in_pinned_plugin(tmp_path):
    _write_trial_plugin(tmp_path, "dev-graph", "dev-graph")
    with pytest.raises(ValueError, match="target skill not found"):
        boot_mod.resolve_target_plugin_dir(
            str(tmp_path), "dev-graph:run-missing"
        )


def test_send_usage_errors(tmp_path, capsys):
    assert send_mod.main(["../evil", str(tmp_path / "task.md")]) == 2
    assert send_mod.main(["lt-x", str(tmp_path / "missing.md")]) == 2


def test_send_jsonl_accept_detection(tmp_path):
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True)
    task = tmp_path / "task.md"
    task.write_text("do it", encoding="utf-8")
    line = json.dumps({"type": "user", "message": {"content": f"読んで実行: {task}"}})
    (projects / "u-2.jsonl").write_text(line + "\n", encoding="utf-8")
    assert send_mod.jsonl_accepted(str(tmp_path / "projects"), "u-2", str(task))
    assert not send_mod.jsonl_accepted(str(tmp_path / "projects"), "u-404", str(task))


# ---- fake backend による tmux 経路の網羅 (実 tmux 非依存) ----------------------

class FakeSendBackend:
    """live-trial-send.main が触る backend 面だけを実装する fake。"""

    def __init__(self, cap=""):
        self.cap = cap
        self.enters = 0
        self.pasted = ""

    def valid_session_name(self, s):
        return backend_mod.valid_session_name(s)

    def require_tmux(self):
        pass

    def paste_file(self, _session, path):
        self.pasted = Path(path).read_text(encoding="utf-8")

    def send_keys(self, _session, *_keys):
        self.enters += 1

    def capture_pane(self, _session, scrollback=False):
        return self.cap


def test_send_started_via_tui_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    monkeypatch.delenv("SESSION_ID", raising=False)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    fb = FakeSendBackend(cap="✻ … (5s · 120 tokens)")
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 0
    # 指示行はファイル経由 (paste) で送られ、taskfile の絶対パスを含む
    assert str(task.resolve()) in fb.pasted


def test_send_unconfirmed_retries_then_warn(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    monkeypatch.delenv("SESSION_ID", raising=False)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    fb = FakeSendBackend(cap="")  # 着手マーカーなし
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 1
    assert fb.enters == 3  # Enter 再送は 3 回で打ち切り
    assert "WARN" in capsys.readouterr().out


def test_send_jsonl_primary_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(send_mod.time, "sleep", lambda _s: None)
    task = tmp_path / "task.md"
    task.write_text("do", encoding="utf-8")
    projects = tmp_path / "projects" / "proj"
    projects.mkdir(parents=True)
    line = json.dumps({"type": "user",
                       "message": {"content": f"読んで実行: {task.resolve()}"}})
    (projects / "u-3.jsonl").write_text(line + "\n", encoding="utf-8")
    monkeypatch.setenv("SESSION_ID", "u-3")
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(tmp_path / "projects"))
    fb = FakeSendBackend(cap="")  # TUI は無反応でも jsonl 一次判定で確定する
    assert send_mod.main(["lt-x", str(task)], backend=fb) == 0


class FakeBootBackend:
    """live-trial-boot.boot が触る backend 面だけを実装する fake。"""

    def __init__(self, captures, cmds):
        self.captures = captures
        self.cmds = cmds
        self.tick = 0
        self.killed = []
        self.sent = ""
        self.argv = None
        self.send_calls = 0
        self.key_sends = []

    def new_session(self, _s, _c, command_argv=None):
        self.argv = command_argv
        if command_argv:
            self.sent = " ".join(command_argv)

    def send_line(self, _s, text):
        self.send_calls += 1
        self.sent = text

    def send_keys(self, _s, *keys):
        self.key_sends.append(tuple(keys))

    def capture_pane(self, _s, scrollback=False):
        return self.captures[min(self.tick, len(self.captures) - 1)]

    def pane_current_command(self, _s):
        v = self.cmds[min(self.tick, len(self.cmds) - 1)]
        self.tick += 1
        return v

    def kill_session(self, s):
        self.killed.append(s)


def test_boot_ready_line_contract(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["Type /help for shortcuts\n❯ "], ["2.1.173"])
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "claude-opus-4-8", "u-1",
                       timeout=5, grace=1)
    assert rc == 0
    out = capsys.readouterr().out
    # SESSION_ID: は行末固定 (parse 互換) / MODEL: は requested の echo
    assert "READY: lt-x" in out
    assert out.strip().endswith("SESSION_ID:u-1")
    assert "MODEL:claude-opus-4-8" in out
    assert "--model claude-opus-4-8" in fb.sent
    assert "--setting-sources local" in fb.sent
    assert fb.argv == boot_mod.build_claude_argv("u-1", "claude-opus-4-8")
    assert fb.send_calls == 0  # 対話 shell への send-line を経由しない
    assert fb.key_sends == []


def test_boot_accepts_exact_bypass_gate_once_then_waits_for_prompt(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    gate = "\n".join(boot_mod._BYPASS_CONFIRM_MARKERS)
    fb = FakeBootBackend(
        [gate, "Welcome to Claude Code\nType /help for shortcuts\n❯ "],
        ["claude", "claude"],
    )
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "", "u-1", timeout=4, grace=1)
    assert rc == 0
    assert fb.key_sends == [("Down",), ("Enter",)]
    assert "READY: lt-x (2s)" in capsys.readouterr().out


def test_boot_ready_regex_matches_real_nbsp_try_prompt_not_numbered_gate():
    real_prompt = '❯\u00a0Try "how do I log an error?"'
    assert boot_mod._READY_RE.search(real_prompt)
    assert boot_mod._READY_RE.search("❯   ")
    assert not boot_mod._READY_RE.search("❯ 1. Yes, I trust this folder")
    assert not boot_mod._READY_RE.search("❯\u00a01. No, exit")


def test_boot_never_repeats_bypass_gate_acceptance(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    gate = "\n".join(boot_mod._BYPASS_CONFIRM_MARKERS)
    fb = FakeBootBackend([gate], ["claude"])
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "", "u-1", timeout=3, grace=1)
    assert rc == 1
    assert fb.key_sends == [("Down",), ("Enter",)]
    assert "TIMEOUT" in capsys.readouterr().out


def test_boot_does_not_answer_non_exact_gate(monkeypatch):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    partial = (
        "WARNING: Claude Code running in Bypass Permissions mode\n"
        "1. No, exit\n2. Continue\nEnter to confirm"
    )
    fb = FakeBootBackend([partial], ["claude"])
    assert boot_mod.boot(
        fb, "lt-x", "/tmp", "", "u-1", timeout=1, grace=1
    ) == 1
    assert fb.key_sends == []


def test_boot_fail_when_claude_dies(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["zsh: command not found: claude"], ["zsh"])
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "", "u-1", timeout=5, grace=0)
    assert rc == 1
    assert "BOOT_FAIL" in capsys.readouterr().out
    assert fb.killed == ["lt-x"]  # 失敗経路でも session を掃除する


def test_boot_timeout_no_ready(monkeypatch, capsys):
    monkeypatch.setattr(boot_mod.time, "sleep", lambda _s: None)
    fb = FakeBootBackend(["still starting"], ["2.1.173"])
    rc = boot_mod.boot(fb, "lt-x", "/tmp", "", "u-1", timeout=2, grace=1)
    assert rc == 1
    assert "TIMEOUT" in capsys.readouterr().out
    assert fb.killed == ["lt-x"]


def test_backend_tmux_wrappers_with_fake_subprocess(monkeypatch, tmp_path):
    calls = []

    class CP:
        returncode = 0
        stdout = "lt-a\nlt-b\nother\n"
        stderr = ""

    def fake_run(args, capture_output=True, text=True, check=False):
        calls.append(list(args))
        return CP()

    monkeypatch.setattr(backend_mod.shutil, "which", lambda _c: "/usr/bin/tmux")
    monkeypatch.setattr(backend_mod.subprocess, "run", fake_run)

    backend_mod.new_session("lt-x", str(tmp_path))
    backend_mod.new_session(
        "lt-direct", str(tmp_path),
        command_argv=("printf", "%s", "safe; touch /tmp/not-created"),
    )
    backend_mod.send_line("lt-x", "hello")
    backend_mod.paste_text("lt-x", "task body\nwith newline")
    assert backend_mod.capture_pane("lt-x", scrollback=True) == CP.stdout
    assert backend_mod.has_session("lt-x")
    assert backend_mod.pane_current_command("lt-x") == "lt-a"
    assert backend_mod.reap("lt-") == ["lt-a", "lt-b"]
    kill_calls = [c for c in calls if c[:2] == ["tmux", "kill-session"]]
    assert len(kill_calls) >= 3  # new_session 前掃除 + reap 2 件
    # paste は session/file 固有 named buffer を load → paste → delete する。
    flat = [c[1] for c in calls]
    assert {"load-buffer", "paste-buffer", "delete-buffer"} <= set(flat)
    load_call = next(c for c in calls if c[1] == "load-buffer")
    paste_call = next(c for c in calls if c[1] == "paste-buffer")
    delete_call = next(c for c in calls if c[1] == "delete-buffer")
    assert load_call[2] == "-b"
    assert paste_call[2:4] == ["-b", load_call[3]]
    assert delete_call[2:4] == ["-b", load_call[3]]
    assert backend_mod.valid_buffer_name(load_call[3])
    assert len(load_call[3]) <= backend_mod._BUFFER_NAME_MAX
    direct = next(c for c in calls if c[1:5] == ["new-session", "-d", "-s", "lt-direct"])
    assert direct[-1] == "printf %s 'safe; touch /tmp/not-created'"
    # CLI dispatch も同じ境界を通る
    assert backend_mod.main(["new-session", "lt-y", str(tmp_path)]) == 0
    assert backend_mod.main(["send-line", "lt-y", "hi"]) == 0
    assert backend_mod.main(["capture-pane", "lt-y", "--scrollback"]) == 0
    assert backend_mod.main(["has-session", "lt-y"]) == 0
    assert backend_mod.main(["kill-session", "lt-y"]) == 0
    assert backend_mod.main(["reap"]) == 0
    assert backend_mod.main(["require"]) == 0
    assert backend_mod.main(["kill-session", "../evil"]) == 2  # session 名検証は CLI 層でも効く


def test_backend_cli_does_not_expose_arbitrary_direct_command(tmp_path):
    """new-session CLI は command 余剰引数を受けず argparse で拒否する。"""
    with pytest.raises(SystemExit) as exc:
        backend_mod.main([
            "new-session", "lt-x", str(tmp_path), "; touch /tmp/injected"
        ])
    assert exc.value.code == 2


def test_backend_paste_buffer_name_is_deterministic_isolated_and_injection_safe(tmp_path):
    path = tmp_path / "task; display-message.md"
    same_a = backend_mod.paste_buffer_name("lt-route-a", path)
    same_b = backend_mod.paste_buffer_name("lt-route-a", path)
    other_session = backend_mod.paste_buffer_name("lt-route-b", path)
    other_path = backend_mod.paste_buffer_name("lt-route-a", tmp_path / "other.md")

    assert same_a == same_b
    assert len({same_a, other_session, other_path}) == 3
    assert backend_mod.valid_buffer_name(same_a)
    assert ";" not in same_a and "/" not in same_a
    assert not backend_mod.valid_buffer_name("x; display-message")
    assert not backend_mod.valid_buffer_name(
        "x" * (backend_mod._BUFFER_NAME_MAX + 1)
    )
    with pytest.raises(ValueError, match="invalid session"):
        backend_mod.paste_buffer_name("lt-safe; display-message", path)
    with pytest.raises(ValueError, match="invalid session"):
        backend_mod.paste_buffer_name("lt-safe\n", path)


def test_backend_paste_buffer_cleanup_runs_when_paste_fails(monkeypatch, tmp_path):
    calls = []

    def fake_tmux(*args, check=False):
        calls.append((args, check))
        if args[0] == "paste-buffer":
            raise RuntimeError("simulated paste failure")
        return None

    task = tmp_path / "task.md"
    task.write_text("payload\n", encoding="utf-8")
    monkeypatch.setattr(backend_mod, "require_tmux", lambda: None)
    monkeypatch.setattr(backend_mod, "_tmux", fake_tmux)

    with pytest.raises(RuntimeError, match="simulated paste failure"):
        backend_mod.paste_file("lt-cleanup", str(task))

    load = next(args for args, _check in calls if args[0] == "load-buffer")
    delete = next(args for args, _check in calls if args[0] == "delete-buffer")
    assert delete == ("delete-buffer", "-b", load[2])


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux unavailable")
def test_backend_real_tmux_eight_parallel_pastes_are_session_isolated(
    monkeypatch, tmp_path
):
    """全 load を先に完了させ、default-buffer 実装なら確実に誤配信する race。"""
    count = 8
    sessions = [f"lt-buffer-race-{i}" for i in range(count)]
    files = []
    receiver = (
        "import sys,time; "
        "line=sys.stdin.readline().rstrip('\\n'); "
        "print('RECEIVED:'+line,flush=True); time.sleep(5)"
    )
    original_tmux = backend_mod._tmux
    barrier = threading.Barrier(count, timeout=10)

    try:
        for i, session in enumerate(sessions):
            task = tmp_path / f"task-{i}.md"
            task.write_text(f"PAYLOAD_{i}\n", encoding="utf-8")
            files.append(task)
            backend_mod.new_session(
                session,
                str(tmp_path),
                command_argv=(sys.executable, "-u", "-c", receiver),
            )

        def synchronized_tmux(*args, check=False):
            result = original_tmux(*args, check=check)
            if args[0] == "load-buffer":
                barrier.wait()
            return result

        monkeypatch.setattr(backend_mod, "_tmux", synchronized_tmux)
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [
                pool.submit(backend_mod.paste_file, session, str(path))
                for session, path in zip(sessions, files)
            ]
            for future in futures:
                future.result(timeout=15)

        for i, session in enumerate(sessions):
            expected = f"RECEIVED:PAYLOAD_{i}"
            captured = ""
            for _ in range(40):
                captured = backend_mod.capture_pane(session)
                if expected in captured:
                    break
                time.sleep(0.05)
            assert expected in captured, captured
            assert all(
                f"RECEIVED:PAYLOAD_{other}" not in captured
                for other in range(count)
                if other != i
            )

        listed = original_tmux("list-buffers", "-F", "#{buffer_name}")
        remaining = set(listed.stdout.splitlines()) if listed.returncode == 0 else set()
        expected_names = {
            backend_mod.paste_buffer_name(session, str(path))
            for session, path in zip(sessions, files)
        }
        assert remaining.isdisjoint(expected_names)
    finally:
        monkeypatch.setattr(backend_mod, "_tmux", original_tmux)
        for session in sessions:
            backend_mod.kill_session(session)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux unavailable")
def test_backend_real_tmux_direct_process_avoids_interactive_shell(tmp_path):
    """tmux pane が対話 shell readiness 無しで指定processを実行する。"""
    session = "lt-direct-process-fixture"
    marker = "DIRECT_PROCESS_READY"
    argv = (
        sys.executable,
        "-u",
        "-c",
        f"import time; print('{marker}', flush=True); time.sleep(5)",
    )
    try:
        backend_mod.new_session(session, str(tmp_path), command_argv=argv)
        captured = ""
        for _ in range(40):
            captured = backend_mod.capture_pane(session)
            if marker in captured:
                break
            time.sleep(0.05)
        assert marker in captured
        assert backend_mod.has_session(session)
        assert backend_mod.pane_current_command(session) not in {"", "zsh", "bash", "sh"}
    finally:
        backend_mod.kill_session(session)
