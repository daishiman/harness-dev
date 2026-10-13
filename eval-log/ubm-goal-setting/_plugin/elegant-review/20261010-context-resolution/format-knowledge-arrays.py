#!/usr/bin/env python3
"""Keep cards readable while retaining short scalar arrays on one line."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];RUN=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()

def render(value,level=0):
 indent='  '*level;child='  '*(level+1)
 if isinstance(value,dict):
  if not value:return '{}'
  return '{\n'+',\n'.join(child+json.dumps(k,ensure_ascii=False)+': '+render(v,level+1) for k,v in value.items())+'\n'+indent+'}'
 if isinstance(value,list):
  if not value:return '[]'
  inline=json.dumps(value,ensure_ascii=False)
  if all(not isinstance(v,(dict,list)) for v in value) and len(indent+inline)<=160:return inline
  return '[\n'+',\n'.join(child+render(v,level+1) for v in value)+'\n'+indent+']'
 return json.dumps(value,ensure_ascii=False)

def apply(write=False):
 draft=json.loads((RUN/'knowledge-context-draft.json').read_text());outputs={};records=[]
 for row in draft['files']:
  p=ROOT/row['path'];before=p.read_bytes();doc=json.loads(before);after=(render(doc)+'\n').encode()
  assert json.loads(after)==doc
  records.append({'path':row['path'],'before_sha256':sha(before),'after_sha256':sha(after),'semantic_sha256':sha(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()),'before_lines':before.count(b'\n'),'after_lines':after.count(b'\n'),'json_value_preserved':True})
  outputs[p]=(before,after)
 overflow=[r for r in records if r['after_lines']>500]
 if overflow:raise ValueError(f'Readable formatting insufficient; actual topic split required: {overflow}')
 if write:
  for p,(before,after) in outputs.items():assert p.read_bytes()==before
  for p,(before,after) in outputs.items():
   if before!=after:p.write_bytes(after)
 result={'applied':write,'files':records,'count':len(records),'all_json_values_preserved':True,'short_scalar_arrays_max_render_width':160,'card_objects_remain_multiline':True,'threshold_not_changed':500,'maximum_result_lines':max(r['after_lines'] for r in records)}
 (RUN/('knowledge-formatting-migration.json' if write else 'knowledge-formatting-plan.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('applied','count','maximum_result_lines','all_json_values_preserved')}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();apply(a.apply)
