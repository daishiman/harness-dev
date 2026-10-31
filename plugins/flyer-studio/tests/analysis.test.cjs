"use strict";
const test=require("node:test"), assert=require("node:assert/strict"), fs=require("node:fs"), os=require("node:os"), path=require("node:path");
const A=require("../scripts/analysis.cjs");
function setup(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),"flyer-analysis-"));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));fs.writeFileSync(dir+"/source.png","readonly image fixture");return dir;}
const draft=(dir)=>({producer:"analysis-producer",purpose:{audience:"AI導入の担当者",benefit:"実例と相談の理解",action:"QRで詳細を確認する"},constraints:["顔と原素材を保持する"],requirements:[{id:"R01",text:"回答を主役とする",kind:"required"}],sources:[{id:"F07",file:dir+"/source.png"}]});
function ready(t){const dir=setup(t);A.template(dir,draft(dir));return filled(dir);}
function filled(dir){const a=A.read(dir+"/analysis.json");const v=a.variants[0];v.observations=[{region:{x:10,y:10,w:50,h:50},observation:"右上の縦の問いと中央の横回答の関係を確認した",refIds:["DD02"]}];v.preservedStrengths=["右上の縦導入と中央の横回答の構図を保持する"];v.decisions=[{requirementId:"R01",candidate:"横回答を大きくし入口の強さを保持する",decision:"adopt",reason:"両方のコピーを読める強さで残すための変更である",targets:["text:answer"],refIds:["DD02"]}];v.nextActions=["顔と干渉しない大きさで横回答を比較する"];A.write(dir+"/analysis.json",a);return {dir,a};}
function approve(dir){A.reviewTemplate(dir);const r=A.read(dir+"/analysis-review.json");r.reviewer="independent-analysis-reviewer";r.reviewedAt=new Date().toISOString();r.decision="PASS";r.returnTo="run-create-flyer";for(const c of Object.values(r.checks)){c.verdict="PASS";c.evidence="元画像の領域と要求別の分析を照合して根拠の連続を確認した";}A.write(dir+"/analysis-review.json",r);return r;}
test("analysis template is not approvable without visual evidence",t=>{const dir=setup(t);A.template(dir,{sources:[{id:"F07",file:dir+"/source.png"}]});assert.throws(()=>A.validate(dir),/分析/);});
test("independent reviewed analysis works without native scene",t=>{const {dir}=ready(t);assert.equal(A.validate(dir).fail,0);approve(dir);assert.equal(A.validateReview(dir).fail,0);});
test("source modification invalidates analysis approval",t=>{const {dir}=ready(t);approve(dir);fs.appendFileSync(dir+"/source.png"," changed");assert.throws(()=>A.validateReview(dir),/元画像|source/);});
test("producer cannot approve own analysis",t=>{const {dir}=ready(t);const r=approve(dir);r.reviewer="analysis-producer";A.write(dir+"/analysis-review.json",r);assert.throws(()=>A.validateReview(dir),/独立/);});
test("missing one of four analysis checks is rejected",t=>{const {dir}=ready(t);const r=approve(dir);delete r.checks.feasibility;A.write(dir+"/analysis-review.json",r);assert.throws(()=>A.validateReview(dir),/契約|4|評価/);});
test("analysis change invalidates prior review",t=>{const {dir,a}=ready(t);approve(dir);a.variants[0].nextActions.push("別の案との比較を追加する");A.write(dir+"/analysis.json",a);assert.throws(()=>A.validateReview(dir),/古|分析/);});
test("pending required decision blocks analysis use",t=>{const {dir,a}=ready(t);a.variants[0].decisions[0].decision="pending";A.write(dir+"/analysis.json",a);assert.throws(()=>A.validate(dir),/未決/);});
test("declining a required request blocks analysis use",t=>{const {dir,a}=ready(t);a.variants[0].decisions[0].decision="decline";A.write(dir+"/analysis.json",a);assert.throws(()=>A.validate(dir),/必須/);});

