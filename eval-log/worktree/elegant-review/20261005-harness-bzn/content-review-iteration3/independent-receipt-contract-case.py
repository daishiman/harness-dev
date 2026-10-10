#!/usr/bin/env python3
"""Independent adversarial verification of failure reporting and acceptance separation."""
import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import tempfile
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[5]
RUN = ROOT / 'eval-log/worktree/elegant-review/20261005-harness-bzn'
SCHEMA = ROOT / 'plugins/dev-graph/schemas/criteria-scenario-verdict.schema.json'
TEST = ROOT / 'plugins/dev-graph/tests/test_skill_criteria_evidence.py'
schema = json.loads(SCHEMA.read_text())
jsonschema.Draft202012Validator.check_schema(schema)
validator = jsonschema.Draft202012Validator(schema)
records = []

def receipt(statuses, verdict):
    return {
        'schema_version': '1.1.0',
        'target': {'plugin': 'dev-graph', 'skill': 'independent-probe',
                   'component_id': 'C01', 'skill_md_sha256': 'a' * 64},
        'verdict': verdict, 'reviewer': '/root/independent_review',
        'loop_scope': 'both', 'iteration_limit': 3,
        'criteria_results': {
            key: {'status': status, 'verify_by': 'test', 'evidence_kind': 'pytest',
                  'test_refs': ['isolated-independent-probe'],
                  'observed': 'Synthetic representation probe, not skill acceptance.'}
            for key, status in zip(('IN2', 'OUT1', 'OUT9'), statuses)
        }
    }

def check(name, value, expected):
    errors = list(validator.iter_errors(value))
    valid = not errors
    assert valid == expected, (name, valid, expected, [e.message for e in errors])
    records.append({'case': name, 'schema_valid': valid, 'expected': expected,
                    'error_paths': [list(e.absolute_path) for e in errors]})

for statuses in itertools.product(('PASS', 'FAIL'), repeat=3):
    for verdict in ('PASS', 'FAIL'):
        check('three-criteria-' + '-'.join(statuses) + '-root-' + verdict,
              receipt(statuses, verdict),
              (verdict == 'PASS') == all(s == 'PASS' for s in statuses))
for bad in ('UNKNOWN', 'ERROR', None, 1, True):
    check('unknown-root-' + repr(bad), receipt(('PASS', 'FAIL', 'PASS'), bad), False)
    check('unknown-criterion-' + repr(bad), receipt(('PASS', bad, 'FAIL'), 'FAIL'), False)

for status, has_ref in itertools.product(('PASS', 'FAIL'), (False, True)):
    value = receipt((status,), status)
    criterion = value['criteria_results']['IN2']
    criterion.update(verify_by='live-trial', evidence_kind='live-trial',
                     scenario_id='planned-synthetic-independent-probe')
    if has_ref:
        criterion['live_trial_verdict_ref'] = 'synthetic-attempted-verdict.json'
    check('live-' + status + '-ref-' + str(has_ref), value, status == 'FAIL' or has_ref)
value = receipt(('FAIL',), 'FAIL')
value['criteria_results']['IN2']['live_trial_verdict_ref'] = 'not-allowed-for-test.json'
check('nonlive-forbids-live-ref', value, False)
value = receipt(('FAIL',), 'FAIL')
value['criteria_results']['IN2']['scenario_id'] = 'not-allowed-for-test'
check('nonlive-forbids-scenario', value, False)
value = receipt(('FAIL',), 'FAIL')
value['criteria_results']['IN2'].update(verify_by='live-trial', evidence_kind='pytest',
                                     scenario_id='planned')
check('live-cannot-relabel-evidence-kind', value, False)

