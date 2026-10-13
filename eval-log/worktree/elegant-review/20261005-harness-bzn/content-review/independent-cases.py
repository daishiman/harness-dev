"""Independent approver cases: repository sources read afresh, writes only temporary fixtures.

Run with /Users/dm/miniconda3/bin/python3; no remote or working-repository Git calls.
"""
from pathlib import Path
import argparse, copy, importlib.util, itertools, json, os, subprocess, sys, tempfile, traceback
from unittest import mock

ROOT = Path('/Users/dm/dev/dev/個人開発/harness')
DG = ROOT / 'plugins/dev-graph'
SS = ROOT / 'plugins/system-spec-harness'
HC = ROOT / 'plugins/harness-creator'
sys.dont_write_bytecode = True
sys.path.insert(0, str(DG / 'scripts'))
sys.path.insert(0, str(DG / 'tests'))

def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

issues = load('plugins/dev-graph/scripts/diff-github-issues.py', 'approver_issues')
projects = load('plugins/dev-graph/scripts/diff-github-project-fields.py', 'approver_projects')
common = load('plugins/dev-graph/scripts/_common.py', 'approver_common')
init = load('plugins/dev-graph/scripts/build-init-scaffold.py', 'approver_init')
guard = load('plugins/system-spec-harness/hooks/guard-confirmed-chapter-overwrite.py', 'approver_guard')
writer = load('plugins/system-spec-harness/skills/run-system-spec-elicit/scripts/apply-spec-transition.py', 'approver_writer')
resolver = load('scripts/extract-plugin-root.py', 'approver_resolver')
ci = load('scripts/extract-ci-workflow-steps.py', 'approver_ci')
lint = load('scripts/lint-sibling-plugin-paths.py', 'approver_lint')
resources = load('plugins/harness-creator/scripts/plugin_resources.py', 'approver_resources')
import test_build_graph_node as graph_fixture
import test_register_package as package_fixture

results = []
def case(name, finding, fn):
    try:
        detail = fn()
        results.append({'case':name,'finding_ids':finding,'result':'PASS','detail':detail})
    except Exception as exc:
        results.append({'case':name,'finding_ids':finding,'result':'FAIL','error':repr(exc),'trace':traceback.format_exc()})

STAMP = '2026-07-13T00:00:00Z'
def issue_node():
    node = package_fixture.task_node(0)
    node.update(parent_feature=None,feature_package_id=None,phase_ref=None,tracker_binding='github',priority='medium')
    node['github_publication']['mode']='issue'
    node['issue_linkage']={'repo':'acme/web','issue_number':12,'issue_url':'https://github.com/acme/web/issues/12','linked_at':node['updated_at']}
    return node

def project_case(values):
    node=issue_node(); node.pop('issue_linkage')
    config={'projects':[]}; remote={'projects':{}}; links=[]
    for index,value in enumerate(values):
        alias=chr(97+index)
        project=copy.deepcopy(graph_fixture.ROADMAP)
        project.update(alias=alias,default=index==0,project_number=7+index)
        project['field_mappings']=project['field_mappings'][1:]
        config['projects'].append(project)
        links.append(graph_fixture.roadmap_link(project_alias=alias,project_number=7+index,project_id='PVT_'+alias,item_id='PVTI_'+alias,sync_state='synced',field_snapshot={'priority':'P2'}))
        data=graph_fixture.roadmap_remote(priority=value)['projects']['roadmap']
        data.update(id='PVT_'+alias,items={'PVTI_'+alias:{'Priority':value}})
        remote['projects'][alias]=data
    node['github_project_linkages']=links
    return {'graph_revision':1,'nodes':[node]},config,remote

def three_way_join():
    graph,config,remote=project_case(['P1','P1','P3'])
    baseline=None
    for order in itertools.permutations(graph['nodes'][0]['github_project_linkages']):
        fresh=copy.deepcopy(graph); fresh['nodes'][0]['github_project_linkages']=list(order)
        report=projects.plan(fresh,config,remote,{},STAMP)
        assert report['imports']==[] and report['update_input'] is None and report['link_input'] is None
        assert len(report['conflicts'])==3 and report['converged'] is False
        if baseline is None: baseline=report['conflicts']
        assert report['conflicts']==baseline
    return 'All six permutations: 3 conflicting origins, no C02 patch or snapshot write.'
case('three_project_order_invariance',['F-0001'],three_way_join)

