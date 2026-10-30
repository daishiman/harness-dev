"use strict";
const test = require("node:test"),
  assert = require("node:assert/strict");
const fs = require("node:fs"),
  path = require("node:path"),
  os = require("node:os");
const P = require("../scripts/project.cjs"),
  { fixture } = require("./fixture.cjs");
function project() {
  return fixture(
    path.join(
      fs.mkdtempSync(path.join(os.tmpdir(), "flyer-design-")),
      "project",
    ),
  );
}
test("配置・配色・余白の設計意図がない案を描画契約で拒否", () => {
  const p = project();
  delete p.concepts.variants[0].designIntent;
  assert.ok(P.validate(p).fail > 0);
});
test("無関係なsignature追加キーで構図差を水増しできない", () => {
  const p = project();
  p.concepts.variants[1].signature = { ...p.concepts.variants[0].signature };
  Object.assign(p.concepts.variants[0].signature, {
    padding1: "差分",
    padding2: "差分",
    padding3: "差分",
  });
  assert.ok(P.validate(p).fail > 0);
});
const D = require("../scripts/design.cjs"),
  C = require("../scripts/checks.cjs");
const { syntheticReview } = require("./fixture.cjs");
function reviewed() {
  const p = project(),
    checks = {
      fingerprint: "a".repeat(64),
      rows: p.scene.variants.map((v, i) => ({
        id: v.id,
        pngSha256: String(i + 1).repeat(64),
      })),
    };
  return { p, checks, review: syntheticReview(p, checks) };
}
function badIntent(mutate, code) {
  const p = project();
  mutate(p);
  assert.ok(P.validate(p).issues.some((issue) => issue.code === code));
}
test("読み順と群の配置理由は実在する全群を指す", () => {
  badIntent(
    (p) => p.concepts.variants[0].designIntent.readingOrder.pop(),
    "intent-reading-order",
  );
  badIntent(
    (p) =>
      (p.concepts.variants[0].designIntent.groups[0].group = "nonexistent"),
    "intent-groups",
  );
});
test("宣言した文字色の理由と紙面内の余白領域が必要", () => {
  badIntent(
    (p) => (p.scene.variants[0].texts[0].color = "#FF0000"),
    "intent-palette",
  );
  badIntent(
    (p) => (p.concepts.variants[0].designIntent.whitespace[0].w = 300),
    "intent-whitespace",
  );
});
test("全必須文字を透明にしても掲載済みとは扱わない", () => {
  badIntent(
    (p) =>
      p.scene.variants[0].texts.forEach((text) => (text.color = "transparent")),
    "text-invisible",
  );
  badIntent(
    (p) => (p.scene.variants[0].ink = "rgba(255,255,255,0)"),
    "text-invisible",
  );
});
test("独立レビュアーの具体的な5観点と3レンズ参照を受理", () => {
  const { p, checks, review } = reviewed();
  assert.doesNotThrow(() => C.validateReview(review, checks, p));
});
test("観点欠落・一言OK・不正な設計参照・紙面外の証拠を拒否", () => {
  for (const mutate of [
    (r) => {
      delete r.items[0].criteria.balance;
    },
    (r) => {
      r.items[0].criteria.spacing.observation = "OK";
    },
    (r) => {
      r.items[0].criteria.color.intentRef = "/balanceReason";
    },
    (r) => {
      r.items[0].criteria.spacing.intentRef = "/whitespace/99";
    },
    (r) => {
      r.items[0].criteria.integration.region.x = 500;
    },
    (r) => {
      r.items[0].expertReviews.composition.criteria = ["balance"];
    },
  ]) {
    const { p, checks, review } = reviewed();
    mutate(review);
    assert.throws(() => C.validateReview(review, checks, p));
  }
});
test("画像を見ず全案へ同じ所見を複写する台帳を拒否", () => {
  const { p, checks, review } = reviewed();
  review.items[1].criteria.balance.observation =
    review.items[0].criteria.balance.observation;
  assert.throws(() => C.validateReview(review, checks, p), /同文/);
  const second = reviewed();
  second.review.items[1].criteria.balance.observation =
    "F11:" + second.review.items[0].criteria.balance.observation;
  assert.throws(
    () => C.validateReview(second.review, second.checks, second.p),
    /同文/,
  );
});
test("自己レビューと制作担当のidentity別名空白だけの変更を拒否", () => {
  for (const mutate of [
    (r) => {
      r.mode = "self-review";
    },
    (r) => {
      r.reviewer = " FIXTURE-AUTHOR ";
    },
    (r) => {
      r.items[0].expertReviews.color.reviewer = "fixture-author";
    },
  ]) {
    const { p, checks, review } = reviewed();
    mutate(review);
    assert.throws(() => C.validateReview(review, checks, p), /独立|制作担当/);
  }
});
test("3専門担当のmodeは3人、知見レンズmodeは同一独立reviewerを要求", () => {
  const { p, checks, review } = reviewed();
  review.mode = "independent-agents";
  assert.throws(() => C.validateReview(review, checks, p), /別のidentity/);
  review.items.forEach((item) =>
    D.contract.expertRoles.forEach(
      (role) => (item.expertReviews[role].reviewer = "independent-" + role),
    ),
  );
  assert.doesNotThrow(() => C.validateReview(review, checks, p));
  review.mode = "independent-reviewer-lenses";
  assert.throws(() => C.validateReview(review, checks, p), /正直/);
});
test("画像のSHAだけでなく品質基準の旧判定も拒否", () => {
  const { p, checks, review } = reviewed();
  review.reviewPolicyFingerprint = "0".repeat(64);
  assert.throws(() => C.validateReview(review, checks, p), /古い/);
  const current = syntheticReview(p, checks);
  current.items[0].pngSha256 = "f".repeat(64);
  assert.throws(() => C.validateReview(current, checks, p), /不合格/);
});

