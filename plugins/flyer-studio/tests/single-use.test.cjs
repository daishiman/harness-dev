"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const P = require("../scripts/project.cjs");
const { fixture } = require("./fixture.cjs");
function setup(t, refs = ["price"]) {
  const top = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-single-use-"));
  t.after(() => fs.rmSync(top, { recursive: true, force: true }));
  const p = fixture(path.join(top, "project"));
  p.brief.policy.maxChars = 300;
  p.brief.singleUseRefs = refs;
  return p;
}
function addLiteral(p, value, id = "literalCopy") {
  p.scene.variants[0].texts.push({ id, text: value, x: 12, y: 285, w: 186, size: 8.5, font: "sans", align: "left", group: "hero" });
}
function codes(p) { return P.validate(p).issues.map(issue => issue.code); }

test("single-use rejects a second selected ref even under a larger legitimate character limit", t => {
  const p = setup(t), original = p.scene.variants[0].texts.find(text => text.ref === "price");
  p.scene.variants[0].texts.push({ ...original, id: "priceAgain" });
  const result = codes(p);
  assert.ok(result.includes("single-use-count"));
  assert.ok(!result.includes("copy-volume"));
});
test("single-use rejects a direct literal reprint of a selected value", t => {
  const p = setup(t); addLiteral(p, "参加料金は " + p.brief.copy.price);
  assert.ok(codes(p).includes("single-use-literal"));
});
test("single-use rejects two copies inside one directly authored block", t => {
  const p = setup(t); addLiteral(p, [p.brief.copy.price, p.brief.copy.price]);
  assert.ok(codes(p).includes("single-use-literal"));
});
test("single-use matches Unicode compatibility normalization and whitespace variants", t => {
  const p = setup(t); addLiteral(p, "食事込み　３，３００円（ 税込 ）");
  assert.ok(codes(p).includes("single-use-literal"));
});
test("selected ref must occur exactly once even when a literal supplies its words", t => {
  const p = setup(t), price = p.scene.variants[0].texts.find(text => text.ref === "price");
  delete price.ref; price.text = p.brief.copy.price;
  assert.ok(codes(p).includes("single-use-count"));
});
test("single-use array values are one logical group across their own lines", t => {
  const p = setup(t, ["apply"]); assert.equal(P.validate(p).fail, 0);
  addLiteral(p, p.brief.copy.apply.join("\n"));
  assert.ok(codes(p).includes("single-use-literal"));
});
test("name-list matching does not count a short name within another name", t => {
  const p = setup(t, ["speakers"]); p.brief.copy.speakers = ["山田", "山田太郎"];
  addLiteral(p, "山田太郎さんの紹介");
  assert.equal(P.validate(p).fail, 0);
});
test("unknown and ambiguous short selected values give configuration errors", t => {
  const p = setup(t, ["missing"]); assert.ok(codes(p).includes("single-use-ref"));
  p.brief.singleUseRefs = ["price"]; p.brief.copy.price = "無料";
  assert.ok(codes(p).includes("single-use-value"));
});
test("legacy briefs and intentional unselected repetition remain compatible", t => {
  const p = setup(t); delete p.brief.singleUseRefs;
  addLiteral(p, p.brief.copy.price); assert.equal(P.validate(p).fail, 0);
  p.brief.singleUseRefs = []; assert.equal(P.validate(p).fail, 0);
  p.brief.singleUseRefs = ["date"]; assert.equal(P.validate(p).fail, 0);
});
test("Hyogo preset selects factual groups and copies without changing date, fee or QR action", t => {
  const p = setup(t); const preset = P.read(P.ROOT + "/references/presets/hyogo-ai/brief.example.json");
  assert.ok(preset.singleUseRefs.includes("price"));
  assert.ok(preset.singleUseRefs.includes("question1"));
  assert.ok(preset.singleUseRefs.includes("date"));
  assert.ok(preset.singleUseRefs.includes("answer"));
  assert.equal(preset.copy.date, "2026年12月6日（日）");
  assert.equal(preset.copy.price, "食事込み 3,300円（税込）");
  assert.deepEqual(preset.copy.apply, ["詳細・お申し込み", "QRコードから"]);
});
