"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const P = require("../scripts/project.cjs"), A = require("../scripts/analysis.cjs"), C = require("../scripts/checks.cjs"), R = require("../scripts/render.cjs"), D = require("../scripts/design.cjs"), E = require("../scripts/essence.cjs");
const { fixture, syntheticReview } = require("./fixture.cjs");
// Synthetic attestations exercise the contract; they are never a real visual approval.
function ready(t, options = {}) {
  const top = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-analysis-bridge-"));
  t.after(() => fs.rmSync(top, { recursive: true, force: true }));
  const dir = path.join(top, "project"), p = fixture(dir);
  p.brief.designer = "unit-analysis-producer"; p.brief.analysisMode = "source-artifact";
  fs.mkdirSync(dir + "/sources");
  for (const id of ["F07", "F11"]) fs.writeFileSync(dir + "/sources/" + id + ".png", "unit-only original " + id);
  if (options.renamed) {
    p.scene.variants.forEach((v, i) => { v.id = "F0" + (i + 1); p.concepts.variants[i].id = v.id; });
  }
  const requirements = [{ id: "PRICE", text: "食事込み料金群を一度だけ掲載する", kind: "required" }];
  if (options.proposal) requirements.push({ id: "ROTATE", text: "角度のある候補を必要な場合だけ比較する", kind: "proposal" });
  if (options.scoped) requirements.push({ id: "VH", text: "F07の縦導入と横回答を保持する", kind: "required", variantIds: ["F07"] });
  p.brief.feedback = requirements.map(r => ({ id: r.id, kind: r.kind, request: r.text,
    source: { variantId: "F07", pngSha256: A.sha(dir + "/sources/F07.png") },
    variantIds: r.id === "VH" ? [options.renamed ? "F01" : "F07"] : "all",
    targets: ["text:price"], analysis: [{ role: "typography", observation: "単体試験として要求と対象の文字要素との対応を記録する" }],
    decision: r.kind === "proposal" ? "decline" : "apply", reason: "単体試験として掲載群と対応する採否の理由を記録する", change: "料金の意味群をまとめて一度だけ配置する候補を試す" }));
  if (options.edit) options.edit(p, requirements);
  P.write(dir + "/brief.json", p.brief); P.write(dir + "/scene.json", p.scene); P.write(dir + "/concepts.json", p.concepts);
  E.baseline(dir, { request: "元画像の良い点を保って要求の料金掲載を直す単体試験" });
  A.template(dir, { producer: p.brief.designer, purpose: p.brief.purpose, constraints: ["原画像を保持する単体契約試験"], requirements, sources: ["F07", "F11"].map(id => ({ id, file: dir + "/sources/" + id + ".png" })) });
  const a = A.read(dir + "/analysis.json");
  for (const v of a.variants) {
    v.observations = [{ region: { x: 10, y: 10, w: 50, h: 50 }, observation: "単体試験用に元画像領域と料金の掲載群との関係を記録する", refIds: ["DD05"] }];
    v.preservedStrengths = [v.id + "の元画像と意味群の関係を維持する"];
    v.decisions = requirements.filter(r => !r.variantIds || r.variantIds.includes(v.id)).map(r => ({ requirementId: r.id, candidate: "単体試験用に承認対象の掲載群を一度だけ置く候補", decision: options.decisionFor?.(v.id, r) || (r.kind === "proposal" ? "decline" : "adopt"), reason: "単体試験用に元の要求から掲載群の判断を追跡する理由", targets: ["text:price"], refIds: ["DD05"] }));
    v.nextActions = ["単体試験の独立した担当の評価を経て制作へ進む"];
  }
  // Source IDs stay on the original images; analysis identities can be deliberately
  // aligned to output IDs before sealing and independently reviewing the analysis.
  if (options.alignAnalysisIds) {
    const ids = new Map(a.variants.map((v, i) => [v.id, p.scene.variants[i].id]));
    for (const v of a.variants) v.id = ids.get(v.id);
    for (const r of a.requirements) if (r.variantIds) r.variantIds = r.variantIds.map(id => ids.get(id));
  }
  if (options.pilot) a.executionPlan = { pilotVariantIds: options.pilot, reason: "主題の保持点が最も壊れやすい案で先に効果を確かめる", propagation: "先行案の目視合格後に同じ処方を残りの案へ展開する" };
  A.write(dir + "/analysis.json", a); A.seal(dir); A.reviewTemplate(dir);
  const r = A.read(dir + "/analysis-review.json"); r.reviewer = "unit-independent-analysis-reviewer"; r.reviewedAt = new Date().toISOString(); r.decision = "PASS"; r.returnTo = "run-create-flyer";
  for (const c of Object.values(r.checks)) { c.verdict = "PASS"; c.evidence = "単体試験用の元画像領域と分析の対応を確認する擬似証跡"; }
  A.write(dir + "/analysis-review.json", r);
  return { dir, p: P.load(dir) };
}
function approved(state) { return A.assertApproved(state.dir, P.load(state.dir)); }