test("制作目的の読者・価値・行動は欠落や空白のまま進めない", () => {
  const missing = project();
  delete missing.brief.purpose;
  assert.ok(
    P.validate(missing).issues.some((issue) => issue.code === "schema-brief"),
  );
  const { prompts } = require("../scripts/cli.cjs");
  for (const key of ["audience", "benefit", "action"]) {
    const p = project();
    p.brief.purpose ||= {
      audience: "対象読者",
      benefit: "提供する価値",
      action: "してほしい行動",
    };
    p.brief.purpose[key] = "  \n ";
    assert.ok(
      P.validate(p).issues.some((issue) => issue.code === "schema-brief"),
    );
    P.write(p.dir + "/brief.json", p.brief);
    assert.throws(() => prompts(p.dir), /目的/);
    assert.equal(fs.existsSync(p.dir + "/prompts"), false);
  }
});

test("新規・presetとも目的は今回の回答を入れる空欄で初期化", () => {
  for (const preset of [undefined, "hyogo"]) {
    const dir = path.join(
      fs.mkdtempSync(path.join(os.tmpdir(), "flyer-purpose-init-")),
      "project",
    );
    P.init(dir, preset);
    assert.deepEqual(P.load(dir).brief.purpose, {
      audience: "",
      benefit: "",
      action: "",
    });
  }
});

test("別用途の目的3点が背景指示へ実値で反映される", () => {
  const p = project();
  const { prompts } = require("../scripts/cli.cjs");
  const purposes = [
    {
      audience: "会社のAI導入を進める担当者",
      benefit: "実例と質問から自社で始める着手点を理解する",
      action: "Peatixから交流会へ申し込む",
    },
    {
      audience: "地域の親子で自然観察を楽しみたい人",
      benefit: "川辺の生き物を観察して身近な自然を知る",
      action: "公民館の窓口で自然観察会へ申し込む",
    },
  ];
  const outputs = purposes.map((purpose) => {
    p.brief.purpose = purpose;
    P.write(p.dir + "/brief.json", p.brief);
    const result = prompts(p.dir);
    const output = fs.readFileSync(
      path.join(p.dir, result.items[0].file),
      "utf8",
    );
    for (const value of Object.values(purpose))
      assert.ok(output.includes(value));
    return output;
  });
  assert.notEqual(outputs[0], outputs[1]);
  for (const value of Object.values(purposes[0]))
    assert.equal(outputs[1].includes(value), false);
  assert.equal(
    P.validate(P.load(p.dir)).fail,
    0,
    "会社向け以外の目的も受け入れる",
  );
});

