from pathlib import Path
import json,subprocess,sys,shutil,hashlib,os
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec98';fx=r/'fx';src=T/'runs/sysspec97/fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec98','run-dev-graph-system-spec','--session-root','fx'],check=True)
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
files={p.relative_to(fx).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (fx/'system-spec').rglob('*') if p.is_file()}
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source_run':'20261101T0200-pr86-name (independent FAIL)','preparation':'前実走の正規writerによる確定問答・出典資料・compiled章を再開入力として複製。C01の正規builderでこの新repoを初期化。graph.nodesは空。C02 payloadは草案のみでconfirmation_evidenceとimported_atを削除。評価report・監査台帳・再利用receipt・PASS結果・登録nodeを種として置いていない。targetは全canonical flowをこのrepoで新規実行し、独立評価と登録を実証する。','source':str(src/'system-spec'),'seed_sha256':files,'byte_identical':all((src/'system-spec'/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False,'graph_nodes_initial':0,'draft_is_confirmation_evidence':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec98','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec97/workdir/task.md').read_text().replace('sysspec97','sysspec98')
a=body.index('実行前の契約確認:')
body=body[:a]+"""
実行前の契約確認:
- 現行C19のPurpose/Output/R0-R3/goal-seek配線と呼ぶ4 Skill/責務promptを全文読む。固定C24 root、親/責務Agentのログ所有権、goal周回と責務切替、本処理と隔離unitの境界に従う。
- 毎周回、coverage/source-citation/schemaの3 CLIを実測してからIN1を記録する。空graphでもschemaを省略しない。全exit0の後だけPASS、未実施/待ちはnot_achieved。その後にintermediate6キーと元goal/hashを検査。後周回成功の遡及は禁止。
- compile CLIのBash末尾で現物path/digestと「開き方: less <絶対repo-root>/system-spec/index.md」をstdoutへ出す。この呼出しにchoice/test/Agentを混ぜない。提示より後の別呼出しでcompile-standard.jsonへchoice=standard/path/digest/open_withを記録してからOUT1 63 tests/評価Agentを実行する。
- 各run Skillで最小成果物を提示した直後に事前回答standardを記録する。新周回の操作より前に直前のmerged_directive_for_nextを入力し、責務Agentへ固定receipt/元goal/hash/担当prompt/周回指示を渡す。
- C05の起動直前に、次の環境と保存契約を会話で共有してからhelper出力そのままのSkill argsで呼ぶ。C05/R2-delegate 2.4とR1-score 4.3のとおり、評価/監査JSONの保存は「python3 -c 'import pathlib,sys; pathlib.Path("<保存先の絶対パスをリテラルで直接記す>").write_text(sys.stdin.read(), encoding="utf-8")' <<'JSON'」の形を使い、引用heredocの本文には妥当なJSONだけを渡す。出力先をp等の変数へ入れてp.write_textする形はconfirmed-chapter guardが静的に解決できないので使わない。C05のallowed-toolsにないWriteやcatリダイレクトを要求しない。必要なJSON組立はread-only Pythonのstdoutで行い、正規C05自身の判断と実fork結果を無改変で保存する。C06出力も正規writerが同じliteral保存形で扱う。
- このrunはSHELL=/bin/zsh、TMPPREFIXを許可run/tmp内へ固定した環境で、長い引用heredocの保存を検証済み。sourceの保存方式をprintf等へ変える必要はない。外側の隔離guardは「許可eval-logのliteral Pathへstdinを無改変で保存するPython」かつ「引用heredocがJSON」のデータ本文だけをmacOS CLI文字列探索から除外する版で、実コマンド・外部接続・書込rootの制約は維持される。guard/settings/sandbox/ソースを被験側で変更しない。
- sourceが明示する正常な回復を禁止しない。confirmed-chapter guardが保存先不明のreport書込を拒否した場合は、R1-score 4.3が指示するとおりspec_dir/outputを変えず保存先をliteralへして再試行できる。保護仕様章やspec-stateの書換・外部サービス接続・別repoへの逃避を実行してはならない。隔離guardが拒否した外部effectを別tool経由で実行しない。任意のreadonly診断が拒否されたら同じraw pathの探索をやめ、正規Agent応答/監査台帳/TaskOutput等の提供済み証拠で確認する。
- 検証用scratchは事前許可の絶対pathだけ。caller取込元はread-only、scratch成果をC05 snapshot/C02取込元へ流用しない。各Skillが明示する個別test以外の大規模unit回帰は外側914PASSで確認済みだが、これを今回flow実行の証拠へ代用しない。
- qa-008入力は前runで原初schema1.0 fixtureから正規writerにより補完し直したもの。元問答/承認/採択は不変、未確認RTO/RPOへの言及はない。今回も再compile・新しい独立評価・正規C02登録を実証し、seedのcompiled章や過去PASSを行動証拠へ代用しない。
"""
body=body.replace('prepare-evaluation.py','build-evaluation-context.py')
# fixture独自の「自作script全面禁止」が正規C05のJSON整形まで拒否する曖昧さを除く。
a=body.index('経路に関する絶対制約');b=body.index('foundation と各セル',a)
body=body[:a]+"""経路と役割ごとの保護条件:
- 仕様state・出典記録・章はsystem-spec-harnessの正規writerだけで生成し、graphと登録contentはC02単一writerで作る。dev-graph親がこれらを生成する独自driver/renderer/evaluatorを作り、正規Skillを代替することは禁止。正規writerへ渡す入力JSON、呼出しログ、実行結果の構造化はwriterそのものの代替とは区別する。
- C05は正規Skillの本物のforkで評価し、C07/C06/C08は実Agentを1件ずつ起動して完了を待ち、実completionのreceipt/digestへ判定を結ぶ。親の自己判定や手製のPASSで代替しない。
- 正規C05自身が、実際に行った意味評価・canonical gate stdout・実auditor結果をJSONへ整形することは、親による偽evaluatorではない。C05のread-only Pythonのstdoutや許可scratchでの一時的serializerは、それが文書/state/graphを生成/変更せず、独立評価を代替せず、最終JSONがC05の実判断とreceiptを忠実に保持し、指定されたreport pathだけを最終出力とする場合に区別して扱う。単に「自作script」という語が出たことだけで未達とせず、実際の書込先・処理・帰属を確認する。各roleのallowed-toolsは尊重し、C05へWrite等を追加しない。
- このhostのAgentは、run_in_background/nameを指定しなくてもruntimeがAsync launchを返す。C05が明示的にbackground/nameを要求しないこと、1message1forkで実completion確定後に次を起動すること、起動受理payloadを判定にしないこと、台帳の全必須行がresolvedであることを確認する。runtimeのAsyncという表示だけを、明示的なasync/canary選択や並列監査と同一視しない。実際に並列起動・起動受理の判定流用・receipt不一致があればFAIL。
- 責務promptをその出力前に読み、必須Verifier/Agentを省略しない。 sourceのchecklist/feedback契約、C24固定root、各周回3CLI実測とIN1/6キー/hash記録、C05の独立性/全gate、C02単一writer/lineage/evaluated_digestはすべて必須。
- 正規SkillがUnknown/必須gateが未達なら別実装へ逃げずFAIL。出力JSONの保存先不明による拒否はsource R1-score4.3のliteral保存先への正規再試行を認める。sourceが明示する回復まで一律禁止しない。仕様書の直接改変・偽評価・外部effectの拒否を別toolで迂回することは認めない。

"""+body[b:]
# 過去試行の成功/失敗というラベルを、今回の成果の代用にしない。
body=body.replace('前の実走はFAILであり、その評価結果を今回の証拠に転用しない。','過去の実走の評価結果は、今回の行動や判定の証拠へ転用しない。')
# 保存方式の例を、評価の本体やhostの実動作と混同しない。
a=body.index('実行前の契約確認:')
body=body[:a]+"""実行前の契約確認:
- 現行C19と4 SkillのSKILL/責務promptを全文読み、そのゴールと停止条件を実行する。C24 receipt/rootを固定し、各生成Bashでexport/cd/pwdを確認する。親はC19集約ログ、子は各責務dirを所有する。
- 毎周回coverage/source-citation/schemaの3CLIを実行してからIN1を記録する。空graphもschema実行、全exit0後のみPASS、未実施/待ちはnot_achieved。その後intermediate6キーと元goal/hashを検査。直前の次指示を新周回より先に入力する。
- 各run Skillの最小成果物を提示してから事前回答standardを記録する。compile CLI末尾にpath/digestと「開き方: less <絶対repo-root>/system-spec/index.md」を表示し、その後の別呼出しでcompile-standard.jsonへ記録する。OUT1 tests/意味評価Agentはその後。
- C05の直前にhelperの成功出力そのままのargsを渡す。C05へrole毎の保護条件とこのhostのAsync応答の実態を共有する。reportのspec_dir/outputは引数どおり、指定pathへliteral保存し、原文JSON/receiptを忠実に保持。R1/R2の安全な保存例と同じ境界を満たす一時的なJSON整形と、正規evaluatorを置換する生成器を混同しない。sourceが禁止する仕様state/章/graphの書換はしない。
- hostはzsh/TMPPREFIXを許可run内へ固定、引用heredoc使用可。隔離guardのJSONデータ識別はprovenanceどおりで書込root/外部effect制約は維持。被験側はguard/settings/sandbox/plugin sourceを変えない。
- scratch単体検証は許可絶対pathだけ、caller取込元はreadonly、scratch成果をC05/C02証拠へ代用しない。コード全体回帰は外側で914PASS済みだが今回のflow行動証拠へ代用しない。
- qa008は原初schema1.0から正規backfillした同一問答の入力で、未確認RTO/RPO文は除去済み。既存問答/承認/採択を変えず、今回の再compile・新しい独立評価・正規C02登録を行う。
"""
(r/'workdir/task.md').write_text(body)

