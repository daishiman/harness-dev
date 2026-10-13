"""Read-only migration provenance/invariant verification; deliberately no semantic L1 score."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
import jsonschema
ROOT=Path(__file__).resolve().parents[5]
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(a,check_current=True):
    errors=[];before={};after={};expected=[]
    for f in a['files']:
        bd=f['before_document'];ad=f['after_document'];bp=copy.deepcopy(bd);ap=copy.deepcopy(ad)
        if len(bd['entries'])!=len(ad['entries']):errors.append('entry count changed '+f['path'])
        for e in bp['entries']:e.pop('background',None)
        for e in ap['entries']:e.pop('background',None)
        if bp!=ap:errors.append('non-background document fields changed '+f['path'])
        if digest(bd)!=f['before_document_sha256'] or digest(ad)!=f['after_document_sha256']:errors.append('document snapshot digest mismatch '+f['path'])
        if check_current and file_sha(ROOT/f['path'])!=f['after_file_sha256']:errors.append('current file differs from frozen background-stage snapshot '+f['path'])
        before.update({e['id']:e for e in bd['entries']});after.update({e['id']:e for e in ad['entries']});expected.extend(e['id'] for e in bd['entries'])
    if len(expected)!=len(set(expected)) or len(expected)!=a['actual_records']:errors.append('duplicate/incorrect actual record inventory')
    if {r['id'] for r in a['records']}!=set(expected) or len(a['records'])!=len(expected):errors.append('audit record inventory mismatch')
    for r in a['records']:
        e=before.get(r['id']);ae=after.get(r['id'])
        if e is None or ae is None:continue
        if e['background']!=r['old_background'] or ae['background']!=r['new_background']:errors.append('background receipt mismatch '+r['id'])
        if digest(e)!=r['old_card_sha256'] or digest(ae)!=r['new_card_sha256']:errors.append('card digest mismatch '+r['id'])
        nb={k:v for k,v in e.items() if k!='background'};na={k:v for k,v in ae.items() if k!='background'}
        if nb!=na or digest(nb)!=r['non_background_sha256']:errors.append('non-background invariant failed '+r['id'])
        for s in r['source_fields']:
            if e.get(s['field'])!=s['source_value'] or hashlib.sha256(s['source_value'].encode()).hexdigest()!=s['source_value_sha256']:errors.append('original field evidence mismatch '+r['id'])
            if s['exact_excerpt'] and s['selected_excerpt'] not in s['source_value']:errors.append('false verbatim excerpt '+r['id'])
        for s in r['raw_source_evidence']:
            p=ROOT/s['path'];lines=p.read_text().splitlines();quote='\n'.join(lines[s['line_start']-1:s['line_end']])
            if file_sha(p)!=s['file_sha256'] or quote!=s['quote'] or hashlib.sha256(quote.encode()).hexdigest()!=s['quote_sha256']:errors.append('raw source evidence mismatch '+r['id'])
    if check_current:
        router=json.loads((ROOT/'plugins/ubm-goal-setting/knowledge/router.json').read_text());paths={str(Path('plugins/ubm-goal-setting/knowledge')/fn) for cfg in router['categories'].values() for fn in cfg['files']}
        if paths!={f['path'] for f in a['files']}:errors.append('current router category inventory changed')
        schema=json.loads((ROOT/'plugins/ubm-goal-setting/knowledge/schema.json').read_text())['knowledge_entry_schema'];v=jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker())
        for f in a['files']:
            for err in v.iter_errors(json.loads((ROOT/f['path']).read_text())):errors.append('nested schema '+f['path']+': '+err.message)
    return errors
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('artifact',type=Path);args=p.parse_args();a=json.loads(args.artifact.read_text());errs=audit(a)
    print(json.dumps({'actual_records':a['actual_records'],'category_files':len(a['files']),'errors':errs,'semantic_quality_awarded':False},ensure_ascii=False));sys.exit(bool(errs))
