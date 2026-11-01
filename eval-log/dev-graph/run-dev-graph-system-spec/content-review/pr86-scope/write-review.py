from pathlib import Path
import json,hashlib,datetime,jsonschema
w=Path('/Users/dm/orca/workspaces/harness/pr86-ci-fix');o=Path('/tmp/pr86-c19-scope-review');m=json.loads((o/'source-manifest.json').read_text())
assert all(hashlib.sha256((w/p).read_bytes()).hexdigest()==h for p,h in m['files'].items())
sha=m['files']['plugins/dev-graph/skills/run-dev-graph-system-spec/SKILL.md'];raw=json.loads((o/'rubric-raw.json').read_text())
report='''# C19 最終sourceの独立レビュー

結論: 今回の境界変更に阻害的な欠陥はなく、4条件のfocused source reviewはPASS。規範採点は84/100、threshold80、high0。

対象はC19 SKILL.md・R0〜R3・prepare-evaluation.pyの全文。C24 resolver、C02 writerのlineage/confirmation境界、共有prompt層、compositionとsystem-spec-harness正規4 entry pointsの契約を照合した。既存verdictの参照はJSON形状の把握に限り、既存の結論・所見を採点根拠にしなかった。

## 4条件と根拠

| 条件 | 判定 | 独立根拠 |
|---|---|---|
| C1 矛盾なし | PASS | R2:18は取込元のstate/出典/章を作る本処理Bashごとに固定receipt rootへのexport/cd/pwd照合を要求。R2:20はcaller入力をread-onlyにして絶対scratchへ書くunit/pytestにだけfixture cwdを許す。両者の適用対象が異なり、本処理代替は禁止される。 |
| C2 漏れなし | PASS | R2:20はread-only、絶対scratch隔離、隔離/非変更確認不能時の不実行、C05評価対象・C02取込元・本処理証拠への流用禁止を全て列挙。helper失敗時の回避禁止、R3のPASS前payload/C02禁止、同じdry-run payload、取込後lineage gateも残る。 |
| C3 整合性あり | PASS | SKILL:142〜147の親によるcanonical Skill/writer調整とR0〜R3独立Agent検証、親単独集約/責務別ログ、周回と責務/Skill切替の区別、前周回次指示の入力は共有Layer5/6と整合。SKILL:95の実preflight reportを選択前main contextで提示する契約と、選択後の独立Agentによるchecklist閉鎖は両立する。確定nodeやsemantic評価は選択前に作らない。 |
| C4 依存関係整合 | PASS | C24→固定receipt再検証helper→正規C05→C02という依存。helperはcwdからauthorityを付替えず絶対argsを作り、lineage/evidence_refはrepo相対。C02は評価dirと取込元dirを照合する。新たな循環・参照切れ・独自compilerはない。 |

## 3観測を緩和していない根拠

1. 正規system-spec-harness flow完了: SKILL:101/129〜130、R2:18/31/36/62がcanonical Skill経路とcoverage/source/evaluator gateを要求。R2:20によりscratch unit成功を本処理実行証拠へ使えない。
2. specification/architectureのlineage/evaluator evidence保持: SKILL:102/131、R3、C02 _spec_confirmationとvalidate-source-lineageが要求する。scratchをC05対象やC02取込元に流用できない。
3. C02だけで登録し生成ロジック複製なし: SKILL:97/102/132/171、R2:20/31、R3の単一writer境界が維持される。unitでcanonical moduleを呼んでも登録成功を代替できない。

成功シナリオの3観測は全て実測が必要。本レビューのscratch probeやfail-closed停止だけでは成功シナリオのPASS証拠にならない。

## 今回の検証

全検査を/tmp/pr86-c19-scope-review/probe/の新規合成repoへ隔離した。helperはforeign cwdから空白/単引用符を含むrootを正しく絶対argsへ引用し、read-mode receipt、repo/worktree/common-dir/git-dir不一致、絶対/escape/eval-log外output、symlink output、content root変更を想定通り拒否した(12ケース)。検査対象scratch入力bytesも不変だった。

C02 _spec_confirmationを正規評価reportではない合成JSONへ単独で呼び、絶対spec_dir受容、別dir拒否、FAIL拒否、evaluated_digest不一致拒否を確認(4ケース)。lineageの現bytes一致/不一致も確認(2ケース)。これらはC05実走・C02 Skill登録・production証拠ではない。

## 規範採点

正規render-findings-score.pyでL0 1.6.0 + evaluator L2を合成し再実行した。24適用ruleのうち機械23、BD-004は独立LLM意味判断で確認。第1 trigger「正規フローで仕様を作りたい」はSKILL:101/R2、第2 trigger「lineage付き取込」はSKILL:102/R3に対応する。人間判定を得たとの主張ではない。生出力のpending_humanはそのまま保存した。

残る減点はFM-005 low(先頭句が採点器の動詞条件外)、PD-001 low(本文100行超でskill-local references不在)、PD-002 medium(本文冒頭30行の禁則語欠落)。後段に保護規則が存在することと機械rubricの減点を混同しない。

## 非阻害的な改善余地と限界

- low: R1 summary/不変目的の旧>=0.1.0表記。SKILL:100とR1入力契約がcomposition正本を明示するため不適切な版を受理する経路ではない。現在0.1.24は>=0.1.22 <1.0.0に適合する。
- low: SKILL:153〜165のsnippetはintermediateの6キーと元goal/hashを検査するがprogress全achieved/IN1を機械照合しない。本文の停止条件と独立Agentによる閉鎖要求は残る。
- C24 custom system_spec rootはC05 snapshot契約によりbasename system-spec以外なら差し戻す。helperの成功はC05の全custom root対応を保証しない。
- C02 _spec_confirmationはPASS/spec_dir/payload evaluated_digestとlineage digestを検査するが、report.artifact_snapshotの章digestとの直接照合はしない。正規C05が入力snapshotを固定することと、C02自身が照合実装済みであることを混同しない。実際の3観測では評価後の章非変更と評価した現物へのevidence接地を独立確認する必要がある。本変更はC02を変更しない。
- このレビューは4条件focused source review。run-elegant-reviewの30思考法フル実走、Phase 1/2/3・全Agent実走、host live trial成功、production flow、外部人間承認を実施したとは主張しない。

評価中に親の正規release scriptでdev-graph composition版が0.1.23→0.1.24になったため、その差分を再確認しmanifestへ反映した。C19 SKILL/責務/helperは不変。source-manifest.jsonの全source SHAを検査後に再計算して一致を確認した。既存source/fixture/証拠は編集せず、出力は/tmpだけ。親の既存証拠編集禁止に従いwrite-eval-log.pyによる既存eval-log追記も行っていない。
'''
(o/'review-report.md').write_text(report)
base={'target':{'plugin':'dev-graph','skill':'run-dev-graph-system-spec','skill_md_sha256':sha},'reviewer':'review_c19_scope（独立した読取り専用レビュー担当）','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),'iterations':1,'human_review_required':False}
feedback={'loop_scope':'both','criteria_evaluated':['IN1','OUT1'],'iteration':1,'iteration_limit':3,'hook_trigger':'親から明示的に委譲された最終C19 sourceの独立レビュー。過去レビューの結論は採点根拠にしない。','next_action':'none'}
elegance=dict(base,review_kind='elegance',verdict='PASS',findings_summary={'contradiction':0,'omission':0,'inconsistency':0,'dependency_break':0,'smell':2},feedback_loop=dict(feedback,positive_feedback=['R2の本処理root拘束と絶対scratch unitの適用集合を分離し、C05/C02/本処理証拠への流用を禁止する。3観測の代替を許さない。','親のcanonical Skill/writer調整、R0〜R3独立検証、集約ログ分離、周回と責務/Skill切替の区別が共有契約と整合する。','pre-choice最小成果物は実preflight report。helper12ケース/C02境界4ケース/lineage2ケースは全て/tmp合成fixtureで想定通り。'],negative_feedback=['low: R1 summary旧版値とcomposition正本の重複を減らす余地がある。','low: goal-seek snippetはprogressの全achieved/IN1を機械照合しない。本文の停止条件と独立検証要求は残る。']),notes='4条件focused source reviewとしてPASS。30思考法フル実走やhost live trial成功を主張しない。IN1/OUT1はsource上の要求維持を確認した範囲。既存source/fixture/証拠を書換えず、/tmpだけへ案を保存。境界限界はreview-report.md。')
rubric=dict(base,review_kind='rubric',verdict='PASS',findings_summary={'contradiction':0,'omission':0,'inconsistency':0,'dependency_break':0,'smell':3},feedback_loop=dict(feedback,positive_feedback=['最終sourceへ正規採点器を再実行し84/100、threshold80、high0。生出力とrubric/composition hashを保存。','BD-004の2 triggerを独立LLMとしてSKILL:101/R2とSKILL:102/R3へ1対1対応を確認。'],negative_feedback=[f"{f['id']} {f['severity']}: {f['message']}" for f in raw['findings']]),notes='規範採点84でPASS。rubric_hash='+raw['rubric_hash']+'; composition_hash='+raw['composition_hash']+'。機械23 rule + BD-004 LLM意味判断1。生出力pending_humanは原文保存。30思考法やhost live trial成功を意味しない。')
schema=json.loads((w/'plugins/harness-creator/skills/run-build-skill/schemas/content-review-verdict.schema.json').read_text())
for name,obj in [('elegance-verdict.json',elegance),('rubric-verdict.json',rubric)]:
 jsonschema.validate(obj,schema);(o/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
(o/'rubric-llm-assessment.json').write_text(json.dumps({'rule':'BD-004','judge':'independent LLM, not human','passed':True,'trigger_mapping':[{'trigger':'正規フローで仕様を作りたいとき','loc':'SKILL.md:101; prompts/R2-delegate.md'},{'trigger':'lineage付きで取り込みたいとき','loc':'SKILL.md:102; prompts/R3-import.md'}]},ensure_ascii=False,indent=2)+'\n')
validation={'content_review_schema':'PASS','source_files_unchanged_after_manifest_update':True,'source_files_checked':len(m['files']),'final_skill_sha256':sha}
(o/'validation-results.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n');print(json.dumps(validation,ensure_ascii=False))