def equal_join():
    graph,config,remote=project_case(['P1','P1','P1'])
    report=projects.plan(graph,config,remote,{},STAMP)
    assert report['counts']['imports']==1 and report['imports'][0]['source_projects']==['a','b','c']
    assert report['update_input']['updates'][0]['node_patch']=={'priority':'high'}
    return 'Three equal imports collapse to one semantic update and retain all origins.'
case('three_equal_project_origins',['F-0001'],equal_join)

def unresolved_cases():
    node=issue_node(); graph={'graph_revision':1,'nodes':[node]}
    variants=[{'issues':{}},{'issues':{'acme/web#12':{'title':'different','state':'open','updated_at':None}}},
              {'issues':{'acme/web#12':{'title':'different','state':'open','updated_at':node['updated_at']}}}]
    for remote in variants:
        r=issues.plan(graph,{},remote,{})
        assert r['changes']==0 and r['unresolved_count']>0 and not r['converged'] and r['next']!='converged'
    graph,config,remote=project_case(['P1','P3'])
    for mutation in ['missing','skip','held']:
        fresh=copy.deepcopy(graph)
        if mutation=='skip':
            for link in fresh['nodes'][0]['github_project_linkages']:link['sync_state']='pending_retry'
        elif mutation=='held': fresh['nodes'][0]['issue_linkage']={'issue_number':12}
        r=projects.plan(fresh,config,{'projects':{}} if mutation=='missing' else remote,{},STAMP)
        assert r['changes']==0 and r['unresolved_count']>0 and not r['converged'] and r['next']!='converged'
    empty=issues.plan({'graph_revision':1,'nodes':[]},{},{'issues':{}},{})
    assert empty['converged'] and empty['unresolved_count']==0
    return 'Missing Issue, bad timestamp, same-time flag, missing/skip/held Projects are nonterminal; empty control converges.'
case('unresolved_is_never_converged',['F-0004'],unresolved_cases)

def heartbeat_authority():
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw);node=issue_node();graph={'graph_revision':5,'nodes':[node]}
        (root/'graph.json').write_text(json.dumps(graph))
        remote={'issues':{'acme/web#12':{'title':'remote edit','state':'open','updated_at':'2026-07-13T00:01:00Z'}}}
        before=issues.plan(graph,{},remote,{})
        context=package_fixture.RegisterPackageInProcessCoverageTest.execution_context(seen='2026-07-13T00:03:00Z')
        args=package_fixture.RP._parser().parse_args(['execution-context','--repo-root',str(root),'--graph','graph.json','--graph-node-id',node['graph_node_id'],'--context-json',json.dumps(context)])
        package_fixture.RP._project_execution_context(args)
        changed=json.loads((root/'graph.json').read_text()); after=issues.plan(changed,{},remote,{})
        assert before['imports']==after['imports'] and after['exports']==[]
        assert changed['nodes'][0]['updated_at']==node['updated_at'] and changed['graph_revision']==6
        assert changed['nodes'][0]['execution_contexts'][0]['last_seen_at']==context['last_seen_at']
    return 'A later context heartbeat advances graph revision but cannot win content timestamp comparison.'
case('heartbeat_is_coordination_not_content',['F-0002'],heartbeat_authority)

def atomic_contracts():
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); target=root/'receipt.json';target.write_bytes(b'original')
        try:common.atomic_json(target,{'changed':True},create_only=True)
        except FileExistsError:pass
        else:raise AssertionError('create-only overwrite')
        assert target.read_bytes()==b'original' and list(root.iterdir())==[target]
        common.atomic_bytes(target,b'replaced');assert target.read_bytes()==b'replaced'
        for fn,error in [(lambda:init._create_file(target,b'x'),init.InitError),
                         (lambda:graph_fixture.BGN._write_atomic(target,b'x',create_only=True),graph_fixture.BGN.WriterError),
                         (lambda:package_fixture.RP._atomic_create_json(target,{}),Exception)]:
            try:fn()
            except error:pass
            else:raise AssertionError('domain caller overwrote receipt')
        assert target.read_bytes()==b'replaced'
    return 'Shared primitive maintains replace/create-only contracts; three callers keep immutable existing bytes.'
case('shared_io_preserves_authority',['F-0005'],atomic_contracts)

