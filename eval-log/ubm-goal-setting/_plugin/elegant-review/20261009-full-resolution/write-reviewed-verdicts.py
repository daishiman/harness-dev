#!/usr/bin/env python3
"""Project independent verdicts only after verifying their reviewed source hashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from jsonschema import Draft7Validator, FormatChecker
import yaml


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def project(root, artifacts, apply=False, allow_nonpassing=False):
    root = root.resolve()
    schema_path = root / 'plugins/harness-creator/skills/run-build-skill/schemas/content-review-verdict.schema.json'
    validator = Draft7Validator(json.loads(schema_path.read_text()), format_checker=FormatChecker())
    payloads = {}
    checked = {}
    for artifact in artifacts:
        review = json.loads(artifact.read_text())
        hashes = {}
        # Include only current reviewed inventories, never historical/baseline hashes.
        current = review.get('current_source', {})
        hashes.update(current.get('source_sha256', {}))
        hashes.update(current.get('hashes', {}))
        for key in ('dependency_sha256', 'source_sha256'):
            if isinstance(review.get(key), dict):
                hashes.update(review[key])
        for target in review.get('targets', []):
            for key in ('reference_file_sha256', 'behavior_related_file_sha256', 'dependency_sha256', 'source_sha256'):
                inventory = target.get(key, {})
                if isinstance(inventory, dict):
                    hashes.update(inventory)
        if not hashes:
            raise ValueError(f'{artifact}: missing current dependency/source hash inventory')
        for relative, expected in hashes.items():
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file() or digest(path) != expected.removeprefix('sha256:'):
                raise ValueError(f'{artifact}: reviewed dependency changed: {relative}')
            checked[relative] = expected
        for value in walk(review):
            if not {'target', 'review_kind', 'verdict', 'feedback_loop'} <= value.keys():
                continue
            validator.validate(value)
            target = value['target']
            plugin, skill = target['plugin'], target['skill']
            if '/' in plugin or '/' in skill or plugin in ('.', '..') or skill in ('.', '..'):
                raise ValueError('invalid target')
            source = root / 'plugins' / plugin / 'skills' / skill / 'SKILL.md'
            if not source.resolve().is_relative_to(root):
                raise ValueError(f'{plugin}/{skill}: source escapes repository')
            if digest(source) != target['skill_md_sha256'].removeprefix('sha256:'):
                raise ValueError(f'{plugin}/{skill}: reviewed SKILL.md changed')
            frontmatter = yaml.safe_load(source.read_text().split('---', 2)[1])
            criteria = {entry['id'] for entry in frontmatter.get('feedback_contract', {}).get('criteria', [])}
            if not criteria <= set(value['feedback_loop']['criteria_evaluated']):
                raise ValueError(f'{plugin}/{skill}: feedback criteria are not completely evaluated')
            if value['verdict'] != 'PASS' and not allow_nonpassing:
                raise ValueError(f'{plugin}/{skill}: independent verdict is {value["verdict"]}')
            key = (plugin, skill, value['review_kind'])
            if key in payloads and payloads[key] != value:
                raise ValueError(f'conflicting independent payload: {key}')
            payloads[key] = value
    if not payloads:
        raise ValueError('no independent verdict payloads')
    for plugin, skill, _ in payloads:
        if not all((plugin, skill, kind) in payloads for kind in ('elegance', 'rubric')):
            raise ValueError(f'{plugin}/{skill}: missing verdict pair')
    if apply:
        # All source hashes and payloads are checked before the first write.
        for plugin, skill, _ in payloads:
            folder = root / 'eval-log' / plugin / skill / 'content-review'
            if not folder.resolve().is_relative_to(root):
                raise ValueError(f'{plugin}/{skill}: verdict destination escapes repository')
        for (plugin, skill, kind), value in sorted(payloads.items()):
            folder = root / 'eval-log' / plugin / skill / 'content-review'
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            os.replace(temporary, folder / f'{kind}-verdict.json')
    counts = {kind: sum(payload['verdict'] == kind for payload in payloads.values())
              for kind in ('PASS', 'FAIL', 'INCOMPLETE')}
    return {'payload_count': len(payloads), 'checked_source_count': len(checked),
            'verdict_counts': counts, 'applied': apply}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--allow-nonpassing', action='store_true',
                        help='Explicitly record an honest FAIL/INCOMPLETE; never convert it to PASS.')
    parser.add_argument('artifacts', type=Path, nargs='+')
    args = parser.parse_args()
    print(json.dumps(project(args.root.resolve(), args.artifacts, args.apply, args.allow_nonpassing), ensure_ascii=False))