// ---- 必須修正の分類（R1）----
const withFix = (review, fix, decision = "FIX") => {
  review.items[0].decision = decision;
  review.items[0].mandatoryFixes = [fix];
  return review;
};
const fix = (extra = {}) => ({
  text: "F07 の下部 y=216 付近で日付と質問群の間隔が狭く、元要求 R-07 の意味の切替が読めない",
  fixClass: "within-plan",
  serves: ["E2"],
  returnTo: "run-create-flyer",
  ...extra,
});
test("必須修正は分類・本質条項・戻り先を持ち、FIX の案は合格にならない", () => {
  const { p, checks, review } = reviewed();
  withFix(review, fix());
  assert.deepEqual(D.classifyFixes(review), {
    fixClasses: { "within-plan": 1 },
    returnTo: ["run-create-flyer"],
    fixCount: 1,
    preferenceNotes: 0,
  });
  assert.throws(() => C.validateReview(review, checks, p), /不合格/);
  const premise = withFix(reviewed().review, fix({ fixClass: "premise", returnTo: "run-intake-flyer", serves: ["E1", "E4"] }));
  assert.deepEqual(D.classifyFixes(premise).returnTo, ["run-intake-flyer"]);
});
test("好み・戻り先の取り違え・本質条項に無い serves・形の崩れた必須修正を拒否", () => {
  for (const [mutate, pattern] of [
    [(r) => withFix(r, fix({ fixClass: "preference" })), /好み（preference）/],
    [(r) => withFix(r, fix({ fixClass: "premise" })), /戻り先が分類と一致しません/],
    [(r) => withFix(r, fix({ fixClass: "deterministic", returnTo: "run-analyze-flyer" })), /戻り先/],
    [(r) => withFix(r, fix({ serves: ["E9"] })), /本質条項/],
    [(r) => withFix(r, fix({ serves: [] })), /目視レビュー契約/],
    [(r) => withFix(r, "日付の間隔を広げる"), /目視レビュー契約/],
    [(r) => withFix(r, fix(), "PASS"), /FIX の案には/],
    [(r) => (r.items[0].decision = "FIX"), /FIX の案には/],
    [(r) => (r.items[0].preferenceNotes = [{ text: "もう少し温かい色が好み", category: "mood" }]), /category/],
  ]) {
    const { p, checks, review } = reviewed();
    mutate(review);
    assert.throws(() => C.validateReview(review, checks, p), pattern);
  }
});
test("好みは preferenceNotes に残しても合格を妨げない", () => {
  const { p, checks, review } = reviewed();
  review.items[0].preferenceNotes = [
    { text: "背景の金色をもう少し控えめにしたい好み", category: "color" },
    { text: "分類しない好みの記録" },
  ];
  assert.equal(D.classifyFixes(review).preferenceNotes, 2);
  assert.doesNotThrow(() => C.validateReview(review, checks, p));
});
test("fixRouting は workflow.md の改善と納品の表と一致する", () => {
  const doc = fs.readFileSync(path.join(P.ROOT, "references/workflow.md"), "utf8");
  const table = doc.slice(doc.indexOf("## 改善と納品"));
  const rows = Object.fromEntries(
    [...table.matchAll(/^\| ([a-z-]+) \|[^|]*\| ([^|]+) \|/gm)].map((m) => [m[1], m[2]]),
  );
  assert.deepEqual(Object.keys(rows).sort(), [...Object.keys(D.contract.fixRouting).filter((k) => k !== "notes"), "preference"].sort());
  for (const [fixClass, returnTo] of Object.entries(D.contract.fixRouting))
    if (fixClass !== "notes") assert.equal(rows[fixClass].match(/run-[a-z-]+/)?.[0], returnTo, fixClass);
  assert.equal(/run-[a-z-]+/.test(rows.preference), false, "preference は記録のみ");
});
test("FIX の revision 辺と、cycle を消費しない差し戻し（nonFixReturns）は混ざらない", () => {
  const comp = JSON.parse(fs.readFileSync(path.join(P.ROOT, "references", "registry.json"), "utf8"));
  const skills = new Set(comp.capabilities.filter((c) => c.kind === "skill").map((c) => c.ref));
  const fixClasses = Object.keys(D.contract.fixRouting).filter((k) => k !== "notes");
  const section = (ref) => {
    const [file, heading] = ref.split("#");
    const doc = fs.readFileSync(path.join(P.ROOT, file), "utf8");
    // 見出しの深さを読み、同じ深さ以上の次の見出しまでを節とする（### 局面カタログ は ### ゴールシーク配線 の前で終わる）。
    const m = new RegExp(`^(#+) ${heading}$`, "m").exec(doc);
    assert.ok(m, ref);
    const body = m.index + m[0].length;
    const end = doc.slice(body).search(new RegExp(`^#{1,${m[1].length}} `, "m"));
    return end < 0 ? doc.slice(m.index) : doc.slice(m.index, body + end);
  };
  const revisions = comp.dependencies.filter((d) => d.type === "revision");
  for (const d of revisions) assert.equal(d.to, `skills/${D.contract.fixRouting[d.fixClass]}`, `revision 辺は FIX だけ: ${d.fixClass}`);
  assert.ok(comp.dependencies.every((d) => !("consumesCycle" in d) && !("trigger" in d)), "非FIXの差し戻しは dependencies に置かない");
  assert.ok(comp.nonFixReturns.length > 0);
  for (const r of comp.nonFixReturns) {
    assert.equal("fixClass" in r, false, r.trigger);
    assert.equal(r.consumesCycle, false, r.trigger);
    assert.ok(![...fixClasses, "preference"].includes(r.trigger), r.trigger);
    assert.ok(skills.has(r.from) && skills.has(r.to) && r.step.startsWith(`${r.to}/`), r.trigger);
    const n = section(r.step).match(new RegExp(`^(\\d+)\\. \\*\\*${r.stepTitle}\\*\\*`, "m"))?.[1];
    assert.ok(n, `戻り先の局面が実在する: ${r.stepTitle}`);
    const base = path.posix.dirname(r.source.split("#")[0]);
    const links = [...section(r.source).matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)].filter((m) => path.posix.join(base, m[2]) === r.step);
    assert.ok(links.some((m) => m[1].endsWith(`局面 ${n}`)), `source が戻り先の局面番号（${n}）を指す`);
    for (const d of revisions) assert.ok(![r.stepTitle, `局面 ${n}`, "消費しない"].some((w) => d.condition.includes(w)), "revision 辺の条件に非FIXの用途を書かない");
  }
});
test("skill の feedback_contract.max_iterations は goal_seek.max_loops と揃い、どちらも cycleBudget の写し", () => {
  const dir = path.join(P.ROOT, "skills");
  for (const name of fs.readdirSync(dir).filter((n) => fs.existsSync(path.join(dir, n, "SKILL.md")))) {
    const fm = fs.readFileSync(path.join(dir, name, "SKILL.md"), "utf8").split(/^---$/m)[1];
    const scalar = (block, key) => fm.match(new RegExp(`^${block}:\\n(?:[ \\t].*\\n)*?[ \\t]+${key}: (\\d+)$`, "m"))?.[1];
    const iterations = scalar("feedback_contract", "max_iterations");
    assert.equal(iterations, scalar("goal_seek", "max_loops"), name);
    if (iterations) assert.equal(Number(iterations), D.contract.cycleBudget, name);
  }
});

