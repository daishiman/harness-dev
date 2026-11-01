"use strict";
// 改善 cycle の台帳（cycle-ledger.json）と finalize の関門（ヒアリング → 本質アンカー → cycle 予算）、
// 再評価テンプレートの退避、案ごとの鮮度判定の検査。案件フォルダは一時フォルダに作る。
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const P = require("../scripts/project.cjs");
const D = require("../scripts/design.cjs");
const C = require("../scripts/checks.cjs");
const I = require("../scripts/intake.cjs");
const E = require("../scripts/essence.cjs");
const { fixture, syntheticReview } = require("./fixture.cjs");

const BASE = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-gates-"));
process.on("exit", () => fs.rmSync(BASE, { recursive: true, force: true }));
let seq = 0;
const fresh = () => path.join(BASE, "case-" + ++seq);
const later = (ms) => new Date(Date.now() + ms).toISOString();

function reviewed() {
  const p = fixture(fresh()),
    checks = {
      fingerprint: "a".repeat(64),
      rows: p.scene.variants.map((v, i) => ({ id: v.id, pngSha256: String(i + 1).repeat(64) })),
    };
  E.baseline(p.dir, { request: "機械関門を検査する確認済みの依頼文" });
  return { p, checks, review: syntheticReview(p, checks) };
}
const fix = (extra = {}) => ({
  text: "F07 の下部 y=216 付近で日付と質問群の間隔が狭く、元要求 R-07 の意味の切替が読めない",
  fixClass: "within-plan",
  serves: ["E2"],
  returnTo: "run-create-flyer",
  ...extra,
});
function withFix(review, value = fix(), at = later(0)) {
  const r = structuredClone(review);
  r.items[0].decision = "FIX";
  r.items[0].mandatoryFixes = [value];
  r.reviewedAt = at;
  return r;
}
// 手書きの消費済み entry。台帳の schema に合う最小の形。
const spent = (n) => ({
  cycle: n,
  at: "2026-10-2" + n + "T00:00:00Z",
  trigger: "visual-review",
  findingsDigest: String(n).repeat(64),
  renderDigest: String(n).repeat(64),
  fixClasses: { "within-plan": 1 },
  returnTo: ["run-create-flyer"],
  consumed: true,
  reason: "FIX: run-create-flyer へ戻す",
  source: { file: "reviews/c" + n + "/visual-review.json", sha256: String(n).repeat(64) },
});
const ledgerWith = (dir, n) =>
  P.write(dir + "/cycle-ledger.json", { version: 1, budget: 3, entries: Array.from({ length: n }, (_, i) => spent(i + 1)) });

test("cycleBudget は composition の revisionBudget.maxCycles と一致する", () => {
  const composition = JSON.parse(fs.readFileSync(path.join(P.ROOT, "plugin-composition.yaml"), "utf8"));
  assert.equal(D.contract.cycleBudget, composition.revisionBudget.maxCycles);
  assert.ok(Number.isInteger(D.contract.cycleBudget) && D.contract.cycleBudget >= 1);
});

test("FIX の評価は 1 cycle を消費し、同じ記録を何度読んでも・退避しても 1 件のまま", () => {
  const { p, checks, review } = reviewed();
  P.write(p.dir + "/visual-review.json", withFix(review));
  const [first] = C.recordCycles(p.dir).entries;
  assert.deepEqual(
    [first.cycle, first.consumed, first.trigger, first.fixClasses, first.returnTo, first.source.file],
    [1, true, "visual-review", { "within-plan": 1 }, ["run-create-flyer"], "visual-review.json"],
  );
  assert.equal(C.recordCycles(p.dir).entries.length, 1, "2 回目の呼び出しで増えない");
  C.renewReview(p, "visual-review.json", checks);
  assert.equal(C.recordCycles(p.dir).entries.length, 1, "退避した同じ記録を二重に数えない");
  assert.equal(P.read(p.dir + "/cycle-ledger.json").budget, D.contract.cycleBudget);
});