def init_restore():
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw);existing=root/'.dev-graph/state/preexisting';existing.mkdir(parents=True)
        (existing/'keep').write_bytes(b'existing')
        example=json.loads((DG/'templates/repo-config.example.json').read_text())
        ctx={'repo_root':str(root),'repository_id':'local:sha256:'+'a'*64,
             'content_roots':{'repository':str(root),**{k:str(root/v) for k,v in example['content_roots'].items()}},
             'local_state_paths':{'config':str(root/'.dev-graph/config.json'),**{k:str(root/v) for k,v in example['local_state'].items()}}}
        snapshot=lambda:{str(p.relative_to(root)):p.read_bytes() if p.is_file() else None for p in root.rglob('*')}
        before=snapshot();original=os.link
        def fault(a,b):
            if Path(b).name.startswith('init-'):raise OSError('independent receipt link fault')
            return original(a,b)
        with mock.patch.object(init,'_context',return_value=ctx),mock.patch.object(os,'link',side_effect=fault):
            try:init.scaffold(argparse.Namespace(repo_root=str(root),config='.dev-graph/config.json',dry_run=False,hook_source='plugin'))
            except OSError:pass
            else:raise AssertionError('expected fault')
        assert snapshot()==before
    return 'Receipt link failure restores all paths and bytes while preserving nested preexisting state.'
case('rollback_restores_full_path_set',['F-0003'],init_restore)

def guard_authority():
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); ss=root/'system-spec';ss.mkdir()
        platforms=writer.CANONICAL_PLATFORMS if hasattr(writer,'CANONICAL_PLATFORMS') else ['web','mobile','tablet','desktop-windows','desktop-linux','desktop-macos']
        state={'matrix':{'database':{p:{'state':'確定','qa_ref':'qa'} for p in platforms}}}
        (ss/'spec-state.json').write_text(json.dumps(state))
        (ss/'database.md').write_text('---\nstatus: confirmed\ncategory: database\naggregate: 確定\nspec_cells: [database.web]\n---\nchapter')
        (ss/'draft.md').write_text('---\nstatus: draft\ncategory: database\n---\ndraft')
        (root/'confirmed-alias').symlink_to(ss/'database.md'); (root/'draft-alias').symlink_to(ss/'draft.md')
        for tool in ['Write','Edit']:
            assert guard.decide({'tool_name':tool,'tool_input':{'file_path':'confirmed-alias'}},root)[0]==2
            assert guard.decide({'tool_name':tool,'tool_input':{'file_path':'draft-alias'}},root)[0]==0
        for command in ['rm -rf system-spec','mv system-spec previous','python3 -c "import shutil; shutil.rmtree(\'system-spec\')"']:
            assert guard.decide({'tool_name':'Bash','tool_input':{'command':command}},root)[0]==2,command
        for command in ['echo x > fixtures/system-spec/spec-state.json','rm -rf scratch','echo x > scratch.txt']:
            assert guard.decide({'tool_name':'Bash','tool_input':{'command':command}},root)[0]==0,command
    return 'Direct-tool aliases and containing directory mutations share protected authority; nested noncanonical fixtures and scratch pass.'
case('guard_same_realpath_same_authority',['F-3001','F-3002','F-3003'],guard_authority)

def candidate_gate():
    catalog=SS/'skills/run-system-spec-elicit/references/required-info-catalog.json'
    ids=[i['item_id'] for i in json.loads(catalog.read_text())['items'] if i['missing_effect']=='block']
    taxonomy=json.loads((SS/'skills/ref-system-design-knowledge/references/system-category-taxonomy.json').read_text())
    state=writer.init_state(taxonomy)
    # Separate answers are accumulated without settling any cell. A later batch joins all proof refs.
    for idx,iid in enumerate(ids):writer.apply_turn(state,{'qa_id':'q'+str(idx),'question':iid,'answer':'explicit answer '+iid,'basis':'user-decision','required_info_items':[iid]})
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw);file=root/'input.json';file.write_text(json.dumps(state)); before=file.read_bytes()
        turn={'ops':[{'action':'confirm','category':state['categories'][0]['id'],'platform':'web','qa_ref':'q0'},
                     {'action':'add-qa-ref','category':state['categories'][0]['id'],'platform':'web','qa_refs':['q'+str(i) for i in range(1,len(ids))]}]}
        turns=root/'turns.json';turns.write_text(json.dumps([turn]));out=root/'output.json'
        cmd=[sys.executable,str(SS/'skills/run-system-spec-elicit/scripts/apply-spec-transition.py'),'chunk','--state',str(file),'--turns',str(turns),'--required-info',str(catalog),'--out',str(out)]
        cp=subprocess.run(cmd,capture_output=True,text=True); assert cp.returncode==0,cp.stderr
        assert file.read_bytes()==before and json.loads(out.read_text())['matrix'][state['categories'][0]['id']]['web']['state']=='確定'
        bad=copy.deepcopy(state);bad['qa_log'][-1]['required_info_items']=[];file.write_text(json.dumps(bad));bad_before=file.read_bytes();out.write_bytes(b'preexisting output');out_before=out.read_bytes()
        cp=subprocess.run(cmd,capture_output=True,text=True);assert cp.returncode==1
        assert file.read_bytes()==bad_before and out.read_bytes()==out_before
    return 'Separated answer accumulation -> first confirm candidate passes; missing last block item changes neither input nor existing output.'
