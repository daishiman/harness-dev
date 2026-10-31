from pathlib import Path
import json,subprocess,sys,shutil,hashlib,os
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec96';fx=r/'fx';src=T/'runs/sysspec95/fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec96','run-dev-graph-system-spec','--session-root','fx'],check=True)
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
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source_run':'20261101T0110-pr86-rerun8 (independent FAIL)','preparation':'前実走の正規writerによる確定問答・出典資料・compiled章を再開入力として複製。C01の正規builderでこの新repoを初期化。graph.nodesは空。C02 payloadは草案のみでconfirmation_evidenceとimported_atを削除。評価report・監査台帳・再利用receipt・PASS結果・登録nodeを種として置いていない。targetは全canonical flowをこのrepoで新規実行し、独立評価と登録を実証する。','source':str(src/'system-spec'),'seed_sha256':files,'byte_identical':all((src/'system-spec'/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False,'graph_nodes_initial':0,'draft_is_confirmation_evidence':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec96','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec95/workdir/task.md').read_text().replace('sysspec95','sysspec96')
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
(r/'workdir/task.md').write_text(body)
# 使用する環境をboot前に固定し、元guardと過去runを改変しない。
settings=fx/'.claude/settings.local.json';config=json.loads(settings.read_text());hook=config['hooks']['PreToolUse'][0]['hooks'][0];hook['command']=hook['command'].replace('/hook/guard.py','/hook/guard-json-data.py');settings.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
shellhome=r/'shell-home';shellhome.mkdir();shellenv='export PATH="'+str(T/'bin')+':/Users/dm/.local/bin:/Users/dm/miniconda3/bin:/usr/bin:/bin:/usr/sbin:/sbin"\nexport TMPDIR="'+str(r/'tmp')+'/"\nexport TMPPREFIX="'+str(r/'tmp/zsh')+'"\n'
for name in ['.zshenv','.zprofile']:(shellhome/name).write_text(shellenv)
(r/'workdir/extra-env.txt').write_text('SHELL=/bin/zsh\nCLAUDE_CODE_SHELL=/bin/zsh\nZDOTDIR='+str(shellhome)+'\nTMPPREFIX='+str(r/'tmp/zsh')+'\n')
for name in ['fixture-qa008-correction.json','qa008-original-input.json','qa008-prior-backfill.json','qa008-grounded-applications.json','fixture-canonical-backfill.log','fixture-canonical-compile.log']:
 shutil.copy2(T/'runs/sysspec95/workdir'/name,r/'workdir'/name)
for name in ['pr86-guard-json-tests.json','pr86-heredoc-probe.json','pr86-heredoc-shell-probe.json']:shutil.copy2(Path('/tmp')/name,r/'workdir'/name)
shutil.copy2(T/'hook/guard-json-data.py',r/'workdir/isolation-guard-source.py')
g=T/'hook/guard-json-data.py';(r/'workdir/guard-provenance.json').write_text(json.dumps({'guard_source':str(g),'guard_sha256':hashlib.sha256(g.read_bytes()).hexdigest(),'original_guard_source':str(T/'hook/guard.py'),'original_guard_sha256':hashlib.sha256((T/'hook/guard.py').read_bytes()).hexdigest(),'rule_change':'macOS CLI規則のみ、ASTで確認したeval-log内literal/stdin無改変writerへ渡す引用JSONデータ本文を除外。他の全規則/許可root/sandbox制約は維持。','boundary_cases_passed':18,'shell':'/bin/zsh','TMPPREFIX':str(r/'tmp/zsh'),'heredoc_probe_bytes':65537,'settings_sha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'protected_chapter_guard_changed':False},ensure_ascii=False,indent=2)+'\n')
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['qa008_input_correction_inherited']='fixture-qa008-correction.json (sysspec95以前の補完を継承、今回stateは前runとbytes同一)';v['environment_proof']='guard-provenance.json';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print('prepared sysspec96: source closure unchanged; source-conforming literal JSON heredoc writer environment')
