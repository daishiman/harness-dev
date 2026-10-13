"""共有語彙契約の破損で検査が素通りしないことを確認する。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name', ['goal-setting', 'challenge'])
@pytest.mark.parametrize('policy', [None, {}, {'goal_exact_phrases': [], 'challenge_stems': []},
                                    {'goal_exact_phrases': '意識する', 'challenge_stems': '意識する'}])
def test_bad_shared_policy_stops_validator_with_input_error(tmp_path, name, policy):
    kind = 'goal' if name == 'goal-setting' else 'challenge'
    root = tmp_path / 'plugin'
    script = root / f'skills/run-ubm-{name}/scripts/validate-{kind}-output.py'
    script.parent.mkdir(parents=True)
    script.write_text((PLUGIN_ROOT / script.relative_to(root)).read_text())
    if policy is not None:
        (root / 'references').mkdir()
        (root / 'references/action-language-policy.json').write_text(json.dumps(policy))
    result = subprocess.run([sys.executable, str(script), '--file', str(tmp_path / 'missing.md')],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert '語彙契約' in result.stderr
    assert 'Traceback' not in result.stderr