case('first_confirm_candidate_publish_barrier',['F-3005'],candidate_gate)

def scope_refusal():
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw);claude=root/'claude';codex=root/'codex';cwd=root/'active/sub';cwd.mkdir(parents=True)
        def plugin(path,name):
            (path/'.claude-plugin').mkdir(parents=True);(path/'.claude-plugin/plugin.json').write_text(json.dumps({'name':name}));return path
        host=plugin(claude/'plugins/cache/market/host/1.0.0','host')
        target=plugin(claude/'plugins/cache/market/provider/9.0.0','provider')
        alias=root/'provider-alias';alias.symlink_to(target,target_is_directory=True)
        registry=claude/'plugins/installed_plugins.json'
        rows=[{'scope':'local','projectPath':str(root/'foreign'),'installPath':str(alias)}]
        registry.write_text(json.dumps({'plugins':{'provider@market':rows}}))
        with mock.patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':str(claude),'CODEX_HOME':str(codex)}):
            assert resolver.resolve('provider',host,cwd) is None
            rows.append({'scope':'user','installPath':str(target)});registry.write_text(json.dumps({'plugins':{'provider@market':rows}}))
            assert resolver.resolve('provider',host,cwd)==target.resolve()
    return 'Foreign local registry through alias excludes real cache path; valid shared user registration restores it.'
case('registry_scope_survives_cache_alias',['F-2001'],scope_refusal)

def literal_env():
    import yaml
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw);(root/'nested dir').mkdir();expected='literal $VALUE \' quote\nnext'
        workflow={'on':'pull_request','env':{'VALUE':'workflow','LITERAL':expected},'jobs':{'job':{'env':{'VALUE':'job'},'steps':[{'env':{'VALUE':'step'},'working-directory':'nested dir','run':'test "$VALUE" = step\ntest "$LITERAL" = '+__import__('shlex').quote(expected)}]}}}
        (root/'pr.yml').write_text(yaml.safe_dump(workflow));steps,skipped=ci.build_steps(root)
        cp=subprocess.run(['bash','-c',ci.render_step(steps[0])],cwd=root,env={**os.environ,'VALUE':'outside'},capture_output=True,text=True)
        assert cp.returncode==0 and not skipped,cp.stderr
        workflow['defaults']={'run':{'working-directory':'${{ github.workspace }}'}};workflow['jobs']['job']['steps'][0].pop('working-directory')
        (root/'pr.yml').write_text(yaml.safe_dump(workflow));steps,skipped=ci.build_steps(root);assert steps==[] and len(skipped)==1
        workflow['jobs']['job']['steps'][0]['working-directory']='nested dir';(root/'pr.yml').write_text(yaml.safe_dump(workflow));steps,skipped=ci.build_steps(root);assert len(steps)==1 and skipped==[]
    return 'Literal env quote/newline/dollar survives shell; working-directory expression skips only when effective.'
case('ci_environment_and_effective_directory',['F-2002','F-2003'],literal_env)

def metadata_spans():
    pattern=lint.compile_patterns(['alpha','beta'])
    text='{"$schema":"../beta/schema.json","command":"python3 ../beta/scripts/x.py"}'
    findings=lint.scan_text(text,'alpha',pattern);assert len(findings)==1 and findings[0].kind=='dotdot'
    assert lint.scan_text('ROOT.parent / "beta" # $schema annotation','alpha',pattern)
    assert lint.scan_text('{"$schema":"../beta/schema.json"}','alpha',pattern)==[]
    return 'Only actual schema value span is exempt; adjacent command and code comment remain detected.'
case('metadata_exception_is_value_scoped',['F-2004'],metadata_spans)

def shared_caller_root():
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw)
        for idx in [1,2]:
            scripts=root/str(idx)/'scripts';scripts.mkdir(parents=True)
            (scripts/'extract-plugin-root.py').write_text('from pathlib import Path\ndef resolve(name,root,cwd):return root/name\n')
        assert resources.resolve_root('provider',root/'1')==root/'1/provider'
        assert resources.resolve_root('provider',root/'2')==root/'2/provider'
        try:resources.resolve_root('provider',root/'missing')
        except resources.ResolverUnavailable:pass
        else:raise AssertionError('missing caller resolver reused another module')
    return 'Two caller roots stay independent and missing resolver cannot inherit a previous successful module.'
