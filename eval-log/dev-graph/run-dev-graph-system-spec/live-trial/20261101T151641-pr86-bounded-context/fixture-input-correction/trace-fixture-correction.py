from pathlib import Path
import json,hashlib,datetime,shutil,subprocess,sys
sys.dont_write_bytecode=True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix')
T=Path('/private/tmp/claude-501/pr86-ci-live/lt')
old=T/'positive-input-v6';D=T/'positive-input-v7'
assert not D.exists();shutil.copytree(old,D)
SS=W/'plugins/system-spec-harness'
writer=SS/'skills/run-system-spec-elicit/scripts/apply-spec-transition.py'
state=D/'system-spec/spec-state.json';before=json.loads(state.read_text())
(D/'v6-before-trace-state.json').write_bytes(state.read_bytes())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
commands=[]
def run(args,tag):
 cmd=[sys.executable,'-B']+list(map(str,args))
 p=subprocess.run(cmd,cwd=W,capture_output=True,text=True)
 (D/(tag+'.stdout')).write_text(p.stdout);(D/(tag+'.stderr')).write_text(p.stderr)
 commands.append({'argv':cmd,'exit':p.returncode})
 print(tag,p.returncode,p.stdout[-100:],p.stderr[-180:],flush=True)
 assert p.returncode==0
