"use strict";
const test = require("node:test"),
  assert = require("node:assert/strict"),
  fs = require("node:fs"),
  cp = require("node:child_process"),
  path = require("node:path");
const P = require("../scripts/project.cjs"),
  C = require("../scripts/checks.cjs");
const dir = process.env.FLYER_ACCEPTANCE_PROJECT;
test("実際のPDF/PNGを使う完了・鮮度・目視の受入試験", { skip: !dir }, () => {
  assert.equal(C.verify(dir).fail, 0, "最新描画は検査を通る");
  const review = fs.readFileSync(dir + "/visual-review.json");
  fs.renameSync(
    dir + "/visual-review.json",
    dir + "/visual-review.acceptance-backup",
  );
  try {
    assert.throws(
      () => C.finalize(dir),
      /visual-review/,
      "未実見の完成扱いは禁止",
    );
  } finally {
    fs.renameSync(
      dir + "/visual-review.acceptance-backup",
      dir + "/visual-review.json",
    );
  }
  const brief = fs.readFileSync(dir + "/brief.json");
  try {
    const b = JSON.parse(brief);
    b.copy.personal += " ";
    P.write(dir + "/brief.json", b);
    const v = C.verify(dir);
    assert.ok(v.issues.some((i) => i.code === "stale-input"));
  } finally {
    fs.writeFileSync(dir + "/brief.json", brief);
  }
  const id = P.load(dir).scene.variants[0].id,
    file = dir + "/out/" + id + "/print.png",
    png = fs.readFileSync(file);
  try {
    fs.appendFileSync(file, "tampered");
    const v = C.verify(dir);
    assert.ok(v.issues.some((i) => i.code === "stale-output"));
  } finally {
    fs.writeFileSync(file, png);
  }
  try {
    const r = JSON.parse(review);
    r.items[0].pngSha256 = "0".repeat(64);
    P.write(dir + "/visual-review.json", r);
    assert.throws(() => C.finalize(dir), /目視レビュー不合格/);
  } finally {
    fs.writeFileSync(dir + "/visual-review.json", review);
  }
  for (const key of [
    "viewedFull",
    "viewedDetails",
    "privacyChecked",
    "axisChecked",
    "worldviewChecked",
  ]) {
    try {
      const r = JSON.parse(review);
      r.items[0][key] = "false";
      P.write(dir + "/visual-review.json", r);
      assert.throws(
        () => C.finalize(dir),
        /目視レビュー/,
        key + "は厳密なtrueのみ",
      );
    } finally {
      fs.writeFileSync(dir + "/visual-review.json", review);
    }
  }
  for (const mutate of [
    (value) => {
      delete value.items[0].criteria.balance;
    },
    (value) => {
      value.items[0].criteria.spacing.observation = "OK";
    },
    (value) => {
      value.items[0].criteria.color.intentRef = "/missing";
    },
    (value) => {
      value.reviewPolicyFingerprint = "0".repeat(64);
    },
    (value) => {
      value.reviewer = P.load(dir).brief.designer;
    },
    (value) => {
      value.mode = "self-review";
    },
  ]) {
    try {
      const value = JSON.parse(review);
      mutate(value);
      P.write(dir + "/visual-review.json", value);
      assert.throws(() => C.finalize(dir));
      assert.equal(P.read(dir + "/out/delivery.json").status, "pending");
    } finally {
      fs.writeFileSync(dir + "/visual-review.json", review);
    }
  }
  // The real merger runs first; an independent Node child then changes the
  // case while finalize still holds its original in-memory project/review.
  // Pixel equality alone cannot catch either the brief or reviewer mutation.
  const originalExec = cp.execFileSync;
  const lateFile = dir + "/out/late-comparison.acceptance.txt";
  const lateBefore = fs.existsSync(lateFile) ? fs.readFileSync(lateFile) : null;
  function duringMerge(mode, fn) {
    let changed = false;
    cp.execFileSync = function (tool, args, options) {
      const result = originalExec.call(cp, tool, args, options);
      if (!changed && tool === process.execPath && path.basename(args[0] || "") === "merge-pdf.cjs") {
        changed = true;
        originalExec.call(cp, process.execPath, ["-e", `
          const fs=require('node:fs'), dir=process.argv[1], mode=process.argv[2];
          if(mode==='brief') { const f=dir+'/brief.json', b=JSON.parse(fs.readFileSync(f)); b.copy.personal+=' '; fs.writeFileSync(f,JSON.stringify(b)); }
          if(mode==='review') fs.appendFileSync(dir+'/visual-review.json','\\n');
          if(mode==='artifact') fs.writeFileSync(dir+'/out/late-comparison.acceptance.txt','independent comparison');
        `, dir, mode], { stdio: "pipe" });
      }
      return result;
    };
    try {
      const result = fn();
      assert.equal(changed, true, "actual merge child was intercepted");
      return result;
    } finally {
      cp.execFileSync = originalExec;
    }
  }
  for (const mode of ["brief", "review"]) {
    try {
      duringMerge(mode, () => assert.throws(() => C.finalize(dir), /完了検査中/));
      assert.equal(P.read(dir + "/out/delivery.json").status, "pending");
    } finally {
      fs.writeFileSync(dir + "/brief.json", brief);
      fs.writeFileSync(dir + "/visual-review.json", review);
    }
  }
  let delivery;
  try {
    delivery = duringMerge("artifact", () => C.finalize(dir));
  } finally {
    if (lateBefore) fs.writeFileSync(lateFile, lateBefore);
    else fs.rmSync(lateFile, { force: true });
  }
  assert.equal(delivery.status, "complete");
  assert.equal(delivery.fail, 0);
  assert.equal(delivery.combinedReview.fail, 0);
  assert.equal(
    delivery.reviewPolicyFingerprint,
    require("../scripts/design.cjs").reviewPolicyFingerprint(),
  );
  assert.ok(fs.statSync(dir + "/out/all.pdf").size > 1000);
  assert.ok(fs.statSync(dir + "/out/white.pdf").size > 1000);
  assert.equal(P.sha(dir + "/out/all.pdf"), delivery.combinedSha256);
});
