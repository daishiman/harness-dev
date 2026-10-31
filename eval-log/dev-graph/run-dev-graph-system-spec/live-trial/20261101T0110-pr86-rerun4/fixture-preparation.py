from pathlib import Path
import json,subprocess,sys,shutil,hashlib,os
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec91';fx=r/'fx';src=T/'runs/sysspec90/fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec91','run-dev-graph-system-spec','--session-root','fx'],check=True)
subprocess.run(['git','init','-q','-b','main',str(fx)],check=True)
subprocess.run(['git','-C',str(fx),'-c','user.name=live-trial','-c','user.email=live-trial@example.invalid','commit','-q','--allow-empty','-m','fixture: canonical resume inputs'],check=True)
(fx/'.git/info/exclude').write_text('plugins/\n.claude/\n')
shutil.copytree(src/'system-spec',fx/'system-spec')
env={k:v for k,v in os.environ.items() if k!='CLAUDE_PROJECT_DIR'}
cp=subprocess.run([sys.executable,'-B',str(W/'plugins/dev-graph/scripts/build-init-scaffold.py'),'--repo-root',str(fx),'--hook-source','plugin'],env=env,check=True,capture_output=True,text=True)
(r/'workdir/fixture-init-receipt.json').write_text(cp.stdout)
assert json.loads((fx/'.dev-graph/state/graph.json').read_text())['nodes']==[]
# 登録前の草案だけを入力として渡す。評価証拠と確定結果は削除する。
draft=json.loads((src/'eval-log/run-dev-graph-system-spec/c02-import-payload.json').read_text())
draft.pop('expected_graph_revision',None)
for a in draft['artifacts']:
 a.pop('confirmation_evidence',None)
 a.get('source_lineage',{}).pop('imported_at',None)
(fx/'candidate-import.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n')
files={p.relative_to(fx).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (fx/'system-spec').rglob('*') if p.is_file()}
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source_run':'20261101T0110-pr86-rerun3 (independent FAIL)','preparation':'前実走の正規writerによる確定問答・出典資料・compiled章を再開入力として複製。C01の正規builderでこの新repoを初期化。graph.nodesは空。C02 payloadは草案のみでconfirmation_evidenceとimported_atを削除。評価report・監査台帳・再利用receipt・PASS結果・登録nodeを種として置いていない。targetは全canonical flowをこのrepoで新規実行し、独立評価と登録を実証する。','source':str(src/'system-spec'),'seed_sha256':files,'byte_identical':all((src/'system-spec'/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False,'graph_nodes_initial':0,'draft_is_confirmation_evidence':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec91','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec90/workdir/task.md').read_text().replace('sysspec90','sysspec91')
a=body.index('実行前の契約確認:')
body=body[:a]+"""
実行前の契約確認:
- 現行C19のPurpose/Output・R2・goal-seek配線を全文読む。本処理のroot照合、隔離unit検証の範囲、親と責務Agentの役割、周回と責務切替の区別をそこに従って実行する。
- 毎周回、現行SKILLの「ゴールシーク検証」にあるcoverage/source-citation/schemaの3 CLIを実行してからIN1を記録する。loop1も空graphへschema CLIを実行し、R3まで待たない。3つの実測exit0を得てからのみPASSを書き、未実施/待ちはnot_achievedとする。その記録の後でintermediate/hash検査を行う。初期化済みという入力条件や後周回の成功で代用しない。
- 各run Skillの最小成果物を提示した直後に事前回答standardを記録し、その後でsemantic Agent/意味層のtestを開始する。記録を最後にまとめない。
- 親は未達checklistを実際の周回として管理し、新しい周回の操作を開始する前に直前のmerged_directive_for_nextを入力する。責務Agentのpromptには固定C24 receipt、元goal/hash、対応する周回/次指示、担当prompt、適用する境界を渡す。
- Agentが検証用のscratchを使うなら、事前に許可された絶対scratch配下でcallerの取込元へ書かないことを確認し、その結果を本処理の評価・登録の根拠へ代用しない。本処理は必ずcanonical Skill/CLI。独立検証は既存のcanonical testと実際の出力のread-only確認で行える。
- コードベース全体のunit回帰は外側のrunnerで914件PASS確認済み。この値を今回のflow実行の証拠へ代用してはならないが、各Skillが明示要求する個別test以外の大規模suiteをこの実走で追加する必要はない。
"""
(r/'workdir/task.md').write_text(body)
print('prepared sysspec91: initialized resume repo; graph empty; no evaluations seeded')
