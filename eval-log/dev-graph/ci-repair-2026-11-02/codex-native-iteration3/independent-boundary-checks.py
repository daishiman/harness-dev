"""Independent synthetic boundary probes; never native-live acceptance evidence."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import contextlib,copy,hashlib,importlib.util,io,json,os,shutil,tempfile,datetime
ROOT=Path('/Users/dm/dev/dev/個人開発/harness')
OUT=Path(__file__).resolve().parent
SCRIPT=ROOT/'plugins/harness-creator/skills/run-skill-live-trial/scripts/manage-codex-live-trial.py'
GUARD=ROOT/'plugins/skill-governance-adapters/scripts/build-external-mutation-guard.py'
VERDICT=SCRIPT.with_name('live-trial-verdict.py')
SOURCES=[SCRIPT,GUARD,VERDICT]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
runner=load(SCRIPT,'independent_runtime_review')
def case(tmp):
 fx,private,work=tmp/'fx',tmp/'private',tmp/'work'
 for p in (fx,private,work):p.mkdir(parents=True)
 providers=tmp/'providers/plugins'
 guard=providers/'skill-governance-adapters/scripts/build-external-mutation-guard.py';guard.parent.mkdir(parents=True);shutil.copyfile(GUARD,guard)
 skill=providers/'dev-graph/skills/run-dev-graph-sync';skill.mkdir(parents=True);(skill/'SKILL.md').write_text('---\nname: run-dev-graph-sync\nexternal_mutation_guard: required\n---\n')
 wrapper=private/'wrapper.py';wrapper.write_text('# synthetic review wrapper, never registered or executed\n')
 adapter=fx/'tools/fake-gh.py';adapter.parent.mkdir();adapter.write_text('# synthetic local adapter, never executed\n')
 command=['python3','-c','raise SystemExit(0)']
 ext={'guard_script':str(guard),'hook_wrapper':str(wrapper),'hook_event_log':str(private/'hook-events.jsonl'),'fake_adapter':str(adapter),'allowed_commands':[command],'target_scopes':['fixture:independent-review']}
 cfg={'repo_root':str(fx),'private_dir':str(private),'workdir':str(work),'target_skill':'dev-graph:run-dev-graph-sync','skill_dir':str(skill),'loaded_provider_roots':[str(providers)],'external_confirmation_fixture':ext}
 raw=private/'synthetic-native.jsonl';raw.write_text(json.dumps({'type':'session_meta','payload':{'id':'synthetic-independent','cwd':str(fx)}})+'\n')
 state={'responses':[],'session_id':'synthetic-independent','native_rollout':str(raw),'external_fixture_pin':runner.external_source_pin(cfg),'writable_roots':[str(fx)]}
 mod=load(guard,'independent_synthetic_guard')
 preview=mod.preview(SimpleNamespace(project_root=str(fx),entrypoint_ref='plugin:dev-graph/skills/run-dev-graph-sync/SKILL.md',target_scope='fixture:independent-review',diff_summary='Independent synthetic validation only',side_effect_summary='No external execution',command_json=json.dumps(command)))
 request={'kind':'external-mutation-confirmation','state':'waiting_user_confirmation','invocation_id':'independent-external','challenge':preview['challenge'],'preview_receipt_id':Path(preview['receipt_path']).stem.removeprefix('preview-'),'preview_sha256':preview['receipt_sha256'],'project_root':str(fx)}
 text=f"GATE-CHALLENGE: {preview['challenge']} {preview['receipt_path']} {preview['receipt_sha256']} fixture:independent-review "+' '.join(command)
 inspected={'completed':True,'pending_tools':[],'session_id':state['session_id']}
 response=runner.validate_external_request(cfg,state,request,assistant_text=text,inspected=inspected)
 response.update(sent_after_turn=1,native_turn=2)
 prompt=f"CONFIRM EXTERNAL MUTATION {preview['challenge']}\n";response['prompt_sha256']=hashlib.sha256(prompt.encode()).hexdigest()
 payload={'hook_event_name':'UserPromptSubmit','session_id':state['session_id'],'cwd':str(fx),'prompt':prompt.strip(),'runtime':'claude'}
 raw=json.dumps(payload)
 output=io.StringIO()
 with patch.object(mod.sys,'stdin',io.StringIO(raw)),contextlib.redirect_stdout(output):
  assert mod.main(['hook-confirm','--runtime','codex'])==0
 row={'runtime':'codex','guard_script_sha256':state['external_fixture_pin']['guard_script_sha256'],'input_raw':raw,'output_raw':output.getvalue(),'returncode':0}
 Path(ext['hook_event_log']).write_text(json.dumps(row)+'\n')
 confirmation=next(fx.glob('.artifact-delivery/external-mutation/confirmation-*.json'))
 assert json.loads(confirmation.read_text())['producer']=='codex-user-prompt-submit'
 return cfg,state,response,text,prompt
results=[]
def record(name,fn):
 try:fn();results.append({'boundary':name,'result':'PASS'})
 except Exception as e:results.append({'boundary':name,'result':'FAIL','error':f'{type(e).__name__}: {e}'})
before={str(p.relative_to(ROOT)):sha(p) for p in SOURCES}
def replay():
 with tempfile.TemporaryDirectory(prefix='synthetic-replay-',dir=OUT) as t:
  cfg,state,response,text,prompt=case(Path(t));response['hook_records_before']=1
  try:runner.verify_external_confirmation(cfg,state,response,{})
  except ValueError as e:assert 'actual native confirmation hook event' in str(e)
  else:raise AssertionError('prior hook event was accepted as fresh confirmation')
  assert 'proof_ref' not in response
record('回答前の有効hook recordを後続回答へ再利用すると拒否・proof未発行',replay)
def actor_alias():
 with tempfile.TemporaryDirectory(prefix='synthetic-alias-',dir=OUT) as t:
  tmp=Path(t);cfg,state,response,text,prompt=case(tmp)
  fx,private=Path(cfg['repo_root']),Path(cfg['private_dir']);alias=fx/'mutable-log-alias';alias.symlink_to(private,target_is_directory=True)
  cfg['external_confirmation_fixture']['hook_event_log']=str(alias/'hook-events.jsonl')
  for name in ('task.md','scenario.json'):(private/name).write_text('{}\n')
  cli=private/'not-run-codex';cli.write_text('#!/bin/sh\nexit 90\n');cli.chmod(0o755)
  cfg.update(run_id='synthetic-alias-review',task_file=str(private/'task.md'),scenario_file=str(private/'scenario.json'),scenario_id='synthetic-only',codex_executable=str(cli))
  path=private/'config.json';path.write_text(json.dumps(cfg))
  try:runner.load_config(path)
  except ValueError as e:assert 'external hook_event_log alias overlaps' in str(e),str(e)
  else:raise AssertionError('actor-writable alias to private hook log accepted')
record('actor writable prefixからprivate hook logへ向くsymlinkを起動前に拒否',actor_alias)
def public_user_binding():
 with tempfile.TemporaryDirectory(prefix='synthetic-user-',dir=OUT) as t:
  cfg,state,response,text,prompt=case(Path(t));runner.verify_external_confirmation(cfg,state,response,{})
  work=Path(cfg['workdir']);ext=cfg['external_confirmation_fixture'];folder=work/'external-confirmations'
  for src,name in [('guard_script','guard-source.py'),('hook_wrapper','hook-wrapper.py'),('hook_event_log','hook-events.jsonl')]:shutil.copyfile(ext[src],folder/name)
  shutil.copytree(cfg['repo_root'],work/'fixture-final',ignore=shutil.ignore_patterns('.guard-key'))
  state['external_fixture_policy']={'allowed_commands':ext['allowed_commands'],'target_scopes':ext['target_scopes'],'guard_source_ref':'external-confirmations/guard-source.py','hook_wrapper_ref':'external-confirmations/hook-wrapper.py','hook_events_ref':'external-confirmations/hook-events.jsonl','fake_adapter_ref':'fixture-final/tools/fake-gh.py'}
  events=work/'native-exec';events.mkdir();(events/'turn-001.jsonl').write_text(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':text}})+'\n')
  user={'normalized_text_sha256':hashlib.sha256(prompt.strip().encode()).hexdigest()};verdict=runner.sibling('live-trial-verdict')
  assert verdict.external_confirmation_proof_errors(work,state,response,user)==[]
  user['normalized_text_sha256']=hashlib.sha256(b'continue').hexdigest()
  errors=verdict.external_confirmation_proof_errors(work,state,response,user)
  assert errors and any('native user input mismatch' in e for e in errors),errors
record('公開proofの有効receiptを一般continueのnative userへ付替えると拒否',public_user_binding)
after={str(p.relative_to(ROOT)):sha(p) for p in SOURCES}
report={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'/root/codex_acceptance_contract','evidence_kind':'independent-synthetic-boundary-probes','not_native_live_acceptance':True,'llm_runs':0,'real_user_configuration_writes':0,'source_writes':0,'source_sha256_before':before,'source_sha256_after':after,'source_unchanged_during_probes':before==after,'results':results,'overall':'PASS' if before==after and all(x['result']=='PASS' for x in results) else 'PARTIAL_OR_FAIL'}
(OUT/'independent-boundary-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
