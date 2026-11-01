from pathlib import Path
import sys,subprocess,json,hashlib,shutil
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');label=sys.argv[1];r=T/'runs'/label;w=r/'workdir';meta=json.loads((w/'project-instructions-provenance.json').read_text())
assert (w/'poll.log').read_text().startswith('DONE')
actual=Path(meta['path']);assert actual.parent==r/'fx' and actual.name in ['CLAUDE.md','CLAUDE.local.md'];assert actual.read_bytes()==(w/'project-instructions.md').read_bytes()
assert hashlib.sha256(actual.read_bytes()).hexdigest()==meta['sha256']
probe=w/'native-memory-probe'
if probe.exists():
 maps=[]
 for src,dest in [('CLAUDE.md','probe-project-instructions.md'),('CLAUDE.local.md','probe-local-instructions.md')]:
  source=probe/src;shutil.copy2(source,probe/dest);maps.append({'original_name':src,'portable_copy':dest,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
 (probe/'portable-input-copies.json').write_text(json.dumps(maps,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(actual,w/'project-instructions-at-collection.md');shutil.copy2(__file__,w/'policy-collection.py')
subprocess.run([sys.executable,'-B','/tmp/pr86-collect-new.py']+sys.argv[1:],check=True)
