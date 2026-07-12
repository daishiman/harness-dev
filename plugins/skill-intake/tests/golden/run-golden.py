#!/usr/bin/env python3
"""skill-intake 決定論ゴールデンテスト。

目的: 同一入力 -> 同一出力 (誰が実行しても同じヒアリングシート) を CI で保証する。
  G1. sample-answers.json を build-intent.py に 3 回通し、intent_contract 部の
      sha256 が 3 回とも一致すること (冪等性)。
  G2. sample-intake.json に対し check_completeness.py --mode all が exit 0 (完全性) であること。

いずれか不成立で exit 1。全成立で exit 0。単体で CI (ci_dogfooding_retest.py 等) から
呼び出せる自己完結スクリプト。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent.parent  # tests/golden -> tests -> plugin root
SCRIPTS = PLUGIN / 'scripts'
REFS = PLUGIN / 'references'
FIXTURES = HERE / 'fixtures'

NORMALIZE = SCRIPTS / 'build-intent.py'
CHECK = SCRIPTS / 'check_completeness.py'
PROBE_TABLE = REFS / 'probe-pattern-table.json'
CANONICAL_MAP = REFS / 'section_canonical_map.json'
SAMPLE_ANSWERS = FIXTURES / 'sample-answers.json'
SAMPLE_INTAKE = FIXTURES / 'sample-intake.json'

REPEAT = 3


def _run(cmd):
    return subprocess.run(
        [sys.executable, *[str(c) for c in cmd]],
        capture_output=True, text=True,
    )


def gate_idempotent_normalize():
    """G1: build-intent を 3 回実行し intent_contract の sha256 一致を確認。"""
    digests = []
    for _ in range(REPEAT):
        proc = _run([NORMALIZE, SAMPLE_ANSWERS, '--table', PROBE_TABLE])
        if proc.returncode != 0:
            return {
                'name': 'G1_idempotent_normalize', 'ok': False,
                'reason': f'normalize exit {proc.returncode}: {proc.stderr.strip()}',
            }
        try:
            out = json.loads(proc.stdout)
        except Exception as e:
            return {'name': 'G1_idempotent_normalize', 'ok': False,
                    'reason': f'stdout not JSON: {e}'}
        contract = out.get('intent_contract', {})
        canon = json.dumps(contract, ensure_ascii=False, sort_keys=True)
        digests.append(hashlib.sha256(canon.encode('utf-8')).hexdigest())
    ok = len(set(digests)) == 1
    return {
        'name': 'G1_idempotent_normalize', 'ok': ok,
        'runs': REPEAT, 'sha256': digests,
        'reason': '' if ok else f'sha256 mismatch across {REPEAT} runs',
    }


def gate_check_all_pass():
    """G2: check_completeness --mode all が exit 0 (全 PASS) であることを確認。"""
    proc = _run([
        CHECK, '--mode', 'all',
        '--canonical-map', CANONICAL_MAP,
        '--probe-table', PROBE_TABLE,
        SAMPLE_INTAKE,
    ])
    ok = proc.returncode == 0
    return {
        'name': 'G2_check_all_pass', 'ok': ok,
        'exit_code': proc.returncode,
        'reason': '' if ok else f'check_all exit {proc.returncode}: {proc.stdout.strip()} {proc.stderr.strip()}',
    }


def main():
    results = [gate_idempotent_normalize(), gate_check_all_pass()]
    ok = all(r['ok'] for r in results)
    report = {'status': 'PASS' if ok else 'FAIL', 'gates': results}
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
