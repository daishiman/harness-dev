from pathlib import Path
import json,hashlib,shutil,subprocess,sys
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');r=T/'runs/sysspec123';w=r/'workdir'
assert (w/'poll.log').read_text().startswith('DONE')
assert (w/'observer-stop').exists()
before=json.loads((w/'execution-invariants-before.json').read_text());after=[]
for x in before['files']:
 p=Path(x['path']);actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==x['sha256'],str(p);after.append({'path':str(p),'sha256':actual})
proof=T/'hook-state/sysspec123';dest=w/'written-source-order-proofs';assert not dest.exists();shutil.copytree(proof,dest)
review=Path('/tmp/pr86-written-read-order-independent-review.json');v=json.loads(review.read_text());assert v.get('result')=='PASS'
for suffix in ['json','md']:shutil.copy2(Path('/tmp/pr86-written-read-order-independent-review.'+suffix),w/('written-source-order-independent-review.'+suffix))
(w/'execution-invariants-after.json').write_text(json.dumps({'files':after,'before_ref':'execution-invariants-before.json','all_unchanged':True,'proof_files':[{'path':p.relative_to(dest).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(dest.rglob('*')) if p.is_file()],'semantic_evaluation_performed_by_hook':False},indent=2)+'\n')
shutil.copy2(__file__,w/'written-source-order-collection.py')
subprocess.run([sys.executable,'-B','/tmp/pr86-collect-policy.py','sysspec123','run-dev-graph-system-spec',sys.argv[1]],check=True)
subprocess.run([sys.executable,'-B','/tmp/pr86-normalize-note.py','sysspec123',sys.argv[1]],check=True)
