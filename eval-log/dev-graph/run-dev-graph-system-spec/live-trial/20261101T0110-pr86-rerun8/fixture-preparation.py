from pathlib import Path
import json,subprocess,sys,shutil,hashlib,os
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec95';fx=r/'fx';src=T/'runs/sysspec94/fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec95','run-dev-graph-system-spec','--session-root','fx'],check=True)
subprocess.run(['git','init','-q','-b','main',str(fx)],check=True)
subprocess.run(['git','-C',str(fx),'-c','user.name=live-trial','-c','user.email=live-trial@example.invalid','commit','-q','--allow-empty','-m','fixture: canonical resume inputs'],check=True)
(fx/'.git/info/exclude').write_text('plugins/\n.claude/\n')
shutil.copytree(src/'system-spec',fx/'system-spec')
env={k:v for k,v in os.environ.items() if k!='CLAUDE_PROJECT_DIR'}
cp=subprocess.run([sys.executable,'-B',str(W/'plugins/dev-graph/scripts/build-init-scaffold.py'),'--repo-root',str(fx),'--hook-source','plugin'],env=env,check=True,capture_output=True,text=True)
(r/'workdir/fixture-init-receipt.json').write_text(cp.stdout)
assert json.loads((fx/'.dev-graph/state/graph.json').read_text())['nodes']==[]
# 登録前の草案だけを入力として渡す。評価証拠と確定結果は削除する。
draft=json.loads((src/'candidate-import.json').read_text())
draft['expected_graph_revision']=0  # 新fixtureの初期graph revisionへのCAS pin（評価/登録結果ではない）
for a in draft['artifacts']:
 a.pop('confirmation_evidence',None)
 a.get('source_lineage',{}).pop('imported_at',None)
