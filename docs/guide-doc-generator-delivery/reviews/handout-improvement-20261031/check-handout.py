"""C09 handout-verify の宣言を読み、今回の資料へ4ゲートを実行する。"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
PLUGIN = ROOT / 'plugins/guide-doc-generator'
SOURCE = Path(json.loads((WORK / 'source.json').read_text())['source_dir'])
config = WORK / 'normalized-config.json'
html = WORK / 'handout.html'
reports = WORK / 'gates'
reports.mkdir(exist_ok=True)
command = (PLUGIN / 'commands/handout-verify.md').read_text()
contract = json.loads(re.search(r'```json\n(.*?)\n```', command, re.S)[1])
schema = json.loads((PLUGIN / 'schemas/handout-config.schema.json').read_text())
cfg = json.loads(config.read_text())
validation = subprocess.run([sys.executable, str(PLUGIN / 'scripts/validate-handout-config.py'), '--config', str(config)], capture_output=True, text=True)
(reports / 'config-validation.log').write_text(validation.stdout + validation.stderr)
normalized = validation.returncode == 0 and cfg.get('provenance', {}).get('normalized_by') == schema['$defs']['provenance']['properties']['normalized_by']['const']
gates = []
for gate_id, script, needs_config in [
    ('selfcontained', 'verify-handout-selfcontained.py', False),
    ('a11y-print', 'verify-handout-a11y-print.py', False),
    ('language', 'verify-handout-language.py', True),
    ('narrative', 'verify-handout-narrative.py', True),
]:
    argv = [sys.executable, str(PLUGIN / 'scripts' / script), '--html', str(html), '--json-report', str(reports / (gate_id + '.json'))]
    if needs_config:
        argv += ['--config', str(config)]
    if gate_id == 'language':
        argv += ['--out-dir', str(SOURCE)]
    if needs_config and not normalized:
        gates.append({'gate_id': gate_id, 'state': 'not-run', 'reason': 'config-not-normalized'})
        continue
    result = subprocess.run(argv, capture_output=True, text=True)
    (reports / (gate_id + '.log')).write_text(result.stdout + result.stderr)
    state = {0: 'pass', 1: 'fail', 2: 'error'}.get(result.returncode, 'error')
    gates.append({'gate_id': gate_id, 'state': state, 'exit_code': result.returncode, 'argv': argv, 'report_path': str(reports / (gate_id + '.json'))})
    print(gate_id, state, flush=True)
states = {g['state'] for g in gates}
for rule in contract['verdict_table']:
    condition = rule['when']
    matches = bool(states.intersection(condition['any_state'])) if 'any_state' in condition else (False if 'only_used' in condition else states.issubset(condition['all_states']))
    if matches:
        verdict = rule['verdict']
        break
summary = {'contract': contract['id'], 'html_sha256': hashlib.sha256(html.read_bytes()).hexdigest(), 'verdict': verdict, 'gates': gates}
(reports / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print('verdict:', verdict, flush=True)
sys.exit(0 if verdict == 'pass' else 1)