# 使用する環境をboot前に固定し、元guardと過去runを改変しない。
settings=fx/'.claude/settings.local.json';config=json.loads(settings.read_text());hook=config['hooks']['PreToolUse'][0]['hooks'][0];hook['command']=hook['command'].replace('/hook/guard.py','/hook/guard-json-data.py');settings.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
shellhome=r/'shell-home';shellhome.mkdir();shellenv='export PATH="'+str(T/'bin')+':/Users/dm/.local/bin:/Users/dm/miniconda3/bin:/usr/bin:/bin:/usr/sbin:/sbin"\nexport TMPDIR="'+str(r/'tmp')+'/"\nexport TMPPREFIX="'+str(r/'tmp/zsh')+'"\n'
for name in ['.zshenv','.zprofile']:(shellhome/name).write_text(shellenv)
(r/'workdir/extra-env.txt').write_text('SHELL=/bin/zsh\nCLAUDE_CODE_SHELL=/bin/zsh\nZDOTDIR='+str(shellhome)+'\nTMPPREFIX='+str(r/'tmp/zsh')+'\n')
for name in ['fixture-qa008-correction.json','qa008-original-input.json','qa008-prior-backfill.json','qa008-grounded-applications.json','fixture-canonical-backfill.log','fixture-canonical-compile.log']:
 shutil.copy2(T/'runs/sysspec97/workdir'/name,r/'workdir'/name)
