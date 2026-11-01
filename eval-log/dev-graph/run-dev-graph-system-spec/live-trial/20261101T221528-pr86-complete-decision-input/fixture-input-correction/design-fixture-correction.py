from pathlib import Path
import json,hashlib,datetime,shutil,subprocess,sys
sys.dont_write_bytecode=True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');T=Path('/private/tmp/claude-501/pr86-ci-live/lt');old=T/'positive-input-v4';D=T/'positive-input-v6';assert not D.exists();shutil.copytree(old,D)
state=D/'system-spec/spec-state.json';prior=json.loads(state.read_text());(D/'v4-before-design-state.json').write_bytes(state.read_bytes())
base=T/'positive-input-v3/before-state.json';state.write_bytes(base.read_bytes());initial=json.loads(state.read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z');prefix='plugins/system-spec-harness/skills/ref-system-design-knowledge/references/'
def app(card,principle,why,tradeoff,mode='applied'):
 return {'knowledge_ref':prefix+card+'.md#中核概念','principle':principle,'applicability':mode,'rationale':'合成fixture作者agentによる回答時の設計解釈であり、新しい利用者回答・承認ではない。'+why,'tradeoffs':[tradeoff]}

# D4は初回のset-decisionより前に新fixtureのgivenとして定義する。
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
url_rows=[('postgresql-select','https://www.postgresql.org/docs/16/sql-select.html'),('kubernetes-cronjob','https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/'),('fastapi-background','https://fastapi.tiangolo.com/tutorial/background-tasks/')]
(D/'decision-evidence').mkdir(exist_ok=True)
def fetch(row):
 name,url=row
 with urlopen(Request(url,headers={'User-Agent':'harness-ci-fixture/1.0'}),timeout=45) as response:
  body=response.read();assert response.status==200 and urlsplit(response.url).hostname==urlsplit(url).hostname
  assert 'text/html' in response.headers.get('Content-Type','')
  result={'name':name,'source_url':url,'final_url':response.url,'status':response.status,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'content_type':response.headers.get('Content-Type')}
 (D/'decision-evidence'/f'{name}.html').write_bytes(body)
 return result
with ThreadPoolExecutor(max_workers=3) as pool: http=list(pool.map(fetch,url_rows))
(D/'decision-evidence/response-metadata.json').write_text(json.dumps(http,ensure_ascii=False,indent=2)+'\n')
decision=json.loads(Path('/tmp/pr86-v6-decision-template.json').read_text())
decision['recommendation']['latest_checked_at']=max(r['retrieved_at'] for r in http)
(D/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
shutil.copy2('/tmp/pr86-v6-decision-template.json',D/'decision-template-v6.json')
now=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
turns=json.loads((D/'turns.json').read_text())
comparison='# D4 合成givenの案別比較\n\nこの文書はCI用の新しい合成入力定義であり、実利用者への提案/新承認ではない。料金の0円は追加OSSライセンス部分だけのgivenで、実価格/総TCOの見積りではない。\n'
for option in sorted(decision['options'],key=lambda o:o['id']):
 comparison+='\n## '+option['id']+'\n'
 for key in ['goal_fit','cost_model','free_tier_limits','security_fit','pros','cons','risks','lock_in','ops_burden','evidence_refs']:
  comparison+='\n- '+key+': '+json.dumps(option[key],ensure_ascii=False)+'\n'
comparison+='\n## 参考：推奨（問の外）\n'+decision['recommendation']['rationale']+'\n\n## 中立な問\n'+turns[1]['question']+'\n\n## 合成利用者の既定回答\n'+turns[1]['answer']+'\n'
(D/'decision-comparison-presentation.md').write_text(comparison)
turns[1]['provenance']+=' v6は同じ回答/採択/業務要件を持つ新givenで、decision-comparison-presentation.mdにid昇順の案別比較、問の外の参考推奨、中立な問、提供済み合成回答を分けて定義する。実利用者の新しい回答/承認ではない。'

turns[0]['design_applications']=[
 app('clean-architecture','業務規則とHTTP/DB/workerの依存を分ける','qa-o1-fixture-v3の請求予定・期限超過/不足明細・締め前再照合を業務ユースケースとし、FastAPIの一覧/再検査APIと独立workerから共有する。billing_expectations/missing_billing_cases/billing_closing_checksと追記監査は同じ業務整合性の境界へ置き、フレームワークやDB row型を中核へ持ち込まない。','API/workerのadapterと境界テストが増える。'),
 app('usability-accessibility','利用者の仕事の状態・認知負荷・回復導線を明示する','請求担当者/経理リーダーのWeb一覧で件数・取引先・対象月・期限・不足明細・金額を示す。qa-o1-fixture-v3の金額順、正しい請求書発行で次走査に解消、手動無視で解消しないという状態を画面で区別する。表示はWeb内だけであり外部メール/Slack通知を追加しない。','未解消と走査待ち/解消済みを区別する表示・操作テストが必要。'),
 app('site-reliability-engineering','利用者視点の指標と観測可能性を業務の検知へ対応させる','15分走査/期限超過から30分以内の一覧表示、締め直後の未解消件数という既回答の測定点を計測対象にする。監視の閾値を勝手に新設せず、O1の月次0件/3か月連続0件と検知・解消/締め検査の履歴を追跡する。','指標収集/履歴保持の費用が残り、SRE適用だけで漏れ0件を保証しない。')]
turns[1]['design_applications']=[
 app('clean-architecture','実行機構を業務ユースケースから隔離する','qa-job-choice-fixture-v3/D4のPG outbox・独立Python worker・CronJobを外側の実行adapterとし、APIと同じ請求/突合ユースケースを呼ぶ。API BackgroundTasksへ業務を閉じ込めず、worker停止後も永続outboxから再開する。','worker/CronJobの構成・adapter・共有ユースケースのテストが増える。'),
 app('site-reliability-engineering','観測可能性と反復作業の自動化を復旧へ結ぶ','qa-job-choice-fixture-v3のjob claim/lease/fencing、リトライ上限/失敗状態、30分超未処理、worker停止後の再開を運用画面/履歴へ対応させる。1秒claim/15分走査は既回答の値であり、新たなSLO数値やリトライ回数を解釈だけで確定しない。','再試行・lease切れ・失敗の観測と復旧手順が必要で、手動運用の消滅を約束しない。'),
 app('cloud-architecture-patterns','複数資産への補償/Blob offloadingの適用境界を見極める','D4は既存の単一PostgreSQL 16内のtransactional outboxと業務データを使い、新broker・外部blob・複数資産の補償を導入しない。このためcard全体の分散資産/Blob設計は非適用とする。PG transaction、claim排他、lease/fencing、業務一意キーによる二重反映防止はQAで確定したDB/worker設計として別に明記する。Cron重複抑制だけをexactly-once保証と扱わない。','外部資産を後から追加する場合には原子性境界と補償を再検討する必要がある。','not_applicable'),
 app('secure-by-design','最小権限と責任分界を非同期実行にも適用する','D4の既存権限/追記監査と最小権限のDB接続という比較条件をworker/CronJobのDBアクセスへ解釈適用する。既存の担当者/リーダー認可と監査ログ保持を維持し、未回答のDB role名・秘密配布方式・追加権限を新設したと主張しない。','APIとworker双方の権限/監査境界を検査する工数が必要。')]
for t in turns:t['provenance']+=' v5は独立した新しい正の合成fixture。v4を実行中に更新したものではない。質問/回答/承認/選択は保持し、作者agentの設計解釈だけを新fixtureの回答記録時に正規writerへ渡す。'
(D/'design-corrected-turns.json').write_text(json.dumps(turns,ensure_ascii=False,indent=2)+'\n')
SS=W/'plugins/system-spec-harness';writer=SS/'skills/run-system-spec-elicit/scripts/apply-spec-transition.py';commands=[]
def run(args,tag):
 cmd=[sys.executable,'-B']+list(map(str,args));p=subprocess.run(cmd,cwd=W,capture_output=True,text=True);(D/(tag+'.stdout')).write_text(p.stdout);(D/(tag+'.stderr')).write_text(p.stderr);commands.append({'argv':cmd,'exit':p.returncode});print(tag,p.returncode,p.stdout[-100:],p.stderr[-120:]);assert p.returncode==0
run([writer,'chunk','--state',state,'--turns',D/'design-corrected-turns.json','--max-loops','2','--require-all'],'design-v6-00')
run([writer,'set-decision','--state',state,'--decision',D/'decision.json'],'design-v6-01')
run([writer,'set-targets','--state',state,'--targets',D/'targets-v4.json'],'design-v6-02')
run([SS/'skills/run-system-spec-doc-fetch/scripts/build-fetched-references.py','assemble','--records',D/'reference-records-v4.json','--targets',state,'--out',D/'system-spec/fetched-references.json'],'design-v6-03')
ext={
'database':'qa-o1-fixture-v3/qa-job-choice-fixture-v3/D4への追加解釈: billing_expectations/missing_billing_cases/billing_closing_checks/job_outboxを既存PostgreSQL 16内に置く。契約ID・対象年月・種別の一意キー、業務更新と同一transactionのoutbox投入、claim排他/lease/fencing、再試行時の冪等な業務反映を対応付ける。締めでは全有効契約・請求予定・有効請求書を同じ整合した業務snapshotで再照合し漏れがあれば拒否する。Cloud Architecture Patternsの外部Blob配置/複数資産の補償は単一DBの本構成には非適用で、外部保存基盤を足さない。原子性境界と再送の比較はDB内transactionと既承認の一意キー/claimに具体化し、Cronだけのexactly-onceを主張しない。',
'backend':'qa-o1-fixture-v3/qa-job-choice-fixture-v3/D4への追加解釈: Clean Architectureの業務ユースケースをAPIとworkerから共有し、請求漏れ判定・締め前整合照合・突合をHTTP/CronJob/DB row型から隔離する。GET /billing-missing、POST /billing-missing/checksの202受付、GET /jobs/{id}の状態取得に既存認可/楽観ロックを適用し、PG outboxと業務更新を同一transactionへ置く。lease/fencing・リトライ上限/失敗状態・一意キーで少なくとも1回の実行に伴う二重業務反映を防ぐ。新broker/RedisやAPI BackgroundTasks案は採用しない。',
'ui-ux':'qa-o1-fixture-v3への追加解釈: usability-accessibility/information-designの利用文脈を担当者/経理リーダーのWeb内「請求漏れ」一覧へ当てる。件数・取引先・対象月・期限・不足明細・金額を金額順に示し、未解消と正しい請求書発行後の走査待ち/解消を区別する。手動無視で解消扱いにしない業務規則を表示/操作へ反映し、色だけに状態を依存させない。外部メール/Slack通知は追加せず、「通知表示」という曖昧な語はWeb内一覧の状態表示だけを指す。',
'security':'qa-o1-fixture-v3/qa-job-choice-fixture-v3/D4への追加解釈: secure-by-designの最小権限/責任分界をAPI・独立worker・CronJobの既存PGアクセスへ適用する。担当者/リーダーの閲覧/再検査権限と既存認可・楽観ロックを共有し、情報システム部へ請求閲覧権を新設しない。検知/解消・締め結果・追記専用監査を物理削除せず、業務/検知結果と監査を整合するtransaction境界へ置く。具体DB role名や新しい秘密配布方式を利用者決定として追加しない。',
'infrastructure':'qa-job-choice-fixture-v3/D4への追加解釈: 既存社内k8sのPython worker Deploymentが1秒claim、同じworker imageのCronJobが15分走査を担う。SREの稼働実体/構成の観測と復旧を、PG永続outbox・lease/fencing・失敗状態・30分超未処理の運用表示へ対応させる。CronJobの重複抑制とDB側の一意キー/冪等性を分け、worker停止時は永続状態から再開する。追加broker/外部Blob補償を持ち込まず、未回答の資源上限/SLO/リトライ数値を勝手に確定しない。',
'frontend':'qa-o1-fixture-v3への追加解釈: 既存の画面/API取得層の依存境界を請求漏れ一覧とjobs状態取得へ使う。担当者/経理リーダーが見るWeb内の件数・期限・不足明細・金額順・未解消/解消を状態として表現し、業務の判定や解消をクライアント独自に決めない。POSTの202受付と最終的なjob状態を区別し、外部通知や新しいグローバル状態管理基盤を追加しない。',
'maintenance-ops':'qa-o1-fixture-v3/qa-job-choice-fixture-v3/D4への追加解釈: Google SREの観測可能性/トイル削減/復旧を、1秒claim・15分走査の稼働、lease/fencing状態、リトライ上限/失敗状態、30分超未処理の運用画面表示、worker停止後の永続outboxからの再開へ対応させる。請求漏れの検知/解消履歴と締め直後未解消件数をO1の月次0件/3か月連続0件へ追跡し、手動無視で解消しない。Clean Codeに従いrunbookの検知/切分け/再開を意図の分かる単位へ分ける。SRE名の引用だけで信頼性を保証せず、未回答の新しい回数/閾値/運用権限を確定しない。'}
ops=[]
for cat,text in ext.items():
 oldtext=prior['design_applications'][cat]['text'];ops.append({'action':'set-design-application','category':cat,'text':oldtext+'\n\n'+text+'\nこれは既存回答に対するfixture作者agentの設計解釈であり、新規の利用者承認ではない。','basis':'agent-inference','recorded_at':now})
 for concern,rec in prior['doctrine_applications'].get(cat,{}).items():ops.append({'action':'set-doctrine-application','category':cat,'concern_id':concern,'text':rec['text']+'\n\n'+text+' concern='+concern+'の章固有適用として記録する。','basis':'agent-inference','recorded_at':now})
(D/'design-chapter-ops.json').write_text(json.dumps(ops,ensure_ascii=False,indent=2)+'\n')
for i,op in enumerate(ops):
 p=D/f'design-op-{i:02d}.json';p.write_text(json.dumps(op,ensure_ascii=False,indent=2)+'\n');run([writer,'apply','--state',state,'--op',json.dumps(op,ensure_ascii=False)],f'design-v6-op-{i:02d}')
run([SS/'skills/run-system-spec-compile/scripts/compile-spec-doc.py','compile','--spec',state,'--references',D/'system-spec/fetched-references.json','--out-dir',D/'system-spec','--repo-root',D],'design-v6-compile')
run([SS/'scripts/validate-coverage-matrix.py','--matrix',state,'--require-complete','--require-basis','--require-foundation'],'design-v6-coverage')
run([SS/'scripts/validate-source-citation.py','--targets',state,'--references',D/'system-spec/fetched-references.json','--state',state,'--repo-root',D],'design-v6-citation')
current=json.loads(state.read_text());assert current['qa_log'][:len(initial['qa_log'])]==initial['qa_log'];assert current['requirements_foundation']==prior['requirements_foundation'];assert [d for d in current['decisions'] if d['id']!='D4']==[d for d in prior['decisions'] if d['id']!='D4'];assert next(d for d in current['decisions'] if d['id']=='D4')==decision;assert current['matrix']==prior['matrix'];assert current['approval_log']==prior['approval_log'];assert current['targets']==prior['targets']
for qid in ['qa-o1-fixture-v3','qa-job-choice-fixture-v3']:
 a=next(q for q in current['qa_log'] if q['id']==qid);b=next(q for q in prior['qa_log'] if q['id']==qid)
 assert {k:v for k,v in a.items() if k not in ['design_applications','provenance']}=={k:v for k,v in b.items() if k not in ['design_applications','provenance']}
for cat,text in ext.items():assert text in (D/'system-spec'/f'{cat}.md').read_text()
(D/'design-correction-provenance.json').write_text(json.dumps({'kind':'new-synthetic-positive-decision-definition','actual_user_approval_claimed':False,'base_state':'positive-input-v3/before-state.json (original48QA)','reason':'v6は旧fixture/実走/確定QAを編集せず48QA基礎から新規定義する。v5と同じ50問答/採択/承認/targets/具体設計解釈を保持し、D4のTCO構築運用移行撤退/periodと案別比較を正規set-decisionの初回入力で補完。公式3文書を新たに実HTTP取得し、givenと設計推論と公式事実を区別する。保護QAの上書き・評価PASS seedは無い。','normal_update_of_v4':False,'old_v4_unchanged':True,'original48QA_unchanged':True,'all_question_answer_basis_source_answered_at_unchanged':True,'foundation_D1_D3_matrix_approvals_targets_unchanged':True,'D4_only_comparison_record_refined':True,'interpretations_are_agent_inference':True,'new_QA_or_approval':False,'D4_adoption_answer_unchanged':True,'D4_confirmed_at_note':'givenの記録上限時刻で実選択の実測ではないと明記','decision_evidence':'decision-evidence/response-metadata.json','qa_design_recording':'新fixtureの初回canonical chunkで記録。writerの正規仕様どおりdesign_application_provenance未指定はdialogue時記録を意味し、legacy_backfillや実利用者承認を偽称しない。fixture全体は合成。','chapters':'set-design-application/set-doctrine-applicationで既存textをprefix保持し具体適用を追加。qa_refs描画の機能を迂回せず、sourceが用意する章単位記録を使う。','source_changed':False,'PASS_or_evaluation_seeded':False,'scenario_contract_changed':False,'commands':commands},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,D/'design-fixture-correction.py')
public=W/'eval-log/dev-graph/live-trial-fixtures/pr86-system-spec-positive-v6';assert not public.exists();shutil.copytree(D,public)
print('v6 D4 positive given rebuilt through canonical writers; no SUT source change')