test("approved analysis is required when used for production and finalization",t=>{const {dir,a}=ready(t);assert.throws(()=>A.assertApproved(dir,{brief:{analysisMode:"source-artifact"}}),/analysis-review/);approve(dir);assert.equal(A.assertApproved(dir,{brief:{analysisMode:"source-artifact"}}).fail,0);a.purpose.action="新しい行動へ変更する";A.write(dir+"/analysis.json",a);assert.throws(()=>A.assertApproved(dir,{brief:{analysisMode:"source-artifact"}}),/古|context/);});
test("unsealed purpose and constraints need deliberate sealing before review",t=>{const {dir,a}=ready(t);a.constraints.push("白い外縁を保持する");A.write(dir+"/analysis.json",a);assert.throws(()=>A.reviewTemplate(dir),/古/);assert.equal(A.seal(dir).fail,0);approve(dir);assert.equal(A.validateReview(dir).fail,0);});
test("unknown design knowledge reference is rejected",t=>{const {dir,a}=ready(t);a.variants[0].observations[0].refIds=["DD99"];A.write(dir+"/analysis.json",a);assert.throws(()=>A.validate(dir),/知見ID/);});
test("source-list coverage prevents unreviewed original artifacts",t=>{const {dir,a}=ready(t);a.sources.push({id:"F11",file:dir+"/source.png",sha256:A.sha(dir+"/source.png")});A.write(dir+"/analysis.json",a);assert.throws(()=>A.validate(dir),/漏れ/);});

test("required scope cannot silently target a nonexistent original artifact",t=>{const {dir,a}=ready(t);a.requirements[0].variantIds=["missing"];a.variants[0].decisions=[];A.write(dir+"/analysis.json",a);assert.throws(()=>A.validate(dir),/契約|対象案ID/);});

