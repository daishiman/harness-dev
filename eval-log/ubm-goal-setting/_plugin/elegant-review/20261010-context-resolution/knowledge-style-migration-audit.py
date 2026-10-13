"""Read-only full-inventory conservation and source-receipt audit; no semantic verdict."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
import jsonschema
ROOT=Path(__file__).resolve().parents[5]
def sha(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def file_sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(a,current=True):
    errors=[];before={};after={};ids=[]
    for f in a['files']:
        b=f['before_document'];n=f['after_document']
        if sha(b)!=f['before_document_sha256'] or sha(n)!=f['after_document_sha256']:errors.append('file snapshot digest '+f['path'])
        if len(b['entries'])!=len(n['entries']):errors.append('count changed '+f['path'])
        if {k:v for k,v in b.items() if k!='entries'}!={k:v for k,v in n.items() if k!='entries'}:errors.append('file metadata changed '+f['path'])
        if [e['id'] for e in b['entries']]!=[e['id'] for e in n['entries']]:errors.append('entry order/identity changed '+f['path'])
        before.update({e['id']:e for e in b['entries']});after.update({e['id']:e for e in n['entries']});ids.extend(e['id'] for e in b['entries'])
        if current and file_sha(ROOT/f['path'])!=f['after_file_sha256']:errors.append('current byte mismatch '+f['path'])
    if len(ids)!=len(set(ids)) or len(ids)!=a['actual_records'] or len(a['records'])!=len(ids) or {r['id'] for r in a['records']}!=set(ids):errors.append('inventory mismatch')
    for r in a['records']:
        b=before.get(r['id']);n=after.get(r['id'])
        if b is None or n is None:continue
        core='title' if b.get('title') else 'content';intent='intent' if 'intent'in b else 'purpose'
        if r['core_field']!=core or r['intent_field']!=intent:errors.append('field precedence mismatch '+r['id'])
        allowed={core,intent}
        if {k:v for k,v in b.items() if k not in allowed}!={k:v for k,v in n.items() if k not in allowed}:errors.append('non-style fields changed '+r['id'])
        if set(b)!=set(n):errors.append('field addition/removal '+r['id'])
        if b!=r['old_card'] or n!=r['new_card'] or sha(b)!=r['old_card_sha256'] or sha(n)!=r['new_card_sha256']:errors.append('card receipt mismatch '+r['id'])
        for field in allowed:
            if b[field]!=r['old_values'][field] or n[field]!=r['new_values'][field]:errors.append('style value receipt mismatch '+r['id'])
        for receipt in r['source_fields']:
            field=receipt['field'];value=receipt['value']
            if b.get(field)!=value or sha(value)!=receipt['value_sha256']:errors.append('source field forgery '+r['id'])
        if sha({k:v for k,v in b.items() if k not in allowed})!=r['unchanged_fields_sha256']:errors.append('unchanged field hash '+r['id'])
    g=a.get('graph')
    if g:
        b=copy.deepcopy(g['before_document']);n=copy.deepcopy(g['after_document'])
        if sha(b)!=g['before_document_sha256'] or sha(n)!=g['after_document_sha256']:errors.append('graph snapshot digest')
        for graph in [b,n]:
            for node in graph['nodes']:node.pop('title',None)
        if b!=n:errors.append('non-title graph data changed')
        for node in g['after_document']['nodes']:
            if node['title']!=after[node['id']].get('title',''):errors.append('graph/source title mismatch '+node['id'])
        if current and file_sha(ROOT/g['path'])!=g['after_file_sha256']:errors.append('current graph bytes mismatch')
    if current:
        schema=json.loads((ROOT/'plugins/ubm-goal-setting/knowledge/schema.json').read_text())['knowledge_entry_schema']
        v=jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker())
        for f in a['files']:
            for err in v.iter_errors(json.loads((ROOT/f['path']).read_text())):errors.append('nested schema '+f['path']+': '+err.message)
    return errors
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('artifact',type=Path);args=p.parse_args();a=json.loads(args.artifact.read_text());errors=audit(a)
    print(json.dumps({'actual_records':a['actual_records'],'category_files':len(a['files']),'errors':errors,'semantic_quality_awarded':False},ensure_ascii=False));sys.exit(bool(errors))
