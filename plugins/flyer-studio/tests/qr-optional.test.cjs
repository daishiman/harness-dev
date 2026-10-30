"use strict";
const test = require("node:test"), assert = require("node:assert/strict"),
  fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const P = require("../scripts/project.cjs"), R = require("../scripts/render.cjs"),
  C = require("../scripts/checks.cjs"), E = require("../scripts/essence.cjs"),
  { fixture, syntheticReview } = require("./fixture.cjs");
function setup(t) {
  const top = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-no-qr-"));
  t.after(() => fs.rmSync(top, { recursive: true, force: true }));
  const dir = top + "/project", p = fixture(dir);
  return { dir, p };
}
function withoutQr(p) {
  delete p.brief.qrUrl;
  p.brief.copy.apply = "当日直接来場";
  p.brief.purpose.action = "案内を確認して当日直接来場する";
  p.brief.requiredRefs = [...new Set([...p.brief.requiredRefs, "apply"])];
  for (const v of p.scene.variants) delete v.qr;
}
function save(p) {
  for (const name of ["brief", "scene", "concepts"]) P.write(p.dir + "/" + name + ".json", p[name]);
}
test("URLがない案件は来場案内を必須掲載し、HTMLにQRを出さない", async t => {
  const { p } = setup(t);
  withoutQr(p);
  assert.equal(P.validate(p).fail, 0);
  for (const v of p.scene.variants) {
    const html = await R.html(p, v);
    assert.match(html, /当日直接来場/);
    assert.doesNotMatch(html, /class="qr(?:halo)?"/);
  }
  p.brief.qrUrl = "";
  assert.equal(P.validate(p).fail, 0, "空文字もURLなしとして扱う");
});
test("URLなしを理由に行動案内の空白・掲載漏れ・古いQR枠を通さない", t => {
  const { p } = setup(t); withoutQr(p);
  p.brief.copy.apply = " ";
  assert.ok(P.validate(p).issues.some(i => i.code === "apply-guidance"));
  p.brief.copy.apply = "当日直接来場";
  p.brief.requiredRefs = p.brief.requiredRefs.filter(ref => ref !== "apply");
  assert.ok(P.validate(p).issues.some(i => i.code === "apply-guidance"));
  p.brief.requiredRefs.push("apply");
  p.scene.variants[0].texts = p.scene.variants[0].texts.filter(text => text.ref !== "apply");
  assert.ok(P.validate(p).issues.some(i => i.code === "copy-missing" && i.id === "F07"));
  p.scene.variants[0].qr = { x: 166, y: 253, size: 32 };
  assert.ok(P.validate(p).issues.some(i => i.code === "qr-without-url"));
});
test("URLありの案件は引き続きHTTP(S)と22mm以上の全案QRを必須にする", t => {
  const { p } = setup(t);
  delete p.scene.variants[0].qr;
  assert.ok(P.validate(p).issues.some(i => i.code === "qr-frame" && i.id === "F07"));
  p.scene.variants[0].qr = { x: 166, y: 253, size: 21 };
  assert.ok(P.validate(p).issues.some(i => i.code === "qr-frame"));
  p.brief.qrUrl = "file:///private/request";
  assert.ok(P.validate(p).issues.some(i => i.code === "qr-url"));
});
test("確定した来場案内の無承認変更は本質アンカーが検出する", t => {
  const { p, dir } = setup(t); withoutQr(p); save(p);
  E.baseline(dir, { request: "予約不要で当日に直接来場できる催しを告知してください" });
  assert.equal(E.check(dir).fail, 0);
  p.brief.copy.apply = "電話予約が必要"; save(p);
  assert.ok(E.check(dir).drift.some(d => d.field === "/copy/apply"));
});
// 実PDF経路が書く納品 index と同じ関数を、PDF を作らずに既定の npm test で確かめる。
test("納品indexは白案があるときだけ白系PDFへリンクし、全案の印刷用PDFとPNGを並べる", t => {
  const { p } = setup(t); withoutQr(p);
  assert.ok(p.scene.variants.some(v => v.paper === "white") && p.scene.variants.some(v => v.paper !== "white"));
  const listsEvery = index => {
    assert.match(index, /<a href="all\.pdf">全案PDF<\/a>/);
    assert.ok(index.includes(`${p.brief.page.width}×${p.brief.page.height}mm・実際のサイズ100%`));
    for (const v of p.scene.variants) {
      assert.ok(index.includes(`<a href="${v.id}/print.pdf">印刷用PDF</a> ／ <a href="${v.id}/print.png">PNG</a>`), v.id);
      assert.ok(index.includes(`<h2>${P.esc(v.id + " " + p.concepts.variants.find(c => c.id === v.id).name)}</h2>`), v.id);
    }
  };
  const mixed = C.deliveryIndex(p);
  assert.match(mixed, /<a href="white\.pdf">白系PDF<\/a>/);
  listsEvery(mixed);
  for (const v of p.scene.variants) v.paper = "color";
  const colorOnly = C.deliveryIndex(p);
  assert.doesNotMatch(colorOnly, /white\.pdf/);
  listsEvery(colorOnly);
});
test("納品indexは案件名と案名を文字として埋め込み、HTMLとして解釈させない", t => {
  const { p } = setup(t);
  p.brief.title = `<img src=x onerror="alert(1)">&夏祭り`;
  p.concepts.variants[0].name = "<script>案</script>";
  const index = C.deliveryIndex(p);
  assert.ok(index.includes(`<title>${P.esc(p.brief.title)}</title>`) && index.includes(`<h1>${P.esc(p.brief.title)}</h1>`));
  assert.doesNotMatch(index, /<img src=x|<script>/);
});
test("実PDF経路: QRなし・白案なしでも検査と納品を通り、古い白PDFとリンクを残さない", { skip: process.env.FLYER_RUNTIME_SMOKE !== "1" }, async t => {
  const { p, dir } = setup(t); withoutQr(p);
  p.brief.whiteCount = 0;
  for (const v of p.scene.variants) v.paper = "color";
  for (const v of p.concepts.variants) v.paper = "color";
  save(p);
  E.baseline(dir, { request: "予約不要の当日来場案内を白案なしで制作してください" });
  await R.render(dir);
  for (const v of p.scene.variants) assert.equal(P.read(dir + "/out/" + v.id + "/layout.json").qr, null);
  const checks = C.verify(dir);
  assert.equal(checks.fail, 0, JSON.stringify(checks.issues));
  // The review is deliberately synthetic for this isolated regression test.
  // It is never used as an actual case's independent visual approval.
  P.write(dir + "/visual-review.json", syntheticReview(P.load(dir), checks));
  fs.writeFileSync(dir + "/out/white.pdf", "stale previous delivery");
  const delivery = C.finalize(dir);
  assert.equal(delivery.status, "complete");
  assert.equal(delivery.fail, 0);
  assert.equal(delivery.combinedReview.fail, 0);
  assert.ok(fs.statSync(dir + "/out/all.pdf").size > 1000);
  assert.equal(fs.existsSync(dir + "/out/white.pdf"), false);
  const index = fs.readFileSync(dir + "/out/index.html", "utf8");
  assert.doesNotMatch(index, /href="white\.pdf"/);
  assert.ok(index.includes(`${p.brief.page.width}×${p.brief.page.height}mm・実際のサイズ100%`));
});