before_tree = ast.parse((RUN / 'test_skill_criteria_evidence.before-iteration3.py').read_text())
after_tree = ast.parse(TEST.read_text())
functions = lambda tree: {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
before, after = functions(before_tree), functions(after_tree)
name = 'test_independent_scenario_receipt_covers_exact_criteria'
assert ast.dump(before[name]) == ast.dump(after[name]), 'acceptance function was changed'

spec = importlib.util.spec_from_file_location('independent_receipt_acceptance_probe', TEST)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
component_id, skill_name, skill_path, criteria_ids = module._targets()[0]
metadata = yaml.safe_load(skill_path.read_text().split('---', 2)[1])
criteria = {c['id']: c for c in metadata['feedback_contract']['criteria']}
value = receipt(('FAIL',), 'FAIL')
value['target'] = {'plugin': 'dev-graph', 'skill': skill_name, 'component_id': component_id,
                   'skill_md_sha256': hashlib.sha256(skill_path.read_bytes()).hexdigest()}
template = value['criteria_results']['IN2']
value['criteria_results'] = {}
for key in criteria_ids:
    criterion = copy.deepcopy(template)
    criterion['verify_by'] = criteria[key]['verify_by']
    if criterion['verify_by'] == 'live-trial':
        criterion.update(evidence_kind='live-trial', scenario_id='planned-independent-fail-probe')
    value['criteria_results'][key] = criterion
validator.validate(value)
with tempfile.TemporaryDirectory(prefix='independent-acceptance-fail-') as td:
    temp = Path(td)
    path = temp / 'eval-log/dev-graph' / skill_name / 'criteria-test/scenario-verdict.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value))
    module.REPO = temp
    try:
        module.test_independent_scenario_receipt_covers_exact_criteria(
            component_id, skill_name, skill_path, criteria_ids)
    except AssertionError as exc:
        tb = exc.__traceback__
        while tb.tb_next:
            tb = tb.tb_next
        assert tb.tb_frame.f_code.co_name == name
        line = TEST.read_text().splitlines()[tb.tb_lineno - 1]
        assert 'receipt["verdict"] == "PASS"' in line, line
        acceptance_rejection = {'rejected': True, 'source_line': tb.tb_lineno, 'assertion': line.strip()}
    else:
        raise AssertionError('FAIL representation bypassed real acceptance gate')

node_review = json.loads((ROOT / 'eval-log/dev-graph/run-dev-graph-node/content-review/elegance-verdict.json').read_text())
assert node_review['feedback_loop']['iteration_limit'] == 3
assert 'CONTENT_REVIEW_ITERATION_LIMIT' not in TEST.read_text()
historical = RUN / 'historical-content-review-iteration2'
manifest = json.loads((historical / 'manifest.json').read_text())
node_old = []
for row in manifest:
    archive = ROOT / row['archive']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == row['sha256'], row['archive']
    if '/run-dev-graph-node/' in row['archive']:
        data = json.loads(archive.read_text())
        assert data['feedback_loop']['iteration_limit'] == 5
        node_old.append({'path': str(archive), 'sha256': row['sha256'], 'historical_limit': 5})
assert len(node_old) == 2

closure_script = ROOT / 'plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py'
spec = importlib.util.spec_from_file_location('independent_cycle3_closure_probe', closure_script)
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)
snap = json.loads((RUN / 'phase3-test-contract-iteration3-before.json').read_text())
fingerprints = []
for previous in snap['actual_behavior_fingerprints']:
    actual = closure.skill_dir_tree_sha(Path(previous['skill_dir']))
    assert actual == previous['behavior_sha256'], previous['skill']
    fingerprints.append({'skill': previous['skill'], 'behavior_sha256': actual, 'unchanged': True})

print(json.dumps({'result': 'PASS', 'findings': ['F-4003', 'F-4004'],
                  'schema_sha256': hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
                  'test_sha256': hashlib.sha256(TEST.read_bytes()).hexdigest(),
                  'schema_cases': records, 'case_count': len(records),
                  'acceptance_function_AST_unchanged': True,
                  'actual_acceptance_rejects_schema_valid_FAIL': acceptance_rejection,
                  'current_node_limit': 3, 'historical_node_limit5_exact_bytes': node_old,
                  'behavior_fingerprints': fingerprints,
                  'source_edits': False, 'execution_scope': 'Synthetic tmp receipts and actual schema/acceptance function only; no live acceptance claimed.'},
                 ensure_ascii=False, indent=2))