// ---- 専門役は昇格時だけ（MD-11）----
function bare(review) {
  for (const item of review.items) item.expertReviews = {};
  return review;
}
const lens = (review, role) => ({
  reviewer: review.reviewer,
  verdict: "PASS",
  criteria: [...D.contract.expertDimensions[role]],
});
test("昇格条件に当たらない案は専門役なしで合格し、テンプレートも専門役を出さない", () => {
  const { p, checks, review } = reviewed();
  assert.doesNotThrow(() => C.validateReview(bare(review), checks, p));
  assert.ok(D.reviewTemplate(p, checks).items.every((item) => Object.keys(item.expertReviews).length === 0));
  review.items[0].expertReviews = { unknown: lens(review, "color") };
  assert.throws(() => C.validateReview(review, checks, p), /未知の専門知見レンズ/);
});
test("確信度 low の観点はその担当の専門役を必須にする", () => {
  const { p, checks, review } = reviewed();
  bare(review).items[0].criteria.integration.confidence = "low";
  assert.throws(() => C.validateReview(review, checks, p), /昇格条件.*F07\/color/);
  review.items[0].expertReviews.color = lens(review, "color");
  assert.doesNotThrow(() => C.validateReview(review, checks, p));
});
test("利用者が指定した専門役は全案で必須、未知の役名は拒否", () => {
  const { p, checks } = reviewed();
  p.brief.requestedExpertRoles = ["typography"];
  const review = syntheticReview(p, checks);
  assert.throws(() => C.validateReview(bare(review), checks, p), /typography/);
  assert.ok(D.reviewTemplate(p, checks).items.every((item) => Object.keys(item.expertReviews).join() === "typography"));
  for (const item of review.items) item.expertReviews.typography = lens(review, "typography");
  assert.doesNotThrow(() => C.validateReview(review, checks, p));
  p.brief.requestedExpertRoles = ["layout"];
  assert.throws(() => D.reviewTemplate(p, checks), /未知の専門役/);
  assert.throws(() => D.requiredExperts(p, review.items[0], []), /未知の専門役/);
});
test("前回 FIX が出た観点は次のレビューで担当の専門役を必須にする", () => {
  const { p, checks, review } = reviewed();
  const failed = structuredClone(review);
  failed.items[0].criteria.hierarchy.verdict = "FIX";
  withFix(failed, fix());
  P.write(p.dir + "/visual-review.json", failed);
  assert.equal(D.archiveReview(p, "visual-review.json", "cycle-1"), "reviews/cycle-1/visual-review.json");
  assert.deepEqual(D.requiredExperts(p, review.items[0], D.reviewHistory(p)), ["typography"]);
  assert.deepEqual(D.requiredExperts(p, review.items[1], D.reviewHistory(p)), []);
  assert.throws(() => C.validateReview(bare(review), checks, p), /F07\/typography/);
});

