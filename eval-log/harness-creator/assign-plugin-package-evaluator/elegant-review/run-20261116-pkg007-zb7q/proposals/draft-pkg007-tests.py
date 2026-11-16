"""PKG-007 レビュー用下書きの境界テスト。製品へ未適用。"""
import importlib.util
import os
from pathlib import Path
import pytest

SCRIPT = Path(__file__).with_name('draft-validate-plugin-package.py')
SPEC = importlib.util.spec_from_file_location('draft_pkg007', SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def skill(tmp_path, refs):
    root = tmp_path / 'plugin'
    folder = root / 'skills' / 'run-demo'
    folder.mkdir(parents=True)
    md = folder / 'SKILL.md'
    md.write_text('---\nname: run-demo\n' + refs + '\n---\n本文\n')
    return root, folder, md


def script(path, text='#!/usr/bin/env python3\n', mode=0o755):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


@pytest.mark.parametrize('refs', [
    'script_refs:\n  - "scripts/check.py" # note',
    "script_refs: ['scripts/check.py'] # note",
])
def test_yaml_block_flow_quotes_comments(tmp_path, refs):
    root, folder, _ = skill(tmp_path, refs)
    script(folder / 'scripts/check.py')
    assert MOD.check_pkg_007(root) == []


@pytest.mark.parametrize('refs', [
    'script_refs: scripts/check.py', 'script_refs: null', 'script_refs: [3]',
    'script_refs: [scripts/check.py',
    'script_refs: []\nscript_refs: []',
    'script_refs: [""]',
])
def test_malformed_yaml_or_refs_fail_at_source(tmp_path, refs):
    root, _, md = skill(tmp_path, refs)
    fs = MOD.check_pkg_007(root)
    assert len(fs) == 1
    assert fs[0]['location'] == str(md)


def test_skill_candidate_precedes_plugin_candidate(tmp_path):
    root, folder, _ = skill(tmp_path, 'script_refs: [scripts/check.py]')
    local = script(folder / 'scripts/check.py', 'print(1)\n', 0o644)
    script(root / 'scripts/check.py')
    fs = MOD.check_pkg_007(root)
    assert len(fs) == 1
    assert fs[0]['location'] == str(local)
    assert 'shebang' in fs[0]['evidence'] and '+x' in fs[0]['evidence']


@pytest.mark.parametrize('kind', ['broken', 'external'])
def test_invalid_first_candidate_is_not_rescued(tmp_path, kind):
    root, folder, md = skill(tmp_path, 'script_refs: [scripts/check.py]')
    local = folder / 'scripts/check.py'
    local.parent.mkdir()
    target = tmp_path / 'outside.py'
    if kind == 'external':
        script(target)
    local.symlink_to(target)
    script(root / 'scripts/check.py')
    fs = MOD.check_pkg_007(root)
    assert len(fs) == 1
    assert fs[0]['location'] == (str(md) if kind == 'broken' else str(target))


def test_missing_reference_fails_even_without_root_scripts(tmp_path):
    root, _, md = skill(tmp_path, 'script_refs: [scripts/missing.py]')
    fs = MOD.check_pkg_007(root)
    assert len(fs) == 1 and fs[0]['location'] == str(md)


def test_explicit_helper_is_not_exempt(tmp_path):
    root, folder, _ = skill(tmp_path, 'script_refs: [scripts/helper.py]')
    script(folder / 'scripts/helper.py', 'def helper():\n    pass\n', 0o644)
    fs = MOD.check_pkg_007(root)
    assert len(fs) == 1 and 'shebang' in fs[0]['evidence'] and '+x' in fs[0]['evidence']


def test_unreferenced_root_helper_keeps_existing_exemption(tmp_path):
    root, _, _ = skill(tmp_path, 'script_refs: []')
    script(root / 'scripts/helper.py', 'def helper():\n    pass\n', 0o644)
    assert MOD.check_pkg_007(root) == []


def test_duplicate_aliases_and_root_scan_emit_one_finding(tmp_path):
    root, folder, _ = skill(tmp_path, 'script_refs: [scripts/a.py, scripts/b.py, ../../scripts/check.py]')
    real = script(root / 'scripts/check.py', 'print(1)\n', 0o644)
    (folder / 'scripts').mkdir()
    (folder / 'scripts/a.py').symlink_to(real)
    (folder / 'scripts/b.py').symlink_to(real)
    fs = MOD.check_pkg_007(root)
    assert len(fs) == 1
    assert fs[0]['location'] == str(real)
    assert 'scripts/a.py' in fs[0]['evidence'] and 'scripts/b.py' in fs[0]['evidence']


def test_permission_contract_uses_mode_bits(tmp_path, monkeypatch):
    root, folder, _ = skill(tmp_path, 'script_refs: [scripts/check.py]')
    script(folder / 'scripts/check.py', mode=0o500)
    monkeypatch.setattr(os, 'access', lambda *args: False)
    assert MOD.check_pkg_007(root) == []


def test_reference_directory_is_not_script(tmp_path):
    root, folder, _ = skill(tmp_path, 'script_refs: [scripts/check.py]')
    (folder / 'scripts/check.py').mkdir(parents=True)
    fs = MOD.check_pkg_007(root)
    assert len(fs) == 1 and '通常ファイル' in fs[0]['evidence']


def test_draft_declares_pyyaml_with_valid_pep723():
    import tomllib
    block = SCRIPT.read_text().split('# /// script\n', 1)[1].split('# ///', 1)[0]
    metadata = tomllib.loads('\n'.join(line.removeprefix('# ') for line in block.splitlines()))
    assert metadata['dependencies'] == ['PyYAML>=6.0']
