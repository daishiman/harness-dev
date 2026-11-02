"""Host選択CodexからClaude台帳へのdowngradeを拒否する。"""
import importlib.util
import json
import os
from pathlib import Path
import pytest
from completeness_test_support import AUDIT, AGGREGATE, golden_ledger, golden_report


def test_codex_process_alone_does_not_change_legacy_default(monkeypatch):
    monkeypatch.delenv('SYSTEM_SPEC_AUDIT_RUNTIME', raising=False)
    monkeypatch.setenv('CODEX_THREAD_ID', 'parent-process-is-codex')
    report = golden_report()
    assert AUDIT.select_runtime() == 'claude'
    assert AUDIT.validate_attribution(report, golden_ledger()) == []
    assert AGGREGATE.validate_report(report, golden_ledger()) == []


@pytest.mark.parametrize('tool', ['Agent', 'Task'])
def test_codex_selection_rejects_legacy_memory_ledger(monkeypatch, tool):
    monkeypatch.delenv('SYSTEM_SPEC_AUDIT_RUNTIME', raising=False)
    monkeypatch.setenv('CODEX_THREAD_ID', 'isolated-negative-review')
    report = golden_report()
    declaration = report['audit_delegations'][0]
    declaration['dispatch']['tool'] = tool
    ledger = golden_ledger()
    if tool == 'Agent':
        dispatch = declaration['dispatch']
        dispatch['tool_use_id'] = 'memory-agent-call'
        ledger['receipts_v12'] = {dispatch['session_id']: {'memory-agent-call': [{
            'subagent_type': dispatch['subagent_type'], 'tool_name': tool,
            'response_sha256': dispatch['response_sha256'], 'verdict': declaration['verdict'],
            'verdict_state': 'resolved'}]}}
    # This same memory evidence is genuinely accepted by the legacy contract.
    assert AUDIT.ledger_corroborates(declaration, ledger)[0]
    monkeypatch.setenv('SYSTEM_SPEC_AUDIT_RUNTIME', 'codex')
    assert not AUDIT.ledger_corroborates(declaration, ledger)[0]
    assert AUDIT.validate_attribution(report, ledger)
    assert AGGREGATE.validate_report(report, ledger)


def test_codex_api_selection_propagates_without_environment(monkeypatch):
    monkeypatch.delenv('SYSTEM_SPEC_AUDIT_RUNTIME', raising=False)
    report = golden_report(); ledger = golden_ledger()
    assert AGGREGATE.validate_report(report, ledger, runtime='codex')
    assert AUDIT.validate_attribution(report, ledger, runtime='codex')
    assert not AUDIT.ledger_corroborates(report['audit_delegations'][0], ledger, runtime='codex')[0]


@pytest.mark.parametrize('value', ['', 'unknown', 'Codex', ' codex ', 'auto'])
def test_explicit_invalid_runtime_fails_all_public_paths(monkeypatch, value, tmp_path):
    monkeypatch.setenv('SYSTEM_SPEC_AUDIT_RUNTIME', value)
    with pytest.raises(ValueError): AUDIT.select_runtime()
    with pytest.raises(ValueError): AUDIT.load_fork_ledger(None)
    report = golden_report(); ledger = golden_ledger()
    assert AUDIT.validate_attribution(report, ledger)
    assert AGGREGATE.validate_report(report, ledger)
    assert not AUDIT.ledger_corroborates(report['audit_delegations'][0], ledger)[0]
    assert AGGREGATE.main(['--report', str(tmp_path / 'not-read.json')]) == 2


def test_codex_cannot_override_host_runtime_to_claude(monkeypatch, tmp_path):
    monkeypatch.setenv('SYSTEM_SPEC_AUDIT_RUNTIME', 'codex')
    with pytest.raises(ValueError): AUDIT.select_runtime('claude')
    assert AGGREGATE.main(['--report', str(tmp_path / 'not-read.json'), '--runtime', 'claude']) == 2
    path = Path(AUDIT.__file__).with_name('build-resume-receipt.py')
    spec = importlib.util.spec_from_file_location('test_native_resume_runtime', path)
    resume = importlib.util.module_from_spec(spec); spec.loader.exec_module(resume)
    assert resume.main(['--repo-root', str(tmp_path), '--runtime', 'claude']) == 2


def test_codex_load_rejects_legacy_and_invalid_native_binding(monkeypatch, tmp_path):
    monkeypatch.setenv('SYSTEM_SPEC_AUDIT_RUNTIME', 'codex')
    path = tmp_path / 'ledger.jsonl'
    for record in ({'schema_version': '1.2', 'tool_name': 'Agent'},
                   {'schema_version': '2.0', 'tool_name': 'spawn_agent'}):
        path.write_text(json.dumps(record) + '\n')
        loaded = AUDIT.load_fork_ledger(path)
        assert loaded['malformed'] > 0
        assert not loaded['native_receipts']
        assert AUDIT.validate_attribution(golden_report(), loaded)
