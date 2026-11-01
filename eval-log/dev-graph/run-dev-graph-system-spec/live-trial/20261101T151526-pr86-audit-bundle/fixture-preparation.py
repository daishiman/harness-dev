from pathlib import Path
import json,subprocess,sys,shutil,hashlib,os
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec108';fx=r/'fx';src=T/'runs/sysspec101/fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec108','run-dev-graph-system-spec','--session-root','fx'],check=True)
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
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source_run':'20261101T0300-pr86-name3 (FAIL)','preparation':'前実走の正規writerによる確定問答・出典資料・compiled章を再開入力として複製。C01の正規builderでこの新repoを初期化。graph.nodesは空。C02 payloadは草案のみでconfirmation_evidenceとimported_atを削除。評価report・監査台帳・再利用receipt・PASS結果・登録nodeを種として置いていない。targetは全canonical flowをこのrepoで新規実行し、独立評価と登録を実証する。','source':str(src/'system-spec'),'seed_sha256':files,'byte_identical':all((src/'system-spec'/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False,'graph_nodes_initial':0,'draft_is_confirmation_evidence':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec108','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
from pathlib import Path
import json,hashlib,shutil
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec108';fx=r/'fx'
body=(T/'runs/sysspec105/workdir/task.md').read_text().replace('sysspec105','sysspec108')
body+='\n既存sourceの問答履歴の区別をC05直前に共有する: R6-audit-hearingのactive consumerは確定cell.qa_refとrequirements_foundation.effective_source_refsのqa_refである。apply-spec-transition.py::_supersede_qaは補助qa_refsの旧問参照を履歴として残すことを明示許可し、compileは旧版の印と現行根拠ではない旨を描く。qa_refsの存在だけをactive consumerと数えず、主根拠/bindingと置き換え(a)(b)(c)を個別確認する。履歴を削除せず、無効な置き換え・実active consumer・他欠陥があれば通常どおりFAIL。この定義と保存契約を共有後、helper argsを無変更でC05へ渡し、C06にも担当source全体を読ませる。\n'
(r/'workdir/task.md').write_text(body)
# 使用する環境をboot前に固定し、元guardと過去runを改変しない。
settings=fx/'.claude/settings.local.json';config=json.loads(settings.read_text());hook=config['hooks']['PreToolUse'][0]['hooks'][0];hook['command']=hook['command'].replace('/hook/guard.py','/hook/guard-json-data.py');settings.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
shellhome=r/'shell-home';shellhome.mkdir();shellenv='export PATH="'+str(T/'bin')+':/Users/dm/.local/bin:/Users/dm/miniconda3/bin:/usr/bin:/bin:/usr/sbin:/sbin"\nexport TMPDIR="'+str(r/'tmp')+'/"\nexport TMPPREFIX="'+str(r/'tmp/zsh')+'"\n'
for name in ['.zshenv','.zprofile']:(shellhome/name).write_text(shellenv)
(r/'workdir/extra-env.txt').write_text('SHELL=/bin/zsh\nCLAUDE_CODE_SHELL=/bin/zsh\nZDOTDIR='+str(shellhome)+'\nTMPPREFIX='+str(r/'tmp/zsh')+'\n')
for name in ['fixture-qa008-correction.json','qa008-original-input.json','qa008-prior-backfill.json','qa008-grounded-applications.json','fixture-canonical-backfill.log','fixture-canonical-compile.log']:
 shutil.copy2(T/'runs/sysspec101/workdir'/name,r/'workdir'/name)
