import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix')
OUT = Path('/tmp/pr86-c19-content-review')
FIX = OUT / 'synthetic'
FIX.mkdir(exist_ok=True)
env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_PROJECT_DIR'}
resolver = W / 'plugins/dev-graph/scripts/resolve-repo-context.py'
helper = W / 'plugins/dev-graph/skills/run-dev-graph-system-spec/scripts/prepare-evaluation.py'

def run(argv, cwd=FIX):
    p = subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)
    return {'rc': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}

root = FIX / "caller repo's 日本語"
root.mkdir(exist_ok=True)
root = root.resolve()
assert run(['git', 'init', '-q', '-b', 'main', str(root)])['rc'] == 0
assert run(['git', '-C', str(root), '-c', 'user.name=fixture', '-c',
            'user.email=fixture@example.invalid', 'commit', '-q', '--allow-empty', '-m', 'fixture'])['rc'] == 0
(root / 'system-spec').mkdir(exist_ok=True)
chapter = root / 'system-spec/index.md'
chapter.write_text('# before\n', encoding='utf-8')
receipt = FIX / 'receipt.json'
c24 = run([sys.executable, '-B', str(resolver), '--repo-root', str(root), '--mode', 'write'])
assert c24['rc'] == 0, c24
receipt.write_text(c24['stdout'])
command = [sys.executable, '-B', str(helper), '--context-receipt', str(receipt), '--output', 'eval-log/result.json']
foreign = FIX / 'foreign'
(foreign / 'system-spec').mkdir(parents=True, exist_ok=True)
foreign = foreign.resolve()
(foreign / 'system-spec/index.md').write_text('# foreign\n')
caller = run(command, root)
fork = run(command, foreign)
assert caller['rc'] == fork['rc'] == 0, (caller, fork)
assert json.loads(caller['stdout']) == json.loads(fork['stdout'])
prepared = json.loads(fork['stdout'])
assert shlex.split(prepared['skill_args']) == ['--spec-dir', str(root / 'system-spec'), '--output', str(root / 'eval-log/result.json')]
results = {'fixture_only': True, 'c24': c24, 'helper_caller': caller, 'helper_foreign_cwd': fork}

for name, report in [('absolute_output', str(FIX / 'outside.json')), ('parent_output', 'eval-log/../outside.json')]:
    results[name] = run(command[:-1] + [report], foreign)
    assert results[name]['rc'] != 0

doc = json.loads(receipt.read_text())
doc['content_roots']['system_spec'] = str(foreign / 'system-spec')
external_receipt = FIX / 'external-receipt.json'
external_receipt.write_text(json.dumps(doc))
results['external_receipt_root'] = run([sys.executable, '-B', str(helper), '--context-receipt', str(external_receipt), '--output', 'eval-log/result.json'])
assert results['external_receipt_root']['rc'] != 0

config_dir = root / '.dev-graph'
config_dir.mkdir(exist_ok=True)
config = config_dir / 'config.json'
config.write_text(json.dumps({'content_roots': {'system_spec': '../foreign/system-spec'}}))
results['external_config_root'] = run([sys.executable, '-B', str(resolver), '--repo-root', str(root), '--mode', 'write'])
assert results['external_config_root']['rc'] != 0
config.unlink()

# C02 の実関数を読取り専用で呼び、受入境界だけを検証する。
# この最小reportは本物のevaluator出力でも監査証跡でもない。
sys.path.insert(0, str(W / 'plugins/dev-graph/scripts'))
spec = importlib.util.spec_from_file_location('c19_probe_c02', W / 'plugins/dev-graph/scripts/build-graph-node.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
(root / 'eval-log').mkdir(exist_ok=True)
report_path = root / 'eval-log/result.json'
old_digest = hashlib.sha256(chapter.read_bytes()).hexdigest()
report = {'verdict': 'PASS', 'spec_dir': str(chapter.parent), 'artifact_snapshot': {'artifacts': {'system-spec/index.md': old_digest}}}
report_path.write_text(json.dumps(report))
lineage = {'origin_kind': 'system-spec-harness', 'source_path': 'system-spec/index.md', 'source_digest': old_digest}
evidence = {'evaluator': module.SPEC_EVALUATOR, 'evidence_ref': 'eval-log/result.json', 'evaluated_digest': old_digest}
results['c02_absolute_spec_dir'] = module._spec_confirmation(evidence, 'specification', lineage, root, 'fixture')
report['spec_dir'] = str(foreign / 'system-spec')
report_path.write_text(json.dumps(report))
try:
    module._spec_confirmation(evidence, 'specification', lineage, root, 'fixture')
    raise AssertionError('foreign spec_dir accepted')
except module.WriterError as error:
    results['c02_foreign_spec_dir_rejected'] = str(error)
report['spec_dir'] = str(chapter.parent)
report_path.write_text(json.dumps(report))
chapter.write_text('# after changed since evaluator\n')
new_digest = hashlib.sha256(chapter.read_bytes()).hexdigest()
lineage['source_digest'] = new_digest
evidence['evaluated_digest'] = new_digest
results['c02_existing_snapshot_gap'] = {'before': old_digest, 'after': new_digest,
    'accepted': module._spec_confirmation(evidence, 'specification', lineage, root, 'fixture'),
    'scope': '既存C02関数の単独受入。正規evaluator/aggregateを実行したとの主張はしない。'}
(OUT / 'boundary-probe-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(json.dumps({'checks': len(results), 'status': 'PASS', 'existing_c02_snapshot_gap': True}, ensure_ascii=False))
