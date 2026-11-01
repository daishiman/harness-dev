"use strict";
// Analysis artifacts are local attestations, never automated visual judgments.
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto"),{isDeepStrictEqual}=require("node:util"),Ajv=require("ajv");
const ROOT=path.resolve(__dirname,"..");
const read=f=>JSON.parse(fs.readFileSync(f,"utf8"));
const write=(f,v)=>{fs.mkdirSync(path.dirname(f),{recursive:true});fs.writeFileSync(f,JSON.stringify(v,null,2)+"\n");};
const sha=f=>crypto.createHash("sha256").update(fs.readFileSync(f)).digest("hex");
const hash=v=>crypto.createHash("sha256").update(JSON.stringify(v)).digest("hex");
const CHECKS=["evidenceAlignment","completeness","changeDiscipline","feasibility"];
const SKIPPED=["run-analyze-flyer","assign-flyer-analysis-review"];
// The yardstick list lives only in design-contract.json; a missing file fails closed.
function policyFingerprint(){
 const files=read(path.join(ROOT,"references/design-contract.json")).analysisPolicyFiles;
 if(!Array.isArray(files)||!files.length)throw Error("design-contract.json に analysisPolicyFiles（分析の規範）がありません");
 return hash(files.map(f=>{const target=path.resolve(ROOT,f);if(!target.startsWith(ROOT+path.sep))throw Error("分析規範の範囲外参照: "+f);if(!fs.existsSync(target))throw Error("分析規範のファイルがありません: "+f);return [f,sha(target)];}));
}
// The brief holds this request's purpose; analysis copies it and never overrides it.
function briefOf(dir){const f=path.join(dir,"brief.json");return fs.existsSync(f)?read(f):null;}
function assertSamePurpose(b,purpose){if(b&&!isDeepStrictEqual(purpose,b.purpose))throw Error("分析の目的が brief の今回の目的（purpose）と異なります。brief.purpose を正にしてください");}
function contextFingerprint(dir,a){
 const b=fs.existsSync(path.join(dir,"brief.json"))?read(path.join(dir,"brief.json")):null;
 const native=b?{title:b.title,purpose:b.purpose,page:b.page,policy:b.policy,feedback:(b.feedback||[]).map(({id,kind,request,variantIds})=>({id,kind,request,variantIds})),analysisBindings:b.analysisBindings||[],singleUseRefs:b.singleUseRefs||[]}:null;
 return hash({native,purpose:a.purpose,constraints:a.constraints,requirements:a.requirements});
}
function schemaCheck(name,a){const ajv=new Ajv({allErrors:true,strict:false}),validate=ajv.compile(read(path.join(ROOT,"schemas",name+".schema.json")));if(!validate(a))throw Error("分析契約が不足: "+ajv.errorsText(validate.errors));}
function sourceFingerprint(a){return hash(a.sources.map(s=>[s.id,s.file,s.sha256]));}
function unique(values,label){if(new Set(values).size!==values.length)throw Error("分析の"+label+"が重複しています");}
function refIds(){const f=path.join(ROOT,"references/design-knowledge-index.json");if(!fs.existsSync(f))throw Error("分析の指針ID正本がありません");return new Set(read(f).entries.map(e=>e.id));}
function applicable(a,id){return a.requirements.filter(r=>!r.variantIds||r.variantIds.includes(id));}
function validate(dir,{unsealed=false}={}){
 const a=read(path.join(dir,"analysis.json"));schemaCheck("analysis",a);assertSamePurpose(briefOf(dir),a.purpose);
 unique(a.sources.map(s=>s.id),"元画像ID");unique(a.variants.map(v=>v.id),"案ID");unique(a.requirements.map(r=>r.id),"要求ID");
 for(const s of a.sources){const file=path.resolve(dir,s.file);if(!fs.existsSync(file)||sha(file)!==s.sha256)throw Error("元画像sourceが変更または欠落: "+s.id);if(fs.existsSync(path.join(dir,"scene.json"))&&file.startsWith(path.join(dir,"out")+path.sep))throw Error("元画像は再描画で変わらないreadonly snapshotを参照してください: "+s.id);}
 for(const r of a.requirements)if(r.variantIds?.some(id=>!a.variants.some(v=>v.id===id)))throw Error("分析要求の対象案IDがありません: "+r.id);
 const refs=refIds();
 for(const v of a.variants){
  if(!a.sources.some(s=>s.id===v.sourceId))throw Error("分析の元画像参照がありません: "+v.id);
  const required=applicable(a,v.id);unique(v.decisions.map(d=>d.requirementId),"案別要求ID");
  if(v.decisions.length!==required.length||required.some(r=>!v.decisions.some(d=>d.requirementId===r.id)))throw Error("分析に要求の漏れがあります: "+v.id);
  for(const d of v.decisions){const r=required.find(r=>r.id===d.requirementId);if(d.decision==="pending")throw Error("分析に未決要求があります: "+v.id+"/"+d.requirementId);if(r.kind==="required"&&d.decision==="decline")throw Error("分析で必須要求を見送れません: "+d.requirementId);}
  for(const e of [...v.observations,...v.decisions])for(const id of e.refIds)if(!refs.has(id))throw Error("分析の参照知見IDがありません: "+id);
 }
 if(a.sources.some(source=>!a.variants.some(v=>v.sourceId===source.id)))throw Error("分析の元画像対象に漏れがあります");
 // A pilot must be a strict subset: trying every variant at once is not a pilot.
 const pilot=a.executionPlan?.pilotVariantIds;
 if(pilot&&(pilot.some(id=>!a.variants.some(v=>v.id===id))||pilot.length>=a.variants.length))throw Error("先行試作案は分析案の一部に限ってください");
 if(!unsealed&&(a.policyFingerprint!==policyFingerprint()||a.contextFingerprint!==contextFingerprint(dir,a)))throw Error("分析の規範または要求contextが古いです。分析を再確認してsealしてください");
 return {fail:0,analysisSha256:sha(path.join(dir,"analysis.json")),sourceFingerprint:sourceFingerprint(a),policyFingerprint:policyFingerprint()};
}
function template(dir,input){
 dir=path.resolve(dir);fs.mkdirSync(dir,{recursive:true});const f=path.join(dir,"analysis.json");if(fs.existsSync(f))throw Error("既存analysis.jsonを上書きしません");
 if(Array.isArray(input))input={sources:input};
 if(!input?.sources?.length)throw Error("分析のsources[{id,file}]が必要です");
 const brief=briefOf(dir),b=brief||{};
 if(input.purpose)assertSamePurpose(brief,input.purpose);
 const requirements=input.requirements||(b.feedback||[]).map(e=>({id:e.id,text:e.request,kind:e.kind,...(Array.isArray(e.variantIds)?{variantIds:e.variantIds}:{})}));
 const sources=input.sources.map(s=>({id:s.id,file:path.resolve(dir,s.file),sha256:sha(path.resolve(dir,s.file))}));
 const ids=sources.map(s=>s.id);
 const a={version:1,producer:input.producer||b.designer||"",purpose:brief?brief.purpose:input.purpose||{audience:"",benefit:"",action:""},constraints:input.constraints||[],policyFingerprint:policyFingerprint(),contextFingerprint:"0".repeat(64),sources,requirements,variants:ids.map(id=>({id,sourceId:sources.find(s=>s.id===id)?.id||sources[0].id,observations:[],preservedStrengths:[],decisions:requirements.filter(r=>!r.variantIds||r.variantIds.includes(id)).map(r=>({requirementId:r.id,candidate:"",decision:"pending",reason:"",targets:[],refIds:[]})),nextActions:[]}))};
 a.contextFingerprint=contextFingerprint(dir,a);
 // Diagnosing existing artwork is what makes a case source-artifact.
 if(brief&&brief.analysisMode!=="source-artifact")write(path.join(dir,"brief.json"),{...brief,analysisMode:"source-artifact"});
 write(f,a);return {file:f,status:"pending-human-analysis",analysisMode:brief?"source-artifact":undefined};
}
function seal(dir){validate(dir,{unsealed:true});const f=path.join(dir,"analysis.json"),a=read(f);a.contextFingerprint=contextFingerprint(dir,a);a.policyFingerprint=policyFingerprint();write(f,a);return validate(dir);}
// 再評価は旧い評価を reviews/<時刻>/ へ退避してから空の台帳を出す（目視評価の renewReview と同じ方式）。退避の前に cycle 台帳へ記録し、FIX の回数を失わない。
function reviewTemplate(dir){const v=validate(dir),f=path.join(dir,"analysis-review.json");if(fs.existsSync(f)){require("./checks.cjs").recordCycles(dir,{allowLegacyAnalysis:true});const to=path.join(dir,"reviews",new Date().toISOString().replace(/[-:.]/g,""),"analysis-review.json");if(fs.existsSync(to))throw Error("退避先に既存の提案評価があります: "+path.relative(dir,to));fs.mkdirSync(path.dirname(to),{recursive:true});fs.renameSync(f,to);}write(f,{version:1,analysisSha256:v.analysisSha256,sourceFingerprint:v.sourceFingerprint,policyFingerprint:v.policyFingerprint,reviewer:"",reviewedAt:"",checks:Object.fromEntries(CHECKS.map(k=>[k,{verdict:"pending",evidence:""}])),mandatoryFixes:[],preferenceNotes:[],decision:"pending",returnTo:"run-analyze-flyer"});return {file:f,status:"pending-independent-review"};}
// Validate the completed review's meaning independently of artifact freshness.
// The ledger uses this same intake contract and never infers a visual fixClass.
function classifyReview(r) {
 schemaCheck("analysis-review",r);
 require("./design.cjs").assertMandatoryFixes(r.mandatoryFixes,"提案評価");
 if(CHECKS.some(k=>r.checks[k].verdict==="pending"))throw Error("提案評価の4条件が未完です");
 const hasFailure=CHECKS.some(k=>r.checks[k].verdict==="FIX");
 if(r.decision==="FIX") {
  if(!hasFailure||!r.mandatoryFixes.length)throw Error("提案評価のFIXには4条件の未達と必須修正が必要です。好みだけなら全条件PASSとしpreferenceNotesへ記録してください");
  if(r.returnTo!=="run-analyze-flyer")throw Error("提案評価の FIX は run-analyze-flyer へ戻します: returnTo="+r.returnTo);
 } else if(r.decision==="PASS") {
  if(hasFailure||r.mandatoryFixes.length||r.returnTo!=="run-create-flyer")throw Error("提案評価のPASSは4条件全PASS・必須修正0・run-create-flyerへの引継ぎが必要です");
 } else throw Error("提案評価の判定が未完です");
 return {fix:r.decision==="FIX",preferenceNotes:(r.preferenceNotes||[]).length};
}
function validateReview(dir){
 const current=validate(dir),a=read(path.join(dir,"analysis.json")),r=read(path.join(dir,"analysis-review.json"));classifyReview(r);
 if(r.analysisSha256!==current.analysisSha256||r.sourceFingerprint!==current.sourceFingerprint||r.policyFingerprint!==current.policyFingerprint)throw Error("分析評価が古いです。分析/元画像/規範を再確認してください");
 const norm=s=>String(s).normalize("NFKC").replace(/\s/g,"").toLowerCase();
 if(!norm(r.reviewer)||norm(r.reviewer)===norm(a.producer))throw Error("独立した別担当による分析評価が必要です");
 if(!/^\d{4}-\d{2}-\d{2}T/.test(r.reviewedAt)||!Number.isFinite(Date.parse(r.reviewedAt)))throw Error("分析評価の日時が不正です");
 if(r.decision!=="PASS")throw Error("分析評価が未承認またはFIXです。run-analyze-flyerへ戻してください");
 return {fail:0,...current,reviewSha256:sha(path.join(dir,"analysis-review.json")),reviewer:r.reviewer};
}
// Request bindings map requirements, not the identity of the artwork whose
// strengths must survive. Until a separate, explicit preservation map exists,
// keep those identities and fail rather than guessing from requirement scope.
function resolvePreservations(analysis, outputIds) {
 unique(outputIds,"保持点の出力案ID");
 unique((analysis.variants||[]).map(v=>v.id),"保持点の分析案ID");
 const outputSet=new Set(outputIds);
 const resolved=Object.fromEntries(outputIds.map(id=>[id,[]]));
 for(const variant of analysis.variants||[]){
  const strengths=variant.preservedStrengths||[];
  if(!strengths.length)continue;
  if(!outputSet.has(variant.id))throw Error("分析の保持点に対応する出力案がありません: "+variant.id+"。保持点のある分析案IDを出力にも残すか、出力IDに合わせて分析と独立評価をやり直してください。analysisBindings は要求の対応であり保持点の改名対応には使えません");
  resolved[variant.id]=[...strengths];
 }
 return resolved;
}
function validateProductionBridge(analysis, project) {
 const {brief,scene}=project;
 const outputIds=scene.variants.map(v=>v.id), inputIds=analysis.variants.map(v=>v.id);
 if(!outputIds.length)throw Error("production bridgeの出力案がありません");
 unique(outputIds,"出力案ID");
 resolvePreservations(analysis, outputIds);
 const briefSchema=read(path.join(ROOT,"schemas/brief.schema.json"));
 const ajv=new Ajv({allErrors:true,strict:false});
 for(const key of ["feedback","analysisBindings"]){
  if(brief[key]===undefined)continue;
  const valid=ajv.compile(briefSchema.properties[key]);
  if(!valid(brief[key]))throw Error("production bridgeの"+key+"契約が不足: "+ajv.errorsText(valid.errors));
 }
 const feedback=brief.feedback||[], bindings=brief.analysisBindings||[];
 unique(feedback.map(f=>f.id),"feedback ID");
 for(const binding of bindings){
  if(!analysis.requirements.some(r=>r.id===binding.requirementId))throw Error("analysisBindingsに未知の要求ID: "+binding.requirementId);
  if(!feedback.some(f=>f.id===binding.feedbackId))throw Error("analysisBindingsの対応feedbackがありません: "+binding.feedbackId);
  if(binding.variantIds.some(id=>!outputIds.includes(id)))throw Error("analysisBindingsの対象出力案がありません: "+binding.requirementId);
 }
 const sameIds=inputIds.length===outputIds.length&&inputIds.every(id=>outputIds.includes(id));
 const resolved=[];
 for(const requirement of analysis.requirements){
  const sourceScope=requirement.variantIds||inputIds;
  const explicit=bindings.filter(binding=>binding.requirementId===requirement.id);
  if(!sameIds&&!explicit.length)throw Error("入力案と出力案が異なるためanalysisBindingsで対応mappingが必要です: "+requirement.id);
  const mapped=explicit.length?explicit:[{requirementId:requirement.id,feedbackId:requirement.id,variantIds:sourceScope}];
  const expected=!requirement.variantIds?outputIds:sameIds?sourceScope:[...new Set(mapped.flatMap(binding=>binding.variantIds))];
  const covered=new Set();
  const decisions=analysis.variants.filter(v=>sourceScope.includes(v.id)).flatMap(v=>v.decisions.filter(d=>d.requirementId===requirement.id).map(d=>d.decision));
  for(const binding of mapped){
   const entry=feedback.find(f=>f.id===binding.feedbackId);
   if(!entry)throw Error("承認分析の要求に対応するfeedbackがありません: "+requirement.id);
   if(entry.kind!==requirement.kind)throw Error("分析の必須required/proposal区分を変更できません: "+requirement.id);
   if(entry.decision==="pending"||(requirement.kind==="required"&&!["apply","preserve"].includes(entry.decision)))throw Error("必須要求の採用/維持またはproposal採否が未解決です: "+requirement.id);
   if((decisions.every(d=>d==="decline")&&entry.decision!=="decline")||(entry.decision==="decline"&&!decisions.includes("decline")))throw Error("承認分析とproposal見送りの対応が異なります: "+requirement.id);
   const originalVariant=analysis.variants.find(v=>v.id===entry.source.variantId)||analysis.variants.find(v=>v.sourceId===entry.source.variantId);
   const original=originalVariant&&analysis.sources.find(source=>source.id===originalVariant.sourceId);
   if(!original||!sourceScope.includes(originalVariant.id)||original.sha256!==entry.source.pngSha256)throw Error("feedbackの元画像SHA/元案が分析の対象と対応しません: "+requirement.id);
   const originalDecision=originalVariant.decisions.find(d=>d.requirementId===requirement.id);
   if((originalDecision.decision==="decline")!==(entry.decision==="decline"))throw Error("feedbackの採否が対応する元案の見送りと異なります: "+requirement.id);
   const targets=entry.variantIds===undefined||entry.variantIds==="all"?outputIds:entry.variantIds;
   if(targets.some(id=>!outputIds.includes(id)))throw Error("feedbackの対象出力案がありません: "+requirement.id);
   for(const id of binding.variantIds){
    if(!expected.includes(id)||!targets.includes(id))throw Error("分析要求に対応するfeedback対象が漏れています: "+requirement.id+"/"+id);
    const corresponding=sameIds&&analysis.variants.find(v=>v.id===id)?.decisions.find(d=>d.requirementId===requirement.id);
    if(corresponding&&(corresponding.decision==="decline")!==(entry.decision==="decline"))throw Error("出力対象の採否と元案の見送りが対応しません。対象別feedbackへ分けてください: "+requirement.id+"/"+id);
    if(covered.has(id))throw Error("analysisBindingsの対象出力が重複しています: "+requirement.id+"/"+id);
    covered.add(id);
   }
   resolved.push({...binding,decision:entry.decision});
  }
  if(expected.some(id=>!covered.has(id)))throw Error("分析要求の対象出力に対応漏れがあります: "+requirement.id);
 }
 return resolved;
}
// new-from-brief skips the diagnosis stages and says so; source-artifact needs an independent PASS.
function assertApproved(dir,project){
 const b=project?.brief||briefOf(dir)||{};
 if(b.analysisMode==="new-from-brief"){
  if(fs.existsSync(path.join(dir,"analysis.json")))throw Error("analysis.json があるのに analysisMode が new-from-brief です。既存紙面を診断した案件は source-artifact にして独立評価を通してください");
  return {fail:0,mode:"new-from-brief",skippedStages:[...SKIPPED]};
 }
 if(b.analysisMode!=="source-artifact")throw Error("brief.analysisMode（分析の進め方）が未決です。既存紙面を診断するなら source-artifact（analysis.json と独立 PASS の analysis-review.json が要る）、brief から新規に作るなら new-from-brief を書いてください。analysisRequired は廃止しました");
 const approval={...validateReview(dir),mode:"source-artifact"};
 const native=project?.scene?project:fs.existsSync(path.join(dir,"scene.json"))?{brief:b,scene:read(path.join(dir,"scene.json"))}:null;
 if(native)approval.productionBindings=validateProductionBridge(read(path.join(dir,"analysis.json")),native);
 return approval;
}
module.exports={read,write,hash,sha,CHECKS,policyFingerprint,contextFingerprint,sourceFingerprint,template,seal,validate,reviewTemplate,validateReview,classifyReview,validateProductionBridge,resolvePreservations,assertApproved};
