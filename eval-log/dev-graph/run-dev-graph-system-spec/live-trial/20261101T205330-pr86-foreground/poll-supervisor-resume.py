from pathlib import Path
import os, sys, json, subprocess, signal, time, hashlib, importlib.util, shutil
sys.dont_write_bytecode=True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix')
T=Path('/private/tmp/claude-501/pr86-ci-live/lt')
w=T/'runs/sysspec117/workdir'; SC=W/'plugins/harness-creator/skills/run-skill-live-trial/scripts'
sid=(w/'session-id.txt').read_text().strip(); projects=T/'home/.claude/projects'
mains=list(projects.glob('*/'+sid+'.jsonl')); assert len(mains)==1
spec=importlib.util.spec_from_file_location('budget',SC/'validate-live-trial-resource-budget.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
usage=m.transcript_token_usage(mains[0]); assert usage['measured'] and usage['total_tokens']<23000000
started=float((w/'start.epoch').read_text()); assert time.time()-started<3300
def ps(pid):
 return subprocess.check_output(['ps','-p',str(pid),'-o','pid=,ppid=,command='],text=True).strip()
parent=ps(72835); child=ps(72941)
assert '/tmp/pr86-poll-supervisor.py sysspec117' in parent
assert child.split()[1]=='72835' and '/live-trial-poll.py ' in child and 'lt-sysspec117' in child
os.kill(72835,signal.SIGSTOP)
os.kill(72941,signal.SIGTERM)
os.kill(72835,signal.SIGTERM); os.kill(72835,signal.SIGCONT)
for _ in range(30):
 p=subprocess.run(['ps','-p','72835,72941','-o','pid='],capture_output=True,text=True)
 if not p.stdout.strip(): break
 time.sleep(0.1)
else: raise RuntimeError('old monitors remain')
state=json.loads((w/'poll-state.json').read_text()); assert state['started_at_unix']==started
shutil.copy2(w/'poll-state.json',w/'poll-state-before-observer-path-correction.json')
shutil.copy2(w/'poll.log',w/'poll-before-observer-path-correction.log')
record={'reason':'canonical poll was using default host projects directory rather than isolated native transcript directory; correct observation path only',
 'old_processes':[parent,child],'stopped_process_scope':'only own supervisor and canonical poll; subject/tmux/observer unchanged',
 'projects_dir':str(projects),'main_transcript':str(mains[0]),'state_untouched':state,'pre_resume_token_usage':usage,
 'started_at_unix':started,'time_reset':False,'scenario_budget_changed':False,'at_unix':time.time()}
(w/'poll-observer-path-correction.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
env=os.environ.copy(); env.update(CLAUDE_PROJECTS_DIR=str(projects),SESSION_ID=sid,TMUX_TMPDIR=(w/'tmux-tmpdir.txt').read_text().strip())
cmd=[sys.executable,'-B',str(SC/'live-trial-poll.py'),str(w/'out/status.json'),'lt-sysspec117','--state-file',str(w/'poll-state.json'),'--scenario-file',str(W/'plugins/dev-graph/tests/fixtures/live-trial-positive-scenarios.json'),'--scenario-id','C19-OUT1-positive-system-spec-lineage-r2']
shutil.copy2(__file__,w/'poll-supervisor-resume.py')
for attempt in range(2):
 with (w/'poll.log').open('w') as f: p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 if p.returncode!=2: break
 alive=subprocess.run([str(T/'lt-env.sh'),'TMUX_TMPDIR='+env['TMUX_TMPDIR'],'tmux','has-session','-t','lt-sysspec117'],capture_output=True).returncode==0
 log=(w/'poll.log').read_text()
 if attempt or not alive or not __import__('re').search(r'state:BUSY_',log): break
 shutil.copy2(w/'poll.log',w/'poll-first-busy-stall.log')
 (w/'poll-busy-stall-retry.json').write_text(json.dumps({'source':'run-skill-live-trial STALL table row2','attempts':1,'session_alive':alive,'original_state':json.loads((w/'poll-state.json').read_text()),'stall_limit_before':600,'stall_limit_after':1200,'scenario_budget_changed':False})+'\n')
 env['STALL_LIMIT']='1200'
(w/'poll-exit.txt').write_text(str(p.returncode)+'\n')
if p.returncode:
 tx=env['TMUX_TMPDIR']; owner=__import__('re').search(r'OWNER_PID:(\d+)',(w/'boot.log').read_text()).group(1)
 c=subprocess.run([str(T/'lt-env.sh'),'TMUX_TMPDIR='+tx,'tmux','capture-pane','-p','-S','-','-E','-','-t','lt-sysspec117'],capture_output=True,text=True)
 (w/'pane-before-reap.txt').write_text(c.stdout if not c.returncode else c.stderr)
 (w/'abort-reason.json').write_text(json.dumps({'reason':'canonical poll nonzero after source-defined BUSY retry if applicable','poll_exit':p.returncode,'poll_state':json.loads((w/'poll-state.json').read_text()),'completion_claimed':False,'automatic_cleanup_at_unix':time.time(),'run_id':'sysspec117','owner_pid':int(owner)},indent=2)+'\n')
 q=subprocess.run([sys.executable,'-B',str(SC/'live-trial-backend.py'),'reap','--run-id','sysspec117','--owner-pid',owner],env=env,capture_output=True,text=True)
 (w/'automatic-reap.log').write_text(q.stdout+q.stderr)
 if q.returncode: raise SystemExit(q.returncode)
 (w/'observer-stop').write_text('canonical poll nonzero; exact owned reap completed\n')
print('poll exit',p.returncode,flush=True)
raise SystemExit(p.returncode)
