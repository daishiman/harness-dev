from pathlib import Path
import os,re,sys,json,time,subprocess,hashlib
sys.dont_write_bytecode=True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix')
T=Path('/private/tmp/claude-501/pr86-ci-live/lt')
SC=W/'plugins/harness-creator/skills/run-skill-live-trial/scripts'
label=sys.argv[1];assert re.fullmatch('sysspec[0-9]+',label)
r=T/'runs'/label;w=r/'workdir';sid=(w/'session-id.txt').read_text().strip();tx=(w/'tmux-tmpdir.txt').read_text().strip()
owner=re.search(r'OWNER_PID:(\d+)',(w/'boot.log').read_text()).group(1)
env=os.environ.copy();env.update(TMUX_TMPDIR=tx,SESSION_ID=sid)
state=w/'poll-state.json';assert not state.exists(),'fresh immutable timer only'
started=float((w/'start.epoch').read_text());state.write_text(json.dumps({'elapsed':int(time.time()-started),'started_at_unix':started,'observed_at_unix':time.time()})+'\n')
(w/'poll-supervisor-provenance.json').write_text(json.dumps({'started_at_source':'start.epoch','started_at_unix':started,'scenario_budget_changed':False,'ownership':{'run_id':label,'owner_pid':int(owner)},'on_nonzero':'capture pane, exact owned reap, stop observer; never convert failure to success','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
cmd=[sys.executable,'-B',str(SC/'live-trial-poll.py'),str(w/'out/status.json'),'lt-'+label,'--state-file',str(state),'--scenario-file',str(W/'plugins/dev-graph/tests/fixtures/live-trial-positive-scenarios.json'),'--scenario-id','C19-OUT1-positive-system-spec-lineage-r2']
with (w/'poll.log').open('w') as f:p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
(w/'poll-exit.txt').write_text(str(p.returncode)+'\n')
if p.returncode:
 c=subprocess.run([str(T/'lt-env.sh'),'TMUX_TMPDIR='+tx,'tmux','capture-pane','-p','-S','-','-E','-','-t','lt-'+label],capture_output=True,text=True)
 (w/'pane-before-reap.txt').write_text(c.stdout if c.returncode==0 else 'capture failed: '+c.stderr)
 reason={'reason':'canonical poll nonzero exit; automatic fail-closed owned cleanup','poll_exit':p.returncode,'poll_state':json.loads(state.read_text()),'completion_claimed':False,'automatic_cleanup_at_unix':time.time(),'run_id':label,'owner_pid':int(owner)}
 (w/'abort-reason.json').write_text(json.dumps(reason,ensure_ascii=False,indent=2)+'\n')
 q=subprocess.run([sys.executable,'-B',str(SC/'live-trial-backend.py'),'reap','--run-id',label,'--owner-pid',owner],env=env,capture_output=True,text=True)
 (w/'automatic-reap.log').write_text(q.stdout+q.stderr)
 if q.returncode:raise SystemExit(q.returncode)
 (w/'observer-stop').write_text('canonical poll nonzero; exact owned reap completed\n')
print('poll exit',p.returncode,flush=True)
raise SystemExit(p.returncode)
