"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const P = require("../scripts/project.cjs");
const D = require("../scripts/design.cjs");
const { fixture, syntheticReview } = require("./fixture.cjs");
function feedback(overrides = {}) {
  return {
    id: "hero-strength",
    kind: "required",
    request: "ここにいる。を、まずここへ。より強く見せる",
    source: { variantId: "F07", pngSha256: "f".repeat(64) },
    variantIds: ["F07"],
    targets: ["text:answer"],
    analysis: [
      {
        role: "typography",
        observation:
          "元画像では上段の誘導コピーが強く、回答の主題が後から見えるため階層の見直しが必要",
      },
    ],
    decision: "apply",
    reason:
      "利用者が回答コピーを主役に指定しており、読者の理解順をその意図へ合わせるため採用する",
    change:
      "回答コピーの大きさと太さ、周囲の余白を見直し、誘導コピーより先に見える構成へ変える",
    ...overrides,
  };
}
function project(entries) {
  const p = fixture(
    path.join(
      fs.mkdtempSync(path.join(os.tmpdir(), "flyer-feedback-")),
      "project",
    ),
  );
  if (entries !== undefined) p.brief.feedback = entries;
  return p;
}
function reviewed(entries) {
  const p = project(entries);
  const checks = {
    fingerprint: "a".repeat(64),
    rows: p.scene.variants.map((v, i) => ({
      id: v.id,
      pngSha256: String(i + 1).repeat(64),
    })),
  };
  const review = syntheticReview(p, checks);
  for (const item of review.items) {
    if (item.feedbackChecks)
      for (const check of item.feedbackChecks)
        Object.assign(check, { verdict: "PASS", criteria: ["hierarchy"] });
  }
  return { p, checks, review };
}
test("feedbackのない従来案件は新しい要求台帳なしで通る", () => {
  const { p, checks, review } = reviewed();
  assert.equal(P.validate(p).fail, 0);
  assert.doesNotThrow(() => D.validateReview(review, checks, p));
});
test("元画像・対象要素・分析・採否理由と適用意図を要求ごとに記録する", () => {
  assert.equal(P.validate(project([feedback()])).fail, 0);
  for (const mutate of [
    (entry) => {
      delete entry.source.pngSha256;
    },
    (entry) => {
      entry.targets = ["text:missing"];
    },
    (entry) => {
      entry.variantIds = ["missing"];
    },
    (entry) => {
      entry.analysis[0].role = "new-duplicate-agent";
    },
    (entry) => {
      entry.reason = " ";
    },
    (entry) => {
      delete entry.change;
    },
  ]) {
    const entry = feedback();
    mutate(entry);
    assert.ok(P.validate(project([entry])).fail > 0);
  }
});
test("明示必須指示の見送りを拒否し、具体的根拠のある維持と提案見送りは許可", () => {
  assert.ok(P.validate(project([feedback({ decision: "decline" })])).fail > 0);
  for (const entry of [
    feedback({
      decision: "preserve",
      reason:
        "元画像の下部軸は既に全幅中央に揃っており、周辺の構成を変えてもこの良い配置を維持する",
    }),
    feedback({
      kind: "proposal",
      decision: "decline",
      reason:
        "提案された強調色は写真と主題の色と競合するため、元の文字色を維持して階層は余白で調整する",
    }),
  ]) {
    const { p, checks, review } = reviewed([entry]);
    assert.equal(P.validate(p).fail, 0);
    assert.doesNotThrow(() => D.validateReview(review, checks, p));
  }
});
test("各対象案で要求別の最終評価と既存criteria証拠の参照を必須にする", () => {
  const base = reviewed([feedback()]);
  assert.doesNotThrow(() => D.validateReview(base.review, base.checks, base.p));
  assert.deepEqual(
    base.review.items[0].feedbackChecks.map((check) => check.feedbackId),
    ["hero-strength"],
  );
  assert.equal(base.review.items[1].feedbackChecks?.length || 0, 0);
  for (const mutate of [
    (r) => {
      delete r.items[0].feedbackChecks;
    },
    (r) => {
      r.items[0].feedbackChecks[0].verdict = "pending";
    },
    (r) => {
      r.items[0].feedbackChecks[0].criteria = ["missing"];
    },
    (r) => {
      r.items[0].feedbackChecks[0].criteria = ["color"];
    },
    (r) => {
      r.items[0].feedbackChecks.push(r.items[0].feedbackChecks[0]);
    },
    (r) => {
      r.items[1].feedbackChecks = r.items[0].feedbackChecks;
    },
  ]) {
    const { p, checks, review } = reviewed([feedback()]);
    mutate(review);
    assert.throws(() => D.validateReview(review, checks, p));
  }
});
test("対象省略とallは全案を評価し、未決の要求は完成しない", () => {
  for (const variantIds of [undefined, "all"]) {
    const entry = feedback();
    if (variantIds === undefined) delete entry.variantIds;
    else entry.variantIds = variantIds;
    const { p, checks, review } = reviewed([entry]);
    assert.ok(review.items.every((item) => item.feedbackChecks?.length === 1));
    assert.doesNotThrow(() => D.validateReview(review, checks, p));
  }
  const { p, checks, review } = reviewed([feedback({ decision: "pending" })]);
  assert.throws(() => D.validateReview(review, checks, p), /未決|未解決/);
});
test("維持は元画像と同じSHAでも評価でき、要求変更後の旧レビューは使えない", () => {
  const entry = feedback({
    decision: "preserve",
    source: { variantId: "F07", pngSha256: "1".repeat(64) },
  });
  const { p, checks, review } = reviewed([entry]);
  assert.doesNotThrow(() => D.validateReview(review, checks, p));
  const before = P.fingerprint(p);
  p.brief.feedback[0].request += "。文字の周囲の余白も確認する";
  const after = P.fingerprint(p);
  assert.notEqual(before, after);
  assert.throws(
    () => D.validateReview(review, { ...checks, fingerprint: after }, p),
    /古い/,
  );
});
