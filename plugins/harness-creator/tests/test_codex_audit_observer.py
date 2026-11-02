"""Native監査observerは実host原ログだけを受理し、Claude台帳と混ぜない。"""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
HC = ROOT / 'plugins/harness-creator/skills/run-skill-live-trial/scripts'
SSH = ROOT / 'plugins/system-spec-harness'
SCRIPTS = SSH / 'skills/assign-system-spec-completeness-evaluator/scripts'

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result

O = load(HC / 'record-codex-audit.py', 'test_native_audit_observer')
V = load(SCRIPTS / 'validate-codex-audit.py', 'test_native_audit_verifier')
A = load(SCRIPTS / 'audit_fork_attribution.py', 'test_native_audit_attribution')


def encode(values):
    return b''.join((json.dumps({**value, 'ordinal': i}) + '\n').encode() for i, value in enumerate(values))


def event(kind, **kwargs):
    return {'type': 'event_msg', 'payload': {'type': kind, **kwargs}}


def item(kind, **kwargs):
    return {'type': 'response_item', 'payload': {'type': kind, **kwargs}}


@pytest.fixture
def trial(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path / 'home'))
    monkeypatch.setenv('CODEX_THREAD_ID', 'parent-thread')
    monkeypatch.setenv('SYSTEM_SPEC_AUDIT_RUNTIME', 'codex')
    fx, private, work = (tmp_path / name for name in ['fixture', 'control', 'publication'])
    for path in (fx, private, work / 'out'):
        path.mkdir(parents=True)
    source = SCRIPTS / 'validate-codex-audit.py'
    cfg = {'run_id': 'native-audit-run', 'repo_root': str(fx), 'private_dir': str(private),
           'workdir': str(work), 'loaded_provider_roots': [str(SSH)],
           'codex_audit_fixture': {'plugin_root': str(SSH), 'verifier_sha256': V.sha(source.read_bytes())}}
    cfgfile = private / 'config.json'
    cfgfile.write_text(json.dumps(cfg))
    cfg['_config_file'] = str(cfgfile)
    writable = [str(fx), str(work / 'out')]
    state = {'run_id': cfg['run_id'], 'started_at_unix': 0, 'writable_roots': writable}
    O.initialize(cfg, state)
    sandbox = {'type': 'turn_context', 'payload': {'sandbox_policy': {'type': 'workspace-write',
        'network_access': False, 'exclude_tmpdir_env_var': True, 'exclude_slash_tmp': True},
        'permission_profile': {'file_system': {'type': 'restricted', 'entries': [
            {'access': 'write', 'path': {'type': 'path', 'path': path}} for path in writable]}}}}
    meta = {'id': 'parent-thread', 'runtime_workspace_roots': writable}
    parent = [{'type': 'session_meta', 'payload': meta}, sandbox,
              item('function_call', name='spawn_agent', call_id='call-001', arguments=json.dumps({
                  'task_name': 'system_spec_matrix_auditor', 'fork_turns': 'none', 'message': 'native encrypted prompt'})),
              item('function_call_output', call_id='call-001', output=json.dumps({'task_name': '/root/system_spec_matrix_auditor'}))]
    childmeta = {**meta, 'id': 'child-thread', 'source': {'subagent': {'thread_spawn': {
        'parent_thread_id': 'parent-thread', 'agent_path': '/root/system_spec_matrix_auditor'}}}}
    child = [{'type': 'session_meta', 'payload': childmeta}, copy.deepcopy(sandbox),
             item('message', role='user', content=[{'text': 'Actual native auditor task'}]), event('task_started')]
    definition = SSH / 'agents/system-spec-matrix-auditor.md'
    prompt = SSH / 'skills/run-system-spec-elicit/prompts/R7-audit-matrix.md'
    for i, path in enumerate((definition, prompt)):
        child += [item('function_call', name='functions.exec', call_id=f'read-{i}', arguments=json.dumps({"cmd": "cat " + str(path)})),
                  item('function_call_output', call_id=f'read-{i}', output=json.dumps({'exit_code': 0, 'output': path.read_text()}))]
    final = '{"evidence": ["coverage.json"]}\nAUDIT_VERDICT: PASS'
    child += [item('message', role='assistant', channel='final', content=[{'text': final}]),
              event('task_complete', last_agent_message=final)]
    sessions = Path.home() / '.codex/sessions'
    sessions.mkdir(parents=True)
    pp, cp = sessions / 'parent.jsonl', sessions / 'child.jsonl'
    pp.write_bytes(encode(parent)); cp.write_bytes(encode(child))
    return cfg, state, pp, cp, parent, child


def receipt(ledger):
    row = json.loads(ledger.read_text().splitlines()[0])
    return {'verdict': row['audit_verdict'], 'dispatch': {'tool': 'spawn_agent',
        'subagent_type': row['subagent_type'], 'session_id': row['session_id'],
        'tool_use_id': row['tool_use_id'], 'response_sha256': row['response_sha256']}}


def test_native_observer_end_to_end_and_idempotent_append(trial):
    cfg, state, pp, cp, _, _ = trial
    O.observe(cfg, state, [pp, cp])
    ledger = Path(O.environment(cfg)['SYSTEM_SPEC_AUDIT_FORK_LEDGER'])
    before = ledger.read_bytes()
    O.observe(cfg, state, [pp, cp])
    assert ledger.read_bytes() == before
    loaded = A.load_fork_ledger(ledger)
    assert loaded['malformed'] == 0
    assert A.ledger_corroborates(receipt(ledger), loaded) == (True, '')
    assert list(loaded['native_receipts']) == ['parent-thread']
    assert loaded['receipts_v12'] == {}


