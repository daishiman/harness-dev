"""Codex 実走の実行境界。LLM/API は呼ばず、境界違反を再現する。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = (Path(__file__).resolve().parents[1] / "plugins/harness-creator/skills/"
          "run-skill-live-trial/scripts/live-trial-codex.py")


def load():
    spec = importlib.util.spec_from_file_location("codex_live_runner_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_resume_retains_sandbox_and_uses_exact_session(tmp_path):
    mod = load()
    cli = tmp_path / "codex"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    cfg = {"codex_executable": str(cli), "repo_root": str(tmp_path),
           "workdir": str(tmp_path / "evidence"), "requested_model": ""}
    sid = "01a199f1-5e57-70a1-85f3-ee877cfcfac2"
    argv = mod.codex_argv(cfg, sid)
    assert argv[-3:] == ["resume", sid, "-"]
    assert argv[:3] == [str(cli.resolve()), "--no-daemon", "exec"]
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert argv[argv.index("--add-dir") + 1] == str((tmp_path / "evidence/out").resolve())
    assert "--ignore-user-config" in argv and "--json" in argv
    assert "sandbox_workspace_write.exclude_tmpdir_env_var=true" in argv
    assert "sandbox_workspace_write.exclude_slash_tmp=true" in argv
    assert "--ephemeral" not in argv
    assert not any("dangerously" in item for item in argv)
    environment = mod.actor_environment(cfg)
    assert environment['TMPDIR'] == str(tmp_path/'.native-tmp')
    assert environment['TMPPREFIX'] == str(tmp_path/'.native-tmp/zsh')
    for name in ('HOME', 'CODEX_HOME', 'PATH', 'ZDOTDIR'):
        assert environment.get(name) == os.environ.get(name)


def test_gate_requires_current_assistant_presentation_and_real_bytes(tmp_path):
    mod = load()
    fx = tmp_path / "fixture"
    fx.mkdir()
    artifact = fx / "result.json"
    artifact.write_text('{"actual":true}\n')
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    request = {"kind": "artifact-delivery-choice", "state": "waiting_user_choice",
               "target_skill": "dev-graph:run-dev-graph-node", "invocation_id": "add-1",
               "artifacts": [{"path": str(artifact), "sha256": sha}]}
    text = f"成果物 {artifact} SHA-256 {sha}。open: cat {artifact}。accept-as-is/light/standard/detailedを選択してください。"
    assert mod.validate_choice_request(request, fixture=fx, assistant_text=text,
                                       permitted_skills={request['target_skill']}, seen_ids=set())
    with pytest.raises(ValueError, match="assistant"):
        mod.validate_choice_request(request, fixture=fx, assistant_text="成果物ができました",
                                    permitted_skills={request['target_skill']}, seen_ids=set())
    artifact.write_text('{"tampered":true}\n')
    with pytest.raises(ValueError, match="digest"):
        mod.validate_choice_request(request, fixture=fx, assistant_text=text,
                                    permitted_skills={request['target_skill']}, seen_ids=set())


def test_gate_rejects_symlink_escape_unknown_skill_and_second_answer(tmp_path):
    mod = load()
    fx = tmp_path / "fx"
    fx.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    alias = fx / "artifact.txt"
    alias.symlink_to(outside)
    sha = hashlib.sha256(outside.read_bytes()).hexdigest()
    req = {"kind": "artifact-delivery-choice", "state": "waiting_user_choice",
           "target_skill": "p:s", "invocation_id": "once",
           "artifacts": [{"path": str(alias), "sha256": sha}]}
    text = f"{alias} {sha} open accept-as-is light standard detailed"
    with pytest.raises(ValueError, match="fixture"):
        mod.validate_choice_request(req, fixture=fx, assistant_text=text,
                                    permitted_skills={"p:s"}, seen_ids=set())
    alias.unlink()
    alias.write_text("outside")
    with pytest.raises(ValueError, match="skill"):
        mod.validate_choice_request(req, fixture=fx, assistant_text=text,
                                    permitted_skills={"p:other"}, seen_ids=set())
    with pytest.raises(ValueError, match="already"):
        mod.validate_choice_request(req, fixture=fx, assistant_text=text,
                                    permitted_skills={"p:s"}, seen_ids={"once"})


def test_native_raw_children_are_bound_to_parent_and_not_path_mentions(tmp_path):
    mod = load()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    main_id = "main-test-01"
    for name, parent in [("child", main_id), ("unrelated", "other-session")]:
        (sessions / f"rollout-{name}.jsonl").write_text(json.dumps({
            "type": "session_meta", "payload": {
                "id": name, "parent_thread_id": parent,
                "source": {"subagent": {"thread_spawn": {"parent_thread_id": parent}}}}}) + "\n")
    children = mod.child_rollouts(sessions, main_id)
    assert [item.name for item in children] == ["rollout-child.jsonl"]


def test_freeze_cannot_overwrite_preexisting_evidence(tmp_path):
    mod = load()
    target = tmp_path / "snapshot.jsonl"
    target.write_text("original")
    source = tmp_path / "raw.jsonl"
    source.write_text("replacement")
    with pytest.raises(FileExistsError):
        mod.copy_once(source, target)
    assert target.read_text() == "original"


def test_process_cleanup_never_targets_an_unowned_group():
    mod = load()
    with pytest.raises(ValueError, match="ownership"):
        mod.stop_owned_process_group(None, expected_pid=os.getpid())


def test_resume_does_not_accept_latest_or_unbound_session(tmp_path):
    mod = load()
    with pytest.raises(ValueError, match="session"):
        mod.codex_argv({"codex_executable": "/bin/true", "repo_root": str(tmp_path),
                        "workdir": str(tmp_path / "evidence")}, "--last")


def test_timeout_stops_only_its_owned_process_group(tmp_path, monkeypatch):
    mod = load()
    cli = tmp_path / "fake-codex"
    cli.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    cli.chmod(0o755)
    fx, private, work = tmp_path / "fx", tmp_path / "private", tmp_path / "evidence"
    fx.mkdir(); private.mkdir(); work.mkdir()
    prompt = tmp_path / "task.md"
    prompt.write_text("fixture task")
    cfg = {"codex_executable": str(cli), "repo_root": str(fx), "private_dir": str(private),
           "workdir": str(work), "run_id": "timeout-test"}
    state = {"run_id": "timeout-test", "started_at_unix": mod.time.time(), "elapsed": 0,
             "budget": {"max_wall_clock_s": 0.1, "max_total_tokens": 100},
             "turns": [], "session_id": None, "collected": False}
    monkeypatch.setattr(mod, "verify_pin", lambda *_: None)
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"],
                                 start_new_session=True)
    try:
        result = mod.execute_turn(cfg, state, prompt)
        assert result["terminated"] == "HARD_CAP"
        assert result["returncode"] != 0
        assert "active_process" not in state
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_finalizer_refuses_to_replace_a_prior_verdict(tmp_path):
    mod = load()
    private = tmp_path / "private"
    private.mkdir()
    work = tmp_path / "evidence"
    work.mkdir()
    (private / "runner-state.json").write_text(json.dumps({"collected": True}))
    (work / "verdict.json").write_text('{"historical":"FAIL"}')
    with pytest.raises(ValueError, match="never be overwritten"):
        mod.finalize({"private_dir": str(private), "workdir": str(work)}, None, [], True)
    assert json.loads((work / "verdict.json").read_text()) == {"historical": "FAIL"}


def test_native_operation_checkpoint_cannot_reorder_or_change_arguments():
    mod = load()
    cfg = {"target_skill": "dev-graph:run-dev-graph-node", "native_operations": [
        {"id": "update", "target_skill": "dev-graph:run-dev-graph-node", "args": "update --input immutable.json"},
        {"id": "feature-reject", "target_skill": "dev-graph:run-dev-graph-node", "args": "add --input feature.json"}]}
    state = {"native_operation_turns": []}
    req = {"kind": "native-operation", "state": "waiting_operation", "operation_id": "update",
           "target_skill": cfg['target_skill'], "args": "update --input immutable.json"}
    assert mod.validate_operation_request(cfg, state, req)["id"] == "update"
    with pytest.raises(ValueError, match="order/skill/args"):
        mod.validate_operation_request(cfg, state, {**req, "args": "update --input other.json"})
    with pytest.raises(ValueError, match="order/skill/args"):
        mod.validate_operation_request(cfg, state, {**req, "operation_id": "feature-reject"})


def test_terminal_marker_does_not_replace_unsubmitted_operation(tmp_path):
    mod = load()
    (tmp_path / "out").mkdir()
    (tmp_path / "out/status.json").write_text('{"status":"PASS"}')
    cfg = {"workdir": str(tmp_path), "native_operations": [{"id": "update"}]}
    with pytest.raises(ValueError, match="before declared"):
        mod._marker(cfg, {"native_operation_turns": [{"submitted": False}]})


def test_secret_material_is_excluded_and_copy_is_explicitly_redacted():
    mod = load()
    assert mod.secret_file(Path('.env.local'))
    assert mod.secret_file(Path('.guard-key'))
    raw = b'Authorization: Bearer abcdefghijklmnopqrstuvwxyz\nfixture-secret-001'
    transformed = mod.public_bytes(raw, ['fixture-secret-001'])
    assert b'abcdefghijklmnopqrstuvwxyz' not in transformed
    assert b'fixture-secret-001' not in transformed
    assert raw.endswith(b'fixture-secret-001')  # no mutation of the original snapshot


def test_operation_read_must_be_the_expected_skill_not_another_source(tmp_path, monkeypatch):
    mod = load()
    expected = tmp_path / 'expected'
    expected.mkdir()
    source = expected / 'SKILL.md'
    source.write_text('expected skill bytes')
    other = tmp_path / 'other.md'
    other.write_text('other source')
    private = tmp_path / 'private'
    cached = private / 'live-usage-cache/transcript.jsonl'
    cached.parent.mkdir(parents=True)
    cached.write_text(json.dumps({'type':'response_item','payload':{'type':'function_call','call_id':'other-read'}})+'\n')
    inspection = {'injected_skills':[{'name':'run-expected','path':str(source),'index':0}],
                  'activations':[{'skill':'p:run-other','path':str(other),
                                  'source_sha256':hashlib.sha256(other.read_bytes()).hexdigest(),
                                  'read_call_id':'other-read'}]}
    class Parser:
        @staticmethod
        def inspect_transcript(*args, **kwargs):
            return inspection
    monkeypatch.setattr(mod, 'sibling', lambda _: Parser)
    monkeypatch.setattr(mod, 'live_usage', lambda *_: {})
    with pytest.raises(ValueError, match='pinned skill bytes'):
        mod.verify_operation_activation({'private_dir':str(private)}, {},
                                        {'target_skill':'p:run-expected','skill_dir':str(expected)},
                                        {'native_records_before':0})


def test_recursive_target_is_rejected_before_any_process_or_state(tmp_path):
    mod = load()
    cfg = {'run_id':'recursive-test','target_skill':'harness-creator:run-skill-live-trial',
           'skill_dir':str(tmp_path/'provider'),'repo_root':str(tmp_path/'fx'),
           'private_dir':str(tmp_path/'private'),'workdir':str(tmp_path/'evidence'),
           'task_file':str(tmp_path/'task.md'),'scenario_file':str(tmp_path/'scenario.json'),
           'scenario_id':'closed-budget','codex_executable':'/bin/true'}
    source = tmp_path/'config.json'
    source.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='recursive'):
        mod.load_config(source)
    assert not (tmp_path/'private').exists()


def test_controller_plan_cannot_be_changed_between_native_turns(tmp_path):
    mod = load()
    config = tmp_path/'config.json'
    config.write_text('{"operation":"old"}')
    state = {'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest()}
    config.write_text('{"operation":"changed"}')
    with pytest.raises(ValueError, match='config/operation plan drift'):
        mod.verify_pin({'_config_file':str(config)}, state)


@pytest.mark.parametrize('relative', ['../old-pass', '/private/tmp/prior-evidence'])
def test_goal_seek_root_cannot_use_external_or_prior_parent_evidence(tmp_path, relative):
    mod = load()
    fx = tmp_path/'fx'; fx.mkdir()
    provider = tmp_path/'provider'; provider.mkdir()
    cfg = {'run_id':'contained-root','target_skill':'p:run-example','skill_dir':str(provider),
           'repo_root':str(fx),'private_dir':str(tmp_path/'private'),'workdir':str(tmp_path/'evidence'),
           'task_file':str(tmp_path/'task.md'),'scenario_file':str(tmp_path/'scenario.json'),
           'scenario_id':'closed-budget','codex_executable':'/bin/true',
           'goal_seek_eval_root_relative':relative}
    source = tmp_path/'config.json'; source.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='contained fixture-relative'):
        mod.load_config(source)


def _safe_runner_config(tmp_path):
    fx = tmp_path/'fixture'; fx.mkdir()
    provider = tmp_path/'provider'; provider.mkdir()
    work = tmp_path/'public'; work.mkdir()
    return {'run_id':'scope-boundary','target_skill':'example:run-example','skill_dir':str(provider),
            'repo_root':str(fx),'private_dir':str(tmp_path/'private'),'workdir':str(work),
            'task_file':str(tmp_path/'task.md'),'scenario_file':str(tmp_path/'scenario.json'),
            'scenario_id':'closed-budget','codex_executable':sys.executable}


@pytest.mark.parametrize('key', ['private_dir', 'skill_dir', 'loaded_provider_roots',
                                 'native_operation', 'task_file', 'scenario_file', 'config_file'])
def test_source_and_controls_may_not_overlap_actor_output_root(tmp_path, key):
    mod = load()
    cfg = _safe_runner_config(tmp_path)
    out = Path(cfg['workdir'])/'out'; out.mkdir()
    protected = out/key
    source = tmp_path/'config.json'
    if key == 'loaded_provider_roots':
        protected.mkdir()
        cfg[key] = [str(protected)]
    elif key == 'native_operation':
        protected.mkdir()
        cfg['native_operations'] = [{'id':'next','target_skill':cfg['target_skill'],
                                     'args':'next','skill_dir':str(protected)}]
    elif key == 'config_file':
        source = protected
    else:
        cfg[key] = str(protected)
        if key in {'private_dir', 'skill_dir'}:
            protected.mkdir()
    source.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='actor writable'):
        mod.load_config(source)


@pytest.mark.parametrize('relation', ['ancestor', 'symlink'])
def test_readonly_provider_root_overlap_is_detected_by_realpath(tmp_path, relation):
    mod = load()
    cfg = _safe_runner_config(tmp_path)
    if relation == 'ancestor':
        cfg['loaded_provider_roots'] = [str(tmp_path)]
    else:
        out = Path(cfg['workdir'])/'out'; out.mkdir()
        alias = tmp_path/'provider-alias'; alias.symlink_to(out, target_is_directory=True)
        cfg['loaded_provider_roots'] = [str(alias)]
    source = tmp_path/'config.json'; source.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='actor writable'):
        mod.load_config(source)


def test_sibling_source_controls_and_output_root_remain_accepted(tmp_path):
    mod = load()
    cfg = _safe_runner_config(tmp_path)
    cfg['loaded_provider_roots'] = [cfg['skill_dir']]
    source = tmp_path/'config.json'; source.write_text(json.dumps(cfg))
    assert mod.load_config(source)['private_dir'] == cfg['private_dir']


def test_implicit_provider_root_does_not_expand_to_fixture_ancestor(tmp_path):
    mod = load()
    cfg = _safe_runner_config(tmp_path)
    source = tmp_path/'config.json'; source.write_text(json.dumps(cfg))
    assert mod.load_config(source)['loaded_provider_roots'] == [cfg['skill_dir']]


def test_collection_excludes_native_runtime_temp_without_deleting_private_original(tmp_path, monkeypatch):
    mod = load()
    cfg = _safe_runner_config(tmp_path)
    private = Path(cfg['private_dir']); private.mkdir()
    fx = Path(cfg['repo_root'])
    temporary = fx/'.native-tmp'; temporary.mkdir()
    original = temporary/'communication.bin'
    original.write_bytes(b'opaque-session-data-with-no-recognizable-secret-prefix')
    (fx/'durable-report.txt').write_text('business output')
    state = {'runtime':'codex','run_id':cfg['run_id'],'status':'BLOCKED','session_id':None,
             'collected':False,'turns':[],'behavior_sha256':'0'*64,
             'elapsed':1,'started_at_unix':mod.time.time()-1}
    (private/'runner-state.json').write_text(json.dumps(state))
    monkeypatch.setattr(mod, 'verify_pin', lambda *_: None)
    mod.collect(cfg)
    work = Path(cfg['workdir'])
    assert not (work/'fixture-final/.native-tmp').exists()
    assert (work/'fixture-final/durable-report.txt').read_text() == 'business output'
    assert original.read_bytes() == b'opaque-session-data-with-no-recognizable-secret-prefix'
    receipt = json.loads((work/'public-copy-receipt.json').read_text())
    assert '.native-tmp' in receipt['excluded_fixture_files']


def test_cli_exit_cleans_background_group_and_preserves_unrelated_process(tmp_path, monkeypatch):
    """Real OS processes: the CLI stand-in exits first, while its child remains."""
    mod = load()
    fx = tmp_path/'fx'; fx.mkdir()
    private = tmp_path/'private'; private.mkdir()
    work = tmp_path/'evidence'; work.mkdir()
    task = tmp_path/'task.md'; task.write_text('process lifecycle fixture only')
    child_pid_file = fx/'background.pid'
    cli = tmp_path/'cli-stand-in'
    cli.write_text(f'''#!{sys.executable}
import pathlib,subprocess,sys
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
pathlib.Path({str(child_pid_file)!r}).write_text(str(p.pid))
''')
    cli.chmod(0o755)
    cfg = {'codex_executable':str(cli),'repo_root':str(fx),'private_dir':str(private),
           'workdir':str(work),'run_id':'background-group-test'}
    state = {'run_id':cfg['run_id'],'started_at_unix':mod.time.time(),'elapsed':0,
             'budget':{'max_wall_clock_s':5,'max_total_tokens':100},'turns':[],
             'session_id':None,'collected':False}
    monkeypatch.setattr(mod, 'verify_pin', lambda *_: None)
    unrelated = subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'], start_new_session=True)
    background_pid = None
    def running(pid):
        result = subprocess.run(['ps','-p',str(pid),'-o','stat='], capture_output=True, text=True)
        state_text = result.stdout.strip()
        return bool(state_text) and not state_text.startswith('Z')
    try:
        turn = mod.execute_turn(cfg, state, task)
        background_pid = int(child_pid_file.read_text())
        deadline = mod.time.monotonic()+2
        while running(background_pid) and mod.time.monotonic()<deadline:
            mod.time.sleep(0.02)
        assert not running(background_pid), 'CLI exited but its owned background process survived'
        assert turn['returncode'] == 0  # actual CLI exit; supervisor may be SIGKILL-reaped
        assert turn['supervisor_returncode'] == -signal.SIGKILL
        assert turn['supervisor_pid'] != turn['cli_pid']
        assert turn['scoped_group_reaped'] is True
        control = json.loads(Path(turn['supervisor_status_file']).read_text())
        assert control['process_group'] == turn['supervisor_pid']
        assert control['child_returncode'] == 0
        assert unrelated.poll() is None
    finally:
        if background_pid is not None and running(background_pid):
            os.kill(background_pid, signal.SIGKILL)
        unrelated.terminate(); unrelated.wait(timeout=3)


def test_cleanup_never_signals_a_numeric_group_after_ownership_leader_exited(monkeypatch):
    mod = load()
    leader = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
    leader.wait(timeout=3)
    signals = []
    monkeypatch.setattr(mod.os, 'killpg', lambda *args: signals.append(args))
    with pytest.raises(RuntimeError, match='group ownership unavailable'):
        mod.stop_owned_process_group(leader, expected_pid=leader.pid)
    assert signals == []
