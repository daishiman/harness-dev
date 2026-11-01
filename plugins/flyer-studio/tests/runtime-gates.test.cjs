"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),os=require("node:os"),path=require("node:path");
const P=require("../scripts/project.cjs"),R=require("../scripts/render.cjs"),C=require("../scripts/checks.cjs"),A=require("../scripts/analysis.cjs"),{fixture}=require("./fixture.cjs");
function setup(t){const top=fs.mkdtempSync(path.join(os.tmpdir(),"flyer-runtime-"));t.after(()=>fs.rmSync(top,{recursive:true,force:true}));const dir=top+"/project";const p=fixture(dir);require("../scripts/essence.cjs").baseline(dir,{request:"試験用の確認済み依頼文"});return {dir,p};}
test("analysisMode decides the analysis gate for the fixture and a new init",t=>{const {dir,p}=setup(t);assert.equal(p.brief.analysisMode,"new-from-brief");assert.equal(A.assertApproved(dir,p).mode,"new-from-brief");const fresh=dir+"-new";P.init(fresh);const brief=P.read(fresh+"/brief.json");assert.equal(brief.analysisMode,"new-from-brief");assert.equal(A.assertApproved(fresh).mode,"new-from-brief");delete brief.analysisMode;P.write(fresh+"/brief.json",brief);assert.throws(()=>A.assertApproved(fresh),/analysisMode/);});
test("source-artifact production rejects missing analysis before opening a browser",async t=>{const {dir,p}=setup(t);p.brief.analysisMode="source-artifact";P.write(dir+"/brief.json",p.brief);await assert.rejects(()=>R.render(dir),/analysis.json/);assert.throws(()=>C.finalize(dir),/analysis.json/);assert.equal(P.read(dir+"/out/delivery.json").status,"pending");});
test("pending feedback blocks production",async t=>{const {dir,p}=setup(t);p.brief.feedback=[{id:"REQ01",kind:"required",request:"回答を第一主役として読みやすくする",source:{variantId:"F07",pngSha256:"a".repeat(64)},targets:["text:answer"],analysis:[{role:"typography",observation:"横回答の文字と入口の強弱を比較して確認する"}],decision:"pending",reason:"候補を比較中で採用方針が未確定のため待つ"}];P.write(dir+"/brief.json",p.brief);await assert.rejects(()=>R.render(dir),/未決/);});
test("vertical mode reaches HTML and defaults preserve horizontal writing",async t=>{const {p}=setup(t);assert.equal(P.validate(p).fail,0);const html=await R.html(p,p.scene.variants[0]);assert.match(html,/writing-mode:vertical-rl;text-orientation:mixed/);assert.match(html,/writing-mode:vertical-rl;text-orientation:upright/);assert.match(html,/writing-mode:horizontal-tb/);});
test("vertical writing without height or unsupported direction is rejected",t=>{const {p}=setup(t);delete p.scene.variants[0].texts.find(t=>t.ref==="lead").h;assert.ok(P.validate(p).fail);p.scene.variants[0].texts[0].writingMode="vertical-lr";assert.ok(P.validate(p).fail);});
// The rotation fixtures turn listen (hero group, x120 y108 w78) given h12.
const turnedBox = { x: 120, y: 108, w: 78, h: 12 };
function turn(p, id, rotation, h) {
  const text = p.scene.variants[0].texts.find(x => x.id === id);
  Object.assign(text, { h, rotation });
  return text;
}
test("文字の回転は宣言した箱の中心でCSSへ渡り、回転しない文字のHTMLは変えない", async t => {
  const { p } = setup(t), v = p.scene.variants[0];
  const before = await R.html(p, v), others = html => html.replace(/<div class="txt" data-id="listen".*?<\/div>/, "");
  assert.doesNotMatch(before, /transform|data-rotation/);
  turn(p, "listen", -8, turnedBox.h);
  assert.equal(P.validate(p).fail, 0);
  const html = await R.html(p, v);
  assert.match(html, /data-id="listen"[^>]*data-rotation="-8"[^>]*height:12mm;[^>]*transform-origin:50% 50%;transform:rotate\(-8deg\);/);
  assert.equal(html.match(/transform:/g).length, 1);
  assert.equal(others(html), others(before), "回転を書いていない文字・素材の出力は同じ");
});
test("回転の範囲外・高さ欠落・縦組・中心軸・文字以外への指定は明示エラーで止める", t => {
  const { p } = setup(t), v = p.scene.variants[0], codes = () => P.validate(p).issues.map(i => i.code);
  const listen = turn(p, "listen", 0, turnedBox.h);
  for (const rotation of [0, 90.5, -91, NaN]) {
    listen.rotation = rotation;
    assert.deepEqual(codes(), ["rotation-metric"], String(rotation));
  }
  for (const rotation of [90, -90]) {
    listen.rotation = rotation;
    assert.deepEqual(codes(), [], "向きを変える±90度までは回せる");
  }
  delete listen.h;
  assert.deepEqual(codes(), ["rotation-metric"], "回転中心を決める高さが要る");
  delete listen.rotation;
  turn(p, "lead", 8, 82);
  assert.deepEqual(codes(), ["rotation-vertical"]);
  delete turn(p, "lead", 8, 82).rotation;
  turn(p, "trio", 3, 8);
  assert.deepEqual(codes(), ["rotation-axis"], "中心軸の意味群は回転で軸を崩さない");
  delete turn(p, "trio", 3, 8).rotation;
  for (const element of [v.logo, v.qr, v.photos[0], v.protectedRegions[0]]) {
    element.rotation = 5;
    assert.deepEqual(codes(), ["unsupported-rotation"]);
    delete element.rotation;
  }
  assert.equal(P.validate(p).fail, 0);
});
test("回転後の外接矩形で、描画前に安全域外と固定要素への重なりを止める", t => {
  const { p } = setup(t), codes = () => P.validate(p).issues.map(i => i.code);
  const brand = turn(p, "brand", 5, 10);
  assert.deepEqual(codes(), ["rotation-safe"], "回転前は安全域内でも、回転で上端が出る");
  delete brand.rotation;
  const apply = turn(p, "apply", 30, 10);
  assert.deepEqual(codes(), ["rotation-collision"], "回転前はQRの上に収まっても、回転でQRに掛かる");
  apply.rotation = -2;
  assert.deepEqual(codes(), []);
});
test("回転した文字のはみ出しと不可視は、回転前の行で判定する", t => {
  const { dir, p } = setup(t), G = require("../scripts/geometry.cjs"), { PNG } = require("pngjs");
  const rotation = 30, center = { x: turnedBox.x + turnedBox.w / 2, y: turnedBox.y + turnedBox.h / 2 };
  turn(p, "listen", rotation, turnedBox.h);
  P.write(dir + "/scene.json", p.scene);
  const bounds = r => {
    const c = [[r.x, r.y], [r.x + r.w, r.y], [r.x, r.y + r.h], [r.x + r.w, r.y + r.h]].map(([x, y]) => G.rotatePoint({ x, y }, center, rotation));
    const xs = c.map(q => q.x), ys = c.map(q => q.y);
    return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
  };
  // A parseable one-page PDF keeps pdffonts/pdfinfo quiet; their verdicts are not under test.
  const objects = ["<</Type/Catalog/Pages 2 0 R>>", "<</Type/Pages/Kids[3 0 R]/Count 1>>", "<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>"];
  let blankPdf = "%PDF-1.4\n";
  const offsets = objects.map((o, i) => { const at = blankPdf.length; blankPdf += `${i + 1} 0 obj\n${o}\nendobj\n`; return at; });
  blankPdf += `xref\n0 4\n0000000000 65535 f \n${offsets.map(n => String(n).padStart(10, "0") + " 00000 n \n").join("")}trailer\n<</Size 4/Root 1 0 R>>\nstartxref\n${blankPdf.length}\n%%EOF\n`;
  // Outputs as the browser would leave them; band paints the turned line in the text color.
  const textIssues = (line, band) => {
    const out = dir + "/out/F07", png = new PNG({ width: 420, height: 594 });
    fs.mkdirSync(out, { recursive: true });
    for (let y = 0; y < png.height; y++)
      for (let x = 0; x < png.width; x++) {
        const q = G.rotatePoint({ x: (x + 0.5) / 2, y: (y + 0.5) / 2 }, center, -rotation), k = (y * png.width + x) * 4;
        png.data.fill(band && q.x >= line.x && q.x <= line.x + line.w && q.y >= line.y && q.y <= line.y + line.h ? 255 : 0, k, k + 3);
        png.data[k + 3] = 255;
      }
    for (const n of ["print.png", "browser.png", "artwork.png"]) fs.writeFileSync(out + "/" + n, PNG.sync.write(png));
    fs.writeFileSync(out + "/print.pdf", blankPdf);
    P.write(out + "/layout.json", { texts: [{ id: "listen", group: "hero", computedColor: "rgb(255, 255, 255)", frame: G.rotatedBox(turnedBox, rotation), lines: [{ text: "聞ける人が、", ...bounds(line) }], rotation, local: { frame: turnedBox, lines: [{ text: "聞ける人が、", ...line }] } }], images: [], qr: null, viewBox: true, errors: [] });
    const shas = [["print.pdf", "pdfSha256"], ["print.png", "pngSha256"], ["browser.png", "browserSha256"], ["layout.json", "layoutSha256"], ["artwork.png", "artworkSha256"]].map(([n, key]) => [key, P.sha(out + "/" + n)]);
    P.write(out + "/render.json", { variantFingerprint: P.fingerprint(P.load(dir), "F07"), ...Object.fromEntries(shas) });
    return C.verify(dir, ["F07"]).issues.filter(i => i.code.startsWith("text-")).map(i => i.code + (i.detail.includes("turned") ? ":turned" : ""));
  };
  const fits = { x: 120, y: 109, w: 60, h: 10 };
  assert.deepEqual(textIssues(fits, false), [], "背景と区別できる回転行は通る");
  assert.deepEqual(textIssues(fits, true), ["text-invisible:turned"], "外接矩形の標本は行の外の背景も拾うので、回転前の行の格子を回して見る");
  assert.deepEqual(textIssues({ x: 129, y: 107, w: 60, h: 14 }, false), ["text-overflow"], "外接矩形どうしでは収まって見えるはみ出し");
});
test("実ブラウザ: 回転した文字は外接矩形と回転前の計測を残し、検査を通る", { skip: process.env.FLYER_RUNTIME_SMOKE !== "1" }, async t => {
  const { dir, p } = setup(t), G = require("../scripts/geometry.cjs");
  turn(p, "listen", -8, turnedBox.h);
  P.write(dir + "/scene.json", p.scene);
  await R.render(dir, "F07");
  const l = P.read(dir + "/out/F07/layout.json"), turned = l.texts.find(x => x.id === "listen");
  const near = (a, b) => ["x", "y", "w", "h"].every(k => Math.abs(a[k] - b[k]) < 0.05);
  assert.ok(near(turned.frame, G.rotatedBox(turnedBox, -8)), JSON.stringify(turned.frame));
  assert.ok(near(turned.local.frame, turnedBox), JSON.stringify(turned.local.frame));
  assert.ok(l.texts.every(x => x.id === "listen" || !("local" in x || "rotation" in x)));
  const checks = C.verify(dir, ["F07"]);
  assert.equal(checks.fail, 0, JSON.stringify(checks.issues));
});
test("render frozen fingerprint rejects input changed after start",t=>{const {dir,p}=setup(t),frozen=P.fingerprint(p);assert.doesNotThrow(()=>R.assertFrozen(dir,frozen));const brief=P.read(dir+"/brief.json");brief.copy.personal+=" ";P.write(dir+"/brief.json",brief);assert.throws(()=>R.assertFrozen(dir,frozen),/描画中/);});
test("render frozen fingerprint rejects changed source bytes",t=>{const {dir,p}=setup(t),frozen=P.fingerprint(p);const e=p.assets.entries.find(e=>e.kind==="photo");fs.appendFileSync(path.join(dir,e.file),"changed");assert.throws(()=>R.assertFrozen(dir,frozen),/描画中/);});

