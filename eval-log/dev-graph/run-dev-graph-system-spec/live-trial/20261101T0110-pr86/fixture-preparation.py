from pathlib import Path
import json,subprocess,sys,shutil,hashlib,datetime
sys.dont_write_bytecode=True
W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');T=Path('/private/tmp/claude-501/pr86-ci-live/lt');O=Path('/private/tmp/claude-501/-Users-dm-dev-dev------harness/4c56fd8f-ccd6-4ef6-a546-d1f3c2d79696/scratchpad/lt');label='sysspec87';r=T/'runs'/label;fx=r/'fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),label,'run-dev-graph-system-spec','--session-root','fx'],check=True)
subprocess.run(['git','init','-q','-b','main',str(fx)],check=True)
subprocess.run(['git','-C',str(fx),'-c','user.name=live-trial','-c','user.email=live-trial@example.invalid','commit','-q','--allow-empty','-m','fixture: confirmed system-spec input'],check=True)
(fx/'.git/info/exclude').write_text('plugins/\n.claude/\n')
(fx/'system-spec').mkdir()
for name in ['spec-state.json','fetched-references.json']:shutil.copy2(O/'runs/sysspec86/fx/system-spec'/name,fx/'system-spec'/name)
state=fx/'system-spec/spec-state.json';original=state.read_bytes();data=json.loads(original);qa_before={q['id']:(q.get('question'),q.get('answer')) for q in data['qa_log']}
applications={
 'qa-031': [('site-reliability-engineering','運用の実体の把握と段階的な更新・復旧','採用するPostgreSQLはqa-031で利用者が選んだ16のままとする。qa-018で提供される15と16は同じ業務要件を満たすため、利用者が挙げた保守期間の長さと次の更新作業の時期を運用上の差として扱う。導入時のマイナー版と復旧手順は実体で確認し、docs/currentの別メジャー版を16の証拠と混同しない。',['ライセンス費は両案0であり、差は更新作業の時期と検証負担。','既存の15前提の記述は16へ整合させる必要がある。']),('ddd','集約の不変条件と境界づけられたコンテキスト','qa-031の版選択はqa-001の既存DB要件のうち版だけを更新する。qa-024の請求書・明細を一つの整合性境界とし、確定後は直接改変せず赤黒訂正を記録する。監査ログは別スキーマへ追記し、G1の単一の信頼できる情報源を保つ。',['強い整合性の境界は請求書単位に限定し、監査への連携とは分ける。'])],
 'qa-002': [('secure-by-design','最小権限と既定拒否','qa-002の社内IdPのOIDCとロール認可・8時間セッションを前提に、qa-026の請求担当・リーダー・内部監査・情報システム部の操作権限を許可表へ分ける。列挙されない操作は拒否し、画面表示だけでなくAPI側でも担当取引先の範囲を判定する設計解釈とする。',['IdP停止の影響を受けるため、障害時の扱いと監査が必要。','細粒度の認可は権限表と境界テストの保守負担を伴う。'])],
 'qa-003': [('information-design','利用文脈を先に固定し、頻度と失敗コストで情報を順位付けする','qa-003のレスポンシブWeb・WCAG2.1AA目標・主要動線3クリック以内を、qa-016/020/021/023の請求担当者・社内PC・数百行・表計算への習熟に照らして解釈する。入力・突合と差分の判断を先に見せ、詳細情報は対応する親の近くへ置き、キーボードから到達できる順序を維持する。',['強調する情報を絞るため、低頻度の情報への到達方法を残して欠落と混同しない。','3クリック目標だけでアクセシビリティの検証を代用しない。'])],
 'qa-004': [('secure-by-design','脅威モデルと独立した多層防御','qa-004のTLS1.3・入力検証・監査ログ・OWASP Top10対策を、qa-030の情報漏えい・金額改変等の事象と守る資産へ対応付ける。通信の暗号化、入力の妥当性、ロール/担当範囲の認可、追記型の記録を別の防御層とし、一つの突破で確定金額と監査ログが同時に失われない境界を設計する。',['防御層ごとに検証と運用記録が増える。','監査に秘密情報や不要な個人情報を残さない制約を併せて持つ。'])],
 'qa-005': [('site-reliability-engineering','宣言的な環境と稼働中の実体の観測','qa-005の社内k8sとGitHub Actionsを、構成変更の追跡・適用済みのイメージ/設定値の確認・段階適用と復旧を同じ運用経路に置くための基盤と解釈する。qa-036で定めた運用条件と、既存のk8s-workload-observability候補を観測の対象へ結び付ける。',['メトリクスやログの保管・閾値調整の運用費が必要。','IaCだけで復旧可能とはせず、実際のリストア訓練を残す。']),('cloud-architecture-patterns','原子性の境界と再送の冪等性','社内k8s上のAPIと非同期workerは同じDBトランザクションに入らない。qa-025で述べた冪等キーによるジョブ起動と再送をその境界に置き、qa-005の配置を、二重適用を吸収できる運用に結び付ける。',['worker側の冪等性と失敗時の再試行状態の記録が必要。'])],
 'qa-006': [('clean-architecture','依存の向きを外側の機構から業務の規則へ向ける','qa-006で採用したFastAPIのREST入口と非同期ジョブを、qa-025の請求書登録・更新・突合・確定・監査検索というユースケースから分離する設計解釈とする。DB rowやFastAPIのrequest型を業務の中核へ持ち込まず、HTTPとworkerの双方から同じ業務境界を呼ぶ。',['port/adapterの変換と境界テストが増える。','単にファイルを層へ分けただけで独立性を満たしたとは扱わない。'])],
 'qa-007': [('clean-architecture','表示形式と業務の正本を境界で分離する','qa-007のReact/TypeScriptと最小限のグローバルストア、qa-032のSPA選択を前提に、画面部品のローカルな状態と利用者/権限など共通の状態を分ける。qa-028の一覧の並べ替え・一致済み明細の折りたたみは表示の責務に置き、金額や突合結果の正本を画面側で再計算しない。',['状態の所有者とAPI境界の型を明示する保守負担がある。','SSRを前提とする公開検索向けの最適化は、社内業務という前提を外れない範囲に留める。'])],
 'qa-008': [('clean-code','意図と効果・失敗を明示し、実行例で手順を検証する','qa-008のオンコール輪番・障害runbook・週次リストア訓練を、誰が何を実行し何を確認すれば回復したと言えるかが読み取れる単位で記録する。バックアップが存在することだけで復旧済みとはせず、既存のRTO/RPOの運用条件と訓練結果へ結び付ける。',['手順と実際の運用がずれないよう、訓練後の更新作業が必要。','自動化は目的ではなく、障害時にも効果と失敗が追えることを優先する。'])]
}
for q in data['qa_log']:
 if q['id'] in applications:
  assert 'design_applications' not in q
  q['legacy_exempt']=True;q['legacy_exempt_reason']='schema1.0の旧試験入力に無かった設計解釈を、同じ問答に基づき試行開始前に補完するため。利用者の新しい回答・承認を作ったという意味ではない。'