// SS-7: the analysis gate is an explicit mode; skipping the diagnosis is recorded, not implied.
const P=require("../scripts/project.cjs");
const purpose={audience:"AI導入の担当者",benefit:"実例と相談の理解",action:"QRで詳細を確認する"};
function caseDir(t){const root=setup(t),dir=root+"/case";P.init(dir);const b=A.read(dir+"/brief.json");b.purpose=purpose;A.write(dir+"/brief.json",b);fs.writeFileSync(dir+"/source.png","readonly image fixture");return dir;}
test("new-from-brief records the skipped diagnosis stages and refuses a hidden analysis",t=>{const dir=caseDir(t);assert.equal(A.read(dir+"/brief.json").analysisMode,"new-from-brief");assert.deepEqual(A.assertApproved(dir),{fail:0,mode:"new-from-brief",skippedStages:["run-analyze-flyer","assign-flyer-analysis-evaluator"]});A.write(dir+"/analysis.json",{});assert.throws(()=>A.assertApproved(dir),/new-from-brief/);});
test("an undecided analysis mode is rejected instead of defaulting",t=>{const dir=setup(t);assert.throws(()=>A.assertApproved(dir,{brief:{}}),/未決/);assert.throws(()=>A.assertApproved(dir,{brief:{analysisRequired:true}}),/analysisRequired は廃止/);});
test("analysis-template switches the case to source-artifact and copies the brief purpose",t=>{const dir=caseDir(t);const r=A.template(dir,{sources:[{id:"F07",file:dir+"/source.png"}]});assert.equal(r.analysisMode,"source-artifact");assert.equal(A.read(dir+"/brief.json").analysisMode,"source-artifact");assert.deepEqual(A.read(dir+"/analysis.json").purpose,purpose);assert.throws(()=>A.assertApproved(dir),/分析契約が不足|analysis-review/);});
test("analysis purpose cannot differ from the brief purpose",t=>{const dir=caseDir(t);assert.throws(()=>A.template(dir,{...draft(dir),purpose:{...purpose,action:"別の行動"}}),/brief の今回の目的/);assert.equal(fs.existsSync(dir+"/analysis.json"),false);A.template(dir,draft(dir));const {a}=filled(dir);assert.doesNotThrow(()=>A.validate(dir,{unsealed:true}));a.purpose.action="分析で書き換えた行動";A.write(dir+"/analysis.json",a);assert.throws(()=>A.validate(dir,{unsealed:true}),/brief の今回の目的/);});
test("analysis policy covers only declared yardsticks and fails closed when one is missing",t=>{const contract=require("../scripts/design.cjs").contract;assert.ok(contract.analysisPolicyFiles.includes("references/stage-common.md")&&contract.analysisPolicyFiles.includes("references/review-rubric.md"));assert.equal(contract.analysisPolicyFiles.some(f=>/SKILL\.md$|manifest|presets\//.test(f)),false);assert.match(A.policyFingerprint(),/^[a-f0-9]{64}$/);const exists=fs.existsSync;t.mock.method(fs,"existsSync",f=>String(f).endsWith("references/review-rubric.md")?false:exists(f));assert.throws(()=>A.policyFingerprint(),/分析規範のファイルがありません/);assert.throws(()=>require("../scripts/design.cjs").reviewPolicyFingerprint(),/品質契約のファイルがありません/);});
test("re-review archives the earlier analysis-review and records its FIX before handing out a fresh sheet",t=>{const {dir}=ready(t);A.reviewTemplate(dir);const r=A.read(dir+"/analysis-review.json");r.reviewer="independent-analysis-reviewer";r.reviewedAt=new Date().toISOString();r.decision="FIX";r.returnTo="run-analyze-flyer";r.mandatoryFixes=[{text:"横回答の読み順の根拠が元画像の領域と結びついていない",serves:["E1"]}];for(const c of Object.values(r.checks)){c.verdict="PASS";c.evidence="元画像の領域と要求別の分析を照合して根拠の連続を確認した";}r.checks.evidenceAlignment.verdict="FIX";A.write(dir+"/analysis-review.json",r);A.reviewTemplate(dir);const archived=fs.readdirSync(dir+"/reviews").map(d=>dir+"/reviews/"+d+"/analysis-review.json").filter(f=>fs.existsSync(f));assert.equal(archived.length,1);assert.equal(A.read(archived[0]).decision,"FIX");assert.equal(A.read(dir+"/analysis-review.json").decision,"pending");const ledger=A.read(dir+"/cycle-ledger.json");assert.equal(ledger.entries.filter(e=>e.trigger==="analysis-review"&&e.consumed).length,1);});

const C=require("../scripts/checks.cjs");
function fixReview(dir) {
 const r=approve(dir);
 r.decision="FIX";r.returnTo="run-analyze-flyer";
 r.checks.evidenceAlignment.verdict="FIX";
 r.mandatoryFixes=[{text:"主題の読み順を示す根拠が元画像の観察領域と対応していない",serves:["E1"]}];
 A.write(dir+"/analysis-review.json",r);
 return r;
}
test("提案のtyped FIXは本質条項を保持し、台帳再読込と原文退避を経て最新PASSへ進める",t=>{
 const {dir}=ready(t),r=fixReview(dir),original=fs.readFileSync(dir+"/analysis-review.json");
 const [entry]=C.recordCycles(dir).entries;
 assert.deepEqual([entry.trigger,entry.fixClasses,entry.returnTo,entry.consumed],["analysis-review",{},["run-analyze-flyer"],true]);
 assert.equal(C.recordCycles(dir).entries.length,1);
 A.reviewTemplate(dir);
 const archived=fs.readdirSync(dir+"/reviews").map(name=>dir+"/reviews/"+name+"/analysis-review.json").filter(fs.existsSync);
 assert.equal(archived.length,1);
 assert.deepEqual(fs.readFileSync(archived[0]),original);
 assert.deepEqual(A.read(archived[0]).mandatoryFixes,r.mandatoryFixes);
 assert.equal(C.recordCycles(dir).entries.length,1,"退避済みの同じFIXを二重消費しない");
 approve(dir);
 assert.equal(A.validateReview(dir).fail,0);
 assert.equal(C.cycleSummary(C.recordCycles(dir)).consumed,1);
});
test("提案の必須修正はserves欠落・空配列・未知本質IDを取込で拒否する",t=>{
 for(const mutate of [fix=>delete fix.serves,fix=>fix.serves=[],fix=>fix.serves=["E99"]]){
  const {dir}=ready(t),r=fixReview(dir);mutate(r.mandatoryFixes[0]);A.write(dir+"/analysis-review.json",r);
  assert.throws(()=>A.validateReview(dir),/serves/);
  assert.throws(()=>C.recordCycles(dir),/serves/);
  assert.equal(fs.existsSync(dir+"/cycle-ledger.json"),false,"不正なFIXを保存しない");
 }
});
test("4条件全PASSの好みだけは提案PASSとして記録しcycleを消費しない",t=>{
 const {dir}=ready(t),r=approve(dir);
 r.preferenceNotes=[{text:"好みとして背景の青を少し淡くしたいが目的や印刷条件は満たす"}];
 A.write(dir+"/analysis-review.json",r);
 assert.equal(A.validateReview(dir).fail,0);
 const [entry]=C.recordCycles(dir).entries;
 assert.deepEqual([entry.consumed,entry.cycle,entry.fixClasses,entry.returnTo],[false,0,{},[]]);
 assert.equal(C.recordCycles(dir).entries.length,1);
 assert.equal(C.cycleSummary(C.recordCycles(dir)).consumed,0);
});
test("提案のdecisionと4条件と必須修正が矛盾する記録を取込で拒否する",t=>{
 for(const mutate of [
  r=>{for(const check of Object.values(r.checks))check.verdict="PASS";},
  r=>{for(const check of Object.values(r.checks))check.verdict="PASS";r.mandatoryFixes=[];r.preferenceNotes=[{text:"見た目の好みだけなので必須の未達ではない"}];},
  r=>{r.decision="PASS";r.returnTo="run-create-flyer";r.mandatoryFixes=[];},
  r=>{r.checks.feasibility.verdict="pending";},
 ]){
  const {dir}=ready(t),r=fixReview(dir);mutate(r);A.write(dir+"/analysis-review.json",r);
  assert.throws(()=>A.validateReview(dir),/提案評価/);
  assert.throws(()=>C.recordCycles(dir),/提案評価/);
  assert.equal(fs.existsSync(dir+"/cycle-ledger.json"),false);
 }
});
test("旧文字列FIXは通常取込を止め、原記録を改変せず退避して新型の再評価へ移れる",t=>{
 const {dir}=ready(t),r=approve(dir);
 r.decision="FIX";r.returnTo="run-analyze-flyer";
 r.mandatoryFixes=["本質への対応も4条件との整合も記録されていない旧い所見"];
 A.write(dir+"/analysis-review.json",r);
 const original=fs.readFileSync(dir+"/analysis-review.json");
 assert.throws(()=>C.recordCycles(dir),/旧文字列.*serves.*analysis-review-template/);
 assert.throws(()=>A.validateReview(dir),/分析契約/);
 A.reviewTemplate(dir);
 const archived=fs.readdirSync(dir+"/reviews").map(name=>dir+"/reviews/"+name+"/analysis-review.json").filter(fs.existsSync);
 assert.deepEqual(fs.readFileSync(archived[0]),original);
 const [entry]=C.recordCycles(dir).entries;
 assert.deepEqual(entry.fixClasses,{});assert.equal(entry.consumed,true);assert.match(entry.reason,/不明.*分類せず/);
 assert.deepEqual(A.read(dir+"/analysis-review.json").mandatoryFixes,[]);
 approve(dir);
 assert.equal(A.validateReview(dir).fail,0);
 assert.equal(C.cycleSummary(C.recordCycles(dir)).consumed,1);
});

test("analysis-review CLI validation stays read-only for PASS/FIX; caller still records the cycle", t => {
 const {spawnSync}=require("node:child_process");
 const {dir}=ready(t);const review=approve(dir);
 const snapshot=()=>Object.fromEntries(fs.readdirSync(dir,{recursive:true}).filter(f=>fs.statSync(path.join(dir,f)).isFile()).sort().map(f=>[f,fs.readFileSync(path.join(dir,f)).toString("base64")]));
 const run=()=>spawnSync(process.execPath,[path.join(__dirname,"../scripts/cli.cjs"),"analysis-review-validate","--project",dir],{encoding:"utf8"});
 const passBefore=snapshot();assert.equal(run().status,0);assert.deepEqual(snapshot(),passBefore);
 review.decision="FIX";review.returnTo="run-analyze-flyer";review.checks.evidenceAlignment.verdict="FIX";
 review.mandatoryFixes=[{text:"観察と採否理由を元画像の領域へ結び直す",serves:["E1"]}];A.write(path.join(dir,"analysis-review.json"),review);
 const fixBefore=snapshot();const result=run();assert.equal(result.status,1);assert.match(result.stderr,/run-analyze-flyer|FIX|修正/);assert.deepEqual(snapshot(),fixBefore);
 assert.equal(fs.existsSync(path.join(dir,"cycle-ledger.json")),false);
 A.reviewTemplate(dir);const ledger=A.read(path.join(dir,"cycle-ledger.json"));assert.equal(ledger.entries.filter(e=>e.trigger==="analysis-review"&&e.consumed).length,1);
});
