import ast, datetime, hashlib, importlib.util, json, os, re, subprocess, sys
from pathlib import Path
import jsonschema
sys.dont_write_bytecode = True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix')
O=Path('/tmp/pr86-name-review')
B='fdaf4c06085c6d5c52be40f990f7166c1f9a1437'
S='plugins/dev-graph/skills/run-dev-graph-system-spec'
old='prepare-evaluation'
new='build-evaluation-context'
def dump(name, value):
    (O/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
def base(p):
    return subprocess.check_output(['git','show',B+':'+p],cwd=W).decode()
def read(p): return (W/p).read_text()
def sha(p): return hashlib.sha256((W/p).read_bytes()).hexdigest()
paths=[S+'/SKILL.md',S+'/prompts/R2-delegate.md','plugins/dev-graph/tests/test_system_spec_evaluation_paths.py']
checks={p:base(p).replace(old,new)==read(p) for p in paths}
old_helper=base(S+'/scripts/'+old+'.py')
helper=read(S+'/scripts/'+new+'.py')
checks['helper_comment_only']=old_helper.replace('# name: '+old,'# name: '+new)==helper
checks['helper_AST_identical']=ast.dump(ast.parse(old_helper),include_attributes=False)==ast.dump(ast.parse(helper),include_attributes=False)
checks['old_helper_absent']=not (W/S/'scripts'/f'{old}.py').exists()
checks['old_reference_absent_from_dev_graph']=not subprocess.run(['rg','-l',old,'plugins/dev-graph'],cwd=W,capture_output=True,text=True).stdout
refs=re.search(r'^script_refs: \[(.*)\]$',read(S+'/SKILL.md'),re.M).group(1).split(', ')
checks['script_refs_resolve']=all((W/S/r).resolve().is_file() for r in refs)
checks['script_name_matches_filename']='# name: '+new+'\n' in helper
checks['least_privilege_metadata_unchanged']=all(line in helper and line in old_helper for line in ['# network: false','# write-scope: none','# dependencies: []'])
checks['owner_root_formula_unchanged']='Path(__file__).resolve().parents[3] / "scripts/resolve-repo-context.py"' in helper and 'Path(__file__).resolve().parents[3] / "scripts/resolve-repo-context.py"' in old_helper
checks['same_directory_depth']=(W/S/'scripts'/f'{new}.py').parents[3]==W/'plugins/dev-graph'
checks['build_allowed_doc28']='`build`' in read('doc/ClaudeCodeスキルの設計書/28-script-execution-model.md')
# JSON-only CLI output contract: argparse options and execution body are exactly in the unchanged AST.
help_proc=subprocess.run([sys.executable,'-B',str(W/S/'scripts'/f'{new}.py'),'--help'],cwd=O,capture_output=True,text=True)
(O/'helper-help.txt').write_text(help_proc.stdout+help_proc.stderr)
checks['help_exit0']=help_proc.returncode==0
checks['help_required_options']='--context-receipt' in help_proc.stdout and '--output' in help_proc.stdout
spec=importlib.util.spec_from_file_location('content_lint', W/'scripts/lint-content-review.py')
lint=importlib.util.module_from_spec(spec);spec.loader.exec_module(lint)
old_fc=lint.FC.extract_frontmatter_feedback_contract(base(S+'/SKILL.md'))
fc=lint.FC.extract_frontmatter_feedback_contract(read(S+'/SKILL.md'))
checks['feedback_contract_identical']=old_fc==fc
checks['criteria_exact_IN1_OUT1']=lint.FC.criteria_ids(fc['criteria'])=={'IN1','OUT1'}
assert all(checks.values()), checks
skill_sha=sha(S+'/SKILL.md')
assert skill_sha=='10b54fd1e3070f57a8a02de2a31fb93a57940e15ab108e6df96947836812f049'
manifest_paths=[S+'/SKILL.md',*[S+'/prompts/'+r for r in ['R0-context.md','R1-preflight.md','R2-delegate.md','R3-import.md']],S+'/scripts/'+new+'.py','plugins/dev-graph/tests/test_system_spec_evaluation_paths.py']
dump('source-manifest.json',{p:sha(p) for p in manifest_paths})
dump('rename-measurements.json',{'baseline_commit':B,'checks':checks,'focused_57_tests_log':'/tmp/pr86-name-focused.log','naming_lint_log':'/tmp/pr86-name-lint.log','external_evidence_limits':'57testsと命名lintは既存ログを読取確認。追加の独立14testsは同directory pytest-output.txt。host live-trialの再走PASSは未確認。'})
raw=json.loads((O/'rubric-raw.json').read_text())
assert raw['score']==84 and raw['threshold']==80 and raw['passed']
assert not any(x['severity']=='high' for x in raw['findings'])
dump('rubric-llm-assessment.json',{'rule':'BD-004','judge':'review_c19_name 独立LLM、human判定ではない','passed':True,'target_sha256':skill_sha,'trigger_mapping':[{'trigger':'正規フローで仕様を作りたいとき','loc':'SKILL.md:98-101; prompts/R2-delegate.md','assessment':'4 entry point検査後にelicit/doc-fetch/compile/evaluatorへ委譲する。renameはhelper呼出先だけを更新し、生成ロジックの所有を変更しない。'},{'trigger':'source lineage付きで取り込みたいとき','loc':'SKILL.md:102; prompts/R3-import.md','assessment':'confirmed章とevaluator PASSだけをC02へ渡す。R3はbaselineから未変更。'}]})
now=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
common={'target':{'plugin':'dev-graph','skill':'run-dev-graph-system-spec','skill_md_sha256':skill_sha},'reviewer':'review_c19_name（独立 incremental rename reviewer）','reviewed_at':now,'iterations':1,'human_review_required':False,'verdict':'PASS'}
loop={'loop_scope':'both','criteria_evaluated':['IN1','OUT1'],'iteration':1,'iteration_limit':3,'hook_trigger':'親の明示委譲: C19 helperの非許可動詞prepareをdoc28許可動詞buildへ変更した限定差分の独立incremental rename review。baseline '+B,'next_action':'none','positive_feedback':[],'negative_feedback':[]}
elegance=dict(common,review_kind='elegance',findings_summary={'contradiction':0,'omission':0,'inconsistency':0,'dependency_break':0,'smell':1},feedback_loop=dict(loop,positive_feedback=['git show baselineとの正規化比較でSKILL/R2/testはprepare-evaluation→build-evaluation-context置換だけ。helperはname headerだけ変更しAST・CLI・安全境界は同一。rename-measurements.json/source-manifest.jsonに現物と照合結果を保存。','dev-graph配下に旧参照0、新script_refs全件実在。新helperは同じskill-local directory深度でowner plugin resolverを解決し、network:false/write-scope:noneを維持。buildはdoc28許可動詞でJSON context生成の責務に合う。','IN1/OUT1の定義・verify_by・閾値は不変。IN1の3 canonical gateとOUT1の委譲/C02/lineage契約を弱めるsource差分がない。追加pytestによるcwd/root/identity/symlink拒否の結果はpytest-output.txt。'],negative_feedback=['既存low制約を継続: 6キー/hash検査自体は各gateのexit/時刻を自動照合しない。本文の実測記録要求と独立Agent検証で運用する。renameで追加退行はない。']),notes='incremental rename reviewとして4条件PASS。30思考法full reviewを再走したという主張ではなく、baselineからの限定rename差分の意味不変と安全境界を確認した。smell1は既存制約の継続。IN1/OUT1は変更影響の評価であり、今回host live-trial再走/OUT1実走PASSや過去周回IN1の証明ではない。')
rubric=dict(common,review_kind='rubric',findings_summary={'contradiction':0,'omission':0,'inconsistency':0,'dependency_break':0,'smell':3},feedback_loop=dict(loop,positive_feedback=['現行SHAへ正規render-findings-score.pyを再実行し84/100、threshold80、high0。100-3(FM-005)-3(PD-001)-10(PD-002)=84を再計算、単なる前版scoreの転記ではない。rubric-raw.jsonを参照。','適用24項目の機械採点23は現行sourceで再実行、BD-004の2triggerと正規委譲/lineage取込の対応は独立LLMで現在のSKILL/R2/R3を再確認。生出力pending_humanは変更せず保持。','renameによってNM系のskill名・trigger・責務・権限・IN1/OUT1には変更がない。script名はdoc28規約を修復し参照を同時更新するため、新たなrubric減点要因はなくscore84を維持する。'],negative_feedback=[x['id']+' '+x['severity']+': '+x['message'] for x in raw['findings']]),notes='incremental rename review。'+raw['rubric_hash']+'; composition_hash='+raw['composition_hash']+'。機械採点は現行sourceで再実行し、BD-004だけ独立LLM意味判定。既存3findingsとscoreは不変。30思考法full reviewまたはhost live-trial再走PASSを主張しない。')
schema=json.loads(read('plugins/harness-creator/skills/run-build-skill/schemas/content-review-verdict.schema.json'))
results={}
for name,obj in [('elegance-verdict.json',elegance),('rubric-verdict.json',rubric)]:
    dump(name,obj)
    jsonschema.Draft7Validator(schema,format_checker=jsonschema.FormatChecker()).validate(obj)
    result=lint._check_verdict(O/name,'dev-graph','run-dev-graph-system-spec',name)
    assert result is None,result
    results[name]={'schema':'PASS','canonical_check_verdict':'PASS','current_sha':skill_sha}
dump('verdict-validation.json',results)
print(json.dumps({'checks':len(checks),'checks_passed':all(checks.values()),'score':raw['score'],'verdicts':results},ensure_ascii=False,indent=2))
