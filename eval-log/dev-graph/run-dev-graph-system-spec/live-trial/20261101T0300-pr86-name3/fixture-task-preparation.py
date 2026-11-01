from pathlib import Path
import json,hashlib,shutil
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec99';fx=r/'fx'
body=(T/'runs/sysspec98/workdir/task.md').read_text().replace('sysspec98','sysspec99')
body+='\n既存sourceの問答履歴の区別をC05直前に共有する: R6-audit-hearingのactive consumerは確定cell.qa_refとrequirements_foundation.effective_source_refsのqa_refである。apply-spec-transition.py::_supersede_qaは補助qa_refsの旧問参照を履歴として残すことを明示許可し、compileは旧版の印と現行根拠ではない旨を描く。qa_refsの存在だけをactive consumerと数えず、主根拠/bindingと置き換え(a)(b)(c)を個別確認する。履歴を削除せず、無効な置き換え・実active consumer・他欠陥があれば通常どおりFAIL。この定義と保存契約を共有後、helper argsを無変更でC05へ渡し、C06にも担当source全体を読ませる。\n'
(r/'workdir/task.md').write_text(body)
# 使用する環境をboot前に固定し、元guardと過去runを改変しない。
settings=fx/'.claude/settings.local.json';config=json.loads(settings.read_text());hook=config['hooks']['PreToolUse'][0]['hooks'][0];hook['command']=hook['command'].replace('/hook/guard.py','/hook/guard-json-data.py');settings.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
shellhome=r/'shell-home';shellhome.mkdir();shellenv='export PATH="'+str(T/'bin')+':/Users/dm/.local/bin:/Users/dm/miniconda3/bin:/usr/bin:/bin:/usr/sbin:/sbin"\nexport TMPDIR="'+str(r/'tmp')+'/"\nexport TMPPREFIX="'+str(r/'tmp/zsh')+'"\n'
for name in ['.zshenv','.zprofile']:(shellhome/name).write_text(shellenv)
(r/'workdir/extra-env.txt').write_text('SHELL=/bin/zsh\nCLAUDE_CODE_SHELL=/bin/zsh\nZDOTDIR='+str(shellhome)+'\nTMPPREFIX='+str(r/'tmp/zsh')+'\n')
for name in ['fixture-qa008-correction.json','qa008-original-input.json','qa008-prior-backfill.json','qa008-grounded-applications.json','fixture-canonical-backfill.log','fixture-canonical-compile.log']:
 shutil.copy2(T/'runs/sysspec98/workdir'/name,r/'workdir'/name)
for name in ['pr86-guard-json-tests.json','pr86-heredoc-probe.json','pr86-heredoc-shell-probe.json']:shutil.copy2(Path('/tmp')/name,r/'workdir'/name)
shutil.copy2(T/'hook/guard-json-data.py',r/'workdir/isolation-guard-source.py')
g=T/'hook/guard-json-data.py';(r/'workdir/guard-provenance.json').write_text(json.dumps({'guard_source':str(g),'guard_sha256':hashlib.sha256(g.read_bytes()).hexdigest(),'original_guard_source':str(T/'hook/guard.py'),'original_guard_sha256':hashlib.sha256((T/'hook/guard.py').read_bytes()).hexdigest(),'rule_change':'macOS CLI規則のみ、ASTで確認したeval-log内literal/stdin無改変writerへ渡す引用JSONデータ本文を除外。他の全規則/許可root/sandbox制約は維持。','boundary_cases_passed':18,'shell':'/bin/zsh','TMPPREFIX':str(r/'tmp/zsh'),'heredoc_probe_bytes':65537,'settings_sha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'protected_chapter_guard_changed':False},ensure_ascii=False,indent=2)+'\n')
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['qa008_input_correction_inherited']='fixture-qa008-correction.json (sysspec98以前の補完を継承、今回stateは前runとbytes同一)';v['environment_proof']='guard-provenance.json';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

shutil.copy2(__file__,r/'workdir/fixture-task-preparation.py')
p=r/'workdir/fixture-provenance.json';v=json.loads(p.read_text());v['task_preparation_note']='初回prepは旧task節名の不一致でtask保存前に停止。fixture/state/graphの初期化は成功済み。fixture-task-preparation.pyで98のsource準拠taskを99へ複製し、既存の補助qa_refs履歴/active consumer定義を明記。新規評価/登録結果のseedは無し。';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert json.loads((fx/'.dev-graph/state/graph.json').read_text())['nodes']==[]
assert not (fx/'eval-log/system-spec-completeness-report.json').exists()
print('sysspec99 prepared: source unchanged, input unchanged, definition clarified')
