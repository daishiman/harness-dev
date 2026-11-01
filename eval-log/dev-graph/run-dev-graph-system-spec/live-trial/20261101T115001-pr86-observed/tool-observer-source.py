"""実エンジンI/Oを当該runの検証者へ複写する。実装処理・判定は実行しない。"""
from pathlib import Path
import hashlib,json,sys,time,re,os,stat,uuid
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt')
MARKER='harness-native-event-mirror-v2'

def observer_io(call,result,observer_path,project_root):
    observed=os.path.realpath(observer_path)
    if call['name']=='Read':
        path=call['input'].get('file_path','')
        if isinstance(path,str) and path:
            resolved=os.path.realpath(path if os.path.isabs(path) else os.path.join(project_root or '/',path))
            if resolved==observed or resolved.startswith(observed+os.sep):return True
    aliases={observer_path,observer_path.replace('/private/tmp/','/tmp/',1),observer_path.replace('/tmp/','/private/tmp/',1) if not observer_path.startswith('/private/tmp/') else observer_path}
    text=json.dumps(call['input'],ensure_ascii=False)
    if MARKER in text or any(x in text for x in aliases):return True
    return MARKER in json.dumps(result,ensure_ascii=False)


def extract(raw,stream,session_id,observer_path,project_root=None):
    calls={};results={};injections=[];ambiguous=set();bad_uuids=set();seen={};h=hashlib.sha256();count=0
    for lineno,line in enumerate(raw.splitlines(keepends=True),1):
        if not line.endswith(b'\n'):break
        h.update(line);count+=len(line)
        try:x=json.loads(line)
        except (ValueError,UnicodeError):continue
        if x.get('type') not in ('assistant','user'):continue
        uid=x.get('uuid')
        if not uid:continue
        signature=json.dumps(x.get('message'),ensure_ascii=False,sort_keys=True)
        if uid in seen:
            if seen[uid]!=signature:
                bad_uuids.add(uid)
                for b in x.get('message',{}).get('content',[]):
                    if isinstance(b,dict):ambiguous.add(b.get('id',b.get('tool_use_id','')))
            continue
        seen[uid]=signature;c=x.get('message',{}).get('content',[])
        if isinstance(c,str):c=[{'type':'text','text':c}]
        if not isinstance(c,list):continue
        source={'uuid':uid,'line':lineno,'prefix_bytes':count,'prefix_sha256':h.hexdigest(),'timestamp':x.get('timestamp')}
        for b in c:
            if not isinstance(b,dict):continue
            if b.get('type')=='tool_use' and b.get('name') in ('Read','Bash','Skill'):
                ident=b['id'];call={'name':b['name'],'input':b.get('input',{}),'source':source}
                if ident in calls:ambiguous.add(ident)
                else:calls[ident]=call
            elif b.get('type')=='tool_result':
                ident=b.get('tool_use_id');result={'content':b.get('content'),'is_error':b.get('is_error',False),'native_result':x.get('toolUseResult'),'source':source}
                if ident in results:ambiguous.add(ident)
                else:results[ident]=result
        text='\n'.join(b.get('text','') for b in c if isinstance(b,dict) and b.get('type')=='text')
        if x['type']=='user' and text.startswith('Base directory for this skill:'):
            injections.append((x,text,source))
    events={}
    for ident,call in calls.items():
        if ident in ambiguous or ident not in results:continue
        result=results[ident]
        if call['source']['uuid'] in bad_uuids or result['source']['uuid'] in bad_uuids:continue
        if result['source']['line']<=call['source']['line']:continue
        if observer_io(call,result,observer_path,project_root):continue
        events[ident]={'observer_projection_id':MARKER,'schema_version':2,'session_id':session_id,'stream':stream,'kind':'tool_call','source':{'assistant':call['source'],'result':result['source']},'tool_use_id':ident,'tool_name':call['name'],'tool_input':call['input'],'is_error':result['is_error'],'tool_result_content':result['content'],'tool_use_result':result['native_result']}
    for x,text,source in injections:
        ident=x.get('sourceToolUseID');pair=events.get(ident)
        if not pair or pair['tool_name']!='Skill' or pair['is_error']:continue
        native=pair['tool_use_result']
        if not isinstance(native,dict) or native.get('success') is not True:continue
        if native.get('commandName')!=pair['tool_input'].get('skill'):continue
        if source['uuid'] in bad_uuids or source['line']<=pair['source']['result']['line']:continue
        if x.get('isMeta') is not True or x.get('turnCompanion') is not True:continue
        if x.get('parentUuid')!=pair['source']['result']['uuid']:continue
        if observer_path in text:continue
        skill=pair['tool_input'].get('skill','')
        if ':' not in skill or project_root is None:continue
        plugin,name=skill.split(':',1)
        if not re.fullmatch('[a-z0-9-]+',plugin) or not re.fullmatch('[a-z0-9-]+',name):continue
        actual=text.splitlines()[0].partition(': ')[2]
        expected=str(Path(project_root)/'plugins'/plugin/'skills'/name)
        if actual!=expected:continue
        events['prompt-'+source['uuid']]={'observer_projection_id':MARKER,'schema_version':2,'session_id':session_id,'stream':stream,'kind':'skill_body_injection','source':source,'source_tool_use_id':ident,'parent_result_uuid':x['parentUuid'],'text':text}
    return events

