#!/usr/bin/env python3
"""Independent current declaration verification for F-4002."""
from pathlib import Path
import ast,hashlib,importlib.util,json,shutil,tempfile,yaml
ROOT=Path(__file__).resolve().parents[5];OUT=Path(__file__).resolve().parent
old=json.loads((OUT/'hc-dependency-pre-ref-skills.json').read_text())
script=ROOT/'plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py'
spec=importlib.util.spec_from_file_location('independent_current_hc_closure',script)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
helper=ROOT/'plugins/harness-creator/scripts/plugin_resources.py';resolver=ROOT/'plugins/harness-creator/scripts/extract-plugin-root.py'
paths={ROOT/'plugins/harness-creator/references/package-contract.json'};records={}
for name,before in old.items():
 skill=ROOT/'plugins/harness-creator/skills'/name;target=skill/'SKILL.md';text=target.read_text()
 expected=before['text'].replace('script_refs:\n','script_refs:\n  - ../../scripts/plugin_resources.py\n  - ../../scripts/extract-plugin-root.py\n',1)
 assert text==expected,name
 fm=yaml.safe_load(text.split('---',2)[1]);prev=yaml.safe_load(before['text'].split('---',2)[1])
 assert fm['script_refs']==['../../scripts/plugin_resources.py','../../scripts/extract-plugin-root.py']+prev['script_refs']
 assert {k:v for k,v in fm.items() if k!='script_refs'}=={k:v for k,v in prev.items() if k!='script_refs'}
 files=module.behavior_closure_files(skill);paths.update(p for _,p in files)
 assert sum(p==helper for _,p in files)==sum(p==resolver for _,p in files)==1
 callers=[]
 for _,p in files:
  if p.suffix!='.py' or not p.is_relative_to(ROOT/'plugins/harness-creator'):continue
  imports=[n for n in ast.walk(ast.parse(p.read_text())) if isinstance(n,ast.ImportFrom) and n.module=='plugin_resources']
  if imports:callers.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'imports':[a.name for n in imports for a in n.names]})
 assert len(callers)==3,name
 records[name]={'skill_md_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'body_and_other_frontmatter_unchanged':True,'helper_and_resolver_present_once':True,'actual_helper_callers':callers,'current_behavior_sha256':module.skill_dir_tree_sha(skill)}
with tempfile.TemporaryDirectory(prefix='independent-current-hc-ref-') as td:
 copied=Path(td)
 for p in paths:
  dest=copied/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 def digest(n):return module.skill_dir_tree_sha(copied/'plugins/harness-creator/skills'/n)
 baseline={n:digest(n) for n in records};assert baseline=={n:r['current_behavior_sha256'] for n,r in records.items()}
 ch=copied/helper.relative_to(ROOT);cr=copied/resolver.relative_to(ROOT)
 ht=ch.read_text();rt=cr.read_text();hmut=ht.replace('return module.resolve(name, plugin_root, cwd or Path.cwd())','return None',1);assert hmut!=ht
 for dependency,path,mutation,original in [('helper',ch,hmut,ht),('resolver',cr,rt+'\nraise RuntimeError("independent semantic mutation")\n',rt)]:
  path.write_text(mutation)
  for n in records:
   assert digest(n)!=baseline[n],(n,dependency)
   records[n][dependency+'_mutation_invalidates']=True
  path.write_text(original)
  path.unlink()
  for n in records:
   try:digest(n)
   except ValueError as exc:
    assert 'missing' in str(exc),str(exc)
    records[n]['missing_'+dependency+'_fails_closed']=True
   else:raise AssertionError((n,dependency,'missing accepted'))
  path.write_text(original)
print(json.dumps({'finding_id':'F-4002','case':'current_both_hc_helper_and_resolver_declarations','result':'PASS','skills':records,'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'resolver_sha256':hashlib.sha256(resolver.read_bytes()).hexdigest(),'proof_scope':'Exact two refs, actual local imports, dynamic resolver chain, copied executable mutation and missing-file refusal; no full build/package execution claim.','source_edits':False,'temporary_copy_only':True},ensure_ascii=False,indent=2))
