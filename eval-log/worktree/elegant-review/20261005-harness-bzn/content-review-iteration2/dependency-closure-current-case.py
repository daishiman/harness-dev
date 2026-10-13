#!/usr/bin/env python3
"""Independent positive verification of the current F-4001 declarations."""
import ast
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[5]
RUN = ROOT / 'eval-log/worktree/elegant-review/20261005-harness-bzn'
before = json.loads((RUN / 'content-review/dependency-pre-ref-skills.json').read_text())
script = ROOT / 'plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py'
spec = importlib.util.spec_from_file_location('independent_current_dependency', script)
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)
common = ROOT / 'plugins/dev-graph/scripts/_common.py'
records = {}
copy_paths = {ROOT / 'plugins/dev-graph/references/package-contract.json'}
for name, previous in before.items():
    skill = ROOT / 'plugins/dev-graph/skills' / name
    current_text = (skill / 'SKILL.md').read_text()
    expected = previous['text'].replace('script_refs: [', 'script_refs: [../../scripts/_common.py, ', 1)
    assert current_text == expected, f'{name}: unexpected change beyond one dependency declaration'
    fm = yaml.safe_load(current_text.split('---', 2)[1])
    previous_fm = yaml.safe_load(previous['text'].split('---', 2)[1])
    assert fm['script_refs'] == ['../../scripts/_common.py'] + previous_fm['script_refs']
    assert {k:v for k,v in fm.items() if k != 'script_refs'} == {k:v for k,v in previous_fm.items() if k != 'script_refs'}
    callers = []
    for ref in fm['script_refs'][1:]:
        path = (skill / ref).resolve()
        tree = ast.parse(path.read_text())
        imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == '_common']
        if imports:
            callers.append({'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'common_imports':[alias.name for n in imports for alias in n.names]})
    assert callers, f'{name}: proposed ref has no actual caller'
    files = closure.behavior_closure_files(skill)
    assert sum(path == common for _,path in files) == 1, f'{name}: helper not uniquely declared'
    copy_paths.update(path for _,path in files)
    records[name] = {'skill_md_sha256':hashlib.sha256((skill/'SKILL.md').read_bytes()).hexdigest(),
                     'body_and_other_frontmatter_unchanged':True, 'actual_common_callers':callers,
                     'helper_present_once':True, 'current_behavior_sha256':closure.skill_dir_tree_sha(skill)}
with tempfile.TemporaryDirectory(prefix='independent-current-common-') as td:
    copied = Path(td)
    for source in copy_paths:
        destination = copied / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    baseline = {name:closure.skill_dir_tree_sha(copied/'plugins/dev-graph/skills'/name) for name in records}
    assert baseline == {name:r['current_behavior_sha256'] for name,r in records.items()}
    copied_common = copied/'plugins/dev-graph/scripts/_common.py'
    helper_text = copied_common.read_text()
    mutated = helper_text.replace('return (json.dumps(', 'return ("CORRUPTED:" + json.dumps(', 1)
    assert mutated != helper_text
    copied_common.write_text(mutated)
    for name in records:
        after = closure.skill_dir_tree_sha(copied/'plugins/dev-graph/skills'/name)
        assert after != baseline[name], name
        records[name]['semantic_helper_mutation_invalidates'] = True
        records[name]['mutated_behavior_sha256'] = after
    copied_common.unlink()
    for name in records:
        try:
            closure.skill_dir_tree_sha(copied/'plugins/dev-graph/skills'/name)
        except ValueError as exc:
            assert 'missing' in str(exc), str(exc)
            records[name]['missing_helper_fails_closed'] = True
        else:
            raise AssertionError(f'{name}: missing helper was accepted')
print(json.dumps({'case':'current_all_nine_shared_helper_declarations', 'finding_id':'F-4001',
                  'result':'PASS', 'skills':records, 'common_sha256':hashlib.sha256(common.read_bytes()).hexdigest(),
                  'closure_script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
                  'proof_scope':'Current declarations, actual direct import sources, behavior closure invalidation, missing-file refusal and exact one-ref diff; no host live execution accepted.',
                  'source_edits':False, 'temporary_copy_only':True}, ensure_ascii=False, indent=2))
