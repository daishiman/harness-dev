from pathlib import Path
import importlib.util,json,tempfile,subprocess,concurrent.futures
p=Path('/tmp/pr86-written-read-order-guard.py');s=importlib.util.spec_from_file_location('g',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='pr86-order-check-') as td:
 root=Path(td)/'fx';root.mkdir();root=root.resolve();(root/'system-spec').mkdir();f=root/'system-spec/doc.txt';f.write_text('provided fixture\n');proof=Path(td).resolve()/'trusted';proof.mkdir();cfg={'root':str(root),'source_path':'system-spec/doc.txt','proof_dir':str(proof)}
 read={'tool_name':'Read','tool_input':{'file_path':str(f)},'cwd':str(root),'session_id':'s1','agent_id':'a1','tool_use_id':'read1'}
 assert m.check(cfg,read,'pre')
 cmd=m.command(root,'system-spec/doc.txt');out=subprocess.check_output(cmd,shell=True,text=True)
 post={'tool_name':'Bash','tool_input':{'command':cmd},'session_id':'s1','agent_id':'a1','tool_use_id':'bash1','tool_response':{'stdout':out,'stderr':'','interrupted':False}}
 assert m.check(cfg,post,'post') is None;assert m.check(cfg,read,'pre') is None
 assert m.check(cfg,dict(read,agent_id='a2'),'pre');assert m.check(cfg,dict(read,session_id='s2'),'pre')
 f.write_text('changed\n');assert m.check(cfg,read,'pre')
 f.unlink();outside=Path(td).resolve()/'outside.txt';outside.write_text('outside');f.symlink_to(outside);assert m.check(cfg,read,'pre')
 assert m.check(cfg,dict(read,tool_input={'file_path':str(root/'other.txt')}),'pre') is None
 f.unlink();f.write_text('provided fixture\n');bad=dict(post,agent_id='forged',tool_input={'command':'echo forged'});assert m.check(cfg,bad,'post') is None;assert m.check(cfg,dict(read,agent_id='forged'),'pre')
 interrupted=dict(post,agent_id='interrupted',tool_response={'stdout':out,'interrupted':True});m.check(cfg,interrupted,'post');assert m.check(cfg,dict(read,agent_id='interrupted'),'pre')
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  results=list(pool.map(lambda i:m.check(cfg,dict(post,tool_use_id='parallel'+str(i)),'post'),range(32)))
 assert all(r is None for r in results);assert m.check(cfg,read,'pre') is None;assert not list(proof.glob('*.tmp'))
 record={'checks':10,'result':'PASS','scope':'ordering/root/hash/session/actor binding, interrupted rejection, atomic concurrent callbacks only; not semantic audit or C19 acceptance','source_artifacts_generated':False,'test_root_canonicalized':True}
 Path('/tmp/pr86-written-read-order-guard-probe.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
