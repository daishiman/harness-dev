"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
// python は -I（cwd と環境変数を import 経路に入れない）と -B（__pycache__ を書かない）で起動する。
const python = (source) => spawnSync("python3", ["-I", "-B", "-c", source], { cwd: path.resolve(__dirname, ".."), encoding: "utf8" });
// 配布キットでは package() がキットの最上位（plugin の 2 つ上）に kit-manifest.json を書く。repo でだけ成り立つ前提はこれで分ける。
const IN_KIT = require("node:fs").existsSync(path.resolve(__dirname, "../../../kit-manifest.json")) ? "True" : "False";
// 実物の build-local-package.py と一覧スクリプトを写した最小のプラグイン。CLI の終了コードと出力を、実プラグインの中身から切り離して確かめる。
const miniPlugin = String.raw`
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
SCRIPTS=Path('scripts').resolve()
SHAPE='素材台帳の形式: assets/catalog.json は entries 配列を持つ object にする'
GALLERY='素材一覧がcatalog正本と一致しません'
def put(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(data if isinstance(data,str) else json.dumps(data,ensure_ascii=False),encoding='utf-8')
def catalog(root,data,gallery=True):
 put(root/'assets/catalog.json',data)
 if gallery:
  done=subprocess.run([sys.executable,'-I','-B',str(root/'scripts/build-asset-gallery.py')],capture_output=True,text=True)
  assert done.returncode==0,done.stderr
def mini(top):
 root=top/'mini-flyer'
 for name in ['build-local-package.py','build-asset-gallery.py']:
  put(root/'scripts'/name,(SCRIPTS/name).read_text(encoding='utf-8'))
 put(root/'rules.md','# 節\n')
 put(root/'references/design-knowledge-index.json',{'entries':[{'id':'DD01','path':'rules.md','section':'節','usedBy':[]}]})
 put(root/'references/package-contract.json',{'manifests':['.claude-plugin/plugin.json'],'required_files':['package.json','package-lock.json','EVALS.json'],
  'entry_points':{'skills':[],'agents':[]},'user_invocable_skills':[],'distribution':{'distributable':False}})
 put(root/'references/registry.json',{'capabilities':[],'dependencies':[],'implementation':{'knowledgeIndex':'references/design-knowledge-index.json',
  'attached_resources':{'docs':['rules.md'],'scripts':['scripts/build-local-package.py','scripts/build-asset-gallery.py'],
   'references':['references/design-knowledge-index.json','references/package-contract.json'],'assets':['assets/catalog.json','assets/index.html']}}})
 # repo の manifest は共有部品の plugin への依存を宣言する。キットへ写すときに KIT_EXCLUDED_DEPENDENCIES だけを外す。
 put(root/'.claude-plugin/plugin.json',{'name':'mini-flyer','version':'1.0.0','description':'検査用の最小プラグイン','author':{'name':'test'},
  'dependencies':['skill-governance-adapters','kept-plugin']})
 for name in ['package.json','EVALS.json']:
  put(root/name,{'version':'1.0.0'})
 put(root/'package-lock.json',{'version':'1.0.0','packages':{'':{'version':'1.0.0'}}})
 # repo 用の台帳は plugin 直下に置き、登録簿には載せず、キットへも写さない（KIT_EXCLUDED_ROOT_FILES）。
 put(root/'artifact-delivery.json',{'plugin':'mini-flyer','entrypoints':[]})
 catalog(root,{'entries':[]})
 # harness 書式の composition は登録簿からの生成物。登録簿や manifest を変えたテストは書き直してから検査する。
 compose(root)
 return root
def compose(root):
 code,out,err=run(root,'--write-composition')
 assert code==0,(code,out,err)
def run(root,*args):
 done=subprocess.run([sys.executable,'-I','-B',str(root/'scripts/build-local-package.py'),*args],capture_output=True,text=True)
 return done.returncode,done.stdout,done.stderr
def report(root):
 """--check の報告。終了コードは失敗の有無と、fail はエラーの数と一致する。"""
 code,out,err=run(root,'--check')
 result=json.loads(out)
 assert code==(1 if result['fail'] else 0) and result['fail']==len(result['errors']),(code,result,err)
 return result
`;
test("package checks read the registry and reject drift in both directions", () => {
  const source = String.raw`
import importlib.util,json,os,shutil,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('flyer_package','scripts/build-local-package.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
STAGES={'run-a':'first','run-b':'second'}
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(data if isinstance(data,str) else json.dumps(data))
def build():
 root=Path(tempfile.mkdtemp())
 write(root/'rules.md','# 節\n')
 write(root/'scripts/run.py','')
 write(root/'agents/lens.md','---\nname: lens\n---\n')
 write(root/'references/design-knowledge-index.json',{'entries':[{'id':'DD01','path':'rules.md','section':'節','usedBy':list(STAGES.values())}]})
 caps=[{'kind':'skill','ref':'skills/'+n,'stage':s} for n,s in STAGES.items()]+[{'kind':'agent','ref':'agents/lens'}]
 write(root/'references/registry.json',{'capabilities':caps,
  'dependencies':[{'from':'skills/run-a','to':'skills/run-b','type':'calls'}],
  'implementation':{'owner':'skills/run-a','entrypoint':'scripts/run.py','workflow':'rules.md#節','knowledgeIndex':'references/design-knowledge-index.json',
   'attached_resources':{'scripts':['scripts/run.py'],'references':['references/design-knowledge-index.json','references/package-contract.json']}},'retired':[],'eval_sinks':['EVALS.json']})
 write(root/'references/package-contract.json',{'manifests':['plugin.json'],'required_files':['package.json','package-lock.json','EVALS.json']})
 write(root/'tests/run.test.cjs','')
 for name in STAGES:
  write(root/'skills'/name/'SKILL.md','---\nname: '+name+'\nversion: 1.0.0\nreference_refs:\n  - ../../rules.md#節\nknowledge_refs:\n  - DD01\n---\n')
  write(root/'skills'/name/'workflow-manifest.json',{'skill':name,'workflowId':name,'version':'1.0.0',
   'phases':[{'id':'A','dependsOn':[],'resourceIds':['rules']}],'resources':[{'id':'rules','path':'../../rules.md','phaseIds':['A']}]})
 for file in ['plugin.json','EVALS.json']:
  write(root/file,{'version':'1.0.0'})
 write(root/'package.json',{'version':'1.0.0','scripts':{'test':'node --test tests/*.test.cjs'}})
 write(root/'package-lock.json',{'version':'1.0.0','packages':{'':{'version':'1.0.0'}}})
 return root
CONTRACT={'manifests':['plugin.json'],'entry_points':{'skills':['run-a','run-b'],'agents':['lens']},'user_invocable_skills':['run-a','run-b']}
def errors(root):
 return module.check_stage_contracts(root)+module.check_registry(root)+module.check_links(root)+module.check_symlinks(root)+module.check_entry_points(root,CONTRACT)+module.check_versions(root,'1.0.0',CONTRACT)
def expect(mutate,needle):
 root=build()
 try:
  mutate(root)
  found=errors(root)
  assert any(needle in e for e in found),(needle,found)
 finally:
  shutil.rmtree(root)
root=build();assert errors(root)==[],errors(root);shutil.rmtree(root)
# キットから外す skill は宣言（KIT_EXCLUDED_SKILLS）で決め、symlink かどうかでは決めない。
# 実体のフォルダで置き、入口の台帳には載せ、独立キットへは写さない。共有正本への symlink とSKILL.mdの無いフォルダは止める。
assert module.KIT_EXCLUDED_SKILLS=={'run-skill-feedback'},module.KIT_EXCLUDED_SKILLS
assert module.KIT_EXCLUDED_DEPENDENCIES=={'skill-governance-adapters'},module.KIT_EXCLUDED_DEPENDENCIES
assert module.KIT_EXCLUDED_ROOT_FILES=={'artifact-delivery.json'},module.KIT_EXCLUDED_ROOT_FILES
root=build();sandbox=Path(tempfile.mkdtemp());copied=sandbox/'kit';shared=sandbox/'shared'
LISTED={**CONTRACT,'entry_points':{**CONTRACT['entry_points'],'skills':['run-a','run-b','run-skill-feedback']}}
def listed(root):
 return module.check_stage_contracts(root)+module.check_registry(root)+module.check_links(root)+module.check_symlinks(root)+module.check_kit_exclusions(root)+module.check_entry_points(root,LISTED)+module.check_versions(root,'1.0.0',LISTED)
try:
 feedback=root/'skills/run-skill-feedback'
 # 版も登録も別の正本に従う実体コピー。登録簿・版の照合には入らない。
 write(feedback/'SKILL.md','---\nname: run-skill-feedback\nversion: 0.1.0\n---\n')
 write(feedback/'workflow-manifest.json',{'version':'0.1.0'})
 assert listed(root)==[],listed(root)
 # 実体があるのに入口の台帳へ載せなければ止める。
 assert any('入口の不一致: entry_points.skills' in e for e in errors(root)),errors(root)
 shutil.copytree(root,copied,ignore=lambda folder,names:module.IGNORE(folder,names,root=root))
 assert not (copied/'skills/run-skill-feedback').exists()
 assert (copied/'skills/run-a/SKILL.md').exists()
 # 宣言していない名前は実体でも外さず、登録簿の照合に掛かる。
 write(root/'skills/run-other/SKILL.md','unregistered copy')
 assert any('登録簿に無い: skills/run-other' in e for e in listed(root)),listed(root)
 shutil.rmtree(root/'skills/run-other')
 # 共有正本への symlink に戻すと、キットから外れていても止める（repo の外では解決できない）。
 write(shared/'SKILL.md','---\nname: run-skill-feedback\n---\n')
 shutil.rmtree(feedback);feedback.symlink_to(shared,target_is_directory=True)
 assert any('キット除外skillがsymlink: skills/run-skill-feedback' in e for e in listed(root)),listed(root)
 feedback.unlink();feedback.mkdir()
 assert any('キット除外skillにSKILL.mdが無い: skills/run-skill-feedback' in e for e in listed(root)),listed(root)
finally:
 shutil.rmtree(root);shutil.rmtree(sandbox)

def rename(root):
 write(root/'skills/run-a/SKILL.md','---\nname: wrong\nreference_refs:\n  - missing.md\nknowledge_refs:\n  - DD99\n---\n')
for needle in ['frontmatter name不一致','stage参照切れ','未知の指針ID']:
 expect(rename,needle)
def manifest(root,**change):
 file=root/'skills/run-b/workflow-manifest.json';data=json.loads(file.read_text());data.update(change);write(file,data)
expect(lambda r:manifest(r,phases=[{'id':'A','dependsOn':['B']},{'id':'B','dependsOn':['A']}]),'依存循環')
expect(lambda r:manifest(r,maxImprovementCycles=3),'cycleBudget')
def loops(root):
 write(root/'references/design-contract.json',{'cycleBudget':3})
 write(root/'skills/run-a/SKILL.md','---\nname: run-a\nreference_refs:\n  - ../../rules.md#節\nknowledge_refs:\n  - DD01\ngoal_seek:\n  enabled: true\n  max_loops: 4\n---\n')
expect(loops,'goal_seek.max_loops が cycleBudget と不一致: run-a')
def registry_budget(root):
 write(root/'references/design-contract.json',{'cycleBudget':3})
 file=root/'references/registry.json';data=json.loads(file.read_text());data['revisionBudget']={'maxCycles':4};write(file,data)
expect(registry_budget,'revisionBudget.maxCycles が cycleBudget と不一致')

expect(lambda r:manifest(r,resources=[],phases=[{'id':'A','dependsOn':[]}]),'resourcesに無い')
expect(lambda r:write(r/'skills/run-b/references/extra.md','x'),'resourcesに無いskill資産')
# 未登録の skill フォルダは、その場所で 1 回だけ報告する（SKILL.md と二重に数えない）。
root=build()
try:
 write(root/'skills/run-c/SKILL.md','---\nname: run-c\n---\n');found=errors(root)
 assert found.count('登録簿に無い: skills/run-c')==1 and not any('skills/run-c/' in e for e in found),found
finally:
 shutil.rmtree(root)
expect(lambda r:write(r/'scripts/extra.py',''),'登録簿に無い: scripts/extra.py')
# owner がフォルダを指しても、manifest の無い skill フォルダの中身は信頼しない。
expect(lambda r:((r/'skills/run-a/workflow-manifest.json').unlink(),write(r/'skills/run-a/extra.md','x')),'登録簿に無い: skills/run-a/extra.md')
expect(lambda r:(r/'scripts/run.py').unlink(),'登録された資産が無い')
# 直下は配布キットへそのまま写るので、登録簿・配布契約・登録済みのscriptsが名指ししないものを止める。
def accept(mutate):
 root=build()
 try:
  mutate(root);found=errors(root);assert found==[],found
 finally:
  shutil.rmtree(root)
expect(lambda r:write(r/'handoff.txt','会話の書き出し'),'登録簿に無い: handoff.txt')
expect(lambda r:write(r/'notes/memo.md','x'),'登録簿に無い: notes')
def unlisted(root):
 file=root/'references/package-contract.json';data=json.loads(file.read_text())
 data['required_files'].remove('package-lock.json');write(file,data)
expect(unlisted,'登録簿に無い: package-lock.json')
expect(lambda r:write(r/'package.json',{'version':'1.0.0','scripts':{}}),'登録簿に無い: tests')
expect(lambda r:write(r/'.env.local','x'),'登録簿に無い: .env.local')
expect(lambda r:write(r/'.private-notes/x.md','x'),'登録簿に無い: .private-notes')
expect(lambda r:write(r/'scripts/.secret','x'),'登録簿に無い: scripts/.secret')
# npm scripts が scripts/ のファイルを実行しても、scripts/ の中身はフォルダごと信頼されない。
def npm_runs_file(root,name):
 write(root/'package.json',{'version':'1.0.0','scripts':{'test':'node --test tests/*.test.cjs','doctor':'node scripts/run.py'}})
 write(root/name,'x')
for name in ['scripts/.secret','scripts/extra.py']:
 expect(lambda r:npm_runs_file(r,name),'登録簿に無い: '+name)
# '..' で名指ししたフォルダの外へ出る語は、行き先を登録しない。
def npm_escape(root):
 write(root/'package.json',{'version':'1.0.0','scripts':{'test':'node --test tests/*.test.cjs','x':'node scripts/../.env.local'}})
 write(root/'.env.local','x')
expect(npm_escape,'登録簿に無い: .env.local')
# glob は glob を含まない最も深い親だけを登録し、直下のフォルダ全体を信頼しない。親の中でも隠し名は信頼しない。
def npm_glob(root,name):
 write(root/'package.json',{'version':'1.0.0','scripts':{'test':'node --test tests/*.test.cjs','lint':'python3 scripts/sub/*.py'}})
 write(root/'scripts/sub/a.py','');write(root/name,'x')
accept(lambda r:npm_glob(r,'scripts/sub/b.py'))
for name in ['scripts/extra.py','scripts/.secret','scripts/sub/.secret']:
 expect(lambda r:npm_glob(r,name),'登録簿に無い: '+name)
# フォルダ単位の登録（attached_resources の '/' 終わり・npm の glob）でも、隠し名は登録で信頼しない。
def presets(root,name):
 file=root/'references/registry.json';data=json.loads(file.read_text())
 data['implementation']['attached_resources']['presets']=['references/presets/'];write(file,data)
 write(root/'references/presets/x/preset.json',{'id':'x'});write(root/name,'x')
accept(lambda r:presets(r,'references/presets/x/notes.md'))
expect(lambda r:presets(r,'references/presets/x/.secret'),'登録簿に無い: references/presets/x/.secret')
expect(lambda r:presets(r,'references/presets/.hidden/a.md'),'登録簿に無い: references/presets/.hidden')
expect(lambda r:write(r/'tests/.env.local','x'),'登録簿に無い: tests/.env.local')
# 写らないフォルダ（.claude・node_modules）へは降りない。shipped() も登録照合の walk も同じ ignored() で外す。
root=build()
try:
 write(root/'.claude/notes.md','[切れ](missing.md)');write(root/'node_modules/pkg/README.md','[切れ](missing.md)')
 walked=[p.relative_to(root).parts for p in module.shipped(root)]
 assert not any(parts[0] in ('.claude','node_modules') for parts in walked),walked
 assert errors(root)==[],errors(root)
finally:
 shutil.rmtree(root)
for name in ['draft.tmp','node_modules/pkg/index.js','__pycache__/run.pyc','.DS_Store','scripts/.DS_Store','skills/run-a/.DS_Store','.claude/settings.json','.gitignore']:
 accept(lambda r:write(r/name,'x'))
# 実物の .gitignore が除外する名前は、どれも IGNORE で配布キットから外れる。
# ただし assets/ の素材画像は git 管理から外すだけで、ローカルキットへは写す（catalog の登録で照合する）。
# .gitignore 自身はキットへ写らない（BASE_IGNORE）ので、キットの中では写っていないことだけを確かめる。
if ${IN_KIT}:
 assert not Path('.gitignore').exists()
else:
 rules=[l.strip() for l in Path('.gitignore').read_text().splitlines() if l.strip() and not l.startswith('#')]
 private=[rule for rule in rules if rule.startswith('assets/')]
 assert rules and private,'.gitignore'
 for prefix in ['','scripts/']:
  for rule in rules:
   if rule not in private:
    accept(lambda r:write(r/(prefix+rule.replace('*','any').rstrip('/')+('/x' if rule.endswith('/') else '')),'x'))
 probe=build()
 try:
  assert not any(module.ignored(probe,probe/rule.replace('**/','').replace('*','any')) for rule in private),private
 finally:
  shutil.rmtree(probe)
# '.' で始まるフォルダも、配布契約の manifest を含めば中へ降りて照合する。
def dot_manifest(root):
 file=root/'references/package-contract.json';data=json.loads(file.read_text())
 data['manifests'].append('.claude-plugin/plugin.json');write(file,data)
 write(root/'.claude-plugin/plugin.json',{'version':'1.0.0'})
accept(dot_manifest)
expect(lambda r:(dot_manifest(r),write(r/'.claude-plugin/.env.local','x')),'登録簿に無い: .claude-plugin/.env.local')
expect(lambda r:write(r/'skills/notes.md','x'),'登録簿に無い: skills/notes.md')
# 素材は catalog の file と別名が指す実ファイルで登録され、形式の崩れた行は素材フォルダ全体を通す理由にならない。
def catalog(root):
 file=root/'references/registry.json';data=json.loads(file.read_text())
 data['implementation']['attached_resources']['assets']=['assets/catalog.json'];write(file,data)
 write(root/'assets/catalog.json',{'entries':[{'file':'logo.png','provenance':{'aliases':[{'file':'old/logo.png'}]}},{'file':''},{'file':3},'broken',{'provenance':'x'}]})
 write(root/'assets/logo.png','x');write(root/'assets/old/logo.png','x')
accept(catalog)
expect(lambda r:(catalog(r),write(r/'assets/notes.txt','x')),'登録簿に無い: assets/notes.txt')
def index(root,used):
 write(root/'references/design-knowledge-index.json',{'entries':[{'id':'DD01','path':'rules.md','section':'節','usedBy':used}]})
expect(lambda r:index(r,['first','second','ghost']),'usedByの未知のstage')
expect(lambda r:index(r,['first']),'usedByに無い指針')
def twin(root):
 file=root/'references/design-knowledge-index.json';data=json.loads(file.read_text())
 data['entries'].append(dict(data['entries'][0],id='DD02'));write(file,data)
expect(twin,'指針の参照先が重複')
expect(lambda r:write(r/'rules.md','# 節\n\n[先](agents/lens.md#無い見出し)\n'),'本文リンク切れ: rules.md')
# markdown に書いた HTML の href/src も、markdown のリンクと同じく照合する。コードフェンスの中と外部 URL は見ない。
accept(lambda r:write(r/'rules.md','# 節\n\n<a href="agents/lens.md">レンズ</a> <img src="https://example.com/a.png">\n\n\x60\x60\x60\n<img src="missing.png">\n\x60\x60\x60\n'))
expect(lambda r:write(r/'rules.md','# 節\n\n<img src="missing.png">\n'),'本文リンク切れ: rules.md -> missing.png')
expect(lambda r:write(r/'rules.md',"# 節\n\n<a href='agents/lens.md#無い見出し'>先</a>\n"),'本文リンク切れ: rules.md -> agents/lens.md#無い見出し')
# 配布する HTML の href/src。'?' 以降と、markdown 以外への '#' は外して実在を見る。
def page(root,body):
 file=root/'references/registry.json';data=json.loads(file.read_text())
 data['implementation']['attached_resources']['pages']=['pages/'];write(file,data)
 write(root/'pages/index.html','<!doctype html><title>x</title>'+body)
accept(lambda r:page(r,'<a href="#top">上へ</a><a href="../rules.md#節">節</a><a href="../agents/lens.md?v=1">レンズ</a><a href="index.html#top">先頭</a><a href="mailto:a@example.com">連絡</a><img SRC="HTTPS://example.com/a.png"><script src="//cdn.example.com/x.js"></script>'))
for body,link in [('<a href="list.html">一覧</a>','list.html'),("<img src='../assets/none.png'>",'../assets/none.png'),('<a href="../rules.md#無い節">節</a>','../rules.md#無い節')]:
 expect(lambda r:page(r,body),'本文リンク切れ: pages/index.html -> '+link)
# symlink は copytree がリンク先の中身を写し、登録照合はリンク先の実体で済むので、リンク先が root の内でも外でもそれだけで止める。
def only(mutate,needle):
 root=build()
 try:
  mutate(root);found=errors(root)
  assert len(found)==1 and found[0].startswith(needle),(needle,found)
 finally:
  shutil.rmtree(root)
only(lambda r:os.symlink(r/'scripts/run.py',r/'scripts/alias.py'),'配布対象のsymlink: scripts/alias.py -> ')
only(lambda r:os.symlink(r/'agents',r/'docs'),'配布対象のsymlink: docs -> ')
def composed(root,**change):
 file=root/'references/registry.json';data=json.loads(file.read_text());data.update(change);write(file,data)
def retire(path='docs/old.md',to='rules.md'):
 return {'path':path,'replacedBy':to}
outside=Path(tempfile.mkdtemp())
try:
 write(outside/'run.py','');write(outside/'EVALS.json',{'version':'1.0.0'})
 expect(lambda r:((r/'scripts/run.py').unlink(),os.symlink(outside/'run.py',r/'scripts/run.py')),'配布対象のsymlink: scripts/run.py -> ')
 expect(lambda r:os.symlink(outside,r/'linked'),'配布対象のsymlink: linked -> ')
 # 評価の書き先は root 内のファイルとして実在させる。フォルダ・空・root の外は登録だけで通さない。
 for sink in ['evals/missing.json','tests','',str(outside/'EVALS.json')]:
  only(lambda r:composed(r,eval_sinks=[sink]),'評価の書き先が無い: '+sink)
 # 退役の移行先も root 内のファイルにする。
 for to in ['missing.md','agents','',str(outside/'run.py')]:
  only(lambda r:composed(r,retired=[retire(to=to)]),'退役の移行先が無い: docs/old.md')
finally:
 shutil.rmtree(outside)
# 退役は配布から外した記録。旧パスにファイルが無ければ通り、残っていれば登録扱いで写る前に 1 回だけ止める。
accept(lambda r:composed(r,retired=[retire()]))
only(lambda r:(composed(r,retired=[retire()]),write(r/'docs/old.md','旧版')),'退役したファイルが残っている: docs/old.md')
# design-contract が名指す知見索引は、登録簿が名指して照合した索引と同じファイルにする。別の実在する JSON も通さない。
def design_contract(root,data):
 write(root/'references/design-contract.json',data)
 file=root/'references/registry.json';comp=json.loads(file.read_text())
 comp['implementation']['attached_resources']['references'].append('references/design-contract.json');write(file,comp)
for named in [None,'references/design-knowledge-index.json','./references/../references/design-knowledge-index.json']:
 accept(lambda r:design_contract(r,{} if named is None else {'knowledgeIndex':named}))
for named in ['references/missing.json','references/package-contract.json',3]:
 only(lambda r:design_contract(r,{'knowledgeIndex':named}),'design-contract の knowledgeIndex が登録簿と不一致: '+str(named))
accept(lambda r:(write(r/'node_modules/pkg/index.js','x'),os.symlink(r/'node_modules/pkg',r/'node_modules/.bin')))
def depend(root):
 file=root/'references/registry.json';data=json.loads(file.read_text())
 data['dependencies'].append({'from':'skills/run-a','to':'skills/run-z','type':'calls'});write(file,data)
expect(depend,'未登録の部品への依存')
expect(lambda r:write(r/'skills/run-a/SKILL.md','---\nname: run-a\nuser-invocable: false\nreference_refs:\n  - ../../rules.md#節\nknowledge_refs:\n  - DD01\n---\n'),'入口の不一致')
expect(lambda r:write(r/'EVALS.json',{'version':'0.9.0'}),'版の不一致: EVALS.json')
def locked_version(root,top=None,package=None):
 file=root/'package-lock.json';data=json.loads(file.read_text())
 if top: data['version']=top
 if package: data['packages']['']['version']=package
 write(file,data)
expect(lambda r:locked_version(r,top='0.9.0'),'版の不一致: package-lock.json =')
expect(lambda r:locked_version(r,package='0.9.0'),'版の不一致: package-lock.json#packages[""].version')
def revision_without_contract(root):
 file=root/'references/registry.json';data=json.loads(file.read_text())
 data['dependencies'].append({'from':'skills/run-b','to':'skills/run-a','type':'revision','fixClass':'premise'})
 write(file,data)
expect(revision_without_contract,'fixRouting の無い revision 関係')
expect(revision_without_contract,'部品の依存循環')
def unknown_type(root):
 file=root/'references/registry.json';data=json.loads(file.read_text())
 data['dependencies'].append({'from':'skills/run-b','to':'skills/run-a','type':'skip-cycle'})
 write(file,data)
expect(unknown_type,'未知の依存type')
expect(unknown_type,'部品の依存循環')

print('package registry negative cases: PASS')
`;
  const result = python(source);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("package asset gate rejects unsafe scope, privacy types, and aliases that duplicate IDs or leave the canonical file", () => {
  const source = String.raw`
import importlib.util,json,shutil,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('flyer_package','scripts/build-local-package.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def build():
 root=Path(tempfile.mkdtemp())
 (root/'assets').mkdir();(root/'assets/canonical.png').write_bytes(b'image')
 (root/'references/presets/case').mkdir(parents=True)
 (root/'references/presets/case/preset.json').write_text(json.dumps({'id':'case'}))
 original={'id':'OLD','file':'canonical.png','sha256':m.digest(root/'assets/canonical.png')}
 entry={'id':'MAIN','aliases':['OLD'],'kind':'reference','file':'canonical.png','sha256':original['sha256'],
 'preset':'case','usage':'reference-only','privacy':{'containsPeople':True},'provenance':{'project':'case-project','aliases':[original]}}
 return root,{'entries':[entry]}
def errors_of(mutate=None):
 root,data=build()
 try:
  if mutate: mutate(root,data)
  (root/'assets/catalog.json').write_text(json.dumps(data))
  return m.check_asset_catalog(root)
 finally: shutil.rmtree(root)
def check(mutate=None,needle=None):
 errors=errors_of(mutate)
 if needle: assert any(needle in e for e in errors),(needle,errors)
 else: assert errors==[],errors
check()
# 別名は正規側と同じ実ファイルを指す。同じ SHA でも別のパスへ向けば、同じ画像の二重同梱なので、それだけを止める。
alias=lambda d:d['entries'][0]['provenance']['aliases'][0]
check(lambda r,d:alias(d).update(file='./canonical.png'))
def twin(root,data,file='old.png'):
 (root/'assets'/file).resolve().write_bytes(b'image');alias(data).update(file=file)
for mutate in [twin,lambda r,d:twin(r,d,'../canonical.png'),lambda r,d:alias(d).update(file='missing.png'),lambda r,d:alias(d).update(sha256='0'*64)]:
 errors=errors_of(mutate);assert errors==['素材別名が指す実ファイル/SHA: MAIN'],errors
# 正規側のファイルが崩れたときは、正規側の 1 件だけを返し、同じファイルを指す別名で二重に数えない。
errors=errors_of(lambda r,d:(r/'assets/canonical.png').write_bytes(b'changed'));assert errors==['素材SHA/境界: MAIN'],errors
check(lambda r,d:d['entries'][0].pop('preset'),'案件素材のpreset欠落')
check(lambda r,d:d['entries'][0].update(preset='missing'),'素材preset参照切れ')
check(lambda r,d:d['entries'][0]['privacy'].update(containsPeople='may-contain-third-parties'),'privacy.containsPeopleは真偽値')
check(lambda r,d:d['entries'][0].update(usage='selectable'),'参照素材の用途')
check(lambda r,d:d['entries'].append(dict(d['entries'][0],id='SECOND',aliases=[],provenance={})),'素材SHAの重複')
check(lambda r,d:d['entries'][0].update(aliases=['MAIN']),'素材ID/別名の重複')
check(lambda r,d:d['entries'][0]['provenance'].update(aliases=[]),'素材別名の履歴欠落')
check(lambda r,d:d['entries'][0].update(file='../outside.png'),'素材SHA/境界')
# 形の崩れた行は例外で止めず、どの素材の何が崩れたかを返す。
check(lambda r,d:d['entries'][0].update(preset=['case']),'素材preset参照切れ')
check(lambda r,d:d['entries'][0].update(provenance='case-project'),'素材provenanceの形式')
check(lambda r,d:d['entries'][0].update(privacy='none'),'privacy.containsPeopleは真偽値')
check(lambda r,d:d['entries'][0].update(file=3),'素材SHA/境界')
check(lambda r,d:d['entries'][0].update(sha256=['x']),'素材SHA/境界')
check(lambda r,d:d['entries'][0]['provenance']['aliases'][0].update(id=['OLD']),'素材別名の履歴欠落')
check(lambda r,d:d['entries'].append('broken'),'素材エントリの形式')
check(lambda r,d:(r/'references/presets/case/preset.json').write_text('[]'),'素材preset参照切れ')
# JSON として読めない preset は、どのファイルかをプラグイン相対のパスで示す。
check(lambda r,d:(r/'references/presets/case/preset.json').write_text('{'),'素材preset参照切れ: MAIN (JSONとして読めない: references/presets/case/preset.json (')
# 台帳が読めないときは例外で止めず、不在・JSON として読めない・形式違反を別の文言で 1 件だけ返す。空の正しい台帳はエラーなし。
def ledger(write=None):
 root,_=build()
 try:
  if write: write(root/'assets/catalog.json')
  return m.check_asset_catalog(root),m.catalog_entries(root)
 finally: shutil.rmtree(root)
for shape in [[],{'entries':3},{}]:
 assert ledger(lambda f:f.write_text(json.dumps(shape)))==([SHAPE],None),shape
assert ledger()==(['素材台帳なし: assets/catalog.json'],None)
errors,entries=ledger(lambda f:f.write_text('{'))
assert entries is None and len(errors)==1 and errors[0].startswith('JSONとして読めない: assets/catalog.json ('),errors
assert ledger(lambda f:f.write_text(json.dumps({'entries':[]})))==([],[])
# check() の報告も同じ読み口を通す。最小のプラグインの写しで台帳を差し替え、エラーの集合を厳密に比べる。
top=Path(tempfile.mkdtemp())
try:
 root=mini(top)
 result=report(root);assert result['errors']==[] and result['assets']==0,result
 for shape in [[],{'entries':3},{}]:
  catalog(root,shape);result=report(root)
  assert result['errors']==[SHAPE] and result['assets']==0,(shape,result)
 # 正しい形の台帳は、行が崩れていても entries の数を数え、行ごとのエラーを返す。
 catalog(root,{'entries':[{},{}]});result=report(root)
 assert result['assets']==2 and result['errors'] and not any(e.startswith(('素材台帳','JSONとして読めない')) for e in result['errors']),result
 catalog(root,'{',gallery=False);result=report(root)
 assert len(result['errors'])==2 and result['errors'][0].startswith('JSONとして読めない: assets/catalog.json (') and result['errors'][1]==GALLERY,result
 (root/'assets/catalog.json').unlink();result=report(root)
 missing={'登録された資産が無い: assets/catalog.json','本文リンク切れ: assets/index.html -> catalog.json','素材台帳なし: assets/catalog.json',GALLERY}
 assert len(result['errors'])==len(missing) and set(result['errors'])==missing and not any('形式' in e for e in result['errors']),result
 for name in ['a','b']:
  (root/'assets'/(name+'.png')).write_bytes(name.encode())
 catalog(root,{'entries':[{'id':n.upper(),'kind':'photo','file':n+'.png','sha256':m.digest(root/'assets'/(n+'.png')),'privacy':{'containsPeople':False}} for n in ['a','b']]})
 result=report(root);assert result['errors']==[] and result['assets']==2,result
finally: shutil.rmtree(top)
print('asset gate negative cases: PASS')
`;
  const result = python(miniPlugin + source);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("FIX routing agrees across registry, contract and workflow without bypassing the dependency DAG", () => {
  const source = String.raw`
import importlib.util,json,shutil,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('flyer_package','scripts/build-local-package.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def write(file,data):
 file.parent.mkdir(parents=True,exist_ok=True)
 file.write_text(data if isinstance(data,str) else json.dumps(data))
def build():
 root=Path(tempfile.mkdtemp())
 stages={'run-intake-flyer':'intake','run-analyze-flyer':'analyze','run-create-flyer':'create'}
 for name in stages: write(root/'skills'/name/'SKILL.md','---\nname: '+name+'\n---\n\n## ゴールシーク実行\n\n### 局面カタログ\n')
 comp={'capabilities':[{'kind':'skill','ref':'skills/'+n,'stage':stage} for n,stage in stages.items()],
 'nonFixReturns':[{'from':'skills/run-create-flyer','to':'skills/run-intake-flyer','trigger':'style-unresolved','step':'skills/run-intake-flyer/SKILL.md#局面カタログ',
  'stepTitle':'様式を決める','consumesCycle':False,'source':'skills/run-create-flyer/SKILL.md#ゴールシーク実行','note':'評価 FIX ではない差し戻し'}],
 'implementation':{'attached_resources':{'references':['references/']}},'dependencies':[
 {'from':'skills/run-intake-flyer','to':'skills/run-analyze-flyer','type':'calls','analysisMode':'source-artifact'},
 {'from':'skills/run-intake-flyer','to':'skills/run-create-flyer','type':'calls','analysisMode':'new-from-brief'},
 {'from':'skills/run-create-flyer','to':'skills/run-analyze-flyer','type':'calls','analysisMode':'source-artifact'},
 {'from':'skills/run-create-flyer','to':'skills/run-intake-flyer','type':'revision','fixClass':'premise'}]}
 write(root/'references/design-contract.json',{'fixRouting':{'deterministic':'run-create-flyer','within-plan':'run-create-flyer','premise':'run-intake-flyer'}})
 write(root/'references/workflow.md','| deterministic | 機械修正 | run-create-flyer | する |\n| within-plan | 配置修正 | run-create-flyer | する |\n| premise | 前提再確認 | run-intake-flyer → 元画像があれば分析、無ければ制作 | する |\n')
 return root,comp
def check(mutate=None,needle=None):
 root,comp=build()
 try:
  if mutate: mutate(root,comp)
  write(root/'references/registry.json',comp)
  errors=m.check_registry(root)
  if needle: assert any(needle in e for e in errors),(needle,errors)
  else: assert errors==[],errors
 finally: shutil.rmtree(root)
check() # 有効な revision は呼出のDAGに循環を作らない。
check(lambda r,c:c['dependencies'].pop(),'revision 関係が fixRouting と不一致')
check(lambda r,c:c['dependencies'][3].update(to='skills/run-analyze-flyer'),'revision 関係が fixRouting と不一致')
check(lambda r,c:c['dependencies'][3].update({'from':'skills/run-analyze-flyer'}),'revision 関係が fixRouting と不一致')
check(lambda r,c:c['dependencies'][3].update(fixClass='within-plan'),'revision 関係が fixRouting と不一致')
check(lambda r,c:c['dependencies'][0].update(type='revision',fixClass='premise'),'revision 関係が fixRouting と不一致')
check(lambda r,c:c['dependencies'].append(dict(c['dependencies'][3])),'revision 関係が fixRouting と不一致')
check(lambda r,c:c['dependencies'][1].update(analysisMode='source-artifact'),'通常呼出の analysisMode/前提分岐が不一致')
check(lambda r,c:c['dependencies'][2].update(condition='brief.analysisMode=source-artifact、または fixClass=premise の FIX'),'通常呼出の analysisMode/前提分岐が不一致')
check(lambda r,c:c['dependencies'][2].update(fixClass='premise'),'通常呼出の analysisMode/前提分岐が不一致')
check(lambda r,c:write(r/'references/workflow.md','| premise | 前提 | run-analyze-flyer | する |\n'),'workflow 改善表が fixRouting と不一致: premise')
check(lambda r,c:c['dependencies'].append({'from':'skills/run-analyze-flyer','to':'skills/run-create-flyer','type':'calls'}),'部品の依存循環')
# cycle を消費しない差し戻し（nonFixReturns）は FIX の revision 辺と混ぜない。各反例はそのエラーだけを出す。
def only(mutate,error):
 root,comp=build()
 try:
  mutate(root,comp);write(root/'references/registry.json',comp)
  errors=m.check_registry(root);assert errors==[error],(error,errors)
 finally: shutil.rmtree(root)
back=lambda c:c['nonFixReturns'][0]
check(lambda r,c:c.pop('nonFixReturns'))
check(lambda r,c:c.update(nonFixReturns=[]))
for value in [{},'x',['x'],[None]]:
 only(lambda r,c:c.update(nonFixReturns=value),'非FIXの差し戻しの形式: nonFixReturns は object の配列にする')
# 値が空でも、fixClass の欄を持てば FIX と区別できない。
for value in ['premise',None]:
 only(lambda r,c:back(c).update(fixClass=value),'非FIXの差し戻しが fixClass を持つ: style-unresolved')
only(lambda r,c:back(c).pop('consumesCycle'),'非FIXの差し戻しが cycle を消費する: style-unresolved')
for value in [True,0,None,'false']:
 only(lambda r,c:back(c).update(consumesCycle=value),'非FIXの差し戻しが cycle を消費する: style-unresolved')
for key in ['from','to']:
 only(lambda r,c:back(c).update({key:'skills/run-ghost'}),'非FIXの差し戻しの部品が未登録: skills/run-ghost')
 only(lambda r,c:back(c).pop(key),'非FIXの差し戻しの部品が未登録: None')
# 登録済みでも skill でない部品は、差し戻しの端にならない。
def agent_end(root,comp):
 comp['capabilities'].append({'kind':'agent','ref':'agents/lens'});write(root/'agents/lens.md','---\nname: lens\n---\n')
 back(comp).update(to='agents/lens')
only(agent_end,'非FIXの差し戻しの部品が未登録: agents/lens')
# 手順と根拠の参照は、root 内のファイルと markdown 見出しへ解決させる。空の参照は root そのものへ解決させない。
outside=str(m.ROOT/'plugin-composition.yaml')
for key,ref in [('step','skills/run-intake-flyer/SKILL.md#無い手順'),('step','skills/run-intake-flyer/missing.md'),('step',''),('step',outside),
                ('source','skills/run-create-flyer/SKILL.md#無い節'),('source',None),('source',3)]:
 only(lambda r,c:back(c).update({key:ref}),'非FIXの差し戻しの参照切れ: '+str(ref))
only(lambda r,c:back(c).pop('step'),'非FIXの差し戻しの参照切れ: None')
# 非FIXの印（consumesCycle・trigger）を持つ辺は、種類を問わず dependencies に置かない。
only(lambda r,c:c['dependencies'][3].update(consumesCycle=False),'dependencies に非FIXの差し戻しが混入: skills/run-create-flyer→skills/run-intake-flyer')
only(lambda r,c:c['dependencies'][0].update(trigger='style-unresolved'),'dependencies に非FIXの差し戻しが混入: skills/run-intake-flyer→skills/run-analyze-flyer')
check(lambda r,c:c['dependencies'].append(dict(back(c),type='revision')),'dependencies に非FIXの差し戻しが混入: skills/run-create-flyer→skills/run-intake-flyer')
# 実プラグインの nonFixReturns は空ではなく、どれもこの検査を通る。
real=m.registry(m.ROOT)
assert real['nonFixReturns'] and m.check_non_fix_returns(m.ROOT,real)==[],m.check_non_fix_returns(m.ROOT,real)
print('FIX routing and DAG negative cases: PASS')
`;
  const result = python(source);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("policy coverage follows usedBy DD bodies, related sections and stage contracts", () => {
  const source = String.raw`
import copy,importlib.util,json,shutil,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('flyer_package','scripts/build-local-package.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=Path(tempfile.mkdtemp())
try:
 shutil.copytree(m.ROOT/'references',root/'references')
 comp=m.registry(m.ROOT)
 for cap in comp['capabilities']:
  if cap['kind']=='skill':
   file=m.capability_file(m.ROOT,cap);dest=root/file.relative_to(m.ROOT)
   dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
 index=json.loads((root/'references/design-knowledge-index.json').read_text())['entries']
 contract=json.loads((root/'references/design-contract.json').read_text())
 def coverage(mutate=None):
  current=copy.deepcopy(contract);entries=copy.deepcopy(index)
  if mutate:mutate(current,entries)
  (root/'references/design-contract.json').write_text(json.dumps(current))
  return m.check_policy_coverage(root,comp,entries)
 def check(mutate=None,needle=None):
  errors=coverage(mutate)
  if needle:assert any(needle in e for e in errors),(needle,errors)
  else:assert errors==[],errors
 check()
 # 専門本文の参照が root 内のファイルに解決しなければ、役ごとの接続の照合を黙って飛ばさず、それだけを止める。
 for ref in ['references/none.md','references','',None,str(m.ROOT/contract['expertSourcesRef'])]:
  errors=coverage(lambda c,e:c.update(expertSourcesRef=ref))
  assert errors==['専門知見の本文の参照切れ: expertSourcesRef -> '+str(ref)],(ref,errors)
 assert coverage(lambda c,e:c.pop('expertSourcesRef'))==['専門知見の本文の参照切れ: expertSourcesRef -> None']
 check(lambda c,e:(c.pop('expertSourcesRef'),c.update(expertRoles=[])))
 for key,file in [('analysisPolicyFiles','references/design-rules.md'),('analysisPolicyFiles','references/designer-knowledge.md'),('analysisPolicyFiles','references/style-profiles.md'),('analysisPolicyFiles','skills/assign-flyer-evaluator/references/review-contract.md'),('analysisPolicyFiles','skills/run-analyze-flyer/references/analysis-contract.md'),('analysisPolicyFiles','schemas/analysis-review.schema.json'),('analysisPolicyFiles','references/workflow.md'),('reviewPolicyFiles','skills/assign-flyer-evaluator/references/review-contract.md'),('reviewPolicyFiles','references/workflow.md')]:
  check(lambda c,e:c[key].remove(file),'規範集合の被覆漏れ: '+key+' -> '+file)
 check(lambda c,e:c.pop('analysisPolicyFiles'),'規範集合がありません: analysisPolicyFiles')
 def remove_role(entries,role):
  for entry in entries:
   if 'review:'+role in entry['usedBy']:
    entry['relatedSections']=[r for r in entry.get('relatedSections',[]) if not r.startswith('references/designer-knowledge.md#'+role)]
 for role in ['composition','color']:
  check(lambda c,e:remove_role(e,role),'専門知見の索引接続漏れ: review:'+role)
 def additional_related(contract,entries):
  entries[0].setdefault('relatedSections',[]).append('references/new-judgment.md#節')
 check(additional_related,'規範集合の被覆漏れ: analysisPolicyFiles -> references/new-judgment.md')
 print('DD/policy coverage negative cases: PASS')
finally:shutil.rmtree(root)
`;
  const result = python(source);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("the CLI turns check failures into a non-zero exit and refuses to write the kit", () => {
  const source = String.raw`
top=Path(tempfile.mkdtemp()).resolve()
try:
 root=mini(top);kit=top/'kit';archive=Path(str(kit)+'.zip')
 # 知見索引が JSON として読めなければ、検査を進めずにどのファイルかを示して止める。
 index=root/'references/design-knowledge-index.json';saved=index.read_text(encoding='utf-8')
 index.write_text('{',encoding='utf-8')
 code,out,err=run(root,'--check')
 assert code==1 and out=='' and err.startswith('JSONとして読めない: references/design-knowledge-index.json ('),(code,out,err)
 index.write_text(saved,encoding='utf-8')
 (root/'notes.txt').write_text('x')
 code,out,err=run(root,'--check')
 assert code==1 and json.loads(out)['errors']==['登録簿に無い: notes.txt'],(code,out,err)
 code,out,err=run(root,'--out',str(kit))
 assert code==1 and '登録簿に無い: notes.txt' in err and not kit.exists() and not archive.exists(),(code,out,err)
 (root/'notes.txt').unlink()
 code,out,err=run(root,'--check')
 assert code==0 and json.loads(out)['fail']==0,(code,out,err)
 # composition は登録簿からの生成物。手で直したもの・無いものは不一致として止め、書き直せば通る。
 composed=root/'plugin-composition.yaml';text=composed.read_text(encoding='utf-8')
 DRIFT='plugin-composition.yaml が references/registry.json からの生成と不一致（--write-composition で書き直す）'
 composed.write_text(text+'# 手直し\n',encoding='utf-8')
 assert report(root)['errors']==[DRIFT],report(root)
 composed.unlink()
 assert report(root)['errors']==[DRIFT],report(root)
 compose(root)
 assert composed.read_text(encoding='utf-8')==text and report(root)['fail']==0
 code,out,err=run(root,'--out',str(kit))
 assert code==0 and json.loads(out)['archive']==str(archive) and archive.is_file() and (kit/'plugins/flyer-studio/scripts/build-local-package.py').is_file(),(code,out,err)
 # キットの manifest からは KIT_EXCLUDED_DEPENDENCIES だけが外れ、repo の manifest はそのまま残る。
 shipped=json.loads((kit/'plugins/flyer-studio/.claude-plugin/plugin.json').read_text(encoding='utf-8'))
 assert shipped['dependencies']==['kept-plugin'],shipped
 assert json.loads((root/'.claude-plugin/plugin.json').read_text(encoding='utf-8'))['dependencies']==['skill-governance-adapters','kept-plugin']
 # 外す依存しか持たない manifest は、キットで dependencies の鍵ごと消す（空の配列を残さない。実 plugin はこちら）。
 import importlib.util
 spec=importlib.util.spec_from_file_location('mini_package',root/'scripts/build-local-package.py')
 pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)
 solo=kit/'plugins/flyer-studio';put(solo/'.claude-plugin/plugin.json',{**shipped,'dependencies':['skill-governance-adapters']})
 pkg.narrow_kit(solo,root)
 assert 'dependencies' not in json.loads((solo/'.claude-plugin/plugin.json').read_text(encoding='utf-8'))
 # 直下の repo 用台帳はキットに写らず、repo 側には残る。
 assert not (kit/'plugins/flyer-studio/artifact-delivery.json').exists() and (root/'artifact-delivery.json').is_file()
 # 外すのは直下の名前だけ。下のフォルダに置いた同名ファイルは写る側として登録簿と照合する。
 (root/'references/artifact-delivery.json').write_text('{}')
 code,out,err=run(root,'--check')
 assert code==1 and json.loads(out)['errors']==['登録簿に無い: references/artifact-delivery.json'],(code,out,err)
finally: shutil.rmtree(top)
print('package CLI exit and refusal: PASS')
`;
  const result = python(miniPlugin + source);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("the kit drops excluded skills and their dependencies from its ledger and passes its own --check", () => {
  const source = String.raw`
top=Path(tempfile.mkdtemp()).resolve()
try:
 # キットの中では plugin のフォルダ名が flyer-studio になる。名前の照合を両側で通すため、repo 側も同じ名前にする。
 root=mini(top).rename(top/'flyer-studio');kit=top/'kit'
 manifest=json.loads((root/'.claude-plugin/plugin.json').read_text(encoding='utf-8'));manifest['name']='flyer-studio'
 put(root/'.claude-plugin/plugin.json',manifest)
 put(root/'skills/run-skill-feedback/SKILL.md','---\nname: run-skill-feedback\nversion: 1.0.0\n---\n')
 # 本物の skills/ には登録済みの skill が並ぶ。外した skill だけのフォルダにしないよう、登録済みのファイルを 1 つ置く。
 put(root/'skills/README.md','# skills\n')
 comp=json.loads((root/'references/registry.json').read_text(encoding='utf-8'))
 comp['implementation']['attached_resources']['docs'].append('skills/README.md')
 contract=json.loads((root/'references/package-contract.json').read_text(encoding='utf-8'))
 contract['entry_points']['skills']=['run-skill-feedback']
 # 本物の台帳は、外す skill の実行時の依存と、その所有者・manifest と同じ repo 側 plugin への依存を宣言する。
 contract['depends_on']=['harness-creator','skill-governance-adapters','kept-plugin']
 contract['runtime_dependencies']=[{'capability':'run-skill-feedback','owner':'harness-creator','required_entry_point':'run-skill-feedback'},
  {'capability':'run-kept','owner':'kept-plugin','required_entry_point':'run-kept'}]
 put(root/'references/package-contract.json',contract)
 comp['external_dependencies']={'harness-creator':{'version':'>=1.4.0 <2.0.0','relation':'skill-feedback-ssot-provider','required_entry_points':['run-skill-feedback']},
  'kept-plugin':{'version':'>=1.0.0','relation':'kept','required_entry_points':['run-kept']}}
 put(root/'references/registry.json',comp)
 compose(root)
 assert report(root)['fail']==0,report(root)
 composed=(root/'plugin-composition.yaml').read_text(encoding='utf-8')
 assert 'ref: skills/run-skill-feedback' in composed and 'harness-creator:' in composed and 'kept-plugin:' in composed,composed
 code,out,err=run(root,'--out',str(kit))
 assert code==0,(code,out,err)
 # キットの台帳からは外れ、repo の台帳には残る。キットは自分の --check を通る。
 shipped=kit/'plugins/flyer-studio'
 ledger=json.loads((shipped/'references/package-contract.json').read_text(encoding='utf-8'))
 assert ledger['entry_points']['skills']==[],ledger
 # 外した skill の実行時の依存と、それだけが要る plugin・KIT_EXCLUDED_DEPENDENCIES も台帳から落ち、他の依存は残る。
 assert ledger['depends_on']==['kept-plugin'],ledger
 assert [d['required_entry_point'] for d in ledger['runtime_dependencies']]==['run-kept'],ledger
 assert json.loads((root/'references/package-contract.json').read_text(encoding='utf-8'))==contract
 assert not (shipped/'skills/run-skill-feedback').exists()
 # キットの composition は写した中身から作り直す。外した skill と、それだけが要る外部依存が落ち、他の外部依存は残る。
 composed=(shipped/'plugin-composition.yaml').read_text(encoding='utf-8')
 assert 'run-skill-feedback' not in composed and 'harness-creator' not in composed and 'kept-plugin:' in composed,composed
 assert report(shipped)['fail']==0,report(shipped)
finally: shutil.rmtree(top)
print('kit entry ledger: PASS')
`;
  const result = python(miniPlugin + source);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("the entry map lives in references/kit-entry.md and is written as the kit's root SKILL.md", () => {
  const source = String.raw`
top=Path(tempfile.mkdtemp()).resolve()
FENCE=chr(96)*3
try:
 root=mini(top);kit=top/'kit'
 contract=json.loads((root/'references/package-contract.json').read_text(encoding='utf-8'))
 contract['required_files'].append('references/kit-entry.md')
 put(root/'references/package-contract.json',contract)
 entry=lambda body,name='mini-flyer':'---\nname: '+name+'\ndescription: 入口\n---\n\n'+body+'\n'
 good='[節](../rules.md#節)・[索引](design-knowledge-index.json)・[外部](https://example.com)\n\n'+FENCE+'\n[そのまま](../rules.md)\n'+FENCE
 put(root/'references/kit-entry.md',entry(good))
 assert report(root)['fail']==0
 # キット直下の SKILL.md へ、リンクを plugin 直下からの相対に直して書き出す。コードフェンスと外部リンクは変えない。
 code,out,err=run(root,'--out',str(kit))
 assert code==0,(code,out,err)
 written=(kit/'plugins/flyer-studio/SKILL.md').read_text(encoding='utf-8')
 for part in ['[節](rules.md#節)','[索引](references/design-knowledge-index.json)','[外部](https://example.com)','[そのまま](../rules.md)']:
  assert part in written,(part,written)
 assert (kit/'plugins/flyer-studio/references/kit-entry.md').is_file() and not (root/'SKILL.md').exists()
 # 直下に SKILL.md を置くなら、正本から書き出したものと一致させる（書き出し済みのキットと同じ形）。
 put(root/'SKILL.md',written)
 assert report(root)['fail']==0
 put(root/'SKILL.md','---\nname: mini-flyer\n---\n')
 assert report(root)['errors']==['plugin 直下の SKILL.md が references/kit-entry.md の書き出しと不一致'],report(root)
 (root/'SKILL.md').unlink()
 # name が plugin 名と違う・書き出すと切れる見出し・plugin の外を指すリンクは止める。
 put(root/'references/kit-entry.md',entry(good,'other'))
 assert report(root)['errors']==['入口の地図の name が plugin 名と不一致: references/kit-entry.md'],report(root)
 put(root/'references/kit-entry.md',entry('[外](../../outside.md)'))
 assert '入口の地図のリンクが plugin の外を指す: references/kit-entry.md -> ../../outside.md' in report(root)['errors'],report(root)
 code,out,err=run(root,'--out',str(top/'kit2'))
 assert code==1 and not (top/'kit2').exists(),(code,out,err)
finally: shutil.rmtree(top)
print('kit entry map: PASS')
`;
  const result = python(miniPlugin + source);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("the real plugin has a root SKILL.md only in the kit and its entry map resolves from the plugin root", () => {
  const result = python(String.raw`
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('flyer_package','scripts/build-local-package.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# repo は harness の規約で plugin 直下に SKILL.md を置かない。キットには narrow_kit() が書き出した入口の地図がある
# （書き出しとの一致は check_kit_entry が見る）。
assert (m.ROOT/'SKILL.md').exists()==${IN_KIT}
assert m.check_kit_entry(m.ROOT)==[],m.check_kit_entry(m.ROOT)
text=m.render_kit_entry(m.ROOT)
assert '](skills/run-intake-flyer/SKILL.md)' in text and '](../' not in text,text
print('real kit entry: PASS')
`);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