test("R4: 同じ所見・同じ画像の再提出と、同じ画像への追記と、好みだけの所見は消費しない", () => {
  const { p, review } = reviewed();
  const step = (value) => {
    P.write(p.dir + "/visual-review.json", value);
    return C.recordCycles(p.dir).entries.at(-1);
  };
  assert.equal(step(withFix(review, fix(), later(0))).consumed, true);
  const again = step(withFix(review, fix(), later(1000)));
  assert.deepEqual([again.consumed, again.cycle], [false, 1]);
  assert.match(again.reason, /再提出/);
  const more = step(withFix(review, fix({ text: fix().text + "。質問群の終端も詰まっている" }), later(2000)));
  assert.equal(more.consumed, false);
  assert.match(more.reason, /追記/);
  const redrawn = withFix(review, fix(), later(3000));
  redrawn.items.forEach((item, i) => (item.pngSha256 = String(i + 5).repeat(64)));
  const next = step(redrawn);
  assert.deepEqual([next.consumed, next.cycle], [true, 2], "新しい画像への FIX は次の cycle");
  const liked = structuredClone(review);
  liked.items.forEach((item, i) => (item.pngSha256 = String(i + 7).repeat(64)));
  liked.items[0].preferenceNotes = [{ text: "背景の金色をもう少し控えめにしたい好み", category: "color" }];
  liked.reviewedAt = later(4000);
  const pref = step(liked);
  assert.deepEqual([pref.consumed, pref.fixClasses, pref.returnTo], [false, { preference: 1 }, []]);
  assert.match(pref.reason, /好み/);
  const ledger = P.read(p.dir + "/cycle-ledger.json");
  assert.equal(ledger.entries.length, 5);
  assert.deepEqual(C.cycleSummary(ledger), { consumed: 2, budget: 3, remaining: 1, entries: 5, over: false });
  // 未完成の PASS 下書き（分類できない）は記録しない。FIX なら記録できないことを知らせる。
  const draft = structuredClone(liked);
  delete draft.items[0].criteria;
  draft.reviewedAt = later(5000);
  assert.equal(step(draft).source.sha256, pref.source.sha256);
  draft.items[0].decision = "FIX";
  P.write(p.dir + "/visual-review.json", draft);
  assert.throws(() => C.recordCycles(p.dir), /分類できないため cycle 台帳へ記録できません/);
});

test("退避済みの旧い形の FIX は分類なしで数え、後のコマンドを止めない", () => {
  const { p, review } = reviewed();
  const old = withFix(review, "日付の間隔を広げる（fixClass の無い旧い形）");
  P.write(p.dir + "/reviews/legacy/visual-review.json", old);
  const [entry] = C.recordCycles(p.dir).entries;
  assert.deepEqual(
    [entry.consumed, entry.fixClasses, entry.returnTo, entry.source.file],
    [true, {}, [], path.join("reviews", "legacy", "visual-review.json")],
  );
  assert.match(entry.reason, /分類できない旧い記録/);
});

test("提案評価の FIX は前提崩れと推測せず分析へ戻し、同じ予算で数える", () => {
  const { p } = reviewed();
  const evidence = "元画像の領域と要求別の分析を照合して根拠の連続を確認した";
  const analysisReview = (extra = {}) => ({
    version: 1,
    analysisSha256: "a".repeat(64),
    sourceFingerprint: "b".repeat(64),
    policyFingerprint: "c".repeat(64),
    reviewer: "independent-analysis-reviewer",
    reviewedAt: later(0),
    checks: Object.fromEntries(
      ["evidenceAlignment", "completeness", "changeDiscipline", "feasibility"].map((k) => [k, { verdict: k === "evidenceAlignment" ? "FIX" : "PASS", evidence }]),
    ),
    mandatoryFixes: [{ text: "右上の縦導入を保持する前提が分析に書かれていない", serves: ["E1"] }],
    decision: "FIX",
    returnTo: "run-analyze-flyer",
    ...extra,
  });
  P.write(p.dir + "/analysis-review.json", analysisReview());
  const [first] = C.recordCycles(p.dir).entries;
  assert.deepEqual(
    [first.trigger, first.fixClasses, first.returnTo, first.consumed, first.source.file],
    ["analysis-review", {}, ["run-analyze-flyer"], true, "analysis-review.json"],
  );
  P.write(p.dir + "/analysis-review.json", analysisReview({ reviewedAt: later(1000), mandatoryFixes: [{ text: "別の観点の追記", serves: ["E2"] }] }));
  assert.equal(C.recordCycles(p.dir).entries.at(-1).consumed, false, "同じ分析への追記は数えない");
  P.write(p.dir + "/analysis-review.json", analysisReview({ reviewedAt: later(2000), analysisSha256: "d".repeat(64) }));
  assert.deepEqual(C.cycleSummary(C.recordCycles(p.dir)).consumed, 2, "直した分析への FIX は次の cycle");
  P.write(p.dir + "/analysis-review.json", analysisReview({ reviewedAt: later(3000), returnTo: "run-create-flyer" }));
  assert.throws(() => C.recordCycles(p.dir), /run-analyze-flyer へ戻します/);
  P.write(p.dir + "/analysis-review.json", analysisReview({ decision: "PASS", returnTo: "run-create-flyer", mandatoryFixes: [], checks: Object.fromEntries(require("../scripts/analysis.cjs").CHECKS.map(k => [k, { verdict: "PASS", evidence }])) }));
  assert.equal(C.recordCycles(p.dir).entries.length, 3, "PASS の提案評価は記録しない");
});

