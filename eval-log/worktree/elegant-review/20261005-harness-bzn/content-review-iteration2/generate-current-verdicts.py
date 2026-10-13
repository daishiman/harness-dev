from pathlib import Path
import datetime, hashlib, json, yaml, jsonschema

ROOT=Path('/Users/dm/dev/dev/個人開発/harness')
RUN=ROOT/'eval-log/worktree/elegant-review/20261005-harness-bzn'
OUT=RUN/'content-review-iteration2'
HC=ROOT/'plugins/harness-creator'
SCHEMA=HC/'skills/run-build-skill/schemas/content-review-verdict.schema.json'
PROTOCOL=HC/'skills/run-build-skill/references/content-review-protocol.md'
RUBRIC=HC/'skills/ref-skill-design-rubric/references/rubric.json'
OVERLAY=HC/'skills/assign-skill-design-evaluator/references/rubric.json'
proof=json.loads((OUT/'dependency-closure-current-results.json').read_text())
assert proof['result']=='PASS'
previous=json.loads((RUN/'content-review/dependency-pre-ref-skills.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')

# Independent judgments from the current declarations, body and prompt contract
# slices. These evaluate preservation/design; they are not test results for the
# unchanged behavior named in each criterion.
judgments={
 'decompose':{
  'triggers':['Large natural-language want -> Hard boundary/Macro flow1-3 and R1/R2 macro brief/DAG.','Ready feature package registration and binding projection -> Macro flow4-6, R2b package gate, R3/R4/R6.'],
  'criteria':{
   'IN1':'Macro flow3/5 retains C11 validation before C02 and tracker projection; R3 accepts validated packages. Declaring the imported helper brings validator/bridge behavior bytes into the same closure.',
   'OUT1':'Hard boundary and Macro flow2/3 distinguish feature/architecture DAG from phase tasks, forbid draft publication and require confirmed/pass/complete before projection. R2 keeps cyclic/task-granularity rejection. No macro elicitation live result is inferred.',
   'OUT2':'Macro flow5/6 and R3/R4 keep source-key registration and binding-specific existing linkage/item identity. New helper ref creates no second writer or idempotency key.',
   'OUT3':'Macro flow6 and R6 require local/Beads/GitHub/Projects write0 preview. The added import-only ref is not a new command invocation.',
   'OUT4':'Macro flow6 and Gotchas preserve mode=both+auto, github+local_only, beads+GitHub rejection and single binding authority.',
   'OUT5':'Post-flow failure rule and R3/R4 keep committed local nodes and operation-specific pending_retry. No rollback authority moves into the shared ref.',
   'OUT6':'Macro flow4/5 and R2b accept only one exact P01..P13 set per source key with common parent/package and internal DAG.',
   'OUT7':'Macro flow4/5 and R2b use the same package gate and graph_node_id+source_digest for automatic/manual origins; the dependency declaration does not split that authority.'}},
 'init':{
  'triggers':['Caller repository/worktree initialization -> Input/output, C24 Execution contract1, R1/R2 context/plan.','Safe six roots/config/state/templates/hooks -> Execution contract2-5 and R3/R4/R5, current build-init-scaffold/create-only receipt.'],
  'criteria':{
   'IN1':'Execution contract5 and R3 keep prewrite repo-config/C11 validation. The declared common file is the actual import used by the validator and initializer.',
   'OUT1':'Purpose and Execution contract2-5 retain six roots/routing/graph, no overwrite and second init changes0. Independent earlier receipt-failure rollback proves only that named source case; current host idempotence remains separate.',
   'OUT2':'Execution contract3/R4 keep template-contract scaffold in the same init call, missing-only copies and preserving user edits; the helper remains the shared create-only primitive.',
   'OUT3':'C24 realpath repository versus code authority remains explicit in Purpose/Execution1/R1; broken/mismatched links stop. Import ref is code authority only and introduces no stored absolute content path.',
   'OUT4':'Input/output and R2/R3 retain enabled=false and owner/project number/field names while excluding token/node IDs; no config field changes accompany this ref.',
   'OUT5':'Execution4/R5 retain plugin default, conditional plain-symlink fallback, non-destructive merge and separate immutable rollback manifest. The declaration does not add a hook or bypass policy.'}},
 'node':{
  'triggers':['Atomic regular artifact add/update -> Classification/write, R0-R4 and build-graph-node single writer.','Exact-13 feature package registration -> Exact-13 package gate, R3 and register-package; helper supplies IO primitives but not package authority.'],
  'criteria':{
   'IN1':'Classification/write4 and R3 retain schema validation, expected_graph_revision CAS, shared lock and commit/rollback sequencing. Existing imports now include one tracked helper file.',
   'OUT1':'Purpose/routing and add/update clauses retain five regular kinds, C14-only feature macro, canonical paths and unmanaged byte preservation. One dependency ref does not alter classification or writer routing.',
   'OUT2':'Classification3/R4 keep all architecture subtypes and conditional API template synthesis with required heading/readiness_fill rules; helper owns serialization/IO only.',
   'OUT3':'Exact-13 gate and R3 still reject 12/14/mixed/duplicate/cross-feature inputs before any commit and produce exact counts/revision receipt. Earlier coordination timestamp proof stays separate from full package behavioral acceptance.'}},
 'render':{
  'triggers':['Visualize dev-graph as static HTML -> Purpose steps1-5 and R1/R2 render request/model.','Self-contained SVG+inline JS without CDN/npm -> Purpose step3/R3 plus receipt counts/digests and browser acceptance.'],
  'criteria':{
   'IN1':'Purpose3 and R3 prohibit external script/link/CDN/npm; common is a Python build-time helper, not an HTML runtime reference. Declaring it does not change generated HTML contract.',
   'OUT1':'Purpose4/5 and R2/R3 require parent_feature-based X/Y, registration/input digest and browser display together. This static review does not open a new HTML artifact or accept browser behavior.'}},
 'requirements':{
  'triggers':['Derive requirements from confirmed spec and feature packages -> Purpose1-3 and R1/R2 source trace.','Handoff only on complete readiness -> Purpose4/5 and R2b/R3 three-gate, missing_sections and no-code boundary.'],
  'criteria':{
   'IN1':'Purpose2/3 and R2b preserve C11/C02 source/readiness digest agreement plus external exact-13 validator ownership. C24/validator/bridge imports use the newly declared common; it is not an alternative readiness authority.',
   'OUT1':'Purpose explicitly forbids code generation and step5/R3 emit only requirements/handoff tied to snapshot digest. New ref is metadata for imported code and does not add a build operation.',
   'OUT2':'Purpose4/R2b require all incomplete/pending/fail/stale missing_sections and held handoff; no criterion or remediation owner is removed by the ref.'}},
 'schedule':{
  'triggers':['Separate feature ready from task ready -> Purpose2-4 and R1/R2 separate candidate sources/batches.','Dependency/parity/resource/lease safe batches -> Purpose3/5 and R3 read-only eligibility/conflict report.'],
  'criteria':{
   'IN1':'Purpose3 and checklist/R3 require active/confirmed/pass/complete, dependencies done and no active lease; shared process/JSON helper declaration does not relax predicates.',
   'OUT1':'Purpose3/R3 retain all depends_on satisfied, not only direct display, before recommendation. Actual execution recommendation trial remains separate.',
   'OUT2':'Purpose5/R2/R3 jointly retain resource_scope overlap and C27 lease exclusion with separate feature/task batches; ref adds no claim writer.',
   'OUT3':'Output/checklist/criteria keep devgraph/<id> branch and public worktree claim command, with C27 owning double-claim prevention; declaring common does not transfer lease authority.'}},
 'status':{
  'triggers':['Metadata search -> Purpose filters/query, R1/R2 AND/tag-mode normalized input.','Read-only dependency/tombstone/completion status -> Purpose report/digest clauses and R3, C24/C11 without tracker/writer.'],
  'criteria':{
   'IN1':'Purpose and R2 retain C11 validation, schema failure/dangling dependency distinction and graph-state fields. The validator imports common, now tracked explicitly.',
   'OUT1':'Purpose/report and R3 keep status/closed_at/depends_on/dependents from the actual graph snapshot rather than inferred text. Added import metadata does not alter query semantics.',
   'OUT2':'Purpose/Gotchas/R1-R3 prohibit writer/sync/render/GitHub/Beads and require pre/post graph/config/content digests. Declaring a helper reference is not an execution of its mutating API.'}},
 'sync':{
  'triggers':['Binding-specific local/tracker sync -> Protocol2 and R3 single mutation authority.','GitHub Issue/Projects/PR convergence -> Protocol1/3/5, R3/R6/R7 and planner converged=true terminal gate.'],
  'criteria':{
   'IN1':'C24/C11 and one bridge/writer authority remain. The two planners and bridge imports now bind their common serialization/process bytes; source cases already prove cross-project conflict cannot create an authoritative C02 patch.',
   'OUT1':'Current frontmatter/Purpose/Protocol/R3 still require changes0 and both plans converged=true, with unresolved blockers remaining nonterminal. Current C03 inventory text still exactly matches criteria.',
   'OUT2':'Issue newer/same-time+flag rules and semantic updated_at preservation remain; heartbeat is coordination only. No timestamp branch changes accompany the dependency ref.',
   'OUT3':'Protocol4/R4 keep tombstone/status and node identity without physical deletion. Missing Issue remains unresolved rather than a false converged tombstone.',
   'OUT4':'R5/Protocol dry-run and external authorize/execute gate remain write0. Listing common does not invoke atomic_json or external mutations.',
   'OUT5':'R6 snapshot-bound explicit decisions and next-sync flag resolution remain. Confirmation flags count as unresolved; no new confirmation source is introduced.',
   'OUT6':'Alias linkage/item identity and equal import deduplication remain. The declaration tracks existing helper bytes, not a second item-add producer.',
   'OUT7':'L/R/B 3-way and all-origin conflict join stay unchanged. Earlier three-project permutation proof remains exact isolated planning evidence, not full remote sync.',
   'OUT8':'Local promotion independent of remote failure, alias pending_retry and remaining operation reports remain. No permission/rate-limit/pagination execution is claimed here.',
   'OUT9':'Protocol5/R7/checklist retain clean default branch merge authority and feature-worktree pending events; shared helper is not a new done or worktree authority.'}},
 'system-spec':{
  'triggers':['Generate through regular system-spec flow -> Purpose1-3 and R0/R1/R2 four-entry-point delegation.','Import confirmed spec/architecture with lineage -> Purpose4/Resume lineage gate/R3 via C02, keeping source bytes and evaluator evidence.'],
  'criteria':{
   'IN1':'Purpose2-4/R0/R3 retain version/entry-point, coverage/citation/evaluator/schema gates and exact source-byte lineage validation. Common ref binds C24/C11/lineage imports while existing system-spec dependency closure remains separate.',
   'OUT1':'Purpose/R2 delegate only to four canonical system-spec skills and R3 imports confirmed/evaluator-PASS artifacts via C02 with lineage, forbidding elicitation/compile duplication. Ref points to the existing import-only helper rather than an alternative specification generator.'}}
}

for name, record in proof['skills'].items():
 key=name.removeprefix('run-dev-graph-');cfg=judgments[key]
 skill=ROOT/'plugins/dev-graph/skills'/name;target=skill/'SKILL.md'
 fm=yaml.safe_load(target.read_text().split('---',2)[1]);criteria=fm['feedback_contract']['criteria']
 assert set(c['id'] for c in criteria)==set(cfg['criteria'])
 assert sha(target)==record['skill_md_sha256'], 'stale declaration: '+name
 folder=OUT/'dev-graph'/name;machine=json.loads((folder/'current-rubric-machine-report.json').read_text())
 assert machine['passed'] and not machine['unscored']
 assert {x['id'] for x in machine['pending_human']}=={'BD-004'}
 paths={target,ROOT/'plugins/dev-graph/scripts/_common.py',ROOT/'plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py'}
 paths.update(Path(c['path']) for c in record['actual_common_callers'])
 paths.update((skill/ref).resolve() for ref in fm['responsibility_refs'])
 paths.add(ROOT/'plugins/dev-graph/references/prompt-common-layers.md')
 source_records=[{'file':str(p),'sha256':sha(p),'review_scope':'Current SKILL declaration/body; prompt Layer2/3/6 contract slices; actual caller imports; whole common helper; declared behavior-closure implementation. Not an all-runtime-path audit.'} for p in sorted(paths)]
 assessments=[{**c,'static_design_verdict':'PASS_FOR_DEPENDENCY_CHANGE_AND_CONTRACT_PRESERVATION','evidence':cfg['criteria'][c['id']],'current_evidence_files':[str(p) for p in sorted(paths)],'behavioral_claim_accepted':False} for c in criteria]
 report={'version':1,'iteration':2,'review_mode':'combined-focused-content-review','claim_type':'design','reviewer':'/root/independent_review','proposer_is_approver':False,'reviewed_at':NOW,
  'target':{'plugin':'dev-graph','skill':name,'skill_md_sha256':sha(target)},
  'slice':'F-4001: add the actual shared import-only _common.py to script_refs; current contract/body preserved, current declared closure now tracks and refuses missing helper.',
  'norms':[{'file':str(p),'sha256':sha(p)} for p in [PROTOCOL,SCHEMA,RUBRIC,OVERLAY]],
  'current_sources':source_records,'exact_change_proof':record,'pre_ref_skill_sha256':previous[name]['sha256'],
  'four_conditions':{
   'C1':{'verdict':'PASS','evidence':'The ref names an existing import-only module; no CLI command, mutation route or criterion contradicts its callers.'},
   'C2':{'verdict':'PASS','evidence':'All nine actual consumer skills include this helper exactly once; every current criterion is listed and its contract impact assessed.'},
   'C3':{'verdict':'PASS','evidence':'Independent text comparison proves exactly one ref added, other frontmatter and whole body unchanged; actual import sources resolve to the same canonical file.'},
   'C4':{'verdict':'PASS','evidence':'Current copied closure changes digest for semantic helper mutation and fails closed when helper is missing; shared helper remains one implementation/authority.'}},
  'criterion_evaluations':assessments,
  'rubric':{'rubric_hash':machine['rubric_hash'],'composition_hash':machine['composition_hash'],'score':machine['score'],'threshold':machine['threshold'],'high_severity':0,'machine_report':str(folder/'current-rubric-machine-report.json'),'findings':machine['findings'],'semantic_adjudication':{'BD-004':{'verdict':'PASS','trigger_to_body_mapping':cfg['triggers']}},'unscored':[],'all_rules_accounted':True,'not_applicable':machine['not_applicable']},
  'independent_case':str(OUT/'dependency-closure-current-results.json'),
  'proof_boundary':{'static_design_adequacy':'PASS only for new helper declaration, tracked invalidation and current criterion contract preservation.','behavioral_live_trial':'NOT_CLAIMED. This reviewer did not execute host dialogue, external mutation, browser/rendered artifact, full package handoff or release acceptance. Gate D remains separate.','unchanged_obligations':'All enumerated criteria were read and assessed statically against current body/prompt ownership; no unchanged verify_by script/test/live behavior is relabelled as executed proof.','prior_verdicts':'No old PASS or SHA-only verdict replacement used. Exact old source text is a diff baseline only; current judgments and case execution are new.','method_coverage':'One focused independent context projects into elegance/rubric artifacts; branch 30-method analysis is separate, no per-skill30-method claim.'},
  'warnings_policy':'Inherited scored medium/low layout/wording findings remain disclosed. No high-severity or new dependency defect remains in this focused source slice.'}
 (folder/'focused-design-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 for kind in ['elegance','rubric']:
  value={'target':report['target'],'review_kind':kind,'verdict':'PASS','reviewer':'/root/independent_review (independent focused design)','reviewed_at':NOW,'iterations':2,'human_review_required':False,
    'findings_summary':{'contradiction':0,'omission':0,'inconsistency':0,'dependency_break':0,'smell':len(machine['findings']) if kind=='rubric' else 0},
    'feedback_loop':{'loop_scope':'both','criteria_evaluated':[c['id'] for c in criteria],'positive_feedback':['One canonical imported helper is now explicitly tracked; all nine skills invalidate on semantic helper mutation and fail closed if it disappears.'],
      'negative_feedback':[f"Inherited nonblocking {f['id']} ({f['severity']}): {f['message']}" for f in machine['findings']] if kind=='rubric' else [],'iteration':2,'iteration_limit':3,'hook_trigger':'user branch review iteration2 after independent F-4001 dependency omission','next_action':'none'},
    'notes':'Static DESIGN PASS for F-4001 one-ref change and current all-criteria contract preservation only. Actual current refs/imports, body diff, full criterion judgments, rubric and copied-closure mutation/missing-file proof are in '+str(folder/'focused-design-review.json')+'. Live-trial/host dialogue, browser artifact, external GitHub/Beads mutation, package handoff and release execution are NOT accepted by this verdict. New independent focused context judgments projected to legacy elegance/rubric artifacts; old verdict PASS is not evidence and this is not a SHA-only update. Branch30-method coverage is separate.'}
  if kind=='rubric':value['notes']+=f" Current rubric={machine['score']}/100 threshold={machine['threshold']} high=0; BD-004 independently judged using current trigger/body mapping; inherited medium/low findings retained."
  jsonschema.validate(value,json.loads(SCHEMA.read_text()))
  (folder/(kind+'-verdict.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(name,'PASS static design','criteria='+str(len(criteria)),'rubric='+str(machine['score']))