def open_directory(path,create_leaf=False):
    """全componentをNOFOLLOWで開く。被験側symlinkをhost権限で辿らない。"""
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts:raise ValueError('absolute anchored path required')
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW;fd=os.open('/',flags)
    try:
        for i,name in enumerate(path.parts[1:]):
            try:new=os.open(name,flags,dir_fd=fd)
            except FileNotFoundError:
                if not create_leaf or i!=len(path.parts)-2:raise
                try:os.mkdir(name,0o700,dir_fd=fd)
                except FileExistsError:pass
                new=os.open(name,flags,dir_fd=fd)
            os.close(fd);fd=new
        return fd
    except BaseException:os.close(fd);raise

def write_json(path,obj):
    data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();path=Path(path);fd=open_directory(path.parent);temp='._observer-'+uuid.uuid4().hex+'.tmp';created=False
    try:
        try:
            target=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
            if not stat.S_ISREG(target.st_mode):raise ValueError('observer target must be regular file')
        except FileNotFoundError:pass
        f=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd);created=True
        with os.fdopen(f,'wb') as stream:stream.write(data)
        os.replace(temp,path.name,src_dir_fd=fd,dst_dir_fd=fd);created=False
    finally:
        if created:
            try:os.unlink(temp,dir_fd=fd)
            except FileNotFoundError:pass
        os.close(fd)

def scan(sid,out,project_root):
    mains=list((T/'home/.claude/projects').glob('*/'+sid+'.jsonl'))
    if len(mains)!=1:return 0
    main=mains[0];files=[('main',main)]+[('subagent/'+p.stem,p) for p in sorted((main.with_suffix('')/'subagents').glob('*.jsonl'))]
    fd=open_directory(out,create_leaf=True);os.close(fd);index=[]
    for stream,p in files:
        if p.is_symlink():raise ValueError('native source stream symlink refused')
        events=extract(p.read_bytes(),stream,sid,str(out),project_root)
        for ident,e in events.items():
            name=re.sub('[^A-Za-z0-9_.-]','_',stream+'-'+ident)+'.json';write_json(out/name,e)
            a=e['source'].get('assistant',e['source']);summary={'stream':stream,'kind':e['kind'],'file':name,'source_line':a['line'],'source_prefix_sha256':a['prefix_sha256']}
            if e['kind']=='tool_call':summary.update(tool_name=e['tool_name'],tool_use_id=e['tool_use_id'],is_error=e['is_error'],input_summary=json.dumps(e['tool_input'],ensure_ascii=False)[:240])
            else:summary['text_start']=e['text'][:180]
            index.append(summary)
    write_json(out/'index.json',{'observer_projection_id':MARKER,'schema_version':2,'observer':'trusted host-side native transcript projection; not model attestation','session_id':sid,'events':index,'policy':'only current index entries are valid; api-request blobs/thinking/summary/Agent outputs excluded; genuine Skill injection must bind native metadata and complete successful Skill pair; observer reads excluded; no workflow decisions executed'})
    return len(index)

def main():
    label,sid=sys.argv[1:3];assert re.fullmatch('[a-z0-9]+',label);assert re.fullmatch('[0-9a-f-]{36}',sid)
    r=T/'runs'/label;out=r/'workdir/tool-observer';stop=r/'workdir/observer-stop'
    while True:
        n=scan(sid,out,str(r/'fx'))
        if stop.exists():print('observer stopped',label,n,flush=True);break
        time.sleep(3)
if __name__=='__main__':main()
