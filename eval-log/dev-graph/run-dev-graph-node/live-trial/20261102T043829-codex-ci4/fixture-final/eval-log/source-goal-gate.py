import hashlib, json, os, sys
goal = json.load(open(sys.argv[1], encoding='utf-8'))
rows = [json.loads(line) for line in open(sys.argv[2], encoding='utf-8') if line.strip()]
progress = json.load(open(sys.argv[3], encoding='utf-8'))
graph = json.load(open(sys.argv[4], encoding='utf-8'))
required_keys = {'original_goal','original_goal_hash','current_goal_snapshot','delta_from_original','merged_directive_for_next','drift_signal'}
expected = hashlib.sha256(goal['original_goal'].encode('utf-8')).hexdigest()
assert rows, 'intermediate.jsonl is empty'
for row in rows:
    assert required_keys <= row.keys(), required_keys - row.keys()
    assert row['original_goal'] == goal['original_goal']
    assert row['original_goal_hash'] == expected
digest = 'sha256:' + hashlib.sha256(json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
receipts = [json.load(open(os.path.join(sys.argv[5], p), encoding='utf-8')) for p in progress.get('writer_receipts') or []]
baseline = progress.get('graph_baseline') or {}
revisions = [baseline.get('graph_revision')] + [r.get('graph_revision_after') for r in receipts]
assert all(r.get('graph_revision_before') == before for r, before in zip(receipts, revisions)), f'writer receipts do not chain from the baseline: {[(r.get("graph_revision_before"), r.get("graph_revision_after")) for r in receipts]}'
last = (receipts[-1].get('graph_revision_after'), receipts[-1].get('graph_digest_after')) if receipts else (baseline.get('graph_revision'), baseline.get('graph_digest'))
assert last == (graph.get('graph_revision'), digest), f'graph changed after the last writer receipt or the graph baseline: {last}'
verifier = progress.get('independent_verifier') or {}
assert verifier.get('agent') in {'dev-graph-integrity-auditor', 'dev-graph:dev-graph-integrity-auditor'}, 'independent verifier not run'
assert verifier.get('verdict') in {'PASS', 'FAIL'}, verifier
assert verifier.get('graph_digest') == digest, f'verifier audited {verifier.get("graph_digest")}, not the current graph {digest}'
def entries(value):
    pairs = list(value.items() if isinstance(value, dict) else ((c.get('id'), c) for c in value))
    out = {cid: (c if isinstance(c, dict) else {'status': c}) for cid, c in pairs}
    assert len(out) == len(pairs), f'duplicate ids: {sorted(map(str, out))}'
    return out
status = {cid: c.get('status') for cid, c in entries(progress.get('feedback_criteria') or {}).items()}
assert set(status) == {'IN1', 'OUT1', 'OUT2', 'OUT3'}, sorted(map(str, status))
outer = {cid: s for cid, s in status.items() if cid != 'IN1'}
assert set(outer.values()) == {'external_pending'}, f'outer criteria are judged outside this run: {outer}'
checklist = entries(progress.get('checklist') or {})
assert set(checklist) == {'containment', 'classification', 'schema', 'package', 'receipt'}, sorted(map(str, checklist))
assert all(c.get('status') in {'achieved', 'not_achieved', 'not_applicable'} for c in checklist.values()), checklist
assert checklist['containment'].get('status') != 'not_applicable' and checklist['schema'].get('status') != 'not_applicable', 'containment and schema are never not_applicable'
assert all(str(c.get('evidence') or '').strip() for c in checklist.values() if c.get('status') == 'not_applicable'), 'not_applicable needs evidence'
na = {cid for cid, c in checklist.items() if c.get('status') == 'not_applicable'}
classified = any(r.get('operation') == 'add' and any((a.get('classification') or {}).get('decision') != 'c14_macro_contract' for a in r.get('artifacts') or []) for r in receipts)
required = {'receipt'} if receipts else set()
required |= {'package'} if any('feature_package_id' in r for r in receipts) else set()
required |= {'classification'} if classified else set()
assert not (na & required), f'not_applicable contradicts the writer receipts: {sorted(na & required)}'
assert progress.get('overall') in {'in_progress', 'blocked', 'PASS'}, progress.get('overall')
if progress['overall'] == 'PASS':
    assert verifier['verdict'] == 'PASS' and status['IN1'] == 'PASS' and all(c['status'] != 'not_achieved' for c in checklist.values()), (verifier['verdict'], status['IN1'], checklist)