// ---- 実見の時刻と丸写し（SS-8）----
function rendered(p, id, pngSha256, createdAt = new Date(Date.now() - 1000).toISOString()) {
  P.write(p.dir + "/out/" + id + "/render.json", { id, pngSha256, createdAt });
}
test("描画より前の実見と、描画記録と違う画像のレビューを拒否", () => {
  const { p, checks, review } = reviewed();
  rendered(p, "F07", checks.rows[0].pngSha256, new Date(Date.now() + 60000).toISOString());
  assert.throws(() => C.validateReview(review, checks, p), /描画より前/);
  rendered(p, "F07", "e".repeat(64));
  assert.throws(() => C.validateReview(review, checks, p), /描画記録/);
  fs.rmSync(p.dir + "/out/F07/render.json");
  assert.throws(() => C.validateReview(review, checks, p), /描画記録/);
});
test("前の画像の観察文を新しい画像へ写したレビューを拒否", () => {
  const { p, checks, review } = reviewed();
  P.write(p.dir + "/visual-review.json", review);
  D.archiveReview(p, "visual-review.json", "cycle-1");
  checks.rows[0].pngSha256 = "9".repeat(64);
  rendered(p, "F07", checks.rows[0].pngSha256);
  const copied = syntheticReview(p, checks);
  assert.throws(() => C.validateReview(copied, checks, p), /転記/);
  copied.items[0].observations = "再描画後の F07 では下部の日付群が質問群から離れ、切替の余白が読めるようになった";
  assert.throws(() => C.validateReview(copied, checks, p), /転記/, "5 観点すべてが同文でも転記");
  copied.items[0].criteria.spacing.observation = "再描画後は質問群の終端から日付までが群の中の行間より広く、意味の切替として読める";
  assert.doesNotThrow(() => C.validateReview(copied, checks, p));
});

