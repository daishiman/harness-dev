#!/usr/bin/env python3
"""Independent copy-only proof for the newly shared dev-graph dependency."""
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT / 'plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py'
spec = importlib.util.spec_from_file_location('independent_behavior_closure', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
skills = [
    'run-dev-graph-decompose', 'run-dev-graph-init', 'run-dev-graph-node',
    'run-dev-graph-render', 'run-dev-graph-requirements', 'run-dev-graph-schedule',
    'run-dev-graph-status', 'run-dev-graph-sync', 'run-dev-graph-system-spec',
]

def skill_dir(root, name):
    return root / 'plugins/dev-graph/skills' / name

def digests(root):
    return {name: module.skill_dir_tree_sha(skill_dir(root, name)) for name in skills}

def add_declared_common(root, names):
    for name in names:
        md = skill_dir(root, name) / 'SKILL.md'
        text = md.read_text()
        lines = text.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith('script_refs: ['):
                lines[index] = line.replace('script_refs: [', 'script_refs: [../../scripts/_common.py, ', 1)
                break
        else:
            raise AssertionError(f'inline refs not found: {name}')
        md.write_text(''.join(lines))

with tempfile.TemporaryDirectory(prefix='independent-common-dependency-') as td:
    copied = Path(td)
    paths = {ROOT / 'plugins/dev-graph/references/package-contract.json',
             ROOT / 'plugins/dev-graph/scripts/_common.py'}
    for name in skills:
        paths.update(path for label, path in module.behavior_closure_files(skill_dir(ROOT, name)))
    for source in paths:
        destination = copied / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    current = digests(ROOT)
    before = digests(copied)
    assert before == current, 'copy failed to preserve current behavior closure'
    common = copied / 'plugins/dev-graph/scripts/_common.py'
    original = common.read_text()
    # A semantic replacement confined to the copy; no current source is edited.
    mutated = original.replace('return (json.dumps(', 'return ("CORRUPTED:" + json.dumps(', 1)
    assert mutated != original, 'mutation must alter executable helper body'
    common.write_text(mutated)
    undeclared_after = digests(copied)
    assert undeclared_after == before, 'expected current missed invalidation reproduced'
    common.write_text(original)
    three = ['run-dev-graph-init', 'run-dev-graph-node', 'run-dev-graph-sync']
    add_declared_common(copied, three)
    three_before = digests(copied)
    common.write_text(mutated)
    three_after = digests(copied)
    three_changed = [n for n in skills if three_before[n] != three_after[n]]
    assert three_changed == three, three_changed
    common.write_text(original)
    add_declared_common(copied, [n for n in skills if n not in three])
    all_before = digests(copied)
    common.write_text(mutated)
    all_after = digests(copied)
    all_changed = [n for n in skills if all_before[n] != all_after[n]]
    assert all_changed == skills, all_changed
    print(json.dumps({
        'case': 'shared_dependency_requires_complete_declarations',
        'result': 'PASS_REPRODUCED_SOURCE_C4_FAILURE',
        'current_digest_unchanged_after_semantic_common_mutation': skills,
        'three_declarations_detect_mutation': three_changed,
        'three_declarations_still_miss_mutation': [n for n in skills if n not in three_changed],
        'all_nine_declarations_detect_mutation': all_changed,
        'minimal_recommended_fix': 'Add ../../scripts/_common.py to the existing script_refs of all nine consuming skills.',
        'scope': 'Current closure implementation unchanged; only copied source and copied declarations mutated.',
        'original_source_edits': False,
        'source': str(SOURCE),
        'current_behavior_digests': current,
    }, ensure_ascii=False, indent=2))