(fx/'candidate-import.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n')
# 新しい合成fixtureのqa-008だけを原初の未backfill入力から再導出する。
# 過去の完成済みbackfillをwriterで上書きしたり、過去試行を改変したりしない。
O=Path('/private/tmp/claude-501/-Users-dm-dev-dev------harness/4c56fd8f-ccd6-4ef6-a546-d1f3c2d79696/scratchpad/lt/runs/sysspec86/fx/system-spec/spec-state.json')
state=fx/'system-spec/spec-state.json';before=json.loads(state.read_text());original=json.loads(O.read_text());data=json.loads(state.read_text())
prior=next(q for q in before['qa_log'] if q['id']=='qa-008');raw=next(q for q in original['qa_log'] if q['id']=='qa-008')
ignore={'design_applications','design_application_provenance','knowledge_ref_corrections','legacy_exempt','legacy_exempt_reason'}
assert {k:v for k,v in prior.items() if k not in ignore}=={k:v for k,v in raw.items() if k not in ignore}
assert original['schema_version']=='1.0' and 'design_applications' not in raw
(r/'workdir/qa008-prior-backfill.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2)+'\n')
(r/'workdir/qa008-original-input.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
apps=json.loads(json.dumps(prior['design_applications']));apps[0]['rationale']=apps[0]['rationale'].split('。')[0]+'。'
assert 'RTO' not in apps[0]['rationale'] and 'RPO' not in apps[0]['rationale']
raw['legacy_exempt']=True;raw['legacy_exempt_reason']='原初schema1.0 fixtureからqa-008の未確認説明を再導出する準備。問答・承認は不変。'
data['qa_log']=[raw if q['id']=='qa-008' else q for q in data['qa_log']]
state.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
appfile=r/'workdir/qa008-grounded-applications.json';appfile.write_text(json.dumps(apps,ensure_ascii=False,indent=2)+'\n')
writer=W/'plugins/system-spec-harness/skills/run-system-spec-elicit/scripts/apply-spec-transition.py'
cp=subprocess.run([sys.executable,'-B',str(writer),'set-qa-design-applications','--state',str(state),'--qa-id','qa-008','--applications',str(appfile)],capture_output=True,text=True);assert cp.returncode==0,cp.stderr
(r/'workdir/fixture-canonical-backfill.log').write_text(cp.stdout+cp.stderr)
after=json.loads(state.read_text());pairs=lambda d:[(q['id'],q.get('question'),q.get('answer')) for q in d['qa_log']]
assert pairs(before)==pairs(after) and before['approval_log']==after['approval_log'] and before['decisions']==after['decisions']
changed=[k for k in before if before[k]!=after.get(k)];assert changed==['qa_log'],changed
compiler=W/'plugins/system-spec-harness/skills/run-system-spec-compile/scripts/compile-spec-doc.py'
cp=subprocess.run([sys.executable,'-B',str(compiler),'compile','--spec',str(state),'--references',str(fx/'system-spec/fetched-references.json'),'--out-dir',str(fx/'system-spec'),'--repo-root',str(fx)],capture_output=True,text=True);assert cp.returncode==0,cp.stderr
(r/'workdir/fixture-canonical-compile.log').write_text(cp.stdout+cp.stderr)
# 草案のcontent digestも新しい入力bytesに整合させる。評価/確認証拠ではない。
for art in draft['artifacts']:
 lineage=art.get('source_lineage',{});source=fx/lineage['source_path'];lineage['source_digest']=hashlib.sha256(source.read_bytes()).hexdigest()
(fx/'candidate-import.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n')
(r/'workdir/fixture-qa008-correction.json').write_text(json.dumps({'original_input_source':str(O),'original_input_sha256':hashlib.sha256(O.read_bytes()).hexdigest(),'prior_backfill_source':str(src/'system-spec/spec-state.json'),'method':'新fixtureのqa-008を原初未backfill entryから再導出。元問答/承認/選択は変更せず、未確認RTO/RPO文だけを除いた設計解釈を正規writerでlegacy_backfill。既存試行/完成済みstateの上書きはしていない。','questions_answers_unchanged':True,'approvals_unchanged':True,'decisions_unchanged':True,'changed_state_top_level_keys':changed,'canonical_backfill_exit':0,'canonical_seed_compile_exit':0,'evaluations_seeded':False,'prior_as_success':False},ensure_ascii=False,indent=2)+'\n')
files={p.relative_to(fx).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (fx/'system-spec').rglob('*') if p.is_file()}
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source_run':'20261101T0110-pr86-rerun7 (independent FAIL)','preparation':'前実走の正規writerによる確定問答・出典資料・compiled章を再開入力として複製。C01の正規builderでこの新repoを初期化。graph.nodesは空。C02 payloadは草案のみでconfirmation_evidenceとimported_atを削除。評価report・監査台帳・再利用receipt・PASS結果・登録nodeを種として置いていない。targetは全canonical flowをこのrepoで新規実行し、独立評価と登録を実証する。','source':str(src/'system-spec'),'seed_sha256':files,'byte_identical':all((src/'system-spec'/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False,'graph_nodes_initial':0,'draft_is_confirmation_evidence':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec95','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec94/workdir/task.md').read_text().replace('sysspec94','sysspec95')
a=body.index('実行前の契約確認:')
body=body[:a]+"""
実行前の契約確認:
- 現行C19のPurpose/Output・R2・goal-seek配線を全文読む。本処理のroot照合、隔離unit検証の範囲、親と責務Agentの役割、周回と責務切替の区別をそこに従って実行する。
- 毎周回、現行SKILLの「ゴールシーク検証」にあるcoverage/source-citation/schemaの3 CLIを実行してからIN1を記録する。loop1も空graphへschema CLIを実行し、R3まで待たない。3つの実測exit0を得てからのみPASSを書き、未実施/待ちはnot_achievedとする。その記録の後でintermediate/hash検査を行う。初期化済みという入力条件や後周回の成功で代用しない。
- compileについては、正規CLIのBash末尾で成果物の現物path・実測digestと「開き方: less <今回の絶対repo-root>/system-spec/index.md」をstdoutへ表示して返す。このBash呼出しにchoice記録、test、Agentを混ぜない。可視CLI出力による3点の提示より後の別Bashでeval-log/choices/compile-standard.jsonへstage=compile・choice=standard・path/digest/open_withを記録し、その後でのみOUT1 63件testsや評価Agentを実行する。会話にも再掲できるが、選択より後の提示で代用しない。Agentへもこの順序を渡す。
- この環境のBash guardは文章内のopenを外部CLIと誤認することがある。C05からC07/C06/C08の各監査を呼ぶpromptで、監査結果の自由文章JSONは最初から許可Write toolで許可絶対pathへ出力するよう必ず伝える。C05自身のreportもWriteが推奨されるが、正規C05が自分の判断を安全なローカル整形scriptでJSON化することは許される。spec/graph/coverageのcanonical生成・検証・登録CLIは通常通りBashで実行し、実際にguardが拒否した操作は別toolへ迂回せずFAILにする。guardやsandboxは変更しない。
- 今回のqa-008補完はfixture-qa008-correction.jsonに開示したとおり、原初schema1.0 entryから未確認RTO/RPO文を除いて正規writerで再導出した入力である。質問/回答/承認/採択は不変で、evaluatorや登録receiptは種に置いていない。今回の実走で再compile・新規独立評価・C02登録を実証する。事前compileを今回の行動証拠に代用しない。
- 各run Skillの最小成果物を提示した直後に事前回答standardを記録し、その後でsemantic Agent/意味層のtestを開始する。記録を最後にまとめない。
- 親は未達checklistを実際の周回として管理し、新しい周回の操作を開始する前に直前のmerged_directive_for_nextを入力する。責務Agentのpromptには固定C24 receipt、元goal/hash、対応する周回/次指示、担当prompt、適用する境界を渡す。
- Agentが検証用のscratchを使うなら、事前に許可された絶対scratch配下でcallerの取込元へ書かないことを確認し、その結果を本処理の評価・登録の根拠へ代用しない。本処理は必ずcanonical Skill/CLI。独立検証は既存のcanonical testと実際の出力のread-only確認で行える。
- コードベース全体のunit回帰は外側のrunnerで914件PASS確認済み。この値を今回のflow実行の証拠へ代用してはならないが、各Skillが明示要求する個別test以外の大規模suiteをこの実走で追加する必要はない。
"""
(r/'workdir/task.md').write_text(body)
print('prepared sysspec95: initialized resume repo; graph empty; no evaluations seeded')