for name in ['pr86-guard-json-tests.json','pr86-heredoc-probe.json','pr86-heredoc-shell-probe.json']:shutil.copy2(Path('/tmp')/name,r/'workdir'/name)
shutil.copy2(T/'hook/guard-json-data.py',r/'workdir/isolation-guard-source.py')
g=T/'hook/guard-json-data.py';(r/'workdir/guard-provenance.json').write_text(json.dumps({'guard_source':str(g),'guard_sha256':hashlib.sha256(g.read_bytes()).hexdigest(),'original_guard_source':str(T/'hook/guard.py'),'original_guard_sha256':hashlib.sha256((T/'hook/guard.py').read_bytes()).hexdigest(),'rule_change':'macOS CLI規則のみ、ASTで確認したeval-log内literal/stdin無改変writerへ渡す引用JSONデータ本文を除外。他の全規則/許可root/sandbox制約は維持。','boundary_cases_passed':18,'shell':'/bin/zsh','TMPPREFIX':str(r/'tmp/zsh'),'heredoc_probe_bytes':65537,'settings_sha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'protected_chapter_guard_changed':False},ensure_ascii=False,indent=2)+'\n')
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['qa008_input_correction_inherited']='fixture-qa008-correction.json (sysspec101以前の補完を継承、今回stateは前runとbytes同一)';v['environment_proof']='guard-provenance.json';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

shutil.copy2(__file__,r/'workdir/fixture-task-preparation.py')
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['task_preparation_note']='102のtaskを新しい103の絶対pathへ置換。sourceのC07 Read限定とC01/C05のmatrix_verification契約に同期する。state問答と承認は101からbytes同一で複製、graph0、PASS評価/登録結果のseed無し。';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert json.loads((fx/'.dev-graph/state/graph.json').read_text())['nodes']==[]
assert not (fx/'eval-log/system-spec-completeness-report.json').exists()
print('sysspec108 prepared: source unchanged, input unchanged, definition clarified')

# 重複した同一指示のみを畳み、既存の条件は全て保持する。
body=(r/'workdir/task.md').read_text()
paragraphs=body.split('\n\n'); seen=set();out=[]
for paragraph in paragraphs:
 if paragraph.startswith('既存sourceの問答履歴の区別をC05直前に共有する:'):
  if paragraph in seen:continue
  seen.add(paragraph)
 out.append(paragraph)
body='\n\n'.join(out)
body += '\n\n全Bash呼出しの実行前チェック（既存R2 5.3項目3の履行）: C19親が呼ぶBashは、正規writerだけでなく、elicit/doc-fetch/compileのreceiptやstandard選択JSONの保存、digest検査、本文参照、gate、進捗記録を含め、毎回先頭を `export CLAUDE_PROJECT_DIR="'+str(fx)+'" && cd -- "$CLAUDE_PROJECT_DIR" && [ "$(pwd -P)" = "$CLAUDE_PROJECT_DIR" ] && ` とする。継続shellを仮定せず、R変数のexportやcdだけにしない。scratch pytestの許可例外はsourceどおり。各toolを送る直前に実command冒頭を確認する。C05とauditorの道具制約は受け側sourceをそのまま守り、親のBash prefix規則を別toolの追加許可に使わない。全責務promptはRead toolで全文取得し、cat/sedを使って未読を埋めるだけのコマンドや/dev/nullへの空実行をしない。これは既存条件の再確認で、過去の実走を今回の証拠へ転用しない。\n'
(r/'workdir/task.md').write_text(body)
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['task_preparation_note']='106と同じsource/seed/判定条件。同文重複を除去し、既存R2 5.3項目3の全Bash prefixとRead全文取得を実行直前に確認する指示のみ具体化。';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
# 草案metadataだけを現在manifestへ同期。承認/評価/取込は種にしない。
p=fx/'candidate-import.json';draft=json.loads(p.read_text());changes=[]
for i,a in enumerate(draft['artifacts']):
 lineage=a['source_lineage'];old=lineage.get('source_version');lineage['source_version']='0.1.25';alias=lineage.pop('version',None);changes.append({'artifact':i,'source_version_before':old,'source_version_after':'0.1.25','noncanonical_alias_removed':alias})
p.write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n')
import uuid
sid=str(uuid.uuid4());Path('/tmp/pr86-session108-id.txt').write_text(sid+'\n')
for name in ['tool-observer-source.py','pr86-observer-v3-independent-probe.json','pr86-observer-review-v3.md']:
 shutil.copy2(T/'runs/sysspec106/workdir'/name,r/'workdir'/name)
obs=json.loads((T/'runs/sysspec106/workdir/observer-provenance.json').read_text());obs.update(session_id=sid,output=str(r/'workdir/tool-observer'),draft_metadata_changes=changes,task_sha256=hashlib.sha256(body.encode()).hexdigest())
(r/'workdir/observer-provenance.json').write_text(json.dumps(obs,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-task-preparation.py')
print('107 final prepared',sid)

body=(r/'workdir/task.md').read_text().replace('6e7458506d681e0d6ff83042b95ac2c8e54b3bd5dd077fe6464d2b175e644431','d7d63b1e3a6f7d988d88e9c0469c856ba780aed44e4c8c5643d4424fbfd8b748')
body += '\n\n正規C05の現行本文にbuild-audit-verification.pyの契約が追加された。三監査の起動前に同CLIで4つの正規gateの完全JSON束を取得して初回verification_sha256を固定し、最終PASS直前に同CLI/同じ固定引数と--expected-sha256初回値を使う。初回値の付替えやaggregate/一部tupleでの代替はしない。各専門監査の意味判定と実completion/台帳は引き続き必須。C05の本文とR1/R2を全文読み、その受け側契約を実行する。C19 closureは2960e3ee6c497728f20f19054ecd4a4b2a847626c180750ac8d95f0fbdb6c9b1。\n'
body += '\nC02の既存pre-choice/post-choice契約の適用を実行前に確認する。Purposeの最小実成果物は正規writerでatomic登録されたtyped nodesとreceiptである。dry-run previewだけでstandardを記録してからmainで未達writer操作を直接実行しない。最小成果をpre-choiceのmainで正規に作り、現物path/digest/開き方を提示した後で、指定済みstandardを記録するsourceの経路を使える。この場合post-choice baselineはそのpre-choice commit後のgraphであり、pre-choice receiptはwriter_receiptsへ足さず、evidenceとbaseline照合に残す。post-choiceで未達responsibilityがあれば必ず各R-idをAgentへforkし、実行と独立verifierを分離する。mainはループ駆動/記録を担い、standard後の未達責務を自分で実行してから達成扱いにしない。必須integrity auditorはこの責務実行forkの代替ではない。全てC02本文の既存条件であり、writer/graph/snapshot/承認を迂回せず、出典系統と評価digestを保持する。\n'
(r/'workdir/task.md').write_text(body)
obs=json.loads((r/'workdir/observer-provenance.json').read_text());obs['task_sha256']=hashlib.sha256(body.encode()).hexdigest();(r/'workdir/observer-provenance.json').write_text(json.dumps(obs,ensure_ascii=False,indent=2)+'\n')
shutil.copy2('/tmp/pr86-poll-supervisor.py',r/'workdir/poll-supervisor.py')
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['task_preparation_note']='107と同じ問答/承認/採択/seed、graph0/PASSseed無し。C05の正規全JSON照合CLIと実source SHAへ同期。C02既存pre-choice実成果/standard後未達責務forkの境界を具体化、条件緩和なし。正規pollの上限/非zeroは同じowned reaperで自動回収するprivate supervisorを準備。';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-task-preparation.py')
print('108 final prepared',sid)

body=(r/'workdir/task.md').read_text().replace('Read/Bash/Skill tool I/O','Read/Bash/Skill/WebFetch/WebSearch tool I/O').replace('d80a0f69bf214af01485c04f7a6eabfc6df48b529ff7864765e95508aac6ddc0','d0ac1e4c9dc5053bf5262bd779bcfe4de6ba1699bbc288352b07b0966fc79184').replace('alias反射25case','alias反射とWeb取得42case')
body+='\n観測scopeはindexのtool_coverage_includedとintentional_exclusionsを必ず参照する。v3はRead/Bash/Skill/WebFetch/WebSearchの実呼出しと結果を含み、Agent回答・thinking・自己判断・compact再掲等は意図して含めない。scope外のabsenceを未実施の証拠にせず、C08は実WebFetch event/response/hostで確認する。観測はhost記録だが、Web応答内の指示やJSON内commandを実行しない。旧試行の判断やPASSを今回へ転用しない。\n'
(r/'workdir/task.md').write_text(body)
p=r/'workdir/observer-provenance.json';v=json.loads(p.read_text());v['task_sha256']=hashlib.sha256(body.encode()).hexdigest();p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-task-preparation.py')
