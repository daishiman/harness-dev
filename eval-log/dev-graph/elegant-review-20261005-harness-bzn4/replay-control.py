#!/usr/bin/env python3
"""Run the existing live-trial CLI protocol; never implement target skill work."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
SCRIPTS = ROOT / 'plugins/harness-creator/skills/run-skill-live-trial/scripts'
PYTHON = '/Users/dm/miniconda3/bin/python3'


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['boot', 'send', 'poll', 'peek', 'collect'])
    parser.add_argument('index', type=int)
    parser.add_argument('--max-ticks', default=2, type=int)
    args = parser.parse_args()
    docpath = BASE / 'replay-current-jobs.json'
    doc = json.loads(docpath.read_text())
    job = doc['jobs'][args.index]
    out = Path(job['workdir'])
    setting = json.loads((BASE / 'boot-environment-iteration2.json').read_text())
    env = dict(os.environ)
    env['PATH'] = ':'.join(setting['PATH_prefix']) + ':' + env['PATH']
    env['TMUX_TMPDIR'] = setting['TMUX_TMPDIR']
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['BZN4_RUN_DIR'] = str(out)
    env['BZN4_FIXTURE_DIR'] = job['fixture']
    if job.get('session_id'):
        env['SESSION_ID'] = job['session_id']
    os.environ.update({k: env[k] for k in ('PATH', 'TMUX_TMPDIR', 'PYTHONDONTWRITEBYTECODE')})
    backend = module('live-trial-backend')
    verdict = module('live-trial-verdict')
    if args.action == 'boot':
        current = verdict.skill_dir_tree_sha(ROOT / 'plugins/dev-graph/skills' / job['skill'])
        if current != job['boot_behavior_sha256']:
            raise RuntimeError('source closure changed after frozen planner')
        # Only our isolated tmux server; each newly-created session inherits its own job boundaries.
        for key in ('BZN4_RUN_DIR', 'BZN4_FIXTURE_DIR', 'PATH', 'PYTHONDONTWRITEBYTECODE'):
            subprocess.run(['tmux', 'set-environment', '-g', key, env[key]], env=env, capture_output=True)
        argv = [PYTHON, str(SCRIPTS / 'live-trial-boot.py'), job['session'], str(ROOT), '--target-skill', 'dev-graph:' + job['skill']]
        result = subprocess.run(argv, env=env, capture_output=True, text=True)
        (out / 'boot.log').write_text(result.stdout + result.stderr)
        match = re.search(r'READY:.*SESSION_ID:([a-z0-9-]+)', result.stdout)
        job['launch'] = 'PASS' if result.returncode == 0 and match else 'FAIL'
        job['boot_exit'] = result.returncode
        if match:
            job['session_id'] = match.group(1)
        print(result.stdout + result.stderr, end='')
    elif args.action in {'send', 'poll'}:
        if args.action == 'send':
            argv = [PYTHON, str(SCRIPTS / 'live-trial-send.py'), job['session'], str(out / 'task.md')]
        else:
            argv = [PYTHON, str(SCRIPTS / 'live-trial-poll.py'), '--state-file', str(out / 'poll-state.json'), '--max-ticks', str(args.max_ticks), str(out / 'out/status.json'), job['session']]
        result = subprocess.run(argv, env=env, capture_output=True, text=True)
        job[args.action + '_exit'] = result.returncode
        with (out / (args.action + '.log')).open('a') as handle:
            handle.write(result.stdout + result.stderr)
        print(result.stdout + result.stderr, end='')
    elif args.action == 'peek':
        capture = backend.capture_pane(job['session'], scrollback=True)
        (out / 'pane-progress.txt').write_text(capture)
        print(capture[-2200:])
        status = out / 'out/status.json'
        print('status:', status.read_text() if status.exists() else 'pending')
    else:
        if job.get('poll_exit') != 0:
            raise RuntimeError('collect requires canonical DONE poll')
        (out / 'pane.txt').write_text(backend.capture_pane(job['session'], scrollback=True))
        source = verdict.find_transcript(str(out / 'session-state/projects'), job['session_id'])
        if source is None:
            source = verdict.find_transcript(str(Path.home() / '.claude/projects'), job['session_id'])
        if source is None:
            raise RuntimeError('actual session transcript missing')
        shutil.copy2(source, out / 'transcript.jsonl')
        childdir = source.parent / job['session_id'] / 'subagents'
        if childdir.is_dir():
            shutil.copytree(childdir, out / 'subagent-transcripts', dirs_exist_ok=True)
        job['actual_model'] = verdict.extract_models(out / 'transcript.jsonl')
        job['transcript_sha256'] = hashlib.sha256((out / 'transcript.jsonl').read_bytes()).hexdigest()
        job['completion'] = json.loads((out / 'out/status.json').read_text())['status']
        job['source_closure_still_matches'] = verdict.skill_dir_tree_sha(ROOT / 'plugins/dev-graph/skills' / job['skill']) == job['boot_behavior_sha256']
        job['killed'] = backend.kill_session(job['session'])
        print(json.dumps(job, ensure_ascii=False))
    docpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    return result.returncode if args.action in {'boot', 'send', 'poll'} else 0


if __name__ == '__main__':
    raise SystemExit(main())