// ---- 案ごとの指紋と再利用（SS-1・R4）----
function archived() {
  const ctx = reviewed();
  assert.doesNotThrow(() => C.validateReview(ctx.review, ctx.checks, ctx.p));
  P.write(ctx.p.dir + "/visual-review.json", ctx.review);
  D.archiveReview(ctx.p, "visual-review.json", "cycle-1");
  return ctx;
}
const fill = (template, reviewer = "second-independent-reviewer") =>
  Object.assign(template, { reviewer, reviewedAt: new Date().toISOString() });
test("入力・画像・規範が同じ案は前回の独立 PASS を引き継ぐ", () => {
  const { p, checks, review } = archived();
  const next = fill(D.reviewTemplate(p, checks));
  for (const [i, item] of next.items.entries()) {
    assert.deepEqual(item.reusedFrom.file, "reviews/cycle-1/visual-review.json");
    const { reusedFrom, ...own } = item;
    assert.deepEqual(own, review.items[i]);
  }
  assert.deepEqual(C.validateReview(next, checks, p).reusedItems, ["F07", "F11"]);
  // A chain points at the original, not at the review that reused it.
  P.write(p.dir + "/visual-review.json", next);
  D.archiveReview(p, "visual-review.json", "cycle-2");
  const third = fill(D.reviewTemplate(p, checks), "third-independent-reviewer");
  assert.equal(third.items[0].reusedFrom.file, "reviews/cycle-1/visual-review.json");
  assert.doesNotThrow(() => C.validateReview(third, checks, p));
  // Archiving the source again moves it; the reuse still resolves by content.
  fs.renameSync(p.dir + "/reviews/cycle-1", p.dir + "/reviews/cycle-0");
  assert.doesNotThrow(() => C.validateReview(third, checks, p));
});
test("1案だけ変えるとその案だけ失効し、共通部分を変えると全案が失効する", () => {
  const { p, checks, review } = archived();
  const before = P.fingerprints(p);
  p.scene.variants[1].fields[0].opacity = 0.97;
  P.write(p.dir + "/scene.json", p.scene);
  const changed = P.load(p.dir);
  const after = P.fingerprints(changed);
  assert.equal(after.common, before.common);
  assert.equal(after.variants.F07, before.variants.F07);
  assert.notEqual(after.variants.F11, before.variants.F11);
  assert.throws(() => C.validateReview(review, checks, changed), /F11/);
  const next = D.reviewTemplate(changed, checks);
  assert.ok(next.items[0].reusedFrom);
  assert.equal(next.items[1].reusedFrom, undefined);
  assert.equal(next.items[1].decision, "pending");
  changed.brief.title += " ";
  const common = P.fingerprints(changed);
  assert.notEqual(common.common, after.common);
  assert.ok(Object.keys(common.variants).every((id) => common.variants[id] !== after.variants[id]));
  assert.ok(D.reviewTemplate(changed, checks).items.every((item) => !item.reusedFrom));
});
test("書き換えた再利用・画像の違う再利用・存在しない元への再利用を拒否", () => {
  for (const [mutate, pattern] of [
    [(r) => (r.items[0].observations += "（追記）"), /再利用/],
    [(r) => (r.items[0].reusedFrom.sha256 = "0".repeat(64)), /再利用/],
    [(r, p) => fs.rmSync(p.dir + "/reviews/cycle-1/visual-review.json"), /再利用/],
  ]) {
    const { p, checks } = archived();
    const next = fill(D.reviewTemplate(p, checks));
    mutate(next, p);
    assert.throws(() => C.validateReview(next, checks, p), pattern);
  }
  const { p, checks } = archived();
  const forged = fill(D.reviewTemplate(p, checks));
  forged.items[0].pngSha256 = checks.rows[0].pngSha256 = "8".repeat(64);
  assert.throws(() => C.validateReview(forged, checks, p), /再利用|描画記録/);
});
test("退避は既存の退避を上書きしない", () => {
  const { p, review } = archived();
  P.write(p.dir + "/visual-review.json", review);
  assert.throws(() => D.archiveReview(p, "visual-review.json", "cycle-1"), /退避先/);
  assert.throws(() => D.archiveReview(p, "brief.json", "cycle-9"), /退避できる/);
  assert.equal(D.archiveReview(p, "pilot-review.json", "cycle-9"), null);
});
