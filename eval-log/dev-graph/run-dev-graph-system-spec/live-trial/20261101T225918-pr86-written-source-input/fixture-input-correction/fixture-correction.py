from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys
sys.dont_write_bytecode=True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');T=Path('/private/tmp/claude-501/pr86-ci-live/lt')
D=T/'positive-input-v3';assert not D.exists();D.mkdir()
shutil.copytree(T/'runs/sysspec95/fx/system-spec',D/'system-spec')
state=D/'system-spec/spec-state.json';before=json.loads(state.read_text());(D/'before-state.json').write_bytes(state.read_bytes())
now=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
provenance='CI live-trial の正の合成入力 v3 を orchestrator が作成。111でO1実現要件が欠けていたことをC05と独立評価が検出したため補完する。以下の問答・承認はシナリオ上の利用者の既定発言であり、実利用者との対話・本番の承認ではない。対象agentが問答やPASSを自作したものでもない。'
answer='''O1 のテスト用要件を次で確定する。対象は qa-024 の有効契約から当月に発生する請求予定とその契約明細。請求予定ごとに契約ID・対象年月・予定請求期限・期待明細を保持する。予定請求期限を過ぎても有効な請求書がない、または請求書に必要な契約明細が欠ける場合を請求漏れとする。金額の食い違いは既存の突合機能へ分け、請求漏れの定義と混同しない。
15分ごとに自動走査し、期限超過から30分以内に担当者のWeb画面の「請求漏れ」一覧へ出す。契約担当の経理担当者と経理リーダーが閲覧し、件数・取引先・対象月・期限・不足明細・金額を表示して金額順に並べる。外部メールやSlackは追加しない。請求書を正しく発行すると次の走査で解消し、単なる手動の無視では解消扱いにしない。検知と解消を既存の追記専用監査ログへ残す。
請求予定は有効契約の期間と月次条件から漏れなく作り、取消済み・対象期間外の契約を除く。締め処理は全有効契約と請求予定・有効請求書を同じ整合した業務スナップショットで再照合し、漏れが残れば確定を拒否して一覧へ返す。結果は対象件数と未解消件数を保持する。締め完了直後の未解消件数をO1の月次計測値とし、元の「月次0件」と「3か月連続0件」を維持する。締め後の変更は元どおり赤黒訂正で、検知履歴・締め検査結果・監査ログを物理削除しない。
新しい表は billing_expectations、missing_billing_cases、billing_closing_checks、job_outbox とし、既存PostgreSQL 16内に置く。請求予定/検知ケースは契約ID・対象年月・種別の一意キーで重複反映を防ぐ。GET /billing-missing は一覧取得、POST /billing-missing/checks は再検査jobを202で受付け、GET /jobs/{id} で状態を返す。認可と更新競合は既存の担当者/リーダー権限と楽観ロックの規則を使う。業務ルールはAPIとworkerで共通に呼ぶユースケースへ置き、FastAPIやDB rowの型を業務中核へ持ち込まない。'''
execution='''比較した2案のうち pg-worker-cron を選ぶ。既存PostgreSQL 16のjob_outboxへ業務更新と同じtransactionで投入し、社内k8s上のPython worker Deploymentが1秒間隔でclaimする。重い突合と手動の再検査を処理し、15分ごとの請求漏れ走査は同じworker imageのCronJobで起動する。CronJobの重複起動抑制に加え、DB claimの排他・lease/fencing token・業務の一意キーと冪等性を使う。再試行で同じjobが実行され得ることは認め、業務効果の二重反映を禁止する。リトライ上限と失敗状態を保存し、30分を超えた未処理と失敗jobを運用画面へ出す。Worker停止時は永続outboxから再開する。監査ログは元の追記専用規則を保ち、業務/検知結果と整合するtransaction境界で残す。
API BackgroundTasksへ処理を寄せ、CronJobから内部HTTPを叩く案はAPI再起動・replica数・再試行・内部認証の運用が結び付くので採らない。外部broker/Redis/新しい保存基盤は足さない。両案のOSSライセンス追加費を0円とする比較はこの合成fixture内の前提であり、実サービスの総費用0や実相場を主張しない。workerのCPU/DB負荷と実装・監視の工数は残る。'''
qa1='qa-o1-fixture-v3';qa2='qa-job-choice-fixture-v3'
app={'knowledge_ref':'plugins/system-spec-harness/skills/ref-system-design-knowledge/references/clean-architecture.md#中核概念','principle':'依存の向きを外側の機構から業務の規則へ向ける','applicability':'applied','rationale':'請求漏れ判定をHTTP/CronJob/workerで共通の業務ユースケースとし、DB取得と通知表示をport/adapterへ分ける。','tradeoffs':['adapterとworkerの境界テストが増える。','永続jobと冪等キーで重複反映を抑える運用が必要。']}
turns=[{'qa_id':qa1,'question':'O1の請求漏れをどう定義し、いつ検知し、誰へ示し、どのデータで月次成果を計測しますか。','answer':answer,'basis':'user-decision','source':{'kind':'user-dialogue'},'answered_at':now,'provenance':provenance,'design_applications':[app],'approval_id':'appr-o1-fixture-v3','approval_note':'合成fixtureのO1詳細要件を、シナリオ上の利用者が上記answerどおり確定した設定。実利用者の承認ではない。','ops':[{'action':'add-qa-ref','category':c,'platform':'web'} for c in ['database','backend','ui-ux','maintenance-ops']]},
{'qa_id':qa2,'question':'非同期実行の構成として、(1) PostgreSQL outboxと独立worker/CronJob、(2) PostgreSQL outboxとAPI BackgroundTasks/内部HTTP起動を比較しました。どちらを採用しますか。別案・保留も選べます。理由と運用条件を教えてください。','answer':execution,'basis':'user-decision','source':{'kind':'user-dialogue'},'answered_at':now,'provenance':provenance,'design_applications':[app],'ops':[{'action':'add-qa-ref','category':c,'platform':'web'} for c in ['backend','database','infrastructure','maintenance-ops']]}]
(D/'turns.json').write_text(json.dumps(turns,ensure_ascii=False,indent=2)+'\n')
urls=['https://www.postgresql.org/docs/16/sql-select.html','https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/','https://fastapi.tiangolo.com/tutorial/background-tasks/']
def option(oid,label,pros,cons,risks,burden):
 return {'id':oid,'label':label,'cost_model':{'category':'free','amount':0,'currency':'JPY','billing_period':'追加OSSライセンス費','tco':'合成fixtureの比較前提。既存PG/k8sを使い追加契約なし。実行資源と実装/監視工数は別に必要。'},'free_tier_limits':'既存OSS構成。実行資源/DB容量に制約があり、総費用0を意味しない。','goal_fit':'G1/O1の永続ジョブと自動走査、G2のWebからの非同期突合を支える。','security_fit':'既存の権限・追記監査と最小権限のDB接続を使う。内部HTTP案は追加の認証面を持つ。','pros':pros,'cons':cons,'risks':risks,'lock_in':'PGのclaim SQLとk8sの運用へ依存するが既存の採用制約内。','ops_burden':burden,'evidence_refs':urls}