test("台帳の形が崩れていれば止め、予算の判定は design-contract.json の値で行う", () => {
  const { p } = reviewed();
  ledgerWith(p.dir, 4);
  const tampered = P.read(p.dir + "/cycle-ledger.json");
  tampered.budget = 99;
  P.write(p.dir + "/cycle-ledger.json", tampered);
  const status = C.cycleStatus(p.dir);
  assert.deepEqual([status.consumed, status.budget, status.over, status.fail], [4, 3, true, 1]);
  delete tampered.entries[0].source;
  P.write(p.dir + "/cycle-ledger.json", tampered);
  assert.throws(() => C.recordCycles(p.dir), /cycle-ledger.json の形が不正です/);
});

test("cycle-status は台帳を作り、要約を返す", async () => {
  const { p } = reviewed();
  const log = console.log;
  console.log = () => {};
  let result;
  try {
    result = await require("../scripts/cli.cjs").main(["cycle-status", "--project", p.dir]);
  } finally {
    console.log = log;
  }
  assert.deepEqual([result.consumed, result.budget, result.remaining, result.fail], [0, 3, 3, 0]);
  assert.deepEqual(P.read(p.dir + "/cycle-ledger.json"), { version: 1, budget: 3, entries: [] });
});

test("予算を超えた finalize は INCOMPLETE を返し、納品物と古い完了記録を残さない", () => {
  const { p, review } = reviewed();
  ledgerWith(p.dir, 3);
  P.write(p.dir + "/visual-review.json", withFix(review));
  for (const name of ["all.pdf", "white.pdf", "index.html", "combined-checks.json"])
    fs.writeFileSync(p.dir + "/out/" + name, "earlier");
  P.write(p.dir + "/out/delivery.json", { status: "complete", fail: 0 });
  const receipt = C.finalize(p.dir);
  assert.equal(receipt.status, "INCOMPLETE");
  assert.equal(receipt.fail, 1);
  assert.deepEqual([receipt.cycles.consumed, receipt.cycles.budget, receipt.cycles.over], [4, 3, true]);
  assert.deepEqual(receipt.unresolved.map((u) => [u.source, u.id, u.fixClass]), [["visual-review.json", "F07", "within-plan"]]);
  assert.deepEqual(P.read(p.dir + "/out/delivery.json"), receipt);
  for (const name of ["all.pdf", "white.pdf", "index.html", "combined-checks.json"])
    assert.ok(!fs.existsSync(p.dir + "/out/" + name), name + " を残さない");
});

test("予算内なら cycle の関門を通り、後段の失敗は pending で残す", () => {
  const { p } = reviewed();
  ledgerWith(p.dir, 3);
  fs.writeFileSync(p.dir + "/out/all.pdf", "earlier");
  // 描画していない案件なので、cycle の関門の後の成果物の読み込みで止まる。
  assert.throws(() => C.finalize(p.dir), (error) => !/予算/.test(error.message));
  assert.equal(P.read(p.dir + "/out/delivery.json").status, "pending");
  assert.ok(!fs.existsSync(p.dir + "/out/all.pdf"), "失敗時も結合成果物を残さない");
});

