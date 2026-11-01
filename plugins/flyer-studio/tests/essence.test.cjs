"use strict";
// 本質アンカー（scripts/essence.cjs）の検査。案件フォルダは一時フォルダに作る。
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const E = require("../scripts/essence.cjs");
const I = require("../scripts/intake.cjs");
const P = require("../scripts/project.cjs");
const ROOT = path.resolve(__dirname, "..");

const BASE = fs.mkdtempSync(path.join(os.tmpdir(), "flyer-essence-"));
process.on("exit", () => fs.rmSync(BASE, { recursive: true, force: true }));
let seq = 0;
const read = (dir, f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
const write = (dir, f, v) => fs.writeFileSync(path.join(dir, f), JSON.stringify(v, null, 2));
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
function caseDir(answers = ANSWERS, confirm = true) {
  const dir = path.join(BASE, "case-" + ++seq);
  P.init(dir);
  I.apply(dir, { originalRequest: REQUEST, answers });
  if (confirm) I.apply(dir, { "confirm-facts": "はい" });
  return dir;
}

test("基準は依頼文・purpose・確定事実を固定し、ハッシュで改ざんを検出できる", () => {
  const dir = caseDir();
  const r = E.baseline(dir, { request: REQUEST });
  assert.equal(r.source, "intake");
  assert.equal(r.fail, 0);
  const b = read(dir, "essence-baseline.json");
  assert.equal(b.originalRequest, REQUEST);
  assert.equal(b.purpose.audience, ANSWERS.audience);
  assert.equal(b.mustFacts["/copy/date"], ANSWERS.date);
  assert.equal(b.mustFacts["/copy/speakers"], null, "該当なしの事実は null");
  assert.match(b.sha256, /^[0-9a-f]{64}$/);
  const c = E.check(dir);
  assert.equal(c.fail, 0);
  assert.equal(c.checked, r.checked);
});

test("基準は上書きできず、未解決のヒアリングや食い違う依頼文では作らない", () => {
  const dir = caseDir();
  E.baseline(dir);
  assert.throws(() => E.baseline(dir), /上書きできません/);
  const open = caseDir({ ...ANSWERS, price: "未定" }, false);
  assert.throws(() => E.baseline(open), /ヒアリングが終わっていません/);
  assert.ok(!fs.existsSync(path.join(open, "essence-baseline.json")));
  assert.throws(() => E.baseline(caseDir(), { request: "別の依頼" }), /最初の依頼文と違います/);
  assert.throws(() => E.baseline(path.join(ROOT, "tmp-case")), /plugin/);
});

test("承認記録の無い目的や事実の変更は drift になり、承認記録があれば通る", () => {
  const dir = caseDir();
  E.baseline(dir);
  const brief = read(dir, "brief.json");
  brief.copy.time = "14:00〜15:30";
  brief.purpose.action = "電話で申し込む";
  write(dir, "brief.json", brief);
  const c = E.check(dir);
  assert.equal(c.fail, 2);
  assert.deepEqual(c.drift.map((d) => d.field).sort(), ["/copy/time", "/purpose/action"]);
  write(dir, "essence-revisions.json", [
    { at: "2027-01-10T09:00:00Z", field: "/copy/time", from: ANSWERS.time, to: "14:00〜15:00", approvedBy: "user", reason: "会場の都合" },
    { at: "2027-01-11T09:00:00Z", field: "/copy/time", from: "14:00〜15:00", to: "14:00〜15:30", approvedBy: "user", reason: "延長" },
    { at: "2027-01-11T10:00:00Z", field: "/purpose/action", from: ANSWERS.action, to: "電話で申し込む", approvedBy: "assistant", reason: "推測" },
  ]);
  const c2 = E.check(dir);
  assert.deepEqual(c2.approved, ["/copy/time"], "承認の連鎖をたどって今の値に届けば通る");
  assert.deepEqual(c2.drift.map((d) => d.field), ["/purpose/action"]);
  assert.equal(c2.ignored.length, 1, "利用者の承認でない記録は数えない");
});

test("基準ファイルを書き換えると drift になる", () => {
  const dir = caseDir();
  E.baseline(dir);
  const b = read(dir, "essence-baseline.json");
  b.purpose.audience = "誰でも";
  write(dir, "essence-baseline.json", b);
  const c = E.check(dir);
  assert.ok(c.drift.some((d) => d.field === "essence-baseline.json" && /書き換え/.test(d.reason)));
});

test("intake.json が無い旧案件は brief から基準を作り、依頼文を必須にする", () => {
  const dir = path.join(BASE, "case-" + ++seq);
  P.init(dir);
  const brief = read(dir, "brief.json");
  brief.purpose = { audience: "地域の方", benefit: "話せる", action: "申し込む" };
  write(dir, "brief.json", brief);
  assert.throws(() => E.baseline(dir), /最初の依頼文が必要です/);
  const r = E.baseline(dir, { request: REQUEST });
  assert.equal(r.source, "brief");
  assert.equal(E.check(dir).fail, 0);
});

test("clauses は本質の正本を読むだけで返す", () => {
  const ids = E.clauses().map((c) => c.id);
  for (const id of ["E1", "E2", "E3"]) assert.ok(ids.includes(id), id);
});

test("essence-revise records the user-approved change so essence-check passes again", () => {
  const dir = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "flyer-revise-")), "p");
  P.init(dir);
  const brief = JSON.parse(fs.readFileSync(dir + "/brief.json", "utf8"));
  brief.purpose = { audience: "地域の事業者", benefit: "相談先が分かる", action: "申し込む" };
  fs.writeFileSync(dir + "/brief.json", JSON.stringify(brief));
  E.baseline(dir, { request: "交流会のチラシを作りたい" });
  brief.purpose.action = "電話で問い合わせる";
  fs.writeFileSync(dir + "/brief.json", JSON.stringify(brief));
  assert.equal(E.check(dir).fail, 1);
  assert.throws(() => E.revise(dir, { field: "/purpose/action" }), /--reason/);
  assert.throws(() => E.revise(dir, { field: "/feedback", reason: "x" }), /基準にない/);
  const r = E.revise(dir, { field: "/purpose/action", reason: "利用者が電話受付に変えると承認" });
  assert.deepEqual([r.entry.from, r.entry.to], ["申し込む", "電話で問い合わせる"]);
  assert.equal(E.check(dir).fail, 0);
  assert.throws(() => E.revise(dir, { field: "/purpose/action", reason: "again" }), /同じ/);
});
