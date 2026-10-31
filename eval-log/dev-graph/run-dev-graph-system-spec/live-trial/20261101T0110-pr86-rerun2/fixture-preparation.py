from pathlib import Path
import json,subprocess,sys,shutil,hashlib,os
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');W=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');r=T/'runs/sysspec89';fx=r/'fx';src=T/'runs/sysspec88/fx'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec89','run-dev-graph-system-spec','--session-root','fx'],check=True)
subprocess.run(['git','init','-q','-b','main',str(fx)],check=True)
subprocess.run(['git','-C',str(fx),'-c','user.name=live-trial','-c','user.email=live-trial@example.invalid','commit','-q','--allow-empty','-m','fixture: canonical resume inputs'],check=True)
(fx/'.git/info/exclude').write_text('plugins/\n.claude/\n')
shutil.copytree(src/'system-spec',fx/'system-spec')
env={k:v for k,v in os.environ.items() if k!='CLAUDE_PROJECT_DIR'}
cp=subprocess.run([sys.executable,'-B',str(W/'plugins/dev-graph/scripts/build-init-scaffold.py'),'--repo-root',str(fx),'--hook-source','plugin'],env=env,check=True,capture_output=True,text=True)
(r/'workdir/fixture-init-receipt.json').write_text(cp.stdout)
assert json.loads((fx/'.dev-graph/state/graph.json').read_text())['nodes']==[]
# 登録前の草案だけを入力として渡す。評価証拠と確定結果は削除する。
draft=json.loads((src/'eval-log/c02-import-payload.json').read_text())
draft.pop('expected_graph_revision',None)
for a in draft['artifacts']:
 a.pop('confirmation_evidence',None)
 a.get('source_lineage',{}).pop('imported_at',None)
(fx/'candidate-import.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n')
files={p.relative_to(fx).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (fx/'system-spec').rglob('*') if p.is_file()}
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source_run':'20261101T0110-pr86-rerun (independent FAIL)','preparation':'前実走の正規writerによる確定問答・出典資料・compiled章を再開入力として複製。C01の正規builderでこの新repoを初期化。graph.nodesは空。C02 payloadは草案のみでconfirmation_evidenceとimported_atを削除。評価report・監査台帳・再利用receipt・PASS結果・登録nodeを種として置いていない。targetは全canonical flowをこのrepoで新規実行し、独立評価と登録を実証する。','source':str(src/'system-spec'),'seed_sha256':files,'byte_identical':all((src/'system-spec'/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False,'graph_nodes_initial':0,'draft_is_confirmation_evidence':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec89','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec88/workdir/task.md').read_text().replace('sysspec88','sysspec89')
start=body.index('### 準備');end=body.index('### 本題',start)
body=body[:start]+'''### 準備済みの再開入力

- このrepoはC01の正規builderで初期化済み（workdir/fixture-init-receipt.json）。graph.nodesは空で、取込結果は無い。C01のSkillを実行するタスクではない。
- system-spec/には前の正規writerが作ったcompiled章もある。これらは再開入力であり、今回のcompile実行・evaluator・登録の成果として代用しない。C19の正規経路で再compile・新規独立評価を行う。
- candidate-import.jsonは前の実走のC02入力を基にした草案。confirmation_evidenceとimported_atは削除済みで、承認/確定根拠ではない。必要ならschema/sectionsの入力草案として参照できるが、今回のsource bytes/version/digestと新しいevaluator証拠へ正規に接地させてから使う。
- fixture-provenanceは `/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec89/workdir/fixture-provenance.json`。fixture入力を探すために / 全体を走査する必要はない。

'''+body[end:]
body=body.replace('dev-graph は未初期化です。入力は未追跡の `system-spec/` の 2 ファイルです。','dev-graph は正規builderで初期化済み、graph.nodesは空です。入力は未追跡の `system-spec/` のstate・出典資料・compiled章です。')
body+='''
実行前に確認する共通契約（sourceに元からある要求の再掲。基準を変更する指示ではない）:
- elicit/doc-fetch/compileの実処理Bashは毎回、再compile・scratchでの検証用compileも含め、R2の `export CLAUDE_PROJECT_DIR='<開始時receiptのrepo_root>' && cd -- "$CLAUDE_PROJECT_DIR" && [ "$(pwd -P)" = "$CLAUDE_PROJECT_DIR" ] && ...` を満たす。初回だけ照合し、後の再実行で照合を省略する形にしない。書き先も指定された試行境界内に限る。
- artifact_deliveryの事前回答standardは、C19だけでなくロードした各run Skillにも適用する。各Skillで最小の実成果物を提示してから選択を記録し、その後にだけsemantic evaluator/責務Agent/意味層テストへ進む。例えばcompileでは最初のcanonical compileの現物・digest・開き方を提示してstandardを記録してから、OUT1のテスト・R1/R2/R3のAgent等を実行する。最後にまとめて選択記録を書く形にしない。
- 既に取得済みの出典やcompiled入力が有効なら正規のresume判断を使える。新しいevaluatorを省略したり前runのPASSを再利用することはできない。
'''
(r/'workdir/task.md').write_text(body)
print('prepared sysspec89: initialized resume repo; graph empty; no evaluations seeded')
