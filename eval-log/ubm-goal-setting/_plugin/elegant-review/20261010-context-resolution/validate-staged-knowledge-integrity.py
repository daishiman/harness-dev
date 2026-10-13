#!/usr/bin/env python3
"""Independently compare final knowledge to captured original documents."""
import hashlib,json
from pathlib import Path
from jsonschema import Draft202012Validator,FormatChecker
ROOT=Path(__file__).resolve().parents[5];RUN=Path(__file__).resolve().parent;KB=ROOT/'plugins/ubm-goal-setting/knowledge'
sha=lambda b:hashlib.sha256(b).hexdigest()
def validate():
 original=json.loads((RUN/'knowledge-context-draft.json').read_text())
 originals={e['id']:e for e in original['records']};errors=[];count=0;seen=set();changes={};hashes={}
 validator=Draft202012Validator(json.loads((KB/'schema.json').read_text())['knowledge_entry_schema'],format_checker=FormatChecker())
 allowed={'background','content','title','intent','purpose','tags'}
 for row in original['files']:
  p=ROOT/row['path'];current=json.loads(p.read_text());before=row['before_document'];validator.validate(current)
  if {k:v for k,v in current.items() if k!='entries'}!={k:v for k,v in before.items() if k!='entries'}:errors.append({'path':row['path'],'error':'document metadata/count changed'})
  if [e['id'] for e in current['entries']]!=[e['id'] for e in before['entries']]:errors.append({'path':row['path'],'error':'ordered identity inventory changed'})
  hashes[row['path']]=sha(p.read_bytes())
  for old,new in zip(before['entries'],current['entries']):
   count+=1;identifier=new['id']
   if identifier in seen:errors.append({'id':identifier,'error':'duplicate identity'})
   seen.add(identifier)
   changed=[field for field in set(old)|set(new) if old.get(field)!=new.get(field)]
   changes[identifier]=sorted(changed)
   if set(changed)-allowed:errors.append({'id':identifier,'error':'unapproved original field mutation','fields':sorted(set(changed)-allowed)})
   if old.get('source')!=new.get('source'):errors.append({'id':identifier,'error':'source provenance changed'})
   if not set(old.get('tags',[]))<=set(new.get('tags',[])):errors.append({'id':identifier,'error':'original tags removed'})
   if ('title' in old)!=('title' in new) or ('content' in old)!=('content' in new):errors.append({'id':identifier,'error':'core field shape changed'})
   record=originals[identifier]
   if old['background']!=record['old_background']:errors.append({'id':identifier,'error':'original background snapshot mismatched'})
 if seen!=set(originals):errors.append({'error':'original inventory incomplete'})
 result={'entry_count':count,'file_count':len(original['files']),'errors':errors,'source_and_identity_preserved':not errors,'allowed_repairs':sorted(allowed),'changed_fields_by_id':changes,'current_source_sha256':hashes,'notes':'Checks preservation and schema, not semantic acceptance. Original core/intent values remain in the full original-document snapshot and dedicated style audit.'}
 (RUN/'validation-staged-knowledge-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'entries':count,'files':len(original['files']),'errors':len(errors)}));return 1 if errors else 0
if __name__=='__main__':raise SystemExit(validate())