// ---- 関門の順序: ヒアリング（a）→ 本質アンカー（b）→ cycle 予算（c）----
const REQUEST = "子育て中の方が気軽に話せる交流会のチラシを作りたい";
const ANSWERS = {
  mode: "new",
  audience: "子育て中で、平日の夜に参加できる地域の方",
  benefit: "同じ悩みを持つ人と気軽に話し、次の一歩が見つかる",
  action: "申込フォームから申し込む",
  title: "子育てトーク交流会",
  content: "少人数で子育ての悩みを話す交流会",
  speakers: "なし",
  date: "2027年3月14日（日）",
  time: "13:30〜15:00（受付 13:00）",
  venue: "市民交流センター 2階 会議室",
  address: "架空市中央1-2-3",
  price: "参加費 500円（資料代込み・税込）",
  "apply-url": "https://forms.kosodate-talk.jp/apply",
  "apply-method": ["QRからお申し込みください"],
  notice: "なし",
  "photo-source": ["none"],
  logo: "none",
  distribution: ["handout"],
  style: ["水彩"],
  "real-person-style": "no-real-people",
  "page-size": "A4 縦",
};
function hearingCase(resolved = true) {
  const dir = fresh();
  P.init(dir);
  I.apply(dir, { originalRequest: REQUEST, answers: resolved ? ANSWERS : { ...ANSWERS, price: "未定" } });
  if (resolved) I.apply(dir, { "confirm-facts": "はい" });
  ledgerWith(dir, 4);
  return dir;
}
const drift = (dir) => {
  const brief = P.read(dir + "/brief.json");
  brief.purpose.action = "電話で申し込む";
  P.write(dir + "/brief.json", brief);
};

test("未解決のヒアリングは予算超過より先に止め、INCOMPLETE にしない", () => {
  const dir = hearingCase(false);
  assert.throws(() => C.finalize(dir), /ヒアリングが終わっていません/);
  assert.equal(P.read(dir + "/out/delivery.json").status, "pending");
});

test("承認の無い本質アンカーの変更は予算超過より先に止め、ヒアリングの未解決はそれより先", () => {
  const dir = hearingCase();
  E.baseline(dir, { request: REQUEST });
  assert.equal(C.finalize(dir).status, "INCOMPLETE", "関門 a・b を通れば c で INCOMPLETE");
  drift(dir);
  assert.throws(() => C.finalize(dir), /本質アンカー（essence-baseline.json）.*\/purpose\/action/);
  assert.equal(P.read(dir + "/out/delivery.json").status, "pending");
  const intake = P.read(dir + "/intake.json");
  intake.unresolved = [...intake.unresolved, "/copy/price"];
  P.write(dir + "/intake.json", intake);
  assert.throws(() => C.finalize(dir), /ヒアリングが終わっていません/);
});

// ---- 再評価テンプレートの退避（SS-8・SS-9）----
test("review-template は前の評価を reviews/<label>/ へ退避してから作り直し、上書きしない", () => {
  const { p, checks, review } = reviewed();
  P.write(p.dir + "/visual-review.json", review);
  const before = P.sha(p.dir + "/visual-review.json");
  assert.equal(C.renewReview(p, "visual-review.json", checks), p.dir + "/visual-review.json");
  const archived = () =>
    fs.readdirSync(p.dir + "/reviews").map((label) => p.dir + "/reviews/" + label + "/visual-review.json");
  assert.deepEqual(archived().map((file) => P.sha(file)), [before]);
  const template = P.read(p.dir + "/visual-review.json");
  assert.ok(template.items.every((item) => item.reusedFrom), "変わっていない案は前回の PASS を引き継ぐ");
  C.renewReview(p, "visual-review.json", checks);
  assert.equal(archived().length, 2, "同じ時刻でも退避先を上書きしない");
  assert.ok(archived().map((file) => P.sha(file)).includes(before));
  assert.equal(C.renewReview(p, "pilot-review.json", checks), p.dir + "/pilot-review.json", "元が無ければ退避せずに作る");
});

// ---- 案ごとの鮮度（D.fingerprint(p, id)）----
function renderRecords(p, legacyIds = []) {
  for (const v of p.scene.variants) {
    const out = p.dir + "/out/" + v.id;
    P.write(out + "/layout.json", { texts: [] });
    P.write(out + "/render.json", {
      id: v.id,
      fingerprint: P.fingerprint(p),
      ...(legacyIds.includes(v.id) ? {} : { variantFingerprint: P.fingerprint(p, v.id) }),
    });
  }
}
const staleIds = (dir) =>
  C.verify(dir).issues.filter((issue) => issue.code === "stale-input").map((issue) => issue.id).sort();

