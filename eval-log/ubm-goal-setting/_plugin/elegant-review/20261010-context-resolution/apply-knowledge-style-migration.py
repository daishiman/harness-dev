"""User-authorized card style-only migration, with preflight and full conservation receipts.

This script is audit-specific and is run only after independent draft findings are resolved.
It never computes a semantic rubric PASS.
"""
import copy,datetime,hashlib,importlib.util,json,os,tempfile
from pathlib import Path
import jsonschema
ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
KB=ROOT/'plugins/ubm-goal-setting/knowledge'
def sha(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def bytes_sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def module(p,name):
    sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def write_atomic(p,data):
    fd,name=tempfile.mkstemp(prefix=p.name+'.style-',dir=p.parent)
    try:
        with os.fdopen(fd,'w')as f:f.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        os.replace(name,p)
    finally:
        if Path(name).exists():Path(name).unlink()
def main():
    draft_path=HERE/'knowledge-style-draft.json';pr_path=HERE/'knowledge-core-pr-draft.json'
    d=json.loads(draft_path.read_text());pr=json.loads(pr_path.read_text());pr_by={r['id']:r for r in pr['records']};draft_by={r['id']:r for r in d['records']}
    assert len(draft_by)==len(d['records'])==d['actual_records']
    router=json.loads((KB/'router.json').read_text());files=[];records=[];schema_path=KB/'schema.json'
    v=jsonschema.Draft202012Validator(json.loads(schema_path.read_text())['knowledge_entry_schema'],format_checker=jsonschema.FormatChecker())
    for cat,cfg in router['categories'].items():
        for name in cfg['files']:
            p=KB/name;b=json.loads(p.read_text());n=copy.deepcopy(b)
            f={'path':str(p.relative_to(ROOT)),'before_file_sha256':bytes_sha(p),'before_document':b,'before_document_sha256':sha(b),'after_document':n}
            for i,e in enumerate(b['entries']):
                dr=draft_by[e['id']];core='title'if e.get('title')else'content';intent='intent'if'intent'in e else'purpose'
                if cat=='principles':
                    cr=pr_by[e['id']];assert cr['field']==core and cr['old_value']==e[core],e['id'];new_core=cr['new_value'];notes=cr['notes']
                else:
                    assert dr['core_field']==core and dr['old_core']==e[core],e['id'];new_core=dr['new_core'];notes=dr['notes']
                assert dr['intent_field']==intent and dr['old_intent']==e[intent],e['id']
                ne=n['entries'][i];ne[core]=new_core;ne[intent]=dr['new_intent']
                allowed={core,intent};nb={k:val for k,val in e.items()if k not in allowed};assert nb=={k:val for k,val in ne.items()if k not in allowed}
                rec={'id':e['id'],'category':cat,'path':f['path'],'core_field':core,'intent_field':intent,'old_card':e,'new_card':ne,'old_card_sha256':sha(e),'new_card_sha256':sha(ne),'old_values':{k:e[k]for k in allowed},'new_values':{k:ne[k]for k in allowed},'unchanged_fields_sha256':sha(nb),'source_fields':[{'field':k,'value':val,'value_sha256':sha(val)}for k,val in e.items()if k not in ['background','tags','related']],'notes':notes,'semantic_status':'PENDING_CURRENT_SOURCE_INDEPENDENT_RECONCILIATION'}
                records.append(rec)
            assert not list(v.iter_errors(n)),p
            f['after_document_sha256']=sha(n);files.append(f)
    assert len(records)==len(d['records'])and{r['id']for r in records}==set(draft_by)
    # Verify the entire current corpus before the first write; other owners' changes are fresh preimages.
    for f in files:assert bytes_sha(ROOT/f['path'])==f['before_file_sha256'],f['path']
    graph_path=KB/'knowledge-graph.json';gb=json.loads(graph_path.read_text());gn=copy.deepcopy(gb);cards={r['id']:r['new_card']for r in records}
    for node in gn['nodes']:node['title']=cards[node['id']].get('title','')
    graph={'path':str(graph_path.relative_to(ROOT)),'before_file_sha256':bytes_sha(graph_path),'before_document':gb,'before_document_sha256':sha(gb),'after_document':gn,'after_document_sha256':sha(gn),'changed_node_titles':[{'id':b['id'],'old_title':b['title'],'new_title':n['title']}for b,n in zip(gb['nodes'],gn['nodes'])if b['title']!=n['title']]}
    assert [x['id']for x in gb['nodes']]==[x['id']for x in gn['nodes']]
    gv=module(ROOT/'plugins/ubm-goal-setting/scripts/validate-knowledge-graph.py','style_graph_validator')
    # Prevalidate the complete candidate corpus, including graph equality, before any production write.
    with tempfile.TemporaryDirectory(prefix='ubm-style-validation-')as tmp:
        staged=Path(tmp)
        for f in files:(staged/Path(f['path']).name).write_text(json.dumps(f['after_document'],ensure_ascii=False))
        nodes,errors=gv.load_entries(staged);assert not errors,errors
        edges,status,errors=gv.load_relations(KB/gv.RELATIONS_FILENAME);assert not errors,errors
        canonical,errors=gv.validate_edges(edges,{n['id']for n in nodes});assert not errors,errors
        assert gv.detect_cycle(canonical)is None
        associations,dropped=gv.build_associations(nodes,staged,{n['id']for n in nodes})
        assert gv.build_graph(nodes,canonical,associations)==gn,'candidate graph changes non-title data'
    for f in files:
        if f['before_document']!=f['after_document']:write_atomic(ROOT/f['path'],f['after_document'])
        f['after_file_sha256']=bytes_sha(ROOT/f['path'])
    # Use production validators purely in memory. The expected synchronization is title-only.
    nodes,errors=gv.load_entries(KB);assert not errors,errors
    edges,status,errors=gv.load_relations(KB/gv.RELATIONS_FILENAME);assert not errors,errors
    canonical,errors=gv.validate_edges(edges,{n['id']for n in nodes});assert not errors,errors
    assert gv.detect_cycle(canonical)is None
    associations,dropped=gv.build_associations(nodes,KB,{n['id']for n in nodes})
    expected=gv.build_graph(nodes,canonical,associations);assert expected==gn,'graph regeneration differs beyond truthful title synchronization'
    assert bytes_sha(graph_path)==graph['before_file_sha256']
    if gb!=gn:write_atomic(graph_path,gn)
    graph['after_file_sha256']=bytes_sha(graph_path)
    artifact={'scope':'Supplemental approved core/intent grammatical repair, preserving previous review histories','applied_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actual_records':len(records),'category_files':len(files),'core_changes':sum(r['old_values'][r['core_field']]!=r['new_values'][r['core_field']]for r in records),'intent_changes':sum(r['old_values'][r['intent_field']]!=r['new_values'][r['intent_field']]for r in records),'draft_sha256':bytes_sha(draft_path),'pr_draft_sha256':bytes_sha(pr_path),'schema_sha256':bytes_sha(schema_path),'files':files,'records':records,'graph':graph,'semantic_quality_awarded_by_script':False,'nested_schema_pass':True,'all_other_fields_preserved':True}
    av=module(HERE/'knowledge-style-migration-audit.py','style_audit');errors=av.audit(artifact);assert not errors,errors
    fixtures=[]
    for kind in ['background_mutation','tag_mutation','source_forgery','missing_inventory_record','graph_edge_mutation']:
        bad=copy.deepcopy(artifact)
        if kind=='background_mutation':bad['files'][0]['after_document']['entries'][0]['background']='fabricated'
        elif kind=='tag_mutation':bad['files'][0]['after_document']['entries'][0]['tags'].append('fabricated')
        elif kind=='source_forgery':bad['records'][0]['source_fields'][0]['value']='fabricated'
        elif kind=='missing_inventory_record':bad['records'].pop()
        else:bad['graph']['after_document']['edges'].append({'source_id':'fabricated'})
        rejected=av.audit(bad,current=False);assert rejected,kind
        fixtures.append({'fixture':kind,'rejected':True,'observed_errors':rejected[:3]})
    artifact['audit_validation']={'errors':[],'negative_fixtures':fixtures,'non_style_field_differences':0,'current_full982_checked':True,'graph_title_only_checked':True}
    out=HERE/'knowledge-style-migration.json';out.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'actual_records':len(records),'core_changes':artifact['core_changes'],'intent_changes':artifact['intent_changes'],'graph_title_changes':len(graph['changed_node_titles']),'audit_errors':[],'artifact_sha256':bytes_sha(out),'semantic_quality_awarded':False}))
if __name__=='__main__':main()
