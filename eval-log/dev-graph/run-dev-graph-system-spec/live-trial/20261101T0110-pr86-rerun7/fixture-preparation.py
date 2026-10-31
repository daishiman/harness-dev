from pathlib import Path
import json,subprocess,sys,shutil,hashlib,os
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec94';fx=r/'fx';src=T/'runs/sysspec93/fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec94','run-dev-graph-system-spec','--session-root','fx'],check=True)
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
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source_run':'20261101T0110-pr86-rerun6 (independent FAIL)','preparation':'前実走の正規writerによる確定問答・出典資料・compiled章を再開入力として複製。C01の正規builderでこの新repoを初期化。graph.nodesは空。C02 payloadは草案のみでconfirmation_evidenceとimported_atを削除。評価report・監査台帳・再利用receipt・PASS結果・登録nodeを種として置いていない。targetは全canonical flowをこのrepoで新規実行し、独立評価と登録を実証する。','source':str(src/'system-spec'),'seed_sha256':files,'byte_identical':all((src/'system-spec'/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False,'graph_nodes_initial':0,'draft_is_confirmation_evidence':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec94','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec93/workdir/task.md').read_text().replace('sysspec93','sysspec94')
a=body.index('実行前の契約確認:')
body=body[:a]+"""
実行前の契約確認:
- 現行C19のPurpose/Output・R2・goal-seek配線を全文読む。本処理のroot照合、隔離unit検証の範囲、親と責務Agentの役割、周回と責務切替の区別をそこに従って実行する。
- 毎周回、現行SKILLの「ゴールシーク検証」にあるcoverage/source-citation/schemaの3 CLIを実行してからIN1を記録する。loop1も空graphへschema CLIを実行し、R3まで待たない。3つの実測exit0を得てからのみPASSを書き、未実施/待ちはnot_achievedとする。その記録の後でintermediate/hash検査を行う。初期化済みという入力条件や後周回の成功で代用しない。
- compileの提示は次の3イベントを分ける。第1に、正規compile CLIを呼ぶBashの末尾で成果物path/digestのCLI結果に続いて「開き方: less <今回の絶対repo-root>/system-spec/index.md」をstdoutへ必ず出力して返す。このBash呼出しにはchoice記録、test、Agentを混ぜない。第2に、次のassistant会話メッセージで現物path・実測digest・上記lessコマンドを提示する。第3に、その会話より後の別Bashでeval-log/choices/compile-standard.jsonへstage=compile・choice=standard・現物path/digest/open_withを記録する。その後でのみpytest/OUT1 63件testsやAgentを実行する。choice生成コマンド内のopen_withの記載やchoice生成後の説明は、選択前の提示に数えない。機械的に見えるOUT1 suiteも選択後に実行し、Agentへも同じ順序を渡す。単なるread/open guard以外の全評価はこの選択の後に行う。
- この隔離環境のBash guardはcommand文字列を検査するので、JSONの自由文章内の英単語 open をmacOS CLIと誤認する場合がある。監査/evaluator自身が判断結果をJSONとして書くときは、最初から許可済みWrite toolで許可された絶対output pathへ書く。これは正規evaluatorの判断/監査reportの出力手段であり、spec/graph/coverage等のcanonical CLIを自作へ置換する意味ではない。C05と各C07/C06/C08監査Agentへも起動promptにこの環境条件を必ず渡す。canonical生成・検証・登録CLIはBashから通常通り実行し、guardが実際に拒否した操作はWriteその他へ迂回せずFAILにする。guard規則やsandboxの変更は禁止。
- 各run Skillの最小成果物を提示した直後に事前回答standardを記録し、その後でsemantic Agent/意味層のtestを開始する。記録を最後にまとめない。
- 親は未達checklistを実際の周回として管理し、新しい周回の操作を開始する前に直前のmerged_directive_for_nextを入力する。責務Agentのpromptには固定C24 receipt、元goal/hash、対応する周回/次指示、担当prompt、適用する境界を渡す。
- Agentが検証用のscratchを使うなら、事前に許可された絶対scratch配下でcallerの取込元へ書かないことを確認し、その結果を本処理の評価・登録の根拠へ代用しない。本処理は必ずcanonical Skill/CLI。独立検証は既存のcanonical testと実際の出力のread-only確認で行える。
- コードベース全体のunit回帰は外側のrunnerで914件PASS確認済み。この値を今回のflow実行の証拠へ代用してはならないが、各Skillが明示要求する個別test以外の大規模suiteをこの実走で追加する必要はない。
"""
(r/'workdir/task.md').write_text(body)
print('prepared sysspec94: initialized resume repo; graph empty; no evaluations seeded')
