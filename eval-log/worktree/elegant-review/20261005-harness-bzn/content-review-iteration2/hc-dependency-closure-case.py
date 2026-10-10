#!/usr/bin/env python3
"""Copy-only F-4002 proof for the shared HC loader plus bundled resolver."""
import ast, hashlib, importlib.util, json, shutil, tempfile
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
script=ROOT/'plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py'
spec=importlib.util.spec_from_file_location('independent_hc_closure',script)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
names=['run-build-skill','run-plugin-package-check']
helper=ROOT/'plugins/harness-creator/scripts/plugin_resources.py'
resolver=ROOT/'plugins/harness-creator/scripts/extract-plugin-root.py'
records={};copy_paths={ROOT/'plugins/harness-creator/references/package-contract.json',helper,resolver}
old={}
for name in names:
 skill=ROOT/'plugins/harness-creator/skills'/name;target=skill/'SKILL.md'
 text=target.read_text();old[name]={'path':str(target),'text':text,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 files=module.behavior_closure_files(skill);copy_paths.update(p for _,p in files)
 assert helper not in [p for _,p in files]
 assert resolver not in [p for _,p in files]
 callers=[]
 for _,path in files:
  if path.suffix!='.py' or not path.is_relative_to(ROOT/'plugins/harness-creator'):continue
  tree=ast.parse(path.read_text())
  imports=[n for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module=='plugin_resources']
  if imports:callers.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'imports':[alias.name for n in imports for alias in n.names]})
 assert callers
 records[name]={'actual_helper_callers':callers,'current_behavior_sha256':module.skill_dir_tree_sha(skill)}
(OUT/'hc-dependency-pre-ref-skills.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
with tempfile.TemporaryDirectory(prefix='independent-hc-common-dependency-') as td:
 copied=Path(td)
 for source in copy_paths:
  dest=copied/source.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
 def digest(name):return module.skill_dir_tree_sha(copied/'plugins/harness-creator/skills'/name)
 baseline={n:digest(n) for n in names}
 assert baseline=={n:records[n]['current_behavior_sha256'] for n in names}
 ch=copied/helper.relative_to(ROOT);cr=copied/resolver.relative_to(ROOT)
 ht=ch.read_text();rt=cr.read_text()
 hmut=ht.replace('return module.resolve(name, plugin_root, cwd or Path.cwd())','return None',1)
 assert hmut!=ht
 ch.write_text(hmut)
 assert {n:digest(n) for n in names}==baseline
 ch.write_text(ht)
 cr.write_text(rt+'\nraise RuntimeError("independent semantic resolver mutation")\n')
 assert {n:digest(n) for n in names}==baseline
 cr.write_text(rt)
 for n in names:
  md=copied/'plugins/harness-creator/skills'/n/'SKILL.md'
  text=md.read_text();text=text.replace('script_refs:\n','script_refs:\n  - ../../scripts/plugin_resources.py\n  - ../../scripts/extract-plugin-root.py\n',1)
  md.write_text(text)
 fixed_before={n:digest(n) for n in names}
 ch.write_text(hmut)
 assert all(digest(n)!=fixed_before[n] for n in names)
 ch.write_text(ht)
 cr.write_text(rt+'\nraise RuntimeError("independent semantic resolver mutation")\n')
 assert all(digest(n)!=fixed_before[n] for n in names)
 for n in names:
  records[n].update({'original_helper_mutation_missed':True,'original_resolver_mutation_missed':True,'proposed_two_refs_detect_both_mutations':True})
print(json.dumps({'finding_id':'F-4002','category':'dependency_break','result':'PASS_REPRODUCED_SOURCE_C4_FAILURE','skills':records,'minimal_fix':'Add ../../scripts/plugin_resources.py and ../../scripts/extract-plugin-root.py to script_refs for run-build-skill and run-plugin-package-check.','proof_scope':'Copy-only digest proof against actual target local callers and dynamic bundled resolver dependency; not a live host execution.','source_edits':False},ensure_ascii=False,indent=2))