test("verify は案ごとの指紋で失効を判定し、共通部分の変更は全案を失効させる", () => {
  const p = fixture(fresh());
  renderRecords(p);
  assert.deepEqual(staleIds(p.dir), []);
  const concepts = P.read(p.dir + "/concepts.json");
  concepts.variants[0].name += "（改）";
  P.write(p.dir + "/concepts.json", concepts);
  assert.deepEqual(staleIds(p.dir), ["F07"], "変えた案だけが失効する");
  renderRecords(P.load(p.dir));
  const brief = P.read(p.dir + "/brief.json");
  brief.copy.personal += " ";
  P.write(p.dir + "/brief.json", brief);
  assert.deepEqual(staleIds(p.dir), ["F07", "F11"]);
});

test("variantFingerprint の無い旧い描画記録は全体の指紋で判定する", () => {
  const p = fixture(fresh());
  renderRecords(p, ["F11"]);
  const concepts = P.read(p.dir + "/concepts.json");
  concepts.variants[0].name += "（改）";
  P.write(p.dir + "/concepts.json", concepts);
  assert.deepEqual(staleIds(p.dir), ["F07", "F11"]);
});

test("先行試作は analysisMode で判定し、試作案以外の変更では試作の PASS を失効させない", () => {
  const p0 = fixture(fresh());
  assert.equal(C.assertPilotOrder(p0, undefined, { mode: "new-from-brief" }), null, "new-from-brief に先行試作は無い");
  P.write(p0.dir + "/analysis.json", { executionPlan: { pilotVariantIds: ["F07"] } });
  const p = P.load(p0.dir),
    out = p.dir + "/out/F07";
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(out + "/print.png", "pilot-F07");
  const row = { id: "F07", variantFingerprint: P.fingerprint(p, "F07"), pngSha256: P.sha(out + "/print.png") };
  P.write(out + "/render.json", {
    id: "F07",
    fingerprint: P.fingerprint(p),
    variantFingerprint: row.variantFingerprint,
    pngSha256: row.pngSha256,
    createdAt: new Date(Date.now() - 60000).toISOString(),
  });
  const checks = { fingerprint: P.fingerprint(p), rows: [row], issues: [], fail: 0 };
  P.write(p.dir + "/out/pilot-checks.json", checks);
  P.write(p.dir + "/pilot-review.json", syntheticReview(p, checks));
  const approval = { mode: "source-artifact" };
  assert.equal(C.assertPilotOrder(p, "F07", approval), null, "試作案だけの描画は先に進める");
  assert.equal(C.assertPilotOrder(p, undefined, approval).reviewer, "unit-independent-reviewer");
  const concepts = P.read(p.dir + "/concepts.json");
  concepts.variants[1].name += "（改）";
  P.write(p.dir + "/concepts.json", concepts);
  assert.ok(C.assertPilotOrder(P.load(p.dir), undefined, approval), "F11 の変更は F07 の試作 PASS を失効させない");
  concepts.variants[0].name += "（改）";
  P.write(p.dir + "/concepts.json", concepts);
  assert.throws(() => C.assertPilotOrder(P.load(p.dir), undefined, approval), /機械検査が未完了か古い/);
});

test("premise を intake へ返す正規FIXは台帳再読込と退避・再開でも1 cycleを保つ", () => {
  const { p, checks, review } = reviewed();
  P.write(p.dir + "/visual-review.json", withFix(review, fix({ fixClass: "premise", returnTo: "run-intake-flyer" })));
  const ledger = C.recordCycles(p.dir);
  assert.deepEqual([ledger.entries[0].fixClasses, ledger.entries[0].returnTo, ledger.entries[0].cycle], [{ premise: 1 }, ["run-intake-flyer"], 1]);
  assert.deepEqual(C.recordCycles(p.dir), ledger, "保存した台帳を読み直してもschema違反にならず重複しない");
  C.renewReview(p, "visual-review.json", checks);
  assert.deepEqual(C.cycleSummary(C.recordCycles(p.dir)), { consumed: 1, budget: D.contract.cycleBudget, remaining: D.contract.cycleBudget - 1, entries: 1, over: false });
  assert.equal(fs.readdirSync(p.dir + "/reviews").length, 1, "評価を退避した後も再開できる");
});
