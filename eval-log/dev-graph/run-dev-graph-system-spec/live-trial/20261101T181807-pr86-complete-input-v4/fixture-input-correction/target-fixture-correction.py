from pathlib import Path
import json,hashlib,subprocess,sys,shutil,re
sys.dont_write_bytecode=True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');T=Path('/private/tmp/claude-501/pr86-ci-live/lt');D=T/'positive-input-v4';old=T/'positive-input-v3'
assert not D.exists();shutil.copytree(old,D)
state=D/'system-spec/spec-state.json';before=json.loads(state.read_text());(D/'targets-before-state.json').write_bytes(state.read_bytes())
targets=before['targets']+[{'target_id':'kubernetes','category':'infrastructure','also_categories':['backend','maintenance-ops']}]
(D/'targets-v4.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2)+'\n')
meta=json.loads(Path('/tmp/pr86-kubernetes-official-response.json').read_text());body=Path('/tmp/pr86-kubernetes-official-response.html').read_bytes();assert meta['status']==200
m=re.search(rb'itemprop=dateModified content="([^"]+)"',body);assert m
updated=m.group(1).decode();evidence=D/'system-spec/retrieval-evidence/kubernetes.html';evidence.write_bytes(body)
shutil.copy2('/tmp/pr86-kubernetes-official-response.json',D/'kubernetes-response-metadata.json')
records=json.loads((D/'system-spec/fetched-references.json').read_text())['references'];records.append({'target_id':'kubernetes','retrieved_at':meta['retrieved_at'],'source_url':meta['source_url'],'official_publisher':'The Kubernetes Authors','official_host':'kubernetes.io','last_updated':updated,'latest_checked_at':meta['retrieved_at'],'evidence_ref':'system-spec/retrieval-evidence/kubernetes.html','evidence_sha256':hashlib.sha256(body).hexdigest(),'summary':'Kubernetes公式CronJob文書。CronJobは反復scheduleに基づきJobを作成する。重複実行や欠落が起こり得るためJobの冪等性が必要。concurrencyPolicyのForbidは同じCronJob由来Jobの並行を制限するが、業務効果のexactly-onceを保証しない。D4のDB一意キー・claim排他・lease/fencingによる重複反映防止を併用する。'})
(D/'reference-records-v4.json').write_text(json.dumps({'records':records},ensure_ascii=False,indent=2)+'\n')
SS=W/'plugins/system-spec-harness'
cmds=[['skills/run-system-spec-elicit/scripts/apply-spec-transition.py','set-targets','--state',str(state),'--targets',str(D/'targets-v4.json')],['skills/run-system-spec-doc-fetch/scripts/build-fetched-references.py','assemble','--records',str(D/'reference-records-v4.json'),'--targets',str(state),'--out',str(D/'system-spec/fetched-references.json')],['scripts/validate-source-citation.py','--targets',str(state),'--references',str(D/'system-spec/fetched-references.json'),'--state',str(state),'--repo-root',str(D)],['skills/run-system-spec-compile/scripts/compile-spec-doc.py','compile','--spec',str(state),'--references',str(D/'system-spec/fetched-references.json'),'--out-dir',str(D/'system-spec'),'--repo-root',str(W)]]
results=[]
for i,c in enumerate(cmds):
 cmd=[sys.executable,'-B',str(SS/c[0])]+c[1:];p=subprocess.run(cmd,cwd=W,capture_output=True,text=True);(D/f'target-v4-{i}.stdout').write_text(p.stdout);(D/f'target-v4-{i}.stderr').write_text(p.stderr);results.append({'argv':cmd,'exit':p.returncode});print(i,p.returncode,p.stdout[-200:],p.stderr[-200:]);assert p.returncode==0
s=json.loads(state.read_text());assert {k:v for k,v in before.items() if k!='targets'}=={k:v for k,v in s.items() if k!='targets'}
shutil.copy2(__file__,D/'target-fixture-correction.py')
(D/'target-correction-provenance.json').write_text(json.dumps({'kind':'synthetic-positive-target-completion','actual_user_approval_claimed':False,'reason':'v3でD4に採用したKubernetesがtargetsとfetched referencesに未列挙だった。既存QA/承認/意思決定は一字も変更せず、単一writerでtargetを追加し実HTTP取得をcanonical assemblerで出典化する。対象agentのSkill実行/監査/PASSとしては主張しない。','new_target':targets[-1],'body_sha256':hashlib.sha256(body).hexdigest(),'response_metadata':'kubernetes-response-metadata.json','commands':results,'all_non_target_state_fields_identical':True,'evaluation_or_graph_seeded':False,'scenario_observations_changed':False},ensure_ascii=False,indent=2)+'\n')
public=W/'eval-log/dev-graph/live-trial-fixtures/pr86-system-spec-positive-v4';assert not public.exists();shutil.copytree(D,public)
print('v4 canonical targets, references, compiled inputs prepared')