case('shared_loader_has_no_second_root_truth',['F-2006'],shared_caller_root)

def literal_manifest_commands():
    manifest=json.loads((HC/'skills/run-skill-create/workflow-manifest.json').read_text())
    commands=[]
    def collect(value):
        if isinstance(value,dict):
            for child in value.values():collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
        elif isinstance(value,str) and 'extract-plugin-root.py' in value:commands.append(value)
    collect(manifest)
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw);host=root/'host space';provider=root/'provider space';marker=root/'executed'
        (host/'scripts').mkdir(parents=True);(provider/'scripts').mkdir(parents=True)
        resolver_file=host/'scripts/extract-plugin-root.py'
        resolver_file.write_text('print('+repr(str(provider))+')\n')
        for cmd in commands:
            import re
            for script in re.findall(r'\$SIBLING_PLUGIN_ROOT/scripts/([^" ]+)',cmd):
                (provider/'scripts'/script).write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("executed")\n')
        env={**os.environ,'PLUGIN_ROOT':str(host),'SKILLS_DIR':str(root/'skills space')}
        for cmd in commands:
            marker.unlink(missing_ok=True)
            cp=subprocess.run(['bash','-c',cmd],env=env,capture_output=True,text=True)
            assert cp.returncode==0 and marker.exists(),(cmd,cp.stderr)
        resolver_file.write_text('raise SystemExit(2)\n')
        for cmd in commands:
            marker.unlink(missing_ok=True)
            cp=subprocess.run(['bash','-c',cmd],env=env,capture_output=True,text=True)
            assert cp.returncode==2 and not marker.exists(),cmd
        # Exact changed builder prefix, including its stop-on-failure boundary.
        text=(HC/'skills/run-build-skill/SKILL.md').read_text()
        start=text.index('GOV_LINT_DIR="$(python3 ')
        prefix=text[start:text.index('\n',start)]
        cp=subprocess.run(['bash','-c',prefix+'\n'+ 'touch "'+str(marker)+'"'],env=env,capture_output=True,text=True)
        assert cp.returncode==2 and not marker.exists()
    return f'{len(commands)} exact current manifest commands succeed with both roots containing spaces and stop on resolver exit2; builder prefix also stops.'
case('current_shell_consumers_quote_and_stop',['F-2005'],literal_manifest_commands)

def stored_install_owner():
    conf=load('plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/conftest.py','approver_planner_fixtures')
    gates=load('plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-spec-gates.py','approver_spec_gates')
    producer=load('plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/derive-task-graph.py','approver_derive')
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw);conf.write_phase_index(root,plugin_meta=True)
        (root/'phase-13-release.md').write_text(conf.SPECFM.render_minimal_phase(13,plugin_slug='test-plugin'))
        (root/'handoff-run-plugin-dev-plan.json').write_text(json.dumps({'target_plugin_slug':'test-plugin','mode':'create'}))
        contract=conf.SPECFM.default_install_contract();graph=producer.derive(root)
        obligations=conf.SPECFM.install_release_obligations(contract,'test-plugin')
        for legacy in [False,True]:
            changed=copy.deepcopy(graph)
            for node in changed['nodes']:
                if node.get('acceptance_criterion') in obligations.values():
                    node['entity_ref']='C99'
                    if legacy:
                        node.pop('execution_kind',None);node['title']=node.pop('acceptance_criterion')
            (root/'task-graph.json').write_text(json.dumps(changed))
            failures=gates.check_install_release(root,contract)
            assert len(failures)==len(obligations) and all('component' in f for f in failures)
        graph['nodes'].append({'phase_ref':'P13','execution_kind':'direct-task','entity_ref':'C99','acceptance_criterion':'unrelated component acceptance'})
        (root/'task-graph.json').write_text(json.dumps(graph));assert gates.check_install_release(root,contract)==[]
    return 'All canonical stored install obligations reject component attribution, current and legacy; unrelated component P13 task passes.'
case('both_install_projections_enforce_owner',['F-3004'],stored_install_owner)

print(json.dumps({'cases':results,'passed':sum(r['result']=='PASS' for r in results),'failed':sum(r['result']=='FAIL' for r in results),'fixture_policy':'temporary directories only; existing test modules supply schema-valid fixtures, no existing test method was reused'},ensure_ascii=False,indent=2))
raise SystemExit(any(r['result']=='FAIL' for r in results))