test("required analysis cannot disappear into an empty production feedback list", t => {
  const state = ready(t, { edit: p => { p.brief.feedback = []; } });
  assert.throws(() => approved(state), /bridge|対応|feedback/);
});
test("same requirement and variant IDs automatically bind without extra configuration", t => {
  assert.equal(approved(ready(t)).fail, 0);
});
test("renamed outputs require explicit coverage mapping", t => {
  assert.throws(() => approved(ready(t, { renamed: true })), /mapping|Bindings|対応/);
});
test("explicit mapping allows different input and output IDs and source-scoped requirements", t => {
  const state = ready(t, { renamed: true, alignAnalysisIds: true, scoped: true, edit: p => { p.brief.analysisBindings = [{ requirementId: "PRICE", feedbackId: "PRICE", variantIds: ["F01", "F02"] }, { requirementId: "VH", feedbackId: "VH", variantIds: ["F01"] }]; } });
  assert.equal(approved(state).fail, 0);
  const analysis = A.read(state.dir + "/analysis.json");
  assert.deepEqual(analysis.variants.map(v => [v.id, v.sourceId]), [["F01", "F07"], ["F02", "F11"]], "original image identities remain explicit after deliberate reanalysis");
  const { p, checks, review } = reviewedImages(state);
  assert.deepEqual(review.items.map(item => item.preservationChecks.map(check => check.strength)), [
    ["F07の元画像と意味群の関係を維持する"], ["F11の元画像と意味群の関係を維持する"],
  ]);
  assert.doesNotThrow(() => D.validateReview(review, checks, p));
});
test("global requirements cannot escape to one output, an empty mapping or a nonexistent output", t => {
  for (const variantIds of [["F01"], [], ["missing"]]) {
    const state = ready(t, { renamed: true, alignAnalysisIds: true, edit: p => { p.brief.analysisBindings = [{ requirementId: "PRICE", feedbackId: "PRICE", variantIds }]; } });
    assert.throws(() => approved(state), /対象|漏れ|契約|mapping|Bindings/);
  }
});
test("feedback target exclusions and downgraded required requests are rejected", t => {
  const excluded = ready(t, { edit: p => { p.brief.feedback[0].variantIds = ["F07"]; } });
  assert.throws(() => approved(excluded), /対象|漏れ|対応/);
  const downgraded = ready(t, { edit: p => { p.brief.feedback[0].kind = "proposal"; } });
  assert.throws(() => approved(downgraded), /必須|required/);
});
test("declined proposals remain traceable and cannot simply be dropped", t => {
  assert.equal(approved(ready(t, { proposal: true })).fail, 0);
  const missing = ready(t, { proposal: true, edit: p => { p.brief.feedback = p.brief.feedback.filter(f => f.id !== "ROTATE"); } });
  assert.throws(() => approved(missing), /bridge|対応|feedback/);
});
test("mapping changes after approval invalidate its context", t => {
  const state = ready(t, { renamed: true, alignAnalysisIds: true, edit: p => { p.brief.analysisBindings = [{ requirementId: "PRICE", feedbackId: "PRICE", variantIds: ["F01", "F02"] }]; } });
  assert.equal(approved(state).fail, 0);
  const b = P.read(state.dir + "/brief.json"); b.analysisBindings[0].variantIds = ["F01"]; P.write(state.dir + "/brief.json", b);
  assert.throws(() => approved(state), /古|context/);
});
test("mixed proposal decisions cannot borrow the other original's adoption or decline", t => {
  const options = { proposal: true, decisionFor: (id, r) => r.id === "ROTATE" && id === "F11" ? "adopt" : undefined };
  const wrongSource = ready(t, { ...options, edit: p => { p.brief.feedback.find(f => f.id === "ROTATE").decision = "apply"; } });
  assert.throws(() => approved(wrongSource), /採否|見送り|対応/);
  const wrongOutput = ready(t, options);
  assert.throws(() => approved(wrongOutput), /採否|見送り|対応/);
  const split = ready(t, { ...options, edit: p => {
    const declined = p.brief.feedback.find(f => f.id === "ROTATE");
    declined.id = "ROTATE_F07"; declined.variantIds = ["F07"];
    const adopted = structuredClone(declined);
    adopted.id = "ROTATE_F11"; adopted.variantIds = ["F11"]; adopted.decision = "apply";
    adopted.source = { variantId: "F11", pngSha256: A.sha(p.dir + "/sources/F11.png") };
    p.brief.feedback.push(adopted);
    p.brief.analysisBindings = [
      { requirementId: "ROTATE", feedbackId: declined.id, variantIds: ["F07"] },
      { requirementId: "ROTATE", feedbackId: adopted.id, variantIds: ["F11"] },
    ];
  } });
  assert.equal(approved(split).fail, 0, "each original's different decision can be translated explicitly");
});
test("pilot variants must be a strict, existing subset before propagation", t => {
  const state = ready(t);
  const plan = (pilotVariantIds) => {
    const a = A.read(state.dir + "/analysis.json");
    a.executionPlan = { pilotVariantIds, reason: "主題の保持点が最も壊れやすい案で先に効果を確かめる", propagation: "先行案の目視合格後に同じ処方を残りの案へ展開する" };
    A.write(state.dir + "/analysis.json", a);
    return () => A.validate(state.dir, { unsealed: true });
  };
  assert.doesNotThrow(plan(["F07"]));
  assert.throws(plan(["F07", "F11"]), /一部/);
  assert.throws(plan(["F99"]), /一部/);
});
// Synthetic pilot outputs stand in for a rendered and mechanically checked pilot.
function pilotOutputs(state, id) {
  const p = P.load(state.dir), out = state.dir + "/out/" + id;
  fs.mkdirSync(out, { recursive: true }); fs.writeFileSync(out + "/print.png", "unit-only pilot image " + id);
  const fingerprint = P.fingerprint(p), pngSha256 = A.sha(out + "/print.png");
  P.write(out + "/render.json", { id, fingerprint, pngSha256, createdAt: new Date(Date.now() - 1000).toISOString() });
  const checks = { fingerprint, rows: [{ id, pngSha256 }], issues: [], fail: 0 };
  P.write(state.dir + "/out/pilot-checks.json", checks);
  return { p, checks };
}
function pilotReview(state, { p, checks }, decision = "PASS") {
  const review = syntheticReview(p, checks);
  for (const item of review.items) {
    for (const check of item.feedbackChecks || []) { check.verdict = "PASS"; check.criteria = ["hierarchy"]; }
    item.decision = decision;
    if (decision === "FIX")
      item.mandatoryFixes = [{ text: item.id + " の料金群 y=270 付近が注意書きと近く、元要求 PRICE の一度だけの掲載が読み取りにくい", fixClass: "within-plan", serves: ["E2"], returnTo: "run-create-flyer" }];
  }
  P.write(state.dir + "/pilot-review.json", review);
}
test("propagation beyond the pilot waits for its independent PASS on current images", async t => {
  const state = ready(t, { pilot: ["F07"] }), approval = approved(state);
  const blocked = /先行試作案の独立PASS前/;
  assert.equal(C.assertPilotOrder(P.load(state.dir), "F07", approval), null, "the pilot itself is always renderable");
  assert.throws(() => C.assertPilotOrder(P.load(state.dir), undefined, approval), blocked);
  assert.throws(() => C.assertPilotOrder(P.load(state.dir), "F11", approval), blocked);
  await assert.rejects(() => R.render(state.dir), blocked, "render stops before opening a browser");
  const pilot = pilotOutputs(state, "F07");
  assert.throws(() => C.assertPilotOrder(pilot.p, "F11", approval), /pilot-review|ENOENT/);
  pilotReview(state, pilot, "FIX");
  assert.throws(() => C.assertPilotOrder(pilot.p, "F11", approval), /不合格/);
  pilotReview(state, pilot);
  assert.equal(C.assertPilotOrder(pilot.p, "F11", approval).reviewer, "unit-independent-reviewer");
  assert.equal(C.assertPilotOrder(pilot.p, undefined, approval).mode, "independent-reviewer-lenses");
  fs.writeFileSync(state.dir + "/out/F07/print.png", "pilot image replaced after review");
  assert.throws(() => C.assertPilotOrder(pilot.p, "F11", approval), /変わりました/);
});
test("a pilot PASS does not survive a changed prescription", t => {
  const state = ready(t, { pilot: ["F07"] }), approval = approved(state), pilot = pilotOutputs(state, "F07");
  pilotReview(state, pilot);
  // The prescription lives in analysis.json, which every variant fingerprint shares.
  const a = A.read(state.dir + "/analysis.json"); a.variants[1].nextActions.push("処方を変更して残りの案へ展開する"); A.write(state.dir + "/analysis.json", a);
  assert.throws(() => C.assertPilotOrder(P.load(state.dir), "F11", approval), /機械検査が未完了か古い/);
});
test("plans without a pilot and legacy projects keep rendering every variant", t => {
  const state = ready(t);
  assert.equal(C.assertPilotOrder(P.load(state.dir), undefined, approved(state)), null);
  assert.throws(() => C.pilotReviewTemplate(state.dir), /executionPlan/);
  const top = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-pilot-legacy-"));
  t.after(() => fs.rmSync(top, { recursive: true, force: true }));
  const legacy = fixture(top + "/project");
  assert.equal(C.assertPilotOrder(legacy, undefined, A.assertApproved(legacy.dir, legacy)), null);
});
test("renamed outputs cannot inherit a pilot by guesswork", t => {
  const state = ready(t, { renamed: true, pilot: ["F07"], edit: p => { p.brief.analysisBindings = [{ requirementId: "PRICE", feedbackId: "PRICE", variantIds: ["F01", "F02"] }]; } });
  assert.throws(() => C.assertPilotOrder(P.load(state.dir), undefined, approved(state)), /保持点.*出力案/);
});