state.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
writer=W/'plugins/system-spec-harness/skills/run-system-spec-elicit/scripts/apply-spec-transition.py'
for qid,items in applications.items():
 vals=[]
 for card,principle,rationale,tradeoffs in items:
  ref='skills/ref-system-design-knowledge/references/'+card+'.md#中核概念';assert (W/'plugins/system-spec-harness'/ref.split('#')[0]).exists()
  vals.append({'knowledge_ref':ref,'principle':principle,'applicability':'applied','rationale':rationale,'tradeoffs':tradeoffs})
 payload=r/'workdir'/('design-applications-'+qid+'.json');payload.write_text(json.dumps(vals,ensure_ascii=False,indent=2)+'\n')
 cp=subprocess.run([sys.executable,str(writer),'set-qa-design-applications','--state',str(state),'--qa-id',qid,'--applications',str(payload)],capture_output=True,text=True);assert cp.returncode==0,cp.stderr
op={'action':'set-design-application','category':'infrastructure','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'basis':'agent-inference','text':'現行resource-mapが注入するSite Reliability EngineeringとCloud Architecture Patterns、および既存候補k8s-workload-observabilityを併用する。qa-005の社内k8s/GitHub Actionsへ、宣言的構成と適用済みイメージ・設定値の観測、段階適用と復旧を対応付ける。qa-036の運用条件に対して、観測結果から復旧行動へ進める手順を置く。qa-025の非同期ジョブ起動の冪等キーと再試行状態は、APIとworkerの原子性の境界を跨ぐ二重適用を防ぐ。これらは既存の問答に対する設計解釈であり、新しい利用者承認を意味しない。'}
cp=subprocess.run([sys.executable,str(writer),'apply','--state',str(state),'--op',json.dumps(op,ensure_ascii=False)],capture_output=True,text=True);assert cp.returncode==0,cp.stderr
final=json.loads(state.read_text());assert qa_before=={q['id']:(q.get('question'),q.get('answer')) for q in final['qa_log']}
prov={'source_seed':str(O/'runs/sysspec86/fx/system-spec'),'original_state_sha256':hashlib.sha256(original).hexdigest(),'prepared_state_sha256':hashlib.sha256(state.read_bytes()).hexdigest(),'question_answer_pairs_unchanged':True,'design_application_backfilled_qa_ids':sorted(applications),'meaning':'旧入力の欠落を、同じ問答に接地した設計解釈として試行開始前に補った。新しい利用者回答/承認やevaluator PASSは捏造していない。legacy_exemptは実際に旧schemaの入力であることを示す準備用フラグで、専用writerがbackfill完了時に削除した。変更前後SHAと全問答の一致を確認した。','upstream_findings_seeded':False}
(r/'workdir/fixture-provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2)+'\n');shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),label,'--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec86/workdir/task.md').read_text().replace(str(T/'runs/sysspec86'),str(r))
body+='''\n今回の入力の補足（試行開始前の準備）:\n- 質問・回答・採択判断は前の入力のまま。qa単位の設計解釈8件を専用writerでlegacy_backfillし、旧『curated card 0件』というinfrastructureの記述を現行注入カードに整合させた。fixture-provenance.jsonとfixture-preparation.py参照。利用者の新しい回答やevaluator PASSを作ったものではない。\n- D1で利用者が選んだ版はPostgreSQL 16。docs/currentの別メジャー版を採用16の出典に代用しない。正規doc-fetch経路で https://www.postgresql.org/docs/16/ と https://www.postgresql.org/support/versioning/ を実際に取得・記録し、採用16.xの最新マイナー版・保守期間を確認する。R5/set-decisionの正規writerでD1のpros/evidence_refs/latest_checked_atを取得証跡と整合させる（採択option_id=pg16は変えない）。旧入力にある『取得済み16.15』などの記述を検証せず現在の根拠に使わない。\n- C19自身の全責務promptを読み、最小の実成果物を提示した時点で事前回答standardを記録する。goal-spec/progress/intermediateを最後にまとめて作らず、開始・各周回で記録しながら進める。未達のC19責務はSKILLのgoal_seek.fork=subagentに従い、該当責務の型/本文を渡したAgentとして実際にforkする。上流のcompleteness evaluatorのAgentだけでC19責務Agentを代用しない。\n- evaluatorが不合格なら、指摘が既存の確定問答・取得資料から正規writerで直せる範囲かを判断し、可能なものはSKILLの上限内で修正→再compile→新しい独立評価を行う。新しい利用者判断が要るなら捏造せずFAIL。PASSになる前のC02登録は禁止。\n'''
(r/'workdir/task.md').write_text(body)
print('sysspec87準備完了。問答不変・原則採否を正規writerでbackfill。')