decision={'id':'D4','category':'backend','question':'非同期突合とO1自動検知のジョブ実行構成','status':'confirmed','serves_goals':['G1','G2'],'options':[
 option('pg-worker-cron','既存PG outbox＋独立Python worker＋k8s CronJob',['APIライフサイクルと分離','永続queueと同じ業務規則を再利用'],['workerのdeploy/監視が増える'],['lease/fencingと冪等実装が必要','Cronの重複抑制だけではexactly-onceを保証しない'],'中: worker/CronJob・未処理齢・失敗件数を監視'),
 option('api-background-http','既存PG outbox＋API BackgroundTasks＋Cronの内部HTTP呼出し',['worker専用imageを減らせる'],['APIの再起動と負荷へ結合','内部HTTP認証と再開処理が増える'],['API停止時に処理が遅れる','複数replica/再試行時に排他が必要'],'中〜高: API運用とjob運用が結合')],
 'recommendation':{'option_id':'pg-worker-cron','rationale':'既存PG/k8sの範囲で永続性とAPIからの分離を保ち、追加brokerを避ける。採否は合成QAで明示済み。','caveats':['CronJobだけでexactly-onceは保証しない。DB排他/lease/fencing/冪等性を別に設計する。','FastAPIのBackgroundTasksは応答後の処理であり、それ自体を定期schedulerや永続queueとは扱わない。','費用比較は明示した合成fixture前提で、実環境価格の見積ではない。'],'confidence':'medium','latest_checked_at':now,'comparison_basis':{'goal_fit':'どちらも実装可能だが独立workerはAPI停止と分離できる。','tco':'追加OSSライセンス費0というfixture前提。独立workerはdeploy/監視工数、API案は内部認証/復旧工数が増える。','security':'PG最小権限を共通に使う。API案は内部HTTP認証面が増える。','operations':'独立workerのpending/lease/失敗を可視化。API案はAPIの負荷/再起動と結合する。','lock_in':'両案とも既存PG/k8s制約内。PG固有claim SQLへの依存は残る。'}},'qa_ref':qa2,'user_decision':{'option_id':'pg-worker-cron','confirmed_at':now}}