test("baseline削除はrenderとfinalizeの前で停止しcycle台帳を変えない", async t => {
  const { dir, p } = setup(t), frozen = P.fingerprint(p);
  C.cycleStatus(dir);
  const ledger = fs.readFileSync(dir + "/cycle-ledger.json", "utf8");
  fs.rmSync(dir + "/essence-baseline.json", { force: true });
  P.write(dir + "/out/delivery.json", { status: "complete", fail: 0 });
  await assert.rejects(() => R.render(dir), /essence-baseline.json.*ありません/);
  assert.equal(P.read(dir + "/out/delivery.json").status, "pending", "描画前の停止でも旧完了記録を失効させる");
  assert.throws(() => R.assertFrozen(dir, frozen), /essence-baseline.json.*ありません/);
  assert.throws(() => C.finalize(dir), /essence-baseline.json.*ありません/);
  assert.equal(P.read(dir + "/out/delivery.json").status, "pending");
  assert.equal(fs.existsSync(dir + "/out/F07/source.html"), false, "ブラウザ描画へ進んでいない");
  assert.equal(fs.readFileSync(dir + "/cycle-ledger.json", "utf8"), ledger);
});
test("目的の無承認変更はrenderとfinalizeの前で停止する", async t => {
  const { dir, p } = setup(t);
  p.brief.purpose.action = "利用者がまだ承認していない電話申込へ変更";
  P.write(dir + "/brief.json", p.brief);
  await assert.rejects(() => R.render(dir), /本質アンカー.*\/purpose\/action/);
  assert.throws(() => C.finalize(dir), /本質アンカー.*\/purpose\/action/);
  assert.equal(fs.existsSync(dir + "/cycle-ledger.json"), false, "関門で止まった試行はcycleを増やさない");
  assert.equal(fs.existsSync(dir + "/out/F07/source.html"), false);
});
test("intakeのない旧briefは明示baseline作成後に次の制作関門へ進める", async t => {
  const { dir, p } = setup(t), E = require("../scripts/essence.cjs");
  fs.rmSync(dir + "/essence-baseline.json", { force: true });
  assert.equal(fs.existsSync(dir + "/intake.json"), false);
  await assert.rejects(() => R.render(dir), /essence-baseline/);
  assert.equal(fs.existsSync(dir + "/essence-baseline.json"), false, "基準は自動作成されない");
  E.baseline(dir, { request: "旧案件の依頼文と確定事実を確認して制作を再開する" });
  assert.equal(E.assertCurrent(dir).intakeGate, null);
  p.brief.analysisMode = "source-artifact";
  P.write(dir + "/brief.json", p.brief);
  await assert.rejects(() => R.render(dir), /analysis.json/, "明示移行後は次の分析承認関門まで進む");
  assert.throws(() => C.finalize(dir), /analysis.json/);
});