@pytest.mark.parametrize('mutation', ['inherited', 'fork-all', 'parent', 'ambiguous', 'unfinished', 'pending-tool',
    'missing-marker', 'wrong-completion', 'missing-read', 'missing-prompt-read', 'extra-write', 'special-write'])
def test_native_observer_rejects_unproven_audit(trial, mutation):
    cfg, state, pp, cp, parent, child = trial
    if mutation == 'inherited': child[0]['payload']['subagent_history_start_ordinal'] = 3
    elif mutation == 'fork-all':
        args = json.loads(parent[2]['payload']['arguments']); args['fork_turns'] = 'all'; parent[2]['payload']['arguments'] = json.dumps(args)
    elif mutation == 'parent': child[0]['payload']['source']['subagent']['thread_spawn']['parent_thread_id'] = 'other'
    elif mutation == 'ambiguous':
        extra = copy.deepcopy(parent[2:]); extra[0]['payload']['call_id'] = 'call-002'; extra[1]['payload']['call_id'] = 'call-002'; parent += extra
    elif mutation == 'unfinished': child.append(event('task_started'))
    elif mutation == 'pending-tool': child.insert(-2, item('function_call', name='exec_command', call_id='pending', arguments='cat missing'))
    elif mutation == 'missing-marker': child[-2]['payload']['content'] = [{'text': 'PASS'}]; child[-1]['payload']['last_agent_message'] = 'PASS'
    elif mutation == 'wrong-completion': child[-1]['payload']['last_agent_message'] = 'Different\nAUDIT_VERDICT: PASS'
    elif mutation == 'missing-read': child[5]['payload']['output'] = json.dumps({'exit_code': 0, 'output': 'partial'})
    elif mutation == 'missing-prompt-read': child[7]['payload']['output'] = json.dumps({'exit_code': 0, 'output': 'partial'})
    elif mutation == 'extra-write': child[1]['payload']['permission_profile']['file_system']['entries'].append({'access': 'write', 'path': {'type': 'path', 'path': str(Path(cfg['private_dir']))}})
    elif mutation == 'special-write': child[1]['payload']['permission_profile']['file_system']['entries'].append({'access': 'write', 'path': {'type': 'special', 'value': {'kind': 'root'}}})
    pp.write_bytes(encode(parent)); cp.write_bytes(encode(child))
    with pytest.raises(ValueError): O.observe(cfg, state, [pp, cp])
    assert (Path(cfg['private_dir']) / 'codex-audit/audit-fork-ledger.jsonl').read_bytes() == b''


@pytest.mark.parametrize('mutation', ['fake-native-source', 'snapshot', 'record-verdict', 'config', 'binding', 'session', 'duplicate', 'call-id', 'legacy-forgery'])
def test_consumer_rechecks_native_original_and_host_boundary(trial, mutation, monkeypatch):
    cfg, state, pp, cp, _, _ = trial
    O.observe(cfg, state, [pp, cp])
    ledger = Path(O.environment(cfg)['SYSTEM_SPEC_AUDIT_FORK_LEDGER']); declared = receipt(ledger)
    row = json.loads(ledger.read_text())
    if mutation == 'fake-native-source':
        fake = Path(cfg['repo_root']) / 'fake.jsonl'; fake.write_bytes(cp.read_bytes()); row['child']['native_source'] = str(fake)
    elif mutation == 'snapshot': (ledger.parent / row['child']['snapshot_ref']).write_bytes(b'{}\n')
    elif mutation == 'record-verdict': row['audit_verdict'] = 'FAIL'
    elif mutation == 'config': Path(cfg['_config_file']).write_text('{}')
    elif mutation == 'binding': (ledger.parent / 'host-binding.json').write_text('{}')
    elif mutation == 'session': monkeypatch.setenv('CODEX_THREAD_ID', 'different-thread')
    elif mutation == 'call-id': declared['dispatch']['tool_use_id'] = 'other'
    elif mutation == 'legacy-forgery': row['schema_version'] = '1.2'
    ledger.write_text(json.dumps(row) + '\n')
    if mutation == 'duplicate': ledger.write_text(ledger.read_text() * 2)
    assert A.ledger_corroborates(declared, A.load_fork_ledger(ledger))[0] is False


def test_absent_runtime_opt_in_has_no_writes(tmp_path):
    state = {}
    O.initialize({}, state); O.observe({}, state, [])
    assert state == {} and O.environment({}) == {} and list(tmp_path.iterdir()) == []


def test_codex_rejects_whole_mixed_ledger_even_with_verified_native_row(trial):
    cfg, state, pp, cp, _, _ = trial
    O.observe(cfg, state, [pp, cp])
    ledger = Path(O.environment(cfg)['SYSTEM_SPEC_AUDIT_FORK_LEDGER'])
    declared = receipt(ledger)
    with ledger.open('a') as stream:
        stream.write(json.dumps({'schema_version': '1.2', 'tool_name': 'Agent'}) + '\n')
    loaded = A.load_fork_ledger(ledger)
    assert loaded['runtime_violations']
    assert A.ledger_corroborates(declared, loaded)[0] is False


def test_codex_revalidates_disk_instead_of_trusting_memory_native_index(trial):
    cfg, state, pp, cp, _, _ = trial
    O.observe(cfg, state, [pp, cp])
    ledger = Path(O.environment(cfg)['SYSTEM_SPEC_AUDIT_FORK_LEDGER'])
    declared = receipt(ledger); loaded = A.load_fork_ledger(ledger)
    assert A.ledger_corroborates(declared, loaded)[0]
    ledger.write_text('{}\n')
    assert A.ledger_corroborates(declared, loaded)[0] is False