def op(data,tag):
 (D/(tag+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 run([writer,'apply','--state',state,'--op',json.dumps(data,ensure_ascii=False)],tag)
qa={q['id']:q for q in before['qa_log']}
source_path='system-spec/fixture-requirements-v7.txt'
rows=[
 ('qa-csrf-written-v7','CSRF防御',qa['qa-037']['answer'].removeprefix('(2) にする。'),['auth-model','security-posture'],'qa-004'),
 ('qa-session-written-v7','セッション保存',qa['qa-038']['answer'].removeprefix('(2) '),['auth-model'],'qa-002'),
 ('qa-auth-written-v7','認証モデル',qa['qa-002']['answer'],['auth-model'],'qa-002'),
 ('qa-security-written-v7','セキュリティ基準',qa['qa-004']['answer'],['security-posture'],'qa-004'),
]
doc='# 新規合成fixture v7の書面要件\n\nこの資料はCI acceptance用にfixture作者がboot前に提供する新しい合成givenである。実利用者との対話・新しい本番承認ではない。古いqa-037/qa-038のbasis変更を有効な利用者入力と主張せず、過去の記録はそのまま残す。本資料に値を明示し、書面source-indexのpath/section/原文SHAで新しいgivenを追跡可能にする。旧fixtureと同じ機能値を使い、採択D1-D4や上位目的は変更しない。\n'
for _,section,answer,_,_ in rows:doc+='\n## '+section+'\n\n'+answer+'\n'
(D/source_path).write_text(doc)
for cat in ['auth','security']:
 op({'action':'reopen','category':cat,'platform':'web','reason':'新規合成fixture: 根拠のないbasis変更を持つ旧qa-037/qa-038を現行の補助根拠にしない。元記録は保持し、提供書面へ正規に再接地する。','reopened_at':now()},'trace-v7-reopen-'+cat)
turns=[]
for qid,section,answer,items,card_from in rows:
 turns.append({'qa_id':qid,'question':source_path+' の「'+section+'」に記載された要件','answer':answer,
  'basis':'user-decision','source':{'kind':'written-requirements','path':source_path,'section':section,'sha256':hashlib.sha256(answer.encode()).hexdigest()},
  'answered_at':now(),'required_info_items':items,
  'provenance':'新規合成fixture v7の提供書面source-index。fixture作者が実行前にこの書面をgivenとして提供した。実利用者の対話や新しい本番承認を主張しない。answered_atは書面をgivenへ記録した実測時刻であり、人の回答を観測した時刻ではない。設計解釈は作者agentの推論であり、書面要求そのものとは区別する。',
  'design_applications':qa[card_from]['design_applications'],'ops':[]})
auth=before['matrix']['auth']['web'];sec=before['matrix']['security']['web']
turns[2]['ops']=[
 {'action':'confirm','category':'auth','platform':'web','serves_goals':auth['serves_goals']},
 {'action':'add-qa-ref','category':'auth','platform':'web','qa_refs':['qa-002','qa-018','qa-026','qa-034','qa-csrf-written-v7','qa-session-written-v7']}]
turns[3]['ops']=[
 {'action':'confirm','category':'security','platform':'web','serves_goals':sec['serves_goals']},
 {'action':'add-qa-ref','category':'security','platform':'web','qa_refs':['qa-004','qa-030','qa-csrf-written-v7']}]
(D/'trace-v7-turns.json').write_text(json.dumps(turns,ensure_ascii=False,indent=2)+'\n')
run([writer,'chunk','--state',state,'--turns',D/'trace-v7-turns.json','--max-loops','4','--require-all','--required-info',SS/'skills/run-system-spec-elicit/references/required-info-catalog.json'],'trace-v7-reconfirm')
for old_id,new_id in [('qa-037','qa-csrf-written-v7'),('qa-038','qa-session-written-v7')]:
 op({'action':'supersede-qa','qa_id':old_id,'superseded_by':new_id,'superseded_at':now(),
 'note':'旧entryのbasis変更を利用者一次入力と扱わない。旧本文/basis/provenanceは保持し、同じ'+('CSRF防御' if old_id=='qa-037' else 'セッション保存')+'の論点を、値を明示した新規合成書面の1論点source-indexへ再接地した。現行セルの主/補助参照に旧entryは残さず、書面の原文とSHAを検証できる。実利用者の新しい対話/承認ではない。'},'trace-v7-supersede-'+old_id)
d3=next(d for d in before['decisions'] if d['id']=='D3')
d3=json.loads(json.dumps(d3))
d3['recommendation']['caveats'][1]='cookieのHttpOnly・Secure・SameSite属性の細部は本比較の公式資料では未確認。具体値とCSRF防御は新規合成書面source-index qa-csrf-written-v7のgivenであり、公式が安全性を保証したとは主張しない。D3の方式採択はqa-034の提供済み回答で保持し、旧qa-037のbasis変更を採択/設定の根拠にしない。'
(D/'trace-v7-D3.json').write_text(json.dumps(d3,ensure_ascii=False,indent=2)+'\n')
run([writer,'set-decision','--state',state,'--decision',D/'trace-v7-D3.json'],'trace-v7-decision-ref')
def replace_refs(text):
 return text.replace('qa-037','qa-csrf-written-v7').replace('qa-038','qa-session-written-v7')+'\nCSRF/セッションの現行根拠は新fixtureの提供書面source-indexであり、旧entryのbasis変更を正当な利用者入力と主張しない。これは与えられた書面値への設計解釈で、実利用者の新承認ではない。'
op({'action':'set-design-application','category':'auth','text':replace_refs(before['design_applications']['auth']['text']),'basis':'agent-inference','recorded_at':now()},'trace-v7-auth-design')
for concern,record in before['doctrine_applications']['auth'].items():
 op({'action':'set-doctrine-application','category':'auth','concern_id':concern,'text':replace_refs(record['text']),'basis':'agent-inference','recorded_at':now()},'trace-v7-auth-'+concern)
run([SS/'skills/run-system-spec-compile/scripts/compile-spec-doc.py','compile','--spec',state,'--references',D/'system-spec/fetched-references.json','--out-dir',D/'system-spec','--repo-root',D],'trace-v7-compile')
run([SS/'scripts/validate-coverage-matrix.py','--matrix',state,'--require-complete','--require-basis','--require-foundation'],'trace-v7-coverage')
run([SS/'scripts/validate-source-citation.py','--targets',state,'--references',D/'system-spec/fetched-references.json','--state',state,'--repo-root',D],'trace-v7-citation')
after=json.loads(state.read_text());aq={q['id']:q for q in after['qa_log']}
for qid,oldq in qa.items():
 extra={'superseded_by','superseded_at','superseded_note'} if qid in ['qa-037','qa-038'] else set()
 assert {k:v for k,v in aq[qid].items() if k not in extra}==oldq
assert len(aq)==len(qa)+4
for cat,row in after['matrix'].items():
 for platform,cell in row.items():
  if (cat,platform) not in [('auth','web'),('security','web')]:assert cell==before['matrix'][cat][platform]
  assert all(ref not in ['qa-037','qa-038'] for ref in [cell.get('qa_ref')]+cell.get('qa_refs',[]))
assert after['requirements_foundation']==before['requirements_foundation']
assert after['approval_log']==before['approval_log'] and after['targets']==before['targets']
assert after['decisions']==[d3 if d['id']=='D3' else d for d in before['decisions']]
assert json.loads((old/'system-spec/spec-state.json').read_text())==before
meta={'kind':'new-synthetic-written-source-recovery','actual_user_approval_claimed':False,
 'source_changed':False,'source_fixture':'positive-input-v6','old_fixture_unchanged':True,
 'new_document':source_path,'document_sha256':digest(D/source_path),
 'reason':'根拠なくbasisを変更した旧qa-037/qa-038の本文/履歴を保持し、auth/securityのみ正規reopen/書面source-indexの新given/confirm/supersedeで現行根拠を再構成する。旧basisを後から本物に変えたのではない。',
 'semantics':'OIDC/ロール/8h、TLS1.3/入力検証/監査、CSRF属性+同期token、PGセッションの値は旧fixtureと同じ。今回の書面はfixture作者が実行前に提供した合成要件であり、実ユーザーの意思決定や本番承認を創作していない。',
 'all_old_50_QA_core_bytes_unchanged':True,'old_37_38_only_supersession_metadata_added':True,
 'new_written_QA_count':4,'foundation_approvals_targets_unchanged':True,
 'matrix_change_scope':['auth/web references','security/web references'],
 'decision_change_scope':'D3の注意書きの根拠参照のみ。採択/比較/QA/時刻は保持。',
 'inherited_review_scope':'v6 input reviewはD4等の旧定義のもの。v7書面再接地の受入や今回のC05/goal PASSを示さない。',
 'PASS_or_evaluation_seeded':False,'scenario_contract_changed':False,'commands':commands}
(D/'trace-correction-provenance.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,D/'trace-fixture-correction.py')
public=W/'eval-log/dev-graph/live-trial-fixtures/pr86-system-spec-positive-v7'
assert not public.exists();shutil.copytree(D,public)
print('v7 canonical written-source recovery complete',flush=True)