for name in ['pr86-guard-json-tests.json','pr86-heredoc-probe.json','pr86-heredoc-shell-probe.json']:shutil.copy2(Path('/tmp')/name,r/'workdir'/name)
shutil.copy2(T/'hook/guard-json-data.py',r/'workdir/isolation-guard-source.py')
g=T/'hook/guard-json-data.py';(r/'workdir/guard-provenance.json').write_text(json.dumps({'guard_source':str(g),'guard_sha256':hashlib.sha256(g.read_bytes()).hexdigest(),'original_guard_source':str(T/'hook/guard.py'),'original_guard_sha256':hashlib.sha256((T/'hook/guard.py').read_bytes()).hexdigest(),'rule_change':'macOS CLI規則のみ、ASTで確認したeval-log内literal/stdin無改変writerへ渡す引用JSONデータ本文を除外。他の全規則/許可root/sandbox制約は維持。','boundary_cases_passed':18,'shell':'/bin/zsh','TMPPREFIX':str(r/'tmp/zsh'),'heredoc_probe_bytes':65537,'settings_sha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'protected_chapter_guard_changed':False},ensure_ascii=False,indent=2)+'\n')
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['qa008_input_correction_inherited']='fixture-qa008-correction.json (sysspec97以前の補完を継承、今回stateは前runとbytes同一)';v['environment_proof']='guard-provenance.json';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print('prepared sysspec98: source closure unchanged; source-conforming literal JSON heredoc writer environment')
