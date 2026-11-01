"""Trusted runner hook: source-check Bash must succeed in this actor before Read.

Only a provided written-source document is guarded. No specification, report,
verdict, or graph is generated. The helper command checks path/file/hash only.
"""
from pathlib import Path
import hashlib,json,os,shlex,sys,tempfile

CODE = "from pathlib import Path;import hashlib,json,sys;r=Path(sys.argv[1]).resolve(strict=True);p=(r/sys.argv[2]).resolve(strict=True);p.relative_to(r);assert p.is_file();print(json.dumps({'written_source_checked':True,'root':str(r),'path':sys.argv[2],'real_path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},sort_keys=True))"
PYTHON = '/Users/dm/miniconda3/bin/python3'
def command(root,relative):
    return PYTHON+' -I -B -c '+shlex.quote(CODE)+' '+shlex.quote(str(root))+' '+shlex.quote(relative)
def prefix(root):
    return 'export CLAUDE_PROJECT_DIR="'+str(root)+'" && cd -- "$CLAUDE_PROJECT_DIR" && [ "$(pwd -P)" = "$CLAUDE_PROJECT_DIR" ] && '
def sha(data):return hashlib.sha256(data).hexdigest()
def actor(data):
    sid=data.get('session_id')
    if not isinstance(sid,str) or not sid:raise ValueError('native session_id missing')
    aid=data.get('agent_id') or 'main'
    if not isinstance(aid,str):raise ValueError('native agent_id invalid')
    return sid,aid
def proof_path(cfg,data,relative):
    sid,aid=actor(data)
    return Path(cfg['proof_dir'])/(sha((sid+'\0'+aid+'\0'+relative).encode())+'.json')
def current(root,relative):
    p=(root/relative).resolve(strict=True)
    p.relative_to(root)
    if not p.is_file():raise ValueError('written source is not a regular file')
    return {'written_source_checked':True,'root':str(root),'path':relative,'real_path':str(p),'sha256':sha(p.read_bytes())}
def record_event(cfg,entry):
    path=Path(cfg['proof_dir'])/'events.jsonl'
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
def check(cfg,data,stage):
    root=Path(cfg['root']).resolve(strict=True);tool=data.get('tool_name')
    ti=data.get('tool_input') or {}
    if not isinstance(ti,dict):return None
    rel=cfg['source_path'];cmd=command(root,rel)
    allowed=[cmd,prefix(root)+cmd]
    if stage=='post' and tool=='Bash' and ti.get('command') in allowed:
        response=data.get('tool_response')
        record_event(cfg,{'stage':'post-shape','tool_use_id':data.get('tool_use_id'),'response_type':type(response).__name__,'response_keys':list(response) if isinstance(response,dict) else []})
        out=response.get('stdout') if isinstance(response,dict) else None
        if not isinstance(response,dict) or response.get('interrupted') is not False:return None
        if not isinstance(out,str):return None
        try:observed=json.loads(out.strip());expected=current(root,rel)
        except (ValueError,OSError):return None
        if observed!=expected:return None
        sid,aid=actor(data)
        proof={'session_id':sid,'agent_id':aid,'tool_use_id':data.get('tool_use_id'),
               'command_sha256':sha(ti['command'].encode()),'stdout_sha256':sha(out.encode()),
               'checked':expected}
        path=proof_path(cfg,data,rel)
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix=path.stem+'.',suffix='.tmp',delete=False) as f:
            temp=Path(f.name)
            f.write(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
        try:os.replace(temp,path)
        finally:temp.unlink(missing_ok=True)
        record_event(cfg,{'stage':'bash-verified','proof':path.name,**proof})
        return None
    if stage!='pre' or tool!='Read':return None
    target=ti.get('file_path')
    if not isinstance(target,str) or not target:return None
    lexical=Path(os.path.abspath(os.path.join(data.get('cwd') or str(root),target)))
    configured=Path(os.path.abspath(root/rel))
    try:same_real=lexical.resolve()==configured.resolve()
    except OSError:same_real=False
    if lexical!=configured and not same_real:return None
    try:
        expected=current(root,rel)
        resolved=lexical.resolve(strict=True);resolved.relative_to(root)
        if resolved!=Path(expected['real_path']):raise ValueError('source identity differs')
        path=proof_path(cfg,data,rel)
        proof=json.loads(path.read_text())
        sid,aid=actor(data)
        if proof.get('session_id')!=sid or proof.get('agent_id')!=aid or proof.get('checked')!=expected:
            raise ValueError('proof missing, foreign, or stale')
    except (OSError,ValueError):
        record_event(cfg,{'stage':'read-denied','session_id':data.get('session_id'),'agent_id':data.get('agent_id'),'tool_use_id':data.get('tool_use_id'),'path':target})
        return ('R6の必須順序: この書面をReadする前に、同じcontextでpath containment/実在/SHAをBashで確認してください。'
                '次の読取専用コマンドをそのまま実行して成功後にReadを再試行できます。'
                'main contextだけは既存の固定root前置きを付け、C06はこのPython確認だけを実行します。\n'+cmd)
    record_event(cfg,{'stage':'read-allowed','session_id':data.get('session_id'),'agent_id':data.get('agent_id'),'tool_use_id':data.get('tool_use_id'),'proof':path.name,'checked':expected})
    return None
if __name__=='__main__':
    cfg=json.loads(Path(sys.argv[1]).read_text());stage=sys.argv[2]
    assert stage in ['pre','post']
    Path(cfg['proof_dir']).mkdir(parents=True,exist_ok=True)
    try:reason=check(cfg,json.load(sys.stdin),stage)
    except Exception as e:
        print('written source guard failed closed: '+type(e).__name__,file=sys.stderr)
        raise SystemExit(2)
    if reason:print(reason,file=sys.stderr);raise SystemExit(2)