(D/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
writer=W/'plugins/system-spec-harness/skills/run-system-spec-elicit/scripts/apply-spec-transition.py'
cmds=[[sys.executable,'-B',str(writer),'chunk','--state',str(state),'--turns',str(D/'turns.json'),'--max-loops','2','--require-all'],[sys.executable,'-B',str(writer),'set-decision','--state',str(state),'--decision',str(D/'decision.json')],
 [sys.executable,'-B',str(W/'plugins/system-spec-harness/skills/run-system-spec-compile/scripts/compile-spec-doc.py'),'compile','--spec',str(state),'--references',str(D/'system-spec/fetched-references.json'),'--out-dir',str(D/'system-spec'),'--repo-root',str(W)],
 [sys.executable,'-B',str(W/'plugins/system-spec-harness/scripts/validate-coverage-matrix.py'),'--matrix',str(state),'--require-complete','--require-basis','--require-foundation'],
 [sys.executable,'-B',str(W/'plugins/system-spec-harness/scripts/validate-source-citation.py'),'--targets',str(state),'--references',str(D/'system-spec/fetched-references.json'),'--state',str(state),'--repo-root',str(D)]]
records=[]
for i,cmd in enumerate(cmds):
 p=subprocess.run(cmd,cwd=W,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True);(D/(str(i)+'.stdout')).write_text(p.stdout);(D/(str(i)+'.stderr')).write_text(p.stderr);records.append({'argv':cmd,'exit':p.returncode});print(i,p.returncode,p.stdout[-150:],p.stderr[-150:]);assert p.returncode==0
current=json.loads(state.read_text());assert current['qa_log'][:len(before['qa_log'])]==before['qa_log'];assert current['requirements_foundation']==before['requirements_foundation'];assert current['decisions'][:len(before['decisions'])]==before['decisions']
for cat in ['backend','database','ui-ux','maintenance-ops']:
 assert qa1 in current['matrix'][cat]['web']['qa_refs']
 assert '請求漏れ' in (D/'system-spec'/(''+cat+'.md' if cat!='maintenance-ops' else 'maintenance-ops.md')).read_text() if (D/'system-spec'/(''+cat+'.md')).exists() else True
(D/'fixture-correction-provenance.json').write_text(json.dumps({'kind':'synthetic-positive-input-repair','reason':'111の正規C05 highと独立検証により、既承認O1の実現要件が欠けていたことを確認。テストの既定発言として詳細とD4を追加。','actual_user_approval_claimed':False,'existing_QA_and_foundation_unchanged':True,'new_QA_ids':[qa1,qa2],'new_decision':'D4','original_state_sha256':hashlib.sha256((D/'before-state.json').read_bytes()).hexdigest(),'repaired_state_sha256':hashlib.sha256(state.read_bytes()).hexdigest(),'writer_only':True,'commands':records,'scenario_observations_changed':False,'PASS_seeded':False,'official_evidence_urls_checked_during_preparation':urls,'prepared_at':now},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,D/'fixture-correction.py')
print('corrected positive input prepared; no evaluation PASS or graph seeded')
