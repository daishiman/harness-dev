from pathlib import Path
import json,subprocess,sys,shutil,hashlib
sys.dont_write_bytecode=True
T=Path('/private/tmp/claude-501/pr86-ci-live/lt');r=T/'runs/sysspec88';fx=r/'fx';src=T/'runs/sysspec87/fx/system-spec'
subprocess.run([sys.executable,str(T/'mkrun.py'),'sysspec88','run-dev-graph-system-spec','--session-root','fx'],check=True)
subprocess.run(['git','init','-q','-b','main',str(fx)],check=True)
subprocess.run(['git','-C',str(fx),'-c','user.name=live-trial','-c','user.email=live-trial@example.invalid','commit','-q','--allow-empty','-m','fixture: resumed canonical inputs'],check=True)
(fx/'.git/info/exclude').write_text('plugins/\n.claude/\n')
(fx/'system-spec').mkdir()
for name in ['spec-state.json','fetched-references.json']:shutil.copy2(src/name,fx/'system-spec'/name)
shutil.copytree(src/'retrieval-evidence',fx/'system-spec/retrieval-evidence')
files={p.relative_to(fx).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (fx/'system-spec').rglob('*') if p.is_file()}
(r/'workdir/fixture-provenance.json').write_text(json.dumps({'source':str(src),'preparation':'前の実走sysspec87の正規writerが更新した問答state・公式取得資料を、そのまま今回の再開入力として複製した。旧compiled章、evaluator report、audit台帳、graph、resume receipt、PASS判定は一切コピーしていない。','source_run':'20261101T0110-pr86 (FAIL)','seed_sha256':files,'byte_identical':all((src/p.relative_to(fx/'system-spec')).read_bytes()==p.read_bytes() for p in (fx/'system-spec').rglob('*') if p.is_file()),'evaluations_seeded':False},ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,r/'workdir/fixture-preparation.py')
subprocess.run([sys.executable,str(T/'mksettings.py'),'sysspec88','--session-root','fx','--allow-fetch-hosts','www.postgresql.org,react.dev,fastapi.tiangolo.com,www.typescriptlang.org,kubernetes.io'],check=True)
body=(T/'runs/sysspec87/workdir/task.md').read_text().replace('sysspec87','sysspec88')
a=body.index('- `system-spec/fetched-references.json`:');b=body.index('\n\nこれらは試験の入力',a)
body=body[:a]+'''- `system-spec/fetched-references.json` と `retrieval-evidence/`: 前の実走で正規doc-fetchが取得し、公式hostとdigestへ接地した資料。その実走で正規writerが更新したspec-stateと共に、今回はそのまま再開入力にした。取得日時・採用版・方針は入力の記録を確認し、doc-fetchの要否は正規Skillで判断すること。compiled章・評価report・監査台帳・graph・resume receiptは種として置いていない。前の実走はFAILであり、その評価結果を今回の証拠に転用しない。fixture-provenance.json参照。'''+body[b:]
a=body.index('今回の入力の補足（試行開始前の準備）:')
body=body[:a]+'''今回の入力の補足（試行開始前の準備）:
- 基礎の承認・質問/回答・採択は既存の合成入力どおり。利用者の新たな承認を作らない。前の実走の正規writerでqa単位の設計解釈とD1の採用PostgreSQL16の出典整合まで済んだstateを再開入力とし、元のfixture問答と採用判断は変えていない。
- 全責務promptとC19のgoal-seek配線を読み、親と責務Agentのログ所有権・6必須キー検査を含む契約を実行する。条件を満たさなければFAILで、手順を省略してPASSにしない。
'''
(r/'workdir/task.md').write_text(body)
print('prepared sysspec88: canonical inputs only')