// Preserved strengths are tied to artwork identity, independently of request scope.
function visualChecks(state) {
  const p = P.load(state.dir);
  const checks = { fingerprint: P.fingerprint(p), rows: p.scene.variants.map((v, i) => ({ id: v.id, pngSha256: String(i + 1).repeat(64) })) };
  return { p, checks };
}
function reviewedImages(state) {
  const { p, checks } = visualChecks(state), review = syntheticReview(p, checks);
  for (const item of review.items)
    for (const check of item.feedbackChecks || []) { check.verdict = "PASS"; check.criteria = ["hierarchy"]; }
  return { p, checks, review };
}
test("same-ID strengths are required in both the template and completed visual review", t => {
  const state = ready(t), { p, checks } = visualChecks(state);
  const template = D.reviewTemplate(p, checks);
  for (const item of template.items)
    assert.deepEqual(item.preservationChecks, [{ strength: item.id + "の元画像と意味群の関係を維持する", verdict: "pending", observation: "" }]);
  const { review } = reviewedImages(state);
  assert.doesNotThrow(() => D.validateReview(review, checks, p));
  const omitted = structuredClone(review); delete omitted.items[0].preservationChecks;
  assert.throws(() => D.validateReview(omitted, checks, p), /保持点.*一致/);
  const unchecked = structuredClone(review); unchecked.items[0].preservationChecks[0].verdict = "pending";
  assert.throws(() => D.validateReview(unchecked, checks, p), /保持点.*確認/);
});
test("renamed originals with strengths cannot silently lose preservation through requirement bindings", t => {
  const state = ready(t, { renamed: true, edit: p => {
    p.brief.analysisBindings = [{ requirementId: "PRICE", feedbackId: "PRICE", variantIds: ["F01", "F02"] }];
  } });
  assert.throws(() => approved(state), /保持点.*出力案/);
  const { p, checks } = visualChecks(state);
  assert.throws(() => D.reviewTemplate(p, checks), /保持点.*出力案/);
});
test("visual validation also rejects an empty preservation list on renamed outputs", t => {
  const state = ready(t), { p, checks, review } = reviewedImages(state);
  assert.doesNotThrow(() => D.validateReview(review, checks, p));
  for (let i = 0; i < p.scene.variants.length; i++) {
    const id = "F0" + (i + 1);
    p.scene.variants[i].id = id; p.concepts.variants[i].id = id;
    checks.rows[i].id = id; review.items[i].id = id;
    review.items[i].preservationChecks = [];
  }
  assert.throws(() => D.validateReview(review, checks, p), /保持点.*出力案/);
});
test("more outputs keep each original's strengths only on its matching output ID", t => {
  const state = ready(t, { edit: p => {
    const extra = structuredClone(p.scene.variants[1]); extra.id = "F12"; p.scene.variants.push(extra);
    const concept = structuredClone(p.concepts.variants[1]); concept.id = "F12"; p.concepts.variants.push(concept);
    p.brief.analysisBindings = [{ requirementId: "PRICE", feedbackId: "PRICE", variantIds: ["F07", "F11", "F12"] }];
  } });
  assert.equal(approved(state).fail, 0);
  const { p, checks } = visualChecks(state), review = D.reviewTemplate(p, checks);
  assert.equal(review.items[0].preservationChecks.length, 1);
  assert.equal(review.items[1].preservationChecks.length, 1);
  assert.equal(review.items[2].preservationChecks, undefined, "do not invent a preservation scope for a new output");
});
test("fewer outputs cannot discard an original's strengths through request-only mappings", t => {
  const state = ready(t, { edit: p => {
    p.scene.variants = p.scene.variants.slice(0, 1); p.concepts.variants = p.concepts.variants.slice(0, 1);
    p.brief.analysisBindings = [{ requirementId: "PRICE", feedbackId: "PRICE", variantIds: ["F07"] }];
  } });
  assert.throws(() => approved(state), /保持点.*F11/);
});
