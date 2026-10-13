"""Audit-only draft preparation; never writes knowledge source cards or awards L1 PASS."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
KB=ROOT/'plugins/ubm-goal-setting/knowledge'
OUT=Path(__file__).parent

def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def sentences(text):
    parts=[];start=0;depth=0
    for i,c in enumerate(text):
        if c in '「『（(':depth+=1
        elif c in '」』）)':depth=max(0,depth-1)
        elif c=='。' and depth==0:parts.append(text[start:i+1].strip());start=i+1
    rest=text[start:].strip()
    if rest:parts.append(rest if rest.endswith('。') else rest+'。')
    return [p for p in parts if p]

def draft(e,cat):
    cause_fields={'principles':['root_cause','content'],'consultation':['root_cause','key_insight'],'phase-advice':['root_cause','background'],'action-guides':['root_cause','rationale'],'mindset':['root_cause','why_the_shift_matters'],'case-studies':['root_cause','insight','key_factor','lesson']}[cat]
    ck=next(k for k in cause_fields if e.get(k))
    context_key=next((k for k in ['applicable_when','trigger','lesson_applicable_when','problem'] if e.get(k)),None)
    if not context_key:context_key='background'
    context=sentences(e[context_key])[0]
    # Explicit excerpts, not an automated semantic score. Later edits are recorded separately.
    selections=[(context_key,context)]+[(ck,s) for s in sentences(e[ck])[:4]]
    if len(selections)<2 or (ck==context_key and selections[0][1]==selections[1][1]):
        other=next((k for k in ['content','focus','lesson','key_insight','expected_outcome','intent'] if k!=ck and e.get(k)),None)
        if other:selections.append((other,sentences(e[other])[0]))
    if re.search(r'これ|この(?:三つ|二つ|[0-9]+)|その(?:負荷|過程|順序)|そうする',e[ck]) and e.get('content') and ck!='content':
        selections.insert(1,('content',sentences(e['content'])[0]))
    dedup=[]
    for k,s in selections:
        if not any(s==v for _,v in dedup):dedup.append((k,s))
    text=''.join(s for _,s in dedup[:5])
    return text,[{'field':k,'source_value':e[k],'source_value_sha256':sha(e[k].encode()),'selected_excerpt':s,'exact_excerpt':s in e[k]} for k,s in dedup[:5]]

router=json.loads((KB/'router.json').read_text());records=[];files=[]
for cat,cfg in router['categories'].items():
    for filename in cfg['files']:
        p=KB/filename;raw=p.read_bytes();doc=json.loads(raw);files.append({'path':str(p.relative_to(ROOT)),'before_file_sha256':sha(raw),'before_document':doc})
        for e in doc['entries']:
            value,sources=draft(e,cat)
            records.append({'id':e['id'],'category':cat,'path':str(p.relative_to(ROOT)),'old_background':e['background'],'old_card_sha256':sha(canonical(e)),'non_background_sha256':sha(canonical({k:v for k,v in e.items() if k!='background'})),'new_background':value,'source_fields':sources,'raw_source_evidence':[],'transformation_notes':[],'semantic_l1_status':'PENDING_INDEPENDENT_FULL_INVENTORY_REVIEW'})
assert len(records)==982 and len({r['id'] for r in records})==982
out={'claim':'Source-grounded background draft, not an L1 quality verdict; all original card data preserved in audit preimages.','files':files,'records':records}
(OUT/'knowledge-context-draft.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'draft_records':len(records),'category_files':len(files),'path':str(OUT/'knowledge-context-draft.json')},ensure_ascii=False))
