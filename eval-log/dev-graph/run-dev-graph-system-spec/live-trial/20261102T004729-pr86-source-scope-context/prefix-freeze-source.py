from pathlib import Path
import json,hashlib,sys,shutil
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');r=T/'runs/sysspec123';w=r/'workdir';sid=(w/'session-id.txt').read_text().strip();main=next((T/'home/.claude/projects').glob('*/'+sid+'.jsonl'));d=T/('review-prefix-sysspec123-'+sys.argv[1]);d.mkdir(exist_ok=False);rows=[]
index=json.loads((w/'tool-observer/index.json').read_text());
for stream,src in [('main',main)]+[('subagent/'+p.stem,p) for p in sorted((main.with_suffix('')/'subagents').glob('*.jsonl'))]:
 raw=src.read_bytes();name=stream.replace('/','-')+'.jsonl';(d/name).write_bytes(raw);rows.append({'stream':stream,'file':name,'original_path':str(src),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
od=d/'tool-observer';od.mkdir()
for entry in index['events']:shutil.copy2(w/'tool-observer'/entry['file'],od/entry['file'])
(od/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n');(d/'manifest.json').write_text(json.dumps({'session_id':sid,'scope':'fixed native prefix only; current stream must retain this prefix; no completion judgment','streams':rows},indent=2)+'\n');print(d,len(rows),'streams',len(index['events']),'events')
