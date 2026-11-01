from pathlib import Path
import json,hashlib,datetime,jsonschema
w=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');o=Path('/tmp/pr86-c19-inner-review');mp=o/'source-manifest.json';manifest=json.loads(mp.read_text())
for rel in ['plugins/harness-creator/skills/assign-skill-design-evaluator/scripts/render-findings-score.py','plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json','plugins/harness-creator/skills/assign-skill-design-evaluator/references/rubric.json','plugins/harness-creator/skills/run-build-skill/schemas/content-review-verdict.schema.json','plugins/dev-graph/scripts/_common.py','plugins/dev-graph/references/prompt-common-layers.md']:
 manifest['files'][rel]=hashlib.sha256((w/rel).read_bytes()).hexdigest()
assert all(hashlib.sha256((w/p).read_bytes()).hexdigest()==h for p,h in manifest['files'].items())
mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');sha=manifest['files']['plugins/dev-graph/skills/run-dev-graph-system-spec/SKILL.md'];raw=json.loads((o/'rubric-raw.json').read_text());probes=json.loads((o/'gate-probe-results.json').read_text())
report='''# C19 inner gate追加の独立incremental review

結論: 今回の追加blockはPASS。規範採点は84/100、threshold80、high0。前回のPASS、既存レビューの結論、親から報告された1457秒trialの成功は、この判定の根拠にしていない。現在のsource、canonical parser、今回のread-only再実行から独立に判断した。

## 変更対象と4条件

対象はC19 SKILL.md「ゴールシーク検証」の3gate CLI blockと、その前後のIN1記録規則。R0〜R3/helper/共有契約との整合も現sourceで確認した。

| 条件 | 判定 | 根拠 |
|---|---|---|
| C1 矛盾なし | PASS | graph未更新の周回もschemaを省略せず、coverage/source/schema全てexit0のときだけ当該周回IN1 PASSにする。未実施・待ち・非0はnot_achieved。後周回の成功を前周回へ遡及しないため、最終成功と途中周回の成功を混同しない。 |
| C2 漏れなし | PASS | 3つ全てのcanonical CLIと必須引数がある。各周回の実結果をprogress/intermediateへ記録した後に6必須キー/hashを検査する順序が明示される。schema gateの観測漏れを、R3で最後に通しただけで埋める経路は無い。 |
| C3 整合性あり | PASS | coverage/source/schema全exit0という既存IN1と一致する。全checklist achievedとIN1 PASSが完了条件で、OUT1はexternal_pendingのまま別live trialが判定する契約を維持。R2の本処理root拘束・scratch隔離、R3のevaluator PASS前取込禁止も維持される。 |
| C4 依存関係整合 | PASS | coverage/sourceはR1で検証したsystem-spec-harness code root、schemaはこのSKILLの所有plugin rootから起動。入力は開始C24 receiptのsystem_spec/graph/repo rootの絶対pathで固定する。cwd、plugin source側content、手作業の別validatorへauthorityを移す必要はない。 |

## CLIとportable root

coverage parserは--matrix/--require-complete/--require-basis/--require-foundationを全て受理し、JSON入力のみを読む。source parserは--targets/--references/--state/--repo-rootを受理し、stateに含まれるtargetsとreferencesを突合し、repo-relative retrieval evidenceを明示repo rootへ解決する。schema parserは--graph/--repo-root/--strict-artifact-readinessを受理し、明示rootのcontainment・schema・artifact readinessを検査する。

5変数は同じBash呼出し内の引用付き絶対pathであり、前のshell変数の残存やcwd探索に依存しない。code rootのplaceholderにはR1で検証した配置とホスト提示SKILLの所有rootを代入する契約で、literal placeholderを実行する意味ではない。read-only検査なので、R2の本処理writer Bashに要求されるexport/cdを追加しなくても入力先は変わらない。

CLIは&&で短絡する。先行gateが失敗すれば後続は未実施となるが、直前の文章がその周回をnot_achievedとし、残るgateを記録するよう要求する。短絡したgateを成功扱いしてはならない。3gateの実測exit0が揃わない限りIN1 PASSは書けない。

## 今回実行した検証

fx90の開始C24 receiptからrepo_root/content_roots.system_spec/local_state_paths.graphを読み、fixture配置のcanonical validatorがレビューsourceとbyte一致することを確認した。validatorの引数とrootを固定して、cwdを/tmp/pr86-c19-inner-reviewへ変えて3gateをread-only再実行し、全てexit0だった。schemaはstrict-artifact-readiness付きで実行した。

/tmp/pr86-c19-inner-review/negative/だけに不正state、不正references、不正graphを作り、各canonical CLIを独立実行。coverage/source/schemaは全て非0で、失敗をPASSへ変換する処理はない。fx90のstate/章/出典・retrieval evidence・specification/architecture登録本文・graph/receiptを検査前後のSHAで比較し不変を確認した。詳細argv/exit/stdout/stderrはgate-probe-results.json。

この再実行が示すのは現在のデータで3gateが動くことと負例拒否であり、過去のloop1がschemaを実施した証拠ではない。今回の新sourceでhost trialを回したとも主張しない。後周回結果の遡及禁止に従い、過去の途中周回をこの結果でPASSへ書換えてはならない。

## 採点

正規render-findings-score.pyを新SHAへ再実行した。L0 1.6.0 + evaluator L2でscore84、high0、適用24 ruleのうち機械23。BD-004は独立LLM判断で、第1 triggerは正規Skill委譲/R2、第2 triggerはlineage付きC02取込/R3に対応すると確認した。生出力のpending_humanは原文のまま保存した。人間が採点したとの主張ではない。

減点はFM-005 low、PD-001 low、PD-002 mediumで、今回追加blockが新たに発生させたhighは無い。今回のblockは本文300行制約内に収まる。

## 範囲と限界

- 6キー/hashのPython検査自体はgate実行の時刻や各exit codeを自動照合しない。新規則は各周回の実測結果の記録を要求し、独立Agentがreceipt/実成果/受入条件を確認する契約と併用する。将来、記録の機械照合を追加する余地はある。
- このレビューは4条件focused incremental review。30思考法フル実走、run-elegant-review Phase1/2/3、host trial、production writer実行を行ったとは主張しない。
- source/fixture/既存eval-logは編集していない。新しいverdictはschema準拠の案として/tmpへ保存し、過去のloop1の欠落を修復済みと扱わない。
'''
(o/'review-report.md').write_text(report)
base={'target':{'plugin':'dev-graph','skill':'run-dev-graph-system-spec','skill_md_sha256':sha},'reviewer':'review_c19_scope（独立incremental reviewer）','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'iterations':1,'human_review_required':False}
feedback={'loop_scope':'both','criteria_evaluated':['IN1','OUT1'],'iteration':1,'iteration_limit':3,'hook_trigger':'親の明示委譲: 各周回IN1実測前PASSを防ぐcanonical3gate blockの独立incremental review。過去PASSは根拠にしない。','next_action':'none'}
elegance=dict(base,review_kind='elegance',verdict='PASS',findings_summary={'contradiction':0,'omission':0,'inconsistency':0,'dependency_break':0,'smell':1},feedback_loop=dict(feedback,positive_feedback=['coverage/source/schema全てexit0だけ当該周回IN1 PASS、未実施/待ち/非0はnot_achieved、後周回結果の遡及禁止が明記される。','canonical CLIの全引数が実parserに存在し、inputは開始C24 receipt、codeは検証済みplugin rootへ固定する。実結果記録後に6キー/hash検査を行う。','fx90へforeign cwdから3gateをread-only再実行して全exit0、/tmp独立負例は全非0。入力SHA不変を確認。'],negative_feedback=['low: 6キー/hash検査自体には各gate exit/時刻の自動照合はない。本文の実測記録要求と独立Agent検証で運用する契約。']),notes='4条件focused incremental reviewとしてPASS。前回PASSや報告されたtrial成功を根拠にしない。現在のread-only gate再実行は過去loop1の実施証拠にならない。30思考法/host trialを行ったとは主張しない。')
rubric=dict(base,review_kind='rubric',verdict='PASS',findings_summary={'contradiction':0,'omission':0,'inconsistency':0,'dependency_break':0,'smell':3},feedback_loop=dict(feedback,positive_feedback=['新SHAへ正規採点器を再実行し84/100、threshold80、high0。適用24の機械23とBD-004独立LLM意味判断1。','新blockのcanonical引数・root固定・記録順を現在sourceで確認し、実データread-only3gateと/tmp負例で検証。'],negative_feedback=[f"{f['id']} {f['severity']}: {f['message']}" for f in raw['findings']]),notes='rubric_hash='+raw['rubric_hash']+'; composition_hash='+raw['composition_hash']+'。生出力pending_humanは保持。BD-004はLLMであり人間採点ではない。30思考法/host trial成功を意味しない。')
schema=json.loads((w/'plugins/harness-creator/skills/run-build-skill/schemas/content-review-verdict.schema.json').read_text())
for name,obj in [('elegance-verdict.json',elegance),('rubric-verdict.json',rubric)]:
 jsonschema.validate(obj,schema);(o/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
(o/'rubric-llm-assessment.json').write_text(json.dumps({'rule':'BD-004','judge':'independent LLM, not human','passed':True,'mapping':['正規フロー生成→SKILL手順3/R2','lineage付き取込→SKILL手順4/R3']},ensure_ascii=False,indent=2)+'\n')
validation={'content_review_schema':'PASS','source_files_unchanged':True,'source_files_checked':len(manifest['files']),'fx90_inputs_unchanged':probes['fx90_inputs_unchanged'],'final_skill_sha256':sha,'score':raw['score']}
(o/'validation-results.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n');print(json.dumps(validation,ensure_ascii=False))
